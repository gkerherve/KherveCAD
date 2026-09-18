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

from . import car_details, car_models, car_profiles, car_wheels
from .car_wheels import closed_grid
from .landmark_kit import Kit
from .model import CadNode

GLASS = "#141c24"
TRIM = "#1e1f22"
CHROME = "#dfe2e6"
LAMP = "#f3f6f8"
TAIL = "#c4121b"

#: columns across a body section (each side of the ring)
COLUMNS = 18
#: stations along the body
STATIONS = 150
#: heights sampled across a measured section
SECTION_LEVELS = 30
#: the end view has narrowed to this much of its widest at the beltline
BELT_WIDTH = 0.90
#: how deep the body-coloured roof panel is, over the glass
ROOF_PANEL = 130.0
#: a greenhouse never narrows past this much of its own beltline
CABIN_WAIST = 0.62
#: how square a section is: 2 is an ellipse, 8 nearly a rectangle
SECTION_ROUND = 4.5
#: a section never pulls in past this much of its width, so a flank
#: stays a flank
ROUND_FLOOR = 0.62
#: the last of the car's length over which its ends round away
END_ROUND = 0.05
#: how much of its width is left at the very nose and tail
END_WIDTH = 0.72
#: and how much of its height the tail has lost by its last station
END_DROP = 0.18
#: the tail starts falling here at the latest
TAIL_START = 0.72
#: the body (not the wing) has fallen to this much of the height by
#: the very tail
TAIL_DROP = 0.62
#: the tail's roof line counts as a wing this far above the deck
WING_GAP = 60.0

SCALES = {"1:18": 1 / 18, "Full-size": 1.0, "1:43": 1 / 43, "1:10": 0.1}

#: follow the blueprint-measured profiles (`car_profiles`) where there
#: are any: the drawing's own bonnet, roof, deck, floor and plan beat
#: any preset, and the nose is where a preset is worst.
USE_MEASURED = True

DEFAULTS = dict(paint="", rim="", tyre="As delivered", finish="Silver",
                caliper="Red", scale=1.0)


def _smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def sample(curve, s):
    """A measured curve (evenly spaced, nose to tail) at *s*."""
    n = len(curve) - 1
    x = min(1.0, max(0.0, s)) * n
    i = min(n - 1, int(x))
    return curve[i] + (curve[i + 1] - curve[i]) * (x - i)


def _round_section(xs, passes=2):
    """Round a section's corners: a weighted pass down its levels."""
    out = list(xs)
    for _ in range(passes):
        prev = list(out)
        for i in range(len(out)):
            a = prev[max(0, i - 1)]
            b = prev[i]
            c = prev[min(len(prev) - 1, i + 1)]
            out[i] = 0.25 * a + 0.5 * b + 0.25 * c
    return out


def smooth_curve(curve, passes=2, window=5):
    """A traced curve carries the drawing's own noise — a pixel here, a
    leader line there — and a body lofted straight onto it ripples from
    station to station, which shades as vertical stripes. A couple of
    moving averages take that out and leave the shape."""
    out = list(curve)
    half = window // 2
    for _ in range(passes):
        prev = list(out)
        for i in range(len(out)):
            lo, hi = max(0, i - half), min(len(prev), i + half + 1)
            out[i] = sum(prev[lo:hi]) / (hi - lo)
    return out


