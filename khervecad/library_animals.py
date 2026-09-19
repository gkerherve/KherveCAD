"""Cartoon animals for the parts library (2026-09-19, the user's request:
"the nicest cutest animals"): 28 chibi toys — Library ▸ Toys & models ▸
Animals ▸ Cartoon animals.

One style for all of them, like a set of vinyl toys: a head as big as
the body, huge glossy eyes (white, a big dark pupil, two highlights),
rosy cheeks, a small smile, a round body and stubby legs. The body,
legs, neck and tail are ONE `blend` (a smooth union), so the toy reads
as a soft moulded figure instead of stacked balls; the head is its own
smooth shape, and everything with another colour — muzzle, belly,
inner ears, spots, stripes, mane, hooves, horns — sits on top as
ordinary coloured solids. About 12 cm tall, facing -Y, standing on
z = 0.

Every species is a parameter set (`SPECIES`) handed to one of a few
body plans: `quadruped` (dog, cat, horse, cow, pig, sheep, tiger, lion,
donkey, zebra, fox, bear, panda, elephant, giraffe, hippo, rabbit,
mouse, koala), `sitter` (gorilla, monkey), `bird` (duck, chicken, owl,
penguin), and the snake, frog, turtle and crocodile.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

CATEGORY = "Cartoon animals"

WHITE = "#fbfaf6"
PUPIL = "#1c1a1f"
BLUSH = "#f59ab2"
NOSE = "#2a2326"
PINK = "#f4b6c2"


def _f(v):
    return f"{v:.2f}"


def _v(p):
    return "[" + ", ".join(_f(c) for c in p) + "]"


def _norm(d):
    n = math.sqrt(sum(c * c for c in d)) or 1.0
    return [c / n for c in d]


def _add(a, b, k=1.0):
    return [a[i] + b[i] * k for i in range(3)]


def on_ellipsoid(c, r, d):
    """The point of the ellipsoid (centre *c*, radii *r*) in direction
    *d* from its centre, and the outward normal there."""
    d = _norm(d)
    t = 1.0 / math.sqrt(sum((d[i] / r[i]) ** 2 for i in range(3)))
    p = [c[i] + d[i] * t for i in range(3)]
    n = _norm([(p[i] - c[i]) / r[i] ** 2 for i in range(3)])
    return p, n


def _segments(r):
    """Round segments for a detail *r* mm across: a highlight needs few,
    a head more — 48 everywhere made a toy 150k triangles."""
    return 12 if r < 3 else 16 if r < 6 else 24 if r < 12 else 36


class Toy:
    """OpenSCAD statements for one toy, grouped by colour."""

    def __init__(self, name):
        self.name = name
        self.lines = []

    # primitives (no colour: for a blend)
    @staticmethod
    def ell(c, r):
        return (f"kcad_ellipsoid(c = {_v(c)}, r = {_v(r)}, "
                f"$fn = {_segments(max(r))});")

    @staticmethod
    def sph(c, r):
        return (f"kcad_ellipsoid(c = {_v(c)}, r = {_v([r, r, r])}, "
                f"$fn = {_segments(r)});")

    @staticmethod
    def cap(a, b, r):
        a = [a[0], a[1], max(a[2], r)]            # never below the ground
        b = [b[0], b[1], max(b[2], r)]
        return (f"kcad_capsule(a = {_v(a)}, b = {_v(b)}, r = {_f(r)}, "
                f"$fn = {_segments(r)});")

    @staticmethod
    def cone(base, tip, r0, r1=0.3):
        d = [tip[i] - base[i] for i in range(3)]
        length = math.sqrt(sum(c * c for c in d)) or 1.0
        tilt = math.degrees(math.acos(max(-1.0, min(1.0, d[2] / length))))
        turn = math.degrees(math.atan2(d[1], d[0]))
        return (f"translate({_v(base)}) rotate([0, {_f(tilt)}, {_f(turn)}]) "
                f"cylinder(h = {_f(length)}, r1 = {_f(r0)}, r2 = {_f(r1)}, "
                f"$fn = {_segments(r0)});")

    def put(self, colour, label, *pieces, material="Plastic"):
        body = " ".join(pieces)
        self.lines.append(f'kcad_material("{material}") color("{colour}") '
                          f"union() {{ {body} }}  // {label}")

    def blend(self, colour, label, radius, pieces, detail=40,
              material="Plastic"):
        body = " ".join(pieces)
        self.lines.append(
            f'kcad_material("{material}") color("{colour}") '
            f"kcad_blend(radius = {_f(radius)}, detail = {detail}) "
            f"{{ {body} }}  // {label}")

    # faces
    def eyes(self, c, r, size, spread=0.42, up=0.16, look=(0.0, 0.0),
             lids=None):
        """Two glossy eyes on the head ellipsoid (*c*, *r*)."""
        for sx in (1, -1):
            d = [sx * spread + look[0], -0.86, up + look[1]]
            p, n = on_ellipsoid(c, r, d)
            e = _add(p, n, -size * 0.25)
            self.put(WHITE, "Eye white", self.ell(
                e, [size * 0.95, size * 0.6, size * 1.1]))
            pupil = _add(e, n, size * 0.42)
            pupil[2] -= size * 0.08
            self.put(PUPIL, "Pupil", self.ell(
                pupil, [size * 0.72, size * 0.36, size * 0.82]),
                material="Glass")
            glint = _add(pupil, n, size * 0.3)
            glint = [glint[0] - sx * size * 0.24, glint[1],
                     glint[2] + size * 0.32]
            self.put(WHITE, "Highlight", self.sph(glint, size * 0.26),
                     material="Emissive")
            small = [pupil[0] + sx * size * 0.2, glint[1],
                     pupil[2] - size * 0.28]
            self.put(WHITE, "Highlight", self.sph(small, size * 0.11),
                     material="Emissive")
            if lids:
                top = _add(e, [0, 0, 1], size * 0.55)
                self.put(lids, "Eyelid", self.ell(
                    top, [size * 1.02, size * 0.64, size * 0.55]))

    def cheeks(self, c, r, size, spread=0.62, down=-0.12):
        for sx in (1, -1):
            p, n = on_ellipsoid(c, r, [sx * spread, -0.72, down])
            self.put(BLUSH, "Cheek", self.ell(_add(p, n, -size * 0.2),
                                              [size, size * 0.35,
                                               size * 0.62]),
                     material="Matte")

    def smile(self, at, width, colour=NOSE):
        mid = [at[0], at[1] - 0.3, at[2] - width * 0.25]
        for sx in (1, -1):
            end = [at[0] + sx * width, at[1], at[2]]
            self.put(colour, "Smile", self.cap(mid, end, width * 0.14))

    def program(self):
        return "\n".join(self.lines)


# -------------------------------------------------------------- parts
def _ears(t, kind, head_c, head_r, colour, inner, size):
    hc, hr = head_c, head_r
    for sx in (1, -1):
        if kind == "pointy":                     # cat, fox, tiger, horse
            base, n = on_ellipsoid(hc, hr, [sx * 0.55, 0.05, 0.84])
            tip = _add(base, [sx * 0.35, 0.1, 1.0], size * 1.5)
            t.put(colour, "Ear", t.cone(_add(base, n, -size * 0.3), tip,
                                        size * 0.75, size * 0.12))
            if inner:
                t.put(inner, "Inner ear", t.cone(
                    _add(base, [0, -1, 0], size * 0.25),
                    _add(tip, [0, -1, -0.6], size * 0.35),
                    size * 0.48, 0.2))
        elif kind == "round":                    # bear, panda, mouse, lion
            p, n = on_ellipsoid(hc, hr, [sx * 0.62, 0.05, 0.78])
            c = _add(p, n, size * 0.35)
            t.put(colour, "Ear", t.ell(c, [size, size * 0.5, size]))
            if inner:
                t.put(inner, "Inner ear", t.ell(
                    _add(c, [0, -1, 0], size * 0.32),
                    [size * 0.62, size * 0.22, size * 0.62]))
        elif kind == "floppy":                   # dog
            p, n = on_ellipsoid(hc, hr, [sx * 0.8, 0.05, 0.45])
            lo = _add(p, [sx * 0.35, -0.05, -1.0], size * 1.5)
            t.put(colour, "Ear", t.cap(p, lo, size * 0.62))
        elif kind == "long":                     # rabbit, donkey
            p, n = on_ellipsoid(hc, hr, [sx * 0.32, 0.1, 0.94])
            tip = _add(p, [sx * 0.28, 0.12, 1.0], size * 2.6)
            t.put(colour, "Ear", t.ell([(p[i] + tip[i]) / 2 for i in range(3)],
                                       [size * 0.62, size * 0.36,
                                        size * 1.45]))
            if inner:
                mid = [(p[i] + tip[i]) / 2 for i in range(3)]
                t.put(inner, "Inner ear", t.ell(
                    _add(mid, [0, -1, 0], size * 0.22),
                    [size * 0.36, size * 0.2, size * 1.15]))
        elif kind == "side":                     # cow, pig, sheep, hippo
            p, n = on_ellipsoid(hc, hr, [sx * 0.92, 0.1, 0.35])
            c = _add(p, [sx, 0.1, 0.15], size * 0.7)
            t.put(colour, "Ear", t.ell(c, [size, size * 0.4, size * 0.55]))
            if inner:
                t.put(inner, "Inner ear", t.ell(
                    _add(c, [0, -1, 0], size * 0.2),
                    [size * 0.66, size * 0.22, size * 0.34]))
        elif kind == "elephant":
            p, n = on_ellipsoid(hc, hr, [sx * 0.9, 0.2, 0.15])
            c = _add(p, [sx * 0.6, 0.35, 0.0], size * 0.9)
            t.put(colour, "Ear", t.ell(c, [size * 0.45, size * 1.25,
                                           size * 1.45]))
            if inner:
                t.put(inner, "Inner ear", t.ell(
                    _add(c, [0, -1, 0], size * 0.3),
                    [size * 0.3, size * 0.9, size * 1.05]))


def _tail(t, kind, root, colour, size, tip=None):
    if kind == "curly":                          # pig
        pts = []
        for k in range(9):
            a = k * 0.8
            pts.append([root[0] + math.sin(a) * size * 0.45,
                        root[1] + size * 0.3 + k * size * 0.1,
                        root[2] + math.cos(a) * size * 0.45])
        t.put(colour, "Tail", *[t.cap(pts[i], pts[i + 1], size * 0.16)
                                for i in range(len(pts) - 1)])
    elif kind == "puff":                         # rabbit, sheep
        t.put(tip or colour, "Tail", t.sph(_add(root, [0, 1, 0.3],
                                                size * 0.4), size * 0.6))
    elif kind == "bushy":                        # fox
        mid = _add(root, [0, 1.1, 0.9], size * 1.2)
        end = _add(root, [0, 2.0, 1.6], size * 1.3)
        t.put(colour, "Tail", t.ell(mid, [size * 0.62, size * 1.1,
                                          size * 0.7]))
        t.put(tip or WHITE, "Tail tip", t.ell(end, [size * 0.45,
                                                    size * 0.55,
                                                    size * 0.45]))
    elif kind in ("tuft", "long"):               # lion, cow, cat, monkey
        a = root
        b = _add(root, [0, 1.0, 0.25], size * 1.4)
        c = _add(root, [0, 1.3, 1.6], size * 1.6)
        t.put(colour, "Tail", t.cap(a, b, size * 0.16),
              t.cap(b, c, size * 0.16))
        if kind == "tuft":
            t.put(tip or colour, "Tail tuft", t.sph(c, size * 0.36))
    elif kind == "stub":
        t.put(colour, "Tail", t.sph(_add(root, [0, 1, 0.2], size * 0.2),
                                    size * 0.3))


def quadruped(p):
    """A four-legged toy from a species' parameters."""
    t = Toy(p["name"])
    s = p.get("scale", 1.0)
    bw, bl, bh = [v * s for v in p.get("body", (22, 30, 20))]
    leg_h = p.get("leg", 14) * s
    leg_r = p.get("leg_r", 7.5) * s
    cz = leg_h + bh * 0.72
    body_c = [0, 0, cz]
    hr = [v * s for v in p.get("head", (25, 22, 23))]
    neck = p.get("neck", 0.0) * s
    head_c = [0, -bl * 0.78 - p.get("head_ahead", 0.0) * s,
              cz + bh * 0.75 + hr[2] * 0.55 + neck]
    main, belly = p["colour"], p.get("belly")
    pieces = [t.ell(body_c, [bw, bl, bh])]
    feet = []
    for sx in (1, -1):
        for sy in (-1, 1):
            top = [sx * bw * 0.52, sy * bl * 0.55, cz - bh * 0.2]
            foot = [sx * bw * 0.56, sy * bl * 0.58, leg_r * 0.9]
            pieces.append(t.cap(top, foot, leg_r))
            feet.append(foot)
    if neck > 0:
        pieces.append(t.cap([0, -bl * 0.62, cz + bh * 0.3],
                            [0, head_c[1] + hr[1] * 0.2, head_c[2] - hr[2] * 0.4],
                            p.get("neck_r", 8.0) * s))
    t.blend(main, "Body", 5.0 * s, pieces)
    t.blend(main, "Head", 3.0 * s, [t.ell(head_c, hr)] + [
        t.ell(_add(head_c, [0, -hr[1] * 0.45, -hr[2] * 0.35]),
              [v * s for v in p["snout_shape"]])] if p.get("snout_shape")
        else [t.ell(head_c, hr)])
    if belly:
        bp, bn = on_ellipsoid(body_c, [bw, bl, bh], [0, -0.35, -0.94])
        t.put(belly, "Belly", t.ell(_add(bp, bn, -bh * 0.35),
                                    [bw * 0.72, bl * 0.72, bh * 0.45]),
              material="Matte")
        cp, cn = on_ellipsoid(body_c, [bw, bl, bh], [0, -0.95, 0.1])
        if p.get("chest", True):
            t.put(belly, "Chest", t.ell(_add(cp, cn, -bw * 0.2),
                                        [bw * 0.55, bw * 0.3, bh * 0.55]),
                  material="Matte")
    hoof = p.get("hoof")
    for foot in feet:
        if hoof:
            base = [foot[0], foot[1], leg_r * 1.06]
            t.put(hoof, "Hoof", t.cap(base, _add(base, [0, 0, leg_r * 0.3]),
                                      leg_r * 1.06))
        elif p.get("paws", True):
            t.put(p.get("paw", belly or main), "Paw", t.ell(
                _add(foot, [0, -leg_r * 0.45, -leg_r * 0.25]),
                [leg_r * 0.8, leg_r * 0.55, leg_r * 0.45]), material="Matte")
    # face
    muzzle = p.get("muzzle")
    mz_c = None
    snout = p.get("snout_shape")
    face_c, face_r = head_c, hr
    if snout:
        face_c = _add(head_c, [0, -hr[1] * 0.45, -hr[2] * 0.35])
        face_r = [v * s for v in snout]
    if muzzle:
        mp, mn = on_ellipsoid(face_c, face_r, [0, -0.93, -0.38])
        mr = [v * s for v in muzzle]
        mz_c = _add(mp, mn, -mr[1] * 0.35)
        t.put(p.get("muzzle_colour", belly or WHITE), "Muzzle",
              t.ell(mz_c, mr), material="Matte")
        np_, nn = on_ellipsoid(mz_c, mr, [0, -0.8, 0.55])
        nose = p.get("nose", NOSE)
        if p.get("nostrils"):
            for sx in (1, -1):
                t.put(nose, "Nostril", t.ell(_add(np_, [sx * mr[0] * 0.38,
                                                         0, -mr[2] * 0.2]),
                                             [mr[0] * 0.14, mr[1] * 0.12,
                                              mr[2] * 0.2]))
        else:
            t.put(nose, "Nose", t.ell(_add(np_, nn, -0.4 * s),
                                      [3.8 * s, 2.6 * s, 2.8 * s]),
                  material="Glass")
            sp, _sn = on_ellipsoid(mz_c, mr, [0, -0.85, -0.45])
            t.smile(sp, 3.0 * s)
    t.eyes(head_c, hr, p.get("eye", 6.4) * s, spread=p.get("eye_spread",
                                                            0.42),
           up=p.get("eye_up", 0.14), lids=p.get("lids"))
    t.cheeks(head_c, hr, 4.2 * s)
    if p.get("ears"):
        _ears(t, p["ears"], head_c, hr, p.get("ear_colour", main),
              p.get("inner_ear", PINK), p.get("ear_size", 8.0) * s)
    if p.get("tail"):
        _tail(t, p["tail"], [0, bl * 0.9, cz + bh * 0.2],
              p.get("tail_colour", main), 9.0 * s, p.get("tail_tip"))
    for extra in p.get("extras", ()):
        extra(t, dict(body_c=body_c, body_r=[bw, bl, bh], head_c=head_c,
                      head_r=hr, cz=cz, leg_h=leg_h, s=s, muzzle=mz_c,
                      feet=feet, leg_r=leg_r))
    return t


