"""A face is the connected flat region under the click, not every
coplanar triangle of the part (Exercise 59: the floor inside the curved
wall, offset 9 inward, also took the plate's outer corner beyond the wall).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QPointF
from PyQt5.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication([])


def _window():
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.show()
    # a plate cut in two islands by a trench that runs across it
    plate = win.model.add_node("cube", dict(width=100, depth=100,
                                            height=10))
    trench = win.model.add_node("cube", dict(width=10, depth=120,
                                             height=20, x=40, y=-10,
                                             z=2))
    both = win.model.wrap_nodes([plate, trench], "difference")
    return win, both


def test_a_face_sketch_outlines_only_the_clicked_island():
    from khervecad import face_sketch
    win, part = _window()
    try:
        g = face_sketch.make(win, part, [75, 50, 10], [0, 0, 1])
        _APP.processEvents()
        segs = win.view2d.scene().face_outline["segments"]
        xs = [p[0] for a, b in segs for p in (a, b)]
        # sketch x = scope x here: the island right of the wall
        assert min(xs) == pytest.approx(50, abs=1e-3) and \
            max(xs) == pytest.approx(100, abs=1e-3)
        assert g is not None
    finally:
        win._dirty = False
        win.close()


def test_offset_entities_takes_the_island_edges_by_mouse():
    """Click the inner face, Offset Entities, click inside the face: the
    copies run 9 inside the island (the trench side, the plate's edges),
    corners joined into one closed loop."""
    from khervecad import face_sketch, sketch_offset
    win, part = _window()
    try:
        face_sketch.make(win, part, [75, 50, 10], [0, 0, 1])
        _APP.processEvents()
        scene = win.view2d.scene()
        panel = sketch_offset.start(win)
        panel.fields["distance"].setValue(9)
        # one click inside the face takes its whole boundary
        assert sketch_offset.press_2d(scene, QPointF(75, 50), 0.8)
        panel.ok.click()
        sk = face_sketch.current(win) or None
        group = sk if sk is not None else next(
            n for n in win.model.root.walk() if n.name.startswith(
                "Sketch on"))
        xs = sorted({round(n.params[k], 3) for n in group.walk()
                     if n.type == "line" for k in ("x1", "x2")})
        assert xs == [59.0, 91.0]
        ys = sorted({round(n.params[k], 3) for n in group.walk()
                     if n.type == "line" for k in ("y1", "y2")})
        assert ys == [9.0, 91.0]
    finally:
        win._dirty = False
        win.close()
