"""Carbon nanostructures: graphene, graphite, nanotubes and fullerenes
(carbon_nano.py) and their Part Library parts (library_carbon.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
from collections import Counter

import pytest

from khervecad import carbon_nano as cn
from khervecad.molecule import find_rings


def _degrees(m):
    deg = Counter()
    for i, j, _o in m.bonds:
        deg[i] += 1
        deg[j] += 1
    return [deg[k] for k in range(len(m.atoms))]


def _rings(m):
    nbrs = [[] for _ in m.atoms]
    for i, j, o in m.bonds:
        nbrs[i].append((j, o))
        nbrs[j].append((i, o))
    return find_rings(len(m.atoms), nbrs)


def _pentagons(m):
    """Every 5-cycle (find_rings keeps one ring per bond)."""
    nbrs = [set() for _ in m.atoms]
    for i, j, _o in m.bonds:
        nbrs[i].add(j)
        nbrs[j].add(i)
    found = set()

    def walk(path):
        if len(path) == 5:
            if path[0] in nbrs[path[-1]]:
                found.add(frozenset(path))
            return
        for k in nbrs[path[-1]]:
            if k not in path:
                walk(path + [k])
    for a in range(len(m.atoms)):
        walk([a])
    return len(found)


def _lengths(m):
    return [math.dist(m.atoms[i][1:], m.atoms[j][1:]) for i, j, _o in m.bonds
            if m.atoms[i][0] != "H" and m.atoms[j][0] != "H"]


@pytest.mark.parametrize("kind, atoms", [("c20", 20), ("c60", 60),
                                         ("c70", 70), ("c80", 80)])
def test_fullerenes_are_closed_cages_with_twelve_pentagons(kind, atoms):
    m = cn.fullerene(kind)
    assert m.formula == f"C{atoms}"
    assert set(_degrees(m)) == {3}                 # every carbon sp2, closed
    assert len(m.bonds) == atoms * 3 // 2
    assert _pentagons(m) == 12
    assert all(1.38 < d < 1.50 for d in _lengths(m))


def test_c60_is_a_round_ball_with_its_double_bonds():
    m = cn.fullerene("c60")
    radii = [math.hypot(*a[1:]) for a in m.atoms]
    assert 3.45 < min(radii) and max(radii) < 3.65        # 7.1 Å across
    orders = Counter(o for _i, _j, o in m.bonds)
    assert orders == {1.0: 60, 2.0: 30}                   # 5-6 and 6-6
    doubles = [d for (i, j, o), d in zip(m.bonds, _lengths(m)) if o == 2.0]
    singles = [d for (i, j, o), d in zip(m.bonds, _lengths(m)) if o == 1.0]
    assert max(doubles) < min(singles)                    # 1.40 < 1.45


def test_c70_is_longer_than_c60():
    c60, c70 = cn.fullerene("c60"), cn.fullerene("c70")

    def span(m, c):
        return max(a[c] for a in m.atoms) - min(a[c] for a in m.atoms)
    assert span(c70, 3) > span(c60, 3) + 1.0            # along the axis
    assert span(c70, 1) == pytest.approx(span(c60, 1), abs=0.3)


@pytest.mark.parametrize("n, m", [(5, 5), (10, 10), (9, 0), (10, 0),
                                  (6, 4), (10, 5), (7, 2)])
def test_nanotubes_close_their_seam_at_the_right_diameter(n, m):
    tube = cn.nanotube(n, m, 3.0)
    radii = [math.hypot(a[1], a[2]) for a in tube.atoms]
    want = cn.diameter(n, m) * 10 / 2
    assert min(radii) == pytest.approx(want, abs=1e-6)
    assert max(radii) == pytest.approx(want, abs=1e-6)
    lo = min(a[3] for a in tube.atoms)
    hi = max(a[3] for a in tube.atoms)
    for a, deg in zip(tube.atoms, _degrees(tube)):
        if lo + 2.0 < a[3] < hi - 2.0:
            assert deg == 3                          # no seam anywhere
        assert deg >= 2
    assert all(1.39 < d < 1.43 for d in _lengths(tube))
    assert sum(1 for r in _rings(tube) if len(r) != 6) == 0


def test_multi_walled_tube_walls_sit_a_graphite_gap_apart():
    tube = cn.nanotube(5, 5, 2.0, walls=3)
    radii = sorted({round(math.hypot(a[1], a[2]), 1) for a in tube.atoms})
    assert len(radii) == 3
    gaps = [b - a for a, b in zip(radii, radii[1:])]
    assert all(3.3 < g < 3.5 for g in gaps)


def test_capped_tube_is_c60_plus_belts():
    m = cn.capped_nanotube(3.0)
    assert (len(m.atoms) - 60) % 10 == 0 and len(m.atoms) > 200
    assert set(_degrees(m)) == {3}
    assert _pentagons(m) == 12


def test_graphene_sheet_density_and_stacking():
    sheet = cn.graphene(4, 4)
    area = 4.0 * 4.0                                  # nm²
    assert len(sheet.atoms) / area == pytest.approx(38.2, rel=0.08)
    assert all(d == pytest.approx(1.42) for d in _lengths(sheet))
    assert {len(r) for r in _rings(sheet)} == {6}
    ab = cn.graphene(3, 3, 2, "AB")
    zs = sorted({round(a[3], 3) for a in ab.atoms})
    assert zs[1] - zs[0] == pytest.approx(cn.INTERLAYER)
    low = {(round(a[1], 2), round(a[2], 2)) for a in ab.atoms
           if round(a[3], 3) == zs[0]}
    high = [(round(a[1], 2), round(a[2], 2)) for a in ab.atoms
            if round(a[3], 3) == zs[1]]
    over = sum(1 for p in high if p in low)
    assert over / len(high) == pytest.approx(0.5, abs=0.1)   # Bernal
    aa = cn.graphene(3, 3, 2, "AA")
    zs = sorted({round(a[3], 3) for a in aa.atoms})
    low = {(round(a[1], 2), round(a[2], 2)) for a in aa.atoms
           if round(a[3], 3) == zs[0]}
    assert all((round(a[1], 2), round(a[2], 2)) in low
               for a in aa.atoms if round(a[3], 3) == zs[1])


def test_ribbons_and_dots_are_hydrogen_capped():
    for m in (cn.nanoribbon("armchair", 1, 3), cn.nanoribbon("zigzag", 1, 3),
              cn.quantum_dot(2)):
        degs = _degrees(m)
        assert all(d == 3 for a, d in zip(m.atoms, degs) if a[0] == "C")
        assert "H" in m.composition()


def test_defects_and_graphite_surface():
    sheet = cn.graphene(3, 3)
    assert len(cn.defect_sheet("vacancy", 3, 3).atoms) == len(sheet.atoms) - 1
    doped = cn.defect_sheet("nitrogen", 3, 3)
    assert 0 < doped.composition()["N"] < 0.1 * len(doped.atoms)
    surf = cn.graphite_surface(3, 3, 4)
    assert max(a[3] for a in surf.atoms) == pytest.approx(0.0)
    assert len({round(a[3], 3) for a in surf.atoms}) == 4
    step = cn.graphite_surface(3, 3, 4, step=True)
    top = [a for a in step.atoms if abs(a[3]) < 0.01]
    assert len(top) < 0.6 * len([a for a in surf.atoms if abs(a[3]) < 0.01])


def test_nonsense_is_refused():
    with pytest.raises(cn.CarbonError):
        cn.nanotube(2, 1, 3)
    with pytest.raises(cn.CarbonError):
        cn.nanotube(4, 5, 3)
    with pytest.raises(cn.CarbonError):
        cn.graphene(3, 3, 2, "XYZ")
    with pytest.raises(cn.CarbonError):
        cn.fullerene("c65")


def test_library_parts_build_within_budget():
    from khervecad import library, library_carbon
    from khervecad import molecule_build as mb
    for part_id, spec in library_carbon.PARTS.items():
        dims = next(iter(spec["sizes"].values()), {})
        group = library.build_part(part_id, dict(dims))
        assert group.children, part_id
    for key in cn.STRUCTURES:                       # also by compound name
        m = mb.resolve(key.upper())
        assert m.formula == key.upper()


# ------------------------------------------------ graphene as loops
@pytest.mark.parametrize("nx, ny", [(2, 4), (3, 4), (8, 8), (12, 10),
                                    (20, 14)])
def test_graphene_loops_leave_no_dangling_atom_or_bond(nx, ny):
    from khervecad import graphene_build as gb
    atoms, bonds = gb.sites(nx, ny)

    def key(p):
        return (round(p[0], 5), round(p[1], 5))
    sites = {key(p) for p in atoms}
    assert len(sites) == len(atoms)
    deg = Counter()
    for p, q in bonds:
        assert key(p) in sites and key(q) in sites      # both ends exist
        assert math.dist(p, q) == pytest.approx(gb.CC_NM)
        deg[key(p)] += 1
        deg[key(q)] += 1
    assert {deg[s] for s in sites} <= {2, 3}


@pytest.mark.parametrize("kw", [dict(), dict(layers=3, stacking="ABC"),
                                dict(layers=2, twist=13.17),
                                dict(kind="graphite", layers=4, step=True)])
def test_graphene_program_draws_what_it_counts(kw):
    from khervecad import graphene_build as gb
    from khervecad import mesh
    from khervecad.scadparse import parse_scad
    code, stats = gb.program(2.5, 2.5, **kw)
    assert "for (t = [30 : 120 : 150])" in code          # angle steps
    assert code.count("sphere(") == 2                    # not an atom list
    root, warnings = parse_scad(code)
    assert not warnings
    assert len(mesh.tessellate(root)) == stats["triangles"]


def test_graphene_variables_drive_the_sheet():
    from khervecad import graphene_build as gb
    from khervecad import mesh
    from khervecad.scadparse import parse_scad
    code, _stats = gb.program(2, 2)
    before = len(mesh.tessellate(parse_scad(code)[0]))
    nx = next(line for line in code.splitlines() if line.startswith("nx ="))
    wider = code.replace(nx, "nx = 20;")
    assert len(mesh.tessellate(parse_scad(wider)[0])) > before


# ------------------------------------------------------ surfaces
def test_every_crystal_face_is_a_surface_part():
    from khervecad import library, library_surfaces as ls
    from khervecad.crystal_library import LIBRARY
    from khervecad.library_groups import short_name
    for key, crystal in LIBRARY.items():
        if key in ls.SKIP:
            continue
        ids = [p for p in ls.PARTS if p.startswith(f"surface_{key}_")]
        assert len(ids) == len(ls.faces(crystal)) >= 3
    for pid in ("surface_si_111", "surface_quartz_0001",
                "surface_rutile_110", "surface_cu_100"):
        group = library.build_part(pid, {"surf_repeat": 3,
                                         "surf_layers": 2})
        assert group.children and "(" in group.name
    assert short_name("Surfaces: Metals") == "Metals"
    assert ls.crystal_of("Copper (111)") == "Copper"
    assert library.PARTS["graphene_sheet"]["category"].startswith(
        "Surfaces: ")
