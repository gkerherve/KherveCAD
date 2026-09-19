"""Collections (Blender's outliner collections): sets of parts shown,
hidden and locked together, and the Collections tab.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication, QGraphicsItem

from khervecad import document, mesh
from khervecad import part_collections as pc
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model(app):
    return DocumentModel()


def _two_parts(model):
    a = model.add_node("cube")
    b = model.add_node("sphere")
    return a, b


def test_create_assign_and_read(model):
    a, b = _two_parts(model)
    name = pc.create(model, "Walls", [a])
    assert name == "Walls"
    assert pc.of(a) == "Walls" and pc.of(b) == ""
    assert pc.members(model, "Walls") == [a]
    assert pc.create(model, "Walls") == "Walls 2"      # unique names
    pc.assign(model, [b], "Roof")                        # made on demand
    assert pc.names(model) == ["Walls", "Walls 2", "Roof"]
    assert pc.summary(model)[2]["members"][0]["id"] == b.id


def test_a_part_belongs_to_one_collection_with_its_insides(model):
    group = model.add_node("union")
    inner = model.add_node("cube", parent=group)
    pc.assign(model, [inner], "A")
    pc.assign(model, [group], "B")
    assert pc.own(inner) == ""                           # absorbed
    assert pc.of(inner) == "B"


def test_hiding_is_a_view_setting_not_a_document_change(model):
    a, b = _two_parts(model)
    pc.create(model, "Hidden", [a])
    whole = len(mesh.tessellate(model.root))
    code = model.to_scad()
    pc.set_visible(model, "Hidden", False)
    with pc.hiding(model):
        shown = len(mesh.tessellate(model.root))
    assert shown == len(mesh.tessellate(b))
    assert shown < whole
    assert a.visible                                     # restored
    assert model.to_scad() == code                       # exports keep it
    assert validate(model.root) == {}                    # not an expression


def test_rename_delete_and_solo(model):
    a, b = _two_parts(model)
    pc.create(model, "One", [a])
    pc.create(model, "Two", [b])
    pc.rename(model, "One", "First")
    assert pc.of(a) == "First"
    with pytest.raises(pc.CollectionError):
        pc.rename(model, "First", "Two")
    pc.solo(model, "Two")
    assert pc.hidden_names(model) == {"First"}
    pc.solo(model, "Two")                                # again: all back
    assert pc.hidden_names(model) == set()
    pc.remove(model, "First")
    assert pc.of(a) == "" and pc.names(model) == ["Two"]


def test_collections_are_saved_and_undone(model, app):
    a, _b = _two_parts(model)
    pc.create(model, "Kept", [a])
    pc.set_locked(model, "Kept", True)
    fd, path = tempfile.mkstemp(suffix=".kcad")
    os.close(fd)
    try:
        document.save_kcad(model, path)
        other = DocumentModel()
        document.load_kcad(other, path)
    finally:
        os.remove(path)
    assert other.collections == [{"name": "Kept", "visible": True,
                                  "locked": True}]
    assert pc.members(other, "Kept")[0].name == a.name
    # undo: a snapshot per change
    app.processEvents()
    pc.set_visible(model, "Kept", False)
    app.processEvents()
    model.undo_stack.undo()
    assert pc.hidden_names(model) == set()


def test_window_hides_the_part_and_locks_it_in_2d(app):
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    a = w.model.add_node("cube")
    b = w.model.add_node("sphere")
    b.params["x"] = 40.0
    app.processEvents()
    w._refresh_preview()
    whole = len(w.view3d.model_mesh or w.view3d.mesh)
    pc.create(w.model, "Box", [a])
    pc.set_visible(w.model, "Box", False)
    w._refresh_preview()
    assert len(w.view3d.model_mesh or w.view3d.mesh) < whole
    assert a.visible
    pc.set_visible(w.model, "Box", True)
    pc.set_locked(w.model, "Box", True)
    w.scene.rebuild()
    items = [i for i in list(w.scene._items.values())
             + list(w.scene._part_items.values())
             if getattr(i, "node", None) is a]
    assert items
    assert all(not (i.flags() & QGraphicsItem.ItemIsMovable)
               for i in items)


def test_the_tab_lists_collections_and_loose_parts(app):
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    a = w.model.add_node("cube")
    w.model.add_node("sphere")
    panel = w.builder.collections
    pc.create(w.model, "Walls", [a])
    top = [panel.tree.topLevelItem(i).text(0)
           for i in range(panel.tree.topLevelItemCount())]
    assert top == ["Walls", "Not in a collection"]
    walls = panel.tree.topLevelItem(0)
    assert walls.child(0).text(0) == a.name
    # the eye column hides it
    panel._clicked(panel.tree.topLevelItem(0), 1)
    assert pc.hidden_names(w.model) == {"Walls"}
    # picking a part here selects it in Main
    panel.tree.topLevelItem(0).child(0).setSelected(True)
    assert w.builder.tree.selected_nodes() == [a]


def test_the_mcp_tool_drives_collections(app):
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    w = MainWindow()
    ex = McpToolExecutor(w)
    a = w.model.add_node("cube")
    out = ex.execute("collections", {"action": "create", "name": "Roof",
                                     "ids": [a.id]})
    assert out["collections"][0]["members"][0]["id"] == a.id
    ex.execute("collections", {"action": "hide", "name": "Roof"})
    info = ex.execute("get_document_info", {})
    assert info["collections"] == [{"name": "Roof", "visible": False,
                                    "locked": False}]
    bad = ex.execute("collections", {"action": "hide", "name": "Nope"})
    assert "error" in bad
