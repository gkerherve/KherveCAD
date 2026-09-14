"""The human figure's rig: skin weights, bone matrices, pose rows, and
set_pose on a figure; plus head-only refinement of a sculpt.

Run with: python -m pytest tests/  (offscreen Qt).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
from collections import Counter
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import deform, document, human, mesh, scadparse
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _closed(tris) -> bool:
    edges = Counter()
    for a, b, c in tris:
        for u, v in ((a, b), (b, c), (c, a)):
            edges[(u, v)] += 1
    return all(edges[(v, u)] == n for (u, v), n in edges.items())


def test_the_rig_ships_with_joints_that_follow_the_macro_targets():
    sk = human.skeleton()
    assert "upperarm02.L" in sk["bones"] and sk["bones"]["upperarm02.L"]["parent"] == "upperarm01.L"
    assert len(sk["weights"]) > 100
    base = human.joint_position("upperarm02.L____head", {})
    heavy = human.joint_position("upperarm02.L____head", {"female-maxweight": 1.0})
    assert base != heavy                       # the helpers move with the body
    assert human.joint_position("no-such-joint", {}) == [0.0, 0.0, 0.0]
    assert "head" in human.bone_names()


def test_a_pose_lifts_the_arm_and_the_body_stays_closed():
    still = human.build(stature=1630)
    lifted = human.build(stature=1630, pose=[["upperarm02.L", 0, 0, 60]])
    assert _closed(lifted) and len(lifted) == len(still)
    # the left hand (x > 350) rises when the upper arm turns about z... the
    # hand is the far end of what moved: it is somewhere else now
    hand_still = [v for t in still for v in t if v[0] > 450]
    hand_lifted = [v for t in lifted for v in t if v[0] > 200 and v not in hand_still]
    assert hand_still and hand_lifted
    # the legs did not move (compared as rounded multisets: a skinned
    # vertex under identity bones comes back equal to 1e-13)
    def legs(tris):
        return Counter(tuple(round(c, 4) for c in v)
                       for t in tris for v in t if v[2] < 300)
    assert legs(still) == legs(lifted)
    # a child bone carries its parent's turn
    elbow = human.build(stature=1630, pose=[["upperarm02.L", 0, 0, 60],
                                             ["lowerarm01.L", 40, 0, 0]])
    assert elbow != lifted and _closed(elbow)
    assert human.pose_points([(1, 2, 3)], [], {}) == [(1, 2, 3)]
    assert human.bone_matrices([["nobody", 1, 2, 3]], {}) == {}


def test_pose_rows_bake_validate_round_trip_and_the_tool_sets_them(app, tmp_path):
    doc = DocumentModel()
    node = doc.add_node("human", dict(stature=1630.0,
                                      pose=[["upperarm02.L", 0.0, 0.0, 60.0]]))
    assert node.id not in validate(doc.root)
    code = doc.to_scad()
    assert 'pose = [["upperarm02.L", 0, 0, 60]]' in code
    path = tmp_path / "pose.scad"
    document.export_scad(doc, str(path))
    other = DocumentModel()
    assert not scadparse.import_scad(other, str(path))
    back = next(n for n in other.root.walk() if n.type == "human")
    assert back.params["pose"] == [["upperarm02.L", 0.0, 0.0, 60.0]]
    assert other.to_scad().splitlines()[3:] == code.splitlines()[3:]
    node.params["pose"] = [["nobody", 1.0, 0.0, 0.0]]
    assert "no bone" in validate(doc.root)[node.id]
    node.params["pose"] = []
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    win = MainWindow()
    ex = McpToolExecutor(win)
    fig = ex.execute("add_node", {"type": "human", "params": {"stature": 1630}})["created"]
    listing = ex.execute("set_pose", {"node_id": fig, "bones": {}})
    assert "upperarm02.L" in listing["bones"] and listing["pose"] == []
    out = ex.execute("set_pose", {"node_id": fig, "bones": {
        "upperarm02.L": {"rz": 60}, "lowerarm01.L": {"rx": 30}}})
    assert "error" not in out, out
    assert out["pose"] == [["upperarm02.L", 0.0, 0.0, 60.0], ["lowerarm01.L", 30.0, 0.0, 0.0]]
    more = ex.execute("set_pose", {"node_id": fig, "bones": {"upperarm02.L": {"rx": 10}}})
    assert more["pose"][0] == ["upperarm02.L", 10.0, 0.0, 60.0]      # rz kept
    bad = ex.execute("set_pose", {"node_id": fig, "bones": {"upperarm": {"rx": 1}}})
    assert "error" in bad and "upperarm01.L" in bad["error"]
    assert "error" in ex.execute("set_pose", {"bones": {"head": {"rx": 1}}})


def test_split_long_edges_can_refine_one_region_only():
    box = [((0, 0, 0), (0, 20, 0), (20, 20, 0)), ((0, 0, 0), (20, 20, 0), (20, 0, 0))]
    whole = deform.split_long_edges(box, 5.0)
    part = deform.split_long_edges(box, 5.0, region=[[-1, -1, -1], [12, 12, 1]])
    assert 2 < len(part) < len(whole)
    # fine near the origin, coarser towards the far corner
    def area(t):
        (ax, ay, _), (bx, by, _), (cx, cy, _) = t
        return abs((bx - ax) * (cy - ay) - (cx - ax) * (by - ay)) / 2
    near = [area(t) for t in part if sum(v[0] + v[1] for v in t) / 3 < 10]
    far = [area(t) for t in part if sum(v[0] + v[1] for v in t) / 3 > 26]
    assert near and far
    assert sum(near) / len(near) < sum(far) / len(far)
    doc = DocumentModel()
    cube = doc.add_node("cube")
    node = doc.wrap_nodes([cube], "sculpt")
    node.params.update(detail=2.0, region=[[0, 0, 15], [20, 20, 21]])
    top = mesh.tessellate(doc.root)
    node.params["region"] = []
    everywhere = mesh.tessellate(doc.root)
    assert 12 < len(top) < len(everywhere)
    node.params["region"] = [[1, 2]]
    assert "two corners" in validate(doc.root)[node.id]
