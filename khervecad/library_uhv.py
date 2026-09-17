"""Surface-science UHV hardware for the Part Library: sample holders,
transfer arms that carry them, XYZT manipulators with a sample head,
and the tools of a preparation and an analysis chamber — sputter ion
gun, LEED optics, X-ray source, e-beam evaporator, a port-mounted
hemispherical analyser, a hot-cathode gauge head and mu-metal liners.

Modelled on the hardware UHV Design and VACGen sell (flag-style sample
plates, magnetically coupled transfer arms, XYZT stages), simplified but
dimensioned like the real thing.

Every port-mounted part follows the library's convention: the CF
sealing face is at z = 0 looking DOWN, the air side is z > 0 and the
vacuum side z < 0 — so the Chamber Designer can drop a part onto any
port and point its business end at the sample. `reach` is how far the
vacuum side goes: the distance from the sealing face to the sample.
Parts of several materials are a union of Objects, one per material.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .library import (CF_SIZES, KF_SIZES, _bolt_ring, _cyl,
                      _kf_flange_head, _micrometer, bellows, cf_flange,
                      cf_flange_solid, _bolt_holes)
from .library_vacuum import (GLASS, PAINT_BODY, PAINT_DARK, STEEL, _around,
                             _cube, _entry, _face_down, _group, _move,
                             _object, _paint, _ring, _torus, _turn, _union)
from .model import CadNode

CATEGORY = "Vacuum"
COPPER = "#c47a4a"
TANTALUM = "#8f9399"
MOLY = "#a3a8ad"
CERAMIC = "#efece4"
SAMPLE = "#3a4766"
MU_METAL = "#6f7a73"
PHOSPHOR = "#7fe07a"
BLACK = "#1d1f22"
HOSE_BLUE = "#2f6fb3"
HOSE_RED = "#b3402f"


# ── helpers ─────────────────────────────────────────────────────────

def _mount(e, dims, key="mount"):
    """The CF row of the mount flange (the table's, or `mount` from the
    Chamber Designer)."""
    return dict(CF_SIZES[str(dims.get(key) or e[key])])


def _blank_mount(p, name="Mount flange"):
    """A blank CF flange with its bolt holes, sealing face down."""
    return _face_down(cf_flange(dict(p, bore=0.0), name), p["thickness"])


def _open_mount(p, name="Mount flange"):
    return _face_down(cf_flange(p, name), p["thickness"])


def _cap(name, r_in, r_out, half_angle, n=24, segments=96):
    """A spherical-cap shell about +Z (centre at the origin, apex at
    z = r_out) out to *half_angle* degrees from the axis."""
    a = math.radians(half_angle)
    outer = [(r_out * math.sin(a * i / n), r_out * math.cos(a * i / n))
             for i in range(n + 1)]
    inner = [(r_in * math.sin(a * i / n), r_in * math.cos(a * i / n))
             for i in range(n, -1, -1)]
    rev = CadNode("rotate_extrude", name, dict(angle=360.0,
                                              segments=segments))
    rev.add(CadNode("polygon", f"{name} section", dict(
        x=0.0, y=0.0, points=[[round(max(r, 0.0), 3), round(z, 3)]
                              for r, z in outer + inner])))
    return rev


def _hose(name, x, y, z, length, colour, turn=(0.0, 0.0, 0.0), r=3.0):
    tube = _cyl(name, r, length, segments=16)
    return _paint(_move(_turn(tube, *turn), x, y, z), colour, "Rubber",
                  name=name)


def _shv(name, z, r=6.0):
    """An SHV high-voltage connector standing on +Z at height *z*."""
    return _union(name, _cyl("Connector body", r, 14.0, z=z, segments=32),
                  _cyl("Insulator", r * 0.55, 6.0, z=z + 14.0, segments=24))


# ── sample holders ──────────────────────────────────────────────────

def flag_plate(w=18.0, h=21.0, t=1.0, tab=6.0, sample=True, heater=False,
               name="Flag sample plate"):
    """A flag-style sample plate lying in XY: the plate spans x ±w/2,
    y 0..h, z 0..t, the grip ear rises past y = h, the sample sits on
    +Z under two spot-welded tantalum clips. Returns a union of
    Objects (plate, sample, ceramics)."""
    ear_w = w * 0.45
    plate = _group(
        "difference", "Plate",
        _union("Plate body", _cube("Plate", w, h, t, x=-w / 2, y=0.0),
               _cube("Grip ear", ear_w, tab, t, x=-ear_w / 2, y=h - 0.1)),
        _cyl("Ear hole", 1.3, t + 2.0, y=h + tab * 0.55, z=-1.0,
             segments=24),
        _cube("Pump-out slot", w * 0.5, 1.2, t + 2.0, x=-w * 0.25, y=1.5,
              z=-1.0))
    s = min(w, h) * 0.55
    clips = [_cube("Clip", s * 0.35, 1.6, 0.1, x=-s * 0.175,
                   y=h / 2 + sy * (s / 2 - 0.6) - 0.8, z=t + 0.5)
             for sy in (-1, 1)]
    clips += [_cube("Clip leg", 1.6, 0.4, 0.6, x=-0.8,
                    y=h / 2 + sy * (s / 2 + 0.2) - 0.2, z=t)
              for sy in (-1, 1)]
    metal = _union("Plate and clips", plate, *clips)
    objects = [_object("Plate (tantalum)", _paint(metal, TANTALUM))]
    if sample:
        crystal = _cube("Sample", s, s, 0.5, x=-s / 2, y=h / 2 - s / 2,
                        z=t)
        objects.append(_object("Sample crystal", _paint(crystal, SAMPLE)))
    if heater:
        blocks = _union("Heater ceramics",
                        _cube("PBN heater", w * 0.7, h * 0.5, 0.8,
                              x=-w * 0.35, y=h * 0.25, z=-0.8),
                        _cube("Spacer", 2.0, 2.0, 1.0, x=-w / 2 + 0.5,
                              y=0.5, z=-1.8),
                        _cube("Spacer", 2.0, 2.0, 1.0, x=w / 2 - 2.5,
                              y=0.5, z=-1.8))
        pads = _union("Contact pads",
                      _cube("Pad", 3.0, 3.0, 0.3, x=-w / 2 + 0.5, y=0.5,
                            z=-2.1),
                      _cube("Pad", 3.0, 3.0, 0.3, x=w / 2 - 3.5, y=0.5,
                            z=-2.1))
        objects.append(_object("Heater (PBN)",
                               _paint(blocks, CERAMIC, "Plastic")))
        objects.append(_object("Contacts (moly)", _paint(pads, MOLY)))
    return _union(name, *objects)


FLAG_SIZES = {
    "Flag plate 18 × 21 mm (Omicron style)": dict(width=18.0, height=21.0,
                                                  thickness=1.0, heater=0),
    "Flag plate 18 × 21 mm, PBN heater": dict(width=18.0, height=21.0,
                                              thickness=1.0, heater=1),
    "Flag plate 12 × 15 mm (compact)": dict(width=12.0, height=15.0,
                                            thickness=0.8, heater=0),
}


def build_flag_plate(dims):
    e = _entry(FLAG_SIZES, dims, "Flag plate 18 × 21 mm (Omicron style)")
    return flag_plate(float(e["width"]), float(e["height"]),
                      float(e["thickness"]), heater=bool(e["heater"]))


def pts_puck(d=25.0, name="PTS sample holder"):
    """A PTS-style (bayonet) sample holder: a moly disc on a grooved
    neck with two bayonet pins, the sample under a clamp ring held by
    four screws. Disc top at z = 3, neck below z = 0."""
    r = d / 2.0
    body = _group(
        "difference", "Puck",
        _union("Puck body", _cyl("Disc", r, 3.0, segments=64),
               _cyl("Neck", r * 0.45, 6.0, z=-6.0, segments=48)),
        _torus("Grip groove", r * 0.47, 0.8, z=-3.0, segments=48))
    pins = _around(2, r * 0.45, lambda i: _turn(
        _cyl("Bayonet pin", 0.8, 2.5, segments=12), y=90.0), 0.0)
    pins = [_move(pin, z=-4.5) for pin in pins]
    clamp = _union("Clamp",
                   _ring("Clamp ring", r * 0.42, r * 0.8, 0.8, z=3.5),
                   *_around(4, r * 0.62, lambda i: _cyl(
                       "Screw head", 0.9, 0.9, z=4.3, segments=16), 45.0))
    crystal = _cyl("Sample", r * 0.5, 0.5, z=3.0, segments=48)
    return _union(name,
                  _object("Holder (molybdenum)",
                          _paint(_union("Holder", body, clamp, *pins),
                                 MOLY)),
                  _object("Sample crystal", _paint(crystal, SAMPLE)))


PTS_SIZES = {"PTS Ø25 mm (bayonet)": dict(diameter=25.0),
             "PTS Ø20 mm (bayonet)": dict(diameter=20.0)}


def build_pts(dims):
    e = _entry(PTS_SIZES, dims, "PTS Ø25 mm (bayonet)")
    return pts_puck(float(e["diameter"]))


def _standing_flag(w=18.0, h=21.0, tab=6.0):
    """A flag plate turned upright in the XZ plane (sample facing -Y),
    ear up, its bottom edge at z = 0."""
    return _turn(flag_plate(w, h, 1.0, tab), x=90.0, name="Stand up")


CAROUSEL_SIZES = {
    "6 flags (CF40)": dict(mount="CF40 (DN40)", slots=6, reach=150.0),
    "12 flags (CF63)": dict(mount="CF63 (DN63)", slots=12, reach=200.0),
}


def build_carousel(dims):
    """A sample parking carousel: a rotary drive on a CF flange turning a
    disc that stands flag plates in receivers round its rim."""
    e = _entry(CAROUSEL_SIZES, dims, "6 flags (CF40)")
    p = _mount(e, dims)
    t, R = p["thickness"], float(e["reach"])
    n = max(int(e["slots"]), 2)
    disc_r = max(22.0 * n / (2 * math.pi) + 12.0, 30.0)
    parts = [_blank_mount(p),
             _cyl("Rotary drive", 25.0, 60.0, z=t, segments=64),
             _cyl("Dial", 32.0, 6.0, z=t + 60.0, segments=72),
             _cyl("Knob", 12.0, 22.0, z=t + 66.0, segments=32),
             _cyl("Shaft", 3.0, R - 4.0, z=-R + 4.0, segments=24),
             _cyl("Carousel disc", disc_r, 4.0, z=-R, segments=96)]
    flags = []
    for i in range(n):
        a = 360.0 * i / n
        rx = disc_r - 6.0
        rails = _union("Receiver",
                       _cube("Rail", 2.0, 3.0, 6.0, x=-11.0, y=-1.5, z=0.0),
                       _cube("Rail", 2.0, 3.0, 6.0, x=9.0, y=-1.5, z=0.0))
        parts.append(_turn(_move(_turn(rails, z=90.0), rx, 0.0, -R + 4.0),
                           z=a, name="Slot"))
        flags.append(_turn(_move(_turn(_standing_flag(), z=90.0), rx, 0.0,
                                 -R + 5.0), z=a, name="Slot"))
    return _union("Sample parking carousel",
                  _object("Carousel", _paint(_union("Carousel metal",
                                                    *parts), STEEL)),
                  *flags)


# ── transfer arms carrying a sample ─────────────────────────────────

def _flag_fork(z, w=18.0, h=21.0, tab=6.0):
    """Fork end effector at height *z* (its top), holding a flag plate by
    its ear under it."""
    fork = _union("Flag fork",
                  _cube("Fork body", 22.0, 6.0, 8.0, z=z - 8.0),
                  _cube("Tine", 2.5, 6.0, 12.0, x=-ear_gap(w) - 2.5,
                        y=-3.0, z=z - 20.0),
                  _cube("Tine", 2.5, 6.0, 12.0, x=ear_gap(w), y=-3.0,
                        z=z - 20.0),
                  _cube("Latch", ear_gap(w) * 2 + 5.0, 1.2, 2.0,
                        x=-ear_gap(w) - 2.5, y=-3.0, z=z - 20.0))
    plate = _move(_standing_flag(w, h, tab), z=z - 8.0 - (h + tab) + 0.5)
    return fork, plate


def ear_gap(w):
    return w * 0.45 / 2.0 + 0.4


def _bayonet(z, d=25.0):
    """PTS bayonet end effector with its puck hanging under it."""
    cup = _group("difference", "Bayonet cup",
                 _cyl("Cup", d * 0.3, 16.0, z=z - 16.0, segments=48),
                 _cyl("Cup bore", d * 0.23 + 0.2, 10.0, z=z - 17.0,
                      segments=48),
                 _cube("L-slot", 2.0, d, 5.0, x=-1.0, z=z - 17.0))
    puck = _move(_turn(pts_puck(d), x=180.0), z=z - 16.0)
    return cup, puck


TRANSFER_SIZES = {
    "Travel 300 mm, flag fork (CF40)": dict(mount="CF40 (DN40)",
                                            travel=300.0, reach=250.0,
                                            effector="flag", rotary=0),
    "Travel 600 mm, flag fork (CF40)": dict(mount="CF40 (DN40)",
                                            travel=600.0, reach=450.0,
                                            effector="flag", rotary=0),
    "Travel 600 mm, PTS bayonet (CF40)": dict(mount="CF40 (DN40)",
                                              travel=600.0, reach=450.0,
                                              effector="pts", rotary=1),
    "Travel 900 mm, rotary + linear (CF63)": dict(mount="CF63 (DN63)",
                                                  travel=900.0,
                                                  reach=700.0,
                                                  effector="flag",
                                                  rotary=1),
}


def build_sample_transfer(dims):
    """A magnetically coupled rotary/linear transfer arm (PowerProbe /
    VACGen style) carrying a sample: the sealed guide tube with its
    support, the magnet carriage slid down to extend the rod *reach*
    into the chamber, and the fork or bayonet with the sample on it."""
    e = _entry(TRANSFER_SIZES, dims, "Travel 300 mm, flag fork (CF40)")
    p = _mount(e, dims)
    t = p["thickness"]
    travel = float(e["travel"])
    reach = min(float(e["reach"]), travel + 40.0)
    L = travel + 90.0
    tube_r = 12.7
    ext = max(min((reach - 40.0) / travel, 1.0), 0.0)
    car_z = t + 25.0 + (1.0 - ext) * travel
    metal = [_blank_mount(p),
             _cyl("Base collar", tube_r + 6.0, 25.0, z=t, segments=48),
             _cyl("Guide tube", tube_r, L, z=t + 25.0, segments=48),
             _cyl("End cap", tube_r + 2.5, 10.0, z=t + 25.0 + L,
                  segments=48),
             _ring("Magnet carriage", tube_r + 0.6, tube_r + 16.0, 70.0,
                   z=car_z),
             _ring("Grip", tube_r + 16.0, tube_r + 18.0, 8.0,
                   z=car_z + 10.0),
             _ring("Grip", tube_r + 16.0, tube_r + 18.0, 8.0,
                   z=car_z + 52.0),
             _move(_turn(_cyl("Lock screw", 3.0, 14.0, segments=16), y=90.0),
                   tube_r + 16.0, 0.0, car_z + 35.0)]
    if travel >= 500.0:                     # a mid-length support
        mid = t + 25.0 + L * 0.6
        metal += [_ring("Support clamp", tube_r, tube_r + 8.0, 20.0,
                        z=mid),
                  _cube("Support strut", 10.0, 10.0, 120.0,
                        x=tube_r + 6.0, y=-5.0, z=mid - 100.0)]
    if int(e.get("rotary") or 0):
        metal += [_cyl("Rotary knob", tube_r + 8.0, 14.0,
                       z=t + 35.0 + L, segments=48),
                  _cyl("Rotary lock", 4.0, 10.0, x=tube_r + 2.0,
                       z=t + 49.0 + L, segments=16)]
    tip = -reach
    metal.append(_cyl("Transfer rod", 4.0, reach - 28.0, z=tip + 28.0,
                      segments=24))
    if e.get("effector") == "pts":
        cup, holder = _bayonet(tip + 28.0)
        metal.append(cup)
    else:
        fork, holder = _flag_fork(tip + 28.0)
        metal.append(fork)
    return _union("Sample transfer arm",
                  _object("Transfer arm", _paint(_union("Arm metal",
                                                        *metal), STEEL)),
                  holder)


# ── manipulators with a sample head ─────────────────────────────────

XYZT_SIZES = {
    "XYZT, Z 100 mm, flag head (CF63)": dict(mount="CF63 (DN63)",
                                             z_travel=100.0,
                                             xy_travel=25.0, reach=250.0,
                                             head="flag", cryo=0),
    "XYZT, Z 200 mm, flag head + LN2 (CF100)": dict(mount="CF100 (DN100)",
                                                    z_travel=200.0,
                                                    xy_travel=25.0,
                                                    reach=350.0,
                                                    head="flag", cryo=1),
    "XYZT, Z 100 mm, PTS heater head (CF63)": dict(mount="CF63 (DN63)",
                                                   z_travel=100.0,
                                                   xy_travel=12.5,
                                                   reach=250.0,
                                                   head="pts", cryo=0),
}


def _sample_head(z, head="flag", cryo=False):
    """The sample stage at the bottom of the manipulator tube, the
    sample facing +X with its centre at height *z*."""
    block = _union("Head block",
                   _cube("Copper block", 14.0, 30.0, 34.0, x=-10.0,
                         y=-15.0, z=z - 17.0),
                   _cube("Receiver rail", 3.0, 2.0, 26.0, x=4.0, y=-11.4,
                         z=z - 13.0),
                   _cube("Receiver rail", 3.0, 2.0, 26.0, x=4.0, y=9.4,
                         z=z - 13.0),
                   _cube("Hold-down spring", 1.0, 20.0, 1.0, x=6.5,
                         y=-10.0, z=z + 12.0))
    objects = []
    if head == "pts":
        cup = _group("difference", "PTS receiver",
                     _move(_turn(_cyl("Receiver", 9.0, 10.0, segments=48),
                                 y=90.0), 4.0, 0.0, z),
                     _move(_turn(_cyl("Receiver bore", 6.0, 12.0,
                                      segments=48), y=90.0), 5.5, 0.0, z))
        holder = _move(_turn(pts_puck(25.0), y=90.0), 20.0, 0.0, z)
        objects.append(_object("Head (copper)",
                               _paint(_union("Head", block, cup), COPPER)))
    else:
        holder = _move(_turn(_turn(flag_plate(18.0, 21.0, 1.0, 6.0,
                                              heater=True), x=90.0),
                             z=-90.0), 7.0, 0.0, z - 10.5)
        objects.append(_object("Head (copper)", _paint(block, COPPER)))
    ceramics = _union("Insulators",
                      _cube("Sapphire spacer", 3.0, 26.0, 30.0, x=-13.0,
                            y=-13.0, z=z - 15.0),
                      *[_cyl("Ceramic bead", 1.2, 4.0, x=-6.0 + 3.0 * k,
                             y=16.0, z=z + 14.0, segments=12)
                        for k in range(3)])
    objects.append(_object("Insulators (ceramic)",
                           _paint(ceramics, CERAMIC, "Plastic")))
    wires = [_cyl("Thermocouple", 0.25, 60.0, x=-6.0 + 3.0 * k, y=16.0,
                  z=z + 18.0, segments=8) for k in range(3)]
    if cryo:
        wires += [_cyl("Cold braid", 2.0, 45.0, x=-6.0, y=-8.0 + 16.0 * k,
                       z=z + 17.0, segments=12) for k in range(2)]
        wires.append(_cyl("LN2 reservoir", 14.0, 30.0, x=-3.0,
                          z=z + 62.0, segments=48))
    objects.append(_object("Wires and braids",
                           _paint(_union("Wires", *wires), COPPER)))
    return objects, holder


def build_xyzt(dims):
    """An XYZT sample manipulator (UHV Design / VACGen style): on the air
    side an XY table with two micrometers, a long edge-welded Z bellows
    between guide columns with a stepper-driven lead screw, and a
    differentially pumped rotary (T) drive with thermocouple and heater
    feedthroughs on top; on the vacuum side the support tube down to a
    copper sample head holding a flag plate (or a PTS puck), with an LN2
    reservoir and cold braids on the cryo version."""
    e = _entry(XYZT_SIZES, dims, "XYZT, Z 100 mm, flag head (CF63)")
    p = _mount(e, dims)
    t, Z = p["thickness"], float(e["z_travel"])
    xy, R = float(e["xy_travel"]), float(e["reach"])
    fr = p["flange_od"] / 2.0
    side = p["flange_od"] * 1.25
    metal = [_open_mount(p),
             _cube("XY table", side, side, 14.0, z=t),
             _move(_micrometer("X micrometer", xy + 40.0, 6.0),
                   side / 2, 0.0, t + 7.0),
             _move(_turn(_micrometer("Y micrometer", xy + 40.0, 6.0),
                         z=90.0), 0.0, side / 2, t + 7.0)]
    z0 = t + 14.0
    bel_len = Z * 1.15 + 20.0
    bel_r = max(p["bore"] * 0.35, 12.0)
    metal.append(_move(bellows(bel_r, bel_r * 0.45, bel_len,
                               max(int(bel_len / 5.0), 6)), z=z0))
    ztop = z0 + bel_len
    for a in (45.0, 225.0):
        r = side * 0.55
        metal.append(_cyl("Guide column", 6.0, bel_len + 16.0,
                          x=r * math.cos(math.radians(a)),
                          y=r * math.sin(math.radians(a)), z=z0,
                          segments=24))
    metal += [_cube("Top plate", side * 0.9, side * 0.9, 16.0, z=ztop),
              _cyl("Lead screw", 5.0, bel_len, x=-side * 0.39,
                   y=side * 0.39, z=z0, segments=24),
              _cyl("Handwheel", 22.0, 8.0, x=-side * 0.39, y=side * 0.39,
                   z=ztop + 16.0, segments=48)]
    motor = _cube("Stepper motor", 42.0, 42.0, 48.0, x=side * 0.45 - 21.0,
                  y=-side * 0.45 - 21.0, z=ztop + 16.0)
    zr = ztop + 16.0
    metal += [_cyl("Rotary drive (T)", fr * 0.7, 40.0, z=zr, segments=64),
              _cyl("Pumped seal port", 5.0, 30.0, x=fr * 0.7, z=zr + 20.0,
                   segments=16),
              _cyl("Graduated dial", fr * 0.8, 6.0, z=zr + 40.0,
                   segments=96),
              _cyl("Top flange", fr * 0.55, 10.0, z=zr + 46.0, segments=64)]
    fz = zr + 56.0
    for k, label in enumerate(("Thermocouple feedthrough",
                               "Heater feedthrough")):
        x = (-1.0 + 2.0 * k) * fr * 0.28
        metal += [_cyl(label, 6.0, 26.0, x=x, z=fz, segments=24),
                  _cyl(f"{label} flange", 10.0, 5.0, x=x, z=fz + 26.0,
                       segments=32)]
    extra = [_object("Stepper motor", _paint(motor, PAINT_DARK))]
    if int(e.get("cryo") or 0):
        metal += [_cyl("LN2 inlet", 3.0, 70.0, x=-4.0, y=fr * 0.25, z=fz,
                       segments=16),
                  _cyl("LN2 outlet", 3.0, 70.0, x=4.0, y=fr * 0.25, z=fz,
                       segments=16)]
    metal.append(_cyl("Support tube", 9.5, R - 17.0 - 20.0, z=-R + 37.0,
                      segments=32))
    metal.append(_cube("Head bracket", 20.0, 16.0, 20.0, x=-13.0, y=-8.0,
                       z=-R + 17.0))
    head, holder = _sample_head(-R, str(e.get("head") or "flag"),
                                bool(int(e.get("cryo") or 0)))
    return _union("XYZT manipulator",
                  _object("Manipulator", _paint(_union("Manipulator metal",
                                                       *metal), STEEL)),
                  *extra, *head, holder)


# ── preparation-chamber tools ───────────────────────────────────────

SPUTTER_SIZES = {
    "Ion gun 5 keV (CF40)": dict(mount="CF40 (DN40)", reach=120.0,
                                 scanned=0),
    "Scanning ion gun (CF63)": dict(mount="CF63 (DN63)", reach=150.0,
                                    scanned=1),
}


def build_sputter_gun(dims):
    """A sputter ion gun: on the vacuum side the ionisation chamber, the
    lens column and the nose aimed at the sample (*reach* away, working
    distance 25 mm); on the air side the housing, the SHV connector, the
    argon inlet through a leak valve and a KF16 differential pump port."""
    e = _entry(SPUTTER_SIZES, dims, "Ion gun 5 keV (CF40)")
    p = _mount(e, dims)
    t, R = p["thickness"], float(e["reach"])
    br = min(p["bore"] / 2.0 - 1.5, 16.0)
    tip = -(R - 25.0)
    col = max(-tip - 70.0, 10.0)
    metal = [_blank_mount(p),
             _cyl("Support tube", br * 0.55, col, z=-col, segments=32),
             _cyl("Ionisation chamber", br, 40.0, z=-col - 40.0,
                  segments=64),
             _cyl("Lens column", br * 0.7, 22.0, z=-col - 62.0,
                  segments=48),
             _cyl("Nose", br * 0.7, -tip - col - 62.0, z=tip,
                  r2=br * 0.7, segments=48),
             _cyl("Nose cone", 3.0, 8.0, z=tip, r2=br * 0.7, segments=48),
             _cyl("Housing", 26.0, 110.0, z=t, segments=64),
             _cyl("Housing cap", 28.0, 8.0, z=t + 110.0, segments=64),
             _move(_turn(_cyl("Gas line", 3.0, 45.0, segments=16), y=90.0),
                   26.0, 0.0, t + 30.0),
             _cube("Leak valve", 28.0, 28.0, 28.0, x=66.0, y=-14.0,
                   z=t + 16.0),
             _cyl("Leak valve knob", 12.0, 30.0, x=80.0, z=t + 44.0,
                  segments=48),
             _move(_turn(_cyl("Pump port tube", 10.0, 35.0, segments=32),
                         y=-90.0), -26.0, 0.0, t + 70.0),
             _move(_turn(_kf_flange_head(KF_SIZES["KF16 (DN16)"],
                                         "Pump port KF16"), y=-90.0),
                   -61.0, 0.0, t + 70.0)]
    if int(e.get("scanned") or 0):
        metal += [_cube("Deflection unit", 40.0, 40.0, 30.0, z=t + 118.0)]
    hv = _shv("SHV connector", t + 118.0 + (30.0 if int(
        e.get("scanned") or 0) else 0.0))
    return _union("Sputter ion gun",
                  _object("Gun", _paint(_union("Gun metal", *metal),
                                        STEEL)),
                  _object("HV connector", _paint(hv, BLACK, "Plastic")))


LEED_SIZES = {
    "4-grid rear-view LEED (CF100)": dict(mount="CF100 (DN100)",
                                          reach=160.0, grid=50.0),
    "Mini LEED (CF63)": dict(mount="CF63 (DN63)", reach=120.0, grid=30.0),
}


def build_leed(dims):
    """Rear-view LEED optics: on the vacuum side four concentric
    hemispherical grids and the phosphor screen, all centred on the
    sample *reach* below the flange (they fit through the flange bore to
    retract), the electron gun down the axis; on the air side the
    retraction bellows, three drive rods, the rear viewport and the HV
    feedthrough ring."""
    e = _entry(LEED_SIZES, dims, "4-grid rear-view LEED (CF100)")
    p = _mount(e, dims)
    t, R = p["thickness"], float(e["reach"])
    rg = min(float(e["grid"]), (p["bore"] / 2.0 - 2.0) / math.sin(
        math.radians(51.0)) - 10.0)
    half = 51.0
    optics = _move(_union("Optics centre",
                          *[_cap(f"Grid {k + 1}", rg + 2.0 * k,
                                 rg + 2.0 * k + 0.2, half)
                            for k in range(4)]), z=-R)
    screen = _move(_cap("Phosphor screen", rg + 9.0, rg + 10.0, half),
                   z=-R)
    top = -R + (rg + 10.0)
    rim = -R + (rg + 10.0) * math.cos(math.radians(half))
    rim_r = (rg + 10.0) * math.sin(math.radians(half))
    metal = [_open_mount(p),
             _ring("Screen rim", rim_r - 3.0, rim_r + 1.0, 3.0, z=rim - 1.5),
             _cyl("Gun drift tube", 4.0, top + R - 12.0, z=-R + 12.0,
                  segments=32),
             _cyl("Gun housing", 7.0, -top, z=top, segments=32)]
    metal += [_move(_cyl("Support rod", 1.5, -rim, segments=12),
                    rim_r * math.cos(a), rim_r * math.sin(a), rim)
              for a in (math.radians(90.0 + 120.0 * k) for k in range(3))]
    fr = p["flange_od"] / 2.0
    lift = 40.0
    metal += [_move(bellows(p["bore"] / 2.0 + 1.0, 6.0, lift, 8), z=t),
              _group("difference", "Retraction flange",
                     _cyl("Retraction plate", fr, 12.0, z=t + lift,
                          segments=96),
                     _cyl("Window bore", p["bore"] * 0.35, 14.0,
                          z=t + lift - 1.0, segments=64)),
              _ring("Viewport tube", p["bore"] * 0.35, p["bore"] * 0.35 + 3,
                    20.0, z=t + lift + 12.0)]
    metal += [_move(_cyl("Drive rod", 5.0, lift + 50.0, segments=24),
                    (fr - 8.0) * math.cos(a), (fr - 8.0) * math.sin(a), t)
              for a in (math.radians(30.0 + 120.0 * k) for k in range(3))]
    metal += _around(8, fr * 0.72, lambda i: _cyl(
        "HV feedthrough", 3.5, 16.0, z=t + lift + 12.0, segments=16), 22.5)
    glass = _cyl("Rear viewport", p["bore"] * 0.35 + 1.0, 3.0,
                 z=t + lift + 29.0, segments=64)
    return _union("LEED optics",
                  _object("LEED body", _paint(_union("LEED metal", *metal),
                                              STEEL)),
                  _object("Grids (molybdenum mesh)",
                          _paint(optics, MOLY, alpha=0.35)),
                  _object("Phosphor screen",
                          _paint(screen, PHOSPHOR, "Glass", alpha=0.7)),
                  _object("Rear viewport",
                          _paint(glass, GLASS, "Glass", alpha=0.45)))


XRAY_SIZES = {"Twin anode Al/Mg (CF40)": dict(mount="CF40 (DN40)",
                                              reach=110.0, lift=50.0),
              "Twin anode Al/Mg (CF63)": dict(mount="CF63 (DN63)",
                                              reach=120.0, lift=50.0)}


def build_xray_source(dims):
    """A twin-anode X-ray source for XPS: the water-cooled anode behind
    its aluminium window cap at 15 mm from the sample, on a retraction
    bellows, with the HV connector and the cooling-water lines."""
    e = _entry(XRAY_SIZES, dims, "Twin anode Al/Mg (CF40)")
    p = _mount(e, dims)
    t, R, lift = p["thickness"], float(e["reach"]), float(e["lift"])
    r = min(p["bore"] / 2.0 - 1.5, 16.0)
    tip = -(R - 15.0)
    metal = [_blank_mount(p),
             _cyl("Shroud", r, -tip - 12.0, z=tip + 12.0, segments=64),
             _cyl("Window cap", r * 0.55, 12.0, z=tip, r2=r, segments=64),
             _move(bellows(r * 0.8, 6.0, lift, 10), z=t),
             _cyl("Retraction plate", p["flange_od"] / 2.0, 10.0,
                  z=t + lift, segments=96),
             _cyl("Head housing", 30.0, 70.0, z=t + lift + 10.0,
                  segments=64)]
    metal += [_cyl("Retraction screw", 4.0, lift + 12.0,
                   x=(p["flange_od"] / 2.0 - 7.0) * math.cos(a),
                   y=(p["flange_od"] / 2.0 - 7.0) * math.sin(a), z=t,
                   segments=16)
              for a in (math.radians(90.0 + 120.0 * k) for k in range(3))]
    anode = _union("Anode",
                   _cyl("Anode tip", 2.0, 8.0, z=tip + 6.0, r2=r * 0.4,
                        segments=6),
                   _cyl("Anode body", r * 0.4, 20.0, z=tip + 14.0,
                        segments=32))
    zt = t + lift + 80.0
    return _union("X-ray source (twin anode)",
                  _object("Source body", _paint(_union("Source metal",
                                                       *metal), STEEL)),
                  _object("Anode (copper)", _paint(anode, COPPER)),
                  _object("HV connector", _paint(_shv("HV connector", zt),
                                                 BLACK, "Plastic")),
                  _object("Water in", _hose("Water in", 14.0, 0.0, zt,
                                            50.0, HOSE_BLUE)),
                  _object("Water out", _hose("Water out", -14.0, 0.0, zt,
                                             50.0, HOSE_RED)))


EVAP_SIZES = {"e-beam evaporator, 4 pockets (CF40)": dict(
    mount="CF40 (DN40)", reach=120.0)}


def build_evaporator(dims):
    """An e-beam evaporator (EFM style): a water-cooled copper shroud
    ending in the exit aperture and shutter, the linear drive feeding the
    rod, HV and cooling lines on the air side."""
    e = _entry(EVAP_SIZES, dims, "e-beam evaporator, 4 pockets (CF40)")
    p = _mount(e, dims)
    t, R = p["thickness"], float(e["reach"])
    r = min(p["bore"] / 2.0 - 1.5, 15.0)
    tip = -(R - 20.0)
    metal = [_blank_mount(p),
             _cyl("Housing", 25.0, 120.0, z=t, segments=64),
             _cyl("Linear drive", 10.0, 50.0, z=t + 120.0, segments=32),
             _cyl("Drive knob", 16.0, 18.0, z=t + 170.0, segments=48),
             _move(_turn(_cyl("Shutter drive", 5.0, 40.0, segments=16),
                         y=90.0), 25.0, 0.0, t + 40.0),
             _cube("Shutter", 2.0, r * 2.2, r * 2.2, x=-r * 0.2,
                   y=-r * 1.1, z=tip - r * 2.4),
             _cyl("Shutter shaft", 1.5, -tip + 5.0, x=r + 2.0,
                  y=-r * 0.8, z=tip - 5.0, segments=12)]
    shroud = _group("difference", "Cooling shroud",
                    _cyl("Shroud", r, -tip, z=tip, segments=64),
                    _cyl("Exit aperture", 3.0, 6.0, z=tip - 1.0,
                         segments=32))
    return _union("e-beam evaporator",
                  _object("Evaporator body", _paint(_union(
                      "Evaporator metal", *metal), STEEL)),
                  _object("Shroud (copper)", _paint(shroud, COPPER)),
                  _object("HV connector", _paint(_move(_turn(
                      _shv("HV connector", 0.0), y=-90.0), -25.0, 0.0,
                      t + 80.0), BLACK, "Plastic")),
                  _object("Water in", _hose("Water in", 12.0, 12.0,
                                            t + 188.0, 40.0, HOSE_BLUE)),
                  _object("Water out", _hose("Water out", -12.0, 12.0,
                                             t + 188.0, 40.0, HOSE_RED)))


GAUGE_SIZES = {"Hot-cathode gauge head (CF40 nipple)": dict(
    mount="CF40 (DN40)", nipple=90.0)}


def build_gauge_head(dims):
    """A hot-cathode (Bayard–Alpert) ion gauge in its own tubulated CF40
    nipple, with the controller head and its display on top."""
    e = _entry(GAUGE_SIZES, dims, "Hot-cathode gauge head (CF40 nipple)")
    p = _mount(e, dims)
    t, N = p["thickness"], float(e["nipple"])
    rb, rt = p["bore"] / 2.0, p["tube_od"] / 2.0
    metal = [_open_mount(p), _ring("Nipple", rb, rt, N, z=t),
             _move(cf_flange(p, "Gauge flange"), z=t + N)]
    metal += [_cyl("Grid post", 0.6, N * 0.7, x=8.0 * math.cos(a),
                   y=8.0 * math.sin(a), z=t + N * 0.3, segments=8)
              for a in (math.radians(45.0 + 90.0 * k) for k in range(4))]
    box_z = t + N + p["thickness"]
    box = _cube("Controller", 70.0, 50.0, 60.0, z=box_z)
    display = _cube("Display", 44.0, 1.0, 22.0, x=-22.0, y=-25.6,
                    z=box_z + 30.0)
    return _union("Ion gauge head",
                  _object("Gauge", _paint(_union("Gauge metal", *metal),
                                          STEEL)),
                  _object("Controller", _paint(box, PAINT_BODY)),
                  _object("Display", _paint(display, PHOSPHOR,
                                            "Emissive")))


# ── analysis ────────────────────────────────────────────────────────

HSA_SIZES = {
    "R150 analyser, CF100 lens (PHOIBOS-150 class)": dict(
        mount="CF100 (DN100)", r0=150.0, reach=180.0, lens=320.0, mu=1),
    "R100 analyser, CF63 lens": dict(mount="CF63 (DN63)", r0=100.0,
                                     reach=160.0, lens=240.0, mu=1),
    "R200 analyser, CF160 lens": dict(mount="CF160 (DN160)", r0=200.0,
                                      reach=220.0, lens=420.0, mu=1),
}


def build_hsa(dims):
    """A hemispherical electron analyser mounted by its lens flange: the
    entrance nozzle reaches to its working distance from the sample; the
    multi-element lens column, with the iris and slit drives, carries the
    analyser base plate; the two hemispheres (mean radius r0) sit under a
    mu-metal outer shield with the entrance slit over the lens and the
    multichannel detector and its electronics at the exit, 2·r0 away."""
    e = _entry(HSA_SIZES, dims, "R150 analyser, CF100 lens (PHOIBOS-150 "
                                "class)")
    p = _mount(e, dims)
    t, R = p["thickness"], float(e["reach"])
    r0, Ll = float(e["r0"]), float(e["lens"])
    rl = p["tube_od"] / 2.0
    wd = max(R * 0.2, 25.0)                 # working distance
    nozzle = R - wd
    metal = [_open_mount(p),
             _cyl("Entrance nozzle", 6.0, nozzle, z=-R + wd,
                  r2=rl * 0.8, segments=64),
             _cyl("Lens column", rl, Ll, z=t, segments=96)]
    metal += [_ring("Lens flange", rl, rl + 12.0, 10.0,
                    z=t + Ll * f) for f in (0.35, 0.7)]
    metal += [_cube("Iris drive", 36.0, 36.0, 30.0, x=rl - 4.0, y=-18.0,
                    z=t + Ll * 0.45),
              _move(_turn(_cyl("Iris knob", 10.0, 20.0, segments=32),
                          y=90.0), rl + 32.0, 0.0, t + Ll * 0.45 + 15.0),
              _cube("Slit drive", 30.0, 30.0, 26.0, x=-rl - 26.0, y=-15.0,
                    z=t + Ll * 0.8)]
    zb = t + Ll
    plate_r = r0 * 1.35
    wall = max(r0 * 0.04, 4.0)
    base = _move(_union("Analyser",
                        _cyl("Base plate", plate_r, 14.0, segments=128),
                        _bolt_ring(40, plate_r - 8.0, 3.2, 4.0, z=14.0,
                                   name="Base bolts"),
                        _move(_cap("Inner hemisphere", r0 * 0.66 - wall,
                                   r0 * 0.66, 90.0, n=32), z=14.0),
                        _cyl("Vent port", 10.0, 30.0,
                             z=14.0 + r0 * 1.34 - wall, segments=32)),
                 -r0, 0.0, zb)
    det_z = zb
    metal += [base,
              _cyl("Detector housing", 40.0, 90.0, x=-2.0 * r0,
                   z=det_z - 90.0, segments=64),
              _cyl("Detector flange", 52.0, 10.0, x=-2.0 * r0,
                   z=det_z - 100.0, segments=64),
              _cube("Support strut", 16.0, 16.0, Ll * 0.8,
                    x=-r0 - 8.0, y=-8.0, z=t + Ll * 0.2)]
    outer = _move(_cap("Outer hemisphere", r0 * 1.34 - wall, r0 * 1.34,
                       90.0, n=40), -r0, 0.0, zb + 14.0)
    electronics = _cube("Detector electronics", 90.0, 70.0, 60.0,
                        x=-2.0 * r0 - 45.0, y=-35.0, z=det_z - 160.0)
    objects = [_object("Analyser body",
                       _paint(_union("Analyser metal", *metal), STEEL)),
               _object("Outer hemisphere (mu-metal shield)"
                       if int(e.get("mu") or 0) else "Outer hemisphere",
                       _paint(outer, MU_METAL if int(e.get("mu") or 0)
                              else STEEL)),
               _object("Detector electronics",
                       _paint(electronics, PAINT_DARK))]
    if int(e.get("mu") or 0):
        sleeve = _ring("Lens mu-metal sleeve", rl + 0.5, rl + 2.0,
                       Ll * 0.3, z=t + 2.0)
        objects.append(_object("Lens shield (mu-metal)",
                               _paint(sleeve, MU_METAL)))
    return _union("Hemispherical analyser (lens mounted)", *objects)


LINER_SIZES = {
    "Sphere liner, Ø300 chamber": dict(radius=140.0, thickness=1.5,
                                       ports=6, port_d=66.0),
    "Sphere liner, Ø200 chamber": dict(radius=92.0, thickness=1.0,
                                       ports=6, port_d=40.0),
}


def mu_metal_liner(radius, thickness=1.5, openings=(), name="Mu-metal "
                   "liner"):
    """A spherical mu-metal liner: a thin shell with an opening where
    each port passes, *openings* = [(theta, phi, diameter)]."""
    n = 64
    outer = [(radius * math.sin(math.pi * i / n),
              radius * math.cos(math.pi * i / n)) for i in range(n + 1)]
    ri = radius - thickness
    inner = [(ri * math.sin(math.pi * i / n), ri * math.cos(math.pi * i / n))
             for i in range(n, -1, -1)]
    shell = CadNode("rotate_extrude", "Liner shell", dict(angle=360.0,
                                                         segments=128))
    shell.add(CadNode("polygon", "Liner section", dict(
        x=0.0, y=0.0, points=[[round(max(r, 0.0), 3), round(z, 3)]
                              for r, z in outer + inner])))
    part = _group("difference", name, shell)
    for theta, phi, d in openings:
        part.add(_turn(_cyl("Port opening", d / 2.0, radius * 0.6,
                            z=radius * 0.6, segments=48),
                       0.0, float(theta), float(phi), name="Opening"))
    return part


def build_liner(dims):
    e = _entry(LINER_SIZES, dims, "Sphere liner, Ø300 chamber")
    ports = [(0.0, 0.0), (180.0, 0.0)] + [(90.0, 90.0 * k)
                                           for k in range(4)]
    ports = ports[:max(int(e["ports"]), 0)]
    return _paint(mu_metal_liner(float(e["radius"]), float(e["thickness"]),
                                 [(th, ph, float(e["port_d"]))
                                  for th, ph in ports]), MU_METAL,
                  name="Mu-metal")


DOOR_SIZES = {"Fast-entry door (CF100)": dict(mount="CF100 (DN100)"),
              "Fast-entry door (CF63)": dict(mount="CF63 (DN63)")}


def build_fast_entry(dims):
    """A load-lock fast-entry door: a hinged viewport door on a Viton
    O-ring, closed by its own weight and the pump-down, with a latch."""
    e = _entry(DOOR_SIZES, dims, "Fast-entry door (CF100)")
    p = _mount(e, dims)
    t = p["thickness"]
    fr, rb = p["flange_od"] / 2.0, p["bore"] / 2.0
    frame = _group("difference", "Door frame",
                   _union("Frame body",
                          _face_down(cf_flange_solid(p, 0.0, "Mount flange"),
                                     t),
                          _cyl("Frame plate", fr, 10.0, z=t, segments=96)),
                   _cyl("Opening", rb, t + 14.0, z=-1.0, segments=96),
                   _bolt_holes(p, z=-1.0, height=t + 2.0))
    door = _group("difference", "Door",
                  _cyl("Door plate", fr, 12.0, z=t + 13.0, segments=96),
                  _cyl("Window bore", rb * 0.7, 14.0, z=t + 12.0,
                       segments=96))
    metal = [frame, door,
             _cube("Hinge block", 16.0, 30.0, 26.0, x=fr - 2.0, y=-15.0,
                   z=t + 2.0),
             _move(_turn(_cyl("Hinge pin", 3.0, 36.0, segments=16), x=90.0),
                   fr + 6.0, 18.0, t + 18.0),
             _cube("Latch", 12.0, 20.0, 24.0, x=-fr - 8.0, y=-10.0,
                   z=t + 4.0),
             _cyl("Handle", 5.0, 40.0, x=-fr * 0.5, z=t + 25.0, segments=24)]
    return _union("Fast-entry door",
                  _object("Door", _paint(_union("Door metal", *metal),
                                         STEEL)),
                  _object("O-ring (Viton)", _paint(_torus(
                      "O-ring", rb + 6.0, 1.8, z=t + 11.8), BLACK,
                      "Rubber")),
                  _object("Window", _paint(_cyl(
                      "Window glass", rb * 0.75, 4.0, z=t + 25.0,
                      segments=96), GLASS, "Glass", alpha=0.45)))


# ── registration ────────────────────────────────────────────────────

def _spec(label, build, sizes, fields=()):
    return dict(label=label, category=CATEGORY, sizes=sizes,
                fields=list(fields), build=build)


_REACH = [("reach", "Reach into chamber")]

PARTS = {
    "sample_flag": _spec("Sample holder: flag-style plate", build_flag_plate,
                         FLAG_SIZES, [("width", "Width"),
                                      ("height", "Height"),
                                      ("thickness", "Thickness")]),
    "sample_pts": _spec("Sample holder: PTS puck (bayonet)", build_pts,
                        PTS_SIZES, [("diameter", "Diameter")]),
    "sample_carousel": _spec("Sample parking carousel", build_carousel,
                             CAROUSEL_SIZES, _REACH),
    "transfer_sample": _spec("Transfer arm with sample holder",
                             build_sample_transfer, TRANSFER_SIZES,
                             [("travel", "Travel"),
                              ("reach", "Extension into chamber")]),
    "manipulator_xyzt": _spec("XYZT manipulator with sample head",
                              build_xyzt, XYZT_SIZES,
                              [("z_travel", "Z travel"),
                               ("xy_travel", "XY travel")] + _REACH),
    "sputter_gun": _spec("Sputter ion gun (Ar+)", build_sputter_gun,
                         SPUTTER_SIZES, _REACH),
    "leed": _spec("LEED optics (4-grid, rear view)", build_leed,
                  LEED_SIZES, _REACH + [("grid", "Inner grid radius")]),
    "xray_source": _spec("X-ray source (twin anode)", build_xray_source,
                         XRAY_SIZES, _REACH),
    "evaporator": _spec("e-beam evaporator", build_evaporator, EVAP_SIZES,
                        _REACH),
    "gauge_head": _spec("Ion gauge head (hot cathode, nipple)",
                        build_gauge_head, GAUGE_SIZES,
                        [("nipple", "Nipple length")]),
    "analyser_lens": _spec("Hemispherical analyser (lens-mounted)",
                           build_hsa, HSA_SIZES,
                           [("r0", "Mean radius"), ("lens", "Lens length")]
                           + _REACH),
    "mu_liner": _spec("Mu-metal liner (sphere)", build_liner, LINER_SIZES,
                      [("radius", "Radius"), ("thickness", "Thickness"),
                       ("port_d", "Opening Ø")]),
    "fast_entry": _spec("Load-lock fast-entry door", build_fast_entry,
                        DOOR_SIZES),
}
