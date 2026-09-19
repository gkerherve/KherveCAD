"""**Leaves** (Qt-free): one real leaf of a species, at true size in mm,
as closed polyhedra — the blade with its thickness, the raised midrib and
veins, the petiole. The detailed half of the tree work: `library_leaves`
makes every species a Library part, and a tree can instance the coarse
level (`detail="low"`) by the thousand.

A species is a recipe (`SPECIES`), not a mesh:

- **Strip blades** (oak, beech, birch, lime, cherry, willow, holly...):
  the blade is a grid over (s along the midrib, t across it). The half
  width is a base profile `s^a (1 - s)^b` (a < 1 a broad or heart-shaped
  base, b < 1 a blunt tip, b > 1 a drawn-out one) times the margin:
  rounded or pointed **lobes** (oak, chestnut-oak), **teeth** (serrate,
  and a second finer set for double-serrate birch and elm), **spines**
  (holly) and an **asymmetric** base (lime, elm).
- **Palmate blades** (maple, sycamore, plane, sweetgum, ginkgo): the
  grid is polar about the petiole, r(θ) = the lobes' pointed peaks over
  a web (`web`), teeth on top, a sinus where the petiole enters.
- **Compound leaves** (ash, rowan, walnut, horse chestnut): strip
  leaflets set along a rachis (pinnate) or round its tip (palmate).
- **Needles and fronds**: pine fascicles, spruce and fir shoots, cedar
  and larch spurs, yew sprays, cypress scale sprays, a palm frond.

The flat grid is then shaped in 3D — folded up along the midrib, arched
and drooping to the tip, the margin rolled and waved, a little twist —
and the bottom sheet is the top one moved down by the thickness, the
edges walled: one closed solid. Veins are tubes laid ON the shaped top
surface (`surface_z`), curving toward the tip like real secondary veins.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
import random

from .treegen import Mesh

#: grid resolution (stations along, across) and tube sides per detail
DETAIL = {"high": (90, 12, 8), "medium": (40, 6, 6), "low": (12, 2, 0)}

# ------------------------------------------------------------ recipes
# length L and width W are the leaf's usual size in mm; profile a, b;
# lobes (count per side, depth 0..1, pointed?); teeth (count per side,
# depth mm, second set); fold degrees, arch (droop at tip / L),
# wave (margin undulation mm, count), curl (margin roll mm), thick mm;
# veins per side and their angle to the midrib; petiole length.
_S = dict
SPECIES = {
    # --- simple blades
    "oak": _S(kind="strip", name="English oak", L=100, W=38, a=1.15,
              b=0.55, lobes=(4.5, 0.62, False), teeth=None, fold=8, arch=0.06,
              wave=(0.8, 6), curl=0.6, thick=0.35, veins=(6, 48),
              petiole=5, base_ears=0.25, colours=("#3d6b2a", "#8a5a2b",
                                                  "#7fae4a")),
    "beech": _S(kind="strip", name="Beech", L=85, W=28, a=0.8, b=0.9,
                lobes=None, teeth=(8, 0.4, None), fold=10, arch=0.05,
                wave=(1.0, 8), curl=0.3, thick=0.25, veins=(8, 42),
                petiole=8, colours=("#4a7f2e", "#b8652b", "#9ccf5a")),
    "birch": _S(kind="strip", name="Silver birch", L=55, W=22, a=0.45,
                b=1.35, lobes=None, teeth=(11, 1.4, 2), fold=6,
                arch=0.05, wave=(0.3, 5), curl=0.2, thick=0.22,
                veins=(7, 45), petiole=20, colours=("#5a8a2f", "#e0b52a",
                                                    "#a6d65e")),
    "lime": _S(kind="strip", name="Lime (linden)", L=85, W=40, a=0.35,
               b=1.25, lobes=None, teeth=(16, 1.0, None), fold=5,
               arch=0.05, wave=(0.4, 4), curl=0.3, thick=0.25,
               veins=(6, 50), petiole=35, asym=0.18, base_back=0.12,
               colours=("#4f8a30", "#d8b43a", "#a0d060")),
    "cherry": _S(kind="strip", name="Wild cherry", L=110, W=28, a=0.8,
                 b=1.4, lobes=None, teeth=(26, 1.1, None), fold=12,
                 arch=0.08, wave=(0.6, 5), curl=0.3, thick=0.28,
                 veins=(10, 55), petiole=30, colours=("#3f7a2c", "#c4452a",
                                                      "#8cc458")),
    "apple": _S(kind="strip", name="Apple", L=75, W=28, a=0.65, b=0.95,
                lobes=None, teeth=(18, 0.7, None), fold=10, arch=0.06,
                wave=(0.5, 4), curl=0.4, thick=0.3, veins=(7, 50),
                petiole=25, colours=("#447a2c", "#c9a13a", "#8cc458")),
    "willow": _S(kind="strip", name="White willow", L=110, W=9, a=0.9,
                 b=1.5, lobes=None, teeth=(40, 0.3, None), fold=6,
                 arch=0.18, wave=(0.2, 3), curl=0.2, thick=0.2,
                 veins=(14, 60), petiole=6, colours=("#7a9a5a", "#d8c24a",
                                                     "#a8c878")),
    "poplar": _S(kind="strip", name="Black poplar", L=80, W=38, a=0.25,
                 b=1.3, lobes=None, teeth=(14, 0.8, None), fold=4,
                 arch=0.04, wave=(0.5, 4), curl=0.2, thick=0.25,
                 veins=(5, 55), petiole=45, colours=("#4c7f34", "#e3c23a",
                                                     "#9bd05a")),
    "chestnut": _S(kind="strip", name="Sweet chestnut", L=180, W=30,
                   a=0.8, b=1.1, lobes=None, teeth=(18, 3.5, None),
                   spiky=True, fold=8, arch=0.08, wave=(0.6, 8), curl=0.3,
                   thick=0.3, veins=(17, 62), petiole=20,
                   colours=("#3d6f28", "#c89232", "#86bb52")),
    "holly": _S(kind="strip", name="Holly", L=75, W=26, a=0.7, b=0.8,
                lobes=None, teeth=(4, 5.0, None), spiky=True, fold=16,
                arch=0.03, wave=(4.0, 4), curl=0.5, thick=0.6,
                veins=(5, 55), petiole=8, glossy=True,
                colours=("#1f4a22", "#1f4a22", "#2f6a2f")),
    "magnolia": _S(kind="strip", name="Magnolia", L=200, W=45, a=0.85,
                   b=0.85, lobes=None, teeth=None, fold=10, arch=0.07,
                   wave=(0.8, 3), curl=1.0, thick=0.6, veins=(12, 58),
                   petiole=25, glossy=True, colours=("#26512a", "#26512a",
                                                     "#3c7a36")),
    "eucalyptus": _S(kind="strip", name="Eucalyptus", L=150, W=14,
                     a=0.9, b=1.6, lobes=None, teeth=None, fold=3,
                     arch=0.05, sickle=0.18, wave=(0.2, 3), curl=0.1,
                     thick=0.4, veins=(12, 65), petiole=20,
                     colours=("#6f8c78", "#6f8c78", "#8aa890")),
    "elm": _S(kind="strip", name="English elm", L=90, W=30, a=0.6, b=1.2,
              lobes=None, teeth=(14, 1.6, 2), fold=10, arch=0.05,
              wave=(1.0, 8), curl=0.4, thick=0.3, veins=(12, 45),
              petiole=6, asym=0.3, colours=("#3f6f28", "#c9a82e",
                                            "#86b850")),
    "bay": _S(kind="strip", name="Bay laurel", L=90, W=20, a=0.9, b=1.1,
              lobes=None, teeth=None, fold=8, arch=0.05, wave=(0.8, 4),
              curl=0.5, thick=0.45, veins=(9, 55), petiole=8, glossy=True,
              colours=("#2d5a2a", "#2d5a2a", "#4b7f3a")),
    # --- palmate blades
    "maple": _S(kind="palm", name="Norway maple", R=75, lobes=5,
                spread=135, depth=0.5, pointed=True, teeth=(2.5, 9.0),
                fold=6, arch=0.05, wave=(0.6, 10), curl=0.3, thick=0.3,
                petiole=90, colours=("#3f7a2c", "#d8431f", "#8cc458")),
    "sycamore": _S(kind="palm", name="Sycamore", R=85, lobes=5, spread=145,
                   depth=0.35, pointed=False, teeth=(6, 2.0), fold=8,
                   arch=0.05, wave=(0.8, 12), curl=0.4, thick=0.35,
                   petiole=100, colours=("#355f26", "#b88a2a", "#7eb24e")),
    "plane": _S(kind="palm", name="London plane", R=100, lobes=5,
                spread=130, depth=0.5, pointed=True, teeth=(2, 5.0),
                fold=5, arch=0.04, wave=(1.0, 10), curl=0.4, thick=0.35,
                petiole=60, colours=("#4a7a2e", "#b0823a", "#90c05a")),
    "sweetgum": _S(kind="palm", name="Sweetgum", R=80, lobes=5,
                   spread=160, depth=0.62, pointed=True, teeth=(4, 0.8),
                   fold=6, arch=0.05, wave=(0.4, 10), curl=0.2, thick=0.3,
                   petiole=80, colours=("#3a6f2a", "#8a1f3a", "#86b852")),
    "ginkgo": _S(kind="palm", name="Ginkgo", R=55, lobes=2, spread=75,
                 depth=0.18, pointed=False, teeth=None, fan=True, fold=2,
                 arch=0.03, wave=(0.5, 12), curl=0.2, thick=0.3,
                 petiole=50, colours=("#5f8f3a", "#e8c21e", "#a2d060")),
    # --- compound leaves
    "ash": _S(kind="pinnate", name="Ash", leaflet="ash_leaflet", pairs=5,
              terminal=True, rachis=260, petiole=50,
              colours=("#4a7a2c", "#d4c048", "#98c85c")),
    "rowan": _S(kind="pinnate", name="Rowan", leaflet="rowan_leaflet",
                pairs=7, terminal=True, rachis=190, petiole=30,
                colours=("#3f742a", "#d0502a", "#8cc458")),
    "walnut": _S(kind="pinnate", name="Walnut", leaflet="walnut_leaflet",
                 pairs=3, terminal=True, rachis=260, petiole=70,
                 colours=("#46762e", "#c8a23a", "#92c25a")),
    "horse_chestnut": _S(kind="digitate", name="Horse chestnut",
                         leaflet="hc_leaflet", count=7, petiole=140,
                         colours=("#3a6b28", "#b8762a", "#86b852")),
    # --- needles, scales, fronds
    "pine": _S(kind="fascicle", name="Scots pine", needles=2, L=60,
               r=0.8, twist=40, colours=("#3a5f3a", "#3a5f3a", "#5f8a50")),
    "spruce": _S(kind="shoot", name="Norway spruce", L=120, needle=18,
                 r=0.6, rows=0, density=11, colours=("#2c4d2e", "#2c4d2e",
                                                    "#6a9a4a")),
    "fir": _S(kind="shoot", name="Silver fir", L=120, needle=25, r=0.9,
              rows=2, density=8, colours=("#2a4a30", "#2a4a30", "#5f8f50")),
    "yew": _S(kind="shoot", name="Yew", L=110, needle=25, r=1.1, rows=2,
              density=6, colours=("#1f3d25", "#1f3d25", "#4a7a3a")),
    "cedar": _S(kind="spur", name="Atlas cedar", needles=30, L=25, r=0.5,
                colours=("#5a7a78", "#5a7a78", "#7a9a90")),
    "larch": _S(kind="spur", name="European larch", needles=36, L=30,
                r=0.45, colours=("#5a8a3a", "#d8a02a", "#9fd06a")),
    "cypress": _S(kind="scales", name="Leyland cypress", L=120,
                  colours=("#2f5a32", "#2f5a32", "#4f7f40")),
    "palm": _S(kind="frond", name="Date palm frond", L=2400, pinnae=60,
               colours=("#5a7a3a", "#8a7a3a", "#7a9a4a")),
}
# leaflets of the compound leaves (strip blades, not listed on their own)
LEAFLETS = {
    "ash_leaflet": _S(kind="strip", L=75, W=13, a=0.75, b=1.3, lobes=None,
                      teeth=(14, 0.8, None), fold=10, arch=0.05,
                      wave=(0.3, 3), curl=0.2, thick=0.25, veins=(9, 55),
                      petiole=3),
    "rowan_leaflet": _S(kind="strip", L=55, W=9, a=0.8, b=1.1, lobes=None,
                        teeth=(16, 0.9, None), fold=10, arch=0.04,
                        wave=(0.2, 3), curl=0.2, thick=0.22, veins=(8, 55),
                        petiole=1),
    "walnut_leaflet": _S(kind="strip", L=110, W=28, a=0.8, b=1.2,
                         lobes=None, teeth=None, fold=8, arch=0.05,
                         wave=(0.8, 4), curl=0.4, thick=0.3, veins=(11, 55),
                         petiole=4),
    "hc_leaflet": _S(kind="strip", L=180, W=30, a=1.4, b=0.9, lobes=None,
                     teeth=(30, 1.4, 2), fold=10, arch=0.06, wave=(0.8, 6),
                     curl=0.4, thick=0.3, veins=(18, 55), petiole=3),
}
SEASONS = ("Summer", "Autumn", "Spring")


# ------------------------------------------------------------ vectors
def _lerp(a, b, t):
    return a + (b - a) * t


def _rot(p, ang, about=(0.0, 0.0)):
    c, s = math.cos(ang), math.sin(ang)
    x, y = p[0] - about[0], p[1] - about[1]
    return (about[0] + x * c - y * s, about[1] + x * s + y * c) + tuple(
        p[2:])


# ------------------------------------------------------- strip blades
def _profile(sp, s):
    """The blade's half width at s (0 base .. 1 tip), before the margin."""
    a, b = sp["a"], sp["b"]
    peak = a / (a + b)
    norm = peak ** a * (1 - peak) ** b
    return sp["W"] / 2 * (s ** a) * ((1 - s) ** b) / norm


