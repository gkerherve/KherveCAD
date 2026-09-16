"""The **Lighting & signals** library: street lamps, park lights,
floodlight masts and traffic signals, modelled piece by piece.

- Victorian street lamp: a stepped cast base, a fluted column with
  collars, a ladder bar, a hexagonal lantern (glowing panes between
  glazing bars), its roof and finial;
- modern LED street light (single or double arm): a tapered pole, a
  slender outreach arm and a flat luminaire whose underside glows;
- park lamp (globe), bollard light, wall lantern;
- floodlight mast: a tall pole and a head frame of angled floodlights
  for pitches and courts;
- traffic lights: a pole-mounted three-aspect signal (backplate, hooded
  visors, lenses — the lit aspect chosen from the colour combo glows,
  the others are dark glass), a mast-arm signal over the road, and a
  pedestrian crossing signal with red / green figures and a push
  button; a Belisha beacon and a stop sign.

Boxes, cylinders and hulls only (no booleans) so the preview is exact;
true sizes in mm, standing on z = 0, facing -Y (the way the light or
signal points). Lit glass is the Emissive material.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from .city_buildings import _f, box, color, cyl, group, move, turn
from .model import CadNode

CATEGORY = "Lighting & signals"

METALS = {"Black": "#26292d", "Heritage green": "#23433a",
          "Anthracite": "#3a3e44", "Silver": "#aeb4ba"}
GLOW = "#fff1c7"
GLOW_COOL = "#eef6ff"
LIT = {"Red": "#ff3b2f", "Amber": "#ffb000", "Green": "#35e07a"}
UNLIT = {"Red": "#4a1512", "Amber": "#4a3510", "Green": "#113a22"}


def sphere(name, x, y, z, r, seg=24):
    return CadNode("sphere", name, dict(x=x, y=y, z=z, radius=r,
                                        segments=seg))


def hull(name, parts):
    h = CadNode("hull", name, {})
    for p in parts:
        h.add(p)
    return h


def _metal(dims, default="Black"):
    return METALS.get(dims.get("_color") or default, METALS[default])


# ------------------------------------------------------------- lamps
def build_victorian(dims):
    h = _f(dims.get("h"), 4500)
    k = h / 4500.0
    m = _metal(dims, "Black")
    parts = [
        cyl("Plinth", 0, 0, 0, 120 * k, 260 * k, 250 * k, seg=8),
        cyl("Base", 0, 0, 120 * k, 520 * k, 230 * k, 120 * k, seg=8),
        cyl("Base collar", 0, 0, 640 * k, 70 * k, 150 * k, seg=16),
        cyl("Column", 0, 0, 700 * k, 2400 * k, 95 * k, 70 * k, seg=16),
        cyl("Collar", 0, 0, 1500 * k, 60 * k, 115 * k, seg=16),
        cyl("Top collar", 0, 0, 3080 * k, 90 * k, 110 * k, 90 * k, seg=16),
        cyl("Neck", 0, 0, 3170 * k, 250 * k, 70 * k, 130 * k, seg=16),
    ]
    # flutes: raised ribs up the column
    for i in range(8):
        a = i * 45.0
        parts.append(turn(box("Flute", 72 * k, -12 * k, 800 * k, 26 * k,
                              24 * k, 2150 * k), z=a, name="Flute"))
    # ladder bar
    parts.append(move(turn(cyl("Ladder bar", 0, 0, 0, 700 * k, 22 * k, seg=8),
                           y=90.0), -350 * k, 0, 2950 * k, "Ladder bar"))
    # lantern: hexagonal cage
    z0, lh, lr = 3420 * k, 700 * k, 260 * k
    parts += [cyl("Lantern base", 0, 0, z0, 70 * k, lr * 0.75, lr, seg=6),
              cyl("Lantern roof", 0, 0, z0 + lh, 260 * k, lr * 1.15, 60 * k,
                  seg=6),
              cyl("Roof lip", 0, 0, z0 + lh - 20 * k, 50 * k, lr * 1.2,
                  seg=6),
              sphere("Finial ball", 0, 0, z0 + lh + 330 * k, 55 * k, 12),
              cyl("Finial", 0, 0, z0 + lh + 380 * k, 160 * k, 20 * k, 4 * k,
                  seg=8)]
    for i in range(6):
        a = math.radians(i * 60.0)
        parts.append(cyl("Glazing bar", math.cos(a) * lr * 0.98,
                         math.sin(a) * lr * 0.98, z0 + 60 * k, lh - 60 * k,
                         18 * k, seg=4))
    body = color(group("Cast iron", parts), m, "Metal")
    glass = color(cyl("Lantern glass", 0, 0, z0 + 60 * k, lh - 60 * k,
                      lr * 0.9, lr * 1.05, seg=6), GLOW, "Emissive")
    return group("Victorian street lamp", [body, glass])


def build_led_street(dims, arms=1):
    h = _f(dims.get("h"), 8000)
    reach = _f(dims.get("reach"), 1500)
    m = _metal(dims, "Silver")
    parts = [cyl("Foundation", 0, 0, 0, 150, 260, seg=12),
             cyl("Pole", 0, 0, 150, h - 150, 110, 60, seg=16),
             cyl("Door panel", 0, -100, 600, 450, 25, seg=4)]
    glow = []
    for side in range(arms):
        sgn = -1 if side == 0 else 1
        arm = hull("Arm", [
            sphere("Joint", 0, 0, h - 60, 55, 12),
            sphere("Tip", 0, sgn * reach, h + 180, 40, 12)])
        parts.append(arm)
        head = hull("Luminaire", [
            box("Back", -170, sgn * reach - (60 if sgn < 0 else -60) - 60,
                h + 110, 340, 120, 110),
            box("Front", -140, sgn * (reach + 620) - 40, h + 130, 280, 80,
                60)])
        parts.append(head)
        glow.append(hull("LED panel", [
            box("A", -130, sgn * reach - 40, h + 100, 260, 80, 12),
            box("B", -110, sgn * (reach + 560) - 40, h + 122, 220, 80, 12)]))
    body = color(group("Pole and arm", parts), m, "Metal")
    return group("LED street light" if arms == 1 else
                 "Double-arm street light",
                 [body, color(group("Light", glow), GLOW_COOL, "Emissive")])


def build_park_lamp(dims):
    h = _f(dims.get("h"), 3500)
    m = _metal(dims, "Anthracite")
    body = color(group("Post", [
        cyl("Base", 0, 0, 0, 300, 140, 90, seg=16),
        cyl("Post", 0, 0, 300, h - 700, 60, 50, seg=16),
        cyl("Collar", 0, 0, h - 420, 60, 90, seg=16),
        cyl("Globe seat", 0, 0, h - 360, 60, 120, 150, seg=16)]),
        m, "Metal")
    globe = color(sphere("Globe", 0, 0, h - 60, 270, 24), "#fff7df",
                  "Emissive")
    cap = color(cyl("Cap", 0, 0, h + 180, 60, 90, 20, seg=16), m, "Metal")
    return group("Park lamp", [body, globe, cap])


def build_bollard(dims):
    h = _f(dims.get("h"), 900)
    m = _metal(dims, "Anthracite")
    body = color(group("Bollard", [
        cyl("Body", 0, 0, 0, h - 200, 100, seg=20),
        cyl("Hood", 0, 0, h - 60, 60, 115, 105, seg=20),
        cyl("Posts", 0, 0, h - 200, 140, 40, seg=8)]), m, "Metal")
    ring = color(cyl("Light ring", 0, 0, h - 200, 140, 96, seg=20), GLOW,
                 "Emissive")
    return group("Bollard light", [body, ring])


def build_wall_lantern(dims):
    h = _f(dims.get("h"), 450)
    m = _metal(dims, "Black")
    k = h / 450.0
    body = color(group("Frame", [
        box("Wall plate", -70 * k, 0, 0, 140 * k, 20 * k, 260 * k),
        box("Bracket", -15 * k, -220 * k, 180 * k, 30 * k, 220 * k, 30 * k),
        cyl("Lantern base", 0, -300 * k, 60 * k, 30 * k, 90 * k, seg=4),
        cyl("Lantern top", 0, -300 * k, 330 * k, 90 * k, 110 * k, 20 * k,
            seg=4)]), m, "Metal")
    glass = color(cyl("Glass", 0, -300 * k, 90 * k, 240 * k, 70 * k, 90 * k,
                      seg=4), GLOW, "Emissive")
    return group("Wall lantern", [body, glass])


def build_floodlight(dims):
    h = _f(dims.get("h"), 15000)
    cols = max(1, int(_f(dims.get("lamps"), 4)))
    m = _metal(dims, "Silver")
    parts = [cyl("Foundation", 0, 0, 0, 300, 600, seg=12),
             cyl("Mast", 0, 0, 300, h - 300, 260, 140, seg=16)]
    for z in range(1, int(h // 3000)):          # climbing rungs
        parts.append(box("Rung", -20, -300, z * 3000, 40, 160, 40))
    width = cols * 700.0
    parts += [box("Head frame", -width / 2, -120, h, width, 80, 60),
              box("Head frame", -width / 2, -120, h + 900, width, 80, 60),
              box("Head post", -40, -120, h - 200, 80, 80, 1200)]
    lights, lenses = [], []
    for row in range(2):
        for c in range(cols):
            x = -width / 2 + 350 + c * 700
            z = h + 150 + row * 900
            lamp = move(turn(group("Floodlight", [
                cyl("Housing", 0, 0, 0, 280, 280, 300, seg=12),
                cyl("Fins", 0, 0, -60, 60, 220, seg=12)]), x=-70.0),
                x, -220, z, "Floodlight")
            lights.append(lamp)
            lenses.append(move(turn(cyl("Lens", 0, 0, 280, 20, 285, seg=12),
                                    x=-70.0), x, -220, z, "Lens"))
    body = color(group("Mast", parts + lights), m, "Metal")
    return group("Floodlight mast", [
        body, color(group("Lenses", lenses), GLOW_COOL, "Emissive")])


# ----------------------------------------------------------- signals
def _signal_head(lit, name="Signal head", pedestrian=False):
    """A three-aspect head (or two-aspect pedestrian head) centred on
    its bottom middle: backplate, body, hoods, lenses."""
    aspects = ("Red", "Green") if pedestrian else ("Red", "Amber", "Green")
    n = len(aspects)
    pitch = 300.0
    height = n * pitch + 60
    parts = [box("Backplate", -330, 40, 0, 660, 20, height + 120),
             box("Housing", -190, -180, 60, 380, 220, height)]
    frame, lenses = [], []
    for i, aspect in enumerate(aspects):
        z = 60 + height - 30 - pitch * (i + 0.5)
        # an open visor over each lens: a sloping top and two cheeks
        frame += [hull("Visor top", [box("Root", -140, -185, z + 120, 280,
                                         5, 30),
                                     box("Lip", -130, -400, z + 80, 260, 5,
                                         22)]),
                  hull("Visor cheek", [box("Root", -142, -185, z - 20, 12, 5,
                                           170),
                                       box("Lip", -132, -400, z + 60, 12, 5,
                                           40)]),
                  hull("Visor cheek", [box("Root", 130, -185, z - 20, 12, 5,
                                           170),
                                       box("Lip", 120, -400, z + 60, 12, 5,
                                           40)])]
        on = aspect == lit
        lens = move(turn(cyl("Lens", 0, 0, 0, 30, 110, seg=20), x=90.0),
                    0, -160, z, aspect)
        lenses.append(color(lens, (LIT if on else UNLIT)[aspect],
                            "Emissive" if on else "Glass",
                            alpha=1.0))
    body = color(group("Housing", parts), "#1d1f22", "Plastic")
    plate_edge = color(box("Backplate border", -335, 60, -5, 670, 8,
                           height + 130), "#f2c200", "Matte")
    hoods = color(group("Hoods", frame), "#1d1f22", "Plastic")
    return group(name, [body, plate_edge, hoods] + lenses)


def _lit(dims, default="Red"):
    colour = dims.get("_color") or default
    return colour if colour in LIT else default


def build_traffic_light(dims):
    h = _f(dims.get("h"), 3600)
    pole = color(group("Pole", [
        cyl("Base", 0, 0, 0, 200, 110, 90, seg=16),
        cyl("Pole", 0, 0, 200, h - 200, 70, seg=16),
        cyl("Cap", 0, 0, h, 40, 75, 40, seg=16)]), "#6d737a", "Metal")
    head = move(_signal_head(_lit(dims)), 0, -90, h - 1260, "Signal head")
    button = color(box("Push button unit", -90, -170, 1000, 180, 100, 280),
                   "#e2b400", "Plastic")
    return group("Traffic light", [pole, head, button])


def build_mast_arm(dims):
    h = _f(dims.get("h"), 6000)
    reach = _f(dims.get("reach"), 6000)
    lit = _lit(dims)
    pole = color(group("Mast arm", [
        cyl("Base", 0, 0, 0, 300, 220, 180, seg=16),
        cyl("Pole", 0, 0, 300, h - 300, 150, 110, seg=16),
        hull("Arm", [sphere("Root", 0, 0, h - 150, 110, 16),
                     sphere("Tip", reach, 0, h + 300, 60, 16)]),
        hull("Brace", [sphere("Low", 0, 0, h - 1200, 50, 12),
                       sphere("High", reach * 0.4, 0, h + 20, 40, 12)])]),
        "#6d737a", "Metal")
    heads = [move(_signal_head(lit), reach * f, -120, h - 1200, "Signal head")
             for f in (0.55, 0.95)]
    sign = color(box("Street sign", reach * 0.1, -60, h + 150, 1800, 30,
                     350), "#1e6a3a", "Matte")
    return group("Traffic light (mast arm)", [pole, sign] + heads)


def build_pedestrian(dims):
    h = _f(dims.get("h"), 3000)
    lit = "Green" if (dims.get("_color") or "Red") == "Green" else "Red"
    pole = color(group("Pole", [
        cyl("Base", 0, 0, 0, 200, 100, 80, seg=16),
        cyl("Pole", 0, 0, 200, h - 200, 60, seg=16)]), "#6d737a", "Metal")
    head = move(_signal_head(lit, "Pedestrian signal", pedestrian=True), 0,
                -80, h - 900, "Pedestrian signal")
    # the figures: a standing (red) and walking (green) person on the lenses
    figures = []
    for aspect, dz in (("Red", 1), ("Green", 0)):
        z = h - 900 + 60 + 30 + 300 * dz + 150
        on = aspect == lit
        col = "#ffffff" if on else "#5a5a5a"
        figures.append(color(group(f"{aspect} figure", [
            sphere("Head", 0, -276, z + 55, 18, 12),
            box("Body", -16, -278, z - 35, 32, 6, 70),
            box("Legs", -20 if aspect == "Green" else -14, -278, z - 95, 40
                if aspect == "Green" else 28, 6, 60)]), col, "Emissive"
            if on else "Matte"))
    button = color(group("Push button", [
        box("Box", -110, -180, 1050, 220, 110, 320),
        cyl("Button", 0, -185, 1180, 10, 35, seg=12)]), "#e2b400", "Plastic")
    return group("Pedestrian crossing signal", [pole, head, button] + figures)


def build_belisha(dims):
    h = _f(dims.get("h"), 2700)
    stripes = []
    band = 300.0
    for i in range(int((h - 300) // band)):
        stripes.append(color(cyl("Band", 0, 0, i * band, band, 55, seg=16),
                             "#1b1b1b" if i % 2 == 0 else "#f4f4f2",
                             "Plastic"))
    top = int((h - 300) // band) * band
    globe = color(sphere("Globe", 0, 0, top + 200, 170, 24), "#ffa31a",
                  "Emissive")
    return group("Belisha beacon", stripes + [globe])


def build_stop_sign(dims):
    h = _f(dims.get("h"), 2400)
    r = 380.0
    pole = color(cyl("Post", 0, 0, 0, h, 35, seg=12), "#9aa0a6", "Metal")
    face = move(turn(turn(cyl("Octagon", 0, 0, 0, 20, r, seg=8), z=22.5),
                     x=90.0, name="Face"), 0, -40, h - r + 50, "Sign")
    border = move(turn(turn(cyl("Border", 0, 0, 0, 16, r + 25, seg=8),
                            z=22.5), x=90.0), 0, -24, h - r + 50, "Border")
    words = CadNode("linear_extrude", "STOP", dict(height=6.0, twist=0.0,
                                                   scale=1.0, center=False,
                                                   segments=0))
    words.add(CadNode("text", "STOP", dict(x=-230.0, y=-80.0, text="STOP",
                                           size=160.0)))
    text = move(turn(words, x=90.0), 0, -62, h - r + 50, "Lettering")
    return group("Stop sign", [
        pole, color(border, "#f4f4f2", "Matte"),
        color(face, "#c8102e", "Plastic"),
        color(text, "#f4f4f2", "Matte")])


# ------------------------------------------------------------- parts
def _entry(label, build, sizes, fields, colors=None):
    entry = dict(label=label, category=CATEGORY, sizes=sizes, build=build,
                 fields=fields)
    if colors:
        entry["colors"] = list(colors)
    return entry


_H = [("h", "Height")]
PARTS = {
    "light_victorian": _entry("Victorian street lamp", build_victorian,
                              {"3.5 m": dict(h=3500), "4.5 m": dict(h=4500),
                               "5.5 m": dict(h=5500)}, _H, METALS),
    "light_led": _entry("LED street light", build_led_street,
                        {"6 m": dict(h=6000, reach=1200),
                         "8 m": dict(h=8000, reach=1500),
                         "10 m": dict(h=10000, reach=2000)},
                        _H + [("reach", "Arm reach")], METALS),
    "light_led_double": _entry(
        "Double-arm street light", lambda d: build_led_street(d, arms=2),
        {"8 m": dict(h=8000, reach=1500), "10 m": dict(h=10000, reach=2000)},
        _H + [("reach", "Arm reach")], METALS),
    "light_park": _entry("Park lamp (globe)", build_park_lamp,
                         {"3 m": dict(h=3000), "3.5 m": dict(h=3500),
                          "4 m": dict(h=4000)}, _H, METALS),
    "light_bollard": _entry("Bollard light", build_bollard,
                            {"0.7 m": dict(h=700), "0.9 m": dict(h=900),
                             "1.1 m": dict(h=1100)}, _H, METALS),
    "light_wall_lantern": _entry("Wall lantern", build_wall_lantern,
                                 {"Small": dict(h=350), "Medium": dict(h=450),
                                  "Large": dict(h=600)}, _H, METALS),
    "light_floodlight": _entry(
        "Floodlight mast (sport)", build_floodlight,
        {"12 m": dict(h=12000, lamps=3), "15 m": dict(h=15000, lamps=4),
         "20 m": dict(h=20000, lamps=6)},
        _H + [("lamps", "Lamps per row")], METALS),
    "signal_traffic": _entry("Traffic light", build_traffic_light,
                             {"Standard (3.6 m)": dict(h=3600),
                              "Tall (4.5 m)": dict(h=4500)}, _H, LIT),
    "signal_mast_arm": _entry("Traffic light on mast arm", build_mast_arm,
                              {"6 m arm": dict(h=6000, reach=6000),
                               "9 m arm": dict(h=6500, reach=9000)},
                              _H + [("reach", "Arm reach")], LIT),
    "signal_pedestrian": _entry("Pedestrian crossing signal",
                                build_pedestrian,
                                {"Standard (3 m)": dict(h=3000)}, _H,
                                ("Red", "Green")),
    "signal_belisha": _entry("Belisha beacon (zebra crossing)", build_belisha,
                             {"Standard (2.7 m)": dict(h=2700)}, _H),
    "sign_stop": _entry("Stop sign", build_stop_sign,
                        {"Standard (2.4 m)": dict(h=2400)}, _H),
}

COUNT_FIELDS = {"lamps"}
