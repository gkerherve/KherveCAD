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
    """An OPEN arc (a line with a bulge, sketch_arc), not a pie slice."""
    from khervecad import sketch_arc
    _draw(view, st.ARC_CENTER, [(0, 0), (20, 0), (0, 20)])
    (c,) = _nodes(view)
    assert c.type == "line" and sketch_arc.is_arc(c)
    g = sketch_arc.geometry(c.params["x1"], c.params["y1"], c.params["x2"],
                            c.params["y2"], c.params["bulge"])
    assert _near(g[2], 20) and _near(math.degrees(g[4]), 90, 2)


def test_three_point_arc(view):
    _draw(view, st.ARC_3PT, [(-20, 0), (20, 0), (0, 20)])
    from khervecad import sketch_arc
    (arc,) = _nodes(view)
    assert arc.type == "line" and sketch_arc.is_arc(arc)
    mx, my = sketch_arc.middle(-20, 0, 20, 0, arc.params["bulge"])
    assert _near(mx, 0, 0.1) and _near(my, 20, 0.1)


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
    made = [n for n in view.scene().model.root.walk() if n.type == "line"]
    assert made                          # an OPEN curve of arcs
    ends = {(n.params["x1"], n.params["y1"]) for n in made} | \
        {(n.params["x2"], n.params["y2"]) for n in made}
    assert (0, 0) in ends and (0, 30) in ends


def test_spline_right_click_and_escape(view):
    _draw(view, st.SPLINE, [(0, 0), (30, 0)])
    QTest.keyClick(view.viewport(), Qt.Key_Escape)
    _click(view, 10, 10, Qt.RightButton)
    assert not _nodes(view)
    _draw(view, st.SPLINE, [(0, 0), (30, 0), (15, 25)])
    _click(view, 5, 5, Qt.RightButton)
    assert any(n.type == "line" for n in view.scene().model.root.walk())


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
    assert [a.data() for a in modify][:8] == [
        "construction", "sk_trim", "sk_extend", "sk_fillet", "sk_chamfer",
        "sk_mirror", "make_region", "offset"]
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
    """An Object's sketch dimensions show in 3D in its Object tab — not
    among the assembly's parts (the user, 2026-10-28: "in assembly mode
    no dimension shown at all")."""
    from khervecad import sketch_constraints as sc, sketch_dims3d as d3
    m = window.model
    obj = m.add_node("component", {}, name="Plate")
    obj.visible = False                     # a definition
    rect = m.add_node("rect", dict(x=-59, y=-22, width=118, height=44),
                      parent=obj)
    sc.add(m, obj, "length", [sc.ref_of(obj, rect, "e0")], 118)
    m.add_instance(obj)
    assert d3.placements(window) == []          # the assembly: none
    window.builder.open_component(obj)          # its Object tab
    QApplication.processEvents()
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
    assert ext.params.get("extent") == "through_all"   # the default
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


def test_a_cuts_drag_arrow_points_into_the_part(window):
    """The user's picture: an Extruded Cut's arrow points DOWN into the
    part, and pulling it further down makes the cut deeper."""
    from khervecad import cut_feature, face_sketch, drag_feature
    from PyQt5.QtCore import QPoint, Qt
    m = window.model
    window.resize(1000, 700)
    window.show()
    block = m.add_node("cube", dict(width=40, depth=40, height=20))
    g = m.add_node("union", dict(x=20, y=20, z=20))
    g.params[face_sketch.KEY] = True
    m.add_node("circle", dict(x=0, y=0, radius=5), parent=g)
    g.params[cut_feature.KEY] = "extruded_cut"
    window._cut_parts = {id(g): block}
    diff = cut_feature.finish(window, g)
    ext = [n for n in diff.walk() if n.type == "linear_extrude"][0]
    for _ in range(5):
        QApplication.processEvents()
    v = window.view3d
    v.pitch = 30.0
    v.fit()
    drag_feature.start(window, ext, quiet=True)
    tool = v.edit_tool
    scr = tool._screen()
    assert scr is not None
    assert scr["b"][1] > scr["a"][1]            # the tip is BELOW: down

    class Ev:
        def __init__(self, x, y):
            self._p = QPoint(int(x), int(y))

        def pos(self):
            return self._p

        def button(self):
            return Qt.LeftButton

        def modifiers(self):
            return Qt.NoModifier
    a, b = scr["a"], scr["b"]
    tip = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    assert tool.mouse_press(Ev(*tip))
    before = ext.params["height"]
    tool.mouse_move(Ev(tip[0] + (b[0] - a[0]), tip[1] + (b[1] - a[1])))
    tool.mouse_release(Ev(tip[0] + (b[0] - a[0]), tip[1] + (b[1] - a[1])))
    assert ext.params["height"] > before          # deeper


