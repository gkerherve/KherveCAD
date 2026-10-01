"""Test parts for printer: the Library section of quick, support-free
prints (Library ▸ Engineering ▸ 3D printing ▸ Test parts for printer).

Every part prints on the first try with no supports: it stands flat
on z = 0 with a chamfered (never rounded) foot, nothing faces down
steeper than 45° (horizontal holes are teardrops, ceilings gabled,
whatever sticks out has a chamfered underside, text on a side wall is
V-carved), and each is ONE closed solid.  Rounded everywhere else.
The Benchy-style boats are original designs in the spirit of 3DBenchy,
not copies of it.

Each part is an OpenSCAD program (shared helper modules + one module
per part) parsed through `scadparse`, so the shipped `.kcad` is an
ordinary editable tree.  `test_print_tests` pins the shipped files to
this module and, with OpenSCAD installed, re-checks every part:
one piece, flat on the bed, under `MAX_OVERHANG_MM2` facing down past
45° (`printability`).

Run `python -m khervecad.tools.print_tests` to rewrite them all.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

SECTION = "Test parts for printer"

#: downward area steeper than 45 deg a part may keep (mm²): the tiny
#: facets of curves and the ends of V-carved letters
MAX_OVERHANG_MM2 = 20.0

HEADER = "$fn = 48;\n"

#: rbox = all edges round (only where its foot is buried); cbox = round
#: top, chamfered foot; pebble = a Minkowski tool round above and
#: chamfered below; tport = horizontal teardrop hole along Y, 40° roof
HELPERS = r"""module rbox(size, r) { hull() for (x = [r, size[0] - r], y = [r, size[1] - r], z = [r, size[2] - r]) translate([x, y, z]) sphere(r = r, $fn = 16); }
// Rounded top, chamfered foot: stands on a surface with no overhang
module cbox(size, r) { hull() for (x = [r, size[0] - r], y = [r, size[1] - r]) { translate([x, y, size[2] - r]) sphere(r = r, $fn = 16); translate([x, y, 0]) cylinder(h = 1.3 * r, r1 = 0.05, r2 = r, $fn = 16); } }
// Minkowski tool: round above, 37 deg chamfer below (no rounded overhang at the bed)
module pebble(r) { hull() { intersection() { sphere(r = r, $fn = 16); translate([-r, -r, 0]) cube([2 * r, 2 * r, r]); } translate([0, 0, -1.3 * r]) cylinder(h = 0.01, r = 0.05, $fn = 8); } }
// Horizontal teardrop hole along Y, point up (40 deg roof)
module tport(r, len) { rotate([90, 0, 0]) linear_extrude(len, center = true) hull() { circle(r = r, $fn = 24); translate([0, 1.56 * r]) square(0.02, center = true); } }
module tug_outline(s = 1) { scale([s, s]) offset(r = 3) offset(delta = -3) hull() { translate([-26, -15]) square([12, 30]); translate([6, 0]) circle(d = 30); translate([28, 0]) circle(r = 3); } }"""

#: file stem -> (module name, body)
PARTS = {}

#: tug in the spirit of 3DBenchy: bridges (pointed windows, gabled cabin
#: ceiling), flared hull, rub rail, deck planks, bollards, capstan, life rings,
#: countersunk teardrop portholes, banded chimney, roof rail, mast, V-carved name
PARTS["Benchy-style tug"] = ("Benchy_style_tug", r"""
    color("#e8533f") union() {
        difference() {
            union() {
                minkowski() { hull() { translate([0, 0, 1.3]) linear_extrude(0.01) offset(r = -1) tug_outline(0.78); translate([0, 0, 14.9]) linear_extrude(0.01) offset(r = -1) tug_outline(1); } pebble(1); }  // Hull
                hull() { translate([0, 0, 11]) linear_extrude(0.01) tug_outline(0.937); translate([0, 0, 13.6]) linear_extrude(1.6) offset(r = 0.6) tug_outline(0.992); }  // Rub rail
                translate([-18, -11, 10]) rbox([24, 22, 23], 1.5);  // Cabin
                hull() { translate([0, 0, 30.8]) linear_extrude(0.1) translate([-16.5, -9.5]) offset(r = 1.5) square([21, 19]); translate([-19.5, -12.5, 33]) rbox([27, 25, 2], 0.8); }  // Roof
                translate([-8, 0, 34]) cylinder(h = 11.3, r = 4.5);  // Chimney
                translate([-8, 0, 40]) cylinder(h = 0.75, r1 = 4.5, r2 = 5.1);  // Chimney band
                translate([-8, 0, 40.7]) cylinder(h = 0.9, r = 5.1);  // Chimney band
                translate([-8, 0, 41.5]) cylinder(h = 0.6, r1 = 5.1, r2 = 4.5);  // Chimney band
                translate([-8, 0, 45.3]) cylinder(h = 0.65, r1 = 4.5, r2 = 5);  // Chimney lip
                translate([-8, 0, 45.9]) cylinder(h = 0.85, r = 5);  // Chimney lip
                translate([-21, 9, 11.5]) cylinder(h = 5, r = 2.5);  // Rod holder
            }
            difference() { translate([0, 0, 12]) linear_extrude(5) offset(r = -2.4) tug_outline(1); translate([-19, -12, 9]) cube([26, 24, 9]); translate([-21, 9, 9]) cylinder(h = 9, r = 2.5); }  // Deck well
            difference() { intersection() { translate([0, 0, 11.6]) linear_extrude(1) offset(r = -2.6) tug_outline(1); for (y = [-9.9 : 2.2 : 10]) translate([-30, y - 0.25, 11.6]) cube([62, 0.5, 1]); } translate([-19, -12, 11]) cube([26, 24, 2]); translate([-21, 9, 11]) cylinder(h = 2, r = 2.7); }  // Deck planks
            hull() { translate([-16, -9, 12]) cube([20, 18, 10]); translate([-16, -0.01, 12]) cube([20, 0.02, 19.3]); }  // Cabin inside, gabled ceiling
            translate([-8, 0, 29]) cylinder(h = 20, r = 3);  // Chimney bore
            hull() { translate([-20, -4, 12]) cube([5, 8, 9]); translate([-20, -0.01, 25.4]) cube([5, 0.02, 0.01]); }  // Rear door, pointed
            hull() { translate([-18.6, -4.8, 12]) cube([1.1, 9.6, 9]); translate([-18.6, -0.01, 26.4]) cube([1.1, 0.02, 0.01]); }  // Door frame
            translate([3, -6, 18]) rotate([90, 0, 90]) linear_extrude(5) polygon([[0, 0], [12, 0], [12, 4], [6, 10], [0, 4]]);  // Front window
            translate([5.5, -6, 18]) rotate([90, 0, 90]) linear_extrude(1) offset(delta = 0.8) polygon([[0, 0], [12, 0], [12, 4], [6, 10], [0, 4]]);  // Front window frame
            for (x = [-14, -5]) translate([x, 14, 18]) rotate([90, 0, 0]) linear_extrude(28) polygon([[0, 0], [6, 0], [6, 4], [3, 7], [0, 4]]);  // Side windows
            for (x = [-14, -5]) translate([x, -10.5, 18]) rotate([90, 0, 0]) linear_extrude(1) offset(delta = 0.8) polygon([[0, 0], [6, 0], [6, 4], [3, 7], [0, 4]]);  // Window frames
            for (x = [-14, -5]) translate([x, 11.5, 18]) rotate([90, 0, 0]) linear_extrude(1) offset(delta = 0.8) polygon([[0, 0], [6, 0], [6, 4], [3, 7], [0, 4]]);  // Window frames
            for (y = [-11, 11]) translate([-6, y, 28]) scale([1, 1, 1.3]) rotate([45, 0, 0]) cube([22, 0.8, 0.8], center = true);  // Beltline groove
            translate([-18, 0, 28]) scale([1, 1, 1.3]) rotate([0, 45, 0]) cube([0.8, 20, 0.8], center = true);  // Beltline groove
            translate([-21, 9, 12.5]) cylinder(h = 6, r = 1.4);  // Rod bore
            for (x = [-10, 0, 10]) translate([x, 0, 6]) tport(1.6, 40);  // Portholes
            for (p = [[-10, 12.84], [0, 12.84], [10, 11.88]]) translate([p[0], p[1] - 0.8, 6]) rotate([-90, 0, 0]) cylinder(h = 1.5, r1 = 1.6, r2 = 3.74);  // Porthole chamfers
            for (p = [[-10, 12.84], [0, 12.84], [10, 11.88]]) translate([p[0], 0.8 - p[1], 6]) rotate([90, 0, 0]) cylinder(h = 1.5, r1 = 1.6, r2 = 3.74);  // Porthole chamfers
            translate([5.55, 0, 14.6]) rotate([90, 0, 90]) minkowski() { linear_extrude(0.01) text("KHERVE", size = 2.6, halign = "center", valign = "center"); cylinder(h = 1.05, r1 = 0, r2 = 1.26, $fn = 8); }  // Name board
        }
        for (p = [[17, 4.4], [17, -4.4], [-22.5, 4.5], [-22.5, -4.5]]) translate([p[0], p[1], 11.5]) { cylinder(h = 3, r = 1); translate([0, 0, 2.95]) cylinder(h = 0.5, r1 = 1, r2 = 1.4); translate([0, 0, 3.4]) cylinder(h = 0.7, r = 1.4); }  // Bollards
        translate([20, 0, 11.5]) { cylinder(h = 2.5, r = 2); translate([0, 0, 2.45]) cylinder(h = 0.6, r1 = 2, r2 = 1.5); translate([0, 0, 3]) cylinder(h = 1.75, r = 1.5); translate([0, 0, 4.65]) cylinder(h = 0.5, r1 = 1.5, r2 = 1.9); translate([0, 0, 5.1]) cylinder(h = 0.7, r = 1.9); }  // Capstan
        translate([8.5, -3, 11.5]) cbox([5, 6, 1.8], 0.6);  // Bow hatch
        translate([10.5, -1.5, 13.1]) cbox([1, 3, 0.9], 0.3);  // Hatch handle
        for (s = [-1, 1]) translate([-11, s * 11, 15]) rotate([-90 * s, 0, 0]) rotate_extrude($fn = 40) polygon([[1.5, 0], [2.7, 0], [2.35, 0.3], [2.1, 0.4], [1.85, 0.3]]);  // Life rings
        translate([0, 0, 34.6]) linear_extrude(1.8) difference() { translate([-18.6, -11.6]) offset(r = 1) offset(delta = -1) square([25.2, 23.2]); translate([-17.8, -10.8]) offset(r = 0.4) offset(delta = -0.4) square([23.6, 21.6]); }  // Roof rail
        translate([2, 0, 34.5]) cylinder(h = 8.5, r = 0.8, $fn = 16);  // Mast
        translate([2, 0, 42.95]) cylinder(h = 1.05, r1 = 0.8, r2 = 0.3, $fn = 16);  // Mast tip
        for (a = [40, -40]) translate([2, 0, 40]) rotate([a, 0, 0]) cylinder(h = 4, r = 0.5, $fn = 12);  // Yard arms
    }
