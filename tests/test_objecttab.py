"""Tests for the Object tab: active-Object tracking, the scoped tree,
scoped variables, scoped code and subtree codegen.

Run with: python -m pytest tests/  (offscreen Qt).

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
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad.model import CadNode, DocumentModel
from khervecad.objecttab import ObjectTab
from khervecad.treepanel import BuilderPanel


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model(app):
    return DocumentModel()


def test_subtree_scad_includes_globals(model):
    model.add_node("assign", dict(variable="size", value="20"))
    comp = model.new_component("Plate")
    model.add_node("cube", dict(width="size"), parent=comp)
    code = model.subtree_scad(comp)
    assert "size = 20;" in code
    assert "module Plate() {" in code
    assert "Plate();" in code
    # the other document content is not included
    other = model.new_component("Other")
    model.add_node("sphere", parent=other)
    code = model.subtree_scad(comp)
    assert "Other" not in code


def test_object_tab_tracks_active(model):
    tab = ObjectTab(model)
    assert tab.active_component() is None
    a = model.new_component("First")
    b = model.new_component("Second")
    tab.set_active(a)
    assert tab.active_component() is a
    # the scoped tree lists only the active Object's contents
    model.add_node("cube", parent=a)
    model.add_node("sphere", parent=b)
    assert [n.type for n in tab.tree._top_nodes()] == ["cube"]
    # rename survives (tracked by id)
    model.rename(a, "Renamed")
    assert tab.active_component() is a
    # deleting the active Object falls back to none
    model.remove_node(a)
    assert tab.active_component() is None


def test_object_tab_survives_undo_restore(model):
    """Undo restores rebuild the tree with fresh node ids — the active
    Object re-resolves by name."""
    tab = ObjectTab(model)
    comp = model.new_component("Keeper")
    tab.set_active(comp)
    state = model._serialize()
    model.restore_state(state)              # fresh CadNode ids
    active = tab.active_component()
    assert active is not None
    assert active.name == "Keeper"
    assert active is not comp


def test_variables_sheet_scopes(model, app):
    panel = BuilderPanel(model)
    model.add_node("assign", dict(variable="global_w", value="100"))
    comp = model.new_component("Widget")
    model.add_node("assign", dict(variable="local_h", value="5"),
                   parent=comp)
    sheet = panel.variables
    # global scope hides the Object's variables
    sheet.set_scope(None)
    names = {n.params["variable"] for n in sheet._assigns()}
    assert names == {"global_w"}
    # object scope shows only its own
    sheet.set_scope(comp)
    names = {n.params["variable"] for n in sheet._assigns()}
    assert names == {"local_h"}


def test_code_scope_follows_active(model, app):
    panel = BuilderPanel(model)
    comp = model.new_component("Solo")
    model.add_node("cube", parent=comp)
    model.new_component("Noise")
    panel.object_tab.set_active(comp)
    assert panel.code_scope.currentIndex() == 1
    code = panel.code.toPlainText()
    assert "module Solo() {" in code
    assert "Noise" not in code
    # releasing the active object falls back to the whole program
    panel.object_tab.set_active(None)
    assert panel.code_scope.currentIndex() == 0
    assert "Noise" in panel.code.toPlainText()


def test_apply_code_object_scope(model, app):
    panel = BuilderPanel(model)
    comp = model.new_component("Editable")
    model.add_node("cube", parent=comp)
    other = model.new_component("Untouched")
    model.add_node("sphere", parent=other)
    panel.object_tab.set_active(comp)
    panel.code.setPlainText(
        "module Editable() {\n"
        "    cylinder(h=30, r1=5, r2=5, $fn=32, center=false);\n"
        "}\n"
        "translate([1, 2, 3]) Editable();\n")
    panel._apply_code()
    comps = model.components()
    assert [c.name for c in comps] == ["Editable", "Untouched"]
    new = comps[0]
    assert new.children[0].type == "cylinder"
    assert new.params["x"] == 1.0
    assert new.params["z"] == 3.0
    # the other Object was not touched
    assert comps[1].children[0].type == "sphere"
    # and the swapped Object is still the active one
    assert panel.object_tab.active_component() is new


def test_isolated_component_requires_object_tab(model, app):
    panel = BuilderPanel(model)
    comp = model.new_component("Iso")
    panel.object_tab.set_active(comp)
    panel.setCurrentIndex(0)                # Main tab
    assert panel.isolated_component() is None
    panel.setCurrentWidget(panel.object_tab)
    assert panel.isolated_component() is comp
