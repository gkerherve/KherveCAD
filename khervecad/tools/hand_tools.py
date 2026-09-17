"""Rewrite the Hand tools library as real multi-part assemblies.

A plier is not one lump of steel: it is two forged levers, a rivet
and two moulded grips.  The first pass at the Tools section modelled
every tool as a single Object, so a hammer's head could not be
coloured apart from its shaft, a chisel's handle could not be pulled
off its blade, and the exploded view had nothing to explode.  This
module writes each tool as the parts it is really made of, one
`component` (Object) per manufactured piece.

Each tool is authored as an OpenSCAD program — one zero-argument
`module` per part plus its placed call — and parsed back through
`scadparse`, so what lands in `khervecad/parts/Tools/` is an ordinary
editable object tree that round-trips.  Nothing here uses a boolean
where a hull or a union will do, so the built-in preview shows every
part in its own colour without waiting for OpenSCAD.

Run `python -m khervecad.tools.hand_tools` to rewrite them all, or
`--only "Claw Hammer"` for one.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import sys
from pathlib import Path

#: steel, wood, brass and the moulded colours the first pass used —
#: kept so a rebuilt tool still looks like the one it replaces
STEEL = "#b8bdc7"
BRIGHT = "#d1d6de"
DARK = "#8c8c94"
BLACK = "#1a1a1a"
WOOD = "#bf8c4c"
BEECH = "#d19954"
SAW_WOOD = "#b27333"
BRASS = "#cc9e40"
SCREW_BRASS = "#cca633"
RED = "#d91a1a"

HEADER = "$fn = 48;\n"


# ----------------------------------------------------------------- #
#  pliers: two crossing levers, a rivet and two grips
# ----------------------------------------------------------------- #

def _plier_lever(side: int, jaw: str) -> str:
    """One forged lever: jaw (full thickness at the pivot, tapering to
    the tip, its gripping face on y = 0), a half-thickness lap at the
    pivot, and the handle leg crossing to the other side.  *side* is
    +1 or -1; *jaw* is that side's jaw solid."""
    lap = 5 if side > 0 else 0
    return f"""        // jaw — tapered, its gripping face on y = 0
{jaw}
        // pivot boss — half thickness, lapped over the other lever
        translate([0, 0, {lap}]) {{
            linear_extrude(height=5) {{
                hull() {{
                    circle(r=10.5, $fn=64);
                    translate([-26, {-side * 11}]) circle(r=7, $fn=64);
                }}
            }}
        }}
        // handle leg — back to full thickness, crossed to the far side
        translate([0, 0, 1]) {{
            linear_extrude(height=8) {{
                hull() {{
                    translate([-22, {-side * 9.5}]) circle(r=7, $fn=64);
                    translate([-62, {-side * 13}]) circle(r=5, $fn=64);
                }}
            }}
        }}"""


def _plier_grip(side: int) -> str:
    return f"""        hull() {{
            translate([-60, {side * 13}, 4]) scale([1, 1, 0.8]) sphere(r=7, $fn=48);
            translate([-150, {side * 26}, 4]) scale([1, 1, 0.8]) sphere(r=8, $fn=48);
        }}"""


def _pliers(prefix: str, jaws, grip_colour: str) -> str:
    """A pair of pliers as five Objects.  *jaws* maps the side (+1/-1)
    to that jaw's 2D hull children."""
    out = [HEADER]
    for side, tag in ((1, "A"), (-1, "B")):
        out.append(f"""module {prefix}_lever_{tag}() {{
    color("{STEEL}") {{
{_plier_lever(side, jaws(side))}
    }}
}}
{prefix}_lever_{tag}();  // Lever {tag} (jaw and handle)
""")
    out.append(f"""module {prefix}_rivet() {{
    color("{DARK}") {{
        translate([0, 0, -0.6]) cylinder(h=11.2, r1=5, r2=5, $fn=64, center=false);  // Shank
        translate([0, 0, -1.2]) cylinder(h=1.2, r1=6.4, r2=5, $fn=64, center=false);  // Peened head
        translate([0, 0, 10]) cylinder(h=1.2, r1=5, r2=6.4, $fn=64, center=false);  // Peened head
    }}
}}
{prefix}_rivet();  // Pivot rivet
""")
    for side, tag in ((-1, "A"), (1, "B")):
        out.append(f"""module {prefix}_grip_{tag}() {{
    color("{grip_colour}") {{
{_plier_grip(side)}
    }}
}}
{prefix}_grip_{tag}();  // Grip {tag}
""")
    return "\n".join(out)