# ------------------------------------------------------------ extras
def spots(colour, count=7, size=6.0, seed=3, on="body"):
    def draw(t, g):
        import random
        rnd = random.Random(seed)
        c = g["body_c"] if on == "body" else g["head_c"]
        r = g["body_r"] if on == "body" else g["head_r"]
        for _ in range(count):
            d = [rnd.uniform(-1, 1), rnd.uniform(-0.9, 0.9),
                 rnd.uniform(-0.1, 1)]
            p, n = on_ellipsoid(c, r, d)
            k = rnd.uniform(0.7, 1.25) * size * g["s"]
            t.put(colour, "Spot", t.ell(_add(p, n, -k * 0.25),
                                        [k, k * 0.9, k * 0.8]),
                  material="Matte")
    return draw


def stripes(colour, count=6, width=2.0):
    """Curved stripes wrapping over the back (tiger, zebra)."""
    def draw(t, g):
        c, r = g["body_c"], g["body_r"]
        for k in range(count):
            y = -0.7 + 1.4 * k / max(count - 1, 1)
            arc = []
            for j in range(7):
                a = math.radians(-80 + j * 26.7)
                p, n = on_ellipsoid(c, r, [math.sin(a), y, math.cos(a)])
                arc.append(_add(p, n, -width * 0.3 * g["s"]))
            t.put(colour, "Stripe", *[t.cap(arc[i], arc[i + 1],
                                            width * g["s"])
                                      for i in range(len(arc) - 1)])
        hc, hr = g["head_c"], g["head_r"]
        for sx in (1, -1):
            for k in range(2):
                a = [sx * (0.8 - k * 0.12), 0.1, 0.35 + k * 0.25]
                p, n = on_ellipsoid(hc, hr, a)
                q, _m = on_ellipsoid(hc, hr, [sx * (0.95 - k * 0.1), -0.25,
                                              0.25 + k * 0.25])
                t.put(colour, "Face stripe", t.cap(_add(p, n, -0.5),
                                                   _add(q, n, -0.5),
                                                   width * 0.8 * g["s"]))
    return draw


