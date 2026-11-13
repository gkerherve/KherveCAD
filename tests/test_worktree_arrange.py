"""Arranging the Objects list (2026-11-13, the user: "we should be able
to arrange the objects list ... currently I don't think it is
possible"): the Work tree tab's rows move by drag, Ctrl+Up / Down and
the right-click menu's Move Up / Down and Sort, and it is the
document's order that changes.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import worktree_tab as wt
from khervecad.model import CadNode, DocumentModel

NAMES = ["Exercice 1", "Exercise 2", "Exercise 10", "Exercise 6",
         "Exercise 5"]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _doc():
    m = DocumentModel()
    m.root.add(CadNode("assign", "w", dict(name="w", value=3)))
    for name in NAMES:
        comp = m.new_component(name, visible=False)
        m.add_node("cube", {}, parent=comp)
    return m


def _order(m):
    return [c.name for c in m.root.children if c.type == "component"]


def test_move_among_skips_what_is_not_an_object():
    m = _doc()
    five = next(c for c in m.root.children if c.name == "Exercise 5")
    assert wt.move_among(m, five, -1)
    assert _order(m) == ["Exercice 1", "Exercise 2", "Exercise 10",
                         "Exercise 5", "Exercise 6"]
    assert m.root.children[0].type == "assign"      # left where it was
    first = next(c for c in m.root.children if c.name == "Exercice 1")
    assert not wt.move_among(m, first, -1)          # already first


def test_sort_reads_numbers_as_numbers():
    m = _doc()
    assert wt.sort_among(m, m.root)
    assert _order(m) == ["Exercice 1", "Exercise 2", "Exercise 5",
                         "Exercise 6", "Exercise 10"]
    assert wt.sort_among(m, m.root, reverse=True)
    assert _order(m)[0] == "Exercise 10"
    assert m.root.children[0].type == "assign"


def test_one_undo_puts_the_order_back(app, monkeypatch):
    m = _doc()
    monkeypatch.setattr(DocumentModel, "UNDO_MERGE_S", 0)
    m._capture()
    before = _order(m)
    wt.sort_among(m, m.root)
    m._capture()
    m.undo_stack.undo()
    assert _order(m) == before


def _rows(tab):
    out = []
    for i in range(tab.tree.topLevelItemCount()):
        top = tab.tree.topLevelItem(i)
        for k in range(top.childCount()):
            out.append(top.child(k))
    return out


def test_the_tab_moves_and_sorts_its_rows(app):
    m = _doc()
    tab = wt.WorkTreeTab(m)
    tab.show()
    rows = _rows(tab)
    assert [r.text(0) for r in rows] == NAMES
    five = rows[-1]
    tab.tree.setCurrentItem(five)
    QTest.keyClick(tab.tree, Qt.Key_Up, Qt.ControlModifier)
    assert _order(m)[-2:] == ["Exercise 5", "Exercise 6"]
    assert tab.tree.currentItem().text(0) == "Exercise 5"   # still picked
    assert tab.sort_list(_rows(tab)[0])
    assert [r.text(0) for r in _rows(tab)] == [
        "Exercice 1", "Exercise 2", "Exercise 5", "Exercise 6",
        "Exercise 10"]
    tab.deleteLater()


def test_a_dropped_row_lands_before_its_target(app):
    m = _doc()
    tab = wt.WorkTreeTab(m)
    tab.resize(300, 400)
    tab.show()
    QTest.qWait(20)
    rows = _rows(tab)
    ten, two = rows[2], rows[1]
    tab.tree.setCurrentItem(ten)
    node = tab.place_of(ten)
    assert wt.place_by(m, node, tab.place_of(two))
    assert _order(m)[:3] == ["Exercice 1", "Exercise 10", "Exercise 2"]
    tab.deleteLater()


def test_the_object_dropdown_follows(app):
    from khervecad.objecttab import ObjectTab
    m = _doc()
    tab = ObjectTab(m)
    wt.sort_among(m, m.root, reverse=True)
    names = [tab.combo.itemText(i) for i in range(1, tab.combo.count())]
    assert names[0] == "Exercise 10" and names[-1] == "Exercice 1"
    tab.deleteLater()
