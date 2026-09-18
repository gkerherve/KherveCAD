"""A car built from a COLOURED four-view drawing (Qt-free, pure Python).

`car_sheets` holds what `khervecad.tools.carsheet` measured off such a
drawing: the side view's floor and roof and the top view's half width
at every station, the end views' cross-section shapes, the wheel
centres, and the glass / lamp / dark-trim / tail-lamp regions of every
view as polygons in millimetres. This builds the car from them:

- the BODY is one closed loft. Each station's section is the end view's
  own shape (the front view in the front half, the rear view in the
  rear, blended across the doors) cut to that station's floor and roof
  and scaled so its widest point is the plan width there. Over each
  wheel the drawing's floor IS the arch, so the wheel shows under it;
- the DETAILS are the body's own surface: every facet is looked at from
  the view it faces most squarely (side, front, rear or top), and if it
  falls inside that view's glass, lamp, trim or tail-lamp region it is
  lifted off the body as a thin closed shell in that colour
  (`patch_shell`). The windows, lamps, bumpers and grille land exactly
  where the drawing puts them, and follow the body's curve;
- wheels from `car_wheels` at the traced centres and the stated track;
  door mirrors where the drawing has them.

No booleans: every piece is a closed polyhedron, so the preview is the
model.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from . import car_models, car_sheets, car_wheels
from .landmark_kit import Kit
from .model import CadNode

#: stations along the body, and heights round each half-section
STATIONS = 170
LEVELS = 40
#: the end faces' concentric rings, as fractions of the end section
CAP_RINGS = (0.85, 0.7, 0.55, 0.4, 0.25, 0.1)
#: how far a detail shell sits off the body, and how thick it is (mm)
LIFT, THICK = 1.2, 3.5
#: regions smaller than this (mm²) are drawing noise, not details
MIN_AREA = dict(glass=2500.0, lamp=600.0, dark=4000.0, tail=800.0)
#: a side view's dark regions above this much of the height are panel
#: lines and shadows, not trim
SIDE_TRIM_BELOW = 0.32
#: a front view's glass below this much of the height is a lamp lens
LAMP_BELOW = 0.66
#: blend from the front view's section to the rear view's over this span
BLEND = (0.38, 0.62)

COLOURS = dict(glass=("#141c24", "Plastic"), lamp=("#eef3f7", "Emissive"),
               dark=("#1e1f22", "Matte"), tail=("#c4121b", "Emissive"))
#: how strongly a leaning facet still counts as seen from the side / the
#: ends rather than from above
SIDE_BIAS, END_BIAS = 1.7, 1.5
#: facets facing down below this height (mm) are the dark underside
UNDERSIDE = 420.0
#: smoothing passes over the end views' section profiles
PROFILE_SMOOTH = 4
#: a lamp region at least this big (mm²) becomes a real lamp
LAMP_PART = 6000.0
#: a door mirror's height when the side view does not show it apart
MIRROR_HEIGHT = 0.72
#: which detail wins where two views' regions meet on one facet
PRIORITY = ("lamp", "tail", "glass", "dark")


# ----------------------------------------------------------- helpers

def _smooth(values, passes=2):
    out = list(values)
    for _ in range(passes):
        prev = list(out)
        for i in range(len(out)):
            a = prev[max(0, i - 1)]
            c = prev[min(len(prev) - 1, i + 1)]
            out[i] = 0.25 * a + 0.5 * prev[i] + 0.25 * c
    return out


def _lerp_table(xs, ys, x):
    if x <= xs[0]:
        return ys[0]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            f = (x - xs[i - 1]) / ((xs[i] - xs[i - 1]) or 1.0)
            return ys[i - 1] + (ys[i] - ys[i - 1]) * f
    return ys[-1]


def _area(poly):
    a = 0.0
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        a += x0 * y1 - x1 * y0
    return abs(a) / 2.0


def _inside(poly, x, y):
    """Even-odd point in polygon."""
    hit = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            if x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi:
                hit = not hit
        j = i
    return hit


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _norm(v):
    n = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def _signed_volume(tris):
    vol = 0.0
    for a, b, c in tris:
        vol += (a[0] * (b[1] * c[2] - b[2] * c[1])
                - a[1] * (b[0] * c[2] - b[2] * c[0])
                + a[2] * (b[0] * c[1] - b[1] * c[0]))
    return vol


def _key(p):
    return (round(p[0], 3), round(p[1], 3), round(p[2], 3))


def fill_pinches(patch, around, limit=12):
    """Grow *patch* until no vertex is a pinch — two parts of the patch
    touching at one corner. A shell's rim walls would meet there twice
    and the solid would not close. *around* maps a vertex key to every
    body triangle round it; a pinch takes its whole fan."""
    patch = list(patch)
    have = {tuple(_key(p) for p in t) for t in patch}
    for _ in range(limit):
        outgoing = {}
        edges = {}
        for a, b, c in patch:
            for p, q in ((a, b), (b, c), (c, a)):
                kp, kq = _key(p), _key(q)
                if (kq, kp) in edges:
                    del edges[(kq, kp)]
                else:
                    edges[(kp, kq)] = True
        for kp, _ in edges:
            outgoing[kp] = outgoing.get(kp, 0) + 1
        pinches = [k for k, n in outgoing.items() if n > 1]
        if not pinches:
            break
        for k in pinches:
            for tri in around.get(k, ()):
                sig = tuple(_key(p) for p in tri)
                if sig not in have:
                    have.add(sig)
                    patch.append(tri)
    return patch


def patch_shell(mesh, tris, lift=LIFT, thick=THICK):
    """A patch of a closed surface (counter-clockwise from outside) as
    a thin CLOSED shell standing off it: an inner copy *lift* out, an
    outer copy *thick* further, and walls along the patch's rim."""
    normals = {}
    for a, b, c in tris:
        n = _cross(_sub(b, a), _sub(c, a))
        for p in (a, b, c):
            k = _key(p)
            s = normals.get(k, (0.0, 0.0, 0.0))
            normals[k] = (s[0] + n[0], s[1] + n[1], s[2] + n[2])
    index, pts = {}, []

    def vid(p, layer):
        k = (_key(p), layer)
        i = index.get(k)
        if i is None:
            n = _norm(normals[_key(p)])
            d = lift if layer == 0 else lift + thick
            i = index[k] = len(pts)
            pts.append((p[0] + n[0] * d, p[1] + n[1] * d, p[2] + n[2] * d))
        return i

    faces, edges = [], {}
    for a, b, c in tris:
        oa, ob, oc = vid(a, 1), vid(b, 1), vid(c, 1)
        ia, ib, ic = vid(a, 0), vid(b, 0), vid(c, 0)
        faces.append((oa, ob, oc))
        faces.append((ia, ic, ib))
        for p, q in ((a, b), (b, c), (c, a)):
            kp, kq = _key(p), _key(q)
            if (kq, kp) in edges:
                del edges[(kq, kp)]
            else:
                edges[(kp, kq)] = (p, q)
    for p, q in edges.values():
        oa, ob = vid(p, 1), vid(q, 1)
        ia, ib = vid(p, 0), vid(q, 0)
        faces.append((oa, ia, ib))
        faces.append((oa, ib, ob))
    mesh.piece(pts, faces)


