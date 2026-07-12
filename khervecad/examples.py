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


# ============================ LEARN =================================
# A progressive tour, one technique per example, basic -> advanced.

def _sphere(name, r, x=0.0, y=0.0, z=0.0, seg=48) -> CadNode:
    return CadNode("sphere", name,
                   dict(x=x, y=y, z=z, radius=r, segments=seg))


def _ext(name, height, child, twist=0.0, scale=1.0) -> CadNode:
    ext = CadNode("linear_extrude", name, dict(
        height=height, twist=twist, scale=scale, center=False,
        segments=0))
    ext.add(child)
    return ext


def _for(name, var, start, end, step, child) -> CadNode:
    loop = CadNode("for_loop", name, dict(
        variable=var, start=start, end=end, step=step, values=""))
    loop.add(child)
    return loop


def learn_01_cube() -> CadNode:
    """1 · The cube. The simplest solid — a box of width/depth/height.
    Every model starts with primitives like this."""
    return _root(_cube("My first cube", 30, 30, 30))


def learn_02_primitives() -> CadNode:
    """2 · The three 3D primitives: cube, sphere and cylinder, set side
    by side. Pick one from the vertical toolbar and edit its size in the
    Properties panel."""
    return _root(
        _cube("Cube", 26, 26, 26, x=-55),
        _sphere("Sphere", 15, x=0, y=13, z=13),
        _cyl("Cylinder", 13, 30, x=45, y=13))


def learn_03_2d_shapes() -> CadNode:
    """3 · 2D sketch shapes — a square, a circle and a polygon — each
    extruded 2 mm so they show in 3D. 2D shapes live in the sketch view
    and become solids when you extrude them."""
    square = CadNode("rect", "Square",
                     dict(x=-15, y=-15, width=30, height=30))
    circle = CadNode("circle", "Circle",
                     dict(x=0, y=0, radius=18, segments=64,
                          angle=360.0, start_angle=0.0))
    tri = CadNode("polygon", "Triangle",
                  dict(x=0, y=0, points=[[-18, -15], [18, -15], [0, 20]]))
    return _root(
        _place(_ext("Square plate", 2, square), x=-50),
        _place(_ext("Disc", 2, circle), x=0),
        _place(_ext("Triangle plate", 2, tri), x=50))


def learn_04_text() -> CadNode:
    """4 · Text — a `text` sketch object extruded into 3D letters. Change
    the string and size in Properties."""
    txt = CadNode("text", "Label", dict(x=-24, y=-8, text="CAD", size=24))
    return _root(_color("Letters", "#3f7fd8", _ext("3D text", 6, txt)))


def learn_05_translate() -> CadNode:
    """5 · Translate — move an object in X/Y/Z. Here the same cube is
    placed three times at growing X (a translate node wraps each)."""
    root = _root()
    for i in range(3):
        root.add(_place(_cube("Box", 20, 20, 20), x=i * 30.0))
    return root


def learn_06_rotate() -> CadNode:
    """6 · Rotate — spin an object about an axis. Four bars fanned out by
    rotating each a bit more about Z."""
    root = _root()
    for a in (0.0, 22.5, 45.0, 67.5, 90.0):
        root.add(_color("Bar", "#d98a3f",
                        _rot(_cube("Bar", 60, 6, 6, y=-3), z=a)))
    return root


def learn_07_scale_mirror() -> CadNode:
    """7 · Scale and mirror. The middle wedge is the original; left is it
    scaled up, right is it mirrored across X."""
    def wedge(name):
        return CadNode("polygon", name,
                       dict(x=0, y=0, points=[[0, 0], [24, 0], [0, 30]]))
    orig = _ext("Original", 12, wedge("W"))
    scaled = CadNode("scale", "Scaled 1.6x", dict(x=1.6, y=1.6, z=1.0))
    scaled.add(_ext("W", 12, wedge("W")))
    mirrored = CadNode("mirror", "Mirror X", dict(x=1, y=0, z=0))
    mirrored.add(_ext("W", 12, wedge("W")))
    return _root(orig, _place(scaled, x=-70),
                 _place(mirrored, x=50))


