# KherveCAD — GPL-3.0-or-later. Copyright (C) 2026 Gwilherm Kerherve
"""The 3D view's view cube: a face click looks square on to it."""

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
import pytest

from khervecad import view_cube


def test_angles_match_the_standard_views():
    assert view_cube.angles((0, -1, 0)) == (-90.0, 0.0)
    assert view_cube.angles((1, 0, 0))[0] == 0.0
    assert view_cube.angles((0, 0, 1))[1] == 89.0
    assert len(view_cube.cells()) == 54


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def test_clicking_the_cube_turns_the_view(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(1200, 800)
    win.show()
    view = win.view3d
    cube = view.view_cube
    view.yaw, view.pitch = -65.0, 35.0
    # find the middle of the TOP face on screen and click it
    centre = cube._screen((0, 0, 1))
    assert cube.cell_at(centre.toPoint()) == (0, 0, 1)
    QTest.mouseClick(cube, Qt.LeftButton, pos=QPoint(int(centre.x()),
                                                     int(centre.y())))
    for _ in range(100):
        QTest.qWait(30)
        if abs(view.pitch - 89.0) < 0.5:
            break
    assert abs(view.pitch - 89.0) < 0.5
    assert win._view_cube_act.isChecked()
    win._dirty = False
    win.close()
