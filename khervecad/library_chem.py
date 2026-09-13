"""Chemistry & lab-glassware parts for the parts library.

Beakers, flasks, test tubes, graduated cylinders, funnels, a burette,
pipettes, a Petri dish, a watch glass, a separating funnel, a condenser
and the bench hardware around them (rack, stand, burner, hotplate...).

Glassware is modelled the way it is made:

- **One wall profile, revolved.** The outer outline is drawn, and the
  inner one is the same outline offset inwards along its normals, so
  the wall is evenly thick everywhere — round the heel of a beaker, over
  the shoulder of a flask. Revolving the closed wall profile makes the
  vessel genuinely hollow *without a boolean*, so the built-in preview
  shows it right even when OpenSCAD is not installed.
- **Real glass.** Every glass piece is a ``color`` node carrying the
  Glass material (translucent in the 3D view); ground-glass joints are
  frosted.
- **The details that make it read as labware:** a rolled rim bead, a
  Griffin pouring spout (a flared polyhedron lip), white enamel
  graduations placed where the volume really reaches (integrated from
  the vessel's own inner profile, so a conical flask's marks crowd
  towards the top), numbers and the nominal volume printed round the
  glass, the calibration ring of a volumetric flask, the Schellbach
  stripe of a burette, glass stopcocks with PTFE keys, stoppers.
- **An optional liquid** (``fill`` % of the nominal volume) with a
  meniscus, coloured from ``LIQUIDS`` — the Part Library's colour combo
  (``dims["_color"]``). A separating funnel holds two layers.

Registered into ``library.PARTS`` via ``PARTS`` here, each entry
carrying a ``build`` callable, so ``library.build_part`` dispatches to
it. Sizes pre-fill common volumes; any dimension can be edited first.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .model import CadNode

CATEGORY = "Chemistry"

#: material colours.
GLASS = "#cfe8ee"        # pale borosilicate
GLASS_ALPHA = 0.3
PRINT = "#f7f7f2"        # white enamel graduations
FROST = "#e9eef0"        # ground-glass joint
PTFE = "#f2f2ee"         # stopcock keys
METAL = "#9aa0a8"
METAL_DK = "#5f646c"
WOOD = "#c8a06a"
WHITE = "#eef1f3"
RUBBER = "#b3261e"       # dropper teat
PLASTIC = "#eef2f4"      # wash-bottle body (LDPE)
CERAMIC = "#d8cbb0"      # wire-gauze centre
DARK = "#2b2e33"         # hotplate top / screens
BRASS = "#c69a4c"        # burner / fittings
BLUE_CAP = "#2d6fd0"     # PE stoppers

#: liquid colour choices (Part Library colour combo) -> (colour, alpha)
LIQUIDS = {
    "Copper sulfate (blue)": ("#1f6fd0", 0.82),
    "Water (clear)": ("#a9d8ee", 0.4),
    "Permanganate (purple)": ("#6e1f86", 0.85),
    "Iron(III) (amber)": ("#d9811a", 0.8),
    "Nickel (green)": ("#2fa04e", 0.8),
    "Red dye": ("#c8231d", 0.8),
    "Empty": None,
}
LIQUID_NAMES = list(LIQUIDS)


# ----------------------------------------------------------- primitives

def _cyl(name, radius, height, z=0.0, x=0.0, y=0.0, r2=None,
         segments=96):
    return CadNode("cylinder", name, dict(
        x=x, y=y, z=z, height=height, radius_bottom=radius,
        radius_top=radius if r2 is None else r2,
        segments=segments, center=False))


def _col(node, color, name=None, alpha=1.0, material=None):
    """Wrap *node* in an OpenSCAD color() node. The glass tint always
    comes with the translucent Glass material."""
    if color == GLASS and material is None:
        material, alpha = "Glass", min(alpha, GLASS_ALPHA)
    params = dict(color=color, alpha=alpha)
    if material:
        params["material"] = material
    c = CadNode("color", name or "Colour", params)
    c.add(node)
    return c


def _revolve(name, profile, color=GLASS, segments=120, alpha=1.0,
             angle=360.0, material=None):
    """A colour-wrapped rotate_extrude of a (radius, height) profile."""
    rev = CadNode("rotate_extrude", name,
                  dict(angle=float(angle), segments=segments))
    rev.add(CadNode("polygon", f"{name} profile",
                    dict(x=0.0, y=0.0,
                         points=[[round(max(r, 0.0), 4), round(z, 4)]
                                 for r, z in profile])))
    return _col(rev, color, name=f"{name} glass" if color == GLASS else name,
                alpha=alpha, material=material)


def _arc(cx, cz, radius, a0, a1, n):
    """Points on a circle arc (degrees), inclusive."""
    return [(cx + radius * math.cos(math.radians(a)),
             cz + radius * math.sin(math.radians(a)))
            for a in [a0 + (a1 - a0) * i / n for i in range(n + 1)]]


def _bezier(p0, p1, p2, n):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1])
            for t in [i / n for i in range(n + 1)]]


def _dims(dims, sizes):
    """Size-table defaults overlaid with any edited field values."""
    entry = sizes.get(dims.get("_size", ""),
                      next(iter(sizes.values())))
    out = dict(entry)
    out.update({k: v for k, v in dims.items()
                if k != "_size" and v is not None})
    return out


def _translate(node, x=0.0, y=0.0, z=0.0, name="Place"):
    t = CadNode("translate", name, dict(x=x, y=y, z=z))
    t.add(node)
    return t


def _rotate(node, x=0.0, y=0.0, z=0.0, name="Turn"):
    r = CadNode("rotate", name, dict(x=x, y=y, z=z))
    r.add(node)
    return r


# ------------------------------------------------------ wall profiles

def _dedupe(points):
    out = []
    for p in points:
        if not out or math.dist(p, out[-1]) > 1e-6:
            out.append(p)
    return out


def _offset_in(outer, w):
    """The outline moved *w* into the cavity, point by point along the
    normal (the cavity is on the left of an outline climbing from the
    axis) — an evenly thick wall round every curve."""
    out = []
    n = len(outer)
    for i, (r, z) in enumerate(outer):
        a, b = outer[max(i - 1, 0)], outer[min(i + 1, n - 1)]
        tr, tz = b[0] - a[0], b[1] - a[1]
        length = math.hypot(tr, tz) or 1.0
        out.append((max(r - w * tz / length, 0.0), z + w * tr / length))
    return out


def _vessel(name, outer, w, bead=0.0, segments=120):
    """Revolved glass wall. *outer* climbs from the base (from the axis
    for a closed bottom) to the top of the wall; *bead* > 0 rolls a rim
    bead of that radius on top. Returns (glass node, inner outline)."""
    outer = _dedupe(outer)
    inner = _offset_in(outer, w)
    top_r, top_z = outer[-1]
    if bead > 0:
        lip = _arc(top_r, top_z + bead, bead, -90.0, 90.0, 10)[1:]
        tip = [(top_r - w, top_z + 2 * bead)]
    else:
        lip, tip = [], [(max(top_r - w, 0.0), top_z)]
    inner = [p for p in inner if p[1] <= tip[0][1]]
    profile = outer + lip + tip + inner[::-1]
    return _revolve(name, _dedupe(profile), segments=segments), inner


def _interp(points):
    """r(z) along an outline (points climbing in z)."""
    pts = sorted(points, key=lambda p: p[1])

    def r_at(z):
        if z <= pts[0][1]:
            return pts[0][0]
        for (r0, z0), (r1, z1) in zip(pts, pts[1:]):
            if z0 <= z <= z1:
                return r0 if z1 == z0 else r0 + (r1 - r0) * (z - z0) / (z1 - z0)
        return pts[-1][0]
    return r_at


def _z_for_volume(inner, step=0.1):
    """A function mL -> the height the liquid reaches, integrated from
    the vessel's own inner outline (pi r^2 dz)."""
    r_at = _interp(inner)
    z0 = min(p[1] for p in inner)
    z1 = max(p[1] for p in inner)
    table, vol, z = [(z0, 0.0)], 0.0, z0
    while z < z1:
        r = r_at(z + step / 2)
        vol += math.pi * r * r * step / 1000.0
        z += step
        table.append((z, vol))

    def z_for(ml):
        for (za, va), (zb, vb) in zip(table, table[1:]):
            if va <= ml <= vb:
                return za + (zb - za) * (ml - va) / (vb - va or 1.0)
        return table[-1][0]
    z_for.capacity = table[-1][1]
    return z_for


