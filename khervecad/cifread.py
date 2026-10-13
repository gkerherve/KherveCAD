"""Crystal structures from CIF files and symmetry operators (Qt-free).

A small-molecule / inorganic CIF (what ICSD, COD, the Materials Project
and a paper's supporting information hand out) names its cell, the
symmetry operators of its space group as text ("-x+1/2, y, -z") and the
asymmetric unit. `read_cif` applies every operator to every site, wraps
into the cell and drops the copies that land on one another, so the
`Crystal` holds every atom of the conventional cell like the library's
own entries. `expand` does the same for a basis an assistant types in
with the operators beside it. No ASE, no space-group tables: the CIF
carries the operators itself (a CIF that gives only the space-group
NAME is refused with the reason).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
import os
import re
from fractions import Fraction

from . import crystal as cr
from .protein import _cif_tokens

#: two sites closer than this (Å) are one atom
SAME_SITE = 0.05

_SYMOP_KEYS = ("_symmetry_equiv_pos_as_xyz", "_space_group_symop_operation_xyz",
               "_space_group_symop.operation_xyz")


def _number(text: str) -> float:
    """'5.4307(2)' -> 5.4307; '.' and '?' are not numbers."""
    m = re.match(r"\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)", text)
    if not m:
        raise ValueError(f"'{text}' is not a number.")
    return float(m.group(1))


def parse_op(text: str):
    """'-x+1/2, y, z-1/4' -> three (row of 3 coefficients, offset)."""
    parts = [p.strip().lower().replace(" ", "")
             for p in text.strip().strip("'\"").split(",")]
    if len(parts) != 3:
        raise ValueError(f"A symmetry operator has three parts: '{text}'.")
    out = []
    for part in parts:
        row = [0.0, 0.0, 0.0]
        shift = 0.0
        for sign, term in re.findall(r"([+-]?)([^+-]+)", part):
            k = -1.0 if sign == "-" else 1.0
            axis = next((i for i, ch in enumerate("xyz") if ch in term), None)
            if axis is None:
                shift += k * float(Fraction(term))
            else:
                coef = term.replace("xyz"[axis], "").replace("*", "")
                row[axis] += k * (float(Fraction(coef)) if coef else 1.0)
        out.append((row, shift))
    return out


def _apply(op, f):
    return [sum(row[i] * f[i] for i in range(3)) + shift
            for row, shift in op]


def expand(sites, ops, crystal_cell):
    """Every atom of the cell from the asymmetric unit *sites*
    [(el, fx, fy, fz)] and the operators *ops* (text), duplicates closer
    than SAME_SITE dropped (distances in *crystal_cell*'s metric)."""
    parsed = [parse_op(o) for o in ops] or [parse_op("x,y,z")]
    out = []
    for el, *f in sites:
        for op in parsed:
            g = [x % 1.0 for x in _apply(op, f)]
            g = [0.0 if x > 1 - 1e-6 else x for x in g]
            p = crystal_cell.cart(g)
            if any(e == el and _close(crystal_cell, p, q)
                   for e, q in ((e, crystal_cell.cart(h))
                                for e, *h in out)):
                continue
            out.append((el, *g))
    return out


def _close(c, p, q):
    """Within SAME_SITE through the periodic images (one cell either way)."""
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            for k in (-1, 0, 1):
                s = c.cart((i, j, k))
                if math.dist(p, [q[n] + s[n] for n in range(3)]) < SAME_SITE:
                    return True
    return False


def _element(row):
    for key in ("_atom_site_type_symbol", "_atom_site_label"):
        text = row.get(key)
        if text:
            m = re.match(r"([A-Z][a-z]?)", text.strip().capitalize())
            if m and m.group(1) in cr.ELEMENTS:
                return m.group(1)
            m = re.match(r"([A-Z])", text.strip().upper())
            if m and m.group(1) in cr.ELEMENTS:
                return m.group(1)
    raise ValueError(f"No element known for site {row}.")


def _tables(text):
    """{item: value} for single items and [rows] keyed by the loop's first
    item for loops — small-molecule CIF names (_cell_length_a)."""
    singles, loops = {}, []
    toks = list(_cif_tokens(text))
    i = 0
    while i < len(toks):
        t = toks[i]
        low = t.lower()
        if low.startswith("data_") and singles.get("_data") is None:
            singles["_data"] = t[5:]
            i += 1
        elif low == "loop_":
            i += 1
            items = []
            while i < len(toks) and toks[i].startswith("_"):
                items.append(toks[i].lower())
                i += 1
            values = []
            while i < len(toks) and not toks[i].startswith("_") and \
                    toks[i].lower() != "loop_" and \
                    not toks[i].lower().startswith("data_"):
                values.append(toks[i])
                i += 1
            if items:
                loops.append([dict(zip(items, values[k:k + len(items)]))
                              for k in range(0, len(values) - len(items) + 1,
                                             len(items))])
        elif t.startswith("_") and i + 1 < len(toks):
            singles[low] = toks[i + 1]
            i += 2
        else:
            i += 1
    return singles, loops


def read_cif(path_or_text: str, key: str = "cif") -> cr.Crystal:
    """A `Crystal` (every atom of the cell) from a CIF file or its text."""
    text = path_or_text
    name = None
    if "\n" not in path_or_text and os.path.exists(path_or_text):
        with open(path_or_text, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        name = os.path.splitext(os.path.basename(path_or_text))[0]
    singles, loops = _tables(text)
    try:
        cell = [_number(singles[k]) for k in (
            "_cell_length_a", "_cell_length_b", "_cell_length_c",
            "_cell_angle_alpha", "_cell_angle_beta", "_cell_angle_gamma")]
    except KeyError as missing:
        raise ValueError(f"The CIF has no {missing.args[0]}.")
    ops, sites = [], []
    for rows in loops:
        if not rows:
            continue
        key0 = next((k for k in _SYMOP_KEYS if k in rows[0]), None)
        if key0:
            ops = [r[key0] for r in rows]
        if "_atom_site_fract_x" in rows[0]:
            for r in rows:
                occ = r.get("_atom_site_occupancy", "1")
                try:
                    if _number(occ) < 0.5:   # a minority of a disordered site
                        continue
                except ValueError:
                    pass
                sites.append((_element(r), _number(r["_atom_site_fract_x"]),
                              _number(r["_atom_site_fract_y"]),
                              _number(r["_atom_site_fract_z"])))
    if not sites:
        raise ValueError("The CIF lists no atom sites (_atom_site_fract_x).")
    group = (singles.get("_symmetry_space_group_name_h-m")
             or singles.get("_space_group_name_h-m_alt") or "?")
    if not ops and group.replace(" ", "") not in ("P1", "?"):
        raise ValueError(f"The CIF names space group {group} but lists no "
                         "symmetry operators; export it with the operators "
                         "(_symmetry_equiv_pos_as_xyz).")
    formula = (singles.get("_chemical_formula_sum")
               or singles.get("_chemical_formula_structural") or "")
    title = (singles.get("_chemical_name_mineral")
             or singles.get("_chemical_name_common")
             or singles.get("_chemical_name_systematic")
             or formula or name or singles.get("_data") or "CIF crystal")
    c = cr.Crystal(key=key, name=str(title).strip(), formula=formula.replace(
        " ", ""), category="Custom", system="from CIF", space_group=group,
        a=cell[0], b=cell[1], c=cell[2], alpha=cell[3], beta=cell[4],
        gamma=cell[5], atoms=[],
        source=f"CIF {name or singles.get('_data', '')}".strip())
    c.atoms = expand(sites, ops, c)
    return c
