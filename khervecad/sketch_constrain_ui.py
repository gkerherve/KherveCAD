"""The sketch's CONSTRAIN panel (2026-10-21): click tools in the 2D view
that add `sketch_constraints` rows, the glyphs that show them on the
sketch, the Constraints window and the MCP `sketch_constraint` body.

A constraint tool is one of the scene's tools ("con_<kind>"): each click
picks the nearest point (ends, corners, centres, vertices) or, failing
that, the nearest curve (a line, an edge, a circle) of a shape; once it
has what the kind needs, the constraint is added (a dimension asks its
value, the measured one offered). Every pick must sit in the same
container — constraints belong to the container holding the shapes.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from . import sketch_constraints as sc

PREFIX = "con_"
#: (kind, mdi glyph) in the panel's order: Fusion's CONSTRAINTS first,
#: then the driven dimensions
TOOLS = [
    ("coincident", "mdi.vector-point"),
    ("horizontal", "mdi.arrow-left-right"),
    ("vertical", "mdi.arrow-up-down"),
    ("equal", "mdi.equal"),
    ("parallel", "mdi.format-align-justify"),
    ("perpendicular", "mdi.vector-line"),
    ("tangent", "mdi.circle-half-full"),
    ("concentric", "mdi.circle-double"),
    ("collinear", "mdi.dots-horizontal"),
    ("midpoint", "mdi.format-horizontal-align-center"),
    ("symmetric", "mdi.mirror"),
    ("fix", "mdi.lock-outline"),
    ("distance", "mdi.ruler"),
    ("hdistance", "mdi.arrow-expand-horizontal"),
    ("vdistance", "mdi.arrow-expand-vertical"),
    ("length", "mdi.ruler-square"),
    ("point_line", "mdi.format-line-spacing"),
    ("radius", "mdi.radius-outline"),
    ("diameter", "mdi.diameter-outline"),
    ("angle", "mdi.angle-acute"),
]
#: glyph letters drawn on the sketch per kind
MARK = {"coincident": "●", "horizontal": "H", "vertical": "V", "diagonal": "45°",
        "parallel": "∥", "perpendicular": "⊥", "tangent": "T",
        "equal": "=", "concentric": "◎", "collinear": "—",
        "midpoint": "M", "symmetric": "⇹", "fix": "🔒", "point_on": "⊙",
        "on_edge": "⊸"}
PICK_PX = 10.0
#: point size of the relation marks (H, V, ●, T, ∘ …) in the 2D view
MARK_PT = 11
#: what each constraint does (the tooltips' "what")
WHAT = {
    "coincident": "Makes things touch: two points become one (line ends "
                  "meet, a corner lands on a centre), or a point sits ON "
                  "a line or circle — whichever is highlighted when you "
                  "click.",
    "horizontal": "Makes a line level — or two points level with each "
                  "other.",
    "vertical": "Makes a line upright — or two points one above the "
                "other.",
    "diagonal": "Keeps a line at 45° to the horizontal.",
    "parallel": "Keeps two lines (or edges) parallel.",
    "perpendicular": "Keeps two lines at a right angle.",
    "tangent": "Makes a line or circle just touch a circle.",
    "equal": "Makes two things the SAME SIZE: two lines (or rectangle / "
             "polygon edges) the same length, two circles the same "
             "radius. Change one and the other follows.",
    "concentric": "Puts two circles on one centre.",
    "collinear": "Puts two lines on one straight line.",
    "midpoint": "Puts a point at the middle of a line.",
    "symmetric": "Mirrors two points about a line.",
    "fix": "Locks a point where it is now.",
    "point_on": "Keeps a point on a line or circle.",
    "on_edge": "Keeps a point on an edge of the part under the sketch.",
    "distance": "Drives the distance between two points.",
    "hdistance": "Drives the horizontal distance between two points.",
    "vdistance": "Drives the vertical distance between two points.",
    "length": "Drives a line's length.",
    "point_line": "Drives the distance from a point to a line.",
    "radius": "Drives a circle's radius.",
    "diameter": "Drives a circle's diameter.",
    "angle": "Drives the angle between two lines.",
}
TIPS = {
    PREFIX + "dimension": (
        "Sketch dimension",
        "Fusion's sketch Dimension (D): sets a size that DRIVES the "
        "shapes — type 25 and the line becomes 25 mm.",
        ["A circle: click it, type the diameter.",
         "A line's length: click it, then anywhere empty.",
         "Two lines: the angle between them. Two points: their "
         "distance. A point and a line: the distance between them.",
         "A value may be an expression of the variables (w / 2)."],
        "Delete constraint removes a dimension like any constraint."),
    PREFIX + "delete": (
        "Delete constraint",
        "Removes one constraint or dimension: click its mark on the "
        "sketch (H, V, =, ∥, a value…). The shapes stay where they are.",
        ["Pick the tool; the mark under the cursor turns red.",
         "Click it. Ctrl+Z brings it back."], None),
    "con_auto": ("Auto constrain",
                 "Adds the constraints the sketch already looks like it "
                 "has: nearly level / upright lines, line ends that meet.",
                 ["Select a shape of the sketch (or nothing for the "
                  "whole scope).", "Click Auto constrain."],
                 "The status bar says how many degrees of freedom are "
                 "left."),
    "con_list": ("Constraints",
                 "Lists the sketch's constraints and dimensions, says "
                 "whether it is fully constrained, and edits or deletes "
                 "them.",
                 ["Select a shape of the sketch.", "Click Constraints…"],
                 None),
}
for _kind, _what in WHAT.items():
    TIPS[PREFIX + _kind] = (
        sc.KINDS[_kind][0], _what,
        ["Pick the tool, then click: " + ", then ".join(
            "a " + w for w in sc.KINDS[_kind][1]) + ".",
         "Points (ends, corners, centres) win over curves under the "
         "cursor; right-click or Esc starts again."]
        + (["Type the value — a number or an expression of the "
            "variables (w / 2)."] if sc.KINDS[_kind][2] else []),
        "Drag a shape afterwards and the rest follows the constraints.")


def tool_of(kind):
    return PREFIX + kind


def handles(tool):
    return isinstance(tool, str) and tool.startswith(PREFIX) \
        and (tool[len(PREFIX):] in sc.KINDS
             or tool in (PREFIX + "delete", PREFIX + "dimension"))


#: what to click, step by step, for the tools whose second pick depends
#: on the first (any order)
STEPS = {
    "coincident": ["Coincident: click a point (a line end, corner or "
                   "centre) — or a line or circle.",
                   "Coincident: click the point, line or circle it must "
                   "touch."],
    "tangent": ["Tangent: click a line or circle.",
                "Tangent: click the circle it must touch."],
}


def _wants(kind, picks):
    """What the next click may pick: None = anything."""
    if kind == "coincident":
        if not picks:
            return None
        return None if picks[0][2] == "point" else "point"
    if kind == "tangent":
        if not picks:
            return "curve"
        return "circle" if picks[0][2] == "line" else "curve"
    if kind in sc.TWO_POINT:
        return None if not picks else "point"
    return sc.KINDS[kind][1][len(picks)]


def prompt(kind, n):
    if kind in STEPS:
        return STEPS[kind][min(n, 1)]
    picks = sc.KINDS[kind][1]
    if kind in sc.TWO_POINT:
        return "%s: click a line, or two points." % sc.KINDS[kind][0]
    return "%s: click %s %d of %d." % (sc.KINDS[kind][0],
                                       "a " + picks[min(n, len(picks) - 1)],
                                       n + 1, len(picks))


# -------------------------------------------------------------- picking
def _shape_items(scene):
    from .view2d import ShapeItem
    return [it for it in scene.items()
            if isinstance(it, ShapeItem)
            and getattr(it, "node", None) is not None
            and it.node.type in sc.SHAPES and it.node.parent is not None]


def _entities(node):
    """(name, kind) of every entity of a shape."""
    t = node.type
    if t == "line":
        # a wide line is a slot: its round ends are circles to dimension
        ends = [("a1", "circle"), ("a2", "circle")] \
            if float(node.params.get("width", 0) or 0) > 1e-6 else []
        return [("p1", "point"), ("p2", "point"), ("m", "point"),
                ("l", "line")] + ends
    if t == "rect":
        return [("v%d" % i, "point") for i in range(4)] + [("c", "point")] \
            + [("e%d" % i, "line") for i in range(4)]
    if t == "circle":
        return [("c", "point"), ("o", "circle")]
    n = len(node.params.get("points") or [])
    return [("v%d" % i, "point") for i in range(n)] + \
        [("e%d" % i, "line") for i in range(n)]


def _seg_dist(p, a, b):
    ab = (b[0] - a[0], b[1] - a[1])
    L = ab[0] ** 2 + ab[1] ** 2 or 1e-12
    t = max(0.0, min(1.0, ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1])
                     / L))
    return math.hypot(p[0] - a[0] - t * ab[0], p[1] - a[1] - t * ab[1])


def pick(scene, scene_pos, want=None, midpoints=False):
    """The (node, entity name, kind) nearest *scene_pos* — points before
    curves — of the kinds *want* allows, or None."""
    from .polygon_draw import px_to_scene
    from .view2d_edit import in_frame_coords
    tol = px_to_scene(scene, PICK_PX)
    allowed = {"curve": ("line", "circle")}.get(want, (want,)) \
        if want else ("point", "line", "circle")
    best = None
    for item in _shape_items(scene):
        q = in_frame_coords(item, scene_pos)
        p = (q.x(), q.y())
        node = item.node
        for name, kind in _entities(node):
            if kind not in allowed:
                continue
            try:
                if kind == "point":
                    pt = sc._point(node, name, {})
                    d = math.hypot(p[0] - pt[0], p[1] - pt[1])
                    rank = 0
                    if name == "m":
                        if not midpoints:
                            continue
                        # the middle fifth of the line is its MIDPOINT
                        # (5 px round the exact centre, unmarked, was too
                        # small to find — the user); elsewhere the line
                        a, b = sc._point(node, "p1", {}), \
                            sc._point(node, "p2", {})
                        L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
                        t = ((p[0] - a[0]) * (b[0] - a[0]) +
                             (p[1] - a[1]) * (b[1] - a[1])) / (L * L)
                        off = _seg_dist(p, a, b)
                        if off > tol or abs(t - 0.5) > 0.1:
                            continue
                        d = min(d, off)
                elif kind == "line":
                    a, b = sc._line(node, name, {})
                    d, rank = _seg_dist(p, a, b), 1
                else:
                    c, r = sc._circle(node, name, {})
                    d = abs(math.hypot(p[0] - c[0], p[1] - c[1]) - r)
                    rank = 1
            except (KeyError, ValueError, IndexError):
                continue
            if d <= tol and (best is None or (rank, d) < best[0]):
                best = ((rank, d), (node, name, kind))
    return best[1] if best else None


def _state(scene):
    if not hasattr(scene, "_con_picks"):
        scene._con_picks = []
    return scene._con_picks


def drop(scene):
    scene._con_picks = []
    scene._con_origin_first = False
    scene._con_hover = None
    scene.update()


def hover(scene, event):
    """Highlight what a click would pick now, and say what to do."""
    tool = getattr(scene, "tool", "")
    if tool == DIMENSION:
        # Smart Dimension shows what a click picks: a line's MIDPOINT,
        # a centre, a line, a circle (the user could not find the
        # midpoint)
        hit = pick(scene, event.scenePos(), midpoints=True)
        if hit != getattr(scene, "_con_hover", None):
            scene._con_hover = hit
            if hit is not None:
                scene.status.emit("Smart Dimension — click to pick this "
                                  "%s." % _say(hit))
            for v in scene.views():
                v.viewport().update()
        return
    if not handles(tool) or tool == DELETE:
        return
    kind = tool[len(PREFIX):]
    picks = _state(scene)
    if len(picks) >= len(sc.KINDS[kind][1]):
        return
    hit = pick(scene, event.scenePos(), _wants(kind, picks))
    if hit is not None and picks and hit[0] is picks[0][0] \
            and hit[1] == picks[0][1]:
        hit = None
    if hit != getattr(scene, "_con_hover", None):
        scene._con_hover = hit
        scene.status.emit(prompt(kind, len(picks)) if hit is None else
                          "%s — click to pick this %s." % (
                              prompt(kind, len(picks)), _say(hit)))
        for v in scene.views():
            v.viewport().update()


def _say(hit):
    node, name, k = hit
    if k == "point":
        return {"c": "centre", "p1": "line end", "p2": "line end",
                "m": "midpoint"}.get(name, "corner")
    return "circle" if k == "circle" else "line"


def _paint_entity(view, painter, items, node, name, colour, width):
    """Draw one entity over the sketch, in view pixels."""
    from PyQt5.QtCore import QPointF
    from PyQt5.QtGui import QPen
    from PyQt5.QtCore import Qt
    pen = QPen(colour, width)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    k = sc.kind_of(node, name)
    if k == "point":
        p = _view_point(view, items, node, sc._point(node, name, {}))
        painter.setBrush(colour)
        painter.drawEllipse(p, 5.0, 5.0)
    elif k == "line":
        a, b = sc._line(node, name, {})
        painter.drawLine(_view_point(view, items, node, a),
                         _view_point(view, items, node, b))
    else:
        c, r = sc._circle(node, name, {})
        pts = [_view_point(view, items, node,
                           (c[0] + r * math.cos(t * math.pi / 36),
                            c[1] + r * math.sin(t * math.pi / 36)))
               for t in range(73)]
        for a, b in zip(pts, pts[1:]):
            painter.drawLine(a, b)
    del QPointF


def _paint_dimension_picks(view, painter):
    """Smart Dimension: the first pick orange, what a click would pick
    blue — a point named (Midpoint, Centre…) so it can be found."""
    from PyQt5.QtCore import QRectF, Qt
    from PyQt5.QtGui import QColor
    scene = view.scene()
    items = {it.node.id: it for it in _shape_items(scene)}
    painter.save()
    try:
        for node, name, _k in _state(scene):
            _paint_entity(view, painter, items, node, name,
                          QColor(230, 120, 20, 230), 4.0)
        hot = getattr(scene, "_con_hover", None)
        if hot is not None:
            node, name, k = hot
            colour = QColor(230, 120, 20) if k == "point" else \
                QColor(33, 118, 199, 220)
            _paint_entity(view, painter, items, node, name, colour, 4.0)
            if k == "point":
                p = _view_point(view, items, node,
                                sc._point(node, name, {}))
                painter.resetTransform()
                font = painter.font()
                font.setBold(True)
                painter.setFont(font)
                painter.setPen(QColor("#c26a00"))
                painter.drawText(QRectF(p.x() + 9, p.y() + 6, 120, 18),
                                 int(Qt.AlignLeft | Qt.AlignVCenter),
                                 _say(hot).capitalize())
    except Exception:                       # never raise out of a paint
        pass
    finally:
        painter.restore()


def paint_picks(view, painter):
    """The first pick in orange, what the cursor would pick in blue, and
    the step to do written at the top of the view."""
    from PyQt5.QtCore import Qt, QRectF
    from PyQt5.QtGui import QColor
    scene = view.scene()
    tool = getattr(scene, "tool", "")
    if tool == DIMENSION:
        _paint_dimension_picks(view, painter)
        return
    if not handles(tool) or tool == DELETE:
        return
    kind = tool[len(PREFIX):]
    items = {it.node.id: it for it in _shape_items(scene)}
    picks = _state(scene)
    painter.save()
    painter.resetTransform()
    painter.setRenderHint(painter.Antialiasing, True)
    for node, name, _k in picks:
        _paint_entity(view, painter, items, node, name,
                      QColor(230, 120, 20, 230), 4.0)
    hot = getattr(scene, "_con_hover", None)
    if hot is not None:
        _paint_entity(view, painter, items, hot[0], hot[1],
                      QColor(33, 118, 199, 220), 4.0)
    text = prompt(kind, len(picks))
    font = painter.font()
    font.setPointSizeF(10.5)
    painter.setFont(font)
    w = painter.fontMetrics().horizontalAdvance(text) + 20
    box = QRectF((view.viewport().width() - w) / 2, 8, w, 24)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(33, 118, 199, 215))
    painter.drawRoundedRect(box, 6, 6)
    painter.setPen(QColor("white"))
    painter.drawText(box, int(Qt.AlignCenter), text)
    painter.restore()


def _ask_value(scene, kind, measured):
    hook = getattr(scene, "ask_value", None)
    if hook is not None:
        return hook(kind, measured)
    from PyQt5.QtWidgets import QInputDialog
    from . import language
    views = scene.views()
    unit = "°" if kind == "angle" else "mm"
    text, ok = QInputDialog.getText(
        views[0] if views else None, language.tr(sc.KINDS[kind][0]),
        language.tr("Value (%s) — a number or an expression:") % unit,
        text="%g" % round(measured, 4))
    return text.strip() if ok and text.strip() else None


def _value(text):
    """A typed dimension: a number, a calculation of numbers ("52 - 10",
    "84 / 2" — the user) worked out, else an expression of the document
    variables kept as written."""
    try:
        return float(text)
    except (TypeError, ValueError):
        pass
    from .expr import resolve
    got = resolve(str(text).replace(",", "."), {}, None)
    if got is not None:
        return round(got, 6)
    return text                     # an expression of the variables


def press(scene, event):
    from PyQt5.QtCore import Qt
    if scene.tool == DELETE:
        delete_press(scene, event)
        return
    if scene.tool == DIMENSION:
        dimension_press(scene, event)
        return
    event.accept()
    if event.button() == Qt.RightButton:
        drop(scene)
        return
    if event.button() != Qt.LeftButton:
        return
    kind = scene.tool[len(PREFIX):]
    picks = _state(scene)
    wants = sc.KINDS[kind][1]
    want = _wants(kind, picks)
    hit = pick(scene, event.scenePos(), want)
    if hit is None:
        from . import face_outline         # a relation to the face's edge
        try:
            hit = face_outline.reference(scene, event.scenePos(), want)
        except Exception:
            hit = None
    if hit is None or (kind in sc.TWO_POINT and not picks
                       and hit[2] == "circle"):
        scene.status.emit(prompt(kind, len(picks)))
        return
    node, name, k = hit
    if picks and node.parent is not picks[0][0].parent:
        scene.status.emit("Constraints join shapes of one group: pick a "
                          "shape beside the first.")
        return
    if picks and hit[0] is picks[0][0] and hit[1] == picks[0][1]:
        scene.status.emit("That is the first pick — click something else.")
        return
    picks.append(hit)
    scene._con_hover = None
    done = len(picks) == len(wants) or \
        (kind in sc.TWO_POINT and k == "line" and len(picks) == 1)
    if not done:
        scene.status.emit(prompt(kind, len(picks)))
        scene.update()
        return
    finish(scene, kind)


def finish(scene, kind):
    picks = list(_state(scene))
    drop(scene)
    if kind == "coincident" and any(k != "point" for _n, _e, k in picks):
        kind = "point_on"              # a point ON a line or circle
    if kind == "point_on" and picks[0][2] != "point":
        picks.reverse()                # the point first
    if kind == "tangent" and picks[1][2] == "line":
        picks.reverse()                # the line first, the circle second
    container = picks[0][0].parent
    refs = [sc.ref_of(container, node, name) for node, name, _ in picks]
    value = None
    if sc.KINDS[kind][2]:
        text = _ask_value(scene, kind, sc.measure(container, kind, refs))
        if text is None:
            return None
        value = _value(text)
    try:
        report = sc.add(scene.model, container, kind, refs, value)
    except ValueError as exc:
        scene.status.emit(str(exc))
        return None
    scene.status.emit("%s added — %s" % (sc.KINDS[kind][0],
                                         sc.status_text(report)))
    return report


def key(scene, event):
    from PyQt5.QtCore import Qt
    if event.key() == Qt.Key_Escape and _state(scene):
        drop(scene)
        return True
    return False


# --------------------------------------------------------------- glyphs
def _anchor(view, items, node, name):
    """Where an entity's marks start, in VIEW pixels."""
    from PyQt5.QtCore import QPointF
    item = _item_or_sibling(items, node)
    if item is None:
        return None
    k = sc.kind_of(node, name)
    if k == "point":
        p = sc._point(node, name, {})
    elif k == "line":
        a, b = sc._line(node, name, {})
        p = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    else:
        c, r = sc._circle(node, name, {})
        p = (c[0] + r * 0.707, c[1] + r * 0.707)
    frame = item.parentItem()
    q = QPointF(*p)
    if frame is not None:
        q = frame.mapToScene(q)
    return view.mapFromScene(q)


