"""Tests for selection highlight across the 2D and 3D views.

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

from khervecad import library, mesh
from khervecad.model import CadNode, DocumentModel


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model(app):
    return DocumentModel()


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    return MainWindow()


# -------------------------------------------------- selected_world_tris

def test_selected_tris_of_leaf_in_transformed_part(model):
    # a cube offset by a translate: selecting the cube must return it
    # at its transformed (world) position, not at the origin.
    cube = model.add_node("cube", dict(width=4.0, depth=4.0,
                                       height=4.0))
    move = model.wrap_nodes([cube], "translate")
    move.params.update(x=100.0, y=0.0, z=0.0)
    tris = mesh.selected_world_tris(model.root, {cube.id})
    assert tris
    xs = [v[0] for t in tris for v in t]
    assert min(xs) == pytest.approx(100.0)
    assert max(xs) == pytest.approx(104.0)


def test_selected_tris_empty_when_nothing_selected(model):
    model.add_node("cube")
    assert mesh.selected_world_tris(model.root, set()) == []


def test_selecting_parent_includes_children(model):
    group = model.add_node("union")
    model.add_node("cube", dict(width=2.0, depth=2.0, height=2.0),
                   parent=group)
    model.add_node("sphere", dict(radius=1.0, segments=8),
                   parent=group)
    whole = mesh.tessellate(model.root)
    selected = mesh.selected_world_tris(model.root, {group.id})
    assert len(selected) == len(whole)          # everything under it


def test_selecting_one_child_marks_only_it(model):
    group = model.add_node("union")
    cube = model.add_node("cube", parent=group)
    model.add_node("sphere", dict(segments=8), parent=group)
    selected = mesh.selected_world_tris(model.root, {cube.id})
    assert len(selected) == 12                   # just the cube faces


def test_highlight_survives_boolean_first_operand(model):
    # a tube inside the kept body of a difference is still highlightable
    body = model.add_node("union")
    tube = library._cyl("Tube", 5.0, 20.0)
    body.add(tube)
    model.add_node("cylinder", dict(radius_bottom=2.0, radius_top=2.0),
                   parent=body)
    model.wrap_nodes([body], "difference")
    # subtract something
    model.root.children[0].add(
        CadNode("sphere", "cut", dict(radius=1.0, segments=6)))
    tris = mesh.selected_world_tris(model.root, {tube.id})
    assert tris                                   # tube is in operand 1


def test_selected_subtracted_tool_is_highlightable(model):
    # a tool removed by a difference (e.g. a bore) still yields its own
    # geometry when selected, so it can be shown in 2D and 3D
    body = model.add_node("cube", dict(width=10.0, depth=10.0,
                                       height=10.0))
    diff = model.wrap_nodes([body], "difference")
    tool = CadNode("cylinder", "Bore",
                   dict(radius_bottom=2.0, radius_top=2.0, height=20.0,
                        segments=8, z=-1.0))
    diff.add(tool)                                # subtracted operand
    assert mesh.selected_world_tris(model.root, {tool.id})  # was empty
    # the plain preview still approximates the difference as operand 1
    assert len(mesh.tessellate(model.root)) == 12          # just the cube


def test_selecting_bore_shows_it_in_both_views(window):
    m = window.model
    tee = library.build_part("cf_tee",
                             dict(library.CF_SIZES["CF40 (DN40)"],
                                  port_length=50.0))
    m.root.add(tee)
    m.structure_changed.emit()
    bore = next(n for n in tee.walk()
                if n.name == "Bore" and n.type == "cylinder")
    assert any(a.type == "difference" for a in _walk_ancestors(bore))
    window.builder.tree.select_nodes([bore])
    assert window.view3d.highlight_mesh           # 3D glow
    assert bore.id in window.scene._part_items     # 2D silhouette


def _walk_ancestors(node):
    probe = node.parent
    while probe is not None:
        yield probe
        probe = probe.parent


# ---------------------------------------------------------- view wiring

def test_window_highlights_selected_part_in_both_views(window):
    m = window.model
    part = library.build_part("cf_tee",
                              dict(library.CF_SIZES["CF63 (DN63)"],
                                   port_length=60.0))
    m.root.add(part)
    m.structure_changed.emit()
    tube = next(n for n in part.walk() if n.name == "Tube"
                and n.type == "cylinder")
    window.builder.tree.select_nodes([tube])
    # 3D: the selected object's faces are queued to glow
    assert window.view3d.highlight_mesh
    # 2D: the selected node is isolated as its own silhouette
    assert window.scene._highlight_ids == {tube.id}
    assert tube.id in window.scene._part_items


def test_isolate_shows_only_selected(window):
    """Selecting a 3D part hides every other object in the 2D view."""
    m = window.model
    a = library.build_part("cf_flange",
                           dict(library.CF_SIZES["CF40 (DN40)"]))
    b = library.build_part("cf_flange",
                           dict(library.CF_SIZES["CF63 (DN63)"]))
    m.root.add(a)
    m.root.add(b)
    m.structure_changed.emit()
    assert len(window.scene._part_items) == 2       # both outlines
    revolve = next(n for n in a.walk()
                   if n.type == "rotate_extrude")
    window.builder.tree.select_nodes([revolve])
    # only the selected object is shown now
    assert list(window.scene._part_items) == [revolve.id]
    assert window.scene._items == {}
    # deselect returns to the overview with both parts
    window.builder.tree.select_nodes([])
    assert len(window.scene._part_items) == 2


def test_selecting_profile_opens_it_for_editing(window):
    """Selecting a 2D profile shows that profile itself, editable, in
    the 2D view — not the revolved solid's silhouette — at any plane."""
    m = window.model
    cross = library.build_part("cf_cross",
                               dict(library.CF_SIZES["CF40 (DN40)"],
                                    port_length=50.0))
    m.root.add(cross)
    m.structure_changed.emit()
    window._set_plane("Front (XZ)")
    profile = next(n for n in cross.walk()
                   if n.name == "Flange -X profile")
    window.builder.tree.select_nodes([profile])
    # the profile is drawn as an editable sketch item, alone
    assert list(window.scene._items) == [profile.id]
    assert window.scene._part_items == {}
    assert window.scene.focus_shape_rect() is not None


