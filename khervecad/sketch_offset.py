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
    return offset_order(model, order, distance, side, cap,
                        parent=shapes[0].parent,
                        width=shapes[0].params.get("width", 0.2))


def offset_order(model, order, distance, side=1, cap=False, parent=None,
                 width=0.2, create=None):
    """The chain *order* ([x1, y1, x2, y2, bulge] end to end) offset by
    *distance* along its left normal (side -1 = the right). New lines go
    into *parent*, or through *create(type, params)* (the 2D sketch).
    A whole circle (a chain of one ``("circle", cx, cy, r, sign)``) gives
    a concentric circle."""
    d = float(distance) * (1 if side >= 0 else -1)
    made = []

    def make(t, p, name):
        n = create(t, p) if create is not None else \
            model.add_node(t, p, parent=parent)
        model.rename(n, name)
        made.append(n)
    if order and order[0][0] == "circle":
        _t, cx, cy, r, sign = order[0]
        r2 = r - d * sign
        if r2 <= 1e-9:
            raise ValueError(language.tr(
                "Offset Entities: the distance is larger than the radius"))
        make("circle", dict(x=round(cx, 6), y=round(cy, 6),
                            radius=round(r2, 6)), "Offset")
        return made
    copies = [_offset_seg(s, d) for s in order]
    if any(c is None for c in copies):
        raise ValueError(language.tr(
            "Offset Entities: the distance is larger than an arc's radius"))
    closed = _key(order[0][0], order[0][1]) == _key(order[-1][2],
                                                    order[-1][3])
    pairs = list(zip(copies, copies[1:]))
    if closed:
        pairs.append((copies[-1], copies[0]))
    snap = max(0.5, 0.05 * abs(d))
    for a, b in pairs:
        if math.hypot(a[2] - b[0], a[3] - b[1]) > JOIN:
            _meet(a, b)
        gap = math.hypot(a[2] - b[0], a[3] - b[1])
        if JOIN < gap <= snap:
            # a part's faceted fillet is a hair off tangent: the copies
            # of a line and an arc miss by that hair — close it
            if abs(a[4]) > 1e-9 and abs(b[4]) <= 1e-9:
                mx, my = b[0], b[1]           # a straight side stays put
            elif abs(b[4]) > 1e-9 and abs(a[4]) <= 1e-9:
                mx, my = a[2], a[3]
            else:
                mx, my = (a[2] + b[0]) / 2, (a[3] + b[1]) / 2
            a[2], a[3], b[0], b[1] = mx, my, mx, my

    def add(x1, y1, x2, y2, bulge=0.0, name="Offset"):
        p = dict(x1=round(x1, 6), y1=round(y1, 6), x2=round(x2, 6),
                 y2=round(y2, 6), width=width)
        if abs(bulge) > 1e-9:
            p["bulge"] = bulge
        make("line", p, name)
    for c in copies:
        add(*c)
    if cap and not closed:
        add(order[0][0], order[0][1], copies[0][0], copies[0][1],
            name="Offset end")
        add(order[-1][2], order[-1][3], copies[-1][2], copies[-1][3],
            name="Offset end")
    return made


# ---- the PART's edges (SolidWorks offsets model edges directly) ----------

#: two edges meeting within this angle (degrees) are one tangent chain
TANGENT_DEG = 12.0


def _seg(params):
    return [float(params["x1"]), float(params["y1"]), float(params["x2"]),
            float(params["y2"]), float(params.get("bulge") or 0.0)]


def _dir_out(s):
    from . import sketch_arc
    return sketch_arc.end_tangent(dict(x1=s[0], y1=s[1], x2=s[2], y2=s[3],
                                       bulge=s[4]))


def _dir_in(s):
    from . import sketch_arc
    t = sketch_arc.end_tangent(dict(x1=s[2], y1=s[3], x2=s[0], y2=s[1],
                                    bulge=-s[4]))
    return (-t[0], -t[1])


def _turned(s):
    return [s[2], s[3], s[0], s[1], -s[4]]


def _same(s, t):
    a = {_key(round(s[0], 3), round(s[1], 3)),
         _key(round(s[2], 3), round(s[3], 3))}
    b = {_key(round(t[0], 3), round(t[1], 3)),
         _key(round(t[2], 3), round(t[3], 3))}
    return a == b and abs(abs(s[4]) - abs(t[4])) < 1e-3


