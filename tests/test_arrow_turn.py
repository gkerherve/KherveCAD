"""Arrows (and Ctrl/Cmd + arrows) turn the 3D view; Shift pans."""
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from khervecad.view3d import View3D


def test_arrows_turn_and_shift_pans():
    v = View3D()
    y0, p0, t0 = v.yaw, v.pitch, list(v.target)
    for mod in (Qt.NoModifier, Qt.ControlModifier):
        y, p = v.yaw, v.pitch
        QTest.keyClick(v, Qt.Key_Right, mod)
        assert v.yaw != y
        QTest.keyClick(v, Qt.Key_Up, mod)
        assert v.pitch != p
    QTest.keyClick(v, Qt.Key_Left, Qt.ShiftModifier)
    assert v.target != t0
