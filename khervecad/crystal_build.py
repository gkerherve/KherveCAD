"""The Crystal Builder's programs: atoms -> unit cell -> supercell ->
particle, written as OpenSCAD with real loops (Qt-free but `apply`).

One crystal is built at up to three levels, each its own Object:

- **Unit cell** — the conventional cell: its lattice box (glass), every
  atom (the ones on faces, edges and corners repeated so the cell reads
  whole) and, where the crystal has them, its coordination polyhedra
  (SiO4 tetrahedra, TiO6 octahedra…), translucent over the atoms.
- **Supercell** — ``for`` i, j, k over na x nb x nc cells, each an
  instance of ONE tiling cell (the cell's atoms without the repeats,
  or its polyhedra), inside the supercell's lattice box.
- **Particle** — a shape (sphere, hemisphere, cube, box, cylinder,
  hexagonal prism, octahedron) centred on the origin (a hemisphere
  stands on z = 0), filled with every cell — or every N x N x N block
  of cells — whose centre lies inside. Spheres and hemispheres on a
  lattice whose c-axis is vertical stack each column with a ``while``
  loop ("while the next cell's centre is inside"); other shapes use
  ``for`` + ``if``.

Everything is in NANOMETRES and every tunable (radius, block size,
gap, supercell counts) is a document variable prefixed with the
crystal (``quartz_r``), so the Variables sheet reshapes a build and two
builds never collide. Before anything is applied the cells, atoms,
polyhedra and triangles are COUNTED (exactly, the same loops in
Python; by volume past `MAX_ITERATIONS`) and a build over `BUDGET`
triangles is refused with the way out — a particle whose atoms would
freeze the view fills with blocks instead ("auto").

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace
from functools import lru_cache

from . import crystal as cr

NM = 0.1                                   # nm per Å
BUILDS = ("unit_cell", "supercell", "particle", "hierarchy", "scatter")
REPRESENTATIONS = ("auto", "atoms", "polyhedra", "both")
FILLS = ("auto", "atoms", "polyhedra", "blocks")
#: shape -> what `size` measures
SHAPES = {"sphere": "diameter", "hemisphere": "diameter",
          "cube": "edge", "box": "x, y, z edges (box_nm)",
          "cylinder": "diameter; height_nm its height",
          "hexagonal_prism": "across corners; height_nm its height",
          "octahedron": "tip to tip"}
#: triangles: refused above BUDGET; "auto" keeps atoms under COMFORT
BUDGET = 800_000
COMFORT = 350_000
#: blocks in one particle before "auto" makes the blocks bigger
MAX_BLOCKS = 20_000
#: loop iterations counted exactly; past it, counts come from volumes
MAX_ITERATIONS = 2_000_000
BOX_COLOUR = "#9ecbff"
_SINGULAR = {"tetrahedra": "tetrahedron", "octahedra": "octahedron",
             "cubes": "cube", "triangles": "triangle",
             "bipyramids": "bipyramid", "cuboctahedra": "cuboctahedron",
             "polyhedra": "polyhedron"}
_BLOCK_SIZES = (2, 3, 4, 5, 8, 10, 15, 20, 25, 30, 40, 50, 75, 100, 150,
                200, 300, 500)


class BuildError(ValueError):
    """A build that cannot or should not be made; says what to do."""


@dataclass
class Spec:
    crystal: cr.Crystal
    build: str = "hierarchy"
    representation: str = "auto"
    supercell: tuple = (4, 4, 4)
    shape: str = "sphere"
    size: float = 10.0                     # nm, see SHAPES
    height: float | None = None            # nm (cylinder, hexagonal prism)
    box: tuple | None = None               # nm (box)
    fill: str = "auto"
    block: int = 10                        # cells per block edge
    gap: float = 0.03                      # between blocks, of a block
    atom_scale: float = 1.0                # x covalent radius
    cell_box: bool = True
    fn: int = 12                           # sphere segments
    scale: float = 1.0                     # model units per nm
    prefix: str = ""
    #: build "scatter": particles spread over a patch, as a dispersion
    #: on a substrate reads under an electron microscope
    count: int = 12
    area: tuple = (100.0, 100.0)           # nm, the patch they sit on
    seed: int = 1                          # the same scatter comes back
    min_gap: float = 1.0                   # nm between particles
    substrate: bool = True
    random_turn: bool = True
    #: write the counts in as numbers instead of document variables: a
    #: Part Library crystal must stand alone, and OpenSCAD modules only
    #: see top-level variables
    inline: bool = False

    def check(self):
        def bad(msg):
            raise BuildError(msg)
        if self.build not in BUILDS:
            bad(f"build is one of {', '.join(BUILDS)}.")
        if self.representation not in REPRESENTATIONS:
            bad(f"representation is one of {', '.join(REPRESENTATIONS)}.")
        if self.fill not in FILLS:
            bad(f"fill is one of {', '.join(FILLS)}.")
        if self.shape not in SHAPES:
            bad(f"shape is one of {', '.join(SHAPES)}.")
        if not 0 < self.size <= 10_000:
            bad("size_nm must be above 0 (and at most 10 µm).")
        if len(self.supercell) != 3 or not all(
                1 <= int(n) <= 60 for n in self.supercell):
            bad("supercell is three counts from 1 to 60.")
        if not 1 <= self.block <= 1000:
            bad("block_cells runs from 1 to 1000.")
        if not 0 <= self.gap < 0.5:
            bad("gap runs from 0 to 0.5 (a fraction of a block).")
        if not 0.05 <= self.atom_scale <= 3:
            bad("atom_scale runs from 0.05 to 3 (x the covalent radius).")
        if not 3 <= self.fn <= 64:
            bad("segments runs from 3 to 64.")
        if self.height is not None and self.height <= 0:
            bad("height_nm must be above 0.")
        if self.box is not None and (len(self.box) != 3
                                     or min(self.box) <= 0):
            bad("box_nm is three positive edges.")
        if self.build == "scatter":
            if not 1 <= int(self.count) <= 500:
                bad("count runs from 1 to 500 particles.")
            if len(self.area) != 2 or min(self.area) <= 0:
                bad("area_nm is [x, y] nanometres, both above 0.")
            if self.min_gap < 0:
                bad("min_gap_nm cannot be negative.")


# ---------------------------------------------------------------- text
def _n(x: float) -> str:
    """0.49134, -0.24567, 12, 0 — five decimals of a nanometre."""
    s = f"{x:.5f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def _vec(p, k=NM) -> str:
    return "[" + ", ".join(_n(v * k) for v in p) + "]"


def _lin(terms) -> str:
    """"0.49134 * i - 0.24567 * j + 0.1" from [(coefficient, name or
    None)]; zero terms dropped."""
    parts = []
    for coef, name in terms:
        if abs(coef) < 5e-6:
            continue
        mag = _n(abs(coef))
        body = mag if name is None else (name if mag == "1"
                                         else f"{mag} * {name}")
        parts.append(("-" if coef < 0 else "+", body))
    if not parts:
        return "0"
    text = ("-" if parts[0][0] == "-" else "") + parts[0][1]
    for sign, body in parts[1:]:
        text += f" {sign} {body}"
    return text


def _ident(key: str) -> str:
    word = re.sub(r"\W", "_", key.strip()) or "Crystal"
    word = word[0].upper() + word[1:]
    return word if word[0].isalpha() else "C" + word


def _add(*vs):
    return tuple(sum(v[i] for v in vs) for i in range(3))


def vectors_nm(c: cr.Crystal):
    return tuple(tuple(x * NM for x in v) for v in c.vectors())


def _reach(V):
    """Row norms of the inverse lattice matrix: the most a fractional
    coordinate grows per nm of distance, per axis."""
    (a, b, c), (d, e, f), (g, h, i) = (
        (V[0][0], V[1][0], V[2][0]), (V[0][1], V[1][1], V[2][1]),
        (V[0][2], V[1][2], V[2][2]))
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    inv = ((e * i - f * h, c * h - b * i, b * f - c * e),
           (f * g - d * i, a * i - c * g, c * d - a * f),
           (d * h - e * g, b * g - a * h, a * e - b * d))
    return tuple(math.sqrt(sum((x / det) ** 2 for x in row)) for row in inv)


def parallelepiped(v1, v2, v3):
    """OpenSCAD (points, faces) of the cell spanned by three vectors."""
    pts = [(0.0, 0.0, 0.0), v1, _add(v1, v2), v2, v3, _add(v1, v3),
           _add(v1, v2, v3), _add(v2, v3)]
    centre = tuple(sum(p[i] for p in pts) / 8 for i in range(3))
    faces = []
    for f in ([0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5],
              [2, 3, 7, 6], [3, 0, 4, 7]):
        n = [0.0, 0.0, 0.0]                       # Newell normal
        for k in range(4):
            p, q = pts[f[k]], pts[f[(k + 1) % 4]]
            n[0] += (p[1] - q[1]) * (p[2] + q[2])
            n[1] += (p[2] - q[2]) * (p[0] + q[0])
            n[2] += (p[0] - q[0]) * (p[1] + q[1])
        mid = [sum(pts[v][i] for v in f) / 4 for i in range(3)]
        out = sum(n[i] * (mid[i] - centre[i]) for i in range(3)) > 0
        faces.append(list(reversed(f)) if out else f)  # clockwise outside
    return [list(p) for p in pts], faces


def _prism_text(V, k=1.0) -> str:
    pts, faces = parallelepiped(*V)
    return (f"polyhedron(points = [{', '.join(_vec(p, k) for p in pts)}], "
            f"faces = {faces})")


@lru_cache(maxsize=None)
def sphere_triangles(fn: int) -> int:
    from . import mesh
    from .model import CadNode
    return len(mesh.tessellate(CadNode("sphere", "S",
                                       dict(radius=1.0, segments=fn))))


# ------------------------------------------------------------ contents
def _cell_atoms(c, display):
    """[(element, xyz Å)]: the cell's atoms, plus — for the displayed
    unit cell — their repeats on the far faces, edges and corners."""
    out = []
    for el, *f in c.atoms:
        f = [x % 1.0 for x in f]
        f = [0.0 if x > 1 - 1e-9 else x for x in f]
        images = [f]
        if display:
            for axis in range(3):
                if f[axis] < 1e-6:
                    images += [g[:axis] + [1.0] + g[axis + 1:]
                               for g in images]
        out += [(el, c.cart(g)) for g in images]
    return out


def resolve_rep(c, rep, level):
    has = bool(c.polyhedra_sites())
    if rep == "auto":
        rep = ("both" if level == "unit_cell" else "polyhedra") if has \
            else "atoms"
    if rep in ("polyhedra", "both") and not has:
        rep = "atoms"
    return rep


def _content(c, rep, display, spec):
    """(lines, atoms, polyhedra, triangles) of one cell's contents."""
    lines, n_atoms, n_poly, tris = [], 0, 0, 0
    poly = c.polyhedra or {}
    hidden = ({poly.get("centre"), poly.get("ligand")}
              if rep == "polyhedra" else set())
    groups = {}
    if rep in ("atoms", "both", "polyhedra"):
        for el, p in _cell_atoms(c, display):
            if el not in hidden:
                groups.setdefault(el, []).append(p)
    per_sphere = sphere_triangles(spec.fn)
    for el, points in groups.items():
        r = cr.radius(el) * NM * spec.atom_scale
        lines.append(f'color("{cr.colour(el)}") {{  // {el} atoms')
        for p in points:
            lines.append(f"  translate({_vec(p)}) sphere(r = {_n(r)}, "
                         f"$fn = {spec.fn});  // {el}")
        lines.append("}")
        n_atoms += len(points)
        tris += len(points) * per_sphere
    if rep in ("polyhedra", "both"):
        label = c.polyhedra_label()
        one = label.rsplit(" ", 1)
        one = f"{one[0]} {_SINGULAR.get(one[1], one[1])}"
        col = cr.colour(poly["centre"])
        head = (f'color("{col}", 0.4)' if rep == "both"
                else f'color("{col}")')
        lines.append(f"{head} {{  // {label}")
        for _idx, _p, ligands in c.polyhedra_sites():
            pts, faces = cr.polyhedron(ligands)
            if not faces:
                continue
            lines.append(
                f"  polyhedron(points = [{', '.join(_vec(q) for q in pts)}"
                f"], faces = {faces});  // {one}")
            n_poly += 1
            tris += len(faces)
        lines.append("}")
    return lines, n_atoms, n_poly, tris


