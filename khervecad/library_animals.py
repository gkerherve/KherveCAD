"""Cartoon animals for the parts library (2026-09-19, the user's request:
"the nicest cutest animals"; second pass the same day: "most animals
look like 2 spheres, you have not put any details") — Library ▸ Toys &
models ▸ Animals ▸ Cartoon animals: 30 chibi toys, ~12 cm tall, facing
-Y, standing on z = 0.

One style for the whole set, like a shelf of vinyl collectibles:

- a head as big as the body, soft moulded bodies (one `blend` each);
- EYES with a white, a coloured iris, a big pupil and two sparkles,
  optional lashes and brows; rosy cheeks;
- a nose that belongs to the animal (heart for cats, button for dogs
  and bears, snout for pigs, nostrils for horses and cows, beaks);
- a mouth with character ("w" for cats, an open smile with a tongue for
  dogs, buck teeth for rabbits, a wide grin for frogs);
- paws with toes, split hooves, fur tufts, a forelock;
- an accessory or a prop: a collar with a tag or a bell, a bow, a
  scarf, a crown; bamboo, a banana, cheese, a carrot, a honey pot, a
  eucalyptus leaf.

Body plans: `sit` (pets and cats sit up like figurines — dog, cat,
fox, bear, panda, koala, rabbit, mouse, lion, tiger), `stand` (farm and
big animals), `ape`, `bird`, and the snake, frog, turtle and crocodile.
Every detail sits on a surface found with `on_ellipsoid` (point and
normal), so the pieces lie on the toy rather than inside it.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
import random

CATEGORY = "Cartoon animals"

WHITE = "#fbfaf6"
PUPIL = "#18161b"
BLUSH = "#f79ab5"
INK = "#2a2326"
PINK = "#f4b0c0"
GOLD = "#f2c14e"
RED = "#e8434f"
BROWN_EYE = "#6b4424"


def _f(v):
    return f"{v:.2f}"


def _v(p):
    return "[" + ", ".join(_f(c) for c in p) + "]"


def _norm(d):
    n = math.sqrt(sum(c * c for c in d)) or 1.0
    return [c / n for c in d]


def _add(a, b, k=1.0):
    return [a[i] + b[i] * k for i in range(3)]


def _mix(a, b, t):
    return [a[i] + (b[i] - a[i]) * t for i in range(3)]


def on_ellipsoid(c, r, d):
    """The point of the ellipsoid (centre *c*, radii *r*) in direction
    *d* from its centre, and the outward normal there."""
    d = _norm(d)
    t = 1.0 / math.sqrt(sum((d[i] / r[i]) ** 2 for i in range(3)))
    p = [c[i] + d[i] * t for i in range(3)]
    n = _norm([(p[i] - c[i]) / r[i] ** 2 for i in range(3)])
    return p, n


def _segments(r):
    """Round segments for a detail *r* mm across: a sparkle needs few,
    a head more — 48 everywhere made a toy 150k triangles."""
    return 10 if r < 1.5 else 14 if r < 4 else 20 if r < 9 else 30


class Toy:
    """OpenSCAD statements for one toy."""

    def __init__(self, name):
        self.name = name
        self.lines = []

    # --- primitives
    @staticmethod
    def ell(c, r):
        return (f"kcad_ellipsoid(c = {_v(c)}, r = {_v(r)}, "
                f"$fn = {_segments(max(r))});")

    @staticmethod
    def sph(c, r):
        return Toy.ell(c, [r, r, r])

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

    @staticmethod
    def disc(c, n, a, b, t, turn=0.0):
        """A thin oval lying on a surface at *c* with normal *n*."""
        n = _norm(n)
        tilt = math.degrees(math.acos(max(-1.0, min(1.0, n[2]))))
        az = math.degrees(math.atan2(n[1], n[0]))
        return (f"translate({_v(c)}) rotate([0, {_f(tilt)}, {_f(az)}]) "
                f"rotate([0, 0, {_f(turn)}]) scale({_v([a, b, t])}) "
                f"sphere(r = 1, $fn = 16);")

    @staticmethod
    def ring(c, radius, r, tilt=(0.0, 0.0, 0.0)):
        """A torus round *c* (axis z, then turned by *tilt* degrees)."""
        return (f"translate({_v(c)}) rotate({_v(tilt)}) "
                f"rotate_extrude($fn = 32) translate([{_f(radius)}, 0]) "
                f"circle(r = {_f(r)}, $fn = 12);")

    @staticmethod
    def hull(*items):
        return "hull() { " + " ".join(items) + " }"

    def chain(self, pts, r):
        radii = r if isinstance(r, (list, tuple)) else [r] * len(pts)
        return [self.cap(pts[i], pts[i + 1], radii[i])
                for i in range(len(pts) - 1)]

    def put(self, colour, label, *pieces, material="Plastic"):
        body = " ".join(pieces)
        self.lines.append(f'kcad_material("{material}") color("{colour}") '
                          f"union() {{ {body} }}  // {label}")

    def blend(self, colour, label, radius, pieces, detail=44,
              material="Plastic"):
        body = " ".join(pieces)
        self.lines.append(
            f'kcad_material("{material}") color("{colour}") '
            f"kcad_blend(radius = {_f(radius)}, detail = {detail}) "
            f"{{ {body} }}  // {label}")

    def program(self):
        body = "\n".join(self.lines)
        k = getattr(self, "scale", 1.0)
        if k != 1.0:                              # a plan drawn small
            return f"scale([{k}, {k}, {k}]) union() {{\n{body}\n}}"
        return body


# ================================================================ face
class Face:
    """The face kit on a head ellipsoid (*c*, *r*)."""

    def __init__(self, t, c, r):
        self.t, self.c, self.r = t, c, r

    def at(self, d, inset=0.0):
        p, n = on_ellipsoid(self.c, self.r, d)
        return _add(p, n, -inset), n

    def eyes(self, size, iris=BROWN_EYE, spread=0.42, up=0.14, lashes=0,
             brows=None, lids=None, shape=1.0):
        t = self.t
        for sx in (1, -1):
            p, n = self.at([sx * spread, -0.86, up])
            e = _add(p, n, -size * 0.3)
            t.put(WHITE, "Eye white", t.ell(e, [size * 0.95, size * 0.58,
                                                size * 1.12 * shape]))
            front = _add(e, n, size * 0.34)
            if iris:
                t.put(iris, "Iris", t.ell(_add(front, [0, 0, -size * 0.08]),
                                          [size * 0.74, size * 0.3,
                                           size * 0.86 * shape]),
                      material="Glass")
            pupil = _add(front, n, size * 0.16)
            t.put(PUPIL, "Pupil", t.ell(_add(pupil, [0, 0, -size * 0.1]),
                                        [size * 0.46, size * 0.22,
                                         size * 0.56 * shape]),
                  material="Glass")
            glint = _add(pupil, n, size * 0.2)
            t.put(WHITE, "Sparkle", t.sph(
                [glint[0] - sx * size * 0.2, glint[1],
                 glint[2] + size * 0.32], size * 0.25), material="Emissive")
            t.put(WHITE, "Sparkle", t.sph(
                [glint[0] + sx * size * 0.24, glint[1],
                 glint[2] - size * 0.3], size * 0.11), material="Emissive")
            if lids:
                t.put(lids, "Eyelid", t.ell(_add(e, [0, -size * 0.05,
                                                     size * 0.5]),
                                            [size * 1.02, size * 0.64,
                                             size * 0.6]))
            for k in range(lashes):
                a = _add(e, [sx * size * (0.55 + 0.2 * k), -size * 0.1,
                             size * (0.95 - 0.28 * k)])
                b = _add(a, [sx * size * 0.45, -size * 0.1, size * 0.28])
                t.put(INK, "Lash", t.cap(a, b, size * 0.07))
            if brows:
                a = _add(e, [-sx * size * 0.5, -size * 0.1, size * 1.45])
                m = _add(e, [0, -size * 0.2, size * 1.62])
                b = _add(e, [sx * size * 0.55, -size * 0.1, size * 1.45])
                t.put(brows, "Brow", t.cap(a, m, size * 0.13),
                      t.cap(m, b, size * 0.13))

    def cheeks(self, size, spread=0.64, down=-0.14, freckles=False):
        t = self.t
        for sx in (1, -1):
            p, n = self.at([sx * spread, -0.7, down])
            t.put(BLUSH, "Cheek", t.disc(_add(p, n, size * 0.05), n,
                                         size, size * 0.62, size * 0.3),
                  material="Matte")
            if freckles:
                for k in range(3):
                    q = _add(p, [sx * (k - 1) * size * 0.5, -0.6,
                                 size * 0.2 * (k % 2)])
                    t.put("#c98a6a", "Freckle", t.sph(q, size * 0.12),
                          material="Matte")

    def muzzle(self, colour, size, down=0.4, deep=0.3):
        """A soft muzzle; returns (centre, radii) for nose and mouth."""
        p, n = self.at([0, -0.92, -down])
        r = [size, size * deep * 2.4, size * 0.72]
        c = _add(p, n, -r[1] * 0.45)
        self.t.put(colour, "Muzzle", self.t.ell(c, r), material="Matte")
        return c, r

    def nose(self, style, colour, on=None, size=3.5):
        t = self.t
        c, r = on or (self.c, self.r)
        p, n = on_ellipsoid(c, r, [0, -0.8, 0.55])
        if style == "heart":                      # cats
            for sx in (1, -1):
                t.put(colour, "Nose", t.sph(_add(p, [sx * size * 0.42, -0.4,
                                                     size * 0.18]),
                                            size * 0.55),
                      t.cone(_add(p, [0, -0.2, size * 0.3]),
                             _add(p, [0, -0.6, -size * 0.75]), size * 0.72,
                             0.25), material="Glass")
        elif style == "button":
            t.put(colour, "Nose", t.ell(_add(p, n, -size * 0.25),
                                        [size * 1.15, size * 0.72,
                                         size * 0.82]), material="Glass")
            t.put(WHITE, "Nose shine", t.sph(_add(p, [-size * 0.35,
                                                      -size * 0.7,
                                                      size * 0.35]),
                                             size * 0.22),
                  material="Emissive")
        elif style == "nostrils":
            for sx in (1, -1):
                q, qn = on_ellipsoid(c, r, [sx * 0.38, -0.9, 0.1])
                t.put(colour, "Nostril", t.disc(_add(q, qn, 0.2), qn,
                                                size * 0.42, size * 0.62,
                                                size * 0.25))
        return p

    def mouth(self, style, on=None, width=4.0, tongue=True):
        t = self.t
        c, r = on or (self.c, self.r)
        p, n = on_ellipsoid(c, r, [0, -0.9, -0.42])
        p = _add(p, n, 0.3)
        if style == "w":                          # cats: a little "w"
            mid = _add(p, [0, 0, width * 0.15])
            for sx in (1, -1):
                low = _add(p, [sx * width * 0.45, 0.2, -width * 0.25])
                end = _add(p, [sx * width * 0.95, 0.4, width * 0.15])
                t.put(INK, "Mouth", t.cap(mid, low, width * 0.11),
                      t.cap(low, end, width * 0.11))
        elif style == "open":                     # dogs: happy, tongue
            t.put("#5a2230", "Mouth", t.disc(p, n, width * 0.95,
                                             width * 0.7, width * 0.3))
            if tongue:
                t.put("#f07a8e", "Tongue", t.ell(
                    _add(p, [0, -width * 0.25, -width * 0.55]),
                    [width * 0.55, width * 0.35, width * 0.7]))
        elif style == "smile":
            pts = [_add(p, [x * width, 0.2 * abs(x),
                            -width * 0.35 * (1 - x * x)])
                   for x in (-1, -0.5, 0, 0.5, 1)]
            t.put(INK, "Smile", *t.chain(pts, width * 0.11))
        elif style == "buck":                     # rabbits, mice
            mid = _add(p, [0, 0, width * 0.1])
            for sx in (1, -1):
                end = _add(p, [sx * width * 0.8, 0.3, width * 0.3])
                t.put(INK, "Mouth", t.cap(mid, end, width * 0.1))
                t.put(WHITE, "Tooth", t.ell(
                    _add(mid, [sx * width * 0.2, -0.3, -width * 0.45]),
                    [width * 0.19, width * 0.1, width * 0.32]))
        return p

    def whiskers(self, on, length=9.0, colour="#7a7078", count=3):
        t = self.t
        c, r = on
        for sx in (1, -1):
            for k in range(count):
                q, _qn = on_ellipsoid(c, r, [sx * 0.75, -0.6,
                                             -0.1 + 0.18 * (k - 1)])
                end = _add(q, [sx * length, -1.0, (k - 1) * length * 0.25])
                t.put(colour, "Whisker", t.cap(q, end, 0.35))

    def ears(self, kind, colour, inner=PINK, size=8.0, tip=None, tilt=0.0):
        t = self.t
        for sx in (1, -1):
            if kind == "pointy":
                base, n = self.at([sx * 0.55, 0.05, 0.84], size * 0.25)
                out = _norm([sx * (0.35 + tilt), 0.08, 1.0])
                top = _add(base, out, size * 1.6)
                t.put(colour, "Ear", t.cone(base, top, size * 0.8, size * 0.1))
                if inner:
                    t.put(inner, "Inner ear", t.cone(
                        _add(base, [0, -size * 0.28, size * 0.1]),
                        _add(top, [0, -size * 0.18, -size * 0.45]),
                        size * 0.5, 0.2))
                if tip:
                    t.put(tip, "Ear tip", t.cone(
                        _add(base, out, size * 1.05), top, size * 0.32,
                        size * 0.08))
            elif kind == "round":
                p, n = self.at([sx * 0.66, 0.05, 0.74])
                c = _add(p, n, size * 0.3)
                t.put(colour, "Ear", t.ell(c, [size, size * 0.52, size]))
                if inner:
                    t.put(inner, "Inner ear", t.ell(
                        _add(c, [0, -size * 0.44, -size * 0.05]),
                        [size * 0.62, size * 0.14, size * 0.62]),
                          material="Matte")
            elif kind == "floppy":
                p, n = self.at([sx * 0.78, 0.1, 0.5])
                low = _add(p, [sx * size * 0.55, -size * 0.15, -size * 1.7])
                t.put(colour, "Ear", t.hull(
                    t.ell(p, [size * 0.5, size * 0.3, size * 0.5]),
                    t.ell(low, [size * 0.75, size * 0.35, size * 0.6])))
            elif kind == "long":
                p, n = self.at([sx * 0.3, 0.12, 0.95])
                top = _add(p, [sx * size * 0.45, size * 0.3, size * 2.7])
                t.put(colour, "Ear", t.hull(
                    t.ell(p, [size * 0.45, size * 0.3, size * 0.5]),
                    t.ell(_mix(p, top, 0.6), [size * 0.62, size * 0.34,
                                              size * 0.6]),
                    t.sph(top, size * 0.42)))
                if inner:
                    t.put(inner, "Inner ear", t.hull(
                        t.ell(_add(_mix(p, top, 0.2), [0, -size * 0.3, 0]),
                              [size * 0.2, size * 0.1, size * 0.2]),
                        t.ell(_add(_mix(p, top, 0.62), [0, -size * 0.32, 0]),
                              [size * 0.38, size * 0.12, size * 0.45])))
            elif kind == "side":
                p, n = self.at([sx * 0.92, 0.1, 0.32])
                c = _add(p, [sx * 1.0, -0.2, 0.1], size * 0.75)
                t.put(colour, "Ear", t.ell(c, [size, size * 0.42,
                                               size * 0.55]))
                if inner:
                    t.put(inner, "Inner ear", t.ell(
                        _add(c, [sx * size * 0.1, -size * 0.25, 0]),
                        [size * 0.66, size * 0.2, size * 0.34]))
            elif kind == "fan":                   # elephant
                p, n = self.at([sx * 0.9, 0.25, 0.15])
                c = _add(p, [sx * 0.5, 0.35, -0.1], size * 0.9)
                t.put(colour, "Ear", t.ell(c, [size * 0.4, size * 1.3,
                                               size * 1.45]))
                if inner:
                    t.put(inner, "Inner ear", t.ell(
                        _add(c, [0, -size * 0.25, 0]),
                        [size * 0.3, size * 0.95, size * 1.05]))
            elif kind == "fluffy":                # koala
                p, n = self.at([sx * 0.8, 0.05, 0.62])
                c = _add(p, n, size * 0.4)
                t.put(colour, "Ear", t.ell(c, [size * 1.1, size * 0.55,
                                               size * 1.05]))
                t.put(WHITE, "Ear fluff", *[t.sph(
                    _add(c, [sx * size * 0.2 * (k - 1), -size * 0.45,
                             size * 0.3 * (1 - abs(k - 1))]),
                    size * 0.45) for k in range(3)], material="Matte")

    def tuft(self, colour, size=5.0, count=3, forward=0.1):
        """A little spray of fur on the crown."""
        t = self.t
        base, _n = self.at([0, -forward, 1.0], size * 0.2)
        pieces = []
        for k in range(count):
            a = (k - (count - 1) / 2) * 0.45
            tip = _add(base, [math.sin(a) * size, -size * 0.2,
                              size * (1.3 - 0.2 * abs(a))])
            pieces.append(t.cone(base, tip, size * 0.42, size * 0.05))
        t.put(colour, "Tuft", *pieces)


# ============================================================== extras
def collar(t, c, radius, colour=RED, charm="tag", charm_colour=GOLD,
           tilt=12.0):
    t.put(colour, "Collar", t.ring(c, radius, radius * 0.1, [tilt, 0, 0]))
    p = [c[0], c[1] - radius * math.cos(math.radians(tilt)) - radius * 0.08,
         c[2] - radius * math.sin(math.radians(tilt)) - radius * 0.2]
    if charm == "tag":
        t.put(charm_colour, "Tag", t.disc(p, [0, -1, -0.2], radius * 0.22,
                                          radius * 0.22, radius * 0.06),
              material="Gold")
    elif charm == "bell":
        t.put(charm_colour, "Bell", t.sph(p, radius * 0.24), material="Gold")
        t.put(INK, "Bell slot", t.disc(_add(p, [0, -radius * 0.22,
                                                -radius * 0.08]),
                                       [0, -1, 0], radius * 0.12,
                                       radius * 0.03, radius * 0.03))
    elif charm == "bow":
        bow(t, p, radius * 0.35, charm_colour)


def bow(t, c, size, colour=RED, normal=(0, -1, 0)):
    for sx in (1, -1):
        t.put(colour, "Bow", t.hull(t.sph(c, size * 0.3),
                                    t.ell(_add(c, [sx * size, 0,
                                                   size * 0.35]),
                                          [size * 0.4, size * 0.3,
                                           size * 0.5]),
                                    t.ell(_add(c, [sx * size, 0,
                                                   -size * 0.35]),
                                          [size * 0.4, size * 0.3,
                                           size * 0.5])))
    t.put(colour, "Bow knot", t.sph(_add(c, list(normal), size * 0.15),
                                    size * 0.38))


def paw(t, c, r, colour, beans=None, toes=True):
    """A soft paw with three toe bumps and the lines between them."""
    t.put(colour, "Paw", t.ell(c, [r, r * 1.15, r * 0.7]))
    if toes:
        for k in (-1, 0, 1):
            t.put(colour, "Toe", t.sph(_add(c, [k * r * 0.52, -r * 0.9,
                                                -r * 0.1]), r * 0.4))
        for k in (-0.5, 0.5):
            t.put(INK, "Toe line", t.cap(
                _add(c, [k * r * 0.52, -r * 1.2, r * 0.1]),
                _add(c, [k * r * 0.52, -r * 1.15, -r * 0.3]), 0.3))
    if beans:
        t.put(beans, "Toe bean", t.disc(_add(c, [0, -r * 1.05, -r * 0.3]),
                                        [0, -0.5, -1], r * 0.35, r * 0.3,
                                        r * 0.1), material="Matte")


def hoof(t, c, r, colour):
    t.put(colour, "Hoof", t.cap(_add(c, [0, 0, r * 0.1]),
                                _add(c, [0, 0, r * 0.55]), r * 1.08))
    t.put(INK, "Hoof split", t.disc(_add(c, [0, -r * 1.12, r * 0.55]),
                                    [0, -1, 0], r * 0.08, r * 0.6,
                                    r * 0.05))


def stripes_on(t, c, r, colour, count, width, span=(-0.75, 0.75),
               reach=100, seed=2, sides=(1, -1)):
    """Stripes wrapping over an ellipsoid from the spine down."""
    rnd = random.Random(seed)
    for k in range(count):
        y = span[0] + (span[1] - span[0]) * (k + 0.5) / count
        for sx in sides:
            arc = []
            for a in range(0, reach + 1, 20):
                ang = math.radians(a + rnd.uniform(-4, 4))
                q, n = on_ellipsoid(c, r, [sx * math.sin(ang), y,
                                           math.cos(ang)])
                arc.append(_add(q, n, -width * 0.45))
            radii = [width * (1.0 - 0.6 * i / len(arc))
                     for i in range(len(arc))]
            t.put(colour, "Stripe", *t.chain(arc, radii), material="Matte")


def spots_on(t, c, r, colour, count, size, seed=3, zmin=-0.2, oval=0.8):
    rnd = random.Random(seed)
    for _ in range(count):
        d = [rnd.uniform(-1, 1), rnd.uniform(-0.9, 0.9), rnd.uniform(zmin, 1)]
        q, n = on_ellipsoid(c, r, d)
        k = rnd.uniform(0.65, 1.25) * size
        t.put(colour, "Spot", t.disc(_add(q, n, 0.15), n, k, k * oval,
                                     k * 0.3, turn=rnd.uniform(0, 180)),
              material="Matte")


# ================================================================ sit
def sit(p):
    """A pet sitting up like a figurine: a pear body, big haunches, front
    legs straight down between them, the tail curled round the side."""
    t = Toy(p["name"])
    main = p["colour"]
    light = p.get("light", WHITE)
    wide = p.get("wide", 1.0)
    body_c, body_r = [0, 4, 24], [24 * wide, 21, 24]
    chest_c, chest_r = [0, -5, 42], [18 * wide, 16, 18]
    hs = p.get("head", 1.0)
    head_c = [0, -8, 70 + 4 * (hs - 1)]
    head_r = [26 * hs * p.get("head_wide", 1.0), 23 * hs, 23 * hs]
    pieces = [t.ell(body_c, body_r), t.ell(chest_c, chest_r)]
    for sx in (1, -1):
        pieces.append(t.ell([sx * 17, 8, 17], [10, 16, 14]))
        pieces.append(t.cap([sx * 9, -11, 36], [sx * 9.5, -15, 7], 5.8))
    t.blend(main, "Body", 5.0, pieces)
    q, n = on_ellipsoid(chest_c, chest_r, [0, -1, -0.1])
    if p.get("bib", True):
        t.put(light, "Chest", t.ell(_add(q, n, -4), [12 * wide, 6, 15]),
              material="Matte")
    for sx in (1, -1):
        t.put(p.get("feet", main), "Hind foot", t.ell([sx * 14, -11, 5],
                                                      [7.5, 11, 5.5]))
        for k in (-1, 0, 1):
            t.put(p.get("feet", main), "Toe", t.sph([sx * 14 + k * 3.6, -21,
                                                     4.6], 2.7))
        paw(t, [sx * 9.5, -16, 5], 6.2, p.get("paws", p.get("feet", main)))
    tail = p.get("tail", "curl")
    tc = p.get("tail_colour", main)
    if tail == "curl":
        pts = [[6, 22, 12], [16, 22, 6], [24, 10, 5], [24, -4, 5],
               [18, -14, 6]]
        t.put(tc, "Tail", *t.chain(pts, [5.5, 5, 4.6, 4.2, 4.0]))
        if p.get("tail_tip"):
            t.put(p["tail_tip"], "Tail tip", t.sph(pts[-1], 4.6))
    elif tail == "fluffy":
        pts = [[6, 22, 12], [20, 22, 10], [28, 8, 12], [26, -6, 16]]
        t.blend(tc, "Tail", 4, [t.cap(pts[i], pts[i + 1], [7, 9.5, 9.5][i])
                                for i in range(3)])
        if p.get("tail_tip"):
            t.put(p["tail_tip"], "Tail tip", t.ell(_add(pts[-1], [0, -2, 3]),
                                                   [8, 8, 8]))
    elif tail == "puff":
        t.put(p.get("tail_tip", WHITE), "Tail", t.sph([0, 25, 10], 8.5),
              material="Matte")
    elif tail == "tuft":
        pts = [[6, 22, 10], [18, 26, 6], [28, 16, 6], [30, 2, 10]]
        t.put(tc, "Tail", *t.chain(pts, 3))
        t.put(p.get("tail_tip", main), "Tail tuft", t.hull(
            t.sph(pts[-1], 4.5), t.sph(_add(pts[-1], [0, -3, 5]), 3)))
    elif tail == "stub":
        t.put(tc, "Tail", t.sph([0, 25, 12], 5))
    elif tail == "long":
        pts = [[4, 24, 8]] + [[math.cos(a) * (18 + a * 3),
                               20 + math.sin(a) * 18, 5 + a * 3]
                              for a in (0.4, 1.2, 2.0, 2.8, 3.4)]
        t.put(tc, "Tail", *t.chain(pts, 1.7))
    hp = [t.ell(head_c, head_r)]
    if p.get("cheek_fluff"):
        for sx in (1, -1):
            hp.append(t.ell(_add(head_c, [sx * head_r[0] * 0.78, -3,
                                          -head_r[2] * 0.42]),
                            [9 * hs, 8 * hs, 7 * hs]))
    t.blend(main, "Head", 3.5, hp)
    face = Face(t, head_c, head_r)
    _face(t, face, p, hs)
    if p.get("collar"):
        col = p["collar"]
        collar(t, [0, -4, 52], 14.5, col[0], col[1], col[2])
    for extra in p.get("extras", ()):
        extra(t, dict(head_c=head_c, head_r=head_r, body_c=body_c,
                      body_r=body_r, chest_c=chest_c, chest_r=chest_r,
                      hs=hs, face=face))
    return t


def _face(t, face, p, hs):
    """Muzzle, nose, mouth, eyes, cheeks, ears and whiskers for a head."""
    mz = None
    if p.get("muzzle"):
        mz = face.muzzle(p.get("muzzle_colour", p.get("light", WHITE)),
                         p["muzzle"] * hs, down=p.get("muzzle_down", 0.42),
                         deep=p.get("muzzle_deep", 0.3))
    face.nose(p.get("nose_style", "button"), p.get("nose", INK), on=mz,
              size=p.get("nose_size", 3.4) * hs)
    face.mouth(p.get("mouth", "smile"), on=mz,
               width=p.get("mouth_w", 3.6) * hs)
    face.eyes(p.get("eye", 7.2) * hs, iris=p.get("iris", BROWN_EYE),
              spread=p.get("eye_spread", 0.42), up=p.get("eye_up", 0.12),
              lashes=p.get("lashes", 0), brows=p.get("brows"),
              lids=p.get("lids"), shape=p.get("eye_shape", 1.0))
    face.cheeks(4.3 * hs, freckles=p.get("freckles", False))
    if p.get("ears"):
        face.ears(p["ears"], p.get("ear_colour", p["colour"]),
                  p.get("inner_ear", PINK), p.get("ear_size", 8.0) * hs,
                  tip=p.get("ear_tip"), tilt=p.get("ear_tilt", 0.0))
    if p.get("whiskers") and mz:
        face.whiskers(mz, p.get("whisker_len", 9.0) * hs,
                      p.get("whisker_colour", "#8a8088"))
    if p.get("tuft"):
        face.tuft(p["tuft"], 5.0 * hs)


# ============================================================== stand
def stand(p):
    """A four-legged toy standing: round body, short legs, big head on a
    short neck (a long one for the giraffe)."""
    t = Toy(p["name"])
    s = p.get("scale", 1.0)
    main, light = p["colour"], p.get("light", WHITE)
    bw, bl, bh = [v * s for v in p.get("body", (22, 29, 20))]
    leg_h, leg_r = p.get("leg", 14) * s, p.get("leg_r", 7.2) * s
    cz = leg_h + bh * 0.7
    body_c, body_r = [0, 2, cz], [bw, bl, bh]
    hs = p.get("head", 1.0) * s
    hr = [25 * hs * p.get("head_wide", 1.0),
          22 * hs * p.get("head_long", 1.0), 22 * hs]
    neck = p.get("neck", 0.0) * s
    head_c = [0, -bl * 0.8 - p.get("head_ahead", 0.0) * s,
              cz + bh * 0.7 + hr[2] * 0.5 + neck]
    pieces = [t.ell(body_c, body_r)]
    feet = []
    for sx in (1, -1):
        for sy in (-1, 1):
            top = [sx * bw * 0.5, sy * bl * 0.56 + 2, cz - bh * 0.2]
            foot = [sx * bw * 0.54, sy * bl * 0.58 + 2, leg_r]
            pieces.append(t.cap(top, foot, leg_r))
            feet.append(foot)
    if neck > 0:
        pieces.append(t.cap([0, -bl * 0.6, cz + bh * 0.35],
                            [0, head_c[1] + hr[1] * 0.35,
                             head_c[2] - hr[2] * 0.3],
                            p.get("neck_r", 8.0) * s))
    t.blend(main, "Body", 5.0 * s, pieces)
    hp = [t.ell(head_c, hr)]
    snout = p.get("snout")
    sc = sr = None
    if snout:
        sc = _add(head_c, [0, -hr[1] * 0.55, -hr[2] * 0.42])
        sr = [v * s for v in snout]
        hp.append(t.ell(sc, sr))
    t.blend(main, "Head", 3.0 * s, hp)
    if p.get("belly", True):
        q, n = on_ellipsoid(body_c, body_r, [0, -0.2, -1])
        t.put(light, "Belly", t.disc(_add(q, n, 0.3), n, bw * 0.62,
                                     bl * 0.6, bh * 0.25), material="Matte")
    for f in feet:
        if p.get("hoof"):
            hoof(t, [f[0], f[1], 0], leg_r, p["hoof"])
        else:
            paw(t, [f[0], f[1] - leg_r * 0.25, leg_r * 0.6], leg_r * 0.95,
                p.get("paws", main))
    face = Face(t, head_c, hr)
    if snout:
        mz = None
        if p.get("muzzle"):
            q, n = on_ellipsoid(sc, sr, [0, -0.9, -0.35])
            mr = [v * s for v in p["muzzle"]]
            mc = _add(q, n, -mr[1] * 0.45)
            t.put(p.get("muzzle_colour", light), "Muzzle", t.ell(mc, mr),
                  material="Matte")
            mz = (mc, mr)
        face.nose(p.get("nose_style", "nostrils"), p.get("nose", INK),
                  on=mz or (sc, sr), size=p.get("nose_size", 3.4) * s)
        face.mouth(p.get("mouth", "smile"), on=mz or (sc, sr),
                   width=p.get("mouth_w", 4.0) * s)
        face.eyes(p.get("eye", 6.6) * hs, iris=p.get("iris", BROWN_EYE),
                  spread=p.get("eye_spread", 0.46), up=p.get("eye_up", 0.2),
                  lashes=p.get("lashes", 0), brows=p.get("brows"),
                  lids=p.get("lids"))
        face.cheeks(4.0 * hs)
        if p.get("ears"):
            face.ears(p["ears"], p.get("ear_colour", main),
                      p.get("inner_ear", PINK), p.get("ear_size", 7.0) * s,
                      tip=p.get("ear_tip"))
        if p.get("tuft"):
            face.tuft(p["tuft"], 4.5 * s)
    else:
        _face(t, face, p, hs)
    _stand_tail(t, p, body_c, body_r, s)
    g = dict(head_c=head_c, head_r=hr, body_c=body_c, body_r=body_r,
             cz=cz, s=s, feet=feet, leg_r=leg_r, face=face, bl=bl, bh=bh,
             colour=main)
    if p.get("collar"):
        col = p["collar"]
        nc = [0, head_c[1] + hr[1] * 0.25, head_c[2] - hr[2] * 0.95]
        collar(t, nc, hr[0] * 0.62, col[0], col[1], col[2], tilt=25)
    for extra in p.get("extras", ()):
        extra(t, g)
    return t


def _stand_tail(t, p, c, r, s):
    root = [0, c[1] + r[1] * 0.95, c[2] + r[2] * 0.25]
    kind = p.get("tail")
    col = p.get("tail_colour", p["colour"])
    if kind == "curly":
        pts = [[root[0] + math.sin(k * 0.9) * 3.6 * s,
                root[1] + 2 * s + k * 0.8 * s,
                root[2] + math.cos(k * 0.9) * 3.6 * s] for k in range(9)]
        t.put(col, "Tail", *t.chain(pts, 1.5 * s))
    elif kind == "tuft":
        a = _add(root, [0, 9 * s, -2 * s])
        b = _add(root, [0, 12 * s, -12 * s])
        t.put(col, "Tail", t.cap(root, a, 1.7 * s), t.cap(a, b, 1.7 * s))
        t.put(p.get("tail_tip", col), "Tail tuft", t.hull(
            t.sph(b, 3.2 * s), t.sph(_add(b, [0, 1 * s, -5 * s]), 2.2 * s)))
    elif kind == "puff":
        t.put(p.get("tail_tip", col), "Tail",
              t.sph(_add(root, [0, 3 * s, 2 * s]), 5 * s))
    elif kind == "horse":
        pts = [root, _add(root, [0, 6 * s, -3 * s]),
               _add(root, [0, 9 * s, -14 * s])]
        t.blend(col, "Tail", 2 * s, [t.cap(pts[0], pts[1], 4 * s),
                                     t.cap(pts[1], pts[2], 5 * s),
                                     t.sph(_add(pts[2], [0, 1 * s, -4 * s]),
                                           4 * s)])


# ================================================================ ape
def ape(p):
    t = Toy(p["name"])
    main, face_col = p["colour"], p["face"]
    body_c, body_r = [0, 0, 26], [24, 20, 26]
    head_c, head_r = [0, -6, 66], [22, 20, 20]
    pieces = [t.ell(body_c, body_r)]
    arms = p.get("arms", "down")
    for sx in (1, -1):
        sh = [sx * 20, -4, 42]
        hand = [sx * 26, -16, 7] if arms == "down" else [sx * 8, -26, 30]
        pieces.append(t.cap(sh, hand, 7.5))
        knee = [sx * 12, -20, 12]
        pieces.append(t.cap([sx * 12, -2, 9], knee, 8.2))
        pieces.append(t.cap(knee, [sx * 10, -27, 5], 6.2))
    t.blend(main, "Body", 5, pieces)
    hp = [t.ell(head_c, head_r)]
    if p.get("crest"):
        hp.append(t.ell([0, -2, 82], [13, 13, 10]))
    t.blend(main, "Head", 3, hp)
    face = Face(t, head_c, head_r)
    # the pale mask is a smaller ellipsoid poking out of the head front,
    # so it follows the head's curve and the eyes sit ON it
    fc = _add(head_c, [0, -7.5, -1.5])
    fr = [head_r[0] * 0.8, head_r[1] * 0.72, head_r[2] * 0.82]
    t.put(face_col, "Face", t.ell(fc, fr), material="Matte")
    q, _n = face.at([0, -1, -0.12])
    mc, mr = _add(q, [0, -4.5, -8]), [11, 6, 7]
    t.put(face_col, "Muzzle", t.ell(mc, mr), material="Matte")
    for sx in (1, -1):
        np_, _ = on_ellipsoid(mc, mr, [sx * 0.3, -0.85, 0.45])
        t.put(INK, "Nostril", t.disc(np_, [0, -1, 0.3], 1.4, 1.1, 0.5))
    face.mouth("smile", on=(mc, mr), width=4.2)
    Face(t, fc, [fr[0], fr[1] + 1.6, fr[2]]).eyes(6.2, iris=p.get("iris", BROWN_EYE), spread=0.4,
                         up=0.3, brows=p.get("brows"))
    face.cheeks(3.6, spread=0.62, down=-0.2)
    bp, bn = on_ellipsoid(body_c, body_r, [0, -1, 0])
    t.put(face_col, "Chest", t.ell(_add(bp, bn, -2.5), [15, 6, 18]),
          material="Matte")
    for sx in (1, -1):
        ep, en = on_ellipsoid(head_c, head_r, [sx, 0.05, 0.1])
        t.put(face_col if p.get("face_ears") else main, "Ear",
              t.ell(_add(ep, en, 1.5), [4, 3, 5.5]))
    if p.get("tail"):
        pts = [[0, 18, 10], [12, 26, 8], [22, 22, 14], [22, 14, 22],
               [16, 12, 24]]
        t.put(main, "Tail", *t.chain(pts, 2.6))
    for extra in p.get("extras", ()):
        extra(t, dict(head_c=head_c, head_r=head_r, face=face,
                      body_c=body_c, body_r=body_r))
    return t


# =============================================================== bird
def bird(p):
    t = Toy(p["name"])
    main, belly = p["colour"], p.get("belly")
    upright = p.get("upright", False)
    body_c = [0, 0, 36] if upright else [0, 0, 30]
    body_r = [24, 20, 32] if upright else [22, 26, 22]
    head_c = [0, -3, 76] if upright else [0, -14, 62]
    head_r = [18, 17, 17]
    if p.get("owl"):
        head_c, head_r = [0, -3, 66], [25, 21, 22]
    t.blend(main, "Body", 5, [t.ell(body_c, body_r), t.ell(head_c, head_r)])
    if belly:
        bp, bn = on_ellipsoid(body_c, body_r, [0, -1, -0.2])
        if p.get("heart_belly"):
            t.put(belly, "Belly", t.hull(
                t.ell(_add(bp, [8, 0, 8]), [9, 4, 9]),
                t.ell(_add(bp, [-8, 0, 8]), [9, 4, 9]),
                t.ell(_add(bp, [0, 1, -14]), [8, 4, 6])), material="Matte")
        else:
            t.put(belly, "Belly", t.ell(_add(bp, bn, -body_r[1] * 0.3),
                                        [body_r[0] * 0.75, body_r[1] * 0.45,
                                         body_r[2] * 0.75]), material="Matte")
        if p.get("chevrons"):
            for k in range(3):
                for j in (-1, 1):
                    q = _add(bp, [j * 5 + (k % 2) * 3, -1.6, 6 - k * 8])
                    t.put(p["chevrons"], "Feather mark", t.cap(
                        q, _add(q, [j * 3, 0, -2.5]), 0.9))
    for sx in (1, -1):
        wp, wn = on_ellipsoid(body_c, body_r, [sx, 0.15, 0.1])
        wing = p.get("wing", main)
        t.put(wing, "Wing", t.ell(_add(wp, wn, -3), [5, body_r[1] * 0.72,
                                                     body_r[2] * 0.6]))
        for k in range(3):
            fq = _add(wp, [sx * 2.5, 4 + k * 3.5, -body_r[2] * 0.42 - k * 1.5])
            t.put(wing, "Wing feather", t.ell(fq, [3, 3.4, 5]))
        foot = [sx * 9, -8, 1.8]
        t.put(p.get("feet", "#f39c12"), "Foot", *[
            t.cap(foot, _add(foot, [k * 4, -6, 0]), 1.8) for k in (-1, 0, 1)])
        t.put(p.get("feet", "#f39c12"), "Leg", t.cap(
            [sx * 9, -2, 3], [sx * 9, 0, body_c[2] - body_r[2] * 0.7], 2))
    beak = p.get("beak", "#f39c12")
    bp, bn = on_ellipsoid(head_c, head_r, [0, -1, -0.2])
    if p.get("flat_beak"):
        t.put(beak, "Beak", t.ell(_add(bp, bn, 2.6), [9, 8, 2.6]),
              t.ell(_add(bp, [0, -2, -3.6]), [7.5, 6.5, 2]))
    else:
        t.put(beak, "Beak", t.cone(_add(bp, bn, -2),
                                   _add(bp, [0, -1, -0.3], 8), 4.5, 0.5))
    face = Face(t, head_c, head_r)
    face.eyes((7.6 if p.get("owl") else 6.0), iris=p.get("iris"),
              spread=0.4 if p.get("owl") else 0.44, up=0.2,
              lashes=p.get("lashes", 0))
    face.cheeks(3.3)
    if p.get("comb"):
        tp, _tn = on_ellipsoid(head_c, head_r, [0, -0.2, 1])
        t.put(RED, "Comb", *[t.sph(_add(tp, [0, k * 3.8, 1.5 - abs(k) * 0.6]),
                                   3.6 - abs(k) * 0.5) for k in (-1, 0, 1)])
        wp, wn = on_ellipsoid(head_c, head_r, [0, -0.8, -0.8])
        t.put(RED, "Wattle", t.ell(_add(wp, wn, 0.5), [2.5, 2, 4]))
    if p.get("owl"):
        for sx in (1, -1):
            ep, _en = on_ellipsoid(head_c, head_r, [sx * 0.6, 0.1, 0.8])
            t.put(main, "Ear tuft", t.cone(ep, _add(ep, [sx * 0.4, 0, 1], 10),
                                           4.8, 0.5))
            fp, fn = on_ellipsoid(head_c, head_r, [sx * 0.42, -0.86, 0.2])
            t.put(p.get("disc", belly or WHITE), "Face disc",
                  t.disc(_add(fp, fn, -1), fn, 10, 11, 3), material="Matte")
    if p.get("hair"):
        face.tuft(p["hair"], 4.0, count=2)
    if p.get("tail_feathers"):
        tp_ = [0, body_r[1] * 0.9, body_c[2] + 6]
        t.put(p["tail_feathers"], "Tail", *[t.ell(
            _add(tp_, [k * 4, 4, 8 - abs(k) * 2]), [3.5, 3, 9])
            for k in (-1, 0, 1)])
    for extra in p.get("extras", ()):
        extra(t, dict(head_c=head_c, head_r=head_r, body_c=body_c,
                      body_r=body_r, face=face))
    return t


# ============================================================== others
def snake(p):
    t = Toy(p["name"])
    main, band = p["colour"], p.get("band", "#4a9a45")
    pts, radii = [], []
    for k in range(40):
        a = k * 0.23
        rad = 34 - k * 0.5
        pts.append([math.cos(a) * rad, math.sin(a) * rad, 8.5 + k * 0.55])
        radii.append(max(8.5 - k * 0.12, 3.2))
    t.blend(main, "Coils", 3, [t.cap(pts[i], pts[i + 1], radii[i])
                               for i in range(len(pts) - 1)])
    for k in range(3, 38, 4):
        up = [0, 0, 1]
        t.put(band, "Diamond", t.disc(_add(pts[k], up, radii[k] * 0.95), up,
                                      radii[k] * 0.6, radii[k] * 0.45,
                                      radii[k] * 0.2, turn=45))
    top = pts[0]
    neck = [top[0] * 0.3, top[1] * 0.3 - 10, 22]
    head_c, head_r = [neck[0], neck[1] - 8, 44], [18.5, 19, 15]
    t.blend(main, "Neck", 4, [t.cap(top, neck, 8), t.cap(neck, head_c, 7.5),
                              t.ell(head_c, head_r)])
    q, n = on_ellipsoid([neck[0], neck[1] - 2, 30], [7.5, 7.5, 12],
                        [0, -1, 0])
    t.put(p.get("belly", "#f7e27e"), "Belly", t.disc(q, n, 5, 10, 1.2))
    face = Face(t, head_c, head_r)
    face.eyes(7.2, iris="#e8b923", spread=0.46, up=0.28, lashes=2)
    face.cheeks(3)
    sp = face.mouth("smile", width=4.5)
    t.put(RED, "Tongue", t.cap(sp, _add(sp, [0, -6, -1.5]), 0.9),
          t.cap(_add(sp, [0, -6, -1.5]), _add(sp, [1.6, -8.5, -2.5]), 0.7),
          t.cap(_add(sp, [0, -6, -1.5]), _add(sp, [-1.6, -8.5, -2.5]), 0.7))
    for extra in p.get("extras", ()):
        extra(t, dict(head_c=head_c, head_r=head_r, face=face))
    return t


def frog(p):
    t = Toy(p["name"])
    main, belly = p["colour"], p.get("belly", "#e9f7c8")
    body_c, body_r = [0, 0, 22], [27, 26, 20]
    head_c, head_r = [0, -12, 38], [26, 20, 15]
    pieces = [t.ell(body_c, body_r), t.ell(head_c, head_r)]
    for sx in (1, -1):
        pieces.append(t.ell([sx * 24, 10, 10], [10, 16, 9]))
        pieces.append(t.cap([sx * 14, -14, 16], [sx * 16, -22, 4], 5))
        pieces.append(t.sph([sx * 14, -14, 46], 10))
    t.blend(main, "Body", 5, pieces)
    bp, bn = on_ellipsoid(body_c, body_r, [0, -1, -0.4])
    t.put(belly, "Belly", t.ell(_add(bp, bn, -6), [18, 7, 12]),
          material="Matte")
    spots_on(t, body_c, body_r, p.get("spots", "#4f9e4c"), 7, 4, seed=5,
             zmin=0.2)
    for sx in (1, -1):
        e = [sx * 14, -20, 48]
        t.put(WHITE, "Eye white", t.ell(e, [7, 5, 7.5]))
        t.put("#e8b923", "Iris", t.ell(_add(e, [0, -2.4, -0.4]),
                                       [5.4, 2.4, 5.8]), material="Glass")
        t.put(PUPIL, "Pupil", t.ell(_add(e, [0, -3.6, -0.5]),
                                    [3.5, 2, 4.2]), material="Glass")
        t.put(WHITE, "Sparkle", t.sph(_add(e, [-sx * 1.5, -5.6, 2.2]), 1.6),
              material="Emissive")
        t.put(BLUSH, "Cheek", t.ell([sx * 19, -27, 32], [4.5, 1.5, 3]),
              material="Matte")
        for k in (-1, 0, 1):
            t.put(main, "Toe", t.sph([sx * 16 + k * 4.2, -25.5, 3], 2.8))
    pts = [[x * 12, -31.4 + 1.6 * x * x, 33 - 3.2 * (1 - x * x)]
           for x in (-1, -0.5, 0, 0.5, 1)]
    t.put(INK, "Smile", *t.chain(pts, 0.8))
    for extra in p.get("extras", ()):
        extra(t, dict(head_c=head_c, head_r=head_r))
    return t


def turtle(p):
    t = Toy(p["name"])
    skin, shell = p["colour"], p["shell"]
    pieces = [t.ell([0, 0, 14], [26, 30, 10])]
    for sx in (1, -1):
        for sy in (-1, 1):
            pieces.append(t.cap([sx * 20, sy * 18, 12],
                                [sx * 27, sy * 24, 5], 7))
    head_c, head_r = [0, -40, 30], [17, 17, 16]
    pieces.append(t.cap([0, -22, 16], [0, -36, 26], 9))
    pieces.append(t.cap([0, 26, 12], [0, 36, 7], 3.5))
    t.blend(skin, "Body", 4, pieces)
    t.blend(skin, "Head", 2, [t.ell(head_c, head_r)])
    t.put(shell, "Shell", f"translate({_v([0, 0, 17])}) "
          f"scale([1, 1.15, 0.72]) sphere(r = 28, $fn = 36);")
    t.put(p.get("rim", "#8d6e3f"), "Shell rim", t.ell([0, 0, 15.5],
                                                      [30, 34.5, 4]))
    scute = p.get("scute", "#a5d66f")
    sc, sr = [0, 0, 17], [28, 32.2, 20.2]
    dirs = [([0, 0, 1], 8)] + [([math.cos(k * math.pi / 3),
                                 math.sin(k * math.pi / 3), 0.9], 7)
                                for k in range(6)]
    for d, a in dirs:
        q, n = on_ellipsoid(sc, sr, d)
        t.put(scute, "Scute", t.disc(_add(q, n, -0.6), n, a, a, 1.8))
    face = Face(t, head_c, head_r)
    face.eyes(5.8, iris="#7a4a2a", spread=0.45, up=0.2)
    face.cheeks(3)
    face.mouth("smile", width=3.8)
    for extra in p.get("extras", ()):
        extra(t, dict(head_c=head_c, head_r=head_r, face=face))
    return t


def crocodile(p):
    t = Toy(p["name"])
    t.scale = p.get("scale", 1.0)
    main, belly = p["colour"], p.get("belly", "#dfe8a6")
    pieces = [t.ell([0, 0, 18], [20, 34, 14]),
              t.cap([0, 28, 16], [0, 62, 8], 11),
              t.cap([0, 62, 8], [0, 86, 5], 5)]
    for sx in (1, -1):
        for sy in (-1, 1):
            pieces.append(t.cap([sx * 16, sy * 18, 14],
                                [sx * 24, sy * 20, 5], 5.5))
    t.blend(main, "Body", 4, pieces)
    head_c, head_r = [0, -38, 26], [20, 18, 16]
    t.blend(main, "Head", 3, [t.ell(head_c, head_r),
                              t.ell([0, -58, 16], [13, 20, 7])])
    t.put(belly, "Jaw", t.ell([0, -54, 11], [12, 19, 4]), material="Matte")
    for k in range(-3, 4):
        y = -66 + abs(k) * 1.5
        t.put(WHITE, "Tooth", t.cone([k * 3.2, y, 12], [k * 3.2, y, 9],
                                     1.3, 0.2))
    for k in range(8):
        y = -16 + k * 11
        z = 31 - k * 2.6 if k < 5 else 31 - 5 * 2.6 - (k - 5) * 4
        for sx in (1, -1):
            t.put(p.get("ridge", "#2e7d32"), "Ridge bump",
                  t.sph([sx * 6, y, z], 3.4 - k * 0.2))
    face = Face(t, head_c, head_r)
    face.eyes(6.4, iris="#e8b923", spread=0.38, up=0.45)
    face.cheeks(3.2, spread=0.72)
    for sx in (1, -1):
        t.put(INK, "Nostril", t.sph([sx * 3, -76, 21], 1.4))
    for extra in p.get("extras", ()):
        extra(t, dict(head_c=head_c, head_r=head_r, face=face))
    return t


# =============================================================== props
def prop_bamboo(t, g):
    """A bamboo stalk held across the chest."""
    a, b = [-16, -22, 20], [14, -22, 64]
    t.put("#7cb342", "Bamboo", t.cap(a, b, 3.2))
    for k in (0.25, 0.5, 0.75):
        t.put("#558b2f", "Bamboo node", t.cap(_mix(a, b, k - 0.02),
                                              _mix(a, b, k + 0.02), 3.6))
    top = _mix(a, b, 0.92)
    for sx in (1, -1):
        t.put("#8bc34a", "Bamboo leaf", t.disc(_add(top, [sx * 6, -1, 2]),
                                               [0, -1, 0.2], 7, 2.4, 0.6,
                                               turn=30 * sx))


def prop_banana(t, g):
    pts = [[-6, -30, 28], [0, -33, 31], [7, -32, 36], [11, -29, 42]]
    t.put("#f7d23e", "Banana", *t.chain(pts, [3.2, 3.4, 3, 2.2]))
    t.put("#6b4a2a", "Banana tip", t.sph(pts[-1], 1.4), t.sph(pts[0], 1.6))


def prop_cheese(t, g):
    t.put("#f7c948", "Cheese", f"translate({_v([0, -26, 4])}) "
          "rotate([0, 0, -30]) linear_extrude(height = 10) "
          "polygon(points = [[0, 0], [16, 0], [0, 11]]);")
    for q in ([4, -24, 8], [8, -27, 6], [3, -28, 3]):
        t.put("#e0a82e", "Cheese hole", t.sph(q, 1.5))


def prop_carrot(t, g):
    a, b = [-10, -24, 18], [10, -26, 30]
    t.put("#f07b22", "Carrot", t.cone(b, a, 4.2, 0.6))
    for k in (-1, 0, 1):
        t.put("#5cb85c", "Carrot leaf", t.ell(_add(b, [2 + k * 1.5, 0,
                                                        4 + abs(k)]),
                                              [1.2, 1.2, 4.5]))


def prop_honey(t, g):
    c = [0, -30, 4]
    t.put("#e8a33c", "Honey pot", t.ell(_add(c, [0, 0, 8]), [10, 10, 9.5]))
    t.put("#f6c54e", "Honey", t.ell(_add(c, [0, 0, 16.2]), [7.5, 7.5, 2.4]),
          t.ell(_add(c, [4, -7.5, 13]), [2, 1.6, 4]))
    t.put("#b86d2a", "Pot rim", t.ring(_add(c, [0, 0, 16]), 7.8, 1.3))
    t.put("#6b4424", "Label", t.disc(_add(c, [0, -9.6, 8]), [0, -1, 0],
                                     5, 3.5, 0.6))


def prop_leaf(t, g):
    c = [0, -24, 30]
    t.put("#6fb36a", "Eucalyptus leaf", t.disc(c, [0, -1, 0.2], 5, 11, 1.2,
                                               turn=20))
    t.put("#4d8a4a", "Stem", t.cap(_add(c, [2, 0, -10]), _add(c, [-2, 0, 9]),
                                   0.7))


def prop_bone(t, g):
    a, b = [-8, -26, 5], [8, -26, 5]
    t.put(WHITE, "Bone", t.cap(a, b, 2.4), *[t.sph(_add(q, [0, dy, 0]), 2.9)
                                            for q in (a, b)
                                            for dy in (-2, 2)])


def crown(t, g):
    c, r = g["head_c"], g["head_r"]
    top, _n = on_ellipsoid(c, r, [0, 0.1, 1])
    t.put(GOLD, "Crown", t.ring(_add(top, [0, 0, 1]), 7, 1.4),
          *[t.cone(_add(top, [math.cos(a) * 7, math.sin(a) * 7, 1]),
                   _add(top, [math.cos(a) * 7.5, math.sin(a) * 7.5, 7]),
                   2.2, 0.4)
            for a in (i * 2 * math.pi / 5 for i in range(5))],
          material="Gold")
    t.put(RED, "Jewel", t.sph(_add(top, [0, -7.6, 3]), 1.5),
          material="Glass")


def scarf(colour, tip=WHITE):
    def draw(t, g):
        c = [0, g["head_c"][1] + 2, g["head_c"][2] - g["head_r"][2] * 0.9]
        t.put(colour, "Scarf", t.ring(c, g["head_r"][0] * 0.62, 3.6,
                                      [8, 0, 0]))
        tail = _add(c, [g["head_r"][0] * 0.4, -g["head_r"][1] * 0.55, -3])
        t.put(colour, "Scarf end", t.hull(t.sph(tail, 3.6),
                                          t.ell(_add(tail, [3, -2, -14]),
                                                [4, 2, 3])))
        t.put(tip, "Scarf stripe", t.ell(_add(tail, [2.6, -2.2, -10]),
                                         [4.2, 2.2, 1.2]))
    return draw


def head_bow(colour, side=1):
    def draw(t, g):
        q, n = on_ellipsoid(g["head_c"], g["head_r"],
                            [side * 0.55, -0.2, 0.85])
        bow(t, _add(q, n, 1.5), 5, colour)
    return draw


def eye_patch(colour, side=1):
    """A patch round one eye (a Dalmatian's, a pup's)."""
    def draw(t, g):
        q, n = on_ellipsoid(g["head_c"], g["head_r"],
                            [side * 0.44, -0.84, 0.16])
        t.put(colour, "Eye patch", t.disc(_add(q, n, 0.2), n, 9.5, 11, 1.2),
              material="Matte")
    return draw


def panda_marks(t, g):
    c, r = g["head_c"], g["head_r"]
    for sx in (1, -1):
        q, n = on_ellipsoid(c, r, [sx * 0.44, -0.84, 0.08])
        t.put(INK, "Eye patch", t.disc(_add(q, n, 0.3), n, 8, 10.5, 1.2,
                                       turn=-sx * 25), material="Matte")
        t.put(INK, "Arm", t.cap([sx * 9, -11, 38], [sx * 9.5, -15, 8], 6.3),
              material="Matte")
        t.put(INK, "Leg", t.ell([sx * 17, 8, 17], [11.4, 17.2, 15.2]),
              t.ell([sx * 14, -11, 5], [8.3, 11.8, 6.3]), material="Matte")
    t.put(INK, "Shoulders", t.ell([0, -4, 50], [19, 14, 6.5]),
          material="Matte")


def tiger_marks(colour, forehead=True):
    def draw(t, g):
        stripes_on(t, g["body_c"], g["body_r"], colour, 5, 1.9,
                   span=(-0.45, 0.75), reach=100, seed=4)
        c, r = g["head_c"], g["head_r"]
        if forehead:
            for dx in (-4, 0, 4):
                q, n = on_ellipsoid(c, r, [dx / 20, -0.55, 0.85])
                t.put(colour, "Forehead stripe", t.disc(
                    _add(q, n, 0.2), n, 1.4, 5.0 - abs(dx) * 0.3, 0.6))
        for sx in (1, -1):
            for k in range(2):
                q, n = on_ellipsoid(c, r, [sx * (0.95 - k * 0.1), -0.2,
                                           0.15 + k * 0.3])
                t.put(colour, "Face stripe", t.disc(_add(q, n, 0.2), n,
                                                    1.4, 5.5, 0.6,
                                                    turn=70 * sx))
    return draw


def lion_mane(colour, dark):
    def draw(t, g):
        c, r = g["head_c"], g["head_r"]
        petals = []
        for k in range(16):
            a = 2 * math.pi * k / 16
            d = [math.cos(a), 0.45, math.sin(a) * 1.05]
            q, n = on_ellipsoid(c, r, d)
            petals.append(t.ell(_add(q, n, 3), [8.5, 7, 8.5]))
        t.blend(colour, "Mane", 3, petals, detail=40)
        for k in range(8):
            a = 2 * math.pi * (k + 0.5) / 8
            q, n = on_ellipsoid(c, r, [math.cos(a), 0.7, math.sin(a)])
            t.put(dark, "Mane lock", t.ell(_add(q, n, 5), [5, 5, 5]))
        top, n = on_ellipsoid(c, r, [0, -0.35, 1])
        t.put(colour, "Mane tuft", t.cone(_add(top, n, -1),
                                          _add(top, [0, -2, 9]), 5, 0.5))
    return draw


def horse_mane(colour, blaze=None):
    def draw(t, g):
        c, r, s = g["head_c"], g["head_r"], g["s"]
        top, _n = on_ellipsoid(c, r, [0, 0.35, 1])
        back = [0, -g["bl"] * 0.35, g["cz"] + g["bh"] * 0.95]
        locks = []
        for k in range(6):
            q = _mix(top, back, k / 5.0)
            locks.append(t.ell(_add(q, [2.5 * s * (1 if k % 2 else -1), 0,
                                        2.5 * s]), [4 * s, 4.5 * s, 4.5 * s]))
        t.blend(colour, "Mane", 2 * s, locks, detail=36)
        fq, _fn = on_ellipsoid(c, r, [0, -0.62, 0.8])
        t.put(colour, "Forelock", t.hull(t.ell(fq, [5 * s, 3 * s, 4 * s]),
                                         t.ell(_add(fq, [2 * s, -4 * s,
                                                         -5 * s]),
                                               [3 * s, 2 * s, 3 * s])))
        if blaze:
            q, n = on_ellipsoid(c, r, [0, -0.95, 0.3])
            t.put(blaze, "Blaze", t.disc(_add(q, n, 0.2), n, 3 * s, 3.8 * s,
                                         0.8 * s))
    return draw


def cow_extras(t, g):
    c, r, s = g["head_c"], g["head_r"], g["s"]
    for sx in (1, -1):
        p, _n = on_ellipsoid(c, r, [sx * 0.55, 0.1, 0.85])
        t.put("#f3e3c0", "Horn", t.cone(p, _add(p, [sx * 0.8, 0, 0.7],
                                                8 * s), 2.8 * s, 1.0 * s))
    spots_on(t, g["body_c"], g["body_r"], INK, 6, 7 * s, seed=6, zmin=0.0,
             oval=0.75)
    q, n = on_ellipsoid(c, r, [0.5, -0.3, 0.8])
    t.put(INK, "Head spot", t.disc(_add(q, n, 0.2), n, 6 * s, 5 * s, 1 * s))
    bc, br = g["body_c"], g["body_r"]
    t.put(PINK, "Udder", t.ell([0, bc[1] + br[1] * 0.4, bc[2] - br[2] * 0.85],
                               [6 * s, 5 * s, 4 * s]))
    fq, fn = on_ellipsoid(c, r, [0, -0.5, 0.9])
    t.put("#f3e3c0", "Forelock", t.ell(_add(fq, fn, 0.5),
                                       [4 * s, 3 * s, 2.5 * s]))


def pig_face(t, g):
    s = g["s"]
    c, r = g["head_c"], g["head_r"]
    p, n = on_ellipsoid(c, r, [0, -1, -0.2])
    snout = _add(p, n, 2.0 * s)
    t.put("#f59ab0", "Snout", f"translate({_v(snout)}) rotate([90, 0, 0]) "
          f"scale([1, 0.78, 1]) cylinder(h = {_f(5.5 * s)}, "
          f"r = {_f(7.8 * s)}, center = true, $fn = 28);")
    for sx in (1, -1):
        t.put("#b0506b", "Nostril", t.ell(_add(snout, [sx * 3 * s,
                                                       -2.9 * s, 0]),
                                          [1.4 * s, 0.7 * s, 2.3 * s]))
    Face(t, c, r).mouth("smile", on=(c, r), width=3.4 * s)
    q, n = on_ellipsoid(g["body_c"], g["body_r"], [-0.7, 0.2, 0.5])
    t.put("#b8876a", "Mud spot", t.disc(_add(q, n, 0.2), n, 5 * s, 4 * s,
                                        1 * s))


def sheep_wool(t, g):
    rnd = random.Random(5)
    c, r, s = g["body_c"], g["body_r"], g["s"]
    pieces = [t.ell(c, [r[0] * 1.06, r[1] * 1.06, r[2] * 1.06])]
    for _ in range(46):
        d = [rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-0.5, 1)]
        q, n = on_ellipsoid(c, r, d)
        pieces.append(t.sph(_add(q, n, 1.6 * s), rnd.uniform(6.5, 9) * s))
    t.blend("#fbfaf6", "Wool", 2.2 * s, pieces, material="Matte")
    hc, hr = g["head_c"], g["head_r"]
    curls = []
    for k in range(7):
        a = math.pi * (0.1 + 0.8 * k / 6)
        q, n = on_ellipsoid(hc, hr, [math.cos(a), 0.15, math.sin(a) * 1.1])
        curls.append(t.sph(_add(q, n, 1.5 * s), 5.2 * s))
    t.blend("#fbfaf6", "Topknot", 1.5 * s, curls, material="Matte")


def elephant_extras(t, g):
    s, c, r = g["s"], g["head_c"], g["head_r"]
    p, _n = on_ellipsoid(c, r, [0, -0.95, -0.28])
    pts = [p, _add(p, [0, -6, -6], s), _add(p, [0, -10, -12], s),
           _add(p, [0, -15, -10], s), _add(p, [0, -17, -4], s)]
    radii = [7 * s, 6 * s, 5.2 * s, 4.6 * s, 4.2 * s]
    t.blend(g["colour"], "Trunk", 2 * s,
            [t.cap(pts[i], pts[i + 1], radii[i]) for i in range(4)] +
            [t.sph(pts[-1], radii[-1])])
    for k in range(3):
        q = _mix(pts[1], pts[2], k / 2.0)
        t.put("#7f93a8", "Trunk crease", t.disc(
            _add(q, [0, -radii[1] * 0.95, 0]), [0, -1, 0.3], radii[1] * 0.7,
            0.4 * s, 0.4 * s))
    for sx in (1, -1):
        q, qn = on_ellipsoid(c, r, [sx * 0.45, -0.85, -0.5])
        t.put(WHITE, "Tusk", t.cone(_add(q, qn, -1),
                                    _add(q, [sx * 0.2, -1, 0.35], 7 * s),
                                    2 * s, 0.7 * s))
    for f in g["feet"]:
        for k in (-1, 0, 1):
            t.put(WHITE, "Toenail", t.ell([f[0] + k * g["leg_r"] * 0.45,
                                           f[1] - g["leg_r"] * 0.95, 2.2 * s],
                                          [1.8 * s, 0.9 * s, 1.6 * s]))
    party = [c[0] + 4 * s, c[1], c[2] + r[2] * 0.9]
    t.put("#7e57c2", "Party hat", t.cone(party, _add(party, [2 * s, 0,
                                                             12 * s]),
                                         5 * s, 0.3 * s))
    t.put(GOLD, "Pompom", t.sph(_add(party, [2 * s, 0, 12.5 * s]), 1.8 * s))


def giraffe_extras(t, g):
    s, c, r = g["s"], g["head_c"], g["head_r"]
    for sx in (1, -1):
        p, _n = on_ellipsoid(c, r, [sx * 0.3, 0.2, 0.95])
        tip = _add(p, [sx * 0.1, 0.1, 1.0], 7 * s)
        t.put("#d98c2b", "Ossicone", t.cap(p, tip, 1.6 * s))
        t.put("#8b5a2b", "Ossicone tip", t.sph(tip, 2.6 * s))
    rnd = random.Random(11)
    bc, br = g["body_c"], g["body_r"]
    for _ in range(12):
        d = [rnd.uniform(-1, 1), rnd.uniform(-0.9, 0.9), rnd.uniform(-0.1, 1)]
        q, n = on_ellipsoid(bc, br, d)
        k = rnd.uniform(3.2, 4.6) * s
        t.put("#c7782a", "Patch", t.disc(_add(q, n, 0.2), n, k, k * 0.85,
                                         0.8 * s, turn=rnd.uniform(0, 90)))
    neck_a = [0, -g["bl"] * 0.6, g["cz"] + g["bh"] * 0.35]
    neck_b = [0, c[1] + r[1] * 0.35, c[2] - r[2] * 0.3]
    for k in range(5):
        q = _mix(neck_a, neck_b, (k + 0.5) / 5)
        for sx in (1, -1):
            t.put("#c7782a", "Neck patch", t.disc(
                _add(q, [sx * 7.8 * s, 0, 0]), [sx, 0, 0.1], 3 * s, 2.6 * s,
                0.7 * s, turn=rnd.uniform(0, 90)))
    for k in range(7):
        q = _add(_mix(neck_b, neck_a, k / 6.0), [0, 3 * s, 8.5 * s])
        t.put("#8b5a2b", "Mane", t.sph(q, 2.2 * s))


def hippo_extras(t, g):
    s, c, r = g["s"], g["head_c"], g["head_r"]
    for sx in (1, -1):
        q, n = on_ellipsoid(c, r, [sx * 0.3, -0.85, -0.55])
        t.put(WHITE, "Tooth", t.ell(_add(q, n, 0.5), [1.8 * s, 1.2 * s,
                                                      2.6 * s]))
        q, n = on_ellipsoid(c, r, [sx * 0.35, -0.75, 0.2])
        t.put("#8a74a0", "Nostril bump", t.sph(_add(q, n, -1), 2.6 * s))
    q, n = on_ellipsoid(g["body_c"], g["body_r"], [0.4, -0.2, 0.9])
    bow(t, _add(q, n, 1.5), 4.5 * s, "#4fc3f7")


def zebra_marks(t, g):
    s = g["s"]
    stripes_on(t, g["body_c"], g["body_r"], INK, 7, 1.9 * s,
               span=(-0.75, 0.8), reach=120, seed=7)
    c, r = g["head_c"], g["head_r"]
    for k in range(3):
        for sx in (1, -1):
            q, n = on_ellipsoid(c, r, [sx * (0.75 - k * 0.1), 0.1 - k * 0.1,
                                       0.3 + k * 0.25])
            t.put(INK, "Face stripe", t.disc(_add(q, n, 0.2), n, 1.3 * s,
                                             5 * s, 0.6 * s, turn=60 * sx))
    for f in g["feet"]:
        for k in range(2):
            z = g["leg_r"] * 1.6 + k * 4 * s
            t.put(INK, "Leg stripe", t.ring([f[0], f[1], z],
                                            g["leg_r"] * 0.98, 1.0 * s))


def fox_socks(t, g):
    for sx in (1, -1):
        t.put(INK, "Sock", t.cap([sx * 9.28, -13.2, 20], [sx * 9.5, -15, 8],
                                 6.7), material="Matte")
        t.put(INK, "Paw", t.ell([sx * 9.5, -16, 5], [6.5, 7.3, 4.5]),
              material="Matte")


def white_cheeks(colour=WHITE):
    """Pale cheek fluff (fox, tiger): over the head's cheek lobes."""
    def draw(t, g):
        c, r, hs = g["head_c"], g["head_r"], g["hs"]
        for sx in (1, -1):
            q = _add(c, [sx * r[0] * 0.8, -4.5 * hs, -r[2] * 0.44])
            t.put(colour, "Cheek fluff", t.ell(q, [9.2 * hs, 7.6 * hs,
                                                  6.8 * hs]),
                  material="Matte")
    return draw