def learn_08_linear_extrude() -> CadNode:
    """8 · Linear extrude — push a 2D profile straight up into a solid,
    optionally twisting it. This plus-shaped profile is extruded 50 mm
    with a 90° twist."""
    plus = CadNode("polygon", "Plus", dict(x=0, y=0, points=[
        [-6, -18], [6, -18], [6, -6], [18, -6], [18, 6], [6, 6],
        [6, 18], [-6, 18], [-6, 6], [-18, 6], [-18, -6], [-6, -6]]))
    return _root(_ext("Twisted column", 50, plus, twist=90.0))


def learn_09_rotate_extrude() -> CadNode:
    """9 · Rotate extrude — revolve a 2D profile around the Z axis to
    make lathe-turned shapes. This profile sweeps out a vase."""
    prof = [[6, 0], [26, 0], [22, 12], [14, 30], [12, 55], [20, 72],
            [18, 78], [6, 78]]
    rev = CadNode("rotate_extrude", "Vase", dict(angle=360, segments=96))
    rev.add(CadNode("polygon", "Vase profile",
                    dict(x=0, y=0, points=[[round(r, 2), round(z, 2)]
                                           for r, z in prof])))
    return _root(_color("Vase", "#57a0a0", rev))


def learn_10_union() -> CadNode:
    """10 · Union — glue overlapping solids into one. Two spheres and a
    bar become a single part."""
    u = CadNode("union", "Union")
    u.add(_sphere("Ball A", 18, x=-16))
    u.add(_sphere("Ball B", 18, x=16))
    u.add(_cyl("Bar", 8, 40, x=-20, y=0, z=-4))
    return _root(_rot(u, x=90))


def learn_11_difference() -> CadNode:
    """11 · Difference — subtract later shapes from the first. A block
    with a bore and two cross-holes drilled through it. (The built-in
    preview shows the block; OpenSCAD shows the holes.)"""
    d = CadNode("difference", "Drilled block")
    d.add(_cube("Block", 50, 40, 30, x=-25, y=-20))
    d.add(_cyl("Bore", 10, 34, z=-2, segments=48))
    d.add(_rot(_cyl("Cross hole", 5, 60, z=-30, segments=32), y=90))
    return _root(d)


def learn_12_intersection() -> CadNode:
    """12 · Intersection — keep only the overlap. A cube intersected with
    a sphere gives a cube with bulged, rounded faces."""
    it = CadNode("intersection", "Intersection")
    it.add(_cube("Cube", 34, 34, 34, x=-17, y=-17, z=-17))
    it.add(_sphere("Sphere", 22))
    return _root(it)


def learn_13_hull() -> CadNode:
    """13 · Hull — wrap a tight convex skin around several shapes. Two
    cylinders hulled become a rounded slot / capsule."""
    h = CadNode("hull", "Hull")
    h.add(_cyl("End A", 10, 8, x=-25))
    h.add(_cyl("End B", 10, 8, x=25))
    return _root(h)


def learn_14_rounded() -> CadNode:
    """14 · Round edges (minkowski) — sweep a small sphere over a box to
    round every edge and corner. The post-extrusion rounding idiom."""
    mk = CadNode("minkowski", "Rounded box")
    mk.add(_cube("Box", 34, 24, 14, x=-17, y=-12, z=0))
    mk.add(_sphere("Rounding", 4, seg=24))
    return _root(mk)


def learn_15_for_row() -> CadNode:
    """15 · For loop — repeat with a counter. `i` runs 0..5 and each
    pillar is placed at x = i * 20 (an expression using the loop
    variable)."""
    pillar = _cyl("Pillar", 6, "10 + i * 6", x="i * 20")
    return _root(_for("Colonnade", "i", 0, 5, 1, pillar))


