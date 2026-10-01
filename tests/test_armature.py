"""armature.py: bones for any mesh with automatic weights, the node's
code, IK through its bones, the rig_armature tool and the PlanetCraft
export of a rigged body.

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

import numpy as np
import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import armature, bake, ik, mesh, scadparse
from khervecad.model import DocumentModel, validate

ARM = [["upper", "", 0, 0, 0, 0, 0, 50],
       ["lower", "upper", 0, 0, 50, 0, 0, 100]]


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _doc(pose=None):
    doc = DocumentModel()
    cap = doc.add_node("capsule", dict(z1=0.0, z2=100.0, radius=8.0))
    node = doc.wrap_nodes([cap], "armature")
    node.params.update(detail=4.0, bones=[list(b) for b in ARM],
                       pose=pose or [])
    return doc, node


def _points(doc):
    return np.asarray(mesh.tessellate(doc.root)).reshape(-1, 3)


def test_the_rest_pose_changes_nothing(app):
    doc, node = _doc()
    assert node.id not in validate(doc.root)
    a = _points(doc)
    assert a[:, 2].max() == pytest.approx(108, abs=0.5)


def test_a_bent_elbow_bends_the_one_skin_smoothly(app):
    doc, node = _doc([["lower", 0, 90, 0]])
    a = _points(doc)
    assert a[:, 0].max() > 55.0               # the forearm lies along +x
    assert a[:, 2].max() < 62.0
    assert a[:, 2].min() == pytest.approx(-8.0, abs=0.5)   # the base stays
    points, faces = bake.to_polyhedron(mesh.tessellate(doc.root))
    assert bake._check_polyhedron(dict(points=points, faces=faces)) is None


def test_weights_sum_to_one_and_follow_the_nearest_bone():
    bones = armature.parse_bones(ARM)
    pts = np.array([[0, 0, 10.0], [0, 0, 90.0], [0, 0, 50.0]])
    w, names = armature.auto_weights(pts, np.zeros((0, 2), int), bones)
    assert np.allclose(w.sum(axis=1), 1.0)
    assert w[0, names.index("upper")] > 0.9
    assert w[1, names.index("lower")] > 0.9
    assert 0.3 < w[2, 0] < 0.7                 # the joint is shared


def test_a_parent_carries_its_children():
    bones = armature.parse_bones(ARM)
    mats = armature.bone_matrices(bones, {"upper": [0, 90, 0]})
    tip = np.asarray(mats["lower"]) @ [0, 0, 100, 1]
    assert tip[:3] == pytest.approx([100, 0, 0], abs=1e-6)


def test_round_trip_and_validation(app):
    doc, node = _doc([["lower", 10, 20, 30]])
    root, warnings = scadparse.parse_scad(doc.to_scad())
    assert not warnings
    back = next(n for n in root.walk() if n.type == "armature")
    assert back.params["bones"] == node.params["bones"]
    assert back.params["pose"] == node.params["pose"]
    node.params["pose"] = [["elbow", 0, 0, 0]]
    assert "elbow" in validate(doc.root)[node.id]
    node.params["pose"] = []
    node.params["bones"] = [["a", "b", 0, 0, 0, 0, 0, 1],
                            ["b", "a", 0, 0, 1, 0, 0, 2]]
    assert "ancestor" in validate(doc.root)[node.id]
    node.params["bones"] = []
    assert "bones" in validate(doc.root)[node.id]


def test_ik_reaches_with_a_bone_tip(app):
    doc, node = _doc()
    out = ik.reach(doc, node, [60, 0, 40], effector="lower", chain=2)
    assert out["rig"] == "armature" and out["reached"], out
    assert node.params["pose"]


def test_bones_from_a_skeleton():
    rows = armature.bones_from_skin([[0, 0, 0, 5, -1], [0, 0, 30, 4, 0],
                                     [0, 0, 60, 3, 1]])
    assert [r[:2] for r in rows] == [["b1", ""], ["b2", "b1"]]
    assert rows[1][2:] == [0, 0, 30, 0, 0, 60]


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 700)
    return win


def test_rig_armature_and_set_pose_tools(window):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(window)
    doc = window.model
    move = doc.add_node("translate", dict(x=100.0))
    cap = doc.add_node("capsule", dict(z1=0.0, z2=100.0, radius=8.0),
                       parent=move)
    out = ex.execute("rig_armature", {
        "node_id": cap.id, "detail": 4,
        "bones": [{"name": "upper", "head": [100, 0, 0],
                   "tail": [100, 0, 50]},
                  {"name": "lower", "parent": "upper",
                   "head": [100, 0, 50], "tail": [100, 0, 100]}],
        "pose": {"lower": {"ry": 90}}})
    assert "error" not in out, out
    assert out["bones"][0]["head"] == [0, 0, 0]       # own frame
    a = np.asarray(mesh.tessellate(doc.root)).reshape(-1, 3)
    assert a[:, 0].max() > 155.0
    out = ex.execute("set_pose", {"node_id": out["armature"],
                                  "bones": {"lower": {"ry": 0}}})
    assert "error" not in out, out
    assert "error" in ex.execute("set_pose", {"node_id": out["armature"],
                                              "bones": {"elbow": {"ry": 1}}})


def test_planetcraft_cuts_a_rigged_body_by_bone(app):
    from khervecad import planetcraft
    doc = DocumentModel()
    body = doc.add_node("capsule", dict(x1=-40.0, z1=60.0, x2=40.0, z2=60.0,
                                        radius=15.0))
    legs = []
    for x, y in ((-30, -10), (-30, 10), (30, -10), (30, 10)):
        legs.append(doc.add_node("capsule", dict(x1=x, y1=y, z1=60.0, x2=x,
                                                 y2=y, z2=0.0, radius=5.0)))
    head = doc.add_node("sphere", dict(x=55.0, z=75.0, radius=14.0))
    group = doc.wrap_nodes([body] + legs + [head], "union")
    rig = doc.wrap_nodes([group], "armature")
    bones = [["spine", "", -40, 0, 60, 40, 0, 60],
             ["Head", "spine", 45, 0, 65, 65, 0, 80]]
    for name, (x, y) in zip(("Back right leg", "Back left leg",
                             "Front right leg", "Front left leg"),
                            ((-30, -10), (-30, 10), (30, -10), (30, 10))):
        bones.append([name, "spine", x, y, 55, x, y, 0])
    rig.params["bones"] = bones
    creature = planetcraft.build_creature(doc, "Beast")
    roles = {p["role"] for p in creature["parts"]}
    assert {"body", "head"} <= roles
    assert sum(1 for r in roles if r.startswith("leg")) == 4
