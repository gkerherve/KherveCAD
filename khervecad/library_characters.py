"""People & characters for the parts library (2026-09-18, the user's
request): figures built on the `human` node (MakeHuman's base body),
every one still editable — the body's gender / age / weight / height
and pose, the muscles as `sculpt` strokes, the clothes as a `paint`
wrapper projecting a colour map from the front, and the pieces a body
cannot grow (hair, cape, cowl ears, chest crest) as ordinary nodes.

- **People**: every `human_design` preset (casual, office, doctor,
  chef, runner, grandparents, …), dressed by the `outfit` node — the
  Human Builder's own choices.
- **Caped superhero** and **Dark knight**: 1.91 m, heroically muscled
  (sculpted — the base mesh has no muscle target, and its "weight" is
  fat), hands on hips, capes, and the same original "K" crest in their
  own colours. They are generic costumed heroes: no studio's logo is
  copied.

The clothes are colour maps: `suit_rules` says the colour of each point
of a front view (x across, z up, in mm), `write_png` rasterises it at
5 mm a pixel into ``khervecad/characters/<key>.png`` (shipped; run
``python -m khervecad.library_characters`` after changing a rule — a
test pins the files to the rules).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os
import struct
import zlib

from .model import CadNode

CATEGORY = "Characters"
FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "characters")

#: the colour map's frame: x -450..450, z 0..1950 mm, 5 mm a pixel
MAP_X, MAP_W, MAP_H, PIXEL = -450.0, 900.0, 1950.0, 5.0

SKIN = (224, 172, 138)


def _hex(rgb):
    return "#%02x%02x%02x" % rgb


# --------------------------------------------------------------- rules
def _hero(x, z):
    ax = abs(x)
    blue, red, yellow = (31, 79, 191), (200, 16, 46), (242, 194, 48)
    if 175 <= ax <= 305 and 990 <= z <= 1170:
        return SKIN                                   # hands on hips
    if z >= 1690:
        return SKIN                                   # head
    if 1600 <= z < 1690 and ax < 62 + (z - 1600) * 0.45:
        return SKIN                                   # neck in the collar
    if 1055 <= z < 1100:
        return yellow                                 # belt
    if 930 <= z < 1055 and ax < 260:
        return red                                    # trunks
    if z < 480 or (z < 505 and ax > 40):
        return red                                    # boots
    return blue


def _knight(x, z):
    ax = abs(x)
    grey, black, gold = (91, 96, 104), (22, 23, 26), (214, 170, 52)
    if 175 <= ax <= 305 and 990 <= z <= 1170:
        return black                                  # gloves
    if z >= 1600:
        return black                                  # cowl and its cape
    if 1052 <= z < 1105:
        return gold                                   # utility belt
    if 930 <= z < 1052 and ax < 260:
        return black                                  # trunks
    if z < 520 or (z < 545 and ax > 40):
        return black                                  # boots
    return grey


RULES = {"hero": _hero, "knight": _knight, "skin": lambda x, z: SKIN}


def png_bytes(rule, width=int(MAP_W / PIXEL), height=int(MAP_H / PIXEL)):
    """The colour map of *rule* as an RGB PNG (x left to right, z up)."""
    rows = bytearray()
    for r in range(height):
        z = (height - 1 - r) * PIXEL + PIXEL / 2
        rows.append(0)
        for i in range(width):
            rows.extend(rule(MAP_X + i * PIXEL + PIXEL / 2, z))

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2,
                                         0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
            + chunk(b"IEND", b""))


def map_path(key):
    return os.path.join(FOLDER, f"{key}.png")


def write_pngs():
    os.makedirs(FOLDER, exist_ok=True)
    for key, rule in RULES.items():
        size = (4, 4) if key == "skin" else ()
        with open(map_path(key), "wb") as fh:
            fh.write(png_bytes(rule, *size))


# ---------------------------------------------------------------- body
#: hands on the hips, feet a little apart
HANDS_ON_HIPS = [["upperarm01.L", 35.0, 5.0, 0.0],
                 ["upperarm01.R", 35.0, -5.0, 0.0],
                 ["lowerarm01.L", 0.0, 70.0, 0.0],
                 ["lowerarm01.R", 0.0, -70.0, 0.0],
                 ["upperleg01.L", 0.0, -4.0, 0.0],
                 ["upperleg01.R", 0.0, 4.0, 0.0]]
HERO_FACE = [["chin-width", 0.7], ["head-square", 0.6],
             ["chin-prominent", 0.5], ["chin-bones", 0.4],
             ["neck-scale-horiz", 0.8], ["neck-scale-depth", 0.5],
             ["cheek-bones", 0.3]]


def _s(kind, x, y, z, radius, strength):
    return [kind, x, y, z, radius, strength, 0.0, 0.0, 0.0]


#: a heroic physique on the 1.91 m hands-on-hips figure (mirrored in x):
#: 1 inflate, 2 smooth, 3 flatten. Pecs are ONE broad stroke pressed
#: flat — two round inflates read as a woman's chest.
HERO_MUSCLES = [
    _s(1, 115, -120, 1490, 150, 26), _s(3, 70, -150, 1440, 120, 0.7),
    _s(1, 236, -60, 1540, 110, 48), _s(1, 240, 40, 1550, 100, 32),
    _s(1, 120, -5, 1585, 85, 16), _s(1, 48, -30, 1628, 55, 8),
    _s(1, 150, -20, 1320, 130, 38), _s(1, 300, 0, 1410, 90, 38),
    _s(1, 330, 100, 1400, 90, 30), _s(1, 350, 20, 1230, 80, 18),
    _s(1, 160, -90, 720, 150, 38), _s(1, 230, -40, 760, 120, 24),
    _s(1, 225, 20, 430, 95, 30), _s(1, 150, -60, 1120, 90, -18),
    _s(1, 38, -125, 1180, 42, 10), _s(1, 38, -128, 1250, 42, 10),
    _s(1, 38, -130, 1320, 42, 10), _s(2, 150, -40, 1400, 260, 1),
    _s(2, 90, -20, 1610, 120, 2)]


def _figure(name, human, map_key, strokes=None, face=None):
    """paint(colour map) > [sculpt] > human, plus an optional skin paint
    over the face (*face*: two corners) for a masked character."""
    body = CadNode("human", name, dict(
        gender=human["gender"], age=human["age"], weight=human["weight"],
        height=human["height"], stature=human["stature"],
        targets=[list(t) for t in human.get("targets", [])], warp=[],
        warp_radius=45.0, pose=[list(p) for p in human["pose"]]))
    if strokes:
        sculpt = CadNode("sculpt", "Muscles", dict(
            strokes=[list(s) for s in strokes], detail=0.0, mirror="x",
            region=[]))
        sculpt.add(body)
        body = sculpt
    paint = CadNode("paint", "Clothes", dict(
        image=map_path(map_key), plane="Front (XZ)", x=MAP_X, y=0.0,
        width=MAP_W, height=MAP_H, sides="both", image2="",
        plane2="Side (YZ)", x2=0.0, y2=0.0, width2=100.0, height2=0.0,
        region=[]))
    paint.add(body)
    if face:
        skin = CadNode("paint", "Face", dict(
            image=map_path("skin"), plane="Front (XZ)", x=MAP_X, y=0.0,
            width=MAP_W, height=MAP_H, sides="front", image2="",
            plane2="Side (YZ)", x2=0.0, y2=0.0, width2=100.0, height2=0.0,
            region=[list(c) for c in face]))
        skin.add(paint)
        paint = skin
    return paint


def _parts(program):
    from . import scadparse
    root, _warnings = scadparse.parse_scad(program)
    return list(root.children)


def _group(name, *children):
    node = CadNode("union", name)
    for child in children:
        if isinstance(child, list):
            for c in child:
                node.add(c)
        else:
            node.add(child)
    return node


# ------------------------------------------------------------ builders
def _cape(colour, top_w, bottom_w, bottom_z, scallops=0):
    """A cape from the shoulder blades (y 72, z 1580) falling back to
    y 300 at *bottom_z*: one flat slab tilted back, its hem straight or
    cut into *scallops* points; plus two straps over the shoulders."""
    top_z, top_y, low_y = 1582.0, 72.0, 300.0
    length = ((top_z - bottom_z) ** 2 + (low_y - top_y) ** 2) ** 0.5
    import math
    tilt = math.degrees(math.atan2(low_y - top_y, top_z - bottom_z))
    hem = [(bottom_w / 2, -length), (-bottom_w / 2, -length)]
    if scallops:
        hem = [(bottom_w / 2, -length)]
        step = bottom_w / scallops
        for i in range(scallops):
            x0 = bottom_w / 2 - i * step
            hem += [(x0 - step / 2, -length + step * 0.45),
                    (x0 - step, -length)]
    pts = [(-top_w / 2, 0.0), (top_w / 2, 0.0)] + hem
    points = ", ".join(f"[{x:.1f}, {y:.1f}]" for x, y in pts)
    return _parts(f"""
