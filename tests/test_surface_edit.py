"""Surface bodies (surface_edit.py): trim, knit, planar, boundary,
thicken, fillet, mirror on sheets made by curve_surface.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import cadexchange as cx, curve_surface as cs, \
    surface_edit as se
from khervecad.model import DocumentModel

pytestmark = pytest.mark.skipif(not cx.occ_available(),
                                reason="OpenCascade not installed")


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def circle_pts(cx_, cy, cz, r, plane, n=24):
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        if plane == "xz":
            out.append([cx_ + r * math.cos(a), cy, cz + r * math.sin(a)])
        else:                                     # "yz"
            out.append([cx_, cy + r * math.cos(a), cz + r * math.sin(a)])
    return out


def tube(model, parent, y, direction, name, draft=0.0, height=100.0):
    surf = model.add_node("curve_surface", dict(
        cs._DEFAULTS, kind="extrude", height=height, direction=direction,
        draft=draft, sheet=True), parent=parent, name=name)
    model.add_node("curve", dict(points=circle_pts(0, y, 0, 20, "xz"),
                                 closed=True), parent=surf)
    return surf


def area(shape):
    from OCP.GProp import GProp_GProps
    from OCP.BRepGProp import BRepGProp
    g = GProp_GProps()
    BRepGProp.SurfaceProperties_s(shape, g)
    return g.Mass()


def volume(shape):
    from OCP.GProp import GProp_GProps
    from OCP.BRepGProp import BRepGProp
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, g)
    return g.Mass()


def test_a_sheet_extrude_with_draft_is_open_and_widens(app):
    m = DocumentModel()
    t = tube(m, m.root, 0, "+Y", "T", draft=10.0, height=100.0)
    sh = cs.shape(t, {})
    assert not cs.is_solid(sh)
    # side area of a cone frustum, r 20 -> 20 + 100 tan 10
    r2 = 20 + 100 * math.tan(math.radians(10))
    slant = math.hypot(100, r2 - 20)
    assert area(sh) == pytest.approx(math.pi * (20 + r2) * slant, rel=0.01)


def test_mutual_trim_then_knit_makes_a_closed_body(app):
    m = DocumentModel()
    a = tube(m, m.root, -50, "+Y", "A", height=100.0)     # along Y
    b = m.add_node("curve_surface", dict(
        cs._DEFAULTS, kind="extrude", height=100.0, direction="+X",
        sheet=True), parent=m.root, name="B")
    m.add_node("curve", dict(points=circle_pts(-50, 0, 0, 20, "yz"),
                             closed=True), parent=b)
    trim = m.add_node("surface_edit", dict(
        se._DEFAULTS, op="trim", mutual=True,
        remove=[[0, -50, 20], [0, 50, 20]]), parent=m.root, name="Trim")
    for s in (a, b):
        m.move_node(s, trim)
    shapes = se.child_shapes(trim, {})
    assert len(shapes) == 2
    out = se.shape_of(trim, {})
    # both tubes were cut where they cross: more faces than the two
    assert len(se._faces(out)) > 2


def test_thicken_makes_a_solid_with_the_wall_volume(app):
    m = DocumentModel()
    t = tube(m, m.root, 0, "+Y", "T", height=50.0)
    th = m.add_node("surface_edit", dict(se._DEFAULTS, op="thicken",
                                         thickness=2.0),
                    parent=m.root, name="Thicken")
    m.move_node(t, th)
    out = se.shape_of(th, {})
    assert cs.is_solid(out)
    # a +2 mm wall grows outward: pi (22^2 - 20^2) 50
    assert abs(volume(out)) == pytest.approx(
        math.pi * (22 ** 2 - 20 ** 2) * 50, rel=0.03)


def test_planar_caps_the_open_end_and_knit_closes_it(app):
    m = DocumentModel()
    t = tube(m, m.root, 0, "+Y", "T", height=50.0)
    cap = m.add_node("surface_edit", dict(
        se._DEFAULTS, op="planar", points=[[20, 0, 0]]),
        parent=m.root, name="Cap")
    m.add_node("curve", dict(points=circle_pts(0, 0, 0, 20, "xz"),
                             closed=True), parent=cap)
    kn = m.add_node("surface_edit", dict(se._DEFAULTS, op="knit",
                                         solid=False),
                    parent=m.root, name="Knit")
    m.move_node(t, kn)
    m.move_node(cap, kn)
    out = se.shape_of(kn, {})
    assert area(out) > math.pi * 20 * 20


def test_mirror_doubles_the_surface(app):
    m = DocumentModel()
    t = tube(m, m.root, 30, "+Y", "T", height=40.0)
    mi = m.add_node("surface_edit", dict(se._DEFAULTS, op="mirror",
                                         plane="XZ (Front)"),
                    parent=m.root, name="Mirror")
    m.move_node(t, mi)
    out = se.shape_of(mi, {})
    assert area(out) == pytest.approx(2 * area(cs.shape(t, {})), rel=0.01)


def test_the_node_bakes_into_triangles(app):
    m = DocumentModel()
    t = tube(m, m.root, 0, "+Y", "T", height=50.0)
    th = m.add_node("surface_edit", dict(se._DEFAULTS, op="thicken",
                                         thickness=2.0),
                    parent=m.root, name="Thicken")
    m.move_node(t, th)
    from khervecad import mesh
    tris = mesh.tessellate(m.root)
    assert len(tris) > 100
