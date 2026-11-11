"""The rest of the Sketch tab in the 3D view (2026-11-02, the user: "all
the other 2D ... tools so that they work in the 3D view").

Drawing tools (sketch_tools / sketch_tools2: arcs, ellipse, spline,
polyline, 3-point shapes, point, conic..., plus polygon and text) run
inside `sketch3d.Sketch3DTool`: its snapped clicks on the plane are their
points, and the 2D tools' own builders make the nodes through `Bench`, a
stand-in for the scene. Modify tools (trim, extend, sketch fillet and
chamfer, mirror, construction) are `Modify3D`: Constrain3D's picking of
what is drawn, the 2D tools' own operations.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from . import constrain3d, sketch_constraints as sc, sketch_modify as sm
from . import sketch_tools as st

#: a click this near (px) a polygon's first point closes it
CLOSE_PX = 10.0
MODIFY = (sm.TRIM, sm.EXTEND, sm.FILLET, sm.CHAMFER, "sk_mirror",
          "sk_construction", "sk_convert")
REGIONS = ("regions", "make_region")


def _polygon_tool():
    from .view2d import POLYGON
    return POLYGON


def _text_tool():
    from .view2d import TEXT
    return TEXT


def draws(tool):
    """A drawing tool that places points on the plane."""
    return st.handles(tool) or tool in (_polygon_tool(), _text_tool())


class _Signal:
    def __init__(self, fn=None):
        self.fn = fn

    def emit(self, *args):
        if self.fn:
            self.fn(*args)


class Bench:
    """What the 2D tools' builders ask of a scene, for the 3D sketch."""

    def __init__(self, sketch, tool):
        self.sketch = sketch
        self.tool = tool
        self.window = sketch.window
        self.model = sketch.window.model
        self.status = _Signal(lambda text: sketch.message(text, 6000))
        self.node_created = _Signal()
        self._sk_points = []
        self._sk_items = []
        self._sk_snaps = []
        self._pending_tangents = []
        self.made = []

    def _create(self, type_, params):
        if type_ == "line" and self.tool != st.SLOT:
            params = dict(params, width=0.2)   # a sketch curve, not a band
        node = self.model.add_node(type_, params, parent=self.parent())
        self.made.append(node)
        return node

    def parent(self):
        return self.sketch.holder or self.sketch.group

    @property
    def ask_value(self):
        return getattr(self.window.view2d.scene(), "ask_value", None)

    def views(self):
        return [self.window.view3d]

    def removeItem(self, item):
        pass

    def line_near(self, p):
        """(node, (a, b)) of the sketch's line under the point, else None.
        A rectangle's or polygon's side counts."""
        got = self._nearest(p)
        return (got[0], got[2]) if got else None

    def pick_line(self, p):
        got = self._nearest(p)
        return got[:2] if got else None

    def _nearest(self, p):
        from . import sketch_constrain_ui as ui
        tol = self.sketch._mm_per_px(*p) * constrain3d.PICK_PX
        best = None
        for node in self.parent().children:
            if node.type not in sc.SHAPES:
                continue
            for name, kind in ui._entities(node):
                if kind != "line":
                    continue
                try:
                    a, b = sc._line(node, name, {})
                except (KeyError, ValueError, IndexError):
                    continue
                d = constrain3d._seg_px(p, a, b)[0]
                if d <= tol and (best is None or d < best[0]):
                    best = (d, node, name, (a, b))
        return best[1:] if best else None


def use(sketch, tool):
    """Tool *tool* now places the sketch's points."""
    sketch.mode = "scene"
    sketch.scene_tool = tool
    sketch.bench = Bench(sketch, tool)
    sketch.points = []
    say(sketch)
    sketch.view.update()


def say(sketch):
    from . import language
    tool = sketch.scene_tool
    if tool == _polygon_tool():
        text = ("Polygon: click its corners; click the first again, Enter "
                "or right-click closes it.")
    elif tool == _text_tool():
        text = "Text: click where it starts."
    else:
        prompts = st.PROMPTS[tool]
        text = prompts[min(len(sketch.points), len(prompts) - 1)]
    sketch.message(language.tr(text))