# ---------------------------------------------------- print and labels

def _ring(r_at, z, deg, center, height=0.5, t=0.3, color=PRINT,
          name="Graduation"):
    """A printed band on the outer surface: *deg* of arc round *center*
    (degrees; -90 faces the front, -Y), *height* tall at height *z*."""
    r0 = r_at(z)
    rev = CadNode("rotate_extrude", name,
                  dict(angle=float(deg), segments=max(4, int(deg / 3))))
    rev.add(CadNode("polygon", f"{name} section", dict(x=0.0, y=0.0, points=[
        [round(r0 - 0.05, 4), round(z - height / 2, 4)],
        [round(r0 + t, 4), round(z - height / 2, 4)],
        [round(r0 + t, 4), round(z + height / 2, 4)],
        [round(r0 - 0.05, 4), round(z + height / 2, 4)]])))
    return _col(_rotate(rev, z=center - deg / 2.0, name=f"{name} at"), color,
                name=name, material="Matte")


def _curved_text(text, r_at, z, start_deg, size, color=PRINT, depth=0.35,
                 name="Print", centred=False):
    """*text* printed round the glass one character at a time, each flat
    on its own tangent plane (so nothing floats off a curve), reading
    left to right seen from outside; tilted with a sloping wall."""
    group = CadNode("union", name)
    r = max(r_at(z), 1.0)
    step = size * 0.7 / r                          # radians per character
    first = math.radians(start_deg)
    if centred:
        first -= step * (len(text) - 1) / 2.0
    dz = 0.5
    slope = math.degrees(math.atan2(r_at(z + dz) - r_at(z - dz), 2 * dz))
    for i, ch in enumerate(text):
        if ch == " ":
            continue
        a = first + step * i
        glyph = CadNode("text", f"'{ch}'", dict(
            x=round(-size * 0.33, 3), y=round(-size * 0.45, 3),
            text=ch, size=size))
        ext = CadNode("linear_extrude", f"'{ch}' depth",
                      dict(height=depth))
        ext.add(glyph)
        placed = _translate(
            _rotate(_rotate(_rotate(ext, x=90.0, name="Stand up"),
                            x=round(slope, 3), name="Follow the wall"),
                    z=round(math.degrees(a) + 90.0, 3), name="Face out"),
            x=round((r - 0.15) * math.cos(a), 4),
            y=round((r - 0.15) * math.sin(a), 4), z=round(z, 4),
            name=f"'{ch}' on the glass")
        group.add(placed)
    return _col(group, color, name=name, material="Matte")


def _num(v):
    return f"{v:g}"


def _graduations(outer, z_for, marks, face=-90.0, size=3.0, unit="mL",
                 minor_mm=6.0, major_mm=11.0, name="Scale"):
    """White graduations: *marks* are (volume, kind) with kind 0 minor,
    1 medium, 2 major-and-numbered; each at the height that volume
    reaches."""
    r_at = _interp(outer)
    scale = CadNode("union", name)
    majors = [v for v, kind in marks if kind == 2]
    for v, kind in marks:
        z = z_for(v)
        r = r_at(z)
        arc = {0: minor_mm, 1: (minor_mm + major_mm) / 2}.get(kind, major_mm)
        deg = math.degrees(min(arc, r * 1.4) / r)
        scale.add(_ring(r_at, z, deg, face, name=f"{_num(v)} {unit} mark"))
        if kind == 2:
            label = _num(v) + (f" {unit}" if majors and v == majors[-1] else "")
            start = face + math.degrees((min(arc, r * 1.4) / 2 + 1.2 + size * 0.35) / r)
            scale.add(_curved_text(label, r_at, z, start, size,
                                   name=f"'{label}'"))
    return scale


def _liquid(inner, z_lo, z_hi, choice, name="Liquid", meniscus=0.8):
    """The liquid between *z_lo* and *z_hi* inside *inner*, with a
    meniscus climbing the glass; None for an empty vessel."""
    spec = LIQUIDS.get(choice) if choice else None
    if spec is None or z_hi <= z_lo + 0.2:
        return None
    color, alpha = spec
    r_at = _interp(inner)
    body = [(max(r - 0.12, 0.0), z) for r, z in sorted(inner, key=lambda p: p[1])
            if z_lo < z < z_hi - meniscus]
    rim = max(r_at(z_hi) - 0.12, 0.0)
    top = [(rim, z_hi), (rim * 0.85, z_hi - meniscus * 0.55),
           (rim * 0.5, z_hi - meniscus * 0.85), (0.0, z_hi - meniscus)]
    prof = _dedupe([(0.0, z_lo), (max(r_at(z_lo) - 0.12, 0.0), z_lo)]
                   + body + top)
    return _revolve(name, prof, color=color, alpha=alpha, material="Glass",
                    segments=96)


def _liquid_choice(dims):
    return dims.get("_color") or LIQUID_NAMES[0]


def _slab(outer_grid, inner_grid, name):
    """A closed polyhedron between two point grids (the glass lip of a
    spout): outer and inner faces plus the four edges."""
    ni, nk = len(outer_grid), len(outer_grid[0])
    pts = [p for row in outer_grid for p in row] + \
          [p for row in inner_grid for p in row]
    L = ni * nk
    I = lambda l, i, k: l * L + i * nk + k
    faces = []
    for i in range(ni - 1):
        for k in range(nk - 1):
            a, b, c, d = I(0, i, k), I(0, i, k + 1), I(0, i + 1, k + 1), I(0, i + 1, k)
            faces += [[a, b, c], [a, c, d]]
            a, b, c, d = I(1, i, k), I(1, i, k + 1), I(1, i + 1, k + 1), I(1, i + 1, k)
            faces += [[a, c, b], [a, d, c]]
    loop = ([(i, 0) for i in range(ni)] + [(ni - 1, k) for k in range(1, nk)]
            + [(i, nk - 1) for i in range(ni - 2, -1, -1)]
            + [(0, k) for k in range(nk - 2, 0, -1)])
    for (i1, k1), (i2, k2) in zip(loop, loop[1:] + loop[:1]):
        a, b = I(0, i1, k1), I(0, i2, k2)
        c, d = I(1, i2, k2), I(1, i1, k1)
        faces += [[a, b, c], [a, c, d]]
    vol = 0.0
    for a, b, c in faces:
        pa, pb, pc = pts[a], pts[b], pts[c]
        vol += (pa[0] * (pb[1] * pc[2] - pb[2] * pc[1])
                - pa[1] * (pb[0] * pc[2] - pb[2] * pc[0])
                + pa[2] * (pb[0] * pc[1] - pb[1] * pc[0]))
    if vol > 0:                     # OpenSCAD: clockwise seen from outside
        faces = [[a, c, b] for a, b, c in faces]
    return CadNode("polyhedron", name, dict(
        points=[[round(v, 4) for v in p] for p in pts], faces=faces))