def combination_pliers() -> str:
    def jaw(s):
        edge = 0 if s > 0 else -2.4
        return f"""        hull() {{
            translate([3, {s * 7}, 0]) cylinder(h=10, r1=7, r2=7, $fn=48);  // Jaw shoulder
            translate([26, {s * 6}, 0]) cylinder(h=10, r1=6, r2=6, $fn=48);  // Pipe grip
        }}
        hull() {{
            translate([26, {s * 6}, 0]) cylinder(h=10, r1=6, r2=6, $fn=48);
            translate([44, {edge}, 1.2]) cube([2, 2.4, 7.6], center=false);  // Serrated nose
        }}"""
    return _pliers("Combination_pliers", jaw, RED)


def needle_nose_pliers() -> str:
    def jaw(s):
        mid = 0 if s > 0 else -3.2
        edge = 0 if s > 0 else -1.2
        return f"""        hull() {{
            translate([3, {s * 7}, 0]) cylinder(h=10, r1=7, r2=7, $fn=48);  // Jaw shoulder
            translate([38, {mid}, 2]) cube([2, 3.2, 6], center=false);
        }}
        hull() {{
            translate([38, {mid}, 2]) cube([2, 3.2, 6], center=false);
            translate([74, {edge}, 4]) cube([2, 1.2, 2.4], center=false);  // Needle tip
        }}"""
    return _pliers("Needle_nose_pliers", jaw, "#1a59cc")


# ----------------------------------------------------------------- #
#  adjustable wrench: body, sliding jaw, worm and its pin
# ----------------------------------------------------------------- #

def adjustable_wrench() -> str:
    return HEADER + f"""
module Body_and_fixed_jaw() {{
    color("{BRIGHT}") {{
        linear_extrude(height=10) {{
            difference() {{
                union() {{
                    hull() {{
                        circle(r=8, $fn=64);
                        translate([150, 0]) circle(r=11, $fn=64);
                    }}
                    translate([172, 0]) circle(r=24, $fn=64);  // Head
                }}
                circle(r=4, $fn=64);  // Hanging hole
                // the opening follows the head's arc, so the preview's
                // uncut approximation shows no tab hanging off it
                polygon(points=[[170, -3], [196.2, -3], [196.3, 0],
                                [195.9, 5], [194.2, 10], [191.9, 14],
                                [170, 14]]);  // Jaw opening
                translate([169, -22]) square([13, 19.5]);  // Slide way
                translate([165.5, -14]) circle(r=8.2, $fn=64);  // Worm pocket
            }}
        }}
    }}
}}
Body_and_fixed_jaw();  // Body and fixed jaw

module Sliding_jaw() {{
    color("{BRIGHT}") {{
        translate([169.5, -12.4, 0]) cube([21, 9.4, 10], center=false);  // Jaw
        translate([169.5, -21.5, 0]) cube([12.5, 10.5, 10], center=false);  // Rack shank
        for (y = [-20 : 2.2 : -13]) {{
            translate([168.7, y, 5]) rotate([0, 90, 0]) rotate([0, 0, 30])
                cylinder(h=1.6, r1=1.1, r2=1.1, $fn=6, center=false);  // Rack tooth
        }}
    }}
}}
Sliding_jaw();  // Sliding jaw

module Worm_screw() {{
    color("{DARK}") {{
        translate([165.5, -14, 0.6]) {{
            cylinder(h=8.8, r1=7.4, r2=7.4, $fn=64, center=false);  // Worm body
            for (a = [0 : 15 : 345]) {{
                rotate([0, 0, a]) translate([7.2, 0, 0])
                    cylinder(h=8.8, r1=0.8, r2=0.8, $fn=8, center=false);  // Knurl
            }}
        }}
    }}
}}
Worm_screw();  // Worm screw

module Worm_pin() {{
    color("{STEEL}") {{
        translate([165.5, -14, -1]) cylinder(h=12, r1=1.6, r2=1.6, $fn=32, center=false);  // Axle
        translate([165.5, -14, -1.6]) cylinder(h=0.8, r1=2.6, r2=2.6, $fn=32, center=false);  // Peened head
        translate([165.5, -14, 10.8]) cylinder(h=0.8, r1=2.6, r2=2.6, $fn=32, center=false);  // Peened head
    }}
}}
Worm_pin();  // Worm pin
"""


# ----------------------------------------------------------------- #
#  claw hammer: head, shaft, grip
# ----------------------------------------------------------------- #