def learn_16_polar() -> CadNode:
    """16 · Polar array — a for loop plus rotate makes a circular
    pattern. `i` runs 0..11 and each spoke is rotated i * 30° about Z."""
    spoke = _rot(_cube("Spoke", 34, 5, 5, x=12, y=-2.5, z=-2.5),
                 z="i * 30")
    hub = _cyl("Hub", 12, 5, segments=48)
    return _root(hub, _for("Spokes", "i", 0, 11, 1, spoke))


def learn_17_grid() -> CadNode:
    """17 · Nested for loops — one loop inside another sweeps a grid.
    `i` and `j` each run 0..4 to place a 5×5 field of pins."""
    pin = _cyl("Pin", 3, 14, x="i * 12", y="j * 12", segments=20)
    inner = _for("Columns", "j", 0, 4, 1, pin)
    base = _cube("Base", 60, 60, 4, x=-6, y=-6, z=-4)
    return _root(base, _for("Rows", "i", 0, 4, 1, inner))


def learn_18_variables() -> CadNode:
    """18 · Variables — name your dimensions once and reuse them. Edit
    `w`, `d`, `h` or `wall` in the Variables tab and the tray follows;
    expressions like `w - 2 * wall` do the maths for you."""
    outer = _cube("Outer", "w", "d", "h")
    inner = _cube("Cavity", "w - 2 * wall", "d - 2 * wall", "h",
                  x="wall", y="wall", z="wall")
    tray = CadNode("difference", "Parametric tray")
    tray.add(outer)
    tray.add(inner)
    return _root(_var("w", 70), _var("d", 45), _var("h", 22),
                 _var("wall", 3), tray)


def learn_19_if_else() -> CadNode:
    """19 · If / else — choose geometry from a condition. `mode` picks a
    cube (mode > 0) or a sphere; flip the variable to 0 to switch. The
    else branch lives in a child group named "Else"."""
    cond = CadNode("if_else", "Pick a shape", dict(condition="mode > 0"))
    cond.add(_color("Then (cube)", "#d98a3f",
                    _cube("Cube", 30, 30, 30, x=-15, y=-15)))
    els = CadNode("union", "Else")
    els.add(_color("Else (sphere)", "#57a0a0", _sphere("Sphere", 20)))
    cond.add(els)
    return _root(_var("mode", 1), cond)


def learn_20_while() -> CadNode:
    """20 · While loop — repeat until a condition fails. `a` climbs from
    0 by 30 while a < 700; each step rotates and lifts a small cube, so
    the loop draws a rising spiral. (Codegen unrolls it into a for.)"""
    step = CadNode("while_loop", "Spiral",
                   dict(variable="a", start=0.0, condition="a < 700",
                        update="a + 30"))
    block = _rot(_place(_cube("Step", 12, 6, 4, y=-3), x=34, z="a * 0.06"),
                 z="a")
    step.add(block)
    return _root(_cyl("Post", 4, 44, segments=24), step)


def learn_21_masters() -> CadNode:
    """21 · Masters — define a part once, place it many times. The
    "Widget" lives in the Masters tab; three Linked copies sit in the
    scene. Edit the master and every copy updates. (See the Masters tab
    and the Objects tree.)"""
    widget = CadNode("union", "Widget")
    widget.add(_cyl("Base", 12, 6, segments=32))
    widget.add(_sphere("Knob", 7, z=12))
    widget.add(_cyl("Stem", 3, 12, z=6, segments=16))
    masters = CadNode("masters", "Masters")
    masters.add(widget)
    root = _root(masters)
    for i, x in enumerate((-45.0, 0.0, 45.0)):
        root.add(CadNode("reference", f"Copy {i + 1}",
                         dict(ref="Widget", x=x, y=0.0, z=0.0,
                              rx=0.0, ry=0.0, rz=i * 30.0)))
    return root


# ============================ PROJECTS =============================
# One finished part per chapter of the "Mastering OpenSCAD in 10
# projects" course, rebuilt natively so each previews and teaches the
# chapter's key technique.