def _module(name, lines) -> str:
    body = "\n".join("  " + line for line in lines)
    return f"module {name}() {{\n{body}\n}}\n"


# --------------------------------------------------------------- shapes
def _shape(spec, p):
    """(variables, bounding radius, its expression, python test, test
    expression over x0 y0 z0, volume) of the particle shape."""
    s = spec.size
    h = spec.height or s
    shape = spec.shape
    if shape in ("sphere", "hemisphere"):
        r = f"{p}_r"
        vars_ = [(r, s / 2, "radius (nm)")]
        test = (lambda x, y, z: x * x + y * y + z * z <= (s / 2) ** 2
                and (shape == "sphere" or z >= 0))
        expr = f"x0 * x0 + y0 * y0 + z0 * z0 <= {r} * {r}"
        if shape == "hemisphere":
            expr = f"z0 >= 0 && {expr}"
        vol = (4 / 3 if shape == "sphere" else 2 / 3) * math.pi * (s / 2) ** 3
        return vars_, s / 2, r, test, expr, vol
    if shape == "cube":
        L = f"{p}_L"
        return ([(L, s, "edge (nm)")], s * math.sqrt(3) / 2,
                f"{L} * 0.86603",
                lambda x, y, z: max(abs(x), abs(y), abs(z)) <= s / 2,
                f"max(abs(x0), abs(y0), abs(z0)) <= {L} / 2", s ** 3)
    if shape == "box":
        bx = spec.box or (s, s, s)
        names = [f"{p}_Lx", f"{p}_Ly", f"{p}_Lz"]
        return ([(n, v, f"{n[-1]} edge (nm)") for n, v in zip(names, bx)],
                math.sqrt(sum(v * v for v in bx)) / 2,
                f"sqrt({names[0]} * {names[0]} + {names[1]} * {names[1]} "
                f"+ {names[2]} * {names[2]}) / 2",
                lambda x, y, z: (abs(x) <= bx[0] / 2 and abs(y) <= bx[1] / 2
                                 and abs(z) <= bx[2] / 2),
                " && ".join(f"abs({v}0) <= {n} / 2"
                            for v, n in zip("xyz", names)),
                bx[0] * bx[1] * bx[2])
    if shape == "cylinder":
        r, H = f"{p}_r", f"{p}_H"
        return ([(r, s / 2, "radius (nm)"), (H, h, "height (nm)")],
                math.hypot(s / 2, h / 2), f"sqrt({r} * {r} + {H} * {H} / 4)",
                lambda x, y, z: x * x + y * y <= (s / 2) ** 2
                and abs(z) <= h / 2,
                f"x0 * x0 + y0 * y0 <= {r} * {r} && abs(z0) <= {H} / 2",
                math.pi * (s / 2) ** 2 * h)
    if shape == "hexagonal_prism":
        D, H = f"{p}_D", f"{p}_H"
        rin = s / 2 * math.cos(math.radians(30))
        c30 = math.cos(math.radians(30))

        def test(x, y, z):
            return (abs(x * c30 + y * 0.5) <= rin and abs(y) <= rin
                    and abs(y * 0.5 - x * c30) <= rin and abs(z) <= h / 2)
        expr = (f"abs(x0 * 0.86603 + y0 * 0.5) <= {D} * 0.43301 && "
                f"abs(y0) <= {D} * 0.43301 && abs(y0 * 0.5 - x0 * 0.86603) "
                f"<= {D} * 0.43301 && abs(z0) <= {H} / 2")
        return ([(D, s, "across corners (nm)"), (H, h, "height (nm)")],
                math.hypot(s / 2, h / 2), f"sqrt({D} * {D} + {H} * {H}) / 2",
                test, expr, 3 * math.sqrt(3) / 2 * (s / 2) ** 2 * h)
    L = f"{p}_L"                                   # octahedron
    return ([(L, s, "tip to tip (nm)")], s / 2, f"{L} / 2",
            lambda x, y, z: abs(x) + abs(y) + abs(z) <= s / 2,
            f"abs(x0) + abs(y0) + abs(z0) <= {L} / 2", (s / 2) ** 3 * 4 / 3)


