"""The structure the Chemistry Builder edits (Qt-free).

A `Scene` is atoms ([element, x, y, z] in ångström), bonds ([i, j, order]),
the lines of a cell box, and named groups of atoms (molecules laid on a
surface). It is built from a library compound or SMILES, a crystal
(conventional cell × repeats), a surface slab (any hkl, optionally with
WHOLE polyhedra at the cut), or a CIF; it can be doped, measured
(distance, angle, torsion) and edited (add / move / delete atoms and
bonds), and turns into a `molecule.Molecule` for the document. The
crystal and surface builders and the doping and whole-polyhedra rules
are ported from KherveMol's chem.py (2026-10-13, the user: "KherveMol has
all that and I want it in KherveCAD").

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from . import crystal as cr
from . import molecule as mol
from .crystal_build import BuildError

#: the most atoms the builder keeps (its canvas stays interactive)
MAX_ATOMS = 6000
#: two atoms bond within this many times their covalent radii
BOND_TOLERANCE = 1.15


@dataclass
class Scene:
    name: str = "Structure"
    atoms: list = field(default_factory=list)      # [el, x, y, z] Å
    bonds: list = field(default_factory=list)      # [i, j, order]
    edges: list = field(default_factory=list)      # [(p, q)] cell lines
    groups: list = field(default_factory=list)     # {name, start, count}
    kind: str = "molecule"                         # crystal / surface …
    #: what made it, so the builder can say so and rebuild it
    source: dict = field(default_factory=dict)

    # ------------------------------------------------------- reading
    def composition(self) -> dict:
        out = {}
        for el, *_p in self.atoms:
            out[el] = out.get(el, 0) + 1
        return out

    def formula(self) -> str:
        return mol.hill_formula(self.composition())

    def mass(self) -> float:
        return sum(cr.ELEMENTS[el][2] for el, *_p in self.atoms
                   if el in cr.ELEMENTS)

    def point(self, i):
        return tuple(self.atoms[i][1:4])

    def neighbours(self, i):
        out = []
        for a, b, _o in self.bonds:
            if a == i:
                out.append(b)
            elif b == i:
                out.append(a)
        return out

    def copy(self) -> "Scene":
        return Scene(self.name, [list(a) for a in self.atoms],
                     [list(b) for b in self.bonds], list(self.edges),
                     [dict(g) for g in self.groups], self.kind,
                     dict(self.source))

    def to_molecule(self) -> mol.Molecule:
        """The scene as a molecule.Molecule (what molecule_build draws)."""
        return mol.Molecule(
            name=self.name, smiles=str(self.source.get("smiles", "")),
            atoms=[(el, float(x), float(y), float(z))
                   for el, x, y, z in self.atoms],
            bonds=[(int(i), int(j), o) for i, j, o in self.bonds],
            charges=[0] * len(self.atoms), key="", category=self.kind)


# ------------------------------------------------------------ measuring
def distance(scene, i, j) -> float:
    return math.dist(scene.point(i), scene.point(j))


def angle(scene, i, j, k) -> float:
    """The angle i-j-k at j, degrees."""
    a, b, c = scene.point(i), scene.point(j), scene.point(k)
    u = [a[n] - b[n] for n in range(3)]
    v = [c[n] - b[n] for n in range(3)]
    nu, nv = math.hypot(*u), math.hypot(*v)
    if nu < 1e-9 or nv < 1e-9:
        return 0.0
    cos = sum(u[n] * v[n] for n in range(3)) / (nu * nv)
    return math.degrees(math.acos(max(-1.0, min(1.0, cos))))


def torsion(scene, i, j, k, m) -> float:
    """The dihedral i-j-k-m, degrees (-180..180)."""
    p = [scene.point(n) for n in (i, j, k, m)]
    b0 = [p[0][n] - p[1][n] for n in range(3)]
    b1 = [p[2][n] - p[1][n] for n in range(3)]
    b2 = [p[3][n] - p[2][n] for n in range(3)]
    nb1 = math.hypot(*b1) or 1.0
    b1 = [x / nb1 for x in b1]

    def perp(v):
        d = sum(v[n] * b1[n] for n in range(3))
        return [v[n] - d * b1[n] for n in range(3)]
    v, w = perp(b0), perp(b2)
    x = sum(v[n] * w[n] for n in range(3))
    c = [b1[1] * v[2] - b1[2] * v[1], b1[2] * v[0] - b1[0] * v[2],
         b1[0] * v[1] - b1[1] * v[0]]
    y = sum(c[n] * w[n] for n in range(3))
    return math.degrees(math.atan2(y, x))


def measure(scene, picked) -> dict:
    """What the picked atoms (2, 3 or 4 indices, in click order) measure:
    {"kind", "value", "unit", "text"}."""
    picked = list(picked)
    names = "-".join(f"{scene.atoms[i][0]}{i + 1}" for i in picked)
    if len(picked) == 2:
        d = distance(scene, *picked)
        return {"kind": "distance", "value": d, "unit": "Å",
                "text": f"{names}: {d:.3f} Å"}
    if len(picked) == 3:
        a = angle(scene, *picked)
        return {"kind": "angle", "value": a, "unit": "°",
                "text": f"{names}: {a:.1f}°"}
    if len(picked) == 4:
        t = torsion(scene, *picked)
        return {"kind": "torsion", "value": t, "unit": "°",
                "text": f"{names}: {t:.1f}° (torsion)"}
    raise ValueError("Pick 2 atoms for a distance, 3 for an angle, 4 for "
                     "a torsion.")


# -------------------------------------------------------------- editing
def add_atom(scene, element, xyz, bond_to=None) -> int:
    element = str(element).strip().capitalize()
    if element not in cr.ELEMENTS:
        raise BuildError(f"Unknown element '{element}'.")
    scene.atoms.append([element, *(float(v) for v in xyz)])
    i = len(scene.atoms) - 1
    if bond_to is not None:
        add_bond(scene, bond_to, i)
    return i


def place_bonded(scene, element, to) -> int:
    """A new *element* atom bonded to atom *to*, at their covalent
    distance, pointing away from *to*'s other neighbours."""
    el0, *p = scene.atoms[to]
    d = (cr.radius(el0) + cr.radius(element.capitalize()))
    nb = scene.neighbours(to)
    if nb:
        away = [0.0, 0.0, 0.0]
        for j in nb:
            q = scene.point(j)
            v = [p[n] - q[n] for n in range(3)]
            nv = math.hypot(*v) or 1.0
            away = [away[n] + v[n] / nv for n in range(3)]
        na = math.hypot(*away)
        if na < 1e-6:                      # neighbours cancel: go up
            away = [0.0, 0.0, 1.0]
        else:
            away = [x / na for x in away]
    else:
        away = [1.0, 0.0, 0.0]
    return add_atom(scene, element, [p[n] + d * away[n] for n in range(3)],
                    bond_to=to)


