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


def test_slopes_face_all_four_ways(app):
    for facing, lip_at in (("-X", lambda v: v[0] < 0.2),
                           ("+X", lambda v: v[0] > 15.8)):
        node = library_lego.slope(3, facing, studs=False)
        assert _extent(node) == [(0.1, 15.9), (0.1, 23.9), (0.0, 9.6)]
        tris = mesh.tessellate(node)
        assert max(v[2] for t in tris for v in t if lip_at(v)) == \
            pytest.approx(1.7)
    # stud indices count from the low-Y end whichever way it faces
    one = library_lego.slope(3, "-X", studs={0})
    top = [v for t in mesh.tessellate(one) for v in t if v[2] > 11.3]
    assert all(1.5 < v[1] < 6.5 for v in top)
    assert all(9.5 < v[0] < 14.5 for v in top)        # on the back column


def test_library_bricks_are_rounded_but_keep_their_size(app):
    plain = library_lego.brick(1, 2)
    soft = library_lego.brick(1, 2, round_=True)
    assert _extent(soft) == _extent(plain)
    pts = [v for t in mesh.tessellate(soft) for v in t]
    # no vertex on the sharp outer corner, nor on the sharp top edge
    assert min(abs(v[0] - 0.1) + abs(v[1] - 0.1) for v in pts
               if v[2] < 8.0) > 0.1
    top = [v for v in pts if abs(v[2] - 9.6) < 1e-6]
    assert min(v[0] for v in top) == pytest.approx(0.1 + 0.35, abs=1e-3)
    # the underside stays hollow, and the stud top is bevelled
    assert not any(n.type == "difference" for n in soft.walk())
    studs = [n for n in soft.walk() if n.name == "Stud"]
    assert len(studs) == 2
    assert max(v[2] for v in pts) == pytest.approx(11.4)
    node = library.build_part("lego_brick", dict(_size="1x2"))
    assert any(n.type == "hull" for n in node.walk())


def test_clear_colours_are_glass(app):
    node = library_lego.colour(library_lego.brick(1, 1), "Trans-clear")
    assert node.params["material"] == "Glass" and node.params["alpha"] < 1


def test_lego_parts_offer_colours_and_count_fields():
    spec = library.PARTS["lego_brick"]
    assert "Red" in spec["colors"] and "Trans-clear" in spec["colors"]
    assert {"nx", "ny"} <= library._COUNT_FIELDS
