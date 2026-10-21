"""MCP sketch_modify and the first-dimension scaling through
sketch_constraint.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication([])


@pytest.fixture
def ex():
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    win = MainWindow()
    yield McpToolExecutor(win)
    win._dirty = False
    win.close()


def test_trim_extend_and_fillet(ex):
    m = ex._w.model
    a = m.add_node("line", dict(x1=0, y1=0, x2=20, y2=0))
    m.add_node("line", dict(x1=10, y1=-5, x2=10, y2=5))
    out = ex.execute("sketch_modify", dict(action="trim", node_id=a.id,
                                           point=[15, 0]))
    assert "error" not in out, out
    assert out["line"]["x2"] == pytest.approx(10)
    poly = m.add_node("polygon", dict(points=[[0, 0], [10, 0], [10, 10],
                                              [0, 10]]))
    out = ex.execute("sketch_modify", dict(action="fillet", node_id=poly.id,
                                           vertex=2, size=2))
    assert "error" not in out, out
    assert out["corners"]
    bad = ex.execute("sketch_modify", dict(action="trim", node_id=poly.id,
                                           point=[0, 0]))
    assert "error" in bad


def test_first_dimension_scales_through_mcp(ex, monkeypatch):
    from khervecad import sketch_constraints as sc
    monkeypatch.setattr(sc, "scale_first_enabled", lambda: True)
    m = ex._w.model
    a = m.add_node("line", dict(x1=0, y1=0, x2=10, y2=0))
    c = m.add_node("circle", dict(x=20, y=0, radius=2))
    i = m.root.children.index(a)
    out = ex.execute("sketch_constraint", dict(
        action="add", kind="length", refs=["%d.l" % i], value=20))
    assert "error" not in out, out
    assert out["scaled"] is True
    assert c.params["radius"] == pytest.approx(4)
