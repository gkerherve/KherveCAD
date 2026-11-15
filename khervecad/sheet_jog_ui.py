"""The SHEET METAL ribbon's Jog (2026-11-15, Exercise "Jog Feature in
SolidWorks Sheet Metal"): a ToolPanel like Extruded Boss's. Two clicks on
the sheet make the bend line, a click on the side that stays put is the
Fixed face; offset, dimension position, jog position, angle, direction
and radius are rows of the window and the jog follows each change at
once. OK keeps it, Cancel takes it back.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from . import language, sheet_jog, sheet_metal_ops as ops

SNAP_DEG = 3.0            # a nearly straight line is made straight

DIM_OPTIONS = [(0, "Outside"), (1, "Inside offset"), (2, "Total")]
POS_OPTIONS = [(0, "Bend centre line"), (1, "Material inside"),
               (2, "Material outside"), (3, "Bend outside")]
DIR_OPTIONS = [(1, "Up"), (-1, "Down")]

#: the window of the moment (one per main window)
_OPEN = {}


def _inverse(m):
    import numpy as np
    return np.linalg.inv(np.array(m, dtype=float))


def _local(matrix, point):
    """A world point -> the body's own frame."""
    if matrix is None:
        return tuple(point)
    import numpy as np
    v = _inverse(matrix) @ np.array([point[0], point[1], point[2], 1.0])
    return (float(v[0]), float(v[1]), float(v[2]))


def straight(p1, p2):
    """The line p1-p2 made exactly vertical or horizontal when it is
    within SNAP_DEG of it (SolidWorks' inferred H / V)."""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    ang = math.degrees(math.atan2(abs(dy), abs(dx)))
    if ang < SNAP_DEG:
        return (p1[0], p1[1]), (p2[0], p1[1])
    if ang > 90 - SNAP_DEG:
        return (p1[0], p1[1]), (p1[0], p2[1])
    return (p1[0], p1[1]), (p2[0], p2[1])


def side_of(p1, p2, q):
    """1 when q lies left of the line p1 -> p2, else -1."""
    cross = (p2[0] - p1[0]) * (q[1] - p1[1]) - (p2[1] - p1[1]) * (q[0] - p1[0])
    return 1 if cross >= 0 else -1


def _extent(body):
    """Corners of the base outline, for the line's end points."""
    pts = [p for p in body.params.get("outline") or []
           if not isinstance(p[0], str) and not isinstance(p[1], str)]
    xs = [float(p[0]) for p in pts] or [0.0, 100.0]
    ys = [float(p[1]) for p in pts] or [0.0, 60.0]
    return min(xs), max(xs), min(ys), max(ys)


def _say(win, text):
    from . import sheet_metal_ui as ui
    ui._say(win, text)


