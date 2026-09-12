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
