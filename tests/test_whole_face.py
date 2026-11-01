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
    from khervecad import cut_feature, face_sketch, sketch_regions, \
        sketch_section
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
    # it FUSES with the block and the plate (it once stood 0.05 mm off
    # both, a separate solid the face then left out)
    from khervecad import mesh
    pts = [v for t in mesh.tessellate(ext, {}) for v in t]
    world = [face_sketch.to_world(g, p[0], p[1]) for p in pts]
    assert min(p[0] for p in world) < 56 - 0.01
    assert min(p[2] for p in world) < 16 - 0.01


def test_the_rib_follows_the_block_when_it_changes(win):
    """2026-11-01, the user: lines drawn to the model's corners and
    closed with its edges must move with it ("they all move together")
    — the block made narrower, the rib's corner goes with it."""
    from khervecad import (cut_feature, face_outline, face_sketch,
                           sketch_regions, sketch_section)
    from khervecad.mcp_tools import McpToolExecutor
    McpToolExecutor(win).execute("apply_code", {"code": (
        "cube([96, 64, 16]); // Plate\n"
        "translate([16, 22, 16]) cube([40, 42, 28]); // Block\n")})
    QTest.qWait(50)
    m = win.model
    plate = next(n for n in m.root.walk() if "Plate" in n.name)
    block = next(n for n in m.root.walk() if n.type == "cube"
                 and "Block" in n.name)
    g = face_sketch.make(win, plate, (80, 64, 8), (0, 1, 0))
    g.params[cut_feature.KEY] = "extruded_boss"
    a = face_sketch.to_local(g, (56, 64, 44))
    b = face_sketch.to_local(g, (96, 64, 16))
    line = m.add_node("line", dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1],
                                   width=0.2), parent=g)
    assert face_outline.pin(win.view2d.scene(), m, line) == 2
    face_sketch.close(win)
    QTest.qWait(50)
    shapes, _ghost = sketch_section.with_section(
        win, g, sketch_regions.shapes_of(g))
    areas = [f[0].area() for f in sketch_regions.faces(shapes)]
    i = next(i for i, ar in enumerate(areas) if abs(ar - 560) < 20)
    win.view3d._pick_cb(dict(kind="face"), i)
    win.view3d._pick_cb(None, None)
    # the block 10 narrower: its top corner moves from x 56 to 46
    m.set_param(block, "width", 30)
    QTest.qWait(50)
    p1 = face_sketch.to_world(g, line.params["x1"], line.params["y1"])
    assert p1[0] == pytest.approx(46, abs=0.01)
    assert p1[2] == pytest.approx(44, abs=0.01)
    p2 = face_sketch.to_world(g, line.params["x2"], line.params["y2"])
    assert (p2[0], p2[2]) == (pytest.approx(96, abs=0.01),
                              pytest.approx(16, abs=0.01))
    from khervecad import mesh
    ext = next(n for n in g.walk() if n.type == "linear_extrude")
    xs = [face_sketch.to_world(g, v[0], v[1])[0]
          for t in mesh.tessellate(ext, {}) for v in t]
    assert 45.8 < min(xs) < 46 - 0.01      # the solid too, fused into it


def test_the_model_edges_are_never_picked_or_dragged(win):
    """The kept outline is "Model edges", locked in the 2D view (the
    user dragged the "Part section" trying to make a region)."""
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QGraphicsItem
    from khervecad import sketch_section
    m = win.model
    poly = m.add_node("polygon", dict(points=[[0, 0], [10, 0], [0, 10]]),
                      name=sketch_section.NAME)
    assert poly.name == "Model edges" and sketch_section.is_section(poly)
    scene = win.view2d.scene()
    scene._rebuild_items()
    item = next(i for i in scene._items.values() if i.node is poly)
    assert not item.flags() & QGraphicsItem.ItemIsMovable
    assert not item.flags() & QGraphicsItem.ItemIsSelectable
    assert item.acceptedMouseButtons() == Qt.NoButton


