"""Bugs found while filming Exercise 7 (2026-11-15).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtWidgets import QApplication

from test_feature_pick import app, win, _block, _click_face  # noqa
from khervecad import cut_feature, feature_pick, normal_to


def _top(win):
    return next(f for f in win._choice_preview["faces"]
                if f["dir"][2] > 0.99)


def test_pick_toggles_start_on_each_time(win):
    """Faces switched off for one Sketch Mode must not stay off."""
    win.builder.active_tree().clearSelection()
    normal_to.create(win)
    feature_pick.toggled(win, "faces", False)
    win.view3d.cancel_pick()
    win.builder.active_tree().clearSelection()
    normal_to.create(win)
    st = feature_pick.state(win)
    assert st["faces"] and st["regions"]
    assert any(k[0] == "part" for k, _t in win.view3d._pick_groups)
    win.view3d.cancel_pick()
    feature_pick.toggled(win, "planes", False)


def test_a_face_click_with_a_stale_selection_starts_a_new_sketch(win):
    """A node still selected (a fillet round the part and its old sketch)
    must not make Sketch Mode reopen that sketch."""
    from khervecad import face_sketch
    win.builder.active_tree().clearSelection()
    normal_to.create(win)
    _click_face(win, _top(win))
    first = feature_pick.sketch_group(win)
    win.model.add_node("rect", {"width": 5, "height": 5}, parent=first)
    from khervecad import sketch_mode
    sketch_mode.finish(win)
    for _ in range(3):
        QApplication.processEvents()
    wrapped = win.model.wrap_nodes([_block(win), first], "union")
    win.builder.active_tree().select_nodes([wrapped])
    normal_to.create(win)
    view = win.view3d
    assert view._pick_cb is not None, "reopened the old sketch"
    node = view._pick_groups[0][0]
    cb = view._pick_cb
    view._end_pick_mode()
    view._pick_cb = None
    cb(dict(kind="face", pos=[40.0, 15.0, 10.0], dir=[1.0, 0.0, 0.0],
            tris=[]), node)
    second = win._face_sketch
    assert second is not None and second is not first
    assert abs(float(second.params.get("x", 40)) - 40) < 1e-6 or \
        second.params.get("rz") is not None


def _all_in_view(view):
    eye, r, u, f = view._camera()
    pts = [v for tri in view.mesh for v in tri]
    assert pts
    for v in pts:
        x, y, _z = view._project(eye, r, u, f, v)
        if not (0 <= x <= view.width() and 0 <= y <= view.height()):
            return False
    return True


def test_leaving_a_sketch_frames_the_whole_model(win):
    """The 3D view came back at the sketch's px/mm, cropping the part."""
    from khervecad import sketch_mode, toolbar_style
    toolbar_style.apply(win, "SolidWorks", remember=False)
    for _ in range(5):
        QApplication.processEvents()
    view = win.view3d
    view.fit()
    saved = (list(view.target), view.distance)
    win.builder.active_tree().clearSelection()
    normal_to.create(win)
    _click_face(win, _top(win))
    win.view2d.zoom(10)             # zoom the sketch right in
    for _ in range(3):
        QApplication.processEvents()
    sketch_mode.finish(win)
    for _ in range(5):
        QApplication.processEvents()
    assert _all_in_view(view), "the part is cropped after the sketch"
    # and Fit frames everything whatever the camera was doing
    view.target = [500.0, 500.0, 500.0]
    view.distance = 3.0
    view.fit()
    assert _all_in_view(view)


def test_a_region_under_the_cursor_beats_the_face_it_lies_on(win):
    """A region slab flush with a part face (a tie in depth, whatever
    the group order) must be the pick, not the face."""
    view = win.view3d
    view.projection = "Orthographic"
    view.fit()
    top = [((0, 0, 20.0), (40, 0, 20.0), (40, 30, 20.0)),
           ((0, 0, 20.0), (40, 30, 20.0), (0, 30, 20.0))]
    region = [((10, 10, 20.0), (30, 10, 20.0), (30, 20, 20.0)),
              ((10, 10, 20.0), (30, 20, 20.0), (10, 20, 20.0))]
    eye, r, u, f = view._camera()
    x, y, _d = view._project(eye, r, u, f, (22.0, 14.0, 20.0))
    for groups in ([(("part", "block"), top), (("region", 0, 0), region)],
                   [(("region", 0, 0), region), (("part", "block"), top)]):
        view._pick_groups = groups
        desc, key = view._pick_at(x, y)
        assert key and key[0] == "region", key
    # off the region the face is still the face
    x, y, _d = view._project(eye, r, u, f, (3.0, 3.0, 20.0))
    desc, key = view._pick_at(x, y)
    assert key and key[0] == "part"


def test_offscreen_runs_never_write_the_real_library(monkeypatch):
    from pathlib import Path
    from khervecad import user_library
    monkeypatch.delenv("KHERVECAD_USER_LIBRARY", raising=False)
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    real = Path.home() / "Documents" / "KherveCAD Library"
    assert user_library.folder() != real
    assert real not in user_library.folder().parents
    monkeypatch.setenv("QT_QPA_PLATFORM", "cocoa")
    assert user_library.folder() == real


def test_properties_edit_after_the_model_is_gone_is_harmless(win):
    """An editor finishing as the window closes (focus out) must not
    raise "DocumentModel has been deleted"."""
    from PyQt5 import sip
    from khervecad.properties import PropertiesPanel
    model = win.model
    node = _block(win)
    panel = PropertiesPanel(model)
    panel.set_node(node)
    sip.delete(model)
    panel._set_param("size", [1, 2, 3])
    panel._rename("Other")
    panel._set_construction(True)
    panel._set_slot("width", 3)
    win._dirty = False
    win.model = None
