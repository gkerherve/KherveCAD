# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Sketch lines coloured by how defined they are, as SolidWorks does
(2026-11-10, the user: "how it is done in SolidWorks"): BLUE while a
shape can still move or change, BLACK once its relations and dimensions
hold it, RED when they contradict each other (over defined).

`states(model, container)` -> {node id: "free" | "defined" | "over"}
from the constraint solver's null space (sketch_constraints.solve's
``free`` vectors): a shape is free when any of its own parameters moves
in that space, and a shape no relation names is free outright.
Remembered per container while its rows and shapes are unchanged.

`apply(scene, focus)` recolours the 2D view's shape items after a
rebuild: every sketch while a sketch is being edited (Sketch Mode,
`focus` not None), and, in the classic overview, the sketches that have
relations at all — an unconstrained drawing there keeps its usual ink.
"""

from . import sketch_constraints as sc
from .model import SHAPE_2D

#: the inks (SolidWorks' blue / black / red)
INK = {"free": "#1d4ed8", "defined": "#111111", "over": "#d32f2f"}
#: a parameter that moves this much in a null-space vector is free
FREE_TOL = 1e-3

_CACHE = {}


def _key(container):
    import json
    try:
        return json.dumps([sc.rows(container),
                           [(c.type, c.name, c.params)
                            for c in container.children]],
                          sort_keys=True, default=str)
    except (TypeError, ValueError):
        return None


def _shapes(container):
    return [c for c in container.children if c.category == SHAPE_2D
            and c.type in sc.SHAPES]


def states(model, container):
    """{node id: state} of the shapes directly in *container*."""
    key = _key(container)
    hit = _CACHE.get(container.id)
    if key is not None and hit is not None and hit[0] == key:
        return hit[1]
    shapes = _shapes(container)
    out = {n.id: "free" for n in shapes}
    if sc.rows(container):
        try:
            report = sc.solve(container, env=sc._env(model), write=False)
        except Exception:
            report = None
        if report is not None and not report.get("ok"):
            out = {n.id: "over" for n in shapes}
        elif report is not None:
            moving = set()
            for vec in report.get("free") or []:
                for (nid, _path), amount in vec.items():
                    if abs(amount) > FREE_TOL:
                        moving.add(nid)
            named = set(report.get("nodes") or {})
            for n in shapes:
                if n.id in named and n.id not in moving:
                    out[n.id] = "defined"
    if key is not None:
        if len(_CACHE) > 400:
            _CACHE.clear()
        _CACHE[container.id] = (key, out)
    return out


def ink(model, node, editing):
    """The colour for sketch shape *node*, or None to keep its own."""
    cont = node.parent
    if cont is None or node.category != SHAPE_2D:
        return None
    if not editing and not sc.rows(cont):
        return None
    if node.params.get("modifier") == "%":
        return None                    # construction keeps its look
    state = states(model, cont).get(node.id)
    return INK.get(state) if state else None


def apply(scene, focus):
    """Recolour the scene's shape items (after a rebuild)."""
    from PyQt5.QtGui import QColor, QPen
    model = getattr(scene, "model", None)
    if model is None:
        return
    editing = focus is not None
    for nid, item in list(getattr(scene, "_items", {}).items()):
        node = getattr(item, "node", None)
        if node is None or not hasattr(item, "pen"):
            continue
        try:
            colour = ink(model, node, editing)
        except Exception:                  # never break a rebuild
            colour = None
        if colour is None:
            continue
        pen = QPen(item.pen())
        pen.setColor(QColor(colour))
        item.setPen(pen)
