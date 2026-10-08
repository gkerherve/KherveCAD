"""TH8S "Monoposto" shifter knob — an entry for the Printables
Thrustmaster TH8S Custom Shifter Knob contest (Oct-Nov 2026).

A palm-shaped knob for the Thrustmaster TH8S: a 39 deg flare (prints
with no support), a diamond-knurled grip band between two grooves, a
shallow thumb pad on each side (either hand), a weight pocket
for a 19 mm steel ball or stacked nuts, and a press-fit badge carrying
the TH8S's 7+R H-pattern, printed in a second colour and clocked to
any angle after the knob is screwed on.

The mount is Thrustmaster's official "Design piece" (printables.com/
model/1825116): a 22.5 x 42.6 mm sleeve holding the female thread that
screws onto their printed adapter. `design_piece_stl` turns the STEP
into an STL stood axis-up, open end at z = 0, and the knob imports it
into a hole of its own size. Thrustmaster's files are not shipped here:
pass the folder they were downloaded to.

`python -m khervecad.tools.shifter_knob [OUT_DIR]` writes the .scad,
the .kcad (two Objects: Knob body, Shift badge), one STL per part at
its print pose (plus an 11 mm thread fit test), and prints the
support-free check of each.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import subprocess
import sys
from pathlib import Path

STEM = "TH8S Monoposto knob"

#: (r, z) of the body above the straight neck and the 39 deg flare; a
#: Catmull-Rom spline runs through them
DOME = [(28.3, 24.5), (29.3, 27.5), (29.5, 30), (29.5, 37), (29.5, 44),
        (28.9, 48.5), (27.2, 52.5), (24.4, 56.2), (20.6, 59.2),
        (16.6, 61.3)]

HEADER = """$fn = 96;
// TH8S "Monoposto" shifter knob
sleeve_d = 22.48;       // Thrustmaster's Design piece: outside diameter
sleeve_h = 42.64;       // and height (thread opening at z = 0)
knurl_teeth = 40;
sleeve_turn = 276;      // the official thread seats the knob turned this far: square to the adapter's flange when tight
badge_d = 30;
fit = 0.15;
weight_d = 23;          // pocket for a 19 mm steel ball or stacked M12 nuts, sealed by the badge
"""

BODY = r"""module profile_body() { rotate_extrude() polygon(@PROFILE@); }
module knurl_star(tw) { linear_extrude(height = 26, twist = tw, slices = 40) polygon([for (i = [0 : 2 * knurl_teeth - 1]) let(a = 180 * i / knurl_teeth, r = i % 2 ? 31.5 : 28.6) [r * cos(a), r * sin(a)]]); }
module knurl_zone() { difference() { translate([0, 0, -1]) cylinder(h = 80, r = 60); rotate_extrude() polygon([[28.6, 30.2], [60, 30.2 - 1.3 * 31.4], [60, 43.8 + 1.3 * 31.4], [28.6, 43.8]]); } }

module Knob_body() {
    color("#1d1f24") union() {
    rotate([0, 0, sleeve_turn]) import("TH8S design piece.stl");  // Official TH8S sleeve (Thrustmaster)
    difference() {
        intersection() {
            profile_body();  // Body
            union() { knurl_zone(); translate([0, 0, 24]) intersection() { knurl_star(38); knurl_star(-38); } }  // Diamond knurl
        }
        translate([0, 97, 41]) scale([1, 1, 1.25]) sphere(r = 70, $fn = 200);  // Thumb pad, left
        translate([0, -97, 41]) scale([1, 1, 1.25]) sphere(r = 70, $fn = 200);  // Thumb pad, right
        translate([0, 0, -0.01]) cylinder(h = sleeve_h - 0.2, d = sleeve_d - 0.2);  // Seat for the official sleeve (overlaps it)
        translate([0, 0, sleeve_h + 1.6]) cylinder(h = 40, d = weight_d);  // Weight pocket
        rotate_extrude() polygon([[28.3, 30.2], [29.7, 28.8], [29.7, 32.1]]);  // Lower band groove
        rotate_extrude() polygon([[28.3, 43.8], [29.7, 42.4], [29.7, 45.7]]);  // Upper band groove
        translate([0, 0, 59.4]) cylinder(h = 5, d = badge_d + 2 * fit);  // Badge seat
    }
    }
}

module Fit_test() {
    color("#1d1f24") union() {
        intersection() { import("TH8S design piece.stl"); translate([0, 0, -1]) cylinder(h = 12, d = 30); }  // First 11 mm of the official thread
        difference() { cylinder(h = 11, d = 30, $fn = 8); translate([0, 0, -1]) cylinder(h = 13, d = sleeve_d - 0.01); }  // Grip ring
    }
}

