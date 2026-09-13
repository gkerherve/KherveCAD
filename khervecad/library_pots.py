"""Pots and planters for the Part Library.

Round pots are ONE revolved wall profile — the outside drawn, the inside
following it a wall's thickness in, a floor with a drainage hole — so
they are hollow without a boolean and the preview is exact. A hexagonal,
octagonal or low-poly pot is the same profile revolved in 6, 8 or 7
segments. Square pots, troughs and the twisted star are a 2D ring
(outline minus the same outline a wall smaller) extruded with a taper
or a twist, over a floor slab. Every pot takes a colour and finish from
the dialog: terracotta (clay), glazes, concrete...

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .model import CadNode

CATEGORY = "Pots"

#: colour name -> (colour, material)
COLOURS = {
    "Terracotta": ("#c4663f", "Clay"),
    "White glaze": ("#f1efe8", "Plastic"),
    "Concrete": ("#9d9c98", "Matte"),
    "Blue glaze": ("#2e6a9b", "Plastic"),
    "Sage green": ("#8ea77e", "Matte"),
    "Charcoal": ("#3a3c40", "Matte"),
    "Sand": ("#d9c7a2", "Matte"),
}
COLOR_NAMES = list(COLOURS)
FIELDS = [("diameter", "Top Ø"), ("height", "Height"), ("wall", "Wall")]
TROUGH_FIELDS = [("length", "Length"), ("depth", "Depth"),
                 ("height", "Height"), ("wall", "Wall")]


def _sizes(ratio=0.9, diameters=(80, 120, 160, 200), wall=3.0):
    return {f"Ø{d}": dict(diameter=float(d), height=round(d * ratio, 1),
                          wall=wall if d < 150 else wall + 1.0)
            for d in diameters}


def _num(dims, key, default):
    try:
        return float(dims.get(key, default))
    except (TypeError, ValueError):
        return float(default)


def _dims(dims, ratio=0.9):
    D = max(_num(dims, "diameter", 120.0), 10.0)
    H = max(_num(dims, "height", D * ratio), 5.0)
    w = min(max(_num(dims, "wall", 3.0), 0.8), D / 6.0)
    return D / 2.0, H, w


def _paint(node, dims, default="Terracotta", name=None):
    colour_name = dims.get("_color") or default
    colour, material = COLOURS.get(colour_name, COLOURS[default])
    paint = CadNode("color", name or colour_name, dict(
        color=colour, alpha=1.0, material=material))
    paint.add(node)
    return paint


def _revolve(name, points, segments=96):
    rev = CadNode("rotate_extrude", name, dict(angle=360.0,
                                              segments=int(segments)))
    rev.add(CadNode("polygon", f"{name} profile", dict(
        x=0.0, y=0.0, points=[[round(r, 3), round(z, 3)]
                              for r, z in points])))
    return rev


def _hole(R):
    return max(R * 0.08, 3.0)


# ── revolved pots ───────────────────────────────────────────────────

def classic_profile(R, H, w):
    """The garden-centre pot: tapered wall, a thicker rim band, a small
    chamfered foot and a drainage hole."""
    rb, rim_h, rim_t = R * 0.72, H * 0.16, w * 1.4
    rt, floor, hole = R - rim_t, w * 1.4, _hole(R)
    return [(hole, 0.0), (rb - 1.5, 0.0), (rb, 1.5), (rt, H - rim_h),
            (R, H - rim_h), (R, H), (rt - w, H), (rb - w * 1.1, floor),
            (hole, floor)]


def build_classic(dims):
    R, H, w = _dims(dims)
    return _paint(_revolve("Flower pot", classic_profile(R, H, w)), dims)


def build_saucer(dims):
    R = max(_num(dims, "diameter", 140.0), 10.0) / 2.0
    H = max(_num(dims, "height", R * 0.36), 3.0)
    w = min(max(_num(dims, "wall", 3.0), 0.8), H / 2.0)
    pts = [(0.0, 0.0), (R * 0.82, 0.0), (R, H), (R - w, H),
           (R * 0.82 - w * 0.6, w), (0.0, w)]
    return _paint(_revolve("Saucer", pts), dims)


def build_cylinder(dims):
    R, H, w = _dims(dims, 0.85)
    floor, hole = w * 1.3, _hole(R)
    pts = [(hole, 0.0), (R - 3.0, 0.0), (R - 0.9, 0.5), (R, 3.0), (R, H),
           (R - w, H), (R - w, floor), (hole, floor)]
    return _paint(_revolve("Cylinder planter", pts), dims, "White glaze")


def _straight_taper(R, H, w, base=0.8):
    floor, hole = w * 1.3, _hole(R)
    return [(hole, 0.0), (R * base, 0.0), (R, H), (R - w, H),
            (R * base - w, floor), (hole, floor)]


def build_hex(dims):
    R, H, w = _dims(dims, 0.8)
    return _paint(_revolve("Hexagonal planter",
                           _straight_taper(R, H, w), segments=6),
                  dims, "Concrete")


def build_octagon(dims):
    R, H, w = _dims(dims, 0.8)
    return _paint(_revolve("Octagonal planter",
                           _straight_taper(R, H, w, 0.85), segments=8),
                  dims, "Sand")


def build_faceted(dims):
    """A low-poly pot: seven facets and a kink at the belly."""
    R, H, w = _dims(dims, 0.9)
    floor, hole = w * 1.3, _hole(R)
    rb, rm, rt = R * 0.62, R, R * 0.86
    pts = [(hole, 0.0), (rb, 0.0), (rm, H * 0.45), (rt, H), (rt - w, H),
           (rm - w, H * 0.45), (rb - w, floor), (hole, floor)]
    return _paint(_revolve("Faceted pot", pts, segments=7), dims,
                  "White glaze")


def _curve(R, H, fn, n=18):
    """Outside points (r, z) of a smooth wall r = R * fn(u), u = z/H."""
    return [(R * fn(i / n), H * i / n) for i in range(n + 1)]


def _shell(outside, w, floor, hole=0.0):
    """Close an outside wall (bottom to rim) into a pot profile: the
    inside a wall's thickness in, down to the floor."""
    inside = [(max(r - w, hole + 0.5), z) for r, z in reversed(outside)
              if z >= floor]
    return [(hole, 0.0)] + outside + inside + [(inside[-1][0], floor),
                                                (hole, floor)]


