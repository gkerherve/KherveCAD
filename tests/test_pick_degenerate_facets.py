# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Zero-area facets do not cut a flat face into edges (2026-11-22,
Exercise 010: the revolved tube's end disk came with degenerate
triangles along its spokes; every click on it snapped to a "diameter"
edge, so Sketch Mode could not open a sketch on the end face)."""

import math

from khervecad import anchors


def _disk(n=24, r=0.6):
    c = (0.0, 0.0, 0.0)
    rim = [(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n),
            0.0) for k in range(n)]
    tris = [(c, rim[k], rim[(k + 1) % n]) for k in range(n)]
    # the side wall, so the rim is a real edge
    for k in range(n):
        a, b = rim[k], rim[(k + 1) % n]
        a2, b2 = (a[0], a[1], -1.0), (b[0], b[1], -1.0)
        tris += [(a, a2, b2), (a, b2, b)]
    return tris, rim


def test_a_click_inside_a_disk_with_degenerate_spokes_is_the_face():
    tris, rim = _disk()
    # zero-area slivers along every spoke (centre, rim point, rim point)
    for p in rim:
        mid = (p[0] / 2, p[1] / 2, 0.0)
        tris.append(((0.0, 0.0, 0.0), mid, p))
    hit = 3                                       # a fan triangle
    a, b, c = tris[hit]
    point = tuple((a[i] + b[i] + c[i]) / 3 for i in range(3))
    # (8 px at the hit depth: more than a thin wedge's width)
    got = anchors.describe_pick(tris, hit, point, tol=0.1)
    assert got["kind"] == "face", got.get("seg")