""")

#: sailboat: 1.6 mm sails with V-groove seams and a V-carved number,
#: boom, shrouds, pennant, stanchions, winches, cockpit wells, rudder
PARTS["Benchy-style sailboat"] = ("Benchy_style_sailboat", r"""
    color("#f5f5f0") union() {
        difference() {
            union() {
                minkowski() { hull() { translate([-22, 0, 1.3]) scale([1, 0.5, 1]) cylinder(h = 0.01, r = 10); translate([0, 0, 1.3]) scale([2.6, 0.5, 1]) cylinder(h = 0.01, r = 9); translate([-24, 0, 11.9]) scale([1, 0.55, 1]) cylinder(h = 0.01, r = 12); translate([2, 0, 11.9]) scale([2.8, 0.55, 1]) cylinder(h = 0.01, r = 10); } pebble(1); }  // Hull
                translate([-16, -4.5, 11.9]) cbox([8, 9, 4.6], 1.2);  // Coachroof
                translate([-6, 0, 10]) cylinder(h = 48, r = 1.4);  // Mast
                translate([-6, 0, 57.95]) cylinder(h = 2.05, r1 = 1.4, r2 = 0.5);  // Mast tip
                translate([0, 0.8, 0]) rotate([90, 0, 0]) linear_extrude(1.6) offset(r = 0.6) polygon([[-4.5, 11], [18, 11], [18, 16], [-4.5, 55]]);  // Jib
                translate([0, 0.8, 0]) rotate([90, 0, 0]) linear_extrude(1.6) offset(r = 0.6) polygon([[-7.5, 11], [-7.5, 54], [-26, 16], [-26, 11]]);  // Main sail
                translate([-16.6, 0, 15]) scale([1, 1, 1.3]) rotate([45, 0, 0]) cube([19.6, 1.8, 1.8], center = true);  // Boom
            }
            translate([-25, 1.4, 10]) rbox([7, 2.8, 6], 1);  // Cockpit well
            translate([-25, -4.2, 10]) rbox([7, 2.8, 6], 1);  // Cockpit well
            for (x = [-15, -11]) translate([x, 0, 14.2]) tport(0.9, 12);  // Coachroof ports
            for (x = [-14, 2, 10]) translate([x, 0, 5]) tport(1.3, 40);  // Hull portholes
            for (z = [20, 28, 36, 44]) for (y = [-0.8, 0.8]) translate([-17.4, y, z]) scale([1, 1, 1.3]) rotate([45, 0, 0]) cube([18.4, 0.5, 0.5], center = true);  // Main sail seams
            for (z = [20, 28, 36, 44]) for (y = [-0.8, 0.8]) translate([7.4, y, z]) scale([1, 1, 1.3]) rotate([45, 0, 0]) cube([22.4, 0.5, 0.5], center = true);  // Jib seams
            translate([-14, -0.4, 24]) rotate([90, 0, 0]) minkowski() { linear_extrude(0.01) text("K7", size = 3.4, halign = "center", valign = "center"); cylinder(h = 1.00, r1 = 0, r2 = 1.20, $fn = 8); }  // Sail number
            translate([-14, 0.4, 24]) rotate([90, 0, 180]) minkowski() { linear_extrude(0.01) text("K7", size = 3.4, halign = "center", valign = "center"); cylinder(h = 1.00, r1 = 0, r2 = 1.20, $fn = 8); }  // Sail number
        }
        for (p = [[-30, 4.8], [-30, -4.8], [-20, 5.2], [-20, -5.2], [4, 4.5], [4, -4.5], [14, 3.9], [14, -3.9], [22, 2.8], [22, -2.8]]) translate([p[0], p[1], 12]) { cylinder(h = 4, r = 0.55, $fn = 12); translate([0, 0, 3.95]) cylinder(h = 0.45, r1 = 0.55, r2 = 0.2, $fn = 12); }  // Stanchions
        for (s = [-1, 1]) hull() { translate([-6, 0, 52]) sphere(r = 0.5, $fn = 12); translate([-6, s * 4.6, 12.4]) sphere(r = 0.5, $fn = 12); }  // Shrouds
        translate([0, 0.4, 0]) rotate([90, 0, 0]) linear_extrude(0.8) polygon([[-5.6, 54], [-2, 58.5], [-5.6, 59.3]]);  // Pennant
        for (y = [-3, 3]) translate([-10, y, 16]) { cylinder(h = 1.2, r = 0.9, $fn = 16); translate([0, 0, 1.15]) cylinder(h = 0.45, r1 = 0.9, r2 = 0.5, $fn = 16); }  // Winches
        translate([6, -2.5, 12.4]) cbox([4.5, 5, 1.3], 0.5);  // Fore hatch
        translate([24, 0.6, 12.6]) rotate([90, 0, 0]) linear_extrude(1.2) polygon([[-1, 0], [1, 0], [1, 0.6], [2.2, 1.9], [2.2, 2.4], [0, 2], [-2.2, 2.4], [-2.2, 1.9], [-1, 0.6]]);  // Bow cleat
        translate([0, 0.8, 0]) rotate([90, 0, 0]) linear_extrude(1.6) polygon([[-31, 0], [-35.5, 0], [-35.5, 6], [-34, 9.5], [-31, 9.5]]);  // Rudder
    }