def _spout(r, top, w, face=180.0, width=None, flare=None, drop=None,
           name="Pouring spout"):
    """A Griffin spout: the rim pulled out into a V lip at *face*."""
    width = width or r * 0.5
    flare = flare or max(2.5, r * 0.13)
    drop = drop or max(6.0, r * 0.3)
    half = min(0.45, width / 2.0 / r)
    phis = [-half + 2 * half * i / 14 for i in range(15)]
    ts = [k / 8 for k in range(9)]
    c = math.radians(face)
    outer, inner = [], []
    for phi in phis:
        f = flare * max(0.0, 1 - (phi / half) ** 2)
        ro, ri = [], []
        for t in ts:
            z = top - drop * (1 - t) - 0.1
            rad = r + f * t * t
            ang = c + phi
            ro.append((rad * math.cos(ang), rad * math.sin(ang), z))
            ri.append(((rad - w) * math.cos(ang), (rad - w) * math.sin(ang), z))
        outer.append(ro)
        inner.append(ri)
    return _col(_slab(outer, inner, name), GLASS, name=name)


def _frost(r, z0, z1, name="Ground-glass joint"):
    """The frosted sleeve of a ground-glass joint."""
    return _revolve(name, [(r - 0.05, z0), (r + 0.22, z0), (r + 0.22, z1),
                           (r - 0.05, z1)], color=FROST, alpha=0.85,
                    material="Matte", segments=72)


def _stopcock(z, r_tube, name="Stopcock"):
    """Glass barrel across the tube with a white PTFE key and handle."""
    part = CadNode("union", name)
    br, bl = r_tube * 1.1 + 1.5, r_tube * 3.6 + 8.0
    barrel = _rotate(_cyl("Barrel", br, bl, z=-bl / 2, segments=48), y=90.0,
                     name="Across the tube")
    part.add(_col(barrel, GLASS, name="Glass barrel"))
    key = _rotate(_cyl("PTFE key", br * 0.8, bl + 6.0, z=-bl / 2 - 3.0,
                       r2=br * 0.62, segments=40), y=90.0, name="Key axis")
    part.add(_col(key, PTFE, name="PTFE key", material="Plastic"))
    handle = CadNode("cube", "Handle", dict(
        x=bl / 2 + 2.0, y=-br * 1.9, z=-1.6, width=3.2, depth=br * 3.8,
        height=3.2, center=False))
    part.add(_col(handle, PTFE, name="Handle", material="Plastic"))
    nut = _rotate(_cyl("Retaining nut", br * 0.9, 4.0, z=-bl / 2 - 7.0,
                       segments=6), y=90.0, name="Nut axis")
    part.add(_col(nut, PTFE, name="Nut", material="Plastic"))
    return _translate(part, z=z, name=f"{name} height")


def _scale_steps(vol):
    """(minor, major) graduation steps for a nominal volume."""
    for step in (1, 2, 5, 10, 25, 50, 100, 200, 500):
        if vol / step <= 12:
            return step, step * 2
    return vol / 10, vol / 5


# --------------------------------------------------------------- vessels

def build_beaker(dims):
    p = _dims(dims, BEAKER_SIZES)
    r, h, w = p["d"] / 2.0, p["h"], p["wall"]
    rh, rb = max(2.5, r * 0.12), w * 0.85
    outer = [(0.0, 0.0)] + _arc(r - rh, rh, rh, -90.0, 0.0, 10) + \
        [(r, h - 2 * rb)]
    part = CadNode("union", "Beaker")
    glass, inner = _vessel("Beaker", outer, w, bead=rb)
    part.add(glass)
    part.add(_spout(r, h, w, face=180.0))
    vol = p["vol"]
    z_for = _z_for_volume(inner)
    step, major = _scale_steps(vol)
    marks = [(v, 2 if abs(v / major - round(v / major)) < 1e-9 else 0)
             for v in [step * i for i in range(1, int(vol / step) + 1)]
             if z_for(v) < h - 5]
    part.add(_graduations(outer, z_for, marks, size=max(2.6, r * 0.09)))
    r_at = _interp(outer)
    big = max(3.5, r * 0.15)
    part.add(_curved_text(f"{_num(vol)} mL", r_at, h * 0.42, -150.0, big,
                          name="Volume print", centred=True))
    part.add(_ring(r_at, h * 0.28, math.degrees(r * 0.45 / r), -25.0,
                   height=h * 0.14, name="Marking spot"))
    liquid = _liquid(inner, w, z_for(vol * p["fill"] / 100.0),
                     _liquid_choice(dims))
    if liquid is not None:
        part.add(liquid)
    return part


def build_graduated_cylinder(dims):
    p = _dims(dims, CYLINDER_SIZES)
    r, h, w = p["d"] / 2.0, p["h"], p["wall"]
    foot_r, foot_h = r * 2.1, 5.0
    rb = w * 0.8
    part = CadNode("union", "Graduated cylinder")
    part.add(_col(_cyl("Hexagonal foot", foot_r, foot_h, segments=6), GLASS,
                  name="Foot"))
    outer = [(0.0, foot_h), (r + 3.0, foot_h), (r + 0.4, foot_h + 5.0),
             (r, foot_h + 8.0), (r, h - 2 * rb)]
    glass, inner = _vessel("Graduated cylinder", outer, w, bead=rb)
    part.add(glass)
    part.add(_spout(r, h, w, face=180.0, width=r * 0.8, flare=max(2.0, r * 0.25),
                    drop=max(6.0, r * 0.6)))
    vol = p["vol"]
    z_for = _z_for_volume(inner)
    minor = vol / 50.0
    marks = []
    for i in range(5, 51):
        v = round(minor * i, 6)
        kind = 2 if i % 5 == 0 else (1 if i % 5 == 0 else 0)
        if z_for(v) < h - 8:
            marks.append((v, kind))
    part.add(_graduations(outer, z_for, marks, size=max(2.4, r * 0.3),
                          minor_mm=min(5.0, r * 0.7), major_mm=min(9.0, r * 1.2)))
    r_at = _interp(outer)
    small = max(2.2, r * 0.22)
    for i, line in enumerate((f"{_num(vol)} mL", "In 20 °C", f"± {_num(vol / 100)}")):
        part.add(_curved_text(line, r_at, h - 16 - i * small * 1.6, -150.0,
                              small, name=f"'{line}'", centred=True))
    liquid = _liquid(inner, foot_h + w, z_for(vol * p["fill"] / 100.0),
                     _liquid_choice(dims))
    if liquid is not None:
        part.add(liquid)
    return part


def build_test_tube(dims):
    p = _dims(dims, TUBE_SIZES)
    r, h, w = p["d"] / 2.0, p["h"], p["wall"]
    rb = w * 0.8
    outer = _arc(0.0, r, r, -90.0, 0.0, 16) + [(r, h - 2 * rb)]
    part = CadNode("union", "Test tube")
    glass, inner = _vessel("Test tube", outer, w, bead=rb, segments=64)
    part.add(glass)
    z_for = _z_for_volume(inner)
    level = z_for(z_for.capacity * p["fill"] / 100.0)
    liquid = _liquid(inner, w, level, _liquid_choice(dims), meniscus=0.6)
    if liquid is not None:
        part.add(liquid)
    return part


def _flask_outline(rb, rn, h, heel, neck_len, shape):
    """Outer outline of a flat-based flask body into its neck."""
    zn = h - neck_len
    if shape == "cone":
        start = _arc(rb - heel, heel, heel, -90.0, -20.0, 6)
        a = start[-1]
        k = 0.78
        cone_end = (a[0] + (rn - a[0]) * k, a[1] + (zn - a[1]) * k)
        shoulder = _bezier(cone_end, (rn, zn), (rn, zn + (zn - cone_end[1]) * 0.4), 10)
        return [(0.0, 0.0)] + start + [cone_end] + shoulder[1:] + [(rn, h)]
    raise ValueError(shape)                               # pragma: no cover


