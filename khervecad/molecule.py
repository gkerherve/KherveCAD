"""Molecules for the Compound Builder (Qt-free): SMILES in, 3D atoms out.

A molecule is written in SMILES — the line notation every chemist and
every assistant knows (water ``O``, ethanol ``CCO``, benzene
``c1ccccc1``, caffeine ``Cn1cnc2c1c(=O)n(C)c(=O)n2C``) — and turned into
3D coordinates here, with no chemistry package:

1. `parse_smiles` reads the organic subset (B C N O P S F Cl Br I and
   aromatic b c n o p s), bracket atoms (``[NH4+]``, ``[O-]``,
   ``[Xe]``, ``[nH]``), bond orders ``- = # :``, branches, ring closures
   (digits and ``%nn``) and ``.`` between fragments; chirality marks are
   read and ignored. Implicit hydrogens come from the usual valences and
   become real atoms.
2. `embed` gives each atom its electron domains — neighbours plus lone
   pairs (valence electrons minus bonds minus charge, halved) — and so
   its shape: linear, trigonal, tetrahedral, trigonal-bipyramidal or
   octahedral, lone pairs taking the right slots (XeF4 comes out square,
   water bent, its angle squeezed by the lone pairs). RINGS are placed
   whole the moment the walk reaches them — a regular polygon (puckered
   for sp3 atoms), a fused ring built on the edge it shares — and every
   other atom goes in a free slot of its neighbour's shape, turned so
   chains run anti and double bonds stay planar. A light relaxation
   (bond lengths, 1-3 distances for the angles, a floor on non-bonded
   distances) then settles it.
3. Bond lengths are the covalent radii summed and shortened for
   aromatic (x0.93), double (x0.87) and triple (x0.79) bonds: C-C 1.52,
   c:c 1.41, C=C 1.32, C#C 1.20 Å.

Coordinates are in ÅNGSTRÖM; molecule_build writes nanometres.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from functools import lru_cache

from .crystal import ELEMENTS

#: van der Waals radii, Å (Bondi 1964; Mantina et al. 2009 for the rest)
VDW = {"H": 1.20, "He": 1.40, "Li": 1.82, "Be": 1.53, "B": 1.92,
       "C": 1.70, "N": 1.55, "O": 1.52, "F": 1.47, "Ne": 1.54,
       "Na": 2.27, "Mg": 1.73, "Al": 1.84, "Si": 2.10, "P": 1.80,
       "S": 1.80, "Cl": 1.75, "Ar": 1.88, "K": 2.75, "Ca": 2.31,
       "Ga": 1.87, "Ge": 2.11, "As": 1.85, "Se": 1.90, "Br": 1.85,
       "Kr": 2.02, "Rb": 3.03, "Sr": 2.49, "In": 1.93, "Sn": 2.17,
       "Sb": 2.06, "Te": 2.06, "I": 1.98, "Xe": 2.16, "Cs": 3.43,
       "Ba": 2.68, "Tl": 1.96, "Pb": 2.02, "Bi": 2.07}
#: valence electrons, for lone pairs (metals: none counted)
VALENCE_ELECTRONS = {"H": 1, "B": 3, "C": 4, "N": 5, "O": 6, "F": 7,
                     "Si": 4, "P": 5, "S": 6, "Cl": 7, "Ge": 4, "As": 5,
                     "Se": 6, "Br": 7, "Sn": 4, "Sb": 5, "Te": 6, "I": 7,
                     "He": 2, "Ne": 8, "Ar": 8, "Kr": 8, "Xe": 8}
#: normal valences of the SMILES organic subset (implicit hydrogens)
VALENCES = {"B": (3,), "C": (4,), "N": (3, 5), "O": (2,), "P": (3, 5),
            "S": (2, 4, 6), "F": (1,), "Cl": (1,), "Br": (1,), "I": (1,)}
_ORGANIC = ("Cl", "Br", "B", "C", "N", "O", "P", "S", "F", "I")
_AROMATIC = {"b": "B", "c": "C", "n": "N", "o": "O", "p": "P", "s": "S",
             "se": "Se", "as": "As"}
_BOND = {"-": 1.0, "=": 2.0, "#": 3.0, ":": 1.5, "/": 1.0, "\\": 1.0}
_SHORTEN = {1.0: 1.0, 1.5: 0.93, 2.0: 0.87, 3.0: 0.79}
#: most atoms (hydrogens included) one molecule may have
MAX_ATOMS = 400


def vdw(element: str) -> float:
    return VDW.get(element, 2.0)


@dataclass
class Molecule:
    """Atoms (element, x, y, z Å), bonds (i, j, order), and metadata."""
    name: str
    smiles: str
    atoms: list = field(default_factory=list)
    bonds: list = field(default_factory=list)
    charges: list = field(default_factory=list)
    key: str = ""
    category: str = ""

    def composition(self) -> dict:
        counts = {}
        for el, *_p in self.atoms:
            counts[el] = counts.get(el, 0) + 1
        return counts

    @property
    def charge(self) -> int:
        return sum(self.charges)

    @property
    def formula(self) -> str:
        return hill_formula(self.composition(), self.charge)

    @property
    def mass(self) -> float:
        return sum(ELEMENTS[el][2] for el, *_p in self.atoms)

    def summary(self) -> dict:
        return {"key": self.key, "name": self.name, "formula": self.formula,
                "smiles": self.smiles, "category": self.category,
                "atoms": len(self.atoms), "bonds": len(self.bonds),
                "charge": self.charge, "molar_mass": round(self.mass, 3)}


def hill_formula(counts: dict, charge: int = 0) -> str:
    """Hill order: C, then H, then the rest alphabetically (all
    alphabetical without carbon); charge appended (H4N+, O4S2-)."""
    order = (["C", "H"] + sorted(e for e in counts if e not in ("C", "H"))
             if "C" in counts else sorted(counts))
    text = "".join(f"{e}{counts[e] if counts[e] > 1 else ''}"
                   for e in order if e in counts)
    if charge:
        mag = abs(charge)
        # "O4S 2-", not "O4S2-": a bare 2 would read as a subscript
        text += (f" {mag}" if mag > 1 else "") + ("+" if charge > 0
                                                 else "-")
    return text


# ------------------------------------------------------------- parsing
_BRACKET = re.compile(
    r"\[(\d*)([A-Z][a-z]?|se|as|[bcnops])(@{0,2}(?:TH|AL|SP|TB|OH)?\d*)"
    r"(H\d*)?([+-]{1,3}\d*)?(?::\d+)?\]")


class SmilesError(ValueError):
    """A SMILES string this reader cannot take; says where."""


def parse_smiles(text: str):
    """(atoms, bonds): atoms are dicts {element, aromatic, charge, h}
    (h = explicit hydrogen count or None), bonds (i, j, order)."""
    s = text.strip()
    if not s:
        raise SmilesError("An empty SMILES string.")
    atoms, bonds, stack, rings = [], [], [], {}
    prev, order, i = None, None, 0

    def add_bond(a, b, o):
        if a == b or any({a, b} == {x, y} for x, y, _o in bonds):
            raise SmilesError(f"A bond from atom {a + 1} to itself or "
                              "twice.")
        both = atoms[a]["aromatic"] and atoms[b]["aromatic"]
        bonds.append((a, b, o if o is not None else (1.5 if both else 1.0)))

    while i < len(s):
        ch = s[i]
        if ch == "(":
            if prev is None:
                raise SmilesError(f"A branch with nothing before it "
                                  f"(position {i + 1}).")
            stack.append(prev)
            i += 1
            continue
        if ch == ")":
            if not stack:
                raise SmilesError(f"An unmatched ')' at position {i + 1}.")
            prev = stack.pop()
            i += 1
            continue
        if ch in _BOND:
            order = _BOND[ch]
            i += 1
            continue
        if ch == ".":
            prev, order = None, None
            i += 1
            continue
        if ch.isdigit() or ch == "%":
            if ch == "%":
                num, i = s[i + 1:i + 3], i + 3
            else:
                num, i = ch, i + 1
            if prev is None:
                raise SmilesError("A ring number with no atom before it.")
            if num in rings:
                start, o0 = rings.pop(num)
                add_bond(start, prev, order if order is not None else o0)
            else:
                rings[num] = (prev, order)
            order = None
            continue
        if ch == "[":
            m = _BRACKET.match(s, i)
            if not m:
                raise SmilesError(f"Cannot read the bracket atom at "
                                  f"position {i + 1}.")
            sym = m.group(2)
            aromatic = sym.islower()
            element = _AROMATIC.get(sym, sym) if aromatic else sym
            h = m.group(4)
            hcount = (int(h[1:]) if h[1:] else 1) if h else 0
            charge = 0
            if m.group(5):
                sign = 1 if m.group(5)[0] == "+" else -1
                rest = m.group(5).lstrip("+-")
                charge = sign * (int(rest) if rest else len(m.group(5)))
            atom = dict(element=element, aromatic=aromatic, charge=charge,
                        h=hcount)
            i = m.end()
        else:
            two = s[i:i + 2]
            if two in ("Cl", "Br"):
                element, aromatic, i = two, False, i + 2
            elif two in ("se", "as"):
                element, aromatic, i = _AROMATIC[two], True, i + 2
            elif ch in _AROMATIC:
                element, aromatic, i = _AROMATIC[ch], True, i + 1
            elif ch in _ORGANIC:
                element, aromatic, i = ch, False, i + 1
            else:
                raise SmilesError(f"'{ch}' at position {i + 1} is not an "
                                  "atom SMILES knows (put other elements in "
                                  "brackets, e.g. [Na+]).")
            atom = dict(element=element, aromatic=aromatic, charge=0, h=None)
        if atom["element"] not in ELEMENTS:
            raise SmilesError(f"Unknown element '{atom['element']}'.")
        atoms.append(atom)
        if prev is not None:
            add_bond(prev, len(atoms) - 1, order)
        prev, order = len(atoms) - 1, None
    if stack:
        raise SmilesError("A '(' is never closed.")
    if rings:
        raise SmilesError(f"Ring bond {', '.join(rings)} is never closed.")
    return atoms, bonds


def add_hydrogens(atoms, bonds):
    """Implicit hydrogens of organic-subset atoms and the explicit ones
    of bracket atoms, as real atoms bonded to their owner."""
    atoms = [dict(a) for a in atoms]
    bonds = list(bonds)
    for idx in range(len(atoms)):
        a = atoms[idx]
        if a["h"] is None:
            arom = [o for x, y, o in bonds if idx in (x, y) and o == 1.5]
            other = [o for x, y, o in bonds if idx in (x, y) and o != 1.5]
            used = sum(other) + len(arom) + (1 if a["aromatic"] else 0)
            vals = VALENCES.get(a["element"], (0,))
            if a["aromatic"]:
                vals = vals[:1]
            fits = [v for v in vals if v >= used]
            count = int(round(fits[0] - used)) if fits else 0
        else:
            count = a["h"]
        for _k in range(max(count, 0)):
            atoms.append(dict(element="H", aromatic=False, charge=0, h=0))
            bonds.append((idx, len(atoms) - 1, 1.0))
    return atoms, bonds


# ------------------------------------------------------------ vectors
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _unit(v):
    n = math.sqrt(_dot(v, v))
    return (v[0] / n, v[1] / n, v[2] / n) if n > 1e-12 else (1.0, 0.0, 0.0)


def _perp(v, u):
    """The part of *v* at right angles to unit *u*."""
    return _sub(v, _mul(u, _dot(v, u)))


def _any_perp(u):
    helper = (0.0, 0.0, 1.0) if abs(u[2]) < 0.9 else (0.0, 1.0, 0.0)
    return _unit(_cross(helper, u))


# ------------------------------------------------------------ geometry
def bond_length(e1, e2, order) -> float:
    return ((ELEMENTS[e1][0] + ELEMENTS[e2][0])
            * _SHORTEN.get(order, 1.0))


_S3 = math.sqrt(3) / 2
#: slot directions per electron-domain count; lone pairs take the last
#: slots (so XeF4's two sit trans, SF4's one equatorial)
TEMPLATES = {
    1: [(1.0, 0.0, 0.0)],
    2: [(1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)],
    3: [(1.0, 0.0, 0.0), (-0.5, _S3, 0.0), (-0.5, -_S3, 0.0)],
    4: [(1.0, 0.0, 0.0), (-1 / 3, math.sqrt(8 / 9), 0.0),
        (-1 / 3, -math.sqrt(2 / 9), math.sqrt(2 / 3)),
        (-1 / 3, -math.sqrt(2 / 9), -math.sqrt(2 / 3))],
    5: [(0.0, 0.0, 1.0), (0.0, 0.0, -1.0), (1.0, 0.0, 0.0),
        (-0.5, _S3, 0.0), (-0.5, -_S3, 0.0)],
    6: [(1.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
        (0.0, -1.0, 0.0), (0.0, 0.0, 1.0), (0.0, 0.0, -1.0)],
}


def domains(atoms, bonds, idx) -> tuple:
    """(neighbours, lone pairs) of atom *idx*."""
    a = atoms[idx]
    mine = [o for x, y, o in bonds if idx in (x, y)]
    ve = VALENCE_ELECTRONS.get(a["element"])
    lone = 0
    if ve is not None:
        lone = max(0, int((ve - a["charge"] - sum(mine)) // 2))
    n = len(mine)
    lone = min(lone, 6 - n) if n <= 6 else 0
    return n, lone


def ideal_angle(neighbours: int, lone: int) -> float:
    """Bond angle by VSEPR: lone pairs squeeze it (water 104.5, ammonia
    107); 5 and 6 domains are read off the template instead."""
    count = neighbours + lone
    if count == 2:
        return 180.0
    if count == 3:
        return 120.0 - 2.0 * lone
    return 109.47 - 2.5 * lone


def find_rings(n, nbrs):
    """The smallest ring through each ring bond (cycle order), smallest
    first — both rings of naphthalene, not the ten-ring round them."""
    rings, seen = [], set()
    for a in range(n):
        if len(nbrs[a]) < 2:
            continue
        for b, _o in nbrs[a]:
            if b < a or len(nbrs[b]) < 2:
                continue
            prev, frontier, found = {a: None}, [a], False
            while frontier and not found:
                nxt = []
                for x in frontier:
                    for y, _o2 in nbrs[x]:
                        if {x, y} == {a, b} or y in prev:
                            continue
                        prev[y] = x
                        if y == b:
                            found = True
                            break
                        nxt.append(y)
                    if found:
                        break
                frontier = nxt
            if not found:
                continue
            path = [b]
            while path[-1] != a:
                path.append(prev[path[-1]])
            key = frozenset(path)
            if key not in seen and len(path) <= 12:
                seen.add(key)
                rings.append(path)
    rings.sort(key=len)
    return rings


def _centroid(points):
    k = len(points)
    return tuple(sum(p[c] for p in points) / k for c in range(3))


def embed(atoms, bonds):
    """3D positions (Å) for a parsed molecule with hydrogens."""
    n = len(atoms)
    nbrs = [[] for _ in range(n)]
    for x, y, o in bonds:
        nbrs[x].append((y, o))
        nbrs[y].append((x, o))
    for lst in nbrs:                      # heavy atoms take slots first
        lst.sort(key=lambda t: atoms[t[0]]["element"] == "H")
    dom = [domains(atoms, bonds, i) for i in range(n)]
    rings = find_rings(n, nbrs)
    ring_done = [False] * len(rings)
    pos = [None] * n
    parent = [None] * n
    order = {}

    def ring_length(ring):
        k = len(ring)
        total = 0.0
        for i in range(k):
            a, b = ring[i], ring[(i + 1) % k]
            total += bond_length(atoms[a]["element"], atoms[b]["element"],
                                 dict(nbrs[a]).get(b, 1.0))
        return total / k

    def puckered(ring):
        return all(dom[x][0] + dom[x][1] >= 4 for x in ring)

    def place_polygon(ring, start, radial, side, queue):
        """A whole ring through the placed atom *start*: *radial* points
        from it to the ring centre, *side* lies in the ring's plane."""
        k, L = len(ring), ring_length(ring)
        R = L / (2 * math.sin(math.pi / k))
        centre = _add(pos[start], _mul(radial, R))
        normal = _cross(radial, side)
        i0 = ring.index(start)
        cyc = ring[i0:] + ring[:i0]
        pucker = 0.25 if puckered(ring) else 0.0
        for m, x in enumerate(cyc):
            if pos[x] is not None:
                continue
            t = 2 * math.pi * m / k
            p = _add(centre, _add(_mul(radial, -R * math.cos(t)),
                                  _mul(side, R * math.sin(t))))
            pos[x] = _add(p, _mul(normal, pucker * (-1) ** m))
            parent[x] = cyc[m - 1]
            queue.append(x)

    def place_fused(ring, i, queue):
        """A ring sharing the placed edge ring[i]-ring[i+1]: built on the
        far side of the ring already there."""
        k, L = len(ring), ring_length(ring)
        A, B = ring[i], ring[(i + 1) % k]
        host = next((r for j, r in enumerate(rings) if ring_done[j]
                     and A in r and B in r), None)
        if host is None:
            return False
        hc = _centroid([pos[x] for x in host])
        normal = _unit(_cross(_sub(pos[host[0]], hc),
                              _sub(pos[host[1]], hc)))
        mid = _mul(_add(pos[A], pos[B]), 0.5)
        e = _unit(_sub(pos[B], pos[A]))
        out = _unit(_cross(normal, e))
        if _dot(out, _sub(hc, mid)) > 0:
            out = _mul(out, -1.0)
        R = L / (2 * math.sin(math.pi / k))
        apothem = L / (2 * math.tan(math.pi / k))
        centre = _add(mid, _mul(out, apothem))
        u1 = _unit(_sub(pos[A], centre))
        u2 = _unit(_cross(normal, u1))
        vb = _sub(pos[B], centre)
        delta = math.atan2(_dot(vb, u2), _dot(vb, u1))
        for j in range(2, k):
            x = ring[(i + j) % k]
            if pos[x] is None:
                t = j * delta
                pos[x] = _add(centre, _add(_mul(u1, R * math.cos(t)),
                                           _mul(u2, R * math.sin(t))))
                parent[x] = ring[(i + j - 1) % k]
                queue.append(x)
        return True

    def reach_rings(atom, came_from, queue):
        """Place any ring *atom* belongs to, and then the rings fused to
        those, until nothing more can be placed."""
        changed = True
        while changed:
            changed = False
            for ri, ring in enumerate(rings):
                if ring_done[ri]:
                    continue
                placed = [x for x in ring if pos[x] is not None]
                if not placed:
                    continue
                k = len(ring)
                if len(placed) == 1 and placed[0] == atom:
                    if came_from is None:
                        radial, side = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)
                    else:
                        radial = _unit(_sub(pos[atom], pos[came_from]))
                        grand = [pos[g] for g, _o in nbrs[came_from]
                                 if g != atom and pos[g] is not None]
                        side = (_perp(_sub(grand[0], pos[came_from]), radial)
                                if grand else (0.0, 0.0, 0.0))
                        side = (_unit(side) if _dot(side, side) > 1e-9
                                else _any_perp(radial))
                    place_polygon(ring, atom, radial, side, queue)
                    ring_done[ri] = changed = True
                    continue
                for i in range(k):
                    if pos[ring[i]] is not None and \
                            pos[ring[(i + 1) % k]] is not None:
                        if place_fused(ring, i, queue):
                            ring_done[ri] = changed = True
                        break
                else:
                    continue
            if changed:
                continue

    offset = 0.0
    for root in range(n):
        if pos[root] is not None:
            continue
        component_start = len(order)
        pos[root] = (offset, 0.0, 0.0)
        queue = [root]
        reach_rings(root, None, queue)
        while queue:
            a = queue.pop(0)
            order[a] = len(order)
            count = min(max(dom[a][0] + dom[a][1], 1), 6)
            template = TEMPLATES[count]
            placed = [b for b, _o in nbrs[a] if pos[b] is not None]
            if parent[a] in placed:
                placed.remove(parent[a])
                placed.insert(0, parent[a])
            if not placed:
                frame_t = frame_w = ((1.0, 0, 0), (0, 1.0, 0), (0, 0, 1.0))
            else:
                u = _unit(_sub(pos[placed[0]], pos[a]))
                if len(placed) > 1:
                    target1 = _perp(_sub(pos[placed[1]], pos[a]), u)
                else:
                    grand = [pos[g] for g, _o in nbrs[placed[0]]
                             if g != a and pos[g] is not None]
                    target1 = (_mul(_perp(_sub(grand[0], pos[placed[0]]), u),
                                    -1.0) if grand else (0.0, 0.0, 0.0))
                if _dot(target1, target1) < 1e-12:
                    target1 = _any_perp(u)
                t0 = _unit(template[0])
                # the first slot NOT along the first: in the linear and
                # octahedral templates slot 1 is opposite slot 0, and a
                # frame built on it collapses (CO2 came out bent, SF6's
                # fluorines on top of each other)
                t1 = next((_unit(_perp(t, t0)) for t in template[1:]
                           if _dot(_perp(t, t0), _perp(t, t0)) > 1e-6),
                          _any_perp(t0))
                frame_t = (t0, t1, _cross(t0, t1))
                w1 = _unit(target1)
                frame_w = (u, w1, _cross(u, w1))
            slots = []
            for t in template:
                c = [_dot(t, e) for e in frame_t]
                slots.append(tuple(sum(c[k] * frame_w[k][j]
                                       for k in range(3)) for j in range(3)))
            free = slots[len(placed):]
            if dom[a][1]:
                free = free[:max(len(free) - dom[a][1], 0)] or free
            for b, o in nbrs[a]:
                if pos[b] is not None:
                    continue
                d = free.pop(0) if free else _any_perp(slots[0])
                L = bond_length(atoms[a]["element"], atoms[b]["element"], o)
                pos[b] = _add(pos[a], _mul(d, L))
                parent[b] = a
                queue.append(b)
                reach_rings(b, a, queue)
        members = [x for x, k in order.items() if k >= component_start]
        offset = max(pos[x][0] for x in members) + 4.0
    return _relax(atoms, bonds, nbrs, dom, pos, rings)


