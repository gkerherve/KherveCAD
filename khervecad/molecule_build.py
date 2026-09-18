"""The Compound Builder's programs: molecules and chemical reactions as
OpenSCAD (Qt-free but `apply`).

A **molecule** (molecule.py: SMILES -> 3D atoms) is drawn as one Object:

- ball and stick — atoms at 0.35 x their van der Waals radius, bonds as
  sticks split at the middle so each half wears its atom's colour, a
  double bond two thinner sticks and a triple three, side by side in
  the molecule's local plane; an aromatic bond keeps its stick and
  gains a thin one on the ring's side;
- space filling — atoms at their full van der Waals radius, no sticks;
- sticks — thin bonds only, small balls at the joints;
- lattice — ball and stick with small balls, for graphene, graphite and
  nanotubes (carbon_nano), where full-size balls hide the rings.

A **reaction** is written the way chemists write it —
``2 H2 + O2 -> 2 H2O``, ``CH4 + 2 O2 -> CO2 + 2 H2O``, ``N2 + 3 H2 <=>
2 NH3``, ``1/2 O2``, ``smiles:CCO`` for anything outside the library —
checked for atom and charge balance (or balanced: the smallest whole
coefficients from the null space of the element matrix, exact in
fractions) and laid out left to right in the XZ plane, read from the
front: a coefficient up to REPEAT_MAX places that many copies of the
molecule side by side (2 H2 draws two H2 molecules) rather than a "2"
in front of one, so the picture reads as molecules and "+"/arrow
symbols only, no coefficient numerals; a larger or fractional
coefficient falls back to a numeral prefix so the model stays light.
The formula under every molecule is optional (off by default).

Everything is in NANOMETRES; the triangles are counted before anything
is applied.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache

from . import molecule as mol
from .crystal import colour
from .molecule_library import COMPOUNDS, get as get_compound

NM = 0.1                                   # nm per Å
STYLES = ("ball_and_stick", "space_filling", "sticks", "lattice")
BALL = 0.35                                # ball and stick: x vdW radius
#: lattice style: small balls, so a graphene honeycomb or a nanotube's
#: wall reads as its rings instead of a heap of spheres
LATTICE_BALL = 0.17
STICK = 0.12                               # bond radius, Å
#: (offset Å, radius Å) of the sticks of one bond, by order
_STICKS = {1.0: [(0.0, STICK)],
           2.0: [(-0.17, 0.08), (0.17, 0.08)],
           3.0: [(-0.24, 0.07), (0.0, 0.07), (0.24, 0.07)],
           1.5: [(0.0, STICK), (0.24, 0.045)]}
BUDGET = 400_000
TEXT_COLOUR = "#3a3f47"
ARROW_COLOUR = "#3a3f47"
_ARROWS = ("<=>", "<->", "⇌", "->", "→", "=>", "=")


class BuildError(ValueError):
    """A molecule or reaction that cannot be built; says what to do."""


# ---------------------------------------------------------------- text
def _n(x: float) -> str:
    s = f"{x:.5f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def _vec(p, k=NM) -> str:
    return "[" + ", ".join(_n(v * k) for v in p) + "]"


def _ident(text: str) -> str:
    word = re.sub(r"\W+", "_", text).strip("_") or "Molecule"
    word = word[0].upper() + word[1:]
    return word if word[0].isalpha() else "M_" + word


def _label(text: str) -> str:
    """Safe in a // comment and an Object name."""
    return re.sub(r"[\r\n]", " ", text)


@lru_cache(maxsize=None)
def _tris(kind: str, fn: int) -> int:
    from . import mesh
    from .model import CadNode
    if kind == "sphere":
        node = CadNode("sphere", "S", dict(radius=1.0, segments=fn))
    else:
        node = CadNode("cylinder", "C", dict(height=1.0, radius_bottom=0.1,
                                            radius_top=0.1, segments=fn))
    return len(mesh.tessellate(node))


