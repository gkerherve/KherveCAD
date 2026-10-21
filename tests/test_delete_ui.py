"""Deleting a container: keep what it holds, or delete everything.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import delete_ui
from khervecad.model import DocumentModel


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _doc():
    m = DocumentModel()
    d = m.add_node("difference", {})
    e = m.add_node("linear_extrude", {}, parent=d)
    p = m.add_node("polygon", {}, parent=e)
    return m, d, e, p


def test_keep_what_is_inside(app, monkeypatch):
    m, d, e, p = _doc()
    monkeypatch.setattr(delete_ui, "ask_hook", lambda n: delete_ui.KEEP)
    assert delete_ui.delete_nodes(None, m, [d]) == delete_ui.KEEP
    assert d not in m.root.children
    assert e in m.root.children and p in e.children


def test_delete_everything_or_cancel(app, monkeypatch):
    m, d, e, p = _doc()
    monkeypatch.setattr(delete_ui, "ask_hook", lambda n: delete_ui.CANCEL)
    delete_ui.delete_nodes(None, m, [d])
    assert d in m.root.children
    monkeypatch.setattr(delete_ui, "ask_hook", lambda n: delete_ui.ALL)
    delete_ui.delete_nodes(None, m, [d])
    assert m.root.children == []


def test_a_leaf_is_deleted_without_asking(app, monkeypatch):
    m, d, e, p = _doc()
    asked = []
    monkeypatch.setattr(delete_ui, "ask_hook",
                        lambda n: asked.append(n) or delete_ui.CANCEL)
    delete_ui.delete_nodes(None, m, [p])
    assert not asked and p not in e.children


def test_the_tree_asks(app, monkeypatch):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        m = win.model
        d = m.add_node("difference", {})
        c = m.add_node("cube", {}, parent=d)
        monkeypatch.setattr(delete_ui, "ask_hook",
                            lambda n: delete_ui.KEEP)
        win.builder.active_tree().select_nodes([d])
        win._delete_selection()
        assert c.parent is m.root and d.parent is None
    finally:
        win._dirty = False
        win.close()
