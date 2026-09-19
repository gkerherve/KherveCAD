"""Realistic animals (2026-09-19) — HIDDEN from the Library (the user:
"this is bad… hide this menu … but the work that was done needs to be
known so that when we improve we should use that"). Not registered in
`library.PARTS`; kept, and tested, as the starting point. At TRUE SIZE
in millimetres.

State and lessons for the next attempt: the generic `quadruped` rig
reads as a cow on sticks; the photo-traced `canine` plan (`LAB`) is
the method to extend — trace a side photograph at true scale, overlay
the render at 55 % and fix where the outlines part — but even traced,
smooth-blended primitives with one flat colour look like a plasticine
model, not a real animal: the next step needs fur/colour variation
(`paint`-like per-face colour), sharper anatomy (a sculpt pass on the
blend) and more than one reference view.

What the cartoons taught, applied to anatomy:

- one smooth skin (`blend`) is what makes a body read as flesh, so the
  whole body — ribcage, belly, hindquarters, shoulder and haunch
  muscles, neck, head, every leg segment and the tail — is ONE blend;
- colour details sit clearly OUTSIDE the skin (or they fight it), so
  markings are thin patches laid along the surface normal (`_patch`),
  and eyes, hooves, horns, manes and noses are their own solids;
- a species is a set of numbers handed to one body plan, so the set
  stays consistent.

The plan is a RIG (`quadruped`): withers height H, body length L (point
of shoulder to buttock), chest depth D, width W; the muscle masses
hang off it; the neck leaves the chest at its own angle and length, the
head at its own pitch; each leg is a chain of joints bent the way the
animal's are — shoulder, elbow, knee (carpus), fetlock, hoof in front;
hip, stifle (forward), hock (BACKWARD), fetlock, hoof behind — with a
radius at every joint, so a horse's cannon is slim and an elephant's
leg a pillar. Leg styles: hoof (ungulates), paw (carnivores: shorter
cannons, round paws), pillar (elephant, rhino, hippo) and knuckle (the
gorilla walks on its knuckles). Proportions are from published
measurements of adult animals (withers heights and body lengths); the
likeness is a good sketch, not a scan.

The snake and the crocodile have their own plans.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
import random

from .library_animals import _add, _f, _norm, _v, on_ellipsoid

CATEGORY = "Realistic animals"
EYE = "#1a1410"


def _mix(a, b, t):
    return [a[i] + (b[i] - a[i]) * t for i in range(3)]


def _seg(r):
    return 16 if r < 15 else 24 if r < 60 else 32


class Body:
    """Statements for one animal: a skin blend plus coloured details."""

    def __init__(self, scale):
        self.skin = []
        self.lines = []
        self.k = scale                 # mm per "unit" of detail sizes

    # primitives
    def ell(self, c, r):
        return (f"kcad_ellipsoid(c = {_v(c)}, r = {_v(r)}, "
                f"$fn = {_seg(max(r))});")

    def cap(self, a, b, r):
        return (f"kcad_capsule(a = {_v(a)}, b = {_v(b)}, r = {_f(r)}, "
                f"$fn = {_seg(r)});")

    def cone(self, base, tip, r0, r1=0.5):
        d = [tip[i] - base[i] for i in range(3)]
        length = math.sqrt(sum(c * c for c in d)) or 1.0
        tilt = math.degrees(math.acos(max(-1.0, min(1.0, d[2] / length))))
        turn = math.degrees(math.atan2(d[1], d[0]))
        return (f"translate({_v(base)}) rotate([0, {_f(tilt)}, {_f(turn)}]) "
                f"cylinder(h = {_f(length)}, r1 = {_f(r0)}, r2 = {_f(r1)}, "
                f"$fn = {_seg(r0)});")

    def chain(self, pts, radii):
        """Capsules through *pts*, each joint lifted clear of the ground
        by its radius (a tail, a trunk or a pillar leg never sinks)."""
        pts = [[q[0], q[1], max(q[2], radii[min(i, len(radii) - 1)])]
               for i, q in enumerate(pts)]
        return [self.cap(pts[i], pts[i + 1], radii[i])
                for i in range(len(pts) - 1)] + [
            self.ell(pts[-1], [radii[-1]] * 3)]

    def patch(self, p, n, a, b, t, turn=0.0):
        """A thin disc lying on the surface at *p* (normal *n*): *a* x *b*
        across, *t* thick along the normal."""
        n = _norm(n)
        tilt = math.degrees(math.acos(max(-1.0, min(1.0, n[2]))))
        az = math.degrees(math.atan2(n[1], n[0]))
        return (f"translate({_v(p)}) rotate([0, {_f(tilt)}, {_f(az)}]) "
                f"rotate([0, 0, {_f(turn)}]) scale({_v([a, b, t])}) "
                f"sphere(r = 1, $fn = 12);")

    def put(self, colour, label, pieces, material="Matte"):
        self.lines.append(f'kcad_material("{material}") color("{colour}") '
                          f"union() {{ {' '.join(pieces)} }}  // {label}")

    def blend(self, colour, label, radius, pieces, detail=64,
              material="Skin"):
        self.lines.append(
            f'kcad_material("{material}") color("{colour}") '
            f"kcad_blend(radius = {_f(radius)}, detail = {detail}) "
            f"{{ {' '.join(pieces)} }}  // {label}")

    def program(self):
        return "\n".join(self.lines)


# ------------------------------------------------------------ quadruped
def rig(p):
    """Joint positions and radii of a four-legged animal from its
    measurements (mm; the animal faces -Y and stands on z = 0)."""
    H, L, D, W = p["H"], p["L"], p["D"], p["W"]
    style = p.get("legs", "hoof")
    chest_z = H - D                           # underside of the chest
    j = {}
    j["withers"] = [0, -L * 0.3, H]
    j["croup"] = [0, L * 0.38, H * p.get("croup", 0.98)]
    j["ribs"] = ([0, -L * 0.14, H - D * 0.5], [W * 0.5, L * 0.36, D * 0.52])
    j["belly"] = ([0, L * 0.1, H - D * 0.58 - p.get("sag", 0.0)],
                  [W * 0.49, L * 0.32, D * 0.47])
    j["haunch"] = ([0, L * 0.34, H - D * 0.42],
                   [W * 0.47, L * 0.2, D * 0.5])
    j["chest"] = ([0, -L * 0.42, H - D * 0.62],
                  [W * 0.38, L * 0.12, D * 0.36])
    # neck and head
    na, nl = math.radians(p.get("neck_angle", 45)), p.get("neck", D * 0.9)
    base = [0, -L * 0.4, H - D * 0.28]
    nd = [0, -math.cos(na), math.sin(na)]
    j["neck"] = (base, _add(base, nd, nl))
    hp = math.radians(p.get("head_pitch", 40))
    hd = [0, -math.cos(hp), -math.sin(hp)]
    j["head_dir"] = hd
    j["head_base"] = j["neck"][1]
    # legs: front — shoulder, elbow, knee, fetlock, ground
    fx = W * 0.3
    front_y = -L * 0.4
    low = {"hoof": 0.07, "paw": 0.04, "pillar": 0.0, "knuckle": 0.0}[style]
    knee = {"hoof": 0.3, "paw": 0.22, "pillar": 0.35, "knuckle": 0.4}[style]
    fl = p.get("front_lean", 0.0) * L
    j["front"] = [[fx, front_y + L * 0.02, H - D * 0.55],
                  [fx, front_y + L * 0.05, chest_z + D * 0.05],
                  [fx, front_y + fl * 0.6, H * knee],
                  [fx, front_y + fl - L * 0.01, H * low + D * 0.03],
                  [fx, front_y + fl - L * 0.03, 0.0]]
    # hind — hip, stifle (forward), hock (back), fetlock, ground
    hx = W * 0.3
    hind_y = L * 0.38
    j["hind"] = [[hx, hind_y - L * 0.02, H - D * 0.35],
                 [hx, hind_y - L * 0.12, chest_z + D * 0.02],
                 [hx, hind_y + L * 0.06, H * (knee + 0.08)],
                 [hx, hind_y + L * 0.02, H * low + D * 0.03],
                 [hx, hind_y, 0.0]]
    return j


def quadruped(p):
    b = Body(p["H"] / 1000.0)
    H, L, D, W = p["H"], p["L"], p["D"], p["W"]
    style = p.get("legs", "hoof")
    j = rig(p)
    coat = p["coat"]
    skin = []
    for key in ("ribs", "belly", "haunch", "chest"):
        c, r = j[key]
        skin.append(b.ell(c, r))
    # shoulder and thigh muscles
    for sx in (1, -1):
        s0 = j["front"][0]
        skin.append(b.ell([sx * W * 0.34, s0[1] + L * 0.02, H - D * 0.5],
                          [W * 0.2, L * 0.12, D * 0.42]))
        h0 = j["hind"][0]
        skin.append(b.ell([sx * W * 0.34, h0[1] - L * 0.02, H - D * 0.5],
                          [W * 0.21, L * 0.14, D * 0.5]))
    if p.get("hump"):                          # camel
        skin.append(b.ell([0, -L * 0.02, H + p["hump"] * 0.4],
                          [W * 0.32, L * 0.18, p["hump"]]))
    # neck: a tapered chain
    n0, n1 = j["neck"]
    r0 = p.get("neck_r", D * 0.34)
    r1 = p.get("head_w", D * 0.4) * 0.45
    pts = [_mix(n0, n1, t) for t in (0.0, 0.35, 0.7, 1.0)]
    skin += b.chain(pts, [r0, r0 * 0.8 + r1 * 0.2, r0 * 0.45 + r1 * 0.55, r1])
    # head: skull, face, muzzle, jaw
    hd, hb = j["head_dir"], j["head_base"]
    hl, hw = p.get("head_l", D * 0.9), p.get("head_w", D * 0.4)
    skull = _add(_add(hb, hd, hl * 0.22), [0, 0, 1], hw * 0.12)
    face = _add(hb, hd, hl * 0.55)
    muzzle = _add(hb, hd, hl * 0.85)
    skin.append(b.ell(skull, [hw * 0.5, hl * 0.3, hw * 0.52]))
    skin.append(b.cap(skull, face, hw * p.get("face_w", 0.36)))
    skin.append(b.ell(muzzle, [hw * p.get("muzzle_w", 0.34),
                               hl * 0.18, hw * p.get("muzzle_h", 0.36)]))
    skin.append(b.cap(_add(skull, [0, 0, -hw * 0.35]),
                      _add(muzzle, [0, 0, -hw * 0.2]), hw * 0.26))
    # legs
    leg_r = p.get("leg_r", [W * 0.2, W * 0.13, W * 0.075, W * 0.07,
                            W * 0.08])
    hind_r = p.get("hind_r", [r * 1.12 for r in leg_r[:2]] + leg_r[2:])
    for sx in (1, -1):
        for chain, radii in ((j["front"], leg_r), (j["hind"], hind_r)):
            pts = [[sx * abs(q[0]), q[1], q[2] + (radii[-1] if k == len(
                chain) - 1 else 0)] for k, q in enumerate(chain)]
            skin += b.chain(pts, radii)
    # tail
    tail = p.get("tail")
    if tail:
        root = _add(j["croup"], [0, L * 0.12, -D * 0.12])
        tl, droop = tail["length"], math.radians(tail.get("droop", 70))
        d = [0, math.cos(droop), -math.sin(droop)]
        tpts = [root, _add(root, d, tl * 0.35),
                _add(_add(root, d, tl * 0.7), [0, 0, -tl * 0.05]),
                _add(_add(root, d, tl), [0, 0, -tl * 0.12])]
        tr = tail.get("r", W * 0.06)
        skin += b.chain(tpts, [tr, tr * 0.8, tr * 0.6, tr * 0.45])
    b.blend(coat, "Body", p.get("blend", W * 0.08), skin,
            detail=p.get("detail", 72))
    # details
    _markings(b, p, j)
    _face(b, p, j, skull, muzzle, hw, hl)
    feet = p.get("feet_colour")
    for sx in (1, -1):
        for chain, radii in ((j["front"], leg_r), (j["hind"], hind_r)):
            g = [sx * abs(chain[-1][0]), chain[-1][1], 0.0]
            r = radii[-1]
            if style == "hoof":
                b.put(p.get("hoof", "#2b2420"), "Hoof", [
                    b.cone(g, _add(g, [0, 0, r * 1.5]), r * 1.12, r * 0.95)],
                    material="Plastic")
            elif feet:
                b.put(feet, "Foot", [b.ell(_add(g, [0, -r * 0.3, r * 0.75]),
                                           [r * 1.1, r * 1.35, r * 0.82])])
    if tail and tail.get("tuft"):
        end = list(tpts[-1])
        end[2] = max(end[2], tl * 0.24 + tr)
        b.put(tail["tuft"], "Tail switch", [b.cap(
            _add(end, [0, -tl * 0.02, tl * 0.08]),
            _add(end, [0, tl * 0.02, -tl * 0.22]), tr * 0.75)])
    for extra in p.get("extras", ()):
        extra(b, p, j, dict(skull=skull, muzzle=muzzle, hw=hw, hl=hl))
    return b


def _face(b, p, j, skull, muzzle, hw, hl):
    hd = j["head_dir"]
    side = p.get("eyes_side", 0.62)             # herbivores look sideways
    for sx in (1, -1):
        eye = _add(_add(skull, hd, hl * 0.12),
                   [sx * hw * 0.44, 0, hw * 0.16])
        n = _norm([sx * side, -1 + side, 0.1])
        r = p.get("eye_r", hw * 0.09)
        b.put(EYE, "Eye", [b.ell(_add(eye, n, r * 0.2), [r, r, r])],
              material="Glass")
        if p.get("ears"):
            _ear(b, p, sx, skull, hw, hl, hd)
    nose = p.get("nose", "#2b2420")
    tip = _add(muzzle, hd, hl * 0.15)
    for sx in (1, -1):
        b.put(nose, "Nostril", [b.patch(
            _add(tip, [sx * hw * 0.14, 0, hw * 0.06]),
            [sx * 0.3, -0.9, 0.2], hw * 0.07, hw * 0.1, hw * 0.03)])
    if p.get("nose_pad"):                       # dog, cat, bear: a pad
        b.put(nose, "Nose", [b.ell(_add(tip, [0, 0, hw * 0.12]),
                                   [hw * 0.2, hw * 0.12, hw * 0.13])],
              material="Glass")


def _ear(b, p, sx, skull, hw, hl, hd):
    kind, size = p["ears"], p.get("ear_size", hw * 0.45)
    colour = p.get("ear_colour", p["coat"])
    base = _add(skull, [sx * hw * 0.34, hl * 0.06, hw * 0.4])
    if kind == "upright":                       # horse, deer, dog, cat, fox
        tip = _add(base, _norm([sx * 0.35, 0.25, 1.0]), size)
        b.put(colour, "Ear", [b.cone(base, tip, size * 0.3, size * 0.03)])
        if p.get("inner_ear"):
            b.put(p["inner_ear"], "Inner ear", [b.cone(
                _add(base, [0, -size * 0.12, size * 0.05]),
                _add(tip, [0, -size * 0.08, -size * 0.2]), size * 0.2,
                size * 0.02)])
    elif kind == "side":                        # cow, pig, sheep, goat
        tip = _add(base, _norm([sx * 1.0, 0.15, -0.1]), size)
        b.put(colour, "Ear", [b.cap(base, tip, size * 0.22)])
    elif kind == "round":                       # bear, lion, tiger, hippo
        b.put(colour, "Ear", [b.ell(_add(base, [sx * size * 0.2, 0, size * 0.3]),
                                    [size * 0.45, size * 0.2, size * 0.45])])
    elif kind == "elephant":
        c = _add(base, [sx * size * 0.35, size * 0.25, -size * 0.35])
        b.put(colour, "Ear", [b.ell(c, [size * 0.1, size * 0.55, size * 0.7])])
    elif kind == "floppy":                      # labrador
        tip = _add(base, [sx * size * 0.3, -size * 0.05, -size * 0.8])
        b.put(colour, "Ear", [b.ell(_mix(base, tip, 0.5),
                                    [size * 0.12, size * 0.35, size * 0.5])])


def _ray_ellipsoid(a, d, c, r):
    """Largest t >= 0 with a + t d on the ellipsoid (c, r), or None."""
    o = [(a[i] - c[i]) / r[i] for i in range(3)]
    e = [d[i] / r[i] for i in range(3)]
    qa = sum(x * x for x in e)
    qb = 2 * sum(o[i] * e[i] for i in range(3))
    qc = sum(x * x for x in o) - 1.0
    disc = qb * qb - 4 * qa * qc
    if disc < 0 or qa == 0:
        return None
    t = (-qb + math.sqrt(disc)) / (2 * qa)
    return t if t >= 0 else None


def surface(masses, a, d):
    """Where the union of the *masses* (ellipsoids) is left by the ray
    from *a* along *d*: the outermost hit, with the normal of the mass
    hit — the blended body's own skin, give or take the blend radius."""
    d = _norm(d)
    best, best_t = None, -1.0
    for c, r in masses:
        t = _ray_ellipsoid(a, d, c, r)
        if t is not None and t > best_t:
            best, best_t = (c, r), t
    if best is None:
        return None, None
    c, r = best
    q = _add(a, d, best_t)
    return q, _norm([(q[i] - c[i]) / r[i] ** 2 for i in range(3)])