# ------------------------------------------------------------ geometry
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _norm(v):
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _unit(v):
    n = _norm(v)
    return (v[0] / n, v[1] / n, v[2] / n) if n > 1e-12 else (1.0, 0.0, 0.0)


def _perp(v, u):
    k = v[0] * u[0] + v[1] * u[1] + v[2] * u[2]
    return (v[0] - k * u[0], v[1] - k * u[1], v[2] - k * u[2])


def _any_perp(u):
    helper = (0.0, 0.0, 1.0) if abs(u[2]) < 0.9 else (0.0, 1.0, 0.0)
    return _unit((helper[1] * u[2] - helper[2] * u[1],
                  helper[2] * u[0] - helper[0] * u[2],
                  helper[0] * u[1] - helper[1] * u[0]))


def _stick(p0, p1, r, fn) -> str:
    """A cylinder from p0 to p1 (Å): OpenSCAD's rotate([0, theta, phi])
    turns +z onto the bond."""
    d = _sub(p1, p0)
    L = _norm(d)
    theta = math.degrees(math.acos(max(-1.0, min(1.0, d[2] / L))))
    phi = math.degrees(math.atan2(d[1], d[0]))
    return (f"translate({_vec(p0)}) rotate([0, {_n(theta)}, {_n(phi)}]) "
            f"cylinder(h = {_n(L * NM)}, r = {_n(r * NM)}, $fn = {fn});")


def ball_radius(element: str, style: str) -> float:
    """Å."""
    if style == "space_filling":
        return mol.vdw(element)
    if style == "sticks":
        return STICK
    if style == "lattice":
        return LATTICE_BALL * mol.vdw(element)
    return BALL * mol.vdw(element)


def geometry(m: mol.Molecule, style: str = "ball_and_stick", fn: int = 16):
    """(lines, triangles) of one molecule: a colour block per element
    holding its balls and the half-bonds that start at them."""
    atoms = m.atoms
    nbrs = [[] for _ in atoms]
    for i, j, o in m.bonds:
        nbrs[i].append((j, o))
        nbrs[j].append((i, o))
    rings = mol.find_rings(len(atoms), nbrs)
    groups, tris = {}, 0
    per_ball, per_stick = _tris("sphere", fn), _tris("cylinder", fn)
    for el, x, y, z in atoms:
        r = ball_radius(el, style) * NM
        groups.setdefault(el, []).append(
            f"translate({_vec((x, y, z))}) sphere(r = {_n(r)}, $fn = {fn});"
            f"  // {el}")
        tris += per_ball
    if style != "space_filling":
        for i, j, o in m.bonds:
            a, b = atoms[i][1:], atoms[j][1:]
            u = _unit(_sub(b, a))
            ring = next((r for r in rings if i in r and j in r), None)
            if ring is not None:
                centre = tuple(sum(atoms[k][1 + c] for k in ring) / len(ring)
                               for c in range(3))
                side = _perp(_sub(centre, a), u)
            else:
                ref = next((atoms[k][1:] for k, _o in nbrs[i] if k != j),
                           None) or next((atoms[k][1:] for k, _o in nbrs[j]
                                          if k != i), None)
                side = _perp(_sub(ref, a), u) if ref else (0.0, 0.0, 0.0)
            side = _unit(side) if _norm(side) > 1e-9 else _any_perp(u)
            mid = tuple((a[c] + b[c]) / 2 for c in range(3))
            sticks = _STICKS.get(o, _STICKS[1.0])
            if style == "sticks":
                sticks = [(off, min(r, STICK)) for off, r in sticks]
            for off, r in sticks:
                s = tuple(side[c] * off for c in range(3))
                p0 = tuple(a[c] + s[c] for c in range(3))
                pm = tuple(mid[c] + s[c] for c in range(3))
                p1 = tuple(b[c] + s[c] for c in range(3))
                label = f"{atoms[i][0]}-{atoms[j][0]} bond"
                groups[atoms[i][0]].append(_stick(p0, pm, r, fn)
                                           + f"  // {label}")
                groups[atoms[j][0]].append(_stick(pm, p1, r, fn)
                                           + f"  // {label}")
                tris += 2 * per_stick
    lines = []
    for el, rows in groups.items():
        lines.append(f'color("{colour(el)}") {{  // {el}')
        lines += ["  " + row for row in rows]
        lines.append("}")
    return lines, tris


