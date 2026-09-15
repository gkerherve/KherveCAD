"""Prusa pieces for the parts library: a little Prusa man — a chibi
figure in the spirit of the "Little Josef Prusa" character (big head,
glasses, beard, orange T-shirt) — and an Original Prusa MINI+ printer
at its real size (380 × 330 × 380 mm: a single Z column on the left,
the X arm cantilevered over a 180 mm bed that slides front to back,
orange printed parts, the display at the front), printing a little
Prusa man of its own.

Both are modelled from scratch here — nothing is taken from someone
else's files — out of ellipsoids, capsules, rounded boxes and discs,
with NO booleans, facing -Y and standing on z = 0.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from .library_home import BRASS, CHROME, _box, _cyl, _paint, _pick, _rod
from .library_home_more import _disc_y
from .library_room import _dims
from .model import CadNode

CATEGORY = "Prusa"

PRUSA_ORANGE = "#fa6831"
SHIRTS = {"Prusa orange": PRUSA_ORANGE, "Black": "#2a2c30",
          "White": "#f1efea", "Navy": "#34496b"}
ACCENTS = {"Prusa orange": PRUSA_ORANGE, "Black": "#2a2c30",
           "Blue": "#2e6fb5"}
SKIN = "#e8b596"
HAIR = "#3b2a20"
JEANS = "#2f3f5c"
SHOE = "#1d1e21"
FRAME = "#2b2d31"
ALU = "#b9bec6"
PEI = "#c9a45a"
SCREEN = "#1d2530"
LENS = "#dfe6ea"


def _ell(name, x, y, z, rx, ry, rz, color, seg=32):
    return _paint(CadNode("ellipsoid", name, dict(
        x=x, y=y, z=z, rx=rx, ry=ry, rz=rz, segments=seg)), color)


def _scaled(node, s, name):
    """*node* scaled by *s* about the origin (its feet stay on z = 0)."""
    if abs(s - 1.0) < 1e-9:
        return node
    wrap = CadNode("scale", name, dict(x=s, y=s, z=s))
    wrap.add(node)
    return wrap


# ------------------------------------------------------- little Prusa man

def _prusa_man_100(shirt):
    """The figure at 100 mm tall, facing -Y."""
    part = CadNode("union", "Prusa man")
    for sx in (-1, 1):
        x = sx * 8.5
        part.add(_box("Shoe", x - 6, -11.0, 0.0, 12, 18, 7, SHOE, r=3))
        part.add(_rod("Leg", (x, 0.0, 9.0), (x, 0.0, 28.0), 6.0, JEANS,
                      "Default"))
        # arms: an orange sleeve, then the forearm and the hand
        part.add(_rod("Sleeve", (sx * 14.0, 0.0, 52.0),
                      (sx * 20.0, -1.0, 44.0), 5.5, shirt, "Default"))
        part.add(_rod("Forearm", (sx * 20.5, -1.0, 43.0),
                      (sx * 22.0, -4.0, 34.0), 4.2, SKIN, "Default"))
        part.add(_ell("Hand", sx * 22.0, -4.5, 31.0, 5.0, 4.5, 5.5, SKIN))
        part.add(_ell("Ear", sx * 18.8, -1.0, 76.0, 2.5, 4.0, 5.0, SKIN))
    part.add(_ell("Hips", 0.0, 0.0, 31.0, 15.0, 9.5, 7.5, JEANS))
    part.add(_ell("T-shirt", 0.0, 0.0, 45.0, 16.0, 11.0, 15.0, shirt))
    part.add(_cyl("Neck", 0.0, 0.0, 56.0, 5, 5.5, SKIN, seg=24))
    # the head: big, as a chibi's is — the beard and the hair are
    # ellipsoids pushed forward under the chin and back over the crown
    part.add(_ell("Head", 0.0, 0.0, 76.0, 19.0, 17.0, 20.0, SKIN))
    part.add(_ell("Beard", 0.0, -5.5, 66.0, 16.0, 12.5, 10.5, HAIR))
    part.add(_ell("Hair", 0.0, 2.5, 84.0, 20.0, 18.0, 14.0, HAIR))
    part.add(_ell("Nose", 0.0, -17.6, 73.5, 2.6, 3.0, 3.2, SKIN))
    part.add(_ell("Mouth", 0.0, -16.2, 67.5, 4.0, 1.5, 1.2, "#8a4b3b"))
    for sx in (-1, 1):
        x = sx * 7.0
        # glasses: a dark rim behind a clear lens, the eye between
        part.add(_disc_y("Glasses rim", x, -15.8, 78.0, 6.4, 1.2, FRAME))
        part.add(_ell("Eye", x, -17.0, 78.0, 1.7, 1.2, 1.9, "#1b1c1f"))
        part.add(_disc_y("Lens", x, -18.2, 78.0, 5.6, 0.8, LENS, "Glass",
                         alpha=0.15))            # the eyes show through
        part.add(_rod("Temple", (sx * 12.8, -17.0, 79.0),
                      (sx * 18.6, -4.0, 80.0), 0.8, FRAME, "Default"))
    part.add(_rod("Bridge", (-1.8, -18.3, 78.6), (1.8, -18.3, 78.6), 0.8,
                  FRAME, "Default"))
    return part


def build_prusa_man(dims):
    p = _dims(dims, MAN_SIZES)
    shirt = _pick(dims, SHIRTS, "Prusa orange")
    return _scaled(_prusa_man_100(shirt), p["h"] / 100.0, "Prusa man")


# ----------------------------------------------------- Prusa MINI+

def _prusa_mini_full(accent):
    """The MINI+ at 1:1, centred, facing -Y: 380 wide, 330 deep, 380
    tall."""
    part = CadNode("union", "Prusa MINI+")
    for sx in (-1, 1):
        for sy in (-1, 1):
            part.add(_cyl("Foot", sx * 160.0, sy * 130.0, 0.0, 8, 12,
                          "#111214", seg=24))
    part.add(_box("Base", -180.0, -150.0, 8.0, 360, 300, 50, FRAME, r=6,
                  material="Metal"))
    part.add(_box("Power supply", -70.0, 150.0, 8.0, 140, 15, 45,
                  "#3a3d42"))
    # the display at the front left, its knob orange
    part.add(_box("Display", -178.0, -165.0, 15.0, 110, 18, 55, FRAME, r=4))
    part.add(_box("Screen", -170.0, -167.0, 25.0, 70, 2, 38, SCREEN))
    part.add(_disc_y("Knob", -85.0, -165.0, 42.0, 12, 8, accent))
    # Y axis: two rods and the bed sliding on them
    for x in (-30.0, 100.0):
        part.add(_rod("Y rod", (x, -140.0, 62.0), (x, 140.0, 62.0), 4,
                      CHROME))
    part.add(_box("Bed carriage", -65.0, -110.0, 66.0, 200, 220, 6, FRAME))
    part.add(_box("Heatbed", -65.0, -100.0, 72.0, 200, 200, 4, ALU,
                  material="Metal"))
    part.add(_box("PEI sheet", -60.0, -95.0, 76.0, 190, 190, 1.2, PEI,
                  material="Metal"))
    # the Z column on the left, its cap and the carriage riding on it
    part.add(_box("Z column", -190.0, -20.0, 58.0, 40, 40, 312, FRAME,
                  material="Metal"))
    part.add(_box("Z cap", -195.0, -25.0, 370.0, 50, 50, 10, accent, r=3))
    part.add(_box("Z carriage", -150.0, -35.0, 175.0, 40, 70, 55, accent,
                  r=4))
    # the X arm cantilevered to the right, the print head on it
    for z in (190.0, 215.0):
        part.add(_rod("X rod", (-110.0, -12.0, z), (170.0, -12.0, z), 4,
                      CHROME))
    part.add(_box("X end", 165.0, -25.0, 180.0, 25, 40, 45, accent, r=4))
    part.add(_box("Print head", 10.0, -45.0, 105.0, 50, 50, 100, accent,
                  r=6))
    part.add(_disc_y("Fan", 35.0, -45.0, 160.0, 18, 3, FRAME))
    part.add(_box("Heater block", 27.0, -8.0, 90.0, 16, 16, 15, ALU,
                  material="Metal"))
    part.add(_cyl("Nozzle", 35.0, 0.0, 78.0, 12, 1.2, BRASS, r2=5, seg=16,
                  material="Metal"))
    # ...printing a little Prusa man, 40 mm tall, on the bed
    print_ = CadNode("translate", "Print", dict(x=-25.0, y=10.0, z=77.2))
    print_.add(_scaled(_prusa_man_100(PRUSA_ORANGE), 0.4, "Printed figure"))
    part.add(print_)
    return part


def build_prusa_mini(dims):
    p = _dims(dims, MINI_SIZES)
    accent = _pick(dims, ACCENTS, "Prusa orange")
    return _scaled(_prusa_mini_full(accent), p["scale"], "Prusa MINI+")


# --------------------------------------------------------------- registry

MAN_SIZES = {"Figure (100 mm)": dict(h=100.0),
             "Desk figure (180 mm)": dict(h=180.0)}
MINI_SIZES = {"Real size (1:1)": dict(scale=1.0),
              "Desk model (1:4)": dict(scale=0.25)}

PARTS = {
    "prusa_man": dict(label="Little Prusa man", category=CATEGORY,
                      sizes=MAN_SIZES, build=build_prusa_man,
                      fields=[("h", "Height")], colors=list(SHIRTS)),
    "prusa_mini": dict(label="Prusa MINI+ printer", category=CATEGORY,
                       sizes=MINI_SIZES, build=build_prusa_mini,
                       fields=[("scale", "Scale")], colors=list(ACCENTS)),
}
