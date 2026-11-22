"""A sketch point behind the camera made picking in 3D crash (the Plane
tool, Exercise 010)."""
from PyQt5.QtWidgets import QApplication

from khervecad.mainwindow import MainWindow


def test_a_pick_point_behind_the_camera_is_skipped():
    QApplication.instance() or QApplication([])
    w = MainWindow()
    w.show()
    v = w.view3d
    eye, _r, _u, fwd = v._camera()
    behind = [eye[i] - 5.0 * fwd[i] for i in range(3)]
    v.pick_points = [behind]
    assert v._pick_at(50, 50) is not None          # no TypeError
    w._dirty = False
    w.close()