def _teeth(s, count, depth, second):
    """Serrations as a mm offset: a forward-leaning saw (tooth points
    toward the tip), optionally with a finer second set on each."""
    if not count:
        return 0.0
    ph = (s * count) % 1.0
    saw = (1 - ph) ** 2.2
    out = depth * saw
    if second:
        ph2 = (s * count * second) % 1.0
        out += depth * 0.4 * (1 - ph2) ** 2.2
    return out - depth * 0.5


def half_width(sp, s, side=1):
    """Half width at s on one side (+1 left, -1 right), margin included —
    never negative."""
    w = _profile(sp, s)
    lobes = sp.get("lobes")
    if lobes:
        n, depth, pointed = lobes
        ph = (s * n + 0.5) % 1.0
        bump = (1 - abs(2 * ph - 1)) if pointed else math.sin(math.pi * ph)
        env = 1 - depth + depth * bump ** (0.6 if not pointed else 1.0)
        w *= env if s > 0.08 else 1.0
    if sp.get("base_ears"):              # oak's little auricles at the base
        w += sp["W"] * sp["base_ears"] * max(0.0, 1 - s / 0.08) * (s / 0.08)
    teeth = sp.get("teeth")
    if teeth:
        count, depth, second = teeth
        edge = min(1.0, s / 0.12, (1 - s) / 0.04)      # none at base, tip
        t = _teeth(s, count, depth, second) * max(edge, 0.0)
        if sp.get("spiky"):
            t = abs(t) * 1.6 - depth * 0.3
        w += t
    if sp.get("asym") and side < 0:
        w *= 1 - sp["asym"] * max(0.0, 1 - s / 0.35)
    # a tooth or sinus must never pinch the blade to nothing part way
    # along: a zero width there is a vertex the solid cannot pass through
    return max(w, 0.3 * _profile(sp, s))


