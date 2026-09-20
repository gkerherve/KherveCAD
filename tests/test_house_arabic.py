"""The Arab courtyard house in the House Builder: round-headed openings
(`arch window` / `arch door`), a flat terrace roof with a crenellated
parapet that leaves the courtyard open, the finished design as a Library
part and House Builder template, and the spec / MCP round trip.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest

from khervecad import house as H
from khervecad import house_arabic, house_designs, house_templates, library
from khervecad import house_walls as W
from khervecad.model import CadNode, validate


def _area(poly):
    return sum(poly[k - 1][0] * poly[k][1] - poly[k][0] * poly[k - 1][1]
               for k in range(len(poly))) / 2.0


def _home(furnished=False, style="Sand render"):
    return H.house_from_spec(house_arabic.courtyard_house(style, furnished))


def _nodes(root, name):
    return [n for n in root.walk() if n.name == name]


# ------------------------------------------------------------- the arch
def test_an_arch_outline_is_counter_clockwise_with_a_round_head():
    shape = W.arch_shape(0.0, 1000.0, 0.0, 2000.0)
    assert _area(shape) > 0
    # a semicircular head: the rectangle to the springing line plus a
    # half disc of radius 500
    assert _area(shape) == pytest.approx(1000 * 1500 + math.pi * 500 ** 2 / 2,
                                         rel=0.01)
    assert max(p[1] for p in shape) == pytest.approx(2000.0)
    xs = [p[0] for p in shape]
    assert min(xs) == 0.0 and max(xs) == 1000.0


def test_the_spandrels_fill_exactly_what_the_arch_leaves_of_the_rectangle():
    w, h = 1000.0, 2000.0
    left, right = (poly for poly, _holes in W._spandrels(0.0, w, 0.0, h))
    assert _area(left) > 0 and _area(right) > 0
    assert _area(left) + _area(right) == pytest.approx(
        w * h - _area(W.arch_shape(0.0, w, 0.0, h)), rel=0.01)


def test_a_low_wide_opening_gets_a_flatter_head_not_a_broken_one():
    shape = W.arch_shape(0.0, 2000.0, 0.0, 700.0)
    assert _area(shape) > 0
    assert max(p[1] for p in shape) == pytest.approx(700.0)


# ------------------------------------------------------ the opening kinds
def test_the_arched_kinds_exist_with_their_own_default_sizes():
    assert set(H.ARCHED) <= set(H.OPENING_KINDS)
    w, h, sill = H.opening_size("arch window")
    assert sill > 0 and h > w
    w, h, sill = H.opening_size("arch door")
    assert sill == 0 and h > 2200


@pytest.mark.parametrize("word,kind", [("arch window", "arch window"),
                                       ("arched window", "arch window"),
                                       ("arch door", "arch door"),
                                       ("arched door", "arch door")])
def test_the_spec_accepts_arched_openings_and_their_aliases(word, kind):
    op = H._opening_from_spec({"kind": word, "side": "S", "offset": 200})
    assert op.kind == kind


def test_an_unknown_kind_still_lists_the_arched_ones():
    with pytest.raises(H.HouseError, match="arch window"):
        H._opening_from_spec({"kind": "portcullis", "side": "S"})


def _one_room_house(kind, side="S"):
    return H.house_from_spec({"floors": [{"rooms": [{
        "name": "Hall", "x": 0, "y": 0, "w": 5000, "d": 4000,
        "openings": [{"kind": kind, "side": side, "offset": 1800}]}]}],
        "roof": {"style": "Flat"}})


@pytest.mark.parametrize("kind", H.ARCHED)
def test_an_arched_opening_builds_clean_solids(kind):
    node = CadNode("union", "h", {})
    for f in H.build_house_floors(_one_room_house(kind)):
        node.add(f)
    assert not validate(node)
    names = {n.name for n in node.walk()}
    assert "Arch fill" in names and "Arch surround" in names
    if kind == "arch window":
        assert {"Window frame", "Glazing"} <= names
    else:
        assert {"Door", "Door studs"} <= names


def test_an_arched_door_between_two_rooms_has_a_lining_and_a_leaf():
    home = H.house_from_spec({"floors": [{"rooms": [
        {"name": "A", "x": 0, "y": 0, "w": 3000, "d": 3000,
         "openings": [{"kind": "arch door", "side": "E", "offset": 900}]},
        {"name": "B", "x": 3000, "y": 0, "w": 3000, "d": 3000}]}]})
    node = CadNode("union", "h", {})
    for f in H.build_house_floors(home):
        node.add(f)
    assert not validate(node)
    assert _nodes(node, "Door lining") and _nodes(node, "Door")


# ---------------------------------------------------------------- roofs
def test_the_roof_spec_round_trips_a_parapet():
    roof = H.roof_from_spec({"style": "Flat", "parapet": 900,
                             "crenellated": True})
    assert roof.parapet == 900 and roof.crenellated
    home = _home()
    back = H.house_from_spec(H.house_to_spec(home))
    assert back.roof.parapet == home.roof.parapet == 1000.0
    assert back.roof.crenellated is True


def test_a_negative_parapet_is_refused():
    with pytest.raises(H.HouseError, match="parapet"):
        H.roof_from_spec({"style": "Flat", "parapet": -1})


def test_a_flat_roof_without_a_parapet_is_what_it_always_was():
    home = H.house_from_spec({"floors": [{"rooms": [{
        "name": "Hall", "x": 0, "y": 0, "w": 4000, "d": 4000}]}],
        "roof": {"style": "Flat"}})
    node = CadNode("union", "h", {})
    for f in H.build_house_floors(home):
        node.add(f)
    assert not _nodes(node, "Parapet")
    assert _nodes(node, "Roof")


def _top_floor_nodes(home):
    floors = H.build_house_floors(home)
    top = CadNode("union", "top", {})
    top.add(floors[-1])
    return top


def test_the_terrace_covers_the_rooms_but_leaves_the_courtyard_open():
    home = _home()
    top = home.floors[-1]
    roofs = [n for n in _top_floor_nodes(home).walk()
             if n.type == "cube" and n.name == "Roof slab"]
    assert len(roofs) >= 10
    void = next(r for r in top.rooms if r.name == "Gallery void")
    cx, cy = void.x + void.w / 2, void.y + void.d / 2
    for c in roofs:                     # no slab over the middle of the court
        p = c.params
        assert not (p["x"] < cx < p["x"] + p["width"]
                    and p["y"] < cy < p["y"] + p["depth"])
    # ...but the stairwell, which is inside the house, is covered
    well = next(r for r in top.rooms if r.name == "Stairwell")
    sx, sy = well.x + well.w / 2, well.y + well.d / 2
    assert any(c.params["x"] < sx < c.params["x"] + c.params["width"]
               and c.params["y"] < sy < c.params["y"] + c.params["depth"]
               for c in roofs)


def test_the_parapet_stands_on_every_outside_wall_and_is_crenellated():
    home = _home()
    nodes = _top_floor_nodes(home)
    assert _nodes(nodes, "Parapet")
    merlons = [n for g in _nodes(nodes, "Merlons") for n in g.walk()
               if n.name == "Merlon"]
    assert len(merlons) > 40
    plain = _home()
    plain.roof.crenellated = False
    assert not _nodes(_top_floor_nodes(plain), "Merlons")


def test_a_low_wall_rings_the_opening_over_the_courtyard():
    parapets = [n for n in _top_floor_nodes(_home()).walk()
                if n.name.startswith("Court parapet")]
    assert {n.name[-1] for n in parapets} == set("NSEW")


# ------------------------------------------------------ the finished house
def test_the_plan_is_a_courtyard_with_rooms_turned_inwards():
    home = _home()
    assert [f.name for f in home.floors] == ["Ground floor", "First floor"]
    court = next(r for r in home.floors[0].rooms if r.name == "Courtyard")
    assert court.surface == "paving"
    # every ground room but the court is indoor, and each principal one
    # has an arched door onto it or onto the hall
    rooms = {r.name: r for r in home.floors[0].rooms}
    assert {"Majlis", "Entrance hall", "Dining room", "Family room",
            "Kitchen", "Diwan", "Guest bedroom", "Stair hall"} <= set(rooms)
    kinds = {o.kind for r in home.floors[0].rooms for o in r.openings}
    assert kinds == {"arch door", "arch window"}


def test_the_gallery_has_a_balustrade_towards_the_court():
    upper = _home().floors[1]
    assert [r.name for r in upper.rooms].count("Gallery") == 4
    rails = [sg for sg in H.wall_segments(upper) if sg.rail]
    assert rails                        # the gallery's open side
    node = CadNode("union", "h", {})
    for f in H.build_house_floors(_home()):
        node.add(f)
    assert _nodes(node, "Handrail")


@pytest.mark.parametrize("style", house_designs.ARAB_STYLES)
@pytest.mark.parametrize("furnished", [False, True])
def test_the_house_builds_clean_in_every_render_furnished_or_not(style,
                                                                furnished):
    home = _home(furnished, style)
    assert home.outer_wall == style
    node = CadNode("union", "h", {})
    for f in H.build_house_floors(home):
        node.add(f)
    assert not validate(node)


def test_nothing_furnished_stands_outside_its_room():
    for floor in _home(True).floors:
        for room in floor.rooms:
            for f in room.furniture:
                assert room.x - 1 <= f.x <= room.x + room.w + 1, \
                    (room.name, f.part_id)
                assert room.y - 1 <= f.y <= room.y + room.d + 1, \
                    (room.name, f.part_id)


def test_the_courtyard_holds_a_fountain():
    court = next(r for r in _home(True).floors[0].rooms
                 if r.name == "Courtyard")
    assert "park_fountain" in {f.part_id for f in court.furniture}


def test_the_design_is_a_library_part_beside_the_other_finished_houses():
    spec = library.PARTS["house_arab_courtyard"]
    assert spec["category"] == "Finished houses"
    assert spec["colors"] == list(house_designs.ARAB_STYLES)
    assert set(spec["sizes"]) == {"Empty (shell)", "Furnished"}
    assert library.insert_hook("house_arab_courtyard") is not None
    node = library.build_part("house_arab_courtyard",
                              dict(spec["sizes"]["Empty (shell)"],
                                   _color="Ochre render"))
    assert not validate(node)


def test_it_is_a_house_builder_template_and_an_mcp_template():
    from khervecad import mcp_schema
    assert "Arab courtyard house" in house_templates.names()
    spec = house_templates.spec("arab courtyard house")
    assert spec["roof"]["parapet"] == 1000.0
    enum = next(t for t in mcp_schema.TOOLS
                if t["name"] == "build_house")["input_schema"][
        "properties"]["template"]["enum"]
    assert set(house_templates.names()) <= set(enum)


def test_the_mcp_schema_offers_the_arched_kinds_and_the_parapet():
    from khervecad import mcp_schema
    props = next(t for t in mcp_schema.TOOLS
                 if t["name"] == "build_house")["input_schema"]["properties"]
    kinds = props["floors"]["items"]["properties"]["rooms"]["items"][
        "properties"]["openings"]["items"]["properties"]["kind"]["enum"]
    assert {"arch window", "arch door"} <= set(kinds)
    assert {"parapet", "crenellated"} <= set(props["roof"]["properties"])


def test_the_new_finishes_exist():
    from khervecad import house_finishes as F
    for name in ("Sand render", "Ochre render", "Terracotta render",
                 "Lime-washed white"):
        assert name in F.WALL_STYLES
    assert {"Walnut", "Turquoise"} <= set(F.JOINERY)
    assert F.room_kind("Gallery") == "hall"
    assert F.room_kind("Majlis") == F.room_kind("Diwan") == "living"
    assert "Flat terrace" in H.ROOF_COLORS
