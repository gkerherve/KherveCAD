"""The model behind a 2D sketch, and only THAT sketch's shapes (2026-11-10,
the user: "when we go from 3D to 2D ... whatever we select is what should
be sketched in the 2D. Take great effort in making sure that the 2D just
look exactly what it should be. Do some tests with different pieces and
see if it's exactly where it should be").

Each test opens Sketch Mode on a face of a known piece and reads the
picture painted behind the sketch at known places of the part: solid
where the part is, clear where it is not, its edges where they are to a
fraction of a millimetre.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QSettings
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import (face_sketch, normal_to, sketch_backdrop,
                       sketch_focus, sketch_mode, toolbar_style)
from khervecad.mainwindow import MainWindow
from khervecad.mcp_tools import McpToolExecutor

BLOCK = """
difference() {
  union() {
    cube([100, 60, 20]); // Base
    translate([55, 10, 20]) cube([40, 20, 15]); // Boss
    translate([20, 40, 20]) cylinder(h = 10, r = 8); // Post
  }
  translate([20, 15, -1]) cylinder(h = 30, r = 5); // Hole
}
"""
BRACKET = """
linear_extrude(height = 40) polygon([[0, 0], [60, 0], [60, 8], [8, 8], [8, 50], [0, 50]]); // L bracket
"""
WEDGE = """
translate([30, -20, 5]) rotate([90, 0, 0]) linear_extrude(height = 30) polygon([[0, 0], [50, 0], [0, 30]]); // Wedge
"""


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    w = MainWindow()
    w.resize(1300, 850)
    w.show()
    toolbar_style.apply(w, "SolidWorks")
    yield w
    if sketch_mode.sketching(w):
        sketch_mode.finish(w)
        QTest.qWait(600)
    toolbar_style.apply(w, "KherveCAD")
    w._dirty = False
    w.close()


def _piece(win, code):
    McpToolExecutor(win).execute("apply_code", {"code": code})
    QApplication.processEvents()
    QTest.qWait(100)
    return next(c for c in win.model.root.children
                if c.visible and c.type != "assign")


def _sketch_on(win, part, point, normal):
    group = face_sketch.make(win, part, point, normal)
    QTest.qWait(900)                           # the turn, then the 2D
    assert sketch_mode.sketching(win) and win.view2d.isVisible()
    assert sketch_backdrop.refresh(win)
    return group


class Picture:
    """The backdrop, read at WORLD points."""

    def __init__(self, win, group=None):
        st = win._sketch_backdrop
        self.image, self.rect = st["image"], st["rect"]
        self.focus = sketch_focus.current(win)
        self.group = group

    def _local(self, world):
        if self.group is not None:
            return face_sketch.to_local(self.group, world)
        from khervecad.view2d import PLANES
        (a, b), _k = PLANES[self.focus.plane]
        return world[a], world[b]

    def pixel(self, world):
        x, y, w, h = self.rect
        sx, sy = self._local(world)
        col = (sx - x) / w * self.image.width()
        row = (sy - y) / h * self.image.height()   # stored upside down
        return int(col), int(row)

    def solid(self, world):
        col, row = self.pixel(world)
        assert 0 <= col < self.image.width() and \
            0 <= row < self.image.height(), "outside the picture"
        return self.image.pixelColor(col, row).alpha() > 128

    def edge_along(self, a, b, steps=400):
        """Where, from world point *a* to *b*, the picture turns from
        solid to clear (or back): the fraction of the way."""
        first = self.solid(a)
        for i in range(1, steps + 1):
            t = i / steps
            p = [a[k] + (b[k] - a[k]) * t for k in range(3)]
            if self.solid(p) != first:
                return t
        return None


# ------------------------------------------------- where the part is
def test_the_top_of_a_block_with_a_boss_a_post_and_a_hole(win):
    part = _piece(win, BLOCK)
    g = _sketch_on(win, part, (80, 50, 20), (0, 0, 1))
    pic = Picture(win, g)
    assert pic.solid((80, 50, 20))             # the face
    assert pic.solid((75, 20, 20))             # under the boss: the boss
    assert pic.solid((20, 40, 20))             # the post
    assert not pic.solid((20, 15, 20))         # the hole goes through
    assert not pic.solid((-2, 30, 20)) and not pic.solid((102, 30, 20))
    assert not pic.solid((50, -2, 20)) and not pic.solid((50, 62, 20))
    # its edges, to a quarter of a millimetre
    t = pic.edge_along((90, 50, 20), (110, 50, 20))
    assert 90 + 20 * t == pytest.approx(100.0, abs=0.25)
    t = pic.edge_along((50, 50, 20), (50, 70, 20))
    assert 50 + 20 * t == pytest.approx(60.0, abs=0.25)
    t = pic.edge_along((20, 15, 20), (30, 15, 20))     # out of the hole
    assert 20 + 10 * t == pytest.approx(25.0, abs=0.3)


def test_the_front_of_the_block_shows_what_stands_above_it(win):
    part = _piece(win, BLOCK)
    g = _sketch_on(win, part, (30, 0, 10), (0, -1, 0))
    pic = Picture(win, g)
    assert pic.solid((50, 0, 10))              # the face
    assert pic.solid((75, 0, 28))              # the boss, behind it
    assert pic.solid((20, 0, 25))              # the post, further back
    assert not pic.solid((42, 0, 28))          # between post and boss
    assert not pic.solid((50, 0, -2)) and not pic.solid((50, 0, 37))
    t = pic.edge_along((75, 0, 30), (75, 0, 40))       # the boss's top
    assert 30 + 10 * t == pytest.approx(35.0, abs=0.25)
    t = pic.edge_along((50, 0, 15), (50, 0, 25))       # the block's top
    assert 15 + 10 * t == pytest.approx(20.0, abs=0.25)


def test_the_right_side_is_not_mirrored(win):
    """Seen from +x, y runs to the RIGHT... of the viewer: the boss
    (y 10..30) and the post (y 32..48) keep their sides."""
    part = _piece(win, BLOCK)
    g = _sketch_on(win, part, (100, 30, 10), (1, 0, 0))
    pic = Picture(win, g)
    assert pic.solid((100, 20, 28))            # the boss
    assert pic.solid((100, 40, 25))            # the post
    assert not pic.solid((100, 5, 28)) and not pic.solid((100, 55, 28))
    assert not pic.solid((100, 40, 33))        # above the post (h 10)
    assert pic.solid((100, 20, 33))            # the boss is 15 high


def test_the_bottom_is_seen_from_below(win):
    part = _piece(win, BLOCK)
    g = _sketch_on(win, part, (60, 40, 0), (0, 0, -1))
    pic = Picture(win, g)
    assert pic.solid((60, 40, 0)) and not pic.solid((20, 15, 0))
    assert pic.solid((20, 40, 0))              # no hole under the post
    t = pic.edge_along((90, 30, 0), (110, 30, 0))
    assert 90 + 20 * t == pytest.approx(100.0, abs=0.25)


def test_an_inside_face_of_a_bracket(win):
    part = _piece(win, BRACKET)
    g = _sketch_on(win, part, (8, 30, 20), (1, 0, 0))
    pic = Picture(win, g)
    assert pic.solid((8, 30, 20))              # the upright's inner face
    assert pic.solid((8, 4, 20))               # the floor leg, end on
    assert not pic.solid((8, 52, 20)) and not pic.solid((8, 30, 42))
    t = pic.edge_along((8, 45, 20), (8, 55, 20))
    assert 45 + 10 * t == pytest.approx(50.0, abs=0.25)


def test_a_sloping_face(win):
    part = _piece(win, WEDGE)
    # the slope runs from (80, y, 5) up to (30, y, 35), y from -50 to -20
    g = _sketch_on(win, part, (55, -35, 20), (0.5145, 0, 0.8575))
    pic = Picture(win, g)
    assert pic.solid((55, -35, 20))
    assert pic.solid((78, -22, 6.2)) and pic.solid((32, -48, 33.8))
    # just past its ends and sides, in the face's own plane
    assert not pic.solid((82, -35, 3.8))
    assert not pic.solid((28, -35, 36.2))
    assert not pic.solid((55, -18, 20)) and not pic.solid((55, -52, 20))
    t = pic.edge_along((55, -30, 20), (55, -10, 20))
    assert -30 + 20 * t == pytest.approx(-20.0, abs=0.25)


# ------------------------------------------------- what the 2D shows
def test_the_whole_face_is_on_show(win):
    part = _piece(win, BLOCK)
    v3 = win.view3d
    v3.yaw, v3.pitch, v3.distance = 30.0, 20.0, 40.0   # zoomed in close
    v3.target = [95.0, 55.0, 18.0]
    _sketch_on(win, part, (80, 50, 20), (0, 0, 1))
    v2 = win.view2d
    seen = v2.mapToScene(v2.viewport().rect()).boundingRect()
    assert seen.left() < 0 and seen.right() > 100
    assert seen.top() < 0 and seen.bottom() > 60
    # ... and it fills the view: not a speck in the middle
    assert seen.width() < 100 * 2.2


def test_the_picture_is_redone_when_the_view_leaves_it(win):
    part = _piece(win, BLOCK)
    g = _sketch_on(win, part, (80, 50, 20), (0, 0, 1))
    st = win._sketch_backdrop
    first = st["rect"]
    v2 = win.view2d
    v2.centerOn(400.0, 300.0)                  # far from the part
    QTest.qWait(50)
    v2.viewport().repaint()
    QTest.qWait(sketch_backdrop.DELAY_MS + 250)
    assert st["rect"] != first
    seen = v2.mapToScene(v2.viewport().rect()).boundingRect()
    r = st["rect"]
    assert r[0] <= seen.left() and r[0] + r[2] >= seen.right()
    # ... and when the model changes
    v2.centerOn(50.0, 30.0)
    QTest.qWait(sketch_backdrop.DELAY_MS + 250)
    assert Picture(win, g).solid((98, 58, 20))
    cube = next(n for n in part.walk() if n.type == "cube"
                and float(n.params.get("width", 0)) == 100)
    win.model.set_param(cube, "width", 90.0)
    QTest.qWait(sketch_backdrop.DELAY_MS + 400)
    assert not Picture(win, g).solid((98, 58, 20))


def test_editing_an_earlier_sketch_shows_the_part_rolled_back(
        win, monkeypatch):
    """SolidWorks rolls the part back to the sketch being edited."""
    from test_stacked_features import _rect_feature
    from khervecad import cut_feature
    monkeypatch.setattr(cut_feature, "IN_3D", True)
    part = _piece(win, "cube([100, 60, 20]); // Base\n")
    boss = _rect_feature(win, part, (50, 30, 20), (20, 20), (60, 40),
                         height=10.0)
    pin = _rect_feature(win, part, (40, 30, 30), (30, 25), (40, 35),
                        height=6.0)
    QApplication.processEvents()
    rect = next(c for c in boss.walk() if c.type == "rect")
    normal_to.edit(win, rect)
    QTest.qWait(900)
    assert sketch_backdrop.refresh(win)
    focus = sketch_focus.current(win)
    tris, _cols = focus.mesh()
    top = max(v[2] for t in tris for v in t[:3])
    assert top == pytest.approx(20.0)          # no boss, no pin: the base
    # ... and the 2D holds that sketch's shapes only
    shown = {it.node for it in win.view2d.scene()._items.values()}
    assert rect in shown
    assert not any(n.parent is not rect.parent for n in shown)
    assert not win.view2d.scene()._part_items


def test_a_plane_sketch_shows_no_other_planes_shapes(win, monkeypatch):
    """The user's "random circles": every sketch square on to the view
    was drawn, whatever its height and whichever feature it made."""
    from test_stacked_features import _rect_feature
    from khervecad import cut_feature
    monkeypatch.setattr(cut_feature, "IN_3D", True)
    part = _piece(win, "cube([100, 60, 20]); // Base\n")
    _rect_feature(win, part, (50, 30, 20), (20, 20), (60, 40), height=10.0)
    m = win.model
    loose = m.add_node("circle", dict(x=5.0, y=5.0, radius=3.0))
    high = m.add_node("translate", dict(x=0.0, y=0.0, z=40.0))
    m.add_node("circle", dict(x=50.0, y=30.0, radius=9.0), parent=high)
    QApplication.processEvents()
    normal_to.turn_to(win, "Top (XY)")
    QTest.qWait(900)
    shown = [it.node for it in win.view2d.scene()._items.values()]
    assert shown == [loose]                    # on the Top plane, unused
    assert not win.view2d.scene()._part_items
    # the model is behind it all the same
    assert sketch_backdrop.refresh(win)
    pic = Picture(win)
    assert pic.solid((80, 50, 0)) and not pic.solid((120, 50, 0))
    # leaving Sketch Mode gives the overview back
    sketch_mode.finish(win)
    QTest.qWait(700)
    assert sketch_focus.current(win) is None


def test_a_sketch_point_is_a_small_mark_at_any_zoom(win):
    from khervecad.view2d import is_sketch_point
    m = win.model
    pt = m.add_node("circle", dict(x=0.0, y=0.0, radius=0.25))
    m.set_modifier(pt, "%")
    QApplication.processEvents()
    assert is_sketch_point(pt)
    v2 = win.view2d
    item = v2.scene()._items[pt.id]
    k = abs(v2.transform().m11())
    v2.scale(40.0, 40.0)                       # far in: 0.25 mm is big
    box = item.shape().boundingRect()
    px = box.width() * abs(v2.transform().m11())
    assert px < 20                             # still a few pixels
    assert k > 0


# ------------------------------------------------- the views round it
def test_no_corner_views_unless_asked_for(win):
    settings = QSettings("Kherve", "KherveCAD")
    settings.remove(sketch_mode.CORNER_KEY)
    try:
        part = _piece(win, BLOCK)
        sketch_mode._show(win, False)
        for name in ("_sketch_inset", "_sketch_mini2d"):
            w = getattr(win, name, None)
            assert w is None or not w.isVisible()
        _sketch_on(win, part, (80, 50, 20), (0, 0, 1))
        for name in ("_sketch_inset", "_sketch_mini2d"):
            w = getattr(win, name, None)
            assert w is None or not w.isVisible()
        act = sketch_mode.corner_action(win)
        act.setChecked(False)                  # (made ticked by conftest)
        act.setChecked(True)
        assert win._sketch_inset.isVisible()
        act.setChecked(False)
        assert not win._sketch_inset.isVisible()
    finally:
        settings.setValue(sketch_mode.CORNER_KEY, True)


def test_the_2d_toolbar_is_along_the_foot_centred(win):
    part = _piece(win, BLOCK)
    _sketch_on(win, part, (80, 50, 20), (0, 0, 1))
    QTest.qWait(50)
    v2 = win.view2d
    bar = v2.nav_bar
    geo, port = bar.geometry(), v2.viewport().geometry()
    assert abs(geo.center().x() - port.center().x()) <= 2
    assert port.bottom() - geo.bottom() < 30 and geo.top() > port.height() / 2
    # on a face the Front / Top / Right buttons are not offered
    assert not any(b.isVisible() for b in win._plane_buttons.values())
    sketch_mode.finish(win)
    QTest.qWait(700)
    normal_to.turn_to(win, "Top (XY)")
    QTest.qWait(900)
    assert all(b.isVisible() for b in win._plane_buttons.values())
