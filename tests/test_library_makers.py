"""Vitamins (library_vitamins.py), Lego Technic and generative panels
(library_generative.py)."""

import math

import pytest

from khervecad import (analysis, library, library_generative,
                       library_vitamins, mesh)
from khervecad.model import DocumentModel, validate
from khervecad.scadparse import parse_scad

PART_IDS = sorted(list(library_vitamins.PARTS)
                  + list(library_generative.PARTS))


@pytest.mark.parametrize("part_id", PART_IDS)
def test_part_builds_valid_and_round_trips(part_id):
    model = DocumentModel()
    model.root.add(library.build_part(part_id, {}))
    assert validate(model.root) == {}
    assert mesh.tessellate(model.root)
    code = model.to_scad()
    again = DocumentModel()
    again.root, warnings = parse_scad(code)
    assert not warnings and again.to_scad() == code


def test_nema17_face_pattern():
    node = library.build_part("vit_nema", {"_size": "NEMA 17 (40 mm)"})
    holes = [n for n in node.walk() if n.type == "hole"]
    xs = sorted({round(n.parent.params["x"], 2) for n in holes})
    assert xs == [-15.5, 15.5]                       # 31 mm pattern


def test_technic_beam_pitch():
    node = library.build_part("technic_beam", {"holes": 5})
    holes = [n for n in node.walk() if n.name.startswith("Hole")]
    assert [n.params["x"] for n in holes] == [0, 8, 16, 24, 32]


def test_delaunay_and_voronoi_cover_the_panel():
    cells = library_generative.voronoi_cells(100, 70, 20, 7, 0.0)
    area = sum(abs(mesh.polygon_area(c)) for c in cells)
    assert area == pytest.approx(100 * 70, rel=1e-6)   # no gaps, no overlap
    walled = library_generative.voronoi_cells(100, 70, 20, 7, 2.0)
    assert sum(abs(mesh.polygon_area(c)) for c in walled) < area


def test_maze_is_a_spanning_tree():
    opened = library_generative.maze_walls(8, 6, 1)
    assert len(opened) == 8 * 6 - 1                   # a perfect maze


def test_hilbert_visits_every_cell_once_in_unit_steps():
    pts = library_generative.hilbert(3)
    assert len(set(pts)) == 64
    assert all(math.dist(a, b) == 1 for a, b in zip(pts, pts[1:]))
