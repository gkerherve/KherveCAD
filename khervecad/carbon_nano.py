"""Carbon nanostructures (Qt-free): graphene, graphite, nanotubes and
fullerenes as atoms and bonds — `molecule.Molecule`s, so the Compound
Builder's own writer (`molecule_build.molecule_program`) draws them.

None of them comes from SMILES: they are LATTICES, placed exactly.

- **Graphene** — the honeycomb of C–C 1.42 Å (a = 2.46 Å), zigzag
  edges along x, armchair along y, cut to a rectangle; atoms left with
  one neighbour are pruned so every edge is clean. Stacks of layers
  3.35 Å apart, Bernal AB (graphite's), ABA, rhombohedral ABC, AA, or a
  second layer TWISTED about the flake's centre (the moiré of twisted
  bilayer graphene); nanoribbons with armchair or zigzag edges capped
  by hydrogen; a round quantum dot; a vacancy; graphitic nitrogen
  doping; the graphite (0001) surface, with or without a step.
- **Nanotubes (n, m)** — graphene rolled along the chiral vector
  C = n a1 + m a2: every lattice site of the strip 0 <= u < |C|,
  0 <= v < L goes onto the cylinder of circumference |C| (so the
  seam closes exactly), armchair (n, n), zigzag (n, 0) or chiral;
  multi-walled tubes nest armchair (or zigzag) walls ~3.4 Å apart.
- **Fullerenes** — C60 from the truncated icosahedron (even
  permutations of (0, ±1, ±3φ), (±1, ±(2+φ), ±2φ), (±φ, ±2, ±φ³)),
  its 6-6 bonds double; C20 the dodecahedron; C70 and longer capped
  (5, 5) tubes are C60 cut across a five-fold axis with 10-atom
  armchair belts let in (C60 along that axis IS a (5, 5) tube's
  ring pattern), then settled by `relax` (bonds and ring angles).

Everything in Å here; molecule_build writes nanometres.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
from functools import lru_cache

from .molecule import Molecule, find_rings

CC = 1.42                    # graphene C-C, Å
A = CC * math.sqrt(3)        # lattice constant 2.46 Å
CH = 1.09                    # C-H, Å
INTERLAYER = 3.35            # graphite layer spacing, Å
WALL_GAP = 3.4               # between the walls of a nanotube
BOND_CUT = 1.62              # C-C closer than this is a bond
PHI = (1 + 5 ** 0.5) / 2
STACKINGS = ("AB", "ABA", "ABC", "AA")


class CarbonError(ValueError):
    """A structure that cannot be built; says what to change."""


# ------------------------------------------------------------- helpers
def _bonds(points, cut=BOND_CUT):
    """(i, j) of every pair closer than *cut* (a grid, not n²)."""
    grid = {}
    for k, p in enumerate(points):
        grid.setdefault(tuple(int(math.floor(c / cut)) for c in p),
                        []).append(k)
    out = []
    for (gx, gy, gz), members in grid.items():
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for j in grid.get((gx + dx, gy + dy, gz + dz), ()):
                        for i in members:
                            if i < j and math.dist(points[i],
                                                   points[j]) < cut:
                                out.append((i, j))
    return out


def _prune(points, min_neighbours=2):
    """Drop atoms with fewer than *min_neighbours* bonds, repeatedly
    (a cut edge leaves dangling atoms)."""
    while True:
        deg = [0] * len(points)
        for i, j in _bonds(points):
            deg[i] += 1
            deg[j] += 1
        keep = [p for p, d in zip(points, deg) if d >= min_neighbours]
        if len(keep) == len(points):
            return keep
        points = keep


def _molecule(name, key, carbon, category, hydrogen=False, orders=None,
              elements=None, centre_axes=(0, 1, 2)):
    """A Molecule of *carbon* points (Å), centred on *centre_axes* (a
    tube only along z: its uneven ends would pull the axis off z),
    bonds by distance; *hydrogen* caps every carbon with two neighbours
    in its plane."""
    pts = [tuple(p) for p in carbon]
    if not pts:
        raise CarbonError("Nothing left: make it bigger.")
    pairs = _bonds(pts)
    nbrs = [[] for _ in pts]
    for i, j in pairs:
        nbrs[i].append(j)
        nbrs[j].append(i)
    els = list(elements) if elements else ["C"] * len(pts)
    atoms = [[el, *p] for el, p in zip(els, pts)]
    bonds = [(i, j, (orders or {}).get((i, j), 1.0)) for i, j in pairs]
    if hydrogen:
        for i, p in enumerate(pts):
            if len(nbrs[i]) != 2:
                continue
            d = [0.0, 0.0, 0.0]
            for j in nbrs[i]:
                v = [p[c] - pts[j][c] for c in range(3)]
                n = math.sqrt(sum(x * x for x in v))
                d = [d[c] + v[c] / n for c in range(3)]
            n = math.sqrt(sum(x * x for x in d)) or 1.0
            atoms.append(["H"] + [p[c] + CH * d[c] / n for c in range(3)])
            bonds.append((i, len(atoms) - 1, 1.0))
    centre = [sum(a[1 + c] for a in atoms) / len(atoms) for c in range(3)]
    for a in atoms:
        for c in centre_axes:
            a[1 + c] -= centre[c]
    return Molecule(name=name, smiles="", atoms=atoms, bonds=bonds,
                    charges=[0] * len(atoms), key=key, category=category)


# ------------------------------------------------------------- graphene
def _honeycomb(x0, x1, y0, y1, z=0.0, shift=(0.0, 0.0)):
    """Graphene sites in [x0, x1) x [y0, y1): the rectangular 4-atom
    cell A x 3CC (zigzag rows along x)."""
    out = []
    basis = ((0.0, 0.0), (0.0, CC), (A / 2, 1.5 * CC), (A / 2, 2.5 * CC))
    i0, i1 = int(math.floor((x0 - shift[0]) / A)) - 1, \
        int(math.ceil((x1 - shift[0]) / A)) + 1
    j0, j1 = int(math.floor((y0 - shift[1]) / (3 * CC))) - 1, \
        int(math.ceil((y1 - shift[1]) / (3 * CC))) + 1
    for i in range(i0, i1):
        for j in range(j0, j1):
            for bx, by in basis:
                x = i * A + bx + shift[0]
                y = j * 3 * CC + by + shift[1]
                if x0 <= x < x1 and y0 <= y < y1:
                    out.append((x, y, z))
    return out


def _rotated(points, degrees):
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return [(c * x - s * y, s * x + c * y, z) for x, y, z in points]


#: in-plane shift of each stacking letter (one bond along y: Bernal)
_LETTER = {"A": (0.0, 0.0), "B": (0.0, CC), "C": (0.0, 2 * CC)}
_PATTERN = {"AB": "AB", "ABA": "AB", "ABC": "ABC", "AA": "A"}


def graphene(width=3.0, depth=3.0, layers=1, stacking="AB", twist=0.0,
             hydrogen=False, name="", key="graphene"):
    """A rectangular flake *width* x *depth* nm, *layers* stacked
    INTERLAYER apart by *stacking* (AB / ABA repeat A B A B, ABC is
    rhombohedral, AA eclipsed), or the second layer turned *twist*
    degrees about the centre."""
    if stacking not in STACKINGS:
        raise CarbonError(f"stacking is one of {', '.join(STACKINGS)}.")
    layers = int(layers)
    if not 1 <= layers <= 12:
        raise CarbonError("From 1 to 12 layers.")
    w, d = width * 10, depth * 10
    if w < 2 * A or d < 3 * CC:
        raise CarbonError("At least 0.5 nm each way.")
    pts = []
    for k in range(layers):
        z = k * INTERLAYER
        if twist and k % 2 == 1:
            r = math.hypot(w, d)
            big = [(x - w / 2, y - d / 2, z) for x, y, z in
                   _honeycomb(-r / 2 + w / 2, r / 2 + w / 2,
                              -r / 2 + d / 2, r / 2 + d / 2, z)]
            layer = [(x + w / 2, y + d / 2, zz) for x, y, zz in
                     _rotated(big, twist)
                     if -w / 2 <= x < w / 2 and -d / 2 <= y < d / 2]
        else:
            pattern = _PATTERN[stacking]
            layer = _honeycomb(0, w, 0, d, z,
                               _LETTER[pattern[k % len(pattern)]])
        pts += _prune(layer)
    title = name or _graphene_name(layers, stacking, twist)
    return _molecule(title, key, pts, "Graphene", hydrogen=hydrogen)


def _graphene_name(layers, stacking, twist):
    if layers == 1:
        return "Graphene"
    if twist:
        return f"Twisted bilayer graphene ({twist:g}°)"
    words = {2: "Bilayer", 3: "Trilayer"}.get(layers, f"{layers}-layer")
    return f"{words} graphene ({stacking})"


def nanoribbon(edge="armchair", width=1.0, length=4.0):
    """A hydrogen-terminated graphene nanoribbon *width* x *length* nm
    with armchair or zigzag edges along its length (x)."""
    w, L = width * 10, length * 10
    if edge == "zigzag":           # zigzag rows run along x already
        pts = _prune(_honeycomb(0, L, 0, w))
    elif edge == "armchair":       # the same sheet turned a quarter
        pts = _prune(_rotated(_honeycomb(0, w, 0, L), 90))
    else:
        raise CarbonError("edge is armchair or zigzag.")
    return _molecule(f"{edge.capitalize()} graphene nanoribbon",
                     f"{edge}_nanoribbon", pts, "Graphene", hydrogen=True)


def quantum_dot(diameter=2.0):
    """A round graphene flake (a graphene quantum dot), H-capped."""
    r = diameter * 5
    pts = [p for p in _honeycomb(-r, r, -r, r) if math.hypot(p[0], p[1]) < r]
    return _molecule("Graphene quantum dot", "graphene_quantum_dot",
                     _prune(pts), "Graphene", hydrogen=True)


def defect_sheet(kind="vacancy", width=3.0, depth=3.0, nitrogen=0.04,
                 seed=7):
    """Graphene with a single vacancy at the centre, or graphitic
    nitrogen doping (a *nitrogen* fraction of the carbons, seeded)."""
    sheet = graphene(width, depth)
    pts = [tuple(a[1:]) for a in sheet.atoms]
    if kind == "vacancy":
        centre = min(range(len(pts)), key=lambda k: math.hypot(*pts[k][:2]))
        pts.pop(centre)
        return _molecule("Graphene with a vacancy", "graphene_vacancy",
                         pts, "Graphene")
    if kind == "nitrogen":
        import random
        rng = random.Random(seed)
        n = max(1, round(nitrogen * len(pts)))
        chosen = set(rng.sample(range(len(pts)), n))
        els = ["N" if k in chosen else "C" for k in range(len(pts))]
        return _molecule("Nitrogen-doped graphene", "graphene_n_doped",
                         pts, "Graphene", elements=els)
    raise CarbonError("kind is vacancy or nitrogen.")


def graphite_surface(width=3.0, depth=3.0, layers=4, step=False):
    """The graphite (0001) surface: *layers* Bernal (AB) sheets, the top
    one at z = 0; *step* keeps only half of the top sheet (a monatomic
    step, as on cleaved HOPG)."""
    w, d = width * 10, depth * 10
    pts = []
    for k in range(int(layers)):
        z = -k * INTERLAYER
        layer = _honeycomb(0, w / 2 if (step and k == 0) else w, 0, d, z,
                           _LETTER["AB"[k % 2]])
        pts += _prune(layer)
    m = _molecule("Graphite (0001) surface with a step" if step else
                  "Graphite (0001) surface", "graphite_surface", pts,
                  "Graphene")
    top = max(a[3] for a in m.atoms)
    for a in m.atoms:
        a[3] -= top
    return m


# ------------------------------------------------------------ nanotubes
def tube_points(n, m, length):
    """Atoms (Å) of an open (n, m) tube *length* Å long along z."""
    a1 = (A, 0.0)
    a2 = (A / 2, A * math.sqrt(3) / 2)
    ch = (n * a1[0] + m * a2[0], n * a1[1] + m * a2[1])
    C = math.hypot(*ch)
    dR = math.gcd(2 * m + n, 2 * n + m)
    t1, t2 = (2 * m + n) // dR, -(2 * n + m) // dR
    T = (t1 * a1[0] + t2 * a2[0], t1 * a1[1] + t2 * a2[1])
    Tl = math.hypot(*T)
    cu = (ch[0] / C, ch[1] / C)
    tu = (T[0] / Tl, T[1] / Tl)
    R = C / (2 * math.pi)
    # lattice coordinates of the strip's corners bound the search
    inv = 1 / (a1[0] * a2[1] - a1[1] * a2[0])
    corners = [(0, 0), ch, (tu[0] * length, tu[1] * length),
               (ch[0] + tu[0] * length, ch[1] + tu[1] * length)]
    ij = [((x * a2[1] - y * a2[0]) * inv, (y * a1[0] - x * a1[1]) * inv)
          for x, y in corners]
    i0, i1 = int(min(p[0] for p in ij)) - 2, int(max(p[0] for p in ij)) + 3
    j0, j1 = int(min(p[1] for p in ij)) - 2, int(max(p[1] for p in ij)) + 3
    b = ((a1[0] + a2[0]) / 3, (a1[1] + a2[1]) / 3)
    out = []
    eps = 1e-6
    for i in range(i0, i1):
        for j in range(j0, j1):
            for ox, oy in ((0.0, 0.0), b):
                x = i * a1[0] + j * a2[0] + ox
                y = i * a1[1] + j * a2[1] + oy
                u = x * cu[0] + y * cu[1]
                v = x * tu[0] + y * tu[1]
                if -eps <= u < C - eps and 0 <= v < length:
                    phi = 2 * math.pi * u / C
                    out.append((R * math.cos(phi), R * math.sin(phi), v))
    return out


def tube_kind(n, m) -> str:
    return "armchair" if n == m else "zigzag" if m == 0 else "chiral"


def nanotube(n=5, m=5, length=3.0, walls=1, hydrogen=False):
    """An open single- (or multi-) walled (n, m) nanotube *length* nm
    long, its axis along z. Extra walls keep the tube's kind: armchair
    (n+5k, n+5k), zigzag (n+9k, 0), a chiral tube's walls scaled."""
    n, m = int(n), int(m)
    if n < 1 or m < 0 or m > n:
        raise CarbonError("Chiral indices need n >= 1 and 0 <= m <= n.")
    if n + m < 4:
        raise CarbonError("Too thin to be a tube: n + m of 4 or more.")
    walls = int(walls)
    if not 1 <= walls <= 6:
        raise CarbonError("From 1 to 6 walls.")
    L = length * 10
    if L < 2 * A:
        raise CarbonError("At least 0.5 nm long.")
    pts, indices = [], []
    for k in range(walls):
        if k == 0:
            nk, mk = n, m
        elif n == m:
            nk = mk = n + 5 * k
        elif m == 0:
            nk, mk = n + 9 * k, 0
        else:                      # grow the diameter by ~WALL_GAP a wall
            d0 = A * math.sqrt(n * n + n * m + m * m) / math.pi
            f = (d0 + 2 * WALL_GAP * k) / d0
            nk, mk = round(n * f), round(m * f)
        indices.append((nk, mk))
        pts += _prune(tube_points(nk, mk, L))
    kind = tube_kind(n, m)
    if walls == 1:
        name = f"{kind.capitalize()} nanotube ({n}, {m})"
    else:
        name = ("Multi-walled nanotube " +
                " @ ".join(f"({a}, {b})" for a, b in indices))
    return _molecule(name, f"nanotube_{n}_{m}", pts, "Nanotubes",
                     hydrogen=hydrogen, centre_axes=(2,))


