"""Parts for 3D printing — what printable-design libraries give (BOSL2's
joiners and hinges, Catch'n'Hole, Gridfinity, the tray and enclosure
generators): joints, hinges, snap-fits, clips, a bottle cap, Gridfinity
bins and baseplates, a divided tray and an electronics enclosure.

Every part is an ordinary node subtree built from the feature nodes
(thread, hole, honeycomb, rounded_polygon…) and booleans, so it arrives
editable in the Object tab and exports as plain OpenSCAD with the
kcad_* helpers. Sizes are the common printable ones; clearances default
to 0.2–0.3 mm, what FDM printers need.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from .model import CadNode

JOINTS = "Printed joints & hinges"
ORGANISE = "Printed organisers"
ENCLOSURES = "Enclosures"

PLA = "#e8e3d8"
COLORS = {"Natural": PLA, "Black": "#2a2c30", "Orange": "#f07b2c",
          "Blue": "#2f6fb3", "Green": "#3f9e5a", "Red": "#c9423a"}


def _d(dims, sizes):
    entry = dict(sizes.get(dims.get("_size", ""), next(iter(sizes.values()))))
    entry.update({k: v for k, v in dims.items()
                  if not k.startswith("_") and v is not None})
    return entry


def _colour(node, dims, default="Natural"):
    col = CadNode("color", node.name, dict(
        color=COLORS.get(dims.get("_color") or default, PLA), alpha=1.0,
        material="Plastic"))
    col.add(node)
    return col


def _cube(name, x, y, z, w, d, h, center=False):
    return CadNode("cube", name, dict(x=x, y=y, z=z, width=w, depth=d,
                                      height=h, center=center))


def _rbox(name, x, y, z, w, d, h, r):
    if r <= 0.01:
        return _cube(name, x, y, z, w, d, h)
    return CadNode("rounded_box", name, dict(
        x=x, y=y, z=z, width=w, depth=d, height=h, radius=min(r, w / 2,
                                                            d / 2, h / 2),
        center=False, segments=24))


def _vbox(name, x, y, z, w, d, h, r):
    """A box with only its VERTICAL edges rounded (a flat top rim, as a
    bin or a tray needs): a rounded polygon extruded."""
    r = max(min(r, w / 2 - 0.01, d / 2 - 0.01), 0.0)
    shape = CadNode("rounded_polygon", f"{name} outline", dict(
        x=x, y=y, segments=8,
        corners=[[0.0, 0.0, r], [w, 0.0, r], [w, d, r], [0.0, d, r]]))
    return _move(_extrude(name, shape, h), z=z)


def _cyl(name, x, y, z, h, r, r2=None, seg=48):
    return CadNode("cylinder", name, dict(
        x=x, y=y, z=z, height=h, radius_bottom=r,
        radius_top=r if r2 is None else r2, segments=seg, center=False))


def _group(name, *children, kind="union"):
    node = CadNode(kind, name)
    for child in children:
        if child is not None:
            node.add(child)
    return node


def _move(node, x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0):
    out = node
    if rx or ry or rz:
        rot = CadNode("rotate", f"Turn {node.name}", dict(x=rx, y=ry, z=rz))
        rot.add(out)
        out = rot
    if x or y or z:
        move = CadNode("translate", f"Move {node.name}", dict(x=x, y=y, z=z))
        move.add(out)
        out = move
    return out


def _extrude(name, shape, height):
    ext = CadNode("linear_extrude", name, dict(
        height=height, twist=0.0, scale=1.0, center=False, segments=0))
    ext.add(shape)
    return ext


def _polygon(name, points):
    return CadNode("polygon", name, dict(x=0.0, y=0.0,
                                         points=[list(p) for p in points]))


# ----------------------------------------------------------------- joints

DOVETAIL_SIZES = {"Small (15 mm)": dict(width=15.0, height=10.0,
                                        length=20.0, clearance=0.2),
                  "Medium (25 mm)": dict(width=25.0, height=15.0,
                                         length=30.0, clearance=0.25)}


def build_dovetail(dims):
    """A sliding dovetail: the male block and the female block beside
    it, the tail flaring 15° each side, the socket wider by the
    clearance all round."""
    p = _d(dims, DOVETAIL_SIZES)
    w, h, length, c = p["width"], p["height"], p["length"], p["clearance"]
    neck = w * 0.4
    flare = h * 0.5 * math.tan(math.radians(15))
    tail = [(-neck / 2, 0), (neck / 2, 0), (neck / 2 + flare, h * 0.5),
            (-neck / 2 - flare, h * 0.5)]
    male = _group(
        "Male",
        _cube("Block", -w / 2, 0, 0, w, h, length),
        _move(_extrude("Tail", _polygon("Tail profile",
                                        [(x, y + h) for x, y in tail]),
                       length)))
    socket = [(x + (c if x > 0 else -c), y - c if y == 0 else y + c)
              for x, y in tail]
    female = _group(
        "Female",
        _cube("Block", -w / 2, 0, 0, w, h, length),
        _move(_extrude("Socket", _polygon("Socket profile",
                                          [(x, y + h - h * 0.5)
                                           for x, y in socket]),
                       length + 2), z=-1),
        kind="difference")
    return _colour(_group("Dovetail joint", male,
                          _move(female, x=w * 1.6)), dims)


SNAP_SIZES = {"Standard": dict(length=15.0, thickness=1.6, width=6.0,
                               hook=1.2, base=4.0)}


def build_snap_fit(dims):
    """A cantilever snap-fit: a base block, a flexing arm and a ramped
    hook that clicks behind an edge (hook depth ≈ the arm's safe
    deflection for PLA)."""
    p = _d(dims, SNAP_SIZES)
    L, t, w, hook, base = (p["length"], p["thickness"], p["width"],
                           p["hook"], p["base"])
    arm = _cube("Arm", 0, 0, base, w, t, L)
    # the hook's profile in the arm's Y-Z plane — the catch flat at the
    # bottom, the ramp leading in from the tip — extruded across the width
    hook_profile = _polygon("Hook profile",
                            [(0, 0), (hook, 0), (0, hook * 3)])
    hook_node = _move(_extrude("Hook", hook_profile, w), y=t,
                      z=base + L - hook * 3, rx=90, rz=90)
    return _colour(_group("Snap-fit", _cube("Base", 0, 0, 0, w, 8, base),
                          arm, hook_node), dims)


HINGE_SIZES = {"30 mm": dict(width=30.0, leaf=20.0, thickness=3.0,
                             knuckles=5, clearance=0.3),
               "50 mm": dict(width=50.0, leaf=30.0, thickness=4.0,
                             knuckles=5, clearance=0.35)}


def build_print_in_place_hinge(dims):
    """A hinge printed in one piece: knuckles alternate along one pin,
    each joined to its own leaf; each leaf is cut away round the other
    leaf's knuckles by the clearance, and the moving knuckles are bored
    round the fixed pin, so it turns straight off the bed."""
    p = _d(dims, HINGE_SIZES)
    w, leaf, t = p["width"], p["leaf"], p["thickness"]
    n = max(int(p["knuckles"]), 3)
    c = p["clearance"]
    r = t                                   # knuckle radius
    pin_r = r * 0.45
    seg = w / n

    def along(name, x0, length, radius):
        return _move(_cyl(name, 0, 0, 0, length, radius), x=x0, z=r, ry=90)
    spans = []
    for k in range(n):
        x0 = k * seg + (c if k else 0)
        length = seg - (c if k else 0) - (c if k < n - 1 else 0)
        spans.append((k, x0, length))
    fixed = _group("Fixed leaf", _cube("Leaf", 0, -leaf, 0, w, leaf, t))
    moving = _group("Moving leaf", _cube("Leaf", 0, 0, 0, w, leaf, t))
    for k, x0, length in spans:
        own, other = (fixed, moving) if k % 2 == 0 else (moving, fixed)
        own.add(along(f"Knuckle {k + 1}", x0, length, r))
        other.add(along(f"Swing clearance {k + 1}", x0 - c, length + 2 * c,
                        r + c))
    fixed_solid = _group("Fixed leaf", *[k for k in list(fixed.children)
                                         if "clearance" not in k.name],
                         kind="union")
    moving_solid = _group("Moving leaf", *[k for k in list(moving.children)
                                           if "clearance" not in k.name],
                          kind="union")
    fixed_cut = _group("Fixed leaf (cleared)", fixed_solid,
                       *[k for k in list(fixed.children)
                         if "clearance" in k.name], kind="difference")
    moving_cut = _group("Moving leaf (cleared)", moving_solid,
                        *[k for k in list(moving.children)
                          if "clearance" in k.name],
                        along("Pin clearance", -1, w + 2, pin_r + c),
                        kind="difference")
    pin = along("Pin", 0, w, pin_r)
    return _colour(_group("Print-in-place hinge", fixed_cut, pin,
                          moving_cut), dims)


LIVING_SIZES = {"60 × 30 mm": dict(width=60.0, length=30.0, thickness=1.2,
                                   slot=1.0, pitch=2.4)}


def build_living_hinge(dims):
    """A flexure panel: rows of staggered slots through a thin plate, so
    a stiff material bends along its length (a living hinge)."""
    p = _d(dims, LIVING_SIZES)
    w, L, t, slot, pitch = (p["width"], p["length"], p["thickness"],
                            p["slot"], p["pitch"])
    plate = _group("Living hinge", _cube("Plate", 0, 0, 0, w, L, t),
                   kind="difference")
    rows = max(int((w - 4) / pitch), 1)
    for i in range(rows):
        x = 2 + i * pitch
        if i % 2 == 0:
            plate.add(_cube(f"Slot {i + 1}", x, 3, -1, slot, L - 6, t + 2))
        else:
            plate.add(_cube(f"Slot {i + 1}a", x, -1, -1, slot, L / 2 - 1.5,
                            t + 2))
            plate.add(_cube(f"Slot {i + 1}b", x, L / 2 + 1.5, -1, slot,
                            L / 2 - 0.5, t + 2))
    return _colour(plate, dims)


BOSS_SIZES = {"M3 insert": dict(diameter=4.0, lead_in=4.8, depth=5.0,
                                boss=8.0, height=8.0),
              "M4 insert": dict(diameter=5.6, lead_in=6.4, depth=6.0,
                                boss=10.0, height=9.0)}


def build_insert_boss(dims):
    """A standoff boss for a heat-set brass insert."""
    p = _d(dims, BOSS_SIZES)
    hole = CadNode("hole", "Insert hole", dict(
        kind="heat_insert", diameter=p["diameter"], depth=p["depth"],
        head_diameter=p["lead_in"], head_depth=0.0, countersink_angle=90.0,
        nut_width=5.5, nut_height=2.4, length=0.0, extra=1.0, segments=32))
    boss = _group("Insert boss",
                  _cyl("Boss", 0, 0, 0, p["height"], p["boss"] / 2),
                  _move(hole, z=p["height"]), kind="difference")
    return _colour(boss, dims)


CAP_SIZES = {"28 mm (PCO)": dict(diameter=28.0, pitch=3.2, height=14.0,
                                 wall=2.0, clearance=0.4),
             "38 mm": dict(diameter=38.0, pitch=3.2, height=16.0, wall=2.2,
                           clearance=0.4)}


def build_bottle_cap(dims):
    """A screw cap for a bottle neck: a knurled shell with a bottle
    thread cut inside (the thread's tap, clearance included)."""
    p = _d(dims, CAP_SIZES)
    D, h, wall = p["diameter"], p["height"], p["wall"]
    outer = D + 2 * wall + 2
    shell = CadNode("knurl", "Grip", dict(diameter=outer, length=h,
                                          count=36, depth=0.6, angle=25.0))
    tap = CadNode("thread", "Neck thread", dict(
        kind="bottle", diameter=D, pitch=p["pitch"], length=h - wall + 1,
        starts=1, left_hand=False, internal=True,
        clearance=p["clearance"], bore=0.0))
    cap = _group("Bottle cap", shell, _move(tap, z=-1), kind="difference")
    return _colour(cap, dims)


CLIP_SIZES = {"6 mm cable": dict(cable=6.0, wall=1.6, width=8.0,
                                 screw=3.4),
              "10 mm cable": dict(cable=10.0, wall=2.0, width=10.0,
                                  screw=4.2)}


def build_cable_clip(dims):
    """A cable clip screwed to a surface: a C round the cable on a tab
    with a countersunk hole."""
    p = _d(dims, CLIP_SIZES)
    r, wall, w = p["cable"] / 2, p["wall"], p["width"]
    ring = _group("Clip", _cyl("Ring", 0, 0, 0, w, r + wall),
                  _cyl("Bore", 0, 0, -1, w + 2, r),
                  _cube("Opening", -r * 0.55, 0, -1, r * 1.1, r + wall + 1,
                        w + 2), kind="difference")
    tab = _group("Tab", _cube("Tab", r, -(r + wall), 0, 3 * r + 6, wall + 1,
                              w),
                 _move(CadNode("hole", "Screw hole", dict(
                     kind="countersink", diameter=p["screw"],
                     depth=wall + 1, head_diameter=p["screw"] * 2,
                     head_depth=0.0, countersink_angle=90.0, nut_width=5.5,
                     nut_height=2.4, length=0.0, extra=1.0, segments=32)),
                     x=2 * r + 3, y=-(r + wall), z=w / 2, rx=90),
                 kind="difference")
    return _colour(_move(_group("Cable clip", ring, tab), rx=90), dims)


# ------------------------------------------------------------- organisers

GRID = 42.0            # Gridfinity pitch
UNIT_H = 7.0           # Gridfinity height unit

GRIDFINITY_SIZES = {"1 × 1 × 3": dict(units_x=1, units_y=1, units_z=3),
                    "2 × 1 × 3": dict(units_x=2, units_y=1, units_z=3),
                    "2 × 2 × 6": dict(units_x=2, units_y=2, units_z=6)}
BASEPLATE_SIZES = {"3 × 3": dict(units_x=3, units_y=3),
                   "5 × 4": dict(units_x=5, units_y=4)}


def _foot(name, x, y):
    """A Gridfinity foot: the stepped profile (0.8 at 45°, 1.8 upright,
    2.15 at 45°) as the hull of three rounded slabs."""
    hull = CadNode("hull", name)
    for inset, z in ((2.95, 0.0), (2.15, 0.8), (2.15, 2.6), (0.25, 4.75)):
        side = GRID - 2 * inset
        hull.add(_rbox("Layer", x + inset, y + inset, z, side, side, 0.01,
                       max(4.0 - inset + 0.8, 0.8) if inset < 2 else 1.6))
    return hull


def build_gridfinity_bin(dims):
    """A Gridfinity bin: a foot per grid cell, walls to the height in
    7 mm units, a stacking lip, open top."""
    p = _d(dims, GRIDFINITY_SIZES)
    nx, ny, nz = int(p["units_x"]), int(p["units_y"]), int(p["units_z"])
    w, d = nx * GRID - 0.5, ny * GRID - 0.5
    h = nz * UNIT_H
    feet = _group("Feet", *[_foot(f"Foot {i + 1},{j + 1}", i * GRID,
                                  j * GRID)
                            for i in range(nx) for j in range(ny)])
    body = _group("Walls", _vbox("Body", 0.25, 0.25, 4.75, w, d, h - 4.75,
                                 3.75),
                  _vbox("Cavity", 1.45, 1.45, 5.95, w - 2.4, d - 2.4, h, 2.6),
                  kind="difference")
    return _colour(_group("Gridfinity bin", feet, body), dims)


def build_gridfinity_baseplate(dims):
    """A Gridfinity baseplate: a plate with one stepped pocket per cell."""
    p = _d(dims, BASEPLATE_SIZES)
    nx, ny = int(p["units_x"]), int(p["units_y"])
    plate = _group("Gridfinity baseplate",
                   _vbox("Plate", 0, 0, 0, nx * GRID, ny * GRID, 5.0, 4.0),
                   kind="difference")
    for i in range(nx):
        for j in range(ny):
            pocket = _foot(f"Pocket {i + 1},{j + 1}", i * GRID, j * GRID)
            plate.add(_move(pocket, z=0.25))
    return _colour(plate, dims)


TRAY_SIZES = {"160 × 100 × 30": dict(width=160.0, depth=100.0, height=30.0,
                                     cols=4, rows=2, wall=1.6, radius=4.0)}


def build_tray(dims):
    """A tray divided into cols × rows compartments with rounded
    corners."""
    p = _d(dims, TRAY_SIZES)
    w, d, h, wall = p["width"], p["depth"], p["height"], p["wall"]
    cols, rows = max(int(p["cols"]), 1), max(int(p["rows"]), 1)
    cw = (w - wall * (cols + 1)) / cols
    cd = (d - wall * (rows + 1)) / rows
    tray = _group("Tray", _vbox("Body", 0, 0, 0, w, d, h, p["radius"]),
                  kind="difference")
    for i in range(cols):
        for j in range(rows):
            tray.add(_vbox(f"Compartment {i + 1},{j + 1}",
                           wall + i * (cw + wall), wall + j * (cd + wall),
                           wall, cw, cd, h, max(p["radius"] - wall, 0.5)))
    return _colour(tray, dims)


# ------------------------------------------------------------- enclosures

ENCLOSURE_SIZES = {"Raspberry Pi 4": dict(pcb_w=85.0, pcb_d=56.0,
                                          height=30.0, wall=2.0,
                                          clearance=2.0, standoff=5.0,
                                          hole_inset=3.5),
                   "Arduino Uno": dict(pcb_w=68.6, pcb_d=53.4, height=25.0,
                                       wall=2.0, clearance=2.0, standoff=5.0,
                                       hole_inset=3.0)}


def build_enclosure(dims):
    """An electronics box for a board: a rounded shell with four
    insert-hole standoffs at the board's corners, a port opening in the
    front, and a lid beside it with a honeycomb vent and a locating
    lip."""
    p = _d(dims, ENCLOSURE_SIZES)
    wall, c = p["wall"], p["clearance"]
    iw, idp = p["pcb_w"] + 2 * c, p["pcb_d"] + 2 * c
    ow, od, h = iw + 2 * wall, idp + 2 * wall, p["height"]
    shell = _group("Shell", _vbox("Shell", 0, 0, 0, ow, od, h, 3.0),
                   _vbox("Inside", wall, wall, wall, iw, idp, h, 1.5),
                   _cube("Port opening", wall + c + 8, -1, wall +
                         p["standoff"] + 1.6, 30, wall + 2, 12),
                   kind="difference")
    box = _group("Box", shell)
    for sx in (0, 1):
        for sy in (0, 1):
            x = wall + c + (p["hole_inset"] if sx == 0
                            else p["pcb_w"] - p["hole_inset"])
            y = wall + c + (p["hole_inset"] if sy == 0
                            else p["pcb_d"] - p["hole_inset"])
            boss = _group("Standoff",
                          _cyl("Post", x, y, wall - 0.5, p["standoff"] + 0.5,
                               3.0),
                          _move(CadNode("hole", "Insert hole", dict(
                              kind="heat_insert", diameter=4.0, depth=4.5,
                              head_diameter=4.8, head_depth=0.0,
                              countersink_angle=90.0, nut_width=5.5,
                              nut_height=2.4, length=0.0, extra=1.0,
                              segments=24)),
                              x=x, y=y, z=wall + p["standoff"]),
                          kind="difference")
            box.add(boss)
    vent = CadNode("honeycomb", "Vent", dict(
        x=0.0, y=0.0, width=iw * 0.6, height=idp * 0.6, cell=5.0, wall=1.2,
        margin=0.0))
    lid = _group("Lid",
                 _vbox("Top", 0, 0, 0, ow, od, wall, 3.0),
                 _cube("Lip", wall + 0.2, wall + 0.2, wall - 0.01, iw - 0.4,
                       idp - 0.4, 2.0),
                 kind="union")
    lid_cut = _group("Lid (vented)", lid,
                     _move(_extrude("Vent cut", vent, wall + 4),
                           x=wall + iw * 0.2, y=wall + idp * 0.2, z=-1),
                     kind="difference")
    return _colour(_group("Enclosure", box,
                          _move(lid_cut, x=ow + 10)), dims)


def _spec(label, category, sizes, build, fields, colors=True):
    return dict(label=label, category=category, sizes=sizes, build=build,
                fields=fields, colors=list(COLORS) if colors else [])


PARTS = {
    "print_dovetail": _spec("Sliding dovetail joint", JOINTS,
                            DOVETAIL_SIZES, build_dovetail,
                            [("width", "Width"), ("height", "Height"),
                             ("length", "Length"),
                             ("clearance", "Clearance")]),
    "print_snap_fit": _spec("Cantilever snap-fit", JOINTS, SNAP_SIZES,
                            build_snap_fit,
                            [("length", "Arm length"),
                             ("thickness", "Arm thickness"),
                             ("width", "Width"), ("hook", "Hook depth"),
                             ("base", "Base height")]),
    "print_hinge": _spec("Print-in-place hinge", JOINTS, HINGE_SIZES,
                         build_print_in_place_hinge,
                         [("width", "Width"), ("leaf", "Leaf length"),
                          ("thickness", "Thickness"),
                          ("knuckles", "Knuckles"),
                          ("clearance", "Clearance")]),
    "print_living_hinge": _spec("Living hinge panel", JOINTS, LIVING_SIZES,
                                build_living_hinge,
                                [("width", "Width"), ("length", "Length"),
                                 ("thickness", "Thickness"),
                                 ("slot", "Slot width"),
                                 ("pitch", "Slot pitch")]),
    "print_insert_boss": _spec("Heat-set insert boss", JOINTS, BOSS_SIZES,
                               build_insert_boss,
                               [("diameter", "Hole"),
                                ("lead_in", "Lead-in"), ("depth", "Depth"),
                                ("boss", "Boss diameter"),
                                ("height", "Height")]),
    "print_bottle_cap": _spec("Bottle cap (threaded)", JOINTS, CAP_SIZES,
                              build_bottle_cap,
                              [("diameter", "Neck diameter"),
                               ("pitch", "Thread pitch"),
                               ("height", "Height"), ("wall", "Wall"),
                               ("clearance", "Clearance")]),
    "print_cable_clip": _spec("Cable clip", JOINTS, CLIP_SIZES,
                              build_cable_clip,
                              [("cable", "Cable diameter"),
                               ("wall", "Wall"), ("width", "Width"),
                               ("screw", "Screw hole")]),
    "gridfinity_bin": _spec("Gridfinity bin", ORGANISE, GRIDFINITY_SIZES,
                            build_gridfinity_bin,
                            [("units_x", "Units X"), ("units_y", "Units Y"),
                             ("units_z", "Height units")]),
    "gridfinity_baseplate": _spec("Gridfinity baseplate", ORGANISE,
                                  BASEPLATE_SIZES,
                                  build_gridfinity_baseplate,
                                  [("units_x", "Units X"),
                                   ("units_y", "Units Y")]),
    "print_tray": _spec("Divided tray", ORGANISE, TRAY_SIZES, build_tray,
                        [("width", "Width"), ("depth", "Depth"),
                         ("height", "Height"), ("cols", "Columns"),
                         ("rows", "Rows"), ("wall", "Wall"),
                         ("radius", "Corner radius")]),
    "enclosure": _spec("Electronics enclosure", ENCLOSURES, ENCLOSURE_SIZES,
                       build_enclosure,
                       [("pcb_w", "Board width"), ("pcb_d", "Board depth"),
                        ("height", "Inside height"), ("wall", "Wall"),
                        ("clearance", "Clearance"),
                        ("standoff", "Standoff height"),
                        ("hole_inset", "Hole inset")]),
}

COUNT_FIELDS = {"knuckles", "units_x", "units_y", "units_z", "cols", "rows"}
