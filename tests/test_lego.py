"""The Lego parts of the library: sizes, dimensions, colours.

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

from khervecad import library, library_lego, mesh
from khervecad.model import CadNode, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _extent(node):
    pts = [v for t in mesh.tessellate(node) for v in t]
    return [(round(min(p[i] for p in pts), 3),
             round(max(p[i] for p in pts), 3)) for i in range(3)]


def _alone(node):
    root = CadNode("root")
    root.add(node)
    return root


LEGO = [pid for pid, spec in library.PARTS.items()
        if spec["category"] == "Lego"]


@pytest.mark.parametrize("part_id", LEGO)
def test_every_lego_part_builds_in_every_size(app, part_id):
    spec = library.PARTS[part_id]
    for size, dims in spec["sizes"].items():
        node = library.build_part(part_id, dict(dims, _size=size,
                                                _color="Yellow"))
        assert validate(_alone(node)) == {}, (part_id, size)
        assert node.name.startswith(size), node.name
        assert node.type == "color" and node.params["color"] == "#F2CD37"


def test_a_2x4_brick_has_the_real_dimensions(app):
    node = library_lego.brick(2, 4)
    # 0.1 mm short of the grid each side; 9.6 mm body + 1.8 mm studs
    assert _extent(node) == [(0.1, 15.9), (0.1, 31.9), (0.0, 11.4)]
    studs = [n for n in node.walk() if n.name == "Stud"]
    tubes = [n for n in node.walk() if n.type == "rotate_extrude"]
    assert len(studs) == 8 and len(tubes) == 3


def test_brick_underside_is_hollow_without_a_boolean(app):
    node = library_lego.brick(2, 2)
    assert not any(n.type == "difference" for n in node.walk())
    tris = mesh.tessellate(node)
    # the space between the walls and the tube is open from below
    # (the tube at the centre spans r 2.4..3.255)
    below = [v for t in tris for v in t
             if 1.7 < v[0] < 4.6 and 1.7 < v[1] < 4.6 and v[2] < 8.5]
    assert not below


def test_slope_runs_down_towards_its_facing(app):
    low_front = library_lego.slope(2, "-Y", studs=False)
    tris = mesh.tessellate(low_front)

    def top_at(y0, y1):
        return max(v[2] for t in tris for v in t if y0 <= v[1] <= y1)
    assert top_at(0.0, 0.2) == pytest.approx(1.7)     # the lip
    assert top_at(15.0, 16.0) == pytest.approx(9.6)   # the back row
    flipped = library_lego.slope(2, "+Y", studs=False)
    assert _extent(flipped) == _extent(low_front)
    tris = mesh.tessellate(flipped)
    assert max(v[2] for t in tris for v in t if v[1] > 15.8) == \
        pytest.approx(1.7)


def test_clear_colours_are_glass(app):
    node = library_lego.colour(library_lego.brick(1, 1), "Trans-clear")
    assert node.params["material"] == "Glass" and node.params["alpha"] < 1


def test_lego_parts_offer_colours_and_count_fields():
    spec = library.PARTS["lego_brick"]
    assert "Red" in spec["colors"] and "Trans-clear" in spec["colors"]
    assert {"nx", "ny"} <= library._COUNT_FIELDS