def _uses_while(spec, V):
    return (spec.shape in ("sphere", "hemisphere")
            and abs(V[2][0]) < 1e-12 and abs(V[2][1]) < 1e-12)


def _footprint(spec) -> float:
    """Radius of the particle's shadow on the plane, nm: what keeps two
    scattered particles apart."""
    s = spec.size
    if spec.shape == "cube":
        return s * math.sqrt(2) / 2
    if spec.shape == "box":
        bx = spec.box or (s, s, s)
        return math.hypot(bx[0], bx[1]) / 2
    return s / 2              # sphere, hemisphere, cylinder, prism, octahedron


def _lift(spec) -> float:
    """How high the particle's centre sits when it rests on the plane (a
    hemisphere is built standing on z = 0 already)."""
    s = spec.size
    if spec.shape == "hemisphere":
        return 0.0
    if spec.shape == "box":
        return (spec.box or (s, s, s))[2] / 2
    if spec.shape in ("cylinder", "hexagonal_prism"):
        return (spec.height or s) / 2
    return s / 2


def _scatter_spots(spec):
    """[(x, y, z, turn)]: dart throwing over the area, no two closer than
    their footprints plus min_gap, each resting on the plane. The same
    seed gives the same arrangement; fewer than asked when it is full."""
    import random
    rng = random.Random(int(spec.seed))
    r, lift = _footprint(spec), _lift(spec)
    reach = [max(side / 2 - r, 0.0) for side in spec.area]
    apart = (2 * r + spec.min_gap) ** 2
    spots = []
    for _dart in range(max(int(spec.count) * 400, 4000)):
        if len(spots) >= spec.count:
            break
        x = rng.uniform(-reach[0], reach[0])
        y = rng.uniform(-reach[1], reach[1])
        if all((x - sx) ** 2 + (y - sy) ** 2 >= apart
               for sx, sy, _z, _t in spots):
            spots.append((x, y, lift, rng.uniform(0.0, 360.0)
                          if spec.random_turn else 0.0))
    return spots