def _shape_z(sp, x, y, L, width):
    """Height of the top surface over the flat point (x, y): the fold up
    from the midrib, the arch and droop to the tip, the margin rolled
    down and waved."""
    s = min(max(x / L, 0.0), 1.0)
    fold = math.tan(math.radians(sp.get("fold", 0))) * abs(y)
    arch = -sp.get("arch", 0.0) * L * s * s
    rel = abs(y) / max(width, 1e-6)
    curl = -sp.get("curl", 0.0) * rel ** 3
    amp, n = sp.get("wave") or (0.0, 1)
    wave = amp * math.sin(s * n * 2 * math.pi) * rel ** 2
    return fold + arch + curl + wave


def _sickle(sp, x, y, L):
    """Eucalyptus leaves bend sideways like a scythe."""
    k = sp.get("sickle", 0.0)
    return y + k * L * (x / L) ** 2 if k else y


def strip_grid(sp, L=None, detail="high"):
    """Rows of (x, y, z) top-surface points: row i at s_i, each running
    from the right margin across the midrib to the left one."""
    n, m, _ = DETAIL[detail]
    L = float(L or sp["L"])
    k = L / sp["L"]
    back = sp.get("base_back", 0.0) * L          # a heart base reaches back
    rows = []
    for i in range(n + 1):
        s = i / n
        x = -back + (L + back) * s
        wl = half_width(sp, s, 1) * k
        wr = half_width(sp, s, -1) * k
        if 0 < i < n and min(wl, wr) < 0.6:
            continue       # hair-thin rows weld into pinches at 0.1 mm
        row = []
        for j in range(m + 1):
            t = -1 + 2 * j / m
            y = t * (wl if t > 0 else wr)
            z = _shape_z(sp, x, y, L, max(wl, wr, 1e-6))
            row.append((x, _sickle(sp, x, y, L), z))
        rows.append(row)
    return rows