def _top(node, root):
    while node.parent is not None and node.parent is not root:
        node = node.parent
    return node


def _under(node, scope):
    while node is not None:
        if node is scope:
            return True
        node = node.parent
    return False


def shown_containers(scene):
    """The sketches whose dimensions and relations are drawn: each
    sketch's own, wherever its shapes are on the view — they belong to
    their Object and move with it (the user, 2026-10-25). In the Object
    tab only the active Object's."""
    model = scene.model
    resolver = getattr(scene, "isolation_resolver", None)
    scope = resolver() if resolver else None
    drawn = {id(it.node.parent) for it in _shape_items(scene)}
    assembly = getattr(scene, "assembly_mode", None)
    assembly = bool(assembly and assembly())
    from .sketch_dims3d import _in_object
    out = []
    for c in sc.containers(model):
        if assembly and _in_object(c, model.root):
            continue          # the assembly shows parts, not sketches
        if id(c) not in drawn:
            # (only what is drawn: an Object's definition is HIDDEN by
            # design — "visible" would drop every Object's dimensions)
            continue
        if scope is not None and scope is not model.root and \
                not _under(c, scope):
            continue
        out.append(c)
    return out


#: px between marks sharing a spot, and the size a mark answers clicks
MARK_GAP = 4
MARK_PICK = 9