def test_a_slot_is_a_slot_with_its_own_sizes(view):
    """The user: a slot is not a "Line". The Slot tool names it Slot 1;
    its Length, Radius, Width, Angle and centre are what you edit, and
    a size a Smart Dimension drives is changed through that dimension."""
    from khervecad import slot2d, sketch_constraints as sc
    _draw(view, st.SLOT, [(0, 0), (24, 0), (12, 8)])
    (slot,) = [n for n in _nodes(view) if n.type == "line"]
    assert slot2d.is_slot(slot) and slot.name == "Slot 1"
    s = slot2d.read(slot)
    assert _near(s["length"], 24) and _near(s["radius"], 8)
    m = view.scene().model
    slot2d.write(m, slot, "length", 30)
    assert _near(slot2d.read(slot)["length"], 30)
    assert _near(slot2d.read(slot)["cx"], 12)          # centre kept
    sc.add(m, slot.parent, "radius",
           [sc.ref_of(slot.parent, slot, "a2")], 8)
    slot2d.write(m, slot, "width", 20)                 # via the R
    assert _near(slot2d.read(slot)["radius"], 10)
    (radius,) = [r for r in sc.rows(slot.parent) if r["kind"] == "radius"]
    assert radius["value"] == pytest.approx(10)
    # drawn level, it stays level
    assert any(r["kind"] == "horizontal" for r in sc.rows(slot.parent))


def test_properties_shows_a_slots_sizes(window):
    from khervecad import slot2d
    m = window.model
    slot = m.add_node("line", dict(x1=0, y1=0, x2=24, y2=0, width=16))
    slot2d.mark(m, slot)
    from khervecad.properties import PropertiesPanel
    panel = window.findChild(PropertiesPanel)
    panel.set_node(slot)
    keys = set(panel._editors)
    assert {"slot:length", "slot:radius", "slot:width"} <= keys
    assert "x1" not in keys


def test_closed_lines_make_a_region_from_the_selection(window):
    """The user: lines like a polygon. Four lines joined end to end,
    selected, Create Region: a Regions node holding them, the square
    they enclose its outline."""
    from khervecad import sketch_modify, regions2d
    m = window.model
    obj = m.add_node("union", {}, name="Sketch")
    pts = [(0, 0), (30, 0), (30, 20), (0, 20)]
    lines = [m.add_node("line", dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1],
                                     width=0.4), parent=obj)
             for a, b in zip(pts, pts[1:] + pts[:1])]
    QApplication.processEvents()
    window.builder.tree.rebuild()
    window.builder.tree.select_nodes(lines)
    sketch_modify._regions(window, "make_region")
    regs = [n for n in obj.walk() if n.type == "regions"]
    assert len(regs) == 1 and all(l.parent is regs[0] for l in lines)
    loops = regions2d.outlines(regs[0])
    xs = [p[0] for lp in loops for p in lp]
    ys = [p[1] for lp in loops for p in lp]
    assert min(xs) == pytest.approx(0) and max(xs) == pytest.approx(30)
    assert min(ys) == pytest.approx(0) and max(ys) == pytest.approx(20)


