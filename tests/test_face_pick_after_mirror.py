"""Sketch Mode: a click on the top face of a MIRRORED feature's original
opens a sketch on that face (2026-11-20, the bearing support filmed by
mouse: after Mirror, clicking the lug's top face picked nothing).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad.mainwindow import MainWindow
from khervecad.mcp_tools import McpToolExecutor


@pytest.fixture
def win():
    QApplication.instance() or QApplication([])
    w = MainWindow()
    w.resize(1400, 900)
    w.show()
    QTest.qWaitForWindowExposed(w)
    yield w
    w._dirty = False
    w.close()


def test_the_originals_face_after_a_mirror_opens_a_sketch(win):
    from khervecad import feature_pick, mirror_feature
    ex = McpToolExecutor(win)
    ex.execute("apply_code", {"code":
               "translate([-10, 0, 0]) cube([20, 60, 40]);\n"
               "translate([35, 10, 0]) cube([45, 40, 10]);\n"})
    QTest.qWait(100)
    lug = [n for n in win.model.root.walk() if n.type == "cube"][-1]
    mirror_feature.mirror(win, [lug], ("main", "Side (YZ)"))
    QTest.qWait(200)
    win.builder.active_tree().clearSelection()
    v = win.view3d
    v.yaw, v.pitch = -60.0, 45.0
    v.fit()
    QTest.qWait(200)
    feature_pick.start(win, feature_pick.SKETCH)
    QTest.qWait(100)
    for key in ("regions", "planes"):
        feature_pick.toggled(win, key, False)
    QTest.qWait(100)
    q = v._project(*v._camera(), (72, 30, 10))
    p = QPoint(int(round(q[0])), int(round(q[1])))
    QTest.mouseMove(v, p)
    QTest.qWait(50)
    QTest.mouseClick(v, Qt.LeftButton, Qt.NoModifier, p)
    QTest.qWait(300)
    g = getattr(win, "_face_sketch", None)
    assert g is not None, win.statusBar().currentMessage()
    assert float(g.params["z"]) == pytest.approx(10, abs=1e-3)
