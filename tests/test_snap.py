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


def test_secondary_anchors_snap_groups_inside_an_object(window):
    """In the Object tab, the Snap tool mates the *groups* that build
    the Object (secondary anchors), not whole Objects: the mate lands
    on the group and solves within the Object's frame."""
    model = window.model
    comp = model.new_component("Bracket", visible=False)
    base = model.add_node("union", parent=comp, name="Base")
    model.add_node("cube", dict(width=20.0, depth=20.0, height=6.0),
                   parent=base)
    post = model.add_node("union", parent=comp, name="Post")
    model.add_node("cube", dict(width=8.0, depth=8.0, height=20.0),
                   parent=post)
    post.params["x"] = 60.0
    window.builder.open_component(comp)          # Object tab active

    assert window._snap_scope() is comp
    assert {p.name for p, _ in window._snap_groups(comp)} == \
        {"Base", "Post"}

    window._start_snap()
    window.view3d._pick_cb(dict(kind="face", name="Face",
                                pos=[60.0, 0.0, 0.0],
                                dir=[0.0, 0.0, -1.0]), post)   # Post base
    window.view3d._pick_cb(dict(kind="face", name="Face",
                                pos=[0.0, 0.0, 6.0],
                                dir=[0.0, 0.0, 1.0]), base)    # Base top
    mate = post.params.get("mate")
    assert mate is not None and mate["parent"] == "Base"
    # Post now sits on Base's top face, back at the Object's axis
    assert post.params["z"] == 6.0
    assert post.params["x"] == 0.0
    # the whole-object assembly anchors are untouched
    assert not comp.params.get("mate")


def test_group_mate_survives_kcad_roundtrip(window, tmp_path):
    """A secondary (group) mate persists and re-solves on load."""
    from khervecad import document
    from khervecad.model import DocumentModel
    model = window.model
    comp = model.new_component("Bracket", visible=False)
    base = model.add_node("union", parent=comp, name="Base")
    model.add_node("cube", dict(width=20.0, depth=20.0, height=6.0),
                   parent=base)
    post = model.add_node("union", parent=comp, name="Post")
    model.add_node("cube", dict(width=8.0, depth=8.0, height=20.0),
                   parent=post)
    from khervecad import mates
    mates.attach(model, post, "Base", "Top", "Bottom")
    path = tmp_path / "bracket.kcad"
    document.save_kcad(model, str(path))

    other = DocumentModel()
    document.load_kcad(other, str(path))
    loaded = next(n for n in other.root.walk()
                  if n.type == "union" and n.name == "Post")
    assert loaded.params["mate"]["parent"] == "Base"


def test_snap_completion_offers_the_tweak_popup(window):
    """After the second click the offset/spin popup opens on the
    mated part, and its flip button spins the mate half a turn."""
    parent, child = _two_cubes(window.model)
    window._start_snap()
    window.view3d._pick_cb(dict(kind="face", name="Face",
                                pos=[55.0, 5.0, 0.0],
                                dir=[0.0, 0.0, -1.0]), child)
    window.view3d._pick_cb(dict(kind="face", name="Face",
                                pos=[10.0, 10.0, 20.0],
                                dir=[0.0, 0.0, 1.0]), parent)
    popup = window._snap_tweak
    assert popup is not None and popup.comp is child
    popup.spin.setValue(180.0)
    assert child.params["mate"]["spin"] == 180.0
    popup.close()
    assert window._snap_tweak is None


def test_snap_hover_labels_name_the_anchor(window):
    """Hovering a face that matches a bbox anchor reads as the anchor
    ("Base · Top"), not the generic Face."""
    parent, child = _two_cubes(window.model)
    label = window._snap_labeler()
    top = dict(kind="face", name="Face", pos=[10.0, 10.0, 20.0],
               dir=[0.0, 0.0, 1.0])
    assert label(top, parent) == "Base · Top"
    odd = dict(kind="face", name="Face", pos=[3.0, 4.0, 20.0],
               dir=[0.0, 0.0, 1.0])
    assert label(odd, parent) == "Base · Face"
    assert not parent.params.get("anchors")   # labelling never persists
