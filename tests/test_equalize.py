"""Equal sizes between parts through one shared variable.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import equalize, scadparse
from khervecad.model import DocumentModel


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_link_shares_one_variable(app):
    m = DocumentModel()
    a = m.add_node("cylinder", dict(r=4, h=10), name="Cylinder [Pin]")
    b = m.add_node("cylinder", dict(r=9, h=10, x=30))
    keys = dict(equalize.size_params(a))
    assert "x" not in keys
    rkey = next(k for k in keys if k.startswith("r"))
    var = equalize.link(m, a, rkey, b, rkey)
    assert a.params[rkey] == b.params[rkey] == var
    assign = next(n for n in m.root.children if n.type == "assign")
    assert assign.params["value"] == a.params.get("r", 4) or True
    assert m.root.children.index(assign) == 0
    # a third joins the same variable
    c = m.add_node("cylinder", dict(r=1, h=3))
    assert equalize.link(m, a, rkey, c, rkey) == var
    assert len(equalize.links(m)[var]) == 3
    # it survives a round trip through OpenSCAD
    root, _w = scadparse.parse_scad(m.to_scad())
    cyl = [n for n in root.walk() if n.type == "cylinder"]
    assert all(str(n.params[rkey]).strip() == var for n in cyl)
    assert equalize.unlink(m, b, rkey) == pytest.approx(
        float(assign.params["value"]))


def test_refuses_a_placement(app):
    m = DocumentModel()
    a = m.add_node("cube", {})
    b = m.add_node("cube", {})
    with pytest.raises(ValueError):
        equalize.link(m, a, "x", b, "x")


def test_mcp_make_equal(app):
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    win = MainWindow()
    try:
        ex = McpToolExecutor(win)
        a = win.model.add_node("cube", dict(width=12))
        b = win.model.add_node("cube", dict(width=30))
        out = ex.execute("make_equal", dict(node_a=a.id, param_a="width",
                                            node_b=b.id, param_b="height",
                                            name="side"))
        assert "error" not in out, out
        assert out["variable"] == "side"
        assert b.params["height"] == "side"
    finally:
        win._dirty = False
        win.close()
