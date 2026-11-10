"""Sketch in 3D (2026-10-27, the user: "we need to be able to draw a
sketch in the 3D. For example, select a plane in 3D and it stays there,
and then make a rectangle").

A `View3D.edit_tool`. First a click chooses WHERE: a drawn plane (the
main Front / Top / Right planes or any reference Plane) or a flat face
of a part — whichever is nearest under the cursor. The camera does not
move. A face-sketch Group is made on it (the same Group Sketch on Face
makes, so Edit Sketch, the extrude arrow and the cuts all work), and
then the clicks draw ON the plane, in 3D:

- Rectangle (R): two corners;
- Circle (C): the centre, then a point on the rim;
- Line (L): click to click, chained; right-click / Enter ends a chain.

Points snap to the grid (the sketch grid size) in the plane's own axes;
Alt draws free. Esc / Done ends the tool and selects the sketch, ready
for Extruded Boss. A press that moves turns the model as always.
`plane_hit` and `local_of` are the geometry, testable without a mouse.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from . import language, refgeom

MODES = ("rect", "circle", "line", "slot")
MODE_KEYS = {"R": "rect", "C": "circle", "L": "line", "S": "slot"}
#: a line or slot this near level or upright (degrees) snaps to it
ANGLE_SNAP = 5.0
#: how near the cursor (pixels) a point or an edge takes it
SNAP_PX = 10.0
EDGE_PX = 7.0


def straighten(a, b, tol=ANGLE_SNAP):
    """*b* moved to lie level or upright from *a* when it nearly does."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    ang = abs(math.degrees(math.atan2(dy, dx))) % 180.0
    if min(ang, 180.0 - ang) < tol:
        return (b[0], a[1])
    if abs(ang - 90.0) < tol:
        return (a[0], b[1])
    return b


