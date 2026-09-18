"""Mechanisms & motion (Library ▸ Engineering): working mechanisms driven
by Customizer sliders — a gear pair, crank and piston, rack and pinion,
cam and follower, four-bar linkage, planetary gearset, XY platform,
scissor lift and a robot arm, most with their motor.

Each is an OpenSCAD program whose moving parts read an annotated
variable (``angle = 0;  // [0:5:720]``), so the Customizer panel shows a
slider and its ▶ runs the mechanism. Inserting one ADDS it: its
variables become document globals under a prefix of their own
(``crank_angle``, then ``crank2_angle`` for a second copy) with their
Customizer groups named after the mechanism, and its Objects land beside
whatever is already in the document. Moving parts are gears, capsules,
cylinders and boxes — no booleans — so every frame previews exactly.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import re

CATEGORY = "Mechanisms & motion"

_MOTOR = '#34383d'
_STEEL = '#c9ccd1'
_FRAME = '#8a8f96'

GEAR_PAIR = f"""
/* [Motion] */
// Motor angle — press play to turn the gears
angle = 0;  // [0:5:720]
/* [Gears] */
// Teeth on the motor's gear
small_teeth = 12;  // [8:1:24]
// Teeth on the driven gear
big_teeth = 24;  // [16:1:40]
/* [Hidden] */
m = 2;
centre = m * (small_teeth + big_teeth) / 2;
module Motor() {{
    color("{_MOTOR}") translate([0, 0, -26]) cylinder(h = 24, r = 11, $fn = 24);  // Motor body
    color("{_STEEL}") translate([0, 0, -2]) cylinder(h = 8, r = 2.4, $fn = 12);  // Motor shaft
}}
module Drive_gear() {{
    color("#f07b2c") rotate([0, 0, angle]) kcad_gear(kind = "spur", m = m, teeth = small_teeth, thickness = 6, bore = 5, backlash = 0.2, detail = 3);  // Drive gear
}}
module Driven_gear() {{
    color("#2f6fb3") translate([centre, 0, 0]) rotate([0, 0, 180 / big_teeth - angle * small_teeth / big_teeth]) kcad_gear(kind = "spur", m = m, teeth = big_teeth, thickness = 6, bore = 8, backlash = 0.2, detail = 3);  // Driven gear
}}
Motor();
Drive_gear();
Driven_gear();
"""

CRANK = f"""
/* [Motion] */
// Motor angle — press play to run the engine
angle = 0;  // [0:5:720]
/* [Gears] */
// Teeth on the motor's gear
small_teeth = 12;  // [8:1:20]
// Teeth on the crank gear
big_teeth = 24;  // [20:1:36]
/* [Crank and piston] */
// Crank pin distance from the gear's centre
throw = 10;  // [6:1:14]
// Connecting rod length, pin to pin
rod_len = 60;  // [50:5:90]
/* [Hidden] */
m = 2;
centre = m * (small_teeth + big_teeth) / 2;
big_turn = -angle * small_teeth / big_teeth;
pin_x = centre + throw * cos(big_turn);
pin_y = throw * sin(big_turn);
piston_x = pin_x + sqrt(rod_len * rod_len - pin_y * pin_y);
module Motor() {{
    color("{_MOTOR}") translate([0, 0, -26]) cylinder(h = 24, r = 11, $fn = 24);  // Motor body
    color("{_STEEL}") translate([0, 0, -2]) cylinder(h = 8, r = 2.4, $fn = 12);  // Motor shaft
}}
module Drive_gear() {{
    color("#f07b2c") rotate([0, 0, angle]) kcad_gear(kind = "spur", m = m, teeth = small_teeth, thickness = 6, bore = 5, backlash = 0.2, detail = 3);  // Drive gear
}}
module Crank_gear() {{
    color("#2f6fb3") translate([centre, 0, 0]) rotate([0, 0, 180 / big_teeth + big_turn]) kcad_gear(kind = "spur", m = m, teeth = big_teeth, thickness = 6, bore = 8, backlash = 0.2, detail = 3);  // Crank gear
}}
module Crank_pin() {{
    color("{_STEEL}") translate([pin_x, pin_y, 6]) cylinder(h = 7, r = 2.5, $fn = 16);  // Crank pin
}}
module Connecting_rod() {{
    color("#3f9e5a") kcad_capsule(a = [pin_x, pin_y, 10], b = [piston_x, 0, 10], r = 2.5, $fn = 16);  // Connecting rod
}}
module Piston() {{
    color("#c9423a") translate([piston_x - 8, -7, 3]) cube([16, 14, 14]);  // Piston
}}
module Guide() {{
    color("{_FRAME}") translate([centre + 28, -9.5, 0]) cube([rod_len + throw + 20, 2, 18]);  // Lower guide rail
    color("{_FRAME}") translate([centre + 28, 7.5, 0]) cube([rod_len + throw + 20, 2, 18]);  // Upper guide rail
}}
Motor();
Drive_gear();
Crank_gear();
Crank_pin();
Connecting_rod();
Piston();
Guide();
"""

RACK = f"""
/* [Motion] */
// Motor angle — press play to slide the rack
angle = 0;  // [0:5:360]
/* [Gears] */
// Teeth on the pinion
pinion_teeth = 14;  // [10:1:24]
/* [Hidden] */
m = 2;
pitch = PI * m;
travel = angle / 360 * pitch * pinion_teeth;
module Motor() {{
    color("{_MOTOR}") translate([0, m * pinion_teeth / 2, -26]) cylinder(h = 24, r = 11, $fn = 24);  // Motor body
    color("{_STEEL}") translate([0, m * pinion_teeth / 2, -2]) cylinder(h = 8, r = 2.4, $fn = 12);  // Motor shaft
}}
module Pinion() {{
    color("#f07b2c") translate([0, m * pinion_teeth / 2, 0]) rotate([0, 0, angle - 90]) kcad_gear(kind = "spur", m = m, teeth = pinion_teeth, thickness = 6, bore = 5, backlash = 0.2, detail = 3);  // Pinion
}}
module Rack() {{
    color("#2f6fb3") translate([travel - (pinion_teeth + 2) * pitch, 0, 0]) kcad_gear(kind = "rack", m = m, thickness = 6, backlash = 0.2, rim = 5, length = (2 * pinion_teeth + 4) * pitch);  // Rack
}}
module Rails() {{
    color("{_FRAME}") translate([-(pinion_teeth + 3) * pitch, -2.4 * m - 9, -2]) cube([(2 * pinion_teeth + 6) * pitch, 4, 10]);  // Rack guide
}}
Motor();
Pinion();
Rack();
Rails();
"""

CAM = f"""
/* [Motion] */
// Motor angle — press play to lift the follower
angle = 0;  // [0:5:720]
/* [Cam] */
// How far the cam's centre sits off the shaft (half the lift)
lift = 8;  // [2:1:12]
// Cam radius
cam_r = 20;  // [14:1:30]
/* [Hidden] */
follow_z = cam_r + lift * sin(angle);
module Motor() {{
    color("{_MOTOR}") translate([0, 12, 0]) rotate([-90, 0, 0]) cylinder(h = 24, r = 11, $fn = 24);  // Motor body
    color("{_STEEL}") translate([0, -8, 0]) rotate([-90, 0, 0]) cylinder(h = 20, r = 2.5, $fn = 12);  // Shaft
}}
module Cam() {{
    color("#f07b2c") rotate([0, -angle, 0]) translate([lift, -6, 0]) rotate([-90, 0, 0]) cylinder(h = 10, r = cam_r, $fn = 48);  // Eccentric cam
}}
module Follower() {{
    color("#2f6fb3") translate([-20, -9, follow_z]) cube([40, 16, 4]);  // Follower foot
    color("{_STEEL}") translate([0, -1, follow_z + 4]) cylinder(h = 60, r = 4, $fn = 16);  // Follower rod
}}
module Guide() {{
    color("{_FRAME}") translate([-18, -9, cam_r + lift + 22]) cube([12.5, 16, 10]);  // Left guide
    color("{_FRAME}") translate([5.5, -9, cam_r + lift + 22]) cube([12.5, 16, 10]);  // Right guide
}}
Motor();
Cam();
Follower();
Guide();
"""

FOUR_BAR = f"""
/* [Motion] */
// Motor angle — press play to rock the linkage
angle = 0;  // [0:5:720]
/* [Links] */
// Crank, driven by the motor (the shortest link)
crank = 15;  // [8:1:18]
// Coupler, crank pin to rocker pin
coupler = 60;  // [50:1:70]
// Rocker, swinging about the second pivot
rocker = 45;  // [40:1:55]
// Distance between the two fixed pivots
ground = 60;  // [55:1:65]
/* [Hidden] */
bx = crank * cos(angle);
by = crank * sin(angle);
f = sqrt((ground - bx) * (ground - bx) + by * by);
alpha = atan2(by, bx - ground);
beta = acos((rocker * rocker + f * f - coupler * coupler) / (2 * rocker * f));
cx = ground + rocker * cos(alpha - beta);
cy = rocker * sin(alpha - beta);
module Motor() {{
    color("{_MOTOR}") translate([0, 0, -34]) cylinder(h = 24, r = 11, $fn = 24);  // Motor body
}}
module Frame() {{
    color("{_FRAME}") translate([-14, -12, -10]) cube([ground + 28, 24, 6]);  // Base
    color("{_FRAME}") translate([ground, 0, -4]) cylinder(h = 4, r = 6, $fn = 20);  // Rocker post
    color("{_STEEL}") translate([0, 0, -4]) cylinder(h = 6, r = 2.5, $fn = 12);  // Motor shaft
}}
module Crank() {{
    color("#f07b2c") kcad_capsule(a = [0, 0, 2], b = [bx, by, 2], r = 4, $fn = 16);  // Crank
}}
module Coupler() {{
    color("#3f9e5a") kcad_capsule(a = [bx, by, 10], b = [cx, cy, 10], r = 3.5, $fn = 16);  // Coupler
    color("{_STEEL}") translate([bx, by, 2]) cylinder(h = 8, r = 1.8, $fn = 12);  // Crank pin
}}
module Rocker() {{
    color("#2f6fb3") kcad_capsule(a = [ground, 0, 2], b = [cx, cy, 2], r = 4, $fn = 16);  // Rocker
    color("{_STEEL}") translate([cx, cy, 2]) cylinder(h = 8, r = 1.8, $fn = 12);  // Rocker pin
}}
Motor();
Frame();
Crank();
Coupler();
Rocker();
"""

PLANETARY = f"""
/* [Motion] */
// Motor (sun) angle — press play to turn the planets
angle = 0;  // [0:10:1440]
/* [Gears] */
// Teeth on the sun gear
sun_teeth = 12;  // [9:3:18]
// Teeth on each planet
planet_teeth = 12;  // [9:3:18]
/* [Hidden] */
m = 1.5;
ring_teeth = sun_teeth + 2 * planet_teeth;
orbit = m * (sun_teeth + planet_teeth) / 2;
carrier = angle * sun_teeth / (sun_teeth + ring_teeth);
module Motor() {{
    color("{_MOTOR}") translate([0, 0, -30]) cylinder(h = 24, r = 11, $fn = 24);  // Motor body
    color("{_STEEL}") translate([0, 0, -6]) cylinder(h = 12, r = 2.4, $fn = 12);  // Motor shaft
}}
module Sun() {{
    color("#f07b2c") rotate([0, 0, angle]) kcad_gear(kind = "spur", m = m, teeth = sun_teeth, thickness = 6, bore = 5, backlash = 0.2, detail = 3);  // Sun gear
}}
module Planets() {{
    for (i = [0 : 2])
        color("#2f6fb3") rotate([0, 0, carrier + 120 * i]) translate([orbit, 0, 0]) rotate([0, 0, 180 - 180 / planet_teeth + (carrier + 120 * i - angle) * sun_teeth / planet_teeth]) kcad_gear(kind = "spur", m = m, teeth = planet_teeth, thickness = 6, bore = 4, backlash = 0.2, detail = 3);  // Planet
}}
module Ring() {{
    color("{_FRAME}") rotate([0, 0, 180 / ring_teeth]) kcad_gear(kind = "internal", m = m, teeth = ring_teeth, thickness = 6, backlash = 0.2, rim = 5, detail = 3);  // Ring gear
}}
module Carrier() {{
    for (i = [0 : 2]) {{
        color("#3f9e5a") kcad_capsule(a = [0, 0, 9], b = [orbit * cos(carrier + 120 * i), orbit * sin(carrier + 120 * i), 9], r = 3, $fn = 12);  // Carrier arm
        color("{_STEEL}") translate([orbit * cos(carrier + 120 * i), orbit * sin(carrier + 120 * i), 0]) cylinder(h = 9, r = 1.9, $fn = 12);  // Planet pin
    }}
    color("{_STEEL}") rotate([0, 0, carrier]) translate([0, 0, 9]) cylinder(h = 20, r = 4, $fn = 6);  // Output shaft
}}
Motor();
Sun();
Planets();
Ring();
Carrier();
"""

XY_TABLE = f"""
/* [Motion] */
// X carriage position — press play to sweep it
x_pos = 0;  // [0:1:60]
// Y table position
y_pos = 0;  // [0:1:50]
module Base() {{
    color("{_FRAME}") cube([170, 120, 6]);  // Base plate
    color("{_FRAME}") translate([10, 10, 6]) cube([10, 100, 18]);  // Left end block
    color("{_FRAME}") translate([150, 10, 6]) cube([10, 100, 18]);  // Right end block
    color("{_STEEL}") translate([10, 25, 16]) rotate([0, 90, 0]) cylinder(h = 150, r = 4, $fn = 16);  // Front X rail
    color("{_STEEL}") translate([10, 95, 16]) rotate([0, 90, 0]) cylinder(h = 150, r = 4, $fn = 16);  // Back X rail
}}
module X_motor() {{
    color("{_MOTOR}") translate([160, 39, 6]) cube([40, 42, 42]);  // X motor
}}
module X_screw() {{
    color("{_STEEL}") translate([20, 60, 16]) rotate([0, 90, 0]) kcad_thread(kind = "trapezoidal", diameter = 8, pitch = 2, length = 130, starts = 1, left_hand = false, internal = false, clearance = 0.2, bore = 0);  // X lead screw
}}
module X_carriage() {{
    color("#2f6fb3") translate([30 + x_pos, 12, 21]) cube([50, 96, 10]);  // X carriage
    color("{_STEEL}") translate([30 + x_pos, 20, 31]) rotate([-90, 0, 0]) cylinder(h = 80, r = 3, $fn = 12);  // Left Y rail
    color("{_STEEL}") translate([80 + x_pos, 20, 31]) rotate([-90, 0, 0]) cylinder(h = 80, r = 3, $fn = 12);  // Right Y rail
    color("{_MOTOR}") translate([35 + x_pos, -30, 21]) cube([40, 42, 30]);  // Y motor
}}
module Y_table() {{
    color("#f07b2c") translate([25 + x_pos, 22 + y_pos, 34]) cube([60, 40, 6]);  // Y table
}}
Base();
X_motor();
X_screw();
X_carriage();
Y_table();
"""

SCISSOR = f"""
/* [Motion] */
// Platform rise — press play to raise and lower it
rise = 60;  // [20:2:170]
/* [Hidden] */
arm = 100;
s = rise / (2 * arm);
c = sqrt(1 - s * s);
span = arm * c;
step = arm * s;
module Base() {{
    color("{_FRAME}") translate([-10, -45, 0]) cube([130, 90, 6]);  // Base frame
    color("{_MOTOR}") translate([125, -21, 6]) cube([40, 42, 42]);  // Motor
    color("{_STEEL}") translate([span, 0, 16]) rotate([0, 90, 0]) cylinder(h = 125 - span, r = 4, $fn = 12);  // Lead screw
    color("#f07b2c") translate([span - 6, -40, 8]) cube([12, 80, 16]);  // Sliding feet
}}
module Arms() {{
    for (side = [-38, 38]) for (k = [0 : 1]) {{
        color("#2f6fb3") kcad_capsule(a = [0, side, 16 + k * step], b = [span, side, 16 + (k + 1) * step], r = 3, $fn = 12);  // Arm
        color("#3f9e5a") kcad_capsule(a = [span, side + (side > 0 ? -7 : 7), 16 + k * step], b = [0, side + (side > 0 ? -7 : 7), 16 + (k + 1) * step], r = 3, $fn = 12);  // Crossing arm
    }}
}}
module Platform() {{
    color("#c9423a") translate([-10, -48, 16 + rise + 3]) cube([130, 96, 6]);  // Platform
}}
Base();
Arms();
Platform();
"""

ROBOT_ARM = f"""
/* [Joints] */
// Base turn — press play to swing it
base_turn = 0;  // [-90:5:90]
// Shoulder lift
shoulder = 45;  // [0:5:110]
// Elbow bend
elbow = -60;  // [-130:5:0]
// Gripper opening
grip = 8;  // [0:1:16]
/* [Hidden] */
upper = 80;
fore = 65;
module Base() {{
    color("{_FRAME}") cylinder(h = 10, r = 35, $fn = 32);  // Base
    color("{_MOTOR}") translate([0, 0, 10]) rotate([0, 0, base_turn]) cylinder(h = 30, r = 18, $fn = 24);  // Turntable motor
}}
module Upper_arm() {{
    color("#f07b2c") rotate([0, 0, base_turn]) translate([0, 0, 50]) rotate([0, -shoulder, 0]) kcad_capsule(a = [0, 0, 0], b = [upper, 0, 0], r = 8, $fn = 16);  // Upper arm
}}
module Forearm() {{
    color("#2f6fb3") rotate([0, 0, base_turn]) translate([0, 0, 50]) rotate([0, -shoulder, 0]) translate([upper, 0, 0]) rotate([0, -elbow, 0]) kcad_capsule(a = [0, 0, 0], b = [fore, 0, 0], r = 6, $fn = 16);  // Forearm
}}
module Gripper() {{
    color("{_STEEL}") rotate([0, 0, base_turn]) translate([0, 0, 50]) rotate([0, -shoulder, 0]) translate([upper, 0, 0]) rotate([0, -elbow, 0]) translate([fore + 6, -grip / 2 - 3, -4]) cube([22, 3, 8]);  // Left finger
    color("{_STEEL}") rotate([0, 0, base_turn]) translate([0, 0, 50]) rotate([0, -shoulder, 0]) translate([upper, 0, 0]) rotate([0, -elbow, 0]) translate([fore + 6, grip / 2, -4]) cube([22, 3, 8]);  // Right finger
}}
Base();
Upper_arm();
Forearm();
Gripper();
"""

#: part id -> (label, variable prefix, program)
MECHANISMS = {
    "motion_gear_pair": ("Motor & gear pair", "gears", GEAR_PAIR),
    "motion_crank": ("Crank & piston with motor", "crank", CRANK),
    "motion_rack": ("Rack & pinion with motor", "rack", RACK),
    "motion_cam": ("Cam & follower with motor", "cam", CAM),
    "motion_four_bar": ("Four-bar linkage", "linkage", FOUR_BAR),
    "motion_planetary": ("Planetary gearset with motor", "planet",
                         PLANETARY),
    "motion_xy_table": ("XY moving platform", "xy", XY_TABLE),
    "motion_scissor": ("Scissor lift platform", "lift", SCISSOR),
    "motion_robot_arm": ("Robot arm (3 joints + gripper)", "arm", ROBOT_ARM),
}

_ASSIGN = re.compile(r"^\s*([A-Za-z_]\w*)\s*=", re.M)


def variables(program: str) -> list:
    return list(dict.fromkeys(_ASSIGN.findall(program)))


def prefixed(program: str, prefix: str) -> str:
    """*program* with every variable it assigns renamed ``prefix_name``
    (strings and comments left alone)."""
    names = variables(program)
    if not names:
        return program
    word = re.compile(r'"[^"]*"|//[^\n]*|/\*.*?\*/|\b('
                      + "|".join(map(re.escape, names)) + r")\b", re.S)

    def rename(match):
        if match.group(1) is None:
            return match.group(0)
        before = program[:match.start()].rsplit("\n", 1)[-1]
        after = program[match.end():]
        # a named argument (kcad_gear(m = m)) keeps its name
        if before.strip() and re.match(r"\s*=(?!=)", after):
            return match.group(0)
        return f"{prefix}_{match.group(1)}"
    return word.sub(rename, program)


def parse(part_id: str, prefix: str = None):
    """(root, label) of a mechanism's program with its variables under
    *prefix* and its Customizer groups named after it."""
    from . import scadparse
    label, default, program = MECHANISMS[part_id]
    # each placed call labelled, so the Objects read "Drive gear"
    program = re.sub(r"^(\w+)\(\);$", lambda m: f"{m.group(1)}();  // "
                     + m.group(1).replace("_", " "), program, flags=re.M)
    root, _warnings = scadparse.parse_scad(
        prefixed(program, prefix or default))
    for node in root.children:
        group = node.params.get("group")
        if node.type == "assign" and group and group != "Hidden":
            node.params["group"] = f"{label} · {group}"
    return root, label


def build(part_id: str, dims=None):
    """The mechanism as ONE node (the Part Library's preview and tests):
    its variables followed by its parts."""
    from .model import CadNode
    root, label = parse(part_id)
    group = CadNode("union", label)
    for node in list(root.children):
        root.remove(node)
        if node.type == "component":
            node.type = "union"
            for key in ("x", "y", "z", "rx", "ry", "rz"):
                node.params.pop(key, None)
        group.add(node)
    return group


def free_prefix(model, base: str) -> str:
    taken = {str(n.params.get("variable", "")) for n in model.global_assigns()}
    prefix, n = base, 1
    while any(v.startswith(prefix + "_") for v in taken):
        n += 1
        prefix = f"{base}{n}"
    return prefix


def insert(part_id: str, model, dims=None):
    """Add the mechanism to *model*: its variables as document globals
    (so its sliders appear in the Customizer), its parts as Objects to
    the right of what the document already holds. Returns the Objects."""
    root, _label = parse(part_id, free_prefix(model,
                                               MECHANISMS[part_id][1]))
    return place(model, root)


def place(model, root):
    """Move *root*'s children into *model*: assigns join the document's
    globals (its Variables group when it has one), everything else
    lands at the top level beside the document's bounding box, Objects
    renamed unique. Returns the Objects added. Shared with the other
    slider-driven libraries (the Solar System's orreries)."""
    from . import anchors, mesh
    offset = 0.0
    if any(c.type not in ("variables", "assign") for c in
           model.root.children):
        try:
            tris = mesh.tessellate(model.root, env=anchors.doc_env(model),
                                   fn=model.effective_fn())
            box = anchors.bbox(tris)
            if box is not None:
                offset = box[1][0] + 60.0
        except Exception:
            offset = 0.0
    names = {c.name for c in model.all_components()}
    index = 0
    for i, child in enumerate(model.root.children):
        if child.type in ("variables", "assign"):
            index = i + 1
    target, at = model.root, index
    for child in model.root.children:
        if child.type == "variables":
            target, at = child, len(child.children)
    added = []
    for node in list(root.children):
        root.remove(node)
        if node.type == "assign":
            target.add(node, at)
            at += 1
            if target is model.root:
                index += 1
            continue
        if node.type == "component":
            base, k = node.name, 1
            while node.name in names:
                k += 1
                node.name = f"{base} {k}"
            names.add(node.name)
            node.params["x"] = float(node.params.get("x") or 0.0) + offset
            added.append(node)
        model.root.add(node)
    model.structure_changed.emit()
    return added


PARTS = {
    pid: dict(label=label, category=CATEGORY,
              sizes={"Standard": {}}, fields=[],
              build=lambda dims, pid=pid: build(pid, dims),
              insert=lambda model, dims, pid=pid: insert(pid, model, dims),
              insert_note="Added as Objects beside the model, driven by "
                          "annotated document variables (prefixed, see "
                          "get_code): change them with set_params on the "
                          "assign nodes, or the Customizer panel's sliders; "
                          "play_motion sets it running.")
    for pid, (label, _prefix, _program) in MECHANISMS.items()
}