def test_snap_and_pin_to_the_hidden_centres_of_a_region(view):
    """The user's plate: its rectangle and circle are hidden inside the
    Regions, yet a new shape snaps to their centres and is fixed there."""
    from khervecad import sketch_regions as sr, face_outline
    from khervecad import sketch_constraints as sc
    m = view.scene().model
    rect = m.add_node("rect", dict(x=-59, y=-22, width=118, height=44))
    circle = m.add_node("circle", dict(x=37, y=0, radius=22))
    faces = sr.faces(sr.shapes_of(m.root))
    reg = sr.make(m, m.root, faces, [sr.face_at(faces, (0, 0)),
                                     sr.face_at(faces, (45, 0))],
                  hide=[rect, circle])
    for s in (rect, circle):
        s.visible = False
    view.scene().rebuild()
    QApplication.processEvents()
    view.set_tool(st.SLOT)
    hit = view.scene().snap(QPointF(37.3, 0.4))
    assert _near(hit.x(), 37, 1e-6) and _near(hit.y(), 0, 1e-6)
    hit = view.scene().snap(QPointF(0.3, -0.2))
    assert _near(hit.x(), 0, 1e-6) and _near(hit.y(), 0, 1e-6)
    slot = m.add_node("line", dict(x1=37, y1=0, x2=13, y2=0, width=16))
    assert face_outline.pin(view.scene(), m, slot) == 1
    assert [r["kind"] for r in sc.rows(m.root)] == ["fix"]


def test_line_chain_bar_closes_a_shape_for_a_region(view):
    """The user could only end lines with the mouse: a bar offers
    Finish / Close shape / Undo line / Cancel. Close shape draws the last
    line back to the start: a closed triangle, one region."""
    from khervecad import sketch_line, sketch_regions as sr
    from khervecad.view2d import LINE
    view.set_tool(LINE)
    for x, y in ((0, 0), (40, 0), (20, 30)):
        _click(view, x, y)
    bar = view.line_bar
    assert bar.isVisible() and bar.close_btn.isEnabled()
    sketch_line.close_shape(view.scene())
    lines = [n for n in _nodes(view) if n.type == "line"]
    assert len(lines) == 3 and not bar.isVisible()
    assert len(sr.faces(lines)) == 1
    # Undo line takes the last one back mid-chain
    for x, y in ((60, 0), (90, 0), (90, 20)):
        _click(view, x, y)
    sketch_line.undo_line(view.scene())
    assert len([n for n in _nodes(view) if n.type == "line"]) == 4


def test_a_selected_cut_shows_in_red(window):
    """The user: selecting a cut (its Cut sketch, its slot or the
    Difference) shows the removed volume see-through red."""
    from khervecad import cut_feature, face_sketch, cut_ghost
    m = window.model
    block = m.add_node("cube", dict(width=60, depth=40, height=10))
    g = m.add_node("union", dict(x=30, y=20, z=10))
    g.params[face_sketch.KEY] = True
    slot = m.add_node("line", dict(x1=-10, y1=0, x2=10, y2=0, width=8),
                      parent=g)
    g.params[cut_feature.KEY] = "extruded_cut"
    window._cut_parts = {id(g): block}
    diff = cut_feature.finish(window, g)
    QApplication.processEvents()
    for chosen in (g, slot, diff):
        window.builder.tree.rebuild()
        window.builder.tree.select_nodes([chosen])
        QApplication.processEvents()
        tris = getattr(window, "_cut_ghost", [])
        assert tris, chosen.name
        xs = [v[0] for t in tris for v in t]
        zs = [v[2] for t in tris for v in t]
        assert min(xs) == pytest.approx(16, abs=0.5)   # the slot's end
        assert max(zs) >= 10 - 0.01         # Through All: past the face…
        assert min(zs) <= 0 + 0.01          # …and out of the bottom
    window.builder.tree.select_nodes([block])
    QApplication.processEvents()
    assert not window._cut_ghost


