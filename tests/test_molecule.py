"""The Compound Builder: SMILES reading, 3D shapes, the compound library,
reactions and their balance, the dialog, the Part Library parts and the
MCP tools (molecule.py, molecule_library.py, molecule_build.py,
molecule_dialog.py, library_molecule.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import mesh
from khervecad import molecule as mol
from khervecad import molecule_build as mb
from khervecad.model import validate
from khervecad.molecule_library import COMPOUNDS, get
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


def _angle(m, a, b, c):
    A, B, C = (m.atoms[k][1:] for k in (a, b, c))
    u = [A[i] - B[i] for i in range(3)]
    v = [C[i] - B[i] for i in range(3)]
    cosv = sum(x * y for x, y in zip(u, v)) / (math.hypot(*u)
                                              * math.hypot(*v))
    return math.degrees(math.acos(max(-1.0, min(1.0, cosv))))


# ------------------------------------------------------------- shapes
@pytest.mark.parametrize("key", list(COMPOUNDS))
def test_every_compound_has_its_formula_and_a_sound_shape(key):
    m = get(key)
    assert m.formula.replace(" ", "") == COMPOUNDS[key][3].replace(" ", "")
    for i, j, o in m.bonds:
        want = mol.bond_length(m.atoms[i][0], m.atoms[j][0], o)
        assert math.dist(m.atoms[i][1:], m.atoms[j][1:]) == \
            pytest.approx(want, rel=0.06), (i, j)
    bonded = {frozenset((i, j)) for i, j, _o in m.bonds}
    for i in range(len(m.atoms)):
        for j in range(i + 1, len(m.atoms)):
            if frozenset((i, j)) in bonded:
                continue
            cov = (mol.ELEMENTS[m.atoms[i][0]][0]
                   + mol.ELEMENTS[m.atoms[j][0]][0])
            assert math.dist(m.atoms[i][1:], m.atoms[j][1:]) > 0.85 * cov


def test_vsepr_shapes():
    assert _angle(get("water"), 1, 0, 2) == pytest.approx(104.5, abs=0.5)
    assert _angle(get("ammonia"), 1, 0, 2) == pytest.approx(107.0, abs=0.5)
    assert _angle(get("carbon_dioxide"), 0, 1, 2) == \
        pytest.approx(180.0, abs=0.5)
    assert _angle(get("methane"), 1, 0, 2) == pytest.approx(109.47, abs=0.5)
    xef4 = get("xenon_tetrafluoride")               # F Xe F F F
    assert sorted(round(_angle(xef4, a, 1, b)) for a, b in
                  ((0, 2), (0, 3), (0, 4), (2, 3), (2, 4), (3, 4))) == \
        [90, 90, 90, 90, 180, 180]                   # square planar
    sf6 = get("sulfur_hexafluoride")                # F S F F F F F
    fl = [0, 2, 3, 4, 5, 6]
    assert sorted({round(_angle(sf6, a, 1, b)) for a in fl for b in fl
                   if a < b}) == [90, 180]


def test_benzene_is_flat_with_even_bonds():
    b = get("benzene")
    ring = [a[1:] for a in b.atoms[:6]]
    u = [ring[1][i] - ring[0][i] for i in range(3)]
    v = [ring[2][i] - ring[0][i] for i in range(3)]
    n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
         u[0] * v[1] - u[1] * v[0]]
    n = [x / math.hypot(*n) for x in n]
    for _el, *p in b.atoms:
        assert abs(sum((p[i] - ring[0][i]) * n[i] for i in range(3))) < 0.01
    for k in range(6):
        assert math.dist(ring[k], ring[(k + 1) % 6]) == \
            pytest.approx(1.414, abs=0.01)


def test_cyclohexane_is_a_puckered_ring():
    assert _angle(get("cyclohexane"), 0, 1, 2) == pytest.approx(110, abs=4)


def test_smiles_reader():
    atoms, bonds = mol.add_hydrogens(*mol.parse_smiles("C1=CC=CC=C1"))
    assert sum(a["element"] == "H" for a in atoms) == 6
    assert mol.from_smiles("[NH4+]").formula == "H4N+"
    assert mol.from_smiles("OS(=O)(=O)O").formula == "H2O4S"
    for bad in ("C1CC", "C(C", "Xy", "C))", ""):
        with pytest.raises(mol.SmilesError):
            mol.from_smiles(bad)


def test_formulas():
    assert mol.formula_counts("Ca(OH)2") == {"Ca": 1, "O": 2, "H": 2}
    assert mol.formula_counts("CuSO4·5H2O") == {"Cu": 1, "S": 1, "O": 9,
                                                 "H": 10}
    assert mol.hill_formula({"C": 6, "H": 12, "O": 6}) == "C6H12O6"
    assert mol.hill_formula({"S": 1, "O": 4}, -2) == "O4S 2-"


# ----------------------------------------------------------- reactions
@pytest.mark.parametrize("equation, balanced", [
    ("H2 + O2 -> H2O", "2 H2 + O2 → 2 H2O"),
    ("CH4 + O2 -> CO2 + H2O", "CH4 + 2 O2 → CO2 + 2 H2O"),
    ("N2 + H2 <=> NH3", "N2 + 3 H2 ⇌ 2 H3N"),
    ("C6H12O6 + O2 -> CO2 + H2O", "C6H12O6 + 6 O2 → 6 CO2 + 6 H2O"),
    ("NH3 + HCl -> NH4+ + smiles:[Cl-]", "H3N + ClH → H4N+ + Cl-"),
])
def test_reactions_balance(equation, balanced):
    code, stats = mb.reaction_program(equation)
    assert stats["equation"] == balanced and stats["balanced"]
    root, warnings = parse_scad(code)
    assert not warnings and not validate(root)


def test_an_unbalanced_reaction_is_reported_not_hidden():
    stats = mb.reaction_program("H2 + O2 -> H2O", balance_it=False)[1]
    assert not stats["balanced"]
    assert stats["atom_balance"]["O"] == (2.0, 1.0)


def test_molecule_program_counts_what_the_view_draws():
    for style in mb.STYLES:
        code, stats = mb.molecule_program(get("caffeine"), style)
        root, warnings = parse_scad(code)
        assert not warnings and not validate(root)
        assert len(mesh.tessellate(root, fn=16)) == stats["triangles"]


def test_species_are_found_by_key_name_formula_or_smiles():
    assert mb.resolve("water").formula == "H2O"
    assert mb.resolve("H2O").key == "water"
    assert mb.resolve("NH4+").key == "ammonium"
    assert mb.resolve("SO4^2-").key == "sulfate"
    assert mb.resolve("smiles:CCO").formula == "C2H6O"
    with pytest.raises(mb.BuildError, match="smiles"):
        mb.resolve("unobtainium")


# ------------------------------------------------------ app and tools
def test_mcp_tools_and_library_parts(window):
    from khervecad import library
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(window)
    listing = ex.execute("list_molecules", {})
    assert len(listing["compounds"]) == len(COMPOUNDS)
    assert ex.execute("list_molecules", {"compound": "CO2"})["formula"] == \
        "CO2"
    out = ex.execute("build_molecule", {"smiles": "CCO", "name": "Ethanol"})
    assert window.model.unit == "nm"
    assert out["formula"] == "C2H6O" and out["objects"]
    rx = ex.execute("build_reaction", {"equation": "CH4 + O2 -> CO2 + H2O"})
    assert rx["equation"] == "CH4 + 2 O2 → CO2 + 2 H2O" and rx["objects"]
    assert "error" in ex.execute("build_molecule", {"smiles": "C1CC"})
    for key in ("water", "caffeine", "sulfur_hexafluoride"):
        assert library.build_part(f"molecule_{key}", {}).children


def test_dialog_previews_refuses_and_builds(window):
    from khervecad import molecule_dialog
    panel = molecule_dialog.open_builder(window)
    panel._refresh()
    assert panel.go.isEnabled() and "C8H10N4O2" in panel.mol_info.text()
    panel.from_smiles.setChecked(True)
    panel.smiles.setText("C1CC")                    # a ring never closed
    panel._refresh()
    assert not panel.go.isEnabled()
    panel.tabs.setCurrentIndex(1)
    panel.equation.setText("H2 + O2 -> H2O")
    panel._refresh()
    assert "2 H2 + O2 → 2 H2O" in panel.rx_info.text()
    panel.build_now()
    assert any(n.type == "component" for n in window.model.root.children)
    panel.close()