def move_atom(scene, i, xyz):
    scene.atoms[i][1:4] = [float(v) for v in xyz]


def set_element(scene, i, element):
    element = str(element).strip().capitalize()
    if element not in cr.ELEMENTS:
        raise BuildError(f"Unknown element '{element}'.")
    scene.atoms[i][0] = element


def add_bond(scene, i, j, order=1):
    if i == j:
        return
    for b in scene.bonds:
        if {b[0], b[1]} == {i, j}:
            b[2] = order
            return
    scene.bonds.append([i, j, order])


def delete_bond(scene, i, j):
    scene.bonds = [b for b in scene.bonds if {b[0], b[1]} != {i, j}]


def delete_atoms(scene, indices):
    """Remove atoms; bonds and groups are re-indexed."""
    gone = set(indices)
    remap, k = {}, 0
    for i in range(len(scene.atoms)):
        if i not in gone:
            remap[i] = k
            k += 1
    scene.atoms = [a for i, a in enumerate(scene.atoms) if i not in gone]
    scene.bonds = [[remap[a], remap[b], o] for a, b, o in scene.bonds
                   if a in remap and b in remap]
    groups = []
    for g in scene.groups:
        kept = [remap[i] for i in range(g["start"], g["start"] + g["count"])
                if i in remap]
        if kept:
            groups.append({**g, "start": min(kept), "count": len(kept)})
    scene.groups = groups


