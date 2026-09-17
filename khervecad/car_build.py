"""The Car Builder's geometry (Qt-free): a `car_models` entry plus the
builder's choices (paint, rim, tyre, finish, caliper, scale) -> one
coloured union of closed polyhedra, true size in mm, front towards -Y,
wheels on z = 0, centred on X and Y.

The body is a LOFT through cross-sections every ~30 mm along the car
(`closed_grid`), so it keeps its curves with no boolean and previews
exactly:
- the lower body's section (`_body_ring`) runs across the car in
  cosine-spaced columns: a crowned top rolled down at the sides, a
  bottom that lifts at the bumpers — and, over each wheel, rises to the
  ARCH (a circle round the axle) in the outer band, so the wheel shows
  under a fender instead of hiding in a slab; the top bulges over the
  arch where the shape has fenders;
- a dark inner tub between the wheels closes the wheel wells;
- the greenhouse (`_cabin_ring`) stands on the body top, its side glass
  leaning in by the tumblehome, the roof line rising from the cowl,
  flat, then falling to the deck (a fastback on a 911); a body-coloured
  roof panel lies on it. An open car gets a windscreen and a cockpit.
Details: lights, grille (BMW kidneys, the Mercedes star, a Bugatti
horseshoe, intakes), tail lights, wings, mirrors and exhausts; wheels
from `car_wheels`, front and rear at their own factory sizes.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from . import car_models, car_wheels
from .car_wheels import closed_grid
from .landmark_kit import Kit
from .model import CadNode

GLASS = "#1b242e"
TRIM = "#1e1f22"
CHROME = "#dfe2e6"
LAMP = "#f3f6f8"
TAIL = "#c4121b"

#: columns across a body section (each side of the ring)
COLUMNS = 18
#: stations along the body
STATIONS = 150

SCALES = {"1:18": 1 / 18, "Full-size": 1.0, "1:43": 1 / 43, "1:10": 0.1}

DEFAULTS = dict(paint="", rim="", tyre="As delivered", finish="Silver",
                caliper="Red", scale=1.0)


def _smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def _knots(pairs, s):
    """Cosine interpolation through (s, v) knots."""
    for (s0, v0), (s1, v1) in zip(pairs, pairs[1:]):
        if s <= s1 or (s1, v1) == pairs[-1]:
            t = 0.0 if s1 == s0 else (s - s0) / (s1 - s0)
            t = min(1.0, max(0.0, t))
            return v0 + (v1 - v0) * (1 - math.cos(math.pi * t)) / 2
    return pairs[-1][1]


class Car:
    """One car's measurements and profile functions."""

    def __init__(self, key, options=None):
        self.key = key
        self.spec = car_models.CARS[key]
        self.p = car_models.profile(key)
        o = dict(DEFAULTS)
        o.update({k: v for k, v in (options or {}).items()
                  if v not in (None, "")})
        self.options = o
        s = self.spec
        self.L, self.W, self.H = float(s["L"]), float(s["W"]), float(s["H"])
        self.wheels = []
        for text in (s["tyre_front"], s["tyre_rear"]):
            tw, ratio, D = car_wheels.tyre_size(text)
            self.wheels.append((tw, ratio, D))
        fo = self.p["fo"] * (self.L - s["wb"])
        self.axles = [-self.L / 2 + fo, -self.L / 2 + fo + s["wb"]]
        self.gc = 0.11 * self.H
        H, p = self.H, self.p
        self.top_knots = [(0.0, p["nose"] * H), (p["ws"], p["cowl"] * H),
                          (p["cb"], p["deck"] * H), (1.0, p["tail"] * H)]
        self.tw_max = max(w[0] for w in self.wheels)

    # ------------------------------------------------------- profiles
    def y(self, s):
        return -self.L / 2 + s * self.L

    def half_width(self, s):
        p = self.p
        front = p["nose_w"] + (1 - p["nose_w"]) * math.sin(
            min(1.0, s / 0.2) * math.pi / 2) ** 0.7
        rear = p["tail_w"] + (1 - p["tail_w"]) * math.sin(
            min(1.0, (1 - s) / 0.16) * math.pi / 2) ** 0.7
        return self.W / 2 * min(front, rear)

    def top(self, s):
        return _knots(self.top_knots, s)

    def bottom(self, s):
        lip = 0.35 * (self.p["nose"] * self.H - self.gc)
        return (self.gc + lip * (1 - _smooth(s / 0.07))
                + lip * (1 - _smooth((1 - s) / 0.06)))

    def arch(self, s):
        """z of the wheel arch over this station, or None."""
        y = self.y(s)
        for ya, (tw, ratio, D) in zip(self.axles, self.wheels):
            R = D / 2 + 35
            dy = y - ya
            if abs(dy) < R:
                return D / 2 + math.sqrt(R * R - dy * dy)
        return None

    def wheel_x(self, i):
        return self.W / 2 - 25 - self.wheels[i][0] / 2

    def roof(self, s):
        p, H = self.p, self.H
        cowl = self.top(p["ws"])
        if s <= p["rf"]:
            t = (s - p["ws"]) / max(1e-6, p["rf"] - p["ws"])
            return cowl + (H - cowl) * math.sin(
                min(1.0, max(0.0, t)) * math.pi / 2) ** 0.85
        if s <= p["rr"]:
            mid, half = (p["rf"] + p["rr"]) / 2, max(1e-6,
                                                     (p["rr"] - p["rf"]) / 2)
            return H - 0.012 * H * ((s - mid) / half) ** 2
        deck = self.top(p["cb"])
        t = (s - p["rr"]) / max(1e-6, p["cb"] - p["rr"])
        return H * 0.988 - (H * 0.988 - deck) * min(1.0, t) ** 1.5

    # --------------------------------------------------------- sections
    def columns(self):
        return [-math.cos(math.pi * i / (COLUMNS - 1))
                for i in range(COLUMNS)]

    def body_top_at(self, s, u):
        """The lower body's top z at station *s*, column *u* (-1..1)."""
        a = self.half_width(s)
        zb, zt = self.bottom(s), self.top(s)
        arch = self.arch(s)
        au = abs(u)
        if arch is not None:
            bump = max(0.0, arch + 55 - zt)
            if self.p["fenders"]:
                zt += bump * _smooth((au - 0.45) / 0.35)
            else:
                zt += bump
        rt = min(0.4 * (zt - zb), 0.09 * self.W, 150.0)
        c = min(0.5, rt / a)
        roll = 0.0
        if au > 1 - c:
            q = (au - (1 - c)) / c
            roll = rt * (1 - math.sqrt(max(0.0, 1 - q * q)))
        return zt + 0.02 * a * (1 - u * u) - roll

    def body_ring(self, s):
        y, a = self.y(s), self.half_width(s)
        zb = self.bottom(s)
        arch = self.arch(s)
        inner = self.W / 2 - 55 - self.tw_max
        cols = self.columns()
        ring = [(a * u, y, self.body_top_at(s, u)) for u in reversed(cols)]
        for u in cols:
            x = a * u
            top = self.body_top_at(s, u)
            z = zb + 30 * max(0.0, abs(u) - 0.85) / 0.15
            if arch is not None and abs(x) > inner:
                z = max(z, min(arch, top - 25))
            ring.append((x, y, z))
        return ring

    def tub_ring(self, s):
        y = self.y(s)
        a = min(self.W / 2 - 60 - self.tw_max, self.half_width(s) - 20)
        zb = self.gc
        zt = max(zb + 60, self.top(s) - 40)
        pts = []
        for u in reversed(self.columns()):
            pts.append((a * u, y, zt))
        for u in self.columns():
            pts.append((a * u, y, zb))
        return pts

    def cabin_ring(self, s, f0=0.0, f1=1.0, lift=0.0):
        """A slice of the greenhouse's section between the fractions
        *f0* and *f1* of its height — the shoulder, the window band and
        the roof are stacked slabs, so they meet face to face instead of
        fighting for the same surface. Side glass leans in with the
        tumblehome, so x narrows with the fraction too."""
        p = self.p
        y, a = self.y(s), self.half_width(s) * p["cabin"]
        zr = self.roof(s) + lift
        top, bottom = [], []
        for u in self.columns():
            zbase = self.body_top_at(s, u * p["cabin"]) - 12
            au = abs(u)
            roll = 0.12 * (self.H - self.top(p["ws"])) * _smooth(
                (au - 0.6) / 0.4) ** 2
            zt = max(zbase + 8, zr + 0.02 * a * (1 - u * u) - roll)

            def at(f):
                x = a * u * (1 + (p["tumble"] - 1) * f)
                return (x, y, zbase + (zt - zbase) * f)
            top.append(at(f1))
            bottom.append(at(f0))
        return list(reversed(top)) + bottom

    # ------------------------------------------------------------ build
    def stations(self, s0, s1, n):
        return [s0 + (s1 - s0) * i / (n - 1) for i in range(n)]

    def build(self) -> CadNode:
        o, p = self.options, self.p
        paint = str(car_models.PAINTS.get(o["paint"], o["paint"]))
        if not paint.startswith("#"):
            paint = car_models.PAINTS[self.spec["paint"]]
        kit = Kit()
        body = kit.mesh(paint, "Metal")
        closed_grid(body, [self.body_ring(s) for s in
                           self.stations(0.0, 1.0, STATIONS)])
        f_edge = (self.axles[0] - self.wheels[0][2] / 2 + self.L / 2) / self.L
        r_edge = (self.axles[1] + self.wheels[1][2] / 2 + self.L / 2) / self.L
        closed_grid(kit.mesh(TRIM, "Matte"),
                    [self.tub_ring(s) for s in
                     self.stations(max(0.02, f_edge), min(0.98, r_edge), 40)])
        if p["open"]:
            self._open_cabin(kit, paint)
        else:
            cabin = self.stations(p["ws"], p["cb"], 70)
            glass = kit.mesh(GLASS, "Plastic")
            for f0, f1, mesh_ in ((0.0, 0.26, body), (0.26, 0.82, glass),
                                  (0.82, 1.0, body)):
                closed_grid(mesh_, [self.cabin_ring(s, f0, f1)
                                    for s in cabin])
        self._lights(kit)
        self._grille(kit)
        self._wing(kit, paint)
        self._mirrors(kit, paint)
        self._exhaust(kit)
        group = kit.node(label_of(self.key))
        for i in (0, 1):
            group.add(self._wheel_pair(i))
        scale = float(o.get("scale") or 1.0)
        if abs(scale - 1.0) > 1e-9:
            wrap = CadNode("scale", group.name, dict(x=scale, y=scale,
                                                     z=scale))
            wrap.add(group)
            return wrap
        return group

    # ---------------------------------------------------------- details
    def _open_cabin(self, kit, paint):
        p = self.p
        closed_grid(kit.mesh(GLASS, "Plastic"),
                    [self.cabin_ring(s) for s in
                     self.stations(p["ws"], p["cb"], 12)])
        s0, s1 = p["cb"] + 0.01, p["cb"] + 0.2
        a = self.half_width((s0 + s1) / 2) * 0.72
        z = self.top((s0 + s1) / 2)
        kit.box(-a, self.y(s0), z - 10, a, self.y(s1), z + 6, TRIM)
        for side in (-1, 1):
            x = side * a * 0.45
            kit.box(x - 200, self.y(s1) - 180, z, x + 200, self.y(s1) - 60,
                    z + 330, TRIM)

    def _lights(self, kit):
        kind = self.spec["lights"]
        s = 0.035
        a, y, zt = self.half_width(s), self.y(s), self.top(s)
        for side in (-1, 1):
            if kind in ("round", "twin"):
                n = 2 if kind == "twin" else 1
                for k in range(n):
                    x = side * a * (0.62 - 0.2 * k)
                    kit.path([(x, y - 40, zt - 70), (x, y + 30, zt - 70)],
                             70 if n == 1 else 55, LAMP, "Emissive",
                             sides=16)
            elif kind == "slim":
                x = side * a * 0.62
                kit.obox(x, y + 10, zt - 55, 360, 90, 45, side * -14,
                         LAMP, "Emissive")
            elif kind == "popup":
                s2 = 0.08
                x = side * self.half_width(s2) * 0.6
                kit.obox(x, self.y(s2), self.top(s2) - 5, 330, 180, 14, 0,
                         TRIM, "Matte")
        s = 0.99
        a, y, zt = self.half_width(s), self.y(s), self.top(s)
        tails = self.spec["tails"]
        if tails == "bar":
            kit.box(-0.85 * a, y - 20, zt - 110, 0.85 * a, y + 20, zt - 60,
                    TAIL, "Emissive")
        for side in (-1, 1):
            if tails == "round":
                for k in range(2):
                    x = side * a * (0.72 - 0.22 * k)
                    kit.path([(x, y - 30, zt - 95), (x, y + 25, zt - 95)],
                             50, TAIL, "Emissive", sides=16)
            elif tails == "slim":
                kit.obox(side * a * 0.6, y, zt - 90, 380, 50, 45, 0,
                         TAIL, "Emissive")

    def _grille(self, kit):
        kind = self.spec["grille"]
        y0 = -self.L / 2
        zb, zt = self.bottom(0.0), self.top(0.0)
        zm = (zb + zt) / 2
        a = self.half_width(0.0)
        if kind == "kidney":
            for side in (-1, 1):
                x = side * 95
                kit.obox(x, y0 + 8, zm - 40, 180, 40, 150, 0, CHROME, "Metal")
                kit.obox(x, y0 + 5, zm - 25, 150, 40, 120, 0, TRIM)
        elif kind == "star":
            kit.obox(0, y0 + 8, zm - 80, 0.9 * a, 40, 170, 0, CHROME, "Metal")
            kit.obox(0, y0 + 5, zm - 70, 0.85 * a, 40, 150, 0, TRIM)
            yc, zc = y0 - 20, zm + 5
            kit.path([(0, yc, zc), (0, yc + 30, zc)], 70, CHROME, "Metal",
                     sides=24)
            for k in range(3):
                t = math.radians(90 + 120 * k)
                kit.bar((0, yc - 6, zc), (62 * math.cos(t), yc - 6,
                                          zc + 62 * math.sin(t)),
                        7, TRIM)
        elif kind == "horseshoe":
            kit.obox(0, y0 + 8, zb + 40, 420, 40, 300, 0, CHROME, "Metal")
            kit.obox(0, y0 + 5, zb + 55, 380, 40, 260, 0, TRIM)
        if kind in ("intake", "star", "kidney", "horseshoe"):
            kit.obox(0, y0 + 5, zb + 15, 1.2 * a, 40, 90, 0, TRIM)

    def _wing(self, kit, paint):
        kind = self.spec["wing"]
        s = 0.97
        a, y1, z = self.half_width(s), self.y(1.0), self.top(s)
        if kind in ("ducktail", "whale"):
            w = 0.8 * a if kind == "ducktail" else 0.95 * a
            depth, rise = (0.09, 70) if kind == "ducktail" else (0.14, 120)
            ya = self.y(1 - depth)
            za = self.top(1 - depth)
            kit.solid([(-w, ya, za - 5), (w, ya, za - 5),
                       (-w, y1 - 20, z - 5), (w, y1 - 20, z - 5),
                       (-w, y1, z + rise), (w, y1, z + rise)], paint, "Metal")
            if kind == "whale":
                kit.box(-w, y1 - 12, z + rise - 8, w, y1 + 12, z + rise + 6,
                        TRIM, "Rubber")
        elif kind in ("wing", "hoop"):
            span = 0.95 * a
            zw = z + (230 if kind == "wing" else 90)
            yc = self.y(0.955)
            for side in (-1, 1):
                x = side * span * 0.7
                kit.box(x - 12, yc - 60, z - 20, x + 12, yc + 60, zw, TRIM)
            colour = TRIM if kind == "wing" else paint
            kit.solid([(-span, yc - 170, zw), (span, yc - 170, zw),
                       (-span, yc + 150, zw + 25), (span, yc + 150, zw + 25),
                       (-span, yc + 150, zw + 50), (span, yc + 150, zw + 50),
                       (-span, yc - 170, zw + 12), (span, yc - 170, zw + 12)],
                      colour, "Metal")
        elif kind == "lip":
            kit.solid([(-0.8 * a, y1 - 90, z - 4), (0.8 * a, y1 - 90, z - 4),
                       (-0.8 * a, y1, z - 4), (0.8 * a, y1, z - 4),
                       (-0.8 * a, y1, z + 45), (0.8 * a, y1, z + 45)],
                      paint, "Metal")

    def _mirrors(self, kit, paint):
        p = self.p
        s = p["ws"] + 0.025
        a = self.half_width(s) * p["cabin"]
        y, z = self.y(s), self.body_top_at(s, p["cabin"])
        for side in (-1, 1):
            x = side * (a + 110)
            kit.bar((side * (a - 10), y + 20, z + 40), (x, y, z + 80), 12,
                    TRIM)
            kit.obox(x, y, z + 45, 170, 70, 95, 0, paint, "Metal")

    def _exhaust(self, kit):
        y1 = self.L / 2
        z = self.bottom(1.0) + 55
        for side in (-1, 1):
            x = side * 0.22 * self.W / 2
            kit.path([(x, y1 - 200, z), (x, y1 + 25, z)], 42, CHROME,
                     "Metal", sides=16)

    def _wheel_pair(self, i) -> CadNode:
        o = self.options
        tw, ratio, D = self.wheels[i]
        tyre_ratio, tread = car_wheels.TYRES.get(
            o["tyre"], car_wheels.TYRES["As delivered"])
        rim = o["rim"] or self.spec["rim"]
        pair = CadNode("union", "Front wheels" if i == 0 else "Rear wheels")
        for side in (-1, 1):
            kit = Kit()
            car_wheels.build_wheel(kit, D, tw, tyre_ratio or ratio, tread,
                                   rim, o["finish"], o["caliper"])
            wheel = kit.node(("Right " if side > 0 else "Left ")
                             + ("front" if i == 0 else "rear"))
            rot = CadNode("rotate", wheel.name, dict(x=0.0, y=90.0 * side,
                                                     z=0.0))
            rot.add(wheel)
            move = CadNode("translate", wheel.name, dict(
                x=side * self.wheel_x(i), y=self.axles[i], z=D / 2))
            move.add(rot)
            pair.add(move)
        return pair


def label_of(key: str) -> str:
    car = car_models.CARS[key]
    return f"{car['make']} {car['model']}"


def build_car(key: str, options: dict | None = None) -> CadNode:
    """The car *key* with the builder's *options*, as one node."""
    return Car(key, options).build()


# ------------------------------------------------------- Part Library

def _part_builder(key):
    def build(dims):
        size = dims.get("_size") or "Full-size"
        scale = float(dims.get("scale") or SCALES.get(size, 1.0))
        return build_car(key, dict(paint=dims.get("_color", ""),
                                   scale=scale))
    return build


CATEGORY = "Cars"

PARTS = {
    f"car_{key}": dict(
        label=car_models.label(key), category=CATEGORY,
        sizes={name: dict(scale=v) for name, v in SCALES.items()},
        fields=[("scale", "Scale")],
        colors=[car["paint"]] + [n for n in car_models.PAINTS
                                 if n != car["paint"]],
        build=_part_builder(key))
    for key, car in car_models.CARS.items()
}