def test_extruded_cut_sketch_snaps_to_centres_origin_and_edges(window):
    """The user's own document: Object 1 > Extrude regions > Regions
    (rectangle + circle), a cut sketched on its top. Hovering with the
    Slot tool snaps — and says so — to the round end's centre, the
    rectangle's centre, the sketch origin and onto an edge."""
    from khervecad import sketch_regions as sr, face_sketch
    from khervecad.sketch_tools import SLOT
    m = window.model
    obj = m.add_node("component", {}, name="Object 1")
    obj.visible = False
    rect = m.add_node("rect", dict(x=-59, y=-22, width=118, height=44),
                      parent=obj)
    c = m.add_node("circle", dict(x=37, y=0, radius=22), parent=obj)
    f = sr.faces(sr.shapes_of(obj))
    ext = sr.extrude(m, obj, f, [sr.face_at(f, (0, 0)),
                                 sr.face_at(f, (45, 0))], hide=[rect, c])
    ext.params["height"] = 16
    window.builder.open_component(obj)
    for _ in range(5):
        QApplication.processEvents()
    face_sketch.make(window, ext, (-2.2672, 0.0, 16.0), (0.0, 0.0, 1.0))
    window._set_tool(SLOT)
    scene = window.view2d.scene()
    for at, want, kind in (((39.4, 0.3), (39.2672, 0.0), "centre"),
                           ((2.4, 0.2), (2.2672, 0.0), "centre"),
                           ((0.15, -0.1), (0.0, 0.0), "origin"),
                           ((10.0, 22.15), (10.0, 22.0), "edge")):
        hit = scene.snap(QPointF(*at))
        assert _near(hit.x(), want[0], 1e-3) and _near(hit.y(), want[1],
                                                       1e-3), (at, hit)
        assert scene._snap_hint[1] == kind
    window.view2d.viewport().repaint()          # the marker draws
    face_sketch.close(window)


def test_extruded_boss_on_the_side_face_of_a_used_sketch(window):
    """The user's plate: its Regions sketch is used by the extrude, so
    Extruded Boss/Base must not pick its regions again — it asks for a
    FACE; sketching on the plate's side and leaving makes a boss out of
    it, the Object joining them."""
    from khervecad import sketch_regions as sr, face_sketch, cut_feature
    m = window.model
    obj = m.add_node("component", {}, name="Object 1")
    rect = m.add_node("rect", dict(x=-59, y=-22, width=118, height=44),
                      parent=obj)
    c = m.add_node("circle", dict(x=37, y=0, radius=22), parent=obj)
    f = sr.faces(sr.shapes_of(obj))
    ext = sr.extrude(m, obj, f, [sr.face_at(f, (0, 0)),
                                 sr.face_at(f, (45, 0))], hide=[rect, c])
    ext.params["height"] = 16
    window.builder.open_component(obj)
    QApplication.processEvents()
    assert not sr.free_shapes(window)
    assert sr.overlap_container(window, []) is None
    calls = []
    window.view3d.start_pick = lambda cb, **k: calls.append((cb, k))
    window._apply_operation("linear_extrude")
    cb, k = calls[-1]
    assert "click the face" in k["banner"]
    # the user clicks the side (x = -59, facing -X) and draws on it
    window.view3d.cancel_pick = lambda: None
    cb({"kind": "face", "pos": (-59.0, 0.0, 8.0),
        "dir": (-1.0, 0.0, 0.0)}, ext)
    group = window._face_sketch
    m.add_node("rect", dict(x=-20, y=-8, width=40, height=30),
               parent=group)
    face_sketch.close(window)
    boss = [n for n in group.walk() if n.type == "linear_extrude"]
    assert boss and boss[0].params["height"] == cut_feature.DEPTH
    assert not boss[0].params.get("reverse")
    assert group.name == "Boss sketch" and group.parent is obj