""")

#: submarine on a flat keel cut 0.64 r below the axis (40 deg at the cut):
#: deck casing with planks, hatches, conning tower, dihedral planes, X propeller
#: whose lower blades stand on the bed, periscope, snorkel, torpedo tubes
PARTS["Benchy-style submarine"] = ("Benchy_style_submarine", r"""
    color("#f5d547") union() {
        difference() {
            union() {
                intersection() { translate([0, 0, 4.5]) hull() { translate([-20, 0, 0]) sphere(r = 7, $fn = 40); translate([12, 0, 0]) sphere(r = 9, $fn = 40); } translate([-40, -20, 0]) cube([80, 40, 40]); }  // Hull, flat bottom
                hull() { translate([-16, -2, 8]) cube([0.1, 4, 5.35]); translate([11.9, -2, 8]) cube([0.1, 4, 7.1]); translate([14, -2, 8]) cube([0.1, 4, 6.87]); }  // Deck casing
                hull() { translate([5, 0, 10]) cylinder(h = 9.5, r = 3.2); translate([-4, 0, 10]) cylinder(h = 9.5, r = 1.4); translate([5, 0, 19.5]) scale([1, 1, 0.35]) sphere(r = 3.2, $fn = 24); translate([-4, 0, 19.5]) scale([1, 1, 0.35]) sphere(r = 1.4, $fn = 16); }  // Conning tower
                hull() { translate([1, -2.4, 12.5]) cube([4, 4.8, 0.1]); translate([1.5, -6.4, 16.6]) cube([3, 12.8, 0.6]); }  // Sail planes
                hull() { translate([16, -5, 6]) cube([3, 10, 0.1]); translate([16.5, -9, 10.4]) cube([2, 18, 0.6]); }  // Bow planes
                hull() { translate([-23, -4.5, 6]) cube([3, 9, 0.1]); translate([-22.5, -8.5, 10.4]) cube([2, 17, 0.6]); }  // Stern planes
                hull() { translate([-24, -0.7, 4]) cube([5, 1.4, 0.1]); translate([-22.5, -0.7, 13.5]) cube([2.5, 1.4, 0.1]); }  // Rudder
                translate([-27.6, -0.6, 0]) cube([2.8, 1.2, 2]);  // Shaft skeg
                translate([-26.2, 0, 4.5]) rotate([0, -90, 0]) linear_extrude(1.2) hull() { circle(r = 2.2, $fn = 24); translate([-3.2, 0]) square(0.1, center = true); }  // Propeller hub
                translate([-27.4, 0, 4.5]) rotate([0, -90, 0]) cylinder(h = 1.2, r1 = 2.2, r2 = 0.8, $fn = 24);  // Hub cone
                intersection() { union() { for (a = [30, -30]) translate([-27.5, 0, 4.5]) rotate([a, 0, 0]) hull() { rotate([0, 90, 0]) cylinder(h = 1, r = 1.1, center = true, $fn = 16); translate([0, 0, 4.6]) rotate([0, 90, 0]) cylinder(h = 1, r = 0.7, center = true, $fn = 16); } for (a = [150, -150]) translate([-27.5, 0, 4.5]) rotate([a, 0, 0]) hull() { rotate([0, 90, 0]) cylinder(h = 1, r = 1.1, center = true, $fn = 16); translate([0, 0, 6.2]) rotate([0, 90, 0]) cylinder(h = 1, r = 0.7, center = true, $fn = 16); } } translate([-35, -10, 0]) cube([10, 20, 20]); }  // Propeller blades
                translate([1.5, 0, 19]) cylinder(h = 7.5, r = 0.7, $fn = 16);  // Periscope
                translate([1.5, 0, 26.5]) hull() { cylinder(h = 0.1, r = 0.7, $fn = 16); translate([2, 0, 3]) sphere(r = 0.7, $fn = 16); }  // Periscope head
                translate([4.5, 0, 19]) cylinder(h = 5, r = 0.8, $fn = 16);  // Snorkel
                translate([4.5, 0, 23.95]) cylinder(h = 0.85, r1 = 0.8, r2 = 0.3, $fn = 16);  // Snorkel cap
                translate([-2.5, 0, 19]) cylinder(h = 6, r = 0.4, $fn = 12);  // Antenna
                translate([-2.5, 0, 24.95]) cylinder(h = 0.55, r1 = 0.4, r2 = 0.15, $fn = 12);  // Antenna tip
            }
            for (x = [-14, -5, 5, 14]) translate([x, 0, 6]) tport(1.6, 40);  // Portholes
            for (y = [-3, 3]) translate([20, y, 5]) rotate([0, 0, 90]) tport(1, 6);  // Torpedo tubes
            for (x = [3, 5, 7]) translate([x, 0, 17.5]) tport(0.6, 10);  // Bridge windows
            translate([-1.53, 1.58, 15.5]) rotate([0, 0, 11.54]) rotate([90, 0, 180]) minkowski() { linear_extrude(0.01) text("K1", size = 2.6, halign = "center", valign = "center"); cylinder(h = 0.95, r1 = 0, r2 = 1.14, $fn = 8); }  // Hull number
            translate([-1.53, -1.58, 15.5]) rotate([0, 0, -11.54]) rotate([90, 0, 0]) minkowski() { linear_extrude(0.01) text("K1", size = 2.6, halign = "center", valign = "center"); cylinder(h = 0.95, r1 = 0, r2 = 1.14, $fn = 8); }  // Hull number
            for (x = [-15 : 1.2 : -7]) translate([x, -3, 13.05 + (x + 16) * 0.0627]) cube([0.3, 6, 2]);  // Deck planks
            for (x = [9.5 : 1.2 : 11.5]) translate([x, -3, 13.05 + (x + 16) * 0.0627]) cube([0.3, 6, 2]);  // Deck planks
        }
        translate([-10, 0, 13.3]) cylinder(h = 0.9, r = 1.3, $fn = 24);  // Aft hatch
        translate([-10.7, -0.25, 14.2]) cbox([1.4, 0.5, 0.5], 0.2);  // Hatch handle
        translate([10.5, 0, 14.5]) cylinder(h = 1, r = 1.3, $fn = 24);  // Fore hatch
        translate([9.8, -0.25, 15.5]) cbox([1.4, 0.5, 0.5], 0.2);  // Hatch handle
    }