def _masses(p, j):
    H, L, D, W = p["H"], p["L"], p["D"], p["W"]
    out = [j[k] for k in ("ribs", "belly", "haunch", "chest")]
    for sx in (1, -1):
        out.append(([sx * W * 0.34, j["front"][0][1] + L * 0.02, H - D * 0.5],
                    [W * 0.2, L * 0.12, D * 0.42]))
        out.append(([sx * W * 0.34, j["hind"][0][1] - L * 0.02, H - D * 0.5],
                    [W * 0.21, L * 0.14, D * 0.5]))
    return out


def _markings(b, p, j):
    rnd = random.Random(p.get("seed", 1))
    H, L, D, W = p["H"], p["L"], p["D"], p["W"]
    mk = p.get("markings")
    if not mk:
        return
    kind, colour = mk[0], mk[1]
    pieces = []
    if kind == "stripes":                       # zebra, tiger, tabby
        count = mk[2] if len(mk) > 2 else 14
        width = mk[3] if len(mk) > 3 else W * 0.035
        span = (-L * 0.44, L * 0.46)
        body = _masses(p, j)
        axis_z = H - D * 0.5
        for k in range(count):
            y = span[0] + (span[1] - span[0]) * (k + 0.5) / count
            y += rnd.uniform(-0.25, 0.25) * (span[1] - span[0]) / count
            reach = rnd.uniform(110, 165)
            lean = rnd.uniform(-0.15, 0.15)
            for sx in (1, -1):
                arc = []
                for a in range(0, int(reach) + 1, 15):
                    ang = math.radians(a)
                    q, n = surface(body, [0, y, axis_z],
                                   [sx * math.sin(ang), lean * math.sin(ang),
                                    math.cos(ang)])
                    if q is not None:
                        arc.append(_add(q, n, -width * 0.55))
                pieces += [f"kcad_capsule(a = {_v(arc[i])}, b = {_v(arc[i + 1])}, "
                           f"r = {_f(width * (1.0 - 0.45 * i / len(arc)))}, $fn = 8);"
                           for i in range(len(arc) - 1)]
    elif kind in ("patches", "spots"):          # holstein, giraffe, dalmatian
        count = mk[2] if len(mk) > 2 else 10
        size = mk[3] if len(mk) > 3 else W * 0.25
        body = _masses(p, j)
        for k in range(count):
            a0 = [0, rnd.uniform(-L * 0.42, L * 0.44), H - D * 0.5]
            d = [rnd.uniform(-1, 1), 0, rnd.uniform(-0.3, 1)]
            p0, n0 = surface(body, a0, d)
            if p0 is None:
                continue
            a = size * rnd.uniform(0.6, 1.2)
            pieces.append(b.patch(_add(p0, n0, W * 0.006), n0, a,
                                  a * rnd.uniform(0.6, 1.0), W * 0.012,
                                  turn=rnd.uniform(0, 180)))
        if kind == "spots" and p.get("neck_spots"):
            n0_, n1_ = j["neck"]
            for k in range(p["neck_spots"]):
                t = (k + 0.5) / p["neck_spots"]
                c = _mix(n0_, n1_, t)
                for sx in (1, -1):
                    q = _add(c, [sx * p.get("neck_r", D * 0.34) * 0.92, 0, 0])
                    pieces.append(b.patch(q, [sx, 0, 0.1], size * 0.55,
                                          size * 0.45, W * 0.012,
                                          turn=rnd.uniform(0, 180)))
    b.put(colour, "Markings", pieces)


