"""The Object tab's icon toolbar (New, Rename, Delete, To Main), nested
Objects in its list, and the Insert menu listing every toolbar tool.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")

from PyQt5.QtWidgets import QApplication

from khervecad import scadparse
from khervecad.model import DocumentModel
from khervecad.objecttab import BUTTONS, ObjectTab


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_toolbar_is_icons_only_in_order(app):
    tab = ObjectTab(DocumentModel())
    buttons = [getattr(tab, attr) for attr, _g, _t in BUTTONS]
    assert [attr for attr, _g, _t in BUTTONS] == \
        ["new_btn", "rename_btn", "delete_btn", "insert_btn"]
    try:
        import qtawesome  # noqa: F401  (icons need it; tests may not)
        drawn = True
    except ImportError:
        drawn = False
    for button in buttons:
        assert button.text() == ""                 # no text on the bar
        assert button.toolTip()
        if drawn:
            assert not button.icon().isNull()
    assert "delete" in BUTTONS[2][1]               # the bin icon


def test_modules_placed_inside_a_colour_are_listed(app):
    """An imported program's modules (`color(...) Pot();`) are Objects
    even when a colour wraps their placed call."""
    m = DocumentModel()
    root, _w = scadparse.parse_scad(
        "module gem_pot() { cube(10); }\n"
        "module rose_pot() { sphere(5); }\n"
        'color("red") gem_pot();\n'
        'color("blue") translate([30, 0, 0]) rose_pot();\n')
    m.root = root
    tab = ObjectTab(m)
    names = [tab.combo.itemText(i) for i in range(tab.combo.count())]
    assert "gem_pot" in names and "rose_pot" in names
    assert {c.name for c in m.all_components()} >= {"gem_pot", "rose_pot"}
    assert m.components() == [c for c in m.root.children
                               if c.type == "component"]   # unchanged


def test_delete_removes_the_object_and_its_instances(app):
    m = DocumentModel()
    tab = ObjectTab(m)
    comp = m.new_component("Bracket")
    m.add_node("cube", parent=comp)
    m.add_instance(comp)
    m.add_instance(comp)
    keep = m.new_component("Other")
    tab.set_active(comp)
    assert tab.delete_btn.isEnabled()
    assert tab.delete_active(confirm=False)
    left = {n.name for n in m.root.walk()}
    assert "Bracket" not in left and keep.name in left
    assert not any(n.type == "reference" for n in m.root.walk())
    assert tab.active_component() is None
    assert not tab.delete_btn.isEnabled()          # nothing left to delete


def test_delete_is_one_undo_step(app):
    m = DocumentModel()
    m.UNDO_MERGE_S = 0.0         # a person's clicks are never 0.4 s apart
    tab = ObjectTab(m)
    comp = m.new_component("Bracket")
    m.add_node("cube", parent=comp)
    m.add_instance(comp)
    QApplication.processEvents()
    tab.set_active(comp)
    tab.delete_active(confirm=False)
    QApplication.processEvents()
    m.undo_stack.undo()
    QApplication.processEvents()
    names = [n.name for n in m.root.walk()]
    assert "Bracket" in names
    assert any(n.type == "reference" for n in m.root.walk())


def _actions(menu):
    out = []
    for act in menu.actions():
        if act.menu() is not None:
            out += _actions(act.menu())
        elif act.data() is not None:
            out.append(act.data())
    return out


def test_insert_menu_lists_every_toolbar_tool(app):
    from khervecad.mainwindow import MainWindow
    from khervecad.toolbars import (MEASURE_TOOLS, OPERATIONS, PRIMITIVES,
                                    TOOLS)
    w = MainWindow()
    insert = next(a.menu() for a in w.menuBar().actions()
                  if a.text().replace("&", "") == "Insert")
    keys = set(_actions(insert))
    wanted = ({t for t, *_rest in TOOLS[1:]} | {t for t, *_r in MEASURE_TOOLS}
              | set(PRIMITIVES) | set(OPERATIONS)
              | {"snap_objects", "assign", "stl_import", "scad_raw"})
    assert wanted <= keys, wanted - keys
    subs = [a.text().replace("&&", "\x00").replace("&", "")
            .replace("\x00", "&") for a in insert.actions() if a.menu()]
    assert "2D Shapes" in subs and "3D Solids" in subs
    assert "Extrude" in subs and "Repeat & logic" in subs