def glyphs(view):
    """Every constraint mark on the sketch: [(QRectF in view pixels,
    text, container, row index)]. Marks that would land on the same spot
    (an H and an = on one line) are laid out side by side."""
    from PyQt5.QtCore import QPointF, QRectF
    from PyQt5.QtGui import QFont, QFontMetrics
    scene = view.scene()
    model = getattr(scene, "model", None)
    if model is None:
        return []
    items = {it.node.id: it for it in _shape_items(scene)}
    font = QFont(view.font())
    # readable: at 8 pt a coincident or point-on mark was a speck (the
    # user could not read it); each sits on its own small tile
    font.setPointSize(MARK_PT)
    font.setBold(True)
    fm = QFontMetrics(font)
    taken = {}                      # spot key -> x advance used so far
    out = []
    view._dim_leaders = []          # (where it belongs, the moved label)

    def place(spot, text, cont, index):
        key = (round(spot.x() / 6), round(spot.y() / 6))
        dx = taken.get(key, 0)
        w = fm.horizontalAdvance(text) + 8
        taken[key] = dx + w + MARK_GAP
        x, y = spot.x() + 6 + dx, spot.y() - 7 - fm.ascent()
        out.append((QRectF(x, y, w, fm.height() + 2), text, cont, index))

    for cont in shown_containers(scene):
        for index, row in enumerate(sc.rows(cont)):
            spots = []
            try:
                for ref in row["refs"]:
                    node, name = sc.entity(cont, ref)
                    spot = _anchor(view, items, node, name)
                    if spot is not None:
                        spots.append(spot)
            except (KeyError, ValueError, IndexError):
                continue
            if not spots:
                continue
            if "value" in row:
                c = QPointF(sum(s.x() for s in spots) / len(spots),
                            sum(s.y() for s in spots) / len(spots))
                unit = "°" if row["kind"] == "angle" else ""
                prefix = {"radius": "R", "diameter": "Ø"}.get(
                    row["kind"], "")
                moved = row.get("label_offset")
                if moved and row["kind"] not in LINEAR:
                    # dragged out of the way (dim_edit), in model units
                    from .dim_edit import scale
                    k = scale(view)
                    home = QPointF(c)
                    c = QPointF(c.x() + moved[0] * k, c.y() + moved[1] * k)
                    place(c, "%s%s%s" % (prefix, row["value"], unit), cont,
                          index)
                    if row["kind"] not in ("radius", "diameter"):
                        # (R and Ø draw their own leader: _paint_radius)
                        view._dim_leaders.append((home, out[-1][0]))
                    continue
                place(c, "%s%s%s" % (prefix, row["value"], unit), cont,
                      index)
            else:
                if row["kind"] == "symmetric" and len(spots) == 3:
                    # on its two points only: every pair mirrored about
                    # one centerline piled its mark up on that line
                    spots = spots[:2]
                for spot in spots:
                    place(spot, MARK.get(row["kind"], "?"), cont, index)
    return out, font


