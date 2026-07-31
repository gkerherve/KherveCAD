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


def test_primitive_dimension_handles_edit_params(window):
    """A 3D primitive selected in the 2D view gets drag handles that
    change its size, mapped through ancestor transforms."""
    from PyQt5.QtCore import QPointF
    m = window.model
    cyl = m.add_node("cylinder", dict(radius_bottom=5.0, radius_top=5.0,
                                      height=20.0, segments=12))
    rot = m.wrap_nodes([cyl], "rotate")           # tilt the local frame
    rot.params.update(x=0.0, y=90.0, z=0.0)
    window._set_plane("Front (XZ)")
    window.builder.tree.select_nodes([cyl])
    item = window.scene._part_items[cyl.id]
    roles = {d["role"] for d in item._dims}
    assert {"radius_bottom", "radius_top", "height"} <= roles

    rb = next(d for d in item._dims if d["role"] == "radius_bottom")
    ax, ay = rb["axis"]
    grab = rb["tip"]                               # grab the handle
    item.handle_pressed("radius_bottom", grab)
    # drag 7 mm further out along the axis -> radius grows by 7
    item.handle_dragged("radius_bottom",
                        QPointF(grab.x() + ax * 7, grab.y() + ay * 7))
    assert abs(cyl.params["radius_bottom"] - 12.0) < 0.01
    assert cyl.params["radius_top"] == 5.0         # only bottom changed
    # off-axis wobble must not move the value
    item.handle_pressed("radius_bottom", grab)
    item.handle_dragged("radius_bottom",
                        QPointF(grab.x() - ay * 25, grab.y() + ax * 25))
    assert abs(cyl.params["radius_bottom"] - 5.0) < 0.01  # no along-axis


class _SceneEvt:
    """Minimal stand-in for a QGraphicsSceneMouseEvent carrying just a
    scene position — enough to drive HandleItem's drag handlers."""

    def __init__(self, scene_pos):
        self._sp = scene_pos

    def scenePos(self):
        return self._sp

    def accept(self):
        pass


def test_dimension_handle_drag_smooth_through_real_handlers(window):
    """Driving HandleItem's actual press/move handlers (which read
    event.scenePos) must change the radius smoothly and reject
    perpendicular cursor wobble — the erratic-drag regression guard."""
    import math

    from PyQt5.QtCore import QPointF
    m = window.model
    part = library.build_part("cf_nipple",
                              dict(library.CF_SIZES["CF40 (DN40)"],
                                   port_length=50.0))
    m.root.add(part)
    m.structure_changed.emit()
    window._set_plane("Front (XZ)")
    tube = next(n for n in part.walk()
                if n.name == "Tube" and n.type == "cylinder")
    window.builder.tree.select_nodes([tube])
    window.scene.snap_enabled = False             # test continuous drag
    item = window.scene._part_items[tube.id]

    spec = next(d for d in item._dims if d["role"] == "radius_bottom")
    handle = next(h for h in item.handles
                  if h.role == "radius_bottom")
    ax, ay = spec["axis"]
    perp = (-ay, ax)
    start = tube.params["radius_bottom"]
    grab = QPointF(handle.pos())
    handle.mousePressEvent(_SceneEvt(grab))
    values = []
    for i in range(1, 9):
        travel = 12.0 * i / 8.0
        noise = 9.0 * math.sin(i * 1.7)           # heavy off-axis wobble
        sp = QPointF(grab.x() + ax * travel + perp[0] * noise,
                     grab.y() + ay * travel + perp[1] * noise)
        handle.mouseMoveEvent(_SceneEvt(sp))
        values.append(tube.params["radius_bottom"])
    # monotonic (no jitter) and lands where the along-axis travel says
    assert all(b >= a - 1e-6 for a, b in zip(values, values[1:]))
    assert abs(values[-1] - (start + 12.0)) < 0.05
    assert tube.params["radius_top"] == start     # untouched