def mane(colour, kind="lion"):
    def draw(t, g):
        hc, hr, s = g["head_c"], g["head_r"], g["s"]
        if kind == "lion":
            pieces = []
            for k in range(14):
                a = 2 * math.pi * k / 14
                d = [math.cos(a), 0.35, math.sin(a)]
                p, n = on_ellipsoid(hc, hr, d)
                pieces.append(t.sph(_add(p, n, 2.0 * s), 9.0 * s))
            t.blend(colour, "Mane", 4.0 * s, pieces)
        else:                                    # horse / zebra: a crest
            pts = []
            top_front, _n = on_ellipsoid(hc, hr, [0, 0.2, 1])
            back = [0, -g["body_r"][1] * 0.45, g["cz"] + g["body_r"][2] * 0.9]
            for k in range(6):
                f = k / 5.0
                pts.append([0, top_front[1] + (back[1] - top_front[1]) * f,
                            top_front[2] + (back[2] - top_front[2]) * f
                            + 3 * s])
            t.put(colour, "Mane", *[t.cap(pts[i], pts[i + 1], 3.2 * s)
                                    for i in range(len(pts) - 1)])
            fp, fn = on_ellipsoid(hc, hr, [0, -0.6, 0.85])
            t.put(colour, "Forelock", t.ell(_add(fp, fn, 1.5 * s),
                                            [5 * s, 3 * s, 4 * s]))
    return draw