#: dimensions drawn as a real dimension line between what they measure
LINEAR = ("distance", "hdistance", "vdistance", "length", "point_line")


def _item_or_sibling(items, node):
    """The 2D item drawing *node*, else one drawing a shape of the same
    sketch: a hidden construction point (a "Reference point") has no
    item, and without its sketch's frame its dimension end was drawn in
    the wrong place (on the other hole)."""
    item = items.get(node.id)
    if item is None and node.parent is not None:
        for sib in node.parent.children:
            item = items.get(sib.id)
            if item is not None:
                break
    return item


def _view_point(view, items, node, xy):
    from PyQt5.QtCore import QPointF
    item = _item_or_sibling(items, node)
    q = QPointF(*xy)
    frame = item.parentItem() if item is not None else None
    if frame is not None:
        q = frame.mapToScene(q)
    return QPointF(view.mapFromScene(q))


def linear_ends(view, items, cont, row):
    """(a, b) in view pixels between which a LINEAR dimension is drawn —
    the points it belongs to (SolidWorks' smart dimension), or None."""
    from PyQt5.QtCore import QPointF
    kind = row["kind"]
    ents = [sc.entity(cont, r) for r in row["refs"]]
    if kind == "length":
        node, name = ents[0]
        a, b = sc._line(node, name, {})
        return _view_point(view, items, node, a), \
            _view_point(view, items, node, b)
    if kind == "point_line":
        (pn, pname), (ln, lname) = ents
        p = sc._point(pn, pname, {})
        a, b = sc._line(ln, lname, {})
        dx, dy = b[0] - a[0], b[1] - a[1]
        d2 = dx * dx + dy * dy or 1.0
        t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / d2
        foot = (a[0] + dx * t, a[1] + dy * t)
        return _view_point(view, items, pn, p), \
            _view_point(view, items, ln, foot)
    (an, aname), (bn, bname) = ents
    pa = _view_point(view, items, an, sc._point(an, aname, {}))
    pb = _view_point(view, items, bn, sc._point(bn, bname, {}))
    if kind == "hdistance":
        pb = QPointF(pb.x(), pa.y())
    elif kind == "vdistance":
        pb = QPointF(pa.x(), pb.y())
    return pa, pb