def cat_tabby(colour):
    def draw(t, g):
        stripes_on(t, g["body_c"], g["body_r"], colour, 3, 1.6,
                   span=(-0.05, 0.6), reach=75, seed=3)
        c, r = g["head_c"], g["head_r"]
        for dx in (-4, 0, 4):
            q, n = on_ellipsoid(c, r, [dx / 22, -0.6, 0.8])
            t.put(colour, "Forehead stripe", t.disc(_add(q, n, 0.2), n, 1.2,
                                                    4.5 - abs(dx) * 0.3, 0.5))
    return draw


def koala_nose(t, g):
    c, r = g["head_c"], g["head_r"]
    q, n = on_ellipsoid(c, r, [0, -1, -0.1])
    t.put("#3a3440", "Nose", t.ell(_add(q, n, 1), [6.5, 5, 8.5]),
          material="Glass")
    t.put(WHITE, "Nose shine", t.sph(_add(q, [-2.5, -5.5, 3.5]), 1.3),
          material="Emissive")


def owl_branch(t, g):
    t.put("#8d6e4f", "Branch", t.cap([-30, -4, 3], [30, -4, 3], 3.2))
    t.put("#7cb342", "Leaf", t.disc([24, -6, 7], [0.3, -1, 0.6], 4, 7, 0.8,
                                    turn=30))