def build_bell(dims):
    """A bell pot: narrow foot, the wall flaring out to a wide rim."""
    R, H, w = _dims(dims, 0.85)
    outside = _curve(R, H, lambda u: 0.62 + 0.38 * u ** 1.8)
    return _paint(_revolve("Bell pot", _shell(outside, w, w * 1.3,
                                              _hole(R))), dims,
                  "Blue glaze")


def build_urn(dims):
    """A footed urn: a stem and foot, a round belly, a flared rim."""
    R, H, w = _dims(dims, 1.1)
    shape = [(0.0, 0.52), (0.07, 0.52), (0.1, 0.36), (0.18, 0.42),
             (0.3, 0.78), (0.5, 0.98), (0.7, 0.9), (0.84, 0.72),
             (0.92, 0.76), (1.0, 0.94)]
    outside = [(R * rr, H * u) for u, rr in shape]
    floor = H * 0.18
    inside = [(max(r - w, 1.0), z) for r, z in reversed(outside)
              if z >= floor + w]
    pts = [(0.0, 0.0)] + outside + inside + [(inside[-1][0], floor + w),
                                            (0.0, floor + w)]
    return _paint(_revolve("Urn", pts), dims, "Charcoal")


def build_bowl(dims):
    """A shallow succulent bowl."""
    R, H, w = _dims(dims, 0.4)
    floor, hole = w * 1.2, _hole(R)
    pts = [(hole, 0.0), (R * 0.55, 0.0), (R * 0.93, H * 0.65), (R, H),
           (R - w, H), (R * 0.93 - w, H * 0.65), (R * 0.55 - w * 0.6,
                                                    floor), (hole, floor)]
    return _paint(_revolve("Succulent bowl", pts), dims, "Terracotta")


