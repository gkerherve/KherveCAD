"""Inverse kinematics (ik.py): the solver, both rigs, the MCP tool.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os
import random

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")

from PyQt5.QtWidgets import QApplication

from khervecad import human, ik, mesh, scadparse
from khervecad.model import DocumentModel

ARM = """
kcad_joint(pivot = [2, 2, 0]) {
  cube([4, 4, 50]);  // Upper
  kcad_joint(pivot = [2, 2, 50]) {
    translate([0, 0, 50]) cube([4, 4, 40]);  // Fore
    translate([0, 0, 90]) cube([4, 4, 4]);  // Grip
  }
}"""


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_euler_decomposition_matches_openscad_rotate():
    rng = random.Random(1)
    for _ in range(100):
        a = [rng.uniform(-85, 85) for _ in range(3)]
        assert ik.matrix_euler(ik.euler_matrix(*a)) == pytest.approx(a)


def test_node_matrix_now_knows_joints():
    root, _w = scadparse.parse_scad(
        "kcad_joint(pivot = [0, 0, 10], a = [90, 0, 0]) cube(1);")
    cube = next(n for n in root.walk() if n.type == "cube")
    p = mesh.mat_apply(mesh.ancestor_matrix(cube), [0, 0, 20])
    assert p == pytest.approx([0, -10, 10])


def test_a_jointed_arm_reaches_a_point(app):
    doc = DocumentModel()
    root, _w = scadparse.parse_scad(ARM)
    for child in list(root.children):
        doc.root.add(child)
    grip = next(n for n in doc.root.walk() if "Grip" in n.name)
    out = ik.reach(doc, grip, [40, 20, 60])
    assert out["reached"] and out["miss"] < 0.5
    tris = mesh.tessellate(grip)
    m = mesh.ancestor_matrix(grip)
    pts = [mesh.mat_apply(m, p) for t in tris for p in t]
    centre = [(min(p[i] for p in pts) + max(p[i] for p in pts)) / 2
              for i in range(3)]
    assert centre == pytest.approx([40, 20, 60], abs=0.5)


def test_out_of_reach_says_how_far(app):
    doc = DocumentModel()
    root, _w = scadparse.parse_scad(ARM)
    for child in list(root.children):
        doc.root.add(child)
    grip = next(n for n in doc.root.walk() if "Grip" in n.name)
    out = ik.reach(doc, grip, [300, 0, 0])
    assert not out["reached"] and "beyond the chain's reach" in out["note"]


@pytest.mark.skipif(not human.available(), reason="no human data")
def test_a_figure_puts_its_hand_on_a_point(app):
    doc = DocumentModel()
    fig = doc.add_node("human", dict(stature=1700.0))
    target = [250.0, -250.0, 1100.0]
    out = ik.reach(doc, fig, target, "left_hand")
    assert out["reached"]
    pts = human.points(stature=1700.0, pose=fig.params["pose"])
    # the wrist's own surface lies within ~3 cm of its joint
    assert min(math.dist(p, target) for p in pts) < 30


def test_the_mcp_tool(app):
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    win = MainWindow()
    ex = McpToolExecutor(win)
    assert "error" not in ex.execute("apply_code", {"code": ARM})
    grip = next(n for n in win.model.root.walk() if "Grip" in n.name)
    out = ex.execute("reach", {"node_id": grip.id, "target": [30, 0, 70]})
    assert "error" not in out, out
    assert out["reached"] and out["rig"] == "joints"
    cube = ex.execute("reach", {"node_id": grip.id})
    assert "error" in cube
