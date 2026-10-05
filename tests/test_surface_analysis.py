"""Draft, curvature and zebra heat maps (surface_analysis.py).

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

from khervecad import heatmap, mesh, surface_analysis as sa


def _cube():
    return mesh.cube_mesh(dict(width=10, depth=10, height=10, center=True,
                               x=0, y=0, z=0))


def _cone(r1=10, r2=5):
    return mesh.cylinder_mesh(dict(segments=48, height=20, radius_bottom=r1,
                                   radius_top=r2, x=0, y=0, z=0,
                                   center=False))


def test_draft_tells_walls_from_tapered_sides():
    cols, stats = sa.draft(_cube())
    # 4 vertical sides of 2 triangles red, top and bottom blue
    assert cols.count(sa.RED) == 8 and cols.count(sa.BLUE) == 4
    assert stats["no_draft_fraction"] == pytest.approx(4 / 6)
    cols, stats = sa.draft(_cone(), wanted=2.0)       # ~14° of taper
    assert sa.RED not in cols and stats["no_draft_fraction"] == 0


def test_curvature_sees_a_sphere_bulge():
    sphere = mesh.sphere_mesh(dict(radius=10, segments=32, x=0, y=0, z=0))
    cols, _ = sa.curvature(sphere)
    reds = sum(c in (sa.RED, "#ef9a9a") for c in cols)
    blues = sum(c in (sa.BLUE, "#90caf9") for c in cols)
    assert reds > blues


def test_zebra_is_black_and_white():
    sphere = mesh.sphere_mesh(dict(radius=10, segments=32, x=0, y=0, z=0))
    cols, stats = sa.zebra(sphere)
    assert set(cols) == {sa.WHITE, sa.BLACK}


@pytest.mark.parametrize("kind", ["draft", "curvature", "zebra"])
def test_heatmap_dispatches(kind):
    cols, stats = heatmap.colours(_cone(), kind)
    assert len(cols) == len(_cone()) and stats["kind"] == kind
    assert stats["legend"]
