"""Tests for the two-click Snap tool (pick a face on each of two
Objects and mate them) and its anchor resolution.

Run with: python -m pytest tests/  (offscreen Qt).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad.mainwindow import MainWindow


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    return MainWindow()


def _two_cubes(model):
    """A 20 mm parent cube at the origin and a 10 mm child at x=50."""
    parent = model.new_component("Base")
    model.add_node("cube", dict(width=20.0, depth=20.0, height=20.0),
                   parent=parent)
    child = model.new_component("Lid")
    model.add_node("cube", dict(width=10.0, depth=10.0, height=10.0),
                   parent=child)
    child.params["x"] = 50.0
    return parent, child


def test_anchor_for_pick_matches_auto_anchor(window):
    parent, _child = _two_cubes(window.model)
    desc = dict(kind="face", name="Face", pos=[10.0, 10.0, 20.0],
                dir=[0.0, 0.0, 1.0])
    anchor = window._anchor_for_pick(parent, desc)
    assert anchor["name"] == "Top"
    assert not parent.params.get("anchors")      # nothing new persisted


def test_anchor_for_pick_creates_custom_for_new_spot(window):
    parent, _child = _two_cubes(window.model)
    desc = dict(kind="face", name="Face", pos=[3.0, 4.0, 20.0],
                dir=[0.0, 0.0, 1.0])
    anchor = window._anchor_for_pick(parent, desc)
    assert anchor["kind"] == "custom"
    assert parent.params["anchors"][0]["name"] == anchor["name"]


def test_two_click_snap_mates_child_onto_parent(window):
    model = window.model
    parent, child = _two_cubes(model)
    window._start_snap()
    first = window.view3d._pick_cb
    assert first is not None                     # tool armed
    groups = window.view3d._pick_groups
    assert [g[0] for g in groups] == [parent, child]
    # click 1: the child's bottom face (world coords: child at x=50)
    first(dict(kind="face", name="Face", pos=[55.0, 5.0, 0.0],
               dir=[0.0, 0.0, -1.0]), child)
    second = window.view3d._pick_cb
    assert second is not None
    # click 2: the parent's top face
    second(dict(kind="face", name="Face", pos=[10.0, 10.0, 20.0],
                dir=[0.0, 0.0, 1.0]), parent)
    mate = child.params.get("mate")
    assert mate == dict(parent="Base", parent_anchor="Top",
                        anchor="Bottom", offset=0.0, spin=0.0)
    # solved: the child's bottom centre sits on the parent's top centre
    assert (child.params["x"], child.params["y"],
            child.params["z"]) == (5.0, 5.0, 20.0)


def test_snap_second_click_rejects_same_object(window):
    model = window.model
    parent, child = _two_cubes(model)
    window._start_snap()
    window.view3d._pick_cb(dict(kind="face", name="Face",
                                pos=[55.0, 5.0, 0.0],
                                dir=[0.0, 0.0, -1.0]), child)
    # clicking the same object re-arms the second pick
    window.view3d._pick_cb(dict(kind="face", name="Face",
                                pos=[55.0, 5.0, 10.0],
                                dir=[0.0, 0.0, 1.0]), child)
    assert window.view3d._pick_cb is not None    # still waiting
    assert child.params.get("mate") is None


def test_snap_needs_two_visible_objects(window):
    model = window.model
    solo = model.new_component("Only")
    model.add_node("cube", parent=solo)
    hidden = model.new_component("Ghost", visible=False)
    model.add_node("cube", parent=hidden)
    window._start_snap()
    assert window.view3d._pick_cb is None        # tool refused to arm