def _closed(node):
    from . import slot2d
    return node.type != "line" or slot2d.is_slot(node)


def _after(sketch, made):
    """What a drawn shape leads to: a cut's first closed shape, its
    feature and window, as the rectangle's."""
    from . import cut_feature, face_outline, sketch_line
    scene = sketch.window.view2d.scene()
    for node in made:
        try:
            face_outline.pin(scene, sketch.window.model, node)
            if node.type == "polygon":
                sketch_line.polygon_relations(sketch.window.model, node)
            elif node.type == "line" and not node.params.get("bulge"):
                sketch._write_relations(node, None)
            if node.type == "line":
                sketch._tie_ends(node)   # a centerline from a corner
            from . import sketch_touch   # on a corner, centre or middle
            sketch_touch.relate(sketch.window.model, node)
        except Exception:                    # never stop a sketch
            pass
    sketch.made.extend(made)
    if made and all(n.type in sc.SHAPES + ("scale", "text") for n in made) \
            and any(_closed(n) for n in made) and sketch.holder is None and \
            sketch.group.params.get(cut_feature.KEY):
        sketch.make_feature()
    sketch.view.update()


def place(sketch, pt):
    """A click at sketch point *pt* for the running tool."""
    tool = sketch.scene_tool
    if tool == _text_tool():
        return _place_text(sketch, pt)
    if tool == _polygon_tool():
        return _place_polygon(sketch, pt)
    sketch.points.append(pt)
    need = st.CLICKS.get(tool)
    if need is not None and len(sketch.points) >= need:
        return finish(sketch)
    say(sketch)
    sketch.view.update()
    return None


def _place_polygon(sketch, pt):
    pts = sketch.points
    if len(pts) >= 3:
        mm = sketch._mm_per_px(*pt) * CLOSE_PX
        if math.hypot(pt[0] - pts[0][0], pt[1] - pts[0][1]) <= mm:
            return finish(sketch)
    pts.append(pt)
    sketch.view.update()
    return None


def _place_text(sketch, pt):
    scene = sketch.window.view2d.scene()
    hook = getattr(scene, "ask_value", None)
    if hook is not None:
        text = hook("text", "Text")
    else:
        from PyQt5.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(sketch.view, "Text", "Text:",
                                        text="Text")
        if not ok:
            return None
    if not text:
        return None
    node = sketch.bench._create("text", dict(text=str(text), x=pt[0],
                                             y=pt[1]))
    _after(sketch, [node])
    return node


def finish(sketch):
    """Make the shape from the points placed. Returns the node or None."""
    tool, bench, pts = sketch.scene_tool, sketch.bench, list(sketch.points)
    sketch.points = []
    if tool == _polygon_tool():
        if len(pts) < 3:
            return None
        node = bench._create("polygon", dict(
            points=[[p[0], p[1]] for p in pts]))
        _after(sketch, [node])
        return node
    bench._sk_points = pts
    bench.made = []
    node = st.finish(bench)
    if node is None:
        say(sketch)
    made, bench.made = bench.made, []
    _after(sketch, made)
    return node


def can_end(sketch):
    tool = sketch.scene_tool
    if tool == _polygon_tool():
        return len(sketch.points) >= 3
    return tool in st._variable() and \
        len(sketch.points) >= st._min_points(tool)


def preview(sketch, h):
    """Sketch points of the shape so far, the cursor at *h*."""
    tool = sketch.scene_tool
    pts = sketch.points + ([h] if h is not None else [])
    if tool == _polygon_tool():
        return pts
    try:
        return list(st.outline(tool, pts) or pts)
    except Exception:              # (a tangent tool's points are clicks)
        return pts


