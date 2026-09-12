"""Tests for the attach/mate system: frame alignment, offsets, spin,
chained refresh, detach, rename tracking and persistence.

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
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import anchors, document, mates
from khervecad.model import DocumentModel


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model(app):
    return DocumentModel()


def _cube(model, name, size=20.0, **placement):
    comp = model.new_component(name)
    comp.params.update(placement)
    model.add_node("cube", dict(width=size, depth=size, height=size),
                   parent=comp)
    return comp


def _anchor_world(comp, name):
    anchor = mates.find_anchor(comp, name)
    return anchors.anchor_world(comp, anchor)


def test_attach_bottom_to_top_stacks(model):
    base = _cube(model, "Base")
    lid = _cube(model, "Lid", size=10.0)
    mates.attach(model, lid, "Base", "Bottom", "Top")
    # the lid's bottom-centre sits exactly on the base's top-centre
    pos, direction = _anchor_world(lid, "Bottom")
    assert pos == pytest.approx([10.0, 10.0, 20.0])
    assert direction == pytest.approx([0.0, 0.0, -1.0])
    assert lid.params["z"] == pytest.approx(20.0)


def test_attach_to_side_rotates(model):
    base = _cube(model, "Base")
    arm = _cube(model, "Arm", size=10.0)
    mates.attach(model, arm, "Base", "Bottom", "Right")
    # the arm's bottom now faces -X, flush on the base's +X face
    pos, direction = _anchor_world(arm, "Bottom")
    assert pos == pytest.approx([20.0, 10.0, 10.0])
    assert direction == pytest.approx([-1.0, 0.0, 0.0], abs=1e-6)


def test_offset_moves_along_axis(model):
    base = _cube(model, "Base")
    lid = _cube(model, "Lid", size=10.0)
    mates.attach(model, lid, "Base", "Bottom", "Top", offset=5.0)
    pos, _d = _anchor_world(lid, "Bottom")
    assert pos == pytest.approx([10.0, 10.0, 25.0])


def test_spin_rotates_about_axis(model):
    base = _cube(model, "Base")
    lid = _cube(model, "Lid", size=10.0)
    mates.attach(model, lid, "Base", "Bottom", "Top", spin=90.0)
    # still stacked, still anti-aligned
    pos, direction = _anchor_world(lid, "Bottom")
    assert pos == pytest.approx([10.0, 10.0, 20.0])
    assert direction == pytest.approx([0.0, 0.0, -1.0], abs=1e-6)
    assert abs(lid.params["rz"] - 90.0) < 1e-3 \
        or abs(lid.params["rz"] + 270.0) < 1e-3


def test_moving_parent_carries_children(model):
    base = _cube(model, "Base")
    lid = _cube(model, "Lid", size=10.0)
    mates.attach(model, lid, "Base", "Bottom", "Top")
    base.params["x"] = 100.0
    assert mates.refresh(model) is True
    pos, _d = _anchor_world(lid, "Bottom")
    assert pos == pytest.approx([110.0, 10.0, 20.0])
    # settled: a second refresh changes nothing
    assert mates.refresh(model) is False


def test_chained_mates_follow(model):
    a = _cube(model, "A")
    b = _cube(model, "B")
    c = _cube(model, "C")
    mates.attach(model, b, "A", "Bottom", "Top")
    mates.attach(model, c, "B", "Bottom", "Top")
    a.params["z"] = 50.0
    mates.refresh(model)
    pos, _d = _anchor_world(c, "Bottom")
    assert pos == pytest.approx([10.0, 10.0, 90.0])   # 50 + 20 + 20


def test_mate_cycle_does_not_hang(model):
    a = _cube(model, "A")
    b = _cube(model, "B")
    mates.attach(model, a, "B", "Bottom", "Top")
    mates.attach(model, b, "A", "Bottom", "Top")
    mates.refresh(model)                    # must terminate
    mates.refresh(model)


def test_detach_and_rename(model):
    base = _cube(model, "Base")
    lid = _cube(model, "Lid", size=10.0)
    mates.attach(model, lid, "Base", "Bottom", "Top")
    model.rename(base, "Chassis")
    assert mates.mate_of(lid)["parent"] == "Chassis"
    mates.detach(model, lid)
    assert mates.mate_of(lid) is None


def test_editing_a_placement_releases_the_mate(model):
    """Typing a position/rotation in Properties must stick: the mate
    re-solves on every change, so left in place it would overwrite the
    value before it reached the screen. Editing by hand detaches, like
    dragging a mated part does."""
    _cube(model, "Base")
    lid = _cube(model, "Lid", size=10.0)
    mates.attach(model, lid, "Base", "Bottom", "Top")
    assert lid.params["z"] == 20.0
    released = []
    model.mate_released.connect(released.append)

    model.set_param(lid, "z", -61.0)
    assert mates.mate_of(lid) is None
    assert released == [lid]
    mates.refresh(model)                     # nothing left to overwrite
    assert lid.params["z"] == -61.0


def test_editing_a_non_placement_param_keeps_the_mate(model):
    _cube(model, "Base")
    lid = _cube(model, "Lid", size=10.0)
    mates.attach(model, lid, "Base", "Bottom", "Top")
    model.set_param(lid, "color", "#ff0000")
    assert mates.mate_of(lid) is not None


def test_mate_roundtrips_kcad(model, tmp_path):
    base = _cube(model, "Base")
    lid = _cube(model, "Lid", size=10.0)
    mates.attach(model, lid, "Base", "Bottom", "Top", offset=2.0,
                 spin=45.0)
    path = tmp_path / "mated.kcad"
    document.save_kcad(model, str(path))
    other = DocumentModel()
    document.load_kcad(other, str(path))
    loaded = other.components()[1]
    mate = mates.mate_of(loaded)
    assert mate == dict(parent="Base", parent_anchor="Top",
                        anchor="Bottom", offset=2.0, spin=45.0)


def test_attach_to_user_anchor(model):
    base = _cube(model, "Base")
    anchors.add_user_anchor(model, base, [20.0, 10.0, 15.0],
                            [1.0, 0.0, 0.0], name="Port")
    bolt = _cube(model, "Bolt", size=4.0)
    mates.attach(model, bolt, "Base", "Bottom", "Port")
    pos, direction = _anchor_world(bolt, "Bottom")
    assert pos == pytest.approx([20.0, 10.0, 15.0])
    assert direction == pytest.approx([-1.0, 0.0, 0.0], abs=1e-6)


def test_attach_dialog_previews_live_and_cancel_restores(model):
    """Changing a value in the Attach dialog moves the part at once;
    Cancel puts the original mate and placement back."""
    base = _cube(model, "Base")
    lid = _cube(model, "Lid", size=10.0, x=50.0)
    dlg = mates.AttachDialog(model, lid)
    dlg.parent_combo.setCurrentIndex(
        dlg.parent_combo.findText("Base"))
    dlg.child_anchor.setCurrentIndex(
        dlg.child_anchor.findData("Bottom"))
    dlg.parent_anchor.setCurrentIndex(
        dlg.parent_anchor.findData("Top"))
    # the preview already applied the mate — no OK needed to see it
    assert lid.params.get("mate", {}).get("parent") == "Base"
    assert lid.params["z"] == pytest.approx(20.0)
    dlg.reject()
    assert lid.params.get("mate") is None        # original: no mate
    assert lid.params["x"] == pytest.approx(50.0)
    assert lid.params.get("z", 0.0) == pytest.approx(0.0)


def test_attach_dialog_ok_keeps_the_previewed_mate(model):
    _cube(model, "Base")
    lid = _cube(model, "Lid", size=10.0)
    dlg = mates.AttachDialog(model, lid)
    dlg.child_anchor.setCurrentIndex(dlg.child_anchor.findData("Bottom"))
    dlg.parent_anchor.setCurrentIndex(dlg.parent_anchor.findData("Top"))
    dlg._apply()
    assert lid.params["mate"] == dict(parent="Base",
                                      parent_anchor="Top",
                                      anchor="Bottom",
                                      offset=0.0, spin=0.0)
    assert lid.params["z"] == pytest.approx(20.0)


def test_flip_spin_normalises():
    assert mates._flip_spin(0.0) == 180.0
    assert mates._flip_spin(180.0) == 0.0
    assert mates._flip_spin(-90.0) == 90.0
    assert mates._flip_spin(90.0) == -90.0


def test_snap_tweak_popup_edits_the_mate_live(model):
    """The post-snap popup nudges offset/spin immediately and Detach
    removes the mate."""
    base = _cube(model, "Base")
    lid = _cube(model, "Lid", size=10.0)
    mates.attach(model, lid, "Base", "Bottom", "Top")
    popup = mates.SnapTweakPopup(model, lid)
    popup.offset.setValue(5.0)
    assert lid.params["mate"]["offset"] == 5.0
    assert lid.params["z"] == pytest.approx(25.0)   # lifted 5 mm
    popup.spin.setValue(45.0)
    assert lid.params["mate"]["spin"] == 45.0
    popup._detach()
    assert lid.params.get("mate") is None


# ------------------------------- a coloured part is still an assembly part

def test_colouring_a_part_keeps_it_mateable(model):
    """Colouring wraps a part in a `color` node, so it stops being a
    direct child of the assembly root. It must still count as an
    assembly part — otherwise the Snap tool sees one part instead of
    two and refuses, and nothing can mate to it."""
    base = _cube(model, "Base")
    lid = _cube(model, "Lid", size=10.0)
    tint = model.wrap_nodes([lid], "color")
    tint.params["color"] = "#c8a000"
    model.structure_changed.emit()

    assert lid in mates.parts(model)
    assert lid in mates._mate_siblings(base)
    assert base in mates._mate_siblings(lid)

    mates.attach(model, lid, "Base", "Bottom", "Top")
    pos, _d = _anchor_world(lid, "Bottom")
    assert pos == pytest.approx([10.0, 10.0, 20.0])   # sat on the base
    # and it still follows its parent
    before = lid.params["x"]
    base.params["x"] = 30.0
    mates.refresh(model)
    assert lid.params["x"] == pytest.approx(before + 30.0)


def test_a_transform_wrapper_is_not_seen_through(model):
    """Only a colour is transparent. A translate round a part really
    does move it, so mating the part inside would place it wrong —
    it stays out of the list rather than snapping to the wrong spot."""
    _cube(model, "Base")
    lid = _cube(model, "Lid", size=10.0)
    moved = model.wrap_nodes([lid], "translate")
    moved.params.update(x=50.0, y=0.0, z=0.0)
    model.structure_changed.emit()
    assert lid not in mates.parts(model)


def test_snap_tool_sees_a_coloured_instance(app):
    """End to end: the two-click Snap tool's part list."""
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    m = w.model
    comp = m.new_component("Block", visible=False)
    m.add_node("cube", dict(width=10.0, depth=10.0, height=10.0),
               parent=comp)
    a = m.add_instance(comp)
    b = m.add_instance(comp)
    tint = m.wrap_nodes([b], "color")
    tint.params["color"] = "#3070c0"
    m.structure_changed.emit()
    names = [p.name for p, _tris in w._snap_groups(None)]
    assert names == [a.name, b.name]


