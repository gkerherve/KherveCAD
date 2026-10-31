"""Extrude end conditions: through all and up to an object.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import extent
from khervecad.model import DocumentModel
from test_lever_by_mouse import win  # noqa: F401


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_through_all_cuts_the_whole_body(app):
    m = DocumentModel()
    d = m.add_node("difference", {})
    m.add_node("cube", dict(width=40, depth=40, height=30), parent=d)
    t = m.add_node("translate", dict(x=20, y=20, z=10), parent=d)
    ex = m.add_node("linear_extrude", dict(height=1), parent=t)
    m.add_node("circle", dict(radius=4), parent=ex)
    extent.set_extent(m, ex, "through_all")
    # the body spans z -10..20 in the extrude's frame -> 2 * (20 + 1)
    assert ex.params["height"] == pytest.approx(42)
    assert ex.params["center"] is True
    d.children[0].params["height"] = 60       # the body grows
    extent.refresh(m)
    assert ex.params["height"] == pytest.approx(2 * 51)


def test_up_to_an_object(app):
    m = DocumentModel()
    roof = m.add_node("cube", dict(z=50, width=10, depth=10, height=5))
    roof.name = "Roof"
    ex = m.add_node("linear_extrude", dict(height=1))
    m.add_node("rect", dict(width=5, height=5), parent=ex)
    assert extent.set_extent(m, ex, "up_to", "Roof", "near") == \
        pytest.approx(50)
    assert extent.set_extent(m, ex, "up_to", "Roof", "far", 2) == \
        pytest.approx(57)
    with pytest.raises(ValueError):
        extent.set_extent(m, ex, "up_to", "Nobody")


def test_window_keeps_the_depth_live(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        m = win.model
        roof = m.add_node("cube", dict(z=50))
        roof.name = "Roof"
        ex = m.add_node("linear_extrude", dict(height=1))
        m.add_node("rect", {}, parent=ex)
        m.set_param(ex, "up_to", "Roof")
        m.set_param(ex, "extent", "up_to")
        assert ex.params["height"] == pytest.approx(70)
        m.set_param(roof, "z", 80)
        assert ex.params["height"] == pytest.approx(100)
    finally:
        win._dirty = False
        win.close()


# ---- SolidWorks' whole Direction 1 list (2026-10-31, the user)
def _plate_with_cutter(app):
    """A 40 x 40 plate z 0..30 and a circle
    sketched at z = 10 (translate) cutting along +z."""
    m = DocumentModel()
    d = m.add_node("difference", {})
    body = m.add_node("union", {}, parent=d)
    m.add_node("cube", dict(width=40, depth=40, height=30), parent=body)
    t = m.add_node("translate", dict(x=20, y=20, z=10), parent=d)
    ex = m.add_node("linear_extrude", dict(height=7), parent=t)
    m.add_node("circle", dict(radius=4), parent=ex)
    return m, ex


def test_through_all_one_way(app):
    m, ex = _plate_with_cutter(app)
    assert extent.set_extent(m, ex, "through_all_one") == pytest.approx(21)
    assert ex.params["center"] is False


def test_up_to_next_stops_at_the_first_surface(app):
    m, ex = _plate_with_cutter(app)
    # from z 10 inside the plate the first surface along +z is its top
    assert extent.set_extent(m, ex, "up_to_next") == pytest.approx(20)


def test_up_to_vertex(app):
    m, ex = _plate_with_cutter(app)
    assert extent.set_extent(m, ex, "up_to_vertex",
                             point=[40, 40, 25]) == pytest.approx(15)
    with pytest.raises(ValueError):
        extent.set_extent(m, ex, "up_to_vertex", point=[0, 0, 0])


def test_up_to_surface_and_offset_from_it(app):
    m, ex = _plate_with_cutter(app)
    top = [5, 5, 30, 0, 0, 1]
    assert extent.set_extent(m, ex, "up_to_face", face=top) == \
        pytest.approx(20)
    assert extent.set_extent(m, ex, "offset_face", face=top,
                             offset=-5) == pytest.approx(15)


def test_mid_plane_keeps_the_distance_centred(app):
    m, ex = _plate_with_cutter(app)
    assert extent.set_extent(m, ex, "mid_plane") == pytest.approx(7)
    assert ex.params["center"] is True
    m.set_param(ex, "height", 12)            # a typed distance stays
    assert ex.params["extent"] == "mid_plane"
    extent.refresh(m)
    assert ex.params["height"] == 12 and ex.params["center"] is True


def test_every_label_is_solidworks(app):
    assert [extent.LABELS[k] for k in extent.EXTENTS] == [
        "Blind", "Through All", "Through All - Both", "Up To Next",
        "Up To Vertex", "Up To Surface", "Offset From Surface",
        "Up To Body", "Mid Plane"]


def test_the_extrude_window_asks_for_the_surface_then_goes_to_it(win):
    from khervecad import extrude_panel as ep
    m = win.model
    d = m.add_node("difference", {})
    m.add_node("cube", dict(width=40, depth=40, height=30), parent=d)
    t = m.add_node("translate", dict(x=20, y=20, z=10), parent=d)
    ex = m.add_node("linear_extrude", dict(height=7), parent=t)
    m.add_node("circle", dict(radius=4), parent=ex)
    ep.choose_extent(win, ex, "up_to_face")
    cb = win.view3d._pick_cb
    assert cb is not None                     # waiting for the click
    cube = d.children[0]
    cb(dict(kind="face", pos=(5, 5, 30), dir=(0, 0, 1)), cube)
    assert ex.params["extent"] == "up_to_face"
    assert ex.params["height"] == pytest.approx(20)