def _count_particle(spec, V, S):
    """Cells (or blocks) the particle keeps, counted with the same loops
    and tests the program runs — or from the volume past
    MAX_ITERATIONS. Returns (count, exact)."""
    _vars, rb, _rbx, test, _expr, vol = _shape(spec, "p")
    g = _reach(V)
    n = [math.ceil(rb * g[a] / S) + 1 for a in range(3)]
    cvol = abs(_det(V)) * S ** 3
    if (2 * n[0] + 1) * (2 * n[1] + 1) * (2 * n[2] + 1) > MAX_ITERATIONS:
        return int(round(vol / cvol)), False
    half = _add(*V)
    half = tuple(S * x / 2 for x in half)
    count = 0
    if _uses_while(spec, V):
        r = spec.size / 2
        cz = S * V[2][2]
        for i in range(-n[0], n[0] + 1):
            for j in range(-n[1], n[1] + 1):
                x0 = S * (i * V[0][0] + j * V[1][0]) + half[0]
                y0 = S * (i * V[0][1] + j * V[1][1]) + half[1]
                if spec.shape == "hemisphere":
                    k = 0
                else:
                    k = math.ceil(-math.sqrt(max(r * r - x0 * x0 - y0 * y0,
                                                 0)) / cz - 0.5)
                while x0 * x0 + y0 * y0 + (cz * (k + 0.5)) ** 2 <= r * r:
                    count += 1
                    k += 1
        return count, True
    for i in range(-n[0], n[0] + 1):
        for j in range(-n[1], n[1] + 1):
            for k in range(-n[2], n[2] + 1):
                x = S * (i * V[0][0] + j * V[1][0] + k * V[2][0]) + half[0]
                y = S * (i * V[0][1] + j * V[1][1] + k * V[2][1]) + half[1]
                z = S * (i * V[0][2] + j * V[1][2] + k * V[2][2]) + half[2]
                if test(x, y, z):
                    count += 1
    return count, True


