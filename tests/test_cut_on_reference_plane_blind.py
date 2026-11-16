"""An Extruded Cut from a sketch on a reference plane starts Blind, One
side (not Through All, Symmetric)."""
import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import extrude_panel, normal_to, refgeom_ui
from khervecad.mainwindow import MainWindow
from khervecad.mcp_tools import McpToolExecutor

app = QApplication.instance() or QApplication([])


def test_cut_from_a_reference_plane_sketch_is_blind_one_side():
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    ex = McpToolExecutor(w)
    ex.execute("apply_code", {"code": "translate([-20,-20,0]) cube([40,40,30]); // Block\n"})
    pl = ex.execute("reference_geometry", {"action": "plane",
                    "points": [[0, 0, 0], [10, 0, 0], [0, 10, 10]]})
    node = next(n for n in w.model.root.walk() if n.id == pl["id"])
    grp = refgeom_ui.sketch_on(w, node=node, open_2d=False)
    ex.execute("add_node", {"type": "rect", "parent_id": grp.id, "params":
               dict(x=-5, y=-5, width=10, height=10)})
    f = ex.execute("sketch_feature", {"node_id": grp.id, "depth": 12})
    ext = next(n for n in w.model.root.walk() if n.id == f["extrude_id"])
    assert extrude_panel.set_operation(w.model, ext, "cut")
    assert not ext.params.get("extent")
    assert not ext.params.get("center")
    w._dirty = False
    w.close()