def test_dimension_handle_snaps_radius_to_grid(window):
    """With grid snap on, a radius drag lands on grid multiples; off,
    it is continuous."""
    from PyQt5.QtCore import QPointF
    m = window.model
    part = library.build_part("cf_nipple",
                              dict(library.CF_SIZES["CF40 (DN40)"],
                                   port_length=50.0))
    m.root.add(part)
    m.structure_changed.emit()
    window._set_plane("Front (XZ)")
    tube = next(n for n in part.walk()
                if n.name == "Tube" and n.type == "cylinder")
    window.builder.tree.select_nodes([tube])
    item = window.scene._part_items[tube.id]
    spec = next(d for d in item._dims if d["role"] == "radius_bottom")
    handle = next(h for h in item.handles if h.role == "radius_bottom")
    ax, ay = spec["axis"]
    grab = QPointF(handle.pos())

    window.scene.snap_enabled = True
    window.scene.grid_size = 5.0
    handle.mousePressEvent(_SceneEvt(grab))
    handle.mouseMoveEvent(_SceneEvt(
        QPointF(grab.x() + ax * 13.2, grab.y() + ay * 13.2)))
    assert tube.params["radius_bottom"] % 5.0 == 0.0   # snapped to grid

    window.scene.snap_enabled = False
    handle.mousePressEvent(_SceneEvt(grab))
    handle.mouseMoveEvent(_SceneEvt(
        QPointF(grab.x() + ax * 13.2, grab.y() + ay * 13.2)))
    assert tube.params["radius_bottom"] % 5.0 != 0.0   # continuous


def test_cube_and_sphere_have_size_handles(window):
    m = window.model
    cube = m.add_node("cube", dict(width=10.0, depth=10.0, height=10.0))
    window._set_plane("Top (XY)")
    window.builder.tree.select_nodes([cube])
    roles = {d["role"] for d in window.scene._part_items[cube.id]._dims}
    assert {"width", "depth"} <= roles            # height is edge-on
    assert "height" not in roles

    m2 = window.model
    sph = m2.add_node("sphere", dict(radius=6.0, segments=12))
    window.builder.tree.select_nodes([sph])
    dims = window.scene._part_items[sph.id]._dims
    assert [d["role"] for d in dims] == ["radius"]


def test_isolated_bounds_frames_selected_part(window):
    """Selecting a part yields a scene rect the 2D view zooms to; with
    nothing selected the whole assembly is shown and there is none."""
    m = window.model
    part = library.build_part("cf_nipple",
                              dict(library.CF_SIZES["CF40 (DN40)"],
                                   port_length=40.0))
    m.root.add(part)
    m.structure_changed.emit()
    window.builder.tree.select_nodes([part])
    rect = window.scene.isolated_bounds()
    assert rect is not None
    assert rect.width() > 0 and rect.height() > 0
    window.builder.tree.select_nodes([])
    assert window.scene.isolated_bounds() is None


def test_revolve_part_has_no_size_handles(window):
    m = window.model
    part = library.build_part("cf_flange",
                              dict(library.CF_SIZES["CF40 (DN40)"]))
    m.root.add(part)
    m.structure_changed.emit()
    revolve = next(n for n in part.walk()
                   if n.type == "rotate_extrude")
    window.builder.tree.select_nodes([revolve])
    assert window.scene._part_items[revolve.id]._dims == []


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


def test_part_outline_is_the_real_shape_not_a_hull(window):
    """The assembly outline must look like the 3D part: a cross tube
    reads as a cross, not as the octagon its convex hull would give.
    The corner between two arms is empty in the projection, so it must
    fall outside the outline."""
    from PyQt5.QtCore import QPointF
    m = window.model
    cross = m.new_component("Cross")
    m.add_node("cube", dict(width=80.0, depth=10.0, height=10.0,
                            x=-40.0, y=-5.0, z=-5.0), parent=cross)
    m.add_node("cube", dict(width=10.0, depth=10.0, height=80.0,
                            x=-5.0, y=-5.0, z=-40.0), parent=cross)
    m.structure_changed.emit()
    window._set_plane("Front (XZ)")
    item = window.scene._part_items[cross.id]
    path = item.path()
    assert path.contains(QPointF(0.0, 0.0))         # the hub
    assert path.contains(QPointF(30.0, 0.0))        # the horizontal arm
    assert path.contains(QPointF(0.0, 30.0))        # the vertical arm
    # the notch between two arms: inside the hull, outside the cross
    assert not path.contains(QPointF(30.0, 30.0))


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


# --------------------------------------------- polygon point highlight

def test_selecting_point_row_highlights_vertex_red(window):
    m = window.model
    part = library.build_part("cf_nipple",
                              dict(library.CF_SIZES["CF40 (DN40)"],
                                   port_length=50.0))
    m.root.add(part)
    m.structure_changed.emit()
    window._set_plane("Front (XZ)")
    profile = next(n for n in part.walk()
                   if n.name == "Flange -Z profile")
    window.builder.tree.select_nodes([profile])
    window.properties.set_node(profile)
    item = window.scene._items[profile.id]

    editor = window.properties._editors["points"]
    editor.table.setCurrentCell(4, 0)             # pick vertex 4
    assert item._hot_vertex == 4
    reds = [h.role for h in item.handles
            if h.brush().color().name() == "#e53935"]
    assert reds == ["v4"]

    editor.table.setCurrentCell(1, 0)             # move to vertex 1
    reds = [h.role for h in item.handles
            if h.brush().color().name() == "#e53935"]
    assert reds == ["v1"]


