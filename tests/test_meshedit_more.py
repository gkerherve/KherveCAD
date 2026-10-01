"""meshedit_more.py and its UI / MCP: Inset, Loop Cut, Knife, Bridge and
Spin — every result a closed solid.

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

from khervecad import mesh, meshedit as me, meshedit_more as mm
from khervecad.model import CadNode


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def _cube():
    t = [x for x, _c, _s in mesh._tess(
        CadNode("cube", "", dict(width=20.0, depth=20.0, height=20.0)), {},
        None, frozenset(), False)]
    return me.triangles_to_mesh(t)


def _top(points):
    return [i for i, q in enumerate(points) if q[2] > 19]


def test_inset_borders_the_face_and_pushes_it():
    p, f = _cube()
    p2, f2, sel = mm.inset(p, f, _top(p), 4, 2)
    assert me.check(p2, f2) is None
    assert len(f2) == 6 + 4
    inner = [p2[i] for i in sel]
    assert all(q[2] == pytest.approx(22) for q in inner)
    assert sorted({round(q[0]) for q in inner}) == [4, 16]


def test_inset_needs_whole_faces():
    p, f = _cube()
    with pytest.raises(mm.EditFailed):
        mm.inset(p, f, [0], 2)


def test_a_loop_cut_rings_the_cube():
    p, f = _cube()
    a, b = me.edges(f)[0]
    p2, f2, sel = mm.loop_cut(p, f, a, b, cuts=2)
    assert me.check(p2, f2) is None
    assert len(sel) == 8 and len(f2) == 2 + 4 * 3


def test_the_knife_splits_what_it_crosses():
    p, f = _cube()
    p2, f2, sel = mm.knife(p, f, [10, 10, 10], [1, 0, 0])
    assert me.check(p2, f2) is None
    assert len(f2) == 6 + 4 and len(sel) == 4
    with pytest.raises(mm.EditFailed):
        mm.knife(p, f, [50, 0, 0], [1, 0, 0])


def test_bridge_tunnels_between_two_faces():
    p, f = _cube()
    p, f, _s = mm.inset(p, f, _top(p), 4)
    bottom = [i for i, q in enumerate(p) if q[2] < 1]
    p, f, _s = mm.inset(p, f, bottom, 4)
    inner = [i for i, q in enumerate(p)
             if 3 < q[0] < 17 and 3 < q[1] < 17]
    p2, f2, _sel = mm.bridge(p, f, inner)
    assert me.check(p2, f2) is None
    assert len(f2) == len(f) - 2 + 4
    # a genus-one solid: V - E + F = 0
    edges = len(me.edges(f2))
    assert len(p2) - edges + len(f2) == 0


def test_spin_curls_a_tapering_horn():
    p, f = _cube()
    p2, f2, sel = mm.spin(p, f, _top(p), [30, 10, 20], [0, 1, 0], 90, 6,
                          0.3)
    assert me.check(p2, f2) is None
    tip = [p2[i] for i in sel]
    centre = [sum(q[k] for q in tip) / len(tip) for k in range(3)]
    # the face turned a quarter round the pivot (30, *, 20): up to z = 40
    assert centre == pytest.approx([30, 10, 40], abs=0.5)
    span = max(q[2] for q in tip) - min(q[2] for q in tip)   # now upright
    assert span == pytest.approx(20 * 0.3, abs=0.2)


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 700)
    return win


def test_edit_mesh_runs_the_new_operations(window):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(window)
    cube = window.model.add_node("cube")
    out = ex.execute("edit_mesh", {"node_id": cube.id, "operation": "open"})
    node = out["node_id"]
    top = {"min": [-1, -1, 19], "max": [21, 21, 21]}
    out = ex.execute("edit_mesh", {"node_id": node, "operation": "inset",
                                   "within": top, "thickness": 3,
                                   "depth": 1})
    assert "error" not in out, out
    assert out["face_count"] == 10
    out = ex.execute("edit_mesh", {"node_id": node, "operation": "spin",
                                   "vertices": out["selection"],
                                   "origin": [30, 10, 21],
                                   "axis": [0, 1, 0], "angle": 60,
                                   "steps": 4, "taper": 0.5})
    assert "error" not in out, out
    out = ex.execute("edit_mesh", {"node_id": node, "operation": "knife",
                                   "at": [10, 10, 5], "normal": [0, 0, 1]})
    assert "error" not in out, out
    out = ex.execute("edit_mesh", {"node_id": node, "operation": "loop_cut",
                                   "edge": [0, 1]})
    assert "error" in out or out["face_count"] > 0
    assert "error" in ex.execute("edit_mesh", {
        "node_id": node, "operation": "bridge", "all": True})


def test_the_keys_reach_the_tools(window):
    from PyQt5.QtCore import QEvent, Qt
    from PyQt5.QtGui import QKeyEvent
    from khervecad import meshedit_ui
    cube = window.model.add_node("cube")
    session = meshedit_ui.start(window, cube)
    assert session is not None
    session.selection = set(i for i, q in enumerate(session.points)
                            if q[2] > 19)
    key = QKeyEvent(QEvent.KeyPress, Qt.Key_I, Qt.NoModifier)
    assert session.wants_key(key)
    session.key_press(key)
    assert len(session.faces) == 10            # inset, now scaling
    session.confirm()
    ctrl_r = QKeyEvent(QEvent.KeyPress, Qt.Key_R, Qt.ControlModifier)
    assert session.wants_key(ctrl_r)
    session.key_press(QKeyEvent(QEvent.KeyPress, Qt.Key_K, Qt.NoModifier))
    assert session._knife == []
    session.key_press(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape,
                                Qt.NoModifier))
    assert session._knife is None
    session.exit()
