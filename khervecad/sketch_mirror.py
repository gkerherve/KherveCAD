"""Mirror Entities — sketch shapes mirrored about a LINE (2026-10-28, the
user: the Mirror we had reflects about a face or plane, "which is not
quite right for a sketch"; SolidWorks' Mirror Entities).

Pick what to mirror — the shapes already selected, or click them with
the tool on — then the line to mirror about: a click on a centerline
(construction line) mirrors at once; Enter or right-click first lets an
ordinary line be the mirror. Each copy is the same kind of shape in the
same sketch (a line stays a line, a circle or arc a circle, a polygon a
polygon; a rectangle stays a rectangle about a level or upright line and
becomes a polygon about a slanted one), and is tied to its original by
Symmetric relations (Equal for a circle's size), so editing one side
moves the other.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

TOOL = "sk_mirror"
EPS = 1e-9
#: polygons up to this many points get a Symmetric relation per vertex
RELATE_POINTS = 12


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def axis_of(line):
    """The mirror line's two ends."""
    p = line.params
    return ((_num(p.get("x1")), _num(p.get("y1"))),
            (_num(p.get("x2")), _num(p.get("y2"))))


def reflect(pt, axis):
    (ax, ay), (bx, by) = axis
    dx, dy = bx - ax, by - ay
    n = dx * dx + dy * dy
    if n < EPS:
        raise ValueError("The mirror line has no length.")
    t = ((pt[0] - ax) * dx + (pt[1] - ay) * dy) / n
    fx, fy = ax + t * dx, ay + t * dy
    return (2 * fx - pt[0], 2 * fy - pt[1])


def _r(v):
    return round(v, 4)


def _axis_angle(axis):
    (ax, ay), (bx, by) = axis
    return math.degrees(math.atan2(by - ay, bx - ax))


def mirrored_params(node, axis):
    """(type, params) of *node* mirrored about *axis*, or None when the
    shape cannot be mirrored as one of its own kind."""
    p = dict(node.params)
    t = node.type
    if t == "line":
        a = reflect((_num(p.get("x1")), _num(p.get("y1"))), axis)
        b = reflect((_num(p.get("x2")), _num(p.get("y2"))), axis)
        p.update(x1=_r(a[0]), y1=_r(a[1]), x2=_r(b[0]), y2=_r(b[1]))
        return t, p
    if t == "circle":
        c = reflect((_num(p.get("x")), _num(p.get("y"))), axis)
        p.update(x=_r(c[0]), y=_r(c[1]))
        angle = _num(p.get("angle", 360), 360)
        if angle < 360 - 1e-6:
            # an arc runs the other way round: its start is the mirror of
            # the old end
            start = _num(p.get("start_angle", 0))
            p["start_angle"] = _r((2 * _axis_angle(axis) - start - angle)
                                  % 360)
        return t, p
    if t == "rect":
        x, y = _num(p.get("x")), _num(p.get("y"))
        w, h = _num(p.get("width"), 1), _num(p.get("height"), 1)
        corners = [reflect(q, axis) for q in
                   ((x, y), (x + w, y), (x + w, y + h), (x, y + h))]
        (ax, ay), (bx, by) = axis
        level = abs(by - ay) < 1e-9 or abs(bx - ax) < 1e-9
        if level and not p.get("center"):
            xs = [q[0] for q in corners]
            ys = [q[1] for q in corners]
            p.update(x=_r(min(xs)), y=_r(min(ys)))
            return t, p
        pts = [[_r(q[0]), _r(q[1])] for q in corners[::-1]]
        out = {k: v for k, v in p.items() if k in ("modifier",)}
        out["points"] = pts
        return "polygon", out
    if t == "polygon":
        pts = p.get("points") or []
        # the points are relative to the polygon's own x, y (a polygon
        # drawn with the mouse has one): reflect them where they ARE —
        # reflected about the origin instead, the copy landed elsewhere
        # and its Symmetric relations dragged the whole sketch over
        ox, oy = _num(p.get("x")), _num(p.get("y"))
        try:
            got = [reflect((ox + _num(q[0]), oy + _num(q[1])), axis)
                   for q in pts]
        except (TypeError, IndexError):
            return None
        n = len(got)
        o = reflect((ox, oy), axis) if ("x" in p or "y" in p) else (0, 0)
        if "x" in p or "y" in p:
            p["x"], p["y"] = _r(o[0]), _r(o[1])
        # reflected, a loop runs the other way round: reverse it so the
        # winding (and so solid / hole) is kept
        p["points"] = [[_r(q[0] - o[0]), _r(q[1] - o[1])]
                       for q in got[::-1]]
        if p.get("paths"):
            p["paths"] = [[n - 1 - int(i) for i in path][::-1]
                          for path in p["paths"]]
        if p.get("corners"):
            p["corners"] = [[n - 1 - int(row[0])] + list(row[1:])
                            for row in p["corners"]]
        return t, p
    return None


