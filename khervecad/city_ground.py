"""A city built ON a landscape (Qt-free): the City Builder's terrain.

With a ``terrain`` in the city spec ({kind, height, seed, cells}) the
flat grass slab gives way to `terrain` ground covering the city and a
margin round it — hills, a mountain, a valley... San Francisco is a
street grid on hills. The height field is EDITED before it becomes
ground, the way a town is really built:

- every road is levelled across: the road's own profile is the ground
  along its centre line, smoothed along its length (a street climbs and
  dips with the hill, but not with every bump), and the ground within
  the road's width takes that profile, blending back to the natural
  slope over a few metres of embankment;
- every building stands on a level PAD at the mean ground height under
  its footprint, the ground round it graded back to the hillside, and a
  stone foundation below it so a downhill corner never floats.

`Ground.z(x, y)` then gives the finished ground height anywhere, which
places trees, street lights and library pieces, and roads are DRAPED:
each road is closed ribbons of sloping strips (tarmac between two
raised pavements) sampled every few metres along it, dashes riding on
the tarmac.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from . import terrain
from .model import CadNode

KINDS = terrain.KINDS
#: road embankment: the ground returns to the hill over this, mm
ROAD_BLEND = 7000.0
PAD_MARGIN, PAD_BLEND = 2000.0, 6000.0
SAMPLE = 4000.0                      # road sample spacing, mm
FOUNDATION = 4000.0


def _f(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _smooth(e0, e1, x):
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def resolve(spec):
    """A terrain spec with its defaults, or None for flat ground."""
    if not spec or spec.get("kind") in (None, "", "flat", "Flat"):
        return None
    kind = spec.get("kind")
    if kind == "heights":
        rows = spec.get("rows") or []
        n = len(rows) - 1
        if n < 2 or any(len(r) != n + 1 for r in rows):
            raise ValueError("terrain heights: rows must be a square grid "
                             "of (n+1) x (n+1) heights in mm, n >= 2")
        return dict(kind="heights", rows=[[_f(v) for v in r] for r in rows],
                    x0=_f(spec.get("x0")), y0=_f(spec.get("y0")),
                    length=_f(spec.get("length")),
                    width=_f(spec.get("width")),
                    height=max(max(max(r) for r in rows), 1000.0),
                    seed=1, cells=n, source=spec.get("source", ""))
    if kind not in KINDS:
        raise ValueError(f'Unknown terrain "{kind}"; use flat or one of '
                         + ", ".join(KINDS))
    return dict(kind=kind, height=max(0.0, _f(spec.get("height"), 25000)),
                seed=int(_f(spec.get("seed"), 1)),
                cells=int(_f(spec.get("cells"), 0)),
                roughness=min(max(_f(spec.get("roughness"), 0.5), 0.0), 1.0))


class Ground:
    """The terrain under a city: the edited height field, `z(x, y)`, the
    ground node and draped roads."""

    def __init__(self, tspec, extent, roads=(), buildings=(), margin=30000.0,
                 road_style=None):
        self.spec = tspec
        x0, y0, x1, y1 = extent
        if tspec["kind"] == "heights":
            self._init_measured(tspec, roads, buildings, road_style)
            return
        self.x0, self.y0 = x0 - margin, y0 - margin
        self.length = (x1 - x0) + 2 * margin
        self.width = (y1 - y0) + 2 * margin
        cells = tspec["cells"] or int(round(max(self.length, self.width)
                                            / 5000.0))
        self.n = max(24, min(cells, 128))
        self.hs, self.water = terrain.height_field(
            tspec["kind"], self.n, self.length, self.width, tspec["height"],
            tspec["seed"], tspec.get("roughness", 0.5))
        self.dx = self.length / self.n
        self.dy = self.width / self.n
        self.road_style = road_style
        self.profiles = []
        self.pads = []
        self.edited = set()           # grid vertices a road or pad moved
        if roads and road_style:
            self._level_roads(roads)
        for b in buildings:
            self.pads.append(self._level_pad(b))

    def _init_measured(self, tspec, roads, buildings, road_style):
        """A measured height field (LiDAR): the grid IS the ground, over
        its own rectangle."""
        self.x0, self.y0 = tspec["x0"], tspec["y0"]
        self.length, self.width = tspec["length"], tspec["width"]
        self.hs = [row[:] for row in tspec["rows"]]
        self.n = len(self.hs) - 1
        self.water = None
        self.dx, self.dy = self.length / self.n, self.width / self.n
        self.road_style = road_style
        self.profiles, self.pads, self.edited = [], [], set()
        if roads and road_style:
            self._level_roads(roads)
        for b in buildings:
            self.pads.append(self._level_pad(b))

    # ------------------------------------------------------ sampling
    def z(self, x, y):
        """The (edited) ground height at (x, y), bilinear."""
        u = (x - self.x0) / self.dx
        v = (y - self.y0) / self.dy
        n = self.n
        u = min(max(u, 0.0), n - 1e-6)
        v = min(max(v, 0.0), n - 1e-6)
        i, j = int(u), int(v)
        fu, fv = u - i, v - j
        h = self.hs
        return ((h[j][i] * (1 - fu) + h[j][i + 1] * fu) * (1 - fv)
                + (h[j + 1][i] * (1 - fu) + h[j + 1][i + 1] * fu) * fv)

    def _graded(self, i, j):
        """A cell a road or a pad graded is grassed over (an embankment,
        a garden), not left as scree."""
        e = self.edited
        return ((i, j) in e or (i + 1, j) in e or (i, j + 1) in e
                or (i + 1, j + 1) in e)

    def _vertex(self, i, j):
        return self.x0 + i * self.dx, self.y0 + j * self.dy

    # ------------------------------------------------------- levelling
    def _level_roads(self, roads):
        """Each road's profile (centre-line heights, smoothed along it),
        then every grid vertex near a road takes the nearest road's
        profile height, blending to the hill beyond its width."""
        for road in roads:
            width, walk, _ = self.road_style(road)
            pts = [(_f(p[0]), _f(p[1])) for p in road.get("points") or []]
            samples = _samples(pts, SAMPLE)
            if len(samples) < 2:
                continue
            raw = [self.z(x, y) for x, y, _t in samples]
            k = 3                                  # +/- 12 m window
            smooth = []
            for i in range(len(raw)):
                lo, hi = max(0, i - k), min(len(raw), i + k + 1)
                smooth.append(sum(raw[lo:hi]) / (hi - lo))
            self.profiles.append((samples, smooth, width / 2 + walk))
        if not self.profiles:
            return
        n = self.n
        new = [row[:] for row in self.hs]
        for j in range(n + 1):
            for i in range(n + 1):
                x, y = self._vertex(i, j)
                best = None
                for samples, zs, half in self.profiles:
                    hit = _nearest_on(samples, zs, x, y)
                    if hit is None:
                        continue
                    d, zr = hit
                    w = _smooth(half + 500.0, half + ROAD_BLEND, d)
                    if best is None or w < best[0]:
                        best = (w, zr)
                if best is not None and best[0] < 1.0:
                    w, zr = best
                    new[j][i] = zr * (1 - w) + self.hs[j][i] * w
                    self.edited.add((i, j))
        self.hs = new

    def _level_pad(self, b):
        """Level a pad for building *b* (resolved: x, y, w, d, rz) at the
        mean ground under its footprint; returns the pad height."""
        cx, cy = _f(b.get("x")), _f(b.get("y"))
        hw, hd = _f(b.get("w"), 8000) / 2, _f(b.get("d"), 8000) / 2
        a = math.radians(_f(b.get("rz")))
        ca, sa = math.cos(a), math.sin(a)
        probes = [(0, 0), (-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd),
                  (0, -hd), (0, hd), (-hw, 0), (hw, 0)]
        pad = sum(self.z(cx + px * ca - py * sa, cy + px * sa + py * ca)
                  for px, py in probes) / len(probes)
        reach = max(hw, hd) + PAD_MARGIN + PAD_BLEND
        i0 = max(0, int((cx - reach - self.x0) / self.dx))
        i1 = min(self.n, int((cx + reach - self.x0) / self.dx) + 1)
        j0 = max(0, int((cy - reach - self.y0) / self.dy))
        j1 = min(self.n, int((cy + reach - self.y0) / self.dy) + 1)
        for j in range(j0, j1 + 1):
            for i in range(i0, i1 + 1):
                x, y = self._vertex(i, j)
                lx = (x - cx) * ca + (y - cy) * sa        # into its frame
                ly = -(x - cx) * sa + (y - cy) * ca
                ex = max(abs(lx) - hw - PAD_MARGIN, 0.0)
                ey = max(abs(ly) - hd - PAD_MARGIN, 0.0)
                w = _smooth(0.0, PAD_BLEND, math.hypot(ex, ey))
                if w < 1.0:
                    self.hs[j][i] = pad * (1 - w) + self.hs[j][i] * w
                    self.edited.add((i, j))
        return pad

    # ------------------------------------------------------------ nodes
    def node(self, name="Ground"):
        group = terrain.from_heights(self.spec["kind"], self.hs, self.water,
                                     self.x0, self.y0, self.length,
                                     self.width, self.spec["height"],
                                     self.spec["seed"],
                                     base_depth=FOUNDATION + 1500.0,
                                     paved=self._graded)
        group.name = name
        return group

    def roads_node(self, roads, kerb, thickness, colours):
        """Draped roads: tarmac between two raised pavements, each a
        closed ribbon following the levelled ground, plus dashes."""
        asphalt_c, pavement_c, dash_c = colours
        tarmac, walks, dashes = [], [], []
        for road in roads:
            width, walk, dashed = self.road_style(road)
            pts = [(_f(p[0]), _f(p[1])) for p in road.get("points") or []]
            samples = _samples(pts, SAMPLE)
            if len(samples) < 2:
                continue
            tarmac.append(_ribbon(samples, self.z, -width / 2, width / 2,
                                  -600.0, thickness, "Tarmac"))
            if walk > 0:
                walks.append(_ribbon(samples, self.z, -width / 2 - walk,
                                     -width / 2, -600.0, kerb, "Pavement"))
                walks.append(_ribbon(samples, self.z, width / 2,
                                     width / 2 + walk, -600.0, kerb,
                                     "Pavement"))
            if dashed:
                dashes.append(_dashes(pts, self.z, thickness + 1.0))
        group = CadNode("union", "Roads", {})
        for nodes, colour, name in ((walks, pavement_c, "Pavements"),
                                    (tarmac, asphalt_c, "Tarmac"),
                                    (dashes, dash_c, "Markings")):
            nodes = [n for n in nodes if n is not None]
            if not nodes:
                continue
            c = CadNode("color", name, dict(color=colour, alpha=1.0,
                                            material="Matte"))
            inner = CadNode("union", name, {})
            for n in nodes:
                inner.add(n)
            c.add(inner)
            group.add(c)
        return group

    def shade_image(self, size=256):
        """A hillshade of the RAW-ish field as rows of (r, g, b) floats,
        for the plan's background: lit from the north-west."""
        n = self.n
        out = []
        top = max(max(row) for row in self.hs) or 1.0
        for j in range(n + 1):
            row = []
            for i in range(n + 1):
                i0, i1 = max(i - 1, 0), min(i + 1, n)
                j0, j1 = max(j - 1, 0), min(j + 1, n)
                sx = (self.hs[j][i1] - self.hs[j][i0]) / ((i1 - i0) * self.dx)
                sy = (self.hs[j1][i] - self.hs[j0][i]) / ((j1 - j0) * self.dy)
                light = 0.75 + 0.9 * (-sx * 0.7 + sy * 0.7)
                h = self.hs[j][i] / top
                row.append((min(max(light, 0.35), 1.2), h))
            out.append(row)
        return out


