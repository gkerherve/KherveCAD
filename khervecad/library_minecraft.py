"""Minecraft characters and mobs for the parts library: Steve, Alex,
Zombie, Skeleton, Wither skeleton, Creeper, Enderman, Spider, Iron
golem, Snow golem, Slime, Ghast, Blaze, Chicken and Sheep.

Each is built in Minecraft PIXELS (a block is 16) from coloured boxes
at the game's own proportions — the 8x8x8 head, 8x4x12 body, 4x4x12
limbs — and scaled by the size's pixel length. Faces are pixel art
(`_face`): rows of letters laid on the front of the head as thin
tiles, one tile per horizontal run of a colour. Nothing is booleaned;
every mob faces -Y and stands on z = 0.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .library_home import _box
from .library_room import _dims
from .model import CadNode

CATEGORY = "Minecraft"

#: how thick a face tile stands proud of the head, in pixels
TILE = 0.3


class _Mob:
    """Boxes in pixels, gathered under one group."""

    def __init__(self, name):
        self.root = CadNode("union", name)

    def box(self, name, x, y, z, w, d, h, color, alpha=1.0):
        """A box from its low corner, all in pixels."""
        self.root.add(_box(name, x, y, z, w, d, h, color, alpha=alpha))

    def turned(self, name, pivot, angles, pieces):
        """*pieces* (a list of box argument tuples, relative to *pivot*)
        rotated by *angles* about *pivot*."""
        mv = CadNode("translate", name, dict(
            x=pivot[0], y=pivot[1], z=pivot[2]))
        rot = CadNode("rotate", name, dict(
            x=angles[0], y=angles[1], z=angles[2]))
        for args in pieces:
            rot.add(_box(*args))
        mv.add(rot)
        self.root.add(mv)

    def face(self, rows, palette, x0, y, z_top, name="Face"):
        """Pixel art on a -Y facing plane at *y*: *rows* top down, one
        letter a pixel ('.' = none), letters looked up in *palette*."""
        for i, row in enumerate(rows):
            j = 0
            while j < len(row):
                ch = row[j]
                k = j
                while k < len(row) and row[k] == ch:
                    k += 1
                if ch != ".":
                    self.box(name, x0 + j, y - TILE, z_top - i - 1,
                             k - j, TILE, 1, palette[ch])
                j = k

    def build(self, px):
        wrap = CadNode("scale", self.root.name, dict(x=px, y=px, z=px))
        wrap.add(self.root)
        return wrap


# ------------------------------------------------------------ humanoids

STEVE_FACE = ["HHHHHHHH",
              "HHHHHHHH",
              "HSSSSSSH",
              "SSSSSSSS",
              "SWBSSBWS",
              "SSSNNSSS",
              "SSMSSMSS",
              "SSMMMMSS"]


def _biped(m, skin, shirt, pants, shoes, hair, face, palette, arm_w=4,
           arms_forward=False, sleeve=None):
    """The player-model body: legs, torso, arms and an 8x8x8 head."""
    m.box("Left leg", 0, -2, 0, 4, 4, 12, pants)
    m.box("Right leg", -4, -2, 0, 4, 4, 12, pants)
    if shoes:
        m.box("Left shoe", 0, -2, 0, 4, 4, 2, shoes)
        m.box("Right shoe", -4, -2, 0, 4, 4, 2, shoes)
    m.box("Body", -4, -2, 12, 8, 4, 12, shirt)
    for side, x in (("Left", 4), ("Right", -4 - arm_w)):
        if arms_forward:
            m.box(f"{side} arm", x, -12, 20, arm_w, 12, 4, skin)
            m.box(f"{side} sleeve", x, -2, 20, arm_w, 4, 4, sleeve or shirt)
        else:
            m.box(f"{side} arm", x, -2, 12, arm_w, 4, 12, skin)
            m.box(f"{side} sleeve", x, -2, 20, arm_w, 4, 4, sleeve or shirt)
    m.box("Head", -4, -4, 24, 8, 8, 8, skin)
    if hair:
        m.box("Hair", -4.1, -4.1, 30, 8.2, 8.2, 2.1, hair)
        m.box("Back hair", -4.1, 2, 25, 8.2, 2.1, 7, hair)
    m.face(face, palette, -4, -4, 32)


def steve():
    m = _Mob("Steve")
    pal = dict(H="#2f1f10", S="#b58a6b", W="#ffffff", B="#523d89",
               N="#8a5a40", M="#6a4030")
    _biped(m, "#b58a6b", "#00a8a8", "#3b3a9a", "#555555", "#2f1f10",
           STEVE_FACE, pal)
    return m


def alex():
    m = _Mob("Alex")
    pal = dict(H="#e07b25", S="#f0c8a0", W="#ffffff", B="#3b8a3a",
               N="#f0c8a0", M="#d9a080")
    face = ["HHHHHHHH", "HHHHHHHH", "HSSSSSHH", "SSSSSSSH",
            "SWBSSBWH", "SSSSSSSH", "SSSMMSSH", "SSSSSSSS"]
    _biped(m, "#f0c8a0", "#6fa84a", "#6b4a2a", "#4a3a2a", "#e07b25",
           face, pal, arm_w=3)
    m.box("Ponytail", -2, 4, 22, 4, 1.5, 8, "#e07b25")
    return m


def zombie():
    m = _Mob("Zombie")
    green = "#5a8f3c"
    pal = dict(H="#3f6b2a", S=green, W="#1f3316", B="#101010",
               N="#3f6b2a", M="#2c4a1e")
    face = ["HHHHHHHH", "SSSSSSSS", "SSSSSSSS", "SBBSSBBS",
            "SSSNNSSS", "SSSSSSSS", "SSMMMMSS", "SSSSSSSS"]
    _biped(m, green, "#1f9a9a", "#3b3a9a", None, None, face, pal,
           arms_forward=True)
    return m


def _skeleton(name, bone, dark, px_scale=1.0):
    m = _Mob(name)
    s = px_scale
    m.box("Left leg", 1 * s, -1 * s, 0, 2 * s, 2 * s, 12 * s, bone)
    m.box("Right leg", -3 * s, -1 * s, 0, 2 * s, 2 * s, 12 * s, bone)
    m.box("Pelvis", -4 * s, -1.5 * s, 12 * s, 8 * s, 3 * s, 2 * s, bone)
    m.box("Spine", -1 * s, -1 * s, 14 * s, 2 * s, 2 * s, 10 * s, bone)
    for k in range(4):
        m.box("Rib", -4 * s, -2 * s, (15 + 2.2 * k) * s,
              8 * s, 4 * s, 1 * s, bone)
    m.box("Left arm", 4 * s, -1 * s, 12 * s, 2 * s, 2 * s, 12 * s, bone)
    m.box("Right arm", -6 * s, -1 * s, 12 * s, 2 * s, 2 * s, 12 * s, bone)
    m.box("Head", -4 * s, -4 * s, 24 * s, 8 * s, 8 * s, 8 * s, bone)
    rows = ["........", "........", "........", ".DD..DD.",
            ".DD..DD.", "...DD...", ".DDDDDD.", "........"]
    if s == 1.0:
        m.face(rows, dict(D=dark), -4, -4, 32)
    else:
        sub = _Mob("Face")
        sub.face(rows, dict(D=dark), -4, -4, 32)
        m.root.add(sub.build(s))
    return m


def skeleton():
    return _skeleton("Skeleton", "#c9c9c9", "#3a3a3a")


def wither_skeleton():
    return _skeleton("Wither skeleton", "#2b2b2b", "#0c0c0c", 1.2)


def enderman():
    m = _Mob("Enderman")
    black, purple = "#161616", "#cc3fe8"
    m.box("Left leg", 1, -1, 0, 2, 2, 30, black)
    m.box("Right leg", -3, -1, 0, 2, 2, 30, black)
    m.box("Body", -4, -2, 30, 8, 4, 12, black)
    m.box("Left arm", 4, -1, 12, 2, 2, 30, black)
    m.box("Right arm", -6, -1, 12, 2, 2, 30, black)
    m.box("Head", -4, -4, 42, 8, 8, 8, black)
    m.face(["........", "........", "........", "........",
            "PPP..PPP", "........", "........", "........"],
           dict(P=purple), -4, -4, 50, "Eyes")
    return m


def creeper():
    m = _Mob("Creeper")
    greens = ["#4fa83a", "#6cc24a", "#3c8a2c", "#8fd46a"]
    for name, x, y in (("Front left foot", 0, -6), ("Front right foot", -4, -6),
                       ("Back left foot", 0, 2), ("Back right foot", -4, 2)):
        m.box(name, x, y, 0, 4, 4, 6, greens[0])
    m.box("Body", -4, -2, 6, 8, 4, 12, greens[1])
    m.box("Head", -4, -4, 18, 8, 8, 8, greens[0])
    # the mottled skin, seeded by position so it never changes
    for i in range(6):
        for j in range(3):
            if (i * 7 + j * 3) % 4 == 0:
                m.box("Mottle", -4 + (i * 5 + j) % 7, -2 - TILE,
                      7 + i * 2, 1, TILE, 1, greens[2 + (i + j) % 2])
    m.face(["........", "........", ".BB..BB.", ".BB..BB.",
            "...BB...", "..BBBB..", "..BBBB..", "..B..B.."],
           dict(B="#0f1a0c"), -4, -4, 26)
    return m


# ----------------------------------------------------------- large mobs

def spider():
    m = _Mob("Spider")
    dark, red = "#3a322c", "#d01818"
    m.box("Abdomen", -5, 3, 4, 10, 12, 8, dark)
    m.box("Thorax", -3, -3, 5, 6, 6, 6, "#2c2520")
    m.box("Head", -4, -11, 4, 8, 8, 8, dark)
    m.face(["........", "RR....RR", ".RR..RR.", "........",
            "........", "........", "........", "........"],
           dict(R=red), -4, -11, 12, "Eyes")
    for k, y in enumerate((-2.5, -0.5, 1.5, 3.5)):
        spread = (-30, -10, 10, 30)[k]
        for side, sign in (("left", 1), ("right", -1)):
            # a 16 px leg from the thorax, sloping down 30° to the floor
            m.turned(f"Leg {k + 1} {side}", (sign * 3, y, 8.866),
                     (0, sign * 30, sign * spread),
                     [(f"Leg {k + 1} {side}", 0 if sign > 0 else -16,
                       -1, -1, 16, 2, 2, dark)])
    return m


def iron_golem():
    m = _Mob("Iron golem")
    iron, dark, vine = "#d9d2c6", "#b7ada0", "#4f8a2a"
    m.box("Left leg", 1, -2.5, 0, 6, 5, 16, iron)
    m.box("Right leg", -7, -2.5, 0, 6, 5, 16, iron)
    m.box("Waist", -4.5, -3, 16, 9, 6, 5, iron)
    m.box("Chest", -9, -5.5, 21, 18, 11, 12, iron)
    m.box("Left arm", 9, -3, 3, 4, 6, 30, dark)
    m.box("Right arm", -13, -3, 3, 4, 6, 30, dark)
    m.box("Head", -4, -7.5, 29, 8, 10, 10, iron)
    m.box("Nose", -1, -9.5, 31, 2, 2, 4, dark)
    m.face(["........", "........", "........", "BRR..RRB",
            "........", "........"],
           dict(R="#b02020", B="#5a4f45"), -4, -7.5, 37, "Eyes")
    for x, z, h in ((-7, 23, 9), (3, 14, 7), (10, 10, 12), (-12, 18, 8)):
        m.box("Vine", x, -5.9 if abs(x) < 9 else -3.4, z, 1, 0.4, h, vine)
    return m


def snow_golem():
    m = _Mob("Snow golem")
    snow, stick = "#f4f8fa", "#6b4a2a"
    m.box("Lower snowball", -6, -6, 0, 12, 12, 12, snow)
    m.box("Upper snowball", -5, -5, 12, 10, 10, 10, snow)
    m.box("Pumpkin", -4, -4, 22, 8, 8, 8, "#e38a1d")
    m.box("Stalk", -1, -1, 30, 2, 2, 1.5, "#5a7a2a")
    m.face(["........", "........", ".BB..BB.", ".BB..BB.",
            "........", ".BBBBBB.", "..B..B..", "........"],
           dict(B="#3a1e05"), -4, -4, 30, "Carved face")
    m.turned("Left arm", (5, 0, 19), (0, -35, 0),
             [("Left arm", 0, -0.5, -0.5, 10, 1, 1, stick)])
    m.turned("Right arm", (-5, 0, 19), (0, 35, 0),
             [("Right arm", -10, -0.5, -0.5, 10, 1, 1, stick)])
    return m


def slime():
    m = _Mob("Slime")
    m.box("Core", -3, -3, 1, 6, 6, 6, "#5fae3e")
    m.face(["........", "........", "BB...BB.", "BB...BB.",
            "........", ".....B..", "........"],
           dict(B="#1f3d14"), -4, -3, 8, "Face")
    m.box("Outer jelly", -4, -4, 0, 8, 8, 8, "#7ccf5a", alpha=0.55)
    return m


def ghast():
    m = _Mob("Ghast")
    white, grey = "#f0f0f0", "#b8b8b8"
    m.box("Body", -8, -8, 14, 16, 16, 16, white)
    lengths = (12, 14, 10, 13, 9, 14, 11, 12, 10)
    for k, h in enumerate(lengths):
        i, j = divmod(k, 3)
        m.box("Tentacle", -6 + j * 5, -6 + i * 5, 14 - h, 2, 2, h, white)
    m.face(["................", "................", "................",
            "................", "..GG........GG..", "..GG........GG..",
            "................", "................", ".....GGGGGG.....",
            ".....GGGGGG.....", "................"],
           dict(G=grey), -8, -8, 30, "Face")
    return m


def blaze():
    m = _Mob("Blaze")
    yellow, rod, smoke = "#f6c33a", "#e89a1e", "#6b5a44"
    m.box("Smoke column", -1, -1, 0, 2, 2, 22, smoke, alpha=0.6)
    m.box("Head", -4, -4, 22, 8, 8, 8, yellow)
    m.face(["........", "........", "........", ".BB..BB.",
            "........", "..BBBB..", "........", "........"],
           dict(B="#3a2508"), -4, -4, 30, "Face")
    for ring, (r, z, count) in enumerate(((9, 14, 4), (7, 7, 4), (5, 1, 4))):
        for k in range(count):
            a = math.radians(360.0 * k / count + 45 * ring)
            m.box("Rod", r * math.cos(a) - 1, r * math.sin(a) - 1, z,
                  2, 2, 8, rod)
    return m


# ------------------------------------------------------ passive animals

def chicken():
    m = _Mob("Chicken")
    white, yellow, red = "#f5f5f0", "#e8a922", "#d02020"
    for side, x in (("Left", 0.5), ("Right", -2.5)):
        m.box(f"{side} leg", x, -0.5, 0, 2, 1, 5, yellow)
        m.box(f"{side} foot", x - 0.5, -2.5, 0, 3, 3, 0.5, yellow)
    m.box("Body", -3, -4, 5, 6, 8, 6, white)
    m.box("Left wing", 3, -3, 6, 1, 6, 4, white)
    m.box("Right wing", -4, -3, 6, 1, 6, 4, white)
    m.box("Head", -2, -6, 9, 4, 3, 6, white)
    m.box("Beak", -2, -8, 12, 4, 2, 2, yellow)
    m.box("Wattle", -1, -7, 10, 2, 1, 2, red)
    m.face(["......", "B..B.."], dict(B="#101010"), -2, -6, 15, "Eyes")
    return m


def sheep():
    m = _Mob("Sheep")
    wool, skin = "#e9e9e9", "#c7a88f"
    for name, x, y in (("Front left leg", 0.5, -6), ("Front right leg", -4.5, -6),
                       ("Back left leg", 0.5, 4), ("Back right leg", -4.5, 4)):
        m.box(name, x, y, 0, 4, 4, 12, skin)
        m.box(name + " wool", x - 0.5, y - 0.5, 6, 5, 5, 6, wool)
    m.box("Body", -5, -8, 11, 10, 18, 9, wool)
    m.box("Head", -3, -14, 15, 6, 8, 6, skin)
    m.box("Head wool", -3.5, -12, 15.5, 7, 6, 6, wool)
    m.face(["......", "......", "WB..BW", "......", "..NN..", "......"],
           dict(W="#ffffff", B="#101010", N="#e9a0a0"), -3, -14, 21, "Face")
    return m


# ------------------------------------------------------------- registry

MOBS = {
    "mc_steve": ("Steve", steve),
    "mc_alex": ("Alex", alex),
    "mc_zombie": ("Zombie", zombie),
    "mc_skeleton": ("Skeleton", skeleton),
    "mc_wither_skeleton": ("Wither skeleton", wither_skeleton),
    "mc_creeper": ("Creeper", creeper),
    "mc_enderman": ("Enderman", enderman),
    "mc_spider": ("Spider", spider),
    "mc_iron_golem": ("Iron golem", iron_golem),
    "mc_snow_golem": ("Snow golem", snow_golem),
    "mc_slime": ("Slime", slime),
    "mc_ghast": ("Ghast", ghast),
    "mc_blaze": ("Blaze", blaze),
    "mc_chicken": ("Chicken", chicken),
    "mc_sheep": ("Sheep", sheep),
}

SIZES = {"Figure (1 px = 5 mm)": dict(px=5.0),
         "Small (1 px = 2.5 mm)": dict(px=2.5),
         "Large (1 px = 10 mm)": dict(px=10.0),
         "Game size (1 block = 1 m)": dict(px=62.5)}


def _builder(maker):
    def build(dims):
        p = _dims(dims, SIZES)
        return maker().build(float(p["px"]))
    return build


PARTS = {
    part_id: dict(label=label, category=CATEGORY, sizes=SIZES,
                  fields=[("px", "Pixel size")], build=_builder(maker))
    for part_id, (label, maker) in MOBS.items()
}