def test_points_table_sizes_to_rows_up_to_15(app):
    from khervecad.properties import PointsEditor
    small = PointsEditor([[0, 0], [1, 0], [1, 1], [0, 1]], lambda p: None)
    big = PointsEditor([[i, i] for i in range(30)], lambda p: None)
    header = small.table.horizontalHeader().sizeHint().height()
    r = PointsEditor._ROW_H
    assert small.table.height() == header + 4 * r + 6      # all 4 rows
    assert big.table.height() == header + 15 * r + 6       # capped at 15


def test_selecting_whole_difference_omits_subtracted_tools(model):
    body = model.add_node("cube", dict(width=20.0, depth=20.0,
                                       height=20.0))
    diff = model.wrap_nodes([body], "difference")
    tool = model.add_node("cylinder",
                          dict(radius_bottom=3.0, radius_top=3.0,
                               height=30.0, segments=8), parent=diff)
    # selecting the whole difference highlights only the kept body,
    # never the removed tool drawn as solid
    assert len(mesh.selected_world_tris(model.root, {diff.id})) == \
        len(mesh.tessellate(body))
    # but selecting the tool alone still shows it
    assert mesh.selected_world_tris(model.root, {tool.id})


def test_dragging_group_edits_own_position(window):
    from PyQt5.QtCore import QPointF
    m = window.model
    grp = m.add_node("union")
    m.add_node("cube", parent=grp)
    m.structure_changed.emit()
    window._set_plane("Top (XY)")
    window.scene.commit_part_move(grp, QPointF(30.0, 20.0))
    assert [c.type for c in m.root.children] == ["union"]   # no wrapper
    assert grp.params["x"] == 30.0 and grp.params["y"] == 20.0


# ------------------------------------------- dragging a selected Move

def test_selected_translate_is_draggable_at_any_depth(window):
    """Highlight a Move inside a part and you can drag it in the 2D
    view — it used to be movable only at the top level, so a nested
    Move showed a silhouette that refused to budge."""
    from PyQt5.QtCore import QPointF
    m = window.model
    comp = m.new_component("Part", visible=False)
    move = m.add_node("translate", dict(x=0.0, y=0.0, z=0.0),
                      parent=comp, name="Move")
    m.add_node("cube", dict(width=10.0, depth=10.0, height=10.0),
               parent=move)
    m.structure_changed.emit()
    window.builder.open_component(comp)          # edit it in the Object tab
    window._set_plane("Front (XZ)")
    window.builder.object_tab.tree.select_nodes([move])

    item = window.scene._part_items[move.id]
    assert item._movable
    window.scene.commit_part_move(move, QPointF(12.0, -4.0))
    assert move.params["x"] == 12.0
    assert move.params["z"] == -4.0


def test_drag_writes_into_the_nodes_own_frame(window):
    """The drag is world mm, but a Move writes in its parent's frame.
    Under a 90° rotation about X the local +Y axis points along world
    +Z, so dragging up the screen must land in y — writing it to z
    would send the part off in the wrong direction entirely."""
    from PyQt5.QtCore import QPointF
    m = window.model
    comp = m.new_component("Part")            # visible: world tris below
    rot = m.add_node("rotate", dict(x=90.0, y=0.0, z=0.0), parent=comp,
                     name="Tilt")
    move = m.add_node("translate", dict(x=0.0, y=0.0, z=0.0),
                      parent=rot, name="Move")
    m.add_node("cube", dict(width=10.0, depth=10.0, height=10.0),
               parent=move)
    m.structure_changed.emit()
    window.builder.open_component(comp)
    window._set_plane("Front (XZ)")
    window.builder.object_tab.tree.select_nodes([move])
    assert window.scene._part_items[move.id]._movable

    window.scene.commit_part_move(move, QPointF(0.0, 10.0))
    assert move.params["x"] == 0.0
    assert move.params["y"] == pytest.approx(10.0, abs=1e-3)
    assert move.params["z"] == pytest.approx(0.0, abs=1e-3)
    # and the geometry really did land 10 mm up the screen: the cube
    # spanned world z 0..10 before the drag
    tris = mesh.selected_world_tris(comp, {move.id})
    assert max(v[2] for t in tris for v in t) == pytest.approx(20.0,
                                                               abs=1e-3)


