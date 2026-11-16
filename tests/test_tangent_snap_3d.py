"""The 3D sketch's Line snaps TANGENT to a circle, like the 2D one
(2026-11-14, the user: "add the tangent snap to the 3D sketch too").

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import face_sketch, tangent_snap
from khervecad.mcp_tools import McpToolExecutor

from test_stacked_features import app, win, _sketch_on  # noqa


def _screen(win, tool, lx, ly):
    v = win.view3d
    q = v._project(*v._camera(), face_sketch.to_world(tool.group, lx, ly))
    return QPoint(int(round(q[0])), int(round(q[1])))


def test_a_3d_line_snaps_tangent_to_a_circle_by_mouse(win):
    McpToolExecutor(win).execute("apply_code",
                                 {"code": "cube([80, 80, 20]);\n"})
    QApplication.processEvents()
    part = next(c for c in win.model.root.children
                if c.visible and c.type != "assign")
    win.show()
    v = win.view3d
    v.resize(900, 700)
    v.set_view("Top", animate=False)
    v.fit()
    QApplication.processEvents()
    tool = _sketch_on(win, part, (40, 40, 20))
    v.fit()
    QApplication.processEvents()
    # the circle the line will touch, in the sketch's own frame
    lx0, ly0 = face_sketch.to_local(tool.group, (40, 40, 20))
    circle = win.model.add_node("circle", dict(x=lx0, y=ly0, radius=12),
                                parent=tool.holder or tool.group)
    tool.set_mode("line")
    start = (lx0 - 30, ly0 - 26)          # off the face diagonal
    want = tangent_snap.tangent_points(start, (lx0, ly0), 12)[0]
    # the start, then a click a little off the tangent point
    QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier,
                     _screen(win, tool, *start))
    QApplication.processEvents()
    near = _screen(win, tool, want[0] + 0.4, want[1] - 0.3)
    QTest.mouseMove(v, near)
    QApplication.processEvents()
    assert tool.tangent is not None            # "Tangent" shows
    QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier, near)
    QApplication.processEvents()
    line = [n for n in circle.parent.children if n.type == "line"][-1]
    p = line.params
    assert (p["x2"], p["y2"]) == pytest.approx(want, abs=1e-3)
    rows = circle.parent.params.get("constraints") or []
    assert any(r["kind"] == "tangent" for r in rows)