def relation_of(a, b, prev=None):
    """The relation a line from *a* to *b* already holds, or None."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    if math.hypot(dx, dy) < 1e-9:
        return None
    tol = 1e-3
    if abs(dy) < tol:
        return "horizontal"
    if abs(dx) < tol:
        return "vertical"
    if abs(abs(dx) - abs(dy)) < tol:
        return "diagonal"
    if prev and abs(dx * prev[0] + dy * prev[1]) < tol * math.hypot(*prev):
        return "perpendicular"
    return None


#: what the cursor says while a line is aimed
RELATION_MARK = {"horizontal": "H", "vertical": "V", "diagonal": "45°",
                 "perpendicular": "90°"}


def start(window, mode="rect"):
    from . import drag_feature, refgeom_ui
    view = window.view3d
    drag_feature.step_aside(view)
    if view.edit_tool is not None:
        try:
            view.edit_tool.cancel()
        except Exception:
            view.edit_tool = None
    tool = Sketch3DTool(window, mode)
    view.edit_tool = tool
    # the camera stays where the user aimed it: the first shape drawn
    # must not trigger the first-geometry Fit
    view.user_moved = True
    # a Plane or a face sketch already selected: draw on it at once
    for node in window.builder.active_tree().selected_nodes():
        if node.type == "ref_plane":
            tool.use_group(refgeom_ui.sketch_on(window, node,
                                                open_2d=False))
            break
        from .face_sketch import group_of
        group = group_of(node)
        if group is not None:
            tool.use_group(group)
            break
    if tool.group is None:
        window._ref_force_planes = True   # show them while picking
    tool.begin()
    return tool


def snap(v, step):
    return round(v / step) * step if step > 0 else v


def tidy(v):
    return round(float(v), 4) + 0.0


def rect_params(a, b):
    x0, x1 = sorted((a[0], b[0]))
    y0, y1 = sorted((a[1], b[1]))
    return dict(x=tidy(x0), y=tidy(y0), width=tidy(x1 - x0),
                height=tidy(y1 - y0))


def circle_params(c, p):
    return dict(x=tidy(c[0]), y=tidy(c[1]),
                radius=tidy(math.hypot(p[0] - c[0], p[1] - c[1])))


#: a press moved further than this (px) is a drag: it draws the shape
DRAG_PX = 6


class Sketch3DTool:
    """See the module docstring."""

    def __init__(self, window, mode="rect"):
        self.window = window
        self.view = window.view3d
        self.mode = mode if mode in MODES else "rect"
        self.group = None             # the sketch Group, once chosen
        self.points = []              # the shape being drawn (local)
        self.hover = None             # local point under the cursor
        self.target = None            # plane / face under the cursor
        self._press = None
        self._pulling = False
        self.holder = None            # the extrude shapes join, if made
        self.snapped = None           # (x, y, kind) under the cursor
        self.lit = []                 # model / sketch edges lit up
        self.info = {}                # the face's segments and points
        self._drag = None             # (node, role) of a dragged point
        self.made = []
        self.arc = self._armed = self._away = False
        self.ready_button = None

    # -- life -------------------------------------------------------
    def begin(self):
        from PyQt5.QtCore import Qt
        v = self.view
        v.setMouseTracking(True)
        v.setCursor(Qt.CrossCursor)
        v.setFocus(Qt.OtherFocusReason)
        self.window._sketch3d_tool = self
        self._sync_button()
        self._say()
        v.update()

    def _sync_button(self):
        try:
            from . import sketch_mode
            sketch_mode.sync_create(self.window)
        except Exception:                           # pragma: no cover
            pass

    def _load_face(self):
        """The face's edges, corners, middles and centres to snap to."""
        from . import face_outline, face_sketch
        self.info = {}
        try:
            part = getattr(self.window, "_cut_parts", {}).get(id(self.group)) \
                or face_sketch.part_of(self.group)
            if part is not None:
                face_outline.show(self.window, self.group, part)
            self.info = getattr(self.window.view2d.scene(),
                                "face_outline", None) or {}
        except Exception:                           # never stop a sketch
            import traceback
            traceback.print_exc()

    def _own(self):
        """(segments, points) of the shapes drawn in this sketch."""
        from . import anchors, face_outline, mesh, sketch_arc, slot2d
        segs, pts = [], []
        env = anchors.doc_env(self.window.model)
        shapes = list((self.holder or self.group).children) \
            if self.group else []
        while any(n.type == "union" for n in shapes):   # a Polyline's group
            shapes = [k for n in shapes for k in (
                n.children if n.type == "union" else [n])]
        for shape in shapes:
            if shape.type == "line" and not slot2d.is_slot(shape):
                p = shape.params        # one line, not a band's two sides
                try:
                    ends = [(float(p[a]), float(p[b])) for a, b in
                            (("x1", "y1"), ("x2", "y2"))]
                except (KeyError, TypeError, ValueError):
                    continue
                if sketch_arc.is_arc(shape):
                    run = sketch_arc.points(*ends[0], *ends[1],
                                            sketch_arc.bulge_of(p))
                    segs += list(zip(run, run[1:]))
                else:
                    segs.append(tuple(ends))
                pts += [(*ends[0], "end"), (*ends[1], "end"),
                        ((ends[0][0] + ends[1][0]) / 2,
                         (ends[0][1] + ends[1][1]) / 2, "middle")]
                continue
            try:
                loops = mesh.node_outlines(shape, env) or \
                    mesh.collect_outlines(shape, env) or []
            except Exception:
                continue
            for loop in loops:
                segs += [(loop[i], loop[(i + 1) % len(loop)])
                         for i in range(len(loop))]
            if shape.type == "circle":
                pts.append((shape.params.get("x", 0), shape.params.get("y", 0),
                            "centre"))
            elif shape.type == "rect":
                pts += face_outline.snap_points(
                    [(loop[i], loop[(i + 1) % len(loop)]) for loop in loops
                     for i in range(len(loop))])
            elif shape.type == "line":
                p = shape.params
                x1, y1, x2, y2 = (p.get(k, 0) for k in
                                  ("x1", "y1", "x2", "y2"))
                pts += [(x1, y1, "end"), (x2, y2, "end"),
                        ((x1 + x2) / 2, (y1 + y2) / 2, "middle")]
        return segs, pts

    def aimed(self, pt):
        """(*pt* moved onto the direction it nearly has, what that direction
        is): level, upright, 45° or square to the last line. A corner it
        snapped to wins; on an edge it stays on the edge."""
        a = self.points[-1]
        if self.snapped is not None and self.snapped[2] != "edge":
            return pt, relation_of(a, pt, self._last_dir())
        dx, dy = pt[0] - a[0], pt[1] - a[1]
        L = math.hypot(dx, dy)
        if L < 1e-9:
            return pt, None
        ang = math.degrees(math.atan2(dy, dx)) % 360.0
        prev = self._last_dir()
        best = None
        for want in (0, 45, 90, 135, 180, 225, 270, 315):
            if abs((ang - want + 180) % 360 - 180) < ANGLE_SNAP:
                best = want
        if best is None and prev is not None:
            base = math.degrees(math.atan2(prev[1], prev[0]))
            for want in (base + 90, base - 90):
                if abs((ang - want + 180) % 360 - 180) < ANGLE_SNAP:
                    best = want
        if best is None:
            return pt, None
        c, s = math.cos(math.radians(best)), math.sin(math.radians(best))
        if abs(c) < 1e-12:
            c = 0.0
        if abs(s) < 1e-12:
            s = 0.0
        # the cursor's own reach along that direction (its distance from
        # the start made a level line 20.0062 long, not 20)
        reach = dx * c + dy * s
        q = (tidy(a[0] + c * reach), tidy(a[1] + s * reach))
        if self.lit and self.snapped is not None:
            # along that direction to where it meets the edge
            e0, e1 = self.lit[0]
            ex, ey = e1[0] - e0[0], e1[1] - e0[1]
            det = c * ey - s * ex
            if abs(det) > 1e-9:
                t = ((e0[0] - a[0]) * ey - (e0[1] - a[1]) * ex) / det
                q = (tidy(a[0] + c * t), tidy(a[1] + s * t))
        return q, relation_of(a, q, prev)

    def _last_dir(self):
        last = self._chain_end()
        if last is None or last.params.get("bulge"):
            return None
        p = last.params
        return (p["x2"] - p["x1"], p["y2"] - p["y1"])

    def _write_relations(self, node, prev):
        """What the line was drawn as stays so (as the 2D Line)."""
        from . import sketch_constraints as sc
        p = node.params
        cont = node.parent
        kind = relation_of((p["x1"], p["y1"]), (p["x2"], p["y2"]),
                           (prev["x2"] - prev["x1"], prev["y2"] - prev["y1"])
                           if prev and not prev.get("bulge") else None)
        rows = []
        l = sc.ref_of(cont, node, "l")
        if kind in ("horizontal", "vertical", "diagonal"):
            rows.append((kind, [l]))
        elif kind == "perpendicular":
            last = self.made[-1]
            rows.append((kind, [sc.ref_of(cont, last, "l"), l]))
        for k, refs in rows:
            try:
                sc.add(self.window.model, cont, k, refs)
            except ValueError:
                pass

    def _chain_end(self):
        """The chain's last line, when the next point starts at its end
        (only then is there a direction for a tangent arc)."""
        last = self.made[-1] if self.made else None
        if self.mode != "line" or len(self.points) < 1 or last is None or \
                last.type != "line" or last.parent is None:
            return None
        end = (last.params["x2"], last.params["y2"])
        at = self.points[-2] if len(self.points) >= 2 and \
            self.points[-1] != end else self.points[-1]
        return last if tuple(at) == tuple(end) else None

    def _bulge(self, pt):
        from . import sketch_arc
        last = self.made[-1]
        start = (last.params["x2"], last.params["y2"])
        return sketch_arc.tangent_bulge(
            start, sketch_arc.end_tangent(last.params), pt)

    def _arc_switch(self, x, y):
        """As the 2D Line: the mouse brought back onto the chain's last
        point and out again makes the next piece a tangent arc (again:
        a line); one arc, then lines."""
        from . import sketch_line as sl
        last = self._chain_end()
        if last is None:
            self.arc = self._armed = self._away = False
            return
        v = self.view
        q = v._project(*v._camera(), self._world(self.points[-1]))
        if q is None:
            return
        d = math.hypot(q[0] - x, q[1] - y)
        if d >= sl.ARC_AWAY_PX:
            # the next line was really being drawn first, as in the 2D
            # view (at 16 px an arc came far too easily)
            self._away = True
        if d <= sl.ARC_ARM_PX and self._away:
            self._armed, self._away = True, False
        elif self._armed and d >= sl.ARC_GO_PX:
            self._armed = False
            self.arc = not self.arc
            self.message(language.tr(
                "Line: tangent ARC — click where it ends (back on the point "
                "and out again for a line)." if self.arc else
                "Line: straight again."), 6000)

    def _world(self, p):
        from .face_sketch import to_world
        return to_world(self.group, p[0], p[1])

    def _closes_area(self):
        """Do the lines drawn split the face into areas, with its edges
        or by themselves?"""
        from . import sketch_regions, sketch_section
        cont = self.holder or self.group
        try:
            shapes, _ghost = sketch_section.with_section(
                self.window, cont, sketch_regions.shapes_of(cont))
            return len(sketch_regions.faces(shapes)) >= 2
        except Exception:
            return False

    def _end_chain(self):
        """A chain ended; the sketch stays open until the user goes on."""
        self.points = []
        self.arc = self._armed = self._away = False
        self.update_ready()
        self.view.update()

    def is_ready(self):
        """A cut's or boss's sketch whose lines now make an area."""
        from . import cut_feature, sketch_regions
        g = self.group
        if g is None or g.parent is None or self.holder is not None or \
                not g.params.get(cut_feature.KEY):
            return False
        lines = [n for n in sketch_regions.shapes_of(g)
                 if n.type == "line"]
        return bool(lines) and self._closes_area()

    def update_ready(self):
        """Say when the sketch has closed an area, and offer the feature
        (the window follows, as SolidWorks' does on leaving the sketch)."""
        from . import cut_feature
        ready = self.is_ready()
        was = self.ready_button is not None and \
            not self.ready_button.isHidden()
        if not ready:
            if self.ready_button is not None:
                self.ready_button.hide()
            return False
        b = self.ready_button
        if b is None:
            from PyQt5.QtCore import Qt
            from PyQt5.QtWidgets import QPushButton
            b = self.ready_button = QPushButton(self.view)
            b.setCursor(Qt.ArrowCursor)
            b.setStyleSheet(
                "QPushButton { background: #2e7d32; color: white; "
                "border-radius: 4px; padding: 6px 16px; font-weight: "
                "bold; } QPushButton:hover { background: #388e3c; }")
            b.clicked.connect(self.go_on)
        label = cut_feature.ALL[self.group.params[cut_feature.KEY]][0]
        b.setText("✓  " + language.tr("Area closed — make %s") % label)
        b.adjustSize()
        b.move((self.view.width() - b.width()) // 2, 40)
        b.show()
        b.raise_()
        if not was:
            self.message(language.tr(
                "Area closed: press the green button, or right-click, to "
                "go on. Or keep drawing."), 8000)
        return True

    def go_on(self):
        self.points = []
        self.finish()

    def _join(self, last, node):
        """A chain's lines stay joined, as the 2D Line tool's."""
        from . import sketch_constraints as sc
        if last is None or last.type != "line" or \
                last.parent is not node.parent or \
                (last.params["x2"], last.params["y2"]) != \
                (node.params["x1"], node.params["y1"]):
            return
        try:
            sc.add(self.window.model, node.parent, "coincident",
                   [sc.ref_of(node.parent, last, "p2"),
                    sc.ref_of(node.parent, node, "p1")])
        except ValueError:
            pass

    def _tie_ends(self, node):
        """A line ending exactly on another line's end is tied to it —
        above all the last line of a loop back on its first point (it
        was not: Smart Dimension 80 on the L's foot pushed its free
        start to -4 and the outline came open). SolidWorks adds the
        same Coincident where it snaps to a point."""
        from . import sketch_constraints as sc
        cont = node.parent
        if cont is None:
            return
        tied = {frozenset(r["refs"]) for r in sc.rows(cont)
                if r["kind"] == "coincident"}
        ends = lambda n: (("p1", (n.params["x1"], n.params["y1"])),
                          ("p2", (n.params["x2"], n.params["y2"])))
        for other in cont.children:
            if other is node or other.type != "line":
                continue
            for a, pa in ends(node):
                for b, pb in ends(other):
                    if pa != pb:
                        continue
                    refs = [sc.ref_of(cont, other, b),
                            sc.ref_of(cont, node, a)]
                    if frozenset(refs) in tied:
                        continue
                    try:
                        sc.add(self.window.model, cont, "coincident", refs)
                        tied.add(frozenset(refs))
                    except (ValueError, KeyError):
                        pass

    def _mm_per_px(self, lx, ly):
        from .face_sketch import to_world
        view = self.view
        eye, right, up, forward = view._camera()
        a = view._project(eye, right, up, forward,
                          to_world(self.group, lx, ly))
        b = view._project(eye, right, up, forward,
                          to_world(self.group, lx + 1.0, ly))
        c = view._project(eye, right, up, forward,
                          to_world(self.group, lx, ly + 1.0))
        if a is None or b is None or c is None:
            return None
        px = max(math.hypot(b[0] - a[0], b[1] - a[1]),
                 math.hypot(c[0] - a[0], c[1] - a[1]))
        return 1.0 / px if px > 1e-9 else None

    def _light(self, segs, a, b):
        """Every piece of the edge a-b belongs to: the whole straight
        side, or the whole circle."""
        from . import face_outline
        for (cx, cy), r in face_outline.arcs(segs):
            tol = max(r * 0.02, 1e-3)
            if abs(math.hypot(a[0] - cx, a[1] - cy) - r) < tol and \
                    abs(math.hypot(b[0] - cx, b[1] - cy) - r) < tol:
                return [(p, q) for p, q in segs
                        if abs(math.hypot(p[0] - cx, p[1] - cy) - r) < tol
                        and abs(math.hypot(q[0] - cx, q[1] - cy) - r) < tol]
        return [face_outline._whole_edge(segs, a, b)]

    def snap_local(self, lx, ly):
        """(x, y) snapped to a point or edge near the cursor, else None;
        sets `snapped` and `lit` for the paint."""
        from . import face_outline
        self.snapped, self.lit = None, []
        mm = self._mm_per_px(lx, ly)
        if mm is None:
            return None
        own_segs, own_pts = self._own()
        segs = list(self.info.get("segments") or []) + own_segs
        pts = list(self.info.get("points") or []) + own_pts
        best = None
        for x, y, kind in pts:
            d = math.hypot(x - lx, y - ly)
            if d <= SNAP_PX * mm and (best is None or d < best[0]):
                best = (d, x, y, kind)
        near = None
        for a, b in segs:
            ex, ey = face_outline._on_segment(lx, ly, a, b)
            d = math.hypot(ex - lx, ey - ly)
            if near is None or d < near[0]:
                near = (d, ex, ey, a, b)
        if near is not None and near[0] <= EDGE_PX * mm:
            self.lit = self._light(segs, near[3], near[4])
        if best is not None:
            self.snapped = (best[1], best[2], best[3])
            return best[1], best[2]
        if self.lit:
            self.snapped = (near[1], near[2], "edge")
            return near[1], near[2]
        return None

    def resume(self):
        """A dimension or relation finished: drawing again."""
        if self.window._sketch3d_tool is self and \
                self.view.edit_tool is None:
            self.view.edit_tool = self
            self.view.setMouseTracking(True)
            self.view.update()

    def make_feature(self):
        """The sketch's first closed shape: the feature is made and THE
        Extrude window opens on it (the arrow, every option, OK / Cancel);
        the Sketch tab still dimensions it and adds shapes from there."""
        from . import cut_feature, drag_feature
        g = self.group
        kind = g.params.get(cut_feature.KEY)
        self._end()
        made = cut_feature.finish(self.window, g)
        if made is None:
            cut_feature.clear_chosen_face(self.window)
        if made is None:
            return made
        if kind in cut_feature.BOSS:     # (a boss opens the window itself)
            drag = self.view.edit_tool
            if isinstance(drag, drag_feature.DragFeature):
                model = self.window.model
                drag.on_cancel = lambda: model.remove_node(g)
            return made
        ext = next((n for n in g.walk() if n.type == "linear_extrude"), None)
        if ext is None:
            return made
        drag = drag_feature.start(self.window, ext, quiet=True, panel=True)
        if drag is not None:
            model = self.window.model

            def undo():
                model.remove_node(g)
                if made.parent is not None and len(made.children) == 1:
                    model.ungroup(made)
            drag.on_cancel = undo
        return made

    def tool_icon(self, tool):
        """A drawing icon of the Sketch tab was clicked."""
        from . import constrain3d, sketch_constrain_ui, sketch_tools
        from .view2d import CIRCLE, LINE, RECT, SELECT
        constrain3d.end(self.window)
        self.resume()
        if sketch_constrain_ui.handles(tool):
            # Smart Dimension and the relations, on this sketch, in 3D
            self.view.edit_tool = None
            if constrain3d.start(self.window, tool):
                return
            self.view.edit_tool = self
        from . import sketch3d_tools as more
        mode = {RECT: "rect", CIRCLE: "circle", LINE: "line",
                sketch_tools.SLOT: "slot"}.get(tool)
        if mode:
            self.set_mode(mode)
        elif tool in more.MODIFY:
            self.view.edit_tool = None
            more.start_modify(self.window, tool)
        elif tool in more.REGIONS:
            self.view.edit_tool = None
            more.start_regions(self.window, tool, self.holder or self.group)
        elif more.draws(tool):
            more.use(self, tool)
        elif tool != SELECT:
            self.message(language.tr(
                "That tool does not work on the 3D sketch yet."), 6000)

    def set_mode(self, mode):
        self.scene_tool = None
        self.mode = mode
        self.points = []
        self._say()
        self.view.update()

    def _say(self):
        if getattr(self, "scene_tool", None) and self.group is not None:
            from . import sketch3d_tools
            sketch3d_tools.say(self)
            return
        if self.group is None:
            text = ("Sketch in 3D: click a plane (Front, Top, Right or "
                    "your own) or a flat face of a part to draw on.")
        else:
            text = {"rect": "Rectangle: click two corners on the plane.",
                    "circle": "Circle: click the centre, then the rim.",
                    "line": "Line: click point to point; A, or back on the "
                            "last point and out, makes an arc; right-click "
                            "or Enter ends the chain.",
                    "slot": "Slot: click one end, the other end, then "
                            "the width."}[self.mode] + \
                " R / C / L / S switch, Alt draws off the grid, Esc ends."
        self.message(language.tr(text))

    def message(self, text, ms=0):
        try:
            self.window.statusBar().showMessage(text, ms)
        except Exception:                           # pragma: no cover
            pass

    def _end(self):
        if self.ready_button is not None:
            self.ready_button.hide()
            self.ready_button.deleteLater()
            self.ready_button = None
        self.window._ref_force_planes = False
        self.window._sketch3d_tool = None
        from . import constrain3d
        constrain3d.end(self.window)
        v = self.view
        if v.edit_tool is self:
            v.edit_tool = None
        v.setMouseTracking(False)
        v.unsetCursor()
        self._sync_button()
        from . import drag_feature
        drag_feature.resume_paused(self.window)
        try:
            from . import face_outline
            face_outline.clear(self.window)
        except Exception:
            pass
        v.update()

    def cancel(self):
        self.finish()

    def finish(self):
        """End the tool; an empty sketch goes, a full one is selected."""
        self._end()
        if self.holder is not None:      # more shapes: back to its window
            return None
        g = self.group
        from . import cut_feature
        if g is not None and g.parent is not None and g.children and \
                g.params.get(cut_feature.KEY):
            made = cut_feature.finish(self.window, g)
            cut_feature.clear_chosen_face(self.window)   # (no window)
            return made
        cut_feature.clear_chosen_face(self.window)
        if g is None or g.parent is None:
            self.message(language.tr("Sketch in 3D ended."), 4000)
            return None
        if not g.children:
            self.window.model.remove_node(g)
            self.message(language.tr("Sketch in 3D ended (nothing drawn)."),
                         4000)
            return None
        try:
            self.window.builder.active_tree().select_nodes([g])
        except Exception:
            pass
        self.message(language.tr(
            "Sketch done — Extruded Boss (or drag its arrow) makes it "
            "solid."), 8000)
        return g

    # -- where ------------------------------------------------------
    def use_group(self, group):
        self.window._ref_force_planes = False     # picked: hide again
        self.group = group
        self.points = []
        self._load_face()
        self._say()

    def plane_hit(self, x, y):
        """(origin, normal, label, what) of the plane or flat face under
        the screen point, nearest first, or None."""
        from . import refgeom_ui
        from .curve_draw import Snapper
        from .sculpt_ui import screen_ray
        origin, d = screen_ray(self.view, x, y)
        best = None
        hit = refgeom_ui.plane_at(self.window, x, y)
        if hit is not None:
            label, o, n, _s, what, p = hit
            best = (math.dist(p, origin), o, n, label, what)
        mesh = getattr(self.view, "model_mesh", None) or self.view.mesh
        if mesh:
            snapper = getattr(self, "_snapper", None)
            if snapper is None or snapper.tris is not mesh:
                snapper = self._snapper = Snapper(mesh)
            got = snapper.hit(tuple(origin), tuple(d))
            if got is not None:
                p, n = got
                dist = math.dist(p, origin)
                if best is None or dist < best[0] - 1e-6:
                    best = (dist, [tidy(c) for c in p],
                            [tidy(c) for c in refgeom.unit(n)],
                            "face", None)
        return None if best is None else best[1:]

    def choose(self, x, y):
        from . import refgeom_ui
        got = self.plane_hit(x, y)
        if got is None:
            self.message(language.tr(
                "No plane or face there — aim at a drawn plane or a part."),
                4000)
            return None
        o, n, label, what = got
        if hasattr(what, "type"):
            group = refgeom_ui.sketch_on(self.window, what, open_2d=False)
        else:
            if isinstance(what, str):
                from . import plane_pick
                label = plane_pick.name_of(what)
            group = refgeom_ui.sketch_on(self.window, origin=o, normal=n,
                                         label=language.tr(label),
                                         open_2d=False)
        self.use_group(group)
        self.view.update()
        return group

    # -- drawing ----------------------------------------------------
    def _grid(self):
        scene = getattr(self.window, "scene", None)
        try:
            step = float(getattr(scene, "grid_size", 1.0))
        except (TypeError, ValueError):
            step = 1.0
        return step if step > 0 else 1.0

    def local_of(self, x, y, free=False):
        """The point on the sketch plane under the screen point, in the
        sketch's own (x, y), snapped to the grid unless *free*."""
        from .face_sketch import _normal_of, to_local, to_world
        from .sculpt_ui import screen_ray
        g = self.group
        origin, d = screen_ray(self.view, x, y)
        o = to_world(g, 0.0, 0.0)
        n = _normal_of(g)
        p = refgeom.ray_plane(list(origin), list(d), o, n)
        if p is None:
            return None
        lx, ly = to_local(g, p)
        self.snapped, self.lit = None, []
        if not free:
            got = self.snap_local(lx, ly)
            if got is not None:
                return (tidy(got[0]), tidy(got[1]))
            step = self._grid()
            lx, ly = snap(lx, step), snap(ly, step)
        return (tidy(lx), tidy(ly))

    def place(self, pt):
        """A click at sketch point *pt*."""
        if getattr(self, "scene_tool", None):
            from . import sketch3d_tools
            return sketch3d_tools.place(self, pt)
        model = self.window.model
        if self.mode == "line" and self.points and not self.arc:
            pt = self.aimed(pt)[0]
        elif self.mode == "slot" and len(self.points) == 1:
            pt = straighten(self.points[-1], pt)
        self.points.append(pt)
        node = None
        if self.mode == "slot" and len(self.points) == 3:
            from . import sketch_constraints as sc, slot2d, sketch_tools
            spec = sketch_tools.slot(*self.points)
            self.points = []
            if spec:
                node = model.add_node(spec[0][0], spec[0][1],
                                      parent=self.holder or self.group)
                slot2d.mark(model, node)
                par = node.params
                kind = "horizontal" if abs(par["y1"] - par["y2"]) < 1e-9 \
                    else "vertical" if abs(par["x1"] - par["x2"]) < 1e-9 \
                    else None
                if kind:
                    try:
                        sc.add(model, node.parent, kind,
                               [sc.ref_of(node.parent, node, "l")])
                    except (ValueError, KeyError):
                        pass
        if self.mode == "rect" and len(self.points) == 2:
            par = rect_params(*self.points)
            if par["width"] > 0 and par["height"] > 0:
                node = model.add_node("rect", par, parent=self.holder or self.group)
            self.points = []
        elif self.mode == "circle" and len(self.points) == 2:
            par = circle_params(*self.points)
            if par["radius"] > 0:
                node = model.add_node("circle", par, parent=self.holder or self.group)
            self.points = []
        elif self.mode == "line" and len(self.points) >= 2:
            a, b = self.points[-2], self.points[-1]
            if a != b:
                # a sketch line, as in the 2D view: a 1 mm line was a band
                # with two sides, and closed nothing with the model's edges
                last = self.made[-1] if self.made else None
                params = dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1], width=0.2)
                arc = self.arc and self._chain_end() is not None
                if arc:
                    bulge = self._bulge(b)
                    if abs(bulge) > 1e-9:
                        params["bulge"] = round(bulge, 10)
                self.arc = self._armed = self._away = False
                node = model.add_node("line", params,
                                      parent=self.holder or self.group)
                if arc:
                    if params.get("bulge"):
                        model.rename(node, "Arc")
                    self._say()          # (lines again: say so)
                self._join(last, node)
                self._tie_ends(node)
                if not arc:
                    self._write_relations(
                        node, last.params if last is not None and
                        last.type == "line" and tuple(a) == (
                            last.params["x2"], last.params["y2"]) else None)
            else:
                self.points = []
        if node is not None:
            self.made.append(node)
            try:                 # tied to what it was drawn on
                from . import face_outline
                face_outline.pin(self.window.view2d.scene(), model, node)
            except Exception:
                pass
            if self.mode == "line" and len(self.points) >= 4 and \
                    tuple(self.points[0]) == tuple(self.points[-1]):
                self._end_chain()        # back on its start: a closed loop
                return node
            if node.type == "line":
                self.update_ready()
            from . import cut_feature
            if self.mode != "line" and self.holder is None and \
                    self.group.params.get(cut_feature.KEY):
                self.make_feature()
                return node
        self.view.update()
        return node

    # -- dragging a drawn point (the constraints follow live) -------
    def handles(self):
        """[(node, role, local point)] of the sketch's draggable points."""
        out = []
        g = self.group
        if g is None or g.parent is None:
            return out
        for n in g.children:
            p = n.params
            try:
                if n.type == "line":
                    out += [(n, "p1", (float(p["x1"]), float(p["y1"]))),
                            (n, "p2", (float(p["x2"]), float(p["y2"])))]
                elif n.type == "rect":
                    x, y = float(p["x"]), float(p["y"])
                    w, h = float(p["width"]), float(p["height"])
                    out += [(n, "c0", (x, y)), (n, "c1", (x + w, y)),
                            (n, "c2", (x + w, y + h)), (n, "c3", (x, y + h))]
                elif n.type == "circle":
                    x, y, r = (float(p["x"]), float(p["y"]),
                               float(p["radius"]))
                    out += [(n, "centre", (x, y)), (n, "rim", (x + r, y))]
            except (KeyError, TypeError, ValueError):
                continue                 # an expression: not draggable
        return out

    def handle_at(self, x, y, px=9.0):
        from .face_sketch import to_world
        from PyQt5.QtCore import QPointF
        del QPointF
        v = self.view
        eye, right, up, forward = v._camera()
        best = None
        for node, role, lp in self.handles():
            s = v._project(eye, right, up, forward,
                           to_world(self.group, lp[0], lp[1]))
            if s is None or s[2] <= 0:
                continue
            d = math.hypot(s[0] - x, s[1] - y)
            if d <= px and (best is None or d < best[0]):
                best = (d, node, role)
        return None if best is None else best[1:]

    def drag_to(self, node, role, pt):
        """Move one point of a drawn shape; the model's constraints
        re-solve at once (MainWindow._model_edited)."""
        p = node.params
        if node.type == "line":
            kx, ky = ("x1", "y1") if role == "p1" else ("x2", "y2")
            p[kx], p[ky] = pt
        elif node.type == "rect":
            x, y = float(p["x"]), float(p["y"])
            w, h = float(p["width"]), float(p["height"])
            corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
            fixed = corners[(int(role[1]) + 2) % 4]
            p.update(rect_params(fixed, pt))
        elif node.type == "circle":
            if role == "centre":
                p["x"], p["y"] = pt
            else:
                p["radius"] = tidy(max(math.hypot(
                    pt[0] - float(p["x"]), pt[1] - float(p["y"])), 0.01))
        self.window.model.node_changed.emit(node)
        self.view.update()

    # -- the view's hooks -----------------------------------------
    def wants_key(self, event):
        from PyQt5.QtCore import Qt
        if event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
            return False
        return event.key() in (Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter,
                               Qt.Key_R, Qt.Key_C, Qt.Key_L, Qt.Key_S)

    def key_press(self, event):
        from PyQt5.QtCore import Qt
        key = event.key()
        if getattr(self, "scene_tool", None) and self.points:
            from . import sketch3d_tools as more
            if key in (Qt.Key_Return, Qt.Key_Enter) and more.can_end(self):
                more.finish(self)
                return True
            if key == Qt.Key_Backspace:
                self.points.pop()
                self.view.update()
                return True
        if key == Qt.Key_Escape:
            if self.points:
                self.points = []
                self.view.update()
            else:
                self.finish()
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            if self.points:
                self._end_chain()
            else:
                self.finish()
        elif event.text().upper() == "A" and self._chain_end() is not None:
            self.arc = not self.arc      # the same as back on the point
            self.view.update()
            self.message(language.tr("Line: tangent ARC — click where it "
                                     "ends." if self.arc else
                                     "Line: straight again."), 6000)
        elif event.text().upper() in MODE_KEYS:
            self.set_mode(MODE_KEYS[event.text().upper()])
        else:
            return False
        return True

    def mouse_press(self, event):
        from PyQt5.QtCore import Qt
        if event.button() == Qt.RightButton:
            if getattr(self, "scene_tool", None) and self.points:
                from . import sketch3d_tools as more
                if more.can_end(self):
                    more.finish(self)
                    return True
            if self.points:
                self._end_chain()
            else:
                self.finish()
            return True
        if event.button() != Qt.LeftButton:
            return False
        if self.group is not None and not self.points:
            grab = self.handle_at(event.pos().x(), event.pos().y())
            if grab is not None:
                self._drag = grab
                return True
        self._press = (event.pos(), event.modifiers())
        self._pulling = False
        # on a sketch the left button DRAWS, as in SolidWorks: press,
        # drag, release makes the shape (2026-11-10, the user). It turned
        # the view, and one slip of the hand lost the square-on look. The
        # middle button turns it meanwhile (`middle_orbits`). Before a
        # plane is chosen a drag still turns, to find the plane.
        return self.group is not None

    @property
    def middle_orbits(self):
        return self.group is not None

    def mouse_release(self, event):
        from PyQt5.QtCore import Qt
        if self._drag is not None:
            self._drag = None
            return True
        press, self._press = self._press, None
        if press is None or event.button() != Qt.LeftButton:
            return False
        free = bool(press[1] & Qt.AltModifier)
        if self.group is None:
            if (event.pos() - press[0]).manhattanLength() > 4:
                return False                # it was an orbit
            self.click(event.pos().x(), event.pos().y(), free)
            return True
        pulled, self._pulling = self._pulling, False
        made = self.click(event.pos().x(), event.pos().y(), free)
        if pulled and self.mode == "line" and made is not None and \
                not getattr(self, "scene_tool", None) and \
                self.window._sketch3d_tool is self:
            self._end_chain()        # one dragged line, not a chain
        return True

    def click(self, x, y, free=False):
        if self.group is None:
            self.choose(x, y)
            return None
        pt = self.local_of(x, y, free)
        if pt is None:
            self.message(language.tr("That is off the sketch plane."), 3000)
            return None
        return self.place(pt)

    def mouse_move(self, event):
        from PyQt5.QtCore import Qt
        x, y = event.pos().x(), event.pos().y()
        if self._drag is not None:
            pt = self.local_of(x, y, bool(event.modifiers() &
                                          Qt.AltModifier))
            if pt is not None:
                self.drag_to(self._drag[0], self._drag[1], pt)
            return True
        if self._press is not None:
            if self.group is None:
                return False                # turning, to find the plane
            press = self._press
            if not self._pulling and \
                    (event.pos() - press[0]).manhattanLength() > DRAG_PX:
                # a drag: its first point is where the button went down
                self._pulling = True
                if not self.points:
                    self.click(press[0].x(), press[0].y(),
                               bool(press[1] & Qt.AltModifier))
            if self._pulling and self.window._sketch3d_tool is self:
                self._arc_switch(x, y)
                self.hover = self.local_of(
                    x, y, bool(event.modifiers() & Qt.AltModifier))
                self.view.update()
            return True
        if self.group is None:
            self.target = self.plane_hit(x, y)
        else:
            self._arc_switch(x, y)
            self.hover = self.local_of(
                x, y, bool(event.modifiers() & Qt.AltModifier))
        self.view.update()
        return False

    def wheel(self, event):
        return False

    # -- drawing on screen ----------------------------------------
    def paint(self, painter, project):
        from PyQt5.QtCore import QPointF, Qt
        from PyQt5.QtGui import QColor, QPen
        from .face_sketch import to_world
        if self.group is None:
            if self.target is not None:
                o, n, label, _w = self.target
                from . import refgeom_ui
                size = refgeom_ui._half(self.window)
                pts = [project(c) for c in
                       refgeom_ui.plane_corners(o, n, size)]
                if all(p is not None and p[2] > 0 for p in pts):
                    from PyQt5.QtGui import QPolygonF
                    painter.setPen(QPen(QColor(240, 140, 30), 2))
                    painter.setBrush(QColor(240, 140, 30, 60))
                    painter.drawPolygon(QPolygonF(
                        [QPointF(p[0], p[1]) for p in pts]))
            return
        g = self.group
        if g.parent is None:
            return

        def scr(lp):
            p = project(to_world(g, lp[0], lp[1]))
            return QPointF(p[0], p[1]) if p is not None and p[2] > 0 else None
        # what has been drawn, on the face
        painter.setPen(QPen(QColor(33, 118, 199), 2))
        for a, b in self._own()[0]:
            qa, qb = scr(a), scr(b)
            if qa and qb:
                painter.drawLine(qa, qb)
        # the edge the cursor is on lights up, whole
        painter.setPen(QPen(QColor(240, 140, 30), 3))
        for a, b in self.lit:
            qa, qb = scr(a), scr(b)
            if qa and qb:
                painter.drawLine(qa, qb)
        if self.snapped is not None:
            q = scr(self.snapped[:2])
            if q is not None:
                painter.setPen(QPen(QColor(240, 140, 30), 2))
                painter.setBrush(QColor(255, 200, 60))
                painter.drawRect(int(q.x()) - 4, int(q.y()) - 4, 8, 8)
                painter.drawText(q + QPointF(10, 16), language.tr(
                    self.snapped[2].capitalize()))
        pen = QPen(QColor(240, 140, 30), 2)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        h = self.hover
        if self.points and getattr(self, "scene_tool", None):
            from . import sketch3d_tools
            qs = [scr(p) for p in sketch3d_tools.preview(self, h)]
            for qa, qb in zip(qs, qs[1:]):
                if qa and qb:
                    painter.drawLine(qa, qb)
        elif self.points and h is not None and self.arc and \
                self._chain_end() is not None:
            from . import sketch_arc
            a = self.points[-1]
            run = sketch_arc.points(a[0], a[1], h[0], h[1], self._bulge(h))
            qs = [scr(p) for p in run]
            for qa, qb in zip(qs, qs[1:]):
                if qa and qb:
                    painter.drawLine(qa, qb)
        elif self.points and h is not None and self.mode == "line":
            q, kind = self.aimed(h)
            qa, qb = scr(self.points[-1]), scr(q)
            if qa and qb:
                painter.drawLine(qa, qb)
                a = self.points[-1]
                L = math.hypot(q[0] - a[0], q[1] - a[1])
                ang = math.degrees(math.atan2(q[1] - a[1], q[0] - a[0])) % 360
                text = f"{tidy(L):g}  ∠ {round(ang, 1):g}°"
                if kind:
                    text = RELATION_MARK[kind] + "  " + text
                painter.drawText(qb + QPointF(10, -10), text)
        elif self.points and h is not None:
            a = self.points[-1]
            if self.mode == "rect":
                corners = [a, (h[0], a[1]), h, (a[0], h[1]), a]
                qs = [scr(c) for c in corners]
                if all(qs):
                    for i in range(4):
                        painter.drawLine(qs[i], qs[i + 1])
                w, ht = abs(h[0] - a[0]), abs(h[1] - a[1])
                if qs[2] is not None:
                    painter.drawText(qs[2] + QPointF(8, -8),
                                     f"{w:g} × {ht:g}")
            elif self.mode == "circle":
                r = math.hypot(h[0] - a[0], h[1] - a[1])
                ring = [scr((a[0] + r * math.cos(t * math.pi / 24),
                             a[1] + r * math.sin(t * math.pi / 24)))
                        for t in range(49)]
                if all(ring):
                    for i in range(48):
                        painter.drawLine(ring[i], ring[i + 1])
                q = scr(h)
                if q is not None:
                    painter.drawText(q + QPointF(8, -8), f"Ø{2 * r:g}")
            elif self.mode == "slot" and len(self.points) == 2:
                # the two ends fixed: the width follows the cursor
                c1, c2 = self.points
                dx, dy = c2[0] - c1[0], c2[1] - c1[1]
                L = math.hypot(dx, dy) or 1.0
                r = abs(dx * (h[1] - c1[1]) - dy * (h[0] - c1[0])) / L
                ux, uy = dx / L, dy / L
                base = math.atan2(uy, ux)
                ring = [(c2[0] + r * math.cos(base - math.pi / 2 + math.pi * i / 12),
                         c2[1] + r * math.sin(base - math.pi / 2 + math.pi * i / 12))
                        for i in range(13)]
                ring += [(c1[0] + r * math.cos(base + math.pi / 2 + math.pi * i / 12),
                          c1[1] + r * math.sin(base + math.pi / 2 + math.pi * i / 12))
                         for i in range(13)]
                qs = [scr(c) for c in ring + ring[:1]]
                if all(qs):
                    for i in range(len(qs) - 1):
                        painter.drawLine(qs[i], qs[i + 1])
                q = scr(h)
                if q is not None:
                    painter.drawText(q + QPointF(8, -8), f"{2 * r:g}")
            else:
                if self.mode == "slot" or self.points:
                    h = straighten(a, h)
                qa, qh = scr(a), scr(h)
                if qa and qh:
                    painter.drawLine(qa, qh)
                    painter.drawText(qh + QPointF(8, -8), f"{math.hypot(h[0] - a[0], h[1] - a[1]):g}")
        painter.setPen(QPen(QColor(33, 118, 199), 1.2))
        painter.setBrush(QColor(255, 255, 255))
        for _n, _r, lp in self.handles():       # draggable points
            q = scr(lp)
            if q is not None:
                painter.drawRect(int(q.x()) - 3, int(q.y()) - 3, 6, 6)
        painter.setBrush(Qt.NoBrush)
        if h is not None:
            q = scr(h)
            if q is not None:
                painter.setPen(QPen(QColor(240, 140, 30), 1.5))
                painter.drawEllipse(q, 4.0, 4.0)