def claw_hammer() -> str:
    return HEADER + f"""
module Hammer_head() {{
    color("{STEEL}") {{
        translate([0, -10, 15]) rotate([90, 0, 0]) cylinder(h=26, r1=13, r2=13, $fn=64, center=false);  // Striking neck
        translate([0, -36, 15]) rotate([90, 0, 0]) cylinder(h=4, r1=14, r2=14, $fn=64, center=false);  // Face
        translate([-12, -10, 3]) cube([24, 30, 24], center=false);  // Eye block
        for (z = [3, 17]) {{
            translate([0, 0, z]) linear_extrude(height=10) {{
                polygon(points=[[-12, 20], [12, 20], [8, 40], [-5, 60], [-22, 72], [-26, 68], [-14, 52], [-10, 35]]);  // Claw
            }}
        }}
    }}
}}
Hammer_head();  // Head

module Shaft() {{
    color("{WOOD}") {{
        translate([-12, 5, 15]) rotate([0, -90, 0]) cylinder(h=150, r1=10, r2=12, $fn=64, center=false);  // Shaft
    }}
}}
Shaft();  // Shaft

module Hammer_grip() {{
    color("{BLACK}") {{
        translate([-155, 5, 15]) rotate([0, -90, 0]) cylinder(h=115, r1=13, r2=14.5, $fn=64, center=false);  // Rubber grip
        translate([-270, 5, 15]) scale([0.4, 1, 1]) sphere(r=14.5, $fn=48);  // Grip end
    }}
}}
Hammer_grip();  // Grip

module Eye_wedge() {{
    color("{BRIGHT}") {{
        translate([-2, 8, 26.5]) cube([4, 14, 2.5], center=false);  // Steel wedge
    }}
}}
Eye_wedge();  // Eye wedge
"""


# ----------------------------------------------------------------- #
#  brick bolster: the forging and its moulded hand guard
# ----------------------------------------------------------------- #

def brick_bolster() -> str:
    return HEADER + f"""
module Bolster() {{
    color("{STEEL}") {{
        translate([0, 0, 9]) rotate([0, 90, 0]) rotate([0, 0, 30]) cylinder(h=150, r1=9, r2=9, $fn=6, center=false);  // Hex shank
        hull() {{
            translate([150, 0, 9]) rotate([0, 90, 0]) rotate([0, 0, 30]) cylinder(h=1, r1=9, r2=9, $fn=6, center=false);
            translate([175, -37.5, 7]) cube([2, 75, 4], center=false);
            translate([200, -37.5, 8.7]) cube([0.5, 75, 0.6], center=false);
        }}
        translate([-4, 0, 9]) rotate([0, 90, 0]) cylinder(h=4, r1=7, r2=9, $fn=64, center=false);  // Striking head
    }}
}}
Bolster();  // Bolster

module Hand_guard() {{
    color("{RED}") {{
        translate([95, 0, 9]) rotate([0, 90, 0]) cylinder(h=6, r1=38, r2=38, $fn=64, center=false);  // Guard disc
        translate([30, 0, 9]) rotate([0, 90, 0]) cylinder(h=65, r1=13, r2=13, $fn=64, center=false);  // Rubber sleeve
    }}
}}
Hand_guard();  // Hand guard
"""


# ----------------------------------------------------------------- #
#  wood chisel: blade, handle, ferrule, striking cap
# ----------------------------------------------------------------- #

#: blade width in mm -> (half width, blade thickness, back z)
CHISELS = [6, 10, 12, 16, 19, 25, 32]


def wood_chisel(width: float) -> str:
    half = width / 2.0
    thick = 5.0 if width >= 12 else 4.0
    z0 = 14 - thick / 2.0
    return HEADER + f"""
module Blade() {{
    color("{STEEL}") {{
        translate([-6, 0, 14]) rotate([0, 90, 0]) cylinder(h=4, r1=4.2, r2=4.2, $fn=32, center=false);  // Tang
        translate([-2, 0, 14]) rotate([0, 90, 0]) cylinder(h=14, r1=6, r2=3.5, $fn=64, center=false);  // Bolster and neck
        hull() {{
            translate([10, {-half}, {z0}]) cube([1, {width}, {thick}], center=false);  // Blade back
            translate([100, {-half}, {z0}]) cube([1, {width}, {thick}], center=false);  // Bevel start
            translate([112, {-half}, {z0}]) cube([0.5, {width}, 0.3], center=false);  // Cutting edge
        }}
    }}
}}
Blade();  // Blade

module Handle() {{
    color("{BEECH}") {{
        hull() {{
            translate([-118, 0, 14]) scale([0.45, 1, 1]) sphere(r=14, $fn=48);
            translate([-12, 0, 14]) rotate([0, 90, 0]) cylinder(h=4, r1=10.5, r2=10.5, $fn=64, center=false);
        }}
    }}
}}
Handle();  // Handle

module Ferrule() {{
    color("{BRASS}") {{
        translate([-8, 0, 14]) rotate([0, 90, 0]) cylinder(h=6, r1=10.92, r2=10.92, $fn=64, center=false);  // Brass ferrule
    }}
}}
Ferrule();  // Ferrule

module Striking_cap() {{
    color("{BLACK}") {{
        translate([-118, 0, 14]) scale([0.5, 1, 1]) sphere(r=14.3, $fn=48);  // Cap dome
        translate([-118, 0, 14]) rotate([0, 90, 0]) cylinder(h=7, r1=14.3, r2=14, $fn=64, center=false);  // Cap hoop
    }}
}}
Striking_cap();  // Striking cap
"""


