"""Chemistry files out of the Chemistry Builder (Qt-free): XYZ, MOL /
SDF (V2000), PDB (CRYST1 + CONECT) and CIF (P 1; the cell from the
crystal's lattice × repeats, a single parallelepiped outline, or the
outline's box; a periodic crystal's face atoms wrapped and kept once).
Ported from KherveMol's chemexport.py for a `chem_scene.Scene`.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os

from .crystal_build import BuildError

FORMATS = {
    "xyz": ("XYZ", "Atom list — every chemistry program"),
    "mol": ("MOL", "MDL molfile V2000 — atoms and bonds (≤ 999 atoms)"),
    "sdf": ("SDF", "MDL structure-data file"),
    "pdb": ("PDB", "Protein Data Bank — atoms and bonds, cell for crystals"),
    "cif": ("CIF", "Crystallographic information file (crystals and slabs)"),
}


def _title(mol):
    return (getattr(mol, "name", None) or "KherveCAD").replace("\n", " ")


def _check(mol):
    if not mol.atoms:
        raise BuildError("There is nothing to export: the structure is empty.")


def xyz_text(mol):
    _check(mol)
    lines = [str(len(mol.atoms)), _title(mol)]
    for a in mol.atoms:
        lines.append(f"{a[0]:<3s} {a[1]:14.6f} {a[2]:14.6f} {a[3]:14.6f}")
    return "\n".join(lines) + "\n"


def mol_text(mol):
    _check(mol)
    if len(mol.atoms) > 999 or len(mol.bonds) > 999:
        raise BuildError("A MOL file holds at most 999 atoms and bonds: use "
                         "XYZ, PDB or CIF for this structure.")
    lines = [_title(mol)[:80], "  KherveCAD", "",
             f"{len(mol.atoms):3d}{len(mol.bonds):3d}  0  0  0  0  0  0  0  0"
             "999 V2000"]
    for a in mol.atoms:
        lines.append(f"{a[1]:10.4f}{a[2]:10.4f}{a[3]:10.4f} {a[0]:<3s}"
                     " 0  0  0  0  0  0  0  0  0  0  0  0")
    for i, j, o in mol.bonds:
        lines.append(f"{i + 1:3d}{j + 1:3d}{int(o):3d}  0")
    lines.append("M  END")
    return "\n".join(lines) + "\n"


def sdf_text(mol):
    return mol_text(mol) + "$$$$\n"


def _cell_from_edges(mol):
    """(origin, a, b, c) of the cell of a crystal / slab / supercell, or
    None for a molecule.

    A library crystal (``crystal:key`` / ``cell:key``) uses its real lattice
    vectors times its cell counts; any other outline that is a single
    parallelepiped uses its three edges; a stacked classic lattice (an
    outline of many cells) falls back to the axis-aligned box of the
    outline, which is exact for the cubic family."""
    src = getattr(mol, "source", {}) or {}
    if getattr(mol, "kind", "") == "crystal" and src.get("crystal"):
        from . import crystal_library
        crystal = crystal_library.LIBRARY.get(src["crystal"])
        if crystal is not None:
            n = tuple(src.get("reps", (1, 1, 1)))
            v = crystal.vectors()
            a, b, c = ([n[k] * x for x in v[k]] for k in range(3))
            mid = [(a[i] + b[i] + c[i]) / 2 for i in range(3)]
            return tuple([-m for m in mid]), a, b, c
    edges = mol.edges
    if not edges:
        return None
    pts = {}
    for e in edges:
        for p in (e[0], e[1]):
            pts[tuple(round(x, 5) for x in p)] = p
    if len(pts) == 8:
        for key in pts:
            inc = []
            for e in edges:
                a = tuple(round(x, 5) for x in e[0])
                b = tuple(round(x, 5) for x in e[1])
                if a == key:
                    inc.append([e[1][i] - e[0][i] for i in range(3)])
                elif b == key:
                    inc.append([e[0][i] - e[1][i] for i in range(3)])
            if len(inc) == 3:
                o, (a, b, c) = pts[key], inc
                det = (a[0] * (b[1] * c[2] - b[2] * c[1])
                       - a[1] * (b[0] * c[2] - b[2] * c[0])
                       + a[2] * (b[0] * c[1] - b[1] * c[0]))
                if abs(det) > 1e-9:
                    if det < 0:
                        b, c = c, b
                    return o, a, b, c
    lo = [min(p[d] for p in pts.values()) for d in range(3)]
    hi = [max(p[d] for p in pts.values()) for d in range(3)]
    if any(hi[d] - lo[d] < 1e-6 for d in range(3)):
        return None
    return (tuple(lo), [hi[0] - lo[0], 0.0, 0.0], [0.0, hi[1] - lo[1], 0.0],
            [0.0, 0.0, hi[2] - lo[2]])


def _lattice_params(a, b, c):
    def ln(v):
        return math.sqrt(sum(x * x for x in v))

    def ang(u, v):
        d = sum(x * y for x, y in zip(u, v)) / (ln(u) * ln(v))
        return math.degrees(math.acos(max(-1.0, min(1.0, d))))
    return ln(a), ln(b), ln(c), ang(b, c), ang(a, c), ang(a, b)


def _fractional(mol, origin, a, b, c):
    det = (a[0] * (b[1] * c[2] - b[2] * c[1])
           - a[1] * (b[0] * c[2] - b[2] * c[0])
           + a[2] * (b[0] * c[1] - b[1] * c[0]))

    def solve(p):
        q = [p[i] - origin[i] for i in range(3)]
        # Cramer's rule for q = f1 a + f2 b + f3 c
        d1 = (q[0] * (b[1] * c[2] - b[2] * c[1])
              - q[1] * (b[0] * c[2] - b[2] * c[0])
              + q[2] * (b[0] * c[1] - b[1] * c[0]))
        d2 = (a[0] * (q[1] * c[2] - q[2] * c[1])
              - a[1] * (q[0] * c[2] - q[2] * c[0])
              + a[2] * (q[0] * c[1] - q[1] * c[0]))
        d3 = (a[0] * (b[1] * q[2] - b[2] * q[1])
              - a[1] * (b[0] * q[2] - b[2] * q[0])
              + a[2] * (b[0] * q[1] - b[1] * q[0]))
        return d1 / det, d2 / det, d3 / det
    return [solve(at[1:4]) for at in mol.atoms]


def cif_text(mol):
    _check(mol)
    cell = _cell_from_edges(mol)
    if cell is None:
        raise BuildError("A CIF needs a crystal, surface or supercell (a "
                         "structure with a cell outline). Use XYZ, MOL or "
                         "PDB for a molecule.")
    o, a, b, c = cell
    la, lb, lc, al, be, ga = _lattice_params(a, b, c)
    frac = _fractional(mol, o, a, b, c)
    keep = list(range(len(mol.atoms)))
    if getattr(mol, "kind", "") == "crystal":
        # a periodic crystal draws the atoms on a cell face in every cell
        # that shares it: wrap them into the cell and keep one of each
        seen, keep, wrapped = set(), [], []
        for i, f in enumerate(frac):
            w = tuple((x % 1.0) if abs(x % 1.0 - 1.0) > 1e-6 else 0.0
                      for x in f)
            key = (mol.atoms[i][0],) + tuple(round(x, 4) % 1.0 for x in w)
            wrapped.append(w)
            if key not in seen:
                seen.add(key)
                keep.append(i)
        frac = wrapped
    counts, rows = {}, []
    for i in keep:
        at, f = mol.atoms[i], frac[i]
        counts[at[0]] = counts.get(at[0], 0) + 1
        rows.append(f" {at[0]}{counts[at[0]]:<4d} {at[0]:<3s} "
                    f"{f[0]:10.6f} {f[1]:10.6f} {f[2]:10.6f}")
    name = "".join(ch if ch.isalnum() else "_" for ch in _title(mol))[:40]
    return "\n".join([
        f"data_{name or 'KherveCAD'}",
        "_audit_creation_method 'KherveCAD'",
        f"_cell_length_a {la:.5f}", f"_cell_length_b {lb:.5f}",
        f"_cell_length_c {lc:.5f}", f"_cell_angle_alpha {al:.4f}",
        f"_cell_angle_beta {be:.4f}", f"_cell_angle_gamma {ga:.4f}",
        "_symmetry_space_group_name_H-M 'P 1'",
        "_symmetry_Int_Tables_number 1", "loop_",
        "_symmetry_equiv_pos_as_xyz", " 'x, y, z'", "loop_",
        "_atom_site_label", "_atom_site_type_symbol", "_atom_site_fract_x",
        "_atom_site_fract_y", "_atom_site_fract_z"] + rows) + "\n"


def pdb_text(mol):
    _check(mol)
    if len(mol.atoms) > 99999:
        raise BuildError("A PDB file holds at most 99999 atoms.")
    lines = [f"REMARK   1 {_title(mol)}"[:80],
             "REMARK   2 Exported by KherveCAD"]
    cell = _cell_from_edges(mol)
    if cell is not None:
        la, lb, lc, al, be, ga = _lattice_params(*cell[1:])
        lines.append(f"CRYST1{la:9.3f}{lb:9.3f}{lc:9.3f}{al:7.2f}{be:7.2f}"
                     f"{ga:7.2f} P 1           1")
    counts = {}
    for k, a in enumerate(mol.atoms, 1):
        counts[a[0]] = counts.get(a[0], 0) + 1
        name = f"{a[0]}{counts[a[0]]}"[:4]
        # atom names of one-letter elements start in column 14
        name = f" {name:<3s}" if len(a[0]) == 1 and len(name) < 4 else \
            f"{name:<4s}"
        lines.append(f"HETATM{k:5d} {name} UNL A   1    "
                     f"{a[1]:8.3f}{a[2]:8.3f}{a[3]:8.3f}  1.00  0.00"
                     f"          {a[0].upper():>2s}")
    nbrs = {}
    for i, j, o in mol.bonds:
        for _ in range(max(1, int(o))):
            nbrs.setdefault(i, []).append(j)
            nbrs.setdefault(j, []).append(i)
    for i in sorted(nbrs):
        lst = nbrs[i]
        for s in range(0, len(lst), 4):
            lines.append("CONECT" + f"{i + 1:5d}"
                         + "".join(f"{j + 1:5d}" for j in lst[s:s + 4]))
    lines.append("END")
    return "\n".join(lines) + "\n"


_WRITERS = {"xyz": xyz_text, "mol": mol_text, "sdf": sdf_text,
            "pdb": pdb_text, "cif": cif_text}


def export(mol, path, fmt=None):
    """Write *mol* to *path*; the format is *fmt* or the extension. Returns
    ``{"path", "format", "atoms", "bytes"}``."""
    ext = (fmt or os.path.splitext(path)[1].lstrip(".")).lower()
    if ext not in _WRITERS:
        raise BuildError(f"Unknown chemistry format '{ext}': "
                         + ", ".join(FORMATS) + ".")
    text = _WRITERS[ext](mol)
    if not path.lower().endswith("." + ext):
        path += "." + ext
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    except OSError as exc:
        raise BuildError(f"Cannot write {path}: {exc.strerror or exc}")
    return {"path": path, "format": ext, "atoms": len(mol.atoms),
            "bytes": os.path.getsize(path)}