""")

#: speedboat: cockpit with bench, bucket seats, console and a hex wheel
#: (flat side down), slanted windscreen, outboard on the bed, cleats, posts
PARTS["Benchy-style speedboat"] = ("Benchy_style_speedboat", r"""
    color("#4a7fd6") union() {
        difference() {
            union() {
                minkowski() { hull() { translate([-24, -9, 1.3]) cube([2, 18, 0.01]); translate([14, 0, 1.3]) scale([2, 0.9, 1]) cylinder(h = 0.01, r = 7); translate([-25, -11, 9.9]) cube([2, 22, 0.01]); translate([16, 0, 9.9]) scale([2.1, 1, 1]) cylinder(h = 0.01, r = 9); } pebble(1); }  // Hull
                hull() { translate([0, -8.5, 10]) rbox([1.8, 17, 1.8], 0.7); translate([-3.4, -8, 15]) rbox([1.6, 16, 1.6], 0.7); }  // Windscreen
                hull() { translate([-29, -1.2, 0]) cube([3, 2.4, 4]); translate([-30.5, -3, 8.5]) rbox([6, 6, 6.5], 1.5); }  // Outboard motor
            }
            translate([-19, -7, 6]) rbox([13, 14, 9], 1.5);  // Cockpit
            translate([19, 0, 10.4]) linear_extrude(1) text("KHERVE", size = 3, halign = "center", valign = "center");  // Deck name
            for (z = [11, 12.6]) for (y = [-3, 3]) translate([-27.5, y, z]) scale([1, 1, 1.3]) rotate([45, 0, 0]) cube([4.4, 0.6, 0.6], center = true);  // Cowling vents
        }
        translate([-19, -7, 5]) cbox([3.5, 14, 4.5], 1);  // Rear bench
        for (y = [-4.8, 1.2]) translate([-12.5, y, 5.5]) cbox([3.5, 3.6, 2.5], 0.8);  // Seat bases
        for (y = [-4.8, 1.2]) translate([-13.4, y, 5.5]) cbox([1.4, 3.6, 5.6], 0.6);  // Seat backs
        translate([-7.6, -6, 5.5]) cbox([1.6, 4, 4], 0.5);  // Console
        translate([-7, -4, 10.79]) rotate([90, 0, 90]) linear_extrude(0.6, center = true) difference() { circle(r = 1.6, $fn = 6); circle(r = 0.9, $fn = 6); }  // Steering wheel
        translate([5, -3, 10.3]) cbox([5, 6, 1.3], 0.5);  // Fore hatch
        translate([29, 0.6, 10.6]) rotate([90, 0, 0]) linear_extrude(1.2) polygon([[-1, 0], [1, 0], [1, 0.6], [2.2, 1.9], [2.2, 2.4], [0, 2], [-2.2, 2.4], [-2.2, 1.9], [-1, 0.6]]);  // Bow cleat
        for (y = [-7.5, 7.5]) translate([-22.5, y + 0.6, 10.6]) rotate([90, 0, 0]) linear_extrude(1.2) polygon([[-1, 0], [1, 0], [1, 0.6], [2.2, 1.9], [2.2, 2.4], [0, 2], [-2.2, 2.4], [-2.2, 1.9], [-1, 0.6]]);  // Stern cleats
        for (p = [[24, 7], [24, -7], [28, 5.8], [28, -5.8]]) translate([p[0], p[1], 10.4]) { cylinder(h = 3.5, r = 0.55, $fn = 12); translate([0, 0, 3.45]) cylinder(h = 0.45, r1 = 0.55, r2 = 0.2, $fn = 12); }  // Bow rail posts
        translate([32, 0, 10.4]) { cylinder(h = 2.5, r = 0.6, $fn = 12); translate([0, 0, 2.45]) cylinder(h = 0.85, r1 = 0.6, r2 = 1, $fn = 12); translate([0, 0, 3.25]) cylinder(h = 0.8, r1 = 1, r2 = 0.3, $fn = 12); }  // Nav light
    }