# ----------------------------------------------------------------- #
#  screwdrivers: handle, over-mould cap, ferrule, blade
# ----------------------------------------------------------------- #

#: label -> (handle radius, handle length, shaft radius, shaft length,
#:           tip width or 0 for Phillips, handle colour)
SCREWDRIVERS = {
    "Flat Screwdriver 3 mm": (10, 70, 1.5, 75, 3.0, "#e6261a"),
    "Flat Screwdriver 5.5 mm": (13, 91, 3.0, 100, 5.5, "#e6261a"),
    "Flat Screwdriver 8 mm": (16, 112, 4.0, 150, 8.0, "#e6261a"),
    "Phillips Screwdriver PH1": (12, 84, 2.5, 80, 0, "#ffcc1a"),
    "Phillips Screwdriver PH2": (14, 98, 3.0, 100, 0, "#ffcc1a"),
}


def screwdriver(name: str) -> str:
    r, hl, sr, sl, tip, colour = SCREWDRIVERS[name]
    neck = round(r * 0.55, 2)
    ridge = round(r * 0.22, 2)
    ridge_r = round(r * 0.9, 2)
    x_cap, x_fer, x_shaft = hl, hl + 9, hl + 12
    x_tip = x_shaft + sl
    if tip:
        wing = round(tip / 2.0, 3)
        tip_t = round(tip * 0.16, 3)
        point = f"""        hull() {{
            translate([{x_tip}, 0, {r}]) rotate([0, 90, 0]) cylinder(h=0.5, r1={sr}, r2={sr}, $fn=64, center=false);  // Shaft end
            translate([{x_tip + 9}, {-wing}, {r - tip_t / 2}]) cube([0.4, {tip}, {tip_t}], center=false);  // Blade edge
        }}"""
    else:
        wing = round(sr * 1.05, 3)
        point = f"""        hull() {{
            translate([{x_tip}, 0, {r}]) rotate([0, 90, 0]) cylinder(h=0.5, r1={sr}, r2={sr}, $fn=64, center=false);  // Shaft end
            translate([{x_tip + 7.5}, 0, {r}]) sphere(r=0.4, $fn=48);  // Point
        }}
        for (a = [0, 90]) {{
            translate([0, 0, {r}]) rotate([a, 0, 0]) hull() {{
                translate([{x_tip}, {-wing}, -0.35]) cube([0.5, {wing * 2}, 0.7], center=false);
                translate([{x_tip + 6}, -0.5, -0.35]) cube([0.5, 1, 0.7], center=false);
            }}  // Cross wing
        }}"""
    return HEADER + f"""
module Handle() {{
    color("{colour}") {{
        translate([0, 0, {r}]) rotate([0, 90, 0]) cylinder(h={hl}, r1={r}, r2={r}, $fn=64, center=false);  // Handle
        translate([0, 0, {r}]) scale([0.5, 1, 1]) sphere(r={r}, $fn=48);  // Handle butt
        for (a = [0 : 60 : 300]) {{
            translate([0, 0, {r}]) rotate([a, 0, 0]) translate([6, 0, {ridge_r}]) rotate([0, 90, 0])
                cylinder(h={hl - 12}, r1={ridge}, r2={ridge}, $fn=64, center=false);  // Grip ridge
        }}
    }}
}}
Handle();  // Handle

module Grip_cap() {{
    color("{BLACK}") {{
        translate([{x_cap}, 0, {r}]) rotate([0, 90, 0]) cylinder(h=10, r1={r}, r2={neck}, $fn=64, center=false);  // Soft cap
    }}
}}
Grip_cap();  // Grip cap

module Ferrule() {{
    color("{BRIGHT}") {{
        translate([{x_fer}, 0, {r}]) rotate([0, 90, 0]) cylinder(h=3, r1={neck}, r2={neck}, $fn=64, center=false);  // Ferrule
    }}
}}
Ferrule();  // Ferrule

module Blade() {{
    color("{BRIGHT}") {{
        translate([{x_shaft - 14}, 0, {r}]) rotate([0, 90, 0]) cylinder(h=14, r1={round(sr * 0.8, 2)}, r2={sr}, $fn=64, center=false);  // Tang
        translate([{x_shaft}, 0, {r}]) rotate([0, 90, 0]) cylinder(h={sl}, r1={sr}, r2={sr}, $fn=64, center=false);  // Shaft
{point}
    }}
}}
Blade();  // Blade
"""