def surface_z(sp, x, y, L):
    """The shaped top at a flat point — where veins lie."""
    s = min(max(x / L, 0.0), 1.0)
    return _shape_z(sp, x, y, L, max(half_width(sp, s), 1e-6))


# --------------------------------------------------- palmate blades
def _palm_r(sp, th):
    """The margin's distance from the petiole at angle th (radians from
    the leaf's axis): pointed or rounded lobes over a web."""
    n, spread, depth = sp["lobes"], math.radians(sp["spread"]), sp["depth"]
    R = sp["R"]
    if sp.get("fan"):                         # ginkgo: a fan with a notch
        rel = min(abs(th) / spread, 1.0)
        notch = 1 - depth * max(0.0, 1 - abs(th) / 0.12)
        # a wedge at the petiole opening into the fan's rounded edge
        return R * (1 - rel ** 5) ** 0.45 * notch
    centres = [spread * (2 * k / (n - 1) - 1) for k in range(n)]
    width = spread / (n - 1)
    best = 0.0
    for c in centres:
        d = abs(th - c) / width
        lobe_len = 1.0 - 0.25 * abs(c) / spread          # side lobes shorter
        if sp["pointed"]:
            v = max(0.0, 1 - d) ** 1.4
        else:
            v = math.cos(min(d, 1.0) * math.pi / 2) ** 0.8
        best = max(best, v * lobe_len)
    r = R * (1 - depth + depth * best)
    teeth = sp.get("teeth")
    if teeth:
        count, amp = teeth
        ph = (th / width * count) % 1.0
        r += amp * ((1 - ph) ** 2 - 0.4) * best
    edge = abs(th) / spread
    if edge > 0.92:                            # the sinus at the petiole
        r *= max(0.25, 1 - (edge - 0.92) / 0.2)
    return r


