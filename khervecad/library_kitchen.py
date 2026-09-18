"""Kitchen and tableware for the Part Library.

Every vessel — plate, bowl, mug, cup, jug, glass, bottle, pan, pot — is
ONE revolved wall: the outside drawn from the axis at the base up to the
rim, the inside the same outline moved a wall's thickness along its
normals (`library_chem._offset_in`, even round every curve), joined by a
rounded lip. So a mug is hollow and a wine glass has a bowl you can see
into, without a boolean, and the preview is exact. A glass can hold a
drink: the inside outline up to the fill line, a hair smaller than the
glass (`liquid`).

Handles are half tori stood on end (`loop_handle`), spouts a hull of
spheres along a curve (`spout`), pan handles rounded boxes; cutlery is
flat outlines extruded, the bowl of a spoon a thin spherical cap made
oval. Everything stands on z = 0; a place setting faces a diner sitting
at -Y (fork on their left, -X).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .library_chem import GLASS, GLASS_ALPHA, _arc, _dedupe, _interp, \
    _offset_in
from .library_music import (box, capsule, cbox, choice, cyl, ellipsoid,
                            extrude, group, loop, move, num, paint, polygon,
                            revolve, sphere, table, torus, turn)
from .model import CadNode

CATEGORY = "Kitchen & tableware"

GLAZES = {"White porcelain": ("#f4f2ec", "Plastic"),
          "Cream stoneware": ("#e9dfc8", "Plastic"),
          "Cobalt blue": ("#2c4f9e", "Plastic"),
          "Sage green": ("#9fb394", "Plastic"),
          "Duck-egg blue": ("#a9d0cd", "Plastic"),
          "Charcoal": ("#3a3b3f", "Matte"),
          "Terracotta": ("#c4663f", "Clay")}
DRINKS = {"Red wine": ("#5a0d1c", 0.9), "White wine": ("#e6d27a", 0.55),
          "Rosé": ("#f0a3a0", 0.6), "Water": ("#bfe3f2", 0.3),
          "Orange juice": ("#f39a1e", 0.9), "Beer": ("#d8961c", 0.85),
          "Cola": ("#3b1a0e", 0.92), "Milk": ("#f6f4ee", 0.95),
          "Empty": None}
COOKWARE = {"Stainless steel": ("#c9ccd1", "Metal"),
            "Copper": ("#c46c3c", "Copper"),
            "Cast iron": ("#2a2a2c", "Matte"),
            "Red enamel": ("#b3261e", "Plastic"),
            "Cream enamel": ("#eee6d2", "Plastic"),
            "Non-stick black": ("#232326", "Matte")}
CUTLERY = {"Stainless steel": ("#cfd2d6", "Metal"),
           "Gold": ("#d4af37", "Gold"),
           "Matte black": ("#26262a", "Matte"),
           "Copper": ("#c46c3c", "Copper")}
WOODS = {"Beech": ("#d8b27a", "Plastic"), "Walnut": ("#5b3a24", "Plastic"),
         "Bamboo": ("#d9bf82", "Plastic"),
         "Olive wood": ("#b7925a", "Plastic")}
BLACK = "#1f1f22"
STEEL = "#c9ccd1"


# ── shared shapes ─────────────────────────────────────────────────────

def bezier(p0, p1, p2, p3, n=12):
    """Points of a cubic Bézier, both ends included."""
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * t * (1 - t) ** 2, \
            3 * t * t * (1 - t), t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
                    a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


def rounded_base(R, r, n=5):
    """Outline from the axis along the floor round a corner of radius *r*
    to the wall at radius *R* (climbing from there)."""
    return [(0.0, 0.0)] + _arc(R - r, r, r, -90.0, 0.0, n)


def wall(outer, w):
    """A revolved vessel profile: the outside (*outer*, from the axis at
    the base to the rim), a round lip, and the inside a wall *w* in.
    Returns (profile, inside)."""
    outer = _dedupe(outer)
    inner = _offset_in(outer, w)
    (ro, zo), (ri, zi) = outer[-1], inner[-1]
    cx, cz = (ro + ri) / 2.0, (zo + zi) / 2.0
    rad = math.hypot(ro - ri, zo - zi) / 2.0
    a0 = math.degrees(math.atan2(zo - cz, ro - cx))
    lip = _arc(cx, cz, rad, a0, a0 + 180.0, 8)[1:-1]
    return _dedupe(outer + lip + inner[::-1]), inner


def vessel(name, outer, w, colour, seg=64):
    profile, inner = wall(outer, w)
    return paint(name, colour[0], colour[1], [revolve(name, profile,
                                                      seg=seg)]), inner


def liquid(inner, fill, drink, name="Drink"):
    """The inside outline up to *fill* (a height) as a solid of *drink*
    ((colour, alpha) or None), 0.4 mm clear of the wall."""
    if not drink:
        return None
    r_at = _interp(inner)
    pts = [(max(r - 0.4, 0.0), z) for r, z in inner if z < fill]
    if not pts:
        return None
    pts += [(max(r_at(fill) - 0.4, 0.0), fill), (0.0, fill)]
    colour, alpha = drink
    return paint(name, colour, "Plastic", [revolve(name, _dedupe(pts),
                                                   seg=64)], alpha=alpha)


def glass_paint(name, kids):
    return paint(name, GLASS, "Glass", kids, alpha=GLASS_ALPHA)


def loop_handle(name, reach, thick, x, z, stretch=1.3, side=1):
    """A D-shaped handle: half a torus of radius *reach* stood upright,
    bulging along +x (-x for *side* -1), stretched in z, its two ends on
    the wall at (x, z ± reach·stretch)."""
    arc = turn(turn(torus(name, reach, thick, angle=180.0, seg=24), x=90.0),
               y=90.0, name="Upright")
    tall = CadNode("scale", "Stretched", dict(x=1.0, y=1.0, z=stretch))
    tall.add(arc)
    placed = move(tall, x, 0.0, z, name)
    return turn(placed, z=180.0, name="Other side") if side < 0 else placed


def spout(name, pts, radii):
    """A spout: a hull of two spheres per stretch of the path."""
    g = CadNode("union", name)
    for (a, ra), (b, rb) in zip(zip(pts, radii), zip(pts[1:], radii[1:])):
        h = CadNode("hull", f"{name} stretch")
        h.add(sphere("From", ra, *a, seg=24))
        h.add(sphere("To", rb, *b, seg=24))
        g.add(h)
    return g


def rbox(name, x, y, z, w, d, h, r):
    """A rounded box centred on (x, y, z)."""
    r = max(min(r, w / 2 - 0.01, d / 2 - 0.01, h / 2 - 0.01), 0.1)
    return CadNode("rounded_box", name, dict(
        x=round(x, 3), y=round(y, 3), z=round(z, 3), width=round(w, 3),
        depth=round(d, 3), height=round(h, 3), radius=round(r, 3),
        center=True, segments=16))


def _glaze(dims, default="White porcelain"):
    return choice(dims, GLAZES, default)


# ── tableware ─────────────────────────────────────────────────────────

PLATE_SIZES = {"Dinner plate Ø270": dict(diameter=270.0, height=24.0),
               "Side plate Ø210": dict(diameter=210.0, height=20.0),
               "Charger Ø310": dict(diameter=310.0, height=22.0),
               "Saucer Ø150": dict(diameter=150.0, height=18.0)}
BOWL_SIZES = {"Cereal bowl Ø150": dict(diameter=150.0, height=65.0),
              "Soup bowl Ø180": dict(diameter=180.0, height=60.0),
              "Serving bowl Ø250": dict(diameter=250.0, height=100.0),
              "Mixing bowl Ø280": dict(diameter=280.0, height=140.0)}
DIAM_H = [("diameter", "Diameter"), ("height", "Height")]


def plate(name, D, H, colour, t=4.0):
    """A plate: a flat well, a curved rise to a slightly lifted rim, a
    foot ring underneath."""
    R, foot = D / 2.0, 3.0
    top = [(0.0, foot + t)] + bezier(
        (0.55 * R, foot + t), (0.7 * R, foot + t), (0.72 * R, H - 2.0),
        (0.8 * R, H - 1.5), 8)[0:] + [(R, H)]
    under = _offset_in(top, -t)
    (ro, zo), (ru, zu) = top[-1], under[-1]
    cx, cz = (ro + ru) / 2.0, (zo + zu) / 2.0
    rad = math.hypot(ro - ru, zo - zu) / 2.0
    a0 = math.degrees(math.atan2(zo - cz, ro - cx))
    lip = _arc(cx, cz, rad, a0 - 180.0, a0, 6)[1:-1]
    profile = _dedupe([(0.0, foot)] + [(r, z) for r, z in under if r > 0] +
                      lip + top[::-1])
    return paint(name, colour[0], colour[1], [
        revolve(name, profile, seg=96),
        revolve("Foot ring", [(0.42 * R, 0.0), (0.47 * R, 0.0),
                              (0.48 * R, foot + 0.5), (0.41 * R, foot + 0.5)],
                seg=96)])


def build_plate(dims):
    row = table(dims, PLATE_SIZES)
    D = max(num(row, "diameter", 270.0), 60.0)
    H = min(max(num(row, "height", 24.0), 10.0), D / 4)
    return plate("Plate", D, H, _glaze(dims))


def bowl_outline(R, H, flat=0.45, belly=0.9):
    return [(0.0, 0.0)] + bezier((flat * R, 0.0), (belly * R, 0.0),
                                 (R, H * 0.45), (R, H), 12)


def build_bowl(dims):
    row = table(dims, BOWL_SIZES)
    R = max(num(row, "diameter", 150.0), 40.0) / 2.0
    H = max(num(row, "height", 65.0), 15.0)
    w = min(max(R * 0.05, 3.0), 6.0)
    body, _inner = vessel("Bowl", bowl_outline(R, H), w, _glaze(dims))
    foot = paint("Foot", *_glaze(dims), [revolve("Foot ring", [
        (0.3 * R, 0.0), (0.36 * R, 0.0), (0.37 * R, 3.0), (0.3 * R, 3.0)])])
    return group("Bowl", [move(body, z=2.0, name="On its foot"), foot])


def build_pasta_bowl(dims):
    """A wide pasta bowl: a deep well and a broad flat rim."""
    D = max(num(dims, "diameter", 280.0), 120.0)
    R = D / 2.0
    outer = [(0.0, 0.0)] + bezier((0.35 * R, 0.0), (0.6 * R, 0.0),
                                  (0.62 * R, 40.0), (0.66 * R, 44.0), 10) + \
        [(R, 50.0)]
    body, _ = vessel("Pasta bowl", outer, 4.5, _glaze(dims))
    return body


MUG_SIZES = {"Mug 300 ml": dict(diameter=82.0, height=95.0),
             "Large mug 450 ml": dict(diameter=90.0, height=115.0),
             "Espresso cup": dict(diameter=60.0, height=58.0)}


def build_mug(dims):
    """A mug: straight hollow wall, a rounded foot, a D handle; an
    optional drink inside."""
    row = table(dims, MUG_SIZES)
    R = max(num(row, "diameter", 82.0), 30.0) / 2.0
    H = max(num(row, "height", 95.0), 30.0)
    w = 4.5 if R > 35 else 3.5
    outer = rounded_base(R - 1.5, 6.0) + [(R, 12.0), (R, H)]
    colour = _glaze(dims)
    body, inner = vessel("Mug", outer, w, colour)
    reach = H * 0.3
    handle = paint("Handle", colour[0], colour[1], [
        loop_handle("Handle", reach, w * 0.9, R - w * 0.4, H * 0.52, 1.15)])
    return group("Mug", [body, handle,
                         liquid(inner, H - 14.0, DRINKS["Cola"],
                                "Coffee")])


def build_teacup(dims):
    """A tulip teacup on its saucer."""
    colour = _glaze(dims)
    R, H = 45.0, 62.0
    outer = [(0.0, 0.0), (18.0, 0.0), (19.0, 4.0), (24.0, 6.0)] + \
        bezier((24.0, 6.0), (38.0, 8.0), (41.0, 35.0), (R, H), 10)
    cup, inner = vessel("Cup", outer, 3.0, colour)
    handle = paint("Handle", colour[0], colour[1], [
        loop_handle("Handle", 15.0, 3.2, 38.0, 38.0, 1.1)])
    tea = liquid(inner, H - 10.0, ("#9a4a14", 0.9), "Tea")
    saucer = plate("Saucer", 150.0, 18.0, colour, t=3.5)
    return group("Teacup and saucer", [
        saucer, move(group("Cup", [cup, handle, tea]), z=11.0,
                     name="In the saucer's well")])


def build_teapot(dims):
    """A round teapot: belly, lid with a knob, a curving spout on +X and
    a handle on -X."""
    colour = _glaze(dims)
    R, H = 85.0, 125.0
    outer = [(0.0, 0.0), (48.0, 0.0), (50.0, 5.0)] + bezier(
        (50.0, 5.0), (R + 12.0, 20.0), (R + 8.0, 95.0), (46.0, 110.0), 12) + \
        [(44.0, H - 10.0)]
    body, _ = vessel("Pot", outer, 4.0, colour)
    lid = revolve("Lid", [(0.0, H - 12.0), (47.0, H - 12.0), (47.0, H - 9.0),
                          (40.0, H + 4.0), (14.0, H + 12.0), (8.0, H + 14.0),
                          (11.0, H + 24.0), (0.0, H + 27.0)])
    s = spout("Spout", [(R - 6.0, 0.0, 30.0), (R + 30.0, 0.0, 55.0),
                        (R + 55.0, 0.0, 95.0), (R + 62.0, 0.0, 108.0)],
              [15.0, 10.0, 7.0, 6.0])
    handle = turn(loop_handle("Handle", 44.0, 7.5, R - 6.0, 62.0, 0.95),
                  z=180.0, name="Opposite the spout")
    return paint("Teapot", colour[0], colour[1], [body, lid, s, handle])


def build_jug(dims):
    """A milk or water jug: a bellied wall, a pulled lip and a handle."""
    colour = _glaze(dims, "Cream stoneware")
    H = max(num(dims, "height", 180.0), 60.0)
    k = H / 180.0
    outer = [(0.0, 0.0), (48.0 * k, 0.0), (50.0 * k, 4.0 * k)] + bezier(
        (50.0 * k, 4 * k), (68.0 * k, 50 * k), (46.0 * k, 130 * k),
        (58.0 * k, H), 12)
    body, inner = vessel("Jug", outer, 4.0 * k, colour)
    # the pouring lip: a tongue hulled from the rim out to a tip
    top_r = outer[-1][0]
    lip = CadNode("hull", "Lip")
    for a in (-32.0, 32.0):
        lip.add(sphere("Rim", 2.5 * k, top_r * math.cos(math.radians(a)),
                       top_r * math.sin(math.radians(a)), H - 2.5 * k,
                       seg=12))
    lip.add(sphere("Tip", 2.5 * k, top_r + 17.0 * k, 0.0, H + 3.0 * k,
                   seg=12))
    lip.add(sphere("Under", 3.0 * k, top_r - 1.0 * k, 0.0, H - 20.0 * k,
                   seg=12))
    handle = loop_handle("Handle", 38.0 * k, 5.5 * k, 54.0 * k, 110.0 * k,
                         1.0, -1)
    return group("Jug", [body, paint("Lip", colour[0], colour[1], [lip]),
                         paint("Handle", colour[0], colour[1], [handle])])


def build_cake_stand(dims):
    colour = _glaze(dims)
    D = max(num(dims, "diameter", 280.0), 120.0)
    stand = revolve("Pedestal", [(0.0, 0.0), (70.0, 0.0), (70.0, 4.0),
                                 (20.0, 20.0), (16.0, 90.0), (26.0, 100.0),
                                 (0.0, 100.0)])
    top = move(plate("Plate", D, 14.0, colour), z=98.0, name="On top")
    return group("Cake stand", [paint("Pedestal", colour[0], colour[1],
                                      [stand]), top])


def build_egg_cup(dims):
    colour = _glaze(dims)
    outer = [(0.0, 0.0), (24.0, 0.0), (24.0, 3.0), (9.0, 12.0),
             (9.0, 22.0)] + bezier((9.0, 22.0), (27.0, 24.0), (26.0, 44.0),
                                   (24.0, 52.0), 8)
    cup, _ = vessel("Egg cup", outer, 2.5, colour)
    egg = paint("Egg", "#e9c9a2", "Matte", [
        ellipsoid("Egg", 21.0, 21.0, 28.0, 0.0, 0.0, 50.0)])
    return group("Egg cup", [cup, egg])


# ── glassware ─────────────────────────────────────────────────────────

STEMWARE = {
    "Red wine glass": dict(foot=38.0, stem=4.0, stem_h=95.0, belly=45.0,
                           rim=34.0, bowl_h=110.0, fill=0.35),
    "White wine glass": dict(foot=36.0, stem=3.8, stem_h=90.0, belly=38.0,
                             rim=30.0, bowl_h=100.0, fill=0.35),
    "Champagne flute": dict(foot=34.0, stem=3.5, stem_h=85.0, belly=27.0,
                            rim=25.0, bowl_h=150.0, fill=0.7),
    "Martini glass": dict(foot=40.0, stem=3.8, stem_h=95.0, belly=60.0,
                          rim=60.0, bowl_h=75.0, fill=0.75, cone=True),
}


def build_stemware(dims):
    """Foot, stem and a hollow bowl, with a drink to its usual level."""
    size = dims.get("_size") or next(iter(STEMWARE))
    g = STEMWARE.get(size, STEMWARE["Red wine glass"])
    w = 1.3
    zs = g["stem_h"] + 6.0
    if g.get("cone"):
        bowl = [(0.0, zs - 4.0)] + bezier((4.0, zs - 4.0), (20.0, zs + 10),
                                          (g["rim"] * 0.8, zs + g["bowl_h"]
                                           * 0.7), (g["rim"],
                                                    zs + g["bowl_h"]), 8)
    else:
        bowl = [(0.0, zs - 4.0)] + bezier(
            (6.0, zs - 4.0), (g["belly"] * 1.25, zs),
            (g["belly"] * 1.05, zs + g["bowl_h"] * 0.75),
            (g["rim"], zs + g["bowl_h"]), 14)
    inner = _offset_in(bowl, w)
    stem = [(0.0, 0.0), (g["foot"], 0.0), (g["foot"], 1.8),
            (g["stem"] * 2.2, 5.0), (g["stem"], 12.0), (g["stem"], zs - 6.0),
            (g["stem"] * 1.6, zs - 3.0)]
    outer = stem + [p for p in bowl if p[0] > g["stem"] * 1.7]
    (ro, zo), (ri, zi) = outer[-1], inner[-1]
    profile = _dedupe(outer + [((ro + ri) / 2 + 0.3, max(zo, zi) + 0.6)] +
                      inner[::-1])
    drink_name = dims.get("_color") or ("Red wine" if "Red" in size else
                                        "White wine")
    top = inner[-1][1]
    fill = inner[0][1] + (top - inner[0][1]) * g["fill"]
    return group(size.split(" (")[0], [
        glass_paint("Glass", [revolve("Glass", profile, seg=96)]),
        liquid(inner, fill, DRINKS.get(drink_name))])


TUMBLERS = {"Whisky tumbler": dict(diameter=82.0, height=90.0, base=14.0,
                                   flare=1.0, fill=0.35),
            "Highball": dict(diameter=68.0, height=150.0, base=10.0,
                             flare=1.04, fill=0.8),
            "Pint glass": dict(diameter=86.0, height=150.0, base=8.0,
                               flare=1.2, fill=0.9),
            "Water tumbler": dict(diameter=78.0, height=110.0, base=8.0,
                                  flare=1.1, fill=0.7)}


def build_tumbler(dims):
    """A flat-bottomed glass: a thick base, a straight or flared wall."""
    row = table(dims, TUMBLERS)
    R1 = max(num(row, "diameter", 80.0), 30.0) / 2.0
    H = max(num(row, "height", 100.0), 30.0)
    R0 = R1 / float(row.get("flare", 1.0))
    base, w = float(row.get("base", 8.0)), 2.0
    outer = [(0.0, 0.0), (R0 - 2.0, 0.0), (R0, 2.0), (R1, H)]
    inner = [(0.0, base), (R0 - w - 2.0, base), (R0 - w, base + 2.0),
             (R1 - w, H)]
    profile = outer + [(R1 - w / 2, H + 0.8)] + inner[::-1]
    size = dims.get("_size") or next(iter(TUMBLERS))
    drink = dims.get("_color") or ("Beer" if "Pint" in size else
                                   "Water")
    fill = base + (H - base) * float(row.get("fill", 0.7))
    return group(size, [glass_paint("Glass", [revolve("Glass", profile)]),
                        liquid(inner, fill, DRINKS.get(drink))])


def build_carafe(dims):
    H = max(num(dims, "height", 240.0), 80.0)
    k = H / 240.0
    outer = [(0.0, 0.0), (52 * k, 0.0), (58 * k, 6 * k)] + bezier(
        (58 * k, 6 * k), (78 * k, 90 * k), (30 * k, 150 * k),
        (32 * k, H), 14)
    profile, inner = wall(outer, 2.2 * k)
    drink = dims.get("_color") or "Water"
    return group("Carafe", [glass_paint("Glass", [revolve("Glass",
                                                          profile)]),
                            liquid(inner, 120 * k, DRINKS.get(drink))])


BOTTLE_GLASS = {"Green": "#2f5b2a", "Amber": "#7a4a12", "Clear": GLASS}


def build_wine_bottle(dims):
    """A 750 ml Bordeaux bottle: glass, wine to the shoulder, a label
    and a foil capsule."""
    H, R, rn = 300.0, 38.0, 14.5
    outer = [(0.0, 0.0), (R - 4.0, 0.0), (R, 4.0), (R, 190.0)] + bezier(
        (R, 190.0), (R, 215.0), (rn, 215.0), (rn, 235.0), 8) + \
        [(rn, H - 12.0), (rn + 1.5, H - 10.0), (rn + 1.5, H)]
    profile, inner = wall(outer, 3.0)
    drink = dims.get("_color") or "Red wine"
    glass = BOTTLE_GLASS["Clear" if drink in ("White wine", "Rosé", "Water")
                         else "Green"]
    return group("Wine bottle", [
        paint("Glass", glass, "Glass", [revolve("Bottle", profile)],
              alpha=0.55),
        liquid(inner, 205.0, DRINKS.get(drink), "Wine"),
        paint("Label", "#efe6cf", "Matte", [cyl("Label", R + 0.3, 80.0,
                                                z=60.0, seg=96)]),
        paint("Capsule", "#7a0f1e", "Metal", [cyl("Foil", rn + 2.0, 50.0,
                                                  z=H - 49.0, seg=48)]),
    ])


def build_mason_jar(dims):
    H = max(num(dims, "height", 140.0), 60.0)
    k = H / 140.0
    R = 42.0 * k
    outer = [(0.0, 0.0), (R - 5 * k, 0.0), (R, 5 * k), (R, 105 * k),
             (33 * k, 118 * k), (33 * k, H - 8 * k)]
    profile, inner = wall(outer, 2.5 * k)
    return group("Mason jar", [
        glass_paint("Glass", [revolve("Jar", profile)]),
        liquid(inner, 95 * k, ("#c22a2a", 0.92), "Jam"),
        paint("Lid", "#c9a24a", "Metal", [cyl("Lid band", 35.5 * k, 12 * k,
                                              z=H - 12 * k, seg=64)]),
    ])


# ── cookware ──────────────────────────────────────────────────────────

PAN_SIZES = {"Ø16 cm": dict(diameter=160.0, height=85.0),
             "Ø18 cm": dict(diameter=180.0, height=95.0),
             "Ø20 cm": dict(diameter=200.0, height=105.0)}
POT_SIZES = {"Ø24 cm stock pot": dict(diameter=240.0, height=200.0),
             "Ø28 cm stock pot": dict(diameter=280.0, height=240.0),
             "Ø20 cm casserole": dict(diameter=200.0, height=100.0),
             "Ø26 cm casserole": dict(diameter=260.0, height=120.0)}
FRY_SIZES = {"Ø24 cm": dict(diameter=240.0), "Ø28 cm": dict(diameter=280.0),
             "Ø20 cm": dict(diameter=200.0)}


def _finish(dims, default="Stainless steel"):
    return choice(dims, COOKWARE, default)


def _lid(R, H, finish, glass=True, knob="#1f1f22"):
    """A lid resting on the rim at *H*: a low dome (glass with a steel
    rim, or the pan's own finish) and a knob."""
    dome = revolve("Lid", [(0.0, H), (R + 2.0, H), (R + 2.0, H + 3.0),
                           (R * 0.6, H + R * 0.12), (0.0, H + R * 0.15)])
    rim = torus("Lid rim", R + 1.5, 2.0, seg=64)
    knob_node = revolve("Knob", [(0.0, 0.0), (10.0, 0.0), (7.0, 8.0),
                                 (14.0, 16.0), (12.0, 22.0), (0.0, 23.0)],
                        seg=32)
    top = H + R * 0.15 - 1.0
    kids = [move(paint("Knob", knob, "Plastic", [knob_node]), z=top,
                 name="Knob")]
    if glass:
        kids += [glass_paint("Lid glass", [dome]),
                 paint("Lid rim", STEEL, "Metal", [move(rim, z=H + 1.5,
                                                        name="Rim")])]
    else:
        kids.append(paint("Lid", finish[0], finish[1], [dome]))
    return group("Lid", kids)


def _pot_outline(R, H, r=10.0):
    return rounded_base(R, r) + [(R, H)]


def build_saucepan(dims):
    """A saucepan with a long handle on +X and a glass lid."""
    row = table(dims, PAN_SIZES)
    R = max(num(row, "diameter", 180.0), 60.0) / 2.0
    H = max(num(row, "height", 95.0), 30.0)
    finish = _finish(dims)
    body, _ = vessel("Pan", _pot_outline(R, H), 2.5, finish)
    L = R * 1.9
    handle = move(turn(rbox("Handle", L / 2, 0.0, 0.0, L, 26.0, 13.0, 6.0),
                       y=-12.0), R - 4.0, 0.0, H - 16.0, "Handle")
    glass = finish[1] in ("Metal", "Copper")
    return group("Saucepan", [
        body, paint("Handle", BLACK if not glass else STEEL,
                    "Matte" if not glass else "Metal", [handle]),
        _lid(R, H, finish, glass)])


def build_stock_pot(dims):
    """A stock pot or casserole: two loop handles and a lid."""
    row = table(dims, POT_SIZES)
    R = max(num(row, "diameter", 240.0), 80.0) / 2.0
    H = max(num(row, "height", 200.0), 40.0)
    size = dims.get("_size") or ""
    casserole = "casserole" in size
    finish = _finish(dims, "Red enamel" if casserole else "Stainless steel")
    body, _ = vessel("Pot", _pot_outline(R, H, 14.0), 3.5, finish)
    handles = []
    for side in (1, -1):
        if casserole:
            handles.append(rbox("Lug", side * (R + 14.0), 0.0, H - 18.0,
                                36.0, 60.0, 14.0, 6.0))
        else:
            ring = turn(torus("Handle", 26.0, 4.0, angle=180.0, seg=24),
                        z=-90.0, name="Outward")
            handles.append(turn(move(ring, R - 12.0, 0.0, H - 25.0, "Handle"),
                                z=0.0 if side > 0 else 180.0,
                                name="Side"))
    glass = finish[1] in ("Metal", "Copper") and not casserole
    return group("Casserole" if casserole else "Stock pot", [
        body, paint("Handles", finish[0] if casserole else STEEL,
                    finish[1] if casserole else "Metal", handles),
        _lid(R, H, finish, glass, knob=STEEL if casserole else BLACK)])


def build_frying_pan(dims):
    """A frying pan: flared low wall, flat base, long riveted handle."""
    row = table(dims, FRY_SIZES)
    R = max(num(row, "diameter", 240.0), 80.0) / 2.0
    finish = _finish(dims, "Non-stick black")
    H = R * 0.4
    outer = rounded_base(R * 0.78, 12.0) + bezier(
        (R * 0.78, 12.0), (R * 0.84, H * 0.5), (R * 0.95, H * 0.9),
        (R, H), 6)
    body, _ = vessel("Pan", outer, 3.0, finish)
    L = R * 1.6
    handle = move(turn(rbox("Handle", L / 2 + 10, 0.0, 0.0, L, 30.0, 14.0,
                            6.0), y=-10.0), R * 0.95, 0.0, H - 12.0,
                  "Handle")
    return group("Frying pan", [body, paint("Handle", BLACK, "Matte",
                                            [handle])])


def build_wok(dims):
    """A carbon-steel wok: a round bowl, a long wooden handle and a
    helper handle opposite."""
    D = max(num(dims, "diameter", 350.0), 150.0)
    R = D / 2.0
    H = R * 0.55
    outer = [(0.0, 0.0)] + bezier((R * 0.3, 0.0), (R * 0.8, 4.0),
                                  (R * 0.97, H * 0.6), (R, H), 12)
    body, _ = vessel("Wok", outer, 2.0, ("#2d2b2a", "Metal"))
    L = R * 1.3
    handle = move(turn(group("Handle", [
        capsule("Socket", (0.0, 0.0, 0.0), (60.0, 0.0, 0.0), 9.0, seg=16),
        paint("Wood", "#b07a44", "Plastic", [capsule(
            "Grip", (60.0, 0.0, 0.0), (L, 0.0, 0.0), 14.0, seg=16)])]),
        y=-15.0), R - 6.0, 0.0, H - 14.0, "Handle")
    helper = turn(move(turn(torus("Helper handle", 22.0, 4.0, angle=180.0,
                                  seg=24), z=-90.0), R - 8.0, 0.0,
                       H - 12.0), z=180.0, name="Opposite")
    return group("Wok", [body, paint("Steel", "#2d2b2a", "Metal",
                                     [handle, helper])])


def build_kettle(dims):
    """A stovetop kettle: domed body, spout on +X, arched handle."""
    finish = _finish(dims)
    R, H = 105.0, 150.0
    outer = [(0.0, 0.0), (R - 6.0, 0.0), (R, 6.0), (R, 50.0)] + bezier(
        (R, 50.0), (R, 115.0), (55.0, 140.0), (38.0, H), 10)
    body = paint("Kettle", finish[0], finish[1], [
        revolve("Body", wall(outer, 1.5)[0]),
        spout("Spout", [(R - 15.0, 0.0, 40.0), (R + 25.0, 0.0, 80.0),
                        (R + 45.0, 0.0, 120.0)], [16.0, 10.0, 7.0])])
    lid = revolve("Lid", [(0.0, H - 2.0), (40.0, H - 2.0), (36.0, H + 10.0),
                          (0.0, H + 14.0)])
    handle = move(turn(torus("Handle", 75.0, 9.0, angle=180.0, seg=32),
                       x=90.0), z=H + 20.0, name="Over the top")
    posts = [cyl("Post", 6.0, 32.0, x, 0.0, H - 12.0, seg=16)
             for x in (-75.0, 75.0)]
    return group("Kettle", [
        body, paint("Lid", finish[0], finish[1], [lid]),
        paint("Handle", BLACK, "Plastic", [handle, sphere(
            "Knob", 11.0, 0.0, 0.0, H + 18.0)] + posts)])


def build_baking_tray(dims):
    W = max(num(dims, "width", 380.0), 120.0)
    D = max(num(dims, "depth", 260.0), 80.0)
    H, t = 22.0, 1.5
    finish = _finish(dims, "Non-stick black")
    return paint("Baking tray", finish[0], finish[1], [
        cbox("Floor", 0.0, 0.0, 0.0, W, D, t),
        cbox("Front", 0.0, -D / 2 + t / 2, 0.0, W, t, H),
        cbox("Back", 0.0, D / 2 - t / 2, 0.0, W, t, H),
        cbox("Left", -W / 2 + t / 2, 0.0, 0.0, t, D, H),
        cbox("Right", W / 2 - t / 2, 0.0, 0.0, t, D, H),
    ])


# ── cutlery and utensils ──────────────────────────────────────────────

def _handle(L, w, t=5.0, y0=0.0):
    return rbox("Handle", 0.0, y0 + L / 2, t / 2, w, L, t, 2.2)


def spoon_bowl(name, length, width, depth, t=1.2, y=0.0):
    """A thin spherical cap made oval: *length* along y, *width* across,
    *depth* deep, its lowest point on z = 0, centred at *y*."""
    Rb = width / 2.0
    rho = (Rb * Rb + depth * depth) / (2 * depth)
    n = 10
    top = [(Rb * i / n, rho - math.sqrt(max(rho * rho - (Rb * i / n) ** 2,
                                                0.0)))
           for i in range(n + 1)]
    pts = [(r, z) for r, z in top] + [(r, z + t) for r, z in reversed(top)]
    sc = CadNode("scale", "Oval", dict(x=1.0, y=length / width, z=1.0))
    sc.add(revolve(name, pts, seg=48))
    return move(sc, y=y, name=name)


def knife(L=220.0):
    blade = polygon("Blade", [(-7.0, 0.0), (7.0, 0.0), (9.0, 70.0),
                              (8.0, 110.0), (2.0, 125.0), (-9.0, 118.0),
                              (-9.0, 60.0)])
    return group("Knife", [_handle(95.0, 14.0),
                           move(extrude("Blade", blade, 1.8), y=L - 125.0,
                                z=1.6, name="Blade")])


def fork(L=200.0):
    neck = polygon("Neck", [(-6.0, 0.0), (6.0, 0.0), (12.0, 30.0),
                            (12.0, 40.0), (-12.0, 40.0), (-12.0, 30.0)])
    tines = [(-10.5 + 7.0 * i,) for i in range(4)]
    return group("Fork", [
        _handle(110.0, 13.0),
        move(extrude("Neck", neck, 2.0), y=108.0, z=1.5, name="Neck"),
        loop("Tines", tines, box("Tine", "p[0]", 147.0, 1.5, 3.0, L - 147.0,
                                 2.0)),
    ])


def spoon(L=200.0, bowl=(62.0, 42.0, 8.0)):
    bl, bw, bd = bowl
    return group("Spoon", [_handle(L - bl + 8.0, 12.0),
                           spoon_bowl("Bowl", bl, bw, bd,
                                      y=L - bl / 2.0)])


def _metal(dims):
    return choice(dims, CUTLERY, "Stainless steel")


def build_cutlery(dims):
    """A table knife, fork, dessert spoon and teaspoon side by side."""
    colour = _metal(dims)
    return paint("Cutlery", colour[0], colour[1], [
        move(fork(), -60.0, name="Fork"),
        move(knife(), -20.0, name="Knife"),
        move(spoon(), 20.0, name="Spoon"),
        move(spoon(140.0, (40.0, 28.0, 6.0)), 60.0, name="Teaspoon"),
    ])


def build_chef_knife(dims):
    """A 20 cm chef's knife: curved edge up to the tip, a black handle
    with three steel rivets."""
    blade = polygon("Blade", [(0.0, 0.0), (45.0, 0.0), (44.0, 60.0)] +
                    [(44.0 * math.cos(math.radians(a)) ** 0.6,
                      60.0 + 140.0 * math.sin(math.radians(a)))
                     for a in range(10, 91, 10)])
    handle = rbox("Handle", 20.0, -60.0, 10.0, 26.0, 120.0, 20.0, 8.0)
    return group("Chef's knife", [
        paint("Blade", STEEL, "Metal", [move(extrude("Blade", blade, 2.2),
                                             z=9.0, name="Blade")]),
        paint("Handle", BLACK, "Plastic", [handle]),
        paint("Rivets", STEEL, "Metal", [loop(
            "Rivets", [(-100.0,), (-60.0,), (-20.0,)],
            cyl("Rivet", 3.0, 0.6, 20.0, "p[0]", 19.8, seg=12))]),
    ])


def build_wooden_spoon(dims):
    wood = choice(dims, WOODS, "Beech")
    return paint("Wooden spoon", wood[0], wood[1], [
        capsule("Handle", (0.0, 0.0, 6.0), (0.0, 230.0, 6.0), 6.0, seg=12),
        move(spoon_bowl("Bowl", 70.0, 50.0, 10.0, t=3.0), y=255.0, z=0.0,
             name="Bowl"),
    ])


def build_spatula(dims):
    wood = choice(dims, WOODS, "Beech")
    blade = rbox("Blade", 0.0, 250.0, 2.0, 75.0, 95.0, 3.0, 1.4)
    return group("Spatula", [
        paint("Handle", wood[0], wood[1], [
            capsule("Handle", (0.0, 0.0, 7.0), (0.0, 190.0, 7.0), 7.0,
                    seg=12)]),
        paint("Blade", BLACK, "Matte", [
            blade, capsule("Neck", (0.0, 188.0, 6.0), (0.0, 205.0, 3.0),
                           3.0)]),
        paint("Slots", "#0a0a0b", "Matte", [loop(
            "Slots", [(-22.0,), (-7.0,), (8.0,), (23.0,)],
            box("Slot", "p[0] - 3", 225.0, 3.4, 6.0, 50.0, 0.3))]),
    ])


def build_whisk(dims):
    """A balloon whisk lying down: eight wire loops round its axis (Y),
    each a torus ring stretched along it, and a handle."""
    wires = CadNode("scale", "Stretched", dict(x=1.0, y=2.3, z=1.0))
    wires.add(torus("Wire", 28.0, 0.9, seg=48))
    one = move(wires, y=130.0 + 28.0 * 2.3, name="Past the handle")
    whisk = group("Whisk", [
        paint("Wires", STEEL, "Metal", [loop(
            "8 wires", [(22.5 * i,) for i in range(8)],
            turn(one, y="p[0]", name="Round the axis"))]),
        paint("Handle", STEEL, "Metal", [move(turn(cyl(
            "Handle", 12.0, 130.0, seg=24, r2=8.0), x=-90.0),
            name="Handle")]),
    ])
    return move(whisk, z=30.0, name="Lying down")


def build_rolling_pin(dims):
    wood = choice(dims, WOODS, "Beech")
    L = max(num(dims, "length", 300.0), 100.0)
    return move(turn(paint("Rolling pin", wood[0], wood[1], [
        cyl("Barrel", 30.0, L, z=-L / 2, seg=48),
        cyl("Handle", 12.0, 90.0, z=L / 2, seg=24),
        cyl("Handle", 12.0, 90.0, z=-L / 2 - 90.0, seg=24),
        sphere("End", 14.0, z=L / 2 + 90.0, seg=16),
        sphere("End", 14.0, z=-L / 2 - 90.0, seg=16)]), y=90.0),
        z=30.0, name="Lying down")


def build_chopping_board(dims):
    wood = choice(dims, WOODS, "Walnut")
    W = max(num(dims, "width", 400.0), 100.0)
    D = max(num(dims, "depth", 280.0), 80.0)
    return group("Chopping board", [
        paint("Board", wood[0], wood[1], [rbox("Board", 0.0, 0.0, 12.0, W,
                                               D, 24.0, 10.0)]),
        paint("Handle hole", "#0c0c0d", "Matte", [
            cbox("Hole", W / 2 - 40.0, 0.0, 24.0, 20.0, 70.0, 0.4)]),
    ])


def build_mills(dims):
    """Salt and pepper mills: turned wood, a steel finial."""
    wood = choice(dims, WOODS, "Walnut")

    def mill(name, H):
        k = H / 180.0
        prof = [(0.0, 0.0), (30 * k, 0.0), (32 * k, 8 * k), (26 * k, 30 * k),
                (22 * k, 90 * k), (28 * k, 140 * k), (31 * k, 150 * k),
                (27 * k, 160 * k), (18 * k, H - 10 * k), (0.0, H - 6 * k)]
        return group(name, [
            paint(name, wood[0], wood[1], [revolve(name, prof, seg=48)]),
            paint("Finial", STEEL, "Metal", [sphere("Finial", 7.0 * k,
                                                    z=H - 4 * k, seg=16)])])
    return group("Salt and pepper mills", [
        move(mill("Pepper mill", 200.0), -45.0, name="Pepper"),
        move(mill("Salt mill", 160.0), 45.0, name="Salt")])


# ── settings ──────────────────────────────────────────────────────────

def build_place_setting(dims):
    """One place at table, for a diner at -Y: dinner plate, side plate
    with a butter knife (top left), fork left, knife and spoon right,
    wine and water glasses (top right), a folded napkin."""
    glaze = _glaze(dims)
    steel = CUTLERY["Stainless steel"]
    kids = [plate("Dinner plate", 270.0, 24.0, glaze),
            move(plate("Side plate", 170.0, 16.0, glaze), -210.0, 200.0,
                 name="Side plate")]
    kids.append(paint("Cutlery", steel[0], steel[1], [
        move(fork(), -165.0, -100.0, name="Fork"),
        move(knife(), 160.0, -100.0, name="Knife"),
        move(spoon(), 195.0, -100.0, name="Spoon"),
        move(turn(knife(170.0), z=-90.0), -280.0, 215.0, 17.0,
             "Butter knife"),
    ]))
    kids.append(move(build_stemware({"_size": "Red wine glass",
                                     "_color": "Red wine"}), 175.0, 190.0,
                     name="Wine glass"))
    kids.append(move(build_tumbler({"_size": "Water tumbler",
                                    "_color": "Water"}), 90.0, 235.0,
                     name="Water glass"))
    kids.append(paint("Napkin", "#e8e1d0", "Matte", [
        rbox("Napkin", -235.0, -30.0, 6.0, 110.0, 160.0, 12.0, 3.0)]))
    return group("Place setting", kids)


def build_tea_set(dims):
    """A tea set on a tray: teapot, two cups and saucers, a milk jug and
    a sugar bowl."""
    glaze = dict(_color=dims.get("_color") or "White porcelain")
    tray = paint("Tray", "#6b4226", "Plastic", [
        rbox("Tray", 0.0, 0.0, 6.0, 560.0, 380.0, 12.0, 5.0),
        cbox("Rim front", 0.0, -186.0, 0.0, 560.0, 8.0, 30.0),
        cbox("Rim back", 0.0, 186.0, 0.0, 560.0, 8.0, 30.0),
        cbox("Rim left", -276.0, 0.0, 0.0, 8.0, 380.0, 30.0),
        cbox("Rim right", 276.0, 0.0, 0.0, 8.0, 380.0, 30.0)])
    on = 12.0
    kids = [tray,
            move(build_teapot(glaze), -60.0, 60.0, on, "Teapot"),
            move(build_teacup(glaze), 160.0, -80.0, on, "Cup 1"),
            move(build_teacup(glaze), -180.0, -90.0, on, "Cup 2"),
            move(build_jug(dict(glaze, height=110.0)), 170.0, 100.0, on,
                 "Milk jug"),
            move(build_bowl(dict(glaze, diameter=90.0, height=55.0)), 20.0,
                 -110.0, on, "Sugar bowl")]
    return group("Tea set", kids)


# ── the table of parts ────────────────────────────────────────────────

def _p(label, build, sizes=None, fields=(), colors=None):
    spec = dict(label=label, category=CATEGORY,
                sizes=sizes or {"Standard": {}}, fields=list(fields),
                build=build)
    if colors:
        spec["colors"] = list(colors)
    return spec


DRINK_NAMES = [n for n in DRINKS]
PARTS = {
    "kitchen_plate": _p("Plate", build_plate, PLATE_SIZES, DIAM_H, GLAZES),
    "kitchen_bowl": _p("Bowl", build_bowl, BOWL_SIZES, DIAM_H, GLAZES),
    "kitchen_pasta_bowl": _p("Pasta bowl (wide rim)", build_pasta_bowl,
                             {"Ø280": dict(diameter=280.0)},
                             [("diameter", "Diameter")], GLAZES),
    "kitchen_mug": _p("Mug (with coffee)", build_mug, MUG_SIZES, DIAM_H,
                      GLAZES),
    "kitchen_teacup": _p("Teacup and saucer", build_teacup, colors=GLAZES),
    "kitchen_teapot": _p("Teapot", build_teapot, colors=GLAZES),
    "kitchen_jug": _p("Jug", build_jug, {"Standard": dict(height=180.0),
                                         "Milk jug": dict(height=110.0)},
                      [("height", "Height")], GLAZES),
    "kitchen_cake_stand": _p("Cake stand", build_cake_stand,
                             {"Ø280": dict(diameter=280.0)},
                             [("diameter", "Diameter")], GLAZES),
    "kitchen_egg_cup": _p("Egg cup (with egg)", build_egg_cup,
                          colors=GLAZES),
    "kitchen_stemware": _p("Wine glass / flute", build_stemware,
                           {k: {} for k in STEMWARE}, colors=DRINK_NAMES),
    "kitchen_tumbler": _p("Tumbler / pint glass", build_tumbler, TUMBLERS,
                          DIAM_H, DRINK_NAMES),
    "kitchen_carafe": _p("Carafe", build_carafe,
                         {"1 litre": dict(height=240.0)},
                         [("height", "Height")], DRINK_NAMES),
    "kitchen_wine_bottle": _p("Wine bottle", build_wine_bottle,
                              colors=("Red wine", "White wine", "Rosé")),
    "kitchen_mason_jar": _p("Mason jar (jam)", build_mason_jar,
                            {"500 ml": dict(height=140.0)},
                            [("height", "Height")]),
    "kitchen_saucepan": _p("Saucepan (with lid)", build_saucepan,
                           PAN_SIZES, DIAM_H, COOKWARE),
    "kitchen_stock_pot": _p("Stock pot / casserole", build_stock_pot,
                            POT_SIZES, DIAM_H, COOKWARE),
    "kitchen_frying_pan": _p("Frying pan", build_frying_pan, FRY_SIZES,
                             [("diameter", "Diameter")], COOKWARE),
    "kitchen_wok": _p("Wok", build_wok, {"Ø35 cm": dict(diameter=350.0)},
                      [("diameter", "Diameter")]),
    "kitchen_kettle": _p("Kettle (stovetop)", build_kettle,
                         colors=COOKWARE),
    "kitchen_baking_tray": _p("Baking tray", build_baking_tray,
                              {"Standard": dict(width=380.0, depth=260.0)},
                              [("width", "Width"), ("depth", "Depth")],
                              COOKWARE),
    "kitchen_cutlery": _p("Cutlery set (knife, fork, spoons)",
                          build_cutlery, colors=CUTLERY),
    "kitchen_chef_knife": _p("Chef's knife", build_chef_knife),
    "kitchen_wooden_spoon": _p("Wooden spoon", build_wooden_spoon,
                               colors=WOODS),
    "kitchen_spatula": _p("Spatula (slotted turner)", build_spatula,
                          colors=WOODS),
    "kitchen_whisk": _p("Whisk", build_whisk),
    "kitchen_rolling_pin": _p("Rolling pin", build_rolling_pin,
                              {"Standard": dict(length=300.0)},
                              [("length", "Barrel length")], WOODS),
    "kitchen_chopping_board": _p("Chopping board", build_chopping_board,
                                 {"Standard": dict(width=400.0,
                                                   depth=280.0)},
                                 [("width", "Width"), ("depth", "Depth")],
                                 WOODS),
    "kitchen_mills": _p("Salt and pepper mills", build_mills, colors=WOODS),
    "kitchen_place_setting": _p("Place setting", build_place_setting,
                                colors=GLAZES),
    "kitchen_tea_set": _p("Tea set on a tray", build_tea_set,
                          colors=GLAZES),
}

COUNT_FIELDS = set()

GROUPS = {
    "Tableware": ("Plate", "Bowl", "Pasta bowl", "Mug", "Teacup", "Teapot",
                  "Jug", "Cake stand", "Egg cup"),
    "Glassware & drinks": ("Wine glass", "Tumbler", "Carafe", "Wine bottle",
                           "Mason jar"),
    "Cookware": ("Saucepan", "Stock pot", "Frying pan", "Wok", "Kettle",
                 "Baking tray"),
    "Cutlery & utensils": ("Cutlery", "Chef's knife", "Wooden spoon",
                           "Spatula", "Whisk", "Rolling pin",
                           "Chopping board", "Salt and pepper"),
    "Table settings": ("Place setting", "Tea set"),
}
GROUP_ORDER = list(GROUPS)


def group_of(label: str) -> str:
    for name, starts in GROUPS.items():
        if any(label.startswith(s) for s in starts):
            return name
    return "Tableware"
