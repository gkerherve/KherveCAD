"""Per-object finishes (part_finish) and shape-built objects
(custom_part).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""
import pytest

from khervecad import custom_part, house as H, library
from khervecad import part_finish as F


def _looks(node):
    return {c.name: (c.params["color"], c.params["material"])
            for c in node.walk() if c.type == "color"}


def test_a_finish_repaints_only_the_named_components():
    dims = F.add(library.default_dims("home_coffee_table"),
                 {"part": "top", "color": "#EEEEEE", "material": "marble"})
    look = _looks(library.build_part("home_coffee_table", dims))
    assert look["Top"] == ("#eeeeee", "Marble")
    assert look["Shelf"][1] == "Wood" and look["Leg"][1] == "Metal"


def test_a_later_finish_for_the_same_component_replaces_it():
    dims = F.add({}, {"part": "Top", "color": "#111111"})
    dims = F.add(dims, {"part": "top", "color": "#222222"})
    dims = F.add(dims, {"material": "Velvet"})
    assert dims["_finish"] == [{"part": "top", "color": "#222222"},
                               {"material": "Velvet"}]
    assert "_finish" not in F.clear(dims)


@pytest.mark.parametrize("bad", [{}, {"color": "red"},
                                 {"material": "Tweed"}])
def test_a_bad_finish_is_refused(bad):
    with pytest.raises(F.FinishError):
        F.check(bad)


def test_a_finish_survives_the_house_spec():
    dims = F.add(H.part_dims("home_sofa"), {"material": "Leather"})
    spec = {"floors": [{"name": "Ground", "rooms": [
        {"name": "Living room", "x": 0, "y": 0, "w": 5000, "d": 4000,
         "furniture": [{"part_id": "home_sofa", "x": 2500, "y": 2000,
                        "dims": dims}]}]}]}
    again = H.house_to_spec(H.house_from_spec(spec))
    f = again["floors"][0]["rooms"][0]["furniture"][0]
    assert f["dims"]["_finish"] == [{"material": "Leather"}]


def test_a_custom_object_builds_from_its_shapes():
    shapes = [{"shape": "box", "name": "Top", "x": -400, "y": -200,
               "z": 700, "w": 800, "d": 400, "h": 40, "r": 5,
               "material": "wood", "color": "#8A5A3A"},
              {"shape": "rod", "a": [0, 0, 0], "b": [0, 0, 700], "r": 20},
              {"shape": "cylinder", "x": 0, "y": 0, "z": 0, "h": 10,
               "r": 200, "r2": 150},
              {"shape": "sphere", "x": 0, "y": 0, "z": 760, "r": 30}]
    node = library.build_part(custom_part.PART_ID,
                              {custom_part.KEY: shapes})
    look = _looks(node)
    assert look["Top"] == ("#8a5a3a", "Wood")
    assert set(look) == {"Top", "Rod", "Cylinder", "Sphere"}


@pytest.mark.parametrize("bad", [[], [{"shape": "torus"}],
                                 [{"shape": "box", "x": 0}],
                                 [{"shape": "sphere", "x": 0, "y": 0,
                                   "z": 0, "r": -1}],
                                 [{"shape": "rod", "a": [0, 0], "b":
                                   [0, 0, 1], "r": 1}]])
def test_bad_shapes_are_refused(bad):
    with pytest.raises(custom_part.ShapeError):
        custom_part.clean(bad)
