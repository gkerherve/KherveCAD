"""A face sketch shows the WHOLE face: every part lying in that plane
and touching the clicked one (2026-10-31, the user: only the clicked
part's face showed, not the block standing beside it on the same face).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtTest import QTest

from test_lever_by_mouse import win  # noqa: F401


def test_the_face_is_every_part_lying_in_it(win):
    from khervecad import face_sketch, scadparse  # noqa: F401
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)
    # a base 60 x 40 x 10 and a block standing on it, both flush with
    # the base's +x side (x = 60): that side face is one L-shaped face
    ex.execute("apply_code", {"code": (
        "cube([60, 40, 10]); // Base\n"
        "translate([40, 0, 10]) cube([20, 40, 30]); // Block\n")})
    QTest.qWait(50)
    base = next(n for n in win.model.root.walk() if "Base" in n.name)
    group = face_sketch.make(win, base, (60, 20, 5), (1, 0, 0))
    QTest.qWait(50)
    segs = win.view2d.scene().face_outline["segments"]
    world = [face_sketch.to_world(group, *p) for s in segs for p in s]
    zs = [p[2] for p in world]
    assert min(zs) == pytest.approx(0, abs=0.01)
    assert max(zs) == pytest.approx(40, abs=0.01)   # the block's too
    assert all(abs(p[0] - 60) < 0.01 for p in world)


def test_a_line_edge_to_edge_closes_with_the_model_edges(win):
    """SolidWorks' "close sketch with model edges": one line from the
    block's top corner to the base's corner makes a triangle with the
    block's side and the base's top, ready to extrude."""
    from khervecad import face_sketch, sketch_regions, sketch_section
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)
    ex.execute("apply_code", {"code": (
        "cube([60, 40, 10]); // Base\n"
        "translate([40, 20, 10]) cube([20, 20, 30]); // Block\n")})
    QTest.qWait(50)
    base = next(n for n in win.model.root.walk() if "Base" in n.name)
    group = face_sketch.make(win, base, (60, 10, 5), (1, 0, 0))
    a = face_sketch.to_local(group, (60, 20, 40))
    b = face_sketch.to_local(group, (60, 0, 10))
    win.model.add_node("line", dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1],
                                    width=0.2), parent=group)
    shapes, _ghost = sketch_section.with_section(
        win, group, sketch_regions.shapes_of(group))
    areas = sorted(cs.area() for cs, *_r in sketch_regions.faces(shapes))
    assert any(a == pytest.approx(300, rel=0.03) for a in areas), areas


def test_hovering_a_face_lights_every_part_lying_in_it(win):
    from khervecad import face_sketch, meshedit_ui
    from khervecad.mcp_tools import McpToolExecutor
    McpToolExecutor(win).execute("apply_code", {"code": (
        "cube([60, 40, 10]); // Base\n"
        "translate([40, 20, 10]) cube([20, 20, 30]); // Block\n")})
    QTest.qWait(50)
    parts = meshedit_ui._parts(win)
    base_tris = next(t for n, t in parts if "Base" in n.name)
    face = [t for t in base_tris if all(abs(v[0] - 60) < 1e-6 for v in t)]
    desc = dict(kind="face", pos=(60, 20, 5), dir=(1, 0, 0), tris=face)
    lit = face_sketch._whole_face_desc(desc, parts)["tris"]
    assert len(lit) > len(face)
    assert max(v[2] for t in lit for v in t) == pytest.approx(40)


def test_extruded_boss_on_a_lone_line_offers_the_area_it_closes(win):
    """The user's rib: Extruded Boss, click the face, draw ONE line from
    the block's corner to the plate's corner, leave the sketch. It used
    to extrude the line itself (a 0.2 mm strip); now the triangle it
    closes with the model edges is offered, and extruded when picked."""
    from khervecad import cut_feature, sketch_regions, sketch_section
    from khervecad.mcp_tools import McpToolExecutor
    McpToolExecutor(win).execute("apply_code", {"code": (
        "cube([96, 64, 16]); // Plate\n"
        "translate([16, 22, 16]) cube([40, 42, 28]); // Block\n")})
    QTest.qWait(50)
    m = win.model
    # the back face y = 64, as Sketch on Face makes it
    g = m.add_node("union", dict(x=0, y=64, z=0, rx=90, ry=0, rz=180))
    g.params["face_sketch"] = True
    g.params[cut_feature.KEY] = "extruded_boss"
    line = m.add_node("line", dict(x1=-56, y1=44, x2=-96, y2=16,
                                   width=0.2), parent=g)
    cut_feature.finish(win, g)
    cb = win.view3d._pick_cb
    assert cb is not None and line.parent is g        # not extruded
    shapes, _ghost = sketch_section.with_section(
        win, g, sketch_regions.shapes_of(g))
    areas = [f[0].area() for f in sketch_regions.faces(shapes)]
    i = next(i for i, a in enumerate(areas) if abs(a - 560) < 20)
    cb(dict(kind="face", pos=(0, 0, 0), dir=(0, 0, 1)), i)
    win.view3d._pick_cb(None, None)                    # Done
    ext = next(n for n in g.walk() if n.type == "linear_extrude")
    reg = next(n for n in ext.walk() if n.type == "regions")
    assert line in list(reg.walk())