def _relax(atoms, bonds, nbrs, dom, pos, rings, iters=800):
    """Settle bond lengths, angles (as 1-3 distances) and clashes by
    gradient steps from the placed start."""
    n = len(atoms)
    pos = [list(p) for p in pos]
    for k, p in enumerate(pos):                  # break exact overlaps
        p[0] += 1e-4 * math.sin(k * 1.7)
        p[1] += 1e-4 * math.cos(k * 2.3)
        p[2] += 1e-4 * math.sin(k * 0.9)
    in_small_ring = {x for r in rings if len(r) <= 5 for x in r}
    terms = []                                   # (i, j, target, weight, floor)
    for x, y, o in bonds:
        terms.append((x, y, bond_length(atoms[x]["element"],
                                         atoms[y]["element"], o), 1.0, False))
    pair13 = set()
    for a in range(n):
        count = dom[a][0] + dom[a][1]
        nb = [b for b, _o in nbrs[a]]
        orders = dict(nbrs[a])
        for ii in range(len(nb)):
            for jj in range(ii + 1, len(nb)):
                b, c = nb[ii], nb[jj]
                if count >= 5:                   # read off the template
                    va, vb = _sub(pos[b], pos[a]), _sub(pos[c], pos[a])
                    cosv = _dot(va, vb) / math.sqrt(_dot(va, va)
                                                    * _dot(vb, vb))
                    theta = math.degrees(math.acos(max(-1.0, min(1.0, cosv))))
                else:
                    theta = ideal_angle(*dom[a])
                la = bond_length(atoms[a]["element"], atoms[b]["element"],
                                 orders[b])
                lc = bond_length(atoms[a]["element"], atoms[c]["element"],
                                 orders[c])
                t = math.sqrt(la * la + lc * lc - 2 * la * lc
                              * math.cos(math.radians(theta)))
                weight = 0.3 if a in in_small_ring else 0.6
                terms.append((b, c, t, weight, False))
                pair13.add((min(b, c), max(b, c)))
    bonded = {(min(x, y), max(x, y)) for x, y, _o in bonds}
    for i in range(n):
        for j in range(i + 1, n):
            if (i, j) in bonded or (i, j) in pair13:
                continue
            floor = 0.72 * (vdw(atoms[i]["element"])
                            + vdw(atoms[j]["element"]))
            terms.append((i, j, floor, 0.3, True))
    step = 0.12
    for _it in range(iters):
        grad = [[0.0, 0.0, 0.0] for _ in range(n)]
        worst = 0.0
        for i, j, t, w, is_floor in terms:
            pi, pj = pos[i], pos[j]
            dx, dy, dz = pi[0] - pj[0], pi[1] - pj[1], pi[2] - pj[2]
            d = math.sqrt(dx * dx + dy * dy + dz * dz) or 1e-9
            if is_floor and d >= t:
                continue
            err = d - t
            worst = max(worst, abs(err))
            f = w * err / d
            gi, gj = grad[i], grad[j]
            gi[0] += f * dx
            gi[1] += f * dy
            gi[2] += f * dz
            gj[0] -= f * dx
            gj[1] -= f * dy
            gj[2] -= f * dz
        if worst < 2e-4:
            break
        for p, g in zip(pos, grad):
            gl = math.sqrt(g[0] * g[0] + g[1] * g[1] + g[2] * g[2])
            s = step if gl * step <= 0.15 else 0.15 / gl
            p[0] -= s * g[0]
            p[1] -= s * g[1]
            p[2] -= s * g[2]
    cx = [sum(p[c] for p in pos) / n for c in range(3)]
    return [(p[0] - cx[0], p[1] - cx[1], p[2] - cx[2]) for p in pos]


