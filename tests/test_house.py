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
    # 4 outer edges of the combined footprint + 1 shared inner wall = 7,
    # not 8 (each room's own 4 sides counted separately)
    assert len(walls) == 7
    shared = [(p1, p2) for p1, p2, _o in walls
             if p1 == (4000.0, 0.0) and p2 == (4000.0, 3000.0)]
    assert len(shared) == 1


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
    assert panel.openings_table.rowCount() == 2

    room = panel.current_floor.rooms[0]
    furniture = H.Furniture("home_sofa", room.x + 2000.0, room.y + 3500.0,
                            180.0)
    room.furniture.append(furniture)
    panel._sync_furniture_table()
    assert panel.furniture_table.rowCount() == 1

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


def test_a_wall_with_openings_is_solid_pieces_not_a_difference():
    # the preview draws a difference as its uncut first operand, which
    # hid every door and window until OpenSCAD finished
    nodes = H._wall_node((0.0, 0.0), (5000.0, 0.0),
                         [(1000.0, 900.0, 2000.0, 0.0, "door"),
                          (3000.0, 1200.0, 1200.0, 900.0, "window")],
                         200.0, 2400.0)
    wall, door_glass, window_glass = nodes
    assert "difference" not in _types(wall)
    names = sorted(c.name for c in wall.children[0].children)
    # 3 piers, a lintel over the door, a sill + lintel for the window
    assert names == ["Lintel", "Lintel", "Pier", "Pier", "Pier", "Sill"]
    # the wall's solid volume is the box minus both openings, exactly
    tris = mesh.tessellate(wall, fn=8)
    assert tris
    vol = sum(c.params["width"] * c.params["depth"] * c.params["height"]
              for c in wall.children[0].children)
    assert vol == pytest.approx(200.0 * (5000.0 * 2400.0
                                         - 900.0 * 2000.0
                                         - 1200.0 * 1200.0))
    for glass in (door_glass, window_glass):
        assert glass.params["material"] == "Glass"
        assert glass.params["alpha"] < 1.0      # see-through
    assert door_glass.children[0].name == "Door glass"


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
    # bookcase turned to face W, its back on the shared wall's face
    assert bookcase.rz == -90.0 and bookcase.y == 1000.0
    assert bookcase.x == pytest.approx(4900.0 - 150.0, abs=1.0)
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
    assert panel.furniture_table.rowCount() == 2
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
