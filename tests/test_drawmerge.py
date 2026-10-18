"""Overlapping parts are merged for the drawing only (drawmerge.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest

from khervecad import csg, drawmerge, mesh
from khervecad.model import CadNode

pytestmark = pytest.mark.skipif(not csg.available(),
                                reason="Manifold not installed")


def _cube(x=0.0, z=0.0, w=10.0):
    return mesh.tessellate(CadNode("cube", params=dict(
        width=w, depth=w, height=w, x=x, z=z)))


def _tube(z0, h, x=5.0, y=5.0):
    return mesh.tessellate(CadNode("cylinder", params=dict(
        height=h, radius_bottom=2.0, radius_top=2.0, segments=24,
        x=x, y=y, z=z0)), fn=24)


def test_a_tube_through_a_wall_becomes_one_solid():
    tris, joined = drawmerge.merged(_cube() + _tube(5.0, 15.0))
    assert joined == 2
    from khervecad import analysis
    vol = analysis.mass_properties(tris)["volume"]
    assert vol < 1000 + 3.15 * 4 * 15          # the overlap counted once


def test_parts_that_only_touch_stay_apart():
    raw = _cube() + _cube(z=10.0)
    tris, joined = drawmerge.merged(raw)
    assert joined == 0 and tris == raw


def test_the_meeting_curve_is_an_edge_on_the_drawing():
    from khervecad import fillet
    from khervecad.blueprint_scene import Geometry
    raw = _cube() + _tube(5.0, 15.0)

    def ring(tris):
        """crease edges on the tube where it meets the cube's top face"""
        return [e for e in fillet.crease_edges(tris, 30.0)
                if abs(e.a[2] - 10.0) < 1e-3 and abs(e.b[2] - 10.0) < 1e-3
                and abs(((e.a[0] - 5) ** 2 + (e.a[1] - 5) ** 2) ** 0.5 - 2)
                < 0.05]
    assert not ring(Geometry(raw, merge=False).tris)
    merged = Geometry(raw)
    assert merged.joined == 2 and len(ring(merged.tris)) >= 20
    assert Geometry(raw, merge=False).raw == raw      # the model's copy