def horns(colour, kind="cow"):
    def draw(t, g):
        hc, hr, s = g["head_c"], g["head_r"], g["s"]
        for sx in (1, -1):
            p, n = on_ellipsoid(hc, hr, [sx * 0.55, 0.1, 0.85])
            if kind == "cow":
                tip = _add(p, [sx * 0.9, 0.0, 0.6], 9 * s)
                t.put(colour, "Horn", t.cone(p, tip, 3.0 * s, 0.8 * s))
            elif kind == "giraffe":
                tip = _add(p, [sx * 0.15, 0.1, 1.0], 8 * s)
                t.put(colour, "Ossicone", t.cap(p, tip, 1.8 * s),
                      t.sph(tip, 2.8 * s))
            else:                                # sheep: curled
                pts = []
                for k in range(8):
                    a = k * 0.7
                    pts.append([p[0] + sx * (4 + 3 * math.sin(a)) * s,
                                p[1] + 3 * math.cos(a) * s + k * 0.6 * s,
                                p[2] - k * 1.1 * s])
                t.put(colour, "Horn", *[t.cap(pts[i], pts[i + 1], 2.4 * s)
                                        for i in range(len(pts) - 1)])
    return draw


def patch_eyes(colour):
    """Panda eye patches under the eyes."""
    def draw(t, g):
        hc, hr, s = g["head_c"], g["head_r"], g["s"]
        for sx in (1, -1):
            p, n = on_ellipsoid(hc, hr, [sx * 0.45, -0.86, 0.1])
            t.put(colour, "Eye patch", t.ell(_add(p, n, -2.8 * s),
                                             [7.5 * s, 3.2 * s, 9.5 * s]),
                  material="Matte")
    return draw


def panda_limbs(colour):
    def draw(t, g):
        for foot in g["feet"]:
            top = [foot[0], foot[1], g["cz"] - g["body_r"][2] * 0.1]
            t.put(colour, "Limb", t.cap(top, foot, g["leg_r"] * 1.06),
                  material="Matte")
        c, r = g["body_c"], g["body_r"]
        p, n = on_ellipsoid(c, r, [0, -0.55, 0.8])
        t.put(colour, "Shoulders", t.ell(_add(p, n, -r[2] * 0.2),
                                         [r[0] * 1.02, r[1] * 0.28,
                                          r[2] * 0.4]), material="Matte")
    return draw


def trunk(colour):
    def draw(t, g):
        s, m = g["s"], g["head_c"]
        hr = g["head_r"]
        p, n = on_ellipsoid(m, hr, [0, -0.9, -0.3])
        pts = [p, _add(p, [0, -1, -0.6], 7 * s), _add(p, [0, -1.2, -1.6], 11 * s),
               _add(p, [0, -1.9, -1.8], 13 * s)]
        radii = [7 * s, 6 * s, 5 * s, 4.5 * s]
        t.blend(colour, "Trunk", 2.0 * s, [t.cap(pts[i], pts[i + 1],
                                                  radii[i])
                                            for i in range(3)])
        for sx in (1, -1):
            q, qn = on_ellipsoid(m, hr, [sx * 0.45, -0.85, -0.45])
            t.put(WHITE, "Tusk", t.cone(_add(q, qn, -1), _add(q, [sx * 0.2, -1, 0.3], 8 * s),
                                        2.0 * s, 0.6 * s))
    return draw


def giraffe_spots(colour):
    return spots(colour, count=14, size=5.0, seed=11)


def pig_snout(colour, nostril):
    def draw(t, g):
        s = g["s"]
        p, n = on_ellipsoid(g["head_c"], g["head_r"], [0, -1, -0.25])
        c = _add(p, n, 2.0 * s)
        t.put(colour, "Snout", f"translate({_v(c)}) rotate([90, 0, 0]) "
              f"scale([1, 0.78, 1]) cylinder(h = {_f(5 * s)}, r = {_f(7.5 * s)}, "
              f"center = true);")
        for sx in (1, -1):
            t.put(nostril, "Nostril", t.ell(_add(c, [sx * 3 * s, -2.6 * s, 0]),
                                            [1.4 * s, 0.8 * s, 2.2 * s]))
        sp, _sn = on_ellipsoid(g["head_c"], g["head_r"], [0, -0.9, -0.62])
        t.smile(sp, 3.2 * s)
    return draw


def wool(colour):
    def draw(t, g):
        import random
        rnd = random.Random(5)
        c, r, s = g["body_c"], g["body_r"], g["s"]
        pieces = []
        pieces.append(t.ell(c, [r[0] * 1.05, r[1] * 1.05, r[2] * 1.05]))
        for _ in range(40):
            d = [rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.45, 1)]
            p, n = on_ellipsoid(c, r, d)
            pieces.append(t.sph(_add(p, n, 1.5 * s), rnd.uniform(7, 9.5) * s))
        t.blend(colour, "Wool", 2.5 * s, pieces)
        hp, hn = on_ellipsoid(g["head_c"], g["head_r"], [0, 0.1, 1])
        t.put(colour, "Wool tuft", t.sph(_add(hp, hn, 1 * s), 8 * s))
    return draw


def whiskers(colour="#6b6570"):
    def draw(t, g):
        if g["muzzle"] is None:
            return
        s, m = g["s"], g["muzzle"]
        for sx in (1, -1):
            for k in (-1, 0, 1):
                a = _add(m, [sx * 5 * s, -3 * s, k * 1.6 * s])
                b = _add(a, [sx * 12 * s, -1 * s, k * 2.8 * s])
                t.put(colour, "Whisker", t.cap(a, b, 0.35 * s))
    return draw


