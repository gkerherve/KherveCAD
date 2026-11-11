"""Linear and Circular Sketch Pattern, as SolidWorks has them
(2026-11-11, the user, with SolidWorks' Circular Pattern window: "I do not
get how our circular pattern is working … linear pattern and circular
pattern like SolidWorks … I should be able to select what I want to
pattern. I do not see what is the centre of rotation").

The old sketch Modify ▸ Pattern wrapped the selection in a `pattern`
node turning about the origin, with nothing on screen to say where that
was. These are sketch tools: a window beside the sketch (`tool_panel`)
with

- **Entities to pattern** — click the lines, circles, rectangles and
  polygons (each turns blue; click again to drop it), or have them
  selected before;
- **Circular**: the **Centre** (a box too: click a point — a line end, a
  circle's centre, a corner — or type X / Y; the origin by default),
  Angle (360°), Equal spacing, Number of instances;
- **Linear**: Direction 1 angle, spacing, instances, and an optional
  Direction 2 (square to it by default).

While the window is open the copies are drawn dashed in the sketch with
the centre marked, so what OK makes is seen first. OK makes OpenSCAD's
own FOR LOOP round the shapes (the user: "like a command like rotate
extrude … using the loop"): circular ``for (i = [0 : n - 1])
rotate([0, 0, i * step], pivot = centre)``, linear ``for (i) [for (j)]
translate([i * dx + j * dx2, …])`` — one row in the tree, one Ctrl+Z,
and the window's numbers kept on the loop (`KEY`), so selecting it and
pressing the button again changes it. The sketch draws the loop's
other instances (`_paint_made`); an Extruded Boss / Cut takes the loop
with the shapes.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

LINEAR, CIRCULAR = "sk_lpattern", "sk_cpattern"
TOOLS = (LINEAR, CIRCULAR)
SHAPES, CENTRE = "shapes", "centre"
LABEL = {LINEAR: "Linear Sketch Pattern", CIRCULAR: "Circular Sketch Pattern"}
MAX_COPIES = 500


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _r(v):
    return round(v, 4) + 0.0


# ------------------------------------------------------------ the maths
def placements(st):
    """[(dx, dy, turn°)] of each COPY (the original, 0 0 0, left out),
    about the centre (cx, cy) for a circular pattern."""
    out = []
    if st["kind"] == CIRCULAR:
        n = max(1, int(st["count"]))
        total = st["angle"]
        if st["equal"]:
            full = abs(total) >= 360 - 1e-9
            step = total / n if full else total / max(1, n - 1)
        else:
            step = total                 # the angle between instances
        for i in range(1, n):
            out.append((0.0, 0.0, step * i))
        return out[:MAX_COPIES]
    a = math.radians(st["angle1"])
    d1 = (math.cos(a), math.sin(a))
    if st["dir2"]:
        b = math.radians(st["angle2"])
        d2 = (math.cos(b), math.sin(b))
        n2 = max(1, int(st["count2"]))
    else:
        d2, n2 = (0.0, 0.0), 1
    for j in range(n2):
        for i in range(max(1, int(st["count1"]))):
            if i == 0 and j == 0:
                continue
            out.append((d1[0] * st["spacing1"] * i + d2[0] * st["spacing2"] * j,
                        d1[1] * st["spacing1"] * i + d2[1] * st["spacing2"] * j,
                        0.0))
    return out[:MAX_COPIES]


def _mover(centre, dx, dy, turn):
    c, s = math.cos(math.radians(turn)), math.sin(math.radians(turn))
    cx, cy = centre

    def move(p):
        x, y = p[0] - cx, p[1] - cy
        return (cx + c * x - s * y + dx, cy + s * x + c * y + dy)
    return move


def _rect_corners(p):
    x, y = _num(p.get("x")), _num(p.get("y"))
    w, h = _num(p.get("width"), 1), _num(p.get("height"), 1)
    if p.get("center"):
        x, y = x - w / 2, y - h / 2
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def copied_params(node, centre, dx, dy, turn):
    """(type, params) of *node* moved by (dx, dy) and turned *turn*°
    about *centre*, or None when it is not a shape this can copy."""
    move = _mover(centre, dx, dy, turn)
    p = dict(node.params)
    t = node.type
    if t == "line":
        a = move((_num(p.get("x1")), _num(p.get("y1"))))
        b = move((_num(p.get("x2")), _num(p.get("y2"))))
        p.update(x1=_r(a[0]), y1=_r(a[1]), x2=_r(b[0]), y2=_r(b[1]))
        return t, p
    if t == "circle":
        c = move((_num(p.get("x")), _num(p.get("y"))))
        p.update(x=_r(c[0]), y=_r(c[1]))
        if _num(p.get("angle", 360), 360) < 360 - 1e-6:
            p["start_angle"] = _r((_num(p.get("start_angle")) + turn) % 360)
        return t, p
    if t == "rect":
        if abs(turn % 360) < 1e-9:
            o = move((_num(p.get("x")), _num(p.get("y"))))
            p.update(x=_r(o[0]), y=_r(o[1]))
            return t, p
        pts = [move(q) for q in _rect_corners(p)]
        out = {k: v for k, v in p.items() if k in ("modifier",)}
        out["points"] = [[_r(q[0]), _r(q[1])] for q in pts]
        return "polygon", out
    if t == "polygon":
        ox, oy = _num(p.get("x")), _num(p.get("y"))
        try:
            pts = [move((ox + _num(q[0]), oy + _num(q[1])))
                   for q in p.get("points") or []]
        except (TypeError, IndexError):
            return None
        if "x" in p or "y" in p:
            o = move((ox, oy))
            p["x"], p["y"] = _r(o[0]), _r(o[1])
        else:
            o = (0.0, 0.0)
        p["points"] = [[_r(q[0] - o[0]), _r(q[1] - o[1])] for q in pts]
        return t, p
    return None


def outline(node, centre=(0.0, 0.0), dx=0.0, dy=0.0, turn=0.0):
    """The shape's outline moved like a copy, for the preview."""
    got = copied_params(node, centre, dx, dy, turn)
    if got is None:
        return []
    t, p = got
    if t == "line":
        return [(_num(p["x1"]), _num(p["y1"])), (_num(p["x2"]), _num(p["y2"]))]
    if t == "circle":
        cx, cy, r = _num(p.get("x")), _num(p.get("y")), _num(p.get("radius"), 1)
        sweep = _num(p.get("angle", 360), 360)
        start = _num(p.get("start_angle")) if sweep < 360 else 0.0
        n = 48
        return [(cx + r * math.cos(math.radians(start + sweep * i / n)),
                 cy + r * math.sin(math.radians(start + sweep * i / n)))
                for i in range(n + 1)]
    if t == "rect":
        pts = _rect_corners(p)
        return pts + pts[:1]
    if t == "polygon":
        ox, oy = _num(p.get("x")), _num(p.get("y"))
        pts = [(ox + _num(q[0]), oy + _num(q[1])) for q in p["points"]]
        return pts + pts[:1]
    return []