def extent(m: mol.Molecule, style: str):
    """(min, max) corners in nm, balls included."""
    lo = [min((a[1 + c] - ball_radius(a[0], style)) for a in m.atoms) * NM
          for c in range(3)]
    hi = [max((a[1 + c] + ball_radius(a[0], style)) for a in m.atoms) * NM
          for c in range(3)]
    return lo, hi


def _module(name, lines) -> str:
    body = "\n".join("  " + line for line in lines)
    return f"module {name}() {{\n{body}\n}}\n"


def _header(title, lines):
    return "\n".join([f"// {title}"] + [f"// {line}" for line in lines]
                     + ["// UNITS: nanometres. Built by KherveCAD's Compound "
                        "Builder (VSEPR placement + relaxation: a sketch of "
                        "the shape, not a quantum-chemistry optimum)."]) + "\n"


# ------------------------------------------------------------ molecules
def resolve(text: str) -> mol.Molecule:
    """A species by library key or name, formula (charge included:
    NH4+, SO4^2-) or ``smiles:...``."""
    t = text.strip()
    if not t:
        raise BuildError("An empty species.")
    if t.lower().startswith("smiles:"):
        smiles = t[7:].strip()
        try:
            return mol.from_smiles(smiles, name=smiles)
        except mol.SmilesError as exc:
            raise BuildError(f"SMILES '{smiles}': {exc}")
    try:
        return get_compound(t)
    except KeyError:
        pass
    key = by_formula(t)
    if key:
        return get_compound(key)
    raise BuildError(
        f"'{t}' is not in the compound library (by key, name or "
        "formula). Give its SMILES as smiles:..., e.g. smiles:CCO for "
        "ethanol.")


def _charge_of(text: str):
    """(formula body, charge): a magnitude counts only after ^ or a space
    ("SO4^2-", "SO4 2-", "Fe^3+"); otherwise the trailing signs do
    ("NH4+" is +1, not +4; "SO4--" is -2)."""
    t = text.strip()
    m = re.match(r"^(.*?)(?:\s+|\^)(\d*)([+-])$", t)
    if m:
        mag = int(m.group(2)) if m.group(2) else 1
        return m.group(1), mag * (1 if m.group(3) == "+" else -1)
    m = re.match(r"^(.*?)([+-]+)$", t)
    if m and m.group(1):
        signs = m.group(2)
        return m.group(1), len(signs) * (1 if signs[0] == "+" else -1)
    return t, 0


def by_formula(text: str) -> str | None:
    """The first library key with this formula and charge."""
    body, charge = _charge_of(text)
    try:
        want = mol.hill_formula(mol.formula_counts(body))
    except ValueError:
        return None
    for key, (_name, _smiles, _cat, formula) in COMPOUNDS.items():
        fbody, fcharge = _charge_of(formula)
        try:
            have = mol.hill_formula(mol.formula_counts(fbody))
        except ValueError:
            continue
        if have == want and fcharge == charge:
            return key
    return None


def molecule_program(m: mol.Molecule, style="ball_and_stick", fn=16,
                     name=""):
    """(program, stats) for one molecule, placed at the origin."""
    if style not in STYLES:
        raise BuildError(f"style is one of {', '.join(STYLES)}.")
    title = name or m.name
    lines, tris = geometry(m, style, fn)
    if tris > BUDGET:
        raise BuildError(f"About {tris:,} triangles — draw it as sticks or "
                         "lower the segments.")
    ident = _ident(m.key or title)
    code = _header(f"{title} ({m.formula})",
                   [(f"SMILES {m.smiles}; " if m.smiles else
                     "Built on its lattice; ") + f"{len(m.atoms)} atoms, "
                    f"{len(m.bonds)} bonds, {m.mass:.2f} g/mol."])
    code += "\n" + _module(ident, lines)
    code += f"\n{ident}();  // {_label(title)} ({m.formula})\n"
    return code, {"name": title, "formula": m.formula, "smiles": m.smiles,
                  "atoms": len(m.atoms), "bonds": len(m.bonds),
                  "molar_mass": round(m.mass, 3), "triangles": tris,
                  "unit": "nm"}