# ------------------------------------------------------------- extras
def mane(colour, crest=True):
    def draw(b, p, j, h):
        n0, n1 = j["neck"]
        r0 = p.get("neck_r", p["D"] * 0.34)
        pieces = []
        for k in range(9):
            t = k / 8.0
            c = _add(_mix(n0, n1, t), [0, 0, r0 * (0.95 - 0.35 * t)])
            pieces.append(b.ell(c, [r0 * 0.14, r0 * 0.35, r0 * 0.3]))
        if crest:
            pieces.append(b.ell(_add(h["skull"], [0, -h["hl"] * 0.12,
                                                  h["hw"] * 0.5]),
                                [h["hw"] * 0.15, h["hl"] * 0.12,
                                 h["hw"] * 0.12]))
        b.put(colour, "Mane", pieces)
    return draw


def lion_mane(colour):
    def draw(b, p, j, h):
        n0, n1 = j["neck"]
        pieces = []
        rnd = random.Random(4)
        r = p.get("neck_r", p["D"] * 0.34) * 1.05
        pieces.append(b.cap(n0, _add(n1, j["head_dir"], h["hl"] * 0.1),
                            r * 1.08))
        for k in range(40):
            t = rnd.uniform(0.15, 1.15)
            a = rnd.uniform(0, 2 * math.pi)
            c = _mix(n0, n1, min(t, 1.0))
            pieces.append(b.ell(_add(c, [math.cos(a) * r * 1.05, 0,
                                         math.sin(a) * r * 1.15]),
                                [r * 0.45, r * 0.5, r * 0.45]))
        b.blend(colour, "Mane", r * 0.2, pieces, detail=48, material="Matte")
    return draw


