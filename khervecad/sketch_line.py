"""The SolidWorks-style Line tool, and the same snapping for the polygon
(2026-10-21, the user: "I want the line to be working just like
SolidWorks").

- Lines CHAIN: each click ends a line and starts the next from that
  point; a double-click, right-click, Enter or Esc ends the chain, and
  so does a click back on the chain's first point (the shape is closed,
  as with the polygon).
- While the cursor moves it SNAPS, first match wins: to an existing
  point (a line end, a corner, a centre, the ORIGIN) within `SNAP_PX`;
  else to horizontal / vertical / 45° from the start within
  `ANGLE_DEG`; then its free coordinate lines up with any existing
  point's x or y (dotted inference line); else the grid.
- A readout at the line's end gives its length and angle.
- Relations are added as SolidWorks does: Horizontal / Vertical when the
  line snapped that way, Coincident where a line starts at the last one's
  end or on a point it snapped to.

The polygon tool uses `snap` and the readout too (`polygon_relations`
adds H / V to the sides that snapped).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

SNAP_PX = 10.0
ALIGN_PX = 7.0
ANGLE_DEG = 4.0
MIN_LEN = 0.05
#: a sketch line's stroke (mm): thin like a sketch, still a solid when
#: extruded — 2 mm drew a 5 mm sketch as a fat bar (the user)
LINE_WIDTH = 0.2


# ---------------------------------------------------------------- points
def sketch_points(scene, skip=None):
    """[(QPointF scene, node, entity name)] of every point a line can
    snap to: line ends, polygon / rectangle corners, circle centres, and
    the origin (node None)."""
    from PyQt5.QtCore import QPointF
    from . import sketch_constrain_ui as scu
    from . import sketch_constraints as sc
    out = [(QPointF(0.0, 0.0), None, "origin")]
    for item in scu._shape_items(scene):
        node = item.node
        if skip is not None and node is skip:
            continue
        frame = item.parentItem()
        for name, kind in scu._entities(node):
            if kind != "point":
                continue
            try:
                x, y = sc._point(node, name, {})
            except (KeyError, ValueError, IndexError, TypeError):
                continue
            q = QPointF(x, y)
            out.append((frame.mapToScene(q) if frame is not None else q,
                        node, name))
    return out


def _px(scene, pixels):
    from .polygon_draw import px_to_scene
    return px_to_scene(scene, pixels)


def snap(scene, raw, start=None, skip=None):
    """(QPointF, info) for the cursor at scene point *raw*; info holds
    "point" (node, name) or None, "angle" ("h" | "v" | "45" | None) and
    "guides" [(QPointF a, QPointF b)] to draw dotted."""
    from PyQt5.QtCore import QPointF
    info = dict(point=None, angle=None, guides=[], origin=False)
    pts = sketch_points(scene, skip)
    # the part under the sketch: the face sketched on, or the part cut
    # by the main plane (section_outline) — its corners, middles, centres
    outline = getattr(scene, "face_outline", None) or {}
    pts = pts + [(QPointF(x, y), None, kind)
                 for x, y, kind in outline.get("points", ())]
    draft = _draft(scene)
    # the points of the shape being drawn count too: line up with them
    # (the user: the point above was just above, and nothing snapped)
    pts = pts + [(QPointF(q), None, "draft") for q in draft
                 if start is None or (q - start).manhattanLength() > 1e-9]
    prev = draft[-2] if len(draft) >= 2 and start is not None else None
    tol = _px(scene, SNAP_PX)
    best = None
    for q, node, name in pts:
        d = math.hypot(q.x() - raw.x(), q.y() - raw.y())
        if d <= tol and (best is None or d < best[0]):
            best = (d, q, node, name)
    if best is not None:
        _d, q, node, name = best
        info["point"] = (node, name) if node is not None else None
        info["origin"] = node is None and name == "origin"
        if start is not None:
            info["angle"] = _angle_of(start, q)
        return QPointF(q), info
    x, y = raw.x(), raw.y()
    if start is not None:
        dx, dy = x - start.x(), y - start.y()
        L = math.hypot(dx, dy)
        if L > 1e-9:
            ang = math.degrees(math.atan2(dy, dx)) % 180.0
            for target, kind in ((0, "h"), (180, "h"), (90, "v"),
                                 (45, "45"), (135, "45")):
                if abs(ang - target) < ANGLE_DEG:
                    t = math.radians(math.degrees(math.atan2(dy, dx)))
                    a = math.radians(round(math.degrees(t) / 45.0) * 45.0)
                    proj = dx * math.cos(a) + dy * math.sin(a)
                    x = start.x() + proj * math.cos(a)
                    y = start.y() + proj * math.sin(a)
                    info["angle"] = kind
                    info["guides"].append((QPointF(start),
                                           QPointF(x, y)))
                    break
            if info["angle"] is None and prev is not None:
                # square to the last side (SolidWorks' perpendicular)
                px, py = start.x() - prev.x(), start.y() - prev.y()
                pl = math.hypot(px, py)
                if pl > 1e-9:
                    nx, ny = -py / pl, px / pl
                    t = dx * nx + dy * ny
                    off = abs(dx * px + dy * py) / pl
                    if L > 1e-9 and math.degrees(math.asin(
                            min(1.0, off / L))) < ANGLE_DEG:
                        x, y = start.x() + t * nx, start.y() + t * ny
                        info["angle"] = "perp"
                        info["guides"].append((QPointF(start),
                                               QPointF(x, y)))
    # ON an edge of the part under the sketch (the cut / face outline)
    if info["angle"] is None and outline.get("segments"):
        from . import face_outline
        etol = _px(scene, SNAP_PX / 2)
        best_e = None
        for a, b in outline["segments"]:
            ex_, ey_ = face_outline._on_segment(x, y, a, b)
            d = math.hypot(ex_ - x, ey_ - y)
            if d <= etol and (best_e is None or d < best_e[0]):
                best_e = (d, ex_, ey_)
        if best_e is not None:
            info["edge"] = True
            return QPointF(best_e[1], best_e[2]), info
    # line up with an existing point's x or y (the free coordinate)
    atol = _px(scene, ALIGN_PX)
    if info["angle"] != "v":
        bx = min(((abs(q.x() - x), q) for q, _n, _m in pts),
                 key=lambda t: t[0], default=None)
        if bx is not None and bx[0] <= atol and info["angle"] not in \
                ("45", "perp"):
            x = bx[1].x()
            info["guides"].append((QPointF(bx[1]), QPointF(x, y)))
    if info["angle"] != "h":
        by = min(((abs(q.y() - y), q) for q, _n, _m in pts),
                 key=lambda t: t[0], default=None)
        if by is not None and by[0] <= atol and info["angle"] not in \
                ("45", "perp"):
            y = by[1].y()
            info["guides"].append((QPointF(by[1]), QPointF(x, y)))
    if getattr(scene, "snap_enabled", False):
        # the grid still rules every coordinate nothing else fixed: a
        # horizontal line's x, a vertical one's y, a 45° line's length
        g = scene.grid_size
        lined = {(round(b.x(), 9), round(b.y(), 9))
                 for _a, b in info["guides"]}
        fixed_x = info["angle"] == "v" or any(
            abs(q.x() - x) < 1e-9 for q, _n, _m in pts) and lined
        fixed_y = info["angle"] == "h" or any(
            abs(q.y() - y) < 1e-9 for q, _n, _m in pts) and lined
        if info["angle"] == "perp":
            pass
        elif info["angle"] == "45" and start is not None:
            d = round((x - start.x()) / g) * g
            x = start.x() + d
            y = start.y() + (d if (y - start.y()) * (x - start.x()) >= 0
                             else -d)
        else:
            if not fixed_x:
                x = round(x / g) * g
            if not fixed_y:
                y = round(y / g) * g
    return QPointF(x, y), info


def _draft(scene):
    """Points of the shape being drawn: the polygon's, or the line
    chain's."""
    from PyQt5.QtCore import QPointF
    poly = getattr(scene, "_poly_points", None)
    if poly:
        return [QPointF(q) for q in poly]
    st = getattr(scene, "_ln", None)
    return list(st.get("chain", [])) if st else []


