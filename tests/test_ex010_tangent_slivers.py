"""Exercise 010's flange: three circles joined by four tangent lines. The
areas between a tangent line and the two circles are regions to pick, also
when the part under the sketch makes the section polygon (it used to
swallow them, so the waist of the flange was lost)."""
import math
import re

import pytest
from PyQt5.QtWidgets import QApplication, QLabel

from khervecad import region_panel, sketch_regions as sr
from khervecad.mainwindow import MainWindow
from khervecad.mcp_tools import McpToolExecutor


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _tangent(ca, ra, cb, rb, side):
    ny = (ra - rb) / (cb - ca)
    nx = side * math.sqrt(1 - ny * ny)
    return (ra * nx, ca + ra * ny), (rb * nx, cb + rb * ny)


def test_tangent_line_slivers_are_offered_with_a_part_under_the_sketch(app):
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    McpToolExecutor(w).execute("apply_code", {
        "code": "translate([-20, -20, 0]) cube([40, 40, 40]); // Block"})
    for _ in range(5):
        app.processEvents()
    m = w.model
    g = m.add_node("rotate", dict(x=90.0, y=0.0, z=0.0), parent=m.root,
                   name="Front sketch")
    cs = [(29.7, 3.8), (22.2, 6.1), (14.7, 3.8)]
    for y, r in cs:
        m.add_node("circle", dict(x=0, y=y, radius=r), parent=g)
    for side in (1, -1):
        for a, b in ((cs[0], cs[1]), (cs[2], cs[1])):
            p, q = _tangent(a[0], a[1], b[0], b[1], side)
            m.add_node("line", dict(x1=p[0], y1=p[1], x2=q[0], y2=q[1],
                                    width=0.2), parent=g)
    own = sr.faces(sr.shapes_of(g))
    assert len(own) == 9
    assert sr.start_3d(w, g)
    texts = [x.text() for x in region_panel._panel(w).findChildren(QLabel)]
    got = [int(mm.group(1)) for t in texts
           for mm in [re.search(r"\((\d+) found\)", t)] if mm]
    assert got and got[0] >= 9, texts
    w._dirty = False
    w.close()