class JogTool:
    """The state and the clicks of one Jog."""

    def __init__(self, win, body):
        self.win, self.body = win, body
        self.model = win.model
        self.index = None                   # the row made so far
        self.p = [None, None]               # the line's two points
        self.side = None
        self.opts = dict(offset=20.0, angle=60.0, radius=0.0, dim=0, pos=3,
                         direction=1)
        self.default_radius = True
        self.stage = "line"                 # line, then face, then done
        self.panel = None
        self.matrix = None
        self.closed = False

    # ------------------------------------------------------ the window
    def open(self):
        from .tool_panel import ToolPanel
        win = self.win
        panel = ToolPanel(win.view3d, language.tr("Jog"),
                          on_ok=self.ok, on_cancel=self.cancel)
        self.panel = panel
        panel.hint(language.tr(
            "Click two points on the sheet for the bend line, then click "
            "the side of the sheet that stays fixed."))
        panel.section(language.tr("Selections"))
        panel.selection("line", language.tr("Bend line"),
                        language.tr("Click two points on the sheet"),
                        on_activate=lambda k: self.activate("line"))
        panel.selection("face", language.tr("Fixed face"),
                        language.tr("Click the side that stays"),
                        on_activate=lambda k: self.activate("face"))
        for key, cap in (("x1", "Line from X"), ("y1", "Line from Y"),
                         ("x2", "Line to X"), ("y2", "Line to Y")):
            panel.number(key, language.tr(cap), 0.0,
                         lambda v, k=key: self.set_point(k, v),
                         minimum=-1e5, maximum=1e5, step=0.5)
        panel.check("default_radius", language.tr("Use default radius"),
                    True, self.set_default_radius)
        panel.number("radius", language.tr("Bend radius"), self.radius0(),
                     lambda v: self.set_opt("radius", v), minimum=0.0)
        panel.section(language.tr("Jog offset"))
        panel.number("offset", language.tr("Offset"), 20.0,
                     lambda v: self.set_opt("offset", v), minimum=0.1)
        panel.choice("dim", language.tr("Dimension position"),
                     [(v, language.tr(t)) for v, t in DIM_OPTIONS], 0,
                     lambda v: self.set_opt("dim", v))
        panel.section(language.tr("Jog position"))
        panel.choice("pos", language.tr("Jog position"),
                     [(v, language.tr(t)) for v, t in POS_OPTIONS], 3,
                     lambda v: self.set_opt("pos", v))
        panel.choice("direction", language.tr("Direction"),
                     [(v, language.tr(t)) for v, t in DIR_OPTIONS], 1,
                     lambda v: self.set_opt("direction", v))
        panel.section(language.tr("Jog angle"))
        panel.number("angle", language.tr("Angle"), 60.0,
                     lambda v: self.set_opt("angle", v), suffix=" °",
                     minimum=1.0, maximum=89.0, step=5.0)
        panel.finish()
        for key in ("x1", "y1", "x2", "y2"):
            panel.show_row(key, False)
        panel.fields["radius"].setEnabled(False)
        panel.set_ok_enabled(False)
        panel.set_active("line")
        panel.open()
        _OPEN[id(win)] = self
        self.arm()

    def radius0(self):
        from . import mesh
        return mesh.rv(self.body.params.get("radius", 2.0), ops._env(
            self.model), 2.0)

    def set_default_radius(self, on):
        self.default_radius = bool(on)
        self.panel.fields["radius"].setEnabled(not on)
        if on:
            self.panel.set_value("radius", self.radius0())
            self.opts["radius"] = 0.0
        else:
            self.opts["radius"] = self.panel.fields["radius"].value()
        self.apply()

    def set_opt(self, key, value):
        self.opts[key] = value
        self.apply()

    def activate(self, stage):
        self.stage = stage
        self.panel.set_active(stage)
        self.arm()

    # ----------------------------------------------------- the clicks
    def arm(self):
        """Wait for the next click on the sheet."""
        from . import bake, mesh
        win = self.win
        view = win.view3d
        root = win._render_scope()[0]
        iso = root if root is not win.model.root else None
        env = bake._codegen_env(self.body)
        with win._isolated_frame(iso):
            tris = mesh.selected_world_tris(root, {self.body.id}, fn=win.model
                                            .effective_fn())
            self.matrix = mesh.ancestor_matrix(self.body, env, stop=iso)
        if not tris or not hasattr(view, "start_pick"):
            return
        text = (language.tr("Click the first point of the bend line")
                if self.stage == "line" and self.p[0] is None else
                language.tr("Click the second point of the bend line")
                if self.stage == "line" else
                language.tr("Click the side that stays fixed"))
        view.start_pick(self.picked, groups=[(self.body, tris)],
                        banner=text, done=False,
                        labeler=lambda desc, node: "")

    def picked(self, desc, _node=None):
        if self.closed or desc is None:
            return
        pt = desc.get("point") or desc.get("pos")
        q = _local(self.matrix, pt)
        q = (round(q[0] * 2) / 2, round(q[1] * 2) / 2, q[2])   # 0.5 mm grid
        if self.stage == "line":
            if self.p[0] is None:
                self.p[0] = (q[0], q[1])
                self.panel.boxes["line"].set_text(
                    language.tr("({x:.1f}, {y:.1f}) → …").format(
                        x=q[0], y=q[1]))
            else:
                a, b = straight(self.p[0], (q[0], q[1]))
                if math.hypot(b[0] - a[0], b[1] - a[1]) < 1e-3:
                    self.arm()
                    return
                self.p = [a, b]
                self.stage = "face"
                self.panel.set_active("face")
                self.show_line()
        else:
            self.side = side_of(self.p[0], self.p[1], (q[0], q[1]))
            self.panel.boxes["face"].set_text(
                language.tr("Face on the {side} of the line").format(
                    side=language.tr("left") if self.side > 0
                    else language.tr("right")))
            self.panel.set_active(None)
            self.apply()
            return
        self.arm()

    def set_point(self, key, value):
        if self.p[1] is None:
            return
        i = 0 if key[1] == "1" else 1
        pt = list(self.p[i])
        pt[0 if key[0] == "x" else 1] = float(value)
        self.p[i] = tuple(pt)
        self.show_line(fields=False)
        self.apply()

    def show_line(self, fields=True):
        a, b = self.p
        if fields:
            for key, v in (("x1", a[0]), ("y1", a[1]), ("x2", b[0]),
                           ("y2", b[1])):
                self.panel.set_value(key, v)
                self.panel.show_row(key, True)
        self.panel.boxes["line"].set_text(
            "({:.1f}, {:.1f}) → ({:.1f}, {:.1f})".format(*a, *b))

    # ----------------------------------------------------- the jog
    def row(self):
        o = self.opts
        return ops.jog_row(self.p[0], self.p[1], o["offset"], o["angle"],
                           0.0 if self.default_radius else o["radius"],
                           o["dim"], o["pos"], self.side, o["direction"])

    def apply(self):
        if self.side is None or self.p[1] is None:
            return
        a, b = self.p
        if math.hypot(b[0] - a[0], b[1] - a[1]) < 1e-3:
            return
        try:
            if self.index is None:
                self.index = ops.add_jog(
                    self.model, self.body, self.p[0], self.p[1],
                    self.opts["offset"], self.opts["angle"],
                    0.0 if self.default_radius else self.opts["radius"],
                    self.opts["dim"], self.opts["pos"], self.side,
                    self.opts["direction"])
            else:
                ops.set_jog(self.model, self.body, self.index, self.row())
        except ValueError as exc:
            self.panel.set_ok_enabled(False)
            _say(self.win, str(exc))
            return
        self.panel.set_ok_enabled(True)

    def finish(self):
        self.closed = True
        try:
            self.win.view3d.cancel_pick()
        except Exception:
            pass
        _OPEN.pop(id(self.win), None)
        self.panel.hide()
        self.panel.deleteLater()

    def ok(self, *_a):
        if self.index is None:
            return
        self.finish()
        from . import sheet_metal_ui as ui
        ui.report(self.win, self.body)

    def cancel(self, *_a):
        if self.index is not None:
            try:
                ops.remove(self.model, self.body, "jogs", self.index)
            except ValueError:
                pass
        self.finish()


def jog(win):
    from . import sheet_metal_ui as ui
    body = ui._body(win)
    if body is None:
        return None
    old = _OPEN.get(id(win))
    if old is not None:
        old.cancel()
    tool = JogTool(win, body)
    tool.open()
    return tool
