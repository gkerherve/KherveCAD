"""Tests for the BSP painter's order (bsp.py) and its use in View3D.

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

from khervecad import bsp
from khervecad.view3d import View3D


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _box(cx, cy, cz, sx, sy, sz):
    """12 outward-facing triangles of an axis-aligned box."""
    x0, x1 = cx - sx / 2, cx + sx / 2
    y0, y1 = cy - sy / 2, cy + sy / 2
    z0, z1 = cz - sz / 2, cz + sz / 2
    p = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (2, 3, 7, 6), (1, 2, 6, 5), (3, 0, 4, 7)]
    tris = []
    for a, b, c, d in quads:
        tris.append((p[a], p[b], p[c]))
        tris.append((p[a], p[c], p[d]))
    return tris


def _pupil_scene():
    """A big pale head with a small dark 'pupil' 1 mm proud of its
    front face (-Y), off towards the far corner as seen by
    _oblique_view — the case a centroid sort gets wrong: the face
    triangle's centroid is nearer the camera than the pupil's."""
    head = _box(0, 0, 0, 40, 40, 40)
    pupil = _box(-14, -20.5, 4, 6, 1, 9)
    tris = head + pupil
    colors = [("#eeeeee", 1.0)] * len(head) + [("#000000", 1.0)] * len(pupil)
    return tris, colors, (-14.0, -21.0, 4.0)


def _front_and_pupil(tree):
    """Indices of the head's front-face pieces (plane y=-20) and of the
    pupil pieces standing proud of it (its own back face is coplanar
    with the head face and may legitimately interleave with it)."""
    front = [i for i, t in enumerate(tree.tris)
             if tree.colors[i][0] == "#eeeeee"
             and all(abs(v[1] + 20.0) < 1e-6 for v in t)]
    pupil = [i for i, t in enumerate(tree.tris)
             if tree.colors[i][0] == "#000000"
             and any(v[1] < -20.0 - 1e-6 for v in t)]
    assert front and pupil
    return front, pupil


def test_split_keeps_every_piece_and_colour():
    tris, colors, _ = _pupil_scene()
    tree = bsp.build(tris, colors, budget=10)
    assert tree is not None
    assert len(tree.tris) >= len(tris)
    assert len(tree.colors) == len(tree.tris)
    # every colour of every piece is one of the inputs
    assert set(tree.colors) == set(colors)
    # the walk visits each piece exactly once
    order = tree.order((100.0, -100.0, 80.0), (-0.6, 0.6, -0.5))
    assert sorted(order) == list(range(len(tree.tris)))


def test_order_paints_the_pupil_after_the_face():
    tris, colors, _ = _pupil_scene()
    tree = bsp.build(tris, colors, budget=10)
    # from anywhere in front of the head, the head's front face (y=-20)
    # must come before every pupil piece
    front, pupil = _front_and_pupil(tree)
    for eye in ((0.0, -100.0, 0.0), (60.0, -80.0, 50.0), (-70.0, -30.0, 10.0)):
        order = tree.order(eye, (0.0, 1.0, 0.0))
        pos = {i: k for k, i in enumerate(order)}
        assert max(pos[i] for i in front) < min(pos[i] for i in pupil)


def test_orthographic_order_uses_the_view_direction():
    tris, colors, _ = _pupil_scene()
    tree = bsp.build(tris, colors, budget=10)
    # the eye sits *inside* the head: only the view direction says the
    # pupil is nearer
    order = tree.order((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), ortho=True)
    pos = {i: k for k, i in enumerate(order)}
    front, pupil = _front_and_pupil(tree)
    assert max(pos[i] for i in front) < min(pos[i] for i in pupil)


def test_split_triangle_pieces_lie_on_either_side():
    tri = ((-10.0, -1.0, 0.0), (10.0, -1.0, 0.0), (0.0, 5.0, 0.0))
    front, back = bsp._split(tri, (-1.0, -1.0, 5.0))    # plane y = 0
    assert len(front) == 1 and len(back) == 2
    assert all(v[1] >= -1e-9 for t in front for v in t)
    assert all(v[1] <= 1e-9 for t in back for v in t)


def test_degenerate_triangles_are_dropped_not_fatal():
    flat = [((0, 0, 0), (1, 0, 0), (2, 0, 0))] * 5
    assert bsp.build(flat, budget=10) is None
    tris, colors, _ = _pupil_scene()
    tree = bsp.build(tris + flat, colors + [None] * 5, budget=10)
    assert tree is not None


def test_limits_fall_back_to_none():
    tris, colors, _ = _pupil_scene()
    assert bsp.build([], None) is None
    assert bsp.build(tris, colors, max_tris=3) is None
    assert bsp.build(tris, colors, budget=0.0) is None
    # a growth cap below the input size can never be met
    assert bsp.build(tris, colors, max_growth=0.0) is None or \
        bsp.MIN_PIECES >= len(tris)


def test_convex_body_does_not_degenerate_into_a_chain():
    """A sphere-like body: every facet plane has all others behind it.
    The axis-median fallback keeps the tree shallow and the build fast."""
    import math
    import time
    tris = []
    n = 48
    for i in range(n):
        for j in range(n // 2):
            def pt(a, b):
                th, ph = 2 * math.pi * a / n, math.pi * b / (n // 2)
                return (20 * math.sin(ph) * math.cos(th),
                        20 * math.sin(ph) * math.sin(th),
                        20 * math.cos(ph))
            p00, p10 = pt(i, j), pt(i + 1, j)
            p01, p11 = pt(i, j + 1), pt(i + 1, j + 1)
            tris.append((p00, p10, p11))
            tris.append((p00, p11, p01))
    t0 = time.perf_counter()
    tree = bsp.build(tris, budget=10)
    assert tree is not None
    # the pure chain took ~0.65 s for 2k facets and grows quadratically;
    # the median planes cut a ring per level (about 2x pieces) instead
    assert time.perf_counter() - t0 < 1.0
    assert len(tree.tris) <= 2.5 * len(tris)

    def depth(node):
        return 0 if node is None else 1 + max(depth(node.back),
                                              depth(node.front))
    assert depth(tree.root) < len(tris) // 4


# ------------------------------------------------------------ in the view
def _pixel_at(view, world):
    eye, right, up, forward = view._camera()
    x, y, _ = view._project(eye, right, up, forward, world)
    img = view.grab().toImage()
    return img.pixelColor(int(x), int(y))


def _oblique_view(app, tris, colors):
    view = View3D()
    view.resize(400, 300)
    view.background = "Light"
    view.set_style("Shaded")
    view.set_mesh(tris, "test", colors)
    view.yaw, view.pitch = -60.0, 20.0
    view.target, view.distance = [0.0, -20.0, 0.0], 120.0
    return view


def test_view_paints_a_feature_in_front_of_a_big_face(app):
    tris, colors, probe = _pupil_scene()
    view = _oblique_view(app, tris, colors)
    assert view.wait_for_bsp() is not None
    c = _pixel_at(view, probe)
    assert c.lightnessF() < 0.3, c.name()      # the pupil is dark


def test_centroid_sort_alone_gets_it_wrong(app, monkeypatch):
    """Guards the test above: without the tree the face wins."""
    monkeypatch.setattr(bsp, "build", lambda *a, **k: None)
    tris, colors, probe = _pupil_scene()
    view = _oblique_view(app, tris, colors)
    view.wait_for_bsp()
    assert view._bsp is None
    c = _pixel_at(view, probe)
    assert c.lightnessF() > 0.5, c.name()


def test_stale_tree_is_not_adopted(app):
    tris, colors, _ = _pupil_scene()
    view = View3D()
    view.set_mesh(tris, "a", colors)
    first = view.wait_for_bsp()
    view.set_mesh(tris[:12], "b", colors[:12])
    assert view._bsp is None or view._bsp is not first
    tree = view.wait_for_bsp()
    assert tree is not None and tree is not first
    assert len(tree.tris) >= 12


def test_snapshot_reuses_the_tree(app):
    tris, colors, _ = _pupil_scene()
    view = View3D()
    view.resize(200, 150)
    view.set_mesh(tris, "test", colors)
    tree = view.wait_for_bsp()
    img, _state = view.snapshot(200, 150)
    assert not img.isNull()
    assert view._bsp is tree
