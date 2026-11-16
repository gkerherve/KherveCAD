"""A sketch snaps to the points and edges of OTHER sketches that lie in
its plane (SolidWorks: Point2@Sketch4 on Sketch3's edge, A B C on a
sloping plane) — exact, not within a grid step."""
import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import face_outline
from khervecad.mainwindow import MainWindow
from khervecad.mcp_tools import McpToolExecutor

app = QApplication.instance() or QApplication([])


@pytest.fixture
def setup():
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    ex = McpToolExecutor(w)
    ex.execute("apply_code", {"code": "translate([-44,-25,0]) cube([88,50,56]); // Block\n"})
    s3 = ex.execute("reference_geometry", {"action": "sketch",
                    "origin": [0, 0, 56], "normal": [0, 0, 1]})["sketch_id"]
    ex.execute("add_node", {"type": "rect", "parent_id": s3, "params":
               dict(x=-30, y=-25, width=60, height=30)})
    s4 = ex.execute("reference_geometry", {"action": "sketch",
                    "origin": [0, -25, 0], "normal": [0, -1, 0]})["sketch_id"]
    for _ in range(5):
        app.processEvents()
    grp = next(n for n in w.model.root.walk() if n.id == s4)
    block = next(n for n in w.model.root.children if n.type != "union"
                 or n.name.startswith("Block") or n.name == "Cube")
    yield w, grp
    w._dirty = False
    w.close()


def test_the_other_sketchs_points_and_edge_are_offered(setup):
    w, grp = setup
    part = next(n for n in w.model.root.children if n is not grp.parent
                and n.id != grp.id)
    face_outline.show(w, grp, part)
    info = w.view2d.scene().face_outline
    pts = [(round(x, 3), round(y, 3)) for x, y, _k in info["points"]]
    # Sketch3's front corners (+-30, z = 56) lie in this plane: x, y = x, z
    assert (30.0, 56.0) in pts and (-30.0, 56.0) in pts
    # ... and its front edge, as an edge the end of a line can sit on
    guides = info.get("guides") or []
    assert any(abs(a[1] - 56) < 1e-6 and abs(b[1] - 56) < 1e-6
               for a, b in guides)