# ------------------------------------------------ the other mate kinds

def test_flush_align_points_the_anchors_the_same_way(model):
    base = _cube(model, "Base")
    lid = _cube(model, "Lid", size=10.0)
    mates.attach(model, lid, "Base", "Top", "Top", align="same")
    pos, direction = _anchor_world(lid, "Top")
    assert direction == pytest.approx([0.0, 0.0, 1.0], abs=1e-6)
    assert pos == pytest.approx([10.0, 10.0, 20.0])     # flush on top


def test_concentric_slides_and_a_drag_keeps_the_mate(model):
    shaft = _cube(model, "Shaft")
    ring = _cube(model, "Ring", size=10.0)
    mates.attach(model, ring, "Shaft", "Bottom", "Top", kind="concentric",
                 offset=5.0, min_offset=0.0, max_offset=30.0)
    pos, _d = _anchor_world(ring, "Bottom")
    assert pos == pytest.approx([10.0, 10.0, 25.0])
    # the user drags it 12 mm up the axis: the slide follows, the mate
    # stays, and the limit holds it at 30
    ring.params["z"] = float(ring.params["z"]) + 12.0
    assert mates.slide_to(model, ring) == pytest.approx(17.0)
    ring.params["z"] = float(ring.params["z"]) + 100.0
    assert mates.slide_to(model, ring) == pytest.approx(30.0)
    mates.refresh(model)
    assert mates.mate_of(ring) is not None
    pos, _d = _anchor_world(ring, "Bottom")
    assert pos[2] == pytest.approx(50.0)


