"""build_creature: monsters for PlanetCraft, every piece in its joint.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest

from khervecad import creature_build as CB, planetcraft as P
from khervecad.model import DocumentModel

#: what each plan must arrive in the game with
JOINTS = {
    "biped": {"head", "legs2"},
    "winged": {"head", "legs2", "wingL", "wingR"},
    "quadruped": {"head", "legs4"},
    "spider": {"head", "legs4"},
    "serpent": {"head", "tail", "legs0"},
    "slime": {"head", "legs0"},
}


def _send(params):
    m = DocumentModel()
    node, spec, parts = CB.build(m, params)
    return P.build_creature(m, spec["name"], node=node), spec, node


@pytest.mark.parametrize("preset", list(CB.PRESETS))
def test_every_preset_arrives_jointed_and_at_its_real_height(preset):
    c, spec, _node = _send({"preset": preset})
    roles = {p["role"] for p in c["parts"]}
    legs = sum(1 for r in roles if r.startswith("leg"))
    for want in JOINTS[spec["plan"]]:
        if want.startswith("legs"):
            assert legs == int(want[4:]), (preset, roles)
        else:
            assert want in roles, (preset, roles)
    assert "body" in roles and not c["auto_legs"]
    assert c["height"] == pytest.approx(spec["height"] / 1000, rel=0.02)
    assert c["triangles"] < 20000
    assert c["nature"] == CB.PRESETS[preset]["nature"]


def test_nothing_in_the_body_is_named_like_a_joint():
    # a piece of the body called "Tail spikes" would be taken for the tail
    for preset in CB.PRESETS:
        m = DocumentModel()
        node, _spec, _parts = CB.build(m, {"preset": preset})
        for part in node.walk():
            if P.role_of(part.name):
                for inner in part.walk():
                    if inner is part:
                        continue
                    r = P.role_of(inner.name)
                    assert r is None or P._family(r) == P._family(
                        P.role_of(part.name)), (preset, part.name, inner.name)


def test_features_override_a_preset():
    c, spec, node = _send({"preset": "Troll", "name": "Frost troll",
                           "horns": "ram", "height": 3000,
                           "skin": "#e8f4fb"})
    assert c["kind"] == "kc_frost_troll" and c["height"] == pytest.approx(3.0)
    assert node.params["creature"]["preset"] == "Troll"
    code, _s, _p = CB.program({"preset": "Troll", "horns": "ram"})
    assert "Left horn" in code and "#7d8f62" in code


def test_a_plan_on_its_own_builds():
    for plan in CB.PLANS:
        c, spec, _node = _send({"plan": plan, "name": f"Test {plan}"})
        assert c["parts"] and spec["plan"] == plan


def test_bad_specs_are_refused_with_the_choices():
    for bad in ({"plan": "octopus"}, {"preset": "Unicorn"},
                {"preset": "Troll", "horns": "antlers"},
                {"preset": "Troll", "height": 50}):
        with pytest.raises(CB.CreatureError):
            CB.program(bad)


def test_options_and_the_library():
    opts = CB.options()
    assert set(opts["presets"]) == set(CB.PRESETS) and "biped" in opts["plans"]
    from khervecad import library
    ours = [k for k, v in library.PARTS.items() if v["category"] == "Monsters"]
    assert len(ours) == len(CB.PRESETS)
    node = library.PARTS["monster_dragon"]["build"]({})
    assert node.params["creature"]["plan"] == "quadruped"