def palm_grid(sp, scale=1.0, detail="high"):
    n, m, _ = DETAIL[detail]
    n = n + n // 2
    spread = math.radians(sp["spread"] if sp.get("fan")
                          else min(sp["spread"] + 22, 175))
    rows = []
    for i in range(n + 1):
        th = -spread + 2 * spread * i / n
        r = _palm_r(sp, th) * scale
        row = []
        for j in range(m + 1):
            u = j / m
            x, y = u * r * math.cos(th), u * r * math.sin(th)
            row.append((x, y, _shape_z(sp, max(x, 0.0), y, sp["R"] * scale,
                                       r)))
        rows.append(row)
    return rows


# ------------------------------------------------- the closed blade
def sheet(mesh, rows, thick):
    """A closed solid from a grid of top-surface points: the bottom sheet
    *thick* below, walls round all four edges."""
    top = [list(r) for r in rows]
    bot = [[(p[0], p[1], p[2] - thick) for p in r] for r in rows]
    n, m = len(rows) - 1, len(rows[0]) - 1
    pts = [p for r in top for p in r] + [p for r in bot for p in r]
    off = (n + 1) * (m + 1)
    idx = lambda i, j: i * (m + 1) + j
    tris = []
    for i in range(n):
        for j in range(m):
            a, b, c, d = idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(
                i, j + 1)
            tris += [(a, b, c), (a, c, d)]
            tris += [(off + a, off + c, off + b), (off + a, off + d, off + c)]
    for i in range(n):              # the two long margins
        for j, flip in ((0, False), (m, True)):
            a, b = idx(i, j), idx(i + 1, j)
            quad = [(a, off + a, off + b), (a, off + b, b)]
            tris += [(q[0], q[2], q[1]) for q in quad] if flip else quad
    for j in range(m):              # base and tip ends
        for i, flip in ((0, True), (n, False)):
            a, b = idx(i, j), idx(i, j + 1)
            quad = [(a, off + a, off + b), (a, off + b, b)]
            tris += [(q[0], q[2], q[1]) for q in quad] if flip else quad
    _orient_piece(mesh, pts, tris)


def _orient_piece(mesh, pts, tris):
    """Add a piece whose triangles share one winding; turn them all
    round if the enclosed volume came out negative (the grid's
    orientation depends on which way the rows run)."""
    vol = 0.0
    for a, b, c in tris:
        pa, pb, pc = pts[a], pts[b], pts[c]
        vol += (pa[0] * (pb[1] * pc[2] - pb[2] * pc[1])
                - pa[1] * (pb[0] * pc[2] - pb[2] * pc[0])
                + pa[2] * (pb[0] * pc[1] - pb[1] * pc[0]))
    if vol < 0:
        tris = [(a, c, b) for a, b, c in tris]
    # weld points that land together (the grid narrows to a point at a
    # blade's base and tip) and drop the triangles that collapse there,
    # or the solid would be open along index-distinct twins
    index, welded, keep = {}, [], []
    remap = []
    for p in pts:
        k = _key(p)
        if k not in index:
            index[k] = len(welded)
            welded.append(k)
        remap.append(index[k])
    for a, b, c in tris:
        a, b, c = remap[a], remap[b], remap[c]
        if len({a, b, c}) == 3:
            keep.append((a, b, c))
    mesh.piece(welded, keep)


def _key(p):
    return (round(p[0], 1), round(p[1], 1), round(p[2], 1))


