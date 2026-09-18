"""Setting a model MOVING from outside — the body of the MCP
`play_motion` tool (mcp_tools.py is past its size): pick the motion
slider, or give a part a spin of its own, and press the Customizer's
▶ so the user watches it go.

A model moves through an annotated document variable (`angle = 0;
// [0:5:360]`) that reaches its parts' placement; the Customizer panel
shows it as a slider whose ▶ sweeps it back and forth. `pick` finds the
one that means motion when none is named — a slider in a Motion or Time
group (every mechanism and orrery puts its driver there), else one
called angle / days / time / spin…, else the only one. `add_spin`
makes a still part turn: a `<part>_spin` variable in a Motion group,
added to the part's own rz, so "make the Earth rotate" works on a
globe that had no motion at all.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import re

from . import customizer
from .model import CadNode, module_name

#: Customizer groups whose sliders drive motion ("Crank & piston ·
#: Motion", "Earth & its moons · Time")
MOTION_GROUPS = ("motion", "time", "animation")
#: names a motion variable goes by (after its prefix: solar_days)
MOTION_NAMES = ("angle", "days", "time", "t", "spin", "turn", "rotation",
                "phase", "frame", "travel", "position", "crank", "motor")
#: the range a new spin variable sweeps: a full turn in 2° notches, one
#: turn every ~11 s at the panel's 60 ms tick
SPIN_OPTIONS = "0:2:360"
#: node types that carry their own rz (a placement the spin adds to)
SPINNABLE = ("component", "union", "reference")


class MotionError(ValueError):
    """Nothing to play, or an ambiguous request: the message says what
    to do instead."""


def sliders(model) -> list:
    """The document's slider variables, in document order."""
    from .customizer_panel import annotated
    out = []
    for node in annotated(model):
        spec = customizer.widget(node)
        if spec and spec.get("kind") == "slider":
            out.append(node)
    return out


def _variable(node) -> str:
    return str(node.params.get("variable", ""))


def _is_motion_name(name: str) -> bool:
    last = name.lower().rsplit("_", 1)[-1]
    return last in MOTION_NAMES or name.lower() in MOTION_NAMES


def pick(model, name=None):
    """The slider to play: *name* exactly, or ending in "_<name>"
    (days finds earth_days); else the model's motion slider."""
    found = sliders(model)
    if not found:
        raise MotionError(
            "Nothing to play: the document has no slider variable. Make "
            "the motion first — an annotated variable such as "
            "`angle = 0;  // [0:5:360]` used in the moving parts' "
            "placement — or pass `spin` with a part's id to make that "
            "part turn.")
    if name:
        exact = [n for n in found if _variable(n) == name]
        if exact:
            return exact[0]
        tail = [n for n in found if _variable(n).endswith("_" + name)]
        if len(tail) == 1:
            return tail[0]
        known = ", ".join(_variable(n) for n in found)
        if tail:
            raise MotionError(f"{name!r} matches several sliders: "
                              f"{', '.join(_variable(n) for n in tail)}.")
        raise MotionError(f"No slider called {name!r}. The sliders are: "
                          f"{known}.")
    grouped = [n for n in found
               if any(g in str(customizer.group_of(n) or "").lower()
                      for g in MOTION_GROUPS)]
    for pool in (grouped, found):
        named = [n for n in pool if _is_motion_name(_variable(n))]
        if named:
            return named[0]
    if grouped:
        return grouped[0]
    if len(found) == 1:
        return found[0]
    raise MotionError(
        "Which one moves it? The sliders are: "
        + ", ".join(_variable(n) for n in found)
        + ". Pass `variable`.")


def add_spin(model, part) -> CadNode:
    """Make *part* turn about its own Z: a `<part>_spin` slider
    (0-360°, Motion group) added to its rz. Returns the variable. A part
    that already spins by one keeps it."""
    if part.type not in SPINNABLE:
        raise MotionError(
            f"{part.name!r} is a {part.type}; spin a part — the Object, "
            "instance or group that holds it (list_tree shows which).")
    rz = str(part.params.get("rz", 0) or 0).strip()
    for node in sliders(model):
        if re.search(rf"\b{re.escape(_variable(node))}\b", rz):
            return node                        # it spins already
    taken = {_variable(n) for n in model.global_assigns()}
    base = module_name(part.name or "part").lower().strip("_") or "part"
    var, k = f"{base}_spin", 1
    while var in taken:
        k += 1
        var = f"{base}_spin{k}"
    assign = CadNode("assign", f"{var} =", dict(
        variable=var, value="0", options=SPIN_OPTIONS,
        description=f"Turns {part.name} about its own axis — press play "
                    "to spin it",
        group="Motion"))
    target = next((c for c in model.root.children
                   if c.type == "variables"), None)
    if target is not None:
        target.add(assign)
    else:
        model.root.add(assign, 0)
    turned = var if rz in ("", "0", "0.0") else f"({rz}) + {var}"
    model.set_param(part, "rz", turned)
    model.structure_changed.emit()
    return assign


def _panel(window):
    panel = getattr(window, "_customizer", None)
    if panel is None:
        raise MotionError("This window has no Customizer panel.")
    return panel


def play(window, params) -> dict:
    """The MCP play_motion tool: start (or, with play false, stop) the
    sweep. Returns what plays, its range and how long a sweep takes."""
    from .customizer_panel import PLAY_INTERVAL_MS
    model = window.model
    panel = _panel(window)
    if params.get("play") is False:
        was = panel.playing_node()
        panel.stop()
        return {"playing": None,
                "stopped": _variable(was) if was is not None else None}
    created = None
    if params.get("spin") is not None:
        part = model.find(int(params["spin"]))
        if part is None:
            raise MotionError(f"No node with id {params['spin']}.")
        known = {n.id for n in model.global_assigns()}
        node = add_spin(model, part)
        if node.id not in known:
            created = _variable(node)
    elif params.get("id") is not None:
        node = model.find(int(params["id"]))
        if node is None or node.type != "assign" or node not in sliders(
                model):
            raise MotionError(f"Node {params['id']} is not a slider "
                              "variable (an annotated assign with a "
                              "range).")
    else:
        node = pick(model, params.get("variable"))
    dock = getattr(window, "_customizer_dock", None)
    if dock is not None:
        dock.show()
        dock.raise_()
    if not panel.play(node):
        raise MotionError(f"{_variable(node)} has no play button — is it "
                          "hidden (a [Hidden] group)?")
    spec = customizer.widget(node)
    lo, hi = float(spec["min"]), float(spec["max"])
    step = float(spec["step"]) or 1.0
    notches = max(int(round((hi - lo) / step)), 1)
    out = {"playing": _variable(node), "id": node.id,
           "range": [lo, step, hi],
           "seconds_per_sweep": round(notches * PLAY_INTERVAL_MS / 1000, 1),
           "note": "It sweeps back and forth until stopped: "
                   "play_motion with play false, or the ■ in the "
                   "Customizer panel. A structural edit stops it too."}
    if created:
        out["created"] = created
        out["note"] = (f"Added {created} (0-360°, Motion group) to the "
                       "part's rz. " + out["note"])
    return out
