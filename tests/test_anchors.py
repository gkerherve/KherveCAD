"""Tests for anchors: bounding-box anchors, world transforms, origin
re-basing, persistence and face/edge pick classification.

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

from khervecad import anchors, document, mesh
from khervecad.model import DocumentModel


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model(app):
    return DocumentModel()


def _cube_component(model, size=20.0, **placement):
    comp = model.new_component("Block")
    comp.params.update(placement)
    model.add_node("cube", dict(width=size, depth=size, height=size),
                   parent=comp)
    return comp


def _by_name(items, name):
    return next(a for a in items if a["name"] == name)


def test_auto_anchors_faces_edges_corners(model):
    comp = _cube_component(model)
    items = anchors.auto_anchors(comp)
    kinds = {}
    for a in items:
        kinds[a["kind"]] = kinds.get(a["kind"], 0) + 1
    assert kinds == {"origin": 1, "face": 6, "edge": 12, "corner": 8}
    top = _by_name(items, "Top")
    assert top["pos"] == pytest.approx([10.0, 10.0, 20.0])
    assert top["dir"] == pytest.approx([0.0, 0.0, 1.0])
    edge = _by_name(items, "Right-Top")
    assert edge["pos"] == pytest.approx([20.0, 10.0, 20.0])


def test_anchors_ignore_placement(model):
    """Anchors are local: moving/rotating the Object must not change
    them (that's what placement is for)."""
    comp = _cube_component(model, x=100.0, rz=45.0)
    top = _by_name(anchors.auto_anchors(comp), "Top")
    assert top["pos"] == pytest.approx([10.0, 10.0, 20.0])


def test_anchor_world_applies_placement(model):
    comp = _cube_component(model, x=50.0, rz=90.0)
    top = _by_name(anchors.auto_anchors(comp), "Top")
    pos, direction = anchors.anchor_world(comp, top)
    # rotate (10, 10, 20) by 90 deg about Z -> (-10, 10, 20), then +50 X
    assert pos == pytest.approx([40.0, 10.0, 20.0])
    assert direction == pytest.approx([0.0, 0.0, 1.0])
    # and to_local round-trips
    assert anchors.to_local(comp, pos) == pytest.approx([10.0, 10.0,
                                                         20.0])


def test_user_anchor_roundtrips_kcad(model, tmp_path):
    comp = _cube_component(model)
    anchors.add_user_anchor(model, comp, [20.0, 10.0, 10.0],
                            [1.0, 0.0, 0.0], name="Port")
    path = tmp_path / "anchored.kcad"
    document.save_kcad(model, str(path))
    other = DocumentModel()
    document.load_kcad(other, str(path))
    loaded = other.components()[0]
    users = anchors.user_anchors(loaded)
    assert len(users) == 1
    assert users[0]["name"] == "Port"
    assert users[0]["pos"] == [20.0, 10.0, 10.0]
    assert users[0]["dir"] == [1.0, 0.0, 0.0]


def test_add_user_anchor_unique_names(model):
    comp = _cube_component(model)
    a1 = anchors.add_user_anchor(model, comp, [0, 0, 0], [0, 0, 1],
                                 name="Face")
    a2 = anchors.add_user_anchor(model, comp, [1, 1, 1], [0, 0, 1],
                                 name="Face")
    assert a1["name"] == "Face"
    assert a2["name"] == "Face 2"
    anchors.remove_user_anchor(model, comp, "Face")
    assert [a["name"] for a in anchors.user_anchors(comp)] == ["Face 2"]


def test_set_origin_keeps_scene_position(model):
    """Re-basing the origin must not move the geometry in the scene."""
    comp = _cube_component(model, x=30.0)
    before = sorted((round(v[0], 3), round(v[1], 3), round(v[2], 3))
                    for t in mesh.tessellate(comp) for v in t)
    top = _by_name(anchors.auto_anchors(comp), "Top")
    anchors.set_origin(model, comp, top["pos"])
    after = sorted((round(v[0], 3), round(v[1], 3), round(v[2], 3))
                   for t in mesh.tessellate(comp) for v in t)
    assert before == after
    # the Top face centre is now the local origin
    new_top = _by_name(anchors.auto_anchors(comp), "Top")
    assert new_top["pos"] == pytest.approx([0.0, 0.0, 0.0])


def test_set_origin_shifts_user_anchors(model):
    comp = _cube_component(model)
    anchors.add_user_anchor(model, comp, [20.0, 10.0, 10.0],
                            [1.0, 0.0, 0.0], name="Port")
    anchors.set_origin(model, comp, [10.0, 10.0, 0.0])
    port = anchors.user_anchors(comp)[0]
    assert port["pos"] == pytest.approx([10.0, 0.0, 10.0])


def test_pick_face_and_edge(model):
    """Picking the middle of a cube face yields the face centre; near a
    boundary it yields the full edge midpoint."""
    comp = _cube_component(model)                    # 0..20 cube
    tris = anchors.local_tris(comp)

    def projector(v):                # orthographic top view: x, y, depth
        return (v[0], v[1], 100.0 - v[2])

    index, point = anchors.pick(tris, projector, 10.0, 10.0)
    assert index is not None
    assert point[2] == pytest.approx(20.0)           # hit the top face
    desc = anchors.describe_pick(tris, index, point, tol=1.0)
    assert desc["kind"] == "face"
    assert desc["pos"] == pytest.approx([10.0, 10.0, 20.0])
    assert desc["dir"] == pytest.approx([0.0, 0.0, 1.0])

    # near the +X boundary of the top face -> the Right-Top edge
    index, point = anchors.pick(tris, projector, 19.6, 10.0)
    desc = anchors.describe_pick(tris, index, point, tol=1.0)
    assert desc["kind"] == "edge"
    assert desc["pos"] == pytest.approx([20.0, 10.0, 20.0])
    # edge direction bisects the two faces (+X and +Z)
    d = desc["dir"]
    assert d[0] == pytest.approx(d[2])
    assert d[0] > 0.5
    assert d[1] == pytest.approx(0.0, abs=1e-6)