def auto_bonds(scene, tolerance=BOND_TOLERANCE):
    """Bond every pair within *tolerance* × their covalent radii."""
    els = [a[0] for a in scene.atoms]
    pts = [tuple(a[1:4]) for a in scene.atoms]
    cut = {}
    for e1 in set(els):
        for e2 in set(els):
            cut[tuple(sorted((e1, e2)))] = tolerance * (
                cr.radius(e1) + cr.radius(e2)) if e1 in cr.ELEMENTS and \
                e2 in cr.ELEMENTS else 0.0
    scene.bonds = find_bonds(pts, els, cut)


def find_bonds(points, elems, cutoffs):
    """[i, j, 1] for every pair under its element pair's cutoff (hash
    grid, so thousands of atoms stay quick)."""
    cutoffs = {k: v for k, v in cutoffs.items() if v > 0}
    if not cutoffs:
        return []
    cell = max(cutoffs.values())
    grid = {}
    for k, p in enumerate(points):
        grid.setdefault(tuple(int(math.floor(x / cell)) for x in p),
                        []).append(k)
    out = []
    for (gx, gy, gz), members in grid.items():
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for i in members:
                        for j in grid.get((gx + dx, gy + dy, gz + dz), ()):
                            if j <= i:
                                continue
                            c = cutoffs.get(tuple(sorted((elems[i],
                                                          elems[j]))))
                            if c and math.dist(points[i], points[j]) <= c:
                                out.append([i, j, 1])
    return out


# --------------------------------------------------------------- doping
def parse_dope(value):
    """[(host, dopant, fraction)] from triples or text "Nb:Mo:0.1"."""
    if not value:
        return []
    if isinstance(value, str):
        value = [part.split(":") for part in value.replace(";", ",")
                 .split(",") if part.strip()]
    out = []
    for row in value:
        try:
            host, dop, frac = row
            host = str(host).strip().capitalize()
            dop = str(dop).strip().capitalize()
            frac = float(frac)
        except (TypeError, ValueError):
            raise BuildError("dope is host:dopant:fraction, e.g. Nb:Mo:0.1.")
        if host not in cr.ELEMENTS or dop not in cr.ELEMENTS:
            raise BuildError(f"Unknown element in dope {host}:{dop}.")
        if not 0 <= frac <= 1:
            raise BuildError("A dopant fraction runs from 0 to 1.")
        out.append((host, dop, frac))
    return out


def substitute(elems, rules, seed=7):
    """round(n × fraction) random host atoms of each rule become the
    dopant — the same ones for the same *seed*. Returns the indices."""
    rng = random.Random(seed)
    changed = []
    for host, dop, frac in parse_dope(rules):
        idx = [i for i, e in enumerate(elems) if e == host]
        for i in sorted(rng.sample(idx, round(len(idx) * frac))):
            elems[i] = dop
            changed.append(i)
    return changed


def dope(scene, rules, seed=7) -> int:
    """Dope a scene in place; bonds kept. Returns atoms substituted."""
    els = [a[0] for a in scene.atoms]
    changed = substitute(els, rules, seed)
    for i in changed:
        scene.atoms[i][0] = els[i]
    scene.source = {**scene.source, "dope": parse_dope(rules), "seed": seed}
    return len(changed)


def _pair_cutoffs(crystal, slack=1.12):
    out = {}
    for e1, e2, d in crystal.bonds:
        out[tuple(sorted((e1, e2)))] = d * slack
    out.update(getattr(crystal, "cutoffs", None) or {})
    if not out:                              # a custom crystal or CIF
        els = {a[0] for a in crystal.atoms}
        for e1 in els:
            for e2 in els:
                out[tuple(sorted((e1, e2)))] = BOND_TOLERANCE * (
                    cr.radius(e1) + cr.radius(e2))
    return out