def build_hanging(dims):
    """A round hanging pot with three lugs at the rim for the cords."""
    R, H, w = _dims(dims, 0.7)
    outside = _curve(R, H, lambda u: 0.25 + 0.75 * math.sin(
        (0.15 + 0.85 * u) * math.pi / 2))
    pot = CadNode("union", "Hanging pot")
    pot.add(_revolve("Bowl", _shell(outside, w, w * 1.2)))
    for k in range(3):
        ring = CadNode("rotate_extrude", "Lug", dict(angle=360.0,
                                                    segments=24))
        ring.add(CadNode("circle", "Lug section", dict(x=3.2, y=0.0,
                                                       radius=1.2)))
        stand = CadNode("rotate", "Upright", dict(x=90.0, y=0.0,
                                                  z=0.0))
        stand.add(ring)
        spot = CadNode("translate", "At the rim", dict(
            x=R + 2.0, y=0.0, z=H + 1.0))
        spot.add(stand)
        turn = CadNode("rotate", f"Lug {k + 1}", dict(x=0.0, y=0.0,
                                                      z=120.0 * k))
        turn.add(spot)
        pot.add(turn)
    return _paint(pot, dims, "White glaze")


def build_self_watering(dims):
    """A self-watering pot: a glazed outer pot holding the water, a
    black inner pot the plant sits in, and a water-level gauge."""
    R, H, w = _dims(dims, 1.0)
    outer_pts = [(0.0, 0.0), (R - 3.0, 0.0), (R, 3.0), (R, H),
                 (R - w, H), (R - w, w * 1.4), (0.0, w * 1.4)]
    ri, top = R - w - 1.5, H
    inner_h = H * 0.72
    inner_pts = [(ri * 0.55, top - inner_h), (ri * 0.8, top - inner_h),
                 (ri, top - 6.0), (ri + 2.5, top - 6.0), (ri + 2.5, top),
                 (ri - 2.0, top), (ri * 0.8 - 2.0, top - inner_h + 2.0),
                 (ri * 0.55, top - inner_h + 2.0)]
    part = CadNode("union", "Self-watering pot")
    part.add(_paint(_revolve("Outer pot", outer_pts), dims, "White glaze"))
    inner = CadNode("color", "Inner pot", dict(color="#1f1f21", alpha=1.0,
                                               material="Plastic"))
    inner.add(_revolve("Inner pot", inner_pts))
    part.add(inner)
    gauge = CadNode("color", "Water gauge", dict(color="#e8e6df",
                                                 alpha=1.0,
                                                 material="Plastic"))
    gauge.add(CadNode("cylinder", "Gauge tube", dict(
        x=ri * 0.7, y=0.0, z=w * 1.4, height=H - w * 1.4 + 6.0,
        radius_bottom=2.2, radius_top=2.2, segments=24, center=False)))
    gauge.add(CadNode("cylinder", "Float", dict(
        x=ri * 0.7, y=0.0, z=H + 4.0, height=5.0, radius_bottom=3.2,
        radius_top=3.2, segments=24, center=False)))
    part.add(gauge)
    return part


# ── extruded pots ───────────────────────────────────────────────────

def _rounded_rect(hx, hy, r, name="Outline"):
    r = max(min(r, hx - 0.2, hy - 0.2), 0.2)
    hull = CadNode("hull", name)
    for sx in (-1, 1):
        for sy in (-1, 1):
            hull.add(CadNode("circle", "Corner", dict(
                x=sx * (hx - r), y=sy * (hy - r), radius=r)))
    return hull


def _ring(outer, inner, name="Wall ring"):
    ring = CadNode("difference", name)
    ring.add(outer)
    ring.add(inner)
    return ring


def _walled(name, outline, inset, height, floor, flare=1.0, twist=0.0):
    """A pot from a 2D outline: the ring (outline minus the same outline
    a wall in) extruded with a flare or twist, on a floor slab."""
    pot = CadNode("union", name)
    walls = CadNode("linear_extrude", "Walls", dict(
        height=float(height), twist=float(twist), scale=float(flare),
        center=False, segments=24 if twist else 1))
    walls.add(_ring(outline(0.0), outline(inset)))
    pot.add(walls)
    base = CadNode("linear_extrude", "Floor", dict(height=float(floor)))
    base.add(outline(0.0))
    pot.add(base)
    return pot


