"""A Regions left in a sketch by a cancelled extrude hid its shapes from
the region finder (2026-11-13, the user's Exercise 10: the Ø32 circle
sat in one, so the U-shaped area round it could not be picked with the
circle as a hole). It is folded back into the sketch first.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import sketch_constraints as sc, sketch_regions
from khervecad.mainwindow import MainWindow
from khervecad.mcp_tools import McpToolExecutor

# the user's Sketch 5, as the program writes it
SKETCH = """
union() {
    hull() { translate([40, -50]) circle(d=0.2, $fn=32); translate([40, 0]) circle(d=0.2, $fn=32); };
    hull() { translate([40, 0]) circle(d=0.2, $fn=32); translate([-40, 0]) circle(d=0.2, $fn=32); };
    hull() { translate([-40, 0]) circle(d=0.2, $fn=32); translate([-40, -50]) circle(d=0.2, $fn=32); };
    kcad_arc(p1 = [-40, -50], p2 = [40, -50], bulge = 1, d = 0.2);
    kcad_regions(seeds = [[-5.3333, -50]], inside = [[0]]) {
        kcad_constraints = "[{\\"kind\\":\\"diameter\\",\\"refs\\":[\\"0.o\\"],\\"value\\":32.0}]";
        translate([0, -50]) circle(r=16, $fn=64);
    }
}
"""


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    w = MainWindow()
    McpToolExecutor(w).execute("apply_code", {"code": SKETCH})
    yield w
    w._dirty = False
    w.close()


def _sketch(win):
    return next(n for n in win.model.root.walk()
                if any(c.type == "regions" for c in n.children))


def test_the_circle_in_a_stray_regions_is_no_region_edge(win):
    cont = _sketch(win)
    reg = next(c for c in cont.children if c.type == "regions")
    assert sketch_regions.stray(reg)
    # as it was: the circle is not among the sketch's shapes
    assert not any(s.type == "circle"
                   for s in sketch_regions.shapes_of(cont))


def test_tidy_folds_it_back_and_the_hole_is_a_region(win):
    cont = _sketch(win)
    assert sketch_regions.tidy(win, cont) == 1
    assert not any(c.type == "regions" for c in cont.children)
    shapes = sketch_regions.shapes_of(cont)
    circle = next(s for s in shapes if s.type == "circle")
    # its Ø32 came along, re-indexed to where it now stands
    rows = [r for r in sc.rows(cont) if r["kind"] == "diameter"]
    assert rows and rows[0]["refs"] == [
        "%d.o" % cont.children.index(circle)]
    faces = sketch_regions.faces(shapes)
    # the U round the hole and the hole itself: the U's area is the
    # outline less the circle
    areas = sorted(f[0].area() for f in faces)
    import math
    hole = math.pi * 16 ** 2
    u = 80 * 50 + math.pi * 40 ** 2 / 2
    assert any(abs(a - hole) < 0.02 * hole for a in areas)
    assert any(abs(a - (u - hole)) < 0.02 * u for a in areas)


# ------------------------------- what left it there, and the surprise
def _block_win(app):
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    McpToolExecutor(w).execute(
        "apply_code", {"code": "cube([40, 30, 20]); // Block\n"})
    for _ in range(5):
        app.processEvents()
    return w


def test_edit_sketch_drops_a_stale_feature_mark(app):
    """A sketch still marked for a Boss / Cut (its feature cancelled)
    reopened with Edit Sketch: Exit Sketch Mode must not extrude it."""
    from khervecad import cut_feature, face_sketch, normal_to
    w = _block_win(app)
    try:
        block = next(c for c in w.model.root.children if c.visible)
        group = face_sketch.make(w, block, (20, 15, 20), (0, 0, 1),
                                 open_2d=False)
        circle = w.model.add_node("circle", {"x": 5.0, "y": 5.0,
                                             "radius": 3.0}, parent=group)
        group.params[cut_feature.KEY] = "extruded_cut"   # left behind
        normal_to.edit(w, circle)
        assert not group.params.get(cut_feature.KEY)
        face_sketch.close(w)
        assert not any(n.type == "difference" for n in w.model.root.walk())
        assert not any(n.type == "linear_extrude"
                       for n in w.model.root.walk())
    finally:
        w._dirty = False
        w.close()


def test_the_exit_button_names_the_feature_it_makes(app):
    from khervecad import cut_feature, face_sketch, sketch_mode
    w = _block_win(app)
    try:
        block = next(c for c in w.model.root.children if c.visible)
        group = face_sketch.make(w, block, (20, 15, 20), (0, 0, 1))
        cut_feature._open(w, "extruded_cut", group, block, (0, 0, 1), [],
                          False)
        text = sketch_mode.create_action(w).text()
        assert "Finish" in text and "Extruded Cut" in text
        group.params.pop(cut_feature.KEY)
        sketch_mode.sync_create(w)
        assert "Finish" not in sketch_mode.create_action(w).text()
    finally:
        w._dirty = False
        w.close()


def test_cancel_gives_a_region_pick_its_shapes_back(win):
    from khervecad import regions2d
    cont = _sketch(win)
    sketch_regions.tidy(win, cont)
    shapes = sketch_regions.shapes_of(cont)
    face_list = sketch_regions.faces(shapes)
    k = max(range(len(face_list)), key=lambda i: face_list[i][0].area())
    reg = sketch_regions.make(win.model, cont, face_list, [k], hide=shapes)
    ext = win.model.wrap_nodes([reg], "linear_extrude")
    assert reg.parent is ext and len(sketch_regions.shapes_of(cont)) == 0
    assert sketch_regions.take_back(win.model, ext)
    assert not any(n.type in ("regions", "linear_extrude")
                   for n in cont.walk())
    assert len(sketch_regions.shapes_of(cont)) == len(shapes)
    assert any(r["kind"] == "diameter" and r["value"] == 32.0
               for r in sketch_constraints_rows(cont))


def sketch_constraints_rows(cont):
    return sc.rows(cont)