def test_a_face_sketch_shows_the_other_sketches_on_that_face(win):
    """2026-11-01, the user: on any face, see the constraints of what is
    there — not just its contour. A sketch on the plate's top holding a
    40 wide rectangle: a new sketch on that face shows the 40, one on
    the plate's side does not."""
    from PyQt5.QtGui import QImage, QPainter
    from khervecad import face_sketch, sketch_dims_face
    from khervecad import sketch_constraints as sc
    from khervecad.mcp_tools import McpToolExecutor
    McpToolExecutor(win).execute("apply_code", {"code":
                                 "cube([96, 64, 10]); // Plate\n"})
    QTest.qWait(50)
    m = win.model
    plate = next(n for n in m.root.walk() if "Plate" in n.name)
    first = face_sketch.make(win, plate, (50, 30, 10), (0, 0, 1))
    rect = m.add_node("rect", dict(x=10, y=10, width=40, height=20),
                      parent=first)
    sc.add(m, first, "length", [sc.ref_of(first, rect, "e0")])
    face_sketch.close(win)
    QTest.qWait(50)

    def drawn():
        img = QImage(800, 600, QImage.Format_ARGB32)
        p = QPainter(img)
        try:
            return sketch_dims_face.paint(win.view2d, p)
        finally:
            p.end()
    face_sketch.make(win, plate, (70, 50, 10), (0, 0, 1))
    QTest.qWait(50)
    assert any(t.startswith("40") for t in drawn())
    face_sketch.close(win)
    face_sketch.make(win, plate, (96, 30, 5), (1, 0, 0))
    QTest.qWait(50)
    assert not any(t.startswith("40") for t in drawn())


def test_a_selected_sketch_shape_shows_as_its_outline_in_3d(win):
    """2026-11-01, the user: each tree step as itself in 3D — a selected
    rectangle is its outline on its plane, not a filled patch; its
    extrude is the solid."""
    m = win.model
    rot = m.add_node("rotate", dict(x=90, y=0, z=0))
    ext = m.add_node("linear_extrude", dict(height=10), parent=rot)
    rect = m.add_node("rect", dict(x=0, y=0, width=30, height=20),
                      parent=ext)
    QTest.qWait(50)
    win.builder.active_tree().select_nodes([rect])
    QTest.qWait(50)
    lines = win.view3d.selection_lines
    assert len(lines) == 1
    assert all(abs(p[1]) < 1e-6 for p in lines[0])       # on y = 0 (XZ)
    assert max(p[2] for p in lines[0]) == pytest.approx(20)
    assert not win._highlight_tris()                     # no fill
    win.builder.active_tree().select_nodes([ext])
    QTest.qWait(50)
    assert win.view3d.selection_lines == [] and win._highlight_tris()


def test_a_cut_centred_on_an_edge_middle_stays_centred(win):
    """2026-11-01, the user: a circle put at the middle of the block's
    top edge, then cut, must stay in the middle when the block's width
    changes."""
    from khervecad import face_outline, face_sketch
    from khervecad.mcp_tools import McpToolExecutor
    from khervecad import sketch_constraints as sc
    McpToolExecutor(win).execute("apply_code", {"code":
                                 "cube([40, 30, 20]); // Block\n"})
    QTest.qWait(50)
    m = win.model
    block = next(n for n in m.root.walk() if n.type == "cube")
    g = face_sketch.make(win, block, (20, 15, 20), (0, 0, 1))
    c = face_sketch.to_local(g, (20, 0, 20))       # the front edge's middle
    circle = m.add_node("circle", dict(x=c[0], y=c[1], radius=6), parent=g)
    assert face_outline.pin(win.view2d.scene(), m, circle) == 1
    row = sc.rows(g)[-1]
    assert row["model"] == "mid"
    face_sketch.close(win)
    m.wrap_nodes([circle], "linear_extrude")
    top = block
    while top.parent is not m.root:
        top = top.parent
    m.wrap_nodes([top, g], "difference")
    QTest.qWait(50)
    m.set_param(block, "width", 60)
    QTest.qWait(50)
    w = face_sketch.to_world(g, circle.params["x"], circle.params["y"])
    assert w[0] == pytest.approx(30, abs=0.01) and w[1] == pytest.approx(0)


