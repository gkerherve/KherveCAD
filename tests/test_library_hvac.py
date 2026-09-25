"""Air conditioning library (library_hvac.py): the indoor and outdoor
split-system units, and the piped-together split system that connects
them through a wall.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest

from khervecad import house as H
from khervecad import library, library_groups
from khervecad import library_hvac as A
from khervecad import mesh
from khervecad.model import validate


@pytest.mark.parametrize("pid", list(A.PARTS))
def test_every_part_builds_clean_in_every_size(pid):
    spec = library.PARTS[pid]
    for size in spec["sizes"]:
        node = spec["build"]({"_size": size})
        assert not validate(node), (pid, size)
        assert mesh.tessellate(node), (pid, size)


def test_the_three_lines_form_one_continuous_path_wall_to_ground():
    # wall -> drop -> run must join end to end (a gap would mean
    # build_split_system fell out of step with _indoor_ports /
    # _outdoor_ports), starting at the indoor unit's mounting height
    # and ending at the outdoor unit's, near the ground
    node = library.PARTS["hvac_split_system"]["build"]({})
    caps = {n.name: n.params for n in node.walk() if n.type == "capsule"}
    for key in ("Liquid", "Gas", "Drain"):
        wall = caps[f"{key} line (wall)"]
        drop = caps[f"{key} line (drop)"]
        run = caps[f"{key} line (run)"]
        for a, b in ((wall, drop), (drop, run)):
            assert (a["x2"], a["y2"], a["z2"]) == pytest.approx(
                (b["x1"], b["y1"], b["z1"]), abs=0.01)
        assert wall["z1"] > 1500.0            # starts high, indoors
        assert run["z2"] < 500.0              # ends low, outdoors


def test_split_system_pipe_crosses_the_full_wall_thickness():
    node = library.PARTS["hvac_split_system"]["build"](
        {"wall_thickness": 300.0})
    caps = {n.name: n.params for n in node.walk() if n.type == "capsule"}
    through = caps["Liquid line (wall)"]
    assert through["y2"] - through["y1"] == pytest.approx(300.0, abs=0.01)


def test_air_conditioning_has_its_own_library_menu():
    sub = {name: cats for section in library_groups.SECTIONS
           for name, _icon, cats in section[1]}
    assert sub["Air conditioning"] == ["Air conditioning"]


def test_indoor_unit_hangs_near_the_ceiling_and_outdoor_stands_on_it():
    assert H.part_rest_z("hvac_indoor_unit") > 1500.0
    assert H.part_rest_z("hvac_outdoor_unit") == 0.0


def test_units_are_offered_in_the_house_builder_catalogue():
    assert "hvac_indoor_unit" in H.FURNITURE_CATALOG["Utility / laundry"]
    assert ("hvac_outdoor_unit"
            in H.FURNITURE_CATALOG["Garden / outdoor"])