def build_erlenmeyer(dims):
    p = _dims(dims, FLASK_SIZES)
    rb, rn, h, w = p["d"] / 2.0, p["neck"] / 2.0, p["h"], p["wall"]
    bead = w * 0.9
    outer = _flask_outline(rb, rn, h - 2 * bead, max(3.0, rb * 0.1),
                           h * 0.2, "cone")
    part = CadNode("union", "Erlenmeyer flask")
    glass, inner = _vessel("Erlenmeyer flask", outer, w, bead=bead)
    part.add(glass)
    vol = p["vol"]
    z_for = _z_for_volume(inner)
    step, major = _scale_steps(vol)
    shoulder = h * 0.62
    marks = [(v, 2 if abs(v / major - round(v / major)) < 1e-9 else 0)
             for v in [step * i for i in range(1, int(vol / step) + 1)]
             if z_for(v) < shoulder]
    part.add(_graduations(outer, z_for, marks, size=max(2.6, rb * 0.08)))
    r_at = _interp(outer)
    part.add(_curved_text(f"{_num(vol)} mL", r_at, h * 0.14, -145.0,
                          max(3.2, rb * 0.12), name="Volume print",
                          centred=True))
    part.add(_ring(r_at, h * 0.3, 32.0, -20.0, height=h * 0.12,
                   name="Marking spot"))
    liquid = _liquid(inner, w, z_for(vol * p["fill"] / 100.0),
                     _liquid_choice(dims))
    if liquid is not None:
        part.add(liquid)
    return part


def build_round_flask(dims):
    p = _dims(dims, FLASK_SIZES)
    rb, rn, h, w = p["d"] / 2.0, p["neck"] / 2.0, p["h"], p["wall"]
    a_top = math.degrees(math.acos(min(rn / rb, 0.999)))
    body = _arc(0.0, rb, rb, -90.0, a_top, 36)
    joint = min(h * 0.14, 24.0)
    outer = body + [(rn, h)]
    part = CadNode("union", "Round-bottom flask")
    glass, inner = _vessel("Round-bottom flask", outer, w)
    part.add(glass)
    part.add(_frost(rn, h - joint, h))
    z_for = _z_for_volume(inner)
    liquid = _liquid(inner, min(z for _r, z in inner),
                     z_for(p["vol"] * p["fill"] / 100.0), _liquid_choice(dims))
    if liquid is not None:
        part.add(liquid)
    # a cork ring to stand it on
    part.add(_col(_revolve("Cork ring", _arc(rb * 0.42, -4.0, 4.0, 0.0, 360.0, 20),
                           color="#b8864b", segments=48),
                  "#b8864b", name="Cork ring stand"))
    return part


def build_funnel(dims):
    p = _dims(dims, FUNNEL_SIZES)
    rc, rs, w = p["d"] / 2.0, p["stem"] / 2.0, p["wall"]
    cone_h, stem_h = p["h"] * 0.55, p["h"] * 0.45
    bead = w * 0.8
    outer = [(rs, 0.0), (rs, stem_h - 4.0)] + \
        _bezier((rs, stem_h - 4.0), (rs, stem_h + 2.0), (rs + 5.0, stem_h + 4.0), 6)[1:] + \
        [(rc, stem_h + cone_h - 2 * bead)]
    glass, _inner = _vessel("Funnel", outer, w, bead=bead, segments=96)
    return glass


def build_burette(dims):
    p = _dims(dims, BURETTE_SIZES)
    r, h, w = p["d"] / 2.0, p["h"], p["wall"]
    tip_h, rb = 16.0, w * 0.8
    rt = r * 0.42
    outer = [(0.9, 0.0), (rt * 0.7, tip_h * 0.6), (rt, tip_h),
             (rt, tip_h + 26.0), (r, tip_h + 38.0), (r, h - 2 * rb)]
    part = CadNode("union", "Burette")
    glass, inner = _vessel("Burette", outer, w, bead=rb, segments=64)
    part.add(glass)
    part.add(_stopcock(tip_h + 13.0, rt))
    vol = p["vol"]
    r_in = r - w
    per_ml = 1000.0 / (math.pi * r_in * r_in)
    zero = h - 30.0
    marks, v = [], 0
    while v <= vol and zero - v * per_ml > tip_h + 50.0:
        marks.append((v, 2 if v % 5 == 0 else 0))
        v += 1
    part.add(_graduations(outer, lambda ml: zero - ml * per_ml, marks,
                          size=max(2.2, r * 0.3), minor_mm=min(4.0, r * 0.6),
                          major_mm=min(7.0, r)))
    r_at = _interp(outer)
    low = zero - vol * per_ml - 4.0
    stripe = CadNode("union", "Schellbach stripe")
    stripe.add(_revolve("White band", [(r - 0.02, low), (r + 0.2, low),
                                       (r + 0.2, zero + 6.0), (r - 0.02, zero + 6.0)],
                        color=PRINT, material="Matte", angle=70.0, segments=24))
    stripe.add(_revolve("Blue line", [(r + 0.15, low), (r + 0.35, low),
                                      (r + 0.35, zero + 6.0), (r + 0.15, zero + 6.0)],
                        color="#1f56c4", material="Matte", angle=8.0, segments=4))
    part.add(_rotate(stripe, z=55.0, name="On the back"))
    part.add(_curved_text(f"{_num(vol)} mL", r_at, zero + 14.0, -90.0,
                          max(2.4, r * 0.32), name="Volume print",
                          centred=True))
    level = zero - vol * (1 - p["fill"] / 100.0) * per_ml
    liquid = _liquid(inner, min(z for _r, z in inner), level,
                     _liquid_choice(dims), meniscus=0.8)
    if liquid is not None:
        part.add(liquid)
    return part


def build_petri_dish(dims):
    p = _dims(dims, PETRI_SIZES)
    r, h, w = p["d"] / 2.0, p["h"], 1.2
    part = CadNode("union", "Petri dish")
    base_outer = [(0.0, 0.0)] + _arc(r - 1.5, 1.5, 1.5, -90.0, 0.0, 6) + [(r, h)]
    base, inner = _vessel("Dish", base_outer, w, segments=120)
    part.add(base)
    lr = r + 1.6
    lid_outer = [(0.0, 0.0)] + _arc(lr - 1.5, 1.5, 1.5, -90.0, 0.0, 6) + [(lr, h * 0.78)]
    lid, _ = _vessel("Lid", lid_outer, w, segments=120)
    part.add(_translate(_rotate(lid, x=180.0, name="Lid upside down"),
                        z=h + h * 0.78 + 0.6, name="Lid on top"))
    agar = _liquid(inner, w, w + (h - w) * p["fill"] / 100.0,
                   dims.get("_color") or "Iron(III) (amber)", name="Agar",
                   meniscus=0.3)
    if agar is not None:
        part.add(agar)
    return part


def build_watch_glass(dims):
    p = _dims(dims, PETRI_SIZES)
    r = p["d"] / 2.0
    sr = r * 2.5
    cz = sr
    rim_a = math.degrees(math.asin(min(r / sr, 0.999)))
    # the underside of a shallow spherical cap, from its lowest point out
    outer = [(sr * math.sin(math.radians(a)), cz - sr * math.cos(math.radians(a)))
             for a in [rim_a * i / 28 for i in range(29)]]
    glass, _ = _vessel("Watch glass", outer, 1.4, segments=96)
    return glass


# ----------------------------------------------------------- lab hardware

def build_test_tube_rack(dims):
    p = _dims(dims, RACK_SIZES)
    n = max(int(p["holes"]), 1)
    hole_d = p["hole_d"]
    pitch = hole_d + 8.0
    length = pitch * n + 8.0
    width = hole_d + 16.0
    part = CadNode("difference", "Test-tube rack")
    body = CadNode("union", "Rack body")
    part.add(body)
    # top plate with holes + base plate + end posts
    body.add(CadNode("cube", "Top plate", dict(
        x=-length / 2.0, y=-width / 2.0, z=55.0, width=length,
        depth=width, height=8.0, center=False)))
    body.add(CadNode("cube", "Base plate", dict(
        x=-length / 2.0, y=-width / 2.0, z=0.0, width=length,
        depth=width, height=8.0, center=False)))
    for sx in (-1.0, 1.0):
        body.add(CadNode("cube", "End post", dict(
            x=sx * (length / 2.0 - 8.0), y=-width / 2.0, z=0.0,
            width=8.0, depth=width, height=63.0, center=False)))
    holes = CadNode("for_loop", "Tube holes", dict(
        variable="i", start=0.0, end=float(n - 1), step=1.0))
    holes.add(_cyl("Hole", hole_d / 2.0, 12.0,
                   x=f"{pitch} * (i - {(n - 1) / 2.0})",
                   z=53.0, segments=32))
    part.add(holes)
    return _col(part, WOOD, name="Rack")


