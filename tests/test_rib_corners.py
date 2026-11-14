"""A rib line drawn from CORNER to corner of the part stays as drawn
(2026-11-14, Exercise 57: the bracket's rib runs from the base's far top
corner to the corner under the second lug's boss). The part's section is
grown 0.05 mm, so a true corner lies 0.07 mm from the grown outline: it
was taken for "not on the part" and run on — back past the base's end
(the rib stood 0.26 mm proud of the end face) and through the lug to the
hole's edge. By mouse: the sketch selected, the ribbon's Rib clicked.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest

from test_lever_by_mouse import win  # noqa: F401
from test_rib import _volume
from test_rib_by_mouse import _rib_button

CODE = ("cube([60, 40, 10]); // Base\n"
        "translate([40, 0, 10]) cube([20, 40, 20]); // Block\n"
        "translate([34, 0, 30]) cube([26, 40, 10]); // Shelf\n")


def test_a_corner_to_corner_rib_line_is_kept_as_drawn(win):
    from khervecad import face_sketch, mesh, refgeom_ui
    from khervecad.mcp_tools import McpToolExecutor
    McpToolExecutor(win).execute("apply_code", {"code": CODE})
    QTest.qWait(50)
    before = _volume(win)
    group = refgeom_ui.sketch_on(win, origin=(0, 20, 0), normal=(0, 1, 0),
                                 label="Rib plane", open_2d=False)
    a = face_sketch.to_local(group, (0, 20, 10))      # base's far corner
    b = face_sketch.to_local(group, (40, 20, 30))     # under the shelf
    line = win.model.add_node("line", dict(x1=a[0], y1=a[1], x2=b[0],
                                           y2=b[1], width=0.2),
                              parent=group)
    win.builder.active_tree().select_nodes([group])
    QTest.qWait(50)
    button, act = _rib_button(win)
    if button is not None:
        QTest.mouseClick(button, Qt.LeftButton)
    else:
        act.trigger()
    QTest.qWait(150)
    rib = next((n for n in win.model.root.walk()
                if n.type == "linear_extrude" and n.name.startswith("Rib")),
               None)
    assert rib is not None, win.statusBar().currentMessage()
    p = line.params
    got = (p["x1"], p["y1"], p["x2"], p["y2"])
    assert got == pytest.approx((a[0], a[1], b[0], b[1]), abs=1e-6)
    box = McpToolExecutor(win).execute(
        "get_node_bounds", {"node_ids": [rib.id]})["nodes"][0]
    assert box["min"][0] > -0.06, box          # not proud of the base's end
    assert box["max"][0] < 40.2, box      # pushed 0.1 into the block
    # the triangle 40 x 20 / 2 under the line, 10 thick
    assert _volume(win) - before == pytest.approx(400 * 10, rel=0.02)