# ----------------------------------------------------------------- #
#  hand saw: blade, handle, two screws
# ----------------------------------------------------------------- #

def _saw_teeth() -> str:
    pts = ["[0, 110]", "[450, 70]", "[450, 0]"]
    x = 448
    while x >= 0:
        pts.append(f"[{x}, 0]")
        pts.append(f"[{x - 2}, -3.5]")
        x -= 4
    pts.append("[0, 0]")
    return ", ".join(pts)


def hand_saw() -> str:
    return HEADER + f"""
module Blade() {{
    color("{BRIGHT}") {{
        linear_extrude(height=0.9) {{
            polygon(points=[{_saw_teeth()}]);  // Blade with teeth
        }}
    }}
}}
Blade();  // Blade

module Handle() {{
    color("{SAW_WOOD}") {{
        translate([0, 0, -10.5]) linear_extrude(height=22) {{
            hull() {{ translate([-110, 12]) circle(r=9, $fn=32); translate([-125, 120]) circle(r=9, $fn=32); }}
            hull() {{ translate([-125, 120]) circle(r=9, $fn=32); translate([-60, 140]) circle(r=9, $fn=32); }}
            hull() {{ translate([-60, 140]) circle(r=9, $fn=64); translate([20, 118]) circle(r=11, $fn=64); }}  // Front loop
            hull() {{ translate([20, 118]) circle(r=11, $fn=32); translate([25, 15]) circle(r=11, $fn=32); }}
            hull() {{ translate([25, 15]) circle(r=11, $fn=64); translate([-110, 12]) circle(r=9, $fn=64); }}  // Lower bar
            hull() {{ translate([-85, 35]) circle(r=10, $fn=64); translate([-78, 118]) circle(r=9, $fn=64); }}  // Grip
        }}
    }}
}}
Handle();  // Handle

module Handle_screw_top() {{
    color("{SCREW_BRASS}") {{
        translate([21, 100, -11.5]) cylinder(h=24, r1=3.2, r2=3.2, $fn=32, center=false);  // Screw
        translate([21, 100, -12.8]) cylinder(h=1.4, r1=6, r2=6, $fn=32, center=false);  // Rosette
        translate([21, 100, 11.4]) cylinder(h=1.4, r1=6, r2=6, $fn=32, center=false);  // Rosette
    }}
}}
Handle_screw_top();  // Handle screw (top)

module Handle_screw_middle() {{
    color("{SCREW_BRASS}") {{
        translate([21, 60, -11.5]) cylinder(h=24, r1=3.2, r2=3.2, $fn=32, center=false);  // Screw
        translate([21, 60, -12.8]) cylinder(h=1.4, r1=6, r2=6, $fn=32, center=false);  // Rosette
        translate([21, 60, 11.4]) cylinder(h=1.4, r1=6, r2=6, $fn=32, center=false);  // Rosette
    }}
}}
Handle_screw_middle();  // Handle screw (middle)

module Handle_screw_bottom() {{
    color("{SCREW_BRASS}") {{
        translate([21, 24, -11.5]) cylinder(h=24, r1=3.2, r2=3.2, $fn=32, center=false);  // Screw
        translate([21, 24, -12.8]) cylinder(h=1.4, r1=6, r2=6, $fn=32, center=false);  // Rosette
        translate([21, 24, 11.4]) cylinder(h=1.4, r1=6, r2=6, $fn=32, center=false);  // Rosette
    }}
}}
Handle_screw_bottom();  // Handle screw (bottom)

"""


# ----------------------------------------------------------------- #
#  hex key set: one key per Object
# ----------------------------------------------------------------- #

#: across-flats size -> y of that key on the bench
HEX_KEYS = [(1.5, 0), (2, 8), (2.5, 16), (3, 24), (4, 33),
            (5, 44), (6, 57), (8, 72), (10, 91)]


