"""More musical instruments: strings, winds and brass, hand percussion.

Guitars and the violin family are built lying on their backs (top up,
+Z; neck along +Y; bass strings on -X) from their published sizes —
body length, the three bout widths, scale length. The body outline is
two circular bouts joined by a smooth waist (`body_outline`); frets sit
where the equal-tempered rule puts them (`library_music.fret_position`),
so the fret spacing is right for the scale, and the bridge lands where
the scale says: the neck joins the body at its 12th (classical), 14th
(steel-string) or 16th (electric) fret. A violin's top and back are
arched as a tapering extrusion of the outline; its f-holes follow the
arch (`arch_z`).

A recorder is one revolved profile with its tone holes where a soprano
has them, scaled for alto and tenor; pan pipes are closed pipes cut to
c / 4f for each note of the scale; wind chimes are free-free tubes
(L ∝ 1 / √f) tuned to a pentatonic chord. A trumpet is its real
wrap: leadpipe, main tuning slide, valves, back bow, and a Bessel-horn
bell, every bend a half torus.

No booleans anywhere, so the preview is exact.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .library_music import (
    BRASS, CATEGORY, CHROME, DARK, IVORY, box, capsule, cbox, choice,
    closed_pipe, cyl, ellipsoid, extrude, fret_position, freq, group, loop,
    midi, move, note_name, num, paint, polygon, revolve, sphere, table,
    torus, turn)
from .model import CadNode

HOLE = "#120d0a"
STEEL = ("#d9dadc", "Metal")
NYLON = ("#f2efe6", "Plastic")
ROSEWOOD = "#3b2016"
EBONY = "#151212"


# ── body outlines ─────────────────────────────────────────────────────

def _smooth(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def half_width(u, L, lower, waist, upper):
    """Half the body's width at u (0 = tail, 1 = neck end)."""
    rl, rw, ru = lower / 2.0, waist / 2.0, upper / 2.0
    u0 = min(rl / L, 0.45)
    u1 = max(1.0 - ru / L, 0.55)
    uw = u0 + (u1 - u0) * 0.55
    if u <= u0:
        return rl * math.sqrt(max(0.0, 1.0 - ((u0 - u) / u0) ** 2))
    if u >= u1:
        return ru * math.sqrt(max(0.0, 1.0 - ((u - u1) / (1.0 - u1)) ** 2))
    if u <= uw:
        return rl + (rw - rl) * _smooth((u - u0) / (uw - u0))
    return rw + (ru - rw) * _smooth((u - uw) / (u1 - uw))


def body_outline(L, lower, waist, upper, n=36, cut=0.0, y0=0.0):
    """The (x, y) outline, counter-clockwise, tail at y = *y0*. *cut* > 0
    carves a cutaway that much deep into the treble (+x) upper bout."""
    us = [(1.0 - math.cos(math.pi * i / n)) / 2.0 for i in range(n + 1)]
    right, left = [], []
    for u in us:
        h = half_width(u, L, lower, waist, upper)
        hr = h
        if cut and u > 0.62:
            hr = h * (1.0 - cut * _smooth((u - 0.62) / 0.2))
        right.append((hr, y0 + u * L))
        left.append((-h, y0 + u * L))
    pts = right + left[-2:0:-1]
    return pts


# ── fretted strings ───────────────────────────────────────────────────

GUITARS = {
    "acoustic": dict(name="Acoustic guitar", L=508.0, lower=397.0,
                     waist=275.0, upper=292.0, depth=115.0, scale=645.0,
                     joint=14, frets=20, strings=6, nut=43.0, heel=56.0,
                     saddle=54.0, bridge_h=12.0, hole=50.0,
                     strings_look=STEEL, kind="acoustic"),
    "classical": dict(name="Classical guitar", L=485.0, lower=365.0,
                      waist=240.0, upper=280.0, depth=100.0, scale=650.0,
                      joint=12, frets=19, strings=6, nut=52.0, heel=62.0,
                      saddle=58.0, bridge_h=12.0, hole=43.0,
                      strings_look=NYLON, kind="classical"),
    "electric": dict(name="Electric guitar", L=440.0, lower=330.0,
                     waist=270.0, upper=250.0, depth=48.0, scale=628.0,
                     joint=16, frets=22, strings=6, nut=43.0, heel=56.0,
                     saddle=52.0, bridge_h=14.0, cut=0.62,
                     strings_look=STEEL, kind="electric"),
    "bass": dict(name="Bass guitar", L=470.0, lower=340.0, waist=260.0,
                 upper=230.0, depth=45.0, scale=864.0, joint=16, frets=20,
                 strings=4, nut=42.0, heel=62.0, saddle=60.0,
                 bridge_h=14.0, cut=0.45, strings_look=STEEL,
                 kind="electric"),
}
UKULELES = {
    "Soprano": dict(name="Ukulele", L=240.0, lower=160.0, waist=125.0,
                    upper=135.0, depth=62.0, scale=346.0, joint=12,
                    frets=12, strings=4, nut=35.0, heel=40.0, saddle=40.0,
                    bridge_h=9.0, hole=26.0, strings_look=NYLON,
                    kind="classical"),
    "Concert": dict(name="Ukulele", L=280.0, lower=180.0, waist=140.0,
                    upper=150.0, depth=68.0, scale=381.0, joint=14,
                    frets=18, strings=4, nut=36.0, heel=42.0, saddle=42.0,
                    bridge_h=9.0, hole=28.0, strings_look=NYLON,
                    kind="classical"),
    "Tenor": dict(name="Ukulele", L=305.0, lower=205.0, waist=160.0,
                  upper=170.0, depth=75.0, scale=432.0, joint=14,
                  frets=18, strings=4, nut=36.0, heel=44.0, saddle=44.0,
                  bridge_h=9.0, hole=30.0, strings_look=NYLON,
                  kind="classical"),
}
WOODS = {"Natural spruce": ("#e3c38c", "#8a4a26"),
         "Cedar": ("#b8763f", "#6b3a1f"),
         "Sunburst": ("#b8561f", "#4a2412"),
         "Black": ("#18181a", "#18181a"),
         "Koa": ("#b27435", "#8a5327")}
PAINTS = {"Cherry red": ("#8d1620", "Plastic"),
          "Black": ("#141416", "Plastic"),
          "Gold top": ("#c9a650", "Metal"),
          "Olympic white": ("#ece8dc", "Plastic"),
          "Sunburst": ("#9a4a1c", "Plastic"),
          "Sea-foam green": ("#8fcbb5", "Plastic")}


