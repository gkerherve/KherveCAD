"""Graphene and graphite as a PARAMETRIC program (Qt-free): the
honeycomb written the way one would by hand — a few variables and one
nest of `for` loops — instead of an atom list.

The lattice is built in zigzag rows along x. Row j holds an A atom and
a B atom above it (one C–C bond, cc, apart) in every column i, the odd
rows shifted half a lattice constant:

    A at ((i + (j % 2) / 2) * a,  j * 1.5 * cc)      B at A + [0, cc]

and the bonds are STEPS OF ANGLE: A's bond to its own B points at 90°,
B's two bonds up to the next row at 30° and 150° (`for (t = [30 : 120 :
150])`), so every bond is drawn once. The first row keeps only its B
atoms and the last only its A atoms, the `if` beside the up-bonds drops
those that would leave the sheet at its sides, and the flake's two sharp
corners (bottom-left B, top-right A — ny is even) are left off, so every
carbon has two or three neighbours: clean zigzag edges, no dangling
atoms or bonds (`sites` mirrors the rules and the tests check it).

Stacking is one more loop over layers k, gap apart (0.335 nm): a
Bernal (AB) layer is the same sheet shifted one bond along y, ABC
cycles three shifts, AA none, and twisted bilayer turns every second
layer `twist` degrees about the flake's centre. The graphite (0001)
surface is the AB stack going DOWN from z = 0, its top layer optionally
cut to half the columns (a monatomic step).

Every number is a variable of the part (Object tab ▸ Variables): nx,
ny, layers, twist... change one and the sheet regrows.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from .crystal import colour
from .molecule import vdw
from .molecule_build import LATTICE_BALL, STICK, BuildError, _tris

A_NM = 0.246                     # lattice constant
CC_NM = A_NM / math.sqrt(3)      # C–C bond, 0.142 nm
GAP_NM = 0.335                   # interlayer spacing
BALL_NM = round(LATTICE_BALL * vdw("C") / 10, 4)
BOND_NM = STICK / 10
BUDGET = 400_000
KINDS = ("sheet", "graphite")
STACKINGS = {"AB": "(k % 2) * cc", "ABA": "(k % 2) * cc",
             "ABC": "(k % 3) * cc", "AA": "0"}


def counts(width: float, depth: float):
    """(nx, ny) for a flake about *width* x *depth* nm; ny even and at
    least 4 (the corner rule assumes the top row is odd)."""
    nx = max(2, int(round(width / A_NM)))
    ny = max(4, int(round(depth / (1.5 * CC_NM))) + 1)
    return nx, ny + ny % 2


def sites(nx, ny, cols=None):
    """One layer as the loops draw it: (atoms [(x, y)], bonds [((x, y),
    (x, y))]) in nm — the program's own rules in Python."""
    cols = cols or nx
    atoms, bonds = [], []
    for j in range(ny):
        for i in range(cols):
            x, y = (i + (j % 2) / 2) * A_NM, j * 1.5 * CC_NM
            if j > 0 and not (j == ny - 1 and i == cols - 1):
                atoms.append((x, y))
            if 0 < j < ny - 1:
                bonds.append(((x, y), (x, y + CC_NM)))
            if j < ny - 1 and not (j == 0 and i == 0):
                atoms.append((x, y + CC_NM))
                for t in (30, 150):
                    ok = ((i < cols - 1 or j % 2 == 0)
                          and not (j == ny - 2 and i == cols - 1)) \
                        if t == 30 else (i > 0 or j % 2 == 1)
                    if ok:
                        r = math.radians(t)
                        bonds.append(((x, y + CC_NM),
                                      (x + CC_NM * math.cos(r),
                                       y + CC_NM + CC_NM * math.sin(r))))
    return atoms, bonds


def atoms_and_bonds(nx, ny, layers=1, top_nx=None):
    """What the loops draw, counted."""
    atoms = bonds = 0
    for k in range(layers):
        a, b = sites(nx, ny, top_nx if (k == 0 and top_nx) else nx)
        atoms += len(a)
        bonds += len(b)
    return atoms, bonds