# --------------------------------------------------------- body plans
def sitter(p):
    """A sitting ape: round body, big head, long arms resting on the
    ground, legs folded in front."""
    t = Toy(p["name"])
    s = p.get("scale", 1.0)
    main, face = p["colour"], p["face"]
    body_c = [0, 0, 26 * s]
    body_r = [24 * s, 20 * s, 26 * s]
    head_c = [0, -6 * s, 64 * s]
    head_r = [22 * s, 20 * s, 20 * s]
    pieces = [t.ell(body_c, body_r)]
    for sx in (1, -1):
        sh = [sx * 20 * s, -4 * s, 40 * s]
        hand = [sx * 26 * s, -18 * s, 6 * s]
        pieces.append(t.cap(sh, hand, 7.5 * s))
        knee = [sx * 12 * s, -20 * s, 12 * s]
        pieces.append(t.cap([sx * 12 * s, -2 * s, 8 * s], knee, 8 * s))
        pieces.append(t.cap(knee, [sx * 10 * s, -28 * s, 5 * s], 6 * s))
    t.blend(main, "Body", 5 * s, pieces)
    t.blend(main, "Head", 3 * s, [t.ell(head_c, head_r)] + (
        [t.sph([0, -4 * s, 80 * s], 12 * s)] if p.get("crest") else []))
    fp, fn = on_ellipsoid(head_c, head_r, [0, -1, -0.15])
    t.put(face, "Face", t.ell(_add(fp, fn, -0.8 * s), [15 * s, 6 * s,
                                                        14 * s]),
          material="Matte")
    mp, mn = on_ellipsoid(head_c, head_r, [0, -0.9, -0.55])
    t.put(face, "Muzzle", t.ell(_add(mp, mn, -1 * s), [11 * s, 7 * s,
                                                        7 * s]),
          material="Matte")
    np_, _nn = on_ellipsoid(_add(mp, mn, -1 * s), [11 * s, 7 * s, 7 * s],
                            [0, -0.8, 0.5])
    for sx in (1, -1):
        t.put(NOSE, "Nostril", t.ell(_add(np_, [sx * 2.4 * s, 0, 0]),
                                     [1.4 * s, 1 * s, 1.1 * s]))
    sp, _sn = on_ellipsoid(_add(mp, mn, -1 * s), [11 * s, 7 * s, 7 * s],
                           [0, -0.85, -0.45])
    t.smile(sp, 3.5 * s)
    face_r = [head_r[0] + 3 * s, head_r[1] + 4.5 * s, head_r[2] + 1 * s]
    t.eyes(head_c, face_r, 6.2 * s, spread=0.36, up=0.2)
    t.cheeks(head_c, face_r, 3.6 * s, spread=0.66)
    bp, bn = on_ellipsoid(body_c, body_r, [0, -1, 0])
    t.put(face, "Chest", t.ell(_add(bp, bn, -2.5 * s), [15 * s, 6 * s,
                                                         18 * s]),
          material="Matte")
    for sx in (1, -1):
        ep, en = on_ellipsoid(head_c, head_r, [sx, 0.05, 0.1])
        t.put(face if p.get("face_ears") else main, "Ear",
              t.ell(_add(ep, en, 1.5 * s), [4 * s, 3 * s, 5.5 * s]))
    if p.get("tail"):
        _tail(t, "long", [0, 18 * s, 10 * s], main, 9 * s)
    return t


def bird(p):
    t = Toy(p["name"])
    s = p.get("scale", 1.0)
    main, belly = p["colour"], p.get("belly")
    upright = p.get("upright", False)
    body_c = [0, 0, 30 * s] if not upright else [0, 0, 36 * s]
    body_r = [22 * s, 26 * s, 22 * s] if not upright else \
        [24 * s, 20 * s, 32 * s]
    head_c = [0, -14 * s, 62 * s] if not upright else [0, -3 * s, 76 * s]
    head_r = [18 * s, 17 * s, 17 * s]
    if p.get("owl"):
        head_c, head_r = [0, -3 * s, 64 * s], [24 * s, 20 * s, 21 * s]
    t.blend(main, "Body", 5 * s, [t.ell(body_c, body_r),
                                  t.ell(head_c, head_r)])
    if belly:
        bp, bn = on_ellipsoid(body_c, body_r, [0, -1, -0.2])
        t.put(belly, "Belly", t.ell(_add(bp, bn, -body_r[1] * 0.3),
                                    [body_r[0] * 0.75, body_r[1] * 0.45,
                                     body_r[2] * 0.75]), material="Matte")
    for sx in (1, -1):
        wp, wn = on_ellipsoid(body_c, body_r, [sx, 0.15, 0.1])
        t.put(p.get("wing", main), "Wing", t.ell(
            _add(wp, wn, -3 * s), [5 * s, body_r[1] * 0.75,
                                   body_r[2] * 0.62]))
        foot = [sx * 9 * s, -8 * s, 1.5 * s]
        t.put(p.get("feet", "#f39c12"), "Foot", t.ell(
            foot, [7 * s, 8 * s, 2 * s]), t.cap(
            [sx * 9 * s, -2 * s, 3 * s],
            [sx * 9 * s, 0, body_c[2] - body_r[2] * 0.7], 2 * s))
    beak = p.get("beak", "#f39c12")
    bp, bn = on_ellipsoid(head_c, head_r, [0, -1, -0.2])
    if p.get("flat_beak"):                       # duck
        t.put(beak, "Beak", t.ell(_add(bp, bn, 3 * s), [9 * s, 8 * s,
                                                         3.2 * s]))
    else:
        t.put(beak, "Beak", t.cone(_add(bp, bn, -2 * s),
                                   _add(bp, [0, -1, -0.3], 8 * s),
                                   4.5 * s, 0.5 * s))
    t.eyes(head_c, head_r, (7.5 if p.get("owl") else 5.8) * s,
           spread=0.4 if p.get("owl") else 0.44, up=0.2)
    t.cheeks(head_c, head_r, 3.2 * s)
    if p.get("comb"):
        tp, tn = on_ellipsoid(head_c, head_r, [0, -0.2, 1])
        t.put("#e74c3c", "Comb", *[t.sph(_add(tp, [0, k * 3.5 * s, 1.5 * s]),
                                         3.4 * s) for k in (-1, 0, 1)])
        wp, wn = on_ellipsoid(head_c, head_r, [0, -0.8, -0.8])
        t.put("#e74c3c", "Wattle", t.ell(_add(wp, wn, 0.5 * s),
                                         [2.5 * s, 2 * s, 4 * s]))
    if p.get("owl"):
        for sx in (1, -1):
            ep, en = on_ellipsoid(head_c, head_r, [sx * 0.6, 0.1, 0.8])
            t.put(main, "Ear tuft", t.cone(ep, _add(ep, [sx * 0.4, 0, 1], 9 * s),
                                           4.5 * s, 0.5 * s))
            fp, fn = on_ellipsoid(head_c, head_r, [sx * 0.42, -0.86, 0.2])
            t.put(p.get("disc", belly or WHITE), "Face disc",
                  t.ell(_add(fp, fn, -4 * s), [9 * s, 3 * s, 9.5 * s]),
                  material="Matte")
    if p.get("tail_feathers"):
        tp_ = [0, body_r[1] * 0.9, body_c[2] + 6 * s]
        t.put(p.get("tail_feathers"), "Tail", t.ell(
            _add(tp_, [0, 4 * s, 6 * s]), [7 * s, 5 * s, 10 * s]))
    return t


