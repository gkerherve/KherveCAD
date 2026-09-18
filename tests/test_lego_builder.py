"""The Lego Builder: placing, stacking, erasing and stud culling
(lego_builder.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import lego_builder as lb
from khervecad import mesh
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model(app):
    return DocumentModel()


def _extent(node):
    pts = [v for t in mesh.tessellate(node) for v in t]
    return [(round(min(p[i] for p in pts), 3),
             round(max(p[i] for p in pts), 3)) for i in range(3)]


def _top(x, y, z):
    return dict(point=[x, y, z], normal=(0.0, 0.0, 1.0))


def test_a_new_build_is_an_object_on_a_baseplate(model):
    build = lb.new_build(model)
    assert build.type == "component" and build.name == lb.BUILD_NAME
    [plate] = lb.pieces(build)
    assert lb.meta(plate)["kind"] == "Baseplate"
    assert validate(model.root) == {}


def test_a_placed_piece_renders_at_its_grid_corner(app):
    piece = lb.piece_node("Brick", 2, 4, "Red", 3, 1, 9.6)
    ext = _extent(piece)
    assert ext[0][0] == pytest.approx(24.1) and ext[1][0] == pytest.approx(8.1)
    assert ext[2][0] == pytest.approx(9.6)


def test_a_click_on_top_drops_the_piece_centred_on_that_stud(model):
    build = lb.new_build(model)
    i, j, z = lb.target(build, _top(20.0, 36.0, lb.BASEPLATE_H), None,
                        "Brick", 2, 4)
    assert (i, j) == (2, 3)           # stud (2, 4) sits in its middle
    assert z == pytest.approx(lb.BASEPLATE_H)
    build.add(lb.piece_node("Brick", 2, 4, "Red", i, j, z))
    # a 1x1 clicked over the brick rests on its top, studs and all
    i2, j2, z2 = lb.target(build, _top(20.0, 36.0, 30.0), None,
                           "Brick", 1, 1)
    assert (i2, j2) == (2, 4)
    assert z2 == pytest.approx(lb.BASEPLATE_H + lb.BRICK_H)


def test_a_click_on_a_side_sets_the_piece_beside_it(model):
    build = lb.new_build(model)
    brick = lb.piece_node("Brick", 2, 2, "Blue", 4, 4, lb.BASEPLATE_H)
    build.add(brick)
    side = dict(point=[48.0 - 0.1, 36.0, 6.0], normal=(1.0, 0.0, 0.0))
    i, j, z = lb.target(build, side, brick, "Brick", 1, 1)
    assert (i, j) == (6, 4)            # the column just past the face
    assert z == pytest.approx(lb.BASEPLATE_H)
    under = dict(point=[40.0, 40.0, lb.BASEPLATE_H],
                 normal=(0.0, 0.0, -1.0))
    assert lb.target(build, under, brick, "Brick", 1, 1) is None


def test_covered_studs_go_and_come_back(model):
    build = lb.new_build(model)
    low = lb.piece_node("Brick", 2, 2, "Blue", 0, 0, lb.BASEPLATE_H)
    build.add(low)
    lb.refresh_studs(build)
    assert len(lb.meta(low)["bare"]) == 4
    top = lb.piece_node("Plate", 1, 2, "Red", 0, 0,
                        lb.BASEPLATE_H + lb.BRICK_H)
    build.add(top)
    lb.refresh_studs(build)
    assert len(lb.meta(low)["bare"]) == 2          # one column covered
    build.remove(top)
    lb.refresh_studs(build)
    assert len(lb.meta(low)["bare"]) == 4


def test_the_panel_builds_by_clicking(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        win._confirm_discard = lambda: True
        panel = lb.open_builder(win)
        panel.go.setChecked(True)
        assert panel.build is not None and win.view3d._pick_cb is not None
        before = len(lb.pieces(panel.build))
        panel._on_pick(_top(20.0, 20.0, lb.BASEPLATE_H), None)
        assert len(lb.pieces(panel.build)) == before + 1
        assert win.view3d._pick_cb is not None      # still armed
        panel.erase_mode.setChecked(True)
        newest = lb.pieces(panel.build)[-1]
        panel._on_pick(_top(20.0, 20.0, 20.0), newest)
        assert len(lb.pieces(panel.build)) == before
        panel._on_pick(None, None)                  # Esc
        assert not panel.go.isChecked()
    finally:
        win._dirty = False
        win.close()


def test_a_library_piece_turns_about_its_own_corner(app):
    part = "Slope 45° 2 × 3"                     # 3 along X, 2 deep
    assert lb.part_shape(part) == (3, 2, lb.BRICK_H)
    for turn in range(4):
        node = lb.piece_node("Part", 0, 0, "Red", 2, 5, 0.0, part=part,
                             turn=turn)
        nx, ny, _h = lb.part_shape(part, turn)
        (x0, x1), (y0, y1), _z = _extent(node)
        # the turned footprint starts at stud (2, 5), whatever the turn
        assert (x0, y0) == pytest.approx((16.1, 40.1), abs=1e-3), turn
        assert (x1, y1) == pytest.approx((16 + nx * 8 - 0.1,
                                          40 + ny * 8 - 0.1), abs=0.05)


def test_levels_stand_on_the_baseplate_and_the_layer_greys_cells(model):
    build = lb.new_build(model)
    assert lb.level_z(build, 0) == pytest.approx(lb.BASEPLATE_H)
    z0 = lb.level_z(build, 0)
    brick = lb.piece_node("Brick", 2, 2, "Blue", 3, 3, z0)
    build.add(brick)
    # one plate up, the brick still fills its cells: greyed
    filled, support = lb.layer(build, lb.level_z(build, 1))
    assert filled[(3, 3)] == (brick, False)
    # three plates up, its top: studs to build on
    filled, support = lb.layer(build, lb.level_z(build, 3))
    assert (3, 3) not in filled and support[(4, 4)] is brick
    ok, _ = lb.can_place(build, 3, 3, 1, 1, lb.level_z(build, 1),
                         lb.PLATE_H)
    assert not ok                                   # runs into it
    ok, why = lb.can_place(build, 8, 8, 1, 1, lb.level_z(build, 3),
                           lb.PLATE_H)
    assert not ok and "hold" in why                 # in the air
    assert lb.can_place(build, 4, 4, 2, 2, lb.level_z(build, 3),
                        lb.BRICK_H)[0]              # half on the brick


def test_the_plan_places_every_kind_of_piece_level_by_level(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        win._confirm_discard = lambda: True
        panel = lb.open_builder(win)
        assert panel.select_piece("Brick")
        first = panel.place_at(2, 2)                 # starts a build
        assert first is not None and panel.build is not None
        assert panel.place_at(2, 2) is None          # taken
        panel.step_level(3)                          # a brick up
        assert panel.select_piece("Slope 45° 2 × 2")
        panel.turn()
        slope = panel.place_at(2, 2)
        assert lb.meta(slope)["turn"] == 1
        assert float(slope.params["z"]) == pytest.approx(
            lb.BASEPLATE_H + lb.BRICK_H)
        assert validate(win.model.root) == {}
        panel.plan.resize(500, 500)
        img = panel.plan.grab()                      # paints, no error
        assert not img.isNull()
        assert panel.erase_at(3, 3)
        assert slope not in lb.pieces(panel.build)
        panel.to_top()
        assert panel.level == 3
    finally:
        win._dirty = False
        win.close()