#: on the loop: the window's numbers, so the pattern opens again in it
KEY = "sketch_pattern"
SPEC_KEYS = ("kind", "count", "angle", "equal", "angle1", "spacing1",
             "count1", "dir2", "angle2", "spacing2", "count2")


def step_angle(st):
    """The angle between two copies of a circular pattern."""
    n = max(1, int(st["count"]))
    total = st["angle"]
    if not st["equal"]:
        return total
    if abs(total) >= 360 - 1e-9:
        return total / n
    return total / max(1, n - 1)


def turn_expression(st):
    """Copy i's turn as the user thinks of it: one turn over the count
    ("i * 360 / 6"), an angle spanned ("i * 90 / (4 - 1)"), or a step."""
    n = max(1, int(st["count"]))
    a = _g(st["angle"])
    if not st["equal"]:
        return "i * %s" % a
    if abs(st["angle"]) >= 360 - 1e-9:
        return "i * %s / %d" % (a, n)
    return "i * %s / %d" % (a, max(1, n - 1))


#: the window's numbers by name, for Properties (pattern_props)
def update(model, loop, key, value):
    """One number of a made pattern changed (Properties): the loop and
    its turn / move written again."""
    st = state_of(loop)
    if key in ("cx", "cy"):
        c = list(st["centre"])
        c[0 if key == "cx" else 1] = float(value)
        st["centre"] = tuple(c)
    else:
        st[key] = value
    _write(model, loop, st)