def test_angle_mate_hinges_about_the_edge(model):
    base = _cube(model, "Base")
    door = _cube(model, "Door", size=10.0)
    mates.attach(model, door, "Base", "Bottom", "Front", kind="angle",
                 angle=90.0)
    # face to face on the front would point the door's bottom to +Y;
    # turned a quarter about the front face's horizontal edge it points
    # up or down instead
    _pos, direction = _anchor_world(door, "Bottom")
    assert abs(direction[1]) < 1e-6 and abs(abs(direction[2]) - 1) < 1e-6


def test_gear_mate_follows_the_parent_spin(model):
    frame = _cube(model, "Frame")
    drive = _cube(model, "Drive", size=10.0)
    driven = _cube(model, "Driven", size=10.0)
    mates.attach(model, drive, "Frame", "Bottom", "Top", spin=30.0)
    mates.attach(model, driven, "Drive", "Bottom", "Top", ratio=2.0)
    assert driven.params["rz"] == pytest.approx(-60.0)   # 2 x 30, reversed
    mates.attach(model, drive, "Frame", "Bottom", "Top", spin=45.0)
    assert driven.params["rz"] == pytest.approx(-90.0)


def test_plain_mates_store_no_extras(model):
    base = _cube(model, "Base")
    lid = _cube(model, "Lid")
    mates.attach(model, lid, "Base", "Bottom", "Top")
    assert set(mates.mate_of(lid)) == {"parent", "parent_anchor",
                                       "anchor", "offset", "spin"}