# ------------------------------------------------------------- veins
def strip_veins(mesh, sp, L, detail, lift):
    """Midrib, secondary veins curving toward the tip, and the petiole —
    tubes on the shaped top surface."""
    _, _, sides = DETAIL[detail]
    if not sides:
        return
    k = L / sp["L"]
    back = sp.get("base_back", 0.0) * L
    mid = []
    for i in range(21):
        x = -back * 0.3 + (L * 0.97) * i / 20
        mid.append((x, _sickle(sp, x, 0.0, L),
                    surface_z(sp, x, 0.0, L) + lift))
    r_mid = max(0.5, sp["W"] * k * 0.02)
    mesh.tube(mid, [r_mid * (1 - 0.8 * i / 20) for i in range(21)], sides)
    count, angle = sp.get("veins") or (0, 45)
    for side in (1, -1):
        for v in range(count):
            s0 = 0.06 + 0.86 * (v + 0.5) / count
            x0 = -back + (L + back) * s0
            w = half_width(sp, s0, side) * k
            path = []
            for q in range(7):
                f = q / 6
                # out at the vein's angle, bending toward the tip near the
                # margin (camptodromous)
                dx = w * f / math.tan(math.radians(angle)) * (1 + 0.6 * f)
                x = x0 + dx
                s = min(max((x + back) / (L + back), 0.0), 1.0)
                wy = half_width(sp, s, side) * k
                y = side * min(w * f, wy * 0.9)
                path.append((x, _sickle(sp, x, y, L),
                             surface_z(sp, x, y, L) + lift * 0.6))
            mesh.tube(path, [r_mid * 0.45 * (1 - 0.6 * q / 6)
                             for q in range(7)], max(4, sides - 2))
    _petiole(mesh, sp.get("petiole", 5) * k, (-back * 0.3, 0.0,
                                              surface_z(sp, 0, 0, L) + lift),
             r_mid * 1.3, sides)


def _petiole(mesh, length, root, r, sides):
    if length <= 0 or not sides:
        return
    path = [(root[0] - length * q / 5, 0.0,
             root[2] - length * 0.15 * (q / 5) ** 2) for q in range(6)]
    mesh.tube(path, [r * (1 + 0.25 * q / 5) for q in range(6)], sides)


def palm_veins(mesh, sp, scale, detail, lift):
    _, _, sides = DETAIL[detail]
    if not sides:
        return
    n = sp["lobes"]
    spread = math.radians(sp["spread"])
    R = sp["R"] * scale
    r_v = max(0.5, R * 0.012)
    angles = ([spread * (2 * k / (n - 1) - 1) for k in range(n)]
              if not sp.get("fan") else
              [spread * (2 * k / 12 - 1) for k in range(13)])
    for th in angles:
        r = _palm_r(sp, th) * scale * 0.93
        path = []
        for q in range(9):
            u = q / 8
            x, y = u * r * math.cos(th), u * r * math.sin(th)
            path.append((x, y, _shape_z(sp, max(x, 0.0), y, R, r) + lift))
        mesh.tube(path, [r_v * (1 - 0.75 * q / 8) for q in range(9)], sides)
    _petiole(mesh, sp.get("petiole", 50) * scale, (0.0, 0.0, lift),
             r_v * 1.4, sides)


# ------------------------------------------------------- whole leaves
def blade_mesh(sp, L=None, detail="high"):
    """(blade Mesh, veins Mesh) of one simple leaf, midrib along +x from
    the petiole at the origin."""
    L = float(L or sp["L"])
    blade, veins = Mesh(), Mesh()
    sheet(blade, strip_grid(sp, L, detail), sp.get("thick", 0.3))
    strip_veins(veins, sp, L, detail, lift=0.05)
    return blade, veins


def palm_mesh(sp, scale=1.0, detail="high"):
    blade, veins = Mesh(), Mesh()
    sheet(blade, palm_grid(sp, scale, detail), sp.get("thick", 0.3))
    palm_veins(veins, sp, scale, detail, lift=0.05)
    return blade, veins


def _placed(mesh_from, mesh_to, ang, dx, dy, dz=0.0, tilt=0.0):
    """Copy *mesh_from*'s points turned by *ang* about z (and tipped by
    *tilt* about x) into *mesh_to* at (dx, dy, dz)."""
    base = len(mesh_to.points)
    ct, st = math.cos(tilt), math.sin(tilt)
    for p in mesh_from.points:
        y, z = p[1] * ct - p[2] * st, p[1] * st + p[2] * ct
        q = _rot((p[0], y), ang)
        mesh_to.points.append([round(q[0] + dx, 1), round(q[1] + dy, 1),
                               round(z + dz, 1)])
    mesh_to.faces.extend([base + a, base + b, base + c]
                         for a, b, c in mesh_from.faces)