def _det(V):
    (a, b, c), (d, e, f), (g, h, i) = V
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)


def _particle_module(name, cell_call, spec, V, p, blocks):
    """The particle's module text and its extra variables."""
    vars_, _rb, rbx, _test, expr, _vol = _shape(spec, p)
    g = _reach(V)
    S = f"{p}_N * " if blocks else ""
    per = f" / {p}_N" if blocks else ""
    half = _add(*V)
    lines = [f"{p}_ni = ceil({rbx} * {_n(g[0])}{per}) + 1;  // loop reach a",
             f"{p}_nj = ceil({rbx} * {_n(g[1])}{per}) + 1;  // loop reach b"]

    def wrap(text):
        return f"{S}({text})" if blocks and text != "0" else text
    origin = [wrap(_lin([(V[0][a], "i"), (V[1][a], "j"), (V[2][a], "k")]))
              for a in range(3)]
    if _uses_while(spec, V):
        r = f"{p}_r"
        x0 = wrap(_lin([(V[0][0], "i"), (V[1][0], "j"), (half[0] / 2, None)]))
        y0 = wrap(_lin([(V[0][1], "i"), (V[1][1], "j"), (half[1] / 2, None)]))
        cz = f"{S}{_n(V[2][2])}"
        zc = f"{cz} * (k + 0.5)"
        start = ("0" if spec.shape == "hemisphere" else
                 f"ceil(-sqrt(max({r} * {r} - x0 * x0 - y0 * y0, 0)) / "
                 f"({cz}) - 0.5)")
        cond = f"x0 * x0 + y0 * y0 + ({zc}) * ({zc}) <= {r} * {r}"
        lines += [
            f"for (i = [-{p}_ni : {p}_ni]) for (j = [-{p}_nj : {p}_nj]) {{"
            "  // Columns",
            f"  x0 = {x0};  // column centre x",
            f"  y0 = {y0};  // column centre y",
            f"  for (k = [for (k = {start}, _w = 0; ({cond}) && _w < 1000; "
            f"k = k + 1, _w = _w + 1) k])  // Stack while inside",
            f"    translate([{', '.join(origin)}]) {cell_call}();",
            "}"]
    else:
        lines.insert(2, f"{p}_nk = ceil({rbx} * {_n(g[2])}{per}) + 1;  "
                        "// loop reach c")
        centre = [wrap(_lin([(V[0][a], "i"), (V[1][a], "j"), (V[2][a], "k"),
                             (half[a] / 2, None)])) for a in range(3)]
        lines += [
            f"for (i = [-{p}_ni : {p}_ni]) for (j = [-{p}_nj : {p}_nj]) "
            f"for (k = [-{p}_nk : {p}_nk]) {{  // Cells",
            f"  x0 = {centre[0]};  // cell centre x",
            f"  y0 = {centre[1]};  // cell centre y",
            f"  z0 = {centre[2]};  // cell centre z",
            f"  if ({expr})  // Inside the {spec.shape.replace('_', ' ')}",
            f"    translate([{', '.join(origin)}]) {cell_call}();",
            "}"]
    return _module(name, lines), vars_


# -------------------------------------------------------------- program
def _tris_label(n: int) -> str:
    return f"{n:,} triangles"


