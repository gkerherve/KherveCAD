"""A car body as ONE smooth closed loft, plus everything laid on it
(Qt-free).

`Body` takes a `car_models` entry and its design (`car_designs`) and
builds cross-sections every ~25 mm along the car. Each section is the
same chain of points, segment by segment, so a feature line always runs
along the same column:

    bottom -> corner / wheel well -> flank -> shoulder -> belt
           -> side glass (or the wing top) -> roof (or the bonnet)

so the belt, the shoulder and the roof rail are crisp lines along the
whole car instead of wandering. Over a wheel the corner segment becomes
the WELL: it climbs the tub wall to the arch (a circle round the axle)
and turns out to the lip, so the wheel stands in a real opening with no
boolean. The shoulder rises over each arch by itself, which is where a
sports car's wings come from.

Everything else is laid ON the body, never floated near it:
- `patch` takes a region in the loft's own (station, column) space —
  the glass, the window frames, the wheel wells, shut lines;
- `decal` projects an outline (rounded rectangle, ellipse, polygon)
  along an axis onto the surface by ray casting — lamps, grilles,
  intakes, plates, vents.
Both become thin closed slabs a few millimetres proud of the paint, so
every colour is its own closed polyhedron and the preview is exact.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

import numpy as np

from .car_wheels import closed_grid

#: points of each segment of a half section (bottom centre to top
#: centre). The names are the feature columns `col` hands out.
SEGMENTS = (("bottom", 5), ("well", 7), ("flank", 7), ("shoulder", 5),
            ("glass", 6), ("roof", 8))
#: station spacing along the car (mm)
STEP = 24.0


def smoothstep(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def pchip(knots):
    """A monotone cubic through (x, y) *knots* (sorted by x): smooth
    and never overshooting, so a profile stays where it was drawn."""
    xs = [float(k[0]) for k in knots]
    ys = [float(k[1]) for k in knots]
    n = len(xs)
    if n == 1:
        return lambda x: ys[0]
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]
    d = [(ys[i + 1] - ys[i]) / h[i] if h[i] else 0.0 for i in range(n - 1)]
    m = [0.0] * n
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
        else:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])

    def f(x):
        if x <= xs[0]:
            return ys[0] + m[0] * (x - xs[0]) * 0.0
        if x >= xs[-1]:
            return ys[-1]
        lo, hi = 0, n - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if xs[mid] <= x:
                lo = mid
            else:
                hi = mid
        i = lo
        t = (x - xs[i]) / h[i] if h[i] else 0.0
        t2, t3 = t * t, t * t * t
        return ((2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h[i] * m[i]
                + (-2 * t3 + 3 * t2) * ys[i + 1] + (t3 - t2) * h[i] * m[i + 1])
    return f


def _bezier(p0, c, p1, n, skip_first=True):
    out = []
    for k in range(n + 1):
        if skip_first and k == 0:
            continue
        t = k / n
        a, b, e = (1 - t) ** 2, 2 * t * (1 - t), t * t
        out.append((a * p0[0] + b * c[0] + e * p1[0],
                    a * p0[1] + b * c[1] + e * p1[1]))
    return out


def _line(p0, p1, n, bow=0.0, skip_first=True):
    """*n* points from p0 to p1, bowed outward (to the right of the
    direction of travel) by *bow* mm at the middle."""
    dx, dz = p1[0] - p0[0], p1[1] - p0[1]
    ln = math.hypot(dx, dz) or 1.0
    nx, nz = dz / ln, -dx / ln
    out = []
    for k in range(n + 1):
        if skip_first and k == 0:
            continue
        t = k / n
        b = bow * 4 * t * (1 - t)
        out.append((p0[0] + dx * t + nx * b, p0[1] + dz * t + nz * b))
    return out


class Body:
    """The body of one car. *spec* is its `car_models` entry, *d* its
    design (`car_designs.design`), *wheels* [(width, ratio, D)] front
    and rear."""

    def __init__(self, spec, d, wheels):
        self.spec, self.d = spec, d
        self.L, self.W, self.H = float(spec["L"]), float(spec["W"]), \
            float(spec["H"])
        L, W, H = self.L, self.W, self.H
        self.wheels = wheels
        fo = d["fo"] * (L - spec["wb"])
        self.axles = [-L / 2 + fo, -L / 2 + fo + spec["wb"]]
        self.s_axle = [fo / L, (fo + spec["wb"]) / L]
        track = spec.get("track")
        self.wheel_x = []
        for i, (tw, _r, D) in enumerate(wheels):
            if track:
                self.wheel_x.append(track[i] / 2)
            else:
                self.wheel_x.append(W / 2 * d["track_w"][i] - tw / 2)
        self._profiles()
        self._loft()

    # ---------------------------------------------------------- profiles
    def _profiles(self):
        d, L, W, H = self.d, self.L, self.W, self.H
        cs, cz = d["cowl"]
        rf, rr = d["roof"]
        ds, dz = d["deck"]
        roof_h = d.get("roof_h", 1.0) * H
        segs = [(0.0, d["nose_z"] * H, cs, cz * H, d["hood_bulge"] * H)]
        segs.append((cs, cz * H, rf, roof_h - d["roof_rise"] * H,
                     d["screen_bow"] * H))
        segs.append((rf, roof_h - d["roof_rise"] * H, rr,
                     roof_h - d["roof_rise"] * H, d["roof_rise"] * H))
        segs.append((rr, roof_h - d["roof_rise"] * H, ds, dz * H,
                     d["back_bow"] * H))
        segs.append((ds, dz * H, 1.0, d["tail_z"] * H, d["deck_bulge"] * H))
        self._top_segs = segs
        # the bonnet / boot line under the cabin, for the cabin height
        knots = [(0.0, d["nose_z"] * H), (cs, cz * H), (ds, dz * H),
                 (1.0, d["tail_z"] * H)] + [(s, z * H) for s, z in
                                            d["line"]]
        self._body_line = pchip(sorted(knots))
        self.belt = pchip([(s, z * H) for s, z in d["belt"]])
        sa = self.s_axle
        R = [w[2] / 2 for w in self.wheels]
        floor = [(0.0, d["chin_z"] * H)]
        floor.append((max(0.02, sa[0] - 1.1 * R[0] / L), d["sill"]))
        floor.append((min(0.98, sa[1] + 1.1 * R[1] / L), d["sill"]))
        floor.append((1.0, d["tail_chin_z"] * H))
        self.floor = pchip(sorted(floor))
        plan = [(s, w) for s, w in d["plan"]]
        self._plan = pchip(plan)

    def top(self, s):
        """Centre-line top of the car at *s* (bonnet, glass, roof, deck).
        An open car has no cabin: its top is the body line, the
        cockpit a dark tub laid in it (`car_dress.cockpit`)."""
        if self.d["open"]:
            return self._body_line(s)
        for s0, z0, s1, z1, bow in self._top_segs:
            if s <= s1 or s1 >= 1.0:
                u = 0.0 if s1 == s0 else min(1.0, max(0.0, (s - s0)
                                                      / (s1 - s0)))
                return z0 + (z1 - z0) * u + bow * 4 * u * (1 - u)
        return self._top_segs[-1][3]

    def y(self, s):
        return -self.L / 2 + s * self.L

    def arch(self, s):
        """(arch top z at this station or None, axle index)."""
        y = self.y(s)
        for i, ya in enumerate(self.axles):
            D = self.wheels[i][2]
            R = D / 2 + self.d["arch_gap"]
            dy = y - ya
            if abs(dy) < R:
                return D / 2 + math.sqrt(R * R - dy * dy), i
        return None, None

    def half_width(self, s):
        """Plan half width at the shoulder, wings flared over the
        wheels to cover them."""
        hw = self.W / 2 * self._plan(s)
        for i, sa in enumerate(self.s_axle):
            tw, _r, D = self.wheels[i]
            need = self.wheel_x[i] + tw / 2 + self.d["lip"]
            dy = abs(s - sa) * self.L
            reach = D / 2 + 260
            if dy < reach:
                k = 0.5 + 0.5 * math.cos(math.pi * dy / reach)
                hw = max(hw, hw + (need - hw) * k)
        return hw

    def shoulder_in(self, s):
        v = self.d["shoulder_in"]
        if isinstance(v, (int, float)):
            return float(v)
        return pchip(v)(s)

    def scallop(self, s):
        """How deep the side cove is here (mm): it deepens towards the
        intake at its back, then the flank returns over a short run."""
        sc = self.d.get("scallop")
        if not sc:
            return 0.0
        s0, s1, depth = sc
        if s <= s0 or s >= s1 + 0.03:
            return 0.0
        if s <= s1:
            return depth * smoothstep((s - s0) / (s1 - s0)) ** 0.8
        return depth * (1.0 - smoothstep((s - s1) / 0.03))

    def belt_z(self, s):
        """The belt line, lifted over each wheel so the wing covers
        it: where a low bonnet meets a big wheel the wings stand up
        out of it, as on a Countach or an F40."""
        z = self.belt(s)
        for i, sa in enumerate(self.s_axle):
            D = self.wheels[i][2]
            need = (D + self.d["arch_gap"] + self.d["arch_cover"]
                    + self.d["belt_over"])
            dy = abs(s - sa) * self.L
            reach = D / 2 + self.d["wing_reach"]
            if dy < reach and need > z:
                k = 0.5 + 0.5 * math.cos(math.pi * dy / reach)
                z = z + (need - z) * k
        return z

    def shoulder_z(self, s):
        z = self.belt_z(s) - self.d["shoulder_drop"]
        for i, sa in enumerate(self.s_axle):
            D = self.wheels[i][2]
            top = D + self.d["arch_gap"] + self.d["arch_cover"]
            dy = abs(s - sa) * self.L
            reach = D / 2 + 380
            if dy < reach and top > z:
                k = 0.5 + 0.5 * math.cos(math.pi * dy / reach)
                z = z + (top - z) * k
        return z

    def fender(self, s):
        """How far the wing top stands over the belt there (mm)."""
        bump = 0.0
        for i, sa in enumerate(self.s_axle):
            D = self.wheels[i][2]
            dy = abs(s - sa) * self.L
            reach = D / 2 + 420
            if dy < reach:
                k = 0.5 + 0.5 * math.cos(math.pi * dy / reach)
                bump = max(bump, self.d["fenders"][i] * k)
        return bump

    # ---------------------------------------------------------- sections
    def half_section(self, s):
        """[(x, z)] from the bottom centre to the top centre."""
        d = self.d
        zb = self.floor(s)
        hw = self.half_width(s)
        zbelt = self.belt_z(s)
        zsh = min(self.shoulder_z(s), zbelt - 12)
        # a low nose leaves no room for the flank: keep a share of it
        zsh = max(zsh, zb + 0.4 * (zbelt - zb))
        fend = self.fender(s)
        # bottom
        tuck = d["tuck"]
        rc = min(d["corner_r"], 0.45 * (zsh - zb))
        za, ax = self.arch(s)
        x_out = hw - tuck
        x_tub = x_out - rc
        alpha = 0.0
        if za is not None:
            tw = self.wheels[ax][0]
            x_tub = min(x_out - rc, self.wheel_x[ax] - tw / 2 - 45)
            alpha = smoothstep((za - zb - rc * 0.4) / 60.0)
            za = min(za, zsh - 25)
        x_in = (x_out - rc) + (x_tub - (x_out - rc)) * alpha

        cove = self.scallop(s)

        def flank_x(z):
            u = min(1.0, max(0.0, (zsh - z) / max(1.0, zsh - zb)))
            x = hw - tuck * u ** 1.7
            if cove:
                # a cove in the flank: deepest at mid flank, none at the
                # sill or the shoulder
                t = (z - zb) / max(1.0, zsh - zb)
                x -= cove * math.sin(math.pi * min(1.0, max(0.0, t))) ** 1.5
            return x

        z_low = zb + rc if za is None else max(zb + rc, za)
        z_low = min(z_low, zsh - 20)
        q1 = (flank_x(z_low), z_low)
        pts = [(0.0, zb)]
        pts += _line((0.0, zb), (x_in, zb + 4), SEGMENTS[0][1] - 1)
        corner_out = (q1[0], zb)
        corner_in = (x_in, z_low)
        c = (corner_out[0] + (corner_in[0] - corner_out[0]) * alpha,
             corner_out[1] + (corner_in[1] - corner_out[1]) * alpha)
        pts += _bezier((x_in, zb + 4), c, q1, SEGMENTS[1][1])
        n = SEGMENTS[2][1]
        for k in range(1, n + 1):
            z = z_low + (zsh - z_low) * (k / n) ** 0.9
            pts.append((flank_x(z), z))
        # shoulder: a quarter superellipse into the belt
        x_belt = hw - self.shoulder_in(s)
        n = SEGMENTS[3][1]
        e = 2.0 / d["shoulder_sq"]
        for k in range(1, n + 1):
            th = math.pi / 2 * k / n
            ct, st = math.cos(th), math.sin(th)
            pts.append((x_belt + (hw - x_belt) * ct ** e,
                        zsh + (zbelt - zsh) * st ** e))
        # the upper part: a bonnet / boot with its wings, or the cabin
        ztop = self.top(s)
        body_line = self._body_line(s)
        h_cab = ztop - max(body_line, zbelt)
        c = smoothstep(h_cab / 70.0) if d["cabin_from"] <= s <= \
            d["cabin_to"] and not d["open"] else 0.0
        ne, ng = SEGMENTS[4][1], SEGMENTS[5][1]
        # bonnet: belt -> wing crest -> centre
        crest = (x_belt - d["crest_in"], zbelt + fend + d["crest_up"])
        hood_e = _line((x_belt, zbelt), crest, ne, bow=4.0)
        hood_g = _bezier(crest, (crest[0] * 0.45, ztop), (0.0, ztop), ng)
        if c > 0:
            wrap = d["screen_wrap"] if s < 0.5 * (d["roof"][0]
                                                  + d["roof"][1]) \
                else -d["back_wrap"]
            z_side = self.top(s - wrap) - d["roof_crown"]
            z_side = max(zbelt + 6, min(z_side, ztop - 4))
            tan = math.tan(math.radians(d["tumble"]))
            xr = x_belt - d["ledge"] - (z_side - zbelt) * tan
            xr *= self._canopy(s)
            xr = max(xr, 0.2 * hw)
            base = (x_belt - d["ledge"], zbelt + 4)
            cab_e = [(x_belt - d["ledge"] * 0.6, zbelt + 2)] + \
                _line(base, (xr, z_side), ne - 1, bow=d["glass_bow"])
            cab_g = _bezier((xr, z_side), (xr * 0.55, ztop), (0.0, ztop), ng)
            hood_e = [(a[0] + (b[0] - a[0]) * c, a[1] + (b[1] - a[1]) * c)
                      for a, b in zip(hood_e, cab_e)]
            hood_g = [(a[0] + (b[0] - a[0]) * c, a[1] + (b[1] - a[1]) * c)
                      for a, b in zip(hood_g, cab_g)]
        pts += hood_e + hood_g
        return pts

    def _canopy(self, s):
        """A mid-engined car's cabin narrows towards its ends in plan,
        like a teardrop."""
        k = self.d["canopy"]
        if not k:
            return 1.0
        a, b = self.d["roof"]
        mid, half = (a + b) / 2, max(0.05, (b - a) / 2 + 0.12)
        u = min(1.0, abs(s - mid) / half)
        return 1.0 - k * u * u

    def ring(self, s):
        """The full closed section at *s*, with the ends rounded off."""
        half = self.half_section(s)
        d = self.d
        y = self.y(s)
        # round the ends in plan and in profile
        zb, zt = half[0][1], half[-1][1]
        out_x, out_z = 1.0, 1.0
        zc = 0.5 * (zb + zt)
        for end, length, kx, kz in ((s * self.L, d["nose_round"],
                                     d["nose_kx"], d["nose_kz"]),
                                    ((1 - s) * self.L, d["tail_round"],
                                     d["tail_kx"], d["tail_kz"])):
            if end < length:
                u = end / length
                f = math.sqrt(max(0.0, 1 - (1 - u) ** 2))
                out_x = min(out_x, kx + (1 - kx) * f)
                out_z = min(out_z, kz + (1 - kz) * f)
        side = [(x * out_x, zc + (z - zc) * out_z) for x, z in half]
        right = [(x, y, z) for x, z in side]
        left = [(-x, y, z) for x, z in reversed(side[1:-1])]
        return right + left

    def _stations(self):
        n = max(60, int(self.L / STEP))
        out = []
        for k in range(n + 1):
            u = k / n
            # denser at the ends, where the nose and tail turn
            out.append(u - 0.85 * math.sin(2 * math.pi * u) / (2 * math.pi))
        return out

    def _loft(self):
        self.stations = self._stations()
        self.rings = np.array([self.ring(s) for s in self.stations])
        self.m = len(self.rings[0])
        # the closed mesh, as triangles for ray casts
        rings = self.rings
        n, m = rings.shape[0], rings.shape[1]
        a = rings[:-1, :, :]
        b = np.roll(rings[:-1], -1, axis=1)
        c = np.roll(rings[1:], -1, axis=1)
        dd = rings[1:]
        t1 = np.stack([a, b, c], axis=2).reshape(-1, 3, 3)
        t2 = np.stack([a, c, dd], axis=2).reshape(-1, 3, 3)
        caps = []
        for i in (0, n - 1):
            ctr = rings[i].mean(axis=0)
            for j in range(m):
                caps.append([ctr, rings[i][j], rings[i][(j + 1) % m]])
        self.tris = np.concatenate([t1, t2, np.array(caps)])
        self._cols()

    def _cols(self):
        """Column index where each segment starts on the right side."""
        self.col = {}
        k = 0
        for name, n in SEGMENTS:
            self.col[name] = k
            k += n
        self.col["top"] = k - 1      # the centre of the roof
        self.half = k - 1

    def add_to(self, mesh):
        closed_grid(mesh, [list(map(tuple, r)) for r in self.rings])

    # ----------------------------------------------- surface parameters
    def station_index(self, s):
        st = self.stations
        if s <= st[0]:
            return 0.0
        if s >= st[-1]:
            return float(len(st) - 1)
        lo, hi = 0, len(st) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if st[mid] <= s:
                lo = mid
            else:
                hi = mid
        return lo + (s - st[lo]) / (st[hi] - st[lo])

    def point(self, i, j):
        """The surface at fractional station *i*, column *j* (columns
        wrap round the ring)."""
        n, m = self.rings.shape[0], self.m
        i = min(max(i, 0.0), n - 1.0)
        i0 = min(int(i), n - 2)
        fi = i - i0
        j = j % m
        j0 = int(j) % m
        fj = j - int(j)
        j1 = (j0 + 1) % m
        r0, r1 = self.rings[i0], self.rings[i0 + 1]
        p0 = r0[j0] * (1 - fj) + r0[j1] * fj
        p1 = r1[j0] * (1 - fj) + r1[j1] * fj
        return p0 * (1 - fi) + p1 * fi

    def normal(self, i, j):
        e = 0.25
        a = self.point(i + e, j) - self.point(i - e, j)
        b = self.point(i, j + e) - self.point(i, j - e)
        nrm = np.cross(b, a)
        ln = np.linalg.norm(nrm)
        if ln < 1e-9:
            return np.array([0.0, 0.0, 1.0])
        nrm = nrm / ln
        # outward: away from the section's own middle
        r = self.rings[int(min(max(i, 0), len(self.rings) - 1))]
        ctr = r.mean(axis=0)
        if np.dot(nrm, self.point(i, j) - ctr) < 0:
            nrm = -nrm
        return nrm

    # ------------------------------------------------------------ slabs
    def patch(self, mesh, s0, s1, j0, j1, out=3.0, inside=3.0, ns=None,
              nj=None):
        """A slab over the surface between stations s0..s1 (fractions of
        L) and columns j0..j1 (each a number or a function of s; a
        column past `half` runs over the top to the other side)."""
        i0, i1 = self.station_index(s0), self.station_index(s1)
        if i1 - i0 < 0.05:
            return
        ns = ns or max(2, int(math.ceil(i1 - i0)) + 1)
        f0 = j0 if callable(j0) else (lambda s, v=j0: v)
        f1 = j1 if callable(j1) else (lambda s, v=j1: v)
        rows = []
        for k in range(ns + 1):
            s = s0 + (s1 - s0) * k / ns
            i = self.station_index(s)
            a, b = f0(s), f1(s)
            cnt = nj or max(2, int(math.ceil(abs(b - a))) + 1)
            rows.append((i, [a + (b - a) * q / cnt for q in range(cnt + 1)]))
        cnt = min(len(r[1]) for r in rows)
        cnt = max(len(r[1]) for r in rows)
        rings = []
        for i, js in rows:
            a, b = js[0], js[-1]
            js = [a + (b - a) * q / (cnt - 1) for q in range(cnt)]
            top, bot = [], []
            for j in js:
                p = self.point(i, j)
                nv = self.normal(i, j)
                top.append(tuple(p + nv * out))
                bot.append(tuple(p - nv * inside))
            rings.append(top + bot[::-1])
        closed_grid(mesh, rings)

    def mirror_patch(self, mesh, s0, s1, j0, j1, **kw):
        """The same patch on both sides."""
        self.patch(mesh, s0, s1, j0, j1, **kw)
        m = self.m
        g0 = (lambda s: m - j1(s)) if callable(j1) else m - j1
        g1 = (lambda s: m - j0(s)) if callable(j0) else m - j0
        self.patch(mesh, s0, s1, g0, g1, **kw)

    # ------------------------------------------------------- ray casts
    def cast(self, origins, direction):
        """Distance along *direction* from each origin to the nearest
        surface hit (NaN for a miss)."""
        o = np.asarray(origins, float)
        dvec = np.asarray(direction, float)
        dvec = dvec / np.linalg.norm(dvec)
        tri = self.tris
        # keep the triangles whose box overlaps the rays' box across
        # the direction
        axes = [k for k in range(3) if abs(dvec[k]) < 0.5]
        lo, hi = o.min(axis=0), o.max(axis=0)
        mask = np.ones(len(tri), bool)
        for k in axes:
            mask &= (tri[:, :, k].max(axis=1) >= lo[k] - 1) & \
                (tri[:, :, k].min(axis=1) <= hi[k] + 1)
        tri = tri[mask]
        out = np.full(len(o), np.nan)
        if not len(tri):
            return out
        v0, e1, e2 = tri[:, 0], tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
        pvec = np.cross(dvec, e2)
        det = np.einsum("ij,ij->i", e1, pvec)
        ok = np.abs(det) > 1e-12
        v0, e1, e2, pvec, det = v0[ok], e1[ok], e2[ok], pvec[ok], det[ok]
        inv = 1.0 / det
        for start in range(0, len(o), 64):
            oo = o[start:start + 64]
            tvec = oo[:, None, :] - v0[None, :, :]
            u = np.einsum("rij,ij->ri", tvec, pvec) * inv
            q = np.cross(tvec, e1[None, :, :])
            v = np.einsum("rij,j->ri", q, dvec) * inv
            t = np.einsum("rij,ij->ri", q, e2) * inv
            hit = (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & \
                (t > 0)
            t = np.where(hit, t, np.inf)
            best = t.min(axis=1)
            best[~np.isfinite(best)] = np.nan
            out[start:start + 64] = best
        return out

    def decal(self, mesh, outline, view, out=3.0, inside=4.0, rings=4,
              lift=0.0):
        """A slab whose outline (u, v points, star-shaped about their
        mean) is projected onto the body along *view*: "front" (u = x,
        v = z, looking along +y), "rear", "right" / "left" (u = y, v =
        z) or "top" (u = x, v = y). *lift* raises the whole slab off
        the surface (a lamp lens over its housing). Returns False if
        any of it misses the body."""
        far = 4 * (self.L + self.W + self.H)
        if view == "front":
            to3 = lambda u, v: (u, -far, v)
            dvec = (0.0, 1.0, 0.0)
        elif view == "rear":
            to3 = lambda u, v: (u, far, v)
            dvec = (0.0, -1.0, 0.0)
        elif view == "right":
            to3 = lambda u, v: (far, u, v)
            dvec = (-1.0, 0.0, 0.0)
        elif view == "left":
            to3 = lambda u, v: (-far, u, v)
            dvec = (1.0, 0.0, 0.0)
        else:
            to3 = lambda u, v: (u, v, far)
            dvec = (0.0, 0.0, -1.0)
        cu = sum(p[0] for p in outline) / len(outline)
        cv = sum(p[1] for p in outline) / len(outline)
        grid = []
        for k in range(1, rings + 1):
            rho = k / rings
            grid.append([(cu + (u - cu) * rho, cv + (v - cv) * rho)
                         for u, v in outline])
        flat = [p for row in grid for p in row] + [(cu, cv)]
        origins = [to3(u, v) for u, v in flat]
        dist = self.cast(origins, dvec)
        if np.isnan(dist).any():
            return False
        dv = np.array(dvec)
        hits = np.array(origins) + dist[:, None] * dv
        top = hits - dv * (out + lift)
        bot = hits + dv * inside
        n = len(outline)
        rings_top = [[tuple(top[r * n + j]) for j in range(n)]
                     for r in range(rings)]
        rings_bot = [[tuple(bot[r * n + j]) for j in range(n)]
                     for r in range(rings)]
        closed_grid(mesh, rings_top + rings_bot[::-1])
        return True


# --------------------------------------------------------------- shapes

def rounded_rect(cu, cv, w, h, r, n=6, slant=0.0):
    """Outline of a rounded rectangle centred on (cu, cv); *slant*
    shears the top towards +u (mm), for raked lamps."""
    r = min(r, w / 2 - 0.1, h / 2 - 0.1)
    pts = []
    for cx, cy, a0 in ((w / 2 - r, -h / 2 + r, -90), (w / 2 - r, h / 2 - r, 0),
                       (-w / 2 + r, h / 2 - r, 90),
                       (-w / 2 + r, -h / 2 + r, 180)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            pts.append((cu + x + slant * (y / h), cv + y))
    return pts


def ellipse(cu, cv, a, b, n=28):
    return [(cu + a * math.cos(2 * math.pi * k / n),
             cv + b * math.sin(2 * math.pi * k / n)) for k in range(n)]


def polygon(points, n_per_edge=3):
    """A closed polygon resampled so a projected slab follows the
    surface between its corners."""
    out = []
    m = len(points)
    for k in range(m):
        a, b = points[k], points[(k + 1) % m]
        for q in range(n_per_edge):
            t = q / n_per_edge
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    # counter-clockwise, so every slab is wound alike
    area = sum(out[i][0] * out[(i + 1) % len(out)][1]
               - out[(i + 1) % len(out)][0] * out[i][1]
               for i in range(len(out)))
    return out if area > 0 else out[::-1]