def compound_mesh(sp, detail="high"):
    """Leaflets on a rachis: pinnate pairs (and a terminal one) or
    digitate round the petiole's tip."""
    leaflet = LEAFLETS[sp["leaflet"]]
    blade, veins = Mesh(), Mesh()
    _, _, sides = DETAIL[detail]
    # a dozen leaflets at full detail is 90k triangles: one step down
    detail = "medium" if detail == "high" else detail
    one_b, one_v = blade_mesh(leaflet, detail=detail)
    if sp["kind"] == "digitate":
        n = sp["count"]
        for k in range(n):
            ang = math.radians(-95 + 190 * k / (n - 1))
            size = 1.0 - 0.45 * abs(k - (n - 1) / 2) / ((n - 1) / 2)
            lb, lv = blade_mesh(leaflet, leaflet["L"] * size, detail)
            _placed(lb, blade, ang, 0, 0)
            _placed(lv, veins, ang, 0, 0)
        if sides:
            _petiole(veins, sp["petiole"], (0.0, 0.0, 0.0), 2.2, sides)
        return blade, veins
    rachis, pairs = sp["rachis"], sp["pairs"]
    path = [(rachis * q / 12, 0.0, -rachis * 0.05 * (q / 12) ** 2)
            for q in range(13)]
    if sides:
        veins.tube(path, [1.6 * (1 - 0.6 * q / 12) for q in range(13)],
                   sides)
        _petiole(veins, sp["petiole"], path[0], 1.8, sides)
    for k in range(pairs):
        x = rachis * (0.12 + 0.8 * k / max(pairs - 1, 1))
        z = -rachis * 0.05 * (x / rachis) ** 2
        for side in (1, -1):
            ang = side * math.radians(62 + 8 * k / pairs)
            _placed(one_b, blade, ang, x, 0, z, tilt=side * 0.12)
            _placed(one_v, veins, ang, x, 0, z, tilt=side * 0.12)
    if sp.get("terminal"):
        _placed(one_b, blade, 0.0, rachis, 0, -rachis * 0.05)
        _placed(one_v, veins, 0.0, rachis, 0, -rachis * 0.05)
    return blade, veins


def needle_mesh(sp, detail="high"):
    """Conifers: (needles, twig) meshes."""
    needles, twig = Mesh(), Mesh()
    sides = max(4, DETAIL[detail][2] or 4)
    rng = random.Random(7)
    kind = sp["kind"]
    if kind == "fascicle":             # pine: needles in a sheath
        twig.tube([(0, 0, 0), (4, 0, 0)], [1.2, 1.0], sides)
        for k in range(sp["needles"]):
            ang = math.radians(k * 360 / sp["needles"])
            path = []
            for q in range(9):
                f = q / 8
                spread = 4 * f
                tw = math.radians(sp["twist"] * f)
                path.append((4 + sp["L"] * f,
                             math.cos(ang + tw) * (0.7 + spread),
                             math.sin(ang + tw) * (0.7 + spread) + 3 * f * f))
            needles.tube(path, [sp["r"] * (1 - 0.8 * (q / 8) ** 3)
                                for q in range(9)], sides)
        return needles, twig
    if kind in ("shoot",):
        L = sp["L"]
        twig.tube([(L * q / 8, 0, -L * 0.03 * (q / 8) ** 2)
                   for q in range(9)], [2.2 * (1 - 0.5 * q / 8)
                                        for q in range(9)], sides)
        count = int(L / 10 * sp["density"])
        for k in range(count):
            f = (k + 0.5) / count
            x = L * f * 0.95
            if sp["rows"]:       # two flat ranks, like fir and yew
                ang = (0.0 if k % 2 else math.pi) + rng.uniform(-0.25, 0.25)
                up = rng.uniform(-0.05, 0.2)
            else:                # all round the shoot, like spruce
                ang = k * 2.39996
                up = math.sin(ang)
            ln = sp["needle"] * (0.8 + 0.4 * math.sin(math.pi * f))
            d = (math.cos(math.radians(55)), math.cos(ang) * 0.82,
                 math.sin(ang) * 0.82 if not sp["rows"] else up)
            base = (x, math.cos(ang) * 1.8, math.sin(ang) * 1.8
                    - L * 0.03 * f * f)
            tip = (base[0] + d[0] * ln, base[1] + d[1] * ln,
                   base[2] + d[2] * ln)
            midp = tuple((base[i] + tip[i]) / 2 for i in range(3))
            needles.tube([base, midp, tip], [sp["r"], sp["r"] * 0.9,
                                             sp["r"] * 0.2], 4)
        return needles, twig
    if kind == "spur":                 # cedar and larch: tufts on a spur
        twig.tube([(0, 0, 0), (0, 0, 6)], [2.5, 2.0], sides)
        for k in range(sp["needles"]):
            ang = k * 2.39996
            tilt = math.radians(25 + 40 * ((k * 0.618) % 1.0))
            d = (math.sin(tilt) * math.cos(ang), math.sin(tilt) * math.sin(ang),
                 math.cos(tilt))
            ln = sp["L"] * rng.uniform(0.8, 1.1)
            base = (d[0] * 1.2, d[1] * 1.2, 5.5)
            tip = (base[0] + d[0] * ln, base[1] + d[1] * ln,
                   base[2] + d[2] * ln)
            needles.tube([base, tip], [sp["r"], sp["r"] * 0.3], 4)
        return needles, twig
    if kind == "scales":               # cypress: flattened scale sprays
        L = sp["L"]

        def spray(start, d, length, depth):
            steps = max(3, int(length / 3))
            path = [(start[0] + d[0] * length * q / steps,
                     start[1] + d[1] * length * q / steps, 0.0)
                    for q in range(steps + 1)]
            needles.tube(path, [1.3 * (1 - 0.5 * q / steps)
                                for q in range(steps + 1)], 4)
            if depth < 2:
                for q in range(1, steps, 2 if depth == 0 else 3):
                    p = path[q]
                    for side in (1, -1):
                        a = math.atan2(d[1], d[0]) + side * math.radians(40)
                        spray(p, (math.cos(a), math.sin(a)),
                              length * 0.38, depth + 1)
        spray((0.0, 0.0), (1.0, 0.0), L, 0)
        twig.tube([(-10, 0, 0), (0, 0, 0)], [1.8, 1.6], sides)
        return needles, twig
    raise ValueError(kind)