def diameter(n, m) -> float:
    """Nanometres."""
    return A * math.sqrt(n * n + n * m + m * m) / math.pi / 10


# ----------------------------------------------------------- fullerenes
def _even_permutations(base, signs=True):
    pts = set()
    for b in base:
        for sx in (1, -1):
            for sy in (1, -1):
                for sz in (1, -1):
                    v = (b[0] * sx, b[1] * sy, b[2] * sz)
                    for k in range(3):
                        pts.add(tuple(round(v[(i + k) % 3], 9)
                                      for i in range(3)))
    return sorted(pts)


def _five_fold_up(points):
    """Turn (0, 1, φ) — a pentagon's centre — onto +z."""
    ang = math.atan2(1, PHI)
    c, s = math.cos(ang), math.sin(ang)
    return [(x, c * y - s * z, s * y + c * z) for x, y, z in points]


def c60_points():
    """C60, a five-fold axis on z, bonds ~1.42 Å (edge 2 scaled)."""
    pts = _even_permutations([(0, 1, 3 * PHI), (1, 2 + PHI, 2 * PHI),
                              (PHI, 2, 2 * PHI + 1)])
    return [tuple(v * CC / 2 for v in p) for p in _five_fold_up(pts)]


def _pentagon_bonds(n, pairs):
    nbrs = [[] for _ in range(n)]
    for i, j in pairs:
        nbrs[i].append((j, 1.0))
        nbrs[j].append((i, 1.0))
    rings = find_rings(n, nbrs)
    return nbrs, rings, {frozenset((r[k], r[(k + 1) % 5]))
                         for r in rings if len(r) == 5 for k in range(5)}