def program(spec: Spec):
    """(OpenSCAD program, stats) for *spec*; raises BuildError when the
    build is impossible or over BUDGET."""
    spec.check()
    c = spec.crystal
    p = spec.prefix or re.sub(r"\W", "_", c.key.lower())
    I = _ident(c.key)
    V = vectors_nm(c)
    scatter = spec.build == "scatter"
    levels = (["particle", "supercell", "unit_cell"]
              if spec.build == "hierarchy"
              else ["particle"] if scatter else [spec.build])
    stats = {"crystal": c.key, "name": c.name, "unit": "nm",
             "levels": levels, "notes": []}
    variables, modules, cells_done, calls = [], [], set(), []
    total = 0

    def tiling(rep):
        name = f"{I}_cell_{rep}"
        if rep not in cells_done:
            lines, na, npoly, tris = _content(c, rep, False, spec)
            modules.append(_module(name, lines))
            cells_done.add(rep)
            tiling.data[rep] = (na, npoly, tris)
        return name, tiling.data[rep]
    tiling.data = {}

    # ---- particle
    placement = 0.0
    if "particle" in levels:
        fill = spec.fill
        rep = resolve_rep(c, "auto" if fill in ("auto", "blocks") else fill,
                          "particle")
        if fill in ("atoms", "polyhedra") and rep != fill:
            stats["notes"].append(f"{c.name} has no coordination polyhedra"
                                  " — filled with atoms.")
        cells, exact = _count_particle(spec, V, 1)
        _l, na, npoly, per_cell = _content(c, rep, False, spec)
        # a scatter draws its particle `count` times: share the budget
        share = max(1, int(spec.count)) if scatter else 1
        if fill == "auto":
            fill = rep if cells * per_cell * share <= COMFORT else "blocks"
        N = spec.block
        if fill == "blocks":
            blocks, exact = _count_particle(spec, V, N)
            while blocks * share > MAX_BLOCKS:
                bigger = [b for b in _BLOCK_SIZES if b > N]
                if not bigger:
                    break
                N = bigger[0]
                blocks, exact = _count_particle(replace(spec, block=N), V, N)
            if N != spec.block:
                stats["notes"].append(
                    f"Blocks of {spec.block}^3 cells would be too many; "
                    f"used {N}^3.")
            variables += [(f"{p}_N", N, "unit cells per block edge"),
                          (f"{p}_g", spec.gap,
                           "gap between blocks (fraction)")]
            col = cr.colour(c.polyhedra["centre"] if c.polyhedra
                            else c.atoms[0][0])
            modules.append(_module(f"{I}_block", [
                f'color("{col}")  // Supercell block',
                f"scale([{p}_N * (1 - {p}_g), {p}_N * (1 - {p}_g), "
                f"{p}_N * (1 - {p}_g)]) {_prism_text(V)};  "
                "// Block of N x N x N cells"]))
            call = f"{I}_block"
            tris = blocks * 12
            part = {"blocks": blocks, "block_cells": N,
                    "cells": blocks * N ** 3}
        else:
            call, (na, npoly, per_cell) = tiling(fill)
            tris = cells * per_cell
            part = {"cells": cells, "atoms": cells * na,
                    "polyhedra": cells * npoly}
        mod, shape_vars = _particle_module(f"{I}_particle", call, spec, V, p,
                                           fill == "blocks")
        variables = shape_vars + variables
        modules.append(mod)
        part.update(shape=spec.shape, fill=fill, size_nm=spec.size,
                    triangles=tris, exact_count=exact,
                    uses_while=_uses_while(spec, V))
        stats["particle"] = part
        total += tris
        rb = _shape(spec, p)[1]
        label = (f"{c.name} {spec.shape.replace('_', ' ')} "
                 f"{_n(spec.size)} nm ({fill})")
        if scatter:
            spots = _scatter_spots(spec)
            if len(spots) < spec.count:
                stats["notes"].append(
                    f"The area holds {len(spots)} of the {spec.count} "
                    "particles asked for — make it bigger, the particles "
                    "smaller or the gap tighter.")
            ax, ay = spec.area
            lines = []
            if spec.substrate:
                lines += ['color("#8a8f98", 0.35)  // Substrate',
                          f"translate([{_n(-ax / 2)}, {_n(-ay / 2)}, -0.4]) "
                          f"cube([{_n(ax)}, {_n(ay)}, 0.4]);  "
                          "// Substrate slab"]
            rows = ", ".join("[" + ", ".join(_n(v) for v in spot) + "]"
                             for spot in spots)
            lines += [f"for (t = [{rows}])  // Particles on the area",
                      "  translate([t[0], t[1], t[2]]) rotate([0, 0, t[3]]) "
                      f"{I}_particle();"]
            modules.append(_module(f"{I}_scatter", lines))
            drawn = tris * len(spots) + (12 if spec.substrate else 0)
            stats["scatter"] = {"particles": len(spots),
                                "area_nm": [ax, ay],
                                "per_particle_triangles": tris,
                                "triangles": drawn}
            total += drawn - tris              # the copies, not the one
            calls.append(("", f"{I}_scatter",
                          f"{len(spots)} {c.name} particles on "
                          f"{_n(ax)} x {_n(ay)} nm"))
        else:
            calls.append(("", f"{I}_particle", label))
            placement = rb + max(2.0, 0.15 * rb)
        if spec.build == "hierarchy" and fill == "blocks":
            spec = replace(spec, supercell=(N, N, N))

    # ---- supercell
    if "supercell" in levels:
        na_, nb_, nc_ = (int(n) for n in spec.supercell)
        rep = resolve_rep(c, spec.representation, "supercell")
        call, (na, npoly, per_cell) = tiling(rep)
        if spec.build == "hierarchy":
            # the block the particle is made of can be 50^3 cells: show
            # as much of it as stays light, and say so
            n0 = na_
            while na_ > 1 and na_ * nb_ * nc_ * per_cell > COMFORT // 2:
                na_ = nb_ = nc_ = na_ - 1
            if na_ < n0:
                stats["notes"].append(
                    f"The supercell Object shows {na_}^3 cells of the "
                    f"{n0}^3 in one block: all of them would be too heavy "
                    "to draw.")
        cells = na_ * nb_ * nc_
        tris = cells * per_cell + (12 if spec.cell_box else 0)
        if spec.build == "hierarchy" and tris > COMFORT and rep != "polyhedra":
            stats["notes"].append("The supercell's atoms are many: its "
                                  "Object is heavy to draw.")
        names = [f"{p}_na", f"{p}_nb", f"{p}_nc"]
        variables += [(n, v, f"supercell cells along {ax}")
                      for n, v, ax in zip(names, (na_, nb_, nc_), "abc")]
        lines = []
        if spec.cell_box:
            upright = abs(V[2][0]) < 1e-12 and abs(V[2][1]) < 1e-12
            if upright and (abs(V[1][0]) < 1e-12 or na_ == nb_):
                box = (f"scale([{names[0]}, {names[1]}, {names[2]}]) "
                       f"{_prism_text(V)}")
            else:
                box = _prism_text(tuple(tuple(x * n for x in v) for v, n in
                                        zip(V, (na_, nb_, nc_))))
            lines += [f'color("{BOX_COLOUR}", 0.12)  // Supercell box',
                      f"{box};  // Lattice box"]
        lines += [
            f"for (i = [0 : {names[0]} - 1]) for (j = [0 : {names[1]} - 1]) "
            f"for (k = [0 : {names[2]} - 1])  // Unit cells",
            f"  translate([{', '.join(_lin([(V[0][a], 'i'), (V[1][a], 'j'), (V[2][a], 'k')]) for a in range(3))}]) {call}();"]
        modules.append(_module(f"{I}_supercell", lines))
        stats["supercell"] = {"cells": cells, "counts": [na_, nb_, nc_],
                              "representation": rep, "atoms": cells * na,
                              "polyhedra": cells * npoly, "triangles": tris}
        total += tris
        corners = [_add(*(tuple(x * n * s for x in v) for v, n, s in
                          zip(V, (na_, nb_, nc_), bits)))
                   for bits in ((a, b, cc) for a in (0, 1) for b in (0, 1)
                                for cc in (0, 1))]
        xs = [q[0] for q in corners]
        ys = [q[1] for q in corners]
        shift = (placement - min(xs), -(min(ys) + max(ys)) / 2)
        calls.append((f"translate([{_n(shift[0])}, {_n(shift[1])}, 0]) ",
                      f"{I}_supercell",
                      f"{c.name} supercell {na_}x{nb_}x{nc_}"))
        width = max(xs) - min(xs)
        placement += width + max(1.0, 0.3 * width)

    # ---- unit cell
    if "unit_cell" in levels:
        rep = resolve_rep(c, spec.representation, "unit_cell")
        lines, na, npoly, tris = _content(c, rep, True, spec)
        if spec.cell_box:
            lines = [f'color("{BOX_COLOUR}", 0.15)  // Cell box',
                     f"{_prism_text(V)};  // Lattice cell"] + lines
            tris += 12
        modules.append(_module(f"{I}_unit_cell", lines))
        stats["unit_cell"] = {"atoms_drawn": na, "atoms_per_cell":
                              len(c.atoms), "polyhedra": npoly,
                              "representation": rep, "triangles": tris}
        total += tris
        corners = [_add(*(tuple(x * s for x in v) for v, s in zip(V, bits)))
                   for bits in ((a, b, cc) for a in (0, 1) for b in (0, 1)
                                for cc in (0, 1))]
        xs = [q[0] for q in corners]
        ys = [q[1] for q in corners]
        shift = (placement - min(xs), -(min(ys) + max(ys)) / 2)
        at = (f"translate([{_n(shift[0])}, {_n(shift[1])}, 0]) "
              if placement else "")
        calls.append((at, f"{I}_unit_cell", f"{c.name} unit cell"))

    stats["triangles"] = total
    if total > BUDGET:
        raise BuildError(
            f"That build is about {_tris_label(total)} — more than the 3D "
            f"view can draw ({_tris_label(BUDGET)}). Fill the particle "
            "with blocks (fill: blocks, bigger block_cells), make it "
            "smaller, or use polyhedra instead of atoms.")
    if total > COMFORT:
        stats["notes"].append(f"About {_tris_label(total)}: expect a few "
                              "seconds per change.")

    scale = "" if abs(spec.scale - 1) < 1e-12 else \
        f"scale([{p}_s, {p}_s, {p}_s]) "
    if scale:
        variables.append((f"{p}_s", spec.scale,
                          "model units per nm (the document is not in nm)"))
    head = [
        f"// {c.name} ({c.formula}), {c.space_group}, {c.system}",
        f"// a = {_n(c.a * NM)} nm, b = {_n(c.b * NM)} nm, "
        f"c = {_n(c.c * NM)} nm, alpha = {c.alpha:g}, beta = {c.beta:g}, "
        f"gamma = {c.gamma:g}; {len(c.atoms)} atoms per cell.",
        f"// Source: {c.source}. Covalent radii (Cordero et al. 2008).",
        "// UNITS: nanometres. Built by KherveCAD's Crystal Builder.",
    ]
    body = "\n".join(modules) + "\n" + "".join(
        f"{at}{scale}{name}();  // {label}\n" for at, name, label in calls)
    if spec.inline and variables:
        # a part that must stand alone: its numbers written in (whole
        # words only, so quartz_N never touches the local quartz_ni)
        values = {name: _n(value) if isinstance(value, float)
                  else str(value) for name, value, _c in variables}
        body = re.sub(r"\b(" + "|".join(map(re.escape, values)) + r")\b",
                      lambda m: values[m.group(1)], body)
        variables = []
    text = "\n".join(head) + "\n"
    text += "".join(f"{name} = {_n(value) if isinstance(value, float) else value};"
                    f"  // {comment}\n" for name, value, comment in variables)
    text += "\n" + body
    return text, stats