def build_retort_stand(dims):
    p = _dims(dims, STAND_SIZES)
    base_l, base_w, base_t = p["base"], p["base"] * 0.62, 12.0
    rod_h, rod_d = p["h"], 12.0
    part = CadNode("union", "Retort stand")
    part.add(_col(CadNode("cube", "Base", dict(
        x=-base_l * 0.3, y=-base_w / 2.0, z=0.0, width=base_l,
        depth=base_w, height=base_t, center=False)), METAL_DK,
        name="Base"))
    part.add(_col(_cyl("Rod", rod_d / 2.0, rod_h,
                       x=-base_l * 0.3 + rod_d, z=base_t), METAL,
                  name="Rod"))
    # a boss head + clamp arm near the top
    boss = CadNode("union", "Clamp")
    boss.add(_cyl("Boss", rod_d, rod_d * 1.6,
                  x=-base_l * 0.3 + rod_d, z=rod_h * 0.75,
                  segments=32))
    arm = CadNode("rotate", "Arm", dict(x=0.0, y=90.0, z=0.0))
    arm.add(_cyl("Arm rod", rod_d * 0.4, base_l * 0.55,
                 x=0.0, z=-base_l * 0.5, segments=24))
    lift = CadNode("translate", "Arm at boss",
                   dict(x=-base_l * 0.3 + rod_d, y=0.0,
                        z=rod_h * 0.75 + rod_d * 0.8))
    lift.add(arm)
    boss.add(lift)
    part.add(_col(boss, METAL, name="Clamp"))
    return part


# ------------------------------------------------ more glass + equipment

def _arm(name, radius, length, at_z, angle=45.0, color=GLASS, ribs=0):
    """A tube leaving the axis at *angle* (deg from vertical), based at
    height *at_z* — condenser side arms, wash-bottle nozzles, etc.
    *ribs* adds hose-barb rings at the far end."""
    base = CadNode("translate", f"{name} base", dict(x=0.0, y=0.0,
                                                     z=at_z))
    rot = CadNode("rotate", f"{name} angle", dict(x=0.0, y=angle,
                                                  z=0.0))
    tube = CadNode("union", f"{name} tube")
    tube.add(_cyl(name, radius, length, segments=24))
    for k in range(ribs):
        z = length - 2.5 - k * 3.2
        tube.add(_cyl(f"{name} barb {k + 1}", radius * 1.25, 1.6, z=z,
                      r2=radius, segments=24))
    rot.add(tube)
    base.add(rot)
    return _col(base, color, name)


def build_volumetric_flask(dims):
    p = _dims(dims, VOLU_SIZES)
    rb, rn, h, w = p["d"] / 2.0, p["neck"] / 2.0, p["h"], p["wall"]
    vol = p["vol"]
    flat = rb * 0.55
    joint = min(18.0, h * 0.09)
    t0 = -math.degrees(math.acos(flat / rb))

    def outline(ez):
        body = [(rb * math.cos(math.radians(a)),
                 ez + ez * math.sin(math.radians(a)))
                for a in [t0 + (70.0 - t0) * i / 30 for i in range(31)]]
        z_base = body[0][1]
        body = [(r, z - z_base) for r, z in body]
        top = body[-1]
        neck_start = (rn, top[1] + (top[0] - rn) * 0.9)
        shoulder = _bezier(top, (rn + (top[0] - rn) * 0.25,
                                 neck_start[1] - 2.0), neck_start, 8)
        return [(0.0, 0.0)] + body + shoulder[1:] + [(rn, h)], neck_start[1]

    # size the pear body so the nominal volume reaches partway up the
    # neck — the calibration ring sits in the neck, as on a real flask
    lo, hi = 5.0, h * 0.45
    for _ in range(40):
        ez = (lo + hi) / 2
        outer, neck_z = outline(ez)
        inner = _offset_in(_dedupe(outer), w)
        z_for = _z_for_volume([pt for pt in inner if pt[1] <= h])
        target = neck_z + 0.4 * (h - joint - neck_z)
        if z_for.capacity < vol or z_for(vol) > target:
            lo = ez                                  # body too small
        else:
            hi = ez
    outer, _neck_z = outline(hi)
    ez = hi
    z_base = 0.0
    part = CadNode("union", "Volumetric flask")
    glass, inner = _vessel("Volumetric flask", outer, w)
    part.add(glass)
    part.add(_frost(rn, h - joint, h))
    z_for = _z_for_volume(inner)
    mark = z_for(vol)
    r_at = _interp(outer)
    part.add(_ring(r_at, mark, 359.9, -90.0, height=0.5, name="Calibration ring"))
    for i, line in enumerate((f"{_num(vol)} mL", "20 °C", "Class A")):
        part.add(_curved_text(line, r_at, ez * 0.9 - i * 5.5 - z_base * 0.0, -90.0,
                              max(3.0, rb * 0.1) if i == 0 else max(2.4, rb * 0.07),
                              name=f"'{line}'", centred=True))
    stopper = [(0.0, h - joint + 2.0), (rn - w - 0.3, h - joint + 2.0),
               (rn - w + 0.2, h), (rn + 3.0, h), (rn + 3.0, h + 2.0),
               (rn + 1.5, h + 3.0), (rn + 1.5, h + 12.0), (0.0, h + 12.0)]
    part.add(_revolve("Stopper", stopper, color=BLUE_CAP, material="Plastic",
                      segments=8))
    liquid = _liquid(inner, w, z_for(vol * min(p["fill"], 100.0) / 100.0),
                     _liquid_choice(dims))
    if liquid is not None:
        part.add(liquid)
    return part


def build_separating_funnel(dims):
    p = _dims(dims, SEP_SIZES)
    r, h, w = p["d"] / 2.0, p["h"], 1.6
    stem_h = h * 0.16
    rs = max(r * 0.14, 2.6)
    rn = max(r * 0.28, 8.0)
    joint = min(18.0, h * 0.07)
    shoulder = h * 0.56
    top_body = _bezier((r, shoulder), (r * 0.95, h * 0.84), (rn, h * 0.88), 12)
    outer = [(rs, 0.0), (rs, stem_h - 6.0)] + \
        _bezier((rs, stem_h - 6.0), (rs, stem_h), (rs * 2.2, stem_h + 8.0), 6)[1:] + \
        [(r, shoulder)] + top_body[1:] + [(rn, h)]
    part = CadNode("union", "Separating funnel")
    glass, inner = _vessel("Funnel body", outer, w, segments=96)
    part.add(glass)
    part.add(_frost(rn, h - joint, h))
    part.add(_stopcock(stem_h - 13.0, rs))
    stopper = [(0.0, h - joint + 1.0), (rn - w - 0.2, h - joint + 1.0),
               (rn - w + 0.3, h), (rn + 1.0, h), (rn + 1.0, h + 3.0),
               (rn * 0.5, h + 5.0), (rn * 0.5, h + 7.0), (rn * 1.3, h + 9.0),
               (rn * 1.3, h + 14.0), (0.0, h + 14.0)]
    part.add(_revolve("Glass stopper", stopper, segments=8))
    z_for = _z_for_volume([pt for pt in inner if pt[1] > stem_h])
    full = z_for(p["vol"] * p["fill"] / 100.0)
    interface = z_for(p["vol"] * p["fill"] / 100.0 * 0.55)
    lower = _liquid(inner, stem_h - 2.0, interface, _liquid_choice(dims),
                    name="Aqueous layer", meniscus=0.01)
    upper = _liquid(inner, interface, full, "Iron(III) (amber)",
                    name="Organic layer")
    for layer in (lower, upper):
        if layer is not None and _liquid_choice(dims) != "Empty":
            part.add(layer)
    return part


