"""Parts for 3D printing (library_print.py): every part builds, is
valid, previews, round-trips as code, and sits where it should."""

import pytest

from khervecad import analysis, library, library_groups, library_print, mesh
from khervecad.model import DocumentModel, validate
from khervecad.scadparse import parse_scad


@pytest.mark.parametrize("part_id", sorted(library_print.PARTS))
def test_part_builds_valid_and_round_trips(part_id):
    model = DocumentModel()
    model.root.add(library.build_part(part_id, {}))
    assert validate(model.root) == {}
    assert mesh.tessellate(model.root)
    code = model.to_scad()
    again = DocumentModel()
    again.root, warnings = parse_scad(code)
    assert not warnings
    assert again.to_scad() == code


def test_parts_are_in_the_library_menu():
    placed = set()
    for _title, entries in library_groups.SECTIONS:
        for _name, _icon, spec in entries:
            placed.update(library_groups.entry_categories(
                spec, list({p["category"] for p in library.PARTS.values()}))[1])
    for spec in library_print.PARTS.values():
        assert spec["category"] in placed


def test_gridfinity_bin_matches_the_grid():
    node = library.build_part("gridfinity_bin", dict(units_x=2, units_y=1,
                                                     units_z=6))
    box = analysis.mass_properties(mesh.tessellate(node))
    assert box["min"][0] == pytest.approx(0.25)
    assert box["max"][0] == pytest.approx(2 * 42 - 0.25)
    assert box["max"][2] == pytest.approx(6 * 7)


def test_tray_compartments_follow_the_counts():
    node = library.build_part("print_tray", dict(cols=3, rows=2))
    assert sum(1 for n in node.walk() if n.type == "linear_extrude"
               and n.name.startswith("Compartment")) == 6