# ---------------------------------------------------------------- apply
def _free_prefix(model, key):
    base = re.sub(r"\W", "_", key.lower())
    taken = {str(n.params.get("variable", "")) for n in model.root.walk()
             if n.type == "assign"}
    prefix, k = base, 2
    while any(t.startswith(prefix + "_") for t in taken):
        prefix, k = f"{base}{k}", k + 1
    return prefix


def apply(window, spec: Spec) -> dict:
    """Build *spec* into the window's document: Objects appended to
    Main, the unit made nanometres when the document is empty (else
    the build is scaled into the document's unit), the sphere segments
    lowered for atoms. One undo step. Returns the stats."""
    from . import units
    from .scadparse import parse_scad
    model = window.model
    notes = []
    if model.unit != "nm":
        if not model.root.children:
            model.set_unit("nm")
            notes.append("The document unit is now nanometres.")
        else:
            spec = replace(spec, scale=1e-6 / units.to_mm(model.unit))
            notes.append(
                f"The document is in {model.unit}, so the crystal is drawn "
                f"at true size in {model.unit} — very small. Start a new "
                "document to build in nanometres.")
    spec = replace(spec, prefix=spec.prefix or _free_prefix(model,
                                                            spec.crystal.key))
    code, stats = program(spec)
    has_atoms = any(stats.get(level, {}).get(key)
                    for level in ("unit_cell", "supercell", "particle")
                    for key in ("atoms", "atoms_drawn"))
    if has_atoms and model.global_fn_on and model.global_fn > spec.fn:
        model.set_global_fn(True, spec.fn)
        notes.append(f"Round objects now use {spec.fn} segments (was "
                     "more): thousands of atoms stay light.")
    root, warnings = parse_scad(code)
    if not root.children:
        raise BuildError("The crystal program produced nothing: "
                         + "; ".join(warnings[:3]))
    objects = []
    for child in list(root.children):
        root.remove(child)
        model.root.add(child)
        if child.type == "component":
            objects.append({"id": child.id, "name": child.name})
    model.group_variables()
    model.structure_changed.emit()
    stats["objects"] = objects
    stats["variables_prefix"] = spec.prefix
    stats["notes"] = notes + stats["notes"]
    if warnings:
        stats["warnings"] = warnings[:8]
    return stats