def _covers(s, t):
    """Shape *s* runs through both ends of piece *t* (a piece _absorb
    joined into an arc)."""
    from . import sketch_arc
    if abs(s[4]) < 1e-9:
        return False
    g = sketch_arc.geometry(*s)
    if g is None:
        return False
    cx, cy, r, _a, _s = g
    return all(abs(math.hypot(x - cx, y - cy) - r) < max(0.01 * r, 0.05)
               for x, y in ((t[0], t[1]), (t[2], t[3])))


def _near(p, q, tol=1e-3):
    return math.hypot(p[0] - q[0], p[1] - q[1]) <= tol


def _tangent(u, v):
    dot = max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1]))
    return math.degrees(math.acos(dot)) <= TANGENT_DEG


def _absorb(shapes):
    """A short straight piece lying on the circle of the arc beside it
    is that arc's first or last facet (the tessellated fillet's end was
    converted as a line): join it to the arc."""
    from . import sketch_arc
    out = [list(s) for s in shapes]
    changed = True
    while changed:
        changed = False
        for i, a in enumerate(out):
            if abs(a[4]) < 1e-9:
                continue
            g = sketch_arc.geometry(*a)
            if g is None:
                continue
            cx, cy, r, a0, sweep = g
            slack = max(0.01 * r, 0.05)
            for j, b in enumerate(out):
                if j == i or abs(b[4]) > 1e-9:
                    continue
                if math.hypot(b[2] - b[0], b[3] - b[1]) > 0.5 * r:
                    continue
                on = [abs(math.hypot(x - cx, y - cy) - r) < slack
                      for x, y in ((b[0], b[1]), (b[2], b[3]))]
                if not all(on):
                    continue
                for cand in (b, _turned(b)):
                    if _near((cand[2], cand[3]), (a[0], a[1]), 1e-3):
                        start, end = (cand[0], cand[1]), (a[2], a[3])
                    elif _near((cand[0], cand[1]), (a[2], a[3]), 1e-3):
                        start, end = (a[0], a[1]), (cand[2], cand[3])
                    else:
                        continue
                    t0 = math.atan2(start[1] - cy, start[0] - cx)
                    t1 = math.atan2(end[1] - cy, end[0] - cx)
                    sw = t1 - t0
                    while sweep > 0 and sw <= 0:
                        sw += 2 * math.pi
                    while sweep < 0 and sw >= 0:
                        sw -= 2 * math.pi
                    out[i] = [start[0], start[1], end[0], end[1],
                              math.tan(sw / 4.0)]
                    del out[j]
                    changed = True
                    break
                if changed:
                    break
            if changed:
                break
    return out