def frond_mesh(sp, detail="high"):
    """A feather palm frond: an arching rachis and folded pinnae."""
    blade, twig = Mesh(), Mesh()
    sides = max(4, DETAIL[detail][2] or 4)
    L = sp["L"]
    rach = [(L * q / 16, 0.0, L * 0.25 * math.sin(math.pi * q / 16 * 0.9)
             - L * 0.12 * (q / 16) ** 2) for q in range(17)]
    twig.tube(rach, [14 * (1 - 0.8 * q / 16) for q in range(17)], sides)
    pinna = dict(LEAFLETS["walnut_leaflet"], L=420, W=30, teeth=None,
                 fold=35, veins=(0, 45), petiole=0, a=0.6, b=1.6)
    count = sp["pinnae"]
    for k in range(count):
        f = 0.12 + 0.86 * k / count
        i = min(int(f * 16), 15)
        t = f * 16 - i
        p = tuple(_lerp(rach[i][c], rach[i + 1][c], t) for c in range(3))
        size = 1.0 - 0.6 * abs(f - 0.45) / 0.55
        pb = Mesh()
        sheet(pb, strip_grid(pinna, pinna["L"] * size,
                             "medium" if detail == "high" else "low"),
              0.5)
        for side in (1, -1):
            _placed(pb, blade, side * math.radians(55), p[0], p[1], p[2],
                    tilt=side * 0.5)
    return blade, twig


# ---------------------------------------------------------- the node
def build(species: str, season: str = "Summer", size: float = 0.0,
          detail: str = "high"):
    """The leaf as a group standing on z = 0: blade (season colour) and
    veins / petiole / twig (a lighter or woody tone)."""
    from .city_buildings import color, group, move
    sp = SPECIES[species]
    summer, autumn, spring = sp["colours"]
    tone = {"Summer": summer, "Autumn": autumn, "Spring": spring}.get(
        season, summer)
    kind = sp["kind"]
    if kind == "strip":
        blade, veins = blade_mesh(sp, size or sp["L"], detail)
    elif kind == "palm":
        blade, veins = palm_mesh(sp, (size or sp["R"]) / sp["R"], detail)
    elif kind in ("pinnate", "digitate"):
        blade, veins = compound_mesh(sp, detail)
    elif kind == "frond":
        blade, veins = frond_mesh(sp, detail)
    else:
        blade, veins = needle_mesh(sp, detail)
    woody = kind in ("fascicle", "shoot", "spur", "scales", "frond")
    vein_tone = ("#6b4a2e" if woody else _lighter(tone, 0.25))
    parts = [color(blade.node(f"{sp['name']} blade"), tone,
                   "Plastic" if sp.get("glossy") else "Matte")]
    if veins.points:
        parts.append(color(veins.node("Veins and petiole" if not woody
                                      else "Twig"), vein_tone, "Matte"))
    zs = [p[2] for m in (blade, veins) for p in m.points] or [0.0]
    return move(group(f"{sp['name']} leaf", parts), 0, 0, -min(zs),
                f"{sp['name']} leaf")


def _lighter(hexcol, f):
    r, g, b = (int(hexcol[i:i + 2], 16) for i in (1, 3, 5))
    r, g, b = (int(c + (255 - c) * f) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"