def test_a_corner_a_cut_eats_leaves_the_point_where_it_was(win):
    """The user's block made 30 wide: its pipe cut (x 24..48) eats the
    top corner the rib was drawn to. The rib's end must not jump to a
    far corner of the same shape; at 35 wide the corner is back."""
    from khervecad import (cut_feature, face_outline, face_sketch,
                           sketch_regions, sketch_section)
    from khervecad.mcp_tools import McpToolExecutor
    McpToolExecutor(win).execute("apply_code", {"code": (
        "cube([96, 64, 16]); // Plate\n"
        "difference() {\n"
        "  translate([16, 22, 16]) cube([40, 42, 28]); // Block\n"
        "  translate([36, 0, 44]) rotate([-90, 0, 0])"
        " cylinder(r = 12, h = 80); // Pipe\n"
        "}\n")})
    QTest.qWait(50)
    m = win.model
    plate = next(n for n in m.root.walk() if "Plate" in n.name)
    block = next(n for n in m.root.walk() if n.type == "cube"
                 and "Block" in n.name)
    g = face_sketch.make(win, plate, (80, 64, 8), (0, 1, 0))
    g.params[cut_feature.KEY] = "extruded_boss"
    a = face_sketch.to_local(g, (56, 64, 44))
    b = face_sketch.to_local(g, (96, 64, 16))
    line = m.add_node("line", dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1],
                                   width=0.2), parent=g)
    assert face_outline.pin(win.view2d.scene(), m, line) == 2
    face_sketch.close(win)
    QTest.qWait(50)
    shapes, _ghost = sketch_section.with_section(
        win, g, sketch_regions.shapes_of(g))
    areas = [f[0].area() for f in sketch_regions.faces(shapes)]
    i = next(i for i, ar in enumerate(areas) if abs(ar - 560) < 30)
    win.view3d._pick_cb(dict(kind="face"), i)
    win.view3d._pick_cb(None, None)

    def end():
        return face_sketch.to_world(g, line.params["x1"],
                                    line.params["y1"])
    m.set_param(block, "width", 30)
    QTest.qWait(50)
    assert end()[0] == pytest.approx(56, abs=0.01)     # stayed
    assert end()[2] == pytest.approx(44, abs=0.01)
    m.set_param(block, "width", 35)
    QTest.qWait(50)
    assert end()[0] == pytest.approx(51, abs=0.01)     # the corner again


def test_a_plain_fix_on_an_edge_middle_follows_the_model(win):
    """2026-11-01, the user's own file: the circle at the middle of the
    block's top edge carried a plain Fix (drawn before sketches followed
    the model), so narrowing the block left it behind. A fix sitting on
    a model corner or edge middle is adopted as a model reference, and
    the outline is the body UNCUT (the cut used to take the middle away)."""
    from khervecad import face_sketch, model_refs
    from khervecad.mcp_tools import McpToolExecutor
    from khervecad import sketch_constraints as sc
    McpToolExecutor(win).execute("apply_code", {"code":
                                 "cube([40, 30, 20]); // Block\n"})
    QTest.qWait(50)
    m = win.model
    block = next(n for n in m.root.walk() if n.type == "cube")
    g = face_sketch.make(win, block, (20, 15, 20), (0, 0, 1))
    c = face_sketch.to_local(g, (20, 0, 20))
    circle = m.add_node("circle", dict(x=c[0], y=c[1], radius=6), parent=g)
    sc.add(m, g, "fix", [sc.ref_of(g, circle, "c")])   # plain, as drawn
    face_sketch.close(win)
    m.wrap_nodes([circle], "linear_extrude")
    top = block
    while top.parent is not m.root:
        top = top.parent
    m.wrap_nodes([top, g], "difference")
    QTest.qWait(50)
    model_refs.adopt(win)
    assert any(r.get("model") == "mid" for n in g.walk() for r in sc.rows(n))
    m.set_param(block, "width", 60)
    QTest.qWait(50)
    w = face_sketch.to_world(g, circle.params["x"], circle.params["y"])
    assert w[0] == pytest.approx(30, abs=0.01) and w[1] == pytest.approx(0)