def test_an_extruded_slot_is_not_extruded_again(window):
    """The user's empty hole: the slot's Extruded Cut had been wrapped in
    a second extrude. Extruded Boss on an already extruded or cut shape
    now refuses and says why, the tree unchanged."""
    from khervecad import cut_feature, face_sketch
    m = window.model
    block = m.add_node("cube", dict(width=60, depth=40, height=10))
    g = m.add_node("union", dict(x=30, y=20, z=10))
    g.params[face_sketch.KEY] = True
    slot = m.add_node("line", dict(x1=-10, y1=0, x2=10, y2=0, width=8),
                      parent=g)
    g.params[cut_feature.KEY] = "extruded_cut"
    window._cut_parts = {id(g): block}
    cut_feature.finish(window, g)
    ext = slot.parent
    window.builder.tree.rebuild()
    for chosen in (slot, ext):
        window.builder.tree.select_nodes([chosen])
        window._apply_operation("linear_extrude")
        assert slot.parent is ext and ext.parent is g      # unchanged
        assert "already extruded" in window.statusBar().currentMessage()


def test_a_2d_difference_still_extrudes(window):
    m = window.model
    d = m.add_node("difference", {})
    m.add_node("rect", dict(x=0, y=0, width=30, height=20), parent=d)
    m.add_node("circle", dict(x=15, y=10, radius=4), parent=d)
    window.builder.tree.rebuild()
    window.builder.tree.select_nodes([d])
    window._apply_operation("linear_extrude")
    assert d.parent.type == "linear_extrude"


def test_a_cut_starts_clean_of_an_old_selection(window):
    """The user's confusing hole sketch: the Boss sketch's rectangle,
    still selected, was drawn in the new cut sketch. Starting a cut now
    clears the selection, and a used sketch is never cut at once."""
    from khervecad import cut_feature
    m = window.model
    block = m.add_node("cube", dict(width=40, depth=40, height=10))
    boss = m.add_node("union", dict(x=0, y=0, z=10), name="Boss sketch")
    boss.params["face_sketch"] = True
    ext = m.add_node("linear_extrude", dict(height=5), parent=boss)
    r = m.add_node("rect", dict(x=0, y=0, width=10, height=10), parent=ext)
    window.builder.tree.rebuild()
    window.builder.tree.select_nodes([r])
    calls = []
    window.view3d.start_pick = lambda cb, **k: calls.append(k)
    assert cut_feature.start(window, "extruded_cut") is None
    assert calls                                    # asks for a face
    assert not window.builder.tree.selected_nodes()
    assert r.parent is ext                          # untouched


def test_a_cut_outline_has_no_seam_line():
    """A hole's round wall closes on a seam the mesh may not weld: that
    lone edge is not drawn (the user's stray red line); the rims are."""
    from khervecad import cut_ghost
    import math
    n, r, h = 32, 10.0, 12.0
    tris = []
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        if i == n - 1:
            a1 = 2 * math.pi + 1e-3         # a seam that does not meet
        p0 = (r * math.cos(a0), r * math.sin(a0))
        p1 = (r * math.cos(a1), r * math.sin(a1))
        tris.append(((*p0, 0.0), (*p1, 0.0), (*p1, h)))
        tris.append(((*p0, 0.0), (*p1, h), (*p0, h)))
        tris.append(((0.0, 0.0, 0.0), (*p1, 0.0), (*p0, 0.0)))
        tris.append(((0.0, 0.0, h), (*p0, h), (*p1, h)))
    edges = cut_ghost._edges(tris)
    vertical = [e for e in edges if abs(e[0][2] - e[1][2]) > 1e-6]
    assert not vertical                      # no seam line
    assert len(edges) >= 2 * (n - 1)          # both rims