def hex_key_set() -> str:
    out = [HEADER]
    for size, y in HEX_KEYS:
        r = round(size / 3 ** 0.5, 3)
        long_leg = 45 + 9 * size
        short_leg = 15 + 3 * size
        ident = f"Hex_key_{str(size).replace('.', '_')}mm"
        out.append(f"""module {ident}() {{
    color("#26262b") {{
        translate([0, {y}, {r}]) {{
            rotate([0, 90, 0]) rotate([0, 0, 30]) cylinder(h={long_leg}, r1={r}, r2={r}, $fn=6, center=false);  // Long leg
            sphere(r={r}, $fn=48);  // Bend
            rotate([0, 0, 90]) rotate([0, -90, 0]) rotate([0, 0, 30])
                cylinder(h={short_leg}, r1={r}, r2={r}, $fn=6, center=false);  // Short leg
        }}
    }}
}}
{ident}();  // Hex key {size} mm
""")
    return "\n".join(out)


# ----------------------------------------------------------------- #
#  spirit level: extrusion, two end caps, two vials
# ----------------------------------------------------------------- #

def spirit_level() -> str:
    return HEADER + f"""
module Body() {{
    color("#ccd1db") {{
        cube([400, 60, 25], center=false);  // Aluminium body
    }}
    color("#f2bf0d") {{
        translate([0, 0, 24.8]) cube([400, 60, 0.4], center=false);  // Label strip
    }}
}}
Body();  // Body

module End_cap_left() {{
    color("{BLACK}") {{
        translate([-6, -1, -1]) cube([6, 62, 27], center=false);  // End cap
    }}
}}
End_cap_left();  // End cap (left)

module End_cap_right() {{
    color("{BLACK}") {{
        translate([400, -1, -1]) cube([6, 62, 27], center=false);  // End cap
    }}
}}
End_cap_right();  // End cap (right)

module Level_vial() {{
    color("{BLACK}") {{
        translate([172, 20, 24]) cube([56, 20, 3], center=false);  // Vial frame
    }}
    kcad_material("Glass") color("#66e64c", 0.6) {{
        translate([180, 30, 27]) rotate([0, 90, 0]) cylinder(h=40, r1=5, r2=5, $fn=64, center=false);  // Vial
    }}
    color("#ffffff") {{
        translate([200, 30, 30]) scale([1.6, 1, 0.6]) sphere(r=3, $fn=48);  // Bubble
    }}
}}
Level_vial();  // Level vial

module Plumb_vial() {{
    color("{BLACK}") {{
        translate([30, 5, 24]) cube([20, 50, 3], center=false);  // Vial frame
    }}
    kcad_material("Glass") color("#66e64c", 0.6) {{
        translate([40, 8, 27]) rotate([-90, 0, 0]) cylinder(h=44, r1=5, r2=5, $fn=64, center=false);  // Vial
    }}
    color("#ffffff") {{
        translate([40, 32, 30]) scale([1, 1.6, 0.6]) sphere(r=3, $fn=48);  // Bubble
    }}
}}
Plumb_vial();  // Plumb vial
"""


# ----------------------------------------------------------------- #
#  tape measure: case, over-mould, blade, hook, clip, lock
# ----------------------------------------------------------------- #

def tape_measure() -> str:
    return HEADER + f"""
module Case() {{
    color("#ffcc0d") {{
        hull() {{
            cylinder(h=32, r1=30, r2=30, $fn=64, center=false);
            translate([22, -30, 0]) cube([14, 60, 32], center=false);
        }}
    }}
}}
Case();  // Case

module Over_mould() {{
    color("{BLACK}") {{
        translate([0, 0, 31.5]) cylinder(h=1.5, r1=21, r2=21, $fn=64, center=false);  // Grip panel
        translate([0, 0, -1]) cylinder(h=1.5, r1=21, r2=21, $fn=64, center=false);  // Grip panel under
    }}
}}
Over_mould();  // Rubber over-mould

module Blade() {{
    color("#f2e64c") {{
        translate([35, -9.5, 1]) cube([21, 19, 0.3], center=false);  // Blade
    }}
}}
Blade();  // Blade

module End_hook() {{
    color("{BLACK}") {{
        translate([55.5, -10, 0]) cube([1.5, 20, 6], center=false);  // End hook
        translate([53, -10, 0.6]) cube([2.5, 20, 1], center=false);  // Rivet plate
    }}
}}
End_hook();  // End hook

module Belt_clip() {{
    color("{BLACK}") {{
        translate([22, -35, 3]) cube([13, 2.5, 25], center=false);  // Spring blade
        translate([22, -35, 28]) cube([13, 7.5, 2.5], center=false);  // Top bridge
    }}
}}
Belt_clip();  // Belt clip

module Lock_button() {{
    color("{RED}") {{
        translate([22, -6, 32]) cube([10, 12, 3], center=false);  // Lock button
    }}
}}
Lock_button();  // Lock button
"""


