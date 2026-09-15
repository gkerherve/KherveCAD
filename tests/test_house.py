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
