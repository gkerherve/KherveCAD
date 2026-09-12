"""Brick-built Lego models: the voxel packer, stud culling and the
Examples-menu models (examples_lego.py).

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
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import examples, examples_lego, mesh
from khervecad.model import validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def test_pack_covers_every_cell_once_with_standard_bricks():
    layer = {(i, j): "a" for i in range(7) for j in range(5)}
    layer.update({(i, 5): "b" for i in range(3)})
    for k in (0, 1):
        seen = []
        for i, j, nx, ny, value in examples_lego.pack(layer, k):
            assert tuple(sorted((nx, ny))) in examples_lego.FOOTPRINTS
            cells = [(i + a, j + b) for a in range(nx) for b in range(ny)]
            assert all(layer[c] == value for c in cells)
            seen += cells
        assert sorted(seen) == sorted(layer)            # each cell once


def test_layers_alternate_so_joints_do_not_stack():
    wall = {(i, 0): "a" for i in range(12)}
    wall.update({(0, j): "a" for j in range(1, 6)})
    assert examples_lego.pack(wall, 0) != examples_lego.pack(wall, 1)


def test_covered_studs_are_not_drawn(app):
    s = examples_lego.Scene()
    s.add("brick", 0, 0, 2, 2, 0.0, "Red", "A")
    s.add("brick", 1, 0, 1, 2, 9.6, "Blue", "B")      # covers one column
    node = s.to_node("Stack")
    studs = [n for n in node.walk() if n.name == "Stud"]
    assert len(studs) == 2 + 2                        # 2 bare below + top


LEGO_MODELS = [(label, build) for label, cat, build in examples.EXAMPLES
               if cat == "Lego"]


def test_there_are_lego_models():
    assert LEGO_MODELS


@pytest.mark.parametrize("label,build", LEGO_MODELS)
def test_lego_models_stay_light_enough_to_orbit(app, label, build):
    root = build()
    assert validate(root) == {}
    tris = mesh.tessellate(root)
    assert 1000 < len(tris) < 60000, (label, len(tris))
    # every brick, plate and tile sits on the 8 mm grid
    for n in root.walk():
        if n.type == "union" and n.name.startswith(("Brick ", "Plate ",
                                                     "Tile ")):
            body = n.children[0]
            for key in ("x", "y"):
                studs = (body.params[key] - 0.1) / 8.0
                assert studs == pytest.approx(round(studs)), n.name


# ------------------------------------------------------------ the sets

def test_every_example_model_is_a_library_set():
    from khervecad import library, library_lego_sets
    labels = {label for label, _b in LEGO_MODELS}
    assert set(library_lego_sets.SETS.values()) == labels
    for pid in library_lego_sets.SETS:
        assert library.PARTS[pid]["category"] == "Lego sets"


def test_a_set_arrives_as_one_coloured_object(app):
    from khervecad import library
    from khervecad.model import DocumentModel
    m = DocumentModel()
    node = library.build_part("lego_set_house", {})
    assert node.type == "union" and node.name == "House"
    m.root.add(node)
    comp = m.enclose_as_part(node)
    assert comp.type == "component"
    assert validate(m.root) == {}
    # several colours: never swapped for a colourless exact render
    assert len(mesh.part_colours(comp)) > 3
    assert not mesh.needs_exact(comp)