class Modify3D(constrain3d.Constrain3D):
    """Trim, extend, sketch fillet / chamfer, mirror and construction on
    what is drawn, picked in the 3D view."""

    def __init__(self, window, tool):
        self.window = window
        self.view = window.view3d
        self.tool = tool
        self.kind = "modify"
        self.picks = []
        self.hover = None
        self._down = None
        self._seen = None
        self.first = None          # a corner's first line
        self.shapes = []           # what Mirror mirrors
        self.axis_next = False

    def _allowed(self):
        if self.tool == sm.TRIM:
            from . import sketch_trim as tr
            return ("line",) if tr.mode() == tr.CORNER \
                else ("line", "circle")
        if self.tool == sm.EXTEND:
            return ("line",)
        if self.tool in (sm.FILLET, sm.CHAMFER):
            return ("point", "line", "circle")   # (an arc is a circle)
        if self.tool == "sk_mirror" and self.axis_next:
            return ("line",)
        return ("point", "line", "circle")

    def _prompt(self):
        if self.tool == "sk_mirror":
            return ("Mirror (3D): click the mirror line." if self.axis_next
                    else "Mirror (3D): click what to mirror (centerlines "
                    "and origins too), then Enter or right-click and the "
                    "mirror line.")
        if self.tool == "sk_construction":
            return "Construction (3D): click a sketch shape."
        if self.tool == "sk_convert":
            return ("Convert Entities (3D): click an edge of the part, or "
                    "inside the face for its whole outline.")
        return sm.PROMPTS[self.tool] + " (3D)"

    def key_press(self, event):
        from PyQt5.QtCore import Qt
        if self.tool == "sk_mirror" and self.shapes and \
                event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.axis_next = True
            self._say(self._prompt())
            return True
        if event.key() == Qt.Key_Escape and (self.shapes or self.first):
            self.shapes, self.first, self.axis_next = [], None, False
            self.view.update()
            self._say(self._prompt())
            return True
        return super().key_press(event)

    def _along(self, hit, x, y):
        """The sketch point on line *hit* under the screen point."""
        project = self._project()
        for node, name, kind, g in self.entities():
            if node is hit[0] and name == hit[1] and kind == "line":
                qa, qb = project(g[0]), project(g[1])
                if qa is None or qb is None:
                    continue
                d, t = constrain3d._seg_px((x, y), qa, qb)
                if d <= constrain3d.PICK_PX:
                    a, b = sc._line(node, name, {})
                    return (a[0] + (b[0] - a[0]) * t,
                            a[1] + (b[1] - a[1]) * t)
        a, b = sc._line(hit[0], hit[1], {})
        return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)

    def click(self, x, y):
        if self.tool == "sk_convert":
            return self._convert(x, y)
        hit = self.pick_at(x, y)
        if hit is None:
            self._say(self._prompt())
            return None
        try:
            return self._do(hit, x, y)
        except ValueError as exc:
            self._refuse("Refused: %s" % exc)
            return None
        finally:
            self.view.update()

    def _do(self, hit, x, y):
        tool, model = self.tool, self.window.model
        node = hit[0]
        if tool == "sk_construction":
            from . import sketch_tools2
            sketch_tools2.toggle_construction(model, [node])
            self._say("%s is %s." % (node.name, "construction now"
                                     if sketch_tools2.is_construction(node)
                                     else "solid again"))
            return node
        if tool == "sk_mirror":
            return self._mirror(hit)
        if tool == sm.TRIM:
            from . import sketch_trim as tr
            p = self._local(x, y)
            if p is None:
                p = self._along(hit, x, y) if node.type == "line" \
                    else (0, 0)
            self._hover_piece = []            # that piece is going
            self._say(tr.pick(model, node, p))
            panel = tr._panel(self.view, create=False)
            if panel is not None:
                panel.refresh()
            return node
        if tool in (sm.TRIM, sm.EXTEND):
            if node.type != "line":
                self._say("%s works on lines." % tool[3:].capitalize())
                return None
            p = self._along(hit, x, y)
            if tool == sm.TRIM:
                self._say("Trim: %s." % sm.trim(model, node, p))
                return node
            end = sm.extend(model, node, p)
            if end is None:
                self._refuse("Extend: nothing ahead to meet.")
            else:
                self._say("Extended to (%g, %g)." % end)
            return node
        round_ = tool == sm.FILLET
        scene = self.window.view2d.scene()
        if node.type in ("polygon", "rect") and hit[1].startswith("v"):
            size = sm._ask(scene, tool)
            if size is not None:
                sm.corner(model, node, int(hit[1][1:]), size, round_)
            return node
        from . import sketch_arc, sketch_corner
        if node.type == "line" and hit[1] in ("p1", "p2"):
            other = sketch_corner.partner(node, hit[1])
            if other is not None:
                size = sm._ask(scene, tool)
                if size is not None:
                    sketch_corner.corner(model, node, other, size, round_)
                return node
        if node.type != "line":
            self._say(sm.PROMPTS[tool])
            return None
        if self.first is None or self.first is node:
            self.first = node
            self._say("Now click the other line.")
            return None
        first, self.first = self.first, None
        size = sm._ask(scene, tool)
        if size is not None:
            sketch_corner.between(model, first, node, size, round_)
        return node

    def _convert(self, x, y):
        """Convert Entities on the sketch drawn in 3D: the part's edge
        under the click, or the whole face when the click is inside."""
        from . import sketch3d, sketch_convert
        sk = getattr(self.window, "_sketch3d_tool", None)
        if sk is None or sk.group is None:
            self._refuse("Convert Entities: open a sketch on a face first.")
            return None
        p = sk.local_of(x, y, True)
        if p is None:
            return None
        mm = sk._mm_per_px(*p) or 0.1
        parent = sk.holder or sk.group
        made = sketch_convert.click(
            self.window.model, parent, sk.info.get("segments") or [],
            p, sketch3d.EDGE_PX * mm)
        if made:
            self._say("Converted %d entit%s." % (
                len(made), "y" if len(made) == 1 else "ies"))
        else:
            self._say("Convert Entities: click an edge of the part, or "
                      "inside the face for its whole outline.")
        self.view.update()
        return made

    def _trim_hover(self, x, y):
        """The piece a click would remove, kept for paint (the user:
        "that quarter circle should be highlighted")."""
        from . import sketch_trim as tr
        pts = []
        if tr.mode() == tr.CLOSEST:
            hit = self.pick_at(x, y)
            p = self._local(x, y)
            if hit is not None and p is not None:
                pts = tr.piece_points(hit[0], p)
        if pts or getattr(self, "_hover_piece", None):
            self._hover_piece = pts
            self.view.update()

    def paint(self, painter, project):
        super().paint(painter, project)
        pts = getattr(self, "_hover_piece", None)
        sk = getattr(self.window, "_sketch3d_tool", None)
        if sk is not None and sk.group is not None and \
                self.tool in (sm.FILLET, sm.CHAMFER):
            from . import sketch_corner
            try:
                sketch_corner.paint_3d(
                    painter, project, sk.group,
                    [self.first] if self.first is not None else [],
                    getattr(self, "_corner_hover", None))
            except Exception:           # never raise out of a paint
                pass
        if pts and sk is not None and sk.group is not None:
            from . import sketch_trim as tr
            try:
                tr.paint_3d(painter, project, sk.group, pts)
            except Exception:           # never raise out of a paint
                pass

    def _local(self, x, y):
        """The screen point on the sketch's plane, in its own (x, y)."""
        sk = getattr(self.window, "_sketch3d_tool", None)
        if sk is None or sk.group is None:
            return None
        try:
            return sk.local_of(x, y, True)
        except Exception:
            return None

    # -- Power trim: a drag across the lines on screen ---------------
    def _power(self):
        from . import sketch_trim as tr
        return self.tool == sm.TRIM and tr.mode() == tr.POWER

    def mouse_press(self, event):
        from PyQt5.QtCore import Qt
        if self._power() and event.button() == Qt.LeftButton:
            self._stroke = (event.pos().x(), event.pos().y())
            return True                  # the drag trims, it never orbits
        if self.tool == "sk_mirror" and event.button() == Qt.RightButton \
                and self.shapes and not self.axis_next:
            self.axis_next = True        # box 2: now the mirror line
            self._say(self._prompt())
            return True
        return super().mouse_press(event)

    def mouse_move(self, event):
        last = getattr(self, "_stroke", None)
        if last is None or not self._power():
            if self.tool == sm.TRIM:
                self._trim_hover(event.pos().x(), event.pos().y())
            elif self.tool in (sm.FILLET, sm.CHAMFER):
                from . import sketch_corner
                hit = self.pick_at(event.pos().x(), event.pos().y())
                was = getattr(self, "_corner_hover", None)
                self._corner_hover = sketch_corner.hovered(
                    hit[0], hit[1]) if hit is not None else []
                if self._corner_hover or was:
                    self.view.update()
            return super().mouse_move(event)
        now = (event.pos().x(), event.pos().y())
        n = self.power_stroke(last, now)
        self._stroke = now
        if n:
            self._say("Power trim: %d piece(s) trimmed." % n)
            self.view.update()
        return True

    def mouse_release(self, event):
        if getattr(self, "_stroke", None) is not None and self._power():
            self._stroke = None
            return True
        return super().mouse_release(event)

    def power_stroke(self, a, b):
        """Trim every sketch line, arc and circle the screen stroke
        a -> b crosses."""
        sk = getattr(self.window, "_sketch3d_tool", None)
        la, lb = self._local(*a), self._local(*b)
        if sk is not None and la is not None and lb is not None:
            from . import sketch_trim as tr
            holder = sk.holder or sk.group
            return tr.power(self.window.model, list(holder.children),
                            la, lb)
        project = self._project()
        n = 0
        model = self.window.model
        for node, name, kind, g in list(self.entities()):
            if kind != "line" or node.type != "line" or node.parent is None:
                continue
            qa, qb = project(g[0]), project(g[1])
            if qa is None or qb is None:
                continue
            t = sm._seg_hit((qa[0], qa[1]), (qb[0], qb[1]), a, b)
            if t is None:
                continue
            la, lb = sc._line(node, name, {})
            t = min(max(t, 0.0), 1.0)
            sm.trim(model, node, (la[0] + (lb[0] - la[0]) * t,
                                  la[1] + (lb[1] - la[1]) * t))
            n += 1
        return n

    def _mirror(self, hit):
        from . import sketch_mirror, sketch_tools2
        node = hit[0]
        # every click is an entity to mirror (centerlines and origins
        # too) until Enter asks for the mirror line (the user)
        is_axis = hit[2] == "line" and node.type == "line" and \
            self.axis_next
        if not is_axis or not self.shapes:
            for n in sketch_mirror.expand(node):
                if n not in self.shapes:
                    self.shapes.append(n)
            self._say("Mirror (3D): %d shape(s); more, or Enter / "
                      "right-click then the mirror line."
                      % len(self.shapes))
            return None
        shapes, self.shapes, self.axis_next = self.shapes, [], False
        copies, skipped = sketch_mirror.mirror(self.window.model, shapes,
                                               node)
        self._say("Mirrored %d shape(s).%s" % (len(copies), (
            " Not in that line's sketch: " + ", ".join(skipped))
            if skipped else ""))
        if not copies:
            self._refuse("Mirror: the shapes must be in the line's sketch.")
        return copies


def start_modify(window, tool):
    view = window.view3d
    constrain3d.end(window)
    old = view.edit_tool
    if old is not None:
        for name in ("exit", "close", "_end", "stop", "cancel"):
            fn = getattr(old, name, None)
            if callable(fn):
                try:
                    fn()
                except Exception:      # pragma: no cover
                    pass
                break
    from . import sketch_trim
    sketch_trim.state.clear()
    if tool != sm.TRIM:
        sketch_trim.close_panel(view)
    t = Modify3D(window, tool)
    view.edit_tool = t
    view.setMouseTracking(True)
    view.update()
    t._say(t._prompt())
    return True


def start_regions(window, tool, container=None):
    from . import sketch_regions
    return sketch_regions.start_3d(window, container,
                                   make_only=tool == "make_region")
