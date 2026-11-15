# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Revolved Boss about the sketch's CONSTRUCTION LINE (2026-11-15,
"Deform Feature in SolidWorks": the rod is revolved about a centre line
drawn along X; KherveCAD only revolved about the sketch's Y axis)."""

import pytest
from PyQt5.QtWidgets import QApplication


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    w.show()
    QApplication.processEvents()
    return w


def _span(obj, node):
    from khervecad import mesh
    tris = mesh.transform_mesh(mesh.ancestor_matrix(node, {}, stop=obj),
                               mesh.tessellate(node, {}))
    return [(min(v[i] for t in tris for v in t),
             max(v[i] for t in tris for v in t)) for i in range(3)]


def _sketch(win, x0, y0, x1, h=10.0):
    win._interface_style = "SolidWorks"
    m = win.model
    obj = m.add_node("component", {}, name="Rod")
    r = m.add_node("rect", dict(x=x0, y=y0, width=x1 - x0, height=h),
                   parent=obj, name="Profile")
    axis = m.add_node("line", dict(x1=x0, y1=y0, x2=x1, y2=y0,
                                   width=0.2), parent=obj, name="Axis")
    axis.params["modifier"] = "%"
    return obj, r, axis


def _top(obj, node):
    while node.parent is not obj:
        node = node.parent
    return node


def test_a_construction_line_along_x_is_the_axis_of_revolution(win):
    from khervecad import revolve_feature
    obj, r, _axis = _sketch(win, 0, 0, 40)
    tool = revolve_feature.revolve(win, [r])
    assert tool is not None and tool.type == "rotate_extrude"
    (x0, x1), (y0, y1), (z0, z1) = _span(obj, _top(obj, tool))
    # a bar along X, radius 10 (the profile's height), not a disc round Y
    assert abs(x0) < 0.5 and abs(x1 - 40) < 0.5
    assert abs(y0 + 10) < 0.5 and abs(y1 - 10) < 0.5
    assert abs(z0 + 10) < 0.5 and abs(z1 - 10) < 0.5


def test_the_axis_may_be_off_the_origin(win):
    from khervecad import revolve_feature
    obj, r, _axis = _sketch(win, 5, 20, 45)
    tool = revolve_feature.revolve(win, [r])
    (x0, x1), (y0, y1), (z0, z1) = _span(obj, _top(obj, tool))
    assert abs(x0 - 5) < 0.5 and abs(x1 - 45) < 0.5
    assert abs(y0 - 10) < 0.5 and abs(y1 - 30) < 0.5      # axis y = 20
    assert abs(z0 + 10) < 0.5 and abs(z1 - 10) < 0.5


def test_no_construction_line_still_revolves_about_y(win):
    from khervecad import revolve_feature
    obj, r, axis = _sketch(win, 0, 0, 40)
    axis.parent.remove(axis)
    tool = revolve_feature.revolve(win, [r])
    (x0, x1), _y, _z = _span(obj, _top(obj, tool))
    assert abs(x0 + 40) < 0.5 and abs(x1 - 40) < 0.5


def test_a_front_plane_sketch_with_lines_revolves_about_its_centre_line(win):
    """The video's way: lines close an area, the construction line is the
    axis (a Regions takes that line in with it) — through the same tool
    the Revolved Boss button runs when the sketch is left."""
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)
    win._interface_style = "SolidWorks"
    sk = ex.execute("reference_geometry", dict(
        action="sketch", origin=[0, 0, 0], normal=[0, -1, 0]))["sketch_id"]

    def line(x1, y1, x2, y2):
        return ex.execute("add_node", dict(
            type="line", parent_id=sk,
            params=dict(x1=x1, y1=y1, x2=x2, y2=y2, width=0.2)))["created"]
    for seg in ((0, 0, 0, 5), (0, 5, 93, 2.7), (93, 2.7, 93, 0),
                (0, 0, 93, 0)):
        line(*seg)
    axis = line(0, 0, 93, 0)
    ex.execute("sketch_modify", dict(action="construction", node_id=axis))
    ex.execute("sketch_feature", dict(node_id=sk, kind="revolved_boss"))
    m = ex.execute("mass_properties", {})
    sx, sy, sz = m["size"]
    assert abs(sx - 93) < 0.5 and abs(sy - 10) < 0.5 and abs(sz - 10) < 0.5
