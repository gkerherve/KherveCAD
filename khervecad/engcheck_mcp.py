"""The window-side half of the engineering checks (mcp_tools.py is past
its size): sharp edges, fits / clearances and the tolerance stack-up,
for both the MCP tools and the Analyse windows (engcheck_dialog.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import edgecheck, fitcheck, mesh


class CheckError(Exception):
    pass


_SKIP = ("variables", "masters", "assign")


def scope_parts(window):
    """The visible parts of the scope the user is in."""
    comp = window.builder.isolated_component()
    root = comp if comp is not None else window.model.root
    return [n for n in root.children if n.visible and n.type not in _SKIP]


def local_tris(window, node):
    """The node's solid in its own frame (a fillet's children) — the
    frame a fillet node's seeds live in."""
    from . import bake
    env = bake._codegen_env(node)
    fn = window.model.effective_fn()
    mesh._set_fn(fn)
    try:
        if node.type == "fillet":
            return [t for t, _c, _s in mesh._children_mesh(
                node, env, None, frozenset(), False)]
        return mesh.tessellate(node, env=env, fn=fn)
    finally:
        mesh._set_fn(None)


# ── sharp edges ────────────────────────────────────────────────────
def sharp_report(window, nodes, face_angle=edgecheck.DEFAULT_FACE_ANGLE,
                 concave=False):
    """The world-mesh report for *nodes* plus, per node, the LOCAL fillet
    seeds of its sharp convex edges (what fillet_edges takes)."""
    from .analysis_dialog import part_tris
    tris, approx = part_tris(window, nodes)
    report = edgecheck.sharp_edges(tris, face_angle, concave)
    report["approximate"] = approx
    report["per_node"] = [
        dict(node_id=n.id, name=n.name,
             fillet_seeds=edgecheck.local_seeds(local_tris(window, n),
                                                face_angle))
        for n in nodes]
    return report


def fillet_sharp(window, nodes, radius=0.5, face_angle=
                 edgecheck.DEFAULT_FACE_ANGLE, kind="round"):
    """Wrap each node in a fillet node holding its sharp edges (a node
    already in a fillet adds them to it). One undo step from a window
    action; returns the fillet nodes."""
    model = window.model
    made = []
    for n in nodes:
        target = n if n.type == "fillet" else (
            n.parent if n.parent is not None and n.parent.type == "fillet"
            else None)
        seeds = edgecheck.local_seeds(local_tris(window, target or n),
                                      face_angle)
        if not seeds:
            continue
        if target is None:
            target = model.wrap_nodes([n], "fillet")
        have = [list(r) for r in (target.params.get("edges") or [])]
        for s in seeds:
            if not any(all(abs(a - b) < 1e-3 for a, b in zip(s, h))
                       for h in have):
                have.append(s)
        target.params["edges"] = have
        target.params["radius"] = float(radius)
        target.params["kind"] = kind
        model.node_changed.emit(target)
        made.append(target)
    return made


def note_on_blueprint(window, text=edgecheck.NOTE_TEXT):
    """Put a general note on the open (or a new) Blueprint sheet, bottom
    left of the drawing area."""
    from . import blueprint_mcp
    st = blueprint_mcp.run(window, {"action": "state"})
    left, _top, _right, bottom = st["usable_rect_mm"]
    return blueprint_mcp.run(window, {"action": "add", "notes": [
        {"type": "text", "text": text, "size": 3.5,
         "x": left + 6.0, "y": bottom - 8.0}]})


# ── fits ───────────────────────────────────────────────────────────
def mated_pairs(nodes):
    names = {n.name for n in nodes}
    out = []
    for n in nodes:
        mate = n.params.get("mate") or {}
        if mate.get("parent") in names:
            out.append((n.name, mate["parent"]))
    return out