def relax(points, iters=600):
    """Settle a closed cage: bonds 1.45 Å round a pentagon, 1.40
    elsewhere, angles 108° in a pentagon and 120° in a hexagon (as 1-3
    distances). Curvature comes from the pentagons by itself."""
    pts = [list(p) for p in points]
    n = len(pts)
    pairs = _bonds(points)
    nbrs, rings, pent = _pentagon_bonds(n, pairs)
    in_pent = {}
    for r in rings:
        if len(r) == 5:
            for k in range(5):
                in_pent[(r[k], frozenset((r[k - 1], r[(k + 1) % 5])))] = True
    terms = []
    for i, j in pairs:
        terms.append((i, j, 1.45 if frozenset((i, j)) in pent else 1.40,
                      1.0))
    for a in range(n):
        nb = [b for b, _o in nbrs[a]]
        for x in range(len(nb)):
            for y in range(x + 1, len(nb)):
                b, c = nb[x], nb[y]
                theta = 108.0 if in_pent.get((a, frozenset((b, c)))) \
                    else 120.0
                t = 2 * 1.42 * math.sin(math.radians(theta) / 2)
                terms.append((b, c, t, 0.5))
    step = 0.2
    for _ in range(iters):
        grad = [[0.0, 0.0, 0.0] for _ in range(n)]
        worst = 0.0
        for i, j, t, w in terms:
            pi, pj = pts[i], pts[j]
            dx, dy, dz = pi[0] - pj[0], pi[1] - pj[1], pi[2] - pj[2]
            d = math.sqrt(dx * dx + dy * dy + dz * dz) or 1e-9
            err = d - t
            worst = max(worst, abs(err))
            f = w * err / d
            grad[i][0] += f * dx
            grad[i][1] += f * dy
            grad[i][2] += f * dz
            grad[j][0] -= f * dx
            grad[j][1] -= f * dy
            grad[j][2] -= f * dz
        if worst < 1e-4:
            break
        for p, g in zip(pts, grad):
            p[0] -= step * g[0]
            p[1] -= step * g[1]
            p[2] -= step * g[2]
    return [tuple(p) for p in pts], pairs