color("{colour}") union() {{  // Cape
  translate([0, {top_y}, {top_z}]) rotate([90 + {tilt:.2f}, 0, 0]) translate([0, 0, -4]) linear_extrude(height = 8) polygon(points = [{points}]);  // Cape cloth
  hull() {{ translate([150, 50, 1585]) cube([55, 30, 12]); translate([140, -40, 1570]) cube([50, 10, 12]); }}  // Left strap
  hull() {{ translate([-205, 50, 1585]) cube([55, 30, 12]); translate([-190, -40, 1570]) cube([50, 10, 12]); }}  // Right strap
}}""")


HERO_CREST = """
translate([0, -170, 1430]) rotate([72, 0, 0]) union() {  // Chest crest
  color("#c8102e") linear_extrude(height = 8) polygon(points = [[0, -104], [-92, 2], [-64, 52], [64, 52], [92, 2]]);  // Crest border
  color("#f2c230") linear_extrude(height = 11) polygon(points = [[0, -86], [-76, 2], [-54, 42], [54, 42], [76, 2]]);  // Crest field
  color("#c8102e") linear_extrude(height = 13) translate([-24, -40]) text(text = "K", size = 60);  // Crest letter
}"""

KNIGHT_CREST = """
translate([0, -170, 1430]) rotate([72, 0, 0]) union() {  // Chest crest
  color("#0e0f11") linear_extrude(height = 8) polygon(points = [[0, -104], [-92, 2], [-64, 52], [64, 52], [92, 2]]);  // Crest border
  color("#2c2f35") linear_extrude(height = 11) polygon(points = [[0, -86], [-76, 2], [-54, 42], [54, 42], [76, 2]]);  // Crest field
  color("#d6aa34") linear_extrude(height = 13) translate([-24, -40]) text(text = "K", size = 60);  // Crest letter
}"""


def build_hero(dims):
    """A caped superhero: blue suit, red trunks, boots and cape, yellow
    belt, an original "K" crest, short dark hair with a quiff."""
    body = _figure("Hero body", dict(gender=1, age=0.1, weight=0.15,
                                     height=0.5, stature=1910,
                                     targets=HERO_FACE,
                                     pose=HANDS_ON_HIPS), "hero",
                   HERO_MUSCLES)
    hair = _parts("""
