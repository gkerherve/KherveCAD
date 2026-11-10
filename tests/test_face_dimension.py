"""Smart Dimension between two FACES of the part (2026-11-10, the user:
"shall I not be able to also fix the distance between one face to
another face? ... that is not possible").

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import constrain3d, face_dim, sketch_constraints as sc

from test_stacked_features import (_base, _box, _rect_feature,  # noqa
                                   app, win)


def _screen(tool, world):
    q = tool._project()(world)
    return q[0], q[1]


def _part(win):
    """A 100 x 60 x 20 block (no sketch) and a 40 x 20 x 15 boss on it."""
    part = _base(win)
    boss = _rect_feature(win, part, (10, 5, 20), (-20, -10), (20, 10),
                         height=15.0)
    v = win.view3d
    v.resize(900, 700)
    v.set_view("Isometric", animate=False)
    v.fit()
    QApplication.processEvents()
    return part, boss


def _dimension(win, a, b, value):
    win.view2d.scene().ask_value = lambda kind, measured: str(value)
    constrain3d.start(win, "con_dimension")
    t = win.view3d.edit_tool
    t.click(*_screen(t, a))
    got = t.click(*_screen(t, b))
    constrain3d.end(win)
    QTest.qWait(50)
    return got


def test_a_bosss_face_to_the_blocks_face(win):
    """The boss's front (its sketch's line) 12 from the block's front
    (no sketch: a reference line where the face meets the sketch)."""
    part, boss = _part(win)
    # middle of the boss's front, middle of the block's front
    assert _dimension(win, (2, -10, 28), (3, -30, 9), 12) is not None
    assert _box(win, boss)[0][1] == pytest.approx(-18.0, abs=0.01)
    cont = next(n for n in boss.walk() if n.params.get("constraints"))
    ref = [c for c in cont.children if c.name.startswith(face_dim.NAME)]
    assert len(ref) == 1 and ref[0].params["ref_face"][3:] == [0, -1, 0]
    assert ref[0].params.get("modifier") == "%"


def test_the_dimension_holds_when_the_face_moves(win):
    part, boss = _part(win)
    _dimension(win, (2, -10, 28), (3, -30, 9), 12)
    move = next(n for n in win.model.root.walk()
                if n.type in ("translate", "cube") and "y" in n.params)
    win.model.set_param(move, "y", -40.0)           # the front: -30 -> -40
    QApplication.processEvents()
    assert _box(win, boss)[0][1] == pytest.approx(-28.0, abs=0.01)


def test_the_face_first_then_the_bosss_face(win):
    part, boss = _part(win)
    assert _dimension(win, (3, -30, 9), (2, -10, 28), 7) is not None
    assert _box(win, boss)[0][1] == pytest.approx(-23.0, abs=0.01)


def test_two_faces_of_two_sketched_features(win):
    """Each face is its own sketch's line: the later sketch is driven."""
    part, boss = _part(win)
    pin = _rect_feature(win, part, (-35, 0, 20), (-40, -5), (-30, 5),
                        height=6.0)
    QApplication.processEvents()
    before = _box(win, boss)
    # the pin's front (y = -5) to the boss's front (y = -10)
    assert _dimension(win, (-35, -5, 23), (2, -10, 28), 3) is not None
    assert _box(win, boss) == before
    assert _box(win, pin)[0][1] == pytest.approx(-7.0, abs=0.01)


def test_a_face_flat_to_the_sketch_is_refused(win):
    part, boss = _part(win)
    # the boss's front, then the block's TOP: parallel to the sketch
    assert _dimension(win, (2, -10, 28), (40, 20, 20), 5) is None
    cont = next(n for n in boss.walk() if n.type == "rect").parent
    assert not [c for c in cont.children if c.name.startswith(face_dim.NAME)]


def test_two_faces_no_sketch_made_cannot_be_driven(win):
    part = _base(win)
    v = win.view3d
    v.resize(900, 700)
    v.set_view("Isometric", animate=False)
    v.fit()
    assert _dimension(win, (3, -30, 9), (10, 0, 20), 5) is None
    assert not any(n.name.startswith(face_dim.NAME)
                   for n in win.model.root.walk())


def test_the_line_where_a_face_meets_a_sketch():
    import numpy as np
    pts = [(50, -30, 0), (50, 30, 0), (50, 30, 20), (50, -30, 20)]
    line = face_dim.line_in_sketch(np.eye(4), pts, (1, 0, 0))
    assert sorted(line) == [(50.0, -30.0), (50.0, 30.0)]
    assert face_dim.line_in_sketch(np.eye(4), pts, (0, 0, 1)) is None


def test_an_assistant_dimensions_a_sketch_to_a_face(win):
    from khervecad.mcp_tools import McpToolExecutor
    part, boss = _part(win)
    ex = McpToolExecutor(win)
    rect = next(n for n in boss.walk() if n.type == "rect")
    cont = rect.parent
    got = ex.execute("sketch_constraint", dict(
        action="face_reference", node_id=cont.id, point=[3, -30, 9]))
    assert got["reference"].endswith(".l") and got["follows_the_face"]
    ex.execute("sketch_constraint", dict(
        action="add", node_id=cont.id, kind="point_line",
        refs=[sc.ref_of(cont, rect, "v0"), got["reference"]], value=9,
        scale_sketch=False))
    QApplication.processEvents()
    assert _box(win, boss)[0][1] == pytest.approx(-21.0, abs=0.01)
    flat = ex.execute("sketch_constraint", dict(
        action="face_reference", node_id=cont.id, point=[40, 20, 20]))
    assert "flat to the sketch" in flat["error"]