def test_profile_edit_point_drag_updates_in_place(window):
    """Reshaping a profile from the 2D view writes back to its points
    and does not tear the item down mid-edit."""
    m = window.model
    cross = library.build_part("cf_cross",
                               dict(library.CF_SIZES["CF40 (DN40)"],
                                    port_length=50.0))
    m.root.add(cross)
    m.structure_changed.emit()
    profile = next(n for n in cross.walk()
                   if n.name == "Flange -X profile")
    window.builder.tree.select_nodes([profile])
    item = window.scene._items[profile.id]
    profile.params["points"][0] = [99.0, 42.0]
    m.node_changed.emit(profile)
    # same item object, updated in place (not rebuilt)
    assert window.scene._items[profile.id] is item
    assert profile.params["points"][0] == [99.0, 42.0]


def test_isolate_silhouette_movable_only_for_top_level(window):
    m = window.model
    part = library.build_part("cf_nipple",
                              dict(library.CF_SIZES["CF40 (DN40)"],
                                   port_length=40.0))
    m.root.add(part)
    m.structure_changed.emit()
    window.builder.tree.select_nodes([part])       # top-level
    assert window.scene._part_items[part.id]._movable
    deep = next(n for n in part.walk() if n.type == "rotate_extrude")
    window.builder.tree.select_nodes([deep])       # nested
    assert not window.scene._part_items[deep.id]._movable


def test_highlight_clears_on_empty_selection(window):
    m = window.model
    cube = m.add_node("cube")
    window.builder.tree.select_nodes([cube])
    assert window.view3d.highlight_mesh
    window.builder.tree.select_nodes([])
    assert window.view3d.highlight_mesh == []


def test_highlight_follows_plane_change(window):
    m = window.model
    part = library.build_part("cf_nipple",
                              dict(library.CF_SIZES["CF40 (DN40)"],
                                   port_length=40.0))
    m.root.add(part)
    m.structure_changed.emit()
    window.builder.tree.select_nodes([part])
    window._set_plane("Front (XZ)")
    assert window.scene.plane == "Front (XZ)"
    assert part.id in window.scene._part_items    # rebuilt for plane


# -------------------------------------------- isolation click behaviour

def _empty_viewport_px(view):
    """A viewport pixel that maps to empty scene space (no item)."""
    from PyQt5.QtCore import QPoint
    scene = view.scene()
    vp = view.viewport()
    for x in range(2, vp.width(), 7):
        for y in range(2, vp.height(), 7):
            p = QPoint(x, y)
            sp = view.mapToScene(p)
            if scene.itemAt(sp, view.transform()) is None:
                return p
    return None


def test_isolated_empty_click_keeps_selection(window):
    """While a part is isolated, clicking empty 2D space must NOT
    deselect it — deselection happens from the object tree only."""
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest
    m = window.model
    part = library.build_part("cf_tee",
                              dict(library.CF_SIZES["CF40 (DN40)"],
                                   port_length=50.0))
    m.root.add(part)
    m.structure_changed.emit()
    window._set_plane("Front (XZ)")
    profile = next(n for n in part.walk()
                   if n.name == "Flange -X profile")
    window.builder.tree.select_nodes([profile])
    assert window.scene._isolating()

    view = window.view2d
    view.resize(600, 400)
    view.show()
    view.fitInView(window.scene.itemsBoundingRect().adjusted(-20, -20,
                                                             20, 20),
                   Qt.KeepAspectRatio)
    empty = _empty_viewport_px(view)
    assert empty is not None

    QTest.mouseClick(view.viewport(), Qt.LeftButton, Qt.NoModifier, empty)
    # selection survives the empty click
    assert window.scene._isolating()
    assert window.scene._highlight_ids == {profile.id}
    assert [n.name for n in window.builder.tree.selected_nodes()] \
        == ["Flange -X profile"]
    # the tree still deselects it
    window.builder.tree.select_nodes([])
    assert not window.scene._isolating()


def test_empty_click_still_deselects_sketch_shape(window):
    """Outside isolation (a plain 2D sketch shape in Top view), an
    empty click clears the selection as before."""
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest
    m = window.model
    rect = m.add_node("rect", dict(x=5.0, y=5.0, width=10.0, height=8.0))
    window._set_plane("Top (XY)")
    window.builder.tree.select_nodes([rect])
    assert rect.id in {n.id for n in window.scene.selected_nodes()}

    view = window.view2d
    view.resize(600, 400)
    view.show()
    view.fitInView(window.scene.itemsBoundingRect().adjusted(-40, -40,
                                                             40, 40),
                   Qt.KeepAspectRatio)
    empty = _empty_viewport_px(view)
    assert empty is not None
    QTest.mouseClick(view.viewport(), Qt.LeftButton, Qt.NoModifier, empty)
    assert window.scene.selected_nodes() == []
