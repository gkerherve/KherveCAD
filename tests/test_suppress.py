"""Suppress and roll back: what the preview draws, the program written,
the round trip through OpenSCAD and the MCP tool.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import mesh, scadparse, suppress
from khervecad.model import DocumentModel


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _part(m):
    d = m.add_node("difference", {})
    m.add_node("cube", dict(size_x=20, size_y=20, size_z=20), parent=d)
    m.add_node("cylinder", dict(x=10, y=10, z=-5), parent=d)
    t = m.add_node("translate", dict(x=50))
    m.add_node("sphere", {}, parent=t)
    return d, t


def _xmax(m):
    tris = mesh.tessellate(m.root)
    return max(p[0] for tri in tris for p in tri)


def test_a_suppressed_wrapper_passes_its_children_through(app):
    m = DocumentModel()
    _d, t = _part(m)
    assert _xmax(m) > 50
    suppress.set_suppressed(m, [t])
    assert _xmax(m) < 30                 # the sphere is back at 0
    assert "kcad_off(" in m.to_scad()


def test_a_suppressed_cut_keeps_the_body_and_a_leaf_vanishes(app):
    m = DocumentModel()
    d, t = _part(m)
    suppress.set_suppressed(m, [d])
    kept = suppress.kept_children(d)
    assert [n.type for n in kept] == ["cube"]
    suppress.set_suppressed(m, [d], False)
    sphere = t.children[0]
    suppress.set_suppressed(m, [sphere])
    assert not mesh.tessellate(t)


def test_rollback_switches_off_what_follows(app):
    m = DocumentModel()
    d, t = _part(m)
    suppress.roll_back_to(m, d)
    assert suppress.is_off(t) and not suppress.is_off(d)
    assert _xmax(m) < 30
    suppress.roll_forward(m)
    assert not suppress.is_off(t)


def test_round_trip_through_openscad(app):
    m = DocumentModel()
    d, t = _part(m)
    suppress.set_suppressed(m, [d])
    suppress.roll_back_to(m, d)
    root, warnings = scadparse.parse_scad(m.to_scad())
    assert not warnings
    kids = root.children
    assert kids[0].type == "difference" and kids[0].params["suppressed"]
    assert kids[1].type == "translate"
    assert not kids[1].params.get("suppressed")
    assert root.params["rollback"] == 1


def test_mcp_suppress(app):
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    win = MainWindow()
    try:
        ex = McpToolExecutor(win)
        d, t = _part(win.model)
        out = ex.execute("suppress", dict(action="suppress",
                                          node_ids=[t.id]))
        assert "error" not in out, out
        assert [s["id"] for s in out["suppressed"]] == [t.id]
        out = ex.execute("suppress", dict(action="rollback", node_id=d.id))
        assert out["rollbacks"][0]["at"] == 1
        out = ex.execute("suppress", dict(action="roll_forward"))
        assert out["rollbacks"] == []
    finally:
        win._dirty = False
        win.close()
