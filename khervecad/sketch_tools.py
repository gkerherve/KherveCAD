"""More sketch tools for the 2D view, towards Fusion's SKETCH ▸ CREATE
(2026-10-19): centre rectangle, centre-point arc, 3-point arc, ellipse,
slot and a point-placed spline. Each is a run of clicks (a drag counts
as two: press and release) and each makes ordinary tree nodes, so the
program stays plain OpenSCAD and re-imports:

- centre rectangle -> `rect` (corner = centre - half size);
- centre-point arc -> `circle` with `start_angle` + `angle` (a sector);
- 3-point arc      -> `polygon`: the circular segment start → through →
  end, closed by its chord;
- ellipse          -> `scale([a / b, 1]) circle(r = b)`;
- slot             -> `line` of that width: `hull()` of two circles,
  centre to centre (what the importer reads such a hull back as);
- spline           -> `polygon` through a closed Catmull-Rom curve of
  the clicked points (Enter, right-click or double-click finishes).

The geometry here is Qt-free; the scene hooks (`press`, `move`,
`release`, ...) are called from view2d.SketchScene.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

RECT_CENTER, ARC_CENTER, ARC_3PT, ELLIPSE, SLOT, SPLINE = (
    "rect_center", "arc_center", "arc_3pt", "ellipse", "slot", "spline")

#: (tool id, mdi glyph, label, shortcut) — beside toolbars.TOOLS
TOOLS = [
    (RECT_CENTER, "mdi.rectangle-outline", "Center rectangle", ""),
    (ARC_CENTER, "mdi.chart-arc", "Center point arc", ""),
    (ARC_3PT, "mdi.vector-curve", "3-point arc", ""),
    (ELLIPSE, "mdi.ellipse-outline", "Ellipse", ""),
    (SLOT, "mdi.pill", "Slot", ""),
    (SPLINE, "mdi.draw", "Spline", ""),
]
#: clicks each tool needs (the spline takes any number, Enter ends it)
CLICKS = {RECT_CENTER: 2, ARC_CENTER: 3, ARC_3PT: 3, ELLIPSE: 2, SLOT: 3}
PROMPTS = {
    RECT_CENTER: ["Click the centre.", "Click a corner."],
    ARC_CENTER: ["Click the centre.", "Click where the arc starts.",
                 "Click where it ends (counter-clockwise)."],
    ARC_3PT: ["Click where the arc starts.", "Click where it ends.",
              "Click a point the arc passes through."],
    ELLIPSE: ["Click the centre.", "Click a corner of its box."],
    SLOT: ["Click the first end's centre.", "Click the other end's centre.",
           "Click to set the width."],
    SPLINE: ["Click points; Enter, right-click or double-click finishes, "
             "Backspace takes one back, Esc cancels."],
}
#: smallest size a shape may have (mm)
MIN = 0.5
#: curve steps per spline span / per arc
SPLINE_STEPS = 8
ARC_STEPS = 32


def _variable():
    """Tools taking any number of clicks (Enter ends)."""
    from . import sketch_tools2
    return {SPLINE} | sketch_tools2.VARIABLE


def _min_points(tool):
    from . import sketch_tools2
    return 2 if tool == sketch_tools2.POLYLINE else 3


def handles(tool):
    return tool in CLICKS or tool in _variable()


def _r(v):
    return round(v, 4)


# ------------------------------------------------------------- geometry
def rect_center(c, corner):
    w, h = 2 * abs(corner[0] - c[0]), 2 * abs(corner[1] - c[1])
    if w < MIN or h < MIN:
        return None
    return [("rect", dict(x=_r(c[0] - w / 2), y=_r(c[1] - h / 2),
                          width=_r(w), height=_r(h)), None)]


def arc_center(c, s, e):
    r = math.hypot(s[0] - c[0], s[1] - c[1])
    if r < MIN:
        return None
    a0 = math.degrees(math.atan2(s[1] - c[1], s[0] - c[0]))
    a1 = math.degrees(math.atan2(e[1] - c[1], e[0] - c[0]))
    sweep = (a1 - a0) % 360.0
    if sweep < 1e-6:
        # all the way round: the circle itself
        return [("circle", dict(x=_r(c[0]), y=_r(c[1]), radius=_r(r)),
                 None)]
    # an OPEN arc (sketch_arc): its two ends and the bulge — it was a
    # filled pie slice, so no contour could be built from arcs (the user)
    from . import sketch_arc
    t = math.radians(a1)
    end = (c[0] + r * math.cos(t), c[1] + r * math.sin(t))
    return [sketch_arc.arc_spec(s, end, sketch_arc.bulge_for_sweep(sweep))]


def circumcentre(a, b, p):
    d = 2 * (a[0] * (b[1] - p[1]) + b[0] * (p[1] - a[1])
             + p[0] * (a[1] - b[1]))
    if abs(d) < 1e-9:
        return None
    a2, b2, p2 = (a[0] ** 2 + a[1] ** 2, b[0] ** 2 + b[1] ** 2,
                  p[0] ** 2 + p[1] ** 2)
    return ((a2 * (b[1] - p[1]) + b2 * (p[1] - a[1]) + p2 * (a[1] - b[1]))
            / d,
            (a2 * (p[0] - b[0]) + b2 * (a[0] - p[0]) + p2 * (b[0] - a[0]))
            / d)


def arc_points(a, b, p, steps=ARC_STEPS):
    """Points of the arc from *a* through *p* to *b*."""
    c = circumcentre(a, b, p)
    if c is None:
        return None
    r = math.hypot(a[0] - c[0], a[1] - c[1])
    ang = [math.atan2(q[1] - c[1], q[0] - c[0]) for q in (a, p, b)]
    ccw = (ang[2] - ang[0]) % (2 * math.pi)
    through = (ang[1] - ang[0]) % (2 * math.pi)
    sweep = ccw if through < ccw else ccw - 2 * math.pi
    return [(c[0] + r * math.cos(ang[0] + sweep * i / steps),
             c[1] + r * math.sin(ang[0] + sweep * i / steps))
            for i in range(steps + 1)]


def arc_3pt(a, b, p):
    """An OPEN arc from *a* to *b* through *p*: three points to drag, not
    a filled polygon of 32 (the user)."""
    if circumcentre(a, b, p) is None or \
            math.hypot(b[0] - a[0], b[1] - a[1]) < MIN:
        return None
    from . import sketch_arc
    return [sketch_arc.arc_spec(a, b, sketch_arc.bulge_through(a, b, p))]


def _polygon(pts):
    if len(pts) < 3:
        return None
    if sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1)
           in zip(pts, pts[1:] + pts[:1])) < 0:
        pts = pts[::-1]                         # counter-clockwise
    o = pts[0]
    return [("polygon", dict(x=_r(o[0]), y=_r(o[1]),
                             points=[[_r(x - o[0]), _r(y - o[1])]
                                     for x, y in pts]), None)]


def ellipse(c, corner):
    a, b = abs(corner[0] - c[0]), abs(corner[1] - c[1])
    if a < MIN or b < MIN:
        return None
    return [("scale", dict(x=_r(a / b), y=1.0, z=1.0),
             [("circle", dict(x=_r(c[0] * b / a), y=_r(c[1]),
                              radius=_r(b)), None)])]


def slot(c1, c2, w):
    dx, dy = c2[0] - c1[0], c2[1] - c1[1]
    length = math.hypot(dx, dy)
    if length < MIN:
        return None
    r = abs(dx * (w[1] - c1[1]) - dy * (w[0] - c1[0])) / length
    if r < MIN / 2:
        return None
    return [("line", dict(x1=_r(c1[0]), y1=_r(c1[1]), x2=_r(c2[0]),
                          y2=_r(c2[1]), width=_r(2 * r)), None)]


def spline_points(pts, steps=SPLINE_STEPS):
    """A closed Catmull-Rom curve through *pts*."""
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2, p3 = (pts[(i - 1) % n], pts[i], pts[(i + 1) % n],
                          pts[(i + 2) % n])
        for s in range(steps):
            t = s / steps
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * (2 * p1[k] + (p2[k] - p0[k]) * t
                                    + (2 * p0[k] - 5 * p1[k] + 4 * p2[k]
                                       - p3[k]) * t2
                                    + (3 * p1[k] - p0[k] - 3 * p2[k]
                                       + p3[k]) * t3) for k in (0, 1)))
    return out


def spline(*pts):
    """An OPEN spline through the points clicked: joined arcs, each point
    an end or a middle handle (it was a closed filled shape)."""
    if len(pts) < 2:
        return None
    from . import sketch_arc
    return sketch_arc.through(sketch_arc.catmull_open(list(pts)))


BUILD = {RECT_CENTER: rect_center, ARC_CENTER: arc_center,
         ARC_3PT: arc_3pt, ELLIPSE: ellipse, SLOT: slot, SPLINE: spline}


def outline(tool, pts):
    """What to draw while placing: the shape the points make so far."""
    from . import sketch_tools2
    more = sketch_tools2.outline(tool, pts)
    if more is not None:
        return more
    if tool == SPLINE:
        from . import sketch_arc
        return sketch_arc.catmull_open(list(pts), 8)
    if len(pts) < 2:
        return []
    if tool in (RECT_CENTER, ELLIPSE):
        (cx, cy), (x, y) = pts[0], pts[1]
        a, b = abs(x - cx), abs(y - cy)
        if tool == RECT_CENTER:
            return [(cx - a, cy - b), (cx + a, cy - b), (cx + a, cy + b),
                    (cx - a, cy + b)]
        return [(cx + a * math.cos(t), cy + b * math.sin(t))
                for t in (2 * math.pi * i / 48 for i in range(48))]
    if tool == ARC_CENTER:
        c, s = pts[0], pts[1]
        r = math.hypot(s[0] - c[0], s[1] - c[1])
        if len(pts) == 2:
            return [(c[0] + r * math.cos(2 * math.pi * i / 48),
                     c[1] + r * math.sin(2 * math.pi * i / 48))
                    for i in range(48)]
        a0 = math.atan2(s[1] - c[1], s[0] - c[0])
        e = pts[2]
        sweep = (math.atan2(e[1] - c[1], e[0] - c[0]) - a0) % (2 * math.pi)
        return [(c[0] + r * math.cos(a0 + sweep * i / 32),
                       c[1] + r * math.sin(a0 + sweep * i / 32))
                      for i in range(33)]
    if tool == ARC_3PT:
        if len(pts) == 2:
            return list(pts)
        return arc_points(pts[0], pts[1], pts[2]) or list(pts)
    if tool == SLOT:
        if len(pts) == 2:
            return list(pts)
        (x1, y1), (x2, y2), w = pts
        L = math.hypot(x2 - x1, y2 - y1) or 1.0
        r = abs((x2 - x1) * (w[1] - y1) - (y2 - y1) * (w[0] - x1)) / L
        base = math.atan2(y2 - y1, x2 - x1)
        half = [(x2 + r * math.cos(base - math.pi / 2 + math.pi * i / 16),
                 y2 + r * math.sin(base - math.pi / 2 + math.pi * i / 16))
                for i in range(17)]
        return half + [(x1 + r * math.cos(base + math.pi / 2
                                          + math.pi * i / 16),
                        y1 + r * math.sin(base + math.pi / 2
                                          + math.pi * i / 16))
                       for i in range(17)]
    return list(pts)


# ------------------------------------------------------- scene hooks
def _state(scene):
    if not hasattr(scene, "_sk_points"):
        scene._sk_points, scene._sk_items = [], []
    return scene._sk_points


def _xy(p):
    return (p.x(), p.y())


def drop(scene):
    """Throw the half-placed shape away (tool change, Esc)."""
    _state(scene).clear()
    _clear_items(scene)
    from . import sketch_tools2
    sketch_tools2.clear_marks(scene)


def _clear_items(scene):
    for item in getattr(scene, "_sk_items", []):
        if item.scene() is scene:
            scene.removeItem(item)
    scene._sk_items = []


def _redraw(scene, cursor):
    from PyQt5.QtCore import QPointF, Qt
    from PyQt5.QtGui import QColor, QPainterPath, QPen
    _clear_items(scene)
    pts = list(_state(scene))
    if not pts:
        return
    if cursor is not None:
        pts.append(cursor)
    shape = outline(scene.tool, pts)
    pen = QPen(QColor("#2176c7"), 0)
    pen.setCosmetic(True)
    pen.setWidthF(1.6)
    path = QPainterPath()
    if len(shape) >= 2:
        path.moveTo(QPointF(*shape[0]))
        for q in shape[1:]:
            path.lineTo(QPointF(*q))
        if len(shape) >= 3:
            path.closeSubpath()
    guide = QPainterPath()
    for q in pts:
        guide.addEllipse(QPointF(*q), 0.0001, 0.0001)
    for p, dashed in ((path, False), (guide, True)):
        pn = QPen(pen)
        if dashed:
            pn.setWidthF(6.0)
            pn.setCapStyle(Qt.RoundCap)
        item = scene.addPath(p, pn)
        item.setZValue(1e6)
        item.setAcceptedMouseButtons(Qt.NoButton)
        scene._sk_items.append(item)


def _say(scene):
    from . import language
    prompts = PROMPTS[scene.tool]
    n = len(_state(scene))
    scene.status.emit(language.tr(prompts[min(n, len(prompts) - 1)]))


def _add(scene, pos):
    pts = _state(scene)
    pts.append(_xy(pos))
    need = CLICKS.get(scene.tool)
    if need is not None and len(pts) >= need:
        finish(scene)
    else:
        _redraw(scene, None)
        _say(scene)


def finish(scene):
    """Make the shape from the points placed (the spline's Enter)."""
    pts = list(_state(scene))
    tool = scene.tool
    drop(scene)
    from . import sketch_tools2
    if not pts:
        spec = None
    elif tool in sketch_tools2.BUILD_SCENE:
        spec = sketch_tools2.BUILD_SCENE[tool](scene, *pts)
    else:
        spec = BUILD[tool](*pts)
    if not spec:
        return None
    node, made = None, []
    for type_, params, kids in spec:
        node = scene._create(type_, params)
        made.append(node)
        for ktype, kparams, _ in kids or []:
            scene.model.add_node(ktype, kparams, parent=node)
    if len(made) > 1 and all(n.type == "line" for n in made):
        # one Polyline group (one row, one Object in Main), each line's
        # end joined to the next one's start
        from . import sketch_constraints as sc
        group = scene.model.wrap_nodes(made, "union")
        if group is not None:
            group.name = "Polyline" if tool == sketch_tools2.POLYLINE \
                else "Spline"
            node = group
        parent = made[0].parent
        try:
            for a, b in zip(made, made[1:]):
                sc.add(scene.model, parent, "coincident",
                       [sc.ref_of(parent, a, "p2"),
                        sc.ref_of(parent, b, "p1")])
        except (ValueError, KeyError):
            pass
    pending = getattr(scene, "_pending_tangents", None)
    if pending and node is not None and node.type == "circle":
        # the perimeter circle clicked on lines: Tangent to each
        from . import sketch_constraints as sc
        parent = node.parent
        for other, name in pending:
            try:
                sc.add(scene.model, parent, "tangent",
                       [sc.ref_of(parent, other, name),
                        sc.ref_of(parent, node, "o")])
            except (ValueError, KeyError):
                pass
    scene._pending_tangents = []
    if tool == SLOT and node is not None and node.type == "line":
        from . import slot2d             # a slot, not "Line n"
        slot2d.mark(scene.model, node)
        # drawn level / upright: it stays so (Horizontal / Vertical, as
        # the Line tool does) — a dimension to one end tilted it
        p = node.params
        kind = "horizontal" if abs(p["y1"] - p["y2"]) < 1e-9 else \
            "vertical" if abs(p["x1"] - p["x2"]) < 1e-9 else None
        if kind and node.parent is not None:
            from . import sketch_constraints as sc
            try:
                sc.add(scene.model, node.parent, kind,
                       [sc.ref_of(node.parent, node, "l")])
            except (ValueError, KeyError):
                pass
    if tool == RECT_CENTER and node is not None and node.parent is not None \
            and abs(pts[0][0]) < 1e-6 and abs(pts[0][1]) < 1e-6:
        # drawn from the origin: its centre stays there, as SolidWorks
        # makes it coincident with the origin — a Smart Dimension on a
        # side used to move the corner and slide the centre away
        from . import sketch_constraints as sc
        try:
            sc.add(scene.model, node.parent, "fix",
                   [sc.ref_of(node.parent, node, "c")])
        except (ValueError, KeyError):
            pass
    scene.node_created.emit(node)
    return node


def press(scene, event):
    from PyQt5.QtCore import Qt
    if event.button() == Qt.RightButton:
        if scene.tool in _variable() and \
                len(_state(scene)) >= _min_points(scene.tool):
            finish(scene)
        else:
            drop(scene)
    elif event.button() == Qt.LeftButton:
        from . import sketch_tools2
        sketch_tools2.mark(scene, event.scenePos())
        _add(scene, scene.snap(event.scenePos()))
    event.accept()


def move(scene, event):
    from . import sketch_tools2
    sketch_tools2.hover(scene, event.scenePos())
    if _state(scene):
        _redraw(scene, _xy(scene.snap(event.scenePos())))
    event.accept()


def release(scene, event):
    """A drag adds its end point too (press = first click)."""
    from PyQt5.QtCore import Qt
    from .polygon_draw import px_to_scene
    if event.button() == Qt.LeftButton and _state(scene) \
            and scene.tool not in _variable():
        down = event.buttonDownScenePos(Qt.LeftButton)
        here = event.scenePos()
        if math.hypot(here.x() - down.x(), here.y() - down.y()) \
                > px_to_scene(scene, 4.0):
            _add(scene, scene.snap(here))
    event.accept()


def double_click(scene, event):
    if scene.tool in _variable():
        pts = _state(scene)
        if len(pts) >= 2 and pts[-1] == pts[-2]:
            pts.pop()                   # the double-click's second press
        if len(pts) >= _min_points(scene.tool):
            finish(scene)
    event.accept()


def key(scene, event):
    """Enter finishes a spline, Backspace takes a point back. True when
    the key was used."""
    from PyQt5.QtCore import Qt
    pts = _state(scene)
    if event.key() in (Qt.Key_Return, Qt.Key_Enter) and \
            scene.tool in _variable():
        finish(scene)
        return True
    if event.key() == Qt.Key_Backspace and pts:
        pts.pop()
        _redraw(scene, None)
        return True
    return False


# the further CREATE tools join these tables (sketch_tools2.register)
from . import sketch_tools2  # noqa: E402,F401
