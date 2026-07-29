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