def _dope_cutoffs(cutoffs, rules):
    """A dopant bonds like the host it replaces."""
    out = dict(cutoffs)
    for host, dop, _f in parse_dope(rules):
        for (e1, e2), d in cutoffs.items():
            if e1 == host:
                out.setdefault(tuple(sorted((dop, e2))), d)
            if e2 == host:
                out.setdefault(tuple(sorted((e1, dop))), d)
            if e1 == e2 == host:
                out.setdefault((dop, dop), d)
    return out


def complete_polyhedra(els, pts, pool, poly):
    """Whole polyhedra at a cut: every centre gets all its ligands within
    the cutoff — from the atoms or from *pool* (periodic images and the
    layers beyond the cut) — and ligands bonded to no centre are dropped."""
    centre, ligand, cut = poly["centre"], poly["ligand"], poly["cutoff"]
    cands = [p for e, p in zip(els, pts) if e == ligand]
    cands += [p for e, p in pool if e == ligand]
    grid = {}
    for p in cands:
        grid.setdefault(tuple(int(math.floor(x / cut)) for x in p),
                        []).append(p)
    keep, seen = [], set()
    for e, p in zip(els, pts):
        if e != centre:
            continue
        g = tuple(int(math.floor(x / cut)) for x in p)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for q in grid.get((g[0] + dx, g[1] + dy, g[2] + dz), ()):
                        k = tuple(round(x, 3) for x in q)
                        if k not in seen and 1e-6 < math.dist(p, q) <= cut:
                            seen.add(k)
                            keep.append(q)
    out_e = [e for e in els if e != ligand]
    out_p = [p for e, p in zip(els, pts) if e != ligand]
    return out_e + [ligand] * len(keep), out_p + keep


def _wire_box(origin, a, b, c):
    def add(*vs):
        return tuple(sum(v[i] for v in vs) for i in range(3))
    corners = {}
    for i in (0, 1):
        for j in (0, 1):
            for k in (0, 1):
                corners[(i, j, k)] = add(origin, tuple(i * x for x in a),
                                         tuple(j * x for x in b),
                                         tuple(k * x for x in c))
    edges = []
    for key, p in corners.items():
        for axis in range(3):
            if key[axis] == 0:
                q = list(key)
                q[axis] = 1
                edges.append((p, corners[tuple(q)]))
    return edges


def _centred(els, pts, edges, mid):
    atoms = [[el, p[0] - mid[0], p[1] - mid[1], p[2] - mid[2]]
             for el, p in zip(els, pts)]
    edges = [(tuple(p[i] - mid[i] for i in range(3)),
              tuple(q[i] - mid[i] for i in range(3))) for p, q in edges]
    return atoms, edges


# ------------------------------------------------------------- building
def molecule_scene(m: mol.Molecule) -> Scene:
    return Scene(name=m.name, atoms=[[el, x, y, z]
                                     for el, x, y, z in m.atoms],
                 bonds=[[i, j, o] for i, j, o in m.bonds], kind="molecule",
                 source={"smiles": m.smiles, "key": m.key})


def compound_scene(text: str) -> Scene:
    """A library compound (key, name or formula) or SMILES."""
    from . import molecule_library as ml
    text = str(text).strip()
    try:
        return molecule_scene(ml.get(text))
    except KeyError:
        pass
    found = ml.by_formula(text) if hasattr(ml, "by_formula") else None
    if found:
        return molecule_scene(ml.get(found[0]) if isinstance(found, list)
                              else found)
    try:
        m = mol.from_smiles(text)
    except mol.SmilesError as exc:
        raise BuildError(f"Not a library compound or SMILES: {exc}")
    m.name = text
    return molecule_scene(m)


