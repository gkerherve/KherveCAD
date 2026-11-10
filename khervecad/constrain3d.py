"""Sketch relations and Smart Dimensions IN the 3D view (2026-11-01,
the user: "I want to be able to use the constraints in 3D mode too —
clicking a constraint switched straight to 2D").

A constraint tool chosen while the 3D model shows (not sketching) runs
here as a `View3D.edit_tool`: every sketch's points, lines, rectangle
sides, circles and slot ends are projected onto the screen; the one
under the mouse lights up (what a click would take), clicks collect the
picks the relation needs — a pick from another sketch comes in as a
fixed reference that follows its source — and the relation or dimension
is added with the 2D tool's own rules
(sketch_constrain_ui: `_wants`, `finish`'s adjustments, `_smart`). What
a solid hides is not offered. A drag still turns the view; Esc / a
right click drops the picks, a second Esc ends the tool.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from . import sketch_constraints as sc

#: how near (px) the mouse must be to take an entity
PICK_PX = 9.0
#: a point beats a curve this close to it
POINT_PX = 7.0
LINE_FIRST_PX = 2.5
#: how far a press may move and still be a click (px)
CLICK_PX = 4


def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)]
            for i in range(4)]


def _apply(m, p):
    return tuple(m[i][0] * p[0] + m[i][1] * p[1] + m[i][3]
                 for i in range(3))


def sketches(window):
    """[(container, 4x4 to the world)] of the sketches in view."""
    from . import mesh
    root = window._render_scope()[0]
    iso = root if root is not window.model.root else None
    out = []
    with window._isolated_frame(iso):
        for c in root.walk():
            if not any(k.type in sc.SHAPES and k.visible
                       for k in c.children):
                continue
            try:
                m = _mul(mesh.ancestor_matrix(c, {}, stop=iso),
                         mesh.node_matrix(c, {}))
            except Exception:
                continue
            out.append((c, m))
    return out


def _seg_px(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    n2 = dx * dx + dy * dy
    t = 0.0 if n2 < 1e-12 else max(0.0, min(1.0, (
        (p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / n2))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy), t


def dim_fixed(container, node):
    """Is *node* a reference copied from the part or another sketch?"""
    p = node.params
    return bool(p.get("ref_world") or p.get("ref_source") or
                p.get("ref_face")) or str(node.name).startswith("Reference")


def sc_entity(node, kind):
    """(entity, kind) of a reference node already in a sketch."""
    if node.type == "line":
        return "l", "line"
    return ("o", "circle") if kind == "circle" else ("c", "point")


class Constrain3D:
    """The edit tool (see the module's docstring)."""

    def __init__(self, window, tool):
        from . import sketch_constrain_ui as ui
        self.window = window
        self.view = window.view3d
        self.tool = tool
        self.kind = tool[len(ui.PREFIX):]
        self.picks = []                 # (node, entity, kind)
        self.hover = None
        self._down = None
        self._seen = None

    # ------------------------------------------------------- geometry
    def _project(self):
        v = self.view
        cam = v._camera()
        return lambda p: v._project(*cam, p)

    def _occluder(self):
        if self._seen is None:
            from . import sketch_dims3d
            try:
                self._seen = sketch_dims3d._occluder(self.window)
            except Exception:
                self._seen = lambda p: True
        return self._seen

    def _shapes(self, cont):
        # not the kept outline of the part (Model edges): it is grown a
        # hair past the part so areas close, and a dimension clicked on
        # it measured 47.55 where the real edge is 47.5 away. A click
        # there falls through to the model's TRUE edge instead
        from . import sketch_section
        return [k for k in cont.children if k.type in sc.SHAPES
                and k.visible and not sketch_section.is_section(k)]

    def entities(self):
        """[(node, entity, kind, world geometry)] of every sketch."""
        from . import sketch_constrain_ui as ui
        out = []
        for cont, m0 in sketches(self.window):
            for m, node in [(m, n) for m in self._levels(cont, m0)
                            for n in self._shapes(cont)]:
                for name, kind in ui._entities(node):
                    try:
                        if kind == "point":
                            g = _apply(m, sc._point(node, name, {}))
                        elif kind == "line":
                            a, b = sc._line(node, name, {})
                            g = (_apply(m, a), _apply(m, b))
                        else:
                            c, r = sc._circle(node, name, {})
                            a0, sweep = ui._end_arc(node, name)
                            g = [_apply(m, (c[0] + r * math.cos(
                                a0 + sweep * i / 48), c[1] + r * math.sin(
                                    a0 + sweep * i / 48))) for i in range(49)]
                    except (KeyError, ValueError, IndexError, TypeError):
                        continue
                    out.append((node, name, kind, g))
        return out

    @staticmethod
    def _levels(cont, m):
        """The frames a sketch's shapes show at: its plane, and the far
        end of its extrude — the top of a cube IS its sketch's outline,
        and that is the edge one sees and clicks (the plane's far side
        lies hidden under the cube)."""
        from . import extrude_panel
        out = [m]
        ext = cont.parent if cont.type == "regions" else cont
        if ext is None or ext.type != "linear_extrude":
            return out
        height = ext.params.get("height")
        # (a boss's: the far end of a cut is inside the part, and offering
        # it put phantom circles in the air beyond a hole)
        if isinstance(height, (int, float)) and height and \
                not ext.params.get("center") and \
                not ext.params.get("reverse") and \
                not extrude_panel.is_cut(ext):
            out.append([[r[0], r[1], r[2], r[3] + r[2] * float(height)]
                        for r in m])
        return out

    def _allowed(self):
        """Which kinds the next click may take."""
        from . import sketch_constrain_ui as ui
        if self.kind == "dimension":
            return ("point", "line", "circle")
        want = ui._wants(self.kind, self.picks)
        if want is None:
            return ("point", "line", "circle")
        if want == "curve":
            return ("line", "circle")
        return (want,)

    def _working_on(self):
        """The container of the sketch being drawn or extruded, if any."""
        w = self.window
        sk = getattr(w, "_sketch3d_tool", None)
        if sk is not None:
            return sk.holder or sk.group
        drag = getattr(w, "_drag_paused", None)
        ext = drag.target() if drag is not None else None
        if ext is not None:
            # the extrude's SKETCH: its Regions when it has one (a
            # reference put beside the Regions was a stray "Sketch 4
            # (Reference edge)" in the History, outside every sketch)
            for child in ext.children:
                if child.type == "regions":
                    return child
        return ext

    def _face_info(self, parent):
        """The face's outline for *parent*'s sketch: (group, info)."""
        from . import face_outline, face_sketch
        group = face_sketch.group_of(parent) if parent is not None else None
        if group is None or group.parent is None:
            return None, {}
        scene = self.window.view2d.scene()
        if getattr(self, "_face_for", None) is not group:
            self._face_for = group
            part = face_sketch.part_of(group)
            if part is not None:
                face_outline.show(self.window, group, part)
        return group, getattr(scene, "face_outline", None) or {}

    def model_near(self, x, y, parent):
        """The face's corner, centre or edge under the screen point:
        ("point", (x, y)) or ("line", (a, b)) in the sketch, or None."""
        from . import face_sketch
        group, info = self._face_info(parent)
        if group is None:
            return None
        project = self._project()

        def scr(p):
            return project(face_sketch.to_world(group, p[0], p[1]))
        best = None
        for px, py, kind in list(info.get("points") or []) + \
                [(0.0, 0.0, "origin")]:
            if kind == "middle":
                continue               # mid-edge: the EDGE is meant
            q = scr((px, py))
            if q is not None:
                d = math.hypot(q[0] - x, q[1] - y)
                if d <= PICK_PX and (best is None or d < best[0]):
                    best = (d, "point", (px, py))
        if best is not None:
            return best[1:]
        for a, b in info.get("segments") or ():
            qa, qb = scr(a), scr(b)
            if qa is None or qb is None:
                continue
            d, _t = _seg_px((x, y), qa, qb)
            if d <= PICK_PX and (best is None or d < best[0]):
                best = (d, "line", (a, b))
        return best[1:] if best else None

    def _corner_near(self, x, y, parent):
        """The CORNER of the face's outline under the screen point (its
        world place), or None."""
        from . import face_sketch
        group, info = self._face_info(parent)
        if group is None:
            return None
        project = self._project()
        # the face's OWN outline only (not the section behind it, whose
        # every facet of a hole is a "corner")
        ends = {(round(p[0], 3), round(p[1], 3))
                for seg in info.get("segments") or () for p in seg}
        for px, py, kind in info.get("points") or ():
            if kind != "corner" or \
                    (round(px, 3), round(py, 3)) not in ends:
                continue
            w = face_sketch.to_world(group, px, py)
            q = project(w)
            if q is not None and math.hypot(q[0] - x, q[1] - y) <= PICK_PX:
                return tuple(w)
        return None

    def _passes_through(self, hit, world):
        """Does the picked line / circle really go through *world* (and
        not only across it on screen)?"""
        for node, name, _kind, g in self.entities():
            if node is not hit[0] or name != hit[1]:
                continue
            pts = list(g) if hit[2] == "circle" else [g[0], g[1]]
            tol = 1e-3
            if hit[2] == "circle":       # drawn as chords: within one
                tol = max(tol, 0.02 * max(math.dist(pts[0], q)
                                          for q in pts))
            for a, b in zip(pts, pts[1:]):
                ab = [b[i] - a[i] for i in range(3)]
                L2 = sum(c * c for c in ab) or 1e-18
                t = max(0.0, min(1.0, sum(
                    (world[i] - a[i]) * ab[i] for i in range(3)) / L2))
                if math.dist(world, [a[i] + ab[i] * t
                                     for i in range(3)]) < tol:
                    return True
        return False

    def model_pick(self, x, y, parent):
        """A click on the face: a fixed construction copy in the sketch,
        as the 2D view makes, returned as a pick."""
        from PyQt5.QtCore import QPointF
        from . import face_outline
        near = self.model_near(x, y, parent)
        if near is None:
            return None
        kind, where = near
        # an edge is named by its MIDDLE: its first end is a corner two
        # edges share, and the other one was taken (the foot's end edge
        # clicked, its long side dimensioned to — as an angle)
        pos = where if kind == "point" else (
            (where[0][0] + where[1][0]) / 2.0,
            (where[0][1] + where[1][1]) / 2.0)
        before = set(map(id, parent.children)) if parent is not None \
            else set()
        made = face_outline.reference(
            self.window.view2d.scene(), QPointF(pos[0], pos[1]), kind,
            parent=parent)
        if parent is not None:           # new ones go if nothing uses them
            if not hasattr(self, "_fresh"):
                self._fresh = []
            self._fresh += [c for c in parent.children
                            if id(c) not in before]
        return made

    def _in_sketch(self, cont, world):
        """World point -> (x, y) in *cont*'s sketch, along its normal."""
        import numpy as np
        from . import model_refs
        p = np.linalg.inv(model_refs.sketch_matrix(self.window, cont)) @ \
            np.array([*world, 1.0])
        return round(float(p[0]), 6), round(float(p[1]), 6)

    def _add_reference(self, cont, kind, pts, tag=None):
        """A fixed construction copy in *cont*: a pick, as the 2D view's.
        *tag* {param: value} says what it follows (model_refs)."""
        model = self.window.model
        made = self._make_reference(model, cont, kind, pts)
        if tag:
            made[0].params.update(tag)
        if not hasattr(self, "_fresh"):
            self._fresh = []
        self._fresh.append(made[0])      # goes again if nothing uses it
        return made

    def _drop_fresh(self):
        """References made for a dimension that did not come about are
        taken out again (they piled up as stray reference edges)."""
        fresh, self._fresh = getattr(self, "_fresh", []), []
        model = self.window.model
        for node in reversed(fresh):
            cont = node.parent
            if cont is None or not cont.children or \
                    cont.children[-1] is not node:
                continue                 # not the last: indices would shift
            idx = str(len(cont.children) - 1)
            rows = sc.rows(cont)
            mine = [r for r in rows if any(
                str(x).partition(".")[0] == idx for x in r.get("refs", ()))]
            if any(r.get("kind") != "fix" for r in mine):
                continue                 # something holds on to it
            keep = [r for r in rows if r not in mine]
            if keep:
                cont.params[sc.KEY] = keep
            else:
                cont.params.pop(sc.KEY, None)
            model.remove_node(node)

    def _make_reference(self, model, cont, kind, pts):
        if kind == "point":
            x, y = pts[0]
            node = model.add_node("circle", dict(x=x, y=y, radius=0.25),
                                  parent=cont, name="Reference point")
            model.set_modifier(node, "%")
            sc.add(model, cont, "fix", [sc.ref_of(cont, node, "c")])
            return node, "c", "point"
        (ax, ay), (bx, by) = pts
        if math.hypot(bx - ax, by - ay) < 1e-6:     # seen end on: a point
            return self._make_reference(model, cont, "point", [(ax, ay)])
        node = model.add_node("line", dict(x1=ax, y1=ay, x2=bx, y2=by,
                                           width=0.2), parent=cont,
                              name="Reference edge")
        model.set_modifier(node, "%")
        for end in ("p1", "p2"):
            sc.add(model, cont, "fix", [sc.ref_of(cont, node, end)])
        return node, "l", "line"

    def _copy_in(self, pick, cont, whole=False):
        """*pick*, of another sketch, as a reference in *cont*; a circle
        is its centre, or with *whole* the circle itself. One already
        copied in is used again."""
        wanted = [pick[0].name, pick[1]]
        for n in cont.children:
            if n.params.get("ref_source") == wanted:
                return n, *sc_entity(n, pick[2])
        # where the shape IS — its own sketch plane, the first of the
        # levels it shows at (the far end of its extrude came last and
        # won: a corner 20 mm away was offered as 29.96, then jumped)
        geo = {}
        for n, e, _k, g in self.entities():
            geo.setdefault((id(n), e), g)
        g = geo.get((id(pick[0]), pick[1]))
        if g is None:
            return None
        tag = dict(ref_source=[pick[0].name, pick[1]])
        if pick[2] == "point":
            return self._add_reference(cont, "point",
                                       [self._in_sketch(cont, g)], tag)
        if pick[2] == "line":
            return self._add_reference(cont, "line",
                                       [self._in_sketch(cont, p) for p in g],
                                       tag)
        n = len(g) - 1                    # a circle: its centre
        c = [sum(p[i] for p in g[:n]) / n for i in range(3)]
        if whole:
            return self._add_circle(cont, self._in_sketch(cont, c), pick)
        return self._add_reference(
            cont, "point", [self._in_sketch(cont, c)],
            dict(ref_source=[pick[0].name, "c"]))

    def _add_circle(self, cont, centre, pick):
        """A fixed construction copy of another sketch's circle. Its
        radius is written as text, an expression: the solver takes that
        as given, so no dimension shows on a reference."""
        model = self.window.model
        radius = sc._circle(pick[0], pick[1], {})[1]
        node = model.add_node(
            "circle", dict(x=centre[0], y=centre[1], radius=str(radius)),
            parent=cont, name="Reference circle")
        model.set_modifier(node, "%")
        sc.add(model, cont, "fix", [sc.ref_of(cont, node, "c")])
        node.params["ref_source"] = [pick[0].name, pick[1]]
        return node, "o", "circle"

    def _home(self, picks):
        """The sketch a relation between *picks* belongs to: the one
        being worked on if it has a pick, else the latest in the tree: the
        newer sketch is the one that hangs on the older."""
        working = self._working_on()
        if any(p[0].parent is working for p in picks):
            return working
        order = {id(n): i for i, n in
                 enumerate(self.window.model.root.walk())}
        return max((p[0].parent for p in picks),
                   key=lambda c: order.get(id(c), -1))

    def _bring_in(self, picks):
        """(picks all in one sketch, the reference nodes made for it)."""
        home = self._home(picks)
        before = set(map(id, home.children))
        out = []
        for p in picks:
            q = p if p[0].parent is home else self._copy_in(p, home, True)
            if q is None:
                raise ValueError("That shape cannot be brought into the "
                                 "sketch.")
            out.append(q)
        return out, [n for n in home.children if id(n) not in before]

    def _discard(self, made):
        for node in reversed(made):
            self.window.model.remove_node(node)

    def model_edge(self, x, y):
        """The model's corner or edge under the screen point, anywhere on
        the part: ("point", p) or ("line", (a, b)) in world, or None."""
        view = self.view
        try:
            desc, _key = view._pick_at(x, y)
        except Exception:
            return None
        if not desc or desc.get("kind") != "edge" or not desc.get("seg"):
            return None
        a, b = desc["seg"]
        project = self._project()
        for p in (a, b):
            q = project(p)
            if q is not None and math.hypot(q[0] - x, q[1] - y) <= PICK_PX:
                return "point", tuple(p)
        return "line", (tuple(a), tuple(b))

    def model_face(self, x, y):
        """The flat face of the part under the screen point, away from
        its edges: {pos, dir, tris} in world, or None (face_dim)."""
        try:
            desc, _key = self.view._pick_at(x, y)
        except Exception:
            return None
        if not desc or desc.get("kind") != "face" or not desc.get("dir"):
            return None
        return dict(pos=list(desc["pos"]), dir=list(desc["dir"]),
                    tris=list(desc.get("tris") or []))

    def _face_pick(self, x, y, parent):
        """A click on a face for Smart Dimension: the sketch line that
        made it, else a reference line in *parent*'s sketch. Returns
        (pick or None, handled) — handled when the click is used up."""
        from . import face_dim
        face = self.model_face(x, y)
        if face is None:
            return None, False
        hit = face_dim.sketch_line(self, face)
        if hit is not None:
            return hit, False
        if parent is None:
            if getattr(self, "face_first", None) is not None:
                self.face_first = None
                self._refuse("Neither face was made by a sketch, so no "
                             "dimension can drive them — use Measure for "
                             "the distance.")
                return None, True
            self.face_first = face           # waits for the sketch's shape
            self.view.update()
            self._say("Smart Dimension (3D): now click the shape or the "
                      "other face to dimension from this face.")
            return None, True
        hit = face_dim.reference(self, parent, face)
        if hit is None:
            self._refuse("That face lies flat to the sketch: its distance "
                         "is the extrude's depth, not a sketch dimension.")
            return None, True
        return hit, False

    def pick_at(self, x, y):
        """The entity under the screen point (x, y), or None."""
        if self.kind == "delete":
            return None
        project = self._project()
        solid = self._occluder()
        working = self._working_on()
        current = None

        def seen(p):
            # the sketch being extruded lies under its own boss: offered
            return current is working or solid(p)
        allowed = self._allowed()
        best = None
        for node, name, kind, g in self.entities():
            current = node.parent
            if kind not in allowed:
                continue
            if kind == "point":
                if name == "m" and self.kind != "dimension":
                    continue
                q = project(g)
                if q is None or not seen(g):
                    continue
                d = math.hypot(q[0] - x, q[1] - y)
                # Horizontal / Vertical mean the line, unless a point
                # is really aimed at (a short line was all ends)
                near = LINE_FIRST_PX if self.kind in sc.TWO_POINT and \
                    not self.picks else POINT_PX
                rank = 0 if d <= near else 2
            elif kind == "line":
                qa, qb = project(g[0]), project(g[1])
                if qa is None or qb is None:
                    continue
                d, t = _seg_px((x, y), qa, qb)
                mid = tuple(g[0][i] + (g[1][i] - g[0][i]) * t
                            for i in range(3))
                if not seen(mid):
                    continue
                rank = 1
            else:
                pts = [project(p) for p in g]
                d, at = 1e9, None
                for i, (qa, qb) in enumerate(zip(pts, pts[1:])):
                    if qa is None or qb is None:
                        continue
                    dd, _t = _seg_px((x, y), qa, qb)
                    if dd < d:
                        d, at = dd, g[i]
                if at is None or not seen(at):
                    continue
                rank = 1
            if d > PICK_PX:
                continue
            key = (rank, d)
            if best is None or key < best[0]:
                best = (key, (node, name, kind))
        return best[1] if best else None

    # --------------------------------------------------------- events
    def mouse_press(self, event):
        from PyQt5.QtCore import Qt
        if event.button() == Qt.RightButton:
            idle = not (self.picks or getattr(self, "_placing", None) or
                        getattr(self, "model_first", None) or
                        getattr(self, "face_first", None))
            self.drop()
            if idle and (getattr(self.window, "_drag_paused", None)
                         is not None or
                         getattr(self.window, "_sketch3d_tool", None)
                         is not None):
                # nothing picked: the tool is done — back to the extrude's
                # arrow or the sketch it was called from (the user was
                # left in Smart Dimension with the arrow gone)
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(0, lambda: end(self.window))
            return True
        if self.kind == "delete" and event.button() == Qt.LeftButton:
            from PyQt5.QtCore import QPoint
            from . import view3d_menu
            pos = event.pos()
            if view3d_menu.relation_at(self.window, pos) or \
                    view3d_menu.dimension_at(self.window, pos):
                # (before the value's own click, which would edit it)
                self.delete_at(pos.x(), pos.y())
                return True
        self._down = event.pos()
        return False                # the view may still orbit on a drag

    def mouse_move(self, event):
        x, y = event.pos().x(), event.pos().y()
        self._cursor = (x, y)
        if getattr(self, "_placing", None) is not None:
            self.view.update()           # the number follows the cursor
            return False
        hit = self.pick_at(x, y)
        near = None
        edge = None
        if hit is None and self.kind == "dimension":
            parent = self.picks[0][0].parent if self.picks \
                else self._working_on()
            near = (self.model_near(x, y, parent), parent)
            if not near[0]:
                edge = self.model_edge(x, y)
        face = None
        if hit is None and edge is None and self.kind == "dimension" \
                and not (near and near[0]):
            face = self.model_face(x, y)     # a face: dimensioned to
        if edge != getattr(self, "edge_hover", None) or \
                (face or {}).get("pos") != \
                (getattr(self, "face_hover", None) or {}).get("pos"):
            self.edge_hover = edge
            self.face_hover = face
            self.view.update()
        if hit != self.hover or near != getattr(self, "model_hover", None):
            self.hover = hit
            self.model_hover = near
            self.view.update()
        return False

    def mouse_release(self, event):
        from PyQt5.QtCore import Qt
        down, self._down = self._down, None
        if down is None or event.button() != Qt.LeftButton or \
                (event.pos() - down).manhattanLength() > CLICK_PX:
            return False
        self._seen = None
        # Shift+click on a circle: its near / far side (min / max)
        self._shift = bool(event.modifiers() & Qt.ShiftModifier)
        try:
            self.click(event.pos().x(), event.pos().y())
        finally:
            self._shift = False
        return True

    def wheel(self, event):
        return False

    def key_press(self, event):
        from PyQt5.QtCore import Qt
        if event.key() == Qt.Key_Escape and self.picks:
            self.drop()
            return True
        return False

    def drop(self):
        self._drop_fresh()
        self.picks = []
        self.model_first = None
        self.face_first = None
        self._placing = None
        self._rim_clicks = {}
        self.view.update()
        self._say(self._prompt())

    def exit(self):
        tool = getattr(self.window, "_sketch3d_tool", None)
        from PyQt5.QtCore import QTimer
        if tool is not None:      # back to the 3D sketch it came from
            QTimer.singleShot(0, tool.resume)
        elif getattr(self.window, "_drag_paused", None) is not None:
            from . import drag_feature      # or to the Extrude window
            QTimer.singleShot(0, lambda: drag_feature.resume_paused(
                self.window))
        self.picks = []
        self.hover = None

    # ---------------------------------------------------------- logic
    def _say(self, text):
        self.window.statusBar().showMessage(text, 8000)

    def _refuse(self, text):
        """Said where the user is looking: across the 3D view, and why
        (the status bar alone goes unseen)."""
        self._say(text)
        self.view.flash(text, 8000)

    def _prompt(self):
        from . import sketch_constrain_ui as ui
        if self.kind == "delete":
            return ("Delete constraint (3D): click a relation mark or a "
                    "dimension's value.")
        if self.kind == "dimension":
            return ("Smart Dimension (3D): click a line, a circle or a "
                    "point." if not self.picks else
                    "Smart Dimension (3D): click a second one — or "
                    "anywhere empty for this one's size.")
        return ui.prompt(self.kind, len(self.picks)) + " (3D)"

    def delete_at(self, x, y):
        """Delete tool: the relation mark or dimension value clicked."""
        from PyQt5.QtCore import QPoint
        from . import view3d_menu
        pos = QPoint(int(x), int(y))
        hit = view3d_menu.relation_at(self.window, pos) or \
            view3d_menu.dimension_at(self.window, pos)
        if hit is None:
            self._say(self._prompt())
            return None
        view3d_menu.delete_dimension(self.window, hit[1], hit[2])
        self._say("Constraint deleted.")
        return hit[1]

    def click(self, x, y):
        if self.kind == "delete":
            return self.delete_at(x, y)
        hit = self.pick_at(x, y)
        if self.kind == "dimension":
            return self._dimension_click(hit, x, y)
        if hit is None:
            # the origin, a corner or an edge of the part, as a Smart
            # Dimension takes them (a Midpoint on the origin found
            # nothing to click)
            parent = self.picks[0][0].parent if self.picks \
                else self._working_on()
            try:
                near = self.model_near(x, y, parent) \
                    if parent is not None else None
                if near is not None and near[0] in self._allowed():
                    hit = self.model_pick(x, y, parent)
            except (ValueError, KeyError):
                hit = None
        if hit is None:
            self._say(self._prompt())
            return None
        if self.picks and hit[:2] == self.picks[0][:2]:
            self._say("That is the first pick — click something else.")
            return None
        self.picks.append(hit)
        wants = sc.KINDS[self.kind][1]
        done = len(self.picks) == len(wants)
        if self.kind in sc.TWO_POINT:     # a line, or two points
            done = hit[2] == "line" or len(self.picks) == 2
        if not done:
            self.view.update()
            self._say(self._prompt())
            return None
        return self._finish()

    def _finish(self):
        from . import sketch_constrain_ui as ui
        picks, self.picks = list(self.picks), []
        kind = self.kind
        try:
            picks, made = self._bring_in(picks)
        except (ValueError, KeyError) as exc:
            self._refuse("Relation refused: %s" % exc)
            return None
        if kind == "coincident" and any(k != "point" for _n, _e, k in picks):
            kind = "point_on"
        if kind == "point_on" and picks[0][2] != "point":
            picks.reverse()
        if kind == "tangent" and picks[1][2] == "line":
            picks.reverse()
        container = picks[0][0].parent
        refs = [sc.ref_of(container, n, name) for n, name, _k in picks]
        value = None
        if sc.KINDS[kind][2]:
            text = ui._ask_value(self.window.view2d.scene(), kind,
                                 sc.measure(container, kind, refs))
            if text is None:
                self._discard(made)
                return None
            value = ui._value(text)
        try:
            report = sc.add(self.window.model, container, kind, refs, value)
        except ValueError as exc:
            self._discard(made)
            self._refuse("Relation refused: %s" % exc)
            return None
        self.view.update()
        self._say("%s added — %s" % (sc.KINDS[kind][0],
                                     sc.status_text(report)))
        return report

    def _place_xy(self, cont, x, y):
        """The sketch (x, y) of *cont* under the screen point, or None."""
        import numpy as np
        from . import model_refs, refgeom
        from .sculpt_ui import screen_ray
        try:
            m = model_refs.sketch_matrix(self.window, cont)
            origin, d = screen_ray(self.view, x, y)
            o = (m @ np.array([0.0, 0.0, 0.0, 1.0]))[:3].tolist()
            n = m[:3, 2].tolist()
            p = refgeom.ray_plane(list(origin), list(d), o, n)
            return None if p is None else self._in_sketch(cont, p)
        except Exception:
            return None

    def _dimension_click(self, hit, x=None, y=None):
        from . import dim_more, sketch_constrain_ui as ui
        placing = getattr(self, "_placing", None)
        if placing is not None:
            # the click that places the number: horizontal / vertical /
            # straight, an arc's length, a diameter across a centerline
            self._placing = None
            try:
                self.view.flash("", 1)
            except Exception:
                pass
            cont = placing[1][0][0].parent
            at = self._place_xy(cont, x, y) if x is not None else None
            return self._make_dimension(dim_more.refine(placing, at))
        if hit is not None and hit[2] == "circle" and x is not None and \
                getattr(self, "_shift", False):
            if not hasattr(self, "_rim_clicks"):
                self._rim_clicks = {}
            at = self._place_xy(hit[0].parent, x, y)
            if at is not None:
                self._rim_clicks[id(hit[0])] = at
        parent = None
        if hit is not None and hit[2] != "point" and x is not None:
            # a CORNER of the part right under the cursor beats a line or
            # circle that merely passes over it on screen (a boss's far
            # rim drawn across the block's corner took the click)
            home = self.picks[0][0].parent if self.picks \
                else self._working_on()
            try:
                corner = self._corner_near(x, y, home) \
                    if home is not None else None
                if corner is not None and \
                        not self._passes_through(hit, corner):
                    hit = None
            except (ValueError, KeyError):
                pass
        if hit is None and x is not None:
            # the model's corner, centre or edge (SolidWorks)
            parent = self.picks[0][0].parent if self.picks \
                else self._working_on()
            try:
                hit = self.model_pick(x, y, parent)
                edge = self.model_edge(x, y) if hit is None and \
                    parent is not None else None
                if edge is not None:     # any edge of the part
                    kind, where = edge
                    pts = [where] if kind == "point" else list(where)
                    hit = self._add_reference(
                        parent, kind,
                        [self._in_sketch(parent, p) for p in pts],
                        dict(ref_world=[list(p) for p in pts]))
            except (ValueError, KeyError):
                hit = None
            if hit is None and not (not self.picks and parent is None and
                                    self.model_edge(x, y) is not None):
                # a FACE of the part (SolidWorks: face to face)
                try:
                    hit, used = self._face_pick(x, y, parent)
                except (ValueError, KeyError):
                    hit, used = None, False
                if used:
                    return None
        face = getattr(self, "face_first", None)
        if face is not None and hit is not None and not self.picks:
            # the face clicked first comes into this shape's sketch
            from . import face_dim
            self.face_first = None
            ref = face_dim.reference(self, hit[0].parent, face)
            if ref is None:
                self._refuse("That face lies flat to the sketch: its "
                             "distance is the extrude's depth.")
                return None
            self.picks.append(ref)
        waiting = getattr(self, "model_first", None)
        if waiting is not None and hit is not None and not self.picks:
            # the model's line clicked first: it comes into this sketch
            self.model_first = None
            kind, pts = waiting
            parent = hit[0].parent
            self.picks.append(self._add_reference(
                parent, kind, [self._in_sketch(parent, p) for p in pts],
                dict(ref_world=[list(p) for p in pts])))
        if not self.picks:
            if hit is None and x is not None and parent is None:
                # no sketch yet: the model's edge waits for the shape
                edge = self.model_edge(x, y)
                if edge is not None:
                    kind, where = edge
                    self.model_first = (kind, [where] if kind == "point"
                                        else list(where))
                    self.view.update()
                    self._say("Smart Dimension (3D): now click the shape in "
                              "the sketch to dimension from this edge.")
                    return None
            if hit is None:
                self._say(self._prompt())
                return None
            self.picks.append(hit)
            self.view.update()
            self._say(self._prompt())
            return None
        first = self.picks[0]
        if hit is None and first[1] == "m":
            first = (first[0], "l", "line")
        if hit is None:
            hit = first if first[2] in ("line", "circle") else None
        if hit is None:
            self._say("Smart Dimension (3D): click the second point or "
                      "line.")
            return None
        if hit[0].parent is not first[0].parent:
            # another sketch's point or line: copied, fixed, into the
            # sketch being worked on, as the 2D view does (2026-11-01, the
            # user: nothing happened)
            home = self._home([first, hit])
            if hit[0].parent is not home:
                hit = self._copy_in(hit, home)
            if first[0].parent is not home:
                first = self._copy_in(first, home)
            if hit is None or first is None:
                self.picks = []
                self._refuse("Those two cannot be dimensioned together.")
                return None
        self.picks = []
        made = ui._smart(first, hit)
        self.view.update()
        if made is None:
            self._refuse("Those two cannot be dimensioned together.")
            return None
        if dim_more.needs_place(made) and x is not None:
            self._placing = made
            self._cursor = (x, y)
            text = "Smart Dimension: " + dim_more.place_prompt(made)
            self._say(text)
            try:                         # said ON the view too
                self.view.flash(text, 15000)
            except Exception:
                pass
            return None
        return self._make_dimension((made[0], made[1], {}))

    def _make_dimension(self, made):
        """Ask the value of (kind, chosen, extra) and add it."""
        from . import dim_more, sketch_constrain_ui as ui
        kind, chosen, extra = made
        clicks, self._rim_clicks = getattr(self, "_rim_clicks", {}), {}
        if kind in ("distance", "point_line") and clicks:
            rim = dim_more.rim_for(chosen, clicks)
            if rim:
                extra = dict(extra, rim=rim)
        container = chosen[0][0].parent
        refs = [sc.ref_of(container, n, name) for n, name, _k in chosen]
        text = ui._ask_value(self.window.view2d.scene(), kind,
                             sc.measure(container, kind, refs, extra))
        if text is None:
            self._drop_fresh()
            return None
        model = self.window.model
        same = [i for i, r in enumerate(sc.rows(container))
                if r["kind"] == kind and sorted(r["refs"]) == sorted(refs)
                and bool(r.get("double")) == bool(extra.get("double"))
                and (r.get("rim") or {}) == (extra.get("rim") or {})]
        driven = False
        try:
            if same:
                report = sc.set_value(model, container, same[0],
                                      ui._value(text))
            else:
                report, _scaled, driven = dim_more.add(
                    model, container, kind, refs, ui._value(text), extra)
        except ValueError as exc:
            self._drop_fresh()
            self._refuse("Dimension refused: %s" % exc)
            return None
        self._fresh = []                 # used: they stay
        if driven and all(dim_fixed(container, n) for n, _e, _k in chosen):
            self._say("%s — both are edges of the PART, not of this "
                      "sketch, so nothing here can move: the dimension "
                      "only measures (in brackets). To drive that "
                      "distance, dimension the sketch of the feature the "
                      "edge belongs to." % sc.KINDS[kind][0])
        elif driven:
            self._say("%s — the sketch is already fully defined there, so "
                      "it was added DRIVEN: it shows the size in brackets "
                      "and follows the sketch." % sc.KINDS[kind][0])
        else:
            self._say("%s %s — %s" % (sc.KINDS[kind][0], text,
                                      sc.status_text(report)))
        self.view.update()
        return report

    # ---------------------------------------------------------- paint
    def _paint_placing(self, painter, project):
        """The dimension as it would be made where the cursor is now:
        its line between what it measures and its value at the cursor."""
        import numpy as np
        from PyQt5.QtCore import QPointF, QRectF, Qt
        from PyQt5.QtGui import QColor, QPen
        from . import dim_more, model_refs
        placing = self._placing
        cursor = getattr(self, "_cursor", None)
        if placing is None or cursor is None:
            return
        cont = placing[1][0][0].parent
        at = self._place_xy(cont, *cursor)
        try:
            kind, chosen, extra = dim_more.refine(placing, at)
            refs = [sc.ref_of(cont, n, name) for n, name, _k in chosen]
            value = sc.measure(cont, kind, refs, extra)
            m = model_refs.sketch_matrix(self.window, cont)
        except Exception:
            return
        ends = []
        try:
            if kind == "arc_length":
                ends = list(sc._line(chosen[0][0], "l", {}))
            elif kind == "point_line":
                p = sc._point(chosen[0][0], chosen[0][1], {})
                a, b = sc._line(chosen[1][0], chosen[1][1], {})
                dx, dy = b[0] - a[0], b[1] - a[1]
                t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / \
                    (dx * dx + dy * dy or 1.0)
                foot = (a[0] + dx * t, a[1] + dy * t)
                ends = [p, foot]
                if extra.get("double"):  # across the centerline
                    ends = [p, (2 * foot[0] - p[0], 2 * foot[1] - p[1])]
            else:
                pa = sc._point(chosen[0][0], chosen[0][1], {})
                pb = sc._point(chosen[1][0], chosen[1][1], {})
                if kind == "hdistance":
                    y = at[1] if at else pa[1]
                    ends = [(pa[0], y), (pb[0], y)]
                elif kind == "vdistance":
                    x = at[0] if at else pa[0]
                    ends = [(x, pa[1]), (x, pb[1])]
                else:
                    ends = [pa, pb]
        except Exception:
            ends = []
        qs = [project((m @ np.array([e[0], e[1], 0.0, 1.0]))[:3].tolist())
              for e in ends]
        ink = QColor(33, 118, 199)
        painter.save()
        painter.setRenderHint(painter.Antialiasing, True)
        if len(qs) == 2 and all(qs):
            painter.setPen(QPen(ink, 1.6, Qt.DashLine))
            painter.drawLine(QPointF(qs[0][0], qs[0][1]),
                             QPointF(qs[1][0], qs[1][1]))
        name = {"hdistance": "horizontal", "vdistance": "vertical",
                "distance": "straight", "arc_length": "arc length",
                "point_line": "diameter" if extra.get("double")
                else "distance"}.get(kind, kind)
        from . import units
        label = "%s%s  ·  %s — click to place" % (
            "Ø" if extra.get("double") else "", units.number(value), name)
        fm = painter.fontMetrics()
        box = QRectF(cursor[0] + 14, cursor[1] - fm.height() - 8,
                     fm.horizontalAdvance(label) + 14, fm.height() + 8)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(33, 118, 199, 225))
        painter.drawRoundedRect(box, 6, 6)
        painter.setPen(QColor("white"))
        painter.drawText(box, int(Qt.AlignCenter), label)
        painter.restore()

    def paint(self, painter, project):
        from PyQt5.QtCore import QPointF
        from PyQt5.QtGui import QColor, QPen
        if getattr(self, "_placing", None) is not None:
            try:
                self._paint_placing(painter, project)
            except Exception:            # never break the paint
                import traceback
                traceback.print_exc()
        geo = {(id(n), e): g for n, e, _k, g in self.entities()}
        near = getattr(self, "model_hover", None)
        if near and near[0]:
            from . import face_sketch
            group = face_sketch.group_of(near[1])
            kind, where = near[0]
            pts = [project(face_sketch.to_world(group, p[0], p[1])) for p in
                   ([where] if kind == "point" else where)]
            if all(pts):
                painter.setPen(QPen(QColor(240, 140, 30), 3))
                if kind == "point":
                    painter.drawEllipse(QPointF(pts[0][0], pts[0][1]), 5, 5)
                else:
                    painter.drawLine(QPointF(pts[0][0], pts[0][1]),
                                     QPointF(pts[1][0], pts[1][1]))

        from PyQt5.QtGui import QPolygonF
        for face, colour in (
                (getattr(self, "face_hover", None), QColor(0, 190, 255, 70)),
                (getattr(self, "face_first", None), QColor(230, 120, 20, 90))):
            if not face:
                continue
            painter.setPen(QPen(colour, 1))
            painter.setBrush(colour)
            for t in face.get("tris") or ():
                qs = [project(p) for p in t[:3]]
                if all(qs):
                    painter.drawPolygon(QPolygonF(
                        [QPointF(q[0], q[1]) for q in qs]))
            painter.setBrush(QColor(0, 0, 0, 0))
        for where, colour in (
                (getattr(self, "edge_hover", None), QColor(0, 190, 255, 235)),
                (getattr(self, "model_first", None), QColor(230, 120, 20))):
            if not where:
                continue
            kind, got = where
            pts = [project(p) for p in
                   ([got] if kind == "point" and getattr(got[0], "__len__",
                                                         None) is None
                    else got)]
            if not all(pts):
                continue
            painter.setPen(QPen(colour, 4))
            if len(pts) == 1:
                painter.drawEllipse(QPointF(pts[0][0], pts[0][1]), 5, 5)
            else:
                painter.drawLine(QPointF(pts[0][0], pts[0][1]),
                                 QPointF(pts[1][0], pts[1][1]))

        def draw(item, colour, width):
            g = geo.get((id(item[0]), item[1]))
            if g is None:
                return
            pen = QPen(colour, width)
            pen.setCosmetic(True)
            painter.setPen(pen)
            if item[2] == "point":
                q = project(g)
                if q is not None:
                    painter.setBrush(colour)
                    painter.drawEllipse(QPointF(q[0], q[1]), 5.0, 5.0)
                return
            pts = list(g) if item[2] == "circle" else [g[0], g[1]]
            qs = [project(p) for p in pts]
            for a, b in zip(qs, qs[1:]):
                if a is not None and b is not None:
                    painter.drawLine(QPointF(a[0], a[1]),
                                     QPointF(b[0], b[1]))
        painter.save()
        painter.setRenderHint(painter.Antialiasing, True)
        for p in self.picks:
            draw(p, QColor(230, 120, 20), 4.0)
        if self.hover is not None:
            draw(self.hover, QColor(0, 190, 255, 235), 6.0)
        painter.restore()


def start(window, tool):
    """Run constraint *tool* in the 3D view. True when it started."""
    from . import sketch_constrain_ui as ui
    view = window.view3d
    end(window)
    old = getattr(view, "edit_tool", None)
    if old is not None:
        for name in ("exit", "close", "_end", "stop", "cancel"):
            fn = getattr(old, name, None)
            if callable(fn):
                try:
                    fn()
                except Exception:         # pragma: no cover
                    pass
                break
    t = Constrain3D(window, tool)
    view.edit_tool = t
    view.setMouseTracking(True)
    view.update()
    t._say(t._prompt())
    return True


def end(window):
    """The 3D constraint tool, if running, stops (another tool chosen)."""
    view = window.view3d
    if isinstance(getattr(view, "edit_tool", None), Constrain3D):
        view.edit_tool.exit()
        view.edit_tool = None
        view.update()
