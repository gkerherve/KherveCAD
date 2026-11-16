"""The Plane window takes a SKETCH point clicked in 3D (SolidWorks' Plane
through Point@Sketch3 ...): a sketch's rectangle corner or line end drawn
in the 3D view is a reference, so a plane can go through three of them."""
import pytest
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import plane_tool as pt
from khervecad.mainwindow import MainWindow
from khervecad.mcp_tools import McpToolExecutor

app = QApplication.instance() or QApplication([])


@pytest.fixture
def win():
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    ex = McpToolExecutor(w)
    ex.execute("apply_code", {"code": "cube([40, 30, 20]); // Block\n"})
    s = ex.execute("reference_geometry", {"action": "sketch",
                   "origin": [0, 0, 50], "normal": [0, 0, 1]})["sketch_id"]
    ex.execute("add_node", {"type": "rect", "parent_id": s, "params":
               dict(x=-10, y=-10, width=60, height=50)})
    for _ in range(5):
        app.processEvents()
    yield w
    w._dirty = False
    w.close()


def test_sketch_points_lists_the_corners(win):
    pts = pt.sketch_points(win)
    for p in ((-10, -10, 50), (50, -10, 50), (50, 40, 50), (-10, 40, 50)):
        assert any(max(abs(a - b) for a, b in zip(q, p)) < 1e-6 for q in pts)


def test_clicking_a_sketch_corner_in_3d_is_a_point_reference(win):
    pt.start(win)
    v = win.view3d
    v.fit()
    app.processEvents()
    cam = v._camera()
    q = v._project(*cam, (50, 40, 50))
    QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier,
                     QPoint(int(q[0]) + 2, int(q[1]) + 1))
    st = win._plane_tool
    assert st["refs"] and st["refs"][0]["kind"] == "point"
    assert st["refs"][0]["point"] == pytest.approx([50, 40, 50], abs=1e-6)
