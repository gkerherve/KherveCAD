"""The lever, end to end with the mouse in the SolidWorks window: Sketch
Mode, the Top Plane, four circles and two lines, Features ▸ Extruded
Boss, three regions clicked in 3D, Done, the arrow dragged to 10 mm —
one solid with both holes through.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import time

import pytest
from PyQt5.QtCore import QEvent, QPoint, QPointF, QRectF, Qt
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import (QAction, QApplication, QPushButton, QTabBar,
                             QToolButton)

from khervecad import analysis, mesh, plane_pick, sketch_mode, toolbar_style
from khervecad import sketch_regions as R

_APP = QApplication.instance() or QApplication([])


@pytest.fixture
def win():
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    w.resize(1500, 950)
    toolbar_style.apply(w, "SolidWorks", remember=False)
    w.show()
    QTest.qWait(50)
    yield w
    toolbar_style.apply(w, "KherveCAD", remember=False)
    w._dirty = False
    w.close()


def _move(widget, p, buttons=Qt.NoButton, mods=Qt.NoModifier):
    QApplication.sendEvent(widget, QMouseEvent(
        QEvent.MouseMove, QPointF(p), Qt.NoButton, buttons, mods))


def _drag(widget, a, b, mods=Qt.NoModifier, steps=8):
    QTest.mousePress(widget, Qt.LeftButton, mods, a)
    for i in range(1, steps + 1):
        _move(widget, QPoint(a.x() + (b.x() - a.x()) * i // steps,
                             a.y() + (b.y() - a.y()) * i // steps),
              Qt.LeftButton, mods)
    QTest.mouseRelease(widget, Qt.LeftButton, mods, b)
    QTest.qWait(30)


def _button_for(win, action):
    return next(b for b in win.findChildren(QToolButton)
                if b.isVisible() and b.defaultAction() is action)


def _wait(cond, seconds=4.0):
    t0 = time.time()
    while not cond() and time.time() - t0 < seconds:
        QTest.qWait(40)
    return cond()


def _rim(c, r, deg):
    a = math.radians(deg)
    return (c[0] + r * math.cos(a), c[1] + r * math.sin(a))


def _open_top_sketch(win):
    """Sketch Mode, then a click on the Top Plane in 3D."""
    v2, v3 = win.view2d, win.view3d
    v2.scene().snap_enabled = False
    QTest.mouseClick(_button_for(win, sketch_mode.create_action(win)),
                     Qt.LeftButton)
    QTest.qWait(30)
    h = win._plane_pick["half"]
    cam = v3._camera()
    top = None
    for fx in (0.8, 0.6, -0.6, -0.8):
        for fy in (0.8, -0.8, 0.6, -0.6):
            q = v3._project(*cam, (h * fx, h * fy, 0.0))
            cand = QPoint(int(q[0]), int(q[1]))
            if plane_pick.hit(win, cand) == "Top (XY)":
                top = cand
                break
        if top:
            break
    assert top is not None
    QTest.mouseClick(v3, Qt.LeftButton, Qt.NoModifier, top)
    assert _wait(lambda: sketch_mode.sketching(win))
    QTest.qWait(200)
    v2.frame_rect(QRectF(-15, -15, 60, 50))
    QTest.qWait(30)


def _extruded_boss(win):
    """Features tab (leaves the sketch), then Extruded Boss/Base."""
    bar = next(b for b in win.findChildren(QTabBar) if b.isVisible() and
               any(b.tabText(i).replace("&", "") == "Features"
                   for i in range(b.count())))
    i = next(i for i in range(bar.count())
             if bar.tabText(i).replace("&", "") == "Features")
    QTest.mouseClick(bar, Qt.LeftButton, Qt.NoModifier,
                     bar.tabRect(i).center())
    assert _wait(lambda: not sketch_mode.sketching(win))
    QTest.qWait(300)
    act = next(a for a in win.findChildren(QAction)
               if a.data() == "linear_extrude")
    QTest.mouseClick(_button_for(win, act), Qt.LeftButton)
    QTest.qWait(50)


def _drag_arrow(win, height):
    """Pull the new extrude's blue arrow to *height* mm (Ctrl snaps)."""
    v3 = win.view3d
    scr = v3.edit_tool._screen()
    a = QPoint(int((scr["a"][0] + scr["b"][0]) / 2),
               int((scr["a"][1] + scr["b"][1]) / 2))
    ux, uy = scr["up"][0] - scr["a"][0], scr["up"][1] - scr["a"][1]
    n = math.hypot(ux, uy)
    px = height / scr["length"] * scr["scale"] * n
    b = QPoint(int(a.x() + ux / n * px), int(a.y() + uy / n * px))
    _move(v3, a)
    _drag(v3, a, b, Qt.ControlModifier, steps=10)