def _angle_of(a, b):
    dx, dy = b.x() - a.x(), b.y() - a.y()
    if abs(dy) < 1e-9 and abs(dx) > 1e-9:
        return "h"
    if abs(dx) < 1e-9 and abs(dy) > 1e-9:
        return "v"
    return None


# --------------------------------------------------------------- overlay
def _state(scene):
    if not hasattr(scene, "_ln"):
        scene._ln = dict(start=None, start_point=None, prev=None, items=[])
    return scene._ln


def _clear(scene):
    st = _state(scene)
    for item in st["items"]:
        if item.scene() is scene:
            scene.removeItem(item)
    st["items"] = []


def readout_text(a, b, unit="mm"):
    L = math.hypot(b.x() - a.x(), b.y() - a.y())
    ang = math.degrees(math.atan2(b.y() - a.y(), b.x() - a.x()))
    return "L %.2f %s   ∠ %.1f°" % (L, unit, ang)


def draw_overlay(scene, start, pt, info):
    """The rubber band, snap marker, dotted guides and the readout."""
    from PyQt5.QtCore import QPointF, Qt
    from PyQt5.QtGui import QBrush, QColor, QFont, QPen
    from PyQt5.QtWidgets import QGraphicsItem, QGraphicsSimpleTextItem
    _clear(scene)
    st = _state(scene)

    def keep(item):
        item.setZValue(1e6)
        item.setAcceptedMouseButtons(Qt.NoButton)
        st["items"].append(item)
        return item
    guide = QPen(QColor("#e08a00"), 0)
    guide.setCosmetic(True)
    guide.setStyle(Qt.DotLine)
    for a, b in info.get("guides", []):
        keep(scene.addLine(a.x(), a.y(), b.x(), b.y(), guide))
    if start is not None:
        pen = QPen(QColor("#2176c7"), 0)
        pen.setCosmetic(True)
        pen.setWidthF(1.8)
        keep(scene.addLine(start.x(), start.y(), pt.x(), pt.y(), pen))
    # the snap marker: a square on a point, a ring otherwise
    r = _px(scene, 5.0)
    mark = QPen(QColor("#e08a00") if info.get("point") or
                info.get("origin") else QColor("#2176c7"), 0)
    mark.setCosmetic(True)
    mark.setWidthF(1.6)
    if info.get("point") or info.get("origin"):
        keep(scene.addRect(pt.x() - r, pt.y() - r, 2 * r, 2 * r, mark))
    else:
        keep(scene.addEllipse(pt.x() - r, pt.y() - r, 2 * r, 2 * r, mark))
    if start is not None:
        from . import units
        unit = units.symbol(getattr(scene.model, "unit", "mm")) \
            if hasattr(units, "symbol") else "mm"
        text = readout_text(start, pt, unit)
        tag = {"h": "  H", "v": "  V", "45": "  45°", "perp": "  ⊥"}.get(
            info.get("angle"), "")
        label = QGraphicsSimpleTextItem(text + tag)
        f = QFont()
        f.setPointSize(9)
        f.setBold(True)
        label.setFont(f)
        label.setBrush(QBrush(QColor("#1b5fa8")))
        label.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        # beside the line's end, screen-sized
        label.setPos(QPointF(pt.x() + _px(scene, 12),
                             pt.y() + _px(scene, 22)))
        scene.addItem(label)
        keep(label)