def _paint_radius(view, painter, items, cont, index, row, ink, bg):
    """A radius / diameter as SolidWorks draws it: a leader from the
    centre through the edge (an arrow there) to the value, which the
    Select or Smart Dimension tool drags anywhere (`label_offset`) —
    the leader swings to follow it."""
    import math
    from PyQt5.QtCore import QPointF, QRectF, Qt
    from PyQt5.QtGui import QBrush, QPen, QPolygonF
    from .dim_edit import scale
    node, name = sc.entity(cont, row["refs"][0])
    c, r = sc._circle(node, name, {})
    pc = _view_point(view, items, node, c)
    pr = _view_point(view, items, node, (c[0] + r, c[1]))
    rpx = math.hypot(pr.x() - pc.x(), pr.y() - pc.y())
    k = scale(view)
    moved = row.get("label_offset") or (0, 0)
    label = QPointF(pc.x() + (rpx + 30) * 0.707 + moved[0] * k,
                    pc.y() - (rpx + 30) * 0.707 + moved[1] * k)
    dx, dy = label.x() - pc.x(), label.y() - pc.y()
    dl = math.hypot(dx, dy) or 1.0
    ux, uy = dx / dl, dy / dl
    edge = QPointF(pc.x() + ux * rpx, pc.y() + uy * rpx)
    pen = QPen(ink, 1.4)
    pen.setCosmetic(True)
    painter.setPen(pen)
    start = pc if row["kind"] == "radius" else \
        QPointF(pc.x() - ux * rpx, pc.y() - uy * rpx)
    painter.drawLine(start, label)
    painter.setBrush(QBrush(ink))
    base = QPointF(edge.x() - ux * 9, edge.y() - uy * 9)
    painter.drawPolygon(QPolygonF([
        edge, QPointF(base.x() - uy * 4, base.y() + ux * 4),
        QPointF(base.x() + uy * 4, base.y() - ux * 4)]))
    painter.drawEllipse(pc, 2.2, 2.2)
    text = ("R%s" if row["kind"] == "radius" else "Ø%s") % row["value"]
    font = painter.font()
    font.setBold(True)
    painter.setFont(font)
    fm = painter.fontMetrics()
    tw = fm.horizontalAdvance(text)
    chip = QRectF(label.x() - tw / 2 - 5, label.y() - fm.height() / 2 - 2,
                  tw + 10, fm.height() + 4)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(bg))
    painter.drawRoundedRect(chip, 4, 4)
    painter.setPen(QPen(ink, 1.0))
    painter.setBrush(Qt.NoBrush)
    painter.drawText(chip, int(Qt.AlignCenter), text)
    if hasattr(view, "_dim_hits"):
        view._dim_hits.append((QRectF(chip), (cont, "constraint", index)))
    return True


def _paint_dimensions(view, painter):
    """Driving dimensions as SolidWorks draws them: a dimension line
    with arrows between the points / line they belong to, its value a
    chip you click to type (dim_edit). Returns the rows drawn."""
    from PyQt5.QtGui import QColor
    scene = view.scene()
    model = getattr(scene, "model", None)
    if model is None or not hasattr(view, "_dim_screen"):
        return set()
    items = {it.node.id: it for it in _shape_items(scene)}
    ink, bg = QColor("#1565c0"), QColor(255, 255, 255, 235)
    drawn = set()
    hidden = not getattr(scene, "show_sketch_dims", True)
    for cont in shown_containers(scene):
        for index, row in enumerate(sc.rows(cont)):
            if hidden:
                # View ▸ Show Smart Dimensions off: no line, no glyph
                if "value" in row:
                    drawn.add((cont.id, index))
                continue
            if row["kind"] in ("radius", "diameter") and "value" in row:
                try:
                    if _paint_radius(view, painter, items, cont, index,
                                     row, ink, bg):
                        drawn.add((cont.id, index))
                except Exception:            # never leave the painter open
                    import traceback
                    traceback.print_exc()
                continue
            if row["kind"] not in LINEAR or "value" not in row:
                continue
            try:
                ends = linear_ends(view, items, cont, row)
            except (KeyError, ValueError, IndexError, TypeError):
                continue
            if ends is None:
                continue
            view._dim_ctx = (cont, "constraint", index)
            off = row.get("offset")
            from .dim_edit import scale
            px = off * scale(view) if isinstance(off, (int, float)) \
                else 26
            try:
                view._dim_screen(painter, ends[0], ends[1], color=ink,
                                 bg=bg, text=str(row["value"]),
                                 offset=px, dots=True)
            finally:
                view._dim_ctx = None
            drawn.add((cont.id, index))
    return drawn


def paint(view, painter):
    """The constraints on the sketch: a mark at each constrained entity
    (side by side where they meet), dimensions as dimension lines; the
    mark under the cursor red while the delete tool is on; picks
    ringed."""
    from PyQt5.QtCore import QPointF, Qt
    from PyQt5.QtGui import QColor, QPen
    scene = view.scene()
    paint_picks(view, painter)
    marks = glyphs(view)
    if not marks:
        return
    marks, font = marks
    painter.save()
    painter.resetTransform()
    drawn = _paint_dimensions(view, painter)
    painter.restore()
    deleting = getattr(scene, "tool", None) == DELETE
    hot = getattr(scene, "_con_hot", None)
    painter.save()
    painter.resetTransform()
    painter.setFont(font)
    ink, red = QColor("#c75b12"), QColor("#d32f2f")
    for rect, text, cont, index in marks:
        is_hot = deleting and hot == (cont.id, index)
        if (cont.id, index) in drawn and not is_hot:
            continue                     # drawn as a dimension line
        if "value" not in sc.rows(cont)[index]:
            # a relation mark: on a white tile, outlined in its colour
            painter.setPen(QPen(red if is_hot else ink, 1.0))
            painter.setBrush(QColor(255, 255, 255, 235))
            painter.drawRoundedRect(rect, 3, 3)
            painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(red if is_hot else ink, 1.2))
        if is_hot:
            painter.drawRect(rect.adjusted(-1, -1, 1, 1))
        painter.drawText(rect, int(Qt.AlignCenter), text)
        if "value" in sc.rows(cont)[index] and \
                hasattr(view, "_dim_hits"):
            # R / Ø / angle values: click to type too
            view._dim_hits.append((rect, (cont, "constraint", index)))
    # a dragged-away Ø / R / angle points back at what it sizes
    lead = QPen(QColor("#c75b12"), 1.0)
    lead.setCosmetic(True)
    painter.setPen(lead)
    for home, rect in getattr(view, "_dim_leaders", []):
        x = min(max(home.x(), rect.left()), rect.right())
        y = min(max(home.y(), rect.top()), rect.bottom())
        painter.drawLine(home, QPointF(x, y))
        painter.drawEllipse(home, 2.0, 2.0)
    painter.restore()


# ---------------------------------------------------- smart dimension
DIMENSION = PREFIX + "dimension"


def _parallel_point(first, second):
    """When the two picked lines are parallel: a pick of a point on the
    first (its start), else None."""
    import math
    try:
        a1, b1 = sc._line(first[0], first[1], {})
        a2, b2 = sc._line(second[0], second[1], {})
    except (KeyError, ValueError, IndexError):
        return None
    u = (b1[0] - a1[0], b1[1] - a1[1])
    v = (b2[0] - a2[0], b2[1] - a2[1])
    lu, lv = math.hypot(*u), math.hypot(*v)
    if lu < 1e-9 or lv < 1e-9 or \
            abs(u[0] * v[1] - u[1] * v[0]) / (lu * lv) > 1e-6:
        return None
    node, name = first[0], first[1]
    if node.type == "line":
        return node, "p1", "point"
    if name.startswith("e"):
        return node, "v" + name[1:], "point"
    return None