""")

#: 20 mm cube, chamfered foot, rounded edges, V-carved X / Y / 20 / maker
PARTS["Calibration cube 20 mm"] = ("Calibration_cube_20_mm", r"""
    color("#4a7fd6") difference() {
        hull() { translate([0.6, 0.6, 0]) cube([18.8, 18.8, 0.01]); for (x = [1, 19], y = [1, 19]) { translate([x, y, 0.8]) cylinder(h = 18.2, r = 1, $fn = 24); translate([x, y, 19]) sphere(r = 1, $fn = 24); } }  // Rounded cube, chamfered foot
        translate([10, 0.6, 10]) rotate([90, 0, 0]) minkowski() { linear_extrude(0.01) text("X", size = 8, halign = "center", valign = "center"); cylinder(h = 1.20, r1 = 0, r2 = 1.44, $fn = 8); }  // X
        translate([19.4, 10, 10]) rotate([90, 0, 90]) minkowski() { linear_extrude(0.01) text("Y", size = 8, halign = "center", valign = "center"); cylinder(h = 1.20, r1 = 0, r2 = 1.44, $fn = 8); }  // Y
        translate([10, 10, 19.4]) linear_extrude(1) text("Z", size = 9, halign = "center", valign = "center");  // Z
        translate([0.6, 10, 10]) rotate([90, 0, -90]) minkowski() { linear_extrude(0.01) text("20", size = 6.5, halign = "center", valign = "center"); cylinder(h = 1.20, r1 = 0, r2 = 1.44, $fn = 8); }  // Size
        translate([10, 19.6, 10]) rotate([90, 0, 180]) minkowski() { linear_extrude(0.01) text("KHERVE", size = 2.6, halign = "center", valign = "center"); cylinder(h = 1.00, r1 = 0, r2 = 1.20, $fn = 8); }  // Maker
    }