def duck_extras(t, g):
    c, r = g["head_c"], g["head_r"]
    q, _n = on_ellipsoid(c, r, [0, 0.2, 1])
    sail = _add(q, [0, 0, 1])
    t.put(WHITE, "Sailor hat", t.ell(sail, [10, 10, 4]),
          t.cap(_add(sail, [0, 0, -1]), _add(sail, [0, 0, 1]), 9))
    t.put("#1e5aa8", "Hat band", t.ring(_add(sail, [0, 0, -1.8]), 9.3, 1.1))


def chicken_egg(t, g):
    t.put("#f3e3c0", "Egg", t.ell([18, -18, 7], [5.5, 5.5, 7.2]))


def frog_crown(t, g):
    crown(t, dict(head_c=[0, -12, 44], head_r=[26, 20, 15]))


def snake_bow(t, g):
    q, n = on_ellipsoid(g["head_c"], g["head_r"], [0.5, 0.1, 0.85])
    bow(t, _add(q, n, 1), 4.5, "#f06292")


def turtle_flower(t, g):
    q, n = on_ellipsoid(g["head_c"], g["head_r"], [0.5, -0.2, 0.85])
    q = _add(q, n, 1.5)
    for k in range(5):
        a = 2 * math.pi * k / 5
        t.put(WHITE, "Petal", t.ell(_add(q, [math.cos(a) * 2.8, 0,
                                             math.sin(a) * 2.8]), [2, 1, 2]))
    t.put(GOLD, "Flower heart", t.sph(_add(q, [0, -0.8, 0]), 1.4))


