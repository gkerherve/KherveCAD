"""Lab and company furniture (library_lab.py) and the building templates
(house_templates.py): every part builds on the floor at true size, the
templates build with nothing outside its room and every bench piece on
a bench, the builder's Template menu and build_house ``template``.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import house as H
from khervecad import house_templates as T
from khervecad import library, library_lab, mesh


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(900, 700)
    return win


@pytest.mark.parametrize("part_id", sorted(library_lab.PARTS))
def test_part_builds_light_and_on_the_floor(app, part_id):
    assert part_id in library.PARTS            # registered via home_extra
    spec = library.PARTS[part_id]
    tris = mesh.tessellate(library.build_part(part_id, {}), fn=12)
    assert 0 < len(tris) < 15000
    zs = [p[2] for t in tris for p in t]
    if not spec.get("rest_z"):                 # wall pieces hang
        assert min(zs) == pytest.approx(0.0, abs=15.0), part_id
    for size in spec["sizes"]:
        assert library.build_part(part_id, {"_size": size}).children


def test_catalogue_lists_only_real_parts():
    for section, ids in H.FURNITURE_CATALOG.items():
        for pid in ids:
            assert pid in library.PARTS, (section, pid)
    for room in ("Chemistry lab", "Physics lab", "Open-plan office",
                 "Meeting room", "Server room"):
        assert room in H.ROOM_TYPES


@pytest.mark.parametrize("name", T.names())
def test_template_builds_furnished(app, name):
    house = H.house_from_spec(T.spec(name))
    floor = house.floors[0]
    assert len(floor.rooms) >= 4 and H.collect_walls(floor)
    count = 0
    for spec_floor, built in zip(T.spec(name)["floors"], house.floors):
        for spec_room, room in zip(spec_floor["rooms"], built.rooms):
            # every piece the spec lists is built: none silently dropped
            assert len(room.furniture) == len(spec_room["furniture"]), \
                room.name
            for fs, f in zip(spec_room["furniture"], room.furniture):
                count += 1
                assert room.x <= f.x <= room.x + room.w, (room.name, f.part_id)
                assert room.y <= f.y <= room.y + room.d, (room.name, f.part_id)
                if fs.get("on_top"):          # landed on a bench or desk
                    assert f.z > 500, (room.name, f.part_id)
    # the smallest design (a 1-bedroom bungalow) is 18 pieces over all
    # floors; the old "> 20" counted the ground floor only, which a
    # two-storey house's bedrooms are not on
    assert count >= 15
    tris = mesh.tessellate(H.build_floor(floor, True), fn=12)
    assert len(tris) < 150_000


def test_expand_keeps_callers_keys():
    params = T.expand({"template": "company office",
                       "roof": {"style": "Flat"}})
    assert params["floors"] and params["roof"] == {"style": "Flat"}
    assert "template" not in params
    with pytest.raises(KeyError):
        T.spec("Castle")


def test_mcp_and_builder_template(window):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(window)
    dry = ex.execute("build_house", {"template": "Physics lab",
                                     "dry_run": True})
    assert dry["dry_run"] and len(dry["floors"][0]["rooms"]) == 4
    assert "error" in ex.execute("build_house", {"template": "Castle"})
    from khervecad import house_dialog
    panel = house_dialog.open_builder(window)
    assert panel.load_template("Chemistry lab", ask=False)
    names = [r.name for r in panel.house.floors[0].rooms]
    assert "Chemistry lab" in names and "Chemical store" in names
    assert house_dialog._guess_category("Laser lab") == "Physics lab"