def project_02_wall_anchor() -> CadNode:
    """Ch.2 · Wall anchor — a tapered plug for a drilled hole. Teaches
    linear_extrude with a scale taper, a difference for the screw cavity,
    and a for loop that cuts the two expansion slits."""
    length, outer = 40.0, 10.0
    section = CadNode("rect", "Section",
                      dict(x=-outer / 2, y=-outer / 2,
                           width=outer, height=outer))
    body = _ext("Tapered post", length, section, scale=0.72)
    cavity = _cyl("Screw cavity", 2.6, length + 2, z=-1, r2=1.0,
                  segments=24)
    slit = _rot(_cube("Slit", outer + 2, 1.4, length * 0.72,
                      x=-(outer + 2) / 2, y=-0.7, z=length * 0.2),
                z="i * 90")
    anchor = CadNode("difference", "Wall anchor")
    anchor.add(body)
    anchor.add(cavity)
    anchor.add(_for("Slits", "i", 0, 1, 1, slit))
    return _root(_color("Anchor", "#c9b28a", anchor))


def project_03_window_stopper() -> CadNode:
    """Ch.3 · Window stopper — a wedge case with a lever on an axle.
    Teaches a nested difference (the axle bore), a hull-shaped lever and a
    rotate that sets the lever angle."""
    case = CadNode("difference", "Case")
    case.add(_cube("Body", 30, 40, 40, x=-15, y=-20))
    case.add(_cube("Frame slot", 34, 18, 34, x=-17, y=-9, z=8))
    case.add(_rot(_cyl("Axle bore", 5.5, 44, z=-22, segments=36), x=90))
    case = _color("Case", "#b8b0a0", case)

    axle = _color("Axle", "#7c7c7c",
                  _place(_rot(_cyl("Axle", 5, 44, segments=36), x=90),
                         z=28, y=22))

    lever_2d = CadNode("hull", "Lever arm")
    lever_2d.add(CadNode("circle", "Pivot",
                         dict(x=0, y=0, radius=6, segments=36,
                              angle=360.0, start_angle=0.0)))
    lever_2d.add(CadNode("circle", "Grip",
                         dict(x=40, y=0, radius=4, segments=36,
                              angle=360.0, start_angle=0.0)))
    lever = _rot(_ext("Lever", 8, lever_2d), x=90)     # lay it flat in Y
    lever = _rot(lever, y=-28)                         # swing it up
    lever = _color("Lever", "#d98a3f", _place(lever, z=28, y=4))
    return _root(case, axle, lever)


def project_04_clock_movement() -> CadNode:
    """Ch.4 · Clock movement mock-up — a quartz movement with the hands
    set to a time. Teaches naming dimensions and colouring each part; the
    three hands are bars rotated by the hour/minute/second angles."""
    body = _color("Body", "#6e6e6e", _cube("Case", 56, 56, 20,
                                           x=-28, y=-28, z=-20))
    terminal = _color("Terminal", "#d4af37",
                      _cyl("Screw terminal", 3.9, 5, segments=36))
    axles = CadNode("union", "Axles")
    axles.add(_cyl("Hour axle", 2.55, 8.3, segments=36))
    axles.add(_cyl("Minute axle", 1.6, 12.1, segments=36))
    axles.add(_cyl("Second axle", 0.5, 14.5, segments=24))
    axles = _color("Axles", "#202020", axles)

    def hand(name, col, length, width, z, angle):
        bar = _cube(name, width, length, 0.8, x=-width / 2, y=0, z=0)
        return _color(name, col, _rot(_place(bar, z=z), z=angle))

    hour = hand("Hour hand", "#111111", 18, 4.0, 8.3,
                -360 * (10 + 9 / 60) / 12)
    minute = hand("Minute hand", "#111111", 25, 2.5, 12.1,
                  -360 * 9 / 60)
    second = hand("Second hand", "#c0332b", 27, 1.2, 14.5,
                  -360 * 30 / 60)
    return _root(body, terminal, axles, hour, minute, second)


