"""A sketch on a REFERENCE PLANE stays on that plane when the model
changes (2026-11-20, the bearing bracket's Plane1: a block extruded down
from it, then a cut that took the block's top face away moved the Plane1
sketch onto a facet of the cylinder below — x 61.6, z 67.9, tilted 42°).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad.mainwindow import MainWindow
from khervecad.mcp_tools import McpToolExecutor


@pytest.fixture
def win():
    QApplication.instance() or QApplication([])
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    yield w
    w._dirty = False
    w.close()


PLACE = ("x", "y", "z", "rx", "ry", "rz")


def test_a_ref_plane_sketch_keeps_its_place_when_its_face_goes(win):
    from khervecad import refgeom_ui
    ex = McpToolExecutor(win)
    ex.execute("apply_code", {"code": "rotate([90, 0, 0]) "
               "cylinder(r = 25, h = 40, center = true, $fn = 48);\n"})
    QTest.qWait(50)
    ex.execute("reference_geometry", {"action": "plane",
                                      "origin": [0, 0, 48],
                                      "normal": [0, 0, 1]})
    plane = next(n for n in win.model.root.walk() if n.type == "ref_plane")
    group = refgeom_ui.sketch_on(win, node=plane, open_2d=True)
    win.model.add_node("rect", dict(x=-10, y=-10, width=20, height=20),
                       parent=group)
    QTest.qWait(50)
    f = ex.execute("sketch_feature", {"node_id": group.id, "depth": 48,
                                      "reverse": True})
    assert "error" not in f, f
    QTest.qWait(50)
    before = {k: group.params.get(k) for k in PLACE}
    # a cut through everything across the block: its top face is gone
    from khervecad import face_sketch
    face_sketch.close(win) if hasattr(face_sketch, "close") else None
    part = group
    slot = face_sketch.make(win, part, (2, 3, 48), (0, 0, 1), open_2d=True)
    s = {"sketch_id": slot.id}
    ex.execute("add_node", {"type": "rect", "parent_id": s["sketch_id"],
                            "params": dict(x=-30, y=-30, width=60,
                                           height=60)})
    c = ex.execute("sketch_feature", {"node_id": s["sketch_id"],
                                      "kind": "extruded_cut", "depth": 10})
    assert "error" not in c, c
    for _ in range(10):
        QTest.qWait(30)
    assert {k: group.params.get(k) for k in PLACE} == before
