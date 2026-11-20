"""A Blind Extruded Cut on a face sketch goes INTO the part, as in
SolidWorks (2026-11-20, Exercise 009's counterbore: chosen Blind in the
Extrude window it cut the air above the face and removed nothing).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""
from PyQt5.QtWidgets import QApplication

from khervecad import analysis, extrude_panel, face_sketch, mesh
from khervecad.mainwindow import MainWindow
from khervecad.mcp_tools import McpToolExecutor

app = QApplication.instance() or QApplication([])


def _volume(w):
    from khervecad import csg
    tris = mesh.tessellate(w.model.root)
    m = csg.to_manifold([(t, None, False) for t in tris], {})
    return m.volume() if m is not None else analysis.mass_properties(
        tris)["volume"]


def test_a_blind_cut_on_a_face_sketch_goes_into_the_part():
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    ex = McpToolExecutor(w)
    ex.execute("apply_code", {"code": "cube([40, 40, 30]); // Block\n"})
    block = next(n for n in w.model.root.walk() if n.type == "cube")
    grp = face_sketch.make(w, block, (20, 20, 30), (0, 0, 1), open_2d=False)
    ex.execute("add_node", {"type": "rect", "parent_id": grp.id, "params":
               dict(x=15, y=15, width=10, height=10)})
    f = ex.execute("sketch_feature", {"node_id": grp.id, "depth": 5})
    ext = next(n for n in w.model.root.walk() if n.id == f["extrude_id"])
    assert extrude_panel.set_operation(w.model, ext, "cut")
    # the Extrude window: End condition Blind, Distance 5
    extrude_panel.choose_extent(w, ext, "")
    extrude_panel.set_direction(w.model, ext, extrude_panel.ONE)
    w.model.set_param(ext, "height", 5.0)
    assert abs(_volume(w) - (40 * 40 * 30 - 10 * 10 * 5)) < 1.0
    w._dirty = False
    w.close()
