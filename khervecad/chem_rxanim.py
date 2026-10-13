"""Reaction animation (Qt-free): reactant atoms travel to product atoms.

A balanced equation says *what* is conserved, not *which* atom ends up
where. `map_atoms` chooses a bijection between the reactant and product
atoms of the same element that keeps as many bonds as possible (a C–H
that survives, an O=O that stays together), then prefers atoms that keep
company (neighbours landing in the same product molecule) and, last,
atoms that have to travel the least.

`Animation` turns that mapping into a film with four keyframes per atom:

* **A** — the reactant molecules spread out on the left,
* **B** — the same molecules packed into a "collision" cluster,
* **C** — the product molecules packed in the same place, each atom at its
  mapped product position,
* **D** — the product molecules spread out on the right.

Progress 0..1 runs A → B (approach), B → C (the reactant bonds break, the
atoms swing to their product places, the new bonds form), C → D (separate). The
atoms and bond list are the reactant scene's own, so a viewer only has to
call `Animation.apply(mol, p)` and redraw. Ported from KherveMol's
rxanim.py for the Chemistry Builder (and `chem_reaction`).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

#: cost, per ångström, of an atom travelling (the last tie-break)
TRAVEL = 0.01
#: reward for neighbours that end up in the same product molecule
COMPANY = 0.3
#: where the phases end (approach, transformation, separation)
PHASES = (0.25, 0.75)
#: bonds that only exist in the reactants vanish before this progress and
#: bonds that only exist in the products appear after the second, so the
#: film has a beat with neither — the atoms are between molecules
BREAK, FORM = 0.42, 0.58
#: how far (Å) atoms bound for different product molecules swing apart in
#: height while they travel, so their paths do not all cross in one line
ARC = 1.3
#: seconds a full run takes at speed 1
DURATION = 7.0


class Side:
    """One side of a reaction as flat lists: every drawn atom (all copies
    of all species) with its element, bonds, molecule number and the
    positions it has when spread out (`spread`) and when packed (`packed`)."""

    def __init__(self, elements, bonds, mols, spread, packed):
        self.elements = list(elements)
        self.bonds = [(int(i), int(j), int(o)) for i, j, o in bonds]
        self.mols = list(mols)
        self.spread = [tuple(p) for p in spread]
        self.packed = [tuple(p) for p in packed]

    def neighbours(self):
        nbr = [[] for _ in self.elements]
        for i, j, o in self.bonds:
            nbr[i].append((j, o))
            nbr[j].append((i, o))
        return nbr


def map_atoms(reac, prod, passes=6):
    """A list ``pi`` with ``pi[i]`` the product atom that reactant atom
    *i* becomes. Raises ValueError when the two sides do not hold the same
    atoms."""
    if sorted(reac.elements) != sorted(prod.elements):
        raise ValueError("The two sides hold different atoms.")
    n = len(reac.elements)
    nbr_r, nbr_p = reac.neighbours(), prod.neighbours()
    pbond = {}
    for i, j, o in prod.bonds:
        pbond[(i, j)] = pbond[(j, i)] = o

    def sig(el, nbr, i):
        return (len(nbr[i]), tuple(sorted(el[j] for j, _o in nbr[i])))

    def dist(a, pa):
        return math.dist(reac.packed[a], prod.packed[pa])

    # seed: same element, same neighbourhood signature, nearest first
    pi = [-1] * n
    free = {}
    for k, el in enumerate(prod.elements):
        free.setdefault(el, []).append(k)
    order = sorted(range(n), key=lambda a: (-len(nbr_r[a]), a))
    for a in order:
        pool = free[reac.elements[a]]
        want = sig(reac.elements, nbr_r, a)
        best = min(pool, key=lambda k: (sig(prod.elements, nbr_p, k) != want,
                                        dist(a, k), k))
        pi[a] = best
        pool.remove(best)

    def contrib(a):
        pa = pi[a]
        s = -TRAVEL * dist(a, pa)
        for b, o in nbr_r[a]:
            pb = pi[b]
            po = pbond.get((pa, pb))
            if po is not None:
                s += 1.0 + (0.25 if po == o else 0.0)
            elif prod.mols[pa] == prod.mols[pb]:
                s += COMPANY
        return s

    groups = {}
    for a in range(n):
        groups.setdefault(reac.elements[a], []).append(a)
    if n > 150:
        passes = min(passes, 2)
    for _ in range(passes):
        improved = False
        for atoms in groups.values():
            for x in range(len(atoms)):
                for y in range(x + 1, len(atoms)):
                    a, b = atoms[x], atoms[y]
                    before = contrib(a) + contrib(b)
                    pi[a], pi[b] = pi[b], pi[a]
                    if contrib(a) + contrib(b) > before + 1e-9:
                        improved = True
                    else:
                        pi[a], pi[b] = pi[b], pi[a]
        if not improved:
            break
    return pi


def _smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _mix(p, q, s):
    return (p[0] + (q[0] - p[0]) * s, p[1] + (q[1] - p[1]) * s,
            p[2] + (q[2] - p[2]) * s)


class Animation:
    """The film of one reaction. Build with `build`; drive with `apply`."""

    def __init__(self, reac, prod, pi, title):
        self.reac, self.prod, self.pi = reac, prod, pi
        self.title = title
        inv = {p: a for a, p in enumerate(pi)}
        self.rbonds = [[i, j, o] for i, j, o in reac.bonds]
        self.pbonds = [[inv[i], inv[j], o] for i, j, o in prod.bonds]
        zs = [p[2] for p in reac.spread + prod.spread]
        xs = [p[0] for p in reac.spread + prod.spread]
        self.top = max(zs) + 2.6 if zs else 3.0
        self.bottom = min(zs) - 1.5 if zs else -3.0
        self.left = min(xs) - 1.5 if xs else -5.0
        self.right = max(xs) + 1.5 if xs else 5.0
        self._static = None

    # ------------------------------------------------------ the film
    def stage(self, p):
        if p < PHASES[0]:
            return "Reactants approach"
        if p < BREAK:
            return "Bonds break"
        if p < FORM:
            return "Atoms rearrange"
        if p < PHASES[1]:
            return "New bonds form"
        return "Products separate"

    def position(self, i, p):
        """Where reactant atom *i* is at progress *p* (0..1)."""
        a, b = self.reac.spread[i], self.reac.packed[i]
        pj = self.pi[i]
        c, d = self.prod.packed[pj], self.prod.spread[pj]
        t1, t2 = PHASES
        if p <= t1:
            return _mix(a, b, _smooth(p / t1))
        if p <= t2:
            s = (p - t1) / (t2 - t1)
            x, y, z = _mix(b, c, _smooth(s))
            side = 1.0 if self.prod.mols[pj] % 2 else -1.0
            return (x, y, z + side * ARC * math.sin(math.pi * s))
        return _mix(c, d, _smooth((p - t2) / (1.0 - t2)))

    def bonds_at(self, p):
        """Bonds that survive stay; the reactants' others break before
        BREAK, the products' new ones form after FORM."""
        if p < BREAK:
            return [list(b) for b in self.rbonds]
        if p >= FORM:
            return [list(b) for b in self.pbonds]
        keep = {frozenset(b[:2]) for b in self.pbonds}
        return [list(b) for b in self.rbonds if frozenset(b[:2]) in keep]

    def notes_at(self, p):
        """The title, the stage caption and three empty anchors that keep
        the camera fit the same for the whole film."""
        mid = (self.left + self.right) / 2
        return [
            {"kind": "text", "text": self.title, "pos": (mid, 0.0, self.top),
             "size": 1.5, "color": "#22303c", "bold": True},
            {"kind": "text", "text": self.stage(p),
             "pos": (mid, 0.0, self.bottom), "size": 1.1,
             "color": "#159c74", "bold": True},
            {"kind": "text", "text": "", "pos": (self.left, 0.0, self.top)},
            {"kind": "text", "text": "", "pos": (self.right, 0.0, self.top)},
            {"kind": "text", "text": "",
             "pos": (mid, 0.0, self.bottom - 0.5)},
        ]

    # ------------------------------------------------- drive a Molecule
    def bind(self, mol):
        """Remember the static equation scene so `restore` can bring it
        back."""
        self._static = ([list(a) for a in mol.atoms],
                        [list(b) for b in mol.bonds],
                        [dict(n) for n in (mol.notes or ())])

    def apply(self, mol, p):
        """Set *mol*'s atoms, bonds and notes to the film at progress *p*."""
        if self._static is None:
            self.bind(mol)
        p = max(0.0, min(1.0, p))
        # the film moves the reactant atoms only: the static scene also
        # holds the products, which the film makes out of the same atoms
        mol.atoms = [[el, *self.position(i, p)]
                     for i, el in enumerate(self.reac.elements)]
        mol.bonds = self.bonds_at(p)
        mol.notes = self.notes_at(p)

    def restore(self, mol):
        """Back to the static equation (reactants → products with arrow)."""
        if self._static is None:
            return
        atoms, bonds, notes = self._static
        mol.atoms = [list(a) for a in atoms]
        mol.bonds = [list(b) for b in bonds]
        mol.notes = [dict(n) for n in notes]

    @property
    def bound(self):
        return self._static is not None


def build(reac, prod, title):
    """An `Animation`, or None when the two sides cannot be paired atom
    for atom (a fractional coefficient draws one copy, so the atoms of the
    two sides then differ)."""
    try:
        pi = map_atoms(reac, prod)
    except ValueError:
        return None
    return Animation(reac, prod, pi, title)