def _g(v):
    return "%g" % round(float(v), 6)


def _write(model, loop, st):
    """The loop (and what it holds above the shapes) set from *st*."""
    inner = loop.children[0] if loop.children else None
    if st["kind"] == CIRCULAR:
        loop.params.update(variable="i", start=0.0,
                           end=float(max(1, int(st["count"])) - 1),
                           step=1.0, values="")
        rot = inner
        rot.params.update(x=0.0, y=0.0, z=turn_expression(st))
        cx, cy = st["centre"]
        for k, v in (("px", cx), ("py", cy)):
            if v:
                rot.params[k] = round(float(v), 4)
            else:
                rot.params.pop(k, None)
        rot.params.pop("pz", None)
        rot.name = "Turn copy i about the centre"
    else:
        loop.params.update(variable="i", start=0.0,
                           end=float(max(1, int(st["count1"])) - 1),
                           step=1.0, values="")
        a = math.radians(st["angle1"])
        d1 = (st["spacing1"] * math.cos(a), st["spacing1"] * math.sin(a))
        two = inner is not None and inner.type == "for_loop"
        if st["dir2"] and not two:        # a second loop, round the move
            inner = model.wrap_nodes([inner], "for_loop")
            inner.name = "Direction 2"
        elif not st["dir2"] and two:
            move = inner.children[0]
            model.ungroup(inner)
            inner = move
        if st["dir2"]:
            inner.params.update(variable="j", start=0.0,
                                end=float(max(1, int(st["count2"])) - 1),
                                step=1.0, values="")
            move = inner.children[0]
            b = math.radians(st["angle2"])
            d2 = (st["spacing2"] * math.cos(b), st["spacing2"] * math.sin(b))
            move.params.update(
                x="i * %s + j * %s" % (_g(d1[0]), _g(d2[0])),
                y="i * %s + j * %s" % (_g(d1[1]), _g(d2[1])), z=0.0)
        else:
            move = inner
            move.params.update(x="i * %s" % _g(d1[0]),
                               y="i * %s" % _g(d1[1]), z=0.0)
        move.name = "Move copy along the row"
    spec = {k: st[k] for k in SPEC_KEYS}
    spec["centre"] = [float(st["centre"][0]), float(st["centre"][1])]
    loop.params[KEY] = spec
    loop.name = LABEL[st["kind"]]
    model.structure_changed.emit()
    model.node_changed.emit(loop)


def make(model, st):
    """The pattern as a FOR LOOP round the shapes (OpenSCAD's own):
    circular ``for (i = [0 : n - 1]) rotate(i * step, pivot = centre)``,
    linear ``for (i) [for (j)] translate(i * d1 [+ j * d2])``. With
    ``st["edit"]`` the loop already there is changed. Returns the loop
    (None when nothing is picked) and the names left out."""
    from .model import SHAPE_2D
    loop = st.get("edit")
    if loop is not None and loop.parent is not None:
        _write(model, loop, st)
        return loop, []
    shapes = [s for s in st["shapes"] if s.category == SHAPE_2D]
    if not shapes:
        return None, []
    container = shapes[0].parent
    skipped = [s.name for s in shapes if s.parent is not container]
    shapes = [s for s in shapes if s.parent is container]
    inner = model.wrap_nodes(shapes, "rotate" if st["kind"] == CIRCULAR
                             else "translate")
    loop = model.wrap_nodes([inner], "for_loop")
    _write(model, loop, st)
    return loop, skipped


def loop_of(node):
    """The sketch-pattern loop *node* is, or lies in (None)."""
    while node is not None:
        if node.type == "for_loop" and isinstance(node.params.get(KEY),
                                                  dict):
            return node
        node = node.parent
    return None


