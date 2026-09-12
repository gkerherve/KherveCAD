"""Converting objects to Lego and Lego back to one solid (legoize.py,
lego_convert.py).

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

from khervecad import legoize, library, mesh
from khervecad.model import CadNode, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _split(node):
    colored = mesh.tessellate_colored(node)
    return [t for t, _c in colored], [c for _t, c in colored]


def _cube(w, d, h, x=0.0, y=0.0, z=0.0, colour=None):
    node = CadNode("cube", "Cube", dict(x=x, y=y, z=z, width=w, depth=d,
                                        height=h, center=False))
    if colour is None:
        return node
    wrap = CadNode("color", "Colour", dict(color=colour, alpha=1.0))
    wrap.add(node)
    return wrap


def test_nearest_colour_matches_the_lego_palette():
    assert legoize.nearest_colour(("#c81a0a", 1.0)) == "Red"
    assert legoize.nearest_colour(("#0055bf", 1.0)) == "Blue"
    assert legoize.nearest_colour(("#aeefec", 0.5)) == "Trans-light blue"
    assert legoize.nearest_colour(None) == legoize.DEFAULT_COLOUR


def test_a_box_becomes_exactly_its_bricks(app):
    group = CadNode("union", "Box")
    group.add(_cube(48, 32, 57.6, colour="#0055BF"))
    lego, info = legoize.to_lego(*_split(group), studs_across=6)
    assert info["studs"] == (6, 4)
    assert info["cells"] == 6 * 4 * 6                  # 57.6 / 9.6 layers
    tints = {n.params["color"] for n in lego.walk() if n.type == "color"}
    assert tints == {"#0055BF"}
    # only the top layer shows studs
    studs = [n for n in lego.walk() if n.name == "Stud"]
    assert len(studs) == 6 * 4


def test_stacked_and_overlapping_solids_keep_their_colours(app):
    group = CadNode("union", "Stack")
    group.add(_cube(16, 16, 9.6, colour="#237841"))           # green below
    group.add(_cube(16, 16, 9.6, z=9.6, colour="#F4F4F4"))    # white on it
    group.add(_cube(8, 8, 12, x=4, y=4, z=4, colour="#237841"))  # overlaps
    cells = legoize.voxelize(*_split(group), (8, 8, 9.6), (0, 0, 0))
    assert {k for (_i, _j, k) in cells} == {0, 1}
    top = {c[0] for (_i, _j, k), c in cells.items() if k == 1}
    assert "#F4F4F4" in top


def test_a_hollow_library_brick_fuses_into_one_block(app):
    brick = library.build_part("lego_brick", dict(_size="2x4",
                                                   _color="Blue"))
    solid, info = legoize.to_solid(*_split(brick))
    cubes = [n for n in solid.walk() if n.type == "cube"]
    assert info["blocks"] == 1
    p = cubes[0].params
    assert (p["width"], p["depth"]) == (16.0, 32.0)
    assert p["height"] == pytest.approx(9.6)           # studs dropped


def test_a_set_fuses_into_few_blocks_and_no_studs(app):
    house = library.build_part("lego_set_house", {})
    solid, info = legoize.to_solid(*_split(house))
    assert validate(_root(solid)) == {}
    assert not any(n.type == "cylinder" for n in solid.walk())
    assert info["blocks"] < 400 and info["colours"] > 5
    # the walls stay white — stacked bricks no longer bleed the
    # baseplate's green up the wall
    white = [n for n in solid.walk()
             if n.type == "color" and n.name == "White"]
    assert white


def _root(node):
    root = CadNode("root")
    root.add(node)
    return root


def test_boxes_merge_greedily():
    cells = {(i, j, k): "a" for i in range(4) for j in range(3)
             for k in range(2)}
    assert legoize.boxes(cells) == [(0, 0, 0, 4, 3, 2, "a")]


def test_too_many_cells_is_refused(app):
    big = CadNode("union", "Big")
    big.add(_cube(100, 100, 100))
    with pytest.raises(ValueError):
        legoize.to_lego(*_split(big), studs_across=96, plates=True)


def test_convert_and_fuse_from_the_window(app):
    from khervecad import lego_convert
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        win._confirm_discard = lambda: True
        part = win.model.add_node("cube")
        comp = lego_convert.convert_to_lego(
            win, part, dict(studs_across=5, plates=False, colour="Red"))
        assert comp is not None and comp.type == "component"
        assert comp.params["x"] > 0                      # beside the cube
        solid = lego_convert.fuse_lego(win, comp)
        assert solid is not None
        assert not any(n.type == "cylinder" for n in solid.walk())
        win.model.undo_stack.undo()
    finally:
        win._dirty = False
        win.close()