# ------------------------------------------------------------ the tool
def press(scene, event):
    from PyQt5.QtCore import Qt
    event.accept()
    st = _state(scene)
    if event.button() == Qt.RightButton:
        end_chain(scene)
        return
    if event.button() != Qt.LeftButton:
        return
    # an arc's end snaps to points, not H / V from its start
    pt, info = snap(scene, event.scenePos(),
                    None if st.get("arc") else st["start"])
    if st["start"] is None:
        st["start"], st["start_point"] = pt, info.get("point")
        st["start_origin"] = info.get("origin")
        st["chain"] = [pt]
        st["made"] = []
        draw_overlay(scene, pt, pt, info)
        _bar(scene)
        scene.status.emit("Line: click where it ends — it snaps to "
                          "points, H / V / 45° and lined-up points. "
                          "Double-click, right-click or Esc ends.")
        return
    start = st["start"]
    if math.hypot(pt.x() - start.x(), pt.y() - start.y()) < MIN_LEN:
        end_chain(scene)                       # a click on the start
        return
    params = dict(x1=round(start.x(), 4), y1=round(start.y(), 4),
                  x2=round(pt.x(), 4), y2=round(pt.y(), 4),
                  width=LINE_WIDTH)
    arc = bool(st.get("arc") and st.get("prev") is not None)
    if arc:
        bulge = _arc_bulge(st, pt)
        if abs(bulge) > 1e-9:
            params["bulge"] = round(bulge, 10)
        st["arc"] = st["armed"] = False      # one arc, then lines again
        info = {k: v for k, v in info.items() if k != "angle"}
    node = scene._create("line", params)
    if arc:
        scene.model.rename(node, "Arc")
    scene.node_created.emit(node)
    _relations(scene, node, info, st)
    st["start"], st["prev"] = pt, node
    st.setdefault("chain", []).append(pt)
    st.setdefault("made", []).append(node)
    st["start_point"], st["start_origin"] = None, False
    chain = st["chain"]
    if len(chain) >= 4 and math.hypot(pt.x() - chain[0].x(),
                                      pt.y() - chain[0].y()) < MIN_LEN:
        # back on the chain's first point: the shape is closed, so the
        # line stops there like the polygon (and SolidWorks') does
        _close_corner(scene, st["made"][0], node)
        end_chain(scene)
        scene.status.emit("Line: shape closed.")
        return
    draw_overlay(scene, pt, pt, info)
    _bar(scene)


