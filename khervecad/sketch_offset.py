# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""SolidWorks' **Offset Entities** (2026-11-14, Exercise 7: a wall drawn as
a line, an R18 arc and a line, then offset 12 with both ends capped).

The selected sketch lines and arcs (lines with a bulge) are put in chain
order — any order, any direction — and each is copied `distance` along
its left normal (`side` -1 = the other way, SolidWorks' Reverse): a line
shifts, an arc keeps its centre and sweep with its radius changed. Where
two copies do not meet (a sharp corner) the lines are run to their
intersection. `cap` closes both ends with lines from the originals'
ends, so the band is one closed outline. KherveCAD's "Offset" operation
is OpenSCAD's offset() of a closed AREA; this copies ENTITIES.
"""

from __future__ import annotations

import math

from . import language

TOOL = "sk_offset"
JOIN = 1e-6


def _p(node):
    p = node.params
    return [float(p["x1"]), float(p["y1"]), float(p["x2"]),
            float(p["y2"]), float(p.get("bulge") or 0.0)]


def _key(x, y):
    return (round(x, 6), round(y, 6))


def chain(shapes):
    """[x1, y1, x2, y2, bulge] in chain order, each running on from the
    last (a segment turned round has its bulge negated), or None when
    the shapes do not form one open or closed chain."""
    segs = [_p(s) for s in shapes if s.type == "line"]
    if not segs:
        return None
    count = {}
    for s in segs:
        for k in (_key(s[0], s[1]), _key(s[2], s[3])):
            count[k] = count.get(k, 0) + 1
    if any(n > 2 for n in count.values()):
        return None
    ends = [k for k, n in count.items() if n == 1]
    start = ends[0] if ends else _key(segs[0][0], segs[0][1])
    out, left, cur = [], list(segs), start
    while left:
        for i, s in enumerate(left):
            if _key(s[0], s[1]) == cur:
                seg = s
                break
            if _key(s[2], s[3]) == cur:
                seg = [s[2], s[3], s[0], s[1], -s[4]]
                break
        else:
            return None
        left.pop(i)
        out.append(seg)
        cur = _key(seg[2], seg[3])
    # the side follows the FIRST selected shape as it was drawn: the
    # chain runs its way
    first = segs[0]
    for seg in out:
        if _key(seg[0], seg[1]) == _key(first[2], first[3]) and \
                _key(seg[2], seg[3]) == _key(first[0], first[1]):
            out = [[t[2], t[3], t[0], t[1], -t[4]] for t in reversed(out)]
            break
    return out


def _offset_seg(s, d):
    """One segment moved *d* along its left normal."""
    x1, y1, x2, y2, b = s
    if abs(b) > 1e-9:
        from . import sketch_arc
        g = sketch_arc.geometry(x1, y1, x2, y2, b)
        if g is not None:
            cx, cy, r, _a0, sweep = g
            r2 = r - d if sweep > 0 else r + d
            if r2 <= 1e-9:
                return None

            def at(x, y):
                L = math.hypot(x - cx, y - cy)
                return cx + (x - cx) / L * r2, cy + (y - cy) / L * r2
            a, c = at(x1, y1), at(x2, y2)
            return [a[0], a[1], c[0], c[1], b]
    L = math.hypot(x2 - x1, y2 - y1)
    if L < 1e-12:
        return None
    nx, ny = -(y2 - y1) / L * d, (x2 - x1) / L * d
    return [x1 + nx, y1 + ny, x2 + nx, y2 + ny, 0.0]


def _meet(a, b):
    """Run two straight copies to where their lines cross."""
    if abs(a[4]) > 1e-9 or abs(b[4]) > 1e-9:
        return
    d1 = (a[2] - a[0], a[3] - a[1])
    d2 = (b[2] - b[0], b[3] - b[1])
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-12:
        return
    t = ((b[0] - a[0]) * d2[1] - (b[1] - a[1]) * d2[0]) / den
    x, y = a[0] + t * d1[0], a[1] + t * d1[1]
    a[2], a[3], b[0], b[1] = x, y, x, y


def offset(model, shapes, distance, side=1, cap=False):
    """New sketch lines / arcs beside *shapes*: the chain offset by
    *distance* (side -1 = the other way), its ends capped when *cap*.
    Returns the new nodes; ValueError when the shapes are no chain."""
    order = chain(shapes)
    if order is None:
        raise ValueError(language.tr(
            "Offset Entities: select lines and arcs that join end to end"))
    d = float(distance) * (1 if side >= 0 else -1)
    copies = [_offset_seg(s, d) for s in order]
    if any(c is None for c in copies):
        raise ValueError(language.tr(
            "Offset Entities: the distance is larger than an arc's radius"))
    closed = _key(order[0][0], order[0][1]) == _key(order[-1][2],
                                                    order[-1][3])
    pairs = list(zip(copies, copies[1:]))
    if closed:
        pairs.append((copies[-1], copies[0]))
    for a, b in pairs:
        if math.hypot(a[2] - b[0], a[3] - b[1]) > JOIN:
            _meet(a, b)
    parent = shapes[0].parent
    width = shapes[0].params.get("width", 0.2)
    made = []

    def add(x1, y1, x2, y2, bulge=0.0, name="Offset"):
        p = dict(x1=round(x1, 6), y1=round(y1, 6), x2=round(x2, 6),
                 y2=round(y2, 6), width=width)
        if abs(bulge) > 1e-9:
            p["bulge"] = bulge
        made.append(model.add_node("line", p, parent=parent, name=name))
    for c in copies:
        add(*c)
    if cap and not closed:
        add(order[0][0], order[0][1], copies[0][0], copies[0][1],
            name="Offset end")
        add(order[-1][2], order[-1][3], copies[-1][2], copies[-1][3],
            name="Offset end")
    return made


# ---- the button: a window like SolidWorks' -------------------------------

def start(win):
    """Offset Entities pressed: the selected sketch lines are offset by
    the window's Distance; Reverse and Cap ends as in SolidWorks."""
    from .tool_panel import ToolPanel
    tr = language.tr
    tree = win.builder.active_tree()
    picked = [n for n in tree.selected_nodes() if n.type == "line"] \
        if hasattr(tree, "selected_nodes") else []
    old = getattr(win, "_offset_panel", None)
    if old is not None:
        old.hide()
    state = {"distance": 10.0, "reverse": False, "cap": False,
             "preview": []}
    model = win.model

    def drop_preview():
        for n in state["preview"]:
            if n.parent is not None:
                n.parent.remove(n)
        state["preview"] = []
        model.structure_changed.emit()

    def preview():
        drop_preview()
        shapes = picked or [n for n in tree.selected_nodes()
                            if n.type == "line"]
        if not shapes:
            panel.boxes["entities"].set_text(tr("— select the lines"))
            return
        panel.boxes["entities"].set_text(
            tr("{n} entities").format(n=len(shapes)))
        try:
            state["preview"] = offset(model, shapes, state["distance"],
                                      -1 if state["reverse"] else 1,
                                      state["cap"])
        except ValueError as exc:
            win.statusBar().showMessage(str(exc), 6000)
        model.structure_changed.emit()

    def finish(keep):
        if not keep:
            drop_preview()
        panel.hide()
        panel.deleteLater()
        win._offset_panel = None

    panel = ToolPanel(win.view2d, tr("Offset Entities"),
                      on_ok=lambda: finish(True),
                      on_cancel=lambda: finish(False))
    panel.hint(tr("Select the lines and arcs to offset (a chain), then "
                  "set the distance."))
    panel.selection("entities", tr("Entities"))
    panel.number("distance", tr("Distance:"), state["distance"],
                 lambda v: (state.__setitem__("distance", float(v)),
                            preview()), minimum=0.01, step=1.0)
    panel.check("reverse", tr("Reverse"), False,
                lambda v: (state.__setitem__("reverse", bool(v)),
                           preview()))
    panel.check("cap", tr("Cap ends"), False,
                lambda v: (state.__setitem__("cap", bool(v)), preview()))
    panel.finish()
    win._offset_panel = panel
    panel.open()
    preview()
    return panel


TIPS = {TOOL: (
    "Offset Entities",
    "Copies the selected sketch lines and arcs a distance away — a wall "
    "of even thickness from one line (SolidWorks' Offset Entities).",
    ["Select the lines / arcs (a chain joined end to end) in the sketch "
     "or the tree.",
     "Click Offset Entities: the copy shows at once.",
     "Set the Distance; tick Reverse for the other side; tick Cap ends "
     "to close both ends.",
     "OK keeps it, Cancel takes it away."],
    "The side is the left of the first line as it was drawn.")}
