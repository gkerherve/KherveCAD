"""Send to PlanetCraft: parts by name, legs found by themselves, the axis
turn and scale, and the creatures/ folder the game reads.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import planetcraft as P, scadparse
from khervecad.model import DocumentModel

HORSE = '''
color("#8b5a2b") translate([-300,-600,500]) cube([600,1200,500]);
color("#aa7744") translate([-200,-850,850]) cube([400,300,300]);  // Head
color("#333333") { translate([-250,-500,0]) cube([120,120,500]);
translate([130,-500,0]) cube([120,120,500]);
translate([-250,380,0]) cube([120,120,500]);
translate([130,380,0]) cube([120,120,500]); }
'''


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def model_of(code):
    m = DocumentModel()
    for n in list(scadparse.parse_scad(code)[0].children):
        m.root.add(n)
    return m


def test_named_head_and_found_legs(app):
    c = P.build_creature(model_of(HORSE), "Box horse")
    roles = {p["role"]: p for p in c["parts"]}
    assert set(roles) == {"body", "head", "legFL", "legFR", "legBL",
                          "legBR"}
    assert c["auto_legs"] and c["kind"] == "kc_box_horse"
    # real size: 1150 mm tall -> 1.15 blocks, feet on 0
    assert c["height"] == pytest.approx(1.15)
    fl = roles["legFL"]
    # a front leg is at -Z (the front) and hinges at its top (0.5 block)
    assert fl["pivot"][2] < 0 and fl["pivot"][1] == pytest.approx(0.5)
    assert fl["size"][1] == pytest.approx(0.5)
    # KherveCAD +x is the creature's left, which the game puts at -x
    assert fl["pivot"][0] < 0 < roles["legFR"]["pivot"][0]
    head = roles["head"]
    assert head["pivot"][2] < 0 and len(head["colors"]) == len(
        head["positions"])
    assert head["colors"][:3] == [pytest.approx(0xaa / 255, abs=1e-3),
                                  pytest.approx(0x77 / 255, abs=1e-3),
                                  pytest.approx(0x44 / 255, abs=1e-3)]


def test_no_legs_under_a_solid_plinth_and_height_override(app):
    c = P.build_creature(model_of("cube([1000,1000,2000]);"), "Statue",
                         height=3.0)
    assert [p["role"] for p in c["parts"]] == ["body"]
    ys = c["parts"][0]["positions"][1::3]
    assert max(ys) - min(ys) == pytest.approx(3.0)


def test_role_names():
    assert P.role_of("Front left leg") == "legFL"
    assert P.role_of("leg_BR") == "legBR"
    assert P.role_of("Leg 3") == "leg"
    assert P.role_of("Head") == "head" and P.role_of("Tail tip") == "tail"
    assert P.role_of("Left wing") == "wingL"
    assert P.role_of("Legend") is None


def test_write_to_the_game_folder(app, tmp_path):
    (tmp_path / "js").mkdir()
    (tmp_path / "js" / "entities.js").write_text("")
    r = P.export(model_of(HORSE), "Box horse", str(tmp_path))
    data = json.loads((tmp_path / "creatures" / "box_horse.json").read_text())
    assert data["format"] == "kherveCAD-creature" and data["version"] == 1
    assert json.loads((tmp_path / "creatures" / "index.json").read_text()) \
        == ["box_horse"]
    assert r["legs"] == 4
    with pytest.raises(P.PlanetCraftError):
        P.export(model_of(HORSE), "x", str(tmp_path / "nowhere"))


MAN = '''
color("#6b8e23") translate([-200,-110,850]) cube([400,220,600]);
color("#f1c27d") translate([-120,-120,1450]) cube([240,240,260]);  // Head
color("#1e2a44") translate([-185,-90,0]) cube([165,180,850]);  // Left leg
color("#1e2a44") translate([20,-90,0]) cube([165,180,850]);  // Right leg
'''


def test_legs_named_by_side_alone_keep_their_joints(app):
    # "Left leg" says a side and no end; it used to come out as legLL,
    # match no joint and be dropped, so the man arrived with no legs
    c = P.build_creature(model_of(MAN), "Walker")
    roles = {p["role"]: p for p in c["parts"]}
    legs = sorted(r for r in roles if r.startswith("leg"))
    assert len(legs) == 2 and all(r in P.ROLES for r in legs)
    # the name says the side, so the pair is one of each...
    assert {r[-1] for r in legs} == {"L", "R"}
    # ...and each swings at its hip
    assert all(roles[r]["pivot"][1] == pytest.approx(0.85) for r in legs)


def test_nature_is_written_only_when_chosen(app):
    auto = P.build_creature(model_of(MAN), "Walker")
    assert "nature" not in auto and P.summary(auto)["nature"] == "auto"
    troll = P.build_creature(model_of(MAN), "Troll", nature="monster")
    assert troll["nature"] == "monster"
    with pytest.raises(P.PlanetCraftError):
        P.build_creature(model_of(MAN), "Walker", nature="vegetable")