def _close_corner(scene, first, last):
    """Coincident between the closing line's end and the first line's
    start, unless the snap already put one there (it does not when the
    point was the origin)."""
    from . import sketch_constraints as sc
    parent = last.parent
    if parent is None or first.parent is not parent or first is last:
        return
    want = {sc.ref_of(parent, last, "p2"), sc.ref_of(parent, first, "p1")}
    if any(r["kind"] == "coincident" and set(r["refs"]) == want
           for r in sc.rows(parent)):
        return
    try:
        sc.add(scene.model, parent, "coincident", sorted(want)[::-1])
    except Exception:                          # a conflict: leave it
        pass


def _relations(scene, node, info, st):
    """Horizontal / Vertical when it snapped so; Coincident with the
    last line's end and with any point it started or ended on."""
    from . import sketch_constraints as sc
    parent = node.parent
    if parent is None:
        return

    def ref(n, name):
        return sc.ref_of(parent, n, name) if n.parent is parent else None
    rows = []
    from . import sketch_arc
    kind = None if sketch_arc.is_arc(node) else (
        info.get("angle") or _angle_of(_qp(node, "p1"), _qp(node, "p2")))
    if kind in ("h", "v"):
        rows.append(("horizontal" if kind == "h" else "vertical",
                     [ref(node, "l")]))
    elif kind == "45":
        rows.append(("diagonal", [ref(node, "l")]))
    prev = st.get("prev")
    if prev is not None and prev.parent is parent:
        rows.append(("coincident", [ref(prev, "p2"), ref(node, "p1")]))
        if info.get("angle") == "perp":
            rows.append(("perpendicular", [ref(prev, "l"), ref(node, "l")]))
    elif st.get("start_point"):
        n, name = st["start_point"]
        r = ref(n, name)
        if r:
            rows.append(("coincident", [ref(node, "p1"), r]))
    end = info.get("point")
    if end:
        n, name = end
        r = ref(n, name)
        if r and n is not node:
            rows.append(("coincident", [ref(node, "p2"), r]))
    for kind, refs in rows:
        if any(r is None for r in refs):
            continue
        try:
            sc.add(scene.model, parent, kind, refs)
        except ValueError:
            pass                                # already held / conflict