def build_condenser(dims):
    p = _dims(dims, CONDENSER_SIZES)
    L, rj, ri, w = p["length"], p["jacket_d"] / 2.0, \
        p["inner_d"] / 2.0, 1.4
    js, je = L * 0.12, L * 0.88
    part = CadNode("union", "Liebig condenser")
    # the water jacket, sealed onto the inner tube at both ends
    jacket = [(ri, js - 6.0)] + \
        _bezier((ri, js - 6.0), (rj, js - 6.0), (rj, js + 4.0), 6)[1:] + \
        [(rj, je - 4.0)] + _bezier((rj, je - 4.0), (rj, je + 6.0), (ri, je + 6.0), 6)[1:]
    part.add(_vessel("Jacket", jacket, w, segments=64)[0])
    part.add(_vessel("Inner tube", [(ri, 0.0), (ri, L)], w, segments=48)[0])
    part.add(_frost(ri, 0.0, 16.0, name="Bottom joint"))
    part.add(_frost(ri, L - 16.0, L, name="Top joint"))
    # two ribbed water side-arms (hose barbs) near the ends
    part.add(_arm("Water out", ri * 0.55, rj * 1.8, je - 6.0, 60.0, ribs=3))
    part.add(_arm("Water in", ri * 0.55, rj * 1.8, js + 6.0, 120.0, ribs=3))
    return part


def build_pipette(dims):
    p = _dims(dims, PIPETTE_SIZES)
    L, rb, rt, w = p["length"], p["bulb_d"] / 2.0, p["tip_d"] / 2.0, 0.8
    lower, bc = L * 0.32, L * 0.5
    hb = rb * 1.6
    bulb = [(rt + (rb - rt) * math.sin(math.radians(a)), bc - hb * math.cos(math.radians(a)))
            for a in [180 * i / 20 for i in range(21)]]
    outer = [(0.7, 0.0), (rt, L * 0.05), (rt, bc - hb)] + bulb[1:-1] + \
        [(rt, bc + hb), (rt, L)]
    part = CadNode("union", "Volumetric pipette")
    glass, _inner = _vessel("Volumetric pipette", outer, w, segments=48)
    part.add(glass)
    r_at = _interp(outer)
    part.add(_ring(r_at, L * 0.8, 359.9, -90.0, height=0.5, name="Calibration ring"))
    part.add(_ring(r_at, L * 0.93, 359.9, -90.0, height=4.0, t=0.25,
                   color=p["band"], name="Colour-code band"))
    part.add(_curved_text(f"{_num(p['vol'])} mL", r_at, bc, -90.0,
                          max(3.0, rb * 0.3), name="Volume print",
                          centred=True))
    return part


def build_dropper(dims):
    p = _dims(dims, DROPPER_SIZES)
    L, rt = p["length"], p["tube_d"] / 2.0
    part = CadNode("union", "Dropper")
    outer = [(0.6, 0.0), (rt * 0.45, L * 0.12), (rt, L * 0.2), (rt, L * 0.74)]
    part.add(_vessel("Glass tube", outer, 0.6, segments=32)[0])
    # rubber teat: a sleeve over the tube and a round bulb
    bz, br = L * 0.74 + L * 0.13, rt * 2.2
    teat = [(0.0, L * 0.64), (rt + 0.8, L * 0.64), (rt + 1.2, L * 0.66),
            (rt + 1.2, L * 0.72)] + \
        _arc(0.0, bz, br, -60.0, 90.0, 18)
    part.add(_revolve("Rubber teat", _dedupe(teat), color=RUBBER,
                      material="Rubber", segments=48))
    return part


def build_bunsen_burner(dims):
    p = _dims(dims, BURNER_SIZES)
    base_r, h, br = p["base"] / 2.0, p["h"], p["barrel"] / 2.0
    part = CadNode("union", "Bunsen burner")
    part.add(_col(_cyl("Base", base_r, 12.0, r2=base_r * 0.6,
                       segments=48), METAL_DK, "Base"))
    part.add(_col(_cyl("Barrel", br, h - 12.0, z=12.0, segments=32),
                  METAL, "Barrel"))
    # gas inlet spigot at the base + needle valve
    part.add(_arm("Gas inlet", br * 0.5, base_r * 1.4, 16.0, 90.0,
                  BRASS, ribs=3))
    part.add(_col(_cyl("Collar", br * 1.25, 14.0, z=20.0, segments=32),
                  METAL_DK, "Air collar"))
    return part


