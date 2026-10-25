"""The extra sketch tools (centre rectangle, arcs, ellipse, slot,
spline) driven with real mouse events, and their nodes round-tripping
through OpenSCAD.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import scadparse, sketch_tools as st
from khervecad.model import DocumentModel
from khervecad.view2d import SketchScene, SketchView


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def view(app):
    scene = SketchScene(DocumentModel())
    scene.snap_enabled = False
    v = SketchView(scene)
    v.resize(600, 500)
    v.show()
    v.centerOn(20, 20)
    yield v
    v.close()


def _click(view, x, y, button=Qt.LeftButton):
    QTest.mouseClick(view.viewport(), button, Qt.NoModifier,
                     view.mapFromScene(QPointF(x, y)))


def _nodes(view):
    return [n for n in view.scene().model.root.walk()
            if n is not view.scene().model.root]


def _draw(view, tool, pts):
    view.set_tool(tool)
    for x, y in pts:
        _click(view, x, y)


def _near(a, b, tol=0.3):
    return abs(a - b) < tol


def test_centre_rectangle(view):
    _draw(view, st.RECT_CENTER, [(20, 20), (30, 26)])
    (rect,) = _nodes(view)
    p = rect.params
    assert rect.type == "rect"
    assert _near(p["x"], 10) and _near(p["y"], 14)
    assert _near(p["width"], 20) and _near(p["height"], 12)


def test_centre_rectangle_by_drag(view):
    view.set_tool(st.RECT_CENTER)
    vp = view.viewport()
    QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier,
                     view.mapFromScene(QPointF(20, 20)))
    QTest.mouseMove(vp, view.mapFromScene(QPointF(30, 30)))
    QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier,
                       view.mapFromScene(QPointF(30, 30)))
    assert [n.type for n in _nodes(view)] == ["rect"]


def test_centre_arc(view):
    _draw(view, st.ARC_CENTER, [(0, 0), (20, 0), (0, 20)])
    (c,) = _nodes(view)
    assert c.type == "circle"
    assert _near(c.params["radius"], 20)
    assert _near(c.params["start_angle"], 0, 2)
    assert _near(c.params["angle"], 90, 2)


def test_three_point_arc(view):
    _draw(view, st.ARC_3PT, [(-20, 0), (20, 0), (0, 20)])
    (poly,) = _nodes(view)
    assert poly.type == "polygon"
    ox, oy = poly.params["x"], poly.params["y"]
    for px, py in poly.params["points"]:
        r = math.hypot(px + ox, py + oy)
        assert py + oy >= -0.5 and (r < 20.5)
    assert max(py + oy for _, py in poly.params["points"]) > 19


def test_ellipse(view):
    _draw(view, st.ELLIPSE, [(10, 10), (40, 20)])
    (sc,) = [n for n in _nodes(view) if n.type == "scale"]
    (circle,) = sc.children
    assert _near(sc.params["x"] * circle.params["radius"], 30)
    assert _near(circle.params["radius"], 10)
    assert _near(sc.params["x"] * circle.params["x"], 10)


def test_slot(view):
    _draw(view, st.SLOT, [(0, 0), (40, 0), (20, 5)])
    (slot,) = _nodes(view)
    assert slot.type == "line"
    assert _near(slot.params["width"], 10) and _near(slot.params["x2"], 40)


def test_spline_enter_finishes(view):
    _draw(view, st.SPLINE, [(0, 0), (30, 0), (30, 30), (0, 30)])
    assert not _nodes(view)
    QTest.keyClick(view.viewport(), Qt.Key_Return)
    (poly,) = _nodes(view)
    assert poly.type == "polygon"
    assert len(poly.params["points"]) == 4 * st.SPLINE_STEPS


def test_spline_right_click_and_escape(view):
    _draw(view, st.SPLINE, [(0, 0), (30, 0)])
    QTest.keyClick(view.viewport(), Qt.Key_Escape)
    _click(view, 10, 10, Qt.RightButton)
    assert not _nodes(view)
    _draw(view, st.SPLINE, [(0, 0), (30, 0), (15, 25)])
    _click(view, 5, 5, Qt.RightButton)
    assert [n.type for n in _nodes(view)] == ["polygon"]


def test_tool_change_drops_half_drawn(view):
    _draw(view, st.SLOT, [(0, 0), (40, 0)])
    view.set_tool(st.ELLIPSE)
    _click(view, 5, 5)
    assert not _nodes(view)
    assert not [i for i in view.scene().items() if i.zValue() >= 1e6
                and i not in view.scene()._sk_items]


@pytest.mark.parametrize("tool, pts", [
    (st.RECT_CENTER, [(20, 20), (30, 26)]),
    (st.ARC_CENTER, [(0, 0), (20, 0), (0, 20)]),
    (st.ARC_3PT, [(-20, 0), (20, 0), (0, 20)]),
    (st.ELLIPSE, [(10, 10), (40, 20)]),
    (st.SLOT, [(0, 0), (40, 0), (20, 5)]),
])
def test_round_trips_through_scad(view, tool, pts):
    _draw(view, tool, pts)
    model = view.scene().model
    code = model.to_scad()
    root, _w = scadparse.parse_scad(code)
    model2 = DocumentModel()
    model2.root = root
    assert model2.to_scad() == code


def test_geometry_refuses_degenerate():
    assert st.arc_3pt((0, 0), (10, 0), (20, 0)) is None
    assert st.slot((0, 0), (0, 0), (5, 5)) is None
    assert st.rect_center((0, 0), (0.1, 5)) is None


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    yield win
    win._dirty = False
    win.close()


def test_sketch_tab_has_create_modify_insert(window):
    from khervecad import ribbon
    keys = dict((k, panels) for k, _f, _s, panels in ribbon.TABS)["sketch"]
    assert keys == ["sketch", "sketch_shapes", "sketch_modify",
                    "sketch_constrain", "sketch_insert"]
    _t, create = ribbon.panel_actions(window, "sketch")
    data = [a.data() for a in create]
    for tool, *_ in st.TOOLS:
        assert tool in data
    _t, modify = ribbon.panel_actions(window, "sketch_modify")
    assert [a.data() for a in modify][:7] == [
        "construction", "sk_trim", "sk_extend", "sk_fillet", "sk_chamfer",
        "make_region", "offset"]
    assert "regions" not in data
    assert "make_region" in data            # among the drawing tools too
    assert {"mirror", "pattern"} <= {a.data() for a in modify}
    _t, insert = ribbon.panel_actions(window, "sketch_insert")
    assert [a.data() for a in insert] == ["import_2d"]


def test_ribbon_tool_sets_the_sketch_tool(window):
    from khervecad import ribbon
    _t, create = ribbon.panel_actions(window, "sketch")
    act = next(a for a in create if a.data() == st.SLOT)
    act.trigger()
    assert window.view2d.scene().tool == st.SLOT


def test_centre_rectangle_on_the_origin_keeps_its_centre(view):
    """Drawn from the origin, a dimension on a side resizes it about the
    origin (it used to move the corner and slide the centre away)."""
    from khervecad import sketch_constraints as sc
    _draw(view, st.RECT_CENTER, [(0, 0), (10, 6)])
    (rect,) = _nodes(view)
    model = view.scene().model
    parent = rect.parent
    sc.add(model, parent, "length", [sc.ref_of(parent, rect, "e0")], 40)
    p = rect.params
    assert _near(p["width"], 40)
    assert _near(p["x"] + p["width"] / 2, 0)
    assert _near(p["y"] + p["height"] / 2, 0)


def test_perimeter_circle_clicked_on_rectangle_sides_is_tangent(view):
    """SolidWorks' Perimeter Circle: clicks on a rectangle's top, bottom
    and right side give the circle touching all three, with Tangent
    relations (the user's video)."""
    from khervecad import sketch_tools2 as st2, sketch_constraints as sc
    _draw(view, st.RECT_CENTER, [(20, 20), (50, 30)])  # x -10..50, y 10..30
    view.set_tool(st2.CIRCLE_3PT)
    _click(view, 35, 30)     # top side
    _click(view, 35, 10)     # bottom side
    _click(view, 50, 22)     # right side
    circle = [n for n in _nodes(view) if n.type == "circle"][0]
    p = circle.params
    assert _near(p["radius"], 10) and _near(p["y"], 20) and _near(p["x"], 40)
    kinds = [r["kind"] for r in sc.rows(circle.parent)]
    assert kinds.count("tangent") == 3


def test_extrude_regions_of_a_rectangle_and_perimeter_circle(view):
    """The user's video: a rectangle with a perimeter circle at its end
    is three regions; the long part and the circle extrude into a plate
    with a round end, the far corners left out."""
    from khervecad import sketch_tools2 as st2, sketch_regions as sr
    _draw(view, st.RECT_CENTER, [(20, 20), (50, 30)])  # x -10..50, y 10..30
    view.set_tool(st2.CIRCLE_3PT)
    _click(view, 35, 30)
    _click(view, 35, 10)
    _click(view, 50, 22)
    view.set_tool(sr.REGIONS)
    scene = view.scene()
    rect = [n for n in _nodes(view) if n.type == "rect"][0]
    faces = sr.faces(sr.shapes_of(rect.parent))
    assert len(faces) == 4      # long part, circle, two far corners
    _click(view, 10, 20)        # the long part
    _click(view, 42, 20)        # the circle
    QTest.keyClick(view.viewport(), Qt.Key_Return)
    ext = [n for n in _nodes(view) if n.type == "linear_extrude"]
    assert len(ext) == 1
    reg = ext[0].children[0]
    assert reg.type == "regions" and rect.parent is reg
    from khervecad import regions2d
    pts = [p for loop in regions2d.outlines(reg) for p in loop]
    xs = [p[0] for p in pts]
    assert _near(max(xs), 50) and _near(min(xs), -10)
    # the far corners are left out: no point at the rectangle's corner
    assert not any(_near(p[0], 50) and _near(p[1], 30) for p in pts)


def test_perimeter_circle_lights_the_sides_it_picks(view):
    """Each side clicked stays lit until the circle is made."""
    from khervecad import sketch_tools2 as st2
    _draw(view, st.RECT_CENTER, [(20, 20), (50, 30)])
    view.set_tool(st2.CIRCLE_3PT)
    scene = view.scene()
    _click(view, 35, 30)
    _click(view, 35, 10)
    assert len(scene._line_marks) == 2
    _click(view, 50, 22)
    assert scene._line_marks == []


def test_perimeter_circle_shows_no_circle_before_the_third_click():
    from khervecad import sketch_tools2 as st2
    assert st2.outline(st2.CIRCLE_3PT, [(0, 0), (10, 0), (5, 5)]) == []


def test_extrude_regions_picked_on_the_3d_view(window):
    """The 3D view: each region under a click is kept, Esc extrudes."""
    from khervecad import sketch_regions as sr
    m = window.model
    obj = m.add_node("union", {}, name="Plate sketch")
    m.add_node("rect", dict(x=-10, y=10, width=60, height=20), parent=obj)
    m.add_node("circle", dict(x=40, y=20, radius=10), parent=obj)
    QApplication.processEvents()
    calls = []
    window.view3d.start_pick = lambda cb, **k: calls.append((cb, k))
    assert sr.start_3d(window, obj)
    cb, k = calls[-1]
    keys = [key for key, _t in k["groups"]]
    assert len(keys) == 4
    faces = sr.faces(sr.shapes_of(obj))
    long_part = sr.face_at(faces, (0, 20))
    circle = sr.face_at(faces, (42, 20))
    cb({"kind": "face"}, long_part)
    cb({"kind": "face"}, circle)
    cb(None, None)
    ext = [n for n in obj.children if n.type == "linear_extrude"]
    assert len(ext) == 1
    reg = ext[0].children[0]
    assert {n.type for n in reg.children} == {"rect", "circle"}


def test_extruded_boss_on_overlapping_shapes_picks_regions(window):
    """SolidWorks' Selected Contours: Extruded Boss on a rectangle with a
    circle on it asks for the regions; a lone shape extrudes at once."""
    m = window.model
    obj = m.add_node("union", {}, name="Plate sketch")
    rect = m.add_node("rect", dict(x=-10, y=10, width=60, height=20),
                      parent=obj)
    m.add_node("circle", dict(x=40, y=20, radius=10), parent=obj)
    lone = m.add_node("rect", dict(x=0, y=0, width=5, height=5))
    QApplication.processEvents()
    calls = []
    window.view3d.start_pick = lambda cb, **k: calls.append(k)
    window.builder.active_tree().select_nodes([rect])
    window._apply_operation("linear_extrude")
    assert calls and "Selected Contours" in calls[-1]["banner"]
    assert not any(n.type == "linear_extrude" for n in m.root.walk())
    calls.clear()
    window.builder.active_tree().select_nodes([lone])
    window._apply_operation("linear_extrude")
    assert not calls
    assert lone.parent.type == "linear_extrude"


def test_region_edges_are_drawn_on_the_3d_view(window):
    """While the regions are picked, every region's edges are drawn —
    the circle's arc across the rectangle shows where they split."""
    from khervecad import sketch_regions as sr
    m = window.model
    obj = m.add_node("union", {}, name="Plate sketch")
    m.add_node("rect", dict(x=-10, y=10, width=60, height=20), parent=obj)
    m.add_node("circle", dict(x=40, y=20, radius=10), parent=obj)
    QApplication.processEvents()
    assert sr.start_3d(window, obj)
    view = window.view3d
    assert len(view.pick_lines) >= 4
    view.resize(400, 300)
    view.repaint()                      # draws them, no error
    view.cancel_pick()
    assert view.pick_lines == []


def test_regions_extrude_follows_its_sketch(window):
    """Extrude → Regions → the rectangle and circle, the Smart Dimension
    on Regions: changing it reshapes the extruded outline, and the whole
    thing round-trips through OpenSCAD code."""
    from khervecad import sketch_regions as sr, regions2d
    from khervecad import sketch_constraints as sc, scadparse
    m = window.model
    obj = m.add_node("union", {}, name="Plate sketch")
    rect = m.add_node("rect", dict(x=-10, y=10, width=60, height=20),
                      parent=obj)
    circle = m.add_node("circle", dict(x=40, y=20, radius=10), parent=obj)
    sc.add(m, obj, "length", [sc.ref_of(obj, rect, "e0")], 60)
    faces = sr.faces(sr.shapes_of(obj))
    picked = [sr.face_at(faces, (0, 20)), sr.face_at(faces, (42, 20))]
    ext = sr.extrude(m, obj, faces, picked, hide=[rect, circle])
    reg = ext.children[0]
    assert rect.parent is reg and circle.parent is reg
    assert [r["kind"] for r in sc.rows(reg)] == ["length"]
    assert not sc.rows(obj)

    def max_x():
        return max(p[0] for loop in regions2d.outlines(reg) for p in loop)
    assert max_x() == pytest.approx(50, abs=0.1)
    # the dimension grows the rectangle; the circle rides on its end
    sc.set_value(m, reg, 0, 90)
    circle.params["x"] = 70
    assert max_x() == pytest.approx(80, abs=0.1)
    code = m.to_scad()
    assert "kcad_regions(" in code
    root, _w = scadparse.parse_scad(code)
    back = [n for n in root.walk() if n.type == "regions"]
    assert back and {c.type for c in back[0].children} >= {"rect", "circle"}


def test_sketch_dimensions_are_drawn_on_the_3d_view(window):
    """An Object's sketch dimensions show on its instances in 3D."""
    from khervecad import sketch_constraints as sc, sketch_dims3d as d3
    m = window.model
    obj = m.add_node("component", {}, name="Plate")
    obj.visible = False                     # a definition
    rect = m.add_node("rect", dict(x=-59, y=-22, width=118, height=44),
                      parent=obj)
    sc.add(m, obj, "length", [sc.ref_of(obj, rect, "e0")], 118)
    m.add_instance(obj)
    placed = d3.placements(window)
    assert placed and placed[0][0] is obj
    from PyQt5.QtGui import QImage, QPainter
    img = QImage(400, 300, QImage.Format_ARGB32)
    p = QPainter(img)
    d3.paint(window, p, lambda v: (200 + v[0], 150 - v[1], 1.0))
    p.end()
    assert d3._local(obj, sc.rows(obj)[0])[0] == "linear"


def test_create_region_makes_a_regions_node_without_extruding(view):
    from khervecad import sketch_tools2 as st2, sketch_regions as sr
    _draw(view, st.RECT_CENTER, [(20, 20), (50, 30)])
    view.set_tool(st2.CIRCLE_3PT)
    _click(view, 35, 30)
    _click(view, 35, 10)
    _click(view, 50, 22)
    view.set_tool(sr.MAKE)
    _click(view, 10, 20)
    _click(view, 42, 20)
    QTest.keyClick(view.viewport(), Qt.Key_Return)
    types = [n.type for n in _nodes(view)]
    assert "regions" in types and "linear_extrude" not in types


def test_a_dimension_typed_in_the_3d_view_drives_the_sketch(window):
    from khervecad import sketch_constraints as sc, sketch_dims3d as d3
    from PyQt5.QtCore import QRectF
    m = window.model
    obj = m.add_node("union", {}, name="Plate")
    rect = m.add_node("rect", dict(x=0, y=0, width=50, height=20),
                      parent=obj)
    sc.add(m, obj, "length", [sc.ref_of(obj, rect, "e0")], 50)
    window._dims3d_hits = [(QRectF(10, 10, 40, 16), obj, 0)]
    from PyQt5.QtCore import QPoint
    assert d3.press(window, QPoint(20, 15))
    assert d3.release(window, QPoint(20, 15))     # a click: type
    box = window.view3d._dim3d_editor
    box.setText("75")
    box.editingFinished.emit()
    assert rect.params["width"] == pytest.approx(75, abs=1e-3)
    assert not d3.press(window, QPoint(300, 300))


def test_construction_with_nothing_selected_is_a_click_tool(view):
    """The user: Construction did nothing. Clicked on a shape it now
    switches it to construction and back."""
    from khervecad import sketch_tools2 as st2
    _draw(view, st.RECT_CENTER, [(20, 20), (50, 30)])
    rect = [n for n in _nodes(view) if n.type == "rect"][0]
    view.set_tool(st2.PICK_CONSTRUCTION)
    _click(view, 20, 30)                    # on its top side
    assert rect.params.get("modifier") == "%"
    _click(view, 20, 30)
    assert rect.params.get("modifier", "") == ""


def test_extruded_cut_cuts_a_face_sketch_into_its_part(window):
    """Extruded Cut: a circle sketched on a block's top face (Sketch on
    Face's Group) is cut into the block, its dimension kept."""
    from khervecad import cut_feature, face_sketch
    from khervecad import sketch_constraints as sc
    m = window.model
    block = m.add_node("cube", dict(width=40, depth=40, height=20))
    group = m.add_node("union", dict(x=20, y=20, z=20))
    group.params[face_sketch.KEY] = True
    circle = m.add_node("circle", dict(x=0, y=0, radius=5), parent=group)
    sc.add(m, group, "diameter", [sc.ref_of(group, circle, "o")], 10)
    group.params[cut_feature.KEY] = "extruded_cut"
    window._cut_parts = {id(group): block}
    diff = cut_feature.finish(window, group)
    assert diff is not None and diff.type == "difference"
    assert diff.children[0] is block and diff.children[1] is group
    ext = [n for n in group.walk() if n.type == "linear_extrude"][0]
    assert ext.parent is group and ext.params.get("reverse")
    assert not ext.params.get("extent")       # blind: its depth is yours
    assert group.name == "Cut sketch"
    # a depth typed stays; one typed under Through All switches it off
    m.set_param(ext, "height", 6.0)
    window._model_edited()
    assert ext.params["height"] == 6.0
    ext.params["extent"] = "through_all"
    m.set_param(ext, "height", 7.0)
    window._model_edited()
    assert ext.params["height"] == 7.0 and not ext.params.get("extent")
    # the code writes the reversed extrude, and reads it back as one node
    from khervecad import scadparse
    code = m.to_scad()
    assert "kcad_extrude_reverse(" in code
    root, _w = scadparse.parse_scad(code)
    back = [n for n in root.walk() if n.type == "linear_extrude"]
    assert back and back[0].params.get("reverse")
    assert back[0].params["height"] == 7.0
    # the dimension went into the extrude with the circle, still driving
    sc.set_value(m, ext, 0, 16)
    assert circle.params["radius"] == pytest.approx(8, abs=1e-3)


def test_extruded_cut_reaches_a_part_nested_in_an_object(window):
    """The face sketch sits in the Object; the block is two levels down
    under a moved group: the cut wraps the block, the sketch carried
    into its frame, and lands where it was drawn."""
    from khervecad import cut_feature, face_sketch, mesh
    m = window.model
    obj = m.add_node("component", {}, name="Part")
    inner = m.add_node("union", dict(x=100, y=0, z=0), parent=obj)
    block = m.add_node("cube", dict(width=40, depth=40, height=20), parent=inner)
    group = m.add_node("union", dict(x=120, y=20, z=20), parent=obj)
    group.params[face_sketch.KEY] = True
    m.add_node("circle", dict(x=0, y=0, radius=5), parent=group)
    group.params[cut_feature.KEY] = "extruded_cut"
    window._cut_parts = {id(group): block}
    diff = cut_feature.finish(window, group)
    assert diff is not None and diff.parent is inner
    assert diff.children[0] is block
    frame = diff.children[1]
    assert frame.type == "multmatrix" and group.parent is frame
    # the circle's centre, in the block's frame, is (20, 20): the middle
    # of its top, where it was drawn on the face
    M = frame.params["matrix"]
    g = mesh.node_matrix(group, {})
    at = [sum(M[r][k] * g[k][3] for k in range(4)) for r in range(3)]
    assert at[0] == pytest.approx(20) and at[1] == pytest.approx(20)


def test_the_face_sketched_on_shows_with_its_arc_centre(window):
    """The user's plate (a rectangle with a round end): sketching on its
    top face shows the face's outline in the sketch, and the cursor
    snaps to the round end's centre — where the slot starts."""
    from khervecad import sketch_regions as sr, face_sketch
    from PyQt5.QtCore import QPointF
    m = window.model
    obj = m.add_node("union", {}, name="Plate")
    rect = m.add_node("rect", dict(x=-59, y=-22, width=118, height=44),
                      parent=obj)
    circle = m.add_node("circle", dict(x=37, y=0, radius=22), parent=obj)
    faces = sr.faces(sr.shapes_of(obj))
    sr.extrude(m, obj, faces, [sr.face_at(faces, (0, 0)),
                               sr.face_at(faces, (45, 0))],
               hide=[rect, circle])
    QApplication.processEvents()
    face_sketch.make(window, obj, (0.0, 0.0, 10.0), (0.0, 0.0, 1.0))
    scene = window.view2d.scene()
    info = scene.face_outline
    assert info and info["segments"]
    xs = [p[0] for s in info["segments"] for p in s]
    assert max(xs) == pytest.approx(59, abs=0.5)
    assert min(xs) == pytest.approx(-59, abs=0.5)
    centres = [(x, y) for x, y, k in info["points"] if k == "centre"]
    assert any(abs(x - 37) < 0.5 and abs(y) < 0.5 for x, y in centres)
    hit = scene.snap(QPointF(37.3, 0.4))
    assert abs(hit.x() - 37) < 0.5 and abs(hit.y()) < 0.5
    window.view2d.viewport().repaint()          # draws, no error
    face_sketch.close(window)
    assert scene.face_outline is None


def test_a_cut_sketch_opens_again_with_its_face(window):
    """Double-click the slot of a cut in the tree: its face sketch opens
    again, showing the face's outline, to change its dimensions."""
    from khervecad import cut_feature, face_sketch
    m = window.model
    block = m.add_node("cube", dict(width=40, depth=40, height=20))
    group = m.add_node("union", dict(x=20, y=20, z=20))
    group.params[face_sketch.KEY] = True
    line = m.add_node("line", dict(x1=-5, y1=0, x2=5, y2=0, width=4),
                      parent=group)
    group.params[cut_feature.KEY] = "extruded_cut"
    window._cut_parts = {id(group): block}
    diff = cut_feature.finish(window, group)
    assert diff is not None
    QApplication.processEvents()
    tree = window.builder.tree
    tree.rebuild()
    item = tree._item_of(line)
    assert item is not None
    tree._double_clicked(item, 0)
    QApplication.processEvents()
    assert window._face_sketch is group
    info = window.view2d.scene().face_outline
    assert info and len(info["segments"]) >= 4     # the block's top
    face_sketch.close(window)


def test_create_region_leads_the_drawing_tools(window):
    from khervecad import ribbon
    data = [a.data() for a in ribbon.panel_actions(window, "sketch")[1]]
    first_tool = next(d for d in data
                      if d not in ("create_sketch", "con_dimension"))
    assert first_tool == "make_region"


def test_face_snaps_include_the_sketch_and_pin_what_lands_there(window):
    """On the plate's face: the rectangle's centre is a snap point too,
    and a slot drawn from the round end's centre is fixed there."""
    from khervecad import sketch_regions as sr, face_sketch
    from khervecad import sketch_constraints as sc
    m = window.model
    obj = m.add_node("union", {}, name="Plate")
    rect = m.add_node("rect", dict(x=-59, y=-22, width=118, height=44),
                      parent=obj)
    circle = m.add_node("circle", dict(x=37, y=0, radius=22), parent=obj)
    faces = sr.faces(sr.shapes_of(obj))
    sr.extrude(m, obj, faces, [sr.face_at(faces, (0, 0)),
                               sr.face_at(faces, (45, 0))],
               hide=[rect, circle])
    QApplication.processEvents()
    group = face_sketch.make(window, obj, (0.0, 0.0, 10.0),
                             (0.0, 0.0, 1.0))
    scene = window.view2d.scene()
    pts = scene.face_outline["points"]
    assert any(abs(x) < 1e-3 and abs(y) < 1e-3 and k == "centre"
               for x, y, k in pts)                   # the rectangle's
    slot = m.add_node("line", dict(x1=37, y1=0, x2=13, y2=0, width=16),
                      parent=group)
    scene.node_created.emit(slot)
    rows = sc.rows(group)
    assert [r["kind"] for r in rows] == ["fix"]
    assert rows[0]["refs"] == [sc.ref_of(group, slot, "p1")]
    face_sketch.close(window)


def test_drawing_snaps_to_the_centre_of_a_shape_already_there(view):
    m = view.scene().model
    m.add_node("circle", dict(x=30, y=10, radius=6))
    view.scene().rebuild()
    QApplication.processEvents()
    view.set_tool(st.SLOT)                      # a drawing tool
    hit = view.scene().snap(QPointF(30.4, 10.3))
    assert abs(hit.x() - 30) < 1e-6 and abs(hit.y() - 10) < 1e-6


def test_undo_in_a_face_sketch_removes_it_from_the_2d_view(window,
                                                           monkeypatch):
    """The user: undo while sketching removed things in 3D only. The
    face sketch is found again in the restored tree, so the 2D view
    drops the undone shape too."""
    from khervecad import face_sketch, model as model_mod
    from khervecad.view2d import ShapeItem
    monkeypatch.setattr(window.model, "UNDO_MERGE_S", 0.0)  # step each
    m = window.model
    block = m.add_node("cube", dict(width=40, depth=40, height=20))
    for _ in range(3):
        QApplication.processEvents()
    group = face_sketch.make(window, block, (20.0, 20.0, 20.0),
                             (0.0, 0.0, 1.0))
    for _ in range(3):
        QApplication.processEvents()
    m.add_node("circle", dict(x=0, y=0, radius=5), parent=group)
    for _ in range(3):
        QApplication.processEvents()
    scene = window.view2d.scene()

    def circles():
        return [it for it in scene.items() if isinstance(it, ShapeItem)
                and it.node.type == "circle"]
    assert circles()
    m.undo_stack.undo()
    for _ in range(5):
        QApplication.processEvents()
    assert not circles()
    assert face_sketch.current(window) is not group      # the new copy
    face_sketch.close(window)


def test_3d_dimensions_drag_out_of_the_sketch(window):
    """SolidWorks: drag a length away from the slot, swing the R8 leader
    — in the 3D view, values kept."""
    from khervecad import cut_feature, face_sketch, sketch_dims3d as d3
    from khervecad import sketch_constraints as sc
    from PyQt5.QtCore import QPoint
    m = window.model
    window.resize(1000, 700)
    window.show()
    block = m.add_node("cube", dict(width=80, depth=40, height=10))
    g = m.add_node("union", dict(x=40, y=20, z=10))
    g.params[face_sketch.KEY] = True
    slot = m.add_node("line", dict(x1=-12, y1=0, x2=12, y2=0, width=16),
                      parent=g)
    sc.add(m, g, "radius", [sc.ref_of(g, slot, "a2")], 8)
    sc.add(m, g, "length", [sc.ref_of(g, slot, "l")], 24)
    for _ in range(10):
        QApplication.processEvents()
    v = window.view3d
    v.fit()
    v.repaint()
    QApplication.processEvents()
    hits = {sc.rows(h[1])[h[2]]["kind"]: h for h in window._dims3d_hits}
    assert set(hits) == {"radius", "length"}
    for kind, key in (("length", "offset"), ("radius", "leader_at")):
        rect = hits[kind][0]
        start = rect.center().toPoint()
        assert d3.press(window, start)
        end = start + QPoint(0, -40)
        d3.move(window, end)
        assert d3.release(window, end)
        assert key in sc.rows(g)[hits[kind][2]]
    assert slot.params["width"] == pytest.approx(16)       # values kept