def state_of(loop):
    """The window's state for an existing pattern loop."""
    from .model import SHAPE_2D
    spec = loop.params.get(KEY) or {}
    st = new_state(spec.get("kind", CIRCULAR))
    for k in SPEC_KEYS:
        if k in spec:
            st[k] = spec[k]
    c = spec.get("centre") or [0.0, 0.0]
    st["centre"] = (float(c[0]), float(c[1]))
    st["centre_name"] = "point (%g, %g)" % st["centre"]
    st["shapes"] = [n for n in loop.walk() if n.category == SHAPE_2D]
    st["edit"] = loop
    return st


def new_state(kind, shapes=()):
    return {"kind": kind, "shapes": list(shapes), "active": SHAPES,
            "centre": (0.0, 0.0), "centre_name": "Origin",
            "count": 6, "angle": 360.0, "equal": True,
            "angle1": 0.0, "spacing1": 20.0, "count1": 4,
            "dir2": False, "angle2": 90.0, "spacing2": 20.0, "count2": 2}


# ------------------------------------------------------- the 2D view
def _state(scene):
    return getattr(scene, "_pattern", None)


def _view(scene):
    views = scene.views()
    return views[0] if views else None


def _panel(scene, kind, create=True):
    view = _view(scene)
    if view is None:
        return None
    store = view.__dict__.setdefault("_pattern_panels", {})
    if kind not in store and create:
        store[kind] = _make_panel(view, kind)
    return store.get(kind)


def start(win, kind):
    """The button: the tool and its window; shapes already selected fill
    Entities to pattern."""
    from .model import SHAPE_2D
    from . import sketch_mode
    picked = [n for n in win.builder.active_tree().selected_nodes()
              if n.category == SHAPE_2D]
    editing = next((loop_of(n) for n in
                    win.builder.active_tree().selected_nodes()
                    if loop_of(n) is not None), None)
    if sketch_mode._in_3d(win):
        win._sketch3d_tool.message(
            "%s works in the 2D sketch: choose 2D sketch view (Extruded "
            "Boss / Cut ask) or Edit Sketch, then press it again."
            % LABEL[kind], 8000)
        return
    if editing is not None:              # change the pattern made before
        kind = editing.params[KEY].get("kind", kind)
    win._set_tool(kind)
    begin(win.view2d.scene(), kind, picked, edit=editing)


def begin(scene, kind, shapes=(), edit=None):
    old = _state(scene)
    if old is not None:
        drop(scene)
    scene._pattern = state_of(edit) if edit is not None else \
        new_state(kind, shapes)
    panel = _panel(scene, kind)
    if panel is not None:
        panel.load()
        panel.open()
    _show(scene)


def prompt(scene):
    st = _state(scene)
    if st is None:
        return ""
    label = LABEL[st["kind"]]
    if st["active"] == CENTRE:
        return ("%s — click the centre of rotation: a line end, a "
                "circle's centre, a corner (or type X / Y)." % label)
    if not st["shapes"]:
        return ("%s — click the lines, circles and shapes to pattern."
                % label)
    return ("%s — %d entities; set the numbers, OK (or Enter) makes the "
            "copies." % (label, len(st["shapes"])))


def _show(scene):
    st = _state(scene)
    ids = {n.id for n in st["shapes"]} if st else set()
    scene.updating = True
    try:
        for item in scene.items():
            node = getattr(item, "node", None)
            if node is not None and hasattr(item, "handle_spec"):
                item.setSelected(node.id in ids)
    finally:
        scene.updating = False
    if st is not None:
        panel = _panel(scene, st["kind"], create=False)
        if panel is not None:
            panel.refresh()
        scene.status.emit(prompt(scene))
    scene.update()


def set_active(scene, which):
    st = _state(scene)
    if st is not None:
        st["active"] = which
        _show(scene)


def ok(scene):
    st = _state(scene)
    if st is None or not st["shapes"]:
        scene.status.emit(prompt(scene))
        return []
    editing = st.get("edit") is not None
    loop, skipped = make(scene.model, st)
    label = LABEL[st["kind"]]
    drop(scene)
    n = len(placements(st)) + 1
    msg = ("%s changed: %d instances." if editing else
           "%s: a for loop of %d instances — select it and press the "
           "button again to change it.") % (label, n)
    if skipped:
        msg += " Not copied (another sketch, or text): %s." % \
            ", ".join(skipped)
    scene.status.emit(msg)
    view = _view(scene)
    if view is not None:
        view.set_tool("select")
    return loop


