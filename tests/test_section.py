"""Tests for planar cross-sections (section.py).

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

from khervecad import section


def _box(x0, y0, z0, x1, y1, z1, inward=False):
    """A closed box, faces wound outward (inward=True: a cavity)."""
    faces = [
        [(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)],   # -Z
        [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],   # +Z
        [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],   # -Y
        [(x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)],   # +Y
        [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)],   # -X
        [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],   # +X
    ]
    tris = []
    for a, b, c, d in faces:
        for tri in ((a, b, c), (a, c, d)):
            tris.append(tri[::-1] if inward else tri)
    return tris


def test_a_cube_cuts_to_one_square():
    sec = section.section(_box(0, 0, 0, 10, 10, 10), "z", 5.0)
    assert len(sec["outlines"]) == 1
    assert sec["outlines"][0]["closed"]
    assert sec["area"] == pytest.approx(100.0)
    assert sec["bounds"] == pytest.approx([0, 0, 10, 10])
    assert sec["plane"] == ("x", "y")


@pytest.mark.parametrize("axis", ["x", "y", "z"])
def test_outer_outlines_run_counter_clockwise_on_every_axis(axis):
    """The solid is always on the left, whatever the plane — so an
    outer outline's area is positive."""
    sec = section.section(_box(0, 0, 0, 10, 20, 30), axis)
    assert len(sec["outlines"]) == 1
    assert sec["outlines"][0]["area"] > 0
    expected = {"x": 20 * 30, "y": 10 * 30, "z": 10 * 20}[axis]
    assert sec["area"] == pytest.approx(expected)


def test_a_hole_subtracts_from_the_area():
    """A square tube: the bore comes back as its own clockwise outline,
    so the net area is wall only."""
    tube = _box(0, 0, 0, 10, 10, 10) + _box(3, 3, -1, 7, 7, 11,
                                           inward=True)
    sec = section.section(tube, "z", 5.0)
    areas = sorted(o["area"] for o in sec["outlines"])
    assert areas == pytest.approx([-16.0, 100.0])
    assert sec["area"] == pytest.approx(84.0)


def test_the_offset_defaults_to_the_middle():
    sec = section.section(_box(0, 0, 4, 10, 10, 20), "z")
    assert sec["offset"] == pytest.approx(12.0)
    assert sec["area"] == pytest.approx(100.0)


def test_a_plane_that_misses_cuts_nothing():
    sec = section.section(_box(0, 0, 0, 10, 10, 10), "z", 50.0)
    assert sec["outlines"] == [] and sec["area"] == 0.0
    assert sec["bounds"] is None


def test_a_leaky_mesh_reports_an_open_outline():
    """A missing face leaves the cut unable to close — reported, not
    papered over, because it is a real defect in the mesh."""
    leaky = [t for i, t in enumerate(_box(0, 0, 0, 10, 10, 10))
             if i not in (4, 5)]                 # drop the -Y face
    sec = section.section(leaky, "z", 5.0)
    assert any(not o["closed"] for o in sec["outlines"])


def test_a_vertex_on_the_plane_does_not_break_the_outline():
    """Cutting exactly through vertices (z = 0 of a box resting on it,
    or a shared vertex) still yields one clean square."""
    sec = section.section(_box(0, 0, -5, 10, 10, 5), "z", 5.0 - 5.0)
    assert len(sec["outlines"]) == 1 and sec["outlines"][0]["closed"]
    assert sec["area"] == pytest.approx(100.0)


def test_an_unknown_axis_is_refused():
    with pytest.raises(ValueError):
        section.section(_box(0, 0, 0, 1, 1, 1), "w")


@pytest.fixture(scope="module")
def app():
    """Held for the module: a QApplication nobody references is
    destroyed at once, and painting text without one crashes Qt."""
    from PyQt5.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_draw_makes_a_picture_of_the_requested_size(app):
    tube = _box(0, 0, 0, 10, 10, 10) + _box(3, 3, -1, 7, 7, 11,
                                           inward=True)
    img = section.draw(section.section(tube, "z", 5.0), 320, 240)
    assert (img.width(), img.height()) == (320, 240)
    # the bore is empty: its centre is the background, not material
    centre = img.pixelColor(160, 134)
    assert centre.name() == "#f7f7f5" or centre.lightness() > 200
    empty = section.draw(section.section(tube, "z", 99.0), 200, 100)
    assert empty.width() == 200