def _relate(model, container, orig, copy, mirror):
    """Symmetric relations between *orig* and *copy* about *mirror*."""
    from . import sketch_constraints as sc
    ref = lambda n, e: sc.ref_of(container, n, e)
    rows = []
    if orig.type == "line" and copy.type == "line":
        rows = [("symmetric", [ref(orig, "p1"), ref(copy, "p1"),
                               ref(mirror, "l")]),
                ("symmetric", [ref(orig, "p2"), ref(copy, "p2"),
                               ref(mirror, "l")])]
    elif orig.type == "circle":
        rows = [("symmetric", [ref(orig, "c"), ref(copy, "c"),
                               ref(mirror, "l")]),
                ("equal", [ref(orig, "o"), ref(copy, "o")])]
    elif orig.type == "polygon" and copy.type == "polygon":
        n = len(orig.params.get("points") or [])
        if n <= RELATE_POINTS:
            rows = [("symmetric", [ref(orig, "v%d" % i),
                                   ref(copy, "v%d" % (n - 1 - i)),
                                   ref(mirror, "l")]) for i in range(n)]
    for kind, refs in rows:
        try:
            sc.add(model, container, kind, refs)
        except Exception:                   # a conflict: geometry stays
            pass


def mirror(model, shapes, line, relate=True):
    """Mirror *shapes* about the line node *line* (all in one sketch).
    Returns (copies, skipped names)."""
    from .model import SHAPE_2D
    container = line.parent
    axis = axis_of(line)
    reflect(axis[0], axis)                  # raises on a zero-length line
    copies, skipped = [], []
    for s in shapes:
        if s is line or s.category != SHAPE_2D:
            continue
        if s.parent is not container:
            skipped.append(s.name)
            continue
        got = mirrored_params(s, axis)
        if got is None:
            skipped.append(s.name)
            continue
        t, params = got
        copy = model.add_node(t, params, parent=container)
        copy.visible = s.visible
        copies.append((s, copy))
    if relate:
        for s, copy in copies:
            _relate(model, container, s, copy, line)
    return [c for _s, c in copies], skipped


# ------------------------------------------------------- the 2D view
# A SolidWorks-like PropertyManager (the user: "say select objects ...
# then select the mirror line"): two boxes filled by clicks in the
# sketch — the active one outlined — and OK / Cancel.
SHAPES, LINE = "shapes", "line"


def _state(scene):
    st = getattr(scene, "_mirror", None)
    if st is None:
        st = scene._mirror = {"shapes": [], "line": None, "active": SHAPES}
    return st


def _is_centerline(node):
    return node.type == "line" and node.params.get("modifier") == "%"


def _show(scene):
    """The picked shapes drawn selected (blue); the mirror line too."""
    st = _state(scene)
    ids = {n.id for n in st["shapes"]}
    if st["line"] is not None:
        ids.add(st["line"].id)
    scene.updating = True
    try:
        for item in scene.items():
            node = getattr(item, "node", None)
            if node is not None and hasattr(item, "handle_spec"):
                item.setSelected(node.id in ids)
    finally:
        scene.updating = False
    panel = _panel(scene, create=False)
    if panel is not None:
        panel.refresh()


def ready(scene):
    st = _state(scene)
    return bool(st["shapes"]) and st["line"] is not None


def prompt(scene):
    st = _state(scene)
    if st["active"] == SHAPES:
        return ("Mirror Entities — 1: click the lines, circles and shapes "
                "to mirror (%d picked), then the centerline."
                % len(st["shapes"]))
    if st["line"] is None:
        return "Mirror Entities — 2: click the centerline (or any line)."
    return "Mirror Entities — press OK (or Enter) to make the copies."


def _view(scene):
    views = scene.views()
    return views[0] if views else None


def _panel(scene, create=True):
    view = _view(scene)
    if view is None:
        return None
    panel = getattr(view, "_mirror_panel", None)
    if panel is None and create:
        panel = view._mirror_panel = _make_panel(view)
    return panel


def start(win):
    """The button: the tool and its panel; shapes already selected fill
    the first box, a selected centerline the second."""
    from .model import SHAPE_2D
    scene = win.view2d.scene()
    picked = [n for n in win.builder.active_tree().selected_nodes()
              if n.category == SHAPE_2D]
    lines = [n for n in picked if _is_centerline(n)]
    others = [n for n in picked if n not in lines]
    win._set_tool(TOOL)
    begin(scene, others, lines[0] if len(lines) == 1 and others else None)


def begin(scene, shapes=(), line=None):
    st = _state(scene)
    st["shapes"], st["line"] = list(shapes), line
    # shapes already picked: the next click is the mirror line
    st["active"] = LINE if st["shapes"] and line is None else SHAPES
    panel = _panel(scene)
    if panel is not None:
        panel.open()
    _show(scene)
    scene.status.emit(prompt(scene))


def set_active(scene, which):
    _state(scene)["active"] = which
    _show(scene)
    scene.status.emit(prompt(scene))


