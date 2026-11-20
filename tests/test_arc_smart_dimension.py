"""Smart Dimension on an ARC gives its radius (SolidWorks' R55), and it
drives the arc (2026-11-20, Exercise 009's rib arc came out a driven
diameter "(Ø110.36)" drawn across the whole circle).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""
from PyQt5.QtWidgets import QApplication

from khervecad import sketch_arc, sketch_constrain_ui as ui
from khervecad import sketch_constraints as sc
from khervecad.model import DocumentModel

app = QApplication.instance() or QApplication([])


def test_a_click_on_an_arc_and_off_it_is_its_radius_and_drives_it():
    m = DocumentModel()
    g = m.add_node("union", {}, parent=m.root)
    b = sketch_arc.bulge_through((-20, 20), (20, 90), (15.3, 46.3))
    arc = m.add_node("line", dict(x1=-20, y1=20, x2=20, y2=90, width=0.2,
                                  bulge=b), parent=g)
    pick = (arc, "o", "circle")
    kind, picks = ui._smart(pick, pick)
    assert kind == "radius"
    sc.add(m, g, kind, [sc.ref_of(g, p[0], p[1]) for p in picks], 60.0)
    cx, cy, r, _a0, _sw = sketch_arc.geometry(
        *(float(arc.params[k]) for k in ("x1", "y1", "x2", "y2")),
        sketch_arc.bulge_of(arc.params))
    assert abs(r - 60.0) < 1e-3