def _qp(node, name):
    from PyQt5.QtCore import QPointF
    from . import sketch_constraints as sc
    x, y = sc._point(node, name, {})
    return QPointF(x, y)


def move(scene, event):
    st = _state(scene)
    _arc_switch(scene, st, event.scenePos())
    if st.get("arc"):
        pt, info = snap(scene, event.scenePos(), None, skip=None)
        info = {k: v for k, v in info.items() if k != "guides"}
    else:
        pt, info = snap(scene, event.scenePos(), st["start"])
    draw_overlay(scene, st["start"], pt, info)
    if st.get("arc") and st["start"] is not None:
        _arc_overlay(scene, st, pt)
    event.accept()


#: SolidWorks' line-to-arc: the mouse brought back onto the chain's last
#: point and taken away again draws a TANGENT ARC (the user: "if we go
#: back to the last point, the next one is an arc"); one arc, then lines
ARC_ARM_PX = 8.0
ARC_GO_PX = 16.0


def _arc_switch(scene, st, raw):
    start, prev = st.get("start"), st.get("prev")
    if start is None or prev is None:
        st["armed"] = st["arc"] = False
        return
    d = math.hypot(raw.x() - start.x(), raw.y() - start.y())
    if d <= _px(scene, ARC_ARM_PX):
        st["armed"] = True
    elif st.get("armed") and d >= _px(scene, ARC_GO_PX):
        st["armed"] = False
        st["arc"] = not st.get("arc")
        scene.status.emit(
            "Line: tangent ARC — click where it ends (back on the point "
            "and out again for a line)." if st["arc"] else
            "Line: straight again.")


def _arc_bulge(st, pt):
    from . import sketch_arc
    start = st["start"]
    d = sketch_arc.end_tangent(st["prev"].params)
    return sketch_arc.tangent_bulge((start.x(), start.y()), d,
                                    (pt.x(), pt.y()))


def _arc_overlay(scene, st, pt):
    from PyQt5.QtCore import QPointF
    from PyQt5.QtGui import QColor, QPainterPath, QPen
    from PyQt5.QtCore import Qt
    from . import sketch_arc
    start = st["start"]
    pts = sketch_arc.points(start.x(), start.y(), pt.x(), pt.y(),
                            _arc_bulge(st, pt))
    path = QPainterPath(QPointF(*pts[0]))
    for x, y in pts[1:]:
        path.lineTo(x, y)
    # the straight rubber band is replaced by the arc
    for item in list(st["items"]):
        if hasattr(item, "line") and not hasattr(item, "rect"):
            scene.removeItem(item)
            st["items"].remove(item)
    pen = QPen(QColor("#2176c7"), 0)
    pen.setCosmetic(True)
    pen.setWidthF(1.8)
    item = scene.addPath(path, pen)
    item.setZValue(1e6)
    item.setAcceptedMouseButtons(Qt.NoButton)
    st["items"].append(item)


def end_chain(scene):
    st = _state(scene)
    st["start"], st["prev"], st["start_point"] = None, None, None
    st["chain"] = []
    st["made"] = []
    _clear(scene)
    _bar(scene)