def _at(win, x, y):
    return win.view2d.mapFromScene(QPointF(x, y))


def test_the_lever_by_mouse_comes_out_one_solid_with_two_holes(win):
    v2, v3 = win.view2d, win.view3d
    _open_top_sketch(win)

    def at(x, y):
        return v2.mapFromScene(QPointF(x, y))
    big, small = ((0, 0), 10), ((30, 20), 6)
    for c, r in (big, small, ((0, 0), 4), ((30, 20), 2.5)):
        v2.set_tool("circle")
        _drag(v2.viewport(), at(*c), at(c[0] + r, c[1]))
    for deg in (125, -55):
        v2.set_tool("line")
        for c, r in (big, small):
            p = at(*_rim(c, r, deg))
            _move(v2.viewport(), p)
            QTest.mouseClick(v2.viewport(), Qt.LeftButton, Qt.NoModifier, p)
        QTest.keyClick(v2.viewport(), Qt.Key_Escape)
    comp = next(n for n in win.model.root.walk() if n.type == "component")
    assert [n.type for n in comp.children] == ["circle"] * 4 + ["line"] * 2
    # Features tab: leaves the sketch; Extruded Boss asks for regions
    _extruded_boss(win)
    assert v3._pick_cb is not None
    QTest.mouseClick(v3.nav_bar.buttons["fit"], Qt.LeftButton)
    QTest.qWait(100)
    cam = v3._camera()
    for world in (_rim((0, 0), 7, 200), (15, 10), _rim((30, 20), 4.3, 20)):
        q = v3._project(*cam, (world[0], world[1], 0.01))
        p = QPoint(int(round(q[0])), int(round(q[1])))
        _move(v3, p)
        QTest.mouseClick(v3, Qt.LeftButton, Qt.NoModifier, p)
        QTest.qWait(20)
    done = next(b for b in v3.findChildren(QPushButton)
                if b.isVisible() and "Done" in b.text())
    QTest.mouseClick(done, Qt.LeftButton)
    QTest.qWait(100)
    ext = [n for n in win.model.root.walk() if n.type == "linear_extrude"]
    assert len(ext) == 1
    # the new extrude starts flat; drag its arrow up 10 mm, Ctrl snaps
    _drag_arrow(win, 10.0)
    assert ext[0].params["height"] == pytest.approx(10)
    # one solid: the region's area times 10, both bores through
    region = next(n for n in win.model.root.walk() if n.type == "regions")
    loops = mesh.collect_outlines(region)
    assert len(loops) == 3                         # outline + two holes
    area = R._cross_section(loops).area()
    vol = analysis.mass_properties(mesh.tessellate(win.model.root))
    assert vol["volume"] == pytest.approx(area * 10, rel=1e-3)
    assert vol["size"][2] == pytest.approx(10, abs=1e-6)
    inside = lambda pt: sum(R._inside(pt, lp) for lp in loops) % 2
    assert not inside((0, 0)) and not inside((30, 20))   # bores through
    assert inside((0, 7)) and inside((15, 10)) and inside((30, 24.5))


def _volume(win):
    return analysis.mass_properties(mesh.tessellate(win.model.root))


def test_extruded_boss_on_one_rectangle_by_mouse(win):
    """A single shape is no region pick: Extruded Boss extrudes it at
    once, flat, and the arrow pulls it to height."""
    _open_top_sketch(win)
    win.view2d.set_tool("rect")
    _drag(win.view2d.viewport(), _at(win, 0, 0), _at(win, 30, 20))
    _extruded_boss(win)
    assert win.view3d._pick_cb is None             # no regions to pick
    ext = [n for n in win.model.root.walk() if n.type == "linear_extrude"]
    assert len(ext) == 1
    _drag_arrow(win, 8.0)
    assert ext[0].params["height"] == pytest.approx(8)
    rect = next(n for n in win.model.root.walk() if n.type == "rect")
    w, d = float(rect.params["width"]), float(rect.params["height"])
    assert (w, d) == (pytest.approx(30, abs=0.1), pytest.approx(20, abs=0.1))
    vol = _volume(win)
    assert vol["volume"] == pytest.approx(w * d * 8, rel=1e-6)
    assert vol["size"] == pytest.approx([w, d, 8], abs=1e-6)