module Shift_badge() {
    color("#e10600") union() {
        cylinder(h = 2.0, d = badge_d);  // Badge plate
        translate([0, 0, 1.99]) cylinder(h = 0.25, d1 = badge_d, d2 = badge_d - 0.5);  // Badge bevel
    }
    color("#f2f2f2") translate([0, 0, 1.99]) linear_extrude(0.8) {
        translate([-9.6, -0.8]) square([19.2, 1.6]);  // Gate
        for (x = [-9, -3, 3, 9]) translate([x - 0.8, -6.2]) square([1.6, 12.4]);  // Lanes
        translate([-9, 9]) text("1", size = 3.2, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");  // Gear 1
        translate([-3, 9]) text("3", size = 3.2, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");  // Gear 3
        translate([3, 9]) text("5", size = 3.2, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");  // Gear 5
        translate([9, 9]) text("7", size = 3.2, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");  // Gear 7
        translate([-9, -9]) text("2", size = 3.2, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");  // Gear 2
        translate([-3, -9]) text("4", size = 3.2, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");  // Gear 4
        translate([3, -9]) text("6", size = 3.2, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");  // Gear 6
        translate([9, -9]) text("R", size = 3.2, font = "Liberation Sans:style=Bold", halign = "center", valign = "center");  // Gear R
    }
}
"""


def _spline(points, steps=6):
    """Catmull-Rom through *points* (ends repeated)."""
    p = [points[0]] + list(points) + [points[-1]]
    out = []
    for i in range(1, len(p) - 2):
        a, b, c, d = p[i - 1], p[i], p[i + 1], p[i + 2]
        for k in range(steps):
            t = k / steps
            out.append(tuple(0.5 * (2 * b[j] + (-a[j] + c[j]) * t
                                    + (2 * a[j] - 5 * b[j] + 4 * c[j] - d[j]) * t * t
                                    + (-a[j] + 3 * b[j] - 3 * c[j] + d[j]) * t ** 3)
                             for j in range(2)))
    out.append(p[-2])
    return out


def profile():
    """The body's half section: base chamfer, straight neck, then the
    flare and dome."""
    pts = [(0, 0), (16.5, 0), (17.5, 1.0), (17.5, 11.0)] + _spline(DOME)
    pts.append((0, 61.6))
    return "[" + ", ".join(f"[{r:.2f}, {z:.2f}]" for r, z in pts) + "]"


SLEEVE = "TH8S design piece.stl"

#: where the Design piece's axis runs in Thrustmaster's STEP (along -Y,
#: thread opening at y = -0.95)
STEP_AXIS = (773.28, 0.505, -0.95)


def program(parts=("assembly",), sleeve=SLEEVE):
    """The whole OpenSCAD text; *parts* picks what is placed: the
    assembly (badge seated), or "body" / "badge" / "fit" alone at print
    pose. *sleeve* is the path the official sleeve STL is imported from."""
    text = HEADER + BODY.replace("@PROFILE@", profile())
    text = text.replace(f'import("{SLEEVE}")', f'import("{sleeve}")')
    calls = {"assembly": "Knob_body();  // Knob body\n"
                         "translate([0, 0, 59.6]) rotate([0, 0, -90]) Shift_badge();  // Shift badge\n",
             "body": "Knob_body();\n", "badge": "Shift_badge();\n",
             "fit": "Fit_test();\n"}
    return text + "".join(calls[p] for p in parts)


def design_piece_stl(step, out):
    """Thrustmaster's Design piece STEP -> an STL stood axis-up, the
    thread opening at z = 0, centred on the z axis."""
    from khervecad import cadexchange, engine
    cx, cz, y0 = STEP_AXIS
    tris = [tuple((x - cx, z - cz, y0 - y) for x, y, z in tri)
            for p in cadexchange.read_parts(step, "Fine") for tri in p.tris]
    engine.write_stl(tris, str(out))
    return out


def main(argv=None):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
    import argparse
    from khervecad.tools import print_tests
    ap = argparse.ArgumentParser(description="Write the TH8S knob.")
    ap.add_argument("out", nargs="?",
                    default=str(Path.home() / "Documents" / STEM))
    ap.add_argument("--thrustmaster", default=str(Path.home() / "Downloads"),
                    help="folder holding Thrustmaster's 'Design piece.stp'")
    args = ap.parse_args(argv)
    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    sleeve = design_piece_stl(Path(args.thrustmaster).expanduser()
                              / "Design piece.stp", out / SLEEVE)
    text = program()
    (out / f"{STEM}.scad").write_text(text)
    warnings = print_tests.write(STEM, text, out / f"{STEM}.kcad")
    print(f"wrote {STEM}.kcad" + (f" ({len(warnings)} warnings)"
                                  if warnings else ""))
    openscad = print_tests.openscad_binary()
    if not openscad:
        print("OpenSCAD not found: no STL or check")
        return 0
    from khervecad import engine
    for part in ("body", "badge", "fit"):
        code = program((part,), sleeve=str(sleeve))
        src = out / f".{part}.scad"
        src.write_text(code)
        stl = out / f"{STEM} - {part}.stl"
        subprocess.run([openscad, *engine.backend_args(openscad), "-o",
                        str(stl), str(src)], capture_output=True, check=True)
        src.unlink()
        print(f"  {stl.name}:", print_tests.printability(code, openscad))
    return 0


if __name__ == "__main__":
    sys.exit(main())