# ---------------------------------------------------------------- helpers
def _samples(pts, step):
    """Points every *step* along a polyline, vertices kept: (x, y, t)
    with t the distance along it."""
    out, t = [], 0.0
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        length = math.hypot(bx - ax, by - ay)
        if length < 1.0:
            continue
        k = max(1, int(math.ceil(length / step)))
        for m in range(k):
            f = m / k
            out.append((ax + (bx - ax) * f, ay + (by - ay) * f, t + length * f))
        t += length
    if pts:
        out.append((pts[-1][0], pts[-1][1], t))
    return out


def _nearest_on(samples, zs, x, y):
    """(distance to the sampled polyline, profile height there)."""
    best = None
    for k in range(len(samples) - 1):
        ax, ay, _ = samples[k]
        bx, by, _ = samples[k + 1]
        vx, vy = bx - ax, by - ay
        l2 = vx * vx + vy * vy
        if l2 < 1e-9:
            continue
        f = min(max(((x - ax) * vx + (y - ay) * vy) / l2, 0.0), 1.0)
        px, py = ax + vx * f, ay + vy * f
        d = math.hypot(x - px, y - py)
        if best is None or d < best[0]:
            best = (d, zs[k] + (zs[k + 1] - zs[k]) * f)
    return best


def _ribbon(samples, zf, left, right, below, above, name):
    """A closed strip between offsets *left* and *right* (mm, right of
    the direction of travel is +) from the centre line, from *below* to
    *above* the ground, sampled along the road: a tube of rectangular
    section, wound outward (the same ring order `treegen.Mesh.tube`
    uses)."""
    points, faces = [], []
    rings = []
    count = len(samples)
    for k, (x, y, _t) in enumerate(samples):
        a = samples[max(k - 1, 0)]
        b = samples[min(k + 1, count - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy) or 1.0
        rx, ry = dy / length, -dx / length           # right of travel
        mid = (left + right) / 2
        cx, cy = x + rx * mid, y + ry * mid
        half = (right - left) / 2
        zl = zf(x + rx * left, y + ry * left)
        zr = zf(x + rx * right, y + ry * right)
        zc = zf(cx, cy)
        base = len(points)
        # angle order about the travel direction: right-down, left-down,
        # left-up, right-up
        points += [[round(cx + rx * half, 1), round(cy + ry * half, 1),
                    round(zr + below, 1)],
                   [round(cx - rx * half, 1), round(cy - ry * half, 1),
                    round(zl + below, 1)],
                   [round(cx - rx * half, 1), round(cy - ry * half, 1),
                    round(zl + above, 1)],
                   [round(cx + rx * half, 1), round(cy + ry * half, 1),
                    round(zr + above, 1)]]
        rings.append((base, (cx, cy, zc + (below + above) / 2)))
    tris = []
    for k in range(len(rings) - 1):
        r0, r1 = rings[k][0], rings[k + 1][0]
        for m in range(4):
            a, b = r0 + m, r0 + (m + 1) % 4
            c, e = r1 + m, r1 + (m + 1) % 4
            tris += [(a, b, e), (a, e, c)]
    first = len(points)
    points.append([round(v, 1) for v in rings[0][1]])
    last = len(points)
    points.append([round(v, 1) for v in rings[-1][1]])
    r0, rl = rings[0][0], rings[-1][0]
    for m in range(4):
        tris.append((first, r0 + (m + 1) % 4, r0 + m))
        tris.append((last, rl + m, rl + (m + 1) % 4))
    faces = [[a, c, b] for a, b, c in tris]           # clockwise outside
    return CadNode("polyhedron", name, dict(points=points, faces=faces))


def _dashes(pts, zf, lift, length=3000.0, gap=3000.0, width=150.0):
    """Centre-line dashes riding on the tarmac: small closed prisms whose
    ends follow the ground."""
    points, faces = [], []
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        seg = math.hypot(bx - ax, by - ay)
        if seg < length:
            continue
        ux, uy = (bx - ax) / seg, (by - ay) / seg
        rx, ry = uy * width / 2, -ux * width / 2
        s = gap / 2
        while s + length < seg:
            p0 = (ax + ux * s, ay + uy * s)
            p1 = (ax + ux * (s + length), ay + uy * (s + length))
            z0, z1 = zf(*p0) + lift, zf(*p1) + lift
            base = len(points)
            for (px, py), z in ((p0, z0), (p1, z1)):
                points += [[round(px + rx, 1), round(py + ry, 1), round(z, 1)],
                           [round(px - rx, 1), round(py - ry, 1), round(z, 1)],
                           [round(px - rx, 1), round(py - ry, 1),
                            round(z + 6, 1)],
                           [round(px + rx, 1), round(py + ry, 1),
                            round(z + 6, 1)]]
            # a box: faces clockwise from outside
            quads = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2),
                     (2, 6, 7, 3), (3, 7, 4, 0)]
            for a, b, c, d in quads:
                faces += [[base + a, base + b, base + c],
                          [base + a, base + c, base + d]]
            s += length + gap
    if not faces:
        return None
    return CadNode("polyhedron", "Dashes", dict(points=points, faces=faces))