def crystal_scene(crystal, reps=(1, 1, 1), dope=None, seed=7) -> Scene:
    """The cell contents repeated *reps* (atoms on the far faces of the
    block included once, so a cell reads whole), doped."""
    if isinstance(crystal, str):
        from .crystal_library import get
        crystal = get(crystal)
    nx, ny, nz = (int(n) for n in reps)
    if not all(1 <= n <= 30 for n in (nx, ny, nz)):
        raise BuildError("Repeat each direction between 1 and 30 cells.")
    rules = parse_dope(dope)
    eps = 1e-6
    seen, pts, els = set(), [], []
    for el, fx, fy, fz in crystal.atoms:
        for i in range(nx + 1):
            for j in range(ny + 1):
                for k in range(nz + 1):
                    p = (fx % 1 + i, fy % 1 + j, fz % 1 + k)
                    if p[0] > nx + eps or p[1] > ny + eps or p[2] > nz + eps:
                        continue
                    key = (el,) + tuple(round(x, 4) for x in p)
                    if key not in seen:
                        seen.add(key)
                        pts.append(crystal.cart(p))
                        els.append(el)
    if len(pts) > MAX_ATOMS:
        raise BuildError(f"{len(pts)} atoms is more than the builder takes "
                         f"({MAX_ATOMS}): fewer cells.")
    a1, a2, a3 = crystal.vectors()
    edges = _wire_box((0.0, 0.0, 0.0), tuple(nx * x for x in a1),
                      tuple(ny * x for x in a2), tuple(nz * x for x in a3))
    substitute(els, rules, seed)
    bonds = find_bonds(pts, els, _dope_cutoffs(_pair_cutoffs(crystal),
                                               rules))
    mid = [(nx * a1[i] + ny * a2[i] + nz * a3[i]) / 2 for i in range(3)]
    atoms, edges = _centred(els, pts, edges, mid)
    label = f"{crystal.name} {nx}×{ny}×{nz}"
    if rules:
        label += ", " + ", ".join(f"{f:g} {d} for {h}" for h, d, f in rules)
    return Scene(name=label, atoms=atoms, bonds=bonds, edges=edges,
                 kind="crystal",
                 source={"crystal": crystal.key, "reps": [nx, ny, nz],
                         "dope": rules, "seed": seed})