def snake(p):
    t = Toy(p["name"])
    s = p.get("scale", 1.0)
    main, belly = p["colour"], p.get("belly", "#f7e27e")
    pts = []
    for k in range(40):
        a = k * 0.23
        rad = (34 - k * 0.5) * s
        pts.append([math.cos(a) * rad, math.sin(a) * rad,
                    8 * s + k * 0.55 * s])
    radii = [max(8.5 * s - k * 0.12 * s, 3.2 * s) for k in range(40)]
    t.blend(main, "Coils", 3 * s, [t.cap(pts[i], pts[i + 1], radii[i])
                                  for i in range(len(pts) - 1)])
    for k in range(2, 38, 5):
        t.put(p.get("band", "#2e7d32"), "Band", t.sph(
            _add(pts[k], [0, 0, radii[k] * 0.5]), radii[k] * 0.62))
    top = pts[0]
    neck = [top[0] * 0.3, top[1] * 0.3 - 10 * s, 22 * s]
    head_c = [neck[0], neck[1] - 8 * s, 42 * s]
    head_r = [15 * s, 17 * s, 13 * s]
    t.blend(main, "Neck", 4 * s, [t.cap(top, neck, 8 * s),
                                  t.cap(neck, head_c, 7.5 * s),
                                  t.ell(head_c, head_r)])
    t.eyes(head_c, head_r, 5.8 * s, spread=0.48, up=0.3)
    t.cheeks(head_c, head_r, 3 * s)
    sp, _sn = on_ellipsoid(head_c, head_r, [0, -0.92, -0.35])
    t.smile(sp, 3.5 * s)
    tp, _tn = on_ellipsoid(head_c, head_r, [0, -1, -0.5])
    t.put("#e74c3c", "Tongue", t.cap(tp, _add(tp, [0, -1, -0.3], 6 * s),
                                     0.9 * s),
          t.cap(_add(tp, [0, -1, -0.3], 6 * s),
                _add(tp, [1.5, -8, -3], s), 0.7 * s),
          t.cap(_add(tp, [0, -1, -0.3], 6 * s),
                _add(tp, [-1.5, -8, -3], s), 0.7 * s))
    return t


def frog(p):
    t = Toy(p["name"])
    s = p.get("scale", 1.0)
    main, belly = p["colour"], p.get("belly", "#e9f7c8")
    body_c, body_r = [0, 0, 22 * s], [27 * s, 26 * s, 20 * s]
    head_c, head_r = [0, -12 * s, 38 * s], [26 * s, 20 * s, 15 * s]
    pieces = [t.ell(body_c, body_r), t.ell(head_c, head_r)]
    for sx in (1, -1):
        pieces.append(t.ell([sx * 24 * s, 10 * s, 10 * s], [10 * s, 16 * s,
                                                              9 * s]))
        pieces.append(t.cap([sx * 14 * s, -14 * s, 16 * s],
                            [sx * 16 * s, -22 * s, 4 * s], 5 * s))
        pieces.append(t.sph([sx * 14 * s, -14 * s, 46 * s], 10 * s))
    t.blend(main, "Body", 5 * s, pieces)
    bp, bn = on_ellipsoid(body_c, body_r, [0, -1, -0.4])
    t.put(belly, "Belly", t.ell(_add(bp, bn, -6 * s), [18 * s, 7 * s,
                                                        12 * s]),
          material="Matte")
    for sx in (1, -1):
        e = [sx * 14 * s, -20 * s, 48 * s]
        t.put(WHITE, "Eye white", t.ell(e, [7 * s, 5 * s, 7.5 * s]))
        t.put(PUPIL, "Pupil", t.ell(_add(e, [0, -3.2 * s, -0.5 * s]),
                                    [5 * s, 2.6 * s, 5.5 * s]),
              material="Glass")
        t.put(WHITE, "Highlight", t.sph(_add(e, [-sx * 1.6 * s, -5.6 * s,
                                                 2.2 * s]), 1.6 * s),
              material="Emissive")
        t.put(BLUSH, "Cheek", t.ell([sx * 19 * s, -27 * s, 32 * s],
                                    [4.5 * s, 1.5 * s, 3 * s]),
              material="Matte")
        for k in (-1, 0, 1):
            t.put(main, "Toe", t.sph([sx * 16 * s + k * 4 * s, -25 * s,
                                      3 * s], 2.6 * s))
    t.smile([0, -31 * s, 33 * s], 9 * s)
    return t


def turtle(p):
    t = Toy(p["name"])
    s = p.get("scale", 1.0)
    skin, shell = p["colour"], p["shell"]
    pieces = [t.ell([0, 0, 14 * s], [26 * s, 30 * s, 10 * s])]
    for sx in (1, -1):
        for sy in (-1, 1):
            pieces.append(t.cap([sx * 20 * s, sy * 18 * s, 12 * s],
                                [sx * 26 * s, sy * 24 * s, 5 * s], 7 * s))
    head_c, head_r = [0, -40 * s, 30 * s], [17 * s, 17 * s, 16 * s]
    pieces.append(t.cap([0, -22 * s, 16 * s], [0, -36 * s, 26 * s], 9 * s))
    t.blend(skin, "Body", 4 * s, pieces)
    t.blend(skin, "Head", 2 * s, [t.ell(head_c, head_r)])
    t.put(shell, "Shell", f"translate({_v([0, 0, 17 * s])}) "
          f"scale([1, 1.15, 0.72]) sphere(r = {_f(28 * s)}, $fn = 36);")
    t.put(p.get("rim", "#8d6e3f"), "Shell rim",
          t.ell([0, 0, 15 * s], [30 * s, 34.5 * s, 4 * s]))
    for k in range(6):
        a = 2 * math.pi * k / 6
        c = [math.cos(a) * 14 * s, math.sin(a) * 16 * s, 34 * s]
        t.put(p.get("scute", "#a5d66f"), "Scute", t.ell(
            c, [7 * s, 7 * s, 3.2 * s]))
    t.put(p.get("scute", "#a5d66f"), "Scute", t.ell([0, 0, 38 * s],
                                                    [8 * s, 8 * s, 2.5 * s]))
    t.eyes(head_c, head_r, 5.5 * s, spread=0.45, up=0.2)
    t.cheeks(head_c, head_r, 3 * s)
    sp, _sn = on_ellipsoid(head_c, head_r, [0, -0.9, -0.4])
    t.smile(sp, 3.5 * s)
    return t


