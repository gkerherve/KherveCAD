# Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later
"""Reference geometry, sketching in 3D, extrude up to a face / both ways,
the 3D measure and the status-bar mass (the user's SolidWorks list,
2026-10-27)."""

import math

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import (extent, measure3d, massbar, mesh, model, refgeom,
                       refgeom_ui, scadparse, sketch3d)
from khervecad.mcp_tools import McpToolExecutor


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(1000, 700)
    yield win
    win._dirty = False
    win.close()


def _screen(view, p):
    eye, right, up, forward = view._camera()
    s = view._project(eye, right, up, forward, p)
    return s[0], s[1]


def test_reference_nodes_round_trip_and_draw_nothing(app):
    m = model.DocumentModel()
    m.add_node("ref_plane", dict(x=1, y=2, z=3, nx=0, ny=1, nz=0,
                                 size=50))
    m.add_node("ref_axis", dict(dx=1, dy=0, dz=0))
    m.add_node("ref_point", dict(x=5))
    code = m.to_scad()
    assert "module kcad_ref_plane" in code
    root = scadparse.parse_scad(code)[0]
    assert [n.type for n in root.children] == ["ref_plane", "ref_axis",
                                               "ref_point"]
    m2 = model.DocumentModel()
    m2.root = root
    assert m2.to_scad() == code
    assert mesh.tessellate(m.root) == []
    assert model.validate(m.root) == {}


def test_constructions():
    o, n = refgeom.offset_plane([0, 0, 10], [0, 0, 2], 5)
    assert o == [0, 0, 15] and n == [0, 0, 1]
    o, n = refgeom.plane_three_points([0, 0, 0], [1, 0, 0], [0, 1, 0])
    assert n == [0, 0, 1]
    o, n = refgeom.plane_at_angle([0, 0, 0], [1, 0, 0], [0, 0, 1], 90)
    assert abs(abs(n[1]) - 1) < 1e-6
    p, d = refgeom.axis_of_planes([0, 0, 0], [1, 0, 0], [0, 0, 0],
                                  [0, 1, 0])
    assert abs(abs(d[2]) - 1) < 1e-9
    m = model.DocumentModel()
    m.add_node("cylinder", dict(height=20, radius_bottom=5, radius_top=5,
                                x=3, y=4))
    tris = mesh.tessellate(m.root)
    side = refgeom_ui.smooth_region(tris, [8, 4, 10])
    p, d = refgeom.axis_of_cylinder(side)
    assert abs(d[2] - 1) < 1e-6
    assert abs(p[0] - 3) < 0.05 and abs(p[1] - 4) < 0.05


def test_two_way_extrude(app):
    m = model.DocumentModel()
    e = m.add_node("linear_extrude", dict(height=5, height2=3))
    m.add_node("rect", dict(width=4, height=4), parent=e)
    zs = [p[2] for t in mesh.tessellate(m.root) for p in t]
    assert min(zs) == -3 and max(zs) == 5
    code = m.to_scad()
    assert "kcad_extrude_two(height=5, height2=3)" in code
    back = scadparse.parse_scad(code)[0].children[0]
    assert back.params["height2"] == 3


def test_extrude_up_to_a_picked_face(app):
    m = model.DocumentModel()
    e = m.add_node("linear_extrude", dict(height=5))
    m.add_node("rect", dict(x=0, y=0, width=10, height=10), parent=e)
    h = extent.set_extent(m, e, "up_to_face", face=[0, 0, 42, 0, 0, 1])
    assert h == 42
    # a slanted face: met where the axis through the sketch centre is
    s = 1 / math.sqrt(2)
    h = extent.set_extent(m, e, "up_to_face",
                          face=[0, 0, 20, s, 0, s])
    assert abs(h - 15) < 1e-6           # z = 20 - x, centre x = 5