def surface_scene(crystal, miller="111", repeat=None, layers=3,
                  termination=None, dope=None, seed=7,
                  complete=False) -> Scene:
    """A slab cut along (hkl), top at z = 0 facing +z, centred in-plane.
    *complete* keeps every coordination polyhedron whole at the cut."""
    from . import crystal_surface as cs
    if isinstance(crystal, str):
        from .crystal_library import get
        crystal = get(crystal)
    hkl = cs.parse_miller(miller)
    rules = parse_dope(dope)
    poly = crystal.polyhedra if complete else None
    if complete and not poly:
        raise BuildError(f"{crystal.name} has no polyhedra to complete.")
    spec = cs.SurfaceSpec(crystal=crystal, miller=hkl, repeat=(1, 1),
                          layers=int(layers), termination=termination)
    spec.check()
    cell = cs.surface_cell(spec)
    if poly:
        pad = max(1, math.ceil(poly["cutoff"] / max(cell["d"], 0.1)))
        cell = cs.surface_cell(spec, pad=pad)
    U, V = cell["U"], cell["V"]
    if repeat is None:                       # about 15 Å across
        def reach(v):
            return max(1, min(10, round(15.0 / (math.hypot(v[0], v[1])
                                               or 1.0))))
        repeat = (reach(U), reach(V))
    nx, ny = (int(n) for n in repeat)
    if len(cell["atoms"]) * nx * ny > MAX_ATOMS:
        raise BuildError(f"{len(cell['atoms']) * nx * ny} atoms is more "
                         f"than the builder takes ({MAX_ATOMS}): fewer "
                         "repeats or layers.")

    def tiles(atoms, ri, rj):
        for i in ri:
            for j in rj:
                ox, oy = i * U[0] + j * V[0], i * U[1] + j * V[1]
                for el, p in atoms:
                    yield el, (p[0] + ox, p[1] + oy, p[2])
    els, pts = [], []
    for el, p in tiles(cell["atoms"], range(nx), range(ny)):
        els.append(el)
        pts.append(p)
    if poly:
        m = 1 + math.ceil(poly["cutoff"] / max(
            min(math.hypot(*U[:2]), math.hypot(*V[:2])), 0.1))
        ri, rj = range(-m, nx + m), range(-m, ny + m)
        pool = list(tiles(cell.get("pad_atoms", []), ri, rj))
        pool += [(el, p) for i in ri for j in rj
                 if not (0 <= i < nx and 0 <= j < ny)
                 for el, p in tiles(cell["atoms"], (i,), (j,))]
        els, pts = complete_polyhedra(els, pts, pool, poly)
    substitute(els, rules, seed)
    bonds = find_bonds(pts, els, _dope_cutoffs(_pair_cutoffs(crystal),
                                               rules))
    depth = cell["depth"]
    edges = _wire_box((0.0, 0.0, -depth), tuple(nx * x for x in U),
                      tuple(ny * x for x in V), (0.0, 0.0, depth))
    mid = [(nx * U[0] + ny * V[0]) / 2, (nx * U[1] + ny * V[1]) / 2, 0.0]
    atoms, edges = _centred(els, pts, edges, mid)
    label = f"{cs.label(crystal, hkl)} {nx}×{ny}, {layers} layers"
    if complete:
        label += ", whole polyhedra"
    if rules:
        label += ", " + ", ".join(f"{f:g} {d} for {h}" for h, d, f in rules)
    return Scene(name=label, atoms=atoms, bonds=bonds, edges=edges,
                 kind="surface",
                 source={"crystal": crystal.key, "miller": list(hkl),
                         "repeat": [nx, ny], "layers": int(layers),
                         "complete": bool(complete), "dope": rules,
                         "seed": seed})


def cif_scene(path, reps=(1, 1, 1)) -> Scene:
    from .cifread import read_cif
    try:
        crystal = read_cif(path)
    except (OSError, ValueError) as exc:
        raise BuildError(f"CIF: {exc}")
    scene = crystal_scene(crystal, reps)
    scene.source["cif"] = str(path)
    return scene


# ----------------------------------------------------------- properties
def properties(scene) -> list:
    """[(label, value)] rows for the properties panel."""
    comp = scene.composition()
    total = sum(comp.values()) or 1
    mass = scene.mass()
    rows = [("Name", scene.name), ("Formula", scene.formula()),
            ("Atoms", str(len(scene.atoms))),
            ("Bonds", str(len(scene.bonds))),
            ("Molar mass" if scene.kind == "molecule" else "Mass",
             f"{mass:.3f} g/mol" if scene.kind == "molecule"
             else f"{mass:.2f} u")]
    for el in sorted(comp, key=lambda e: (-comp[e], e)):
        share = 100 * cr.ELEMENTS[el][2] * comp[el] / mass if mass else 0
        rows.append((el, f"{comp[el]} atoms · {100 * comp[el] / total:.1f} "
                         f"at.% · {share:.1f} wt.%"))
    if scene.bonds:
        ds = [distance(scene, i, j) for i, j, _o in scene.bonds]
        rows.append(("Bond lengths", f"{min(ds):.3f} – {max(ds):.3f} Å"))
    src = scene.source
    if src.get("crystal"):
        from .crystal_library import LIBRARY
        c = LIBRARY.get(src["crystal"])
        if c is not None:
            rows += [("Space group", c.space_group),
                     ("Cell", f"a {c.a:.4f}, b {c.b:.4f}, c {c.c:.4f} Å; "
                              f"{c.alpha:g}°, {c.beta:g}°, {c.gamma:g}°"),
                     ("Density", f"{c.computed_density():.3f} g/cm³")]
    if src.get("dope"):
        rows.append(("Doping", ", ".join(f"{f:g} {d} for {h}"
                                         for h, d, f in src["dope"])))
    return rows
