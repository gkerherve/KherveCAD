"""SolidWorks' Up To Body by mouse (Exercise 58: the Ø44 boss goes down
onto the fork and hub). The profile lands on the body's SURFACE
everywhere — the depth is where the LAST ray from the profile meets the
body, not a plane through the body's near face.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest

import test_lever_by_mouse as L
import test_extrude_from_offset_by_mouse as F
from khervecad import extent, extrude_panel

win = L.win


def _slope(model, parent=None):
    """A thick slab rising along +x: its underside is z = 40 at x = 0 and
    z = 40 + x * tan(10 deg) beyond."""
    move = model.add_node("translate", dict(x=0, y=-20, z=40), parent=parent)
    turn = model.add_node("rotate", dict(x=0, y=-10, z=0), parent=move)
    model.add_node("cube", dict(width=120, depth=60, height=6), parent=turn)
    move.name = "Roof"
    return move


def _reopen(win, ext):
    """Adding the body closed the Extrude window; the user clicks the
    extrude in the tree and the window is back."""
    from khervecad import drag_feature
    drag_feature.start(win, ext, panel=True)
    QTest.qWait(100)
    panel = extrude_panel._panel(win)
    assert panel is not None and panel.isVisible()
    return panel


def test_contact_depth_is_where_the_whole_profile_lands(win):
    panel, ext = F._rect_extrude(win)
    slab = _slope(win.model, ext.parent)
    panel = _reopen(win, ext)
    h = extent.set_extent(win.model, ext, "up_to", "Roof", "contact")
    near = extent.set_extent(win.model, ext, "up_to", "Roof", "near")
    # the rectangle spans x 0..30: its far edge meets the slab 5 mm
    # higher than its near edge, and the boss must reach that far
    assert h > 44
    assert h >= near + 2
    extent.set_extent(win.model, ext, "up_to", "Roof", "contact")
    lo, hi = F._z(win, ext)
    assert hi == pytest.approx(h, abs=0.1)
    QTest.mouseClick(panel.ok, Qt.LeftButton)


def test_up_to_body_pick_in_the_extrude_window(win):
    """Window: End condition Up To Body, then a click on the body in 3D."""
    panel, ext = F._rect_extrude(win)
    slab = _slope(win.model, ext.parent)
    panel = _reopen(win, ext)
    v3 = win.view3d
    v3.fit()
    QTest.qWait(150)
    F._choose(panel.fields["extent"], "Up To Body")
    assert v3._pick_cb is not None, "Up To Body asks for a click"
    # click the slab's near end face
    import math
    a = math.radians(10)
    world = (60 * math.cos(a), 10, 40 + 60 * math.sin(a) + 3)
    win.view3d.fit()
    QTest.qWait(150)
    q = v3._project(*v3._camera(), world)
    p = QPoint(int(q[0]), int(q[1]))
    QTest.mouseMove(v3, p)
    QTest.mouseClick(v3, Qt.LeftButton, Qt.NoModifier, p)
    QTest.qWait(200)
    assert ext.params.get("up_to_side") == "contact"
    assert ext.params["height"] > 44
    assert extrude_panel._panel(win) is panel
    QTest.mouseClick(panel.ok, Qt.LeftButton)
