"""Exercise 154 (SolidWorks surface exercise) rebuilt with the surface
tool windows: loft, drafted extrudes, mirror, trims, boundary / planar
caps, knit, fillet, thicken 2 mm.

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
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import cadexchange as cx, curve_surface as cs, \
    surface_edit as se, surface_tool as st
from khervecad.mainwindow import MainWindow
from khervecad.model import validate

pytestmark = pytest.mark.skipif(not cx.occ_available(),
                                reason="OpenCascade not installed")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def arc(x, r, n=25):
    return [[x, r * math.cos(math.pi * i / (n - 1)),
             r * math.sin(math.pi * i / (n - 1))] for i in range(n)]


def circ(cx_, cy, cz, r, plane, n=24):
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        out.append([cx_ + r * math.cos(a), cy, cz + r * math.sin(a)]
                   if plane == "xz" else
                   [cx_ + r * math.cos(a), cy + r * math.sin(a), cz])
    return out


def sheet(win, name, pts, direction, draft):
    m = win.model
    n = m.add_node("curve_surface", dict(
        cs._DEFAULTS, kind="extrude", height=120, direction=direction,
        draft=draft, sheet=True), parent=m.root, name=name)
    m.add_node("curve", dict(points=pts, closed=True), parent=n, name="c")
    return n


def run_tool(win, op, nodes, pick_rows=None, **params):
    """The window: select, open, fill the clicks' rows, OK."""
    win.builder.active_tree().select_nodes(nodes)
    panel = st.start(win, op)
    assert panel is not None, op
    node = win._surface_state["node"]
    for k, v in params.items():
        win.model.set_param(node, k, v)
    if pick_rows is not None:
        key = st.OPS[op][2]
        win.model.set_param(node, key, pick_rows)
    problem = validate(win.model.root).get(node.id)
    assert problem is None, f"{node.name}: {problem}"
    st.ok(win)
    return node


def test_the_whole_exercise_by_the_tools(app):
    win = MainWindow()
    win.resize(1200, 800)
    win.show()
    QTest.qWaitForWindowExposed(win)
    m = win.model
    loft = m.add_node("curve_surface", dict(cs._DEFAULTS, kind="loft",
                                            sheet=True),
                      parent=m.root, name="Surface-Loft1")
    m.add_node("curve", dict(points=arc(0, 100)), parent=loft)
    m.add_node("curve", dict(points=arc(150, 50)), parent=loft)
    arm = sheet(win, "Surface-Extrude1", circ(75, 150, 0, 25, "xz"),
                "-Y", 10)
    cone = sheet(win, "Surface-Extrude2", circ(75, 0, 150, 25, "xy"),
                 "-Z", 10)
    mir = run_tool(win, "mirror", [arm], plane="XZ (Front)")
    # lower halves of the arms: trim by the z = 0 plane
    plane0 = m.add_node("surface_edit", dict(se._DEFAULTS, op="planar"),
                        parent=m.root, name="Plane (z=0)")
    m.add_node("curve", dict(
        points=[[-200, -300, 0], [400, -300, 0], [400, 300, 0],
                [-200, 300, 0]], closed=True, style="straight"),
        parent=plane0)
    t0 = run_tool(win, "trim", [mir, plane0],
                  pick_rows=[[75, 84, -23], [75, -84, -23]])
    # mutual trim: pieces inside each other go
    win.builder.active_tree().select_nodes([loft, t0, cone])
    st.start(win, "trim")
    t1 = win._surface_state["node"]
    win.model.set_param(t1, "mutual", True)
    pcs = se.pieces_of(se.child_shapes(t1, {}))
    assert len(pcs) == 14
    rows = [se.point_on(pcs[i]) for i in (1, 2, 3, 5, 6, 7, 8, 10, 11, 13)]
    win.model.set_param(t1, "remove", rows)
    st.ok(win)
    cap = run_tool(win, "boundary", [t1], pick_rows=[
        [75 + 25 * math.cos(0.8), 150, 25 * math.sin(0.8)],
        [75 + 25 * math.cos(0.8), -150, 25 * math.sin(0.8)],
        [0, 0, 100], [150, 0, 50]])
    top = run_tool(win, "planar", [cap], pick_rows=[[100, 0, 150]])
    knit = run_tool(win, "knit", [top])
    shape = se.shape_of(knit, {})
    es = se._edges(shape)

    def edge_at(x, y, z):
        return se.edge_point(es[se._nearest((x, y, z), es)])
    fil = run_tool(win, "fillet", [knit], pick_rows=[
        edge_at(50, 0, 150) + [5], edge_at(76, 63, 40) + [10],
        edge_at(77, -62, 40) + [10], edge_at(39, -1, 87) + [15]])
    th = run_tool(win, "thicken", [fil], thickness=2.0)
    out = se.shape_of(th, {})
    assert cs.is_solid(out)
    from OCP.GProp import GProp_GProps
    from OCP.BRepGProp import BRepGProp
    tris = cx._mesh_shape_rel(out, se.DEFLECTION, se.ANGLE)
    zs = [v[2] for t in tris for v in t]
    ys = [v[1] for t in tris for v in t]
    assert max(zs) == pytest.approx(152, abs=1.5)       # 150 high + wall
    assert max(ys) - min(ys) == pytest.approx(300, abs=5)   # 150 a side
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(out, g)
    assert abs(g.Mass()) == pytest.approx(99000, rel=0.08)
    # every node of the chain is green
    assert not validate(m.root)
    win._dirty = False
    win.close()
