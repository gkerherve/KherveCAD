"""Crystal SURFACES: a slab of any crystal cut along any (hkl) plane
(Qt-free but `apply`).

Si(111), α-quartz (0001), rutile (110), Cu(100), GaN (10-10)… A
surface is the crystal re-described in a cell whose first two vectors
lie IN the plane:

1. ``in_plane_basis`` searches the integer lattice vectors u with
   h·u1 + k·u2 + l·u3 = 0 (they lie in the plane for ANY crystal
   system, since (hkl) are reciprocal-lattice coordinates) and takes
   the shortest pair whose cross product is exactly ±(h, k, l) — only
   then do they span the plane's 2D lattice, not a super-cell of it —
   reduced to an angle of at least 60°. A third vector w with
   h·w1 + k·w2 + l·w3 = 1 steps one interplanar spacing, so (u, v, w)
   has the conventional cell's volume and carries all its atoms.
2. Every atom is re-expressed in (u, v, w), wrapped into the in-plane
   parallelogram, and repeated ``layers`` times along w — wrapping per
   atom keeps the slab a straight prism instead of a sheared one.
3. It is turned so the surface normal is +z and u runs along +x, the
   top surface at z = 0 and the slab below it.

``termination`` (0..1 of a layer) shifts where the cut falls, which
picks the terminating plane: Si(111) cut between the close pair of a
bilayer shows one dangling bond per atom, cut through it three.
Surfaces are BULK-TERMINATED — no relaxation or reconstruction (no
Si(111) 7x7), which is a structure the user would bring from a paper.

The program is one module for a surface cell (the full slab depth,
atoms grouped by element) and a ``for`` over nx × ny of it, in
NANOMETRES, like `crystal_build`, whose budget and `apply` rules it
shares.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, replace

from . import crystal as cr
from . import crystal_build as cb

SEARCH = 6                                   # |index| of candidate vectors
MAX_REPEAT = 80


@dataclass
class SurfaceSpec:
    crystal: cr.Crystal
    miller: tuple = (1, 1, 1)
    repeat: tuple = (6, 6)                   # surface cells along u, v
    layers: int = 3                          # interplanar spacings deep
    #: 0..1 of a layer; None cuts in the widest gap between planes
    termination: float | None = None
    atom_scale: float = 1.0
    fn: int = 12
    cell_box: bool = True
    scale: float = 1.0                       # model units per nm
    prefix: str = ""

    def check(self):
        if len(self.miller) != 3 or not any(self.miller):
            raise cb.BuildError("miller is three (or four, hexagonal "
                                "h k i l) integers, not all zero.")
        if not all(1 <= int(n) <= MAX_REPEAT for n in self.repeat):
            raise cb.BuildError(f"repeat is two counts from 1 to "
                                f"{MAX_REPEAT}.")
        if not 1 <= self.layers <= 60:
            raise cb.BuildError("layers runs from 1 to 60.")
        if self.termination is not None and not 0 <= self.termination < 1:
            raise cb.BuildError("termination runs from 0 to just under 1.")
        if not 0.05 <= self.atom_scale <= 3:
            raise cb.BuildError("atom_scale runs from 0.05 to 3.")
        if not 3 <= self.fn <= 64:
            raise cb.BuildError("segments runs from 3 to 64.")


# ------------------------------------------------------------- vectors
def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _norm(a):
    return math.sqrt(_dot(a, a))


def _lat(c, n):
    return c.cart(n)


def parse_miller(value) -> tuple:
    """(h, k, l) from a list or text: "111", "1 1 1", "1-10", "0001",
    "10-10" (hexagonal h k i l, i dropped once checked)."""
    if isinstance(value, str):
        text, out, sign = value.strip("()[] "), [], 1
        tokens = text.replace(",", " ").split()
        if len(tokens) == 1:
            for ch in tokens[0]:
                if ch == "-":
                    sign = -1
                elif ch.isdigit():
                    out.append(sign * int(ch))
                    sign = 1
                else:
                    raise cb.BuildError(f"Cannot read Miller indices "
                                        f"{value!r}.")
        else:
            try:
                out = [int(t) for t in tokens]
            except ValueError:
                raise cb.BuildError(f"Cannot read Miller indices {value!r}.")
    else:
        out = [int(v) for v in value]
    if len(out) == 4:
        if out[2] != -(out[0] + out[1]):
            raise cb.BuildError("In h k i l, i must equal -(h + k).")
        out = [out[0], out[1], out[3]]
    if len(out) != 3 or not any(out):
        raise cb.BuildError("Miller indices are three integers (or four, "
                            "hexagonal), not all zero.")
    g = math.gcd(math.gcd(abs(out[0]), abs(out[1])), abs(out[2]))
    return tuple(v // g for v in out)


def centerings(c):
    """Fractional translations mapping the cell's atoms onto themselves
    ((0, 0, 0) first): the I, F, C… centring the conventional cell
    hides. Without them Si(111) came out a 2x2 of its real cell."""
    eps = 1e-4

    def key(el, f):
        return (el,) + tuple(round((x % 1.0) % (1 - eps) / eps) for x in f)
    sites = {key(el, f) for el, *f in c.atoms}
    el0, *f0 = c.atoms[0]
    out = [(0.0, 0.0, 0.0)]
    for el, *f in c.atoms[1:]:
        if el != el0:
            continue
        t = tuple((f[i] - f0[i]) % 1.0 for i in range(3))
        if max(min(x, 1 - x) for x in t) < eps:
            continue
        if all(key(e, [g[i] + t[i] for i in range(3)]) in sites
               for e, *g in c.atoms) and t not in out:
            out.append(t)
    return out


def in_plane_basis(c, hkl):
    """(u, v, w) lattice vectors in conventional fractions: u, v
    spanning the (hkl) plane's primitive 2D lattice, w the shortest
    step to the next lattice plane."""
    rng = range(-SEARCH, SEARCH + 1)
    cents = centerings(c)
    plane, step, seen = [], [], set()
    for n in itertools.product(rng, rng, rng):
        for t in cents:
            f = tuple(n[i] + t[i] for i in range(3))
            k = tuple(round(x, 4) for x in f)
            if not any(k) or k in seen:
                continue
            seen.add(k)
            dot = _dot(f, hkl)
            if abs(dot) < 1e-6:
                plane.append((_norm(_lat(c, f)), f))
            elif dot > 1e-6:
                step.append((dot, _norm(_lat(c, f)), f))
    if not plane or not step:
        raise cb.BuildError(f"No surface cell found for {hkl}.")
    delta = min(s[0] for s in step)
    step = [s for s in step if abs(s[0] - delta) < 1e-6]
    # primitive 2D area = primitive volume / interplanar spacing
    v_prim = c.volume() / len(cents)
    G = _cross(_lat(c, (1, 0, 0)), _lat(c, (0, 1, 0)))  # scale below
    normal_len = _norm(_recip(c, hkl))
    d = delta / normal_len
    area = v_prim / d
    plane.sort()
    best = None
    for (lu, u), (lv, v) in itertools.combinations(plane[:150], 2):
        cu, cv = _lat(c, u), _lat(c, v)
        if abs(_norm(_cross(cu, cv)) - area) > 1e-4 * area:
            continue
        cos = _dot(cu, cv) / (lu * lv)
        if cos > 1e-6:                        # take the 90-120° angle
            v, cv, cos = tuple(-x for x in v), tuple(-x for x in cv), -cos
        if cos < -0.5 - 1e-6:
            continue
        score = (round(lu + lv, 6), round(abs(cos + 0.5), 6))
        if best is None or score < best[0]:
            best = (score, u, v)
    del G
    if best is None:
        raise cb.BuildError(f"No surface cell found for {hkl}: indices too "
                            "high for this cell.")
    _s, u, v = best
    normal = _cross(_lat(c, u), _lat(c, v))
    if _dot(normal, _lat(c, step[0][2])) < 0:  # right-handed, normal up
        u, v = v, u
        normal = tuple(-x for x in normal)
    nn = _norm(normal)
    w = min(step, key=lambda s: (round(-_dot(_lat(c, s[2]), normal)
                                       / (s[1] * nn), 6), s[1]))[2]
    return u, v, w


def _recip(c, hkl):
    """h a* + k b* + l c* (Å⁻¹, no 2π): its length is 1 / d(hkl)."""
    a1, a2, a3 = c.vectors()
    V = _dot(a1, _cross(a2, a3))
    bs = [tuple(x / V for x in _cross(a2, a3)),
          tuple(x / V for x in _cross(a3, a1)),
          tuple(x / V for x in _cross(a1, a2))]
    return tuple(sum(hkl[j] * bs[j][i] for j in range(3)) for i in range(3))


def _solve(M, x):
    """M (columns) · f = x for a 3x3."""
    a, b, d = M
    det = _dot(a, _cross(b, d))
    return (_dot(x, _cross(b, d)) / det, _dot(a, _cross(x, d)) / det,
            _dot(a, _cross(b, x)) / det)


def surface_cell(spec: SurfaceSpec):
    """The slab's frame and atoms: dict with U, V (in-plane vectors,
    rotated Å), depth (Å), d (interplanar spacing Å) and atoms
    [(element, (x, y, z) Å)] of ONE surface cell over the whole depth,
    top at z = 0."""
    c = spec.crystal
    hkl = tuple(spec.miller)
    u, v, w = in_plane_basis(c, hkl)
    cu, cv, cw = (_lat(c, n) for n in (u, v, w))
    ex = tuple(x / _norm(cu) for x in cu)
    nz = _cross(cu, cv)
    ez = tuple(x / _norm(nz) for x in nz)
    ey = _cross(ez, ex)

    def rot(p):
        return (_dot(p, ex), _dot(p, ey), _dot(p, ez))
    d = _dot(cw, ez)
    ru, rv, rw = rot(cu), rot(cv), rot(cw)
    sw, tw = _solve2(ru, rv, rw)
    eps = 1e-6

    def wrap(x):
        x %= 1.0
        return 0.0 if x > 1 - eps else x
    cell, seen = [], set()
    for el, *f in c.atoms:
        s, t, g = _solve((u, v, w), tuple(f))
        s, t, g = wrap(s), wrap(t), wrap(g)
        k = (el, round(s, 4) % 1, round(t, 4) % 1, round(g, 4) % 1)
        if k not in seen:                    # centring twins collapse
            seen.add(k)
            cell.append((el, s, t, g))
    term = spec.termination
    if term is None:
        term = widest_gap([g for *_x, g in cell])
    atoms = []
    for el, s, t, g in cell:
        gg = wrap(g - term)
        for layer in range(spec.layers):
            z = gg - layer                   # layers below the top one
            s2, t2 = wrap(s + (z - g) * sw), wrap(t + (z - g) * tw)
            atoms.append((el, (s2 * ru[0] + t2 * rv[0],
                               s2 * ru[1] + t2 * rv[1], z * d)))
    top = max(p[2] for _e, p in atoms)
    atoms = [(el, (p[0], p[1], p[2] - top)) for el, p in atoms]
    return {"U": ru, "V": rv, "d": d, "hkl": hkl, "termination": term,
            "depth": spec.layers * d, "atoms": atoms,
            "vectors": {n: [round(x, 4) for x in vec]
                        for n, vec in (("u", u), ("v", v), ("w", w))}}


def widest_gap(heights) -> float:
    """Where to cut a layer: the middle of the widest gap between its
    atomic planes (fractions of a layer), so the fewest bonds break —
    Si(111) ends on a whole bilayer, rutile (110) on its O-Ti-O row."""
    hs = sorted({round(h % 1.0, 4) % 1.0 for h in heights})
    if len(hs) < 2:
        return round((hs[0] + 0.5) % 1.0, 4) if hs else 0.0
    gaps = [((hs[(i + 1) % len(hs)] - hs[i]) % 1.0 or 1.0, hs[i])
            for i in range(len(hs))]
    gap, low = max(gaps, key=lambda x: (round(x[0], 4), -x[1]))
    return round((low + gap / 2) % 1.0, 4)


def _solve2(a, b, q):
    det = a[0] * b[1] - a[1] * b[0]
    return ((q[0] * b[1] - q[1] * b[0]) / det,
            (a[0] * q[1] - a[1] * q[0]) / det)


def label(c, hkl) -> str:
    h, k, l = hkl
    if c.system.lower().startswith(("hex", "trig")):
        idx = (h, k, -(h + k), l)
    else:
        idx = (h, k, l)
    txt = "".join(f"-{-n}" if n < 0 else str(n) for n in idx)
    return f"{c.name} ({txt})"


# ------------------------------------------------------------- program
def program(spec: SurfaceSpec):
    spec.check()
    cell = surface_cell(spec)
    nx, ny = (int(n) for n in spec.repeat)
    U, V, atoms = cell["U"], cell["V"], cell["atoms"]
    k = cb.NM * spec.scale
    per = cb.sphere_triangles(spec.fn)
    n_atoms = len(atoms) * nx * ny
    tris = n_atoms * per
    if tris > cb.BUDGET:
        raise cb.BuildError(
            f"{n_atoms} atoms ({tris} triangles) is more than the 3D view "
            f"draws ({cb.BUDGET}): fewer repeats or layers, or fewer "
            "segments.")
    name = cb._ident(spec.prefix or "surface")
    title = label(spec.crystal, cell["hkl"])
    lines, groups = [], {}
    for el, p in atoms:
        groups.setdefault(el, []).append(p)
    for el, pts in groups.items():
        r = cr.radius(el) * k * spec.atom_scale
        lines.append(f'color("{cr.colour(el)}") {{  // {el} atoms')
        for p in pts:
            lines.append(f"  translate({cb._vec(p, k)}) sphere(r = "
                         f"{cb._n(r)}, $fn = {spec.fn});  // {el}")
        lines.append("}")
    cell_mod = f"{name}_cell"
    code = [f"{name}_nx = {nx};", f"{name}_ny = {ny};",
            cb._module(cell_mod, lines)]
    body = [f"for (i = [0 : {name}_nx - 1], j = [0 : {name}_ny - 1])",
            f"  translate([{cb._lin([(U[0] * k, 'i'), (V[0] * k, 'j')])}, "
            f"{cb._lin([(U[1] * k, 'i'), (V[1] * k, 'j')])}, 0]) "
            f"{cell_mod}();"]
    if spec.cell_box:
        pts = [(0, 0), (nx, 0), (nx, ny), (0, ny)]
        poly = ", ".join(
            "[" + cb._n((a * U[0] + b * V[0]) * k) + ", "
            + cb._n((a * U[1] + b * V[1]) * k) + "]" for a, b in pts)
        depth = cell["depth"] * k
        body.append(f'color("{cb.BOX_COLOUR}", 0.15) translate([0, 0, '
                    f'{cb._n(-depth - 0.02 * k * 10)}]) linear_extrude('
                    f'height = {cb._n(0.02 * k * 10)}) polygon([{poly}]);'
                    "  // Slab base")
    part = cb._ident(title.replace("(", " ").replace(")", " ")) \
        .strip("_") or "Surface"
    code.append(cb._module(part, body))
    code.append(f"{part}();  // {title}")
    stats = {"surface": title, "miller": list(cell["hkl"]),
             "interplanar_spacing_nm": round(cell["d"] / 10, 5),
             "surface_cell_nm": [round(_norm(U) / 10, 5),
                                 round(_norm(V) / 10, 5)],
             "surface_angle_deg": round(math.degrees(math.acos(
                 max(-1, min(1, _dot(U, V) / (_norm(U) * _norm(V)))))), 2),
             "vectors_conventional": cell["vectors"],
             "termination": cell["termination"],
             "atoms_per_surface_cell": len(atoms), "atoms": n_atoms,
             "triangles": tris,
             "slab_nm": [round(nx * _norm(U) / 10, 3),
                         round(ny * _norm(V) / 10, 3),
                         round(cell["depth"] / 10, 4)],
             "notes": ["Bulk-terminated: no relaxation or reconstruction. "
                       "Change termination to pick the top plane."]}
    return "\n".join(code), stats


def apply(window, spec: SurfaceSpec) -> dict:
    """Build the slab into the window's document (nm rules as
    crystal_build.apply). One undo step."""
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
            notes.append(f"The document is in {model.unit}: the surface is "
                         "drawn at true size there — very small.")
    spec = replace(spec, prefix=spec.prefix or cb._free_prefix(
        model, spec.crystal.key + "_surf"))
    code, stats = program(spec)
    if model.global_fn_on and model.global_fn > spec.fn:
        model.set_global_fn(True, spec.fn)
    root, warnings = parse_scad(code)
    if not root.children:
        raise cb.BuildError("The surface program produced nothing: "
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
    stats["notes"] = notes + stats["notes"]
    if warnings:
        stats["warnings"] = warnings[:8]
    return stats


def spec_from_params(params: dict) -> SurfaceSpec:
    base = cb.spec_from_params({k: params[k] for k in ("crystal", "custom")
                                if k in params})
    rep = params.get("repeat", (6, 6))
    rep = (rep, rep) if isinstance(rep, (int, float)) else tuple(rep)
    try:
        spec = SurfaceSpec(
            crystal=base.crystal,
            miller=parse_miller(params.get("miller", "111")),
            repeat=tuple(int(n) for n in rep),
            layers=int(params.get("layers", 3)),
            termination=(None if params.get("termination") in (None, "auto")
                         else float(params["termination"])),
            atom_scale=float(params.get("atom_scale", 1.0)),
            fn=int(params.get("segments", 12)),
            cell_box=bool(params.get("cell_box", True)))
    except (TypeError, ValueError) as exc:
        raise cb.BuildError(f"Bad argument: {exc}")
    spec.check()
    return spec


def build_surface(window, params: dict) -> dict:
    """MCP build_surface: build, or with dry_run only describe."""
    spec = spec_from_params(params)
    if params.get("dry_run"):
        _code, stats = program(spec)
        stats["dry_run"] = True
        return stats
    return apply(window, spec)
