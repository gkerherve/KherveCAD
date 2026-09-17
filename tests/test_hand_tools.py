"""The Hand tools library: each tool is the parts it is really made of.

A plier is two levers, a rivet and two grips; a chisel is a blade, a
handle, a ferrule and a striking cap.  These tests pin the split (so
nobody flattens a tool back into one lump), pin the shipped files to
`khervecad.tools.hand_tools` (so the generator stays the source of
truth), and check that the parts that should touch really do.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import document, library_kcad, mesh, scadparse
from khervecad.model import DocumentModel, validate
from khervecad.tools import hand_tools


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


#: what each tool is made of — the file must hold exactly these Objects
EXPECTED = {
    "Combination Pliers": ["Lever A (jaw and handle)",
                           "Lever B (jaw and handle)",
                           "Pivot rivet", "Grip A", "Grip B"],
    "Needle-Nose Pliers": ["Lever A (jaw and handle)",
                           "Lever B (jaw and handle)",
                           "Pivot rivet", "Grip A", "Grip B"],
    "Adjustable Wrench": ["Body and fixed jaw", "Sliding jaw",
                          "Worm screw", "Worm pin"],
    "Claw Hammer": ["Head", "Shaft", "Grip", "Eye wedge"],
    "Brick Bolster": ["Bolster", "Hand guard"],
    "Hand Saw": ["Blade", "Handle", "Handle screw (top)",
                 "Handle screw (middle)", "Handle screw (bottom)"],
    "Spirit Level": ["Body", "End cap (left)", "End cap (right)",
                     "Level vial", "Plumb vial"],
    "Tape Measure": ["Case", "Rubber over-mould", "Blade", "End hook",
                     "Belt clip", "Lock button"],
    "Utility Knife": ["Body", "Rubber over-mould", "Blade slider",
                      "Blade"],
    "Wood Chisel 25 mm": ["Blade", "Handle", "Ferrule", "Striking cap"],
    "Phillips Screwdriver PH2": ["Handle", "Grip cap", "Ferrule",
                                 "Blade"],
}

#: a combination spanner is one forging and a cold chisel one bar —
#: these must NOT be split
ONE_PIECE = ["Combination Spanner 13 mm", "Cold Chisel"]


def _objects(stem):
    doc = DocumentModel()
    document.load_kcad(doc, str(hand_tools.folder() / f"{stem}.kcad"))
    return doc, [c for c in doc.root.children if c.type == "component"]


@pytest.mark.parametrize("stem", sorted(EXPECTED))
def test_tool_ships_the_parts_it_is_made_of(app, stem):
    _doc, parts = _objects(stem)
    assert [p.name for p in parts] == EXPECTED[stem]


@pytest.mark.parametrize("stem", ONE_PIECE)
def test_a_single_forging_stays_one_object(app, stem):
    _doc, parts = _objects(stem)
    assert len(parts) == 1


@pytest.mark.parametrize("stem", sorted(hand_tools.programs()))
def test_every_part_has_geometry_and_no_errors(app, stem):
    doc, parts = _objects(stem)
    assert validate(doc.root) == {}
    assert len(parts) >= 2, f"{stem} is still one lump"
    for part in parts:
        assert mesh.tessellate(part), f"{stem}: {part.name} previews empty"


@pytest.mark.parametrize("stem", sorted(hand_tools.programs()))
def test_the_shipped_file_matches_the_generator(app, stem, tmp_path):
    hand_tools.write(stem, hand_tools.programs()[stem],
                     tmp_path / f"{stem}.kcad")
    fresh = (tmp_path / f"{stem}.kcad").read_text()
    shipped = (hand_tools.folder() / f"{stem}.kcad").read_text()
    assert fresh == shipped, f"{stem}.kcad is out of step with hand_tools"


@pytest.mark.parametrize("stem", hand_tools.SOCKET_SETS)
def test_a_socket_set_holds_one_object_per_socket(app, stem):
    _doc, parts = _objects(stem)
    names = [p.name for p in parts]
    assert names[0] == "Storage rail"
    assert sum(1 for n in names if n.startswith("Socket ")) >= 10
    for wanted in ("Extension bar", "Ratchet body", "Drive anvil",
                   "Reverse lever", "Ratchet grip"):
        assert wanted in names, (stem, wanted)


def test_every_tool_program_parses_without_a_warning(app):
    for stem, text in hand_tools.programs().items():
        _root, warnings = scadparse.parse_scad(text)
        assert warnings == [], (stem, warnings)


def _bounds(node, beyond_x=None):
    """The node's extent, optionally over the part of it past *beyond_x*
    — the blade of a chisel, the jaw of a plier."""
    tris = mesh.tessellate(node)
    pts = [p for tri in tris for p in tri
           if beyond_x is None or p[0] >= beyond_x]
    return [(min(p[i] for p in pts), max(p[i] for p in pts))
            for i in range(3)]


@pytest.mark.parametrize("stem", ["Combination Pliers",
                                  "Needle-Nose Pliers"])
def test_the_two_plier_jaws_close_on_the_centre_line(app, stem):
    _doc, parts = _objects(stem)
    by_name = {p.name: p for p in parts}
    a, b = (by_name["Lever A (jaw and handle)"],
            by_name["Lever B (jaw and handle)"])
    # each lever reaches the jaw tip
    assert _bounds(a)[0][1] > 40 and _bounds(b)[0][1] > 40
    # past the pivot boss the jaws are on opposite sides of y = 0 and
    # meet on it — that face is what grips
    jaw_a, jaw_b = _bounds(a, 20)[1], _bounds(b, 20)[1]
    assert jaw_a[0] > -0.01 and jaw_a[1] > 1
    assert jaw_b[1] < 0.01 and jaw_b[0] < -1
    # the levers cross: each handle runs down the other jaw's side
    assert _bounds(a)[1][0] < -10 and _bounds(b)[1][1] > 10


def test_the_chisel_blade_grows_with_its_width(app):
    narrow = _bounds({p.name: p for p in _objects("Wood Chisel 6 mm")[1]}
                     ["Blade"], 50)
    wide = _bounds({p.name: p for p in _objects("Wood Chisel 32 mm")[1]}
                   ["Blade"], 50)
    assert round(narrow[1][1] - narrow[1][0]) == 6
    assert round(wide[1][1] - wide[1][0]) == 32


def test_the_tools_are_all_in_the_hand_tools_menu():
    for stem in list(hand_tools.programs()) + hand_tools.SOCKET_SETS:
        assert library_kcad.tool_group(library_kcad.label(stem)) != "Other"