def edge_chain(segs, p, tol, chain=True):
    """The part's edge at sketch point *p* (the face outline *segs*, the
    pieces a sketch plane cuts from the part) — with *chain*, run on
    through every edge meeting it tangentially (SolidWorks' Select
    chain) — as [x1, y1, x2, y2, bulge] end to end, oriented so the
    PART lies on its left: offset_order's side +1 goes into the part.
    A round hole or boss edge is [("circle", cx, cy, r, sign)]. None
    when no edge is near *p*."""
    from . import sketch_arc, sketch_convert as cv
    segs = [(tuple(a[:2]), tuple(b[:2])) for a, b in segs]
    hit = cv.edge_at(segs, p, tol)
    if hit is None:
        return None
    picked = cv.convert(cv.whole_edge(segs, *hit), segs)
    if not picked:
        return None
    if picked[0][0] == "circle":
        c = picked[0][1]
        cx, cy, r = float(c["x"]), float(c["y"]), float(c["radius"])
        eps = max(1e-3, r * 1e-3)
        sign = 1 if cv.inside(segs, (cx + r - eps, cy)) else -1
        return [("circle", cx, cy, r, sign)]
    seed = _seg(picked[0][1])
    every = _absorb([_seg(q) for t, q in cv.convert(segs, segs)
                     if t == "line"])
    seed = next((s for s in every if _same(s, seed)), None) or next(
        (s for s in every if _covers(s, seed)), seed)
    order = [seed]
    if chain:
        rest = [s for s in every if s is not order[0]]
        for forward in (True, False):
            while True:
                end = order[-1] if forward else order[0]
                at = (end[2], end[3]) if forward else (end[0], end[1])
                head = _dir_out(end) if forward else _dir_in(end)
                nxt = None
                for s in rest:
                    for cand in (s, _turned(s)):
                        start = (cand[0], cand[1]) if forward else \
                            (cand[2], cand[3])
                        if not _near(start, at):
                            continue
                        go = _dir_in(cand) if forward else _dir_out(cand)
                        if _tangent(head, go):
                            nxt = (s, cand)
                            break
                    if nxt:
                        break
                if nxt is None:
                    break
                rest.remove(nxt[0])
                if forward:
                    order.append(nxt[1])
                else:
                    order.insert(0, nxt[1])
                if _near((order[0][0], order[0][1]),
                         (order[-1][2], order[-1][3])):
                    break                       # round the whole loop
    # the part on the left: a point a hair to the left of the first
    # piece's middle lies inside the outline
    s = order[0]
    mx, my = sketch_arc.middle(*s)
    ux, uy = _dir_in(s) if abs(s[4]) > 1e-9 else \
        ((s[2] - s[0]), (s[3] - s[1]))
    if abs(s[4]) > 1e-9:
        # the tangent at the middle: perpendicular to the radius
        g = sketch_arc.geometry(*s)
        if g is not None:
            cx, cy, _r, _a, sweep = g
            rx, ry = mx - cx, my - cy
            ux, uy = (-ry, rx) if sweep > 0 else (ry, -rx)
    L = math.hypot(ux, uy) or 1.0
    eps = max(1e-3, tol * 0.05)
    if not cv.inside(segs, (mx - uy / L * eps, my + ux / L * eps)):
        order = [_turned(t) for t in reversed(order)]
    return order


def offset_edges(model, segs, points, distance, side=1, cap=False,
                 chain=True, tol=0.5, parent=None, create=None):
    """Offset Entities of the part's edges at sketch *points*: one chain
    per point (Select chain), each offset into the part by *distance*
    (side -1 = out of it). Returns the new nodes."""
    made = []
    for p in points:
        order = edge_chain(segs, p, tol, chain)
        if order is None:
            raise ValueError(language.tr(
                "Offset Entities: no edge of the part near {p}").format(
                    p=[round(v, 3) for v in p]))
        made += offset_order(model, order, distance, side, cap,
                             parent=parent, create=create)
    return made


# ---- the button: a window like SolidWorks' -------------------------------