def build_square(dims):
    """A tapered square planter with rounded corners."""
    R, H, w = _dims(dims, 0.9)
    flare = 1.22
    half = R / flare

    def outline(inset):
        return _rounded_rect(half - inset, half - inset,
                             max(half * 0.18 - inset, 1.0))
    return _paint(_walled("Square planter", outline, w, H, w * 1.3, flare),
                  dims, "Concrete")


def _star(r_out, r_in, points=6, name="Star"):
    pts = []
    for i in range(points * 2):
        r = r_out if i % 2 == 0 else r_in
        a = i * math.pi / points
        pts.append([round(r * math.cos(a), 3), round(r * math.sin(a), 3)])
    return CadNode("polygon", name, dict(x=0.0, y=0.0, points=pts))


def build_twist(dims):
    """A six-pointed star planter, twisted and flaring as it rises."""
    R, H, w = _dims(dims, 1.0)
    flare = 1.15
    r_out = R / flare

    def outline(inset):
        return _star(r_out - inset, r_out * 0.74 - inset)
    return _paint(_walled("Twisted star planter", outline, w, H, w * 1.3,
                          flare, twist=40.0), dims, "Sage green")


def build_trough(dims):
    """A window box: a long rounded trough, slightly flared."""
    L = max(_num(dims, "length", 600.0), 40.0)
    D = max(_num(dims, "depth", 180.0), 30.0)
    H = max(_num(dims, "height", 160.0), 20.0)
    w = min(max(_num(dims, "wall", 4.0), 0.8), D / 6.0)
    flare = 1.08

    def outline(inset):
        return _rounded_rect(L / 2.0 / flare - inset, D / 2.0 / flare - inset,
                             max(D * 0.12 - inset, 1.0))
    return _paint(_walled("Window box", outline, w, H, w * 1.3, flare),
                  dims, "Terracotta")


def _part(label, build, sizes=None, fields=FIELDS):
    return dict(label=label, category=CATEGORY, sizes=sizes or _sizes(),
                fields=fields, build=build, colors=COLOR_NAMES)


PARTS = {
    "pot_classic": _part("Flower pot (classic, tapered)", build_classic),
    "pot_saucer": _part("Saucer (drip tray)", build_saucer,
                        _sizes(0.14, (100, 140, 180, 220))),
    "pot_cylinder": _part("Cylinder planter", build_cylinder,
                          _sizes(0.85)),
    "pot_bell": _part("Bell pot", build_bell, _sizes(0.85)),
    "pot_urn": _part("Urn (footed)", build_urn,
                     _sizes(1.1, (120, 160, 220, 300))),
    "pot_bowl": _part("Succulent bowl (shallow)", build_bowl,
                      _sizes(0.4, (100, 150, 200, 260))),
    "pot_hex": _part("Hexagonal planter", build_hex, _sizes(0.8)),
    "pot_octagon": _part("Octagonal planter", build_octagon, _sizes(0.8)),
    "pot_faceted": _part("Low-poly faceted pot", build_faceted),
    "pot_square": _part("Square planter (tapered)", build_square),
    "pot_twist": _part("Twisted star planter", build_twist, _sizes(1.0)),
    "pot_hanging": _part("Hanging pot (with lugs)", build_hanging,
                         _sizes(0.7, (100, 140, 180))),
    "pot_self_watering": _part("Self-watering pot", build_self_watering,
                               _sizes(1.0, (120, 160, 200))),
    "pot_trough": _part(
        "Window box (trough)", build_trough,
        {"400 mm": dict(length=400.0, depth=150.0, height=130.0, wall=4.0),
         "600 mm": dict(length=600.0, depth=180.0, height=160.0, wall=4.0),
         "800 mm": dict(length=800.0, depth=200.0, height=180.0,
                        wall=5.0)},
        TROUGH_FIELDS),
}