# ----------------------------------------------------------------- #
#  utility knife: body, over-mould, slider, blade
# ----------------------------------------------------------------- #

def utility_knife() -> str:
    return HEADER + f"""
module Body() {{
    color("#ffcc0d") {{
        linear_extrude(height=14) {{
            hull() {{
                circle(r=10, $fn=64);
                translate([140, 2]) circle(r=9, $fn=64);
                translate([60, 6]) circle(r=12, $fn=64);
            }}
        }}
    }}
}}
Body();  // Body

module Over_mould() {{
    color("{BLACK}") {{
        translate([0, 0, 13.5]) linear_extrude(height=1.5) {{
            hull() {{ translate([5, 0]) circle(r=6, $fn=32); translate([110, 3]) circle(r=6, $fn=32); }}
        }}
    }}
}}
Over_mould();  // Rubber over-mould

module Blade_slider() {{
    color("{BLACK}") {{
        translate([90, 6, 14]) cube([14, 6, 4], center=false);  // Slider
        translate([90, 6, 10]) cube([14, 6, 4], center=false);  // Slider shank
    }}
}}
Blade_slider();  // Blade slider

module Blade() {{
    color("{BRIGHT}") {{
        translate([0, 0, 6]) linear_extrude(height=1) {{
            polygon(points=[[145, -5], [145, 9], [166, 9], [178, -5]]);  // Trapezoid blade
        }}
    }}
}}
Blade();  // Blade
"""


# ----------------------------------------------------------------- #
#  socket sets: every socket, the extension bar and the ratchet's own
#  pieces are separate parts — they come out of the rail one at a time
# ----------------------------------------------------------------- #

SOCKET_SETS = ["Socket Set 1-4 in Drive", "Socket Set 3-8 in Drive",
               "Socket Set 3-8 in Drive SAE", "Socket Set 1-2 in Drive"]

#: how the ratchet's steel pieces divide into the parts that move
#: against each other — the rest of the group stays with the body
RATCHET_PARTS = [("Drive anvil", ("Square drive", "Detent ball")),
                 ("Reverse lever", ("Reverse lever",))]


def _component(model, name, placement):
    """A fresh visible Object named *name*, placed like *placement*."""
    from khervecad.model import CadNode, NODE_TYPES
    node = CadNode("component", name)
    node.params.update(dict(NODE_TYPES["component"]["params"]))
    for key in ("x", "y", "z", "rx", "ry", "rz", "color", "alpha"):
        if key in placement:
            node.params[key] = placement[key]
    return node


def _wrapped(colour_node, children):
    """*children* under a copy of their color() wrapper."""
    from khervecad.document import node_from_dict, node_to_dict
    wrapper = node_from_dict(node_to_dict(colour_node))
    for kid in list(wrapper.children):
        wrapper.remove(kid)
    for kid in children:
        wrapper.add(kid)
    return wrapper


def _labels(rail):
    """The size marks printed on a storage rail, left to right."""
    out = []
    for group in rail.children:
        if group.params.get("color") != "#ffffff":
            continue
        stack = list(group.children)
        while stack:
            node = stack.pop(0)
            if node.type == "text":
                out.append(str(node.params.get("text", "")))
            stack[:0] = list(node.children)
    return out