def cancel(scene):
    st = _state(scene)
    drop(scene)
    view = _view(scene)
    if view is not None:
        view.set_tool("select")
    if st is not None:
        scene.status.emit("%s cancelled." % LABEL[st["kind"]])


def drop(scene):
    st = _state(scene)
    scene._pattern = None
    if st is not None:
        panel = _panel(scene, st["kind"], create=False)
        if panel is not None:
            panel.hide()
    try:
        scene.updating = True
        scene.clearSelection()
    finally:
        scene.updating = False
    scene.update()


def _point_at(scene, pos):
    """(x, y, name) of the sketch point under *pos*, in the frame."""
    from . import sketch_constrain_ui as scu, sketch_constraints as sc
    hit = scu.pick(scene, pos, "point", midpoints=True)
    if hit is None:
        hit = scu.pick(scene, pos, "circle")
        if hit is None:
            return None
        node = hit[0]
        return (_num(node.params.get("x")), _num(node.params.get("y")),
                "%s (centre)" % node.name)
    node, name = hit[0], hit[1]
    try:
        x, y = sc._point(node, name, {})
    except Exception:
        return None
    word = {"p1": "start", "p2": "end", "c": "centre", "m": "middle"}.get(
        name, name)
    return (x, y, "%s (%s)" % (node.name, word))


def press(scene, event):
    from PyQt5.QtCore import Qt
    from . import sketch_constrain_ui as scu
    event.accept()
    st = _state(scene)
    if st is None:
        begin(scene, scene.tool)
        st = _state(scene)
    if event.button() == Qt.RightButton:
        ok(scene)
        return
    if event.button() != Qt.LeftButton:
        return
    pos = event.scenePos()
    if st["active"] == CENTRE:
        got = _point_at(scene, pos)
        if got is None:
            scene.status.emit(prompt(scene))
            return
        st["centre"], st["centre_name"] = (got[0], got[1]), got[2]
        st["active"] = SHAPES
        panel = _panel(scene, st["kind"], create=False)
        if panel is not None:
            panel.load()
        _show(scene)
        return
    hit = scu.pick(scene, pos)
    if hit is None:
        scene.status.emit(prompt(scene))
        return
    node = hit[0]
    if node in st["shapes"]:
        st["shapes"].remove(node)
    else:
        st["shapes"].append(node)
    _show(scene)


def key(scene, event):
    from PyQt5.QtCore import Qt
    if event.key() in (Qt.Key_Return, Qt.Key_Enter):
        ok(scene)
        return True
    if event.key() == Qt.Key_Escape:
        cancel(scene)
        return True
    return False


def _frame_of(scene, node):
    from .view2d_edit import Frame
    for it in scene.items():
        if getattr(it, "node", None) is node:
            f = it.parentItem()
            return f if isinstance(f, Frame) else None
    return None


#: preview colours
COPY_INK = "#1e88e5"
CENTRE_INK = "#e65100"


def paint(scene, painter):
    """The copies dashed and the centre marked, while the window is
    open (scene coordinates)."""
    from PyQt5.QtCore import QPointF, Qt
    from PyQt5.QtGui import QColor, QPen, QPolygonF
    st = _state(scene)
    if st is None:
        _paint_made(scene, painter)
        return
    frame = _frame_of(scene, st["shapes"][0]) if st["shapes"] else None
    to_scene = (lambda p: frame.mapToScene(QPointF(*p))) if frame else \
        (lambda p: QPointF(*p))
    view = _view(scene)
    k = view.transform().m11() if view is not None else 1.0
    px = 1.0 / max(abs(k), 1e-9)
    painter.save()
    pen = QPen(QColor(COPY_INK), 1.6 * px, Qt.DashLine)
    pen.setCosmetic(False)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    for dx, dy, turn in placements(st):
        for s in st["shapes"]:
            pts = outline(s, st["centre"], dx, dy, turn)
            if len(pts) >= 2:
                painter.drawPolyline(QPolygonF([to_scene(p) for p in pts]))
    if st["kind"] == CIRCULAR:
        c = to_scene(st["centre"])
        ink = QColor(CENTRE_INK)
        painter.setPen(QPen(ink, 2 * px))
        r = 7 * px
        painter.drawEllipse(c, r, r)
        painter.drawLine(QPointF(c.x() - 2 * r, c.y()),
                         QPointF(c.x() + 2 * r, c.y()))
        painter.drawLine(QPointF(c.x(), c.y() - 2 * r),
                         QPointF(c.x(), c.y() + 2 * r))
        if st["shapes"]:                 # the radius to the first entity
            pts = outline(st["shapes"][0])
            if pts:
                mx = sum(p[0] for p in pts) / len(pts)
                my = sum(p[1] for p in pts) / len(pts)
                painter.setPen(QPen(ink, 1.2 * px, Qt.DotLine))
                painter.drawLine(c, to_scene((mx, my)))
        painter.setPen(QPen(ink))
        painter.resetTransform()
        if view is not None:
            at = view.mapFromScene(c)
            painter.drawText(at.x() + 12, at.y() - 10, "Centre")
    painter.restore()