def test_top_level_drag_still_wraps_in_a_translate(window):
    """A part with nowhere to put the move still gets one wrapped
    round it — the long-standing assembly-view behaviour."""
    from PyQt5.QtCore import QPointF
    m = window.model
    cube = m.add_node("cube", dict(width=10.0, depth=10.0, height=10.0))
    m.structure_changed.emit()
    window._set_plane("Front (XZ)")
    window.scene.commit_part_move(cube, QPointF(5.0, 7.0))
    assert cube.parent.type == "translate"
    assert cube.parent.params["x"] == 5.0
    assert cube.parent.params["z"] == 7.0


def test_drop_is_committed_after_the_event_not_during_it(window):
    """Committing a drag rebuilds the scene, which deletes the item Qt
    is still delivering the release to — that took the whole process
    down (0xC0000409). The commit must land on the next event-loop
    turn instead, once the item is no longer the mouse grabber."""
    from PyQt5.QtCore import QPointF
    from PyQt5.QtWidgets import QApplication
    m = window.model
    comp = m.new_component("Part", visible=False)
    move = m.add_node("translate", dict(x=0.0, y=0.0, z=0.0),
                      parent=comp, name="Move")
    m.add_node("cube", dict(width=20.0, depth=20.0, height=20.0),
               parent=move)
    m.structure_changed.emit()
    window.builder.open_component(comp)
    window._set_plane("Front (XZ)")
    window.builder.object_tab.tree.select_nodes([move])

    item = window.scene._part_items[move.id]
    item.setPos(QPointF(30.0, -15.0))            # the drag
    item.queue_commit()                          # what the release does

    # nothing has touched the model yet: the item is still alive and
    # still the one Qt is delivering the release to
    assert move.params["x"] == 0.0
    assert item.scene() is window.scene
    QApplication.processEvents()                 # ...and now it lands
    assert move.params["x"] == 30.0
    assert move.params["z"] == -15.0
    assert move.id not in window.scene._part_items         or window.scene._part_items[move.id] is not item   # rebuilt


def test_dragging_a_snapped_group_releases_its_mate(window):
    """A mate re-solves on every change, so dragging a snapped part
    would be undone before it reached the screen. The drag detaches,
    the same rule as typing a position in Properties."""
    from PyQt5.QtCore import QPointF

    from khervecad import mates
    m = window.model
    comp = m.new_component("Part", visible=False)
    base = m.add_node("union", parent=comp, name="Base")
    m.add_node("cube", dict(width=20.0, depth=20.0, height=20.0),
               parent=base)
    lid = m.add_node("union", parent=comp, name="Lid")
    m.add_node("cube", dict(width=10.0, depth=10.0, height=10.0),
               parent=lid)
    m.structure_changed.emit()
    mates.attach(m, lid, "Base", "Bottom", "Top")
    assert lid.params["z"] == pytest.approx(20.0)

    window.builder.open_component(comp)
    window._set_plane("Front (XZ)")
    window.scene.commit_part_move(lid, QPointF(0.0, 15.0))
    assert mates.mate_of(lid) is None
    assert lid.params["z"] == pytest.approx(35.0)
    mates.refresh(m)                          # nothing to overwrite it
    assert lid.params["z"] == pytest.approx(35.0)


def test_drag_inside_a_part_that_has_anchors(window):
    """Dragging maps the delta through the ancestor chain, which meant
    resolving each ancestor's params — including an Object's "anchors"
    list, which is not points. The ValueError escaped through a Qt
    slot and PyQt aborted the process (0xC0000409)."""
    from PyQt5.QtCore import QPointF

    from khervecad import anchors
    m = window.model
    comp = m.new_component("Part", visible=False)
    comp.params.update(x=5.0, y=0.0, z=0.0)
    move = m.add_node("translate", dict(x=0.0, y=0.0, z=0.0),
                      parent=comp, name="Move")
    m.add_node("cube", dict(width=20.0, depth=20.0, height=20.0),
               parent=move)
    m.structure_changed.emit()
    # a picked anchor, exactly what the Snap tool stores on a part
    anchors.add_user_anchor(m, comp, [10.0, 10.0, 20.0],
                            [0.0, 0.0, 1.0], name="Port")
    assert isinstance(comp.params["anchors"], list)

    window.builder.open_component(comp)
    window._set_plane("Front (XZ)")
    window.scene.commit_part_move(move, QPointF(12.0, -4.0))
    assert move.params["x"] == 12.0
    assert move.params["z"] == -4.0
