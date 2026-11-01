"""Sketch relations and Smart Dimensions in the 3D view (2026-11-01,
the user: clicking a constraint switched straight to 2D).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtTest import QTest

from test_lever_by_mouse import win  # noqa: F401


def _screen(tool, world):
    q = tool._project()(world)
    return q[0], q[1]


def _setup(win):
    m = win.model
    g = m.add_node("union", {}, name="Sketch")
    line = m.add_node("line", dict(x1=0, y1=0, x2=40, y2=6, width=0.2),
                      parent=g)
    QTest.qWait(50)
    v = win.view3d
    v.resize(800, 600)
    v.set_view("Top", animate=False)
    v.fit()
    return g, line


def test_horizontal_by_a_click_in_3d(win):
    from khervecad import constrain3d
    g, line = _setup(win)
    assert constrain3d.start(win, "con_horizontal")
    tool = win.view3d.edit_tool
    x, y = _screen(tool, (20, 3, 0))
    assert tool.pick_at(x, y)[:2] == (line, "l")       # it lights up
    tool.click(x, y)
    assert line.params["y1"] == pytest.approx(line.params["y2"])
    assert any(r["kind"] == "horizontal" for r in g.params["constraints"])


def test_smart_dimension_in_3d(win):
    from khervecad import constrain3d
    g, line = _setup(win)
    win.view2d.scene().ask_value = lambda kind, measured: "50"
    assert constrain3d.start(win, "con_dimension")
    tool = win.view3d.edit_tool
    x, y = _screen(tool, (10, 1.5, 0))
    tool.click(x, y)
    tool.click(5, 5)                       # empty: the line's length
    p = line.params
    assert ((p["x2"] - p["x1"]) ** 2 + (p["y2"] - p["y1"]) ** 2) ** 0.5 \
        == pytest.approx(50, abs=0.01)


def test_choosing_a_constraint_in_solidworks_stays_in_3d(win):
    from khervecad import constrain3d, sketch_mode
    _setup(win)
    win._interface_style = "SolidWorks"
    sketch_mode.tool_chosen(win, "con_vertical")
    assert isinstance(win.view3d.edit_tool, constrain3d.Constrain3D)
    assert not sketch_mode.sketching(win)


def test_command_plus_and_minus_zoom_the_3d_view(win):
    from khervecad import sketch_mode
    _setup(win)
    win._interface_style = "SolidWorks"
    assert not sketch_mode.sketching(win)
    v = win.view3d
    before = v.distance
    win._zoom(1.25)
    assert v.distance < before
    win._zoom(1 / 1.25)
    assert v.distance == __import__("pytest").approx(before, rel=0.01)


def _two_sketches(win):
    m = win.model
    g, line = _setup(win)
    other = m.add_node("union", {}, name="Other sketch")
    far = m.add_node("line", dict(x1=0, y1=30, x2=40, y2=30, width=0.2),
                     parent=other)
    round_ = m.add_node("circle", dict(x=70, y=30, radius=6), parent=other)
    mine = m.add_node("circle", dict(x=70, y=0, radius=3), parent=g)
    QTest.qWait(50)
    win.view3d.fit()
    return g, line, other, far, round_, mine


def test_a_relation_crosses_sketches_through_a_reference(win):
    from khervecad import constrain3d
    g, line, other, far, _r, _m = _two_sketches(win)
    constrain3d.start(win, "con_parallel")
    tool = win.view3d.edit_tool
    tool.click(*_screen(tool, (20, 3, 0)))
    tool.click(*_screen(tool, (20, 30, 0)))
    # the newer sketch hangs on the older: its line tilts, the first stays
    assert (line.params["y1"], line.params["y2"]) == (0, 6)
    assert far.params["y2"] - far.params["y1"] == pytest.approx(
        (far.params["x2"] - far.params["x1"]) * 6 / 40, abs=1e-3)
    assert "constraints" not in g.params
    assert [c.name for c in other.children if c.params.get("ref_source")] == [
        "Reference edge"]
    assert any(r["kind"] == "parallel" for r in other.params["constraints"])


def test_equal_circles_across_sketches_leaves_no_dimension(win):
    from khervecad import constrain3d
    _g, _l, other, _f, round_, mine = _two_sketches(win)
    constrain3d.start(win, "con_equal")
    tool = win.view3d.edit_tool
    tool.click(*_screen(tool, (73, 0, 0)))
    tool.click(*_screen(tool, (76, 30, 0)))
    assert float(round_.params["radius"]) == pytest.approx(3, abs=1e-3)
    assert mine.params["radius"] == 3
    assert not [r for r in other.params["constraints"] if "value" in r]


def test_a_refused_relation_leaves_no_reference(win):
    from khervecad import constrain3d, sketch_constraints as sc
    g, line, other, far, _r, _m = _two_sketches(win)
    # the newer sketch's line cannot be both horizontal and along a slope
    sc.add(win.model, other, "horizontal", [sc.ref_of(other, far, "l")])
    constrain3d.start(win, "con_parallel")
    tool = win.view3d.edit_tool
    x = line.params["x1"] + 20
    tool.click(*_screen(tool, (x, (line.params["y1"] + line.params["y2"]) / 2,
                               0)))
    tool.click(*_screen(tool, (20, 30, 0)))
    assert not [c for c in other.children if c.params.get("ref_source")]


def test_two_cubes_follow_the_plate_top_and_keep_their_size(win):
    """Dimension from the plate's top line to a cube, and from that cube
    to a second one: 64 -> 60 takes both down 4 (the user)."""
    from khervecad import constrain3d, face_sketch as fs, sketch_constraints as sc
    m = win.model
    obj = m.add_node("component", {}, name="Part")
    obj.visible = True
    win.builder.open_component(obj)
    QTest.qWait(50)
    g = m.add_node("union", {}, parent=obj)
    ext = m.add_node("linear_extrude", dict(height=16), parent=g)
    plate = m.add_node("rect", dict(x=0, y=0, width=64, height=64), parent=ext)
    sc.add(m, ext, "fix", [sc.ref_of(ext, plate, "v0")])
    sc.add(m, ext, "length", [sc.ref_of(ext, plate, "e1")], 64.0)
    QTest.qWait(100)
    v = win.view3d
    v.resize(800, 600)
    v.set_view("Top", animate=False)
    v.fit()

    def cube(part, z, h, at, size):
        gr = fs.make(win, part, (*at, z), (0, 0, 1), open_2d=False)
        e = m.add_node("linear_extrude", dict(height=h), parent=gr)
        lx, ly = fs.to_local(gr, (*at, z))
        return gr, e, m.add_node("rect", dict(x=lx, y=ly, width=size,
                                              height=size), parent=e)

    def dim(a, b, value):
        win.view2d.scene().ask_value = lambda k, x: str(value)
        constrain3d.start(win, "con_dimension")
        t = v.edit_tool
        t.click(*_screen(t, a))        # the model's line first
        t.click(*_screen(t, b))
        constrain3d.end(win)
        QTest.qWait(50)

    def tops(gr, n):
        return [round(fs.to_world(gr, *sc._point(n, i, {}))[1], 2)
                for i in ("v0", "v2")]
    ga, ea, a = cube(g, 16, 5, (30, 50), 10)
    QTest.qWait(100)
    dim((20, 64, 16), (35, 60, 21), 10)
    assert tops(ga, a) == [44, 54]
    gb, eb, b = cube(ga, 21, 4, (32, 38), 4)
    QTest.qWait(100)
    dim((34, 54, 21), (34, 42, 25), 8)
    assert tops(gb, b) == [42, 46]
    assert not [c for c in ea.children if c is not a and "Reference edge"
                not in c.name]
    row = [i for i, r in enumerate(sc.rows(ext)) if r.get("value") == 64.0][0]
    sc.set_value(m, ext, row, 60.0)
    QTest.qWait(300)
    assert tops(ga, a) == [40, 50]
    assert tops(gb, b) == [38, 42]


def test_a_refused_relation_says_so_on_the_view(win):
    from khervecad import constrain3d, sketch_constraints as sc
    g, line, other, far, _r, _m = _two_sketches(win)
    sc.add(win.model, other, "horizontal", [sc.ref_of(other, far, "l")])
    constrain3d.start(win, "con_parallel")
    tool = win.view3d.edit_tool
    tool.click(*_screen(tool, (20, 3, 0)))
    tool.click(*_screen(tool, (20, 30, 0)))
    assert "refused" in win.view3d._flash_text


def test_a_cut_opens_a_sloped_face(win):
    """No skin over the hole on the triangle's slope (the user)."""
    import math
    from khervecad import cut_feature, face_sketch as fs
    m = win.model
    obj = m.add_node("component", {}, name="Rib")
    obj.visible = True
    win.builder.open_component(obj)
    r = m.add_node("rotate", dict(x=90, y=0, z=0), parent=obj)
    e = m.add_node("linear_extrude", dict(height=12), parent=r)
    m.add_node("polygon", dict(points=[[0, 0], [64, 0], [0, 48]]), parent=e)
    QTest.qWait(200)
    L = math.hypot(64, 48)
    n = (48 / L, 0, 64 / L)
    P = (32, -6, 24)
    g = fs.make(win, r, P, n, open_2d=False)
    g.params["cut"] = "extruded_cut"
    lx, ly = fs.to_local(g, P)
    m.add_node("circle", dict(x=lx, y=ly, radius=3), parent=g)
    QTest.qWait(50)
    cut_feature.finish(win, g)
    QTest.qWait(400)
    near = [t for t in win.view3d.model_mesh
            if math.dist([sum(v[i] for v in t[:3]) / 3 for i in range(3)], P)
            < 2.5]
    assert not near
    assert "lead=0.01" in m.to_scad().replace(" ", "")