def _smart(first, second):
    """(kind, picks) a Fusion-style sketch dimension makes of one or two
    picks — None when it needs another click."""
    k1 = first[2]
    if second is None:
        # a circle WAITS (the user: a click on a circle gave its diameter
        # at once, so two circles' centres could not be dimensioned): a
        # second circle / point / line measures from its centre, an
        # empty click or the same circle again gives its size
        return None
    if k1 == "circle" and second[:2] == first[:2]:
        # a slot's end gives its radius, a circle its diameter
        return ("radius" if str(first[1]).startswith("a") else
                "diameter"), [first]
    if k1 == "circle":
        first = _centre(first)
        k1 = "point"
    if second[2] == "circle" and k1 != "circle":
        second = _centre(second)
    k2 = second[2]
    if k1 == "line" and k2 == "line":
        if second[:2] == first[:2]:
            return "length", [first]
        para = _parallel_point(first, second)
        if para is not None:
            # parallel lines: the distance between them (SolidWorks),
            # not an angle of 0
            return "point_line", [para, second]
        return "angle", [first, second]
    if k1 == "point" and k2 == "point":
        return "distance", [first, second]
    if k1 == "point" and k2 == "line":
        return "point_line", [first, second]
    if k1 == "line" and k2 == "point":
        return "point_line", [second, first]
    return None


def _near_origin(scene, pos):
    """Is the click on the sketch's origin (within face_outline.SNAP_PX)?"""
    import math
    from . import face_outline
    views = scene.views()
    k = abs(views[0].transform().m11()) if views else 1.0
    return math.hypot(pos.x(), pos.y()) * k <= face_outline.SNAP_PX


def _centre(pick):
    """A circle pick as its centre point: a circle's c, a slot end's
    centre (its line's end)."""
    node, name, _kind = pick
    if node.type == "circle":
        return (node, "c", "point")
    if str(name).startswith("a"):
        return (node, "p1" if name == "a1" else "p2", "point")
    return pick


def _rehome(scene, pick, container):
    """A "Reference point" made by a click on the model, remade inside
    *container*; None when *pick* is not one."""
    node, name, kind = pick
    if node.parent is container or node.name != "Reference point" or \
            node.params.get("modifier") != "%" or kind != "point":
        return None
    from PyQt5.QtCore import QPointF
    from . import face_outline
    old = node.parent
    x, y = float(node.params["x"]), float(node.params["y"])
    try:
        ref = sc.ref_of(old, node, "c")
        rows = [r for r in sc.rows(old)
                if not (r["kind"] == "fix" and r["refs"] == [ref])]
        if any(ref in r.get("refs", ()) for r in rows):
            return None                  # used by another dimension
        if old.children and old.children[-1] is not node:
            return None                  # removing it would renumber rows
        old.params["constraints"] = rows
        if not rows:
            old.params.pop("constraints", None)
        scene.model.remove_node(node)
        made = face_outline.reference(scene, QPointF(x, y), "point",
                                      parent=container)
    except Exception:
        return None
    return made


def _editable(pick):
    """Is the pick in a sketch still being drawn (not one an extrude has
    taken into its Regions)?"""
    parent = pick[0].parent
    return parent is not None and parent.type != "regions"


def _reference_copy(scene, pick, container):
    """A fixed construction point in *container* where *pick*'s point (a
    circle's centre) lies; (node, "c", "point") or None."""
    from PyQt5.QtCore import QPointF
    from .view2d_edit import in_frame_coords
    node, name, kind = pick
    if kind == "circle":
        name, kind = ("p1" if name == "a1" else "p2") \
            if str(name).startswith("a") else "c", "point"
    if kind == "line":
        return _reference_edge(scene, node, name, container)
    if kind != "point":
        return None
    try:
        x, y = sc._point(node, name, {})
    except (KeyError, ValueError, IndexError):
        return None
    items = getattr(scene, "_items", {})
    src = items.get(node.id)
    frame = src.parentItem() if src is not None else None
    world = frame.mapToScene(QPointF(x, y)) if frame is not None \
        else QPointF(x, y)
    probe = next((items[c.id] for c in container.children
                  if c.id in items), None)
    q = in_frame_coords(probe, world) if probe is not None else world
    ref = scene.model.add_node(
        "circle", dict(x=round(q.x(), 4), y=round(q.y(), 4), radius=0.25,
                       modifier="%"), parent=container,
        name="Reference point")
    try:
        sc.add(scene.model, container, "fix",
               [sc.ref_of(container, ref, "c")])
    except Exception:
        pass
    return (ref, "c", "point")


def _reference_edge(scene, node, name, container):
    """A fixed construction line in *container* along *node*'s edge /
    line *name* (another sketch's rectangle side, the user's boss
    dimensioned to the base's edge); (line, "l", "line") or None."""
    from PyQt5.QtCore import QPointF
    from .view2d_edit import in_frame_coords
    try:
        a, b = sc._line(node, name, {})
    except (KeyError, ValueError, IndexError):
        return None
    items = getattr(scene, "_items", {})
    src = items.get(node.id)
    frame = src.parentItem() if src is not None else None
    probe = next((items[c.id] for c in container.children
                  if c.id in items), None)

    def local(p):
        w = frame.mapToScene(QPointF(*p)) if frame is not None \
            else QPointF(*p)
        q = in_frame_coords(probe, w) if probe is not None else w
        return round(q.x(), 4), round(q.y(), 4)
    (x1, y1), (x2, y2) = local(a), local(b)
    ref = scene.model.add_node(
        "line", dict(x1=x1, y1=y1, x2=x2, y2=y2, width=0.2, modifier="%"),
        parent=container, name="Reference edge")
    try:
        for end in ("p1", "p2"):
            sc.add(scene.model, container, "fix",
                   [sc.ref_of(container, ref, end)])
    except Exception:
        pass
    return (ref, "l", "line")


def _hide_references(scene, chosen):
    """A face's edge / point copied in to dimension to (face_outline.
    reference) is hidden once the dimension holds it (the user): the
    dimension still measures from it."""
    for node, _name, _kind in chosen:
        if node.name in ("Reference edge", "Reference point") and \
                node.visible:
            scene.model.set_visible(node, False)