def capped_points(belts: int):
    """C60 + 10 x *belts*: C60 cut across its five-fold axis and pulled
    apart by *belts* 10-atom armchair rings (C70 is one belt), the top
    half turned 36° for an odd count so the rings keep alternating."""
    base = c60_points()
    ring_z = sorted({round(p[2], 6) for p in base})
    step = ring_z[4] - ring_z[3]                 # the two equator rings
    lower = [p for p in base if p[2] < 0]
    upper = [p for p in base if p[2] > 0]
    eq_low = [p for p in lower if abs(p[2] - ring_z[3]) < 1e-3]
    eq_up = [p for p in upper if abs(p[2] - ring_z[4]) < 1e-3]
    out = list(lower)
    for k in range(1, belts + 1):
        src = eq_up if k % 2 else eq_low
        out += [(x, y, ring_z[3] + k * step) for x, y, _z in src]
    turn = 36.0 if belts % 2 else 0.0
    rise = belts * step
    out += [(x, y, z + rise) for x, y, z in _rotated(upper, turn)]
    return out


@lru_cache(maxsize=32)
def _fullerene(kind: str):
    if kind == "c60":
        pts = c60_points()
        pairs = _bonds(pts)
        _nbrs, _rings, pent = _pentagon_bonds(len(pts), pairs)
        orders = {p: (1.0 if frozenset(p) in pent else 2.0) for p in pairs}
        pts, _pairs = relax(pts)
        return pts, orders, "Buckminsterfullerene C60"
    if kind == "c20":
        pts = _even_permutations([(1, 1, 1), (0, 1 / PHI, PHI)])
        k = 1.44 / (2 / PHI)
        pts, _pairs = relax([tuple(v * k for v in p) for p in pts])
        return pts, None, "Fullerene C20 (dodecahedrane cage)"
    if kind.startswith("c") and kind[1:].isdigit():
        atoms = int(kind[1:])
        belts = (atoms - 60) // 10
        pts, _pairs = relax(capped_points(belts))
        return pts, None, (f"Fullerene C{atoms}" if belts == 1 else
                           f"Capped (5, 5) nanotube C{atoms}")
    raise CarbonError(f"No fullerene '{kind}'.")