def test_sketch_a_rectangle_in_3d_and_drag_it(window, app):
    win = window
    app.processEvents()
    win.view3d.target, win.view3d.distance = [10.0, 10.0, 0.0], 400.0
    tool = sketch3d.start(win)
    assert win.view3d.edit_tool is tool and tool.group is None
    # click the Top plane in 3D (shown by default) a little off centre
    win.view3d.show_planes = True
    x, y = _screen(win.view3d, (5.0, 5.0, 0.0))
    group = tool.choose(x, y)
    assert group is not None and group.params.get("face_sketch")
    for corner in ((0.0, 0.0), (20.0, 10.0)):
        tool.place(corner)
    rect = [n for n in group.children if n.type == "rect"]
    assert rect and rect[0].params["width"] == 20
    # a click in 3D lands on the plane, snapped
    tool.set_mode("circle")
    a = _screen(win.view3d, sketch_world(group, 30, 30))
    b = _screen(win.view3d, sketch_world(group, 34, 30))
    tool.click(*a)
    tool.click(*b)
    circ = [n for n in group.children if n.type == "circle"]
    assert circ and abs(circ[0].params["radius"] - 4) < 1.01
    # drag a corner
    tool.drag_to(rect[0], "c2", (25.0, 15.0))
    assert rect[0].params["width"] == 25
    assert tool.finish() is group
    assert win.view3d.edit_tool is None


def sketch_world(group, lx, ly):
    from khervecad.face_sketch import to_world
    return to_world(group, lx, ly)


def test_measure_arithmetic():
    face = dict(kind="face", pos=[0, 0, 0], dir=[0, 0, 1],
                tris=[[[0, 0, 0], [10, 0, 0], [0, 10, 0]]])
    one = measure3d.describe(face)
    assert one["area"] == 50
    other = measure3d.describe(dict(kind="face", pos=[3, 4, 12],
                                    dir=[0, 0, -1]))
    both = measure3d.between(one, other)
    assert both["distance"] == 13 and both["normal_distance"] == 12
    edge = measure3d.describe(dict(kind="edge", pos=[0, 0, 0],
                                   seg=[[0, 0, 0], [3, 4, 0]]))
    assert edge["length"] == 5


def test_mass_readout_follows_material(window, app):
    ex = McpToolExecutor(window)
    ex.execute("apply_code", {"code": "cube(10);"})
    app.processEvents()
    text = massbar.update(window)
    assert "1.24 g" in text and "PLA" in text
    massbar.set_material(window, "Steel")
    assert "7.85 g" in massbar.update(window)
    assert window.model.root.params["mass_material"] == "Steel"


def test_planes_are_drawn_and_hit(window, app):
    win = window
    win.view3d.show_planes = True        # a test may have turned it off
    refgeom_ui.add_plane(win, [0, 0, 30], [0, 0, 1], size=60)
    labels = [p[0] for p in refgeom_ui.planes_in_view(win)]
    assert "Plane 1" in labels and "Top" in labels
    assert not win.view3d.grab().isNull()      # paints without error


def test_a_flat_sketch_adds_no_mass(window, app):
    ex = McpToolExecutor(window)
    ex.execute("apply_code", {"code": "cube(10);"})
    refgeom_ui.sketch_on(window, origin=[0, 0, 40], normal=[0, 0, 1],
                         label="Top", open_2d=False)
    sk = [n for n in window.model.root.walk()
          if n.params.get("face_sketch")][0]
    window.model.add_node("rect", dict(width=30, height=30), parent=sk)
    app.processEvents()
    assert "1.24 g" in massbar.update(window)


def test_mcp_reference_geometry(window, app):
    ex = McpToolExecutor(window)
    r = ex.execute("reference_geometry", {"action": "plane",
                                          "offset_from": "Top",
                                          "distance": 20})
    plane = r.get("result", r)
    assert plane["origin"][2] == 20
    s = ex.execute("reference_geometry", {"action": "sketch",
                                          "node_id": plane["id"]})
    s = s.get("result", s)
    assert s["name"].startswith("Sketch on")
    lst = ex.execute("reference_geometry", {})
    lst = lst.get("result", lst)
    assert [x["kind"] for x in lst["reference"]] == ["ref_plane"]


