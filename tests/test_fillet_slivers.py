"""A fillet along a faceted junction ignores sliver creases
(2026-11-22, Exercise 159: the R0.1 rounding where the pipe outlets
meet the dome left spikes).

Where a revolved dome meets a pipe the preview mesh has tiny sliver
faces: along a run of 0.01-0.02 long creases an edge or two has face
normals folded 130-165 degrees from its neighbours. The rolling-ball
profile of such an edge reaches r / tan(beta / 2) along the faces — seven
radii for 164 degrees — and stands up as a spike beside the rounding.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from khervecad import fillet

R = 0.1


def _run(n=40, step=0.02, slivers=(), spacing=1.0):
    """A concave run along x: faces z-up and y-up, 90 degrees, with
    each index in *slivers* folded 164 degrees (a sliver face)."""
    edges = []
    for i in range(n):
        nl, nr, angle = (0.0, 0.0, 1.0), (0.0, 1.0, 0.0), 90.0
        if i in slivers:
            nl, angle = (0.0, -0.9613, 0.2756), 164.0
        edges.append(fillet.Edge((i * step, 0.0, 0.0),
                                 ((i + 1) * step, 0.0, 0.0),
                                 nl, nr, angle, False))
    pts = [e.a for e in edges] + [edges[-1].b]
    return dict(points=pts, edges=edges, closed=False, convex=False)


def _reach(run):
    body = fillet.strip(run, R, "round", 6)
    assert body
    # a 90 degree rounding stays within r * sqrt(2) of its edge line
    return max(math.hypot(v[1], v[2]) for t in body for v in t[:3])


def test_a_clean_run_stays_close_to_its_edge():
    assert _reach(_run()) < 1.5 * R


def test_one_sliver_crease_makes_no_spike():
    assert _reach(_run(slivers={20})) < 1.5 * R


def test_two_neighbouring_slivers_make_no_spike():
    assert _reach(_run(slivers={20, 21})) < 1.5 * R


def test_slivers_at_several_places_make_no_spike():
    assert _reach(_run(slivers={5, 6, 20, 33})) < 1.5 * R


def test_a_real_change_along_the_run_is_kept():
    """Half the run at 90 degrees, half at 120: no outlier, no change."""
    run = _run()
    for e in run["edges"][20:]:
        e.nl = (0.0, 0.0, 1.0)
        e.nr = (0.0, math.sin(math.radians(120)), math.cos(math.radians(120)))
        e.angle = 120.0
    smooth = fillet.smoothed(run, R)
    assert smooth[19].nr == run["edges"][19].nr
    assert smooth[30].angle == 120.0


def _corner(normals, width=R):
    """Bevel's corner piece at a vertex where three creases meet,
    between three faces with the given *normals*."""
    from khervecad import bevel
    pairs = ((0, 1), (1, 2), (2, 0))
    edges = []
    for i, j in pairs:
        d = fillet._unit(fillet._cross(normals[i], normals[j]))
        edges.append(fillet.Edge((0.0, 0.0, 0.0), d, normals[i], normals[j],
                                 60.0, False))
    runs = [dict(edges=edges)]
    return bevel.corners(edges, runs, width, 6, 2.0)


def _extent(pieces):
    import numpy as np
    far = 0.0
    for piece, _convex in pieces:
        pts = np.asarray(piece.to_mesh().vert_properties)[:, :3]
        far = max(far, float(np.abs(pts).max()))
    return far


def test_a_corner_of_three_planes_makes_a_small_piece():
    n = [fillet._unit(v) for v in ((0.0, 0.0, 1.0), (0.0, 1.0, 0.3),
                                   (1.0, 0.0, 0.3))]
    pieces = _corner(n)
    assert pieces and _extent(pieces) < 4 * R


def test_a_corner_of_nearly_parallel_faces_makes_no_piece_a_mile_wide():
    """Sliver faces at a vertex (Exercise 159): three planes within a
    few degrees of each other meet 125 inches from it, and the corner
    piece reached there."""
    n = [fillet._unit(v) for v in ((0.0, 0.0, 1.0), (0.0, 0.04, 1.0),
                                   (0.04, 0.0, 1.0))]
    assert _extent(_corner(n)) < 4 * R