def test_mirror_keeps_the_part_and_copies_it_about_a_plane(window):
    """SolidWorks' Mirror: the selected part is kept and a mirror copy
    added about the chosen plane — a standard one, or a picked face."""
    from khervecad import mesh
    m = window.model
    ear = m.add_node("cube", dict(x=10, y=0, z=0, width=5, depth=5,
                                  height=5))
    window.builder.tree.rebuild()
    window.builder.tree.select_nodes([ear])
    window.mirror_plane_hook = lambda: "Right Plane (YZ)"
    window._apply_operation("mirror")
    mir = ear.parent
    assert mir.type == "symmetry" and mir.name == "Mirror"
    tris = mesh.selected_world_tris(m.root, {mir.id})
    xs = sorted({round(v[0], 3) for t in tris for v in t})
    assert xs[0] == pytest.approx(-15) and xs[-1] == pytest.approx(15)
    # a face as the plane: the cube's own side at x = 15
    other = m.add_node("cube", dict(x=0, y=20, z=0, width=5, depth=5,
                                    height=5))
    window.builder.tree.rebuild()
    window.builder.tree.select_nodes([other])
    window.mirror_plane_hook = lambda: "Pick a face in the 3D view…"
    calls = []
    window.view3d.start_pick = lambda cb, **k: calls.append(cb)
    window.view3d.cancel_pick = lambda: None
    window._apply_operation("mirror")
    calls[-1]({"kind": "face", "pos": (5.0, 22.0, 2.0),
               "dir": (1.0, 0.0, 0.0)}, other)
    mir2 = other.parent
    assert mir2.type == "symmetry"
    assert (mir2.params["x"], mir2.params["cx"]) == (1.0, 5.0)


def test_mirror_with_nothing_selected_picks_parts_in_3d(window):
    m = window.model
    a = m.add_node("cube", dict(width=5, depth=5, height=5))
    window.builder.tree.rebuild()
    window.builder.tree.clearSelection()
    window.mirror_plane_hook = lambda: "Top Plane (XY)"
    calls = []
    window.view3d.start_pick = lambda cb, **k: calls.append((cb, k))
    window._apply_operation("mirror")
    cb, k = calls[-1]
    assert "click the parts to mirror" in k["banner"]
    cb({"kind": "face"}, a)                 # one part chosen
    calls[-1][0](None, None)                # Done
    assert a.parent.type == "symmetry"
    assert a.parent.params["z"] == 1.0


def test_a_mirrored_sketch_extrudes_both_halves():
    from khervecad.model import DocumentModel
    from khervecad import mesh, mirror_feature
    m = DocumentModel()
    ext = m.add_node("linear_extrude", dict(height=5))
    r = m.add_node("rect", dict(x=10, y=0, width=5, height=5), parent=ext)
    mirror_feature.apply(m, [r], (1, 0, 0))
    t = mesh.tessellate(m.root)
    xs = [v[0] for tr in t for v in tr]
    assert min(xs) == pytest.approx(-15) and max(xs) == pytest.approx(15)


def test_a_fillet_where_an_ear_meets_the_plate_adds_material():
    """The user's R2: a fillet on the line where an upright meets its
    base. The parts are merged first, so that line is an INSIDE corner
    and the fillet adds material there instead of rounding the
    upright's own bottom edge away."""
    from khervecad.model import DocumentModel
    from khervecad import fillet
    m = DocumentModel()
    grp = m.add_node("union", {})
    m.add_node("cube", dict(width=40, depth=20, height=5), parent=grp)
    m.add_node("cube", dict(x=10, y=5, z=5, width=12, depth=10,
                            height=20), parent=grp)
    f = m.wrap_nodes([grp], "fillet")
    f.params.update(radius=2.0, kind="round",
                    edges=[[10.0, 5.0, 5.0, 10.0, 15.0, 5.0]])
    res = fillet.baked(f, {})
    assert res["adds"] and not res["cuts"]


def test_two_lines_join_two_circles_into_one_region():
    """Two circles joined by two lines (a lever's outline): the waist
    between the lines is a face, so the whole outline can be extruded."""
    from khervecad.model import DocumentModel
    from khervecad import sketch_regions as R
    m = DocumentModel()
    g = m.add_node("union", {})
    m.add_node("circle", dict(x=0, y=0, radius=18.5), parent=g)
    m.add_node("circle", dict(x=0, y=40, radius=12.35), parent=g)
    m.add_node("line", dict(x1=-14.6, y1=1.2, x2=-10, y2=40.2), parent=g)
    m.add_node("line", dict(x1=14.8, y1=1.3, x2=10.6, y2=40.3), parent=g)
    f = R.faces(R.shapes_of(g))
    assert R.face_at(f, (0, 20)) is not None
    assert R.face_at(f, (-16, 25)) is None     # outside the lines: no face
    assert R.overlapping(g)
