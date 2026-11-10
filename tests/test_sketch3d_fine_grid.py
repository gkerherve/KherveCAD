"""The 3D sketch's grid gets finer on a small face (2026-11-10, the
user: a circle could not be put on a 0.84 x 0.5 mm face — under a 0.5 mm
grid every click jumped to one of its corners).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import face_sketch
from khervecad.mcp_tools import McpToolExecutor

from test_stacked_features import app, win, _sketch_on  # noqa


def _tool(win, size):
    McpToolExecutor(win).execute(
        "apply_code", {"code": "cube([%g, %g, %g]);\n" % (size, size, size)})
    QApplication.processEvents()
    part = next(c for c in win.model.root.children
                if c.visible and c.type != "assign")
    v = win.view3d
    v.resize(900, 700)
    v.set_view("Isometric", animate=False)
    v.fit()
    QApplication.processEvents()
    tool = _sketch_on(win, part, (size / 2, size / 2, size))
    v.fit()
    return tool


def test_a_small_face_gets_a_fine_grid(win):
    tool = _tool(win, 0.8)
    win.scene.grid_size = 0.5
    step = tool.grid_at(0.4, 0.4)
    assert step < 0.5 and step in (0.01, 0.02, 0.05, 0.1, 0.2)
    # a click off every snap lands on that fine grid, inside the face
    v = win.view3d
    q = v._project(*v._camera(), (0.31, 0.47, 0.8))
    x, y = tool.local_of(q[0], q[1])
    assert 0 < x < 0.8 and 0 < y < 0.8
    assert (x, y) not in ((0.0, 0.5), (0.5, 0.5), (0.5, 0.0), (0.0, 0.0))
    assert round(x / step) * step == pytest.approx(x, abs=1e-9)


def test_an_ordinary_part_keeps_the_grid(win):
    tool = _tool(win, 80.0)
    win.scene.grid_size = 1.0
    assert tool.grid_at(40.0, 40.0) == 1.0