def crocodile(p):
    t = Toy(p["name"])
    s = p.get("scale", 1.0)
    main, belly = p["colour"], p.get("belly", "#dfe8a6")
    pieces = [t.ell([0, 0, 18 * s], [20 * s, 34 * s, 14 * s]),
              t.cap([0, 28 * s, 16 * s], [0, 62 * s, 8 * s], 11 * s),
              t.cap([0, 62 * s, 8 * s], [0, 84 * s, 5 * s], 5 * s)]
    for sx in (1, -1):
        for sy in (-1, 1):
            pieces.append(t.cap([sx * 16 * s, sy * 18 * s, 14 * s],
                                [sx * 24 * s, sy * 20 * s, 4 * s], 5.5 * s))
    t.blend(main, "Body", 4 * s, pieces)
    head_c, head_r = [0, -38 * s, 26 * s], [20 * s, 18 * s, 16 * s]
    t.blend(main, "Head", 3 * s, [t.ell(head_c, head_r), t.ell(
        [0, -58 * s, 16 * s], [13 * s, 20 * s, 7 * s])])
    t.put(belly, "Jaw", t.ell([0, -54 * s, 11 * s], [12 * s, 19 * s,
                                                    4 * s]),
          material="Matte")
    for k in range(-3, 4):
        t.put(WHITE, "Tooth", t.cone([k * 3.2 * s, -66 * s + abs(k) * 1.5 * s,
                                      12 * s],
                                     [k * 3.2 * s, -66 * s + abs(k) * 1.5 * s,
                                      9 * s], 1.3 * s, 0.2))
    for k in range(7):
        y = -16 * s + k * 12 * s
        t.put(p.get("ridge", "#2e7d32"), "Ridge", t.cone(
            [0, y, 30 * s - k * 2.4 * s], [0, y, 36 * s - k * 2.4 * s],
            3.5 * s, 0.4))
    t.eyes(head_c, head_r, 6 * s, spread=0.38, up=0.45)
    t.cheeks(head_c, head_r, 3.2 * s, spread=0.7)
    for sx in (1, -1):
        t.put(NOSE, "Nostril", t.sph([sx * 3 * s, -76 * s, 21 * s], 1.4 * s))
    return t


# ------------------------------------------------------------- species
def _q(name, colour, **kw):
    kw.update(name=name, colour=colour, plan=quadruped)
    return kw


