"""Rib by MOUSE with a line that stops short of the part (2026-11-14,
Exercise 52: the bracket's rib line ends 2 mm under the bearing): the
sketch selected, the ribbon's Rib button clicked — the line is run on to
the part and the rib fills to it, as SolidWorks does.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QAction

from test_lever_by_mouse import win, _button_for  # noqa: F401
from test_rib import _volume
from test_rib_extends import CODE


def _rib_button(win):
    act = next(a for a in win.findChildren(QAction)
               if a.data() in ("rib", "cut:rib", "boss:rib")
               and a.isEnabled())
    try:
        return _button_for(win, act), act
    except StopIteration:
        return None, act


def test_rib_button_runs_a_short_line_on_to_the_part(win):
    from khervecad import face_sketch, refgeom_ui
    from khervecad.mcp_tools import McpToolExecutor
    McpToolExecutor(win).execute("apply_code", {"code": CODE})
    QTest.qWait(50)
    before = _volume(win)
    group = refgeom_ui.sketch_on(win, origin=(0, 20, 0), normal=(0, 1, 0),
                                 label="Rib plane", open_2d=False)
    a = face_sketch.to_local(group, (30, 20, 48))     # 2 under the shelf
    b = face_sketch.to_local(group, (30, 20, 10))     # on the base
    win.model.add_node("line", dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1],
                                    width=0.2), parent=group)
    win.builder.active_tree().select_nodes([group])
    QTest.qWait(50)
    button, act = _rib_button(win)
    if button is not None:
        QTest.mouseClick(button, Qt.LeftButton)
    else:                                   # on a ribbon tab not shown
        act.trigger()
    QTest.qWait(150)
    rib = next((n for n in win.model.root.walk()
                if n.type == "linear_extrude" and n.name.startswith("Rib")),
               None)
    assert rib is not None, win.statusBar().currentMessage()
    assert _volume(win) - before == pytest.approx(20 * 40 * 10, rel=0.03)