# ------------------------------------------------------------ reactions
@dataclass
class Term:
    coef: Fraction | None
    text: str
    molecule: mol.Molecule


def parse_reaction(text: str):
    """(reactants, products, reversible): lists of Term."""
    s = text.strip()
    m = re.search(r"\s*(⇌|→)\s*", s) or \
        re.search(r"\s(<=>|<->|->|=>|=)\s", s)
    if not m:
        raise BuildError("No arrow: write the reaction as 'A + B -> C' "
                         "(or <=>, →, ⇌, =), with spaces round it.")
    reversible = m.group(1) in ("<=>", "<->", "⇌")
    sides = []
    for part in (s[:m.start()], s[m.end():]):
        terms = []
        for chunk in re.split(r"\s\+\s", part.strip()):
            if not chunk.strip():
                raise BuildError("An empty term: every '+' needs a species "
                                 "on both sides.")
            t = re.match(r"^\s*(\d+/\d+|\d+(?:\.\d+)?)?\s*(.+?)\s*$", chunk)
            coef = Fraction(t.group(1)) if t.group(1) else None
            text_ = t.group(2)
            if re.match(r"^\d", text_) and not text_.lower().startswith(
                    "smiles:"):
                raise BuildError(f"Put a space after the coefficient in "
                                 f"'{chunk.strip()}'.")
            terms.append(Term(coef, text_, resolve(text_)))
        if not terms:
            raise BuildError("A side of the reaction is empty.")
        sides.append(terms)
    return sides[0], sides[1], reversible


def _counts(m: mol.Molecule):
    counts = m.composition()
    return counts, m.charge


def balance_check(left, right, coefs):
    """{element or 'charge': (left, right)} and whether they agree."""
    table = {}
    for side, terms, cs in ((0, left, coefs[:len(left)]),
                            (1, right, coefs[len(left):])):
        for term, c in zip(terms, cs):
            counts, charge = _counts(term.molecule)
            for el, k in list(counts.items()) + [("charge", charge)]:
                row = table.setdefault(el, [Fraction(0), Fraction(0)])
                row[side] += c * k
    ok = all(a == b for a, b in table.values())
    return {k: (float(a), float(b)) for k, (a, b) in table.items()}, ok


