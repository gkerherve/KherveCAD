"""Wheels and tyres for the Car Builder (Qt-free).

A wheel is built with its axis along +Z, the outer face at +Z, centred
on the origin, and written into a `landmark_kit.Kit` — one closed
polyhedron per colour and material, so four wheels are a handful of
nodes and preview exactly. `car_build` turns and places them.

Tyres are revolved closed profiles (`revolve`): a sidewall bulge, a
rounded shoulder and a tread. The overall diameter is the car's own
(from its published tyre size, `tyre_size`); a tyre style only changes
the sidewall ratio, so the rim grows or shrinks inside the same tyre.
Rims are a barrel with a lip, a dark well, a brake disc and caliper, a
hub and spokes (each spoke a convex hull, `_spoke`), in the styles of
`RIMS`.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
import re

RUBBER = "#1c1d20"
WELL = "#2a2c30"
DISC = "#8d9096"
WHITEWALL = "#f1f0ea"

#: tyre style -> (sidewall ratio or None = as delivered, tread)
TYRES = {
    "As delivered": (None, "road"),
    "Performance (low profile)": (0.30, "road"),
    "Sport": (0.40, "road"),
    "Touring": (0.55, "road"),
    "Classic": (0.70, "road"),
    "Classic whitewall": (0.70, "whitewall"),
    "Off-road": (0.65, "offroad"),
    "Racing slick": (0.35, "slick"),
}

#: rim style -> spoke recipe
RIMS = {
    "Five spoke": dict(n=5, w0=60, w1=46, dish=25),
    "Ten spoke": dict(n=10, w0=24, w1=22, dish=20),
    "Y spoke": dict(n=5, pair=9, w0=34, w1=26, dish=30),
    "Mesh (BBS)": dict(n=16, w0=12, w1=10, dish=35, mesh=True),
    "Fuchs": dict(n=5, w0=55, w1=170, dish=18),
    "Turbine": dict(n=12, w0=26, w1=30, dish=10, skew=14),
    "Centre lock": dict(n=10, w0=30, w1=20, dish=35, centre_lock=True),
    "Monoblock": dict(n=6, w0=110, w1=210, dish=8),
    "Steel with hubcap": dict(n=0, hubcap=True),
}

#: rim finish -> (colour, material)
FINISHES = {
    "Silver": ("#c9ccd1", "Metal"),
    "Chrome": ("#e4e7ea", "Metal"),
    "Gunmetal": ("#4b4f55", "Metal"),
    "Black": ("#222326", "Plastic"),
    "Gold": ("#c9a24a", "Gold"),
    "White": ("#eeeeea", "Plastic"),
}

CALIPERS = {"Red": "#c41e24", "Yellow": "#e3b51b", "Black": "#2a2b2e",
            "Silver": "#b9bdc2"}


def tyre_size(text: str):
    """(width mm, sidewall ratio, overall diameter mm) of "245/35 R20"."""
    m = re.match(r"\s*(\d+)\s*/\s*(\d+)\s*[A-Z]*\s*R?\s*(\d+(?:\.\d+)?)",
                 text.upper())
    if not m:
        raise ValueError(f"not a tyre size: {text!r}")
    width, ratio, rim = float(m[1]), float(m[2]) / 100, float(m[3])
    return width, ratio, rim * 25.4 + 2 * width * ratio


# ------------------------------------------------------------ meshing

def closed_grid(mesh, rings, wrap_rings=False, wrap_points=True,
                caps=True):
    """Rings of equal length joined into ONE closed piece of *mesh*
    (`treegen.Mesh`); open ends fanned from their centroid. The winding
    is chosen by signed volume, so callers never think about it."""
    n, m = len(rings), len(rings[0])
    pts = [p for ring in rings for p in ring]
    tris = []
    last = n if wrap_rings else n - 1
    lastp = m if wrap_points else m - 1
    for i in range(last):
        i2 = (i + 1) % n
        for j in range(lastp):
            j2 = (j + 1) % m
            a, b = i * m + j, i * m + j2
            c, d = i2 * m + j2, i2 * m + j
            tris += [(a, b, c), (a, c, d)]
    if caps and not wrap_rings:
        for i, flip in ((0, True), (n - 1, False)):
            ring = rings[i]
            centre = tuple(sum(p[k] for p in ring) / m for k in range(3))
            ci = len(pts)
            pts.append(centre)
            for j in range(m):
                a, b = i * m + j, i * m + (j + 1) % m
                tris.append((ci, b, a) if flip else (ci, a, b))
    vol = 0.0
    for a, b, c in tris:
        pa, pb, pc = pts[a], pts[b], pts[c]
        vol += (pa[0] * (pb[1] * pc[2] - pb[2] * pc[1])
                - pa[1] * (pb[0] * pc[2] - pb[2] * pc[0])
                + pa[2] * (pb[0] * pc[1] - pb[1] * pc[0]))
    if vol < 0:
        tris = [(a, c, b) for a, b, c in tris]
    mesh.piece(pts, tris)


def revolve(mesh, profile, segments=48):
    """A closed (r, z) *profile* loop turned about Z."""
    rings = []
    for k in range(segments):
        a = 2 * math.pi * k / segments
        ca, sa = math.cos(a), math.sin(a)
        rings.append([(r * ca, r * sa, z) for r, z in profile])
    closed_grid(mesh, rings, wrap_rings=True, wrap_points=True)


def _arc(cx, cz, r, a0, a1, steps):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * t / steps)),
             cz + r * math.sin(math.radians(a0 + (a1 - a0) * t / steps)))
            for t in range(steps + 1)]


def tyre_profile(R, rr, tw, tread="road"):
    """The tyre's closed (r, z) section: bead, bulging sidewall, rounded
    shoulder, tread and back."""
    h = tw / 2
    side = R - rr
    sh = min((0.08 if tread == "slick" else 0.22) * tw, 0.45 * side)
    bulge = min(0.06 * tw, 12.0)
    mid = rr + 0.45 * side
    pts = [(rr, -h + 8), (mid - 0.2 * side, -h - bulge * 0.5),
           (mid + 0.15 * side, -h - bulge * 0.3)]
    pts += _arc(R - sh, -h + sh, sh, 180, 90, 5)
    pts += _arc(R - sh, h - sh, sh, 90, 0, 5)
    pts += [(mid + 0.15 * side, h + bulge * 0.3),
            (mid - 0.2 * side, h + bulge * 0.5), (rr, h - 8)]
    # counter-clockwise in (r, z) is not needed: closed_grid picks it
    return pts


# ------------------------------------------------------------- wheel

def _spoke(kit, angle, r0, r1, w0, w1, z_in, z_out, dish, thick,
           colour, material, skew=0.0):
    """One spoke from radius *r0* (hub, sunk by *dish*) to *r1* (rim)."""
    pts = []
    for r, w, zf, turn in ((r0, w0, z_out - dish, 0.0),
                           (r1, w1, z_out, skew)):
        a = math.radians(angle + turn)
        d = (math.cos(a), math.sin(a))
        p = (-d[1], d[0])
        for s in (-0.5, 0.5):
            for z in (zf - thick, zf):
                pts.append((d[0] * r + p[0] * w * s,
                            d[1] * r + p[1] * w * s, z))
    kit.solid(pts, colour, material)


def build_wheel(kit, D, tw, ratio, tread="road", rim="Five spoke",
                finish="Silver", caliper="Red", segments=48):
    """Write one wheel (axis +Z, outer face +Z) into *kit*."""
    R = D / 2
    rr = max(R - tw * ratio, 0.5 * R)
    h = tw / 2
    colour, material = FINISHES.get(finish, FINISHES["Silver"])

    tyre = kit.mesh(RUBBER, "Rubber")
    revolve(tyre, tyre_profile(R, rr, tw, tread), segments)
    if tread == "whitewall":
        white = kit.mesh(WHITEWALL, "Rubber")
        a, b = rr + 0.2 * (R - rr), rr + 0.55 * (R - rr)
        z = h + min(0.06 * tw, 12.0) * 0.35
        revolve(white, [(a, z - 2), (b, z - 2), (b, z + 1.5), (a, z + 1.5)],
                segments)
    elif tread == "offroad":
        blocks = 40
        for k in range(blocks):
            a = 360.0 * k / blocks
            off = 0.22 * tw if k % 2 else -0.22 * tw
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            kit.obox(ca * (R - 4), sa * (R - 4), off - 0.2 * tw,
                     22, 0.9 * math.pi * 2 * R / blocks, 0.4 * tw,
                     a, RUBBER, "Rubber")

    # rim barrel + lip
    face = h - 12
    rim_mesh = kit.mesh(colour, material)
    revolve(rim_mesh, [(rr - 18, -h + 14), (rr + 4, -h + 14),
                       (rr + 4, face - 14), (rr + 16, face - 14),
                       (rr + 16, face), (rr - 18, face)], segments)
    # dark well and brake behind the spokes
    revolve(kit.mesh(WELL, "Matte"),
            [(0, -h + 20), (rr - 17, -h + 20), (rr - 17, -h + 34),
             (0, -h + 34)], 24)
    disc_r = 0.8 * (rr - 20)
    revolve(kit.mesh(DISC, "Metal"),
            [(0.35 * rr, -h + 40), (disc_r, -h + 40), (disc_r, -h + 68),
             (0.35 * rr, -h + 68)], 36)
    cal = CALIPERS.get(caliper, CALIPERS["Red"])
    a = math.radians(40)
    kit.obox(math.cos(a) * (disc_r - 25), math.sin(a) * (disc_r - 25),
             -h + 30, 70, 0.9 * disc_r * 0.9, 50, 130, cal, "Plastic")

    spec = RIMS.get(rim, RIMS["Five spoke"])
    hub_r = 0.24 * rr
    if spec.get("hubcap"):
        revolve(rim_mesh, [(0, face - 30), (rr - 10, face - 30),
                           (rr - 10, face - 20), (0.75 * rr, face - 14),
                           (0.3 * rr, face - 8), (0, face - 8)], 36)
        revolve(kit.mesh(FINISHES["Chrome"][0], "Metal"),
                [(0, face - 10)] + [(0.55 * rr * math.cos(t), face - 10
                                     + 30 * math.sin(t))
                                    for t in (0.0, 0.5, 1.0, 1.35)]
                + [(0, face + 20)], 36)
        return
    dish = spec.get("dish", 20)
    thick = 22
    n = spec["n"]
    for k in range(n):
        ang = 360.0 * k / n
        pairs = ((ang - spec["pair"], ang + spec["pair"])
                 if spec.get("pair") else (ang,))
        for a in pairs:
            _spoke(kit, a, hub_r - 6, rr - 12, spec["w0"], spec["w1"],
                   -h, face, dish, thick, colour, material,
                   spec.get("skew", 0.0))
        if spec.get("mesh"):
            _spoke(kit, ang + 180.0 / n, 0.55 * rr, rr - 12, 9, 9,
                   -h, face - 6, 6, 12, colour, material, -22.0)
            _spoke(kit, ang + 180.0 / n, 0.55 * rr, rr - 12, 9, 9,
                   -h, face - 6, 6, 12, colour, material, 22.0)
    # hub
    revolve(rim_mesh, [(0, face - dish - 30), (hub_r, face - dish - 30),
                       (hub_r, face - dish), (0.6 * hub_r, face - dish + 8),
                       (0, face - dish + 8)], 32)
    if spec.get("centre_lock"):
        kit.cone(0, 0, face - dish, face - dish + 30, 0.55 * hub_r,
                 0.5 * hub_r, cal, "Plastic", sides=6)
    else:
        for k in range(5):
            a = math.radians(72 * k + 36)
            kit.cone(math.cos(a) * 0.62 * hub_r, math.sin(a) * 0.62 * hub_r,
                     face - dish, face - dish + 14, 9, 8,
                     FINISHES["Chrome"][0], "Metal", sides=6)
