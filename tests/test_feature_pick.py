"""Extruded Boss / Cut start with toggles on top of the 3D view — Faces,
Sketch regions, Planes, 2D | 3D — and one click, not a window
(2026-11-13, the user).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication

from khervecad import (cut_feature, feature_pick, plane_pick,
                       sketch_choice)
from khervecad.mainwindow import MainWindow
from khervecad.mcp_tools import McpToolExecutor


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app, monkeypatch):
    monkeypatch.setattr(sketch_choice, "ask_hook", None)
    QSettings("Kherve", "KherveCAD").remove(feature_pick.KEY_WHERE)
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    McpToolExecutor(w).execute(
        "apply_code", {"code": "cube([40, 30, 20]); // Block\n"})
    for _ in range(5):
        QApplication.processEvents()
    yield w
    w._dirty = False
    w.close()


def _block(win):
    return next(c for c in win.model.root.children
                if c.visible and c.type not in ("assign", "variables"))


def _click_face(win, face):
    view = win.view3d
    eye, r, u, f = view._camera()
    x, y, _z = view._project(eye, r, u, f, face["pos"])
    win._feature_pick["pos"] = None
    view._run_pick(x, y)


def test_cut_shows_the_toggles_not_a_window(win):
    cut_feature.start(win, "extruded_cut")
    bar = feature_pick.bars(win)["view3d"]
    assert bar.isVisible()
    for key in ("faces", "regions", "planes", "2d", "3d"):
        assert bar.buttons[key].isVisible()
    assert bar.buttons["faces"].isChecked()
    assert not bar.buttons["planes"].isChecked()
    assert bar.buttons["2d"].isChecked()                 # 2D by default
    assert win.view3d._pick_cb is not None
    assert len(win._choice_preview["faces"]) == 6
    # Planes on: drawn; Faces off: a part is no longer clickable
    bar.buttons["planes"].click()
    assert win._plane_pick and win._plane_pick.get("feature")
    bar.buttons["faces"].click()
    assert not any(k[0] == "part" for k, _t in win.view3d._pick_groups)
    assert not win._choice_preview["show_faces"]
    # Esc: nothing made, the bar goes
    win.view3d.cancel_pick()
    assert win._feature_pick is None and not bar.isVisible()
    assert not win._plane_pick
    feature_pick.toggled(win, "faces", True)
    feature_pick.toggled(win, "planes", False)


def test_a_face_click_opens_the_sketch_and_2d_3d_switch_it(win):
    cut_feature.start(win, "extruded_cut")
    top = next(f for f in win._choice_preview["faces"]
               if f["dir"][2] > 0.99)
    _click_face(win, top)
    group = feature_pick.sketch_group(win)
    assert group is not None and abs(float(group.params["z"]) - 20) < 1e-6
    assert win._face_sketch is group                     # in 2D
    assert win._feature_pick is None
    # 3D: the same sketch, drawn on the model; nothing cut meanwhile
    feature_pick.toggled(win, "3d", True)
    assert win._face_sketch is None
    assert win._sketch3d_tool is not None and \
        win._sketch3d_tool.group is group
    assert group.parent is not None
    assert not any(n.type == "difference" for n in win.model.root.walk())
    assert feature_pick.bars(win)["view3d"].isVisible()
    # and back
    feature_pick.toggled(win, "2d", True)
    assert win._sketch3d_tool is None and win._face_sketch is group
    assert QSettings("Kherve", "KherveCAD").value(
        feature_pick.KEY_WHERE) == "2d"


def test_a_plane_click_sketches_on_it(win, monkeypatch):
    cut_feature.start(win, "extruded_boss")
    feature_pick.toggled(win, "planes", True)
    monkeypatch.setattr(plane_pick, "hit", lambda w, pos: "Front (XZ)")
    from PyQt5.QtCore import QPoint
    win._feature_pick["pos"] = QPoint(5, 5)
    cb = win.view3d._pick_cb
    win.view3d._pick_cb = None
    cb(None, None)
    group = feature_pick.sketch_group(win)
    assert group is not None and group.name == "Sketch on Front Plane"
    feature_pick.toggled(win, "planes", False)


def test_a_region_click_uses_that_sketch(win, monkeypatch):
    calls = []
    from khervecad import sketch_regions
    monkeypatch.setattr(sketch_regions, "start_3d",
                        lambda w, s, cut=False, preselect=None:
                        calls.append((s, cut, preselect)))
    win._feature_pick = None
    feature_pick.start(win, "extruded_boss")
    pick = win._feature_pick
    pick["sketches"] = ["S0", "S1"]
    feature_pick.picked(win, {"kind": "face"}, ("region", 1, 2))
    for _ in range(3):
        QApplication.processEvents()
    assert calls == [("S1", False, 2)]


# ------------------------------------- every Boss, as every Cut (same day)
@pytest.mark.parametrize("op, kind", [
    ("linear_extrude", "extruded_boss"), ("rotate_extrude", "revolved_boss"),
    ("sweep", "swept_boss"), ("section_loft", "lofted_boss")])
def test_every_boss_button_shows_the_toggles(win, op, kind):
    win.builder.active_tree().clearSelection()
    win._apply_operation(op)
    assert win._feature_pick is not None
    assert win._feature_pick["kind"] == kind
    assert feature_pick.bars(win)["view3d"].isVisible()
    win.view3d.cancel_pick()
    assert win._feature_pick is None


def test_extruded_boss_shows_the_toggles_with_an_old_sketch_there(win):
    McpToolExecutor(win).execute(
        "apply_code", {"code": "cube([40, 30, 20]); // Block\n"
                       "translate([60, 0, 0]) square(5); // Loose\n"})
    win.builder.active_tree().clearSelection()
    win._apply_operation("linear_extrude")
    assert win._feature_pick and \
        win._feature_pick["kind"] == "extruded_boss"
    win.view3d.cancel_pick()


@pytest.mark.parametrize("kind, made", [
    ("revolved_boss", "rotate_extrude"), ("swept_boss", "sweep"),
    ("lofted_boss", "section_loft")])
def test_a_boss_sketched_on_a_face_is_made_on_leaving(win, kind, made):
    cut_feature.start(win, kind)
    top = next(f for f in win._choice_preview["faces"]
               if f["dir"][2] > 0.99)
    _click_face(win, top)
    group = feature_pick.sketch_group(win)
    assert group.params[cut_feature.KEY] == kind
    win.model.add_node("rect", {"x": 4.0, "y": 0.0, "width": 6.0,
                                "height": 5.0}, parent=group)
    tool = cut_feature.finish(win, group)
    assert tool is not None and tool.type == made
    assert not any(n.type == "difference" for n in win.model.root.walk())
    if kind == "revolved_boss":       # about the sketch's own Y axis
        assert tool.parent.type == "rotate"
        assert float(tool.parent.params["x"]) == -90.0
    if kind == "lofted_boss":         # a second section to loft to
        assert len(tool.params["heights"]) == 2


def test_a_sketch_clicked_for_a_swept_boss_is_used_whole(win):
    group = win.model.add_node("union", {}, parent=win.model.root)
    win.model.add_node("circle", {"radius": 3.0}, parent=group)
    made = feature_pick._use_sketch(
        win, {"kind": "swept_boss", "label": "Swept Boss/Base"}, group)
    assert made is not None and made.type == "sweep"
    assert made.parent is group


def test_a_revolved_cut_refuses_a_sketch_on_no_part(win):
    group = win.model.add_node("union", {}, parent=win.model.root)
    win.model.add_node("circle", {"radius": 3.0}, parent=group)
    made = feature_pick._use_sketch(
        win, {"kind": "revolved_cut", "label": "Revolved Cut"}, group)
    assert made is None
    assert win._feature_pick is not None          # the bar again
    win.view3d.cancel_pick()


# ----------------------- the bottom bar stays; Sketch Mode too (same day)
def test_the_bottom_bar_stays_while_the_toggles_show(win):
    cut_feature.start(win, "extruded_boss")
    nav = win.view3d.nav_bar
    assert win.view3d._pick_cb is not None and nav.isVisible()
    win.view3d.cancel_pick()
    assert nav.isVisible() and not win.view3d.keep_nav_in_pick
    # an ordinary pick still clears the view
    win.view3d.start_pick(lambda *a: None, banner="pick")
    assert nav.isHidden()
    win.view3d.cancel_pick()


def test_sketch_mode_shows_the_toggles_with_planes_on(win):
    from khervecad import normal_to
    win.builder.active_tree().clearSelection()
    normal_to.create(win)
    pick = win._feature_pick
    assert pick and pick["kind"] == feature_pick.SKETCH
    assert pick["label"] == "Sketch Mode"
    bar = feature_pick.bars(win)["view3d"]
    assert bar.isVisible() and bar.buttons["planes"].isChecked()
    assert bar.buttons["2d"].isChecked()
    win.view3d.cancel_pick()
    feature_pick.toggled(win, "planes", False)


def test_sketch_mode_on_a_face_opens_a_plain_sketch_2d_and_3d(win):
    from khervecad import normal_to
    win.builder.active_tree().clearSelection()
    normal_to.create(win)
    top = next(f for f in win._choice_preview["faces"]
               if f["dir"][2] > 0.99)
    _click_face(win, top)
    group = feature_pick.sketch_group(win)
    assert group is not None and win._face_sketch is group
    assert not group.params.get(cut_feature.KEY)        # just a sketch
    assert feature_pick.bars(win)["view2d"].isVisible()
    feature_pick.toggled(win, "3d", True)
    assert win._sketch3d_tool is not None and \
        win._sketch3d_tool.group is group
    feature_pick.toggled(win, "2d", True)
    assert win._face_sketch is group


def test_sketch_mode_on_a_plane_turns_to_it(win, monkeypatch):
    from khervecad import normal_to
    turned = []
    monkeypatch.setattr(normal_to, "turn_to",
                        lambda w, plane, *a, **k: turned.append(plane))
    feature_pick.start(win, feature_pick.SKETCH)
    monkeypatch.setattr(plane_pick, "hit", lambda w, pos: "Top (XY)")
    from PyQt5.QtCore import QPoint
    win._feature_pick["pos"] = QPoint(5, 5)
    cb = win.view3d._pick_cb
    win.view3d._pick_cb = None
    cb(None, None)
    assert turned == ["Top (XY)"]
    feature_pick.toggled(win, "planes", False)