def _bar(scene):
    """Show / update the Finish · Close shape · Undo line · Cancel bar
    (the user: a chain of lines could only be ended with the mouse)."""
    st = _state(scene)
    for view in scene.views():
        bar = getattr(view, "line_bar", None)
        if bar is not None:
            bar.update_for(len(st.get("made") or []),
                           st.get("start") is not None)


def close_shape(scene):
    """The last line back to the chain's first point: a closed shape,
    ready for Create Region."""
    st = _state(scene)
    chain, made = st.get("chain") or [], st.get("made") or []
    if len(made) < 2 or st.get("start") is None:
        return None
    a, b = st["start"], chain[0]
    node = scene._create("line", dict(x1=round(a.x(), 4), y1=round(a.y(), 4),
                                      x2=round(b.x(), 4), y2=round(b.y(), 4),
                                      width=LINE_WIDTH))
    scene.node_created.emit(node)
    from . import sketch_constraints as sc
    parent = node.parent
    for first, second in ((made[-1], "p2"), (made[0], "p1")):
        try:
            sc.add(scene.model, parent, "coincident",
                   [sc.ref_of(parent, first, second),
                    sc.ref_of(parent, node,
                              "p1" if first is made[-1] else "p2")])
        except (ValueError, KeyError):
            pass
    end_chain(scene)
    scene.status.emit("Closed: select the lines and Create Region to "
                      "make a shape of them.")
    return node


def undo_line(scene):
    """Take the last line of the chain back."""
    st = _state(scene)
    made = st.get("made") or []
    if not made:
        end_chain(scene)
        return
    node = made.pop()
    chain = st.get("chain") or []
    if len(chain) > 1:
        chain.pop()
    if node.parent is not None:
        scene.model.remove_node(node)
    st["start"] = chain[-1] if chain else None
    st["prev"] = made[-1] if made else None
    _clear(scene)
    _bar(scene)


def double_click(scene, event):
    end_chain(scene)
    event.accept()


def key(scene, event):
    from PyQt5.QtCore import Qt
    if event.key() in (Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter) and \
            _state(scene)["start"] is not None:
        end_chain(scene)
        return True
    return False


def drop(scene):
    end_chain(scene)


# -------------------------------------------------------- the polygon
def polygon_relations(model, node, flags=None):
    """Relations on a finished polygon, read from its real sides (the
    snap flags alone once put H on a 45° side): Horizontal / Vertical,
    45° and Perpendicular to the side before. *flags* is kept for old
    callers and ignored."""
    from . import sketch_constraints as sc
    parent = node.parent
    if parent is None:
        return
    try:
        pts = [(float(p[0]), float(p[1])) for p in node.params["points"]]
    except (KeyError, TypeError, ValueError, IndexError):
        return
    n = len(pts)
    sides = [(pts[(i + 1) % n][0] - pts[i][0],
              pts[(i + 1) % n][1] - pts[i][1]) for i in range(n)]
    tol = 1e-6

    def add(kind, refs):
        try:
            sc.add(model, parent, kind, refs)
        except ValueError:
            pass                                # already held / conflict
    for i, (dx, dy) in enumerate(sides):
        length = math.hypot(dx, dy)
        if length < tol:
            continue
        e = sc.ref_of(parent, node, "e%d" % i)
        if abs(dy) < tol * length:
            add("horizontal", [e])
        elif abs(dx) < tol * length:
            add("vertical", [e])
        elif abs(abs(dx) - abs(dy)) < tol * length:
            add("diagonal", [e])
        if i == 0 and n < 3:
            continue
        pdx, pdy = sides[i - 1]
        plen = math.hypot(pdx, pdy)
        square = plen > tol and abs(dx * pdx + dy * pdy) < tol * length * plen
        # H next to V is square already; only a slanted pair needs it
        level = lambda x, y: abs(x) < tol or abs(y) < tol
        if square and not (level(dx, dy) and level(pdx, pdy)):
            add("perpendicular", [sc.ref_of(parent, node, "e%d" % (i - 1)
                                             if i else "e%d" % (n - 1)), e])
