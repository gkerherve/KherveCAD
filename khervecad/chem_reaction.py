"""Reactions as films (Qt-free): reactant atoms travel to product atoms.

`animation(text)` parses and balances an equation (molecule_build's own
rules), lays out every copy of every species — reactants packed and
spread on the left, products on the right — and hands both sides to
`chem_rxanim`, which pairs each reactant atom with a product atom of the
same element (keeping bonds, company, short trips). The Chemistry Builder
plays the film on its canvas; `animated_program` writes it as OpenSCAD
driven by ONE Motion slider `rx_t` (0..1): every atom's x, y, z is a
`lookup` over sampled keyframes, the bonds that survive are always drawn,
the ones that break only while `rx_t` < BREAK and the new ones from FORM
on — so View ▸ Customizer's ▶ plays the reaction in the document.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from fractions import Fraction

from . import chem_rxanim as rx
from . import crystal as cr
from . import molecule_build as mb
from .crystal_build import BuildError

#: keyframes sampled for the document's lookup tables
SAMPLES = 25
#: bond stick radius, Å
STICK = 0.18
VARIABLE = "rx_t"


def _coefficients(left, right, balance_it=True):
    given = [t.coef for t in left + right]
    if balance_it and any(c is None for c in given):
        coefs = mb.balance(left, right)
        if any(c is not None for c in given):
            ratio = next(g / c for g, c in zip(given, coefs) if g)
            coefs = [g if g is not None else c * ratio
                     for g, c in zip(given, coefs)]
    elif balance_it:
        coefs = mb.balance(left, right)
    else:
        coefs = [c if c is not None else Fraction(1) for c in given]
    return coefs


def _centred(m):
    pts = [tuple(a[1:4]) for a in m.atoms]
    c = [sum(p[i] for p in pts) / len(pts) for i in range(3)]
    return [tuple(p[i] - c[i] for i in range(3)) for p in pts]


def _side(copies, gap, shift):
    """Elements, bonds, molecule numbers and positions of *copies*
    [(molecule, centred points)] laid in a row *gap* Å apart, centred on
    x = *shift*; plus the row's width."""
    els, bonds, mols, rows = [], [], [], []
    cursor = 0.0
    for k, (m, pts) in enumerate(copies):
        lo = min(p[0] for p in pts)
        hi = max(p[0] for p in pts)
        base = len(els)
        els += [a[0] for a in m.atoms]
        mols += [k] * len(m.atoms)
        bonds += [(i + base, j + base, int(round(o)) or 1)
                  for i, j, o in m.bonds]
        rows.append((cursor - lo, pts))
        cursor += hi - lo + gap
    width = max(0.0, cursor - gap)
    pos = []
    for dx, pts in rows:
        pos += [(p[0] + dx - width / 2 + shift, p[1], p[2]) for p in pts]
    return els, bonds, mols, pos, width


def animation(text: str, balance_it: bool = True):
    """(Animation, equation text) for *text*; BuildError when a side's
    copies cannot be whole molecules or the atoms of the sides differ."""
    left, right, _rev = mb.parse_reaction(text)
    coefs = _coefficients(left, right, balance_it)
    if any(c.denominator != 1 for c in coefs):
        raise BuildError("A film needs whole coefficients: double the "
                         "equation (1/2 O2 has no half molecule to move).")
    sides = []
    for terms, cs in ((left, coefs[:len(left)]),
                      (right, coefs[len(left):])):
        copies = []
        for t, c in zip(terms, cs):
            pts = _centred(t.molecule)
            copies += [(t.molecule, pts)] * int(c)
        sides.append(copies)
    total = sum(len(m.atoms) for side in sides for m, _p in side)
    if total > 2 * 400:
        raise BuildError("That reaction moves too many atoms for a film.")
    cr_, cp_ = _side(sides[0], 1.2, 0.0), _side(sides[1], 1.2, 0.0)
    if sorted(cr_[0]) != sorted(cp_[0]):
        raise BuildError("The two sides do not hold the same atoms — "
                         "check the coefficients.")
    sr, sp = _side(sides[0], 1.8, 0.0), _side(sides[1], 1.8, 0.0)
    x0 = max(sr[4], sp[4]) / 2 + max(cr_[4], cp_[4]) / 2 + 0.5
    ar, dp = _side(sides[0], 1.8, -x0), _side(sides[1], 1.8, x0)
    reac = rx.Side(cr_[0], cr_[1], cr_[2], ar[3], cr_[3])
    prod = rx.Side(cp_[0], cp_[1], cp_[2], dp[3], cp_[3])

    def term(c, t):
        return (f"{c} " if c != 1 else "") + t.molecule.formula
    eq = (" + ".join(term(c, t) for c, t in zip(coefs, left)) + " → " +
          " + ".join(term(c, t) for c, t in zip(coefs[len(left):], right)))
    film = rx.build(reac, prod, eq)
    if film is None:
        raise BuildError("The reactant and product atoms cannot be paired.")
    return film, eq


