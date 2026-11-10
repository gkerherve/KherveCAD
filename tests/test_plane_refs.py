"""A sketch on a PLANE through the part follows the part (2026-11-10,
the user: the cone revolved from lines on the Front plane, drawn from a
pin's corner, stayed in the air when the pin changed — "yes, fix it").

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import (face_sketch, model_refs, plane_refs,
                       revolve_feature, sketch_constraints as sc)

from test_stacked_features import (_base, _box, _rect_feature,  # noqa
                                   _volume, app, win)


def _tower(win):
    """Base 100 x 60 x 20, a boss 60 x 36 x 15 on it, a 20 x 20 x 12
    boss on that, an 8 x 8 pocket 8 deep in it and a 2 x 2 pin 14 tall
    on the pocket's floor: its top at z = 53."""
    part = _base(win)
    b2 = _rect_feature(win, part, (30, 20, 20), (-30, -18), (30, 18),
                       height=15.0)
    b3 = _rect_feature(win, part, (0, 0, 35), (-10, -10), (10, 10),
                       height=12.0)
    on = face_sketch.group_of(b3)
    _rect_feature(win, on, (0, 0, 47), (-4, -4), (4, 4),
                  kind="extruded_cut", height=8.0)
    pin = _rect_feature(win, on.parent, (0, 0, 39), (-1, -1), (1, 1),
                        height=14.0)
    return part, b2, b3, pin


def _front_sketch(win, lines, fixed):
    """Lines on the Front plane, the points *fixed* [(line, end)] pinned
    where they are (what a snap onto the part's section does)."""
    m = win.model
    g = m.add_node("union", dict(x=0.0, y=0.0, z=0.0, rx=90.0, ry=0.0,
                                 rz=0.0), name="Sketch on Front Plane")
    g.params[face_sketch.KEY] = True
    nodes = [m.add_node("line", dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1],
                                     width=0.2), parent=g)
             for a, b in lines]
    for i, end in fixed:
        sc.add(m, g, "fix", [sc.ref_of(g, nodes[i], end)])
    for i in range(len(nodes)):
        sc.add(m, g, "coincident",
               [sc.ref_of(g, nodes[i], "p2"),
                sc.ref_of(g, nodes[(i + 1) % len(nodes)], "p1")])
    QApplication.processEvents()
    return g, nodes


def _cone(win):
    part, b2, b3, pin = _tower(win)
    g, lines = _front_sketch(
        win, [((0, 53), (1, 53)), ((1, 53), (0, 59)), ((0, 59), (0, 53))],
        [(0, "p1"), (0, "p2")])
    sc.add(win.model, g, "vertical", [sc.ref_of(g, lines[2], "l")])
    sc.add(win.model, g, "length", [sc.ref_of(g, lines[2], "l")], 6.0)
    rev = revolve_feature.revolve(win, list(lines))
    QApplication.processEvents()
    model_refs.adopt(win)                 # as on leaving the sketch
    return part, b2, b3, pin, rev


def _rows(rev):
    return sc.rows(rev.children[0])


def test_points_on_the_section_take_the_feature_they_sit_on(win):
    part, b2, b3, pin, rev = _cone(win)
    fixes = [r for r in _rows(rev) if r["kind"] == "fix"]
    assert len(fixes) == 2
    owner = pin.params["feature_order"]
    assert all(r.get(plane_refs.OWNER) == owner for r in fixes), fixes
    kinds = {tuple(r["at"]): r["model"] for r in fixes}
    assert kinds[(0.0, 53.0)] == "mid"        # the middle of the pin's top
    assert kinds[(1.0, 53.0)] is True         # its corner


def test_the_cone_rises_with_the_pin(win):
    part, b2, b3, pin, rev = _cone(win)
    full = _volume(win)
    cone = math.pi * 1 * 1 * 6 / 3
    win.model.set_param(pin, "height", 20.0)
    QApplication.processEvents()
    lo, hi = _box(win, rev)
    assert (lo[2], hi[2]) == pytest.approx((59.0, 65.0), abs=0.02)
    assert _volume(win) - full == pytest.approx(2 * 2 * 6, abs=0.3)
    assert cone > 0