def program(width=3.0, depth=3.0, layers=1, stacking="AB", twist=0.0,
            kind="sheet", step=False, fn=12, name=""):
    """(OpenSCAD program, stats) of a graphene flake / stack or the
    graphite surface, in nm."""
    if stacking not in STACKINGS:
        raise BuildError(f"stacking is one of {', '.join(STACKINGS)}.")
    if kind not in KINDS:
        raise BuildError(f"kind is one of {', '.join(KINDS)}.")
    layers = int(layers)
    if not 1 <= layers <= 12:
        raise BuildError("From 1 to 12 layers.")
    nx, ny = counts(width, depth)
    top_nx = max(1, nx // 2) if step else None
    n_atoms, n_bonds = atoms_and_bonds(nx, ny, layers, top_nx)
    tris = n_atoms * _tris("sphere", fn) + n_bonds * _tris("cylinder", 8)
    if tris > BUDGET:
        raise BuildError(f"About {tris:,} triangles: make it smaller or "
                         "use fewer layers.")
    graphite = kind == "graphite"
    if not name:
        if graphite:
            name = "Graphite (0001) surface" + (" with a step" if step
                                                else "")
        elif twist and layers > 1:
            name = f"Twisted bilayer graphene ({twist:g}°)"
        elif layers == 1:
            name = "Graphene"
        else:
            name = {2: "Bilayer", 3: "Trilayer"}.get(
                layers, f"{layers}-layer") + f" graphene ({stacking})"
    shift = STACKINGS[stacking]
    lines = [
        f"// {name}: the honeycomb as loops — atoms on two",
        "// sublattices, bonds as steps of 120 degrees.",
        "a = 0.246;        // lattice constant, nm",
        "cc = a / sqrt(3); // C-C bond, 0.142 nm",
        f"nx = {nx};  // hexagons along x (zigzag edge)",
        f"ny = {ny};  // atom rows along y (armchair edge), even",
        f"layers = {layers};",
        f"gap = {GAP_NM};  // between layers, nm",
    ]
    if twist:
        lines.append(f"twist = {twist:g};  // every second layer turned, "
                     "degrees")
    if step:
        lines.append(f"top_nx = {top_nx};  // the top layer stops here: "
                     "a step")
    lines += [f"ball = {BALL_NM};  // atom radius, nm",
              f"stick = {BOND_NM};  // bond radius, nm"]
    z = "-k * gap" if graphite else "k * gap"
    cols = "(k == 0 ? top_nx : nx)" if step else "nx"
    if twist:
        place = ("translate([nx * a / 2, ny * 0.75 * cc, 0]) "
                 "rotate([0, 0, (k % 2) * twist]) "
                 "translate([-nx * a / 2, -ny * 0.75 * cc, "
                 f"{z}])")
    else:
        place = f"translate([0, {shift}, {z}])"
    up_ok = (f"(t == 30 ? (i < {cols} - 1 || j % 2 == 0) && "
             f"!(j == ny - 2 && i == {cols} - 1) : (i > 0 || j % 2 == 1))")
    lines += [
        f'color("{colour("C")}")',
        f"for (k = [0 : layers - 1])  // layers, {stacking} stacking" if
        not twist else "for (k = [0 : layers - 1])  // layers",
        f"  {place}",
        f"    for (j = [0 : ny - 1], i = [0 : {cols} - 1])",
        "      translate([(i + (j % 2) / 2) * a, j * 1.5 * cc, 0]) {",
        f"        if (j > 0 && !(j == ny - 1 && i == {cols} - 1))  // A atom",
        f"          sphere(r = ball, $fn = {fn});",
        "        if (j > 0 && j < ny - 1)  // A-B bond, straight up",
        "          rotate([0, 90, 90]) cylinder(h = cc, r = stick, $fn = 8);",
        "        if (j < ny - 1 && !(j == 0 && i == 0))",
        "          translate([0, cc, 0]) {  // B atom",
        f"            sphere(r = ball, $fn = {fn});",
        "            for (t = [30 : 120 : 150])  // bonds up to the next row",
        f"              if {up_ok}",
        "                rotate([0, 90, t]) cylinder(h = cc, r = stick, "
        "$fn = 8);",
        "          }",
        "      }",
    ]
    stats = {"name": name, "atoms": n_atoms, "bonds": n_bonds,
             "cells": [nx, ny], "layers": layers, "triangles": tris,
             "size_nm": [round((nx - 0.5) * A_NM, 3),
                         round((ny - 1) * 1.5 * CC_NM, 3)],
             "unit": "nm"}
    return "\n".join(lines) + "\n", stats