def ok(scene):
    st = _state(scene)
    if not ready(scene):
        scene.status.emit(prompt(scene))
        return []
    copies = _run(scene, st["shapes"], st["line"])
    view = _view(scene)
    if view is not None:
        view.set_tool("select")
    return copies


def cancel(scene):
    drop(scene)
    view = _view(scene)
    if view is not None:
        view.set_tool("select")
    scene.status.emit("Mirror Entities cancelled.")


def _run(scene, shapes, line):
    try:
        copies, skipped = mirror(scene.model, shapes, line)
    except ValueError as exc:
        scene.status.emit(str(exc))
        return []
    msg = "Mirrored %d shape(s) about %s." % (len(copies), line.name)
    if skipped:
        msg += " Not mirrored (another sketch, or a kind it cannot " \
               "copy): %s." % ", ".join(skipped)
    drop(scene)
    scene.status.emit(msg)
    return copies


def press(scene, event):
    from PyQt5.QtCore import Qt
    from . import sketch_constrain_ui as scu
    event.accept()
    st = _state(scene)
    if _panel(scene, create=False) is None or \
            not _panel(scene, create=False).isVisible():
        begin(scene)
    if event.button() == Qt.RightButton:
        if ready(scene):
            ok(scene)
        elif st["shapes"]:
            set_active(scene, LINE)
        return
    if event.button() != Qt.LeftButton:
        return
    pos = event.scenePos()
    if st["active"] == LINE:
        hit = scu.pick(scene, pos, "line")
        if hit is None or hit[0].type != "line" or hit[0] in st["shapes"]:
            scene.status.emit(prompt(scene))
            return
        st["line"] = hit[0]
        _show(scene)
        scene.status.emit(prompt(scene))
        return
    hit = scu.pick(scene, pos)
    if hit is None:
        scene.status.emit(prompt(scene))
        return
    node = hit[0]
    if _is_centerline(node) and st["shapes"] and node not in st["shapes"]:
        st["line"], st["active"] = node, LINE    # box 2 filled by itself
    elif node is st["line"]:
        st["line"] = None
    elif node in st["shapes"]:
        st["shapes"].remove(node)
    else:
        st["shapes"].append(node)
    _show(scene)
    scene.status.emit(prompt(scene))


def key(scene, event):
    from PyQt5.QtCore import Qt
    st = _state(scene)
    if event.key() in (Qt.Key_Return, Qt.Key_Enter):
        if ready(scene):
            ok(scene)
        elif st["shapes"]:
            set_active(scene, LINE)
        return True
    if event.key() == Qt.Key_Escape:
        cancel(scene)
        return True
    return False


def drop(scene):
    scene._mirror = None
    panel = _panel(scene, create=False)
    if panel is not None:
        panel.hide()
    try:
        scene.updating = True
        scene.clearSelection()
    finally:
        scene.updating = False


def _make_panel(view):
    from .tool_panel import ToolPanel

    class MirrorPanel(ToolPanel):
        """Mirror Entities' window: two boxes, OK / Cancel."""

        def __init__(self):
            super().__init__(view, "Mirror Entities",
                             on_ok=lambda: ok(view.scene()),
                             on_cancel=lambda: cancel(view.scene()))
            self.hint("Mirrors sketch shapes about a line. Fill the two "
                      "boxes by clicking in the sketch, then OK.")
            activate = lambda key: set_active(view.scene(), key)
            self.box_shapes = self.selection(
                SHAPES, "1  Entities to mirror", on_activate=activate)
            self.box_line = self.selection(
                LINE, "2  Mirror about", on_activate=activate)
            self.finish()

        def refresh(self):
            scene = view.scene()
            st = _state(scene)
            names = [n.name for n in st["shapes"]]
            self.box_shapes.set_text(
                ", ".join(names) if names else
                "Click the lines, circles and shapes to mirror — each "
                "turns blue. Click one again to drop it.")
            line = st["line"]
            self.box_line.set_text(
                line.name + (" (centerline)" if _is_centerline(line)
                             else "")
                if line is not None else
                "Click the centerline (or any line) to mirror about.")
            self.set_active(st["active"])
            self.set_ok_enabled(ready(scene))
            self.adjustSize()
            self.place()

        def show(self):
            super().show()

    return MirrorPanel()


TIPS = {TOOL: (
    "Mirror Entities",
    "Mirrors sketch shapes about a line — usually a centerline — as "
    "SolidWorks does: the copies are tied to the originals by Symmetric "
    "relations, so changing one side changes the other.",
    ["Click this: a panel opens top-left of the sketch.",
     "Box 1, Entities to mirror: click the lines, circles and shapes "
     "(already selected ones are filled in).",
     "Box 2, Mirror about: click the centerline — or click the box, then "
     "any line.",
     "OK (or Enter) makes the copies; Cancel or Esc leaves."],
    "A rectangle mirrored about a slanted line becomes a polygon.")}
