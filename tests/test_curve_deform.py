# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""SolidWorks' Deform > Curve to curve (2026-11-15, "Deform Feature in
SolidWorks"): a body carried from an initial curve onto a target curve."""

import math

import pytest

ROD = "rotate([0, 90, 0]) cylinder(r = 3, h = 40, $fn = 48);"
R = 40.0 / (math.pi / 2)


def _arc(n=120):
    return [[R * math.sin(t), 0.0, R * (1 - math.cos(t))]
            for t in (i * math.pi / 2 / n for i in range(n + 1))]


def _tess(code):
    from khervecad import mesh, scadparse
    root = scadparse.parse_scad(code)[0]
    return root, [tuple(t[:3]) for t in mesh.tessellate(root)]


def _code(init, targ):
    rows = lambda pts: "[" + ", ".join(  # noqa: E731
        "[%g, %g, %g]" % tuple(p) for p in pts) + "]"
    return ("kcad_curve_deform(initial = %s, target = %s) { %s }"
            % (rows(init), rows(targ), ROD))


def test_a_rod_bends_onto_a_quarter_circle():
    from khervecad import analysis
    _r, straight = _tess(ROD)
    _r, bent = _tess(_code([[0, 0, 0], [40, 0, 0]], _arc()))
    xs = [p[0] for t in bent for p in t]
    zs = [p[2] for t in bent for p in t]
    assert max(xs) == pytest.approx(R + 3, abs=0.3)
    assert max(zs) == pytest.approx(R, abs=0.3)
    assert min(xs) == pytest.approx(0, abs=0.05)         # start stays put
    v0 = analysis.mass_properties(straight)["volume"]
    v1 = analysis.mass_properties(bent)["volume"]
    assert v1 == pytest.approx(v0, rel=0.03)


def test_where_the_curves_coincide_the_body_does_not_move():
    # target: straight for 20, then bends up; the first 20 mm are untouched
    targ = [[x, 0, 0] for x in range(0, 21)] + \
           [[20 + 20 * math.sin(t), 0, 20 * (1 - math.cos(t))]
            for t in (i * 0.05 for i in range(1, 21))]
    _r, bent = _tess(_code([[0, 0, 0], [40, 0, 0]], targ))
    near = [p for t in bent for p in t if p[0] < 15]
    assert near and max(abs(p[2]) for p in near) < 3.001
    assert max(p[2] for t in bent for p in t) > 10


def test_a_curve_chained_from_sketch_lines_and_arcs(app_window):
    """The video's target: line 20, a R10 arc, a vertical, a R15 arc and
    the top line — chained from the lines of a Front sketch into one
    polyline of about 93 mm."""
    from khervecad import curve_deform
    win = app_window
    m = win.model
    g = m.add_node("union", {}, name="Sketch6")
    from khervecad import sketch_arc

    def ln(x1, y1, x2, y2, bulge=0.0):
        n = m.add_node("line", dict(x1=x1, y1=y1, x2=x2, y2=y2, width=0.2),
                       parent=g)
        if bulge:
            n.params["bulge"] = bulge
        return n
    b = math.tan(math.radians(90) / 4)
    nodes = [ln(0, 0, 10, 0), ln(10, 0, 20, 10, b), ln(20, 10, 20, 15),
             ln(20, 15, 35, 30, -b), ln(35, 30, 74, 30)]
    pts = curve_deform.sketch_curve(nodes)
    assert pts is not None
    length = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    assert length == pytest.approx(10 + 15.71 + 5 + 23.56 + 39, abs=0.3)
    assert pts[-1][0] == pytest.approx(74) and pts[-1][1] == pytest.approx(30)


@pytest.fixture
def app_window():
    from PyQt5.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    w.show()
    return w