def test_a_part_with_a_stray_edge_still_hides_dimensions():
    """One non-manifold edge must not make the whole model see-through."""
    from khervecad import sketch_dims3d
    a, b, c, d = (0, 0, 0), (10, 0, 0), (0, 10, 0), (0, 0, 10)
    tet = [(a, c, b), (a, b, d), (b, c, d), (c, a, d)]
    fin = [(a, b, (5, -5, 0))]               # a third face on edge a-b
    flat = [((50, 0, 0), (60, 0, 0), (50, 10, 0))]
    assert len(sketch_dims3d._closed_solids(tet + fin + flat)) == 5


def test_a_forward_cut_really_cuts_in_openscad(win):
    """The cut's lead called a helper the program did not define, so
    OpenSCAD left the part uncut (the user's arc and slot)."""
    import os
    import subprocess
    import tempfile
    from khervecad import analysis, engine
    m = win.model
    d = m.add_node("difference", {})
    m.add_node("cube", dict(width=20, depth=20, height=20), parent=d)
    e = m.add_node("linear_extrude", dict(height=30), parent=d)
    m.add_node("rect", dict(x=5, y=5, width=10, height=10), parent=e)
    code = m.to_scad()
    assert "module kcad_extrude_two" in code
    binary = engine.find_openscad()
    if not binary:
        pytest.skip("no OpenSCAD")
    with tempfile.TemporaryDirectory() as t:
        src, out = os.path.join(t, "a.scad"), os.path.join(t, "a.stl")
        with open(src, "w") as fh:
            fh.write(code)
        subprocess.run([binary, "-o", out, src], capture_output=True,
                       timeout=120)
        tris = engine.parse_mesh(out)
    assert analysis.mass_properties(tris)["volume"] == pytest.approx(
        6000, abs=1)


def test_a_big_fillet_leaves_the_part_below_it_square():
    """Radius 48 must not weld the plate's corner away, 0.9 mm off."""
    from khervecad import fillet, mesh
    from khervecad.model import CadNode
    f = CadNode("fillet", "F", dict(radius=48, kind="round", detail=12,
                                    edges=[[0, 0, 55, 16, 0, 55]]))
    plate = CadNode("cube", "P", dict(width=96, depth=64, height=16))
    up = CadNode("cube", "U", dict(width=16, depth=64, height=39, z=16))
    for c in (plate, up):
        c.parent = f
        f.children.append(c)
    if not fillet.compute:
        return
    pts = {tuple(round(c, 3) for c in v)
           for t in mesh.tessellate(f, {}) for v in t[:3]}
    assert (96, 0, 16) in pts and (0, 0, 0) in pts
    tops = [p for p in pts if p[2] == 16 and p[1] < 2]
    assert all(p[1] == 0 or p[0] <= 16 for p in tops)
