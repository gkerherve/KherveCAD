"""Every feature's own face centre is offered to a sketch (2026-11-10,
the user: on a boss flush with the base, "I cannot access the centre of
that plane ... somehow it is focused on another centre").

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QPointF
from PyQt5.QtWidgets import QApplication

from khervecad import face_outline, face_sketch
from khervecad.mcp_tools import McpToolExecutor

from test_stacked_features import (_rect_feature, _sketch_on,  # noqa
                                   app, win)


def _flush(win):
    """A 100 x 60 x 20 block from the origin and a 40 x 20 x 10 boss on
    it, flush with the block's x = 0 end."""
    McpToolExecutor(win).execute(
        "apply_code", {"code": "cube([100, 60, 20]); // Base\n"})
    QApplication.processEvents()
    part = next(c for c in win.model.root.children
                if c.visible and c.type != "assign")
    boss = _rect_feature(win, part, (10, 20, 20), (0, 10), (40, 30),
                         height=10.0)
    return part, boss


def _centres(tool):
    return sorted(
        tuple(round(v, 2) + 0.0 for v in
              face_sketch.to_world(tool.group, x, y))
        for x, y, kind in tool.info["points"] if kind == "face centre")


def test_the_bosss_own_end_centre_is_offered_on_the_flush_face(win):
    part, boss = _flush(win)
    tool = _sketch_on(win, face_sketch.group_of(boss), (0, 20, 25),
                      "extruded_cut", (-1, 0, 0))
    got = _centres(tool)
    assert (0.0, 20.0, 25.0) in got          # the boss's end, alone
    assert (0.0, 30.0, 10.0) in got          # the block's end, alone
    assert (0.0, 30.0, 15.0) in got          # the two together, as before
    # ... and the snap goes to it
    x, y = face_sketch.to_local(tool.group, (0, 20, 25))
    hit = face_outline.snap(win.view2d.scene(), QPointF(x + 0.01, y - 0.01))
    assert hit is not None and hit[1] == "face centre"
    assert (hit[0].x(), hit[0].y()) == pytest.approx((x, y), abs=1e-6)


def test_a_face_of_one_feature_keeps_its_single_centre(win):
    part, boss = _flush(win)
    tool = _sketch_on(win, face_sketch.group_of(boss), (20, 20, 30),
                      "extruded_cut", (0, 0, 1))
    assert set(_centres(tool)) == {(20.0, 20.0, 30.0)}


def test_two_islands_of_one_face_each_give_their_centre(win):
    """Two bosses of one height: their tops are one plane, two faces."""
    part, boss = _flush(win)
    other = _rect_feature(win, part, (80, 40, 20), (70, 30), (90, 50),
                          height=10.0)
    tool = _sketch_on(win, face_sketch.group_of(other), (80, 40, 30),
                      "extruded_cut", (0, 0, 1))
    got = _centres(tool)
    assert (80.0, 40.0, 30.0) in got and (20.0, 20.0, 30.0) in got