def split_socket_set(path) -> int:
    """Rewrite the socket set at *path* with one Object per socket, one
    for the extension bar, and the ratchet's body, anvil, reverse lever
    and grip apart.  Returns the number of Objects written."""
    from PyQt5.QtWidgets import QApplication
    from khervecad import document
    from khervecad.model import DocumentModel
    _app = QApplication.instance() or QApplication([])
    doc = DocumentModel()
    document.load_kcad(doc, str(path))
    old = [c for c in doc.root.children if c.type == "component"]
    sockets = next((c for c in old if c.name.endswith("sockets")), None)
    if sockets is None:                 # already split — nothing to do
        return len(old)
    rail = next(c for c in old if c.name.endswith("rail"))
    ratchet = next(c for c in old if c.name.endswith("ratchet"))
    marks = _labels(rail)

    fresh = []
    rail.name = "Storage rail"
    fresh.append(rail)

    group = sockets.children[0]
    kids = list(group.children)
    for i, kid in enumerate(kids):
        group.remove(kid)
        last = i == len(kids) - 1
        name = "Extension bar" if last else \
            f"Socket {marks[i] if i < len(marks) else i + 1}"
        part = _component(doc, name, sockets.params)
        part.add(_wrapped(group, [kid]))
        fresh.append(part)

    taken = set()
    for name, wanted in RATCHET_PARTS:
        picked = []
        for colour in ratchet.children:
            for kid in list(colour.children):
                tag = (kid.name or "").split("[")[-1].rstrip("]")
                if tag in wanted and id(kid) not in taken:
                    taken.add(id(kid))
                    colour.remove(kid)
                    picked.append((colour, kid))
        if not picked:
            continue
        part = _component(doc, name, ratchet.params)
        part.add(_wrapped(picked[0][0], [kid for _, kid in picked]))
        fresh.append(part)
    for colour in list(ratchet.children):
        if not colour.children:
            ratchet.remove(colour)
    # the grip is whatever is not the steel the head is forged from —
    # the SAE set's is blue, the metric ones' red
    steel = next((c.params.get("color") for c in ratchet.children
                  if any("Ratchet head" in (k.name or "")
                         for k in c.children)), None)
    grips = [c for c in ratchet.children
             if c.params.get("color") != steel]
    for colour in grips:
        ratchet.remove(colour)
    ratchet.name = "Ratchet body"
    fresh.insert(len(fresh) - len(RATCHET_PARTS), ratchet)
    if grips:
        grip = _component(doc, "Ratchet grip", ratchet.params)
        for colour in grips:
            grip.add(colour)
        fresh.append(grip)

    for child in list(doc.root.children):
        if child.type == "component":
            doc.root.remove(child)
    for part in fresh:
        doc.root.add(part)
    document.save_kcad(doc, str(path))
    return len(fresh)


# ----------------------------------------------------------------- #
#  what this module writes
# ----------------------------------------------------------------- #

def programs() -> dict:
    """Every tool this module rewrites: file stem -> OpenSCAD text."""
    out = {
        "Combination Pliers": combination_pliers(),
        "Needle-Nose Pliers": needle_nose_pliers(),
        "Adjustable Wrench": adjustable_wrench(),
        "Claw Hammer": claw_hammer(),
        "Brick Bolster": brick_bolster(),
        "Hand Saw": hand_saw(),
        "Hex Key Set": hex_key_set(),
        "Spirit Level": spirit_level(),
        "Tape Measure": tape_measure(),
        "Utility Knife": utility_knife(),
    }
    for width in CHISELS:
        out[f"Wood Chisel {width} mm"] = wood_chisel(width)
    for name in SCREWDRIVERS:
        out[name] = screwdriver(name)
    return out


def write(stem: str, text: str, path) -> list:
    """Parse *text* and save it as the .kcad at *path*.  Returns the
    parser's warnings — a rewritten tool must produce none."""
    from PyQt5.QtWidgets import QApplication
    from khervecad import document, scadparse
    from khervecad.model import DocumentModel
    _app = QApplication.instance() or QApplication([])
    root, warnings = scadparse.parse_scad(text)
    doc = DocumentModel()
    doc.root = root
    doc.global_fn = 45
    doc.global_fn_on = False
    doc.group_variables()
    document.save_kcad(doc, str(path))
    return warnings


def folder():
    from khervecad import library_kcad
    return library_kcad.PARTS_DIR / "Tools"


def main(argv=None):
    import argparse
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    ap = argparse.ArgumentParser(description="Rewrite the Hand tools "
                                             "as multi-part assemblies.")
    ap.add_argument("--only", action="append",
                    help="one tool's file stem (repeatable)")
    ap.add_argument("--into", help="folder to write into")
    args = ap.parse_args(argv)
    into = Path(args.into) if args.into else folder()
    into.mkdir(parents=True, exist_ok=True)
    todo = programs()
    if args.only:
        todo = {k: v for k, v in todo.items() if k in args.only}
        missing = set(args.only) - set(todo) - set(SOCKET_SETS)
        if missing:
            ap.error(f"no such tool: {', '.join(sorted(missing))}")
    for stem, text in sorted(todo.items()):
        warnings = write(stem, text, into / f"{stem}.kcad")
        note = f"  ({len(warnings)} warnings)" if warnings else ""
        print(f"wrote {stem}.kcad{note}")
        for warning in warnings:
            print(f"    {warning}")
    for stem in SOCKET_SETS:
        if args.only and stem not in args.only:
            continue
        path = into / f"{stem}.kcad"
        if path.exists():
            print(f"split {stem}.kcad into {split_socket_set(path)} objects")
    return 0


if __name__ == "__main__":
    sys.exit(main())