def project_05_pen_holder() -> CadNode:
    """Ch.5 · Pen holder — a ring of arches around a cup. Teaches partial
    rotate_extrude (each arch is a half-torus stood upright) placed by a
    polar for loop, the way the gothic pen holder is built."""
    cup = CadNode("rotate_extrude", "Cup", dict(angle=360, segments=72))
    cup.add(CadNode("polygon", "Cup wall", dict(
        x=0, y=0, points=[[16, 0], [19, 0], [19, 80], [16, 80]])))
    cup = _color("Cup", "#b0894f", cup)

    def arch():
        prof = CadNode("circle", "Bar", dict(x=15, y=0, radius=2.2,
                                             segments=20, angle=360.0,
                                             start_angle=0.0))
        rev = CadNode("rotate_extrude", "Arch",
                      dict(angle=180, segments=64))
        rev.add(prof)
        return _rot(rev, x=-90)                # stand the half-torus up

    piece = _rot(_color("Arch", "#b0894f", _place(arch(), y=24)),
                 z="i * 60")
    return _root(cup, _for("Arch ring", "i", 0, 5, 1, piece))


def project_06_stamp() -> CadNode:
    """Ch.6 · Rubber stamp — mirrored text on a handled base. Teaches the
    text object, mirror (so the imprint reads the right way round), linear
    extrude and a coloured handle."""
    plate = _color("Base", "#8a5a3a",
                   _ext("Plate", 3, CadNode("rect", "Plate area",
                        dict(x=-24, y=-11, width=48, height=22))))
    txt = CadNode("text", "Text", dict(x=-15, y=-6, text="OPEN", size=12))
    relief = CadNode("mirror", "Mirror (reads right when stamped)",
                     dict(x=1, y=0, z=0))
    relief.add(_place(_ext("Letters", 2, txt), z=3))
    relief = _color("Letters", "#c8783c", relief)
    stem = _color("Handle", "#5a3a24",
                  _cyl("Stem", 6, 22, z=3, segments=36))
    knob = _color("Knob", "#5a3a24", _sphere("Knob", 11, z=32))
    return _root(plate, relief, stem, knob)


def _star_points(points, r_out, r_in):
    pts = []
    for k in range(points * 2):
        angle = math.pi * k / points
        radius = r_out if k % 2 == 0 else r_in
        pts.append([round(radius * math.cos(angle), 2),
                    round(radius * math.sin(angle), 2)])
    return pts


def project_07_flame_sculpture() -> CadNode:
    """Ch.7 · Flame sculpture — twisting, tapering spires. Teaches linear
    extrude with both twist and scale at once: a star profile spins as it
    shrinks to a point."""
    def flame(height, twist, col, x, y):
        star = CadNode("polygon", "Star",
                       dict(x=0, y=0, points=_star_points(6, 16, 7)))
        return _color("Flame", col,
                      _place(_ext("Flame", height, star,
                                  twist=twist, scale=0.05), x=x, y=y))
    return _root(
        flame(150, 300, "#e2622c", 0, 0),
        flame(112, 240, "#f0902a", 28, 8),
        flame(120, -260, "#d9451f", -28, 8))


def _tree3d(length, radius, depth) -> CadNode:
    node = CadNode("union", f"Branch d{depth}")
    node.add(_cyl("Segment", radius, length, r2=radius * 0.72,
                  segments=16))
    if depth <= 0:
        node.add(_color("Leaf", "#3f8f3f",
                        _sphere("Leaf", radius * 2.4, z=length, seg=16)))
        return node
    top = CadNode("union", "Fork")
    for az in (0.0, 120.0, 240.0):
        child = _tree3d(length * 0.72, radius * 0.7, depth - 1)
        top.add(_rot(_rot(child, x=32), z=az))
    node.add(_place(top, z=length))
    return node


def project_08_recursive_tree() -> CadNode:
    """Ch.8 · Recursive tree — a trunk that keeps splitting into smaller
    branches. Teaches recursion: the Python builder unrolls it into the
    object tree, so you can open branch inside branch inside branch."""
    return _root(_color("Trunk", "#7a5230", _tree3d(40, 5, 3)))