# ------------------------------------------------------------- the car

class SheetCar:
    def __init__(self, key, options=None):
        self.key = key
        self.spec = car_models.CARS[key]
        self.data = car_sheets.SHEETS[key]
        self.options = dict(options or {})
        s = self.spec
        self.L, self.W, self.H = float(s["L"]), float(s["W"]), float(s["H"])
        st = self.data["stations"]
        self.ys = [r[0] for r in st]
        self.floor = _smooth([r[1] for r in st])
        self.roof = _smooth([r[2] for r in st])
        self.half = _smooth([r[3] for r in st])
        # the end views step where a bumper or a wing lip starts; a loft
        # through those steps is a stack of ridges
        self.front = _smooth(self.data["front"], PROFILE_SMOOTH)
        self.rear = _smooth(self.data["rear"], PROFILE_SMOOTH)
        self._rings = {}
        self.regions = {}
        wheels = self.data.get("wheels", [])
        for view, regs in self.data["decals"].items():
            keep = []
            for cls, poly in regs:
                if view == "side" and cls == "tail":
                    continue        # the rear view places the tail lamps
                if view in ("front", "rear") and cls in ("lamp", "tail") \
                        and _area(poly) >= LAMP_PART:
                    continue        # built as lamps (`_lamps`), not decals
                if view == "side" and cls == "dark":
                    # trim on a flank is the sill and the bumper ends:
                    # low, and wholly low
                    if max(p[1] for p in poly) > SIDE_TRIM_BELOW * self.H:
                        continue
                if view == "front" and cls == "glass" and \
                        max(p[1] for p in poly) < LAMP_BELOW * self.H:
                    cls = "lamp"
                if _area(poly) < MIN_AREA[cls]:
                    continue
                xs = [p[0] for p in poly]
                ys = [p[1] for p in poly]
                keep.append((cls, poly, (min(xs), max(xs), min(ys),
                                         max(ys))))
            self.regions[view] = keep

    # ------------------------------------------------------ sections
    def y_of(self, s):
        return self.ys[0] + (self.ys[-1] - self.ys[0]) * s

    def shape(self, s, z):
        """The end views' half width at height *z* (fraction of W/2)."""
        v = min(1.0, max(0.0, z / self.H))
        n = len(self.front) - 1
        f = _lerp_table([k / n for k in range(n + 1)], self.front, v)
        r = _lerp_table([k / n for k in range(n + 1)], self.rear, v)
        t = min(1.0, max(0.0, (s - BLEND[0]) / (BLEND[1] - BLEND[0])))
        t = t * t * (3 - 2 * t)
        return (1 - t) * f + t * r

    def ring(self, s):
        key = round(s, 5)
        got = self._rings.get(key)
        if got is None:
            got = self._rings[key] = self._ring(s)
        return got

    def contains(self, s, x, z):
        """Is (x, z) inside the section at station *s*?"""
        ring = self.ring(s)
        right = ring[:LEVELS]
        if z < right[0][2] or z > right[-1][2]:
            return False
        for (x0, _, z0), (x1, _, z1) in zip(right, right[1:]):
            if z0 <= z <= z1:
                f = (z - z0) / ((z1 - z0) or 1.0)
                return abs(x) <= x0 + (x1 - x0) * f
        return False

    def surface_y(self, x, z, front=True, reach=0.3, steps=240):
        """Where the body's skin is at (x, z), walking in from the nose
        (or the tail): the y a lamp sits at."""
        for i in range(steps + 1):
            s = reach * i / steps
            s = s if front else 1.0 - s
            if self.contains(s, x, z):
                return self.y_of(s)
        return None

    def _ring(self, s):
        y = self.y_of(s)
        zb = _lerp_table(self.ys, self.floor, y)
        zt = max(_lerp_table(self.ys, self.roof, y), zb + 20.0)
        half = max(_lerp_table(self.ys, self.half, y), 15.0)
        levels = [zb + (zt - zb) * k / (LEVELS - 1) for k in range(LEVELS)]
        shape = [self.shape(s, z) for z in levels]
        # scale by the end view's widest over the WHOLE height, not over
        # this station's own slice: over an arch the slice starts higher,
        # and renormalising each slice ballooned the flank there
        widest = max(self.shape(s, self.H * k / 40) for k in range(41)) \
            or 1.0
        xs = _smooth([max(8.0, half * v / widest) for v in shape], 1)
        right = [(xs[k], y, levels[k]) for k in range(LEVELS)]
        left = [(-xs[k], y, levels[k]) for k in range(LEVELS - 1, -1, -1)]
        return right + left

    def body_tris(self):
        rings = [self.ring(i / (STATIONS - 1)) for i in range(STATIONS)]
        m = len(rings[0])
        tris = []
        for i in range(STATIONS - 1):
            r0, r1 = rings[i], rings[i + 1]
            for j in range(m):
                j2 = (j + 1) % m
                tris.append((r0[j], r0[j2], r1[j2]))
                tris.append((r0[j], r1[j2], r1[j]))
        for ring, flip in ((rings[0], True), (rings[-1], False)):
            c = tuple(sum(p[k] for p in ring) / m for k in range(3))
            # the end face as concentric rings, not one fan: a lamp or a
            # bumper drawn on it needs facets of its own size to land on
            layers = [ring] + [[(c[0] + (p[0] - c[0]) * f, p[1],
                                 c[2] + (p[2] - c[2]) * f) for p in ring]
                               for f in CAP_RINGS]
            for outer, inner in zip(layers, layers[1:]):
                for j in range(m):
                    j2 = (j + 1) % m
                    quad = ((outer[j], outer[j2], inner[j2]),
                            (outer[j], inner[j2], inner[j]))
                    for a, b, cc in quad:
                        tris.append((a, cc, b) if flip else (a, b, cc))
            last = layers[-1]
            for j in range(m):
                a, b = last[j], last[(j + 1) % m]
                tris.append((c, b, a) if flip else (c, a, b))
        tris = [t for t in tris if _key(t[0]) != _key(t[1])
                and _key(t[1]) != _key(t[2]) and _key(t[0]) != _key(t[2])]
        if _signed_volume(tris) < 0:
            tris = [(a, c, b) for a, b, c in tris]
        return tris

    # ------------------------------------------------------- details
    def classify(self, tri):
        a, b, c = tri
        n = _norm(_cross(_sub(b, a), _sub(c, a)))
        cx = (a[0] + b[0] + c[0]) / 3
        cy = (a[1] + b[1] + c[1]) / 3
        cz = (a[2] + b[2] + c[2]) / 3
        if n[2] < -0.85 and cz < UNDERSIDE:
            return "dark"                       # the underside
        # the view a facet is DRAWN in: side glass and wing-top lamps
        # lean, and by the bare biggest component they went to the top
        # view, where the drawing has nothing for them
        score = dict(side=abs(n[0]) * SIDE_BIAS,
                     front=max(0.0, -n[1]) * END_BIAS,
                     rear=max(0.0, n[1]) * END_BIAS,
                     top=max(0.0, n[2]))
        view = max(score, key=score.get)
        if view == "side":
            u, v = cy, cz
        elif view in ("front", "rear"):
            u, v = abs(cx), cz
        else:
            u, v = cy, cx
        found = set()
        for cls, poly, (x0, x1, y0, y1) in self.regions.get(view, ()):
            if view in ("front", "rear"):
                # symmetric about the centre line: test both sides
                hit = any(x0 <= uu <= x1 and y0 <= v <= y1
                          and _inside(poly, uu, v) for uu in (u, -u))
            elif view == "top":
                hit = any(x0 <= u <= x1 and y0 <= vv <= y1
                          and _inside(poly, u, vv) for vv in (v, -v))
            else:
                hit = x0 <= u <= x1 and y0 <= v <= y1 and \
                    _inside(poly, u, v)
            if hit:
                found.add(cls)
        for cls in PRIORITY:
            if cls in found:
                return cls
        return None

    # --------------------------------------------------------- build
    def paint(self):
        name = self.options.get("paint") or self.spec["paint"]
        colour = car_models.PAINTS.get(name, name)
        return colour if str(colour).startswith("#") else \
            car_models.PAINTS[self.spec["paint"]]

    def build(self) -> CadNode:
        kit = Kit()
        paint = self.paint()
        tris = self.body_tris()
        body = kit.mesh(paint, "Plastic")
        index, pts, faces = {}, [], []
        for tri in tris:
            ids = []
            for p in tri:
                k = _key(p)
                if k not in index:
                    index[k] = len(pts)
                    pts.append(p)
                ids.append(index[k])
            faces.append(tuple(ids))
        body.piece(pts, faces)
        groups = {}
        for tri in tris:
            cls = self.classify(tri)
            if cls:
                groups.setdefault(cls, []).append(tri)
        around = {}
        for tri in tris:
            for p in tri:
                around.setdefault(_key(p), []).append(tri)
        for cls, patch in groups.items():
            colour, material = COLOURS[cls]
            patch_shell(kit.mesh(colour, material),
                        fill_pinches(patch, around))
        self._mirrors(kit, paint)
        self._lamps(kit)
        name = f"{self.spec['make']} {self.spec['model']}"
        group = kit.node(name)
        for i in range(2):
            group.add(self._wheel_pair(i))
        scale = float(self.options.get("scale") or 1.0)
        if abs(scale - 1.0) > 1e-9:
            wrap = CadNode("scale", name, dict(x=scale, y=scale, z=scale))
            wrap.add(group)
            return wrap
        return group

    def _lamps(self, kit):
        """Headlamps and tail lamps as the things they are: a round lens
        in a chrome ring standing out of the wing where the front view
        has a lamp, and the red panels of the tail where the rear view
        has them — each set ON the body's skin at its own height."""
        for view, front in (("front", True), ("rear", False)):
            for cls, poly in self.data["decals"].get(view, ()):
                if view == "front" and cls == "glass" and \
                        max(p[1] for p in poly) < LAMP_BELOW * self.H:
                    cls = "lamp"
                if cls not in ("lamp", "tail") or _area(poly) < LAMP_PART:
                    continue
                xs = [p[0] for p in poly]
                zs = [p[1] for p in poly]
                cx, cz = (min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2
                w, h = max(xs) - min(xs), max(zs) - min(zs)
                y = self.surface_y(cx, cz, front)
                if y is None:
                    continue
                out = -1.0 if front else 1.0
                if cls == "lamp" and 0.55 < w / max(h, 1) < 1.8:
                    r = (w + h) / 4
                    kit.path([(cx, y - out * 40, cz), (cx, y + out * 6, cz)],
                             r + 12, "#dfe2e6", "Metal", sides=28)
                    kit.path([(cx, y - out * 30, cz), (cx, y + out * 12, cz)],
                             r, COLOURS["lamp"][0], "Emissive", sides=28)
                else:
                    colour, material = COLOURS[cls]
                    kit.box(cx - w / 2, y - out * 30, cz - h / 2,
                            cx + w / 2, y + out * 8, cz + h / 2,
                            colour, material)

    def _mirrors(self, kit, paint):
        m = self.data.get("mirror") or {}
        side, top = m.get("side"), m.get("top")
        if not top:
            return
        # a side view draws the mirror OVER the door, so it is no bump
        # in its silhouette: the top view places it, the beltline
        # height stands in for the side view's
        y = top[0]
        z = side[1] if side else MIRROR_HEIGHT * self.H
        x = abs(top[1])
        for sx in (-1, 1):
            cx = sx * x
            kit.solid([(cx + dx, y + dy, z + dz)
                       for dx in (-70, 70) for dy in (-35, 35)
                       for dz in (-45, 45)], paint, "Plastic")
            kit.bar((sx * (x - 110), y + 10, z - 30), (cx, y, z - 10), 10,
                    COLOURS["dark"][0])

    def _wheel_pair(self, i):
        o = self.options
        text = self.spec["tyre_front" if i == 0 else "tyre_rear"]
        tw, ratio, D = car_wheels.tyre_size(text)
        wheels = self.data["wheels"]
        y = wheels[i][0] if len(wheels) > i else \
            (-1 if i == 0 else 1) * self.spec["wb"] / 2
        track = self.spec.get("track")
        x = track[i] / 2.0 if track else \
            _lerp_table(self.ys, self.half, y) - tw / 2 - 20
        tyre_ratio, tread = car_wheels.TYRES.get(
            o.get("tyre") or "As delivered", car_wheels.TYRES["As delivered"])
        rim = o.get("rim") or self.spec["rim"]
        pair = CadNode("union", "Front wheels" if i == 0 else "Rear wheels")
        for side in (-1, 1):
            kit = Kit()
            car_wheels.build_wheel(kit, D, tw, tyre_ratio or ratio, tread,
                                   rim, o.get("finish") or "Silver",
                                   o.get("caliper") or "Red")
            wheel = kit.node(("Right " if side > 0 else "Left ")
                             + ("front" if i == 0 else "rear"))
            rot = CadNode("rotate", wheel.name, dict(x=0.0, y=90.0 * side,
                                                     z=0.0))
            rot.add(wheel)
            move = CadNode("translate", wheel.name, dict(
                x=side * x, y=y, z=D / 2))
            move.add(rot)
            pair.add(move)
        return pair


def build(key, options=None) -> CadNode:
    return SheetCar(key, options).build()
