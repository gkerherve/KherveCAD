"""Make2D — the current view as a line drawing (make2d.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import drawing, make2d


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    w.resize(1000, 700)
    w.show()
    c = w.model.add_node("cube", dict(width=30, depth=20, height=10))
    w.model.enclose_as_part(c)
    for _ in range(5):
        app.processEvents()
    yield w
    w._dirty = False
    w.deleteLater()


@pytest.mark.parametrize("ext", [".svg", ".dxf", ".pdf", ".png"])
def test_writes_every_format(win, tmp_path, ext):
    out = tmp_path / ("view" + ext)
    make2d.make(win, out)
    assert out.is_file() and out.stat().st_size > 200
    assert make2d.VIEW not in drawing.VIEWS          # cleaned up


def test_lines_follow_the_camera(win):
    from khervecad import drawing_dialog
    tris, _name = drawing_dialog.model_tris(win)
    with make2d.camera_view(win.view3d) as name:
        right, up, forward = drawing.VIEWS[name]
        _e, r, u, f = win.view3d._camera()
        assert (right, up, forward) == (tuple(r), tuple(u), tuple(f))
        lines = drawing.view_lines(tris, name, hidden_lines=False)
    # a box seen at an angle: its 9 visible edges, nothing hidden
    assert len(lines["visible"]) >= 9 and not lines["hidden"]


def test_mcp_current_view(win, tmp_path):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)
    got = ex.execute("export_drawing", {"path": str(tmp_path / "c.svg"),
                                        "views": ["Current"],
                                        "blueprint": False})
    assert "error" not in got, got
    assert (tmp_path / "c.svg").is_file()
