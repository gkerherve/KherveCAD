"""The Protein Builder: peptides built from a sequence, PDB and mmCIF
reading and writing, secondary structure, the cartoon and atom programs,
the Compound Builder's Protein tab, the Part Library presets and the MCP
tools (protein.py, protein_build.py, protein_dialog.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import io
import json
import math

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import mesh
from khervecad import protein as P
from khervecad import protein_build as PB
from khervecad.model import validate
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


def _xyz(p, r, name):
    return p.atoms[r.atoms[name]].xyz


# -------------------------------------------------------------- building
def test_helix_has_textbook_geometry():
    p = P.build_peptide("ACDEFGHIKLMNPQRSTVWY", "helix")
    res = p.residues()
    assert p.sequence() == "ACDEFGHIKLMNPQRSTVWY"
    for i in range(1, len(res) - 1):
        r, prev, nxt = res[i], res[i - 1], res[i + 1]
        phi = P.torsion(_xyz(p, prev, "C"), _xyz(p, r, "N"),
                        _xyz(p, r, "CA"), _xyz(p, r, "C"))
        psi = P.torsion(_xyz(p, r, "N"), _xyz(p, r, "CA"), _xyz(p, r, "C"),
                        _xyz(p, nxt, "N"))
        omega = P.torsion(_xyz(p, r, "CA"), _xyz(p, r, "C"),
                          _xyz(p, nxt, "N"), _xyz(p, nxt, "CA"))
        want_phi = -65.0 if r.letter == "P" else -57.0
        assert phi == pytest.approx(want_phi, abs=1e-6)
        assert psi == pytest.approx(-47.0, abs=1e-6)
        assert abs(abs(omega) - 180.0) < 1e-6
    for i in range(len(res) - 4):
        # the i -> i+4 hydrogen bond and the 3.6-residue turn
        if res[i + 4].letter != "P":
            assert 2.7 < math.dist(_xyz(p, res[i], "O"),
                                   _xyz(p, res[i + 4], "N")) < 3.3
        assert 5.9 < math.dist(_xyz(p, res[i], "CA"),
                               _xyz(p, res[i + 4], "CA")) < 6.6


def test_every_residue_is_l_and_every_bond_sound():
    p = P.build_peptide("ACDEFGHIKLMNPQRSTVWY" * 2, "strand")
    for r in p.residues():
        if r.letter == "G":
            continue
        # PeptideBuilder's L convention: N-C-CA-CB = +122.7
        assert P.torsion(_xyz(p, r, "N"), _xyz(p, r, "C"), _xyz(p, r, "CA"),
                         _xyz(p, r, "CB")) == pytest.approx(122.7, abs=1.5)
    for i, j in p.bonds:
        d = math.dist(p.atoms[i].xyz, p.atoms[j].xyz)
        assert 1.15 < d < 1.9, (p.atoms[i].name, p.atoms[j].name, d)
    # ring closures come out at a bond length, not merely "near"
    names = {(p.atoms[i].resname, p.atoms[i].name, p.atoms[j].name)
             for i, j in p.bonds}
    assert ("PRO", "CD", "N") in names and ("TRP", "NE1", "CE2") in names


def test_side_chains_pick_rotamers_that_clear_the_helix():
    p = P.build_peptide("ACDEFGHIKLMNQRSTVWY" * 2, "helix")
    assert P.clashes(p) == 0
    assert p.summary()["helix_residues"] == 38


def test_hairpin_strands_pair_up():
    p = PB.preset("beta_hairpin")
    res = p.residues()
    n = len(res)
    for i in range(5):
        assert 3.5 < math.dist(_xyz(p, res[i], "CA"),
                               _xyz(p, res[n - 1 - i], "CA")) < 6.0
    assert P.clashes(p) <= 3


@pytest.mark.parametrize("text, message", [
    ("ACDB", "Not an amino-acid"), ("", "empty"),
])
def test_bad_sequences_say_why(text, message):
    with pytest.raises(P.ProteinError, match=message):
        P.build_peptide(text)


def test_secondary_words_letters_and_padding():
    assert P.clean_secondary("strand", 3) == "EEE"
    assert P.clean_secondary("hht", 5) == "HHTCC"
    with pytest.raises(P.ProteinError):
        P.clean_secondary("HHZ", 3)
    with pytest.raises(P.ProteinError):
        P.clean_secondary("HHHH", 3)
    assert P.clean_sequence(">sp|X\nACD EF\n*") == "ACDEF"


# ------------------------------------------------------------- reading
def test_pdb_round_trip_keeps_atoms_bonds_and_structure():
    p = P.build_peptide("SWTWENGKWTWKAAAAAAAAA", "CEEEETTEEEECHHHHHHHHC")
    q = P.parse_pdb(P.to_pdb(p))
    assert [(a.name, a.element, a.resname, a.resseq) for a in q.atoms] == \
        [(a.name, a.element, a.resname, a.resseq) for a in p.atoms]
    assert all(math.dist(a.xyz, b.xyz) < 1e-3
               for a, b in zip(p.atoms, q.atoms))
    assert q.secondary == p.secondary
    assert {frozenset(b) for b in q.bonds} == {frozenset(b)
                                              for b in p.bonds}


def test_geometry_finds_helix_and_strands_without_records():
    helix = P.build_peptide("A" * 16, "helix")
    q = P.parse_pdb("\n".join(ln for ln in P.to_pdb(helix).splitlines()
                              if not ln.startswith("HELIX")))
    assert sum(1 for s in q.secondary.values() if s == "H") >= 14
    hairpin = PB.preset("beta_hairpin")
    assert set(P.assign_secondary(hairpin).values()) <= {"E"}


MMCIF = """data_TEST
_entry.id TEST
_struct.title 'A test peptide'
loop_
_struct_conf.conf_type_id
_struct_conf.beg_auth_asym_id
_struct_conf.beg_auth_seq_id
_struct_conf.end_auth_asym_id
_struct_conf.end_auth_seq_id
HELX_P B 1 B 4
loop_
_atom_site.group_PDB
_atom_site.id
_atom_site.type_symbol
_atom_site.label_atom_id
_atom_site.label_alt_id
_atom_site.label_comp_id
_atom_site.label_asym_id
_atom_site.label_seq_id
_atom_site.pdbx_PDB_ins_code
_atom_site.Cartn_x
_atom_site.Cartn_y
_atom_site.Cartn_z
_atom_site.auth_seq_id
_atom_site.auth_comp_id
_atom_site.auth_asym_id
_atom_site.auth_atom_id
_atom_site.pdbx_PDB_model_num
"""


def _cif_rows(p):
    rows = []
    for k, a in enumerate(p.atoms, 1):
        rows.append(f"{'HETATM' if a.hetero else 'ATOM'} {k} {a.element} "
                    f"\"{a.name}\" . {a.resname} X {a.resseq} ? {a.x:.3f} "
                    f"{a.y:.3f} {a.z:.3f} {a.resseq} {a.resname} B "
                    f"{a.name} 1")
    rows.append("ATOM 999 C CA B GLY X 9 ? 0 0 0 9 GLY B CA 1")  # altloc B
    rows.append("ATOM 998 C CA . GLY X 9 ? 0 0 0 9 GLY B CA 2")  # model 2
    return "\n".join(rows) + "\n#\n"


def test_mmcif_reads_atoms_titles_and_helices():
    p = P.build_peptide("ACDEFG", "helix")
    q = P.parse_text(MMCIF + _cif_rows(p))
    assert q.name == "A Test Peptide"
    assert len(q.atoms) == len(p.atoms)            # altloc B, model 2 out
    assert q.chains() == ["B"] and q.sequence() == "ACDEFG"
    assert [q.secondary.get(("B", i, "")) for i in range(1, 6)] == \
        ["H", "H", "H", "H", None]


def test_ligands_water_and_disulfides_bond_by_distance():
    p = P.build_peptide("CAAAC", "coil")
    text = P.to_pdb(p).replace("END\n", "")
    sg = [a for a in p.atoms if a.name == "SG"][0]
    text += (f"HETATM 9001  O   HOH W   1    {sg.x + 20:8.3f}{sg.y:8.3f}"
             f"{sg.z:8.3f}  1.00  0.00           O\n"
             f"HETATM 9002 ZN    ZN Z   1    {sg.x:8.3f}{sg.y + 2.3:8.3f}"
             f"{sg.z:8.3f}  1.00  0.00          ZN\nEND\n")
    q = P.parse_pdb(text)
    s = q.summary()
    assert s["ligands"] == ["ZN"] and s["waters"] == 1
    zn = [i for i, a in enumerate(q.atoms) if a.element == "Zn"][0]
    assert any(zn in b for b in q.bonds)             # Zn-S by distance


def test_fetch_uses_the_cache_and_the_injected_opener(tmp_path,
                                                      monkeypatch):
    monkeypatch.setattr(P, "cache_dir", lambda: str(tmp_path))
    pdb = P.to_pdb(P.build_peptide("ACDEFGHIK", "helix"))
    cif = MMCIF + _cif_rows(P.build_peptide("ACDEFG", "helix"))
    calls = []

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def opener(req, timeout=60):
        url = req.full_url
        calls.append(url)
        if "rcsb" in url:
            return Response(cif.encode())
        if url.endswith("/P69905"):
            return Response(json.dumps([{
                "pdbUrl": "https://alphafold.example/AF-P69905.pdb"}])
                .encode())
        return Response(pdb.encode())

    p = P.fetch(pdb_id="1abc", opener=opener)
    assert p.source == "PDB 1ABC" and p.sequence() == "ACDEFG"
    P.fetch(pdb_id="1ABC", opener=opener)
    assert len(calls) == 1                                   # cached
    af = P.fetch(uniprot="p69905", opener=opener)
    assert af.sequence() == "ACDEFGHIK" and len(calls) == 3
    with pytest.raises(P.ProteinError, match="not a PDB ID"):
        P.fetch(pdb_id="crambin")

    def broken(req, timeout=60):
        raise OSError("offline")

    with pytest.raises(P.ProteinError, match="offline"):
        P.fetch(pdb_id="9XYZ", opener=broken)


# ------------------------------------------------------------ programs
@pytest.mark.parametrize("style", PB.STYLES)
def test_every_style_parses_validates_and_counts_its_triangles(style):
    p = PB.preset("beta_hairpin")
    code, stats = PB.protein_program(p, style)
    root, warnings = parse_scad(code)
    assert not warnings
    assert validate(root) == {}
    assert len(mesh.tessellate(root)) == stats["triangles"]
    coloured = mesh.tessellate_colored(root)
    xs = [v[0] for tri, _c in coloured for v in tri]
    assert max(xs) - min(xs) > 1.0                 # nm: not all at 0


@pytest.mark.parametrize("colour", PB.COLOURS)
def test_every_colour_scheme_builds(colour):
    code, _stats = PB.protein_program(PB.preset("melittin"), "cartoon",
                                      colour)
    assert code.count("polyhedron(") >= 1


def test_cartoon_draws_helix_ribbons_and_strand_arrows():
    p = P.build_peptide("A" * 30, "C" * 3 + "H" * 12 + "C" * 3 + "E" * 9
                        + "CCC")
    code, stats = PB.protein_program(p, "cartoon")
    assert f'color("{PB.SS_COLOURS["H"]}")' in code
    assert f'color("{PB.SS_COLOURS["E"]}")' in code
    assert stats["ribbons"] >= 5          # coil, helix, coil, strand, coil
    root, _w = parse_scad(code)
    pts = [v for tri in mesh.tessellate(root) for v in tri]
    assert len(pts) > 0


def test_chain_selection_and_errors():
    p = P.build_peptide("ACDEF", "helix", chain="A")
    q = P.build_peptide("GHIKL", "helix", chain="B")
    both = P.parse_pdb(P.to_pdb(p) + P.to_pdb(q))
    code, stats = PB.protein_program(both, "cartoon", chains="B")
    assert stats["drawn_residues"] == 5 and "Chain B" in code
    with pytest.raises(PB.BuildError, match="No chain C"):
        PB.protein_program(both, chains="C")
    with pytest.raises(PB.BuildError, match="style"):
        PB.protein_program(both, "ribbons")


def test_the_budget_refuses_huge_atom_models(monkeypatch):
    monkeypatch.setattr(PB, "BUDGET", 1000)
    with pytest.raises(PB.BuildError, match="cartoon"):
        PB.protein_program(PB.preset("melittin"), "space_filling")


# ----------------------------------------------------------- the window
def test_build_protein_tool_adds_one_object_in_nanometres(window):
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(window)
    out = ex.execute("build_protein", {"preset": "alpha_helix"})
    assert window.model.unit == "nm"
    assert len(out["objects"]) == 1
    assert out["residues"] == 20 and out["clashes"] == 0
    dry = ex.execute("build_protein", {"sequence": "GIGAVLK",
                                       "secondary": "helix",
                                       "style": "ball_and_stick",
                                       "dry_run": True})
    assert dry["dry_run"] and dry["colour"] == "element"
    listing = ex.execute("list_proteins", {})
    assert "beta_hairpin" in {p["key"] for p in listing["presets"]}


def test_protein_parts_are_in_the_part_library():
    from khervecad import library
    ids = [k for k in library.PARTS if k.startswith("protein_")]
    assert len(ids) == len(PB.PRESETS)
    group = library.build_part("protein_beta_hairpin", {})
    assert group.children


def test_protein_tab_previews_and_builds(window, app):
    from khervecad import molecule_dialog
    panel = molecule_dialog.open_builder(window)
    panel.tabs.setCurrentIndex(2)
    tab = panel.protein_tab
    tab.source.setCurrentIndex(1)                      # sequence
    tab.sequence.setPlainText("SWTWENGKWTWK")
    tab.secondary.setText("CEEEETTEEEEC")
    panel._refresh()
    assert panel.go.isEnabled()
    assert "12 residues" in tab.info.text()
    tab.source.setCurrentIndex(2)                      # PDB, not fetched
    panel._refresh()
    assert not panel.go.isEnabled() and "Fetch" in tab.info.text()
    tab.source.setCurrentIndex(0)
    panel._refresh()
    panel.build_now()
    assert any(c.type == "component" for c in window.model.root.children)
    panel.close()