color("#15161a") union() {  // Hair
  kcad_ellipsoid(c = [0, -40, 1842], r = [96, 120, 80]);  // Hair cap
  kcad_ellipsoid(c = [0, -112, 1880], r = [78, 48, 34]);  // Front hair
  kcad_ellipsoid(c = [14, -150, 1858], r = [24, 18, 20]);  // Forelock curl
}""")
    return _group("Caped superhero", body, _cape("#c8102e", 410, 880, 270),
                  _parts(HERO_CREST), hair)


def build_knight(dims):
    """A dark knight: grey suit, black cowl with pointed ears, gloves,
    boots, trunks and a long scalloped cape, gold utility belt with
    pouches, the "K" crest in black and gold."""
    body = _figure("Knight body", dict(gender=1, age=0.15, weight=0.15,
                                       height=0.5, stature=1910,
                                       targets=HERO_FACE,
                                       pose=HANDS_ON_HIPS), "knight",
                   HERO_MUSCLES,
                   face=[[-78, -230, 1664], [78, -40, 1752]])
    extras = _parts("""
color("#16171a") union() {  // Cowl
  kcad_ellipsoid(c = [0, -32, 1836], r = [100, 124, 90]);  // Cowl top
  translate([52, -55, 1880]) rotate([0, 12, 0]) cylinder(h = 80, r1 = 16, r2 = 2);  // Left ear
  translate([-52, -55, 1880]) rotate([0, -12, 0]) cylinder(h = 80, r1 = 16, r2 = 2);  // Right ear
}
color("#d6aa34") union() {  // Belt pouches
  for (a = [-62, -38, 38, 62]) translate([sin(a) * 150, -cos(a) * 118, 1060]) rotate([0, 0, a]) cube([34, 22, 44], center = false);  // Pouch
}""")
    return _group("Dark knight", body,
                  _cape("#16171a", 440, 1040, 90, scallops=7), extras,
                  _parts(KNIGHT_CREST))


def build_figure(dims):
    """A plain human figure (the toolbar's human) to pose and sculpt."""
    p = dict(FIGURE_SIZES.get(dims.get("_size", ""), FIGURE_SIZES["Man"]))
    p.update({k: v for k, v in dims.items()
              if not k.startswith("_") and v is not None})
    return CadNode("human", "Human figure", dict(
        gender=p["gender"], age=p["age"], weight=p["weight"],
        height=p["height"], stature=p["stature"], targets=[], warp=[],
        warp_radius=45.0, pose=[]))


FIGURE_SIZES = {
    "Man": dict(gender=1.0, age=0.3, weight=0.0, height=0.2,
                stature=1780.0),
    "Woman": dict(gender=0.0, age=0.3, weight=0.0, height=0.1,
                  stature=1650.0),
    "Senior": dict(gender=1.0, age=1.0, weight=0.3, height=0.0,
                   stature=1720.0),
}


def _spec(label, build, sizes=None, fields=()):
    return dict(label=label, category=CATEGORY, build=build,
                sizes=sizes or {"Standard": {}}, fields=list(fields))


PARTS = {
    "person_figure": _spec("Human figure (to pose and sculpt)",
                           build_figure, FIGURE_SIZES,
                           [("stature", "Height"), ("gender", "Gender 0-1"),
                            ("age", "Age 0-1"), ("weight", "Weight -1..1")]),
    "person_man": _spec("Man (everyday clothes)",
                        lambda dims: _preset("Casual man")),
    "person_woman": _spec("Woman (everyday clothes)",
                          lambda dims: _preset("Casual woman")),
    "person_hero": _spec("Caped superhero", build_hero),
    "person_knight": _spec("Dark knight", build_knight),
}


def _preset(name):
    from . import human_design
    return human_design.build({"preset": name})


def _slug(name):
    return "person_" + "".join(c if c.isalnum() else "_"
                               for c in name.lower()).strip("_")


def _add_presets():
    from . import human_design
    for name in human_design.PRESETS:
        if name in ("Casual man", "Casual woman"):
            continue
        PARTS[_slug(name)] = _spec(name, lambda dims, n=name: _preset(n))


_add_presets()


if __name__ == "__main__":
    write_pngs()
    print("wrote", ", ".join(sorted(RULES)), "to", FOLDER)