def balance(left, right):
    """The smallest whole coefficients that balance atoms and charge;
    BuildError when there are none or more than one family of them."""
    species = left + right
    elements = sorted({el for t in species for el in t.molecule.composition()})
    rows = []
    for el in elements + ["charge"]:
        row = []
        for idx, t in enumerate(species):
            counts, charge = _counts(t.molecule)
            k = charge if el == "charge" else counts.get(el, 0)
            row.append(Fraction(k if idx < len(left) else -k))
        rows.append(row)
    n = len(species)
    # reduced row echelon form, exact
    pivots, r = [], 0
    for col in range(n):
        piv = next((i for i in range(r, len(rows)) if rows[i][col] != 0),
                   None)
        if piv is None:
            continue
        rows[r], rows[piv] = rows[piv], rows[r]
        lead = rows[r][col]
        rows[r] = [v / lead for v in rows[r]]
        for i in range(len(rows)):
            if i != r and rows[i][col] != 0:
                f = rows[i][col]
                rows[i] = [a - f * b for a, b in zip(rows[i], rows[r])]
        pivots.append(col)
        r += 1
    free = [c for c in range(n) if c not in pivots]
    if len(free) != 1:
        raise BuildError(
            "That reaction cannot be balanced in one way (" +
            ("no solution" if not free else "several independent ways") +
            ") — give the coefficients yourself.")
    x = [Fraction(0)] * n
    x[free[0]] = Fraction(1)
    for i, col in enumerate(pivots):
        x[col] = -rows[i][free[0]]
    if all(v < 0 for v in x):
        x = [-v for v in x]
    if any(v <= 0 for v in x):
        raise BuildError("No balance with every species present — check "
                         "the species.")
    lcm = 1
    for v in x:
        lcm = lcm * v.denominator // math.gcd(lcm, v.denominator)
    ints = [int(v * lcm) for v in x]
    g = 0
    for v in ints:
        g = math.gcd(g, v)
    return [Fraction(v // g) for v in ints]


def _fmt_coef(c: Fraction) -> str:
    return str(c.numerator) if c.denominator == 1 else \
        f"{c.numerator}/{c.denominator}"


def equation_text(left, right, coefs, reversible) -> str:
    def side(terms, cs):
        return " + ".join((f"{_fmt_coef(c)} " if c != 1 else "")
                          + t.molecule.formula for t, c in zip(terms, cs))
    arrow = "⇌" if reversible else "→"
    return (f"{side(left, coefs[:len(left)])} {arrow} "
            f"{side(right, coefs[len(left):])}")


def _text(s, x, z, size) -> str:
    """Upright text facing -Y (read from the front), left edge at x."""
    return (f"translate([{_n(x)}, 0, {_n(z)}]) rotate([90, 0, 0]) "
            f"linear_extrude(height = {_n(size * 0.12)}) "
            f"text(\"{s}\", size = {_n(size)});  // {s}")


def _text_width(s, size) -> float:
    return 0.62 * size * len(s)


#: a coefficient up to this many draws that many copies of the molecule
#: side by side instead of a numeral in front of one; above it (or for
#: a fraction) a numeral prefix is kept so the model stays light.
REPEAT_MAX = 12


def reaction_program(text: str, balance_it: bool = True,
                     style: str = "ball_and_stick", fn: int = 16,
                     labels: bool = False):
    """(program, stats) for a reaction laid out left to right."""
    if style not in STYLES:
        raise BuildError(f"style is one of {', '.join(STYLES)}.")
    left, right, reversible = parse_reaction(text)
    given = [t.coef for t in left + right]
    if balance_it and any(c is None for c in given):
        coefs = balance(left, right)
        if any(c is not None for c in given):
            # keep the user's ratio when they gave some: only fill gaps
            ratio = next(g / c for g, c in zip(given, coefs) if g)
            coefs = [g if g is not None else c * ratio
                     for g, c in zip(given, coefs)]
    elif balance_it:
        coefs = balance(left, right)
    else:
        coefs = [c if c is not None else Fraction(1) for c in given]
    table, ok = balance_check(left, right, coefs)
    species = {}
    for t in left + right:
        species.setdefault(t.molecule.smiles, t.molecule)
    sizes = [(hi[2] - lo[2]) for lo, hi in
             (extent(m, style) for m in species.values())]
    size = max(0.22, min(0.6, 0.35 * max(sizes)))      # text height, nm
    gap = 0.35 * size + 0.15
    modules, lines, tris = [], [], 0
    idents = {}
    for smiles, m in species.items():
        ident = _ident(m.key or m.formula or m.name) + "_mol"
        while ident in idents.values():
            ident += "_"
        idents[smiles] = ident
        body, t = geometry(m, style, fn)
        modules.append(_module(ident, body))
        species[smiles] = (m, t)
    x = 0.0
    low = min(extent(m, style)[0][2] for m, _t in species.values())
    for side_idx, (terms, cs) in enumerate(
            ((left, coefs[:len(left)]), (right, coefs[len(left):]))):
        first = True
        for term, c in zip(terms, cs):
            repeats = (int(c) if c.denominator == 1 and 1 <= c <= REPEAT_MAX
                       else None)
            for i in range(repeats or 1):
                if not first:
                    lines.append(_text("+", x, -size / 2, size))
                    x += _text_width("+", size) + gap
                first = False
                if repeats is None and i == 0 and c != 1:
                    s = _fmt_coef(c)
                    lines.append(_text(s, x, -size / 2, size))
                    x += _text_width(s, size) + gap * 0.6
                m, t = species[term.molecule.smiles]
                lo, hi = extent(m, style)
                cx = x - lo[0]
                lines.append(f"translate([{_n(cx)}, 0, 0]) "
                             f"{idents[term.molecule.smiles]}();  "
                             f"// {_label(m.name)}")
                tris += t
                if labels:
                    s = m.formula
                    w = _text_width(s, size * 0.6)
                    lines.append(_text(s, cx + (lo[0] + hi[0]) / 2 - w / 2,
                                       low - size * 1.2, size * 0.6))
                x = cx + hi[0] + gap
        if side_idx == 0:
            L = max(1.0, 3 * size)
            if reversible:
                for dz, sgn in ((size * 0.18, 1), (-size * 0.18, -1)):
                    start = x if sgn > 0 else x + L
                    lines += _arrow(start, dz, L * sgn, size)
            else:
                lines += _arrow(x, 0.0, L, size)
            tris += 2 * _tris("cylinder", 24)
            x += L + gap
    title = equation_text(left, right, coefs, reversible)
    body = [f'color("{TEXT_COLOUR}") {{  // Coefficients, signs and '
            "labels"] + ["  " + ln for ln in lines if "text(" in ln] + ["}"]
    body += [ln for ln in lines if "text(" not in ln and "cylinder" not in ln]
    arrows = [ln for ln in lines if "cylinder" in ln]
    if arrows:
        body += [f'color("{ARROW_COLOUR}") {{  // Arrow'] + \
            ["  " + ln for ln in arrows] + ["}"]
    if tris > BUDGET:
        raise BuildError(f"About {tris:,} triangles — use the sticks "
                         "style.")
    code = _header(f"Reaction: {title}",
                   ["balanced" if ok else "NOT balanced: " + ", ".join(
                       f"{k} {a:g} -> {b:g}" for k, (a, b) in table.items()
                       if a != b)])
    code += "\n" + "\n".join(modules) + "\n" + _module("Reaction", body)
    code += f"\nReaction();  // {_label(title)}\n"
    return code, {"equation": title, "balanced": ok,
                  "coefficients": [_fmt_coef(c) for c in coefs],
                  "species": [{"formula": t.molecule.formula,
                               "name": t.molecule.name,
                               "side": "reactant" if i < len(left)
                               else "product"}
                              for i, t in enumerate(left + right)],
                  "atom_balance": table, "triangles": tris, "unit": "nm"}


def _arrow(x, z, L, size):
    """A shaft and a cone along +x (or -x for negative L)."""
    sgn = 1 if L > 0 else -1
    L = abs(L)
    head = min(0.35 * size + 0.1, L * 0.4)
    r = 0.05 * size + 0.02
    yaw = 0 if sgn > 0 else 180
    return [
        f"translate([{_n(x)}, 0, {_n(z)}]) rotate([0, 90, {yaw}]) "
        f"cylinder(h = {_n(L - head)}, r = {_n(r)}, $fn = 24);  // Arrow shaft",
        f"translate([{_n(x + sgn * (L - head))}, 0, {_n(z)}]) "
        f"rotate([0, 90, {yaw}]) cylinder(h = {_n(head)}, r1 = {_n(3 * r)}, "
        f"r2 = 0, $fn = 24);  // Arrow head"]


# ---------------------------------------------------------------- apply
def apply(window, code: str, stats: dict, fn: int = 16) -> dict:
    """Add a molecule or reaction program to the window's document: an
    empty document becomes nanometres, round objects drop to *fn*
    segments. One undo step."""
    from .scadparse import parse_scad
    model = window.model
    notes = []
    if model.unit != "nm":
        if not model.root.children:
            model.set_unit("nm")
            notes.append("The document unit is now nanometres.")
        else:
            notes.append(
                f"Molecules are in nanometres but this document is in "
                f"{model.unit}: a 0.1 nm bond reads as 0.1 {model.unit}. "
                "Start a new document for chemistry.")
    if model.global_fn_on and model.global_fn > fn:
        model.set_global_fn(True, fn)
        notes.append(f"Round objects now use {fn} segments.")
    root, warnings = parse_scad(code)
    if not root.children:
        raise BuildError("The program produced nothing: "
                         + "; ".join(warnings[:3]))
    objects = []
    for child in list(root.children):
        root.remove(child)
        model.root.add(child)
        if child.type == "component":
            objects.append({"id": child.id, "name": child.name})
    model.group_variables()
    model.structure_changed.emit()
    out = dict(stats)
    out["objects"] = objects
    out["notes"] = notes
    if warnings:
        out["warnings"] = warnings[:8]
    return out


# ------------------------------------------------------------------ MCP
def list_molecules(params: dict) -> dict:
    from .molecule_library import CATEGORIES
    key = params.get("compound")
    if key:
        m = resolve(str(key))              # key, name or formula
        out = m.summary()
        out["atoms_nm"] = [[el, round(x * NM, 4), round(y * NM, 4),
                            round(z * NM, 4)] for el, x, y, z in m.atoms]
        out["bonds"] = [[i, j, o] for i, j, o in m.bonds]
        return out
    cat = params.get("category")
    rows = [{"key": k, "name": name, "formula": formula.replace(" ", ""),
             "smiles": smiles, "category": c}
            for k, (name, smiles, c, formula) in COMPOUNDS.items()
            if not cat or c.lower() == str(cat).lower()]
    from .carbon_nano import STRUCTURES
    cages = [{"key": k, "name": name, "category": c}
             for k, (name, c, _b) in STRUCTURES.items()]
    return {"categories": list(CATEGORIES), "compounds": rows,
            "carbon_structures": cages,
            "carbon_note": "Build a cage with compound: its key (c60). "
                           "Graphene, graphite and nanotubes of any size "
                           "and (n, m) are Part Library parts: list_parts "
                           "category 'Surfaces: Graphene & graphite' / "
                           "'Crystals (nanotubes)'.",
            "styles": list(STYLES), "units": "nm"}


def _style(params):
    style = str(params.get("style", "ball_and_stick"))
    if style not in STYLES:
        raise BuildError(f"style is one of {', '.join(STYLES)}.")
    fn = int(params.get("segments", 16))
    if not 4 <= fn <= 64:
        raise BuildError("segments runs from 4 to 64.")
    return style, fn


def build_molecule(window, params: dict) -> dict:
    style, fn = _style(params)
    if params.get("smiles"):
        try:
            m = mol.from_smiles(str(params["smiles"]),
                                name=str(params.get("name") or
                                         params["smiles"]))
        except mol.SmilesError as exc:
            raise BuildError(f"SMILES: {exc}")
    elif params.get("compound"):
        m = resolve(str(params["compound"]))
    else:
        raise BuildError("Give a compound (library key, name or formula) "
                         "or a smiles.")
    code, stats = molecule_program(m, style, fn, str(params.get("name") or
                                                     ""))
    if params.get("dry_run"):
        stats["dry_run"] = True
        return stats
    return apply(window, code, stats, fn)


def build_reaction(window, params: dict) -> dict:
    style, fn = _style(params)
    text = params.get("equation")
    if not isinstance(text, str) or not text.strip():
        raise BuildError("Give the equation, e.g. '2 H2 + O2 -> 2 H2O'.")
    code, stats = reaction_program(text, bool(params.get("balance", True)),
                                   style, fn,
                                   bool(params.get("labels", True)))
    if params.get("dry_run"):
        stats["dry_run"] = True
        return stats
    return apply(window, code, stats, fn)