def dimension_press(scene, event):
    """The sketch Dimension tool: a circle then a click off the geometry
    (or on it again) its diameter, then another circle / point / line the
    distance from its centre; a line then a click off the geometry (or
    on the same line) its length;
    two lines the angle; two points the distance; a point and a line
    the distance between them. The value typed DRIVES the shapes."""
    from PyQt5.QtCore import Qt
    event.accept()
    if event.button() != Qt.LeftButton:
        drop(scene)
        return
    picks = _state(scene)
    # a line's midpoint too, right at it (the user: the middle of a line
    # to a circle's centre)
    hit = pick(scene, event.scenePos(), midpoints=True)
    if hit is None:
        # on the face's own edge or corner: dimension to it (SolidWorks)
        from . import face_outline
        try:
            hit = face_outline.reference(
                scene, event.scenePos(),
                parent=picks[0][0].parent if picks else None)
        except Exception:
            hit = None
    if not picks and getattr(scene, "_con_origin_first", False):
        # the origin was clicked first, before any sketch was known: it
        # joins the sketch of this second pick
        scene._con_origin_first = False
        if hit is not None:
            from PyQt5.QtCore import QPointF
            from . import face_outline
            origin = face_outline.reference(scene, QPointF(0.0, 0.0),
                                            "point", parent=hit[0].parent)
            if origin is not None:
                picks.append(origin)
    if not picks:
        if hit is None:
            if _near_origin(scene, event.scenePos()):
                scene._con_origin_first = True
                scene.status.emit("Dimension: the origin — now click a "
                                  "point, a line's middle or a circle.")
                return
            scene.status.emit("Dimension: click a line, a circle or a "
                              "point.")
            return
        made = _smart(hit, None)
        if made is None:
            picks.append(hit)
            scene.status.emit(
                "Dimension: click a second line or point — or anywhere "
                "empty for this one's length." if hit[2] == "line" else
                "Dimension: click another circle, a point or a line for "
                "the distance from the centre — or anywhere empty (or "
                "the circle again) for its diameter."
                if hit[2] == "circle" else
                "Dimension: click the second point or a line.")
            scene.update()
            return
    else:
        first = picks[0]
        if hit is None and first[1] == "m" and first[0].type == "line":
            first = (first[0], "l", "line")   # its midpoint, then empty
        if hit is None:
            # empty space: a line's length, a circle's size
            hit = first if first[2] in ("line", "circle") else None
        if hit is None:
            scene.status.emit("Dimension: click the second point or line.")
            return
        if hit[0].parent is not first[0].parent:
            # the part's origin / a face point clicked FIRST was put in the
            # sketch Group; the hole's circle lives in its extrude — move
            # that reference beside the second pick, whichever came first
            first = _rehome(scene, first, hit[0].parent) or first
            hit = _rehome(scene, hit, first[0].parent) or hit
        if hit[0].parent is not first[0].parent:
            # a shape of ANOTHER sketch (the circle of the extruded one,
            # the user's): a fixed Reference point copy of its centre /
            # point in the sketch being drawn, and the dimension to it
            target, other = (first, hit) if _editable(first) or \
                not _editable(hit) else (hit, first)
            copy = _reference_copy(scene, other, target[0].parent)
            if copy is not None:
                if other is hit:
                    hit = copy
                else:
                    first = copy
        if hit[0].parent is not first[0].parent:
            scene.status.emit("Dimensions join shapes of one sketch — "
                              "pick a point, a line or a circle of the "
                              "other one.")
            return
        made = _smart(first, hit)
    drop(scene)
    if made is None:
        scene.status.emit("Those two cannot be dimensioned together.")
        return
    kind, chosen = made
    container = chosen[0][0].parent
    refs = [sc.ref_of(container, n, name) for n, name, _k in chosen]
    text = _ask_value(scene, kind, sc.measure(container, kind, refs))
    if text is None:
        return
    same = [i for i, r in enumerate(sc.rows(container))
            if r["kind"] == kind and sorted(r["refs"]) == sorted(refs)]
    if same:
        # already dimensioned: change that one, never stack a second on
        # top of it (the two then hid each other)
        try:
            report = sc.set_value(scene.model, container, same[0],
                                  _value(text))
        except ValueError as exc:
            scene.status.emit(str(exc))
            return
        scene.status.emit("%s changed to %s — %s" % (
            sc.KINDS[kind][0], text, sc.status_text(report)))
        return
    try:
        report, scaled = sc.add_dimension(scene.model, container, kind,
                                          refs, _value(text))
    except ValueError as exc:
        scene.status.emit(str(exc))
        return
    _hide_references(scene, chosen)
    scene.status.emit("%s %s — %s%s" % (
        sc.KINDS[kind][0], text, sc.status_text(report),
        " The whole sketch was scaled to it (first dimension)."
        if scaled else ""))


# --------------------------------------------------- delete constraint
DELETE = PREFIX + "delete"


def mark_at(view, view_pos):
    """(container, row index) of the mark under a VIEW pixel, or None."""
    found = glyphs(view)
    if not found:
        return None
    best = None
    for rect, _t, cont, index in found[0]:
        c = rect.center()
        d = max(abs(c.x() - view_pos.x()) - rect.width() / 2,
                abs(c.y() - view_pos.y()) - rect.height() / 2, 0)
        if d <= MARK_PICK and (best is None or d < best[0]):
            best = (d, cont, index)
    return best[1:] if best else None


def delete_press(scene, event):
    from PyQt5.QtCore import Qt
    event.accept()
    if event.button() != Qt.LeftButton or not scene.views():
        return
    view = scene.views()[0]
    hit = mark_at(view, view.mapFromScene(event.scenePos()))
    if hit is None:
        scene.status.emit("Delete constraint: click a constraint's mark "
                          "(H, V, =, a dimension's value…).")
        return
    cont, index = hit
    row = sc.rows(cont)[index]
    sc.remove(scene.model, cont, index)
    scene._con_hot = None
    scene.status.emit("Removed %s." % sc.describe(cont, row))
    scene.update()


def delete_move(scene, event):
    if not scene.views():
        return
    view = scene.views()[0]
    hit = mark_at(view, view.mapFromScene(event.scenePos()))
    hot = (hit[0].id, hit[1]) if hit else None
    if hot != getattr(scene, "_con_hot", None):
        scene._con_hot = hot
        scene.update()


# ---------------------------------------------------- window and panel
def container_for(win):
    """Where the panel's commands act: the parent of a selected shape,
    a selected container, else the scope's root."""
    sel = [win.model.find(i) for i in getattr(win, "_selected_ids", ())]
    sel = [n for n in sel if n is not None]
    for n in sel:
        if n.type in sc.SHAPES and n.parent is not None:
            return n.parent
        if n.params.get(sc.KEY):
            return n
    iso = win.builder.isolated_component()
    return iso if iso is not None else win.model.root


def auto(win):
    cont = container_for(win)
    n = sc.auto_constrain(win.model, cont)
    report = sc.solve(cont, write=False)
    win.statusBar().showMessage(
        "Auto constrain: %d constraint%s added — %s" % (
            n, "" if n == 1 else "s", sc.status_text(report)), 8000)
    return n