#: the instances a pattern loop makes, as the sketch draws them
MADE_INK = "#2b2b2b"


def _paint_made(scene, painter):
    """The sketch draws a loop's shapes once (the first instance): the
    other instances are drawn here, so the sketch shows the pattern."""
    from PyQt5.QtCore import QPointF, Qt
    from PyQt5.QtGui import QColor, QPen, QPolygonF
    model = getattr(scene, "model", None)
    if model is None:
        return
    view = _view(scene)
    k = view.transform().m11() if view is not None else 1.0
    px = 1.0 / max(abs(k), 1e-9)
    for loop in [n for n in model.root.walk()
                 if n.type == "for_loop" and isinstance(n.params.get(KEY),
                                                        dict)]:
        st = state_of(loop)
        shown = [s for s in st["shapes"] if _frame_of(scene, s) is not None
                 or any(getattr(it, "node", None) is s
                        for it in scene.items())]
        if not shown:
            continue
        frame = _frame_of(scene, shown[0])
        if frame is not None:
            # the frame holds the loop's own turn for i = 0 (none): the
            # copies are placed from the shapes' own coordinates
            to_scene = lambda p, f=frame: f.mapToScene(QPointF(*p))
        else:
            to_scene = lambda p: QPointF(*p)
        painter.save()
        dashed = any(s.params.get("modifier") == "%" for s in shown)
        painter.setPen(QPen(QColor(MADE_INK), 1.2 * px,
                            Qt.DashLine if dashed else Qt.SolidLine))
        painter.setBrush(Qt.NoBrush)
        for dx, dy, turn in placements(st):
            for s in shown:
                pts = outline(s, st["centre"], dx, dy, turn)
                if len(pts) >= 2:
                    painter.drawPolyline(QPolygonF([to_scene(p)
                                                    for p in pts]))
        painter.restore()