""")

#: planter: 2.4 mm wall, 3 mm floor, drainage, rim chamfered underneath
PARTS["Twisted planter"] = ("Twisted_planter", r"""
    color("#f2a33a") difference() {
        union() {
            linear_extrude(height = 80, twist = 90, scale = 1.3, slices = 80) offset(r = 5) offset(delta = -5) circle(d = 60, $fn = 6);  // Outer wall
            hull() { translate([0, 0, 74.5]) linear_extrude(0.01) rotate(-83.81) scale([1.2794, 1.2794]) offset(r = 5) offset(delta = -5) circle(d = 60, $fn = 6); translate([0, 0, 77]) linear_extrude(3) rotate(-86.63) offset(r = 1.5) scale([1.2888, 1.2888]) offset(r = 5) offset(delta = -5) circle(d = 60, $fn = 6); }  // Rim
        }
        intersection() { linear_extrude(height = 81, twist = 91.125, scale = 1.30375, slices = 80) offset(r = 2.6) offset(delta = -5) circle(d = 60, $fn = 6); translate([-60, -60, 3]) cube([120, 120, 90]); }  // Inside, 2.4 mm wall
        translate([0, 0, -1]) cylinder(h = 5, r = 4);  // Drainage hole
        for (a = [30, 150, 270]) rotate([0, 0, a]) translate([14, 0, -1]) cylinder(h = 5, r = 2.5);  // Drainage holes
    }
