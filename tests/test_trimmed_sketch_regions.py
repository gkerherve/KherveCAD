# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""A trimmed rectangle's open lines, ending on a boss's ring, are offered
as regions with the part's edge (2026-11-12, the user: "once done I am
not able to create those as regions")."""

import math

import pytest
from PyQt5.QtWidgets import QApplication


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def test_open_lines_closing_with_the_part_are_offered(app):
    from khervecad.mainwindow import MainWindow
    from khervecad import sketch_regions as sr
    w = MainWindow()
    w.show()
    QApplication.processEvents()
    m = w.model
    obj = m.add_node("component", {}, name="Ex")
    obj.visible = True
    ext = m.add_node("linear_extrude", {"height": 56}, parent=obj,
                     name="Boss")
    m.add_node("circle", dict(x=0, y=0, radius=28), parent=ext)
    y0 = -math.sqrt(28 ** 2 - 24 ** 2)
    for a, b in (((-24, y0), (-24, -90)), ((-24, -90), (24, -90)),
                 ((24, -90), (24, y0))):
        m.add_node("line", dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1],
                                width=0.2), parent=obj)
    w.builder.open_component(obj)
    for _ in range(10):
        QApplication.processEvents()
    assert not sr.faces(sr.shapes_of(obj))        # not closed by itself
    assert obj in sr.all_sketches(w)              # but offered
