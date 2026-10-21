"""The SolidWorks-style Line tool, and the same snapping for the polygon
(2026-10-21, the user: "I want the line to be working just like
SolidWorks").

- Lines CHAIN: each click ends a line and starts the next from that
  point; a double-click, right-click, Enter or Esc ends the chain.
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
    pt, info = snap(scene, event.scenePos(), st["start"])
    if st["start"] is None:
        st["start"], st["start_point"] = pt, info.get("point")
        st["start_origin"] = info.get("origin")
        st["chain"] = [pt]
        draw_overlay(scene, pt, pt, info)
        scene.status.emit("Line: click where it ends — it snaps to "
                          "points, H / V / 45° and lined-up points. "
                          "Double-click, right-click or Esc ends.")
        return
    start = st["start"]
    if math.hypot(pt.x() - start.x(), pt.y() - start.y()) < MIN_LEN:
        end_chain(scene)                       # a click on the start
        return
    node = scene._create("line", dict(x1=round(start.x(), 4),
                                      y1=round(start.y(), 4),
                                      x2=round(pt.x(), 4),
                                      y2=round(pt.y(), 4), width=2.0))
    scene.node_created.emit(node)
    _relations(scene, node, info, st)
    st["start"], st["prev"] = pt, node
    st.setdefault("chain", []).append(pt)
    st["start_point"], st["start_origin"] = None, False
    draw_overlay(scene, pt, pt, info)


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
    kind = info.get("angle") or _angle_of(
        _qp(node, "p1"), _qp(node, "p2"))
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
    pt, info = snap(scene, event.scenePos(), st["start"])
    draw_overlay(scene, st["start"], pt, info)
    event.accept()


def end_chain(scene):
    st = _state(scene)
    st["start"], st["prev"], st["start_point"] = None, None, None
    st["chain"] = []
    _clear(scene)


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