""")

#: saucer for the planter: flared wall, ribs the pot stands on
PARTS["Drip saucer"] = ("Drip_saucer", r"""
    color("#f2a33a") union() {
        difference() {
            hull() { linear_extrude(0.01) offset(r = 4.4) offset(r = 5) offset(delta = -5) circle(d = 60, $fn = 6); translate([0, 0, 9]) linear_extrude(0.01) offset(r = 7.4) offset(r = 5) offset(delta = -5) circle(d = 60, $fn = 6); }  // Dish
            hull() { translate([0, 0, 2]) linear_extrude(0.01) offset(r = 2) offset(r = 5) offset(delta = -5) circle(d = 60, $fn = 6); translate([0, 0, 9.01]) linear_extrude(0.01) offset(r = 5.4) offset(r = 5) offset(delta = -5) circle(d = 60, $fn = 6); }  // Well
            translate([0, 0, 1.6]) linear_extrude(1) text("KHERVE", size = 4.5, halign = "center", valign = "center");  // Name
        }
        for (a = [30 : 60 : 330]) rotate([0, 0, a]) translate([9, -0.8, 1.9]) cube([14, 1.6, 1.3]);  // Ribs the pot stands on
    }
""")

#: keychain tag: chamfered foot, raised border, ring boss, raised name
PARTS["Keychain tag"] = ("Keychain_tag", r"""
    color("#9a6fd6") difference() {
        union() {
            minkowski() { translate([0, 0, 1.04]) linear_extrude(1.16) offset(r = 2.4) square([42, 12]); pebble(0.8); }  // Tag
            translate([0, 0, 2.8]) linear_extrude(0.9) difference() { offset(r = 1.9) square([42, 12]); offset(r = 1.1) square([42, 12]); }  // Raised border
            translate([1.5, 6, 2.8]) cylinder(h = 0.9, r = 3.6);  // Ring boss
            translate([25, 6, 2.8]) linear_extrude(1) offset(r = 0.2) text("KHERVE", size = 6, halign = "center", valign = "center");  // Raised name
        }
        translate([1.5, 6, -1]) cylinder(h = 6, r = 2.5);  // Key ring hole
    }
