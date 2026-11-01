"""Extruded Cut drawn on the face in the 3D view (2026-11-01, the user).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import analysis, cut_feature, mesh, sketch3d
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


def test_straighten_snaps_level_and_upright():
    assert sketch3d.straighten((0, 0), (10, 0.5)) == (10, 0)
    assert sketch3d.straighten((0, 0), (0.5, 10)) == (0, 10)
    assert sketch3d.straighten((0, 0), (10, 10)) == (10, 10)


def test_a_slot_drawn_in_3d_is_cut_on_done(win, monkeypatch):
    monkeypatch.setattr(cut_feature, "IN_3D", True)
    McpToolExecutor(win).execute("apply_code",
                                 {"code": "cube([40, 30, 20]); // Block\n"})
    QApplication.processEvents()
    m = win.model
    part = next(c for c in m.root.children if c.visible and c.type != "assign")
    full = analysis.mass_properties(mesh.tessellate(m.root))["volume"]
    cut_feature.start(win, "extruded_cut")
    win.view3d._pick_cb(dict(kind="face", pos=(20, 15, 20),
                             dir=(0, 0, 1)), part)
    tool = win.view3d.edit_tool
    assert isinstance(tool, sketch3d.Sketch3DTool)
    assert not getattr(win, "_face_sketch", None)     # no 2D view
    tool.set_mode("slot")
    tool.place((10, 10))
    tool.place((30, 10.5))                            # snaps level
    slot = tool.place((20, 13))
    assert slot.params["slot"] and slot.params["y2"] == slot.params["y1"]
    tool.finish()
    assert win.view3d.edit_tool is None
    assert any(n.type == "difference" for n in m.root.walk())
    QApplication.processEvents()
    left = analysis.mass_properties(mesh.tessellate(m.root))["volume"]
    assert left < full - 100


def _on_face(win, monkeypatch):
    monkeypatch.setattr(cut_feature, "IN_3D", True)
    McpToolExecutor(win).execute("apply_code",
                                 {"code": "cube([40, 30, 20]); // Block\n"})
    QApplication.processEvents()
    part = next(c for c in win.model.root.children
                if c.visible and c.type != "assign")
    cut_feature.start(win, "extruded_cut")
    win.view3d._pick_cb(dict(kind="face", pos=(20, 15, 20),
                             dir=(0, 0, 1)), part)
    return win.view3d.edit_tool


def test_the_sketch_icons_drive_it_and_no_bar_shows(win, monkeypatch):
    from PyQt5.QtWidgets import QPushButton
    from khervecad import sketch_tools
    tool = _on_face(win, monkeypatch)
    assert not win.view3d.findChildren(QPushButton, "sketch3d_bar")
    win._set_tool(sketch_tools.SLOT)
    assert tool.mode == "slot" and win.view3d.edit_tool is tool
    win._set_tool("circle")
    assert tool.mode == "circle"
    tool.finish()


def test_snaps_to_a_middle_and_lights_the_edge(win, monkeypatch):
    tool = _on_face(win, monkeypatch)
    win.view3d.resize(800, 600)
    win.view3d.fit()
    mids = [p for p in tool.info["points"] if p[2] == "middle"]
    assert mids
    x, y, _k = mids[0]
    got = tool.snap_local(x + 0.05, y + 0.05)
    assert got == (x, y) and tool.snapped[2] == "middle" and tool.lit
    tool.finish()


def test_what_was_drawn_can_be_seen(win, monkeypatch):
    tool = _on_face(win, monkeypatch)
    tool.place((5, 5))
    tool.place((15, 12))
    assert len(tool._own()[0]) >= 4          # the rectangle's sides
    tool.finish()
