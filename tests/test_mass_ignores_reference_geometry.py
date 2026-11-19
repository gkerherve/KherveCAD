# KherveCAD - GPL-3.0-or-later
"""mass_properties of the whole scope leaves reference planes, axes and
points out: they are construction, not solid (Exercise 1, problems row 7)."""
from PyQt5.QtWidgets import QApplication
from khervecad.mcp_tools import McpToolExecutor

APP = QApplication.instance() or QApplication([])


def test_a_reference_plane_does_not_add_volume():
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    ex = McpToolExecutor(w)
    ex.execute("apply_code", {"code": "cube([10, 10, 10]);"})
    before = ex.execute("mass_properties", {})["volume"]
    r = ex.execute("reference_geometry", {"action": "plane", "origin": [0, 0, 30],
                                           "normal": [0, 0, 1]})
    assert "error" not in r, r
    after = ex.execute("mass_properties", {})
    assert "error" not in after, after
    assert abs(after["volume"] - before) < 1e-6
    assert all(n.type not in ("ref_plane", "ref_axis", "ref_point")
               for n in w.model.root.walk() if n.id in after["nodes"])
    w._dirty = False