@lru_cache(maxsize=512)
def _built(smiles: str):
    atoms, bonds = parse_smiles(smiles)
    atoms, bonds = add_hydrogens(atoms, bonds)
    if len(atoms) > MAX_ATOMS:
        raise SmilesError(f"{len(atoms)} atoms: the builder takes up to "
                          f"{MAX_ATOMS}.")
    coords = embed(atoms, bonds)
    return (tuple((a["element"], *xyz) for a, xyz in zip(atoms, coords)),
            tuple(bonds), tuple(a["charge"] for a in atoms))


def from_smiles(smiles: str, name: str = "", key: str = "",
                category: str = "") -> Molecule:
    """A 3D molecule from SMILES (cached); SmilesError on bad input."""
    atoms, bonds, charges = _built(smiles.strip())
    return Molecule(name=name or smiles, smiles=smiles.strip(),
                    atoms=[list(a) for a in atoms], bonds=list(bonds),
                    charges=list(charges), key=key, category=category)


def formula_counts(text: str) -> dict:
    """{element: count} of a plain formula ("C6H12O6", "Ca(OH)2",
    "CuSO4·5H2O"); a trailing charge or phase is ignored. ValueError on
    nonsense."""
    body = re.sub(r"\((aq|s|l|g)\)$", "", text.strip())
    body = re.sub(r"\s*\^?\d*[+-]$", "", body)
    total = {}
    for part in re.split(r"[·*.]", body):
        m = re.match(r"^(\d*)(.*)$", part)
        mult = int(m.group(1)) if m.group(1) else 1
        for el, k in _parse_group(m.group(2)).items():
            total[el] = total.get(el, 0) + k * mult
    if not total:
        raise ValueError(f"'{text}' is not a formula.")
    return total


def _parse_group(text):
    stack, i = [{}], 0
    while i < len(text):
        ch = text[i]
        if ch in "([":
            stack.append({})
            i += 1
        elif ch in ")]":
            if len(stack) == 1:
                raise ValueError(f"Unbalanced brackets in '{text}'.")
            group = stack.pop()
            m = re.match(r"\d+", text[i + 1:])
            k = int(m.group()) if m else 1
            i += 1 + (len(m.group()) if m else 0)
            for el, c in group.items():
                stack[-1][el] = stack[-1].get(el, 0) + c * k
        else:
            m = re.match(r"([A-Z][a-z]?)(\d*)", text[i:])
            if not m or m.group(1) not in ELEMENTS:
                raise ValueError(f"Cannot read '{text[i:]}' as a formula.")
            c = int(m.group(2)) if m.group(2) else 1
            stack[-1][m.group(1)] = stack[-1].get(m.group(1), 0) + c
            i += len(m.group())
    if len(stack) != 1:
        raise ValueError(f"Unbalanced brackets in '{text}'.")
    return stack[0]
