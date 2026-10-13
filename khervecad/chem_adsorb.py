"""Molecules lying on a surface in the Chemistry Builder (Qt-free).

A molecule added to a slab `Scene` becomes a GROUP (its atoms are a run
`start`..`start + count`): laid flat (flattest side down), upright
(longest axis up) or as drawn, spun about the surface normal, centred
over the slab or at the first free spot, its lowest atom `height` Å above
the top layer; then moved (`translate`, `place`), turned about its own
centre (`rotate`) or removed. Not bonded to the surface. Ported from
KherveMol's adsorbates.py.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .chem_scene import MAX_ATOMS
from .crystal_build import BuildError

MODES = ("flat", "upright", "as drawn")
#: closest a new molecule may sit to one already on the slab (Å)
CLEARANCE = 2.2


def _grouped(mol):
    out = set()
    for g in mol.groups:
        out.update(range(g["start"], g["start"] + g["count"]))
    return out


def surface_indices(mol):
    """Indices of the atoms that are the slab (not in any group)."""
    grouped = _grouped(mol)
    return [i for i in range(len(mol.atoms)) if i not in grouped]


def top_layer(mol):
    """z of the highest slab atom."""
    idx = surface_indices(mol)
    if not idx:
        raise BuildError("There is no surface to place a molecule on.")
    return max(mol.atoms[i][3] for i in idx)


def group_of(mol, atom):
    """Index in ``mol.groups`` of the group holding *atom*, or None."""
    if atom is None:
        return None
    for gi, g in enumerate(mol.groups):
        if g["start"] <= atom < g["start"] + g["count"]:
            return gi
    return None


def members(mol, gi):
    g = mol.groups[gi]
    return range(g["start"], g["start"] + g["count"])


def centroid(mol, gi):
    idx = list(members(mol, gi))
    return tuple(sum(mol.atoms[i][d] for i in idx) / len(idx)
                 for d in (1, 2, 3))


def pose(mol, gi):
    """Where a group is: ``{"x", "y", "height"}`` — the centre in x, y and
    the lowest atom's height above the top layer (Å)."""
    idx = list(members(mol, gi))
    cx, cy, _cz = centroid(mol, gi)
    return {"x": cx, "y": cy,
            "height": min(mol.atoms[i][3] for i in idx) - top_layer(mol)}


def translate(mol, gi, dx=0.0, dy=0.0, dz=0.0):
    for i in members(mol, gi):
        a = mol.atoms[i]
        a[1] += dx
        a[2] += dy
        a[3] += dz