def build_hotplate(dims):
    p = _dims(dims, HOTPLATE_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    plate_r = p["plate"] / 2.0
    part = CadNode("union", "Hotplate stirrer")
    part.add(_col(CadNode("cube", "Body", dict(
        x=-w / 2.0, y=-d / 2.0, z=0.0, width=w, depth=d, height=h,
        center=False)), METAL, "Body"))
    part.add(_col(_cyl("Top plate", plate_r, 6.0, y=-d * 0.15, z=h,
                       segments=48), DARK, "Top plate"))
    # two control knobs on the front face
    for sx in (-1.0, 1.0):
        knob = CadNode("rotate", "Knob axis", dict(x=-90.0, y=0.0,
                                                   z=0.0))
        knob.add(_cyl("Knob", 12.0, 10.0, segments=24))
        lift = CadNode("translate", "Knob pos",
                       dict(x=sx * w * 0.25, y=-d / 2.0, z=h * 0.35))
        lift.add(knob)
        part.add(_col(lift, DARK, "Knob"))
    return part


def build_tripod(dims):
    p = _dims(dims, TRIPOD_SIZES)
    r, h = p["ring_d"] / 2.0, p["h"]
    part = CadNode("union", "Tripod")
    # top ring (thin annular disc)
    part.add(_revolve("Ring", [(r - 4.0, h), (r + 4.0, h),
                               (r + 4.0, h + 6.0), (r - 4.0, h + 6.0)],
                      color=METAL, segments=48))
    legs = CadNode("for_loop", "Legs", dict(variable="a", start=0.0,
                   end=240.0, step=120.0))
    rot = CadNode("rotate", "Leg angle", dict(x=0.0, y=0.0, z="a"))
    leg = CadNode("rotate", "Splay", dict(x=0.0, y=12.0, z=0.0))
    leg.add(_cyl("Leg", 5.0, h + 4.0, x=r * 0.9, segments=16))
    rot.add(leg)
    legs.add(rot)
    part.add(_col(legs, METAL, "Legs"))
    return part


def build_wire_gauze(dims):
    p = _dims(dims, GAUZE_SIZES)
    s = p["side"]
    part = CadNode("union", "Wire gauze")
    part.add(_col(CadNode("cube", "Mesh", dict(
        x=-s / 2.0, y=-s / 2.0, z=0.0, width=s, depth=s, height=1.2,
        center=False)), METAL, "Mesh"))
    part.add(_col(_cyl("Ceramic centre", s * 0.32, 1.6, z=0.6,
                       segments=48), CERAMIC, "Ceramic"))
    return part


def build_gas_cylinder(dims):
    p = _dims(dims, GAS_SIZES)
    r, h = p["d"] / 2.0, p["h"]
    color = GAS_COLORS.get(dims.get("_size", ""), "#3b7a4b")
    part = CadNode("union", "Gas cylinder")
    # body + rounded shoulder (revolved) so no boolean, colour-coded
    shoulder = r * 0.9
    prof = [(0.0, 0.0), (r, 0.0), (r, h),
            (r * 0.55, h + shoulder), (r * 0.28, h + shoulder)]
    part.add(_revolve("Bottle", prof, color=color, segments=64))
    # neck + valve + guard
    part.add(_col(_cyl("Neck", r * 0.28, 30.0, z=h + shoulder,
                       segments=24), METAL_DK, "Neck"))
    part.add(_col(_cyl("Valve", r * 0.16, 26.0, z=h + shoulder + 30.0,
                       segments=16), BRASS, "Valve"))
    part.add(_arm("Outlet", r * 0.08, r * 0.6, h + shoulder + 40.0,
                  90.0, BRASS))
    return part


def build_balance(dims):
    p = _dims(dims, BALANCE_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    part = CadNode("union", "Analytical balance")
    # base with a sloped display block
    part.add(_col(CadNode("cube", "Base", dict(
        x=-w / 2.0, y=-d / 2.0, z=0.0, width=w, depth=d,
        height=h * 0.34, center=False)), METAL, "Base"))
    part.add(_col(CadNode("cube", "Display", dict(
        x=-w * 0.34, y=-d / 2.0 - 6.0, z=8.0, width=w * 0.68,
        depth=8.0, height=h * 0.16, center=False)), DARK, "Display"))
    # glass draught shield + weighing pan inside
    part.add(_col(CadNode("cube", "Draught shield", dict(
        x=-w / 2.0, y=-d * 0.18, z=h * 0.34, width=w,
        depth=d * 0.8, height=h * 0.66, center=False)), GLASS,
        "Shield"))
    part.add(_col(_cyl("Pan", w * 0.22, 4.0, y=d * 0.1,
                       z=h * 0.34 + 4.0, segments=48), METAL,
                  "Pan"))
    return part


def build_wash_bottle(dims):
    p = _dims(dims, WASH_SIZES)
    r, h, w = p["d"] / 2.0, p["h"], 1.6
    part = CadNode("union", "Wash bottle")
    outer = [(0.0, 0.0)] + _arc(r - 5.0, 5.0, 5.0, -90.0, 0.0, 6) + \
        [(r, h * 0.7)] + _bezier((r, h * 0.7), (r, h * 0.84), (r * 0.5, h * 0.88), 8)[1:] + \
        [(r * 0.5, h)]
    part.add(_col(_vessel("Bottle", outer, w, segments=64)[0].children[0],
                  PLASTIC, name="LDPE bottle", alpha=0.78, material="Plastic"))
    part.add(_col(_cyl("Cap", r * 0.62, 14.0, z=h, segments=32),
                  BLUE_CAP, "Cap", material="Plastic"))
    # the bent delivery tube, swept along its path
    nozzle = CadNode("sweep", "Delivery tube", dict(
        path=[[0.0, 0.0, h + 12.0], [0.0, 0.0, h + 40.0],
              [r * 0.4, 0.0, h + 58.0], [r * 1.4, 0.0, h + 60.0]],
        smooth=3, wall=0.8))
    nozzle.add(CadNode("circle", "Tube section", dict(radius=r * 0.1,
                                                     segments=16)))
    part.add(_col(nozzle, PLASTIC, name="Nozzle", material="Plastic"))
    r_at = _interp(outer)
    part.add(_curved_text("H2O", r_at, h * 0.45, -90.0, r * 0.35,
                          color="#1f56c4", name="Label", centred=True))
    return part


# --------------------------------------------------------------- registry

BEAKER_SIZES = {
    "50 mL": dict(d=42.0, h=60.0, wall=1.2, vol=50.0, fill=60.0),
    "100 mL": dict(d=50.0, h=70.0, wall=1.3, vol=100.0, fill=60.0),
    "250 mL": dict(d=70.0, h=95.0, wall=1.5, vol=250.0, fill=60.0),
    "500 mL": dict(d=85.0, h=120.0, wall=1.6, vol=500.0, fill=60.0),
    "1 L": dict(d=105.0, h=145.0, wall=1.8, vol=1000.0, fill=60.0),
}
CYLINDER_SIZES = {
    "10 mL": dict(d=15.0, h=140.0, wall=1.2, vol=10.0, fill=70.0),
    "50 mL": dict(d=24.0, h=195.0, wall=1.3, vol=50.0, fill=70.0),
    "100 mL": dict(d=30.0, h=250.0, wall=1.5, vol=100.0, fill=70.0),
    "250 mL": dict(d=40.0, h=320.0, wall=1.6, vol=250.0, fill=70.0),
}
TUBE_SIZES = {
    "12 × 75 mm": dict(d=12.0, h=75.0, wall=0.9, fill=40.0),
    "16 × 100 mm": dict(d=16.0, h=100.0, wall=1.0, fill=40.0),
    "18 × 150 mm": dict(d=18.0, h=150.0, wall=1.1, fill=40.0),
}
FLASK_SIZES = {
    "100 mL": dict(d=64.0, neck=22.0, h=105.0, wall=1.4, vol=100.0, fill=60.0),
    "250 mL": dict(d=85.0, neck=28.0, h=145.0, wall=1.6, vol=250.0, fill=60.0),
    "500 mL": dict(d=105.0, neck=34.0, h=180.0, wall=1.8, vol=500.0, fill=60.0),
}
FUNNEL_SIZES = {
    "Small (50 mm)": dict(d=50.0, stem=8.0, h=90.0, wall=1.2),
    "Medium (75 mm)": dict(d=75.0, stem=10.0, h=130.0, wall=1.4),
    "Large (100 mm)": dict(d=100.0, stem=12.0, h=170.0, wall=1.5),
}
BURETTE_SIZES = {
    "25 mL": dict(d=13.0, h=350.0, wall=1.1, vol=25.0, fill=80.0),
    "50 mL": dict(d=15.0, h=520.0, wall=1.2, vol=50.0, fill=80.0),
}
PETRI_SIZES = {
    "60 mm": dict(d=60.0, h=15.0, fill=45.0),
    "90 mm": dict(d=90.0, h=16.0, fill=45.0),
    "100 mm": dict(d=100.0, h=18.0, fill=45.0),
}
RACK_SIZES = {
    "6 × 16 mm": dict(holes=6.0, hole_d=17.0),
    "12 × 16 mm": dict(holes=12.0, hole_d=17.0),
    "6 × 20 mm": dict(holes=6.0, hole_d=21.0),
}
STAND_SIZES = {
    "Standard": dict(base=160.0, h=450.0),
    "Tall": dict(base=200.0, h=750.0),
}
VOLU_SIZES = {
    "100 mL": dict(d=62.0, neck=15.0, h=170.0, wall=1.3, vol=100.0, fill=100.0),
    "250 mL": dict(d=80.0, neck=17.0, h=220.0, wall=1.4, vol=250.0, fill=100.0),
    "500 mL": dict(d=100.0, neck=19.0, h=270.0, wall=1.5, vol=500.0, fill=100.0),
}
SEP_SIZES = {
    "100 mL": dict(d=58.0, h=200.0, vol=100.0, fill=70.0),
    "250 mL": dict(d=78.0, h=260.0, vol=250.0, fill=70.0),
    "500 mL": dict(d=95.0, h=320.0, vol=500.0, fill=70.0),
}
CONDENSER_SIZES = {
    "Liebig 200 mm": dict(length=280.0, jacket_d=30.0, inner_d=12.0),
    "Liebig 300 mm": dict(length=400.0, jacket_d=32.0, inner_d=13.0),
}
#: colour-code bands follow the usual pipette convention
PIPETTE_SIZES = {
    "10 mL": dict(length=330.0, bulb_d=18.0, tip_d=4.0, vol=10.0,
                  band="#d0302a"),
    "25 mL": dict(length=400.0, bulb_d=24.0, tip_d=5.0, vol=25.0,
                  band="#1f56c4"),
}
DROPPER_SIZES = {
    "Pasteur 150 mm": dict(length=150.0, tube_d=6.0),
    "Pasteur 230 mm": dict(length=230.0, tube_d=7.0),
}
BURNER_SIZES = {
    "Standard": dict(base=65.0, h=130.0, barrel=13.0),
}
HOTPLATE_SIZES = {
    "Standard": dict(w=220.0, d=260.0, h=110.0, plate=150.0),
    "Large": dict(w=300.0, d=340.0, h=130.0, plate=200.0),
}
TRIPOD_SIZES = {
    "Standard": dict(ring_d=110.0, h=200.0),
    "Tall": dict(ring_d=130.0, h=300.0),
}
GAUZE_SIZES = {
    "125 mm": dict(side=125.0),
    "150 mm": dict(side=150.0),
}
#: gas cylinders are colour-coded like the carpet squares.
GAS_COLORS = {
    "Nitrogen (black)": "#2b2e33", "Oxygen (white)": "#e6ebee",
    "Argon (green)": "#3b9a5a", "Helium (brown)": "#7a5230",
    "CO₂ (grey)": "#8a9099", "Hydrogen (red)": "#c0392b",
}
GAS_SIZES = {name: dict(d=230.0, h=1200.0, color=hexcol)
             for name, hexcol in GAS_COLORS.items()}
BALANCE_SIZES = {
    "Analytical": dict(w=230.0, d=340.0, h=340.0),
}
WASH_SIZES = {
    "250 mL": dict(d=64.0, h=150.0),
    "500 mL": dict(d=78.0, h=185.0),
}

_D = [("d", "Diameter")]
_FILL = [("fill", "Liquid %")]
PARTS = {
    "chem_beaker": dict(label="Beaker (Griffin)", category=CATEGORY,
                        sizes=BEAKER_SIZES, build=build_beaker,
                        colors=LIQUID_NAMES,
                        fields=_D + [("h", "Height"), ("wall", "Wall")]
                        + _FILL),
    "chem_cylinder": dict(label="Graduated cylinder", category=CATEGORY,
                          sizes=CYLINDER_SIZES,
                          build=build_graduated_cylinder,
                          colors=LIQUID_NAMES,
                          fields=_D + [("h", "Height"),
                                       ("wall", "Wall")] + _FILL),
    "chem_test_tube": dict(label="Test tube", category=CATEGORY,
                           sizes=TUBE_SIZES, build=build_test_tube,
                           colors=LIQUID_NAMES,
                           fields=_D + [("h", "Length"),
                                        ("wall", "Wall")] + _FILL),
    "chem_erlenmeyer": dict(label="Erlenmeyer (conical) flask",
                            category=CATEGORY, sizes=FLASK_SIZES,
                            build=build_erlenmeyer, colors=LIQUID_NAMES,
                            fields=_D + [("neck", "Neck Ø"),
                                         ("h", "Height"),
                                         ("wall", "Wall")] + _FILL),
    "chem_round_flask": dict(label="Round-bottom flask",
                             category=CATEGORY, sizes=FLASK_SIZES,
                             build=build_round_flask, colors=LIQUID_NAMES,
                             fields=_D + [("neck", "Neck Ø"),
                                          ("h", "Height"),
                                          ("wall", "Wall")] + _FILL),
    "chem_funnel": dict(label="Funnel", category=CATEGORY,
                        sizes=FUNNEL_SIZES, build=build_funnel,
                        fields=_D + [("stem", "Stem Ø"),
                                     ("h", "Height"), ("wall", "Wall")]),
    "chem_burette": dict(label="Burette (with stopcock)",
                         category=CATEGORY, sizes=BURETTE_SIZES,
                         build=build_burette, colors=LIQUID_NAMES,
                         fields=_D + [("h", "Length"), ("wall", "Wall")]
                         + _FILL),
    "chem_petri": dict(label="Petri dish (with lid)", category=CATEGORY,
                       sizes=PETRI_SIZES, build=build_petri_dish,
                       colors=["Iron(III) (amber)"] + [n for n in LIQUID_NAMES
                                                       if n != "Iron(III) (amber)"],
                       fields=_D + [("h", "Height"), ("fill", "Agar %")]),
    "chem_watch_glass": dict(label="Watch glass", category=CATEGORY,
                             sizes=PETRI_SIZES, build=build_watch_glass,
                             fields=_D),
    "chem_rack": dict(label="Test-tube rack", category=CATEGORY,
                      sizes=RACK_SIZES, build=build_test_tube_rack,
                      fields=[("holes", "Holes"),
                              ("hole_d", "Hole Ø")]),
    "chem_stand": dict(label="Retort stand + clamp", category=CATEGORY,
                       sizes=STAND_SIZES, build=build_retort_stand,
                       fields=[("base", "Base length"),
                               ("h", "Rod height")]),
    "chem_volumetric": dict(label="Volumetric flask", category=CATEGORY,
                            sizes=VOLU_SIZES,
                            build=build_volumetric_flask,
                            colors=LIQUID_NAMES,
                            fields=_D + [("neck", "Neck Ø"),
                                         ("h", "Height"),
                                         ("wall", "Wall")] + _FILL),
    "chem_sep_funnel": dict(label="Separating funnel", category=CATEGORY,
                            sizes=SEP_SIZES,
                            build=build_separating_funnel,
                            colors=LIQUID_NAMES,
                            fields=_D + [("h", "Height")] + _FILL),
    "chem_condenser": dict(label="Condenser (Liebig)", category=CATEGORY,
                           sizes=CONDENSER_SIZES, build=build_condenser,
                           fields=[("length", "Length"),
                                   ("jacket_d", "Jacket Ø"),
                                   ("inner_d", "Inner Ø")]),
    "chem_pipette": dict(label="Pipette (volumetric)", category=CATEGORY,
                         sizes=PIPETTE_SIZES, build=build_pipette,
                         fields=[("length", "Length"),
                                 ("bulb_d", "Bulb Ø"),
                                 ("tip_d", "Tube Ø")]),
    "chem_dropper": dict(label="Dropper (Pasteur)", category=CATEGORY,
                         sizes=DROPPER_SIZES, build=build_dropper,
                         fields=[("length", "Length"),
                                 ("tube_d", "Tube Ø")]),
    "chem_bunsen": dict(label="Bunsen burner", category=CATEGORY,
                        sizes=BURNER_SIZES, build=build_bunsen_burner,
                        fields=[("base", "Base Ø"), ("h", "Height"),
                                ("barrel", "Barrel Ø")]),
    "chem_hotplate": dict(label="Hotplate stirrer", category=CATEGORY,
                          sizes=HOTPLATE_SIZES, build=build_hotplate,
                          fields=[("w", "Width"), ("d", "Depth"),
                                  ("h", "Height"), ("plate", "Plate Ø")]),
    "chem_tripod": dict(label="Tripod", category=CATEGORY,
                        sizes=TRIPOD_SIZES, build=build_tripod,
                        fields=[("ring_d", "Ring Ø"),
                                ("h", "Height")]),
    "chem_gauze": dict(label="Wire gauze", category=CATEGORY,
                       sizes=GAUZE_SIZES, build=build_wire_gauze,
                       fields=[("side", "Side")]),
    "chem_gas_cylinder": dict(label="Gas cylinder (pick gas)",
                              category=CATEGORY, sizes=GAS_SIZES,
                              build=build_gas_cylinder,
                              fields=_D + [("h", "Body height")]),
    "chem_balance": dict(label="Analytical balance", category=CATEGORY,
                         sizes=BALANCE_SIZES, build=build_balance,
                         fields=[("w", "Width"), ("d", "Depth"),
                                 ("h", "Height")]),
    "chem_wash_bottle": dict(label="Wash bottle", category=CATEGORY,
                             sizes=WASH_SIZES, build=build_wash_bottle,
                             fields=_D + [("h", "Height")]),
}
