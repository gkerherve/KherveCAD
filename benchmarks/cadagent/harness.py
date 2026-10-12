"""Run a language-model agent on the benchmark through KherveCAD's MCP tools.

    python -m benchmarks.cadagent.harness --validate
    python -m benchmarks.cadagent.harness --model gemma4:12b --reps 2

The model talks to a real (offscreen) KherveCAD window through the same
`McpToolExecutor` an MCP client reaches, so what is measured is the
tool interface itself. Three conditions:

    C0  code once: one apply_code call, no feedback.
    C1  + seeing: apply_code again, read the tree and code, render_view.
    C2  + measuring: also mass_properties, get_node_bounds,
        check_printability, check_interference, probe_surface, measure.

Results go to results/<model>.jsonl, one line per run.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PyQt5.QtCore import QEvent  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv[:1])

from khervecad import analysis, csg, mcp_schema, mesh  # noqa: E402
from khervecad.mainwindow import MainWindow  # noqa: E402
from khervecad.mcp_tools import McpToolExecutor  # noqa: E402

from benchmarks.cadagent.tasks import FRAME, TASKS  # noqa: E402

OUT = Path(__file__).resolve().parent / "results"
OLLAMA = "http://localhost:11434/api/chat"
BUDGET = 12                       # tool calls per run (C1, C2)
SEE = ["apply_code", "get_code", "list_tree", "render_view"]
MEASURE = ["mass_properties", "get_node_bounds", "check_printability",
           "check_interference", "probe_surface", "measure"]
TOOLS = {"C0": ["apply_code"], "C1": SEE, "C2": SEE + MEASURE}

SYSTEM = """You are a CAD engineer working in KherveCAD, whose document \
compiles to OpenSCAD. Build the part the user asks for by calling \
apply_code with an OpenSCAD program (it replaces the whole document each \
time). Use exact dimensions. Make each separate part its own OpenSCAD \
module (it becomes an Object) and call it to place it. {extra} When you are finished, reply with the \
single word DONE and no tool call."""

EXTRA = {
    "C0": "You have exactly one apply_code call, with no feedback, so get "
          "it right first time.",
    "C1": "You may look at your result with render_view and read it back "
          "with list_tree or get_code, then correct it.",
    "C2": "You may look at your result with render_view, and measure it: "
          "get_node_bounds and mass_properties for sizes, probe_surface "
          "to test whether a point is solid, check_printability and "
          "check_interference. Check every requirement before you finish.",
}


# ------------------------------------------------------------ window
def settle(seconds=0.2):
    t = time.time()
    while time.time() - t < seconds:
        app.processEvents()
        app.sendPostedEvents(None, QEvent.DeferredDelete)
        time.sleep(0.005)


class Bench:
    def __init__(self):
        self.win = MainWindow()
        self.win.resize(1200, 800)
        self.win.show()
        settle(1)
        self.ex = McpToolExecutor(self.win)

    def call(self, name, args):
        try:
            out = self.ex.execute(name, dict(args))
        except Exception as e:          # ToolError and anything else
            out = {"error": str(e)}
        settle(0.3)
        return out

    def reset(self):
        self.call("new_document", {"discard_unsaved_changes": True})

    def parts(self):
        root = self.win.model.root
        return [n for n in root.children if n.visible
                and n.type not in ("variables", "masters", "assign")]

    # -------------------------------------------------------- checks
    def solids(self):
        """The geometry as Manifold solids: one per top-level part (its
        pieces unioned), and the union of everything. Separate overlapping
        primitives are one solid, as a slicer would print them."""
        fn = self.win.model.effective_fn()
        per = []
        for n in self.parts():
            rows = [(t, None, False) for t in mesh.tessellate(n, fn=fn)]
            solid = csg.to_manifold(rows, {}) if rows else None
            per.append((n.name, solid, len(rows)))
        good = [s for _, s, _ in per if s is not None]
        whole = None
        if good:
            whole = good[0] if len(good) == 1 else \
                csg._m.Manifold.batch_boolean(good, csg._m.OpType.Add)
        return per, whole

    def evaluate(self, task, ref_volume=None):
        per, whole = self.solids()
        open_parts = any(s is None and k for _, s, k in per)
        tris = csg.to_triangles(whole) if whole is not None else []
        results = []
        for check in task["checks"]:
            kind = check[0]
            ok = False
            try:
                if not tris:
                    ok = False
                elif kind == "box":
                    lo, hi = analysis.bounds(tris)
                    tol = check[3]
                    ok = all(abs(lo[i] - check[1][i]) <= tol and
                             abs(hi[i] - check[2][i]) <= tol
                             for i in range(3))
                elif kind in ("solid", "empty"):
                    inside = analysis.point_inside(check[1], tris)
                    ok = inside == (kind == "solid")
                elif kind == "volume":
                    ok = ref_volume is not None and abs(
                        whole.volume() - ref_volume) <= check[1] * ref_volume
                elif kind == "watertight":
                    ok = not open_parts and analysis.watertight(tris)["ok"]
                elif kind in ("overhang", "min_wall"):
                    rep = analysis.print_check(
                        tris, overhang_deg=check[1] if kind == "overhang"
                        else 45, min_wall=check[1] if kind == "min_wall"
                        else 0.8)
                    ok = _status(rep, "overhang" if kind == "overhang"
                                 else "thin_walls") == "pass"
                elif kind == "parts":
                    ok = sum(len(s.decompose()) for _, s, _ in per
                             if s is not None) >= check[1]
                elif kind == "clear":
                    sol = [s for _, s, _ in per if s is not None]
                    ok = len(sol) >= 2 and all(
                        (sol[i] ^ sol[j]).volume() < 1e-3
                        for i in range(len(sol))
                        for j in range(i + 1, len(sol)))
            except Exception as e:
                ok = False
                check = tuple(check) + (f"error: {e}",)
            results.append({"check": list(check), "ok": bool(ok)})
        volume = whole.volume() if whole is not None else 0.0
        return results, volume


def _contact(pair):
    """Parts resting face to face (a lid on its box) touch; they do not
    intersect. Their overlap box is flat in one axis."""
    lo, hi = pair.get("overlap_min"), pair.get("overlap_max")
    return (pair["status"] == "intersect" and lo is not None and
            min(hi[i] - lo[i] for i in range(3)) < 0.05)


def _status(report, key):
    """The status of one check in an analysis.print_check report."""
    name = {"overhang": "Overhangs", "thin_walls": "Wall thickness"}[key]
    for entry in report.get("checks", []):
        if entry.get("name") == name:
            return entry.get("status")
    return None


# ------------------------------------------------------------ model
def tool_specs(names):
    by = {t["name"]: t for t in mcp_schema.TOOLS}
    specs = []
    for n in names:
        t = by[n]
        schema = json.loads(json.dumps(t["input_schema"]))
        if n == "apply_code":
            schema["properties"] = {"code": schema["properties"]["code"]}
            schema["required"] = ["code"]
        specs.append({"type": "function", "function": {
            "name": n, "description": t["description"][:600],
            "parameters": schema}})
    return specs


def chat(model, messages, tools, seed):
    body = json.dumps({"model": model, "messages": messages,
                       "tools": tools, "stream": False, "think": False,
                       "options": {"temperature": 0.2, "seed": seed,
                                   "num_ctx": 8192}}).encode()
    req = urllib.request.Request(OLLAMA, body,
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.loads(r.read())["message"]


def run(bench, model, task, cond, seed, ref_volume):
    bench.reset()
    names = TOOLS[cond]
    tools = tool_specs(names)
    messages = [{"role": "system",
                 "content": SYSTEM.format(extra=EXTRA[cond])},
                {"role": "user", "content": FRAME + " " + task["brief"]}]
    calls, used = 0, []
    start = time.time()
    budget = 1 if cond == "C0" else BUDGET
    done = False
    for _turn in range(BUDGET + 4):
        try:
            msg = chat(model, messages, tools, seed)
        except Exception as e:
            used.append({"error": f"model: {e}"})
            break
        messages.append({k: msg[k] for k in ("role", "content",
                                             "tool_calls") if k in msg})
        tcs = msg.get("tool_calls") or []
        if not tcs:
            break
        for tc in tcs:
            fn = tc["function"]
            name, args = fn["name"], fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {}
            if name not in names:
                out = {"error": f"Unknown tool {name}."}
            else:
                if name == "apply_code":
                    args = {"code": args.get("code", ""), "mode": "replace"}
                if name == "render_view":
                    args = {**args, "max_width": 512, "fit": True,
                            "wait_for_exact": False}
                out = bench.call(name, args)
                calls += 1
            used.append(name)
            reply = {"role": "tool", "content": ""}
            if isinstance(out, dict) and out.get("image_png_base64"):
                reply["images"] = [out.pop("image_png_base64")]
            reply["content"] = json.dumps(out, default=str)[:3000]
            messages.append(reply)
            if calls >= budget:
                done = True
                break
        if done:
            break
    elapsed = time.time() - start
    checks, volume = bench.evaluate(task, ref_volume)
    code = bench.call("get_code", {}).get("code", "")
    return {"model": model, "task": task["id"], "tier": task["tier"],
            "condition": cond, "seed": seed, "calls": calls,
            "tools": used, "seconds": round(elapsed, 1),
            "success": all(c["ok"] for c in checks),
            "passed": sum(c["ok"] for c in checks), "of": len(checks),
            "checks": checks, "volume": round(volume, 2),
            "ref_volume": ref_volume, "code": code[:6000]}


# ------------------------------------------------------------ driver
def references(bench):
    """Apply every reference program; the checks must all pass on it."""
    refs, bad = {}, []
    for task in TASKS:
        bench.reset()
        out = bench.call("apply_code", {"code": task["ref"],
                                        "mode": "replace"})
        _, volume = bench.evaluate(task, None)
        checks, _ = bench.evaluate(task, volume)
        refs[task["id"]] = round(volume, 3)
        failed = [c["check"] for c in checks if not c["ok"]]
        if failed or "error" in out:
            bad.append((task["id"], failed, out.get("error")))
        print(f"{task['id']:16s} V={volume:10.1f}  "
              f"{'OK' if not failed else 'FAIL ' + str(failed)}")
    return refs, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--model", default="gemma4:12b")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--tasks", nargs="*")
    ap.add_argument("--conditions", nargs="*", default=["C0", "C1", "C2"])
    a = ap.parse_args()
    bench = Bench()
    refs, bad = references(bench)
    if a.validate:
        print("bad:", bad)
        sys.stdout.flush()
        os._exit(1 if bad else 0)
    OUT.mkdir(exist_ok=True)
    path = OUT / (a.model.replace(":", "_").replace("/", "_") + ".jsonl")
    done = set()
    if path.exists():
        for line in path.read_text().splitlines():
            r = json.loads(line)
            done.add((r["task"], r["condition"], r["seed"]))
    tasks = [t for t in TASKS if not a.tasks or t["id"] in a.tasks]
    with path.open("a") as f:
        for seed in range(1, a.reps + 1):
            for task in tasks:
                for cond in a.conditions:
                    if (task["id"], cond, seed) in done:
                        continue
                    r = run(bench, a.model, task, cond, seed,
                            refs[task["id"]])
                    f.write(json.dumps(r) + "\n")
                    f.flush()
                    print(f"{task['id']:16s} {cond} s{seed} "
                          f"{'PASS' if r['success'] else 'fail'} "
                          f"{r['passed']}/{r['of']} calls={r['calls']} "
                          f"{r['seconds']}s", flush=True)
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