def _fretboard(cfg, y_nut, top, joint_y):
    """Neck, fretboard, frets, markers, headstock and tuners."""
    S = cfg["scale"]
    nut, heel = cfg["nut"], cfg["heel"]
    frets = cfg["frets"]
    y_end = y_nut - fret_position(S, frets) - 8.0

    def half(y):
        t = (y_nut - y) / max(y_nut - joint_y, 1.0)
        return (nut + (heel - nut) * t) / 2.0

    fb_t = 6.0
    D = top
    neck = polygon("Neck", [(-half(joint_y - 20), joint_y - 20),
                            (half(joint_y - 20), joint_y - 20),
                            (nut / 2, y_nut), (-nut / 2, y_nut)])
    board = polygon("Fretboard", [(-half(y_end), y_end),
                                  (half(y_end), y_end),
                                  (nut / 2, y_nut), (-nut / 2, y_nut)])
    fret_rows = [(y_nut - fret_position(S, n), half(
        y_nut - fret_position(S, n)) - 0.5) for n in range(1, frets + 1)]
    dots = []
    for n in (3, 5, 7, 9, 12, 15, 17, 19, 21):
        if n > frets:
            continue
        y = y_nut - (fret_position(S, n - 1) + fret_position(S, n)) / 2
        for x in ((-half(y) / 2, half(y) / 2) if n == 12 else (0.0,)):
            dots.append((x, y))
    head_len = 60.0 + 25.0 * cfg["strings"] / 2
    per_side = (cfg["strings"] + 1) // 2
    head = polygon("Headstock", [(-nut / 2, y_nut), (nut / 2, y_nut),
                                 (nut / 2 + 18.0, y_nut + head_len),
                                 (-nut / 2 - 18.0, y_nut + head_len)])
    wood = cfg.get("neck_colour", "#9a5b2c")
    kids = [
        paint("Neck", wood, "Plastic", [
            extrude("Neck", neck, 20.0, D - 20.0),
            extrude("Headstock", head, 14.0, D - 16.0)]),
        paint("Fretboard", ROSEWOOD, "Plastic", [
            extrude("Fretboard", board, fb_t, D)]),
        paint("Frets", "#d6d2c8", "Metal", [loop(
            f"{frets} frets", fret_rows,
            box("Fret", "-p[1]", "p[0] - 1", D + fb_t, "2 * p[1]", 2.0,
                1.2))]),
        paint("Nut", IVORY, "Plastic", [
            cbox("Nut", 0.0, y_nut + 2.5, D, nut, 5.0, fb_t + 3.0)]),
    ]
    if dots:
        kids.append(paint("Markers", IVORY, "Plastic", [loop(
            "Fret markers", dots, cyl("Dot", 3.5, 0.3, "p[0]", "p[1]",
                                      D + fb_t, seg=16))]))
    pegs = []
    for i in range(per_side):
        y = y_nut + 30.0 + i * (head_len - 40.0) / max(per_side - 1, 1)
        for side in (-1, 1):
            if side == 1 and per_side * 2 > cfg["strings"] and i == per_side - 1:
                continue
            w = nut / 2 + 18.0 * (y - y_nut) / head_len
            pegs.append(capsule("Tuner post", (side * (w - 6), y, D - 9.0),
                                (side * (w + 16), y, D - 9.0), 3.0))
            pegs.append(ellipsoid("Tuner key", 6.0, 9.0, 4.0,
                                  side * (w + 20), y, D - 9.0, seg=16))
    kids.append(paint("Tuners", CHROME, "Metal", pegs))
    if cfg["kind"] == "classical":
        kids.append(paint("Head slots", HOLE, "Matte", [
            cbox(f"Slot {s}", s * 11.0, y_nut + head_len / 2 + 5, D - 2.0,
                 12.0, head_len - 45.0, 0.4) for s in (-1, 1)]))
    return group("Neck and head", kids), D + fb_t


def _strings(cfg, y_saddle, z_saddle, y_nut, z_nut, name="Strings"):
    n = cfg["strings"]
    spread_n = cfg["nut"] - 7.0
    spread_s = cfg["saddle"]
    colour, material = cfg["strings_look"]
    kids = []
    for i in range(n):
        f = i / max(n - 1, 1) - 0.5
        r = 0.55 - 0.3 * i / max(n - 1, 1) if n > 4 else 0.9 - 0.3 * i / 3
        kids.append(capsule(f"String {i + 1}",
                            (f * spread_s, y_saddle, z_saddle),
                            (f * spread_n, y_nut, z_nut), r, seg=6))
    return paint(name, colour, material, kids)