FULLERENES = ("c20", "c60", "c70", "c80")


def fullerene(kind="c60"):
    kind = str(kind).lower()
    if kind not in FULLERENES and not (
            kind[1:].isdigit() and int(kind[1:]) >= 70
            and int(kind[1:]) % 10 == 0 and int(kind[1:]) <= 1000):
        raise CarbonError("A fullerene is C20, C60, or C60 + 10k (C70, "
                          "C80 ... a capped (5, 5) tube).")
    pts, orders, name = _fullerene(kind)
    return _molecule(name, kind, pts, "Fullerenes", orders=orders)


def capped_nanotube(length=3.0):
    """A (5, 5) nanotube closed by C60 halves, about *length* nm long
    overall."""
    belts = max(1, round((length * 10 - 7.1) / (A / 2)))
    return fullerene(f"c{60 + 10 * belts}")


# ------------------------------------------------------------- the list
#: key -> (name, category, builder) of the ready structures
STRUCTURES = {
    "c20": ("Fullerene C20", "Fullerenes", lambda: fullerene("c20")),
    "c60": ("Buckminsterfullerene C60 (buckyball)", "Fullerenes",
            lambda: fullerene("c60")),
    "c70": ("Fullerene C70", "Fullerenes", lambda: fullerene("c70")),
    "c80": ("Fullerene C80 (D5d)", "Fullerenes", lambda: fullerene("c80")),
}


def get(key: str) -> Molecule:
    """A ready structure by key or name; KeyError when unknown."""
    k = str(key).strip().lower().replace(" ", "_")
    by_name = {v[0].lower(): kk for kk, v in STRUCTURES.items()}
    k = by_name.get(str(key).strip().lower(), k)
    if k not in STRUCTURES:
        raise KeyError(key)
    return STRUCTURES[k][2]()
