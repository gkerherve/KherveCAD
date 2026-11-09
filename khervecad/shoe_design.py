"""The **Shoe Builder**'s model (Qt-free): a spec of choices -> an
OpenSCAD program -> one Object.

Every shoe stands on ONE last: stations along the foot (`X`, toe at
x = 0, the heel seat a half circle about x = 217), and at each station
a half width (the toe shape, `WIDTHS`), an upper height (`UPPERS`) and
a sole height. The upper is a chain of hulled cross-sections (straight
sides rolling into a domed top) minus the same chain a wall in, whose
top is opened after the upper's `openx`, so a pump is a closed toe box
with side walls and a loafer is closed over the instep. The sole is a
chain of planks across the foot, so it follows the upper's outline; a
thin sole rises with the heel height (a half cosine from the ball to
the seat), a thick sole (cupsole, runner, vulcanised, lug) has its own
toe spring and heel drop. Heels: a stiletto as wide as the seat at the
top curving down to a pin (optionally ending in a devil-tail arrow), a
block, a wedge under the arch. Extras: heel cup, boot shaft, high-top
collar, sandal straps, laces, heel tab, rubber toe cap, tread and an
ORIGINAL side wave (never a brand's mark).

Size: EU size -> length (EU x 2/3 cm), the last scaled in x and y only
— heel heights stay what they say. Men's lasts are 4 % wider.

Everything is generated as plain OpenSCAD (modules with arguments,
literal arrays — the preview cannot evaluate user functions inside
placements) and parsed by `scadparse`, so the result is an ordinary
editable tree, and the spec rides on the Object as
``params["shoe"]`` so the builder can update it.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import copy
import math

X = [0, 6, 14, 24, 38, 52, 64, 76, 88, 102, 118, 135, 150, 165, 180, 195,
     207, 217]
BASE_LENGTH = 241.5          # the last's own length: EU 37

WIDTHS = {
    "Pointed": [2, 9, 16, 23, 31, 35, 36.5, 37, 35.5, 33, 30, 28, 27, 26,
                25.5, 25, 25, 24.5],
    "Round": [12, 20, 26, 30, 34, 36, 37, 37.5, 36, 33.5, 30.5, 28.5, 27.5,
              26.5, 26, 25.5, 25, 24.5],
    "Square": [24, 27, 30, 32, 34.5, 36, 37, 37.5, 36, 33.5, 30.5, 28.5,
               27.5, 26.5, 26, 25.5, 25, 24.5],
}

# upper: heights, where the top opens, and what goes with it
UPPERS = {
    "Pump": dict(h=[5, 10, 16, 22, 31, 37, 42, 46, 40, 34, 31, 30, 31, 33,
                    38, 45, 52, 58], openx=80, cup=(39, 50)),
    "Ballet flat": dict(h=[12, 17, 22, 27, 32, 36, 39, 40, 34, 28, 25, 25,
                           26, 28, 32, 38, 44, 48], openx=70, cup=(22, 30)),
    "Loafer": dict(h=[14, 19, 25, 30, 36, 41, 45, 49, 53, 57, 60, 52, 44,
                      40, 40, 42, 46, 50], openx=130, cup=(40, 46)),
    "Oxford": dict(h=[12, 17, 22, 27, 32, 36, 40, 44, 48, 52, 56, 52, 46,
                      44, 44, 46, 50, 54], openx=128, cup=(44, 50),
                   laces=(9, 10, 4, 9), seams=True),
    "Sneaker": dict(h=[18, 24, 30, 35, 41, 45, 49, 53, 58, 63, 67, 64, 56,
                       52, 54, 58, 64, 68], openx=128, cup=(46, 52),
                    laces=(8, 10, 6, 11), tab=True),
    "High-top": dict(h=[18, 24, 30, 35, 41, 45, 49, 53, 58, 64, 70, 72, 70,
                        68, 70, 74, 78, 80], openx=125, collar=75,
                     laces=(8, 11, 7, 11)),
    "Ankle boot": dict(h=[14, 19, 25, 30, 36, 41, 45, 49, 53, 57, 60, 52,
                          44, 40, 40, 42, 46, 50], openx=150, shaft=95),
    "Work boot": dict(h=[14, 19, 25, 30, 36, 41, 45, 49, 53, 57, 60, 52,
                         44, 40, 40, 42, 46, 50], openx=150, shaft=120,
                      laces=(8, 10, 4, 12), shaft_laces=7),
    "Sandal": dict(h=[12, 17, 22, 27, 32, 36, 39, 40, 34, 28, 25, 25, 26,
                      28, 32, 38, 44, 48], openx=0, cup=(18, 22),
                   straps=True),
}

# soles: thickness at the front and back, toe spring, a rubber layer,
# tread lugs. "Thin" rises with the heel height instead.
SOLES = {
    "Thin": dict(thin=True),
    "Leather": dict(front=5, back=25, spring=6, waist=True),
    "Cupsole": dict(front=12, back=20, spring=9, rubber=True, tread=10),
    "Runner": dict(front=12, back=30, spring=10, rubber=True, tread=12),
    "Vulcanised": dict(front=8, back=10, spring=5, foxing=True),
    "Lug": dict(front=16, back=28, spring=10, rubber=True, tread=8),
}
HEELS = ("Stiletto", "Block", "Wedge", "None")
DECORATIONS = ("None", "Wave", "Double wave", "Stripe")
GENDERS = ("Women", "Men")

COLOURS = {
    "Red": "#d1001c", "Black": "#141414", "White": "#f4f4f2",
    "Off-white": "#f5f3ea", "Nude": "#d8c3a5", "Tan": "#c9a37b",
    "Brown": "#6b3f22", "Dark brown": "#3b2416", "Cognac": "#8a5a2b",
    "Navy": "#1d3557", "Blue": "#1f4e9c", "Pink": "#e9a7b5",
    "Green": "#1f6b3a", "Lime": "#c8ff00", "Charcoal": "#2b2f38",
    "Grey": "#9a9a90", "Gum": "#a0682e", "Cork": "#c9a06a",
    "Gold": "#c9a227", "Silver": "#c0c4c8", "Burgundy": "#5a0009",
}

DEFAULTS = dict(
    name="Shoe", gender="Women", size=38, toe="Round", upper="Pump",
    sole="Thin", heel="Stiletto", heel_height=90.0, arrow=False,
    decoration="None", pair=False,
    upper_colour="Black", lining_colour="Nude", sole_colour="Black",
    heel_colour="", accent_colour="Red", lace_colour="",
)

PRESETS = {
    "Devil arrow pump": dict(toe="Pointed", upper="Pump", heel="Stiletto",
                             heel_height=110, arrow=True,
                             upper_colour="Red", lining_colour="Black",
                             sole_colour="Burgundy"),
    "Classic black pump": dict(toe="Round", upper="Pump",
                               heel_height=90, upper_colour="Black",
                               lining_colour="Tan"),
    "Kitten heel pump": dict(toe="Pointed", upper="Pump", heel_height=45,
                             upper_colour="Blue", lining_colour="Nude"),
    "Block-heel ankle boot": dict(upper="Ankle boot", heel="Block",
                                  heel_height=75, upper_colour="Brown",
                                  lining_colour="Nude",
                                  sole_colour="Dark brown"),
    "Cork wedge sandal": dict(upper="Sandal", heel="Wedge",
                              heel_height=90, upper_colour="Off-white",
                              heel_colour="Cork", sole_colour="Dark brown"),
    "Square-toe loafer": dict(toe="Square", upper="Loafer", heel="Block",
                              heel_height=25, upper_colour="Brown",
                              sole_colour="Dark brown"),
    "Ballet flat": dict(upper="Ballet flat", heel="None", heel_height=0,
                        upper_colour="Pink", lining_colour="Nude"),
    "Tennis sneaker": dict(gender="Men", size=43, upper="Sneaker",
                           sole="Cupsole", upper_colour="White",
                           sole_colour="White", accent_colour="Navy"),
    "Oxford dress shoe": dict(gender="Men", size=43, upper="Oxford",
                              sole="Leather", upper_colour="Black",
                              sole_colour="Dark brown",
                              lining_colour="Tan"),
    "Work boot": dict(gender="Men", size=43, upper="Work boot",
                      sole="Lug", upper_colour="Cognac",
                      sole_colour="Black", accent_colour="Dark brown"),
    "Running shoe": dict(gender="Men", size=43, upper="Sneaker",
                         sole="Runner", upper_colour="Charcoal",
                         sole_colour="White", accent_colour="Lime",
                         decoration="Double wave"),
    "High-top basketball": dict(gender="Men", size=43, upper="High-top",
                                sole="Cupsole", upper_colour="White",
                                sole_colour="White", accent_colour="Red",
                                lace_colour="Black", decoration="Wave"),
    "Retro court shoe": dict(gender="Men", size=43, upper="Sneaker",
                             sole="Cupsole", upper_colour="Off-white",
                             sole_colour="Off-white", accent_colour="Green",
                             heel_colour="Gum"),
    "Canvas skate shoe": dict(gender="Men", size=43, upper="Sneaker",
                              sole="Vulcanised", upper_colour="Navy",
                              sole_colour="Off-white",
                              accent_colour="Red", lace_colour="Off-white",
                              decoration="Stripe"),
}


class SpecError(ValueError):
    """A choice the builder does not know."""


def colour(value, fallback="#888888") -> str:
    if not value:
        return fallback
    v = str(value).strip()
    if v.startswith("#") and len(v) in (4, 7):
        return v
    for k, hexcol in COLOURS.items():
        if k.lower() == v.lower():
            return hexcol
    raise SpecError(f"unknown colour {value!r}")


def _pick(value, choices, key):
    for c in choices:
        if str(c).lower() == str(value).lower():
            return c
    raise SpecError(f"unknown {key} {value!r}; one of {', '.join(choices)}")


def normalise(spec=None) -> dict:
    """Defaults < preset < the given keys, every choice checked."""
    spec = dict(spec or {})
    out = dict(DEFAULTS)
    preset = spec.pop("preset", None)
    if preset:
        name = _pick(preset, list(PRESETS), "preset")
        out.update(PRESETS[name])
        out["name"] = name
    for k, v in spec.items():
        if k not in DEFAULTS:
            raise SpecError(f"unknown key {k!r}")
        if v is not None:
            out[k] = v
    out["gender"] = _pick(out["gender"], GENDERS, "gender")
    out["toe"] = _pick(out["toe"], list(WIDTHS), "toe")
    out["upper"] = _pick(out["upper"], list(UPPERS), "upper")
    out["sole"] = _pick(out["sole"], list(SOLES), "sole")
    out["heel"] = _pick(out["heel"], HEELS, "heel")
    out["decoration"] = _pick(out["decoration"], DECORATIONS, "decoration")
    out["size"] = max(30.0, min(50.0, float(out["size"])))
    out["heel_height"] = max(0.0, min(160.0, float(out["heel_height"])))
    out["arrow"] = bool(out["arrow"])
    out["pair"] = bool(out["pair"])
    for k in ("upper_colour", "lining_colour", "sole_colour", "heel_colour",
              "accent_colour", "lace_colour"):
        colour(out[k], "#000000")            # raises on a bad name
    if not SOLES[out["sole"]].get("thin"):
        out["heel"] = "None" if out["heel"] in ("Stiletto", "Wedge") \
            else out["heel"]
    if out["heel"] == "None" and SOLES[out["sole"]].get("thin"):
        out["heel_height"] = 0.0
    return out


def length_mm(spec) -> float:
    """Shoe length for its EU size (Paris points: 2/3 cm)."""
    return float(spec["size"]) * 20.0 / 3.0 - 5.0


# --------------------------------------------------------------- profile
def _ease(x, x0, x1):
    if x <= x0:
        return 0.0
    if x >= x1:
        return 1.0
    return (1 - math.cos(math.pi * (x - x0) / (x1 - x0))) / 2


def profile(spec):
    """(Z sole top - sole_t, B underside, R rubber top, heel seat z) per
    station."""
    sole = SOLES[spec["sole"]]
    hh = spec["heel_height"] if spec["heel"] != "None" else 0.0
    if sole.get("thin"):
        z = [hh * _ease(x, 80, 207) for x in X]
        return z, [0.0] * len(X), None, hh
    front, back, spring = sole["front"], sole["back"], sole["spring"]
    lift = hh if spec["heel"] == "Block" else 0.0
    z, b = [], []
    for x in X:
        toe = spring * max(0.0, 1 - x / 40.0) ** 1.5
        top = front + (back - front) * _ease(x, 88, 200) + toe \
            + lift * _ease(x, 80, 207)
        under = toe
        if sole.get("waist"):                # leather sole: raised waist
            under = max(toe, (back - 5) * _ease(x, 95, 160)
                        * (1 - _ease(x, 165, 178)))
        z.append(top - 3.5)
        b.append(under)
    r = [bb + 3 - 3.5 for bb in b] if sole.get("rubber") else None
    return z, b, r, z[-1]


def _arr(values) -> str:
    return "[" + ", ".join(f"{v:.2f}".rstrip("0").rstrip(".") or "0"
                           for v in values) + "]"


# ----------------------------------------------------------- the library
LIB = r"""
module Sec(x, z, hw, h) {
  translate([x, 0, z]) rotate([90, 0, 90]) linear_extrude(height = 0.2)
    hull() {
      translate([-hw, 0]) square([2 * hw, 0.1]);
      translate([0, h * 0.45]) scale([hw, h * 0.55]) circle(r = 1, $fn = 40);
    }
}
module Plank(x, z, hw, t) { translate([x - 0.1, -hw, z]) cube([0.2, 2 * hw, t]); }
module Upper(X, Z, W, H, openx, st, wl) {
  difference() {
    for (i = [0:16]) hull() {
      Sec(X[i], Z[i] + st, W[i], H[i]);
      Sec(X[i + 1], Z[i + 1] + st, W[i + 1], H[i + 1]);
    }
    for (i = [0:16]) hull() {
      Sec(X[i] + (i == 0 ? 4 : 0), Z[i] + st + 0.01, W[i] - wl, X[i] > openx ? 300 : H[i] - wl);
      Sec(X[i + 1] + (i == 16 ? 2 : 0), Z[i + 1] + st + 0.01, W[i + 1] - wl, X[i + 1] > openx ? 300 : H[i + 1] - wl);
    }
  }
}
module Cup(hh, cs, cb, st, wl) {
  translate([217, 0, hh + st]) difference() {
    intersection() {
      cylinder(r = 24.5, h = cb + 10, $fn = 72);
      translate([0, -26, 0]) cube([26, 52, cb + 10]);
    }
    translate([0, 0, -1]) cylinder(r = 24.5 - wl, h = cb + 12, $fn = 72);
    translate([0, -60, cs]) rotate([0, -atan((cb - cs) / 24.5), 0]) translate([-30, 0, 0]) cube([120, 120, 200]);
  }
}
module Outsole(X, Z, W, hh, st) {
  for (i = [0:16]) hull() {
    Plank(X[i], Z[i], W[i] + 1.2, st);
    Plank(X[i + 1], Z[i + 1], W[i + 1] + 1.2, st);
  }
  for (a = [0:15:75]) hull() {
    Plank(217 + 24.5 * sin(a), hh, 24.5 * cos(a) + 1.2, st);
    Plank(217 + 24.5 * sin(a + 15), hh, 24.5 * cos(a + 15) + 1.2, st);
  }
}
module Thick_sole(X, Z, B, W, grow, st) {
  for (i = [0:16]) hull() {
    Plank(X[i], B[i], W[i] + grow, Z[i] + st - B[i]);
    Plank(X[i + 1], B[i + 1], W[i + 1] + grow, Z[i + 1] + st - B[i + 1]);
  }
  for (a = [0:15:75]) hull() {
    Plank(217 + 24.5 * sin(a), B[17], 24.5 * cos(a) + grow, Z[17] + st - B[17]);
    Plank(217 + 24.5 * sin(a + 15), B[17], 24.5 * cos(a + 15) + grow, Z[17] + st - B[17]);
  }
}
module Insole(X, Z, W, st, wl) {
  for (i = [1:16]) hull() {
    Plank(X[i], Z[i] + st, W[i] - wl - 0.4, 0.8);
    Plank(X[i + 1], Z[i + 1] + st, W[i + 1] - wl - 0.4, 0.8);
  }
  translate([217, 0, Z[17] + st]) intersection() {
    cylinder(r = 24.5 - wl - 0.4, h = 0.8, $fn = 72);
    translate([0, -30, 0]) cube([30, 60, 1]);
  }
}
module Stiletto(hh, ah) {
  for (i = [0:23]) {
    t0 = i / 24;
    t1 = (i + 1) / 24;
    rx0 = 2.6 + 9.9 * pow(1 - t0, 2);
    rx1 = 2.6 + 9.9 * pow(1 - t1, 2);
    ry0 = 2.6 + 20.9 * pow(1 - t0, 2.6);
    ry1 = 2.6 + 20.9 * pow(1 - t1, 2.6);
    z0 = hh - t0 * (hh - ah) - 0.5;
    z1 = hh - t1 * (hh - ah) - 0.5;
    hull() {
      translate([241.5 - 14 * pow(t0, 0.7) - rx0, 0, z0]) scale([rx0, ry0, 1]) cylinder(r = 1, h = 0.5, $fn = 40);
      translate([241.5 - 14 * pow(t1, 0.7) - rx1, 0, z1]) scale([rx1, ry1, 1]) cylinder(r = 1, h = 0.5, $fn = 40);
    }
  }
}
module Arrow(ah) {
  hull() {
    translate([224.9, 0, ah]) scale([12, 4, 1]) rotate([0, 0, 45]) cube([1.414, 1.414, 1.6], center = true);
    translate([224.9, 0, 0.4]) sphere(r = 0.4, $fn = 12);
  }
}
module Block(hh) {
  hull() {
    translate([229, 0, hh - 0.5]) scale([12, 21, 1]) cylinder(r = 1, h = 0.5, $fn = 48);
    translate([231, 0, 0]) scale([9.5, 14, 1]) cylinder(r = 1, h = 1, $fn = 48);
  }
}
module Wedge(X, Z, W, hh) {
  for (i = [7:16]) hull() {
    Plank(X[i], 0, W[i] + 1.2, Z[i] + 0.1);
    Plank(X[i + 1], 0, W[i + 1] + 1.2, Z[i + 1] + 0.1);
  }
  for (a = [0:15:75]) hull() {
    Plank(217 + 24.5 * sin(a), 0, 24.5 * cos(a) + 1.2, hh + 0.1);
    Plank(217 + 24.5 * sin(a + 15), 0, 24.5 * cos(a + 15) + 1.2, hh + 0.1);
  }
}
module Straps(X, Z, W, H, st, wl) {
  for (s = [[2, 4], [7, 8]]) difference() {
    hull() { Sec(X[s[0]], Z[s[0]] + st, W[s[0]], H[s[0]]); Sec(X[s[1]], Z[s[1]] + st, W[s[1]], H[s[1]]); }
    hull() { Sec(X[s[0]] - 1, Z[s[0]] + st + 0.01, W[s[0]] - wl, H[s[0]] - wl); Sec(X[s[1]] + 1, Z[s[1]] + st + 0.01, W[s[1]] - wl, H[s[1]] - wl); }
  }
}
module Shaft(hh, height, st, wl) {
  translate([212, 0, hh + st]) difference() {
    scale([1.2, 1, 1]) cylinder(r = 26, h = height, $fn = 72);
    translate([0, 0, -1]) scale([1.2, 1, 1]) cylinder(r = 26 - wl * 1.5, h = height + 2, $fn = 72);
  }
}
module Shaft_laces(hh, height, n, st) {
  for (k = [0:n - 1]) translate([212 - 31.2 + 1, -11, hh + st + 12 + k * (height - 20) / (n - 1)]) cube([3, 22, 2]);
}
module Collar(hh, height, st) {
  translate([206, 0, hh + st]) difference() {
    scale([1.3, 1, 1]) cylinder(r = 27, h = height, $fn = 72);
    translate([0, 0, -1]) scale([1.3, 1, 1]) cylinder(r = 24, h = height + 2, $fn = 72);
    translate([-50, -40, height * 0.45]) rotate([0, 28, 0]) cube([40, 80, 200]);
  }
}
module Laces(X, Z, H, a, b, n, half, st) {
  for (k = [0:n - 1]) {
    f = k / (n - 1);
    x = X[a] + (X[b] - X[a]) * f;
    z = Z[a] + (Z[b] - Z[a]) * f + st + H[a] + (H[b] - H[a]) * f;
    translate([x - 1.5, -half, z - 1.6]) cube([3, 2 * half, 1.6]);
  }
}
module Heel_tab(hh, st) {
  translate([217, 0, hh + st + 30]) intersection() {
    difference() { cylinder(r = 25.2, h = 24, $fn = 72); translate([0, 0, -1]) cylinder(r = 23.4, h = 26, $fn = 72); }
    translate([10, -12, 0]) cube([20, 24, 24]);
  }
}
module Side_wave(X, Z, W, H, a, b, lift, rise, n, st) {
  for (side = [-1, 1]) for (k = [0:n - 1]) for (i = [a:b - 1]) hull() {
    translate([X[i], side * (W[i] + 0.4), Z[i] + st + H[i] * lift + k * 4 + rise * (i - a) / (b - a)]) sphere(r = 1.3, $fn = 10);
    translate([X[i + 1], side * (W[i + 1] + 0.4), Z[i + 1] + st + H[i + 1] * lift + k * 4 + rise * (i + 1 - a) / (b - a)]) sphere(r = 1.3, $fn = 10);
  }
}
module Tread(n, x0, x1, half) {
  for (k = [0:n - 1]) translate([x0 + (x1 - x0) * k / (n - 1) - 1.5, -half, -0.6]) cube([3, 2 * half, 1]);
}
module Foxing(X, B, W) {
  for (i = [0:16]) hull() {
    Plank(X[i], B[i] + 1.5, W[i] + 1.7, 1.4);
    Plank(X[i + 1], B[i + 1] + 1.5, W[i + 1] + 1.7, 1.4);
  }
}
"""


def _shoe_body(spec) -> str:
    """The calls for one shoe at the origin, in its own unscaled last."""
    up = UPPERS[spec["upper"]]
    sole = SOLES[spec["sole"]]
    z, b, r, hh = profile(spec)
    w = WIDTHS[spec["toe"]]
    h = up["h"]
    Xs, Z, W, H = _arr(X), _arr(z), _arr(w), _arr(h)
    upper_c = colour(spec["upper_colour"])
    lining_c = colour(spec["lining_colour"])
    sole_c = colour(spec["sole_colour"])
    heel_c = colour(spec["heel_colour"], upper_c)
    accent_c = colour(spec["accent_colour"])
    lace_c = colour(spec["lace_colour"], accent_c)
    st, wl = 3.5, 1.6
    out = []

    def add(hexcol, call, label):
        out.append(f'color("{hexcol}") {call};  // {label}')

    if sole.get("thin"):
        add(sole_c, f"Outsole({Xs}, {Z}, {W}, {hh:.2f}, {st})", "Sole")
    else:
        B = _arr(b)
        if r is not None:
            R = _arr(r)
            add(heel_c if spec["heel_colour"] else sole_c,
                f"Thick_sole({Xs}, {R}, {B}, {W}, 2.6, {st})", "Outsole")
            add(sole_c, f"Thick_sole({Xs}, {Z}, {R}, {W}, 3.0, {st})",
                "Midsole")
            add(heel_c if spec["heel_colour"] else sole_c,
                f"Tread({sole['tread']}, 30, 230, 20)", "Tread")
        else:
            add(sole_c, f"Thick_sole({Xs}, {Z}, {B}, {W}, 1.8, {st})",
                "Sole")
        if sole.get("foxing"):
            add(colour("Black"), f"Foxing({Xs}, {B}, {W})", "Foxing stripe")
    add(lining_c, f"Insole({Xs}, {Z}, {W}, {st}, {wl})", "Insole")
    if up.get("straps"):
        add(upper_c, f"Straps({Xs}, {Z}, {W}, {H}, {st}, {wl})", "Straps")
    else:
        add(upper_c, f"Upper({Xs}, {Z}, {W}, {H}, {up['openx']}, {st}, "
                     f"{wl})", "Upper")
    if up.get("cup"):
        cs, cb = up["cup"]
        add(upper_c, f"Cup({hh:.2f}, {cs}, {cb}, {st}, {wl})", "Heel cup")
    if up.get("shaft"):
        add(upper_c, f"Shaft({hh:.2f}, {up['shaft']}, {st}, {wl})", "Shaft")
    if up.get("shaft_laces"):
        add(lace_c, f"Shaft_laces({hh:.2f}, {up['shaft']}, "
                    f"{up['shaft_laces']}, {st})", "Shaft laces")
    if up.get("collar"):
        add(upper_c, f"Collar({hh:.2f}, {up['collar']}, {st})", "Collar")
    if up.get("laces"):
        a, bb, n, half = up["laces"]
        add(lace_c, f"Laces({Xs}, {Z}, {H}, {a}, {bb}, {n}, {half}, {st})",
            "Laces")
    if up.get("tab"):
        add(accent_c, f"Heel_tab({hh:.2f}, {st})", "Heel tab")
    if up.get("seams"):
        seam = _arr([v + 0.4 for v in h])
        add(colour("Black"), f"Straps({Xs}, {Z}, {W}, {seam}, {st}, {wl})",
            "Toe cap seam")
    if sole.get("foxing"):                   # rubber toe cap
        cap = _arr([v + 0.4 for v in w])
        caph = _arr([6, 11, 15, 18, 20] + [1] * 13)
        add(sole_c, f"Upper({Xs}, {Z}, {cap}, {caph}, 0, {st}, {wl})",
            "Toe cap")
    deco = spec["decoration"]
    if deco != "None" and not up.get("straps"):
        n = 2 if deco == "Double wave" else 1
        lift, rise = (0.25, -6) if deco == "Stripe" else (0.12, 14)
        a, bb = (9, 16) if deco == "Stripe" else (6, 15)
        add(accent_c, f"Side_wave({Xs}, {Z}, {W}, {H}, {a}, {bb}, {lift}, "
                      f"{rise}, {n}, {st})", "Side decoration")
    if spec["heel"] == "Stiletto" and sole.get("thin") and hh > 0:
        ah = 22 if spec["arrow"] else 1
        add(heel_c, f"Stiletto({hh:.2f}, {ah})", "Heel")
        if spec["arrow"]:
            add(heel_c, f"Arrow({ah})", "Devil arrow tip")
    elif spec["heel"] == "Block" and hh > 0:
        add(heel_c if spec["heel_colour"] else sole_c,
            f"Block({hh:.2f})", "Block heel")
    elif spec["heel"] == "Wedge" and hh > 0:
        add(heel_c, f"Wedge({Xs}, {Z}, {W}, {hh:.2f})", "Wedge")
    return "\n".join(out)


def program(spec=None) -> str:
    """The whole OpenSCAD program for the spec (one shoe or a pair)."""
    spec = normalise(spec)
    sx = length_mm(spec) / BASE_LENGTH
    sy = sx * (1.04 if spec["gender"] == "Men" else 1.0)
    body = _shoe_body(spec)
    shoe = f"scale([{sx:.4f}, {sy:.4f}, 1]) {{\n{body}\n}}"
    if spec["pair"]:
        gap = 2 * 38 * sy + 25
        shoe = (f"{shoe}  // Right shoe\n"
                f"translate([0, {gap:.1f}, 0]) mirror([0, 1, 0]) "
                f"{shoe}  // Left shoe")
    return LIB + "\n" + shoe + "\n"


def build(spec=None):
    """The shoe (or pair) as ONE union node."""
    from . import scadparse
    from .model import CadNode
    spec = normalise(spec)
    root, _warnings = scadparse.parse_scad(program(spec))
    group = CadNode("union", spec["name"] or "Shoe")
    for child in list(root.children):
        group.add(child)
    return group


def insert(model, spec=None, x=None, y=0.0, rz=0.0, replace=None):
    """Add the shoe to *model* as one Object carrying its spec in
    ``params["shoe"]`` (beside what is there, or where *replace* was)."""
    spec = normalise(spec)
    node = build(spec)
    if replace is not None:
        x = float(replace.params.get("x", 0.0))
        y = float(replace.params.get("y", 0.0))
        rz = float(replace.params.get("rz", 0.0))
        model.remove_node(replace)
    elif x is None:
        x = free_x(model)
    model.root.add(node)
    part = model.enclose_as_part(node, spec["name"] or "Shoe")
    part.params.update(x=float(x), y=float(y), rz=float(rz))
    part.params["shoe"] = copy.deepcopy(spec)
    model.structure_changed.emit()
    return part


def free_x(model) -> float:
    from . import mesh
    tris = mesh.tessellate(model.root, fn=8)
    if not tris:
        return 0.0
    return max(p[0] for t in tris for p in t) + 60.0


def options() -> dict:
    """Every choice, for the MCP tool and the dialog."""
    return dict(
        presets={k: dict(v) for k, v in PRESETS.items()},
        genders=list(GENDERS), toes=list(WIDTHS), uppers=list(UPPERS),
        soles=list(SOLES), heels=list(HEELS),
        decorations=list(DECORATIONS), colours=dict(COLOURS),
        size="EU 30-50 (length = EU x 2/3 cm)",
        heel_height="mm, 0-160; a thin sole rises with it, a thick "
                    "sole only takes a Block heel",
        defaults=dict(DEFAULTS),
        note="No brand logos or named brand designs: the side "
             "decoration is an original wave or stripe.")