def start(win):
    """Offset Entities pressed: the selected sketch lines are offset by
    the window's Distance; Reverse and Cap ends as in SolidWorks. With a
    sketch open, a click on an EDGE OF THE PART (3D view or 2D sketch)
    offsets that edge — with Select chain, every edge running on from it
    tangentially — into the part (Exercise 54)."""
    from .tool_panel import ToolPanel
    tr = language.tr
    tree = win.builder.active_tree()
    picked = [n for n in tree.selected_nodes() if n.type == "line"] \
        if hasattr(tree, "selected_nodes") else []
    old = getattr(win, "_offset_panel", None)
    if old is not None:
        old.hide()
    state = {"distance": 10.0, "reverse": False, "cap": False,
             "chain": True, "preview": [], "edges": []}
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
        if not shapes and not state["edges"]:
            panel.boxes["entities"].set_text(
                tr("— select lines, or click an edge of the part"))
            return
        side = -1 if state["reverse"] else 1
        made, n = [], 0
        try:
            if shapes:
                made += offset(model, shapes, state["distance"], side,
                               state["cap"])
                n += len(shapes)
            for segs, p, tol, parent, create in state["edges"]:
                order = edge_chain(segs, p, tol, state["chain"])
                if order is None:
                    continue
                n += len(order)
                made += offset_order(model, order, state["distance"],
                                     side, state["cap"], parent=parent,
                                     create=create)
        except ValueError as exc:
            win.statusBar().showMessage(str(exc), 6000)
        state["preview"] = made
        panel.boxes["entities"].set_text(
            tr("{n} entities").format(n=n))
        model.structure_changed.emit()

    def add_edge(segs, p, tol, parent=None, create=None):
        """A click on the part's edge at sketch point *p*: the chain is
        offset (and shown) at once. False when no edge is there."""
        if edge_chain(segs, p, tol, state["chain"]) is None:
            return False
        state["edges"].append((segs, p, tol, parent, create))
        preview()
        return True

    def stop_picking():
        win._offset_pick = None
        view = win.view3d
        tool = getattr(view, "edit_tool", None)
        if getattr(tool, "tool", None) == TOOL:
            sk = getattr(win, "_sketch3d_tool", None)
            view.edit_tool = sk
            view.update()
        scene = win.view2d.scene()
        if getattr(scene, "tool", None) == TOOL:
            win.view2d.set_tool("select")

    def finish(keep):
        if not keep:
            drop_preview()
        stop_picking()
        panel.hide()
        panel.deleteLater()
        win._offset_panel = None

    panel = ToolPanel(win.view2d, tr("Offset Entities"),
                      on_ok=lambda: finish(True),
                      on_cancel=lambda: finish(False))
    panel.hint(tr("Select the sketch lines and arcs to offset, or click "
                  "an edge of the part; then set the distance."))
    panel.selection("entities", tr("Entities"))
    panel.number("distance", tr("Distance:"), state["distance"],
                 lambda v: (state.__setitem__("distance", float(v)),
                            preview()), minimum=0.01, step=1.0)
    panel.check("reverse", tr("Reverse"), False,
                lambda v: (state.__setitem__("reverse", bool(v)),
                           preview()))
    panel.check("chain", tr("Select chain"), True,
                lambda v: (state.__setitem__("chain", bool(v)),
                           preview()))
    panel.check("cap", tr("Cap ends"), False,
                lambda v: (state.__setitem__("cap", bool(v)), preview()))
    panel.finish()
    win._offset_panel = panel
    win._offset_pick = add_edge
    panel.open()
    # clicks on the part's edges: the 3D sketch, else the 2D sketch
    sk = getattr(win, "_sketch3d_tool", None)
    if sk is not None and getattr(sk, "group", None) is not None:
        from . import sketch3d_tools
        sk.resume()
        if win.view3d.edit_tool is sk:
            win.view3d.edit_tool = None      # paused, not closed
        sketch3d_tools.start_modify(win, TOOL)
    elif not picked:
        try:
            win.view2d.set_tool(TOOL)
        except Exception:                     # pragma: no cover
            pass
    preview()
    return panel


def click_3d(window, sk, p, tol):
    """Modify3D's click with Offset Entities on: the part's edge at the
    3D sketch's point *p* goes to the open window."""
    pick = getattr(window, "_offset_pick", None)
    if pick is None or sk is None:
        return False
    return pick(sk.info.get("segments") or [], p, tol,
                parent=sk.holder or sk.group)


def press_2d(scene, pos, tol):
    """The 2D sketch's click with Offset Entities on."""
    win = scene.views()[0].window() if scene.views() else None
    pick = getattr(win, "_offset_pick", None)
    outline = getattr(scene, "face_outline", None) or {}
    segs = outline.get("segments") or []
    if pick is None or not segs:
        scene.status.emit(language.tr(
            "Offset Entities: click an edge of the part."))
        return False
    ok = pick(segs, (pos.x(), pos.y()), tol, create=scene._create)
    if not ok:
        scene.status.emit(language.tr(
            "Offset Entities: no edge of the part there."))
    return ok


TIPS = {TOOL: (
    "Offset Entities",
    "Copies the selected sketch lines and arcs a distance away — a wall "
    "of even thickness from one line (SolidWorks' Offset Entities).",
    ["Select the lines / arcs (a chain joined end to end) in the sketch "
     "or the tree — or, with the window open, click an edge of the part "
     "(Select chain takes every edge running on from it tangentially).",
     "Click Offset Entities: the copy shows at once.",
     "Set the Distance; tick Reverse for the other side; tick Cap ends "
     "to close both ends.",
     "OK keeps it, Cancel takes it away."],
    "The side is the left of the first line as it was drawn.")}