""")

#: phone stand, printed on its side: diamond windows, cable hole and V channel
PARTS["Phone stand"] = ("Phone_stand", r"""
    color("#7cc47f") difference() {
        minkowski() { translate([0, 0, 1.56]) linear_extrude(67.24) offset(r = 0.6) offset(r = -1.2) offset(r = 0.6) offset(delta = -1.2) polygon([[0, 0], [80, 0], [80, 16], [75, 16], [75, 5], [67, 5], [36, 72], [28, 72], [57, 5], [0, 5]]); pebble(1.2); }  // Rounded profile, prints on its side
        for (s = [20, 36, 52]) for (z = [17.5, 35, 52.5]) translate([62 - 0.4087 * s, 5 + 0.9127 * s, z]) rotate([0, 0, 24.12]) rotate([0, 90, 0]) linear_extrude(20, center = true) scale([1.25, 1]) rotate(45) square(7, center = true);  // Diamond windows
        translate([71, 2.5, 35]) rotate([90, 0, 0]) linear_extrude(9, center = true) hull() { circle(r = 2.2, $fn = 24); translate([0, 3.43]) square(0.02, center = true); }  // Cable hole
        translate([-1, 0, 0]) rotate([90, 0, 90]) linear_extrude(73) polygon([[-1, 31.5], [-1, 38.5], [2.2, 35]]);  // Cable channel
        translate([79.5, 10.5, 35]) rotate([0, 90, 0]) minkowski() { linear_extrude(0.01) text("KHERVE", size = 5, halign = "center", valign = "center"); cylinder(h = 1.10, r1 = 0, r2 = 1.32, $fn = 8); }  // Name on the lip
    }
""")


def program(stem: str) -> str:
    """The OpenSCAD text of one part, at its own origin."""
    module, body = PARTS[stem]
    return (HEADER + HELPERS + "\n" + f"module {module}() {{\n"
            + body.strip("\n") + "\n}\n" + f"{module}();  // {stem}\n")


def programs() -> dict:
    return {stem: program(stem) for stem in PARTS}


def write(stem: str, text: str, path) -> list:
    """Parse *text* and save it as the .kcad at *path*; returns the
    parser's warnings (a part must produce none)."""
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
    return library_kcad.PARTS_DIR / SECTION


def _off(path):
    """(vertices, triangles) of an OFF file."""
    import numpy as np
    lines = [ln for ln in Path(path).read_text().split("\n")
             if ln.strip() and not ln.startswith("#")]
    nv, nf = map(int, lines[1].split()[:2])
    verts = np.array([[float(v) for v in ln.split()[:3]]
                      for ln in lines[2:2 + nv]])
    tris = []
    for ln in lines[2 + nv:2 + nv + nf]:
        q = [int(v) for v in ln.split()]
        tris += [[q[1], q[k], q[k + 1]] for k in range(2, q[0])]
    return verts, np.array(tris)


def openscad_binary() -> str:
    """OpenSCAD for the check — found even where the test suite has
    switched the app's engine off (KHERVECAD_DISABLE_ENGINE)."""
    import shutil
    from khervecad import engine
    found = engine.bundled_openscad() or shutil.which("openscad")
    return found or next((c for c in engine._CANDIDATES
                          if Path(c).exists()), "")


def printability(text: str, openscad: str) -> dict:
    """Render *text* with OpenSCAD and judge it for a support-free
    print: `pieces` (closed solids), `zmin`, `bed_mm2` (area flat on
    the plate) and `overhang_mm2` (faces more than 0.3 mm up looking
    down steeper than 45°)."""
    import numpy as np
    import manifold3d as mf
    with tempfile.TemporaryDirectory() as tmp:
        src, out = Path(tmp) / "part.scad", Path(tmp) / "part.off"
        src.write_text(text)
        args = [openscad, "-o", str(out), str(src)]
        from khervecad import engine
        args[1:1] = engine.backend_args(openscad)
        subprocess.run(args, capture_output=True, check=True)
        verts, tris = _off(out)
    solid = mf.Manifold(mf.Mesh(vert_properties=verts.astype(np.float32),
                                tri_verts=tris.astype(np.uint32)))
    a, b, c = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
    n = np.cross(b - a, c - a)
    length = np.maximum(np.linalg.norm(n, axis=1), 1e-12)
    area, nz = length / 2, n[:, 2] / length
    cz = (a[:, 2] + b[:, 2] + c[:, 2]) / 3
    z0 = verts[:, 2].min()
    return {"pieces": len(solid.decompose()), "zmin": float(z0),
            "bed_mm2": float(area[(nz < -0.999) & (cz < z0 + 0.05)].sum()),
            "overhang_mm2": float(area[(nz < -0.7072)
                                       & (cz > z0 + 0.3)].sum())}


def main(argv=None):
    import argparse
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
    ap = argparse.ArgumentParser(description="Rewrite the Test parts "
                                             "for printer library.")
    ap.add_argument("--check", action="store_true",
                    help="render each part with OpenSCAD and judge it")
    args = ap.parse_args(argv)
    into = folder()
    into.mkdir(parents=True, exist_ok=True)
    for stem, text in programs().items():
        warnings = write(stem, text, into / f"{stem}.kcad")
        print(f"wrote {stem}.kcad" + (f"  ({len(warnings)} warnings)"
                                       if warnings else ""))
        if args.check:
            print("    ", printability(text, openscad_binary()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
