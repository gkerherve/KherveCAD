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


WING_BEAST = '''union() {  // Wing Beast
  color("#884422") {  // Body
    kcad_ellipsoid(c = [0, 0, 600], r = [200, 400, 200], $fn = 12);  // Trunk
  }
  color("#884422") {  // Head
    kcad_ellipsoid(c = [0, -450, 750], r = [120, 150, 120], $fn = 12);  // Skull
    sphere(r = 30);  // Head top
  }
  color("#553311") {  // Legs
    kcad_capsule(a = [120, -250, 500], b = [120, -250, 30], r = 40, $fn = 8);  // One
    kcad_capsule(a = [-120, -250, 500], b = [-120, -250, 30], r = 40, $fn = 8);  // Two
    kcad_capsule(a = [120, 250, 500], b = [120, 250, 30], r = 40, $fn = 8);  // Three
    kcad_capsule(a = [-120, 250, 500], b = [-120, 250, 30], r = 40, $fn = 8);  // Four
  }
}'''


def test_a_name_holding_a_part_word_is_not_that_part_when_it_holds_others(app):
    # "Wing Beast" is the beast, not a wing; its Head keeps its own "Head
    # top"; and "Legs" holding four is four legs, dealt out by where each
    # stands — named, so nothing is found automatically
    c = P.build_creature(model_of(WING_BEAST), "Wing Beast")
    assert sorted(p["role"] for p in c["parts"]) == sorted(
        ["body", "head", "legFL", "legFR", "legBL", "legBR"])
    assert not c["auto_legs"]
    assert P.role_of("Legs") == "legs" and P.role_of("Front legs") == "legsF"


def test_a_built_creature_brings_its_own_game_numbers(app):
    from khervecad import creature_build
    m = DocumentModel()
    node, _spec, _parts = creature_build.build(m, {"preset": "Ogre"})
    c = P.build_creature(m, "Ogre", node=node)
    assert (c["speed"], c["health"], c["damage"], c["nature"], c["plan"]) \
        == (0.7, 50, 7, "monster", "biped")
    # ...which a caller's own numbers still override
    c = P.build_creature(m, "Ogre", node=node, speed=1.5, nature="animal")
    assert c["speed"] == 1.5 and c["nature"] == "animal"


def test_a_serpent_and_a_slime_are_not_given_legs(app):
    from khervecad import creature_build
    for preset in ("Serpent", "Slime"):
        m = DocumentModel()
        node, _spec, _parts = creature_build.build(m, {"preset": preset})
        c = P.build_creature(m, preset, node=node)
        assert not any(p["role"].startswith("leg") for p in c["parts"])
        assert "head" in {p["role"] for p in c["parts"]}


def test_list_and_remove_what_the_game_has(app, tmp_path):
    (tmp_path / "js").mkdir()
    (tmp_path / "js" / "entities.js").write_text("")
    P.export(model_of(HORSE), "Box horse", str(tmp_path))
    r = P.export(model_of(MAN), "Walker", str(tmp_path), nature="person")
    assert r["book_url"].endswith("/creatures.html#kc_walker")
    listed = P.list_creatures(str(tmp_path))["creatures"]
    assert [c["name"] for c in listed] == ["box_horse", "walker"]
    assert listed[1]["nature"] == "person" and listed[0]["legs"] == 4
    assert P.remove("kc_box_horse", str(tmp_path))["left"] == ["walker"]
    assert json.loads((tmp_path / "creatures" / "index.json").read_text()) \
        == ["walker"]
    with pytest.raises(P.PlanetCraftError):
        P.remove("dragon", str(tmp_path))