def test_an_on_edge_row_off_its_edge_is_repaired():
    """The user's block corner had its On Edge moved onto the plate's
    edge 16 mm away, so every dimension "could not hold": the edge is put
    back through the point, same direction."""
    from khervecad.model import CadNode
    from khervecad import model_refs
    cont = CadNode("linear_extrude", "E")
    rect = CadNode("rect", "R")
    rect.params.update(x=16.0, y=22.0, width=40.0, height=42.0)
    cont.add_child(rect) if hasattr(cont, "add_child") else (
        cont.children.append(rect), setattr(rect, "parent", cont))
    cont.params["constraints"] = [{"kind": "on_edge", "refs": ["0.v0"],
                                   "edge": [0.0, 64.0, 0.0, 0.0]}]
    assert model_refs._repair(cont) == 1
    e = cont.params["constraints"][0]["edge"]
    assert e[0] == pytest.approx(16) and e[2] == pytest.approx(16)


def test_on_outline_needs_the_edge_on_the_model():
    from khervecad import model_refs
    segs = [((0, 0), (96, 0)), ((96, 0), (96, 64)), ((96, 64), (0, 64)),
            ((0, 64), (0, 0))]
    assert model_refs._on_outline(segs, [0, 64, 0, 0])
    assert not model_refs._on_outline(segs, [16, 0, 16, 64])


def test_a_slot_on_a_face_is_cut_whole_not_clipped_to_the_face(win):
    """2026-11-01, the user's slot on the rib's slope, drawn from the
    face's edge: it was split by the model's edges and its round end,
    outside the face, never cut. A slot is a closed contour: no regions."""
    from khervecad import face_sketch, sketch_regions
    from khervecad.mcp_tools import McpToolExecutor
    McpToolExecutor(win).execute("apply_code", {"code":
                                 "cube([40, 30, 20]); // Block\n"})
    QTest.qWait(50)
    m = win.model
    block = next(n for n in m.root.walk() if n.type == "cube")
    g = face_sketch.make(win, block, (20, 15, 20), (0, 0, 1))
    a = face_sketch.to_local(g, (40, 15, 20))
    b = face_sketch.to_local(g, (30, 15, 20))
    m.add_node("line", dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1], width=6,
                            slot=True), parent=g)
    assert sketch_regions.overlap_container(win, []) is None


def test_deleting_a_cuts_sketch_unwraps_its_difference(win):
    """The user's slot sketch deleted: the Difference and Body the cut
    made went too, so nothing is left cutting nothing."""
    from khervecad import delete_ui
    from khervecad.extrude_panel import CUT_KEY
    from khervecad.mcp_tools import McpToolExecutor
    McpToolExecutor(win).execute("apply_code", {"code":
                                 "cube([40, 30, 20]); // Block\n"})
    QTest.qWait(50)
    m = win.model
    block = next(n for n in m.root.walk() if n.type == "cube")
    top = block
    while top.parent is not m.root:
        top = top.parent
    body = m.wrap_nodes([top], "union")
    body = body if body is not None else top.parent
    m.rename(body, "Body")
    sk = m.add_node("cube", dict(size=5), parent=m.root)
    d = m.wrap_nodes([body, sk], "difference")
    d = d if d is not None else body.parent
    d.params[CUT_KEY] = True
    delete_ui.delete_nodes(None, m, [sk])
    assert not any(n.type == "difference" or n.name == "Body"
                   for n in m.root.walk())
    assert block.parent is not None


def test_a_later_cut_stays_out_of_an_earlier_features_section(win):
    """The user's slot cut in the rib: the rib's Model edges took the
    slot's tool in as well and the rib lost a rectangle right through."""
    from khervecad import sketch_section
    m = win.model
    block = m.add_node("cube", dict(size=[40, 30, 20]))
    sketch = m.add_node("union", {})
    tool = m.add_node("cube", dict(size=[4, 4, 60]))
    QTest.qWait(30)
    before = sketch_section.built_before(win, sketch)
    assert before
    body = m.wrap_nodes([block, sketch], "union")
    body = body if body is not None else block.parent
    d = m.wrap_nodes([body, tool], "difference")
    assert d is not None or body.parent.type == "difference"
    after = sketch_section.built_before(win, sketch)
    assert sorted(map(str, after)) == sorted(map(str, before))
