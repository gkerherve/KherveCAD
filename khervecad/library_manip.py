"""Realistic UHV manipulators, a detailed magnetic transfer arm and a
detailed residual gas analyser for the Part Library.

The manipulators follow the construction of the commercial families:

- **Omniax style** (VACGEN): CF100/CF160 base, a hinged flange and a
  short XY bellows under an all-metal cross-roller XY stage (±25 mm), two
  stout guide columns with a ball screw and a long Z bellows (100-1000
  mm), a differentially pumped rotary feedthrough (DPRF) on the carriage.
- **Transax style** (VACGEN): CF63 base, two independent bellows (XY and
  Z), a single box column beside the probe carrying a cantilever arm.
- **HPT style** (VACGEN high-precision translator): compact, one bellows
  between a base plate and a top plate riding on three guide rods, a
  vertical Z micrometer and two XY micrometers on the top plate.
- **UHV Design XYZT style**: motorised XY stage, a profile rail on an
  extrusion spine with a stepper on top, and a MagiDrive rotary.

Every one ends in a vacuum-side sample head (flag, PTS or LN2-cooled flag)
*reach* below its CF sealing face, which is at z = 0 looking down like
every port-mounted part (see library_uhv).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .library import (CF_SIZES, KF_SIZES, _cyl, _kf_flange_head,
                      _micrometer, bellows, cf_flange)
from .library_uhv import (_mount,
                          _open_mount, _sample_head, _standing_flag,
                          between, pts_puck)
from .library_vacuum import (PAINT_DARK, STEEL, _around, _cube, _entry,
                             _face_down, _move, _object, _paint, _ring,
                             _torus, _turn, _union)

CATEGORY = "Vacuum"
ALU = "#c9ccd1"
ANODISED = "#2b2e33"
SCALE = "#f2f0e6"
LED_GREEN = "#43e06a"


def _bag():
    """Parts sorted by material: steel, aluminium, dark, white."""
    return {"steel": [], "alu": [], "dark": [], "white": []}


def _objects(name, bag, extra=()):
    looks = (("steel", "Stainless steel", STEEL, "Metal"),
             ("alu", "Aluminium", ALU, "Metal"),
             ("dark", "Motors and knobs", ANODISED, "Plastic"),
             ("white", "Scales and ceramics", SCALE, "Plastic"))
    objects = [_object(f"{name}: {label}",
                       _paint(_union(label, *bag[key]), colour, material))
               for key, label, colour, material in looks if bag[key]]
    return _union(name, *objects, *extra)


def _box(name, x, y, z, w, d, h):
    """A box from its corner."""
    return _cube(name, w, d, h, x=x, y=y, z=z)


def _hcyl_x(name, r, length, x, y, z, segments=32):
    return _move(_turn(_cyl(name, r, length, segments=segments), y=90.0),
                 x, y, z)


def _hcyl_y(name, r, length, x, y, z, segments=32):
    return _move(_turn(_cyl(name, r, length, segments=segments), x=-90.0),
                 x, y, z)


def _stepper(bag, name, x, y, z, size=42.0, length=48.0, axis="z"):
    """A NEMA stepper: body, end caps, a connector block, shaft coupling.
    Its body runs up (+Z), out along +X or +Y from (x, y, z) by *axis*,
    the shaft coupling back the other way."""
    body = _union(name, _cube("Motor body", size, size, length, z=0.0),
                  _cube("Connector", size * 0.4, 8.0, 12.0, y=size / 2,
                        x=-size * 0.2, z=length * 0.6))
    caps = _union(f"{name} caps",
                  _cube("End cap", size * 1.02, size * 1.02, 6.0, z=-1.0),
                  _cube("End cap", size * 1.02, size * 1.02, 6.0,
                        z=length - 5.0))
    coupling = _cyl("Coupling", size * 0.22, 22.0, z=-22.0, segments=24)
    turn = {"z": (0.0, 0.0, 0.0), "x": (0.0, 90.0, 0.0),
            "y": (-90.0, 0.0, 0.0)}[axis]
    bag["dark"].append(_move(_turn(body, *turn), x, y, z))
    bag["alu"].append(_move(_turn(caps, *turn), x, y, z))
    bag["steel"].append(_move(_turn(coupling, *turn), x, y, z))


def _scale(bag, x, y, z, length, step=10.0):
    """A white scale strip on the +Y face with a tick every *step* mm."""
    bag["white"].append(_box("Scale", x - 5.0, y, z, 10.0, 2.0, length))
    ticks = [_box("Tick", x - 5.0 + (0.0 if i % 5 else -1.5), y + 1.9,
                  z + i * step, 5.0 if i % 5 else 8.0, 0.6, 0.8)
             for i in range(int(length / step) + 1)]
    bag["dark"].append(_union("Ticks", *ticks))


def _xy_stage(bag, z0, side, travel, motor):
    """A cross-roller XY stage: a fixed plate, X slides, a middle plate, Y
    slides and the top plate, driven by micrometers or steppers. Returns
    the top of the stage."""
    rail = side * 0.8
    bag["alu"] += [_cube("XY base plate", side, side, 14.0, z=z0),
                   _cube("X carriage plate", side * 0.92, side * 0.92, 12.0,
                         z=z0 + 20.0),
                   _cube("Y carriage plate", side * 0.84, side * 0.84, 14.0,
                         z=z0 + 38.0)]
    for s in (-1, 1):
        bag["steel"] += [_box("X cross-roller rail", -rail / 2,
                              s * side * 0.3 - 4.0, z0 + 14.0, rail, 8.0, 6.0),
                         _box("Y cross-roller rail", s * side * 0.3 - 4.0,
                              -rail / 2, z0 + 32.0, 8.0, rail, 6.0)]
    if motor:
        _stepper(bag, "X motor", side / 2 + 24.0, 0.0, z0 + 26.0, axis="x")
        _stepper(bag, "Y motor", 0.0, side / 2 + 24.0, z0 + 45.0, axis="y")
    else:
        length = travel * 2.0 + 40.0
        bag["steel"] += [
            _move(_micrometer("X micrometer", length, 7.0), side * 0.46,
                  0.0, z0 + 26.0),
            _move(_turn(_micrometer("Y micrometer", length, 7.0), z=90.0),
                  0.0, side * 0.42, z0 + 45.0)]
        bag["alu"] += [_box("X micrometer bracket", side * 0.46 - 10.0,
                            -16.0, z0 + 14.0, 10.0, 32.0, 24.0),
                       _box("Y micrometer bracket", -16.0,
                            side * 0.42 - 10.0, z0 + 32.0, 32.0, 10.0, 24.0)]
    return z0 + 52.0


def _feedthroughs(bag, z, r, cryo):
    """The top of a manipulator: a CF40 flange with thermocouple and
    heater feedthroughs (and the LN2 lines of a cooled head)."""
    small = dict(CF_SIZES["CF16 (DN16)"])
    bag["steel"].append(_move(cf_flange(dict(CF_SIZES["CF40 (DN40)"],
                                             bore=0.0), "Top flange"), z=z))
    t = CF_SIZES["CF40 (DN40)"]["thickness"]
    for k, label in enumerate(("Thermocouple", "Heater")):
        x = (-1 + 2 * k) * r * 0.45
        bag["steel"] += [_cyl(f"{label} tube", 8.0, 24.0, x=x, z=z + t,
                              segments=24),
                         _move(cf_flange(dict(small, bore=0.0),
                                         f"{label} flange"), x, 0.0,
                               z + t + 24.0)]
        bag["dark"].append(_cyl(f"{label} connector", 7.0, 18.0, x=x,
                                z=z + t + 24.0 + small["thickness"],
                                segments=24))
    if cryo:
        for s in (-1, 1):
            bag["steel"] += [_cyl("LN2 line", 3.2, 80.0, y=s * 9.0,
                                  z=z + t, segments=16),
                             _cyl("Bayonet", 6.0, 20.0, y=s * 9.0,
                                  z=z + t + 80.0, segments=24)]


def _vacuum_side(bag, reach, head, tube_r):
    """The support tube down to the sample head, *reach* below the face."""
    cryo = head == "cryo"
    bag["steel"] += [
        _cyl("Support tube", tube_r, max(reach - 37.0, 5.0),
             z=-reach + 37.0, segments=48),
        _ring("Guide bush", tube_r, tube_r + 3.0, 14.0, z=-20.0),
        _box("Head bracket", -13.0, -8.0, -reach + 17.0, 20.0, 16.0, 20.0)]
    head_objs, holder = _sample_head(-reach, "pts" if head == "pts"
                                     else "flag", cryo)
    return head_objs + [holder]


def _rotary(bag, z, r, kind="dprf"):
    """A rotary drive on the carriage: a differentially pumped rotary
    feedthrough (two KF16 pump ports, a graduated dial and a handwheel)
    or a MagiDrive (a magnet housing and a big knob)."""
    if kind == "magidrive":
        bag["steel"].append(_cyl("MagiDrive housing", r * 0.6, 70.0, z=z,
                                 segments=64))
        bag["dark"].append(_cyl("MagiDrive knob", r * 0.8, 22.0, z=z + 70.0,
                                segments=64))
        bag["white"].append(_ring("Angle scale", r * 0.6, r * 0.82, 2.0,
                                  z=z + 60.0))
        return z + 92.0
    kf = dict(KF_SIZES["KF16 (DN16)"])
    bag["steel"].append(_cyl("DPRF body", r * 0.62, 60.0, z=z, segments=64))
    for k, zz in enumerate((z + 16.0, z + 40.0)):
        a = 90.0 * k
        port = _union("Pump port", _hcyl_x("Pump tube", 8.0, 28.0, 0.0,
                                           0.0, 0.0, 24),
                      _move(_turn(_kf_flange_head(kf, "KF16"), y=90.0),
                            28.0, 0.0, 0.0))
        bag["steel"].append(_turn(_move(port, r * 0.62, 0.0, zz), z=a))
    bag["alu"].append(_cyl("Graduated dial", r * 0.78, 6.0, z=z + 60.0,
                           segments=128))
    bag["dark"] += [_ring("Handwheel", r * 0.55, r * 0.72, 14.0,
                          z=z + 66.0),
                    *[_turn(_box("Spoke", 0.0, -3.0, z + 70.0, r * 0.62, 6.0,
                                 6.0), z=120.0 * k) for k in range(3)]]
    bag["white"].append(_union("Dial marks", *[
        _turn(_box("Mark", r * 0.66, -0.4, z + 66.0, r * 0.12, 0.8, 0.4),
              z=10.0 * k) for k in range(36)]))
    return z + 80.0


# ── Omniax style ────────────────────────────────────────────────────

OMNIAX_SIZES = {
    "Omniax style Z100, CF100 base, flag head": dict(
        mount="CF100 (DN100)", z_travel=100.0, xy_travel=25.0, reach=250.0,
        head="flag", motor=0),
    "Omniax style Z300, CF100 base, LN2 flag head": dict(
        mount="CF100 (DN100)", z_travel=300.0, xy_travel=25.0, reach=350.0,
        head="cryo", motor=0),
    "Omniax style Z600, CF160 base, motorised, PTS head": dict(
        mount="CF160 (DN160)", z_travel=600.0, xy_travel=25.0, reach=400.0,
        head="pts", motor=1),
}


def build_omniax(dims):
    """An Omniax-style XYZ manipulator with its DPRF rotary."""
    e = _entry(OMNIAX_SIZES, dims, "Omniax style Z100, CF100 base, flag "
                                   "head")
    p = _mount(e, dims)
    t, fr = p["thickness"], p["flange_od"] / 2.0
    Z, xy, R = float(e["z_travel"]), float(e["xy_travel"]), float(e["reach"])
    motor = bool(int(e.get("motor") or 0))
    bag = _bag()
    bag["steel"] += [_open_mount(p),
                     _ring("Hinged flange", p["bore"] / 2.0, fr, 12.0, z=t),
                     _box("Hinge block", fr - 12.0, -22.0, t, 34.0, 44.0,
                          26.0),
                     _hcyl_y("Hinge pin", 5.0, 56.0, fr + 5.0, -28.0,
                             t + 13.0)]
    bel_r = min(p["bore"] / 2.0 * 0.75, 40.0)
    bag["steel"].append(_move(bellows(bel_r, 9.0, 40.0, 8), z=t + 12.0))
    side = p["flange_od"] * 1.55
    z0 = t + 52.0
    bag["steel"] += [_cyl("Stage post", 7.0, 40.0, x=sx * fr * 0.72,
                          y=sy * fr * 0.72, z=t + 12.0, segments=16)
                     for sx in (-1, 1) for sy in (-1, 1)]
    ztop = _xy_stage(bag, z0, side, xy, motor)
    comp = 40.0 + Z * 0.25
    bel_len = comp + Z * 0.5
    col_h = comp + Z + 110.0
    cy = -side * 0.34
    for s in (-1, 1):
        bag["steel"] += [_cyl("Guide column", 14.0, col_h, x=s * side * 0.3,
                              y=cy, z=ztop, segments=48),
                         _cyl("Column foot", 22.0, 12.0, x=s * side * 0.3,
                              y=cy, z=ztop, segments=48)]
    bag["alu"].append(_box("Top yoke", -side * 0.38, cy - 30.0,
                           ztop + col_h, side * 0.76, 60.0, 22.0))
    bag["steel"].append(_cyl("Ball screw", 8.0, col_h, y=cy, z=ztop,
                             segments=24))
    zc = ztop + bel_len
    bag["alu"] += [_box("Z carriage", -side * 0.38, cy - 30.0, zc,
                        side * 0.76, side * 0.34 + 60.0, 24.0)]
    bag["steel"] += [_cyl("Linear bearing", 22.0, 60.0, x=s * side * 0.3,
                          y=cy, z=zc - 18.0, segments=48) for s in (-1, 1)]
    bag["steel"] += [_cyl("Ball nut", 16.0, 40.0, y=cy, z=zc - 8.0,
                          segments=32)]
    bag["steel"].append(_move(bellows(bel_r * 0.9, 10.0, bel_len,
                                      max(int(bel_len / 6.0), 6)), z=ztop))
    _scale(bag, side * 0.3 + 20.0, cy, ztop + 12.0, col_h - 20.0)
    bag["dark"].append(_box("Pointer", side * 0.3 + 12.0, cy + 2.0, zc + 6.0,
                            20.0, 3.0, 3.0))
    if motor:
        _stepper(bag, "Z motor", 0.0, cy, ztop + col_h + 22.0 + 22.0,
                 size=57.0, length=76.0)
    else:
        bag["dark"] += [_cyl("Z handwheel", 45.0, 14.0, y=cy,
                             z=ztop + col_h + 22.0, segments=64),
                        _cyl("Handle", 6.0, 40.0, x=34.0, y=cy,
                             z=ztop + col_h + 36.0, segments=16)]
    zr = _rotary(bag, zc + 24.0, max(fr * 0.7, 45.0))
    _feedthroughs(bag, zr, 30.0, e["head"] == "cryo")
    extra = _vacuum_side(bag, R, e["head"], 19.0 if p["bore"] > 90 else 12.7)
    return _objects("Omniax-style manipulator", bag, extra)


# ── Transax style ───────────────────────────────────────────────────

TRANSAX_SIZES = {
    "Transax style Z150, CF63 base, flag head": dict(
        mount="CF63 (DN63)", z_travel=150.0, xy_travel=25.0, reach=250.0,
        head="flag"),
    "Transax style Z300, CF63 base, PTS head": dict(
        mount="CF63 (DN63)", z_travel=300.0, xy_travel=25.0, reach=300.0,
        head="pts"),
    "Transax style Z450, CF63 base, LN2 flag head": dict(
        mount="CF63 (DN63)", z_travel=450.0, xy_travel=25.0, reach=350.0,
        head="cryo"),
}


def build_transax(dims):
    """A Transax-style manipulator: independent XY and Z bellows, a box
    column beside the probe and a cantilever arm on its carriage."""
    e = _entry(TRANSAX_SIZES, dims, "Transax style Z150, CF63 base, flag "
                                    "head")
    p = _mount(e, dims)
    t, fr = p["thickness"], p["flange_od"] / 2.0
    Z, xy, R = float(e["z_travel"]), float(e["xy_travel"]), float(e["reach"])
    bag = _bag()
    bag["steel"] += [_open_mount(p), _move(bellows(20.0, 7.0, 30.0, 6),
                                           z=t)]
    side = p["flange_od"] * 1.45
    ztop = _xy_stage(bag, t + 30.0, side, xy, False)
    comp = 30.0 + Z * 0.25
    bel_len = comp + Z * 0.5
    col_h = comp + Z + 90.0
    cy = -side * 0.5 - 20.0
    bag["alu"] += [_box("Column", -25.0, cy - 35.0, ztop - 14.0, 50.0, 70.0,
                        col_h + 14.0),
                   _box("Column foot", -45.0, cy - 40.0, ztop - 14.0, 90.0,
                        side * 0.5 + 20.0, 14.0)]
    zc = ztop + bel_len
    bag["alu"] += [_box("Carriage", -32.0, cy - 42.0, zc - 20.0, 64.0, 84.0,
                        60.0),
                   _box("Cantilever arm", -side * 0.3, cy + 35.0, zc + 10.0,
                        side * 0.6, -cy - 35.0 + side * 0.3, 18.0)]
    bag["steel"] += [_move(bellows(17.0, 8.0, bel_len,
                                   max(int(bel_len / 6.0), 6)), z=ztop),
                     _cyl("Lead screw cap", 10.0, 10.0, y=cy,
                          z=ztop + col_h, segments=24)]
    bag["dark"].append(_cyl("Z handwheel", 36.0, 14.0, y=cy,
                            z=ztop + col_h + 10.0, segments=64))
    _scale(bag, 0.0, cy + 35.0, ztop + 10.0, col_h - 20.0)
    zr = _rotary(bag, zc + 28.0, 40.0)
    _feedthroughs(bag, zr, 28.0, e["head"] == "cryo")
    extra = _vacuum_side(bag, R, e["head"], 12.7)
    return _objects("Transax-style manipulator", bag, extra)


# ── HPT style ───────────────────────────────────────────────────────

HPT_SIZES = {
    "HPT style Z50, CF40 base, flag head": dict(mount="CF40 (DN40)",
                                                z_travel=50.0,
                                                xy_travel=12.5, reach=200.0,
                                                head="flag"),
    "HPT style Z100, CF63 base, PTS head": dict(mount="CF63 (DN63)",
                                                z_travel=100.0,
                                                xy_travel=12.5, reach=250.0,
                                                head="pts"),
}


def build_hpt(dims):
    """An HPT-style translator: base plate, three guide rods, a top plate
    driven by a vertical micrometer, one bellows, XY micrometers."""
    e = _entry(HPT_SIZES, dims, "HPT style Z50, CF40 base, flag head")
    p = _mount(e, dims)
    t, fr = p["thickness"], p["flange_od"] / 2.0
    Z, xy, R = float(e["z_travel"]), float(e["xy_travel"]), float(e["reach"])
    bag = _bag()
    plate_r = fr * 1.35
    comp = 30.0 + Z * 0.3
    bel_len = comp + Z * 0.5
    rod_h = comp + Z + 40.0
    bag["steel"] += [_open_mount(p),
                     _move(bellows(p["bore"] * 0.3, 6.0, bel_len,
                                   max(int(bel_len / 5.0), 6)), z=t + 12.0)]
    bag["alu"] += [_cyl("Base plate", plate_r, 12.0, z=t, segments=96),
                   _cyl("Top plate", plate_r * 0.95, 16.0,
                        z=t + 12.0 + bel_len, segments=96)]
    for k in range(3):
        a = math.radians(90.0 + 120.0 * k)
        x, y = plate_r * 0.8 * math.cos(a), plate_r * 0.8 * math.sin(a)
        bag["steel"] += [_cyl("Guide rod", 6.0, rod_h, x=x, y=y, z=t + 12.0,
                              segments=24),
                         _cyl("Linear bushing", 10.0, 26.0, x=x, y=y,
                              z=t + 7.0 + bel_len, segments=32),
                         _cyl("Rod cap", 8.0, 6.0, x=x, y=y,
                              z=t + 12.0 + rod_h, segments=24)]
    a = math.radians(30.0)
    zx, zy = plate_r * 0.8 * math.cos(a), plate_r * 0.8 * math.sin(a)
    bag["steel"].append(_move(_turn(_micrometer("Z micrometer", bel_len + 20,
                                                 8.0), y=-90.0), zx, zy,
                              t + 12.0))
    ztop = t + 28.0 + bel_len
    bag["alu"] += [_cube("XY slide", plate_r * 1.1, plate_r * 1.1, 10.0,
                         z=ztop),
                   _cube("Probe plate", plate_r * 0.9, plate_r * 0.9, 10.0,
                         z=ztop + 12.0)]
    length = xy * 2.0 + 30.0
    bag["steel"] += [_move(_micrometer("X micrometer", length, 6.0),
                           plate_r * 0.55, 0.0, ztop + 5.0),
                     _move(_turn(_micrometer("Y micrometer", length, 6.0),
                                 z=90.0), 0.0, plate_r * 0.55, ztop + 17.0)]
    zr = ztop + 22.0
    bag["steel"].append(_cyl("Rotary seal", 22.0, 40.0, z=zr, segments=48))
    bag["dark"].append(_cyl("Rotary knob", 30.0, 16.0, z=zr + 40.0,
                            segments=48))
    _feedthroughs(bag, zr + 56.0, 26.0, False)
    extra = _vacuum_side(bag, R, e["head"], 9.5)
    return _objects("HPT-style translator", bag, extra)


# ── UHV Design XYZT style ───────────────────────────────────────────

UHVD_SIZES = {
    "UHV Design style XYZT Z200, CF63, flag head": dict(
        mount="CF63 (DN63)", z_travel=200.0, xy_travel=25.0, reach=300.0,
        head="flag"),
    "UHV Design style XYZT Z400, CF100, LN2 flag head": dict(
        mount="CF100 (DN100)", z_travel=400.0, xy_travel=25.0, reach=350.0,
        head="cryo"),
}


def build_uhvd(dims):
    """A UHV Design-style motorised XYZT stage: stepper XY stage, a
    profile rail on an extrusion spine, a stepper Z drive and a MagiDrive
    rotary on the carriage arm."""
    e = _entry(UHVD_SIZES, dims, "UHV Design style XYZT Z200, CF63, flag "
                                 "head")
    p = _mount(e, dims)
    t = p["thickness"]
    Z, xy, R = float(e["z_travel"]), float(e["xy_travel"]), float(e["reach"])
    bag = _bag()
    bag["steel"] += [_open_mount(p), _move(bellows(p["bore"] * 0.35, 7.0,
                                                   30.0, 6), z=t)]
    side = p["flange_od"] * 1.5
    ztop = _xy_stage(bag, t + 30.0, side, xy, True)
    comp = 35.0 + Z * 0.25
    bel_len = comp + Z * 0.5
    col_h = comp + Z + 100.0
    cy = -side * 0.5 - 30.0
    bag["dark"].append(_box("Extrusion spine", -30.0, cy - 30.0, ztop - 14.0,
                            60.0, 60.0, col_h + 14.0))
    bag["alu"] += [_box("Spine slot", sx, cy - 3.0, ztop, 2.0, 6.0, col_h)
                   for sx in (-31.0, 29.0)]
    bag["steel"] += [_box("Profile rail", -10.0, cy + 30.0, ztop, 20.0, 15.0,
                          col_h),
                     _box("Rail carriage", -22.0, cy + 30.0,
                          ztop + bel_len - 30.0, 44.0, 24.0, 60.0),
                     _box("Lead screw", -5.0, cy - 50.0, ztop, 10.0, 10.0,
                          col_h)]
    zc = ztop + bel_len
    bag["alu"].append(_box("Carriage arm", -side * 0.28, cy + 54.0, zc,
                           side * 0.56, -cy - 54.0 + side * 0.28, 20.0))
    bag["steel"].append(_move(bellows(p["bore"] * 0.3, 8.0, bel_len,
                                      max(int(bel_len / 6.0), 6)), z=ztop))
    _stepper(bag, "Z motor", 0.0, cy - 45.0, ztop + col_h + 22.0, size=57.0,
             length=76.0)
    bag["alu"].append(_box("Motor bracket", -34.0, cy - 80.0, ztop + col_h,
                           68.0, 70.0, 22.0))
    _scale(bag, 38.0, cy + 30.0, ztop, col_h)
    zr = _rotary(bag, zc + 20.0, 55.0, kind="magidrive")
    _feedthroughs(bag, zr, 26.0, e["head"] == "cryo")
    extra = _vacuum_side(bag, R, e["head"], 12.7)
    return _objects("UHV Design-style XYZT", bag, extra)


# ── transfer arm, in detail ─────────────────────────────────────────

ARM_SIZES = {
    "Travel 300 mm, flag fork (CF40)": dict(
        mount="CF40 (DN40)", travel=300.0, reach=250.0, effector="flag",
        aligner=0),
    "Travel 600 mm, flag fork, port aligner (CF40)": dict(
        mount="CF40 (DN40)", travel=600.0, reach=450.0, effector="flag",
        aligner=1),
    "Travel 600 mm, PTS bayonet, port aligner (CF63)": dict(
        mount="CF63 (DN63)", travel=600.0, reach=450.0, effector="pts",
        aligner=1),
    "Travel 900 mm, pincer grip, supported (CF63)": dict(
        mount="CF63 (DN63)", travel=900.0, reach=700.0, effector="pincer",
        aligner=1),
}


def _effector(bag, kind, z):
    """End effector hanging from the rod end at *z*; returns the sample
    Objects it carries."""
    if kind == "pts":
        bag["steel"] += [_cyl("Bayonet sleeve", 8.5, 18.0, z=z - 18.0,
                              segments=48),
                         _box("Bayonet slot", -1.0, -9.0, z - 14.0, 2.0, 18.0,
                              8.0)]
        return [_move(_turn(pts_puck(25.0), x=180.0), z=z - 18.0)]
    if kind == "pincer":
        bag["steel"] += [_cube("Pincer body", 16.0, 12.0, 14.0, z=z - 14.0),
                         _hcyl_y("Pivot pin", 1.5, 16.0, 0.0, -8.0, z - 18.0)]
        for s in (-1, 1):
            bag["steel"].append(_turn(_box("Jaw", -1.5, -4.0, z - 44.0, 3.0,
                                           8.0, 30.0), y=s * 6.0,
                                      name="Jaw angle"))
            bag["steel"].append(_box("Jaw pad", s * 4.0 - 1.0, -4.0,
                                     z - 46.0, 2.0, 8.0, 6.0))
        plate = _move(_turn(_standing_flag(), z=0.0), z=z - 44.0 - 21.0)
        return [plate]
    ear = 18.0 * 0.45 / 2.0 + 0.4
    bag["steel"] += [_cube("Fork head", 24.0, 8.0, 10.0, z=z - 10.0),
                     _box("Tine", -ear - 2.5, -3.0, z - 24.0, 2.5, 6.0, 14.0),
                     _box("Tine", ear, -3.0, z - 24.0, 2.5, 6.0, 14.0),
                     _box("Tine lip", -ear - 0.5, -3.0, z - 24.0, 1.0, 6.0,
                          1.5),
                     _box("Tine lip", ear - 0.5, -3.0, z - 24.0, 1.0, 6.0,
                          1.5),
                     _box("Leaf spring", -ear, 2.2, z - 20.0, ear * 2, 0.4,
                          9.0)]
    return [_move(_standing_flag(), z=z - 10.0 - 27.0 + 0.5)]


def build_arm_detailed(dims):
    """A magnetically coupled linear/rotary transfer arm in detail: a
    rotatable base flange with an optional port aligner (a short bellows
    between two plates and three push-pull screws), the Ø38 guide tube
    with a mm scale, a carriage with bearing housings, a knurled rotation
    ring, a lock lever and a pointer, the end stop and a CF16 bake-out
    port at the far end, a support strut on long arms, and inside the
    chamber the rod, its guide bush and the end effector with a sample."""
    e = _entry(ARM_SIZES, dims, "Travel 300 mm, flag fork (CF40)")
    p = _mount(e, dims)
    t, fr = p["thickness"], p["flange_od"] / 2.0
    travel = float(e["travel"])
    reach = min(float(e["reach"]), travel + 60.0)
    bag = _bag()
    bag["steel"] += [_open_mount(p),
                     _ring("Rotatable flange ring", 20.0, fr * 0.92, 10.0,
                           z=t)]
    z = t + 10.0
    if int(e.get("aligner") or 0):
        bag["alu"] += [_cyl("Aligner lower plate", fr, 12.0, z=z,
                            segments=96),
                       _cyl("Aligner upper plate", fr, 12.0, z=z + 42.0,
                            segments=96)]
        bag["steel"].append(_move(bellows(20.0, 6.0, 30.0, 6), z=z + 12.0))
        for k in range(3):
            a = math.radians(90.0 + 120.0 * k)
            x, y = fr * 0.78 * math.cos(a), fr * 0.78 * math.sin(a)
            bag["steel"].append(_cyl("Push-pull screw", 3.0, 70.0, x=x, y=y,
                                     z=z - 6.0, segments=16))
            bag["dark"] += [_cyl("Knurled nut", 6.5, 8.0, x=x, y=y,
                                 z=z + 54.0, segments=12),
                            _cyl("Knurled nut", 6.5, 8.0, x=x, y=y,
                                 z=z - 8.0, segments=12)]
        z += 54.0
    L = travel + 160.0
    bag["steel"] += [_cyl("Base collar", 26.0, 30.0, z=z, segments=64),
                     _cyl("Guide tube", 19.0, L, z=z + 30.0, segments=64)]
    zt = z + 30.0
    _scale(bag, 0.0, 19.0, zt + 20.0, travel + 60.0, step=10.0)
    ext = max(min((reach - 60.0) / travel, 1.0), 0.0)
    zc = zt + 20.0 + (1.0 - ext) * travel
    bag["alu"] += [_ring("Carriage body", 19.5, 36.0, 110.0, z=zc)]
    bag["steel"] += [_ring("Bearing housing", 19.5, 39.0, 14.0, z=zc),
                     _ring("Bearing housing", 19.5, 39.0, 14.0, z=zc + 96.0)]
    bag["dark"] += [_ring("Rotation ring", 36.0, 41.0, 46.0, z=zc + 32.0),
                    *_around(12, 41.0, lambda i: _cyl(
                        "Knurl", 2.0, 46.0, z=zc + 32.0, segments=8)),
                    _hcyl_x("Lock lever", 3.0, 40.0, 38.0, 0.0, zc + 20.0,
                            16),
                    CadSphere("Lever ball", 78.0, 0.0, zc + 20.0, 6.0)]
    bag["alu"].append(_box("Pointer", -2.0, 36.0, zc + 55.0, 4.0, 12.0, 2.0))
    zend = zt + L
    bag["steel"] += [_ring("End stop", 19.0, 26.0, 16.0, z=zend - 16.0),
                     _cyl("End cap", 24.0, 10.0, z=zend, segments=64),
                     _cyl("Bake-out port", 10.0, 24.0, z=zend + 10.0,
                          segments=32),
                     _move(cf_flange(dict(CF_SIZES["CF16 (DN16)"], bore=0.0),
                                     "Bake-out blank"), z=zend + 34.0)]
    if travel >= 600.0:
        zs = zt + L * 0.72
        bag["alu"] += [_ring("Support clamp", 19.0, 30.0, 24.0, z=zs),
                       _box("Clamp ear", 28.0, -8.0, zs, 30.0, 16.0, 24.0)]
        bag["steel"].append(between("Support strut", 6.0,
                                    (fr * 0.9, 0.0, t + 10.0),
                                    (50.0, 0.0, zs + 12.0), segments=24))
    bag["steel"] += [_ring("Rod guide bush", 5.5, 16.0, 12.0, z=-18.0),
                     _cyl("Transfer rod", 5.0, reach - 30.0,
                          z=-reach + 30.0, segments=32)]
    extra = _effector(bag, str(e.get("effector") or "flag"), -reach + 30.0)
    return _objects("Transfer arm", bag, extra)


def CadSphere(name, x, y, z, r):
    from .model import CadNode
    return CadNode("sphere", name, dict(x=float(x), y=float(y), z=float(z),
                                        radius=float(r), segments=24))


# ── residual gas analyser, in detail ────────────────────────────────

RGA_SIZES = {
    "100 amu, Faraday cup, box head (CF40)": dict(
        mount="CF40 (DN40)", probe=130.0, cdem=0, head="box"),
    "200 amu, Faraday + electron multiplier, box head (CF40)": dict(
        mount="CF40 (DN40)", probe=150.0, cdem=1, head="box"),
    "300 amu, cylindrical head (CF40)": dict(
        mount="CF40 (DN40)", probe=170.0, cdem=1, head="cylinder"),
}


def build_rga_detailed(dims):
    """A quadrupole RGA in detail. Vacuum side: the detector housing
    (Faraday cup, and an electron multiplier beside it), four
    molybdenum rods held by two ceramic spacers, three support posts and
    the open ion source at the tip — focus plate, a wire anode cage, the
    repeller cage and the thoria-coated filament. Air side: the
    feedthrough collar and the electronics head (a finned box with its
    connectors and status LEDs, or a cylindrical one)."""
    e = _entry(RGA_SIZES, dims, "100 amu, Faraday cup, box head (CF40)")
    p = _mount(e, dims)
    t = p["thickness"]
    P = max(float(e["probe"]), 60.0)
    bag = _bag()
    rods_len = P - 55.0
    z_rods = -30.0 - rods_len
    bag["steel"] += [_face_down(cf_flange(dict(p, bore=0.0), "Mount flange"),
                                t),
                     _cyl("Detector housing", 15.0, 28.0, z=-30.0,
                          segments=48),
                     _cyl("Faraday cup", 5.0, 6.0, z=-36.0, segments=24)]
    bag["white"] += [_ring("Feedthrough insulator", 4.0, 12.0, 3.0,
                           z=-2.0)]
    if int(e.get("cdem") or 0):
        bag["dark"].append(_cyl("Electron multiplier", 5.5, 24.0, x=10.0,
                                y=8.0, z=-28.0, r2=3.0, segments=24))
    rods = [_cyl("Quadrupole rod", 3.2, rods_len, x=sx * 5.6, y=sy * 5.6,
                 z=z_rods, segments=24) for sx in (-1, 1) for sy in (-1, 1)]
    bag["white"] += [_ring("Ceramic spacer", 2.5, 13.5, 5.0, z=z)
                     for z in (z_rods + 4.0, -40.0)]
    bag["steel"] += [_cyl("Support post", 1.2, rods_len + 24.0,
                          x=12.0 * math.cos(math.radians(a)),
                          y=12.0 * math.sin(math.radians(a)),
                          z=z_rods - 22.0, segments=12)
                     for a in (45.0, 165.0, 285.0)]
    zi = z_rods - 4.0
    ionizer = [_group_diff_plate(zi),
               *_around(8, 7.0, lambda i: _cyl("Anode wire post", 0.35, 14.0,
                                               z=zi - 16.0, segments=8)),
               _torus("Anode ring", 7.0, 0.4, z=zi - 2.0, segments=48),
               _torus("Anode ring", 7.0, 0.4, z=zi - 9.0, segments=48),
               _torus("Anode ring", 7.0, 0.4, z=zi - 16.0, segments=48),
               *_around(12, 11.0, lambda i: _cyl("Repeller post", 0.4,
                                                 18.0, z=zi - 19.0,
                                                 segments=8)),
               _torus("Repeller ring", 11.0, 0.5, z=zi - 2.5, segments=64),
               _torus("Repeller ring", 11.0, 0.5, z=zi - 19.0, segments=64)]
    bag["steel"].append(_union("Ion source", *ionizer))
    filament = _union("Filament",
                      _torus("Filament wire", 9.0, 0.2, z=zi - 9.0,
                             segments=48),
                      _cyl("Filament leg", 0.4, 12.0, x=9.0, z=zi - 9.0,
                           segments=8),
                      _cyl("Filament leg", 0.4, 12.0, x=-9.0, z=zi - 9.0,
                           segments=8))
    extra = [_object("Rods (molybdenum)", _paint(_union("Rods", *rods),
                                                  "#a3a8ad")),
             _object("Filament (thoriated iridium)",
                     _paint(filament, "#e8a040", "Emissive"))]
    bag["steel"].append(_cyl("Feedthrough collar", 17.0, 22.0, z=t,
                             segments=48))
    if e.get("head") == "cylinder":
        zb = t + 22.0
        bag["alu"] += [_cyl("Electronics head", 34.0, 150.0, z=zb,
                            segments=96),
                       *[_ring("Cooling fin", 34.0, 40.0, 2.5,
                               z=zb + 20.0 + 9.0 * k) for k in range(8)]]
        bag["dark"] += [_cyl("Top cap", 35.0, 14.0, z=zb + 150.0,
                             segments=96),
                        _cyl("Connector", 8.0, 16.0, x=15.0,
                             z=zb + 164.0, segments=24),
                        _cyl("Connector", 6.0, 14.0, x=-15.0,
                             z=zb + 164.0, segments=24)]
        leds = [_box("LED", -35.8, -8.0 + 8.0 * k, zb + 135.0, 1.0, 4.0,
                     4.0) for k in range(3)]
    else:
        zb = t + 22.0
        bag["alu"] += [_box("Electronics box", -60.0, -36.0, zb, 150.0, 72.0,
                            92.0),
                       *[_box("Heat-sink fin", -55.0 + 11.0 * k, -32.0,
                              zb + 92.0, 2.0, 64.0, 14.0) for k in range(13)]]
        bag["dark"] += [_box("Connector panel", 90.0, -30.0, zb + 10.0, 3.0,
                             60.0, 72.0),
                        _box("DB-9 serial", 93.0, -22.0, zb + 50.0, 6.0,
                             22.0, 10.0),
                        _hcyl_x("Power jack", 5.0, 10.0, 93.0, 12.0,
                                zb + 55.0, 24),
                        _hcyl_x("Mounting screw", 2.5, 6.0, 93.0, -24.0,
                                zb + 20.0, 12)]
        leds = [_box("LED", 93.0, -18.0 + 9.0 * k, zb + 30.0, 2.0, 4.0, 4.0)
                for k in range(4)]
    extra.append(_object("Status LEDs", _paint(_union("LEDs", *leds),
                                               LED_GREEN, "Emissive")))
    return _objects("Residual gas analyser", bag, extra)


def _group_diff_plate(z):
    from .library_vacuum import _group
    return _group("difference", "Focus plate",
                  _cyl("Focus plate", 13.0, 1.0, z=z - 1.0, segments=64),
                  _cyl("Focus aperture", 2.5, 3.0, z=z - 2.0, segments=24))


# ── registration ────────────────────────────────────────────────────

def _spec(label, build, sizes, fields=()):
    return dict(label=label, category=CATEGORY, sizes=sizes,
                fields=list(fields), build=build)


_MANIP_FIELDS = [("z_travel", "Z travel"), ("xy_travel", "XY travel"),
                 ("reach", "Reach into chamber")]

PARTS = {
    "manip_omniax": _spec("Manipulator: Omniax style (dual bellows, DPRF)",
                          build_omniax, OMNIAX_SIZES, _MANIP_FIELDS),
    "manip_transax": _spec("Manipulator: Transax style (side column)",
                           build_transax, TRANSAX_SIZES, _MANIP_FIELDS),
    "manip_hpt": _spec("Manipulator: HPT style (three-rod translator)",
                       build_hpt, HPT_SIZES, _MANIP_FIELDS),
    "manip_uhvd": _spec("Manipulator: UHV Design style XYZT (motorised)",
                        build_uhvd, UHVD_SIZES, _MANIP_FIELDS),
    "transfer_arm_detailed": _spec("Transfer arm, detailed (scale, "
                                   "aligner, effectors)",
                                   build_arm_detailed, ARM_SIZES,
                                   [("travel", "Travel"),
                                    ("reach", "Extension into chamber")]),
    "rga_detailed": _spec("Residual gas analyser, detailed",
                          build_rga_detailed, RGA_SIZES,
                          [("probe", "Probe length")]),
}
