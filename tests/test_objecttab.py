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


def test_object_contents_not_greyed_when_definition_hidden(model, app):
    """An Object is hidden in Main (it is a definition), but editing it
    in the Object tab must show its contents at full strength — not
    greyed as if hidden."""
    panel = BuilderPanel(model)
    comp = model.new_component("Spacer", visible=False)
    body = model.add_node("union", parent=comp, name="Body")
    inner = model.add_node("cylinder", parent=body)
    panel.open_component(comp)
    tree = panel.object_tab.tree
    assert not tree._item_of(body).font(0).italic()
    assert not tree._item_of(inner).font(0).italic()
    # a genuinely hidden child inside the Object still greys, though
    model.set_visible(body, False)
    assert tree._item_of(body).font(0).italic()


def test_instance_is_one_opaque_row_in_main(model, app):
    """Inserting an Object shows a single row in Main; its construction
    tree is not exposed there (that lives in the Object tab)."""
    panel = BuilderPanel(model)
    comp = model.new_component("Widget", visible=False)
    g = model.add_node("union", parent=comp, name="Sub")
    model.add_node("cube", parent=g)
    inst = model.add_instance(comp)
    row = panel.tree._item_of(inst)
    assert row is not None
    assert row.childCount() == 0


def test_visible_component_is_opaque_in_main(model, app):
    """A visible top-level Object (an imported mesh, an old-style part)
    also shows as one row in Main — you see the part, not its
    features."""
    panel = BuilderPanel(model)
    comp = model.new_component("Imported", visible=True)
    model.add_node("cube", parent=comp)
    row = panel.tree._item_of(comp)
    assert row.childCount() == 0


def test_isolated_object_ignores_main_placement(model, app):
    """An Object mated in Main carries a placement on its own params.
    Editing it in the Object tab must show it at its LOCAL origin —
    the assembly placement (and the hidden-in-Main flag) do not apply
    to the definition's own editing view."""
    comp = model.new_component("Spacer", visible=False)
    tr = model.add_node("translate", dict(z=-10.0), parent=comp)
    model.add_node("cube", dict(width=20.0, depth=20.0, height=10.0),
                   parent=tr)
    # a Main-tab mate left this placement on the component
    comp.params.update(x=5.0, z=73.7, rx=180.0)

    code = model.subtree_scad(comp)
    call = [l for l in code.splitlines()
            if "Spacer()" in l and "module" not in l][-1]
    assert "translate" not in call        # no assembly placement
    assert "rotate" not in call
    assert not call.strip().startswith("*")   # not disabled
    # the real placement is untouched (Main still needs it)
    assert comp.params["z"] == 73.7
    assert comp.params["rx"] == 180.0


def test_isolated_frame_zeroes_placement_and_restores(model, app):
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    comp = w.model.new_component("Part", visible=False)
    w.model.add_node("cube", parent=comp)
    comp.params.update(x=3.0, z=50.0, ry=90.0)
    with w._isolated_frame(comp):
        assert comp.params["x"] == 0.0
        assert comp.params["z"] == 0.0
        assert comp.params["ry"] == 0.0
        assert comp.visible is True
    assert comp.params["x"] == 3.0
    assert comp.params["z"] == 50.0
    assert comp.params["ry"] == 90.0
    assert comp.visible is False


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
    panel.open_component(comp)              # Object tab current
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
    panel.open_component(comp)              # Object tab + object scope
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


def test_new_object_hidden_in_main_by_default(model, app):
    """UI-created Objects start hidden in the Main assembly; the model
    API default stays visible (imports, scripts)."""
    tab = ObjectTab(model)
    comp = tab.new_object()
    assert comp.visible is False
    assert model.new_component("api").visible is True


def test_hidden_object_still_renders_isolated(model):
    """Main-tab visibility and the Object view are independent: a
    hidden Object still has code (unstarred), a mesh in its local
    frame, and anchors."""
    from khervecad import anchors, mesh
    comp = model.new_component("Ghost", visible=False)
    model.add_node("cube", parent=comp)
    # assembly code keeps the * (hidden in Main and in exports)
    assert "*Ghost();" in model.to_scad()
    # the isolated render drops it
    iso = model.subtree_scad(comp)
    assert "*Ghost();" not in iso
    assert "Ghost();" in iso
    assert comp.visible is False            # flag restored
    # anchors still exist (bbox from the forced-visible local mesh)
    items = anchors.auto_anchors(comp)
    assert any(a["kind"] == "face" for a in items)
    # while the plain assembly tessellation skips it
    assert mesh.tessellate(model.root) == []


def test_code_scope_follows_last_tree_tab(model, app):
    panel = BuilderPanel(model)
    comp = model.new_component("Solo")
    model.add_node("cube", parent=comp)
    model.new_component("Noise")
    panel.open_component(comp)              # Object tab current
    assert panel.code_scope.currentIndex() == 1
    panel.setCurrentWidget(panel._main_page)
    assert panel.code_scope.currentIndex() == 0
    assert "Noise" in panel.code.toPlainText()
    panel.setCurrentWidget(panel.object_tab)
    assert panel.code_scope.currentIndex() == 1
    assert "Noise" not in panel.code.toPlainText()


# ------------------------------- commands act on the tree in front

def _window_editing_an_object(app):
    """A MainWindow with the Object tab open on a two-solid Object."""
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    m = w.model
    comp = m.new_component("Block", visible=False)
    body = m.add_node("cube", dict(width=20.0, depth=20.0, height=20.0),
                      parent=comp, name="Body")
    hole = m.add_node("cylinder", dict(radius=4.0, height=30.0),
                      parent=comp, name="Hole")
    w.builder.open_component(comp)
    return w, comp, body, hole


def test_difference_applies_inside_the_object_tab(app):
    """Operations read the tree the user is working in. They used to
    read the Main tree unconditionally, which is empty while the Object
    tab is up — so clicking Difference in an Object did nothing."""
    w, comp, body, hole = _window_editing_an_object(app)
    w.builder.object_tab.tree.select_nodes([body, hole])
    w._apply_operation("difference")

    assert [c.type for c in comp.children] == ["difference"]
    diff = comp.children[0]
    assert [c.name for c in diff.children] == ["Body", "Hole"]
    # and the new wrapper is selected in the Object tab, not in Main
    assert w.builder.object_tab.tree.selected_nodes() == [diff]


def test_delete_and_duplicate_follow_the_object_tab(app):
    w, comp, body, hole = _window_editing_an_object(app)
    w.builder.object_tab.tree.select_nodes([hole])
    w._duplicate_selection()
    assert len(comp.children) == 3

    w.builder.object_tab.tree.select_nodes([hole])
    w._delete_selection()
    assert hole not in comp.children
    assert body in comp.children             # only the selection went


def test_operations_still_apply_in_main(app):
    """The Main tab keeps working exactly as before."""
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    m = w.model
    a = m.new_component("A")
    m.add_node("cube", parent=a)
    b = m.new_component("B")
    m.add_node("sphere", parent=b)
    w.builder.setCurrentWidget(w.builder._main_page)
    w.builder.tree.select_nodes([a, b])
    w._apply_operation("union")
    assert [c.type for c in m.root.children] == ["union"]