def horns(colour, kind):
    def draw(b, p, j, h):
        sk, hw, hl, hd = h["skull"], h["hw"], h["hl"], j["head_dir"]
        for sx in (1, -1):
            base = _add(sk, [sx * hw * 0.32, hl * 0.02, hw * 0.45])
            if kind == "cow":
                pts = [base, _add(base, [sx * hw * 0.45, 0, hw * 0.05]),
                       _add(base, [sx * hw * 0.7, -hw * 0.1, hw * 0.35])]
                b.put(colour, "Horn", [b.cap(pts[0], pts[1], hw * 0.07),
                                       b.cap(pts[1], pts[2], hw * 0.045)],
                      material="Plastic")
            elif kind == "goat":
                pts = [base]
                for k in range(1, 6):
                    a = k * 0.35
                    pts.append(_add(base, [sx * hw * 0.08 * k,
                                           hw * 0.25 * math.sin(a) * k * 0.6,
                                           hw * 0.3 * math.cos(a) * k * 0.4]))
                b.put(colour, "Horn", [b.cap(pts[i], pts[i + 1],
                                             hw * (0.08 - i * 0.012))
                                       for i in range(5)], material="Plastic")
            elif kind == "antlers":
                main = [base, _add(base, [sx * hw * 0.3, hw * 0.1, hw * 0.8]),
                        _add(base, [sx * hw * 0.6, hw * 0.3, hw * 1.6]),
                        _add(base, [sx * hw * 0.7, hw * 0.1, hw * 2.3])]
                pieces = [b.cap(main[i], main[i + 1], hw * 0.05)
                          for i in range(3)]
                for k in (1, 2):
                    tine = _add(main[k], [sx * hw * 0.1, -hw * 0.45,
                                          hw * 0.35])
                    pieces.append(b.cap(main[k], tine, hw * 0.035))
                b.put(colour, "Antler", pieces, material="Plastic")
            elif kind == "ossicones":
                tip = _add(base, [sx * hw * 0.05, hw * 0.1, hw * 0.55])
                b.put(colour, "Ossicone", [b.cap(base, tip, hw * 0.07),
                                           b.ell(tip, [hw * 0.1] * 3)])
        if kind == "rhino":
            tip = _add(h["muzzle"], hd, hl * 0.02)
            b.put(colour, "Horn", [
                b.cone(_add(tip, [0, 0, hw * 0.3]),
                       _add(tip, [0, -hw * 0.25, hw * 1.25]), hw * 0.26,
                       hw * 0.02),
                b.cone(_add(sk, [0, -hl * 0.18, hw * 0.45]),
                       _add(sk, [0, -hl * 0.2, hw * 0.95]), hw * 0.16,
                       hw * 0.02)], material="Plastic")
    return draw


def trunk(colour):
    def draw(b, p, j, h):
        m, hw, hl = h["muzzle"], h["hw"], h["hl"]
        pts = [m, _add(m, [0, -hl * 0.1, -hl * 0.35]),
               _add(m, [0, -hl * 0.12, -hl * 0.8]),
               _add(m, [0, -hl * 0.28, -hl * 1.15]),
               _add(m, [0, -hl * 0.45, -hl * 1.25])]
        b.blend(colour, "Trunk", hw * 0.05, b.chain(
            pts, [hw * 0.24, hw * 0.2, hw * 0.16, hw * 0.12, hw * 0.1]),
            detail=48)
        for sx in (1, -1):
            base = _add(m, [sx * hw * 0.25, 0, -hw * 0.2])
            b.put("#f2ead8", "Tusk", [b.cap(base, _add(base, [sx * hw * 0.1,
                                                                -hl * 0.35,
                                                                -hl * 0.2]),
                                            hw * 0.05)], material="Plastic")
    return draw


def points(colour, height=0.25):
    """Dark lower legs (bay horse, fox)."""
    def draw(b, p, j, h):
        pieces = []
        for chain in (j["front"], j["hind"]):
            for sx in (1, -1):
                lo = [sx * abs(chain[-1][0]), chain[-1][1], 0]
                up = [sx * abs(chain[2][0]), chain[2][1], p["H"] * height]
                pieces.append(b.cap(lo, up, p["W"] * 0.085))
        b.put(colour, "Leg points", pieces)
    return draw


def pale(colour, where="belly"):
    """A pale underside / muzzle / rump."""
    def draw(b, p, j, h):
        if where == "belly":
            c, r = j["belly"]
            pt, n = on_ellipsoid(c, r, [0, 0, -1])
            b.put(colour, "Belly", [b.patch(_add(pt, n, p["W"] * 0.004), n,
                                            r[0] * 0.75, r[1] * 0.85,
                                            p["W"] * 0.02)])
        elif where == "muzzle":
            b.put(colour, "Muzzle", [b.ell(_add(h["muzzle"], j["head_dir"],
                                                h["hl"] * 0.02),
                                           [h["hw"] * p.get("muzzle_w", 0.34) * 1.04,
                                            h["hl"] * 0.17,
                                            h["hw"] * p.get("muzzle_h", 0.36) * 1.04])])
        elif where == "rump":
            c, r = j["haunch"]
            pt, n = on_ellipsoid(c, r, [0, 1, 0.15])
            b.put(colour, "Rump", [b.patch(_add(pt, n, p["W"] * 0.004), n,
                                           r[0] * 0.55, r[2] * 0.5,
                                           p["W"] * 0.02)])
        elif where == "chest":
            c, r = j["chest"]
            pt, n = on_ellipsoid(c, r, [0, -1, -0.2])
            b.put(colour, "Chest", [b.patch(_add(pt, n, p["W"] * 0.004), n,
                                            r[0] * 0.75, r[2] * 0.8,
                                            p["W"] * 0.02)])
    return draw