def dalmatian_spots(t, g):
    spots_on(t, g["body_c"], g["body_r"], INK, 18, 3.4, seed=7, zmin=-0.5)
    spots_on(t, g["head_c"], g["head_r"], INK, 3, 2.2, seed=9, zmin=0.3)


# ============================================================ species
def _sit(name, colour, **kw):
    kw.update(name=name, colour=colour, plan=sit)
    return kw


def _stand(name, colour, **kw):
    kw.update(name=name, colour=colour, plan=stand)
    return kw


SPECIES = {
    "Dog": _sit("Dog", "#e0a868", light="#fbf0dc", ears="floppy",
                ear_colour="#9a5f2e", ear_size=8.5, muzzle=9.5,
                nose_style="button", mouth="open", iris=BROWN_EYE,
                collar=(RED, "tag", GOLD), tail="curl", tail_tip="#fbf0dc",
                extras=[prop_bone]),
    "Dalmatian": _stand("Dalmatian", "#fbfaf6", light="#fbfaf6",
                        ears="floppy", ear_colour=INK, ear_size=7,
                        muzzle=8.5, muzzle_colour="#fbfaf6",
                        nose_style="button", mouth="open",
                        collar=("#1e88e5", "tag", GOLD), tail="tuft",
                        tail_tip="#fbfaf6", paws="#fbfaf6",
                        extras=[dalmatian_spots, eye_patch(INK, -1)]),
    "Cat": _sit("Cat", "#f2a65a", light="#fff3e2", ears="pointy",
                inner_ear=PINK, muzzle=8.2, muzzle_colour="#fff3e2",
                nose_style="heart", nose="#f06b8b", mouth="w",
                iris="#7cc04a", lashes=2, whiskers=True, cheek_fluff=True,
                collar=("#e91e63", "bell", GOLD), tail="curl",
                tail_tip="#fff3e2", extras=[cat_tabby("#c8702e")]),
    "Black cat": _sit("Black cat", "#34303a", light="#4a4452",
                      ears="pointy", inner_ear=PINK, muzzle=8.2,
                      muzzle_colour="#4a4452", nose_style="heart",
                      nose="#f06b8b", mouth="w", iris="#f2d13a", lashes=2,
                      whiskers=True, whisker_colour="#d8d4dc",
                      cheek_fluff=True, collar=("#7e57c2", "bow", "#b39ddb"),
                      tail="curl", bib=False),
    "Fox": _sit("Fox", "#ef7a2e", light="#fbfaf6", ears="pointy",
                inner_ear="#fbfaf6", ear_tip=INK, muzzle=8.6,
                muzzle_colour="#fbfaf6", nose_style="button", mouth="w",
                iris="#e0a030", cheek_fluff=True, tail="fluffy",
                tail_tip="#fbfaf6", extras=[fox_socks, white_cheeks()]),
    "Bear": _sit("Bear", "#9a643a", light="#dcb48a", ears="round",
                 inner_ear="#dcb48a", muzzle=10, muzzle_colour="#e8c9a0",
                 nose_style="button", mouth="smile", tail="stub",
                 extras=[prop_honey]),
    "Panda": _sit("Panda", "#fbfaf6", light="#fbfaf6", ears="round",
                  ear_colour=INK, inner_ear=None, muzzle=9.5, bib=False,
                  nose_style="button", mouth="smile", iris="#3a2a2a",
                  tail="stub", feet=INK, extras=[panda_marks, prop_bamboo]),
    "Koala": _sit("Koala", "#a5abb3", light="#eceef2", ears="fluffy",
                  ear_size=10, nose_style="none", mouth="smile",
                  tail="stub", head_wide=1.05,
                  extras=[koala_nose, prop_leaf]),
    "Rabbit": _sit("Rabbit", "#f3efe9", light="#fbfaf6", ears="long",
                   ear_size=7.5, inner_ear=PINK, muzzle=7.2,
                   nose_style="heart", nose="#f06b8b", mouth="buck",
                   whiskers=True, whisker_colour="#c0b8c4", tail="puff",
                   lashes=2, extras=[prop_carrot, head_bow("#f06292", -1)]),
    "Mouse": _sit("Mouse", "#b9b3be", light="#f3efe9", ears="round",
                  ear_size=12, inner_ear=PINK, muzzle=7, nose_style="heart",
                  nose="#f06b8b", mouth="buck", whiskers=True, tail="long",
                  tail_colour=PINK, head=1.05, extras=[prop_cheese]),
    "Tiger": _sit("Tiger", "#f5892e", light="#fff3e2", ears="round",
                  ear_size=6.8, inner_ear="#fff3e2", muzzle=9,
                  muzzle_colour="#fff3e2", nose_style="heart",
                  nose="#f06b8b", mouth="w", iris="#e0a030", whiskers=True,
                  cheek_fluff=True, tail="curl", tail_tip=INK,
                  extras=[tiger_marks(INK)]),
    "Lion": _sit("Lion", "#f4bf55", light="#fde7b8", ears="round",
                 ear_size=6.5, inner_ear="#fde7b8", muzzle=9,
                 muzzle_colour="#fde7b8", nose_style="heart", nose="#8b4a2b",
                 mouth="w", iris="#c07a2a", tail="tuft",
                 tail_tip="#a8561f",
                 extras=[lion_mane("#c8672a", "#a8561f"), crown]),
    "Horse": _stand("Horse", "#b8773f", light="#d9a06a", ears="pointy",
                    inner_ear="#7a4a24", ear_size=6.5, snout=(14, 16, 12),
                    muzzle=(12.5, 8, 8.5), muzzle_colour="#f0d4b4",
                    nose="#7a4a24", leg=21, leg_r=6.4, neck=9,
                    hoof="#4a3528", tail="horse", tail_colour="#4a3528",
                    lashes=2, extras=[horse_mane("#4a3528", blaze=WHITE)]),
    "Donkey": _stand("Donkey", "#9c9ca6", light="#ececf0", ears="long",
                     ear_size=6.2, inner_ear="#6b6b75", snout=(14, 16, 12),
                     muzzle=(12.5, 8, 8.5), muzzle_colour="#f3f3f5",
                     nose="#55525c", leg=17, leg_r=6.4, neck=6,
                     hoof="#3b3a40", tail="tuft", tail_tip="#3b3a40",
                     extras=[horse_mane("#55525c")]),
    "Zebra": _stand("Zebra", "#fbfaf6", light="#fbfaf6", ears="pointy",
                    inner_ear=INK, ear_size=6.2, snout=(14, 16, 12),
                    muzzle=(12.5, 8, 8.5), muzzle_colour=INK,
                    nose="#55525c", leg=19, leg_r=6.2, neck=8, hoof=INK,
                    tail="tuft", tail_tip=INK, belly=False,
                    extras=[zebra_marks, horse_mane(INK)]),
    "Cow": _stand("Cow", "#fbfaf6", light="#fbfaf6", ears="side",
                  ear_colour="#fbfaf6", snout=(15, 14, 11),
                  muzzle=(14.5, 8.5, 9.5), muzzle_colour="#f7b6c6",
                  nose="#b0506b", hoof="#5a4535", tail="tuft",
                  tail_tip=INK, leg=15, lashes=3, belly=False,
                  collar=("#6d4c41", "bell", GOLD), extras=[cow_extras]),
    "Pig": _stand("Pig", "#f7b6c6", light="#fbd0da", ears="side",
                  ear_colour="#f39cb2", inner_ear="#f7b6c6",
                  body=(24, 27, 21), hoof="#d77c95", tail="curly",
                  nose_style="none", mouth="none", lashes=2,
                  extras=[pig_face, head_bow("#81d4fa", 1)]),
    "Sheep": _stand("Sheep", "#3b3740", ears="side", ear_colour="#3b3740",
                    inner_ear="#6b6570", muzzle=7.5,
                    muzzle_colour="#4a4650", nose_style="heart",
                    nose="#f06b8b", mouth="smile", hoof="#2a2326",
                    tail="puff", tail_tip="#fbfaf6", leg=13, leg_r=5.4,
                    belly=False, lashes=2, extras=[sheep_wool]),
    "Elephant": _stand("Elephant", "#9fb3c8", light="#c3d2e0", ears="fan",
                       ear_size=11, inner_ear="#f4b6c2", body=(28, 31, 25),
                       head=1.05, leg=15, leg_r=9.5, paws="#9fb3c8",
                       tail="tuft", tail_tip="#6d7f93", mouth="smile",
                       nose_style="none", belly=False,
                       extras=[elephant_extras]),
    "Giraffe": _stand("Giraffe", "#f5c451", light="#fbe7a8", ears="side",
                      ear_size=6, head=0.85, snout=(12, 14, 10),
                      muzzle=(10.5, 7, 7.5), muzzle_colour="#fbe7a8",
                      nose="#8b5a2b", leg=30, leg_r=5.4, neck=46,
                      neck_r=8.2, head_ahead=4, hoof="#6b3f20", tail="tuft",
                      tail_tip="#6b3f20", body=(19, 26, 17), lashes=3,
                      belly=False, extras=[giraffe_extras]),
    "Hippo": _stand("Hippo", "#a894c0", light="#d8cae8", ears="round",
                    ear_size=5, inner_ear="#f4b6c2", body=(30, 32, 24),
                    head_wide=1.08, snout=(22, 14, 14), nose="#6b5680",
                    leg=11, leg_r=9, tail="puff", tail_tip="#a894c0",
                    eye_up=0.4, mouth="smile", paws="#a894c0",
                    extras=[hippo_extras]),
    "Gorilla": dict(name="Gorilla", plan=ape, colour="#3b3740",
                    face="#6b6570", crest=True,
                    extras=[prop_banana]),
    "Monkey": dict(name="Monkey", plan=ape, colour="#8b5a2b",
                   face="#f0c9a0", face_ears=True, tail=True,
                   arms="hold", extras=[prop_banana]),
    "Duck": dict(name="Duck", plan=bird, colour="#f9d94e", beak="#f39c12",
                 flat_beak=True, wing="#f2c630", hair="#f9d94e",
                 extras=[duck_extras]),
    "Chicken": dict(name="Chicken", plan=bird, colour="#fbfaf6", comb=True,
                    beak="#f5b041", tail_feathers="#ece4d4", lashes=2,
                    extras=[chicken_egg]),
    "Owl": dict(name="Owl", plan=bird, colour="#9c6b45", belly="#ecd3ae",
                owl=True, upright=True, beak="#f5b041", wing="#7a4f30",
                disc="#ecd3ae", iris="#f39c12", chevrons="#9c6b45",
                extras=[owl_branch]),
    "Penguin": dict(name="Penguin", plan=bird, colour="#2f3440",
                    belly="#fbfaf6", upright=True,
                    beak="#f39c12", feet="#f39c12",
                    extras=[scarf(RED, WHITE)]),
    "Snake": dict(name="Snake", plan=snake, colour="#86cc74", band="#4a9a45",
                  extras=[snake_bow]),
    "Frog": dict(name="Frog", plan=frog, colour="#6cc26b",
                 extras=[frog_crown]),
    "Turtle": dict(name="Turtle", plan=turtle, colour="#94d47f",
                   shell="#6b9a3a", extras=[turtle_flower]),
    "Crocodile": dict(name="Crocodile", plan=crocodile, colour="#5aa84f",
                      scale=1.35),
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
    """*group* lifted so its lowest point is z = 0."""
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
