"""Configurations: save, apply, round trip in the .kcad, MCP.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import configurations as cf, document, mesh
from khervecad.model import DocumentModel


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _doc():
    m = DocumentModel()
    m.add_node("assign", dict(variable="L", value=20))
    m.add_node("cube", dict(width="L", depth=10, height=10))
    return m


def _xmax(m):
    return max(p[0] for t in mesh.tessellate(m.root) for p in t)


def test_save_and_apply(app):
    m = _doc()
    cf.save(m, "Short")
    cf.save(m, "Long", {"L": 80})
    assert cf.active(m) == "Long"
    cf.apply(m, "Long")
    assert _xmax(m) == pytest.approx(80)
    cf.apply(m, "Short")
    assert _xmax(m) == pytest.approx(20)
    with pytest.raises(ValueError):
        cf.save(m, "Bad", {"nope": 1})
    with pytest.raises(ValueError):
        cf.apply(m, "Missing")


def test_saved_in_the_kcad(app, tmp_path):
    m = _doc()
    cf.save(m, "Long", {"L": 80})
    path = str(tmp_path / "c.kcad")
    document.save_kcad(m, path)
    m2 = DocumentModel()
    document.load_kcad(m2, path)
    assert cf.all_of(m2) == {"Long": {"L": 80}}
    assert cf.active(m2) == "Long"


def test_mcp_configurations(app):
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    win = MainWindow()
    try:
        ex = McpToolExecutor(win)
        win.model.add_node("assign", dict(variable="L", value=20))
        out = ex.execute("configurations", dict(action="save", name="A"))
        assert "error" not in out, out
        ex.execute("configurations", dict(action="save", name="B",
                                          values={"L": 5}))
        out = ex.execute("configurations", dict(action="apply", name="B"))
        assert out["variables"]["L"] == 5 and out["active"] == "B"
        dlg = cf.open_window(win)
        assert dlg.list.count() == 2
        dlg.close()
    finally:
        win._dirty = False
        win.close()