SPECIES = {
    "Dog": _q("Dog", "#d9a066", belly="#f7e7cf", ears="floppy",
              ear_colour="#8b5a2b", muzzle=(10, 8, 7), tail="long",
              extras=[spots("#8b5a2b", count=2, size=8, seed=2)]),
    "Dalmatian": _q("Dalmatian", "#fbfaf6", belly="#fbfaf6", ears="floppy",
                    ear_colour="#2a2326", muzzle=(10, 8, 7), tail="long",
                    extras=[spots("#2a2326", count=12, size=3.5, seed=7)]),
    "Cat": _q("Cat", "#f0a35e", belly="#fff3e2", ears="pointy",
              muzzle=(8, 5.5, 5.5), nose="#f06b8b", tail="long",
              extras=[stripes("#c56d2c", count=4, width=1.8), whiskers()]),
    "Black cat": _q("Black cat", "#35323a", belly="#4a4650", ears="pointy",
                    inner_ear="#f4b6c2", muzzle=(8, 5.5, 5.5),
                    muzzle_colour="#4a4650", nose="#f06b8b", tail="long",
                    extras=[whiskers("#d8d4dc")]),
    "Horse": _q("Horse", "#a86b3c", belly="#c98c56", ears="pointy",
                inner_ear="#6b3f20", ear_size=6, head=(20, 22, 22),
                snout_shape=(14, 16, 12), muzzle=(12, 8, 8),
                muzzle_colour="#e8c8a8", nostrils=True, nose="#6b3f20",
                leg=22, leg_r=6.5, neck=10, hoof="#3b2a20", tail="tuft",
                tail_tip="#3b2a20", extras=[mane("#3b2a20", "horse")],
                chest=False),
    "Donkey": _q("Donkey", "#9a9aa2", belly="#e6e6ea", ears="long",
                 ear_size=6.5, head=(20, 22, 22), snout_shape=(14, 16, 12),
                 muzzle=(12, 8, 8), muzzle_colour="#f1f1f3", nostrils=True,
                 nose="#55525c", leg=18, leg_r=6.5, neck=6, hoof="#3b3a40",
                 tail="tuft", tail_tip="#3b3a40",
                 extras=[mane("#55525c", "horse")], chest=False),
    "Zebra": _q("Zebra", "#fbfaf6", belly="#fbfaf6", ears="pointy",
                inner_ear="#2a2326", ear_size=6, head=(20, 22, 22),
                snout_shape=(14, 16, 12), muzzle=(12, 8, 8),
                muzzle_colour="#2a2326", nostrils=True, nose="#55525c",
                leg=20, leg_r=6.3, neck=8, hoof="#2a2326", tail="tuft",
                tail_tip="#2a2326", chest=False,
                extras=[stripes("#2a2326", count=7, width=2.2),
                        mane("#2a2326", "horse")]),
    "Cow": _q("Cow", "#fbfaf6", belly="#fbfaf6", ears="side",
              ear_colour="#fbfaf6", muzzle=(14, 9, 9),
              muzzle_colour="#f7b6c6", nostrils=True, nose="#b0506b",
              hoof="#4a3b30", tail="tuft", tail_tip="#2a2326", leg=16,
              extras=[spots("#2a2326", count=6, size=8, seed=4),
                      horns("#f7e7cf")]),
    "Pig": _q("Pig", "#f7b6c6", belly="#fbd0da", ears="side",
              ear_colour="#f39cb2", inner_ear="#f7b6c6", body=(24, 28, 21),
              hoof="#d77c95", tail="curly",
              extras=[pig_snout("#f39cb2", "#b0506b")]),
    "Sheep": _q("Sheep", "#3b3740", ears="side", ear_colour="#3b3740",
                inner_ear="#6b6570", muzzle=(10, 7, 7),
                muzzle_colour="#4a4650", nose="#f06b8b", hoof="#2a2326",
                tail="puff", tail_tip="#fbfaf6", leg=13, leg_r=5.5,
                extras=[wool("#fbfaf6")]),
    "Tiger": _q("Tiger", "#f28b30", belly="#fff3e2", ears="round",
                ear_size=6.5, inner_ear="#fff3e2", muzzle=(10, 7, 6.5),
                nose="#f06b8b", tail="long", tail_colour="#f28b30",
                extras=[stripes("#2a2326", count=6, width=2.2),
                        whiskers()]),
    "Lion": _q("Lion", "#f2b84b", belly="#fbe3b0", ears="round",
               ear_size=6.5, inner_ear="#fbe3b0", muzzle=(10, 7, 6.5),
               nose="#8b4a2b", tail="tuft", tail_tip="#a0522d",
               extras=[mane("#b8612a", "lion"), whiskers()]),
    "Fox": _q("Fox", "#ee7b30", belly="#fbfaf6", ears="pointy",
              inner_ear="#2a2326", muzzle=(9, 9, 6), muzzle_colour="#fbfaf6",
              tail="bushy", tail_tip="#fbfaf6", paw="#2a2326"),
    "Bear": _q("Bear", "#8b5a2b", belly="#c69a6a", ears="round",
               inner_ear="#c69a6a", muzzle=(11, 8, 7),
               muzzle_colour="#e0c29a", body=(25, 28, 23), tail="stub"),
    "Panda": _q("Panda", "#fbfaf6", ears="round", ear_colour="#2a2326",
                inner_ear=None, muzzle=(11, 8, 7), body=(25, 28, 23),
                paw="#2a2326", tail="stub",
                extras=[patch_eyes("#2a2326"), panda_limbs("#2a2326")]),
    "Koala": _q("Koala", "#9aa0a8", belly="#e6e8ec", ears="round",
                ear_size=10, inner_ear="#fbfaf6", body=(22, 24, 22),
                nose="#35323a", muzzle=(7, 7, 9), muzzle_colour="#4a4650",
                tail="stub"),
    "Elephant": _q("Elephant", "#9fb3c8", belly="#c3d2e0", ears="elephant",
                   ear_size=11, inner_ear="#f4b6c2", body=(28, 32, 25),
                   head=(26, 23, 25), leg=15, leg_r=9.5,
                   hoof="#c3d2e0", tail="tuft", tail_tip="#6d7f93",
                   extras=[trunk("#9fb3c8")], chest=False),
    "Giraffe": _q("Giraffe", "#f5c451", belly="#fbe7a8", ears="side",
                  ear_size=6, head=(17, 21, 18), snout_shape=(12, 14, 10),
                  muzzle=(10, 7, 7), muzzle_colour="#fbe7a8", nostrils=True,
                  nose="#8b5a2b", leg=30, leg_r=5.5, neck=46, neck_r=8.5,
                  head_ahead=4, hoof="#6b3f20", tail="tuft",
                  tail_tip="#6b3f20", body=(19, 26, 17), chest=False,
                  extras=[giraffe_spots("#b8612a"),
                          horns("#b8612a", "giraffe"),
                          mane("#b8612a", "horse")]),
    "Hippo": _q("Hippo", "#a58fb8", belly="#d6c6e2", ears="round",
                ear_size=5, inner_ear="#f4b6c2", body=(30, 33, 24),
                head=(26, 25, 21), muzzle=(20, 12, 12),
                muzzle_colour="#c6b2d6", nostrils=True, nose="#6b5680",
                leg=11, leg_r=9, tail="stub", eye_up=0.35, chest=False),
    "Rabbit": _q("Rabbit", "#f3efe9", belly="#fbfaf6", ears="long",
                 ear_size=7, inner_ear="#f4b6c2", body=(20, 22, 20),
                 muzzle=(8, 6, 5.5), nose="#f06b8b", leg=10, tail="puff",
                 tail_tip="#fbfaf6", extras=[whiskers("#b8b2bc")]),
    "Mouse": _q("Mouse", "#b8b2bc", belly="#f3efe9", ears="round",
                ear_size=11, inner_ear="#f4b6c2", body=(18, 22, 17),
                head=(22, 20, 20), muzzle=(7, 7, 5), nose="#f06b8b",
                leg=8, leg_r=5, tail="long", tail_colour="#f4b6c2",
                extras=[whiskers()]),
    "Gorilla": dict(name="Gorilla", plan=sitter, colour="#3b3740",
                    face="#6b6570", crest=True),
    "Monkey": dict(name="Monkey", plan=sitter, colour="#8b5a2b",
                   face="#f0c9a0", face_ears=True, tail=True, scale=0.85),
    "Duck": dict(name="Duck", plan=bird, colour="#f7d64a", beak="#f39c12",
                 flat_beak=True, wing="#f2c630"),
    "Chicken": dict(name="Chicken", plan=bird, colour="#fbfaf6",
                    comb=True, beak="#f5b041", tail_feathers="#e8e2d6"),
    "Owl": dict(name="Owl", plan=bird, colour="#9c6b45", belly="#e3c7a0",
                owl=True, upright=True, beak="#f5b041", wing="#7a4f30",
                disc="#e3c7a0"),
    "Penguin": dict(name="Penguin", plan=bird, colour="#2f3440",
                    belly="#fbfaf6", upright=True, beak="#f39c12",
                    feet="#f39c12"),
    "Snake": dict(name="Snake", plan=snake, colour="#7cc36b",
                  band="#4a9a45"),
    "Frog": dict(name="Frog", plan=frog, colour="#6cc26b"),
    "Turtle": dict(name="Turtle", plan=turtle, colour="#8fd07a",
                   shell="#6b9a3a"),
    "Crocodile": dict(name="Crocodile", plan=crocodile, colour="#5aa84f"),
}


def build(name, dims=None):
    """The toy *name* as ONE node (its program parsed into nodes)."""
    from . import scadparse
    from .model import CadNode
    spec = SPECIES[name]
    toy = spec["plan"](spec)
    root, _warnings = scadparse.parse_scad(toy.program())
    group = CadNode("union", f"{name} (cartoon)")
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
    return "cartoon_" + "".join(c if c.isalnum() else "_"
                                for c in name.lower()).strip("_")


PARTS = {_slug(name): dict(label=name, category=CATEGORY,
                           sizes={"Toy (12 cm)": {}}, fields=[],
                           build=lambda dims, n=name: build(n, dims))
         for name in SPECIES}