def test_the_cone_rises_with_a_boss_far_below(win):
    """The edge nearest where the pin's top was is then the top of the
    boss under it (57, against 63): each reference follows ITS feature."""
    part, b2, b3, pin, rev = _cone(win)
    win.model.set_param(b2, "height", 25.0)
    QApplication.processEvents()
    assert _box(win, pin)[1][2] == pytest.approx(63.0, abs=0.02)
    lo, hi = _box(win, rev)
    assert (lo[2], hi[2]) == pytest.approx((63.0, 69.0), abs=0.02)
    cube = next(n for n in part.walk() if n.type == "cube") \
        if part.type != "cube" else part
    win.model.set_param(cube, "height", 30.0)
    QApplication.processEvents()
    lo, hi = _box(win, rev)
    assert (lo[2], hi[2]) == pytest.approx((73.0, 79.0), abs=0.02)


def test_the_cone_widens_with_the_pin(win):
    part, b2, b3, pin, rev = _cone(win)
    rect = next(c for c in pin.walk() if c.type == "rect")
    # (the rectangle is held on the face's centre: it re-centres)
    win.model.set_param(rect, "width", 3.0)
    QApplication.processEvents()
    lo, hi = _box(win, rev)
    assert (lo[0], hi[0]) == pytest.approx((-1.5, 1.5), abs=0.02)
    assert (lo[2], hi[2]) == pytest.approx((53.0, 59.0), abs=0.02)


def test_it_still_follows_after_save_and_open(win, tmp_path):
    part, b2, b3, pin, rev = _cone(win)
    path = str(tmp_path / "cone.kcad")
    win._path = path
    from khervecad import document
    document.save_kcad(win.model, path)
    win._dirty = False
    win.open_any(path)
    QApplication.processEvents()
    from PyQt5.QtTest import QTest
    QTest.qWait(50)
    root = win.model.root
    rev = next(n for n in root.walk() if n.type == "rotate_extrude")
    pin = max((n for n in root.walk() if n.type == "linear_extrude"),
              key=lambda n: n.params["feature_order"])
    win.model.set_param(pin, "height", 20.0)
    QApplication.processEvents()
    lo, hi = _box(win, rev)
    assert (lo[2], hi[2]) == pytest.approx((59.0, 65.0), abs=0.02)


def test_a_switched_off_owner_leaves_the_sketch_where_it_was(win):
    from khervecad import suppress
    part, b2, b3, pin, rev = _cone(win)
    suppress.set_suppressed(win.model, [pin], True)
    QApplication.processEvents()
    lo, hi = _box(win, rev)
    assert (lo[2], hi[2]) == pytest.approx((53.0, 59.0), abs=0.02)


def test_a_point_off_the_section_is_left_alone(win):
    """A deliberate Fix in the air is no reference to the part."""
    part, b2, b3, pin = _tower(win)
    g, lines = _front_sketch(
        win, [((20, 70), (24, 70)), ((24, 70), (20, 76)),
              ((20, 76), (20, 70))], [(0, "p1")])
    model_refs.adopt(win)
    assert not plane_refs.has_refs(g)
    win.model.set_param(pin, "height", 20.0)
    QApplication.processEvents()
    assert lines[0].params["y1"] == pytest.approx(70.0)


def test_an_edge_is_matched_by_its_direction():
    """A pin's top is never taken for its bottom, however near."""
    box = [((1, 49), (1, 63)), ((1, 63), (-1, 63)),
           ((-1, 63), (-1, 49)), ((-1, 49), (1, 49))]
    top = plane_refs.match_edge(box, [1, 53, -1, 53])
    assert top == ((1, 63), (-1, 63))


