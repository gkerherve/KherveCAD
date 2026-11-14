"""Fillet by MOUSE on an R32-style rib foot (2026-11-14, Exercise 52):
the ribbon's Fillet with nothing selected, a click on the concave edge
in the 3D view, radius larger than the face beyond it — the fillet stays
within the part's width and stays one closed solid (a later cut cuts).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QAction

from test_lever_by_mouse import win, _button_for, _move, _wait  # noqa: F401
from test_fillet_overflow import CODE


def test_a_picked_fillet_stays_on_the_part_by_mouse(win):
    from khervecad import csg, mesh
    from khervecad.mcp_tools import McpToolExecutor
    McpToolExecutor(win).execute("apply_code", {"code": CODE})
    QTest.qWait(100)
    win.builder.active_tree().select_nodes([])
    act = next(a for a in win.findChildren(QAction)
               if a.data() == "fillet" and a.isEnabled())
    try:
        QTest.mouseClick(_button_for(win, act), Qt.LeftButton)
    except StopIteration:
        act.trigger()
    v3 = win.view3d
    assert _wait(lambda: v3._pick_cb is not None), "Fillet asks no click"
    QTest.mouseClick(v3.nav_bar.buttons["fit"], Qt.LeftButton)
    QTest.qWait(100)
    # the concave edge where the wall meets the base: x 30, z 10
    q = v3._project(*v3._camera(), (30.0, 10.0, 10.0))
    p = QPoint(int(round(q[0])), int(round(q[1])))
    _move(v3, p)
    QTest.mouseClick(v3, Qt.LeftButton, Qt.NoModifier, p)
    QTest.qWait(100)
    v3.cancel_pick()
    fil = next((n for n in win.model.root.walk() if n.type == "fillet"),
               None)
    assert fil is not None and fil.params.get("edges"), "no edge picked"
    seed = fil.params["edges"][0]
    assert seed[0] == pytest.approx(30, abs=0.5) and \
        seed[2] == pytest.approx(10, abs=0.5), seed      # that edge
    win.model.set_param(fil, "radius", 15)          # Properties: 15
    QTest.qWait(100)
    xs = [pt[0] for t in mesh.tessellate(win.model.root) for pt in t[:3]]
    assert max(xs) == pytest.approx(40, abs=0.05)
    rows = mesh._tess(fil, {}, None, set(), False)
    assert csg.to_manifold(rows, {}) is not None