def _table(values) -> str:
    return "[" + ", ".join(f"[{mb._n(p)}, {mb._n(v)}]"
                           for p, v in values) + "]"


def _at(anim, i, samples):
    """'[lookup(rx_t, ...), …]' — atom *i*'s position over the film, nm."""
    keys = [k / (samples - 1) for k in range(samples)]
    pos = [anim.position(i, p) for p in keys]
    return "[" + ", ".join(
        f"lookup({VARIABLE}, {_table((p, q[c] * mb.NM) for p, q in zip(keys, pos))})"
        for c in range(3)) + "]"


def animated_program(anim, equation: str, samples: int = SAMPLES,
                     fn: int = 12) -> tuple:
    """(OpenSCAD program, stats) of the film driven by the `rx_t` slider."""
    n = len(anim.reac.elements)
    where = [_at(anim, i, samples) for i in range(n)]
    lines = [f'color("{cr.colour(el)}") translate({where[i]}) '
             f"sphere(r = {mb._n(mb.ball_radius(el, 'ball_and_stick') * mb.NM)}"
             f", $fn = {fn});  // {el}{i + 1}"
             for i, el in enumerate(anim.reac.elements)]

    def stick(i, j):
        r = mb._n(STICK * mb.NM)
        return (f"  hull() {{ translate({where[i]}) sphere(r = {r}, "
                f"$fn = 8); translate({where[j]}) sphere(r = {r}, "
                f"$fn = 8); }}")
    rb = {frozenset(b[:2]) for b in anim.rbonds}
    pb = {frozenset(b[:2]) for b in anim.pbonds}
    kept, broken, formed = rb & pb, rb - pb, pb - rb
    out = [f"// {equation} — a film: drag or play {VARIABLE} (View ▸ "
           "Customizer).", "", "/* [Motion] */",
           "// Reaction progress: reactants approach, bonds break, atoms "
           "rearrange, products separate",
           f"{VARIABLE} = 0;  // [0:0.01:1]", "",
           "module Reaction_film() {"]
    out += ["  " + line for line in lines]
    if kept:
        out += ['  color("#9a9a9a") {  // Bonds that stay']
        out += ["  " + stick(*sorted(b)) for b in sorted(kept, key=sorted)]
        out += ["  }"]
    if broken:
        out += [f'  if ({VARIABLE} < {rx.BREAK}) color("#c9a227") {{  '
                "// Bonds that break"]
        out += ["  " + stick(*sorted(b)) for b in sorted(broken, key=sorted)]
        out += ["  }"]
    if formed:
        out += [f'  if ({VARIABLE} >= {rx.FORM}) color("#2e9e6a") {{  '
                "// Bonds that form"]
        out += ["  " + stick(*sorted(b)) for b in sorted(formed, key=sorted)]
        out += ["  }"]
    out += ["}", "", "Reaction_film();  // Reaction film"]
    return "\n".join(out) + "\n", {
        "equation": equation, "atoms": n, "bonds_kept": len(kept),
        "bonds_broken": len(broken), "bonds_formed": len(formed),
        "slider": VARIABLE, "unit": "nm"}