def test_extruded_boss_on_a_triangle_of_lines_by_mouse(win):
    """Lines closing a shape (the line stops on its first point): the
    Extruded Boss asks for the region, one click and Done make the prism
    — and the triangle keeps its shape (its relations were solved on the
    wrong lines while they moved into the Regions node)."""
    _open_top_sketch(win)
    v2 = win.view2d
    v2.set_tool("line")
    for x, y in ((0, 0), (30, 0), (15, 20), (0, 0)):
        p = _at(win, x, y)
        _move(v2.viewport(), p)
        QTest.mouseClick(v2.viewport(), Qt.LeftButton, Qt.NoModifier, p)
    _extruded_boss(win)
    v3 = win.view3d
    assert v3._pick_cb is not None
    QTest.mouseClick(v3.nav_bar.buttons["fit"], Qt.LeftButton)
    QTest.qWait(100)
    q = v3._project(*v3._camera(), (15, 6, 0.01))
    p = QPoint(int(round(q[0])), int(round(q[1])))
    _move(v3, p)
    QTest.mouseClick(v3, Qt.LeftButton, Qt.NoModifier, p)
    done = next(b for b in v3.findChildren(QPushButton)
                if b.isVisible() and "Done" in b.text())
    QTest.mouseClick(done, Qt.LeftButton)
    QTest.qWait(100)
    _drag_arrow(win, 5.0)
    ext = [n for n in win.model.root.walk() if n.type == "linear_extrude"]
    assert len(ext) == 1 and ext[0].params["height"] == pytest.approx(5)
    lines = [n for n in win.model.root.walk() if n.type == "line"]
    pts = {(round(float(n.params[k1]), 1), round(float(n.params[k2]), 1))
           for n in lines for k1, k2 in (("x1", "y1"), ("x2", "y2"))}
    assert pts == {(0.0, 0.0), (30.0, 0.0), (15.0, 20.0)}
    xs = [x for x, _y in pts]
    ys = [y for _x, y in pts]
    area = abs((xs[1] - xs[0]) * (ys[2] - ys[0])
               - (xs[2] - xs[0]) * (ys[1] - ys[0])) / 2
    vol = _volume(win)
    assert vol["volume"] == pytest.approx(area * 5, rel=2e-3)


def _select_all_shapes(win, corner=(-14, 30), other=(40, -14)):
    """Select every sketch shape with the mouse: the Select tool and a
    box dragged round the sketch from empty space."""
    v2 = win.view2d
    v2.set_tool("select")
    from khervecad.model import SHAPE_2D
    _drag(v2.viewport(), _at(win, *corner), _at(win, *other))
    QTest.qWait(50)
    return [n for n in win.model.root.walk() if n.category == SHAPE_2D]


def test_selected_lines_and_circles_extrude_at_once(win):
    """Select the lever's sides and circles, Extruded Boss: the area
    they close comes out at once, both bores through — no regions to
    click."""
    _open_top_sketch(win)
    v2 = win.view2d
    big, small = ((0, 0), 10), ((30, 20), 6)
    for c, r in (big, small, ((0, 0), 4), ((30, 20), 2.5)):
        v2.set_tool("circle")
        _drag(v2.viewport(), _at(win, *c), _at(win, c[0] + r, c[1]))
    for deg in (125, -55):
        v2.set_tool("line")
        for c, r in (big, small):
            p = _at(win, *_rim(c, r, deg))
            _move(v2.viewport(), p)
            QTest.mouseClick(v2.viewport(), Qt.LeftButton, Qt.NoModifier, p)
        QTest.keyClick(v2.viewport(), Qt.Key_Escape)
    shapes = _select_all_shapes(win)
    picked = win.builder.active_tree().selected_nodes()
    assert set(map(id, picked)) == set(map(id, shapes))
    # Extruded Boss straight from the sketch's own selection
    act = next(a for a in win.findChildren(QAction)
               if a.data() == "linear_extrude")
    act.trigger()
    QTest.qWait(100)
    assert win.view3d._pick_cb is None             # nothing to click
    ext = [n for n in win.model.root.walk() if n.type == "linear_extrude"]
    assert len(ext) == 1
    region = next(n for n in win.model.root.walk() if n.type == "regions")
    loops = mesh.collect_outlines(region)
    inside = lambda pt: sum(R._inside(pt, lp) for lp in loops) % 2
    assert not inside((0, 0)) and not inside((30, 20))
    assert inside((0, 7)) and inside((15, 10))


def test_a_washer_of_two_circles_keeps_its_hole(win):
    _open_top_sketch(win)
    v2 = win.view2d
    for r in (10, 4):
        v2.set_tool("circle")
        _drag(v2.viewport(), _at(win, 0, 0), _at(win, r, 0))
    _select_all_shapes(win)
    act = next(a for a in win.findChildren(QAction)
               if a.data() == "linear_extrude")
    act.trigger()
    QTest.qWait(100)
    region = next(n for n in win.model.root.walk() if n.type == "regions")
    loops = mesh.collect_outlines(region)
    assert len(loops) == 2                         # a ring, not a disc