# ------------------------------------------------------------------ MCP
def spec_from_params(params: dict) -> Spec:
    """A Spec from build_crystal's arguments; BuildError on bad input."""
    from .crystal_library import get
    if params.get("custom"):
        try:
            crystal = cr.custom(params["custom"])
        except ValueError as exc:
            raise BuildError(str(exc))
    else:
        try:
            crystal = get(params.get("crystal") or "")
        except KeyError as exc:
            raise BuildError(str(exc.args[0]))
    sc = params.get("supercell", 4)
    sc = (sc, sc, sc) if isinstance(sc, (int, float)) else tuple(sc)
    try:
        spec = Spec(
            crystal=crystal,
            build=str(params.get("build", "hierarchy")),
            representation=str(params.get("representation", "auto")),
            supercell=tuple(int(n) for n in sc),
            shape=str(params.get("shape", "sphere")),
            size=float(params.get("size_nm", 10.0)),
            height=(None if params.get("height_nm") is None
                    else float(params["height_nm"])),
            box=(None if params.get("box_nm") is None
                 else tuple(float(v) for v in params["box_nm"])),
            fill=str(params.get("fill", "auto")),
            block=int(params.get("block_cells", 10)),
            gap=float(params.get("gap", 0.03)),
            atom_scale=float(params.get("atom_scale", 1.0)),
            cell_box=bool(params.get("cell_box", True)),
            fn=int(params.get("segments", 12)),
            count=int(params.get("count", 12)),
            area=tuple(float(v) for v in params.get("area_nm",
                                                    (100.0, 100.0))),
            seed=int(params.get("seed", 1)),
            min_gap=float(params.get("min_gap_nm", 1.0)),
            substrate=bool(params.get("substrate", True)),
            random_turn=bool(params.get("random_turn", True)))
    except (TypeError, ValueError) as exc:
        raise BuildError(f"Bad argument: {exc}")
    spec.check()
    return spec


def list_crystals(params: dict) -> dict:
    """list_crystals: the library, or one crystal in full."""
    from .crystal_library import CATEGORIES, LIBRARY, get
    key = params.get("crystal")
    if key:
        try:
            crystal = get(key)
        except KeyError as exc:
            raise BuildError(str(exc.args[0]))
        out = crystal.summary()
        out["atoms"] = [[el, round(x, 5), round(y, 5), round(z, 5)]
                        for el, x, y, z in crystal.atoms]
        out["nearest_nm"] = {f"{a}-{b}": round(crystal.nearest(a, b) / 10,
                                               4)
                             for a, b, _d in crystal.bonds}
        return out
    cat = params.get("category")
    rows = [c.summary() for c in LIBRARY.values()
            if not cat or c.category.lower() == str(cat).lower()]
    for row in rows:
        row.pop("source", None)
    return {"categories": list(CATEGORIES), "crystals": rows,
            "shapes": SHAPES, "units": "nm"}


def build_crystal(window, params: dict) -> dict:
    """build_crystal: build, or with dry_run only count."""
    spec = spec_from_params(params)
    if params.get("dry_run"):
        _code, stats = program(replace(spec, prefix=_free_prefix(
            window.model, spec.crystal.key)))
        stats["dry_run"] = True
        return stats
    return apply(window, spec)