def guitar(cfg, dims, colour_pick):
    """Any fretted instrument from a GUITARS-style *cfg*."""
    L, S, D = cfg["L"], cfg["scale"], cfg["depth"]
    joint_y = L
    y_nut = joint_y + fret_position(S, cfg["joint"])
    y_saddle = y_nut - S
    outline = body_outline(L, cfg["lower"], cfg["waist"], cfg["upper"],
                           cut=cfg.get("cut", 0.0))
    kids = []
    if cfg["kind"] == "electric":
        colour, material = colour_pick
        kids.append(paint("Body", colour, material, [
            extrude("Body", polygon("Body outline", outline), D)]))
        neck_cfg = dict(cfg, neck_colour="#c9955a")
    else:
        top_c, side_c = colour_pick
        kids.append(paint("Back and sides", side_c, "Plastic", [
            extrude("Sides", polygon("Body outline", outline), D - 3.0)]))
        kids.append(paint("Top", top_c, "Plastic", [
            extrude("Top", polygon("Top outline", outline), 3.0, D - 3.0)]))
        neck_cfg = dict(cfg, neck_colour=side_c if side_c != "#18181a"
                        else "#3a2a20")
    neck, fb_top = _fretboard(neck_cfg, y_nut, D, joint_y)
    kids.append(neck)
    if cfg["kind"] == "electric":
        z_s = D + cfg["bridge_h"]
        n_pick = 2 if cfg["strings"] == 6 else 1
        pickups = [cbox(f"Pickup {i + 1}", 0.0,
                        y_saddle + 40.0 + i * 95.0, D, 72.0, 38.0, 8.0)
                   for i in range(n_pick)]
        kids.append(paint("Pickups", "#161618", "Plastic", pickups))
        kids.append(paint("Hardware", CHROME, "Metal", [
            cbox("Bridge", 0.0, y_saddle, D, cfg["saddle"] + 30.0, 12.0,
                 cfg["bridge_h"]),
            cbox("Tailpiece", 0.0, y_saddle - 45.0, D, cfg["saddle"] + 30,
                 14.0, 10.0),
            capsule("Switch", (cfg["upper"] * 0.28, L * 0.82, D),
                    (cfg["upper"] * 0.28, L * 0.82, D + 18.0), 2.5)]))
        knobs = [cyl(f"Knob {i + 1}", 9.0, 16.0,
                     cfg["lower"] * 0.26 + (i % 2) * 34.0,
                     L * 0.2 + (i // 2) * 38.0, D, seg=24)
                 for i in range(4 if n_pick == 2 else 2)]
        kids.append(paint("Knobs", "#d8b760", "Metal", knobs))
    else:
        z_s = D + cfg["bridge_h"]
        hole_r = cfg["hole"]
        fb_end = y_nut - fret_position(S, cfg["frets"]) - 8.0
        hole_y = min(fb_end - hole_r - 12.0, L * 0.72)
        kids.append(paint("Rosette", "#3b2618", "Plastic", [
            cyl("Rosette", hole_r + 12.0, 0.3, 0.0, hole_y, D, seg=64)]))
        kids.append(paint("Sound hole", HOLE, "Matte", [
            cyl("Sound hole", hole_r, 0.5, 0.0, hole_y, D, seg=64)]))
        bridge = [cbox("Bridge", 0.0, y_saddle - 8.0, D,
                       cfg["saddle"] * 2.8, 28.0, 8.0)]
        kids.append(paint("Bridge", ROSEWOOD, "Plastic", bridge))
        kids.append(paint("Saddle", IVORY, "Plastic", [
            cbox("Saddle", 0.0, y_saddle, D + 8.0, cfg["saddle"] + 16.0,
                 3.0, cfg["bridge_h"] - 8.0)]))
        if cfg["kind"] == "acoustic":
            guard = [(hole_r * 0.6 + 60 * math.cos(a) * 0.8,
                      hole_y - hole_r * 0.4 + 60 * math.sin(a) * 1.2)
                     for a in [math.radians(-100 + 9 * i)
                               for i in range(24)]]
            kids.append(paint("Pickguard", "#4a1e10", "Plastic", [
                extrude("Pickguard", polygon("Pickguard", guard), 0.4, D)]))
    kids.append(_strings(cfg, y_saddle, z_s, y_nut, fb_top + 1.2))
    return group(cfg["name"], kids)


def _gtr_part(key):
    cfg = GUITARS[key]

    def build(dims):
        if cfg["kind"] == "electric":
            pick = choice(dims, PAINTS, "Sunburst" if key == "bass"
                          else "Cherry red")
        else:
            pick = choice(dims, WOODS, "Natural spruce")
        return guitar(cfg, dims, pick)
    return build


def build_ukulele(dims):
    size = dims.get("_size") or "Soprano"
    cfg = UKULELES.get(size, UKULELES["Soprano"])
    return guitar(cfg, dims, choice(dims, WOODS, "Koa"))


# ── the violin family ─────────────────────────────────────────────────

BOWED = {
    "Violin (4/4)": dict(name="Violin", L=356.0, upper=168.0, waist=111.0,
                         lower=208.0, rib=31.0, arch=15.0, string=328.0,
                         stop=195.0, fb=270.0, nut=24.0, bridge_w=42.0,
                         bridge_h=33.0, endpin=False),
    "Violin (3/4)": dict(name="Violin", L=335.0, upper=158.0, waist=104.0,
                         lower=195.0, rib=29.0, arch=14.0, string=307.0,
                         stop=183.0, fb=254.0, nut=23.0, bridge_w=40.0,
                         bridge_h=31.0, endpin=False),
    "Viola (16\")": dict(name="Viola", L=406.0, upper=190.0, waist=125.0,
                         lower=236.0, rib=38.0, arch=17.0, string=370.0,
                         stop=220.0, fb=300.0, nut=25.0, bridge_w=46.0,
                         bridge_h=36.0, endpin=False),
    "Cello (4/4)": dict(name="Cello", L=755.0, upper=345.0, waist=235.0,
                        lower=440.0, rib=120.0, arch=25.0, string=690.0,
                        stop=400.0, fb=580.0, nut=31.0, bridge_w=90.0,
                        bridge_h=85.0, endpin=True),
}
VARNISH = {"Amber": "#b8631f", "Red-brown": "#7e2a15",
           "Golden": "#c98a2e", "Dark brown": "#4a2412"}
_ARCH_SCALE = 0.72


def _arch_ring(phi):
    """(scale, height fraction) of the arch at angle *phi* (degrees): a
    quarter ellipse from the edge (1, 0) up to the plateau (0.72, 1)."""
    a = math.radians(phi)
    return _ARCH_SCALE + (1.0 - _ARCH_SCALE) * math.cos(a), math.sin(a)


def arched_body(outline, rib, arch, steps=4):
    """One closed polyhedron through scaled copies of the (centred, CCW)
    *outline*: the back arched down to z = 0, straight ribs, the top
    arched up — rings, not stacked solids, so no hidden face lies on
    another. Faces clockwise from outside, as OpenSCAD wants."""
    rings = []
    for j in range(steps + 1):                       # back, plateau up
        sc, f = _arch_ring(90.0 - 90.0 * j / steps)
        rings.append((sc, arch * (1.0 - f)))
    rings.append((1.0, arch + rib))
    for j in range(1, steps + 1):                    # top, edge up
        sc, f = _arch_ring(90.0 * j / steps)
        rings.append((sc, arch + rib + arch * f))
    n = len(outline)
    points = [[round(sc * x, 3), round(sc * y, 3), round(z, 3)]
              for sc, z in rings for x, y in outline]
    bottom, top = len(points), len(points) + 1
    points += [[0.0, 0.0, 0.0], [0.0, 0.0, round(rings[-1][1], 3)]]
    faces = []
    for k in range(len(rings) - 1):
        for i in range(n):
            a, b = k * n + i, k * n + (i + 1) % n
            faces.append([a, a + n, b + n, b])
    last = (len(rings) - 1) * n
    for i in range(n):
        faces.append([bottom, i, (i + 1) % n])
        faces.append([top, last + (i + 1) % n, last + i])
    return CadNode("polyhedron", "Arched body", dict(points=points,
                                                    faces=faces))


def arch_z(x, y, cfg, base):
    """Height of the arched top over (x, y): which scaled copy of the
    outline the point lies on says where on the arch it is."""
    L = cfg["L"]
    yc = L / 2.0

    def inside(s):
        u = (yc + (y - yc) / s) / L
        return 0.0 <= u <= 1.0 and abs(x) / s <= half_width(
            u, L, cfg["lower"], cfg["waist"], cfg["upper"])
    lo, hi = _ARCH_SCALE, 1.0
    if inside(lo):
        return base + cfg["arch"]
    for _ in range(24):
        mid = (lo + hi) / 2.0
        if inside(mid):
            hi = mid
        else:
            lo = mid
    c = min(max((hi - _ARCH_SCALE) / (1.0 - _ARCH_SCALE), 0.0), 1.0)
    return base + cfg["arch"] * math.sqrt(1.0 - c * c)


def build_bowed(dims):
    """A violin, viola or cello on its back: arched back and top, ribs,
    f-holes following the arch, neck, raised fingerboard, pegbox and
    scroll, bridge, tailpiece, chinrest (or endpin) and four strings."""
    size = dims.get("_size") or next(iter(BOWED))
    cfg = BOWED.get(size, BOWED["Violin (4/4)"])
    varnish = VARNISH.get(dims.get("_color") or "Amber", VARNISH["Amber"])
    L, rib, arch = cfg["L"], cfg["rib"], cfg["arch"]
    k = L / 356.0
    centred = body_outline(L, cfg["lower"], cfg["waist"], cfg["upper"],
                           y0=-L / 2.0)
    base = arch + rib                                  # top of the ribs
    top_z = base + arch
    body = move(arched_body(centred, rib, arch), y=L / 2.0,
                name="Tail at y = 0")
    y_bridge = L - cfg["stop"]
    y_nut = y_bridge + cfg["string"]
    z_nut = base + 20.0 * k
    z_fb_end = top_z + 18.0 * k
    y_fb_end = y_nut - cfg["fb"]
    kids = [paint("Body", varnish, "Plastic", [body])]

    def slab(name, y, w, z0, z1, d=4.0):
        return cbox(name, 0.0, y, z0, w, d, z1 - z0)
    neck = CadNode("hull", "Neck")
    neck.add(slab("Neck root", L - 2.0, cfg["nut"] + 10.0, arch, z_nut - 6))
    neck.add(slab("Neck at the nut", y_nut, cfg["nut"],
                  z_nut - 6 - 14 * k, z_nut - 6))
    pegbox = cbox("Pegbox", 0.0, y_nut + 40.0 * k, z_nut - 6 - 26 * k,
                  cfg["nut"] - 2.0, 80.0 * k, 26.0 * k)
    scroll = move(turn(cyl("Scroll", 19.0 * k, 36.0 * k, z=-18.0 * k,
                           seg=32), y=90.0), 0.0, y_nut + 95.0 * k,
                  z_nut - 18.0 * k, "Scroll")
    kids.append(paint("Neck and scroll", varnish, "Plastic",
                      [neck, pegbox, scroll]))
    board = CadNode("hull", "Fingerboard")
    board.add(slab("At the nut", y_nut - 2.0, cfg["nut"], z_nut - 6,
                   z_nut))
    board.add(slab("Over the top", y_fb_end + 2.0, cfg["bridge_w"] * 0.95,
                   z_fb_end - 6, z_fb_end))
    tail = CadNode("hull", "Tailpiece")
    tail.add(slab("Tail end", 28.0 * k, 18.0 * k, base + 2.0,
                  base + 6.0))
    tail.add(slab("Bridge end", 125.0 * k, cfg["bridge_w"] * 0.95,
                  top_z + 4.0, top_z + 9.0))
    ebony = [board, tail]
    for i, side in enumerate((-1, 1, -1, 1)):
        y = y_nut + (18.0 + 16.0 * i) * k
        ebony.append(capsule("Peg", (-side * 8 * k, y, z_nut - 16 * k),
                             (side * 30 * k, y, z_nut - 16 * k), 3.5 * k))
        ebony.append(ellipsoid("Peg head", 3.5 * k, 9 * k, 11 * k,
                               side * 34 * k, y, z_nut - 16 * k, seg=16))
    if cfg["endpin"]:
        ebony.append(capsule("Endpin", (0.0, 5.0, base - rib / 2),
                             (0.0, -350.0, base - rib / 2), 5.0))
    else:
        cx, cy = -30.0 * k, 34.0 * k
        ebony.append(ellipsoid("Chinrest", 48.0 * k, 26.0 * k, 7.0 * k, cx,
                               cy, arch_z(cx, cy, cfg, base) + 7.0 * k,
                               seg=24))
    kids.append(paint("Ebony fittings", EBONY, "Plastic", ebony))
    kids.append(paint("Bridge", "#e2c69b", "Plastic", [
        cbox("Bridge", 0.0, y_bridge, top_z, cfg["bridge_w"], 4.0 * k,
             cfg["bridge_h"])]))
    fholes = []
    for side in (-1, 1):
        x0 = side * cfg["waist"] * 0.34
        pts = [(x0 + side * 5 * k, y_bridge + 36 * k),
               (x0, y_bridge + 12 * k), (x0 - side * 2 * k, y_bridge - 12 * k),
               (x0 + side * 4 * k, y_bridge - 36 * k)]
        pts3 = [(x, y, arch_z(x, y, cfg, base) + 0.3) for x, y in pts]
        for a, b in zip(pts3, pts3[1:]):
            fholes.append(capsule("f-hole", a, b, 1.4 * k, seg=6))
        for x, y, z in (pts3[0], pts3[-1]):
            fholes.append(sphere("f-hole eye", 2.6 * k, x, y, z - 1.0,
                                 seg=12))
    kids.append(paint("f-holes", HOLE, "Matte", fholes))
    strings = []
    for i in range(4):
        f = i / 3.0 - 0.5
        at_bridge = (f * cfg["bridge_w"] * 0.8, y_bridge,
                     top_z + cfg["bridge_h"])
        strings.append(capsule(f"String {i + 1}", at_bridge,
                               (f * cfg["nut"] * 0.7, y_nut, z_nut + 0.8),
                               0.45 * k, seg=6))
        strings.append(capsule(f"String {i + 1} (after)", at_bridge,
                               (f * cfg["bridge_w"] * 0.7, 125.0 * k,
                                top_z + 9.0), 0.45 * k, seg=6))
    kids.append(paint("Strings", "#c9c9cc", "Metal", strings))
    return group(cfg["name"], kids)


# ── winds and brass ───────────────────────────────────────────────────

RECORDERS = {"Soprano (C5)": dict(length=330.0, diameter=25.0),
             "Alto (F4)": dict(length=480.0, diameter=33.0),
             "Tenor (C4)": dict(length=640.0, diameter=40.0)}
RECORDER_WOODS = {"Pearwood": ("#c48d57", "Plastic"),
                  "Rosewood": ("#5a2a18", "Plastic"),
                  "Maple": ("#e3c99a", "Plastic"),
                  "Ivory ABS": ("#efe6cf", "Plastic"),
                  "Black ABS": ("#232326", "Plastic")}


def recorder_profile(L, R):
    """(r, z) outline, foot at z = 0, beak at z = L."""
    return [(0.0, 0.0), (0.8 * R, 0.0), (0.86 * R, 0.03 * L),
            (0.86 * R, 0.17 * L), (0.78 * R, 0.21 * L), (0.74 * R, 0.22 * L),
            (0.86 * R, 0.72 * L), (R, 0.735 * L), (R, 0.9 * L),
            (0.8 * R, 0.975 * L), (0.3 * R, L), (0.0, L)]


def _radius_at(profile, z):
    for (r0, z0), (r1, z1) in zip(profile, profile[1:]):
        if z0 <= z <= z1 and z1 > z0:
            return r0 + (r1 - r0) * (z - z0) / (z1 - z0)
    return profile[-1][0]


def build_recorder(dims):
    """A recorder lying along +Y (foot at y = 0), its holes up."""
    row = table(dims, RECORDERS)
    L = max(num(row, "length", 330.0), 150.0)
    R = max(num(row, "diameter", 25.0), 8.0) / 2.0
    colour, material = choice(dims, RECORDER_WOODS, "Pearwood")
    prof = recorder_profile(L, R)
    body = move(turn(revolve("Recorder", prof, seg=48), x=-90.0,
                     name="Lying along Y"), z=R, name="On the table")
    holes = []
    # soprano positions from the foot, as fractions of the length
    for i, (f, r, double) in enumerate((
            (0.69, 0.16, False), (0.63, 0.17, False), (0.57, 0.16, False),
            (0.48, 0.16, False), (0.42, 0.17, False), (0.35, 0.1, True),
            (0.275, 0.1, True))):
        y = f * L
        zs = R + _radius_at(prof, y) - 0.8
        for x in ((-0.2 * R, 0.2 * R) if double else (0.0,)):
            holes.append(cyl(f"Hole {i + 1}", r * R, 1.2, x, y, zs,
                             seg=12))
    yw = 0.875 * L
    holes.append(cbox("Window", 0.0, yw, 2 * R - 0.8, 0.45 * R, 0.035 * L,
                      1.2))
    return group("Recorder", [paint("Body", colour, material, [body]),
                              paint("Holes", HOLE, "Matte", holes)])


FLUTE_FINISH = {"Silver": ("#d3d6da", "Metal"),
                "Gold": ("#d4b25a", "Metal"),
                "Rose gold": ("#d49a7e", "Metal")}


def build_flute(dims):
    """A concert flute lying along +Y: body, head joint with lip plate
    and crown, a row of key cups and the rod that carries them."""
    L = max(num(dims, "length", 670.0), 300.0)
    R = 9.5
    colour, material = choice(dims, FLUTE_FINISH, "Silver")
    tube = move(turn(cyl("Tube", R, L, seg=32), x=-90.0), z=R + 1.5,
                name="Lying along Y")
    crown = move(turn(cyl("Crown", R + 1.5, 14.0, seg=32), x=-90.0),
                 0.0, L, R + 1.5, "Crown")
    lip = ellipsoid("Lip plate", 13.0, 17.0, 2.5, 0.0, L - 95.0,
                    2 * R + 1.5, seg=24)
    keys = [(L * 0.08 + i * (L * 0.62) / 12.0, 6.5 if i % 3 else 7.5)
            for i in range(13)]
    metal = [tube, crown, lip,
             loop("Key cups", keys, cyl("Key", "p[1]", 3.0, 0.0, "p[0]",
                                        2 * R + 0.5, seg=24)),
             capsule("Key rod", (R + 2.0, L * 0.05, R + 5.5),
                     (R + 2.0, L * 0.72, R + 5.5), 1.5)]
    return group("Flute", [
        paint("Body", colour, material, metal),
        paint("Embouchure", HOLE, "Matte", [
            ellipsoid("Embouchure hole", 5.0, 6.0, 1.0, 0.0, L - 95.0,
                      2 * R + 3.8, seg=16)])])


BRASS_FINISH = {"Lacquered brass": ("#d8ae4b", "Metal"),
                "Silver plate": ("#d0d3d7", "Metal"),
                "Gold plate": ("#e0bb58", "Metal")}


def _bell_profile(length, throat, mouth, wall=1.2, n=20):
    """A Bessel horn r = b / (x0 - x)^0.7 from *throat* to *mouth*, as a
    hollow revolved profile along +Z (mouth at z = length)."""
    k = 0.7
    # r(z) = A / (z1 - z)^k with r(0) = throat, r(length) = mouth
    ratio = (mouth / throat) ** (1.0 / k)
    z1 = length * ratio / (ratio - 1.0)
    A = throat * z1 ** k
    outer = [(A / (z1 - length * i / n) ** k, length * i / n)
             for i in range(n + 1)]
    inner = [(max(r - wall, 0.0), z) for r, z in reversed(outer)
             if z > length * 0.35]
    return outer + [(mouth + 2.0, length), (mouth + 2.0, length + 2.5),
                    (mouth - wall, length + 2.5)] + inner + \
        [(0.0, inner[-1][1])] + [(0.0, 0.0)]


def build_trumpet(dims):
    """A B-flat trumpet in its real wrap, bell toward -Y, valves up:
    mouthpiece and leadpipe, the main tuning slide's U at the front,
    three valves, the back bow and the bell."""
    colour, material = choice(dims, BRASS_FINISH, "Lacquered brass")
    r = 5.8
    zt, zm, zb = 90.0, 45.0, 0.0          # leadpipe, middle, bell levels
    xl = 26.0                             # leadpipe side of the valves
    metal = [
        capsule("Leadpipe", (xl, 250.0, zt), (xl, -160.0, zt), r),
        capsule("Slide return", (xl, -160.0, zm), (xl, -40.0, zm), r),
        capsule("Into the valves", (xl, -40.0, zm), (0.0, -40.0, zm), r),
        capsule("Valves to the back bow", (0.0, -40.0, zm),
                (0.0, 200.0, zm), r),
        capsule("Bell tube", (0.0, 200.0, zb), (0.0, -60.0, zb), r),
        # bends: half tori stood in the YZ plane
        move(turn(torus("Back bow", 22.5, r, angle=180.0, seg=24), y=-90.0),
             0.0, 200.0, 22.5, "Back bow"),
        move(turn(turn(torus("Main slide", 22.5, r, angle=180.0, seg=24),
                       z=180.0), y=-90.0), xl, -160.0, 67.5,
             "Main tuning slide"),
        move(turn(revolve("Mouthpiece", [
            (0.0, 0.0), (4.5, 0.0), (5.5, 55.0), (13.0, 78.0), (13.5, 86.0),
            (9.0, 86.0), (4.0, 70.0), (0.0, 70.0)], seg=32), x=-90.0),
             xl, 250.0, zt, "Mouthpiece"),
        move(turn(revolve("Bell", _bell_profile(260.0, r, 62.0), seg=64),
                  x=90.0), 0.0, -60.0, zb, "Bell"),
    ]
    for i, y in enumerate((-40.0, -70.0, -100.0)):
        metal.append(cyl(f"Valve {i + 1}", 11.5, 95.0, 0.0, y, 12.0,
                         seg=32))
        metal.append(cyl(f"Valve cap {i + 1}", 12.5, 6.0, 0.0, y, 107.0,
                         seg=32))
        metal.append(cyl(f"Valve stem {i + 1}", 2.5, 16.0, 0.0, y, 113.0,
                         seg=12))
    buttons = [cyl(f"Finger button {i + 1}", 8.0, 4.0, 0.0, y, 129.0,
                   seg=24) for i, y in enumerate((-40.0, -70.0, -100.0))]
    return move(group("Trumpet", [
        paint("Brass", colour, material, metal),
        paint("Finger buttons", "#f1ece0", "Plastic", buttons)]),
        z=64.0, name="Bell clear of the floor")


PAN_SIZES = {"8 pipes (C5 major)": dict(pipes=8, start="C5"),
             "13 pipes (G4 major)": dict(pipes=13, start="G4"),
             "20 pipes (nai, B3–G6)": dict(pipes=20, start="B3")}
PAN_LOOKS = {"Bamboo": ("#cfb277", "Plastic"),
             "Dark bamboo": ("#8a6a3a", "Plastic"),
             "Wood": ("#a8683a", "Plastic")}


def pan_notes(start, count):
    """The notes of a major scale (G major for a nai starting on B)."""
    root = midi(start)
    tonic = root if start[0] != "B" else root - 4       # B3 -> G major
    steps = [0, 2, 4, 5, 7, 9, 11]
    notes, m = [], tonic
    octave = 0
    while len(notes) < count:
        for s in steps:
            n = tonic + 12 * octave + s
            if n >= root and len(notes) < count:
                notes.append(n)
        octave += 1
    return notes


def build_pan_pipes(dims):
    """Closed pipes side by side, each c / 4f long for its note, the
    tops level, bound by two cords."""
    row = table(dims, PAN_SIZES)
    notes = pan_notes(row.get("start", "C5"), int(num(row, "pipes", 8)))
    colour, material = choice(dims, PAN_LOOKS, "Bamboo")
    wall = 1.5
    rows, pitch_x, x = [], 0.0, 0.0
    for m in notes:
        t = (m - notes[0]) / max(notes[-1] - notes[0], 1)
        r_in = 8.5 - 4.0 * t
        L = closed_pipe(m, r_in) + wall
        rows.append((x, L, r_in + wall, r_in))
        x += 2 * (r_in + wall) + 0.6
    top = max(L for _x, L, _ro, _ri in rows)
    pipes = [(x, top - L, L, ro) for x, L, ro, _ri in rows]
    bores = [(x, top, ri) for x, _L, _ro, ri in rows]
    cords = []
    for depth in (18.0, 55.0):
        reach = [p for p in pipes if p[2] > depth + 10.0]
        if not reach:
            continue
        x1 = reach[-1][0] + reach[-1][3]
        for side in (-1, 1):
            cords.append(box("Cord", -rows[0][2], side * (rows[0][2] + 0.8)
                             - 1.2, top - depth, x1 + rows[0][2], 2.4, 5.0))
    return group("Pan pipes", [
        paint("Pipes", colour, material, [loop(
            f"{len(notes)} pipes {note_name(notes[0])}–"
            f"{note_name(notes[-1])}", pipes,
            cyl("Pipe", "p[3]", "p[2]", "p[0]", 0.0, "p[1]", seg=24))]),
        paint("Bores", HOLE, "Matte", [loop(
            "Open ends", bores, cyl("Bore", "p[2]", 0.4, "p[0]", 0.0,
                                    "p[1]", seg=24))]),
        paint("Cords", "#6a2018", "Matte", cords),
    ])


def build_harmonica(dims):
    """A 10-hole diatonic harmonica: wooden comb between chrome covers,
    the holes along the front."""
    W, D, H = 102.0, 27.0, 20.0
    colour, material = choice(dims, {"Pear wood": ("#c9965a", "Plastic"),
                                     "Black": ("#1c1c1f", "Plastic")},
                              "Pear wood")
    covers = CadNode("hull", "Cover")
    covers.add(cbox("Cover front", 0.0, 0.0, H - 6.0, W, D - 4.0, 6.0))
    covers.add(cbox("Cover crown", 0.0, 3.0, H - 1.0, W - 16.0, D - 12.0,
                    1.0))
    lower = CadNode("hull", "Lower cover")
    lower.add(cbox("Cover front", 0.0, 0.0, 0.0, W, D - 4.0, 6.0))
    lower.add(cbox("Cover crown", 0.0, 3.0, -1.0, W - 16.0, D - 12.0, 1.0))
    holes = [(-W / 2 + 7.0 + i * 9.8,) for i in range(10)]
    return move(group("Harmonica", [
        paint("Comb", colour, material, [cbox("Comb", 0.0, 0.0, 6.0,
                                              W - 6.0, D, H - 12.0)]),
        paint("Covers", CHROME, "Metal", [covers, lower]),
        paint("Holes", HOLE, "Matte", [loop(
            "10 holes", holes, box("Hole", "p[0]", -D / 2 - 0.3, 7.5, 5.5,
                                   1.0, H - 15.0))]),
    ]), z=1.0, name="On the table")


# ── hand percussion ───────────────────────────────────────────────────

def build_triangle(dims):
    """A steel triangle hanging from its clip, and its beater."""
    side = max(num(dims, "side", 180.0), 60.0)
    r = 5.0
    h = side * math.sqrt(3) / 2
    a, b, c = (-side / 2, 0.0, r), (side / 2, 0.0, r), (0.0, 0.0, h + r)
    gap = tuple(a[i] + (c[i] - a[i]) * 0.12 for i in range(3))
    tri = [capsule("Base", a, b, r), capsule("Right side", b, c, r),
           capsule("Left side", c, gap, r)]
    return group("Triangle", [
        paint("Triangle", "#c8ccd2", "Metal", tri),
        paint("Clip", "#8b1e24", "Matte", [
            capsule("Cord", c, (0.0, 0.0, h + 60.0), 1.2),
            cbox("Clip", 0.0, 0.0, h + 60.0, 14.0, 10.0, 45.0)]),
        paint("Beater", "#c8ccd2", "Metal", [
            capsule("Beater", (side * 0.7, -30.0, 4.0),
                    (side * 0.7 + 30, -220.0, 4.0), 3.0)]),
    ])


def build_tambourine(dims):
    """A headed tambourine: wooden shell, head, and pairs of jingles in
    slots round the shell."""
    D = max(num(dims, "diameter", 254.0), 120.0)
    R, H = D / 2.0, 50.0
    pairs = int(num(dims, "pairs", 5))
    colour, material = choice(dims, {"Natural": ("#c99a60", "Plastic"),
                                     "Black": ("#1c1c1f", "Plastic"),
                                     "Red": ("#a0212b", "Plastic")},
                              "Natural")
    body = []
    for dy in (-2.0, 2.0):
        body.append(move(turn(cyl("Jingle", 21.0, 1.2, z=-0.6, seg=24),
                              x=90.0), R - 8.0, dy, H / 2 + 1.5, "Jingle"))
    jingles = loop(f"{pairs} pairs of jingles",
                   [(360.0 * i / pairs + 18.0,) for i in range(pairs)],
                   turn(group("Pair", body), z="p[0]", name="Round"))
    return group("Tambourine", [
        paint("Shell", colour, material, [revolve("Shell", [
            (R - 7.0, 0.0), (R, 0.0), (R, H), (R - 7.0, H)], seg=96)]),
        paint("Head", "#efe7d2", "Matte", [cyl("Head", R, 0.6, z=H,
                                               seg=96)]),
        paint("Jingles", "#cfd3d9", "Metal", [jingles]),
    ])


def build_bongos(dims):
    """A pair of bongos — macho and hembra — joined by a centre block."""
    from .library_music import SHELLS, drum
    shell = choice(dims, SHELLS, "Natural maple")
    macho = drum("Macho", 178.0, 150.0, shell, lugs=4, taper=0.8,
                 head="#e6d3a8", bottom=False)
    hembra = drum("Hembra", 216.0, 150.0, shell, lugs=4, taper=0.8,
                  head="#e6d3a8", bottom=False)
    return group("Bongos", [
        move(macho, -100.0, name="Macho (small)"),
        move(hembra, 120.0, name="Hembra (large)"),
        paint("Centre block", shell[0], shell[1], [
            cbox("Block", 0.0, 0.0, 50.0, 60.0, 50.0, 70.0)]),
    ])


def build_cajon(dims):
    """A cajón: a plywood box with a thin front playing plate (the tapa,
    -Y) and the sound port at the back."""
    W, D, H = 300.0, 300.0, 480.0
    colour, material = choice(dims, {"Birch": ("#d9b784", "Plastic"),
                                     "Walnut": ("#5b3a24", "Plastic"),
                                     "Black": ("#1d1d20", "Plastic")},
                              "Birch")
    return group("Cajón", [
        paint("Box", colour, material, [cbox("Box", 0.0, 0.0, 0.0, W, D,
                                             H)]),
        paint("Tapa", "#e4c79a", "Plastic", [
            cbox("Tapa", 0.0, -D / 2 - 1.5, 10.0, W - 20.0, 3.0, H - 20.0)]),
        paint("Sound port", HOLE, "Matte", [
            move(turn(cyl("Port", 58.0, 1.0, seg=48), x=-90.0), 0.0,
                 D / 2, H * 0.62, "On the back")]),
    ])


def build_maracas(dims):
    colour, material = choice(dims, {"Painted red": ("#c8342b", "Plastic"),
                                     "Natural gourd": ("#c99a4f", "Plastic"),
                                     "Yellow": ("#e2b72c", "Plastic")},
                              "Painted red")
    kids = []
    for i, (x, rz) in enumerate(((-45.0, 12.0), (45.0, -12.0))):
        one = group(f"Maraca {i + 1}", [
            paint("Head", colour, material, [ellipsoid(
                "Head", 38.0, 44.0, 38.0, 0.0, 140.0, 38.0)]),
            paint("Handle", "#b77a3f", "Plastic", [
                capsule("Handle", (0.0, 0.0, 12.0), (0.0, 100.0, 22.0),
                        11.0, seg=16)]),
        ])
        kids.append(move(turn(one, z=rz), x, name=f"Maraca {i + 1}"))
    return group("Maracas", kids)


CHIME_SIZES = {"5 tubes (C pentatonic)": dict(tubes=5, longest=420.0),
               "6 tubes": dict(tubes=6, longest=520.0),
               "8 tubes": dict(tubes=8, longest=640.0)}


def build_wind_chimes(dims):
    """Aluminium tubes on cords round a wooden disc, tuned to a C
    pentatonic chord: a free-free tube's pitch goes as 1 / L², so
    L = L₀ √(f₀ / f). A striker at mid-height and a sail below."""
    row = table(dims, CHIME_SIZES)
    n = int(num(row, "tubes", 5))
    L0 = max(num(row, "longest", 420.0), 100.0)
    scale = [0, 2, 4, 7, 9]
    notes = [midi("C5") + 12 * (i // 5) + scale[i % 5] for i in range(n)]
    lengths = [L0 * math.sqrt(freq(notes[0]) / freq(m)) for m in notes]
    r_ring = 60.0 + 6.0 * n
    drop, disc_t = 60.0, 18.0
    top = 40.0 + 180.0 + L0 + drop            # underside of the disc
    tubes, cords = [], []
    for i, L in enumerate(lengths):
        a = math.radians(360.0 * i / n)
        x, y = r_ring * math.cos(a), r_ring * math.sin(a)
        tubes.append((x, y, top - drop - L, L))
        cords.append(capsule(f"Cord {i + 1}", (x, y, top),
                             (x, y, top - drop), 0.8, seg=6))
    mid = top - drop - lengths[-1] * 0.55
    cords.append(capsule("Centre cord", (0.0, 0.0, top), (0.0, 0.0, 40.0 +
                                                           120.0), 0.8, seg=6))
    cords.append(capsule("Hanger", (0.0, 0.0, top + disc_t),
                         (0.0, 0.0, top + disc_t + 60.0), 0.8, seg=6))
    return group("Wind chimes", [
        paint("Tubes", "#c7cbd1", "Metal", [loop(
            f"{n} tubes", tubes, cyl("Tube", 12.0, "p[3]", "p[0]", "p[1]",
                                     "p[2]", seg=24))]),
        paint("Wood", "#9a6433", "Plastic", [
            cyl("Top disc", r_ring + 25.0, disc_t, z=top, seg=48),
            cyl("Striker", r_ring - 26.0, 12.0, z=mid, seg=48),
            move(turn(cbox("Sail", 0.0, 0.0, 0.0, 70.0, 4.0, 120.0), z=0.0),
                 z=40.0, name="Sail")]),
        paint("Cords", "#e8e2d0", "Matte", cords),
        paint("Ring", "#c7cbd1", "Metal", [move(turn(torus(
            "Hanging ring", 14.0, 2.0, seg=24), x=90.0), z=top + disc_t +
            74.0, name="Hanging ring")]),
    ])


# ── accessories ───────────────────────────────────────────────────────

def build_music_stand(dims):
    from .library_music import tripod
    H = max(num(dims, "height", 1150.0), 600.0)
    desk = move(turn(group("Desk", [
        cbox("Desk", 0.0, 0.0, 0.0, 500.0, 4.0, 330.0),
        cbox("Ledge", 0.0, -30.0, 0.0, 500.0, 60.0, 4.0)]), x=-20.0,
        name="Tilted back"), 0.0, 0.0, H - 250.0, "Desk")
    return group("Music stand", [
        tripod("Stand", H - 250.0, 300.0, colour="#1b1b1e"),
        paint("Desk", "#1b1b1e", "Metal", [desk])])


def build_metronome(dims):
    """A pyramid metronome: its case, the dark scale face, and the
    pendulum with its sliding weight."""
    H = max(num(dims, "height", 220.0), 100.0)
    colour, material = choice(dims, {"Walnut": ("#5b3a24", "Plastic"),
                                     "Mahogany": ("#6a2a1a", "Plastic"),
                                     "Black": ("#1c1c1f", "Plastic")},
                              "Walnut")
    body = CadNode("hull", "Case")
    body.add(cbox("Base", 0.0, 0.0, 0.0, H * 0.55, H * 0.5, 4.0))
    body.add(cbox("Top", 0.0, 0.0, H - 4.0, H * 0.12, H * 0.12, 4.0))
    face = CadNode("hull", "Scale face")
    face.add(cbox("Face low", 0.0, -H * 0.2, H * 0.12, H * 0.22, 1.0, 1.0))
    face.add(cbox("Face high", 0.0, -H * 0.075, H * 0.9, H * 0.06, 1.0,
                  1.0))
    return group("Metronome", [
        paint("Case", colour, material, [body]),
        paint("Scale", "#e9dfc3", "Matte", [face]),
        paint("Pendulum", CHROME, "Metal", [
            capsule("Pendulum", (0.0, -H * 0.22, H * 0.14),
                    (H * 0.12, -H * 0.13, H * 0.95), 1.5),
            cbox("Weight", H * 0.06, -H * 0.185, H * 0.55, 18.0, 10.0, 16.0)]),
    ])


def _p(label, build, sizes=None, fields=(), colors=None):
    spec = dict(label=label, category=CATEGORY,
                sizes=sizes or {"Standard": {}}, fields=list(fields),
                build=build)
    if colors:
        spec["colors"] = list(colors)
    return spec


_ONE = {"Standard": {}}
PARTS = {
    "music_acoustic_guitar": _p("Acoustic guitar (dreadnought)",
                                _gtr_part("acoustic"), colors=WOODS),
    "music_classical_guitar": _p("Classical guitar (nylon)",
                                 _gtr_part("classical"), colors=WOODS),
    "music_electric_guitar": _p("Electric guitar (single-cut)",
                                _gtr_part("electric"), colors=PAINTS),
    "music_bass_guitar": _p("Bass guitar (4-string)", _gtr_part("bass"),
                            colors=PAINTS),
    "music_ukulele": _p("Ukulele", build_ukulele,
                        {k: {} for k in UKULELES}, colors=WOODS),
    "music_violin": _p("Violin family (violin, viola, cello)", build_bowed,
                       {k: {} for k in BOWED}, colors=VARNISH),
    "music_recorder": _p("Recorder", build_recorder, RECORDERS,
                         [("length", "Length"), ("diameter", "Head Ø")],
                         RECORDER_WOODS),
    "music_flute": _p("Flute (concert)", build_flute,
                      {"C flute": dict(length=670.0)},
                      [("length", "Length")], FLUTE_FINISH),
    "music_trumpet": _p("Trumpet (B♭)", build_trumpet, colors=BRASS_FINISH),
    "music_pan_pipes": _p("Pan pipes (tuned)", build_pan_pipes, PAN_SIZES,
                          colors=PAN_LOOKS),
    "music_harmonica": _p("Harmonica (10-hole)", build_harmonica,
                          colors=("Pear wood", "Black")),
    "music_triangle": _p("Triangle", build_triangle,
                         {'7"': dict(side=180.0), '6"': dict(side=150.0),
                          '9"': dict(side=230.0)}, [("side", "Side")]),
    "music_tambourine": _p("Tambourine", build_tambourine,
                           {'10"': dict(diameter=254.0, pairs=5),
                            '8"': dict(diameter=203.0, pairs=4),
                            '12"': dict(diameter=305.0, pairs=8)},
                           [("diameter", "Diameter"), ("pairs", "Jingles")],
                           ("Natural", "Black", "Red")),
    "music_bongos": _p("Bongos", build_bongos,
                       colors=("Natural maple", "Black", "Red sparkle")),
    "music_cajon": _p("Cajón", build_cajon,
                      colors=("Birch", "Walnut", "Black")),
    "music_maracas": _p("Maracas (pair)", build_maracas,
                        colors=("Painted red", "Natural gourd", "Yellow")),
    "music_wind_chimes": _p("Wind chimes (tuned)", build_wind_chimes,
                            CHIME_SIZES),
    "music_stand": _p("Music stand", build_music_stand,
                      {"Standard": dict(height=1150.0)},
                      [("height", "Height")]),
    "music_metronome": _p("Metronome", build_metronome,
                          {"Standard": dict(height=220.0)},
                          [("height", "Height")],
                          ("Walnut", "Mahogany", "Black")),
}

COUNT_FIELDS = {"pairs", "tubes", "pipes"}

GROUPS = {
    "Strings": ("Acoustic guitar", "Classical guitar", "Electric guitar",
                "Bass guitar", "Ukulele", "Violin"),
    "Winds & brass": ("Recorder", "Flute", "Trumpet", "Pan pipes",
                      "Harmonica"),
    "Hand percussion": ("Triangle", "Tambourine", "Bongos", "Cajón",
                        "Maracas", "Wind chimes"),
    "Accessories": ("Music stand", "Metronome"),
}
