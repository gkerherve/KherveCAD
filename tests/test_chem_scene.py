"""The Chemistry Builder's structure: building, measuring, editing,
doping and whole polyhedra (chem_scene)."""

import pytest

from khervecad import chem_scene as cs


def test_water_measures_its_bond_and_angle():
    s = cs.compound_scene("water")
    o = next(i for i, a in enumerate(s.atoms) if a[0] == "O")
    h1, h2 = [i for i, a in enumerate(s.atoms) if a[0] == "H"]
    assert cs.measure(s, [o, h1])["value"] == pytest.approx(0.96, abs=0.05)
    assert cs.measure(s, [h1, o, h2])["value"] == pytest.approx(104.5,
                                                                abs=2)


def test_torsion_of_ethane_is_staggered():
    s = cs.compound_scene("CC")
    c1, c2 = [i for i, a in enumerate(s.atoms) if a[0] == "C"]
    h1 = next(j for j in s.neighbours(c1) if s.atoms[j][0] == "H")
    h2 = next(j for j in s.neighbours(c2) if s.atoms[j][0] == "H")
    t = abs(cs.measure(s, [h1, c1, c2, h2])["value"])
    assert min(abs(t - 60), abs(t - 180)) < 10


def test_editing_reindexes_bonds():
    s = cs.compound_scene("CCO")
    n = len(s.atoms)
    new = cs.place_bonded(s, "Cl", 0)
    assert len(s.atoms) == n + 1 and [0, new, 1] in s.bonds
    cs.delete_atoms(s, [0])
    assert all(max(i, j) < len(s.atoms) for i, j, _o in s.bonds)


def test_a_crystal_block_and_its_bonds():
    s = cs.crystal_scene("nacl", (2, 2, 2))
    comp = s.composition()
    assert comp["Na"] + comp["Cl"] == 125      # 5x5x5 sites of a 2^3 block
    assert s.bonds and len(s.edges) == 12


def test_doping_is_reproducible():
    a = cs.crystal_scene("rutile", (3, 3, 3), dope="Ti:Zr:0.25", seed=3)
    b = cs.crystal_scene("rutile", (3, 3, 3), dope="Ti:Zr:0.25", seed=3)
    assert a.atoms == b.atoms
    ti, zr = a.composition()["Ti"], a.composition()["Zr"]
    assert zr == round((ti + zr) * 0.25)
    with pytest.raises(cs.BuildError):
        cs.parse_dope("Xx:Mo:0.1")


def test_whole_polyhedra_at_a_surface_cut():
    plain = cs.surface_scene("rutile", "110", (2, 2), 2)
    whole = cs.surface_scene("rutile", "110", (2, 2), 2, complete=True)
    ti = whole.composition()["Ti"]
    # every Ti keeps its six oxygens
    for i, a in enumerate(whole.atoms):
        if a[0] == "Ti":
            near = [j for j, b in enumerate(whole.atoms) if b[0] == "O"
                    and cs.distance(whole, i, j) < 2.2]
            assert len(near) == 6
    assert whole.composition()["O"] >= plain.composition()["O"]
    assert ti == plain.composition()["Ti"]


def test_properties_rows():
    rows = dict(cs.properties(cs.compound_scene("water")))
    assert rows["Formula"] == "H2O" and "g/mol" in rows["Molar mass"]


# ---------------------------------------------------------------- files
def test_every_format_writes_and_a_cif_reads_back(tmp_path):
    from khervecad import chem_io, cifread
    s = cs.crystal_scene("nacl", (1, 1, 1))
    for ext in ("xyz", "mol", "sdf", "pdb", "cif"):
        out = chem_io.export(s, str(tmp_path / f"nacl.{ext}"))
        assert out["atoms"] == len(s.atoms) and out["bytes"] > 0
    back = cifread.read_cif(str(tmp_path / "nacl.cif"))
    assert back.composition() == {"Na": 4, "Cl": 4}
    assert back.a == pytest.approx(5.64, abs=0.01)
    water = cs.compound_scene("water")
    assert chem_io.xyz_text(water).splitlines()[0] == "3"
    with pytest.raises(cs.BuildError, match="cell"):
        chem_io.cif_text(water)


# --------------------------------------------------- molecules on a slab
def test_a_molecule_lies_on_a_surface_and_moves():
    from khervecad import chem_adsorb as ad
    slab = cs.surface_scene("cu", "111", (4, 4), 2)
    n = len(slab.atoms)
    benzene = cs.compound_scene("c1ccccc1")
    g = ad.add(slab, benzene, height=2.5, mode="flat")
    assert len(slab.atoms) == n + 12 and slab.groups[g]["count"] == 12
    assert ad.pose(slab, g)["height"] == pytest.approx(2.5)
    zs = [slab.atoms[i][3] for i in ad.members(slab, g)
          if slab.atoms[i][0] == "C"]
    assert max(zs) - min(zs) < 0.2             # flat: the ring lies down
    ad.place(slab, g, x=1.0, y=-2.0, height=3.0)
    p = ad.pose(slab, g)
    assert (p["x"], p["y"], p["height"]) == pytest.approx((1, -2, 3))
    ad.rotate(slab, g, rz=90)
    g2 = ad.add(slab, cs.compound_scene("water"), mode="upright", auto=True)
    ad.remove(slab, g)
    assert len(slab.groups) == 1 and slab.groups[0]["start"] == n
    assert g2 == 1