def _rot(axis, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    if axis == 0:
        return ((1, 0, 0), (0, c, -s), (0, s, c))
    if axis == 1:
        return ((c, 0, s), (0, 1, 0), (-s, 0, c))
    return ((c, -s, 0), (s, c, 0), (0, 0, 1))


def rotate(mol, gi, rx=0.0, ry=0.0, rz=0.0):
    """Turn a group about its own centre by (rx, ry, rz) degrees about the
    world axes (z is the surface normal)."""
    cx, cy, cz = centroid(mol, gi)
    mats = [_rot(k, d) for k, d in enumerate((rx, ry, rz)) if d]
    for i in members(mol, gi):
        a = mol.atoms[i]
        p = [a[1] - cx, a[2] - cy, a[3] - cz]
        for m in mats:
            p = [sum(m[r][c] * p[c] for c in range(3)) for r in range(3)]
        a[1], a[2], a[3] = cx + p[0], cy + p[1], cz + p[2]


def place(mol, gi, x=None, y=None, height=None):
    """Put a group's centre at (x, y) and/or its lowest atom *height* Å above
    the top layer; leave unspecified values alone."""
    cx, cy, _ = centroid(mol, gi)
    p = pose(mol, gi)
    translate(mol, gi, 0.0 if x is None else x - cx,
              0.0 if y is None else y - cy,
              0.0 if height is None else height - p["height"])


def _oriented(molecule, mode, spin):
    """The molecule's atoms as (element, x, y, z) turned by *mode* and *spin*
    and centred on x, y with its lowest atom at z = 0."""
    pts = [tuple(a[1:4]) for a in molecule.atoms]
    n = len(pts)
    c = [sum(p[i] for p in pts) / n for i in range(3)]
    pts = [tuple(p[i] - c[i] for i in range(3)) for p in pts]
    pts = _orient_points(pts, mode)
    a = math.radians(spin)
    ca, sa = math.cos(a), math.sin(a)
    pts = [(p[0] * ca - p[1] * sa, p[0] * sa + p[1] * ca, p[2]) for p in pts]
    low = min(p[2] for p in pts)
    return [(at[0], p[0], p[1], p[2] - low)
            for at, p in zip(molecule.atoms, pts)]


def _free(mol, atoms, dx, dy, top, height):
    """True if *atoms* placed at offset (dx, dy) clear every adsorbate."""
    others = [mol.atoms[i] for g in range(len(mol.groups))
              for i in members(mol, g)]
    for el, x, y, z in atoms:
        px, py, pz = x + dx, y + dy, z + top + height
        for o in others:
            if (o[1] - px) ** 2 + (o[2] - py) ** 2 + (o[3] - pz) ** 2 \
                    < CLEARANCE ** 2:
                return False
    return True


def add(mol, molecule, name=None, height=2.4, dx=0.0, dy=0.0, mode="flat",
        spin=0.0, auto=False):
    """Put *molecule* (a molecule `Scene`) on the surface scene *mol*, in
    place; returns the new group's index.

    *dx*, *dy* offset it from the centre of the slab. With *auto* it goes
    to the first free spot instead (a spiral out from the centre, clear of
    every molecule already there)."""
    if not molecule.atoms:
        raise BuildError("There is no molecule to place on the surface.")
    if getattr(molecule, "kind", "molecule") != "molecule":
        raise BuildError("Only a molecule can be placed on a surface, not "
                         "another crystal or slab.")
    if mode not in MODES:
        raise BuildError(f"mode is one of {', '.join(MODES)}.")
    surf = surface_indices(mol)
    top = top_layer(mol)
    xs = [mol.atoms[i][1] for i in surf]
    ys = [mol.atoms[i][2] for i in surf]
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    atoms = _oriented(molecule, mode, spin)
    if auto and mol.groups:
        half = max(max(xs) - min(xs), max(ys) - min(ys)) / 2
        found = None
        r = 0.0
        while r <= half * 1.2 and found is None:
            steps = 1 if r == 0 else max(6, int(2 * math.pi * r / 2.0))
            for s in range(steps):
                t = 2 * math.pi * s / steps
                cand = (r * math.cos(t), r * math.sin(t))
                if _free(mol, atoms, cand[0], cand[1], top, height):
                    found = cand
                    break
            r += 2.0
        if found is not None:
            dx, dy = found
    if len(mol.atoms) + len(atoms) > MAX_ATOMS:
        raise BuildError("Too many atoms: shrink the slab or the molecule.")
    start = len(mol.atoms)
    for el, x, y, z in atoms:
        mol.atoms.append([el, x + cx + dx, y + cy + dy, z + top + height])
    for i, j, o in molecule.bonds:
        mol.bonds.append([i + start, j + start, o])
    label = name or getattr(molecule, "name", None) or "Molecule"
    label = _unique(mol, label)
    mol.groups.append({"name": label, "start": start, "count": len(atoms)})
    return len(mol.groups) - 1


def _unique(mol, name):
    taken = {g["name"] for g in mol.groups}
    if name not in taken:
        return name
    n = 2
    while f"{name} ({n})" in taken:
        n += 1
    return f"{name} ({n})"


def remove(mol, gi):
    """Delete a group's atoms and bonds; later groups and bond indices
    shift down."""
    g = mol.groups[gi]
    start, count = g["start"], g["count"]
    gone = set(range(start, start + count))

    def shift(i):
        return i - count if i >= start + count else i
    mol.atoms = [a for i, a in enumerate(mol.atoms) if i not in gone]
    mol.bonds = [[shift(i), shift(j), o] for i, j, o in mol.bonds
                 if i not in gone and j not in gone]
    del mol.groups[gi]
    for h in mol.groups:
        if h["start"] > start:
            h["start"] -= count


# ------------------------------------------------- principal axes
def _eigen(m, sweeps=60):
    """Eigenvectors of a symmetric 3x3 (Jacobi), largest eigenvalue first,
    as a right-handed orthonormal set."""
    a = [row[:] for row in m]
    v = [[1.0 if i == j else 0.0 for j in range(3)] for i in range(3)]
    for _ in range(sweeps):
        p, q = max(((0, 1), (0, 2), (1, 2)), key=lambda t: abs(a[t[0]][t[1]]))
        if abs(a[p][q]) < 1e-12:
            break
        th = 0.5 * math.atan2(2 * a[p][q], a[q][q] - a[p][p])
        c, s = math.cos(th), math.sin(th)
        for k in range(3):
            akp, akq = a[k][p], a[k][q]
            a[k][p], a[k][q] = c * akp - s * akq, s * akp + c * akq
        for k in range(3):
            apk, aqk = a[p][k], a[q][k]
            a[p][k], a[q][k] = c * apk - s * aqk, s * apk + c * aqk
        for k in range(3):
            vkp, vkq = v[k][p], v[k][q]
            v[k][p], v[k][q] = c * vkp - s * vkq, s * vkp + c * vkq
    order = sorted(range(3), key=lambda i: -a[i][i])
    vecs = [[v[k][i] for k in range(3)] for i in order]
    x, y = vecs[0], vecs[1]
    z = [x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2],
         x[0] * y[1] - x[1] * y[0]]
    return [x, y, z]


def _principal_frame(points):
    """Unit axes of a point set, longest spread first: (e1, e2, e3)."""
    n = len(points)
    c = [sum(p[i] for p in points) / n for i in range(3)]
    q = [[p[i] - c[i] for i in range(3)] for p in points]
    cov = [[sum(v[i] * v[j] for v in q) / n for j in range(3)]
           for i in range(3)]
    return _eigen(cov)


def _orient_points(pts, mode):
    """Centred points turned by *mode* (see `add_adsorbate`): the flattest
    side down, the longest axis up, or as they are."""
    n = len(pts)
    if mode == "as drawn" or n < 2:
        return pts
    if n == 2:
        # a diatomic has one axis: along x when flat, up (z) when upright
        d = [pts[1][i] - pts[0][i] for i in range(3)]
        ln = math.sqrt(sum(v * v for v in d)) or 1.0
        e1 = [v / ln for v in d]
        helper = (0.0, 0.0, 1.0) if abs(e1[2]) < 0.9 else (1.0, 0.0, 0.0)
        e2 = [e1[1] * helper[2] - e1[2] * helper[1],
              e1[2] * helper[0] - e1[0] * helper[2],
              e1[0] * helper[1] - e1[1] * helper[0]]
        n2 = math.sqrt(sum(v * v for v in e2)) or 1.0
        e2 = [v / n2 for v in e2]
        e3 = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2],
              e1[0] * e2[1] - e1[1] * e2[0]]
    else:
        e1, e2, e3 = _principal_frame(pts)
    # flat: longest along x, middle along y, shortest up (z);
    # upright: shortest along x, middle along y, longest up
    axes = (e1, e2, e3) if mode == "flat" else (e3, e2, e1)
    return [tuple(sum(p[i] * ax[i] for i in range(3)) for ax in axes)
            for p in pts]
