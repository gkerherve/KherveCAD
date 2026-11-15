"""The SHEET METAL ribbon's Hole and Slot (2026-11-15): a ToolPanel like
Jog's. Hole: each click on the sheet puts a hole there (0.5 mm grid), the
diameter row sets its size, the X / Y rows move the last one. Slot: two
clicks are the centre line's ends, the width row sets the width. The cuts
are in the flat plate's own coordinates, so they follow their panel
through a jog (sheet_jog). OK keeps what was made, Cancel takes it back.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import language, sheet_metal_ops as ops
from .sheet_jog_ui import _local, _say

_OPEN = {}


class CutTool:
    def __init__(self, win, body, kind):
        self.win, self.body, self.kind = win, body, kind
        self.model = win.model
        self.made = []                      # indices of what this tool added
        self.p = None                       # a slot's first point
        self.size = 8.0 if kind == "hole" else 6.0
        self.panel = None
        self.matrix = None
        self.closed = False

    def open(self):
        from .tool_panel import ToolPanel
        title = language.tr("Hole" if self.kind == "hole" else "Slot")
        panel = ToolPanel(self.win.view3d, title, on_ok=self.ok,
                          on_cancel=self.cancel)
        self.panel = panel
        panel.hint(language.tr(
            "Click on the sheet to put a hole there." if self.kind == "hole"
            else "Click the two ends of the slot's centre line."))
        panel.section(language.tr("Selections"))
        panel.selection("where", language.tr(
            "Hole position" if self.kind == "hole" else "Slot centre line"),
            language.tr("Click on the sheet"))
        panel.set_active("where")
        panel.section(language.tr("Size"))
        panel.number("size", language.tr(
            "Diameter" if self.kind == "hole" else "Width"), self.size,
            self.set_size, minimum=0.1)
        panel.finish()
        panel.set_ok_enabled(False)
        panel.open()
        _OPEN[id(self.win)] = self
        self.arm()

    def set_size(self, value):
        self.size = float(value)
        if not self.made:
            return
        key = "holes" if self.kind == "hole" else "slots"
        rows = ops._rows(self.body, key)
        i = self.made[-1]
        rows[i][2 if self.kind == "hole" else 4] = self.size
        try:
            ops._set(self.model, self.body, key, rows)
        except ValueError as exc:
            _say(self.win, str(exc))

    def arm(self):
        from . import bake, mesh
        win, view = self.win, self.win.view3d
        root = win._render_scope()[0]
        iso = root if root is not win.model.root else None
        env = bake._codegen_env(self.body)
        with win._isolated_frame(iso):
            tris = mesh.selected_world_tris(root, {self.body.id},
                                            fn=win.model.effective_fn())
            self.matrix = mesh.ancestor_matrix(self.body, env, stop=iso)
        if not tris or not hasattr(view, "start_pick"):
            return
        view.start_pick(self.picked, groups=[(self.body, tris)], done=False,
                        banner=language.tr("Click on the sheet"),
                        labeler=lambda desc, node: "")

    def picked(self, desc, _node=None):
        if self.closed or desc is None:
            return
        q = _local(self.matrix, desc.get("point") or desc.get("pos"))
        q = (round(q[0] * 2) / 2, round(q[1] * 2) / 2)
        try:
            if self.kind == "hole":
                ops.add_hole(self.model, self.body, q[0], q[1], self.size)
                self.made.append(len(ops._rows(self.body, "holes")) - 1)
                self.panel.boxes["where"].set_text(
                    "({:.1f}, {:.1f})".format(*q))
            elif self.p is None:
                self.p = q
                self.panel.boxes["where"].set_text(
                    "({:.1f}, {:.1f}) → …".format(*q))
            else:
                ops.add_slot(self.model, self.body, self.p, q, self.size)
                self.made.append(len(ops._rows(self.body, "slots")) - 1)
                self.panel.boxes["where"].set_text(
                    "({:.1f}, {:.1f}) → ({:.1f}, {:.1f})".format(*self.p, *q))
                self.p = None
        except ValueError as exc:
            _say(self.win, str(exc))
            self.p = None
        self.panel.set_ok_enabled(bool(self.made))
        self.arm()

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
        if not self.made:
            return
        self.finish()
        from . import sheet_metal_ui as ui
        ui.report(self.win, self.body)

    def cancel(self, *_a):
        key = "holes" if self.kind == "hole" else "slots"
        for i in sorted(self.made, reverse=True):
            try:
                ops.remove(self.model, self.body, key, i)
            except ValueError:
                pass
        self.finish()


def start(win, kind):
    from . import sheet_metal_ui as ui
    body = ui._body(win)
    if body is None:
        return None
    old = _OPEN.get(id(win))
    if old is not None:
        old.cancel()
    tool = CutTool(win, body, kind)
    tool.open()
    return tool