def fit_report(window, nodes, wanted=fitcheck.DEFAULT_CLEARANCE,
               near=fitcheck.DEFAULT_NEAR):
    from .analysis_dialog import part_tris
    parts, approx = [], False
    for n in nodes:
        tris, a = part_tris(window, [n])
        approx = approx or a
        parts.append((n.name, tris))
    report = fitcheck.clearances(parts, wanted, near, mated_pairs(nodes))
    ids = {n.name: n.id for n in nodes}
    for p in report["pairs"]:
        p["a_id"], p["b_id"] = ids.get(p["a"]), ids.get(p["b"])
    report["approximate"] = approx
    return report


def sheet_notes(model, drawing=None):
    """The saved notes of the assembly sheet, or of one Object's own
    drawing."""
    if drawing and drawing.lower() != "assembly":
        state = (getattr(model, "part_drawings", None) or {}).get(drawing)
        if state is None:
            raise CheckError(f"no drawing of {drawing!r}; drawing_set "
                             "list names them")
    else:
        state = model.drawing
    if not state:
        raise CheckError("There is no Blueprint yet — open File > "
                         "Blueprint (or the blueprint tool) and give "
                         "dimensions tolerances first.")
    return state.get("notes") or []


# ── MCP bodies ─────────────────────────────────────────────────────
def _nodes(ex, params):
    ids = params.get("node_ids")
    nodes = ex._nodes(ids) if ids else scope_parts(ex._w)
    if not nodes:
        raise CheckError("Nothing to check — the scope is empty.")
    return nodes


def mcp_sharp(ex, params):
    nodes = _nodes(ex, params)
    angle = float(params.get("face_angle") or edgecheck.DEFAULT_FACE_ANGLE)
    report = sharp_report(ex._w, nodes, angle,
                          bool(params.get("concave")))
    if params.get("highlight"):
        ex._w.view3d.set_highlight_mesh(report["tris"])
    chains = report["chains"]
    out = {k: report[k] for k in ("status", "count", "length", "message",
                                  "face_angle", "per_node", "approximate")}
    out["nodes"] = [n.id for n in nodes]
    out["chains"] = chains[:edgecheck.MAX_LISTED]
    if len(chains) > edgecheck.MAX_LISTED:
        out["chains_listed"] = edgecheck.MAX_LISTED
    if report["count"]:
        out["fix"] = ("Round them: fillet_edges with node_id and edges = "
                      "that node's fillet_seeds (radius 0.5 is a "
                      "deburr). Or keep them and note it on the drawing: "
                      "blueprint add {type: 'text', text: '"
                      + edgecheck.NOTE_TEXT + "'}.")
    return out


def mcp_fits(ex, params):
    nodes = _nodes(ex, params)
    if len(nodes) < 2:
        raise CheckError("Give at least two parts (or have two visible "
                         "in the scope).")
    report = fit_report(
        ex._w, nodes,
        float(params.get("clearance", fitcheck.DEFAULT_CLEARANCE)),
        float(params.get("near", fitcheck.DEFAULT_NEAR)))
    if params.get("nominal") is not None and \
            params.get("diametral_clearance") is not None:
        report["fit"] = fitcheck.classify(float(params["nominal"]),
                                          float(params[
                                              "diametral_clearance"]))
    report["nodes"] = [n.id for n in nodes]
    report["unit"] = ex._w.model.unit
    return report


def mcp_stackup(ex, params):
    blueprint = getattr(ex._w, "_blueprint", None)
    if blueprint is not None and hasattr(blueprint, "flush_pending"):
        blueprint.flush_pending()
    notes = sheet_notes(ex._w.model, params.get("drawing"))
    try:
        report = fitcheck.stackup(notes, params.get("chain"),
                                  params.get("limits"))
    except (ValueError, KeyError, TypeError) as exc:
        raise CheckError(str(exc))
    report["dimensions"] = [
        dict(index=i, kind=n.get("kind"), nominal=round(
            fitcheck.dim_value(n), 4), tol_plus=n.get("tol_plus", ""),
             tol_minus=n.get("tol_minus", ""))
        for i, n in fitcheck.dimensions(notes)]
    return report
