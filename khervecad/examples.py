"""Ready-made example models for the Examples menu.

Each entry builds a complete document tree (a fresh ``root`` node) that
replaces the current document, so a new user can load something real and
take it apart. The examples double as a tour of the app: variables and
expressions, booleans, the part library, the fasteners (hex bolts,
socket screws, nuts), and Masters with Linked copies.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .model import CadNode, DocumentModel


# --------------------------------------------------------------- helpers

def _root(*children) -> CadNode:
    root = CadNode("root")
    for child in children:
        root.add(child)
    return root


def _var(name, value) -> CadNode:
    return CadNode("assign", f"{name} =",
                   dict(variable=name, value=str(value)))


def _cyl(name, radius, height, z=0.0, x=0.0, y=0.0, r2=None,
         segments=64) -> CadNode:
    return CadNode("cylinder", name, dict(
        x=x, y=y, z=z, height=height, radius_bottom=radius,
        radius_top=radius if r2 is None else r2,
        segments=segments, center=False))


def _cube(name, w, d, h, x=0.0, y=0.0, z=0.0, center=False) -> CadNode:
    return CadNode("cube", name, dict(x=x, y=y, z=z, width=w, depth=d,
                                      height=h, center=center))


def _place(node, x=0.0, y=0.0, z=0.0) -> CadNode:
    t = CadNode("translate", "Position", dict(x=x, y=y, z=z))
    t.add(node)
    return t


def _rot(node, x=0.0, y=0.0, z=0.0) -> CadNode:
    r = CadNode("rotate", "Rotate", dict(x=x, y=y, z=z))
    r.add(node)
    return r


def _ring(name, count, builder) -> CadNode:
    """A for-loop that stamps *builder(i)* — a node — every 360/count."""
    count = max(int(count), 1)
    step = 360.0 / count
    loop = CadNode("for_loop", name, dict(
        variable="a", start=0.0, end=360.0 - step / 2, step=step))
    rot = CadNode("rotate", "Around axis", dict(x=0.0, y=0.0, z="a"))
    rot.add(builder)
    loop.add(rot)
    return loop


def _bolt(size, length):
    from . import library
    return library.hex_bolt(dict(library.BOLT_SIZES[size]), length)


def _screw(size, length):
    from . import library
    return library.socket_screw(dict(library.BOLT_SIZES[size]), length)


def _nut(size):
    from . import library
    return library.hex_nut(dict(library.BOLT_SIZES[size]))


def _spur_gear(name, teeth, module_, thickness, bore) -> CadNode:
    """A spur gear: a root disc with trapezoidal teeth stamped round it
    by a for-loop, and a central bore."""
    pr = module_ * teeth / 2.0                # pitch radius
    rr = max(pr - 1.25 * module_, module_)    # root radius
    orr = pr + module_                        # outer radius
    base_w = module_ * 1.5
    tip_w = base_w * 0.55
    gear = CadNode("difference", name)
    body = CadNode("union", f"{name} body")
    body.add(_cyl("Root disc", rr + 0.3, thickness,
                  segments=max(48, teeth * 3)))
    tooth = CadNode("linear_extrude", "Tooth", dict(
        height=thickness, twist=0.0, scale=1.0, center=False,
        segments=0))
    tooth.add(CadNode("polygon", "Tooth profile", dict(
        x=0.0, y=0.0, points=[
            [round(rr - 0.4, 3), round(-base_w / 2, 3)],
            [round(orr, 3), round(-tip_w / 2, 3)],
            [round(orr, 3), round(tip_w / 2, 3)],
            [round(rr - 0.4, 3), round(base_w / 2, 3)]])))
    body.add(_ring("Teeth", teeth, tooth))
    gear.add(body)
    if bore > 0:
        gear.add(_cyl("Bore", bore / 2.0, thickness + 2.0, z=-1.0,
                      segments=48))
    return gear


# --------------------------------------------------------------- builders

def parametric_box() -> CadNode:
    """A hollow, open-topped box driven entirely by variables — edit
    ``w``, ``d``, ``h`` or ``wall`` in the Variables tab and the whole
    part follows."""
    outer = CadNode("cube", "Outer shell",
                    dict(width="w", depth="d", height="h", center=False))
    cavity = CadNode("cube", "Cavity",
                     dict(x="wall", y="wall", z="wall",
                          width="w - 2 * wall", depth="d - 2 * wall",
                          height="h", center=False))
    box = CadNode("difference", "Hollow box")
    box.add(outer)
    box.add(cavity)
    return _root(_var("w", 60), _var("d", 40), _var("h", 30),
                 _var("wall", 2), box)


def l_bracket() -> CadNode:
    """A right-angle mounting bracket: two plates unioned, then two
    fixing holes drilled through the base — the classic boolean idiom."""
    base = CadNode("cube", "Base plate",
                   dict(width=60, depth=40, height=6))
    wall = CadNode("cube", "Upright",
                   dict(width=60, depth=6, height=40))
    body = CadNode("union", "Bracket body")
    body.add(base)
    body.add(wall)
    hole1 = _cyl("Hole 1", 3.2, 8, x=15, y=22, z=-1, segments=32)
    hole2 = _cyl("Hole 2", 3.2, 8, x=45, y=22, z=-1, segments=32)
    bracket = CadNode("difference", "L-bracket")
    bracket.add(body)
    bracket.add(hole1)
    bracket.add(hole2)
    return _root(bracket)


def bolt_and_nut() -> CadNode:
    """A single M10 hex bolt through a plate with a nut on the back —
    the simplest look at the fastener library (a real ISO thread,
    chamfered head and nut)."""
    from . import library
    size = "M10"
    s = library.BOLT_SIZES[size]
    plate_t = 12.0
    length = plate_t + s["nut_h"] + 8.0
    plate = CadNode("difference", "Plate")
    plate.add(_cube("Plate body", 60, 40, plate_t, x=-30, y=-20))
    plate.add(_cyl("Clearance", s["d"] / 2.0 + 0.6, plate_t + 2, z=-1,
                   segments=32))
    root = _root(plate)
    root.add(_place(_bolt(size, length), z=plate_t - length))
    root.add(_place(_nut(size), z=-s["nut_h"]))
    return root


def bolted_flange_joint() -> CadNode:
    """Two pipe flanges bolted face to face by a ring of hex bolts and
    nuts — the fasteners placed round the bolt circle by a for-loop."""
    from . import library
    size = "M8"
    s = library.BOLT_SIZES[size]
    R, t, nbolts, bcr = 48.0, 10.0, 6, 37.0
    stack = CadNode("difference", "Flange pair")
    flanges = CadNode("union", "Flanges")
    flanges.add(_cyl("Flange A", R, t, z=0.0, segments=96))
    flanges.add(_cyl("Flange B", R, t, z=t, segments=96))
    stack.add(flanges)
    stack.add(_cyl("Bore", 16.0, 2 * t + 2, z=-1.0, segments=64))
    stack.add(_ring("Bolt holes", nbolts,
                    _cyl("Hole", s["d"] / 2.0 + 0.6, 2 * t + 2, z=-1.0,
                         x=bcr, segments=20)))
    root = _root(stack)
    length = 2 * t + s["nut_h"] + 8.0
    root.add(_ring("Bolts", nbolts,
                   _place(_bolt(size, length), x=bcr, z=2 * t - length)))
    root.add(_ring("Nuts", nbolts,
                   _place(_nut(size), x=bcr, z=-s["nut_h"])))
    return root


def pillow_block() -> CadNode:
    """A pillow-block bearing housing: a boss bored for the bearing on a
    footed base, held down by two socket cap screws."""
    from . import library
    bw, bd, bh = 96.0, 44.0, 12.0
    boss_r, bore, block_h = 24.0, 26.0, 46.0
    hole_x = bw / 2.0 - 13.0
    block = CadNode("difference", "Pillow block")
    body = CadNode("union", "Body")
    body.add(_cube("Base", bw, bd, bh, x=-bw / 2, y=-bd / 2))
    body.add(_cyl("Boss", boss_r, block_h, segments=72))
    block.add(body)
    block.add(_cyl("Bearing bore", bore / 2.0, block_h + 2, z=-1,
                   segments=64))
    for sx in (-1, 1):
        block.add(_cyl("Mount hole", 4.5, bh + 2, z=-1, x=sx * hole_x,
                       segments=24))
    root = _root(block)
    s = library.BOLT_SIZES["M8"]
    length = bh + 10.0
    for sx in (-1, 1):
        root.add(_place(_screw("M8", length), x=sx * hole_x,
                        z=bh - length))
    return root


def spur_gear() -> CadNode:
    """A single spur gear (module 3, 24 teeth) with a keyed-style bore —
    a for-loop stamps the teeth round a root disc."""
    return _root(_spur_gear("Spur gear 24T", 24, 3.0, 12.0, 10.0))


def gear_pair() -> CadNode:
    """Two meshing spur gears on their centre distance, the pinion
    phased by half a tooth so the teeth interleave."""
    module_, th = 3.0, 12.0
    big, small = 24, 12
    g1 = _spur_gear("Gear 24T", big, module_, th, 10.0)
    g2 = _spur_gear("Pinion 12T", small, module_, th, 6.0)
    centre = module_ * (big + small) / 2.0
    root = _root(g1)
    root.add(_place(_rot(g2, z=360.0 / small / 2.0), x=centre))
    return root


def ball_bearing() -> CadNode:
    """A deep-groove ball bearing (6204-ish): an inner and outer race
    with a ring of balls between them. The races are revolved rings, so
    they are genuinely hollow without a boolean and preview correctly."""
    bore, od, w, balls = 20.0, 52.0, 15.0, 9
    r_in, r_out = bore / 2.0, od / 2.0
    r_race = (r_in + r_out) / 2.0
    ball_r = (r_out - r_in) * 0.28
    ro_i = r_race - ball_r * 0.55             # inner race outer radius
    ri_o = r_race + ball_r * 0.55             # outer race inner radius

    def annulus(name, r0, r1):
        rev = CadNode("rotate_extrude", name, dict(angle=360,
                                                   segments=96))
        rev.add(CadNode("polygon", f"{name} profile", dict(
            x=0.0, y=0.0, points=[
                [round(r0, 3), 0.0], [round(r1, 3), 0.0],
                [round(r1, 3), round(w, 3)],
                [round(r0, 3), round(w, 3)]])))
        return rev

    root = _root(annulus("Outer race", ri_o, r_out),
                 annulus("Inner race", r_in, ro_i))
    root.add(_ring("Balls", balls,
                   CadNode("sphere", "Ball",
                           dict(x=r_race, y=0.0, z=w / 2.0,
                                radius=ball_r, segments=24))))
    return root


def vbelt_pulley() -> CadNode:
    """A V-belt pulley: a revolved grooved profile (hollow, so the bore
    needs no boolean) with a radial grub screw in the hub."""
    R, bore, w = 40.0, 12.0, 20.0
    prof = [[bore / 2, 0], [R, 0], [R, w * 0.32], [R - 7, w * 0.5],
            [R, w * 0.68], [R, w], [bore / 2, w]]
    rev = CadNode("rotate_extrude", "Pulley", dict(angle=360,
                                                   segments=96))
    rev.add(CadNode("polygon", "Pulley profile", dict(
        x=0.0, y=0.0, points=[[round(r, 3), round(z, 3)]
                              for r, z in prof])))
    root = _root(rev)
    root.add(_place(_rot(_screw("M5", 12), y=90), x=R - 3, z=w / 2.0))
    return root


def threaded_rod() -> CadNode:
    """A length of M12 threaded rod (studding) with a nut run onto each
    end — the twist-extruded ISO thread on its own."""
    from . import library
    size = "M12"
    s = library.BOLT_SIZES[size]
    length = 90.0
    root = _root(library.thread_solid(s["d"], s["pitch"], length,
                                      name="Threaded rod"))
    root.add(_place(_nut(size), z=8.0))
    root.add(_place(_nut(size), z=length - 8.0 - s["nut_h"]))
    return root


def fan_impeller() -> CadNode:
    """A radial fan impeller: a bored hub with six pitched blades stamped
    round it by a for-loop."""
    hub_r, hub_h, blades, R = 14.0, 20.0, 6, 50.0
    body = CadNode("union", "Impeller")
    body.add(_cyl("Hub", hub_r, hub_h, segments=48))
    blade = _rot(_cube("Blade", R - hub_r, 3, hub_h * 0.8,
                       x=hub_r - 2, y=-1.5, z=hub_h * 0.1),
                 x=28.0)
    body.add(_ring("Blades", blades, blade))
    impeller = CadNode("difference", "Fan impeller")
    impeller.add(body)
    impeller.add(_cyl("Bore", 6.0, hub_h + 2, z=-1, segments=32))
    return _root(impeller)


def bolt_circle() -> CadNode:
    """A Masters demo: one M6 bolt lives in the Masters store, and a
    for-loop drops six Linked copies of it around a flange disc. Edit
    the master and every bolt in the ring updates."""
    from .library import default_part
    bolt = default_part("bolt_hex")
    bolt.name = "Bolt"
    masters = CadNode("masters", "Masters")
    masters.add(bolt)
    disc = _cyl("Flange disc", 42, 6, segments=96)
    ref = CadNode("reference", "Copy of Bolt",
                  dict(ref="Bolt", x="30 * cos(i * 60)",
                       y="30 * sin(i * 60)", z=6, rx=0.0, ry=0.0,
                       rz=0.0))
    ring = CadNode("for_loop", "Bolt ring",
                   dict(variable="i", start=0, end=5, step=1, values=""))
    ring.add(ref)
    return _root(masters, disc, ring)


def _color(name, hex_color, child) -> CadNode:
    c = CadNode("color", name, dict(color=hex_color, alpha=1.0))
    c.add(child)
    return c


def _extrude(name, height, child) -> CadNode:
    ext = CadNode("linear_extrude", name, dict(
        height=height, twist=0.0, scale=1.0, center=False, segments=0))
    ext.add(child)
    return ext


def orientation_cubes() -> CadNode:
    """Inspired by BOSL2's orientations example: a cube marked with its
    local X/Y/Z axes — coloured edge stripes and axis rods — so you can
    read orientation at a glance."""
    s = 30.0
    cube = _color("Body", "#b8bcc2",
                  _cube("Cube", s, s, s, x=-s / 2, y=-s / 2, z=-s / 2))
    root = _root(cube)
    bar = s * 0.9
    e = s / 2.0
    # coloured edge stripes at the top, like the original
    root.add(_color("X edge", "#d64545",
                    _cube("X", bar, 2, 2, x=-bar / 2, y=e - 2, z=e - 2)))
    root.add(_color("Y edge", "#3f9e4d",
                    _cube("Y", 2, bar, 2, x=e - 2, y=-bar / 2, z=e - 2)))
    root.add(_color("Z edge", "#3a6fd8",
                    _cube("Z", 2, 2, bar, x=e - 2, y=e - 2, z=-bar / 2)))
    # axis rods out of the origin corner
    rod = s * 0.8
    root.add(_color("X axis", "#d64545",
                    _rot(_cyl("Xr", 1.4, rod, segments=16), y=90)))
    root.add(_color("Y axis", "#3f9e4d",
                    _rot(_cyl("Yr", 1.4, rod, segments=16), x=-90)))
    root.add(_color("Z axis", "#3a6fd8",
                    _cyl("Zr", 1.4, rod, segments=16)))
    return root


def boolean_regions() -> CadNode:
    """Inspired by BOSL2's boolean_geometry example: a square and a
    circle combined four ways — union, difference, intersection and
    exclusive-or — each extruded to a thin plate and laid out in a row."""
    def shapes():
        rect = CadNode("rect", "A (square)",
                       dict(x=-24, y=-24, width=48, height=48))
        circ = CadNode("circle", "B (circle)",
                       dict(x=18, y=18, radius=26, segments=64,
                            angle=360.0, start_angle=0.0))
        return rect, circ

    def op(kind, name):
        a, b = shapes()
        node = CadNode(kind, name)
        node.add(a)
        node.add(b)
        return node

    def xor():
        a1, b1 = shapes()
        a2, b2 = shapes()
        d1 = CadNode("difference", "A-B")
        d1.add(a1)
        d1.add(b1)
        d2 = CadNode("difference", "B-A")
        d2.add(b2)
        d2.add(a2)
        u = CadNode("union", "XOR")
        u.add(d1)
        u.add(d2)
        return u

    root = _root()
    plates = [
        ("Union", "#e06666", op("union", "Union A+B")),
        ("Difference", "#6fa8dc", op("difference", "Difference A-B")),
        ("Intersection", "#93c47d", op("intersection", "Intersection")),
        ("XOR", "#c27ba0", xor()),
    ]
    for i, (label, hexc, region) in enumerate(plates):
        root.add(_place(_color(label, hexc, _extrude(label, 4.0, region)),
                        x=i * 90.0))
    return root


def _tree_branch(length, sc, depth) -> CadNode:
    """One branch of the fractal tree, recursively built (the builder is
    plain Python, so it can recurse where the node tree — which has no
    recursion — cannot)."""
    node = CadNode("union", f"Branch d{depth}")
    node.add(_color("Wood", "#9c8b74",
                    _cyl("Trunk", length * 0.09, length,
                         r2=max(length * 0.09 * sc, 0.4), segments=14)))
    top = CadNode("translate", "Top", dict(x=0.0, y=0.0, z=length))
    if depth > 0:
        for rz in (0.0, 180.0):                # two opposed children
            spread = _rot(_tree_branch(length * sc, sc, depth - 1),
                          y=32.0)
            top.add(_rot(spread, z=90.0 + rz))
    else:
        top.add(_color("Leaf", "#59b359",
                       CadNode("sphere", "Leaf",
                               dict(x=0.0, y=0.0, z=length * 0.2,
                                    radius=length * 0.6, segments=12))))
    node.add(top)
    return node


def fractal_tree() -> CadNode:
    """Inspired by BOSL2's fractal_tree: a recursively branching tree
    (five levels), grey wood with green leaves — built by recursing in
    the Python builder and unrolling into the object tree."""
    return _root(_tree_branch(120.0, 0.72, 5))


def bosl2_attachments_raw() -> CadNode:
    """A BOSL2 example (attachments) dropped in verbatim as an OpenSCAD
    code node. It renders through the **OpenSCAD engine only** (the
    built-in preview stays blank) and needs BOSL2 installed as a
    ``BOSL2`` library folder."""
    code = (
        "// BOSL2 example — renders via the OpenSCAD engine.\n"
        "// Needs BOSL2 on the OpenSCAD library path (a 'BOSL2' folder).\n"
        "include <BOSL2/std.scad>\n"
        "$fn = 32;\n"
        "cuboid([60,40,40], rounding=5, edges=\"Z\", anchor=BOTTOM) {\n"
        "    attach(TOP, BOTTOM)\n"
        "    prismoid([60,40],[20,20], h=50, rounding1=5, rounding2=10) {\n"
        "        attach(TOP) cylinder(d=20, h=30, center=false) {\n"
        "            attach(TOP) cylinder(d1=50, d2=30, h=12,"
        " center=false);\n"
        "        }\n"
        "    }\n"
        "}\n")
    return _root(CadNode("scad_raw", "BOSL2 attachments", dict(code=code)))


def vacuum_starter() -> CadNode:
    """An assembly starter from the part library: a CF tee with a turbo
    pump hung below it — drag the parts in the 2D assembly view or edit
    them in the tree."""
    from .library import default_part
    tee = default_part("cf_tee")
    turbo = default_part("turbo")
    mount = CadNode("translate", "Turbo position", dict(x=0, y=0, z=-170))
    mount.add(turbo)
    return _root(tee, mount)


def desk_setup() -> CadNode:
    """A furniture scene: a table with a monitor and a chair, each a
    coloured library part — a quick way to block out a room."""
    from .library import default_part
    table = default_part("room_table")
    monitor = default_part("room_monitor")
    mon_pos = CadNode("translate", "Monitor position",
                      dict(x=0, y=0, z=740))
    mon_pos.add(monitor)
    chair = default_part("room_chair")
    chair_pos = CadNode("translate", "Chair position",
                        dict(x=0, y=-520, z=0))
    chair_pos.add(chair)
    return _root(table, mon_pos, chair_pos)


#: (menu label, category, builder) — grouped in the Examples menu.
EXAMPLES = [
    ("Parametric box", "Mechanical", parametric_box),
    ("L-bracket with holes", "Mechanical", l_bracket),
    ("Bolt & nut through a plate", "Mechanical", bolt_and_nut),
    ("Bolted flange joint", "Mechanical", bolted_flange_joint),
    ("Pillow-block bearing", "Mechanical", pillow_block),
    ("Spur gear", "Mechanical", spur_gear),
    ("Meshing gear pair", "Mechanical", gear_pair),
    ("Ball bearing", "Mechanical", ball_bearing),
    ("V-belt pulley", "Mechanical", vbelt_pulley),
    ("Threaded rod & nuts", "Mechanical", threaded_rod),
    ("Fan impeller", "Mechanical", fan_impeller),
    ("Bolt circle (Masters demo)", "Mechanical", bolt_circle),
    ("Orientation cubes", "Showcase", orientation_cubes),
    ("Boolean regions (2D ops)", "Showcase", boolean_regions),
    ("Fractal tree", "Showcase", fractal_tree),
    ("BOSL2 attachments (raw OpenSCAD)", "Showcase", bosl2_attachments_raw),
    ("Vacuum starter (CF tee + turbo)", "Vacuum", vacuum_starter),
    ("Desk setup", "Room", desk_setup),
]


def load_example(model: DocumentModel, build) -> None:
    """Replace the document with the example built by *build*."""
    model.root = build()
    model.structure_changed.emit()