def project_09_parabolic_reflector() -> CadNode:
    """Ch.9 · Parabolic reflector — a dish whose depth follows z =
    r²/(4f). Teaches building a rotate_extrude profile from a computed
    curve, closed off with a wall thickness."""
    focus, rim, wall, n = 40.0, 75.0, 3.0, 24
    inner = [[round(rim * i / n, 2),
              round((rim * i / n) ** 2 / (4 * focus), 2)]
             for i in range(n + 1)]
    outer = [[round(rim * i / n, 2),
              round((rim * i / n) ** 2 / (4 * focus) - wall, 2)]
             for i in range(n, -1, -1)]
    prof = CadNode("polygon", "Dish profile",
                   dict(x=0, y=0, points=inner + outer))
    dish = CadNode("rotate_extrude", "Reflector",
                   dict(angle=360, segments=96))
    dish.add(prof)
    return _root(_color("Reflector", "#9fb6c6", dish))


def project_10_fan_wheel() -> CadNode:
    """Ch.10 · Fan wheel — a hub with pitched blades in a polar array.
    Teaches combining a for-loop polar pattern with a twisted linear
    extrude, so each blade carries the same aerofoil pitch."""
    hub = _color("Hub", "#8a8a8a", _cyl("Hub", 14, 16, z=-8, segments=48))
    section = CadNode("rect", "Blade section",
                      dict(x=-3, y=-18, width=6, height=36))
    blade = _rot(_ext("Blade", 40, section, twist=-42), y=90)
    blade = _rot(_color("Blade", "#c7c7c7", _place(blade, x=14)),
                 z="i * 45")
    return _root(hub, _for("Blades", "i", 0, 7, 1, blade))


#: (menu label, category, builder) — grouped in the Examples menu.
EXAMPLES = [
    ("1 · Cube", "Learn", learn_01_cube),
    ("2 · Three primitives", "Learn", learn_02_primitives),
    ("3 · 2D shapes", "Learn", learn_03_2d_shapes),
    ("4 · 3D text", "Learn", learn_04_text),
    ("5 · Translate", "Learn", learn_05_translate),
    ("6 · Rotate", "Learn", learn_06_rotate),
    ("7 · Scale & mirror", "Learn", learn_07_scale_mirror),
    ("8 · Linear extrude", "Learn", learn_08_linear_extrude),
    ("9 · Rotate extrude (vase)", "Learn", learn_09_rotate_extrude),
    ("10 · Union", "Learn", learn_10_union),
    ("11 · Difference", "Learn", learn_11_difference),
    ("12 · Intersection", "Learn", learn_12_intersection),
    ("13 · Hull", "Learn", learn_13_hull),
    ("14 · Round edges", "Learn", learn_14_rounded),
    ("15 · For loop (row)", "Learn", learn_15_for_row),
    ("16 · Polar array", "Learn", learn_16_polar),
    ("17 · Nested for (grid)", "Learn", learn_17_grid),
    ("18 · Variables", "Learn", learn_18_variables),
    ("19 · If / else", "Learn", learn_19_if_else),
    ("20 · While loop (spiral)", "Learn", learn_20_while),
    ("21 · Masters", "Learn", learn_21_masters),
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
    ("Ch.2 · Wall anchor", "Projects", project_02_wall_anchor),
    ("Ch.3 · Window stopper", "Projects", project_03_window_stopper),
    ("Ch.4 · Clock movement", "Projects", project_04_clock_movement),
    ("Ch.5 · Pen holder", "Projects", project_05_pen_holder),
    ("Ch.6 · Rubber stamp", "Projects", project_06_stamp),
    ("Ch.7 · Flame sculpture", "Projects", project_07_flame_sculpture),
    ("Ch.8 · Recursive tree", "Projects", project_08_recursive_tree),
    ("Ch.9 · Parabolic reflector", "Projects",
     project_09_parabolic_reflector),
    ("Ch.10 · Fan wheel", "Projects", project_10_fan_wheel),
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