def rings(colour, neck=8, legs=5):
    """Stripe rings round the neck and the legs (a zebra's)."""
    def draw(b, p, j, h):
        W = p["W"]
        pieces = []

        def ring(c, axis, radius):
            wr = radius * 0.12
            radius = radius * 1.0 + wr * 0.25
            axis = _norm(axis)
            u = _norm([axis[1], -axis[0], 0]) if abs(axis[2]) < 0.9 \
                else [1, 0, 0]
            v = [axis[1] * u[2] - axis[2] * u[1], axis[2] * u[0] - axis[0] * u[2],
                 axis[0] * u[1] - axis[1] * u[0]]
            pts = [_add(_add(c, u, math.cos(a) * radius), v,
                        math.sin(a) * radius)
                   for a in (2 * math.pi * k / 10 for k in range(11))]
            return [f"kcad_capsule(a = {_v(pts[i])}, b = {_v(pts[i + 1])}, "
                    f"r = {_f(wr)}, $fn = 8);" for i in range(10)]
        n0, n1 = j["neck"]
        r0 = p.get("neck_r", p["D"] * 0.34)
        r1 = p.get("head_w", p["D"] * 0.4) * 0.45
        axis = [n1[i] - n0[i] for i in range(3)]
        for k in range(neck):
            t = (k + 0.5) / neck
            pieces += ring(_mix(n0, n1, t), axis, (r0 + (r1 - r0) * t) * 1.15)
        leg_r = p.get("leg_r") or [W * 0.2, W * 0.13, W * 0.075,
                                   W * 0.07, W * 0.08]
        for chain in (j["front"], j["hind"]):
            for sx in (1, -1):
                for seg in (1, 2):
                    a0 = [sx * abs(chain[seg][0]), chain[seg][1],
                          chain[seg][2]]
                    a1 = [sx * abs(chain[seg + 1][0]), chain[seg + 1][1],
                          chain[seg + 1][2]]
                    for k in range(legs // 2 + 1):
                        t = (k + 0.5) / (legs // 2 + 1)
                        rad = leg_r[seg] + (leg_r[seg + 1] - leg_r[seg]) * t
                        pieces += ring(_mix(a0, a1, t),
                                       [a1[i] - a0[i] for i in range(3)], rad)
        b.put(colour, "Rings", pieces)
    return draw


def brow(colour):
    """An ape's brow ridge and sagittal crest."""
    def draw(b, p, j, h):
        sk, hw, hl = h["skull"], h["hw"], h["hl"]
        b.put(colour, "Brow", [
            b.cap(_add(sk, [hw * 0.3, -hl * 0.28, hw * 0.25]),
                  _add(sk, [-hw * 0.3, -hl * 0.28, hw * 0.25]), hw * 0.1),
            b.ell(_add(sk, [0, hl * 0.05, hw * 0.45]),
                  [hw * 0.18, hl * 0.3, hw * 0.3])])
    return draw


def wool(colour):
    def draw(b, p, j, h):
        rnd = random.Random(8)
        pieces = []
        for key in ("ribs", "belly", "haunch", "chest"):
            c, r = j[key]
            pieces.append(b.ell(c, [v * 1.12 for v in r]))
            for _ in range(10):
                pt, n = on_ellipsoid(c, [v * 1.1 for v in r],
                                     [rnd.uniform(-1, 1), rnd.uniform(-1, 1),
                                      rnd.uniform(-0.4, 1)])
                pieces.append(b.ell(pt, [p["W"] * 0.12] * 3))
        b.blend(colour, "Fleece", p["W"] * 0.05, pieces, detail=56,
                material="Matte")
    return draw


# --------------------------------------------------------- other plans
def snake(p):
    b = Body(1.0)
    L, r = p["L"], p["r"]
    pts = []
    for k in range(34):
        t = k / 33.0
        pts.append([math.sin(t * 3.4 * math.pi) * L * 0.09,
                    -L * 0.32 + t * L * 0.64 * 0.9, r])
    radii = [r * (0.75 + 0.35 * math.sin(math.pi * min(t * 1.4, 1)))
             for t in (k / 33.0 for k in range(34))]
    radii[-1] = r * 0.2
    radii[-2] = r * 0.35
    head = _add(pts[0], [0, -r * 1.4, r * 0.35])
    skin = b.chain(pts, radii) + [
        b.ell(head, [r * 1.05, r * 1.7, r * 0.72])]
    b.blend(p["coat"], "Body", r * 0.3, skin, detail=90)
    rnd = random.Random(3)
    marks = []
    for k in range(1, 32, 2):
        c = pts[k]
        marks.append(b.patch(_add(c, [0, 0, radii[k] * 0.98]), [0, 0, 1],
                             radii[k] * 0.7, radii[k] * 0.55, r * 0.08,
                             turn=rnd.uniform(0, 90)))
    b.put(p["pattern"], "Pattern", marks)
    for sx in (1, -1):
        b.put(EYE, "Eye", [b.ell(_add(head, [sx * r * 0.62, -r * 0.8,
                                             r * 0.35]),
                                 [r * 0.18] * 3)], material="Glass")
    return b


def crocodile(p):
    b = Body(1.0)
    L = p["L"]
    r = L * 0.075
    spine = [[0, -L * 0.12 + t * L * 0.62, r * (1.05 - 0.9 * t) + r * 0.35]
             for t in (k / 10.0 for k in range(11))]
    radii = [r * (1.0 - 0.85 * (k / 10.0) ** 1.4) for k in range(11)]
    skin = b.chain(spine, radii)
    skin.append(b.ell([0, -L * 0.05, r * 1.1], [r * 1.35, L * 0.16, r * 0.85]))
    head = [0, -L * 0.3, r * 0.95]
    skin.append(b.ell(head, [r * 0.85, L * 0.1, r * 0.55]))
    skin.append(b.ell([0, -L * 0.42, r * 0.7], [r * 0.5, L * 0.1, r * 0.33]))
    for sx in (1, -1):
        for y in (-L * 0.16, L * 0.08):
            sh = [sx * r * 1.1, y, r * 1.0]
            el = [sx * r * 2.1, y - r * 0.2, r * 0.8]
            ft = [sx * r * 2.2, y - r * 0.4, r * 0.18]
            skin += b.chain([sh, el, ft], [r * 0.42, r * 0.3, r * 0.22])
    b.blend(p["coat"], "Body", r * 0.2, skin, detail=90)
    scutes = []
    for k in range(18):
        y = -L * 0.2 + k * L * 0.035
        z = r * (1.05 - 0.6 * k / 18) + r * 1.1
        for sx in (1, -1):
            scutes.append(b.cone([sx * r * 0.3, y, z - r * 0.12],
                                 [sx * r * 0.3, y, z + r * 0.12],
                                 r * 0.12, r * 0.02))
    b.put(p["scute"], "Scutes", scutes)
    for sx in (1, -1):
        b.put("#c9a227", "Eye", [b.ell([sx * r * 0.45, -L * 0.28,
                                        r * 1.5], [r * 0.14] * 3)],
              material="Glass")
    teeth = [b.cone([sx * r * 0.45, -L * 0.33 - k * L * 0.018, r * 0.62],
                    [sx * r * 0.47, -L * 0.33 - k * L * 0.018, r * 0.45],
                    r * 0.05, r * 0.01)
             for sx in (1, -1) for k in range(6)]
    b.put("#f2ead8", "Teeth", teeth, material="Plastic")
    return b


# ------------------------------------------------------------- canine
#: A Labrador measured in side view from a photograph, scaled so the
#: withers stand at the breed standard's 570 mm: (x across, y along
#: — front -Y —, z up) in mm, x the offset of a left-hand part. Every
#: dog-shaped animal is this template stretched (`canine`).
LAB = dict(
    ribs=((0, -120, 412), (114, 225, 150)),
    chest=((0, -288, 420), (74, 74, 92)),
    back=((0, 20, 478), (90, 335, 84)),
    keel=((0, -60, 330), (80, 170, 70)),
    loin=((0, 130, 448), (100, 165, 96)),
    croup=((0, 275, 455), (110, 118, 106)),
    shoulder=((68, -185, 440), (42, 92, 120)),
    thigh=((70, 322, 384), (56, 80, 108)),
    neck=[((0, -205, 482), 86), ((0, -255, 560), 74), ((0, -288, 616), 66)],
    skull=((0, -332, 620), (72, 72, 52)),
    flew=((26, -452, 566), (22, 46, 30)),
    brow=((0, -392, 630), (58, 30, 40)),
    cheek=((42, -374, 600), (32, 42, 38)),
    muzzle=[((0, -407, 594), 40), ((0, -488, 590), 37)],
    jaw=((0, -447, 562), (44, 58, 30)),
    nose=((0, -524, 596), (24, 14, 18)),
    eye=((37, -397, 634), 10),
    ear=((78, -326, 596), (11, 42, 58)),
    front=[((62, -232, 402), 42), ((62, -160, 262), 32), ((62, -158, 172), 25),
           ((62, -162, 104), 21), ((62, -170, 36), 19)],
    front_foot=((62, -184, 18), (24, 36, 18)),
    hind=[((68, 300, 452), 52), ((68, 336, 214), 33), ((68, 400, 130), 25),
          ((68, 421, 88), 21), ((68, 410, 36), 19)],
    hind_foot=((68, 396, 18), (24, 36, 18)),
    tail=[((0, 361, 531), 38), ((0, 460, 522), 34), ((0, 560, 512), 29),
          ((0, 650, 509), 22), ((0, 713, 512), 14)],
    belly=((0, 60, 300), (80, 170, 22)),
)


def canine(p):
    """A dog-shaped carnivore from the Labrador template: *size* is the
    withers height over the Lab's 570 mm, then *long* / *wide* stretch
    the body, *leg* the legs below the elbow, *head* and *snout* the
    skull and muzzle; ``ears`` pendant / pricked / round, ``tail``
    otter / brush / whip, ``coat`` / ``pale`` colours."""
    b = Body(1.0)
    k = p["H"] / 570.0
    long_, wide = p.get("long", 1.0), p.get("wide", 1.0)
    leg = p.get("leg", 1.0)
    head, snout = p.get("head", 1.0), p.get("snout", 1.0)
    elbow_z = 262.0

    def z_of(z):                                # legs stretch below the elbow
        return z * leg if z < elbow_z else z + elbow_z * (leg - 1.0)

    def P(q, side=1):
        x, y, z = q
        return [side * x * wide * k, y * long_ * k, z_of(z) * k]

    def Hd(q, side=1):
        """A head point: the head scales about the skull, the snout
        lengthens forward of the stop."""
        x, y, z = q
        sk = LAB["skull"][0]
        dy = y - sk[1]
        if y < -392:                            # forward of the stop
            dy = (-392 - sk[1]) + (y + 392) * snout
        return P([x * head, sk[1] + dy * head, sk[2] + (z - sk[2]) * head],
                 side)

    def R(r):
        return r * k

    skin = []
    for key in ("ribs", "chest", "loin", "croup", "back", "keel"):
        c, r = LAB[key]
        skin.append(b.ell(P(c), [r[0] * wide * k, r[1] * long_ * k, r[2] * k]))
    for side in (1, -1):
        for key in ("shoulder", "thigh"):
            c, r = LAB[key]
            skin.append(b.ell(P(c, side), [r[0] * wide * k, r[1] * long_ * k,
                                           r[2] * k]))
    pts = [P(q) for q, _r in LAB["neck"]]
    skin += b.chain(pts, [R(r) * p.get("neck_r", 1.0) for _q, r in LAB["neck"]])
    c, r = LAB["skull"]
    skin.append(b.ell(Hd(c), [v * k * head for v in r]))
    c, r = LAB["brow"]
    skin.append(b.ell(Hd(c), [v * k * head for v in r]))
    head_masses = []
    for key in ("skull", "brow"):
        c, r = LAB[key]
        head_masses.append((Hd(c), [v * k * head for v in r]))
    for side in (1, -1):
        for key in ("cheek", "flew"):
            c, r = LAB[key]
            skin.append(b.ell(Hd(c, side), [v * k * head for v in r]))
            head_masses.append((Hd(c, side), [v * k * head for v in r]))
    mz = [Hd(q) for q, _r in LAB["muzzle"]]
    mw = p.get("muzzle_w", 1.0)
    mr = LAB["muzzle"][0][1] * k * head
    # a broad, square muzzle: two capsules side by side
    for side in (1, -1):
        off = [side * mr * 0.38 * mw, 0, 0]
        skin.append(b.cap(_add(mz[0], off), _add(mz[1], off), mr * 0.82))
    c, r = LAB["jaw"]
    skin.append(b.ell(Hd(c), [r[0] * k * head * mw, r[1] * k * head * snout,
                              r[2] * k * head]))
    for side in (1, -1):
        for chain, foot in (("front", "front_foot"), ("hind", "hind_foot")):
            q = [P(c, side) for c, _r in LAB[chain]]
            skin += b.chain(q, [R(r) * p.get("bone", 1.0)
                                for _c, r in LAB[chain]])
            c, r = LAB[foot]
            skin.append(b.ell(P(c, side), [v * k * p.get("bone", 1.0)
                                           for v in r]))
    tail = p.get("tail", "otter")
    tq = [P(c) for c, _r in LAB["tail"]]
    if tail == "brush":                         # wolf, fox: hangs, bushy
        tq = [P(LAB["tail"][0][0])] + [
            _add(P(LAB["tail"][0][0]), [0, 110 * k * i, -95 * k * i])
            for i in (1, 2, 3, 4)]
        tr = [R(40), R(52), R(56), R(50), R(30)]
    elif tail == "whip":                        # cat, lion, tiger: long, low
        tq = [P(LAB["tail"][0][0])] + [
            _add(P(LAB["tail"][0][0]), [0, 130 * k * i, -110 * k * i + 12 * k * i * i])
            for i in (1, 2, 3, 4, 5)]
        tr = [R(22), R(18), R(16), R(15), R(14), R(13)]
    else:
        tr = [R(r) for _c, r in LAB["tail"]]
        fine_q, fine_r = [], []
        for i in range(len(tq) - 1):             # smooth: no beads
            for t in (0.0, 0.34, 0.67):
                fine_q.append(_mix(tq[i], tq[i + 1], t))
                fine_r.append(tr[i] + (tr[i + 1] - tr[i]) * t)
        tq, tr = fine_q + [tq[-1]], fine_r + [tr[-1]]
    tail_skin = b.chain(tq, tr)
    b.blend(p["coat"], "Body", R(18), skin + (tail_skin if tail != "brush"
                                              else []),
            detail=p.get("detail", 84))
    if tail == "brush":
        b.blend(p.get("tail_colour", p["coat"]), "Tail", R(20), tail_skin,
                detail=40)
        if p.get("tail_tip"):
            b.put(p["tail_tip"], "Tail tip", [b.ell(tq[-1], [tr[-1] * 1.2] * 3)])
    # pale underside, chest and muzzle
    pale = p.get("pale")
    if pale:
        c, r = LAB["belly"]
        b.put(pale, "Belly", [b.ell(P(c), [r[0] * wide * k, r[1] * long_ * k,
                                           r[2] * k])])
        cc, cr = LAB["chest"]
        q, n = surface([(P(cc), [cr[0] * wide * k, cr[1] * long_ * k,
                                 cr[2] * k])], P([0, -250, 420]), [0, -1, -0.3])
        if q:
            b.put(pale, "Chest", [b.patch(_add(q, n, R(1)), n, R(70), R(90),
                                          R(10))])
    if p.get("face_mask"):                      # pale jaw, lips and cheeks
        c, r = LAB["jaw"]
        pieces = [b.ell(_add(Hd(c), [0, 0, -R(3)]),
                        [r[0] * k * head * mw * 1.08,
                         r[1] * k * head * snout * 1.04, r[2] * k * head])]
        for side in (1, -1):
            c, r = LAB["cheek"]
            pieces.append(b.ell(_add(Hd(c, side), [0, 0, -R(10)]),
                                [r[0] * k * head * 1.05, r[1] * k * head,
                                 r[2] * k * head * 0.8]))
        b.put(p["face_mask"], "Face mask", pieces)
    # face
    c, r = LAB["nose"]
    b.put(p.get("nose", "#1c1614"), "Nose", [b.ell(Hd(c), [v * k * head
                                                            for v in r])],
          material="Glass")
    for side in (1, -1):
        c, r = LAB["eye"]
        er = r * k * head
        centre = Hd([0, c[1] + 40, c[2]])
        q, n = surface(head_masses, centre, [side * 0.62, -0.72, 0.18])
        if q is None:
            q, n = Hd(c, side), [side, 0, 0]
        b.put(p.get("eye", "#3a2414"), "Eye", [b.ell(_add(q, n, -er * 0.35),
                                                     [er, er, er])],
              material="Glass")
        b.put("#5a4030", "Eye rim", [b.patch(_add(q, n, -er * 0.3), n,
                                             er * 1.35, er * 1.1, er * 0.35)])
        lip0 = Hd([0, -502, 568])
        lip1 = Hd([38, -414, 566], side)
        b.put("#3a2a22", "Lip line", [b.cap(lip0, lip1, R(3.5))])
        ears = p.get("ears", "pendant")
        c, r = LAB["ear"]
        colour = p.get("ear_colour", p["coat"])
        if ears == "pendant":                   # a soft triangle, close
            corners = [(Hd([62, -352, 642], side), 11), (Hd([66, -296, 634],
                                                               side), 11),
                       (Hd([80, -334, 548], side), 15)]
            b.put(colour, "Ear", ["hull() { " + " ".join(
                b.ell(q, [rr * k * head] * 3) for q, rr in corners) + " }"])
        elif ears == "pricked":
            base = Hd([44, -318, 668], side)
            tip = _add(base, [side * 18 * k, 12 * k, 105 * k * p.get(
                "ear_size", 1.0)])
            b.put(colour, "Ear", [b.cone(base, tip, 34 * k * p.get(
                "ear_size", 1.0) * head, 3 * k)])
        else:                                   # round (big cats)
            base = Hd([50, -318, 672], side)
            b.put(colour, "Ear", [b.ell(base, [26 * k * head, 12 * k * head,
                                               26 * k * head])])
    for extra in p.get("extras", ()):
        extra(b, p, k, P, Hd)
    return b


# ------------------------------------------------------------- species
def _q(name, **kw):
    kw.update(name=name, plan=quadruped)
    return kw


SPECIES = {
    "Horse": _q("Horse", H=1600, L=2400, D=700, W=620, neck=900,
                neck_angle=52, neck_r=230, head_l=620, head_w=240,
                head_pitch=62, coat="#6b3f22", ears="upright",
                ear_size=150, legs="hoof", hoof="#2b2420",
                tail=dict(length=900, droop=75, r=55, tuft="#1f1a17"),
                extras=[mane("#1f1a17"), points("#1f1a17", 0.24),
                        pale("#e8e0d0", "muzzle")]),
    "Donkey": _q("Donkey", H=1200, L=1700, D=560, W=480, neck=560,
                 neck_angle=40, neck_r=180, head_l=520, head_w=210,
                 head_pitch=55, coat="#8a8580", ears="upright",
                 ear_size=260, inner_ear="#f1ece6", legs="hoof",
                 tail=dict(length=620, droop=80, r=35, tuft="#3a3632"),
                 extras=[mane("#3a3632", False), pale("#efe9e0", "muzzle"),
                         pale("#e6e0d6", "belly")]),
    "Zebra": _q("Zebra", H=1350, L=2300, D=620, W=560, neck=720,
                neck_angle=48, neck_r=200, head_l=540, head_w=220,
                head_pitch=60, coat="#f4f1ea", ears="upright",
                ear_size=150, legs="hoof", markings=("stripes", "#1c1a18",
                                                     24, 26),
                tail=dict(length=650, droop=78, r=35, tuft="#1c1a18"),
                leg_r=[112, 70, 38, 34, 40],
                extras=[mane("#1c1a18"), pale("#2a2624", "muzzle"),
                        rings("#1c1a18")]),
    "Cow": _q("Cow", H=1400, L=2400, D=780, W=700, neck=600,
              neck_angle=25, neck_r=300, head_l=620, head_w=320,
              head_pitch=55, sag=40, coat="#f4f1ea", ears="side",
              ear_size=200, legs="hoof", markings=("patches", "#1c1a18", 14,
                                                   190),
              tail=dict(length=1000, droop=85, r=35, tuft="#1c1a18"),
              extras=[horns("#e8dcc0", "cow"), pale("#e8b4b8", "muzzle")]),
    "Pig": _q("Pig", H=900, L=1500, D=560, W=560, neck=180, neck_angle=10,
              neck_r=240, head_l=420, head_w=260, head_pitch=30,
              muzzle_w=0.3, coat="#e8b4a6", ears="side", ear_size=160,
              legs="hoof", hoof="#6b4a44", leg_r=[110, 70, 45, 40, 44],
              tail=dict(length=240, droop=40, r=18), nose="#b07a70"),
    "Sheep": _q("Sheep", H=800, L=1200, D=440, W=440, neck=300,
                neck_angle=35, neck_r=120, head_l=300, head_w=140,
                head_pitch=55, coat="#2c2826", ears="side", ear_size=110,
                legs="hoof", leg_r=[70, 45, 28, 25, 28],
                tail=dict(length=150, droop=85, r=35),
                extras=[wool("#e9e2d0")]),
    "Goat": _q("Goat", H=750, L=1200, D=380, W=360, neck=380,
               neck_angle=55, neck_r=110, head_l=300, head_w=130,
               head_pitch=55, coat="#f1ece6", ears="side", ear_size=120,
               legs="hoof", leg_r=[70, 42, 25, 22, 25],
               tail=dict(length=150, droop=10, r=25),
               extras=[horns("#6b5a48", "goat")]),
    "Deer": _q("Deer", H=1000, L=1700, D=440, W=380, neck=560,
               neck_angle=60, neck_r=120, head_l=380, head_w=150,
               head_pitch=55, coat="#9a6a3f", ears="upright", ear_size=170,
               inner_ear="#e8d8c4", legs="hoof", leg_r=[80, 48, 26, 22, 24],
               tail=dict(length=200, droop=30, r=35),
               extras=[horns("#d9c6a0", "antlers"), pale("#f1e8da", "belly"),
                       pale("#f1e8da", "rump")]),
    "Dog (Labrador)": dict(name="Dog (Labrador)", plan=canine, H=570,
                           coat="#dcb680", ear_colour="#cf9f62"),
    "Wolf": dict(name="Wolf", plan=canine, H=800, long=1.02, wide=0.92,
                 leg=1.12, head=1.12, snout=1.35, muzzle_w=0.85,
                 bone=1.05, coat="#8d8a86", ears="pricked", ear_size=0.9,
                 ear_colour="#6f6c68", tail="brush", tail_colour="#7d7a76",
                 tail_tip="#2a2826", face_mask="#d9d4ce", eye="#b8892a"),
    "Fox": dict(name="Fox", plan=canine, H=400, long=1.15, wide=0.85,
                leg=0.95, head=1.05, snout=1.45, muzzle_w=0.72, bone=0.85,
                coat="#c4622d", ears="pricked", ear_size=1.25,
                ear_colour="#8a3f1c", tail="brush", tail_colour="#c4622d",
                tail_tip="#f4efe8", face_mask="#f4efe8", eye="#b8892a"),
    "Cat": _q("Cat", H=250, L=460, D=130, W=120, neck=90, neck_angle=40,
              neck_r=45, head_l=100, head_w=80, head_pitch=5, muzzle_w=0.3,
              coat="#a07850", ears="upright", ear_size=50,
              inner_ear="#e8b4b8", legs="paw", leg_r=[28, 18, 11, 10, 12],
              nose_pad=True, nose="#c47a80", eyes_side=0.15, eye_r=11,
              markings=("stripes", "#5a3e28", 12, 6),
              tail=dict(length=280, droop=20, r=14)),
    "Lion": _q("Lion", H=1200, L=1900, D=560, W=480, neck=380,
               neck_angle=30, neck_r=190, head_l=420, head_w=260,
               head_pitch=10, muzzle_w=0.32, coat="#c8a066",
               ears="round", ear_size=120, legs="paw",
               leg_r=[125, 80, 55, 50, 62], nose_pad=True, nose="#6b3f2a",
               eyes_side=0.2, tail=dict(length=900, droop=60, r=30,
                                        tuft="#5a3a1e"),
               extras=[lion_mane("#7a4a24")]),
    "Tiger": _q("Tiger", H=1000, L=1900, D=480, W=440, neck=330,
                neck_angle=25, neck_r=170, head_l=380, head_w=240,
                head_pitch=10, muzzle_w=0.32, coat="#d9772b", ears="round",
                ear_size=100, legs="paw", leg_r=[115, 75, 50, 46, 58],
                nose_pad=True, nose="#c47a80", eyes_side=0.2,
                markings=("stripes", "#1c1a18", 22, 22),
                tail=dict(length=950, droop=55, r=38),
                extras=[pale("#f4efe8", "belly"), pale("#f4efe8", "muzzle")]),
    "Brown bear": _q("Brown bear", H=1100, L=2000, D=640, W=680, neck=300,
                     neck_angle=20, neck_r=250, head_l=420, head_w=300,
                     head_pitch=20, croup=0.9, coat="#5a3d28", ears="round",
                     ear_size=110, legs="paw", leg_r=[150, 105, 80, 75, 90],
                     nose_pad=True, eyes_side=0.2, feet_colour="#3a281c",
                     tail=dict(length=100, droop=60, r=40)),
    "Elephant": _q("Elephant", H=3000, L=3400, D=1300, W=1400, neck=300,
                   neck_angle=10, neck_r=650, head_l=1200, head_w=1000,
                   head_pitch=60, coat="#8a8580", ears="elephant",
                   ear_size=950, legs="pillar",
                   leg_r=[340, 290, 250, 240, 260], croup=0.93,
                   tail=dict(length=1100, droop=85, r=50, tuft="#3a3632"),
                   extras=[trunk("#8a8580")], eye_r=45),
    "Giraffe": _q("Giraffe", H=3000, L=2200, D=900, W=700, neck=2100,
                  neck_angle=62, neck_r=200, head_l=650, head_w=240,
                  head_pitch=55, coat="#e2c088", ears="side", ear_size=180,
                  legs="hoof", leg_r=[150, 95, 60, 55, 70], croup=0.78,
                  markings=("spots", "#8a5a2b", 22, 180), neck_spots=7,
                  tail=dict(length=900, droop=80, r=30, tuft="#2a2220"),
                  extras=[horns("#8a5a2b", "ossicones"),
                          mane("#8a5a2b", False)]),
    "Rhinoceros": _q("Rhinoceros", H=1700, L=3400, D=900, W=1100,
                     neck=300, neck_angle=5, neck_r=450, head_l=750,
                     head_w=460, head_pitch=35, coat="#8a8580",
                     ears="upright", ear_size=200, legs="pillar",
                     leg_r=[250, 200, 160, 150, 170],
                     tail=dict(length=600, droop=85, r=40, tuft="#3a3632"),
                     extras=[horns("#b0a898", "rhino")]),
    "Hippopotamus": _q("Hippopotamus", H=1500, L=3500, D=1000, W=1400,
                       neck=200, neck_angle=5, neck_r=600, head_l=900,
                       head_w=700, head_pitch=15, muzzle_w=0.45,
                       muzzle_h=0.4, coat="#8a7a80", ears="round",
                       ear_size=120, legs="pillar",
                       leg_r=[260, 220, 190, 185, 200], croup=0.95,
                       tail=dict(length=450, droop=85, r=50),
                       extras=[pale("#d8a8a8", "belly")]),
    "Camel": _q("Camel", H=1900, L=2300, D=720, W=600, neck=1100,
                neck_angle=20, neck_r=170, head_l=520, head_w=210,
                head_pitch=15, coat="#c49a64", ears="round", ear_size=100,
                legs="hoof", hoof="#6b5a48", leg_r=[150, 90, 55, 50, 75],
                hump=420, tail=dict(length=500, droop=85, r=30,
                                    tuft="#6b5a48")),
    "Gorilla": _q("Gorilla", H=1300, L=1000, D=620, W=720, neck=180,
                  neck_angle=30, neck_r=240, head_l=380, head_w=380,
                  head_pitch=0, muzzle_w=0.42, muzzle_h=0.4,
                  coat="#2a2a2e", ears="round", ear_size=70,
                  ear_colour="#44444c", legs="knuckle", croup=0.7,
                  front_lean=-0.1, leg_r=[180, 140, 105, 90, 95],
                  hind_r=[150, 110, 80, 70, 85], eyes_side=0.05,
                  eye_r=26, nose="#141416", feet_colour="#3a3a40",
                  extras=[pale("#4a4a52", "chest"),
                          pale("#4a4a52", "muzzle"), brow("#2a2a2e")]),
    "Crocodile": dict(name="Crocodile", plan=crocodile, L=4000,
                      coat="#56613a", scute="#3d4628"),
    "Python": dict(name="Python", plan=snake, L=3000, r=55,
                   coat="#b99a62", pattern="#5a4028"),
}


def build(name, dims=None):
    from . import scadparse
    from .model import CadNode
    spec = SPECIES[name]
    body = spec["plan"](spec)
    root, _warnings = scadparse.parse_scad(body.program())
    group = CadNode("union", name)
    for child in list(root.children):
        group.add(child)
    return _on_ground(group)


def _on_ground(group):
    """*group* lifted so its lowest point is z = 0: a smooth blend
    bulges a little past its primitives, so a belly or a coil that
    touches the ground in the plan dips under it in the mesh."""
    from . import mesh
    from .model import CadNode
    tris = mesh.tessellate(group, fn=12)
    low = min((v[2] for t in tris for v in t), default=0.0)
    if abs(low) < 1e-6:
        return group
    lift = CadNode("translate", group.name, dict(x=0.0, y=0.0, z=-low))
    lift.add(group)
    wrap = CadNode("union", group.name)
    wrap.add(lift)
    return wrap


def _slug(name):
    return "animal_" + "".join(c if c.isalnum() else "_"
                               for c in name.lower()).strip("_")


PARTS = {_slug(name): dict(label=name, category=CATEGORY,
                           sizes={"Life size": {}}, fields=[],
                           build=lambda dims, n=name: build(n, dims))
         for name in SPECIES}
