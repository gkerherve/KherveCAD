"""Extruded Boss / Cut ask what to use and where to sketch (2026-11-11,
the user: "a pop-up … select this model or create a new sketch … the
option between doing a sketch in 3D or 2D so that I make a final
decision").

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import analysis, cut_feature, mesh, sketch3d, sketch_choice
from khervecad.mainwindow import MainWindow
from khervecad.mcp_tools import McpToolExecutor


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    w = MainWindow()
    yield w
    w._dirty = False
    w.close()


def _block(win, code="cube([40, 30, 20]); // Block\n"):
    McpToolExecutor(win).execute("apply_code", {"code": code})
    QApplication.processEvents()
    return next(c for c in win.model.root.children
                if c.visible and c.type not in ("assign", "variables"))


def _answer(monkeypatch, answer):
    asked = []

    def hook(label, selection):
        asked.append((label, selection))
        return answer
    monkeypatch.setattr(sketch_choice, "ask_hook", hook)
    return asked


def test_the_window_offers_the_selection_first(app):
    dlg = sketch_choice.ChoiceDialog(None, "Extruded Cut", "Block")
    assert dlg.source() == "selection"
    assert not dlg.where_box.isEnabled()      # nothing new to sketch
    dlg.set_source("face")
    assert dlg.where_box.isEnabled()
    dlg.in2d.setChecked(True)
    assert dlg.choice() == {"source": "face", "where": "2d"}
    part = sketch_choice.ChoiceDialog(None, "Extruded Cut",
                                      "a face of Block")
    assert part.source() == "selection" and part.where_box.isEnabled()
    plain = sketch_choice.ChoiceDialog(None, "Extruded Cut", None)
    assert "selection" not in plain._source_buttons
    assert plain.source() == "face"


def test_dont_ask_again_keeps_the_answer(monkeypatch):
    monkeypatch.setattr(sketch_choice, "ask_hook", None)
    sketch_choice.set_asks(False)
    try:
        from PyQt5.QtCore import QSettings
        QSettings("Kherve", "KherveCAD").setValue("sketch/feature_where",
                                                  "2d")
        assert sketch_choice.ask(None, "Extruded Cut", None) == \
            {"source": "face", "where": "2d"}
        assert sketch_choice.ask(None, "Extruded Cut", "Block")["source"] \
            == "selection"
    finally:
        sketch_choice.set_asks(True)


def test_cancel_makes_nothing(win, monkeypatch):
    _block(win)
    _answer(monkeypatch, False)
    before = len(list(win.model.root.walk()))
    cut_feature.start(win, "extruded_cut")
    assert win.view3d._pick_cb is None
    assert len(list(win.model.root.walk())) == before


def test_a_cut_on_a_face_sketched_in_2d(win, monkeypatch):
    part = _block(win)
    asked = _answer(monkeypatch, {"source": "face", "where": "2d"})
    cut_feature.start(win, "extruded_cut")
    assert asked == [("Extruded Cut", None)]
    win.view3d._pick_cb(dict(kind="face", pos=(20, 15, 20),
                             dir=(0, 0, 1)), part)
    assert getattr(win, "_face_sketch", None) is not None   # the 2D sketch
    assert not isinstance(win.view3d.edit_tool, sketch3d.Sketch3DTool)


def test_a_cut_on_a_face_sketched_in_3d(win, monkeypatch):
    part = _block(win)
    _answer(monkeypatch, {"source": "face", "where": "3d"})
    cut_feature.start(win, "extruded_cut")
    win.view3d._pick_cb(dict(kind="face", pos=(20, 15, 20),
                             dir=(0, 0, 1)), part)
    assert isinstance(win.view3d.edit_tool, sketch3d.Sketch3DTool)
    assert not getattr(win, "_face_sketch", None)
    win.view3d.edit_tool.finish()


def test_a_selected_part_is_offered_and_only_it_is_picked(win,
                                                          monkeypatch):
    _block(win, "cube([40, 30, 20]); // Block\n"
                "translate([60, 0, 0]) cube([10, 10, 10]); // Other\n")
    block = next(c for c in win.model.root.walk() if "Block" in c.name
                 and c.parent is win.model.root)
    win.builder.active_tree().select_nodes([block])
    asked = _answer(monkeypatch, {"source": "selection", "where": "3d"})
    groups = []
    real = win.view3d.start_pick
    monkeypatch.setattr(win.view3d, "start_pick",
                        lambda cb, groups=None, **k: (
                            groups and globals().setdefault("_g", groups),
                            real(cb, groups=groups, **k)))
    cut_feature.start(win, "extruded_cut")
    assert asked[0][1] == "a face of " + block.name
    assert [p for p, _t in globals().pop("_g")] == [block]


def test_extruded_boss_asks_too_and_a_plane_sketch_cuts(win, monkeypatch):
    """The Boss button with a part selected asks; a cut on the Top plane
    through the middle of a centred block takes material away."""
    part = _block(win, "translate([-20, -15, -10]) cube([40, 30, 20]);"
                       " // Block\n")
    win.builder.active_tree().select_nodes([part])
    asked = _answer(monkeypatch, {"source": "face", "where": "3d"})
    win._apply_operation("linear_extrude")
    assert asked and asked[0][0] == "Extruded Boss/Base" and asked[0][1]
    assert win.view3d._pick_cb is not None    # a face to click
    win.view3d.cancel_pick()

    full = analysis.mass_properties(mesh.tessellate(win.model.root))["volume"]
    _answer(monkeypatch, {"source": "plane", "where": "3d"})
    cut_feature.start(win, "extruded_cut")
    state = getattr(win, "_plane_pick", None)
    assert state and state.get("on_plane")
    from khervecad import plane_pick
    cb = state["on_plane"]
    plane_pick.stop(win)
    cb("Top (XY)")
    tool = win.view3d.edit_tool
    assert isinstance(tool, sketch3d.Sketch3DTool)
    assert tool.group.name == "Sketch on Top Plane"
    tool.set_mode("rect")
    tool.place((-5, -5))
    tool.place((5, 5))
    if win.view3d.edit_tool is tool:
        tool.finish()
    QApplication.processEvents()
    left = analysis.mass_properties(mesh.tessellate(win.model.root))["volume"]
    assert left < full - 100


def test_options_turn_the_question_back_on(win):
    from khervecad import options_dialog
    sketch_choice.set_asks(False)
    try:
        dlg = options_dialog.OptionsDialog(win)
        assert not dlg.ask_where.isChecked()
        dlg.ask_where.setChecked(True)
        dlg.apply()
        assert sketch_choice.asks()
    finally:
        sketch_choice.set_asks(True)