def test_the_main_plane_cuts_the_part_for_the_sketch():
    from khervecad import section_outline
    m = model.DocumentModel()
    u = m.add_node("union", {})
    m.add_node("cube", dict(width=66, depth=42, height=12, y=-21),
               parent=u)
    m.add_node("cube", dict(width=12, depth=42, height=60, x=54, y=-21),
               parent=u)
    hole = m.add_node("difference", {})
    m.add_node("cube", dict(width=20, depth=20, height=20, x=100, y=-10),
               parent=hole)
    m.add_node("cube", dict(width=6, depth=40, height=6, x=107, y=-20,
                            z=7), parent=hole)
    tris = mesh.tessellate(m.root)
    segs = section_outline.segments(tris, "Front (XZ)")
    pts = {p for s in segs for p in s}
    assert (54.0, 12.0) in pts            # the inner corner of the L
    assert (107.0, 7.0) in pts            # the hole stays a hole
    # a plane lying ON a face cuts just inside it: the face's outline
    for n in m.root.walk():
        if n.type == "cube" and n.params.get("y") == -21:
            n.params["y"] = 0.0
    segs = section_outline.segments(mesh.tessellate(m.root), "Front (XZ)")
    assert (54.0, 12.0) in {p for s in segs for p in s}


def test_any_plane_cuts_the_part():
    from khervecad import section_outline
    m = model.DocumentModel()
    m.add_node("cube", dict(width=66, depth=42, height=12))
    m.add_node("cube", dict(width=12, depth=42, height=60, x=54))
    tris = mesh.tessellate(m.root)
    # the middle of the bracket's depth, y = 21, seen from the front
    segs = section_outline.plane_segments(
        tris, (0, 21, 0), (0, -1, 0), (1, 0, 0), (0, 0, 1))
    pts = {p for s in segs for p in s}
    assert (54.0, 12.0) in pts and (66.0, 60.0) in pts


def test_a_shape_drawn_up_to_the_part_edge_stays_on_it(app):
    """The user's case: a centre rectangle up to the top edge of the
    face, then a width of 14 — the height must not change."""
    from types import SimpleNamespace
    from khervecad import face_outline, sketch_constraints as sc
    m = model.DocumentModel()
    g = m.add_node("union", {})
    rect = m.add_node("rect", dict(x=-5, y=-40, width=10, height=80),
                      parent=g)
    top = ((-100.0, 40.0), (100.0, 40.0))
    scene = SimpleNamespace(face_outline=dict(
        segments=[top], points=[]), views=lambda: [])
    assert face_outline.pin(scene, m, rect) == 2     # both top corners
    assert {r["kind"] for r in sc.rows(g)} == {"on_edge"}
    _report, scaled = sc.add_dimension(m, g, "hdistance",
                                       ["0.v2", "0.v3"], 14)
    assert not scaled                    # tied to the part: no rescale
    p = rect.params
    assert abs(p["width"] - 14) < 1e-6
    assert abs(p["y"] + p["height"] - 40) < 1e-6     # still on the edge


def test_dimension_a_face_sketch_to_the_part_origin(window, app):
    """The user's plate: a hole sketched on the top face, dimensioned
    from the part's centre (its origin) — 50 mm."""
    from PyQt5.QtCore import QPointF
    from khervecad import face_outline, face_sketch
    from khervecad import sketch_constraints as sc
    ex = McpToolExecutor(window)
    ex.execute("apply_code", {"code":
                              "translate([-49, -21, 0]) cube([98, 42, 20]);"})
    app.processEvents()
    part = window.model.root.children[-1]
    group = face_sketch.make(window, part, (30.0, 5.0, 20.0), (0, 0, 1))
    app.processEvents()
    scene = window.view2d.scene()
    pts = {k: (x, y) for x, y, k in scene.face_outline["points"]}
    ox, oy = pts["part origin"]
    hole = window.model.add_node("circle", dict(x=5.0, y=-5.0, radius=5),
                                 parent=group)
    app.processEvents()
    ref = face_outline.reference(scene, QPointF(ox, oy), "point")
    assert ref is not None and ref[0].parent is hole.parent
    cont = hole.parent
    sc.add_dimension(window.model, cont, "distance",
                     [sc.ref_of(cont, hole, "c"),
                      sc.ref_of(cont, ref[0], "c")], 50)
    c = face_sketch.to_world(group, hole.params["x"], hole.params["y"])
    assert abs(math.hypot(c[0], c[1]) - 50) < 1e-3
    window.model.remove_node(group)
