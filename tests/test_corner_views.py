"""The small 3D / 2D corner views resize from their top-left grip.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import QEvent, QPoint, QPointF, QSettings, Qt
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication([])


def _send(widget, kind, local, button=Qt.LeftButton):
    glob = widget.mapToGlobal(local)
    ev = QMouseEvent(kind, QPointF(local), QPointF(glob), button,
                     button if kind != QEvent.MouseButtonRelease
                     else Qt.NoButton, Qt.NoModifier)
    QApplication.sendEvent(widget, ev)


def test_grip_shrinks_and_remembers():
    from khervecad import sketch_mode
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        for view in (sketch_mode._mini2d(win), sketch_mode._inset(win)):
            w, h = view.W, view.H
            _send(view, QEvent.MouseButtonPress, QPoint(5, 5))
            # mouse move events go to the grabbing widget: send directly
            view.mouseMoveEvent(QMouseEvent(
                QEvent.MouseMove, QPointF(5, 5),
                QPointF(view.mapToGlobal(QPoint(65, 45))),
                Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
            view.mouseReleaseEvent(None)
            assert (view.W, view.H) == (w - 60, h - 40)
            saved = QSettings("Kherve", "KherveCAD").value(view.KEY)
            assert saved == "%dx%d" % (w - 60, h - 40)
            view.set_size(10, 10)                 # never vanishes
            assert (view.W, view.H) == (view.MIN_W, view.MIN_H)
    finally:
        win._dirty = False
        win.close()