def cabin_range(curve):
    """(front, back) of the greenhouse in a measured roof line: from
    its highest point, walk out to the first place where it stops
    falling — the cowl in front of the windscreen and the deck behind
    the backlight."""
    n = len(curve)
    peak = max(range(n), key=lambda i: curve[i])
    front = peak
    while front > 1 and curve[front - 1] < curve[front]:
        front -= 1
    back = peak
    while back < n - 2 and curve[back + 1] < curve[back]:
        back += 1
    return front / (n - 1), back / (n - 1)


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
        self._sections = {}
        #: how far in the body pulls under a wheel arch: the wheel
        #: stands outside this, under the wing
        self.tub_half = max(0.22 * self.W,
                            self.W / 2 - max(w[0] for w in self.wheels) - 40)
        self.measured = (car_profiles.PROFILES.get(key)
                         if USE_MEASURED else None)
        if self.measured:
            self._fit_measured()

    def _fit_measured(self):
        """Follow the blueprint for the LINE of the car — bonnet, deck,
        floor and plan — while the shape preset still says where the
        cabin starts and ends. A roof line alone cannot: on a smooth
        car it climbs from the nose to the roof without a kink, so
        hunting for the windscreen in it puts the glass over the
        bonnet."""
        m = self.measured = {k: (smooth_curve(v) if isinstance(v, list)
                                 else v)
                             for k, v in self.measured.items()}
        p = self.p
        ws, cb = p["ws"], p["cb"]
        roof = m["roof"]
        n = len(roof) - 1
        inside = [(i / n, v) for i, v in enumerate(roof)
                  if ws <= i / n <= cb]
        peak = max(v for _, v in inside)
        band = [s for s, v in inside if v > peak - 0.02]
        p["rf"], p["rr"] = (band[0], band[-1]) if len(band) > 1 \
            else (ws + (cb - ws) * 0.35, ws + (cb - ws) * 0.6)
        after = [v for i, v in enumerate(roof) if i / n > cb]
        self.deck_min = (min(after) if after else 0.0) * self.H
        self.cowl_z = sample(roof, ws) * self.H
        self.deck_z = sample(roof, cb) * self.H
        if m["width"]:
            # normalise on the body, not on a wing mirror sticking out
            ordered = sorted(m["width"])
            self.width_ref = ordered[int(0.9 * (len(ordered) - 1))] or 1.0
        else:
            self.width_ref = 1.0

    # ------------------------------------------------------- profiles
    def y(self, s):
        return -self.L / 2 + s * self.L

    def half_width(self, s):
        p = self.p
        if self.measured and self.measured["width"]:
            w = sample(self.measured["width"], s) / self.width_ref
            half = self.W / 2 * min(1.0, w)
            return max(half, self._arch_flare(s))
        front = p["nose_w"] + (1 - p["nose_w"]) * math.sin(
            min(1.0, s / 0.26) * math.pi / 2) ** 0.85
        rear = p["tail_w"] + (1 - p["tail_w"]) * math.sin(
            min(1.0, (1 - s) / 0.16) * math.pi / 2) ** 0.7
        waist = 1.0 - 0.025 * math.sin(math.pi * min(1.0, max(0.0, s)))
        return self.W / 2 * min(front, rear) * waist

    def _arch_flare(self, s):
        """How wide the body must be here to cover its own wheel: a
        stated track is the truth, and the arch flares over it. Without
        a stated track the wheels are set in from the body instead, and
        nothing flares."""
        if not self.spec.get("track"):
            return 0.0
        y = self.y(s)
        out = 0.0
        for i, (ya, (tw, _ratio, D)) in enumerate(zip(self.axles,
                                                      self.wheels)):
            reach = D * 0.55
            over = 1.0 - min(1.0, abs(y - ya) / reach)
            if over > 0:
                need = self.spec["track"][i] / 2.0 + tw / 2 + 20.0
                out = max(out, need * _smooth(over)
                          + self.W / 2 * 0.5 * (1 - _smooth(over)))
        return min(out, self.W / 2)

    def top(self, s):
        """The top of the car at this station. On a measured car it is
        the drawing's own roof line, greenhouse included: the body and
        the glass are cut out of ONE lofted shape at the beltline, so
        nothing has to be stuck on afterwards."""
        if not self.measured:
            return _knots(self.top_knots, s)
        return sample(self.measured["roof"], s) * self.H

    def bottom(self, s):
        if self.measured:
            # the drawing's floor dips to the ground at each tyre: the
            # BODY stops at the sill
            return max(sample(self.measured["floor"], s) * self.H, self.gc)
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
        """The wheel's centre across the car: inside the bodywork at
        ITS OWN station, never beyond the published width. A measured
        plan narrows towards the nose and the tail, and a track fixed
        to W/2 hung the front wheels outside the wings."""
        track = self.spec.get("track")
        if track:
            # the drawing states it; no need to infer a stance
            return track[i] / 2.0
        s = (self.axles[i] + self.L / 2) / self.L
        a = min(self.W / 2, max(self.half_width(s), 0.34 * self.W))
        return min(self.W / 2 - 25, a - 15) - self.wheels[i][0] / 2

    def roof(self, s):
        if self.measured:
            return max(sample(self.measured["roof"], s) * self.H,
                       self.top(s) + 8)
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

    def shoulder(self, s):
        """(beltline z, top z) at the centre of this station: a car has
        a CREASE where the flank turns into the bonnet or the deck, and
        the flank below it is near vertical. Over a wheel both lift to
        clear the arch — the fender bulge."""
        zb, zt = self.bottom(s), self.top(s)
        arch = self.arch(s)
        if arch is not None and not self.measured:
            # a preset body has no wing over the wheel until one is
            # raised here; a drawn one already does, so lifting it
            # again would grow a second hump over the first
            zt += max(0.0, arch + 55 - zt)
        belt = zt - self.p["belt"] * max(120.0, zt - zb)
        return belt, zt

    def belt_v(self, s):
        """Where the glass starts, as a fraction of the car's height:
        the level above which the drawing's end view narrows sharply —
        the shoulder. Below it is bodywork, above it is the greenhouse."""
        m = self.measured
        t = min(1.0, max(0.0, s))
        curve = [(1 - t) * f + t * r for f, r in zip(m["nose"], m["tail"])]
        n = len(curve) - 1
        widest = max(curve) or 1.0
        top = max((i for i, v in enumerate(curve) if v >= 0.98 * widest),
                  default=n)
        for i in range(top, n + 1):
            if curve[i] < BELT_WIDTH * widest:
                return i / n
        return 1.0

    def _section(self, s):
        """(floor z, roof z, levels, half widths) of the measured
        section at *s*, cached.

        A car's shape is the INTERSECTION of what its drawings show: the
        plan says how wide it is at this station, the end view how wide
        it is at this height, and the body is as narrow as either — so a
        nose rounds in both directions at once and a roof tapers.
        (Reading the front view as a slice instead made every section a
        box, since a projection is the whole car's envelope.)
        The wheel wells are cut in the same breath: under the arch the
        body pulls in to the tub, and the wheel stands in the gap."""
        key = round(s, 4)
        got = self._sections.get(key)
        if got is not None:
            return got
        zb, zt = self.bottom(s), self.top(s)
        # the taper to the tail starts where the cabin's glass ends,
        # and never later than TAIL_START: a 911's preset cabin runs to
        # 95 % of the car, which left no length to fall in
        cb = min(self.p["cb"], TAIL_START)
        if s > cb:
            # past the cabin the drawing's roof line carries the WING
            # as well as the body. The body itself falls away to the
            # tail: take the lower of the two, or a whale tail turns
            # the whole rear into a brick.
            f = (s - cb) / max(1e-6, 1.0 - cb)
            # the traced roof line ENDS on the wing's trailing edge, so
            # interpolating to it kept the whole tail at wing height —
            # a brick. The body itself falls to about boot height.
            line = (sample(self.measured["roof"], cb) * (1 - f)
                    + TAIL_DROP * f) * self.H
            zt = min(zt, line)
        if s > 1.0 - END_ROUND:
            f = (s - (1.0 - END_ROUND)) / END_ROUND
            zt -= (zt - zb) * END_DROP * f
        zt = max(zt, zb + 60)
        arch = self.arch(s)
        n = SECTION_LEVELS
        levels = [zb + (zt - zb) * k / (n - 1) for k in range(n)]
        plan = self.half_width(s)
        # close the very ends: a loft that runs at full width to its
        # last station ends on a flat wall, and the tail read as a
        # packing case however right the rest of the line was
        for edge in (s, 1.0 - s):
            if edge < END_ROUND:
                plan *= 1.0 - (1.0 - END_WIDTH) * (1.0 - edge / END_ROUND)
        belt = self.belt_z(s)
        belt_x = min(plan, self.W / 2 * self.section_shape(s, belt))
        xs = []
        span = max(1.0, zt - zb)
        for z in levels:
            # a rounded-rectangle section (superellipse) under the
            # drawing's own envelope: the intersection of two
            # silhouettes alone is a box, and no car is a box
            v = (z - zb) / span
            round_ = max(0.0, 1.0 - abs(2 * v - 1) ** SECTION_ROUND) \
                ** (1.0 / SECTION_ROUND)
            x = min(plan * (ROUND_FLOOR + (1 - ROUND_FLOOR) * round_),
                    self.W / 2 * self.section_shape(s, z))
            if z > belt:
                # an end view's silhouette closes to a point at the very
                # crown of the roof, but a roof is not a point at THIS
                # station: keep its shape, not its vanishing act
                x = max(x, CABIN_WAIST * belt_x)
            if arch is not None and z < arch:
                x = min(x, self.tub_half)
            xs.append(max(x, 20.0))
        # A body is not the hard intersection of two silhouettes: that
        # leaves a crease where the flank meets the bonnet and reads as
        # a box. Rounding the section down its own height puts the
        # shoulder and the roof edge back.
        xs = _round_section(xs)
        got = (zb, zt, levels, xs)
        self._sections[key] = got
        return got

    def body_top_at(self, s, u):
        """The body's outer surface z at column *u* (-1..1). On a
        measured car: the highest level of the drawing's own section
        that still reaches that far out."""
        if self.measured and self.measured.get("nose"):
            zb, zt, levels, xs = self._section(s)
            a = max(xs) or 1.0
            want = abs(u) * a * 0.999
            best = zb
            for z, x in zip(levels, xs):
                if x >= want:
                    best = z
            return best
        return self._preset_top_at(s, u)

    def _preset_top_at(self, s, u):
        """The preset body's outer surface z at column *u* (-1..1): flat-ish
        over the middle, then down to the beltline over the shoulder.
        *crisp* 1 chamfers it in a straight line (a wedge), 0 rolls it
        round (a fifties wing)."""
        a = self.half_width(s)
        belt, zt = self.shoulder(s)
        arch = self.arch(s)
        au, p = abs(u), self.p
        if arch is not None and p["fenders"]:
            # the bulge belongs over the wheel, not over the bonnet
            flat = self.top(s)
            zt = flat + (zt - flat) * _smooth((au - 0.45) / 0.4)
            belt = min(belt, zt - p["belt"] * max(120.0, zt
                                                  - self.bottom(s)))
        k = 0.62 + 0.18 * p["crisp"]
        crown = 0.035 * a * (1 - p["crisp"])
        if au <= k:
            return zt + crown * (1 - (au / k) ** 2)
        q = (au - k) / (1 - k)
        power = 1.0 + 2.2 * (1 - p["crisp"])
        return zt - (zt - belt) * q ** power

    def section_shape(self, s, z):
        """The half width at height *z* as a fraction of the widest, the
        drawing's own FRONT view morphing into its REAR view along the
        car. This is what a preset cannot guess: a round nose, a
        tumblehome, a flared wing."""
        m = self.measured
        v = min(1.0, max(0.0, z / self.H))
        t = min(1.0, max(0.0, s))
        return (1 - t) * sample(m["nose"], v) + t * sample(m["tail"], v)

    def measured_ring(self, s, z0=None, z1=None):
        """A section shaped by the drawing between the heights *z0* and
        *z1*: the plan gives its width, the side view its top and floor,
        the end views its shape."""
        y = self.y(s)
        zb, zt, _, _ = self._section(s)
        lo = zb if z0 is None else max(zb, min(z0, zt - 6))
        hi = zt if z1 is None else min(zt, max(z1, lo + 6))
        n = SECTION_LEVELS
        levels = [lo + (hi - lo) * k / (n - 1) for k in range(n)]
        xs = [self.width_at(s, z) for z in levels]
        right = [(xs[k], y, levels[k]) for k in range(n)]
        left = [(-xs[k], y, levels[k]) for k in range(n - 1, -1, -1)]
        return right + left

    def width_at(self, s, z):
        """Half the car's width at (station, height), from the drawing."""
        _, _, levels, xs = self._section(s)
        if z <= levels[0]:
            return xs[0]
        for k in range(1, len(levels)):
            if z <= levels[k]:
                span = levels[k] - levels[k - 1] or 1.0
                f = (z - levels[k - 1]) / span
                return xs[k - 1] + (xs[k] - xs[k - 1]) * f
        return xs[-1]

    def belt_z(self, s):
        """The beltline height at this station. Worked out from the
        floor and roof lines directly, never from `_section` — that
        asks for the beltline itself."""
        zb = self.bottom(s)
        zt = max(self.top(s), zb + 60)
        return min(max(self.belt_v(s) * self.H, zb + 40), zt)

    def measured_wing(self, kit, body):
        """Whatever the drawing's roof line carries above the deck at
        the tail — a ducktail, a whale tail, a rear wing — as the thin
        shelf it is."""
        run = [s for s in self.stations(self.p["cb"], 1.0, 26)
               if sample(self.measured["roof"], s) * self.H
               > self.deck_min + WING_GAP]
        if len(run) < 4:
            return
        rings = []
        for s in run:
            top = sample(self.measured["roof"], s) * self.H
            a = self.half_width(s) * 0.99
            y = self.y(s)
            lo = max(self.deck_min - 10, top - 0.10 * self.H)
            rings.append([(a, y, lo), (a, y, top), (-a, y, top),
                          (-a, y, lo)])
        closed_grid(body, rings)

    def measured_glasshouse(self, kit, body):
        """Everything above the beltline, from the same measured
        sections as the body: side glass and screens in near-black, a
        body-coloured roof panel over them. The greenhouse is not a
        separate shape stuck on the car — it is the top of the car."""
        runs, current = [], []
        for s in self.stations(0.02, 0.98, 90):
            zb, zt, _, _ = self._section(s)
            if zt - self.belt_z(s) > 0.07 * self.H:
                current.append(s)
            elif current:
                runs.append(current)
                current = []
        if current:
            runs.append(current)
        glass = kit.mesh(GLASS, "Plastic")
        for run in runs:
            if len(run) < 4:
                continue
            roof_lo = []
            for s in run:
                _, zt, _, _ = self._section(s)
                roof_lo.append(zt - ROOF_PANEL)
            closed_grid(glass, [self.measured_ring(s, self.belt_z(s), lo)
                                for s, lo in zip(run, roof_lo)])
            closed_grid(body, [self.measured_ring(s, lo - 4, None)
                               for s, lo in zip(run, roof_lo)])

    def body_ring(self, s):
        """The section: a floor, a near-vertical flank up to the
        beltline crease and the shoulder over it — plus the wheel arch
        cut into the outer band. A measured car uses its drawing's own
        section instead (`measured_ring`)."""
        if self.measured and self.measured.get("nose"):
            return self.measured_ring(s, None, self.belt_z(s) + 8)
        y, a = self.y(s), self.half_width(s)
        zb = self.bottom(s)
        arch = self.arch(s)
        inner = self.W / 2 - 55 - self.tw_max
        cols = self.columns()
        ring = []
        for u in reversed(cols):
            au = abs(u)
            # the flank tucks in a little under the crease and again at
            # the sill, so the car is widest at its beltline
            x = a * u * (1.0 - 0.02 * _smooth((au - 0.8) / 0.2))
            ring.append((x, y, self.body_top_at(s, u)))
        for u in cols:
            au = abs(u)
            x = a * u * (1.0 - 0.10 * _smooth((au - 0.75) / 0.25))
            top = self.body_top_at(s, u)
            z = zb + 25 * _smooth((au - 0.8) / 0.2)
            if arch is not None and abs(a * u) > inner:
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

    def cabin_height(self, s):
        """How far the greenhouse stands over the body at its centre."""
        return self.roof(s) - self.body_top_at(s, 0.0)

    def cabin_ring(self, s, f0=0.0, f1=1.0, out=0.0):
        """The greenhouse's section between the fractions *f0* and *f1*
        of its height. The glass is the same shell pushed *out* mm
        proud, so it is strictly OUTSIDE the body-coloured cabin — two
        surfaces that never share a plane and so never fight for it."""
        p = self.p
        y, a = self.y(s), self.half_width(s) * p["cabin"]
        zr = self.roof(s)
        top, bottom = [], []
        for u in self.columns():
            # the greenhouse stands on the SHOULDER, never on a fender
            # bulge: over a wheel the body top rises, and a cabin that
            # followed it would swallow its own glass
            zbase = min(self.body_top_at(s, u * p["cabin"]),
                        self.top(s) + 40) - 10
            au = abs(u)
            roll = 0.12 * (self.H - self.top(p["ws"])) * _smooth(
                (au - 0.6) / 0.4) ** 2
            zt = max(zbase + 8, zr + 0.02 * a * (1 - u * u) - roll)

            def at(f):
                x = a * u * (1 + (p["tumble"] - 1) * f)
                if out and u:
                    # proud only where the shell has climbed clear of
                    # the body: lower down it is buried in the wing and
                    # an offset would burst through the bonnet
                    x += math.copysign(out * _smooth((f - 0.30) / 0.18),
                                       u)
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
        body = kit.mesh(paint, "Plastic")
        closed_grid(body, [self.body_ring(s) for s in
                           self.stations(0.0, 1.0, STATIONS)])
        if not self.measured:
            # a measured body pulls in to the tub by itself at every
            # wheel arch, and a second tub inside it only fights the
            # same surface
            f_edge = (self.axles[0] - self.wheels[0][2] / 2
                      + self.L / 2) / self.L
            r_edge = (self.axles[1] + self.wheels[1][2] / 2
                      + self.L / 2) / self.L
            closed_grid(kit.mesh(TRIM, "Matte"),
                        [self.tub_ring(s) for s in
                         self.stations(max(0.02, f_edge),
                                       min(0.98, r_edge), 40)])
        if self.measured and self.measured.get("nose"):
            self.measured_glasshouse(kit, body)
            self.measured_wing(kit, body)
        elif p["open"]:
            self._open_cabin(kit, paint)
        else:
            self._greenhouse(kit, body)
        car_details.front(kit, self, paint)
        car_details.rear(kit, self, paint)
        if not self.measured:
            self._wing(kit, paint)      # a drawn roof line already has it
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

    def _greenhouse(self, kit, body):
        """Windscreen, side windows, roof and backlight. Each is its own
        closed loft, overlapping its neighbour a little so no two share
        a plane: the windscreen and the backlight are glass over their
        whole height, the roof is body-coloured over the side glass."""
        p = self.p
        glass = kit.mesh(GLASS, "Plastic")
        rf, rr = p["rf"], p["rr"]
        screen = self.stations(p["ws"], rf + 0.004, 26)
        closed_grid(glass, [self.cabin_ring(s) for s in screen])
        roof = self.stations(rf - 0.03, rr + 0.05, 30)
        closed_grid(body, [self.cabin_ring(s, 0.62, 1.0) for s in roof])
        sides = self.stations(rf - 0.004, rr + 0.004, 26)
        closed_grid(glass, [self.cabin_ring(s, 0.0, 0.67) for s in sides])
        back = self.stations(rr - 0.004, p["cb"], 26)
        closed_grid(glass, [self.cabin_ring(s) for s in back])

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
                       (-w, y1, z + rise), (w, y1, z + rise)], paint, "Plastic")
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
                      colour, "Plastic")
        elif kind == "lip":
            kit.solid([(-0.8 * a, y1 - 90, z - 4), (0.8 * a, y1 - 90, z - 4),
                       (-0.8 * a, y1, z - 4), (0.8 * a, y1, z - 4),
                       (-0.8 * a, y1, z + 45), (0.8 * a, y1, z + 45)],
                      paint, "Plastic")

    def _mirrors(self, kit, paint):
        p = self.p
        s = p["ws"] + 0.025
        a = self.half_width(s) * p["cabin"]
        y, z = self.y(s), self.body_top_at(s, p["cabin"])
        for side in (-1, 1):
            x = side * (a + 110)
            kit.bar((side * (a - 10), y + 20, z + 40), (x, y, z + 80), 12,
                    TRIM)
            kit.obox(x, y, z + 45, 170, 70, 95, 0, paint, "Plastic")

    def _exhaust(self, kit):
        y1 = self.L / 2
        z = self.bottom(1.0) + 55
        for side in (-1, 1):
            x = side * 0.22 * self.W / 2
            kit.path([(x, y1 - 220, z), (x, y1 - 12, z)], 42, CHROME,
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
    """The car *key* with the builder's *options*, as one node. A car
    with a coloured four-view drawing behind it (`car_sheets`) is built
    from that drawing, surface details and all."""
    from . import car_sheet_build, car_sheets
    if key in car_sheets.SHEETS:
        return car_sheet_build.build(key, options)
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
#: cars whose body is traced from a blueprint get their own menu: they
#: are a different kind of thing from one shaped to published figures
MEASURED_CATEGORY = "Cars (from blueprints)"


def category_of(key: str) -> str:
    from . import car_sheets
    if key in car_sheets.SHEETS or (USE_MEASURED
                                    and car_profiles.PROFILES.get(key)):
        return MEASURED_CATEGORY
    return CATEGORY

PARTS = {
    f"car_{key}": dict(
        label=car_models.label(key), category=category_of(key),
        sizes={name: dict(scale=v) for name, v in SCALES.items()},
        fields=[("scale", "Scale")],
        colors=[car["paint"]] + [n for n in car_models.PAINTS
                                 if n != car["paint"]],
        build=_part_builder(key))
    for key, car in car_models.CARS.items()
}