def _make_panel(view, kind):
    from .tool_panel import ToolPanel

    class PatternPanel(ToolPanel):
        def __init__(self):
            super().__init__(view, LABEL[kind],
                             on_ok=lambda: ok(view.scene()),
                             on_cancel=lambda: cancel(view.scene()))
            scene = view.scene
            activate = lambda key: set_active(scene(), key)
            if kind == CIRCULAR:
                self.hint("Copies sketch shapes round a centre. Click the "
                          "shapes, then the centre box and a point — or "
                          "type X / Y. The copies show dashed first.")
            else:
                self.hint("Copies sketch shapes in a row (and a second "
                          "row with Direction 2). The copies show dashed "
                          "first.")
            self.box_shapes = self.selection(
                SHAPES, "1  Entities to pattern", on_activate=activate)
            if kind == CIRCULAR:
                self.box_centre = self.selection(
                    CENTRE, "2  Centre of rotation", on_activate=activate)
                self.number("cx", "Centre X", 0.0,
                            lambda v: self._set("cx", v),
                            minimum=-1e6)
                self.number("cy", "Centre Y", 0.0,
                            lambda v: self._set("cy", v),
                            minimum=-1e6)
                self.section("Parameters")
                self.number("angle", "Angle", 360.0,
                            lambda v: self._set("angle", v), suffix=" °",
                            minimum=-360.0, maximum=360.0, step=15.0)
                self.check("equal", "Equal spacing", True,
                           lambda v: self._set("equal", v))
                self.number("count", "Instances", 6,
                            lambda v: self._set("count", int(v)),
                            suffix="", minimum=2, maximum=MAX_COPIES,
                            decimals=0)
            else:
                self.section("Direction 1")
                self.number("angle1", "Angle", 0.0,
                            lambda v: self._set("angle1", v), suffix=" °",
                            minimum=-360.0, maximum=360.0, step=15.0)
                self.number("spacing1", "Spacing", 20.0,
                            lambda v: self._set("spacing1", v),
                            minimum=-1e6)
                self.number("count1", "Instances", 4,
                            lambda v: self._set("count1", int(v)),
                            suffix="", minimum=1, maximum=MAX_COPIES,
                            decimals=0)
                self.check("dir2", "Direction 2", False,
                           lambda v: self._set("dir2", v))
                self.number("angle2", "Angle 2", 90.0,
                            lambda v: self._set("angle2", v), suffix=" °",
                            minimum=-360.0, maximum=360.0, step=15.0)
                self.number("spacing2", "Spacing 2", 20.0,
                            lambda v: self._set("spacing2", v),
                            minimum=-1e6)
                self.number("count2", "Instances 2", 2,
                            lambda v: self._set("count2", int(v)),
                            suffix="", minimum=1, maximum=MAX_COPIES,
                            decimals=0)
            self.finish()

        def _set(self, key, value):
            st = _state(view.scene())
            if st is None:
                return
            if key in ("cx", "cy"):
                c = list(st["centre"])
                c[0 if key == "cx" else 1] = float(value)
                st["centre"], st["centre_name"] = tuple(c), "typed point"
            else:
                st[key] = value
            self.refresh()
            view.scene().update()

        def load(self):
            st = _state(view.scene())
            if st is None:
                return
            for key in ("angle", "equal", "count", "angle1", "spacing1",
                        "count1", "dir2", "angle2", "spacing2", "count2"):
                self.set_value(key, st[key])
            self.set_value("cx", st["centre"][0])
            self.set_value("cy", st["centre"][1])
            self.refresh()

        def refresh(self):
            st = _state(view.scene())
            if st is None:
                return
            names = [n.name for n in st["shapes"]]
            self.box_shapes.set_text(
                ", ".join(names) if names else
                "Click the lines, circles and shapes to pattern — each "
                "turns blue. Click one again to drop it.")
            if kind == CIRCULAR:
                self.box_centre.set_text(
                    "%s  (%g, %g)" % (st["centre_name"], round(
                        st["centre"][0], 3), round(st["centre"][1], 3)))
            else:
                for key in ("angle2", "spacing2", "count2"):
                    self.show_row(key, st["dir2"])
            self.set_active(st["active"])
            self.set_ok_enabled(bool(st["shapes"]))
            self.adjustSize()

    return PatternPanel()


TIPS = {
    LINEAR: ("Linear Sketch Pattern",
             "Copies sketch shapes in a row, or a grid with Direction 2 — "
             "each copy a real shape you can dimension and extrude.",
             ["Click this, then click the shapes to copy (they turn blue).",
              "Set the direction's angle, the spacing and the number of "
              "instances; tick Direction 2 for a grid.",
              "The copies show dashed; OK (or Enter) makes them."],
             "Select the shapes first and they are already in the box."),
    CIRCULAR: ("Circular Sketch Pattern",
               "Copies sketch shapes round a centre — bolt holes on a "
               "flange, spokes, teeth. The centre is marked in orange.",
               ["Click this, then click the shapes to copy (they turn "
                "blue).",
                "Click the Centre box, then a point in the sketch (a line "
                "end, a circle's centre) — or type X and Y. The origin is "
                "the default.",
                "Set the angle (360° = all round), Equal spacing and the "
                "number of instances; the copies show dashed.",
                "OK (or Enter) makes them."],
               "Equal spacing off: the angle is the step between copies."),
}
