"""The House Builder (house.py, house_items.py, house_dialog.py):
floor-by-floor rooms, wall/opening generation and the Build flow.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import house as H
from khervecad import mesh
from khervecad.model import validate
from khervecad.scadparse import parse_scad


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 700)
    return win


# --------------------------------------------------------------- walls
def test_two_adjacent_rooms_share_one_wall_not_two():
    floor = H.Floor("Ground floor", rooms=[
        H.Room("A", 0.0, 0.0, 4000.0, 3000.0),
        H.Room("B", 4000.0, 0.0, 4000.0, 3000.0),
    ])
    walls = H.collect_walls(floor)
    # the 4 sides of the combined footprint (the two rooms' S and N edges
    # run on as one wall each) + 1 shared inner wall
    assert len(walls) == 5
    shared = [(p1, p2) for p1, p2, _o, interior in walls
             if p1 == (4000.0, 0.0) and p2 == (4000.0, 3000.0) and interior]
    assert len(shared) == 1
    assert sum(1 for *_rest, interior in walls if not interior) == 4


def test_an_opening_lands_on_the_shared_wall_from_either_room():
    floor = H.Floor("Ground floor", rooms=[
        H.Room("A", 0.0, 0.0, 4000.0, 3000.0,
              openings=[H.Opening("door", "E", 1000.0, 900.0, 2000.0)]),
        H.Room("B", 4000.0, 0.0, 4000.0, 3000.0),
    ])
    walls = H.collect_walls(floor)
    shared = next(w for w in walls
                 if w[0] == (4000.0, 0.0) and w[1] == (4000.0, 3000.0))
    assert shared[2] == [(1000.0, 900.0, 2000.0, 0.0, "door")]
    assert shared[3] is True                      # a wall between rooms


def test_opening_offset_clamps_inside_a_short_wall():
    floor = H.Floor("Ground floor", rooms=[
        H.Room("A", 0.0, 0.0, 1000.0, 3000.0,
              openings=[H.Opening("door", "S", 5000.0, 900.0, 2000.0)]),
    ])
    group = H.build_floor(floor, is_top=True)
    assert not validate(group)
    _root, warnings = parse_scad(group.to_scad())
    assert not warnings


# ------------------------------------------------------------- geometry
def test_a_simple_house_has_no_validation_errors_and_real_triangles():
    floor = H.Floor("Ground floor", rooms=[
        H.Room("Living room", 0.0, 0.0, 5000.0, 4000.0,
              openings=[H.Opening("door", "S", 2000.0, 900.0, 2000.0),
                        H.Opening("window", "N", 500.0, 1500.0, 1200.0,
                                 900.0)],
              furniture=[H.Furniture("home_sofa", 2500.0, 3500.0, 180.0)]),
        H.Room("Kitchen", 5000.0, 0.0, 3000.0, 4000.0,
              openings=[H.Opening("door", "W", 1500.0, 900.0, 2000.0)],
              furniture=[H.Furniture("home_kitchen", 6500.0, 3800.0,
                                     180.0)]),
    ])
    group = H.build_floor(floor, is_top=True)
    assert not validate(group)
    tris = mesh.tessellate(group, fn=16)
    assert len(tris) > 0


def test_a_floor_with_no_rooms_refuses():
    floor = H.Floor("Empty floor")
    with pytest.raises(H.HouseError):
        H.build_floor(floor, is_top=True)


def test_house_bounds_spans_every_floor():
    house = H.House(floors=[
        H.Floor("Ground floor", rooms=[H.Room("A", 0, 0, 4000, 3000)]),
        H.Floor("First floor", rooms=[H.Room("B", -500, -500, 3000,
                                             3000)]),
    ])
    assert house.bounds() == (-500.0, -500.0, 4000.0, 3000.0)


# ------------------------------------------------------------- apply()
def test_apply_inserts_one_object_per_floor_stacked_plus_a_garden(window):
    model = window.model
    house = H.House(floors=[
        H.Floor("Ground floor", rooms=[H.Room("A", 0, 0, 4000, 3000)]),
        H.Floor("First floor", rooms=[H.Room("B", 0, 0, 4000, 3000)]),
    ], garden=H.Garden(width=3000.0, depth=4000.0))
    inserted = H.apply(model, house)
    names = [c.name for c in inserted]
    assert names == ["Ground floor", "First floor", "Garden"]
    assert all(c.type == "component" and c.visible for c in inserted)
    ground, first, garden = inserted
    assert ground.params["z"] == 0.0
    assert first.params["z"] == pytest.approx(
        H.WALL_HEIGHT + H.SLAB_THICKNESS)
    for node in model.root.walk():
        assert not validate(node)
    code = model.to_scad()          # must not raise
    assert "Ground_floor" in code and "First_floor" in code


def test_apply_refuses_a_house_with_no_floors(window):
    with pytest.raises(H.HouseError):
        H.apply(window.model, H.House(floors=[]))


# --------------------------------------------------------------- dialog
def test_dialog_add_edit_and_build(window):
    from khervecad import house_dialog

    panel = house_dialog.open_builder(window)
    assert house_dialog.open_builder(window) is panel   # one per window

    panel._add_room()
    assert len(panel.current_floor.rooms) == 2

    panel.current_room = panel.current_floor.rooms[0]
    panel._sync_room_fields()
    panel._add_opening("door")
    panel._add_opening("window")
    assert len(panel.current_room.openings) == 2
    assert panel.items_list.count() == 2

    room = panel.current_floor.rooms[0]
    furniture = H.Furniture("home_sofa", room.x + 2000.0, room.y + 3500.0,
                            180.0)
    room.furniture.append(furniture)
    panel._sync_items()
    assert panel.items_list.count() == 3      # door, window, sofa

    panel._add_floor()
    assert [f.name for f in panel.house.floors] == \
        ["Ground floor", "First floor"]

    panel._build()
    assert "Built:" in panel.status.text()
    names = [c.name for c in window.model.root.children]
    assert names == ["Ground floor", "First floor", "Garden"]
    panel.close()


def test_removing_the_last_floor_is_refused(window, monkeypatch):
    from PyQt5.QtWidgets import QMessageBox

    from khervecad import house_dialog

    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    panel = house_dialog.open_builder(window)
    panel._remove_floor()
    assert len(panel.house.floors) == 1
    panel.close()


def test_furniture_catalogue_parts_all_exist():
    from khervecad.library import PARTS
    for parts in H.FURNITURE_CATALOG.values():
        for part_id in parts:
            assert part_id in PARTS, part_id


# ------------------------------------------------ openings, no booleans
def _types(node):
    return {n.type for n in node.walk()}


def _walls(floor, **kw):
    from khervecad import house_walls as W
    return W.build_walls(floor, H.floor_look(H.House(**kw)))


def test_a_wall_leaf_is_one_solid_with_its_openings_as_holes():
    # one extruded outline per leaf: no seams across a facade, real
    # reveals, and the preview shows the openings exactly
    from khervecad import analysis
    room = H.Room("A", 0.0, 0.0, 5000.0, 4000.0, openings=[
        H.Opening("door", "S", 1000.0, 900.0, 2000.0),
        H.Opening("window", "S", 3000.0, 1200.0, 1200.0, 900.0)])
    floor = H.Floor("G", rooms=[room])
    nodes = _walls(floor, outer_wall="Red brick")
    south = [n for n in nodes if n.name == "Wall"
             and all(p[1] <= 1e-6 for t in mesh.tessellate(n, fn=8)
                     for p in t)]
    assert len(south) == 1
    assert south[0].params["material"] == "Brick"
    tris = mesh.tessellate(south[0], fn=8)
    vol = analysis.mass_properties(tris)["volume"]
    # 100 thick, 5200 long (corner wraps), 2600 high, minus both openings
    assert vol == pytest.approx(100.0 * (5200.0 * 2600.0 - 900.0 * 2000.0
                                         - 1200.0 * 1200.0), rel=1e-6)
    glass = [n for n in nodes if n.params.get("material") == "Glass"]
    assert {n.name for n in glass} == {"Glazing", "Door glass"}
    assert all(n.params["alpha"] < 1.0 for n in glass)
    names = {n.name for n in nodes}
    assert {"Window frame", "Sill", "Window board", "Door frame", "Door",
            "Threshold", "Front step", "Plinth", "Wall lining"} <= names


def test_outside_corners_are_closed_and_partitions_are_thinner():
    floor = H.Floor("G", rooms=[H.Room("A", 0, 0, 4000, 3000),
                                H.Room("B", 4000, 0, 4000, 3000)],
                    wall_thickness=300.0, inner_wall_thickness=90.0)
    segs = {(sg.horizontal, sg.c): sg for sg in H.wall_segments(floor)}
    south, west = segs[(True, 0.0)], segs[(False, 0.0)]
    # the facing wraps the corner by the other wall's half thickness
    assert (south.ext_a, south.ext_b) == (150.0, 150.0)
    assert south.outside == -1 and west.outside == -1
    assert segs[(False, 4000.0)].thickness == 90.0
    assert segs[(False, 4000.0)].interior
    # the corner square is filled: the facing of both walls reaches it
    tris = [t for n in _walls(floor) if n.name == "Wall"
            for t in mesh.tessellate(n, fn=8)]
    assert min(p[0] for t in tris for p in t) == pytest.approx(-150.0)
    assert min(p[1] for t in tris for p in t) == pytest.approx(-150.0)


def test_an_l_shaped_house_knows_inside_from_outside():
    floor = H.Floor("G", rooms=[H.Room("A", 0, 0, 10000, 5000),
                                H.Room("B", 0, 5000, 5000, 5000)])
    line = sorted((sg.a, sg.b, sg.outside) for sg in H.wall_segments(floor)
                  if sg.horizontal and sg.c == 5000.0)
    # shared with B, then the outside of the L (outdoors above it)
    assert line == [(0.0, 5000.0, 0), (5000.0, 10000.0, 1)]
    reflex = next(sg for sg in H.wall_segments(floor)
                  if sg.horizontal and sg.c == 5000.0 and sg.outside)
    assert reflex.ext_a == 0.0                   # no wrap at a reflex corner


def test_region_loops_cut_holes_and_notches():
    from khervecad.house_walls import region_loops
    loops = region_loops([(0, 0, 10, 10)], [(2, 2, 4, 4), (6, 0, 8, 5)])
    assert len(loops) == 1
    outline, holes = loops[0]
    assert len(outline) == 8                     # the door notch
    assert len(holes) == 1 and len(holes[0]) == 4
    # a full-height opening splits the wall in two
    assert len(region_loops([(0, 0, 10, 10)], [(4, -1, 6, 11)])) == 2


def test_overlapping_openings_do_not_overlap_pieces():
    spans = H._opening_spans([(0.0, 1000.0, 2000.0, 0.0, "door"),
                              (500.0, 1000.0, 2000.0, 0.0, "door")],
                             4000.0, 2400.0)
    assert spans[0][:2] == (0.0, 1000.0)
    assert spans[1][:2] == (1000.0, 1500.0)


# ------------------------------------------- furniture as nested Objects
def test_each_piece_of_furniture_is_its_own_object_inside_the_floor(window):
    house = H.House(floors=[H.Floor("Ground floor", rooms=[
        H.Room("Toilet", 0, 0, 2000, 1600, furniture=[
            H.Furniture("home_toilet", 1000, 500, 180.0),
            H.Furniture("room_chair", 500, 1000),
            H.Furniture("room_chair", 1500, 1000)])])])
    ground, = H.apply(window.model, house)
    inner = [n for n in ground.walk()
             if n.type == "component" and n is not ground]
    assert [n.name for n in inner] == ["Toilet", "Chair", "Chair 2"]
    assert inner[0].params["rz"] == 180.0
    code = window.model.to_scad()
    assert "module Toilet()" in code and "Toilet();" in code
    for node in window.model.root.walk():
        assert not validate(node)


# ----------------------------------------------------- build_house spec
SPEC = {"floors": [{"rooms": [
    {"name": "Living room", "x": 0, "y": 0, "w": 5000, "d": 4500,
     "openings": [{"kind": "door", "side": "S", "offset": 3400}],
     "furniture": [{"part_id": "home_sofa", "size": "3-seater",
                    "color": "Grey", "wall": "N"},
                   {"part_id": "home_bookcase", "wall": "E",
                    "along": 1000}]},
    {"name": "Kitchen", "x": 5000, "y": 0, "w": 3000, "d": 4500,
     "furniture": [{"part_id": "home_kitchen", "size": "3 units",
                    "wall": "E"},
                   {"part_id": "room_table", "x": 1500, "y": 2000}]},
]}], "garden": {"width": 3000}}


def test_house_from_spec_puts_backs_flush_against_walls():
    house = H.house_from_spec(SPEC)
    floor = house.floors[0]
    living, kitchen = floor.rooms
    sofa, bookcase = living.furniture
    # sofa: 950 deep, back against N's inside face (4500 - 100)
    assert sofa.rz == 0.0 and sofa.x == 2500.0
    assert sofa.y == pytest.approx(4400.0 - 475.0, abs=1.0)
    assert sofa.dims["_color"] == "Grey" and sofa.dims["w"] == 2200.0
    # bookcase turned to face W, its back on the shared (thinner) wall
    assert bookcase.rz == -90.0 and bookcase.y == 1000.0
    assert bookcase.x == pytest.approx(4950.0 - 150.0, abs=1.0)
    units, table = kitchen.furniture
    assert units.x == pytest.approx(7900.0 - 300.0, abs=1.0)
    assert (table.x, table.y) == (6500.0, 2000.0)     # room-relative
    assert house.garden.width == 3000.0


@pytest.mark.parametrize("bad, words", [
    ({}, "floors"),
    ({"floors": [{"rooms": [{"w": 1000}]}]}, "'d'"),
    ({"floors": [{"rooms": [{"w": 1, "d": 1, "openings": [
        {"side": "Q"}]}]}]}, "side"),
    ({"floors": [{"rooms": [{"w": 1, "d": 1, "furniture": [
        {"part_id": "nope"}]}]}]}, "No library part"),
    ({"floors": [{"rooms": [{"w": 1, "d": 1, "furniture": [
        {"part_id": "home_sofa", "size": "huge"}]}]}]}, "no size"),
])
def test_house_from_spec_refuses_with_a_reason(bad, words):
    with pytest.raises(H.HouseError, match=words):
        H.house_from_spec(bad)


def test_build_house_tool_inserts_and_reports(window):
    out = H.build_house(window, SPEC)
    names = [o["name"] for o in out["objects"]]
    assert names == ["Ground floor", "Garden"]
    assert "Sofa" in out["objects"][0]["contains"]
    dry = H.build_house(window, dict(SPEC, dry_run=True))
    assert dry["dry_run"] and len(window.model.root.children) == 2


# ------------------------------------ design saved with the document
def test_house_to_spec_round_trips():
    house = H.house_from_spec(SPEC)
    again = H.house_from_spec(H.house_to_spec(house))
    assert H.house_to_spec(again) == H.house_to_spec(house)
    sofa = again.floors[0].rooms[0].furniture[0]
    assert sofa.dims["_color"] == "Grey" and sofa.dims["w"] == 2200.0


def test_build_again_replaces_the_house_and_stores_the_design(window):
    model = window.model
    H.build_house(window, SPEC)
    assert model.house["objects"] == ["Ground floor", "Garden"]
    spec = dict(model.house)
    spec["floors"][0]["rooms"][0]["w"] = 6000.0
    H.apply(model, H.house_from_spec(spec))
    names = [c.name for c in model.root.children]
    assert names == ["Ground floor", "Garden"]      # updated, not copied
    assert model.house["floors"][0]["rooms"][0]["w"] == 6000.0
    assert '"house"' in model._serialize()          # in undo snapshots


def test_house_design_saves_and_loads_with_the_kcad(window, tmp_path):
    from khervecad.document import load_kcad, save_kcad
    from khervecad.model import DocumentModel
    H.build_house(window, SPEC)
    path = str(tmp_path / "house.kcad")
    save_kcad(window.model, path)
    other = DocumentModel()
    load_kcad(other, path)
    assert other.house == window.model.house
    other.clear()
    assert other.house is None


def test_builder_opens_on_the_documents_house_and_updates_it(window):
    from khervecad import house_dialog
    H.build_house(window, SPEC)
    panel = house_dialog.open_builder(window)
    rooms = panel.current_floor.rooms
    assert [r.name for r in rooms] == ["Living room", "Kitchen"]
    assert [f.part_id for f in rooms[0].furniture] == \
        ["home_sofa", "home_bookcase"]
    assert panel.room_list.count() == 2
    assert panel.items_list.count() == 3      # a door + two pieces
    # edit by hand, Build: the same house is updated in place
    rooms[1].w = 3500.0
    panel._build()
    assert [c.name for c in window.model.root.children] == \
        ["Ground floor", "Garden"]
    assert window.model.house["floors"][0]["rooms"][1]["w"] == 3500.0
    # an AI build while the builder is open refreshes it
    H.build_house(window, {"floors": [{"rooms": [
        {"name": "Studio", "w": 4000, "d": 4000}]}]})
    assert [r.name for r in panel.current_floor.rooms] == ["Studio"]
    panel.close()


# ------------------------------------------------------ canvas handles
def test_room_handles_move_the_side_they_sit_on(app):
    from PyQt5.QtCore import QPointF

    from khervecad import house_items as HI
    room = H.Room("A", 0.0, 0.0, 4000.0, 3000.0)
    item = HI.RoomItem(room)
    by_role = {h.role: h for h in item.handles}
    assert len(by_role) == 8
    # Y-up: the N handles sit on the top edge (y = d), S on y = 0
    assert by_role["N"].pos().y() == 3000.0
    assert by_role["SW"].pos() == QPointF(0.0, 0.0)
    item.handle_dragged("N", QPointF(2000.0, 3600.0))
    assert (room.y, room.d) == (0.0, 3600.0)        # top edge moved
    item.handle_dragged("SW", QPointF(-500.0, 500.0))
    assert (room.x, room.y, room.w, room.d) == (-500.0, 500.0, 4500.0,
                                                3100.0)
    item.handle_dragged("E", QPointF(4100.0, 9999.0))
    assert room.w == 4600.0 and room.d == 3100.0    # E only moves x


def test_selected_room_sits_above_its_neighbours(app):
    from PyQt5.QtWidgets import QGraphicsScene

    from khervecad import house_items as HI
    scene = QGraphicsScene()
    a = HI.RoomItem(H.Room("A", 0, 0, 4000, 3000))
    b = HI.RoomItem(H.Room("B", 4000, 0, 4000, 3000))
    scene.addItem(a)
    scene.addItem(b)
    a.setSelected(True)
    assert a.zValue() > b.zValue()


# ---------------------------------------------------------- zoom range
def test_3d_zoom_reaches_house_scale(window):
    from khervecad import viewnav
    view = window.view3d
    view.distance = 4000.0
    for _ in range(40):
        viewnav.zoom_3d(view, 0.5)
    assert view.distance == view.MAX_DISTANCE
    assert view.MAX_DISTANCE >= 100_000.0     # a 100 m site, not 5 m


# ------------------------------------------------- the plan's own items
class _SceneEvent:
    """The bits of a QGraphicsSceneMouseEvent the plan items read —
    PyQt5 cannot construct the real one."""

    def __init__(self, pos=(0.0, 0.0), modifiers=None):
        from PyQt5.QtCore import QPointF, Qt
        self._pos = QPointF(*pos)
        self._mods = modifiers if modifiers is not None else Qt.NoModifier

    def scenePos(self):
        return self._pos

    def modifiers(self):
        return self._mods

    def accept(self):
        pass


def _scene_event(_kind, pos=(0.0, 0.0), modifiers=None):
    return _SceneEvent(pos, modifiers)


def test_furniture_is_drawn_at_its_real_size_and_turns_on_double_click(app):
    from PyQt5.QtCore import Qt

    from khervecad import house_items as HI
    f = H.Furniture("home_sofa", 2000.0, 1000.0, 0.0,
                    H.part_dims("home_sofa", "3-seater"))
    item = HI.FurnitureItem(f, "Sofa")
    # the sofa's real 2.2 m x 0.95 m footprint, not a 0.4 m marker
    assert item.rect().width() == pytest.approx(2200.0, abs=20.0)
    assert item.rect().height() == pytest.approx(950.0, abs=20.0)
    item.mouseDoubleClickEvent(_scene_event("GraphicsSceneMouseDoubleClick"))
    assert f.rz == 90.0 and item.rotation() == 90.0
    item.mouseDoubleClickEvent(_scene_event(
        "GraphicsSceneMouseDoubleClick", modifiers=Qt.ShiftModifier))
    assert f.rz == 0.0                        # Shift turns it back
    for _ in range(3):
        item.rotate_by(90.0)
    assert f.rz == -90.0                      # kept in (-180, 180]


def test_dragging_a_door_slides_it_along_and_onto_another_wall(app):
    from khervecad import house_items as HI
    room = H.Room("A", 0.0, 0.0, 4000.0, 3000.0)
    door = H.Opening("door", "S", 0.0, 900.0, 2000.0)
    room.openings.append(door)
    item = HI.OpeningItem(room, door, H.Floor("G", rooms=[room]))
    item._grab = 450.0                        # held by its middle
    item.mouseMoveEvent(_scene_event("GraphicsSceneMouseMove", (2000, 50)))
    assert (door.side, door.offset) == ("S", 1550.0)
    item.mouseMoveEvent(_scene_event("GraphicsSceneMouseMove",
                                     (3950, 1500)))
    assert (door.side, door.offset) == ("E", 1050.0)


def test_plan_walls_leave_a_gap_for_each_opening():
    from khervecad import house_items as HI
    pieces = HI.wall_pieces((0.0, 0.0), (5000.0, 0.0),
                            [(1000.0, 900.0, 2000.0, 0.0, "door")],
                            200.0, 2400.0)
    # half a wall past each end closes the corners; the door is a gap
    assert [(r.left(), r.right()) for r in pieces] == \
        [(-100.0, 1000.0), (1900.0, 5100.0)]
    assert all(r.height() == 200.0 for r in pieces)


def test_moving_a_room_carries_its_furniture(app):
    from PyQt5.QtWidgets import QGraphicsScene

    from khervecad import house_items as HI
    room = H.Room("A", 0.0, 0.0, 4000.0, 3000.0,
                  furniture=[H.Furniture("room_chair", 1000.0, 1000.0)])
    scene = QGraphicsScene()
    item = HI.RoomItem(room)
    scene.addItem(item)
    item.setPos(500.0, 250.0)
    assert (room.x, room.y) == (500.0, 250.0)
    chair = room.furniture[0]
    assert (chair.x, chair.y) == (1500.0, 1250.0)


def test_builder_edits_the_selected_door_or_furniture(window):
    from khervecad import house_dialog
    H.build_house(window, SPEC)
    panel = house_dialog.open_builder(window)
    living = panel.current_floor.rooms[0]
    panel.items_list.setCurrentRow(1)                 # the sofa
    assert panel.current_item is living.furniture[0]
    assert panel.editor.currentIndex() == 2
    assert panel.fu_size.currentText().startswith("3-seater")
    panel._rotate_selected(90.0)
    assert living.furniture[0].rz == 90.0
    panel.items_list.setCurrentRow(0)                 # the door
    assert panel.editor.currentIndex() == 1
    panel.op_side.setCurrentIndex(panel.op_side.findData("N"))
    assert living.openings[0].side == "N"
    panel.close()


# --------------------------------------------- the main window's 2D view
def test_2d_view_frames_the_whole_house_and_draws_its_plan(window):
    H.build_house(window, SPEC)
    scene, view = window.scene, window.view2d
    drawn = scene.itemsBoundingRect()
    # the scene used to be a fixed 4 m square: most of the house fell
    # outside it, so Fit could not frame it nor the view scroll to it
    assert scene.sceneRect().contains(drawn)
    view.fit_content()
    shown = view.mapToScene(view.viewport().rect()).boundingRect()
    assert shown.contains(drawn)
    ground = scene._part_items[window.model.root.children[0].id]
    colours = {c.name() for _poly, c in ground._faces}
    # its own colours (walls, floors, glass, furniture), not one blob,
    # and cut like a floor plan: the roof is not drawn over the rooms
    assert len(colours) > 4
    assert H.ROOF_COLOR not in colours


# ---------------------------------------------------------------- roofs
_ROOF_PARTS = ("Roof", "Roof slope", "Roof covering", "Gable", "Wedge")


def _roof_clears_the_walls(group, floor):
    """Nothing of a wall stands above the roof over it — the facing's
    top once showed as a brick strip along every eave."""
    from khervecad.house_roof import RoofShape
    sh = RoofShape(H.Roof("Gable"), floor)
    walls = [n for n in group.children if n.name in ("Wall", "Wall lining")]
    top = max(p[2] for n in walls for t in mesh.tessellate(n, fn=8)
              for p in t)
    assert top <= floor.wall_height + 1e-6


@pytest.mark.parametrize("style", H.ROOF_STYLES)
def test_every_roof_style_builds_over_the_top_floor(style):
    floor = H.Floor("Ground floor", rooms=[H.Room("A", 0, 0, 8000, 5000)])
    roof = H.Roof(style, H.ROOF_PITCH[style] or 35.0)
    group = H.build_floor(floor, is_top=True, roof=roof)
    assert not validate(group)
    assert "difference" not in _types(group)
    pieces = [n for n in group.children if n.name in _ROOF_PARTS]
    assert pieces
    top = max(p[2] for n in pieces for t in mesh.tessellate(n, fn=8)
              for p in t)
    if style == "Flat":
        assert top == pytest.approx(H.WALL_HEIGHT + H.ROOF_THICKNESS)
    else:
        assert top > H.WALL_HEIGHT + 800.0        # it really rises
        _roof_clears_the_walls(group, floor)
    _root, warnings = parse_scad(group.to_scad())
    assert not warnings


def test_the_ridge_runs_along_the_long_side_unless_told():
    floor = H.Floor("G", rooms=[H.Room("A", 0, 0, 8000, 4000)])
    (a, b), = H.roof_outline(H.Roof("Gable"), floor)["lines"]
    assert a[1] == b[1] == 2000.0                 # along X
    (a, b), = H.roof_outline(H.Roof("Gable", ridge="y"), floor)["lines"]
    assert a[0] == b[0] == 4000.0                 # along Y
    hip = H.roof_outline(H.Roof("Hip"), floor)["lines"]
    assert len(hip) == 5                          # a ridge and four hips


def test_outdoor_areas_get_no_walls_and_no_roof():
    floor = H.Floor("G", rooms=[
        H.Room("House", 0, 0, 6000, 4000),
        H.Room("Patio", 6000, 0, 4000, 4000, surface="paving")])
    assert len(H.collect_walls(floor)) == 4       # the house's four only
    eave = H.roof_outline(H.Roof("Gable"), floor)["eave"]
    assert eave[2] == pytest.approx(6000.0 + H.ROOF_EAVE)
    group = H.build_floor(floor, is_top=True, roof=H.Roof("Gable"))
    assert not validate(group)
    patio = next(n for n in group.children if n.name == "Patio")
    assert patio.params["color"] == H.PAVING_COLOR


def test_roofs_and_surfaces_round_trip_and_old_designs_stay_flat():
    spec = dict(SPEC, roof={"style": "hipped", "pitch": 25,
                            "color": "slate"})
    spec["floors"][0]["rooms"][1]["surface"] = "garden"
    house = H.house_from_spec(spec)
    assert (house.roof.style, house.roof.pitch, house.roof.color) == \
        ("Hip", 25.0, "Slate")
    again = H.house_from_spec(H.house_to_spec(house))
    assert again.roof == house.roof
    assert again.floors[0].rooms[1].surface == "garden"
    spec["floors"][0]["rooms"][1]["surface"] = "indoor"
    assert H.house_from_spec(SPEC).roof.style == "Flat"
    with pytest.raises(H.HouseError, match="pitch"):
        H.house_from_spec(dict(SPEC, roof={"style": "gable", "pitch": 80}))


def test_a_garage_door_is_a_sectional_metal_panel():
    room = H.Room("Garage", 0, 0, 3500, 6000, openings=[
        H.Opening("garage door", "S", 550.0, 2400.0, 2100.0)])
    nodes = _walls(H.Floor("G", rooms=[room]))
    sections = [n for n in nodes if n.name == "Door section"]
    assert len(sections) == 4
    assert all(n.params["material"] == "Metal" and n.params["alpha"] == 1.0
               for n in sections)
    house = H.house_from_spec({"floors": [{"rooms": [
        {"w": 3500, "d": 6000, "openings": [{"kind": "garage"}]}]}]})
    assert house.floors[0].rooms[0].openings[0].width == 2400.0


# ------------------------------------------------ furniture on furniture
def _one_room(*pieces):
    return H.Floor("G", rooms=[H.Room("A", 0, 0, 5000, 4000,
                                      furniture=list(pieces))])


def test_a_tv_sits_on_its_stand_even_when_turned():
    for rz in (0.0, 90.0):
        unit = H.Furniture("home_sideboard", 2000, 2000, rz,
                           H.part_dims("home_sideboard", "TV unit"))
        tv = H.Furniture("room_tv", 2000, 2000, rz,
                         H.part_dims("room_tv", "55"))
        assert H.surface_below(_one_room(unit, tv), tv) == \
            pytest.approx(560.0, abs=1.0)
    lone = H.Furniture("room_tv", 500, 500, 0.0, H.part_dims("room_tv"))
    assert H.surface_below(_one_room(lone), lone) == 0.0


def test_a_microwave_goes_on_the_worktop_not_the_wall_cupboards():
    kitchen = H.Furniture("home_kitchen", 2500, 3000, 0.0,
                          H.part_dims("home_kitchen"))
    micro = H.Furniture("home_microwave", 2800, 3000, 0.0,
                        H.part_dims("home_microwave"))
    assert H.surface_below(_one_room(kitchen, micro), micro) == \
        pytest.approx(900.0, abs=1.0)


def test_wall_pieces_hold_nothing_and_on_top_works_from_a_spec():
    shelf = H.Furniture("home_wall_shelf", 1000, 1000, 0.0,
                        H.part_dims("home_wall_shelf"), z=1300.0)
    lamp = H.Furniture("home_table_lamp", 1000, 1000, 0.0,
                       H.part_dims("home_table_lamp"))
    assert H.surface_below(_one_room(shelf, lamp), lamp) == 0.0
    room = H.house_from_spec({"floors": [{"rooms": [{
        "w": 4000, "d": 4000, "furniture": [
            {"part_id": "home_pendant"},
            {"part_id": "home_side_table", "x": 1000, "y": 1000},
            {"part_id": "home_table_lamp", "x": 1000, "y": 1000,
             "on_top": True}]}]}]}).floors[0].rooms[0]
    assert room.furniture[0].z == H.part_rest_z("home_pendant")
    assert room.furniture[2].z == pytest.approx(550.0, abs=1.0)


def test_builder_sets_a_piece_on_what_is_under_it(window):
    from khervecad import house_dialog
    H.build_house(window, SPEC)
    panel = house_dialog.open_builder(window)
    living = panel.current_floor.rooms[0]
    unit = H.Furniture("home_sideboard", living.x + 1500, living.y + 1500,
                       0.0, H.part_dims("home_sideboard", "TV unit"))
    tv = H.Furniture("room_tv", unit.x, unit.y, 0.0, H.part_dims("room_tv"))
    living.furniture += [unit, tv]
    panel.current_room = living
    panel._sync_items()
    panel._rebuild_canvas()
    panel.items_list.setCurrentRow(panel.items_list.count() - 1)   # the TV
    assert panel.current_item is tv
    panel._sit_selected()
    assert tv.z == pytest.approx(560.0, abs=1.0)
    assert panel.fu_z.value() == pytest.approx(0.56, abs=0.001)
    assert "m up" in panel.items_list.currentItem().text()
    panel.fu_z.setValue(1.0)
    assert tv.z == 1000.0
    panel.close()


def test_a_side_wing_with_nothing_above_it_gets_its_own_roof():
    # the shape that showed the hole: a two-storey house with a
    # single-storey garage beside it, which had no roof at all
    house = H.House(floors=[
        H.Floor("Ground floor", rooms=[
            H.Room("House", 0, 0, 8000, 6000),
            H.Room("Garage", 8000, 0, 3500, 6000)]),
        H.Floor("First floor", rooms=[H.Room("Landing", 0, 0, 8000, 6000)])],
        roof=H.Roof("Gable"))
    wings = H.wing_roofs(house, 0)
    assert len(wings) == 1
    bounds, attach = wings[0]
    assert bounds == (8000.0, 0.0, 11500.0, 6000.0)
    assert attach == "W"                      # the house is to its west
    assert H.wing_roofs(house, 1) == []       # the top floor has the roof
    ground = H.build_floor(house.floors[0], is_top=False, roof=house.roof,
                           wings=wings)
    assert not validate(ground)
    wing = [n for n in ground.children if n.name.startswith("Wing roof")]
    assert wing, [n.name for n in ground.children]
    zs = [p[2] for n in wing for t in mesh.tessellate(n, fn=8) for p in t]
    # it leans on the house: highest where they meet, lower at the far side
    assert max(zs) > H.WALL_HEIGHT
    high = [p for n in wing for t in mesh.tessellate(n, fn=8) for p in t
            if p[2] > max(zs) - 1.0]
    assert min(p[0] for p in high) < 8600.0


def test_uncovered_rects_finds_what_has_nothing_on_top():
    below = [(0.0, 0.0, 10.0, 10.0)]
    assert H.uncovered_rects(below, [(0.0, 0.0, 10.0, 10.0)]) == []
    assert H.uncovered_rects(below, []) == [(0.0, 0.0, 10.0, 10.0)]
    # a floor above covering only the left half leaves the right one open
    assert H.uncovered_rects(below, [(0.0, 0.0, 6.0, 10.0)]) == \
        [(6.0, 0.0, 10.0, 10.0)]


def test_outer_and_inner_walls_are_finished_differently():
    floor = H.Floor("G", rooms=[H.Room("A", 0, 0, 4000, 3000),
                                H.Room("B", 4000, 0, 4000, 3000)])
    group = H.build_floor(floor, is_top=True, walls=("Red brick", "Sage"))
    assert not validate(group)
    colours = {n.params["color"] for n in group.children
               if n.type == "color" and n.name.endswith("wall")
               or n.name == "Wall"}
    assert H.WALL_STYLES["Red brick"][0] in colours
    assert H.INNER_WALL_STYLES["Sage"][0] in colours
    # the gable a pitched roof closes is wall, so it is brick too — it
    # stood out as a bare white triangle over a brick house
    gabled = H.build_floor(floor, is_top=True, roof=H.Roof("Gable"),
                           walls=("Red brick", "Sage"))
    gable = next(n for n in gabled.children if n.name == "Gable")
    assert gable.params["color"] == H.WALL_STYLES["Red brick"][0]


def test_a_room_finish_tiles_its_own_walls_around_the_openings():
    from khervecad import analysis
    room = H.Room("Studio", 0, 0, 2500, 2000, finish="White tiles",
                  openings=[H.Opening("door", "S", 800.0, 900.0, 2000.0)])
    floor = H.Floor("G", rooms=[room])
    nodes = H.room_finish_nodes(room, floor)
    tiles = H.ROOM_FINISHES["White tiles"]
    assert nodes[0].name == "Studio floor"
    assert nodes[0].params["material"] == tiles[1][1]
    linings = [n for n in nodes if n.name == "Wall tiles"]
    assert len(linings) == 4                    # one solid per wall
    south = next(n for n in linings
                 if mesh.tessellate(n, fn=8)[0][0][1] < 200.0
                 and all(p[1] < 200.0 for t in mesh.tessellate(n, fn=8)
                         for p in t))
    vol = analysis.mass_properties(mesh.tessellate(south, fn=8))["volume"]
    # 10 mm of tiles, floor to ceiling, between the side walls, minus
    # the door
    assert vol == pytest.approx(10.0 * (2300.0 * 2400.0 - 900.0 * 2000.0),
                                rel=1e-6)
    assert not H.room_finish_nodes(
        H.Room("Lawn", 0, 0, 1000, 1000, surface="garden",
               finish="White tiles"), floor)
    group = H.build_floor(floor, is_top=True)
    assert not validate(group)
    assert "Wall tiles" in [n.name for n in group.children]


def test_bathrooms_and_kitchens_are_tiled_where_the_fixtures_stand():
    from khervecad import house_finishes as F
    spec = {"floors": [{"rooms": [
        {"name": "Bathroom", "w": 3000, "d": 2500, "furniture": [
            {"part_id": "home_bath", "wall": "N"}]},
        {"name": "Kitchen", "x": 3000, "w": 3500, "d": 2500, "furniture": [
            {"part_id": "home_kitchen", "wall": "S"}]},
        {"name": "Bedroom", "x": 6500, "w": 3000, "d": 2500}]}]}
    floor = H.house_from_spec(spec).floors[0]
    bath, kitchen, bed = floor.rooms
    assert F.finish_of(bath) in H.ROOM_FINISHES
    assert F.coverage_of(bath) == "wet" and F.coverage_of(kitchen) == "splash"
    assert F.finish_of(bed) is None
    assert F.flooring_of(bed)[1] in ("Carpet", "Floorboards")

    def tile_top(room, side_y):
        zs = [p[2] for n in H.room_finish_nodes(room, floor)
              if n.name == "Wall tiles" for t in mesh.tessellate(n, fn=8)
              for p in t if abs(p[1] - side_y) < 60.0]
        return (min(zs), max(zs)) if zs else None
    # the bath's wall is tiled to the ceiling, the others to half height
    assert tile_top(bath, 2450.0) == (0.0, 2400.0)
    assert tile_top(bath, 50.0) == (0.0, F.HALF_TILE)
    # a splashback band behind the worktop, nothing elsewhere
    assert tile_top(kitchen, 50.0) == F.SPLASH
    assert tile_top(kitchen, 2450.0) is None
    # none means none
    bath.finish = F.NO_FINISH
    assert not [n for n in H.room_finish_nodes(bath, floor)
                if n.name == "Wall tiles"]


def test_a_fireplace_gets_a_chimney_through_the_roof():
    from khervecad.house_roof import CHIMNEY_CLEAR
    spec = {"roof": {"style": "Gable"}, "floors": [
        {"rooms": [{"name": "Living", "w": 5000, "d": 4000, "furniture": [
            {"part_id": "home_fireplace", "wall": "W"}]},
            {"name": "Snug", "x": 5000, "w": 3000, "d": 4000, "furniture": [
                {"part_id": "home_fireplace", "wall": "W"}]}]},
        {"rooms": [{"name": "Bedroom", "w": 8000, "d": 4000}]}]}
    house = H.house_from_spec(spec)
    groups = H.build_house_floors(house)
    ground, first = groups

    def boxes(group, name):
        return [n for n in group.children if n.name == name]
    # the outside wall's fireplace: a stack from the ground, outside
    stacks = boxes(ground, "Chimney stack") + boxes(first, "Chimney stack")
    assert any(n.children[0].params["x"] < 0.0 for n in stacks)
    # the partition's fireplace: a breast upstairs too, a stack in the roof
    assert boxes(first, "Chimney breast")
    pots = boxes(first, "Chimney pot")
    assert len(pots) >= 2
    top = max(p.children[0].params["z"] for p in pots)
    ridge = house.floors[1].wall_height + 2000.0 * 0.7
    assert top > ridge
    assert not validate(first)
    house.roof.chimney = "none"
    assert not boxes(H.build_house_floors(house)[1], "Chimney pot")


def test_wall_styles_finishes_and_wing_roofs_round_trip():
    spec = dict(SPEC, roof={"style": "Gable", "wings": "shed"},
                walls={"outside": "red brick", "inside": "Sage"})
    spec["floors"][0]["rooms"][1]["finish"] = "blue tiles"
    spec["floors"][0]["rooms"][1]["flooring"] = "oak parquet"
    spec["floors"][0]["inner_wall_thickness"] = 80
    spec["roof"]["chimney"] = "ridge"
    spec["walls"]["joinery"] = "oak"
    house = H.house_from_spec(spec)
    assert house.floors[0].rooms[1].flooring == "Oak parquet"
    assert house.floors[0].inner_wall_thickness == 80.0
    assert (house.roof.chimney, house.joinery) == ("ridge", "Oak")
    assert house.roof.wings == "Lean-to"
    assert (house.outer_wall, house.inner_wall) == ("Red brick", "Sage")
    assert house.floors[0].rooms[1].finish == "Blue tiles"
    again = H.house_from_spec(H.house_to_spec(house))
    assert H.house_to_spec(again) == H.house_to_spec(house)
    assert H.house_from_spec(SPEC).outer_wall == "Painted plaster"
    for bad, words in ((dict(SPEC, walls={"outside": "gold"}), "not one of"),
                       (dict(SPEC, roof={"wings": "dome"}), "wings")):
        with pytest.raises(H.HouseError, match=words):
            H.house_from_spec(bad)
    spec["floors"][0]["rooms"][1]["finish"] = "lino"
    with pytest.raises(H.HouseError, match="finish"):
        H.house_from_spec(spec)


def test_builder_adds_rooms_by_kind_and_changes_the_roof(window):
    from khervecad import house_dialog
    panel = house_dialog.open_builder(window)
    panel._add_room("Garage")
    garage = panel.current_room
    assert (garage.name, garage.w, garage.d, garage.surface) == \
        ("Garage", 3500.0, 6000.0, "indoor")
    panel._add_opening("garage door")
    assert garage.openings[-1].width == 2400.0
    panel._add_room("Garden")
    assert panel.current_room.surface == "garden"
    panel._add_opening("door")
    assert not panel.current_room.openings        # no walls outdoors
    assert house_dialog._guess_category("Front porch") == "Entrance / porch"
    assert house_dialog._guess_category("Kids bedroom") == "Kids' room"
    panel.roof_style.setCurrentText("Hip")
    assert panel.house.roof.style == "Hip"
    assert panel.house.roof.pitch == H.ROOF_PITCH["Hip"]
    panel._build()
    assert window.model.house["roof"]["style"] == "Hip"
    panel.close()