def open_window(win):
    from PyQt5.QtWidgets import (QDialog, QHBoxLayout, QLabel,
                                 QListWidget, QPushButton, QVBoxLayout,
                                 QInputDialog, QMessageBox)
    from . import language
    dlg = getattr(win, "_constraints_window", None)
    if dlg is None:
        dlg = QDialog(win)
        dlg.setWindowTitle(language.tr("Sketch constraints"))
        lay = QVBoxLayout(dlg)
        dlg.status = QLabel()
        dlg.status.setWordWrap(True)
        dlg.list = QListWidget()
        lay.addWidget(dlg.status)
        lay.addWidget(dlg.list)
        from PyQt5.QtWidgets import QCheckBox
        from PyQt5.QtCore import QSettings
        dlg.scale_first = QCheckBox(language.tr(
            "Scale the whole sketch on its first dimension"))
        dlg.scale_first.setToolTip(language.tr(
            "SolidWorks' option: the first size you give a sketch scales "
            "every shape in it to match; later dimensions drive only "
            "their own shapes."))
        dlg.scale_first.setChecked(sc.scale_first_enabled())
        dlg.scale_first.toggled.connect(lambda on: QSettings(
            "Kherve", "KherveCAD").setValue(sc.SCALE_FIRST, bool(on)))
        lay.addWidget(dlg.scale_first)
        row = QHBoxLayout()
        lay.addLayout(row)
        buttons = {}
        for key, text in (("value", "Edit value…"), ("delete", "Delete"),
                          ("auto", "Auto constrain"),
                          ("close", "Close")):
            b = QPushButton(language.tr(text))
            row.addWidget(b)
            buttons[key] = b

        def fill():
            cont = container_for(win)
            dlg.container = cont
            dlg.list.clear()
            for r in sc.rows(cont):
                dlg.list.addItem(sc.describe(cont, r))
            dlg.status.setText(language.tr(
                "%s — %d constraint(s). %s") % (
                cont.name, len(sc.rows(cont)),
                sc.status_text(sc.solve(cont, write=False))))

        def delete():
            i = dlg.list.currentRow()
            if i >= 0:
                sc.remove(win.model, dlg.container, i)
                fill()

        def edit():
            i = dlg.list.currentRow()
            rs = sc.rows(dlg.container)
            if i < 0 or "value" not in rs[i]:
                return
            text, ok = QInputDialog.getText(
                dlg, language.tr("Value"), language.tr("New value:"),
                text=str(rs[i]["value"]))
            if ok and text.strip():
                try:
                    sc.set_value(win.model, dlg.container, i,
                                 _value(text.strip()))
                except ValueError as exc:
                    QMessageBox.warning(dlg, language.tr("Constraints"),
                                        str(exc))
                fill()

        buttons["value"].clicked.connect(edit)
        buttons["delete"].clicked.connect(delete)
        buttons["auto"].clicked.connect(lambda: (auto(win), fill()))
        buttons["close"].clicked.connect(dlg.close)
        dlg.fill = fill
        win._constraints_window = dlg
    dlg.fill()
    dlg.show()
    dlg.raise_()
    return dlg


def _keep(win, act, tool):
    """Unticked: once the click has done its work, tick it again if the
    tool is still this one (another tool picked changes it first)."""
    from PyQt5.QtCore import QTimer

    def check():
        if win.view2d.scene().tool == tool and not act.isChecked():
            act.setChecked(True)
    QTimer.singleShot(0, check)


def panel_actions(win):
    """The CONSTRAIN panel: Auto constrain, the Constraints window, then
    one checkable tool per kind (in the window's tool group)."""
    acts = getattr(win, "_constrain_actions", None)
    if acts is not None:
        return acts
    from PyQt5.QtWidgets import QAction
    from . import icons, language, toolbars, tooltips
    tooltips.TIPS.update(TIPS)
    acts = []
    for key, glyph, text, slot in (
            ("con_auto", "mdi.auto-fix", "Auto constrain",
             lambda: auto(win)),
            ("con_list", "mdi.format-list-checks", "Constraints…",
             lambda: open_window(win))):
        act = QAction(icons.icon(glyph, icons.family_color("draw")),
                      language.tr(text), win)
        act.setData(key)
        toolbars.remember_glyph(act, glyph, "draw")
        tooltips.apply(act, key)
        act.triggered.connect(lambda _=False, f=slot: f())
        acts.append(act)
    for kind, glyph in TOOLS:
        tool = tool_of(kind)
        act = QAction(icons.icon(glyph, icons.family_color("draw")),
                      language.tr(sc.KINDS[kind][0]), win)
        act.setData(tool)
        act.setCheckable(True)
        toolbars.remember_glyph(act, glyph, "draw")
        tooltips.apply(act, tool)
        act.triggered.connect(lambda _=False, t=tool: win._set_tool(t))
        # a second click on the button keeps the tool (the user: it
        # switched itself off)
        act.toggled.connect(lambda on, a=act, t=tool: on or _keep(win, a, t))
        win._tool_group.addAction(act)
        acts.append(act)
    # Delete first, then the constraints (what the panel shows), Auto /
    # list after
    act = QAction(icons.icon("mdi.link-variant-off",
                             icons.family_color("draw")),
                  language.tr("Delete constraint"), win)
    act.setData(DELETE)
    act.setCheckable(True)
    toolbars.remember_glyph(act, "mdi.link-variant-off", "draw")
    tooltips.apply(act, DELETE)
    act.triggered.connect(lambda _=False: win._set_tool(DELETE))
    win._tool_group.addAction(act)
    dim = QAction(icons.icon("mdi.ruler", icons.family_color("draw")),
                  language.tr("Sketch dimension"), win)
    dim.setData(DIMENSION)
    dim.setCheckable(True)
    toolbars.remember_glyph(dim, "mdi.ruler", "draw")
    tooltips.apply(dim, DIMENSION)
    dim.triggered.connect(lambda _=False: win._set_tool(DIMENSION))
    dim.toggled.connect(lambda on: on or _keep(win, dim, DIMENSION))
    win._tool_group.addAction(dim)
    acts = [dim, act] + acts[2:] + acts[:2]
    win._constrain_actions = acts
    return acts


# ------------------------------------------------------------------ MCP
def run_mcp(win, params):
    """MCP `sketch_constraint`: list / add / remove / set_value / auto /
    solve on a container (node_id; default the scope's root)."""
    model = win.model
    nid = params.get("node_id")
    cont = model.find(int(nid)) if nid is not None else None
    if nid is not None and cont is None:
        raise ValueError("No node %s." % nid)
    if cont is None:
        iso = win.builder.isolated_component()
        cont = iso if iso is not None else model.root
    action = params.get("action", "list")
    out = {"node_id": cont.id}
    if action == "add":
        if params.get("value") is not None and \
                params.get("scale_sketch", True):
            # the first dimension scales the sketch, as in the 2D view
            report, out["scaled"] = sc.add_dimension(
                model, cont, params["kind"], params["refs"],
                params.get("value"))
        else:
            report = sc.add(model, cont, params["kind"], params["refs"],
                            params.get("value"))
        out["status"] = sc.status_text(report)
    elif action == "remove":
        sc.remove(model, cont, int(params["index"]))
    elif action == "set_value":
        sc.set_value(model, cont, int(params["index"]), params["value"])
    elif action == "auto":
        out["added"] = sc.auto_constrain(model, cont)
    elif action != "list" and action != "solve":
        raise ValueError("Unknown action %r." % action)
    report = sc.solve(cont, write=False)
    out.update(
        status=sc.status_text(report), dof=report.get("dof"),
        ok=report.get("ok"),
        constraints=[dict(index=i, text=sc.describe(cont, r), **r)
                     for i, r in enumerate(sc.rows(cont))],
        shapes=[dict(index=i, id=n.id, type=n.type, name=n.name,
                     entities=[e for e, _ in _entities(n)])
                for i, n in enumerate(cont.children)
                if n.type in sc.SHAPES])
    return out
