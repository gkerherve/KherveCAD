"""Parts library — parametric vacuum hardware built from tree nodes.

CF (ConFlat) and KF (Quick Flange) flanges, straight nipples, tees
and crosses in the conventional sizes, threaded fasteners (hex bolts,
socket head cap screws and hex nuts with real helical ISO threads),
plus a simplified turbo pump shell. Every part is generated as an
ordinary node subtree, so inserted parts stay fully editable and the
generated OpenSCAD reads like a human wrote it. Dimensions are
editable before insertion — any size works, the tables only pre-fill
the standard ones.

CF flanges are modelled from the manufacturer cross-section drawings
(Kurt J. Lesker / VACGen style): the whole flange is one revolved
profile with the recessed sealing face, the **knife edge** at the
gasket seal diameter, the gasket seat wall and the edge chamfers —
then the bolt circle is subtracted with a for-loop.

Threads use the OpenSCAD twist-extrude idiom: a thread-form
cross-section (root flat, 60° flanks, crest flat between the minor
and major radii) extruded with ``twist = -360 * length / pitch``
yields a true single-start helical V-thread. Nuts subtract the same
solid with clearance, so nuts really thread onto their bolts.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                             QDoubleSpinBox, QFormLayout, QHBoxLayout,
                             QLabel, QListWidget, QSpinBox, QVBoxLayout)

from .model import CadNode, DocumentModel

#: CF (ConFlat) conventional sizes, mm (gasket_od = copper gasket
#: outer diameter, which locates the knife edge and the recess).
CF_SIZES = {
    "CF16 (DN16)": dict(flange_od=34.0, thickness=7.5,
                        bolt_circle=27.0, bolts=6, bolt_hole=4.4,
                        bore=16.0, tube_od=19.1, gasket_od=21.3),
    "CF40 (DN40)": dict(flange_od=69.9, thickness=12.7,
                        bolt_circle=58.7, bolts=6, bolt_hole=6.6,
                        bore=35.0, tube_od=38.1, gasket_od=48.3),
    "CF63 (DN63)": dict(flange_od=114.3, thickness=17.5,
                        bolt_circle=92.1, bolts=8, bolt_hole=8.4,
                        bore=60.0, tube_od=63.5, gasket_od=82.6),
    "CF100 (DN100)": dict(flange_od=152.4, thickness=20.0,
                          bolt_circle=130.3, bolts=16, bolt_hole=8.4,
                          bore=97.0, tube_od=101.6, gasket_od=120.7),
    "CF160 (DN160)": dict(flange_od=203.2, thickness=22.3,
                          bolt_circle=181.0, bolts=20, bolt_hole=8.4,
                          bore=147.0, tube_od=152.4, gasket_od=171.5),
}

#: ISO metric coarse fasteners, mm (DIN 933 hex head / DIN 912 socket
#: head / DIN 934 nut). af = across flats, socket = hex key size.
BOLT_SIZES = {
    "M3": dict(d=3.0, pitch=0.5, af=5.5, head_h=2.0, socket=2.5,
               nut_h=2.4, length=12.0),
    "M4": dict(d=4.0, pitch=0.7, af=7.0, head_h=2.8, socket=3.0,
               nut_h=3.2, length=16.0),
    "M5": dict(d=5.0, pitch=0.8, af=8.0, head_h=3.5, socket=4.0,
               nut_h=4.0, length=20.0),
    "M6": dict(d=6.0, pitch=1.0, af=10.0, head_h=4.0, socket=5.0,
               nut_h=5.0, length=20.0),
    "M8": dict(d=8.0, pitch=1.25, af=13.0, head_h=5.3, socket=6.0,
               nut_h=6.5, length=25.0),
    "M10": dict(d=10.0, pitch=1.5, af=17.0, head_h=6.4, socket=8.0,
                nut_h=8.0, length=30.0),
    "M12": dict(d=12.0, pitch=1.75, af=19.0, head_h=7.5, socket=10.0,
                nut_h=10.0, length=40.0),
    "M16": dict(d=16.0, pitch=2.0, af=24.0, head_h=10.0, socket=14.0,
                nut_h=13.0, length=50.0),
    "M20": dict(d=20.0, pitch=2.5, af=30.0, head_h=12.5, socket=17.0,
                nut_h=16.0, length=60.0),
}

#: KF (Quick Flange / QF) conventional sizes, mm.
KF_SIZES = {
    "KF16 (DN16)": dict(flange_od=30.0, thickness=5.0, bore=16.0,
                        tube_od=20.0),
    "KF25 (DN25)": dict(flange_od=40.0, thickness=5.0, bore=24.0,
                        tube_od=28.0),
    "KF40 (DN40)": dict(flange_od=55.0, thickness=5.0, bore=38.0,
                        tube_od=44.5),
    "KF50 (DN50)": dict(flange_od=75.0, thickness=6.5, bore=50.0,
                        tube_od=57.0),
}

#: turbo pump classes by inlet flange (typical commercial sizes —
#: the DN63 class is ~80 l/s, DN100 ~300 l/s, DN160 ~700 l/s).
TURBO_SIZES = {
    "DN63 CF (~80 l/s)": dict(inlet="CF63 (DN63)",
                              exhaust="KF16 (DN16)",
                              body_od=92.0, body_height=90.0),
    "DN100 CF (~300 l/s)": dict(inlet="CF100 (DN100)",
                                exhaust="KF25 (DN25)",
                                body_od=120.0, body_height=110.0),
    "DN160 CF (~700 l/s)": dict(inlet="CF160 (DN160)",
                                exhaust="KF40 (DN40)",
                                body_od=170.0, body_height=150.0),
}

#: port directions as rotate([x, y, z]) mapping +Z to the port axis.
_PORTS = {
    "+X": (0.0, 90.0, 0.0), "-X": (0.0, -90.0, 0.0),
    "+Y": (-90.0, 0.0, 0.0), "-Y": (90.0, 0.0, 0.0),
    "+Z": (0.0, 0.0, 0.0), "-Z": (180.0, 0.0, 0.0),
}


def _cyl(name, radius, height, z=0.0, x=0.0, y=0.0, r2=None,
         segments=96):
    return CadNode("cylinder", name, dict(
        x=x, y=y, z=z, height=height, radius_bottom=radius,
        radius_top=radius if r2 is None else r2,
        segments=segments, center=False))


def _bolt_holes(p, z, height):
    """A for-loop of bolt holes around the bolt circle."""
    bolts = max(int(p["bolts"]), 1)
    step = 360.0 / bolts
    loop = CadNode("for_loop", "Bolt holes", dict(
        variable="a", start=0.0, end=360.0 - step / 2, step=step))
    rot = CadNode("rotate", "Around axis", dict(x=0.0, y=0.0, z="a"))
    rot.add(_cyl("Bolt hole", p["bolt_hole"] / 2.0, height,
                 z=z, x=p["bolt_circle"] / 2.0, segments=24))
    loop.add(rot)
    return loop


# -------------------------------------------------------------- threads

#: ISO 60-degree thread form as fractions of one pitch around the
#: cross-section: root flat, rising flank, crest flat, falling flank.
_THREAD_FORM = (0.25, 0.3125, 0.125, 0.3125)


def thread_profile(d_major: float, pitch: float, n: int = 72):
    """Cross-section polygon for a twist-extruded helical thread: a
    circle whose radius traces the ISO thread form (minor radius at
    the root, 60° flanks, flat crest at the major radius) once around.
    Extruded with twist = -360*L/pitch this sweeps a true V-thread."""
    depth = 0.6134 * pitch                    # ISO: 5H/8 engagement
    r_minor = d_major / 2.0 - depth
    root, rise, crest, fall = _THREAD_FORM

    def radius(u):
        if u < root:
            return r_minor
        u -= root
        if u < rise:
            return r_minor + depth * (u / rise)
        u -= rise
        if u < crest:
            return d_major / 2.0
        u -= crest
        return d_major / 2.0 - depth * (u / fall)
    return [[round(radius(i / n) * math.cos(2 * math.pi * i / n), 4),
             round(radius(i / n) * math.sin(2 * math.pi * i / n), 4)]
            for i in range(n)]


def thread_solid(d: float, pitch: float, length: float,
                 clearance: float = 0.0, name: str = "Thread") -> CadNode:
    """A threaded cylinder: thread-form polygon + twisted extrusion.
    *clearance* grows the major diameter (for the hole in a nut)."""
    turns = length / pitch
    ext = CadNode("linear_extrude", name, dict(
        height=length, twist=round(-360.0 * turns, 2), scale=1.0,
        center=False, segments=max(int(turns * 8), 16)))
    ext.add(CadNode("polygon", f"{name} profile", dict(
        x=0.0, y=0.0,
        points=thread_profile(d + 2.0 * clearance, pitch))))
    return ext


def _hex(name, af, height, z=0.0):
    """Hexagonal prism: a 6-segment cylinder with the circumradius
    that gives *af* across flats."""
    return _cyl(name, round(af / math.sqrt(3.0), 3), height, z=z,
                segments=6)


def hex_bolt(p, length: float) -> CadNode:
    """DIN 933 style hex head bolt, fully threaded."""
    part = CadNode("union", "Hex bolt")
    part.add(thread_solid(p["d"], p["pitch"], length))
    part.add(_hex("Hex head", p["af"], p["head_h"], z=length))
    return part


def socket_screw(p, length: float) -> CadNode:
    """DIN 912 style socket head cap screw with hex socket."""
    part = CadNode("difference", "Socket head screw")
    solid = CadNode("union", "Screw body")
    solid.add(thread_solid(p["d"], p["pitch"], length))
    solid.add(_cyl("Cap head", 0.75 * p["d"], p["d"], z=length,
                   segments=48))
    part.add(solid)
    part.add(_hex("Hex socket", p["socket"], 0.6 * p["d"] + 1.0,
                  z=length + 0.4 * p["d"]))
    return part


def hex_nut(p) -> CadNode:
    """DIN 934 style hex nut — the threaded hole is the bolt thread
    subtracted with clearance, so it really mates."""
    part = CadNode("difference", "Hex nut")
    part.add(_hex("Nut body", p["af"], p["nut_h"]))
    hole = CadNode("translate", "Thread hole", dict(x=0.0, y=0.0,
                                                    z=-1.0))
    hole.add(thread_solid(p["d"], p["pitch"], p["nut_h"] + 2.0,
                          clearance=0.15, name="Internal thread"))
    part.add(hole)
    return part


# ------------------------------------------------------------- flanges

#: CF sealing face constants (from manufacturer drawings), mm.
_CF_RECESS_DEPTH = 1.6       # sealing-face counterbore depth
_CF_KNIFE_HEIGHT = 1.1       # knife edge rise above the recess floor
_CF_KNIFE_SETBACK = 0.9      # knife tip radius inside the gasket OD
_CF_SEAT_CLEARANCE = 0.3     # recess wall outside the gasket OD
_CF_CHAMFER = 1.0            # outer edge chamfers


def cf_profile(p, tube_length: float = 0.0):
    """The revolved cross-section of a ConFlat flange, as (radius, z)
    points — the same view a Lesker/VACGen drawing shows. z = 0 is
    the flange back, z = thickness the sealing face; the tube extends
    below z = 0. Features, from the bore outward: recess floor, the
    knife edge (70° ridge at the gasket seal diameter), recess wall
    (gasket seat) and chamfered outer edge."""
    r_od = p["flange_od"] / 2.0
    t = p["thickness"]
    r_bore = max(p["bore"], 0.0) / 2.0
    r_tube = p["tube_od"] / 2.0
    r_seat = p["gasket_od"] / 2.0 + _CF_SEAT_CLEARANCE
    r_knife = p["gasket_od"] / 2.0 - _CF_KNIFE_SETBACK
    floor = t - _CF_RECESS_DEPTH
    tip = floor + _CF_KNIFE_HEIGHT
    half_base = _CF_KNIFE_HEIGHT * math.tan(math.radians(35.0))
    cham = min(_CF_CHAMFER, t / 4.0)

    points = [(r_bore, floor)]               # bore meets the recess
    if tube_length > 0 and r_tube > r_bore:
        points += [(r_bore, -tube_length), (r_tube, -tube_length),
                   (r_tube, 0.0)]
    else:
        points += [(r_bore, 0.0)]
    points += [
        (r_od - cham, 0.0), (r_od, cham),     # back edge chamfer
        (r_od, t - cham), (r_od - cham, t),   # face edge chamfer
        (r_seat, t),                          # face in to the recess
        (r_seat, floor),                      # gasket seat wall
        (r_knife + half_base, floor),         # floor to the knife
        (r_knife, tip),                       # knife edge tip
        (r_knife - half_base, floor),         # back to the floor
    ]
    return [[round(x, 4), round(z, 4)] for x, z in points]


def cf_flange_solid(p, tube_length: float = 0.0,
                    name: str = "CF flange") -> CadNode:
    """The revolved (knife-edged) flange body without bolt holes."""
    revolve = CadNode("rotate_extrude", f"{name} revolve",
                      dict(angle=360.0, segments=128))
    revolve.add(CadNode("polygon", f"{name} profile", dict(
        x=0.0, y=0.0, points=cf_profile(p, tube_length))))
    return revolve


def cf_flange(p, name="CF flange", tube_length=0.0) -> CadNode:
    """A ConFlat flange with the true sealing geometry — recessed
    face, knife edge, gasket seat — and the bolt circle subtracted."""
    part = CadNode("difference", name)
    part.add(cf_flange_solid(p, tube_length, name))
    part.add(_bolt_holes(p, z=-1.0, height=p["thickness"] + 2.0))
    return part


def _kf_flange_solid(p, name="KF flange") -> CadNode:
    """The KF clamp head only (chamfered disc + taper to the tube OD),
    z = 0 at the sealing face, no tube and no bore."""
    solid = CadNode("union", name)
    solid.add(_cyl("Clamp face", p["flange_od"] / 2.0,
                   p["thickness"] * 0.6))
    solid.add(CadNode("cylinder", "Clamp taper", dict(
        x=0.0, y=0.0, z=p["thickness"] * 0.6,
        height=p["thickness"] * 0.4,
        radius_bottom=p["flange_od"] / 2.0,
        radius_top=p["tube_od"] / 2.0, segments=96, center=False)))
    return solid


def _kf_flange_head(p, name="KF flange") -> CadNode:
    """KF clamp head oriented for a fitting: the taper rises from the
    tube OD (z = 0, the inner/tube side) to the flange, then the flat
    sealing face sits on top (z = thickness) — so the seal faces
    *outward* at the end of the tube, like a CF flange does."""
    t = p["thickness"]
    solid = CadNode("union", name)
    solid.add(CadNode("cylinder", "Clamp taper", dict(
        x=0.0, y=0.0, z=0.0, height=t * 0.4,
        radius_bottom=p["tube_od"] / 2.0,
        radius_top=p["flange_od"] / 2.0, segments=96, center=False)))
    solid.add(_cyl("Clamp face", p["flange_od"] / 2.0, t * 0.6,
                   z=t * 0.4))
    return solid


def kf_flange(p, name="KF flange", tube_length=20.0) -> CadNode:
    """A KF flange: chamfered clamp disc + tube, bore subtracted."""
    solid = _kf_flange_solid(p, f"{name} solid")
    if tube_length > 0:
        solid.add(_cyl("Tube", p["tube_od"] / 2.0, tube_length,
                       z=p["thickness"]))
    part = CadNode("difference", name)
    part.add(solid)
    part.add(_cyl("Bore", p["bore"] / 2.0,
                  p["thickness"] + tube_length + 2.0, z=-1.0))
    return part


def kf_fitting(p, ports, name="KF fitting", port_length=40.0) -> CadNode:
    """A multi-port KF fitting (nipple / elbow / tee): one clamp-flanged
    tube per port, all bores meeting at the centre. KF has no bolts."""
    part = CadNode("difference", name)
    solid = CadNode("union", f"{name} body")
    part.add(solid)
    for port in ports:
        rx, ry, rz = _PORTS[port]
        frame = CadNode("rotate", f"Port {port}", dict(x=rx, y=ry, z=rz))
        frame.add(_cyl("Tube", p["tube_od"] / 2.0, port_length))
        lift = CadNode("translate", "Flange position", dict(
            x=0.0, y=0.0, z=port_length - p["thickness"]))
        lift.add(_kf_flange_head(p, f"Flange {port}"))
        frame.add(lift)
        solid.add(frame)
    for port in ports:
        rx, ry, rz = _PORTS[port]
        frame = CadNode("rotate", f"Bore {port}", dict(x=rx, y=ry, z=rz))
        frame.add(_cyl("Bore", p["bore"] / 2.0, port_length + 1.0,
                       z=-1.0))
        part.add(frame)
    return part


# ---------------------------------------------------------- fittings

def cf_fitting(p, ports, name="CF fitting",
               port_length=60.0, extra_solids=()) -> CadNode:
    """A multi-port CF fitting (nipple / tee / cross / valve body):
    one flanged tube per port direction, all bores meeting at the
    centre. *extra_solids* joins additional body parts (valve slabs,
    bonnets, ...) into the union before the bores are subtracted."""
    part = CadNode("difference", name)
    solid = CadNode("union", f"{name} body")
    part.add(solid)
    for extra in extra_solids:
        solid.add(extra)
    for port in ports:
        rx, ry, rz = _PORTS[port]
        frame = CadNode("rotate", f"Port {port}",
                        dict(x=rx, y=ry, z=rz))
        frame.add(_cyl("Tube", p["tube_od"] / 2.0, port_length))
        lift = CadNode("translate", "Flange position", dict(
            x=0.0, y=0.0, z=port_length - p["thickness"]))
        lift.add(cf_flange_solid(p, 0.0, f"Flange {port}"))
        frame.add(lift)
        solid.add(frame)
    for port in ports:
        rx, ry, rz = _PORTS[port]
        frame = CadNode("rotate", f"Bore {port}",
                        dict(x=rx, y=ry, z=rz))
        frame.add(_cyl("Bore", p["bore"] / 2.0, port_length + 1.0,
                       z=-1.0))
        part.add(frame)
    for port in ports:
        rx, ry, rz = _PORTS[port]
        frame = CadNode("rotate", f"Bolts {port}",
                        dict(x=rx, y=ry, z=rz))
        frame.add(_bolt_holes(p, z=port_length - p["thickness"] - 1.0,
                              height=p["thickness"] + 2.0))
        part.add(frame)
    return part


# --------------------------------------------------------------- valves

def _x_cylinder(name, radius, length, z=0.0, segments=96):
    """A cylinder along the X axis, centred, lifted to height *z*."""
    lift = CadNode("translate", f"{name} at height",
                   dict(x=0.0, y=0.0, z=z))
    frame = CadNode("rotate", f"{name} axis", dict(x=0.0, y=90.0,
                                                   z=0.0))
    frame.add(CadNode("cylinder", name, dict(
        x=0.0, y=0.0, z=0.0, height=length, radius_bottom=radius,
        radius_top=radius, segments=segments, center=True)))
    lift.add(frame)
    return lift


def gate_valve(p, name="Gate valve") -> CadNode:
    """A VAT-style gate valve: two knife-edge CF flanges on a thin
    slab body (short face-to-face), the teardrop bonnet housing the
    gate retracts into, and the actuator on top."""
    t = p["thickness"]
    half = max(1.6 * t, 14.0)                 # face-to-face = 2*half
    slab_w = 2.0 * (half - t) + 2.0           # between the flanges
    r_body = p["gasket_od"] / 2.0 + 6.0
    travel = p["bore"] + 10.0                 # gate retract height

    body = CadNode("hull", "Valve body (slab)")
    body.add(_x_cylinder("Body lower", r_body, slab_w))
    body.add(_x_cylinder("Bonnet housing", r_body * 0.5, slab_w,
                         z=travel))
    actuator = CadNode("union", "Actuator")
    actuator.add(_cyl("Bonnet flange", r_body * 0.5,
                      6.0, z=travel + r_body * 0.5 - 4.0))
    actuator.add(_cyl("Actuator stem", r_body * 0.16,
                      p["bore"] * 0.8, z=travel + r_body * 0.5))
    actuator.add(_cyl("Handwheel", r_body * 0.45, 5.0,
                      z=travel + r_body * 0.5 + p["bore"] * 0.8))
    return cf_fitting(p, ["+X", "-X"], name, half,
                      extra_solids=[body, actuator])


def angle_valve(p, name="Right-angle valve",
                port_length=None) -> CadNode:
    """A right-angle (90°) CF valve: inlet below, outlet to the side,
    spherical body, bonnet and handwheel on the vertical axis."""
    r_tube = p["tube_od"] / 2.0
    length = port_length or max(2.4 * p["thickness"],
                                r_tube * 2.2, 40.0)
    body = CadNode("sphere", "Valve body", dict(
        x=0.0, y=0.0, z=0.0, radius=r_tube * 1.45, segments=64))
    bonnet = CadNode("union", "Bonnet + handwheel")
    bonnet.add(CadNode("cylinder", "Bonnet", dict(
        x=0.0, y=0.0, z=r_tube * 0.6, height=r_tube * 2.0,
        radius_bottom=r_tube * 1.15, radius_top=r_tube * 0.85,
        segments=64, center=False)))
    bonnet.add(_cyl("Stem", r_tube * 0.22, r_tube * 1.4,
                    z=r_tube * 2.6))
    bonnet.add(_cyl("Handwheel", r_tube * 1.3, r_tube * 0.35,
                    z=r_tube * 4.0))
    return cf_fitting(p, ["-Z", "+X"], name, length,
                      extra_solids=[body, bonnet])


# ------------------------------------------------------------ turbo pump

def turbo_pump(inlet=None, exhaust=None, body_height=110.0,
               body_od=120.0) -> CadNode:
    """A simplified turbo pump shell: CF inlet flange on top of a
    cylindrical body, conical lower housing, KF exhaust port and a
    base collar."""
    inlet = inlet or CF_SIZES["CF100 (DN100)"]
    exhaust = exhaust or KF_SIZES["KF25 (DN25)"]
    part = CadNode("difference", "Turbo pump (simplified)")
    solid = CadNode("union", "Pump body")
    part.add(solid)

    # main body with the inlet flange on top
    solid.add(_cyl("Body", body_od / 2.0, body_height))
    solid.add(_cyl("Inlet flange", inlet["flange_od"] / 2.0,
                   inlet["thickness"], z=body_height))
    # conical lower housing + motor/electronics collar
    solid.add(CadNode("cylinder", "Lower cone", dict(
        x=0.0, y=0.0, z=-30.0, height=30.0,
        radius_bottom=body_od * 0.35, radius_top=body_od / 2.0,
        segments=96, center=False)))
    solid.add(_cyl("Base collar", body_od * 0.42, 16.0, z=-46.0))
    # exhaust: KF tube + clamp flange sticking out in +X near the base
    exhaust_frame = CadNode("rotate", "Exhaust port",
                            dict(x=0.0, y=90.0, z=0.0))
    exhaust_len = body_od / 2.0 + 28.0
    exhaust_frame.add(CadNode("translate", "At base height",
                              dict(x=0.0, y=0.0, z=0.0)))
    tube = _cyl("Exhaust tube", exhaust["tube_od"] / 2.0, exhaust_len)
    tube.params["y"] = 0.0
    exhaust_frame.children[0].add(tube)
    exhaust_frame.children[0].add(
        _cyl("Exhaust flange", exhaust["flange_od"] / 2.0,
             exhaust["thickness"], z=exhaust_len))
    exhaust_lift = CadNode("translate", "Exhaust",
                           dict(x=0.0, y=0.0, z=-20.0))
    exhaust_lift.add(exhaust_frame)
    solid.add(exhaust_lift)

    # inlet bore with a simple rotor hub hinted inside
    part.add(_cyl("Inlet bore", inlet["bore"] / 2.0,
                  inlet["thickness"] + 42.0,
                  z=body_height - 40.0))
    part.add(_bolt_holes(inlet, z=body_height - 1.0,
                         height=inlet["thickness"] + 2.0))
    # exhaust bore
    ex_bore_frame = CadNode("translate", "Exhaust bore lift",
                            dict(x=0.0, y=0.0, z=-20.0))
    ex_rot = CadNode("rotate", "Exhaust bore", dict(x=0.0, y=90.0,
                                                    z=0.0))
    ex_rot.add(_cyl("Bore", exhaust["bore"] / 2.0, exhaust_len + 2.0,
                    z=body_od / 4.0))
    ex_bore_frame.add(ex_rot)
    part.add(ex_bore_frame)

    hub = CadNode("cylinder", "Rotor hub", dict(
        x=0.0, y=0.0, z=body_height - 38.0, height=30.0,
        radius_bottom=inlet["bore"] * 0.18,
        radius_top=inlet["bore"] * 0.10, segments=48, center=False))
    result = CadNode("union", "Turbo pump")
    result.add(part)
    result.add(hub)
    return result


# ------------------------------------------------------------ feedthrough

def feedthrough(p, kind="cf", pins=4, pin_d=2.0, stub=18.0) -> CadNode:
    """An electrical feedthrough: a blank CF/KF flange carrying a ring
    of conductor pins that pass straight through, protruding *stub* mm
    on each side. Monochrome so the CF bolt circle still cuts cleanly."""
    t = p["thickness"]
    part = CadNode("difference", f"{kind.upper()} feedthrough")
    body = CadNode("union", "Feedthrough body")
    part.add(body)
    if kind == "cf":
        body.add(cf_flange_solid(dict(p, bore=0.0), 0.0, "Flange"))
        r_ring = max(p["gasket_od"] / 2.0 - 6.0, pin_d * 2.0)
    else:
        body.add(_kf_flange_solid(p, "Flange"))
        r_ring = max(p["tube_od"] / 2.0 - 4.0, pin_d * 2.0)
    # ceramic insulator boss on the sealing face
    body.add(_cyl("Insulator boss", r_ring + pin_d * 1.6, t * 0.5, z=t))
    # conductor pins on a ring, through the flange
    pins = max(int(pins), 1)
    step = 360.0 / pins
    loop = CadNode("for_loop", "Pins", dict(
        variable="a", start=0.0, end=360.0 - step / 2.0, step=step))
    rot = CadNode("rotate", "Pin angle", dict(x=0.0, y=0.0, z="a"))
    rot.add(_cyl("Pin", pin_d / 2.0, stub * 2.0 + t, z=-stub,
                 x=r_ring, segments=20))
    loop.add(rot)
    body.add(loop)
    if kind == "cf":
        part.add(_bolt_holes(p, z=-1.0, height=t + 2.0))
    return part


# -------------------------------------------------- hemispherical analyser

def _dome_profile(radius, wall=None, n=48):
    """(r, z) cross-section of a hemispherical dome (z >= 0), revolved
    360° to a real hemisphere solid — or a shell when *wall* is given.
    Built from arcs, not a boolean, so the built-in preview shows it."""
    arc = [(radius * math.cos(math.radians(90.0 * i / n)),
            radius * math.sin(math.radians(90.0 * i / n)))
           for i in range(n + 1)]                # (R,0) up to (0,R)
    if not wall:
        pts = [(0.0, 0.0)] + arc                 # solid quarter disc
    else:
        ri = max(radius - wall, 0.05)
        inner = [(ri * math.cos(math.radians(90.0 * i / n)),
                  ri * math.sin(math.radians(90.0 * i / n)))
                 for i in range(n + 1)]
        pts = arc + list(reversed(inner))        # shell between the arcs
    return [[round(x, 4), round(z, 4)] for x, z in pts]


def _hemisphere(name, radius, wall=None, segments=128) -> CadNode:
    """A hemispherical dome (or shell) as a revolved arc profile."""
    revolve = CadNode("rotate_extrude", name,
                      dict(angle=360.0, segments=segments))
    revolve.add(CadNode("polygon", f"{name} profile",
                        dict(x=0.0, y=0.0,
                             points=_dome_profile(radius, wall))))
    return revolve


def _bolt_ring(count, circle_r, head_r, head_h, z,
               name="Bolt ring") -> CadNode:
    """A for-loop of hex bolt heads (6-sided prisms) around a circle."""
    count = max(int(count), 1)
    step = 360.0 / count
    loop = CadNode("for_loop", name, dict(
        variable="a", start=0.0, end=360.0 - step / 2, step=step))
    rot = CadNode("rotate", "Around axis", dict(x=0.0, y=0.0, z="a"))
    rot.add(_cyl("Bolt head", head_r, head_h, z=z, x=circle_r,
                 segments=6))
    loop.add(rot)
    return loop


def _plain_flange(od, thickness, bore, bolts, bolt_circle, bolt_hole,
                  z, name="Flange") -> CadNode:
    """A simple bolted flange disc: a plate with a central bore and a
    ring of clearance holes — the plain cousin of cf_flange, for the
    analyser's lens and side-port mounts."""
    part = CadNode("difference", name)
    part.add(_cyl(f"{name} disc", od / 2.0, thickness, z=z))
    if bore > 0:
        part.add(_cyl(f"{name} bore", bore / 2.0, thickness + 2.0,
                      z=z - 1.0))
    count = max(int(bolts), 1)
    step = 360.0 / count
    loop = CadNode("for_loop", f"{name} holes", dict(
        variable="a", start=0.0, end=360.0 - step / 2, step=step))
    rot = CadNode("rotate", "Around axis", dict(x=0.0, y=0.0, z="a"))
    rot.add(_cyl("Bolt hole", bolt_hole / 2.0, thickness + 2.0,
                 z=z - 1.0, x=bolt_circle / 2.0, segments=18))
    loop.add(rot)
    part.add(loop)
    return part


def _entrance_lens(R, mount, name="Entrance lens") -> CadNode:
    """The electron transfer lens, built along local +Z from the
    analyser end (z = 0, a bolted flange) out to the tapered entrance
    nozzle at the sample end — a long, stepped column."""
    g = CadNode("union", name)
    z = 0.0
    lf_od = mount["flange_od"] * 0.55
    lf_t = R * 0.06
    g.add(_plain_flange(lf_od, lf_t, R * 0.22, 8, lf_od * 0.82,
                        mount["bolt_hole"], z, "Lens flange"))
    z += lf_t
    neck = R * 0.14
    g.add(_cyl("Lens neck", R * 0.22, neck, z=z))
    z += neck
    for i, (rf, hf) in enumerate([(0.16, 0.34), (0.12, 0.34)]):
        h = R * hf
        g.add(_cyl(f"Lens tube {i + 1}", R * rf, h, z=z))
        z += h
    cone = R * 0.26
    g.add(CadNode("cylinder", "Entrance nozzle", dict(
        x=0.0, y=0.0, z=z, height=cone,
        radius_bottom=R * 0.12, radius_top=R * 0.035,
        segments=48, center=False)))
    return g


def _detector(R, mount, name="Detector") -> CadNode:
    """The exit detector housing (channeltron / MCP), built along local
    +Z from the analyser end — a short, fat housing with a connector and
    an end cap: the counterpart on the opposite side to the lens."""
    g = CadNode("union", name)
    z = 0.0
    df_od = mount["flange_od"] * 0.50
    df_t = R * 0.06
    g.add(_plain_flange(df_od, df_t, R * 0.20, 8, df_od * 0.82,
                        mount["bolt_hole"], z, "Detector flange"))
    z += df_t
    hz = R * 0.42
    g.add(_cyl("MCP housing", R * 0.24, hz, z=z))
    z += hz
    cz = R * 0.16
    g.add(_cyl("Connector", R * 0.12, cz, z=z))
    z += cz
    g.add(_cyl("End cap", R * 0.15, R * 0.05, z=z))
    return g


def hemispherical_analyser(r_out=150.0, r_in=75.0,
                           mount=None) -> CadNode:
    """A hemispherical electron energy analyser (HSA): a polished dome
    closed by a large **equatorial bolt flange** (the signature bolted
    ring), a concentric inner hemisphere and a top vent port. As in a
    real analyser the **entrance lens** and the **detector** sit on
    *opposite* sides of the base — the long stepped lens angles out one
    side to its entrance nozzle at the sample, the shorter detector
    housing out the other — with a small pumping port between them."""
    mount = mount or CF_SIZES["CF160 (DN160)"]
    R = float(r_out)
    wall = max(R * 0.05, 4.0)
    part = CadNode("union", "Hemispherical analyser")

    # --- equatorial mounting flange: the defining bolted ring --------
    plate_t = R * 0.10
    plate_r = R * 1.14
    bc_r = R * 1.04                        # bolt circle, in the overhang
    nbolts = 36
    head_r, head_h = R * 0.035, R * 0.045
    plate = CadNode("difference", "Equatorial flange")
    plate.add(_cyl("Flange ring", plate_r, plate_t, z=-plate_t))
    plate.add(_cyl("Aperture", r_in * 0.85, plate_t + 2.0,
                   z=-plate_t - 1.0))
    step = 360.0 / nbolts
    holes = CadNode("for_loop", "Flange holes", dict(
        variable="a", start=0.0, end=360.0 - step / 2, step=step))
    hrot = CadNode("rotate", "Around axis", dict(x=0.0, y=0.0, z="a"))
    hrot.add(_cyl("Bolt hole", head_r * 0.55, plate_t + 2.0,
                  z=-plate_t - 1.0, x=bc_r, segments=14))
    holes.add(hrot)
    plate.add(holes)
    part.add(plate)
    part.add(_bolt_ring(nbolts, bc_r, head_r, head_h, z=0.0,
                        name="Bolt heads"))
    part.add(_bolt_ring(nbolts, bc_r, head_r * 0.95, head_h,
                        z=-plate_t - head_h, name="Nuts"))

    # --- domes: outer shell + concentric inner shell -----------------
    part.add(_hemisphere("Outer dome", R, wall=wall))
    if r_in < R - wall - 2.0:
        part.add(_hemisphere("Inner dome", r_in,
                             wall=max(wall * 0.7, 3.0)))

    # --- small vent port on top of the dome --------------------------
    top = CadNode("union", "Top port")
    top.add(_cyl("Vent tube", R * 0.06, R * 0.18, z=R - wall))
    top.add(_cyl("Vent cap", R * 0.09, R * 0.03,
                 z=R - wall + R * 0.18))
    part.add(top)

    # --- entrance lens: angled off ONE side of the base --------------
    lens_pos = CadNode("translate", "Lens mount",
                       dict(x=R * 0.12, y=0.0, z=-plate_t))
    lens_tilt = CadNode("rotate", "Lens angle", dict(x=0.0, y=135.0,
                                                     z=0.0))
    lens_tilt.add(_entrance_lens(R, mount))
    lens_pos.add(lens_tilt)
    part.add(lens_pos)

    # --- detector: angled off the OPPOSITE side ----------------------
    det_pos = CadNode("translate", "Detector mount",
                      dict(x=-R * 0.12, y=0.0, z=-plate_t))
    det_tilt = CadNode("rotate", "Detector angle", dict(x=0.0, y=225.0,
                                                        z=0.0))
    det_tilt.add(_detector(R, mount))
    det_pos.add(det_tilt)
    part.add(det_pos)

    # --- a small pumping port on the base, between the two -----------
    pump_pos = CadNode("translate", "Pump port",
                       dict(x=0.0, y=R * 0.5, z=-plate_t))
    pump_tilt = CadNode("rotate", "Pump angle", dict(x=135.0, y=0.0,
                                                     z=0.0))
    pump_tilt.add(_cyl("Pump tube", R * 0.11, R * 0.40))
    pcap = CadNode("translate", "Pump flange pos",
                   dict(x=0.0, y=0.0, z=R * 0.40))
    pcap.add(_plain_flange(R * 0.32, R * 0.05, R * 0.16, 6, R * 0.25,
                           mount["bolt_hole"] * 0.8, 0.0, "Pump flange"))
    pump_tilt.add(pcap)
    pump_pos.add(pump_tilt)
    part.add(pump_pos)

    return part


# -------------------------------------------------- XYZ(R1) manipulator

def _lift(node, z):
    t = CadNode("translate", "Lift", dict(x=0.0, y=0.0, z=z))
    t.add(node)
    return t


def bellows(r_in, amp, length, convolutions, name="Bellows") -> CadNode:
    """An edge-welded bellows as a revolved sawtooth ring (no boolean):
    the outer surface ripples between a valley and a ridge radius over a
    straight bore. *length* is the Z travel — the point of the size
    table asking for different bellows lengths."""
    r_out = r_in + amp
    r_mid = r_in + amp * 0.12                 # deep valleys → clear ribs
    convolutions = max(int(convolutions), 2)
    step = length / convolutions
    outer = []
    for i in range(convolutions + 1):
        outer.append((r_mid, i * step))
        if i < convolutions:
            outer.append((r_out, i * step + step / 2.0))
    prof = outer + [(r_in, length), (r_in, 0.0)]
    rev = CadNode("rotate_extrude", name, dict(angle=360.0, segments=96))
    rev.add(CadNode("polygon", f"{name} profile", dict(
        x=0.0, y=0.0,
        points=[[round(r, 3), round(z, 3)] for r, z in prof])))
    return rev


def _micrometer(name, length, radius) -> CadNode:
    """A micrometer drive along +X: barrel, thimble, ratchet cap."""
    g = CadNode("rotate", f"{name} axis", dict(x=0.0, y=90.0, z=0.0))
    g.add(_cyl("Barrel", radius, length * 0.6, segments=24))
    g.add(_cyl("Thimble", radius * 1.3, length * 0.4, z=length * 0.6,
               segments=24))
    g.add(_cyl("Ratchet", radius * 0.7, length * 0.18, z=length,
               segments=20))
    return g


def manipulator(z_travel=50.0, mount=None, xy_travel=25.0) -> CadNode:
    """A UHV XYZ(R1) sample manipulator: a CF mount flange, an
    edge-welded bellows of the chosen Z travel, an XY micrometer stage
    on a top plate, a Z column with a rotary (R1) drive on top, and the
    sample rod running down the centre through the bore."""
    mount = mount or CF_SIZES["CF40 (DN40)"]
    t = mount["thickness"]
    bore_r = max(mount["bore"] / 2.0, 6.0)
    flange_r = mount["flange_od"] / 2.0
    part = CadNode("union", "XYZ manipulator")
    part.add(cf_flange(mount, "Mount flange", tube_length=0.0))
    # bellows (the Z travel) rising from the flange face
    bel_r = bore_r + 3.0
    part.add(_lift(bellows(bel_r, bel_r * 0.7, z_travel,
                           max(z_travel / 10.0, 4)), t))
    top_z = t + z_travel
    plate_r = flange_r * 0.85
    part.add(_lift(_cyl("Stage plate", plate_r, 14.0, segments=64),
                   top_z))
    stage_z = top_z + 14.0
    block = 0.9 * plate_r
    part.add(_lift(CadNode("cube", "XY stage", dict(
        x=-block / 2.0, y=-block / 2.0, z=0.0, width=block, depth=block,
        height=block * 0.7, center=False)), stage_z))
    mlen = xy_travel + flange_r * 0.7
    part.add(_lift(_micrometer("X drive", mlen, bel_r * 0.5),
                   stage_z + block * 0.35))
    ydrv = CadNode("rotate", "Y drive turn", dict(x=0.0, y=0.0, z=90.0))
    ydrv.add(_micrometer("Y drive", mlen, bel_r * 0.5))
    part.add(_lift(ydrv, stage_z + block * 0.35))
    # Z column + rotary (R1) drive on top
    z2 = stage_z + block * 0.7
    col_h = z_travel * 0.5 + 40.0
    part.add(_lift(_cyl("Z column", plate_r * 0.4, col_h, segments=32),
                   z2))
    z_top = z2 + col_h
    part.add(_lift(_cyl("Rotary drive (R1)", plate_r * 0.7, 16.0,
                        segments=48), z_top))
    part.add(_lift(_cyl("Rotary knob", plate_r * 0.5, 24.0,
                        r2=plate_r * 0.55, segments=32), z_top + 16.0))
    # sample rod down the centre, through the bore into the chamber
    rod_bottom = -(z_travel * 0.4 + 90.0)
    part.add(_cyl("Sample rod", bore_r * 0.35, z2 - rod_bottom,
                  z=rod_bottom, segments=24))
    return part


# ----------------------------------------------------- backing pumps

_PUMP_BODY = "#8a9099"       # cast body
_PUMP_MOTOR = "#3a3f45"      # motor housing
_PUMP_OIL = "#d9a441"        # oil sight glass
_PUMP_TRIM = "#5f646c"


def _colour(node, hexcol, name="Colour"):
    c = CadNode("color", name, dict(color=hexcol, alpha=1.0))
    c.add(node)
    return c


def _horiz_cyl(name, radius, length, x=0.0, z=0.0, r2=None,
               segments=64, color=None):
    """A cylinder lying along +X, its -X end at *x*, axis at height *z*."""
    lift = CadNode("translate", f"{name} pos", dict(x=x, y=0.0, z=z))
    rot = CadNode("rotate", f"{name} axis", dict(x=0.0, y=90.0, z=0.0))
    rot.add(CadNode("cylinder", name, dict(
        x=0.0, y=0.0, z=0.0, height=length, radius_bottom=radius,
        radius_top=radius if r2 is None else r2, segments=segments,
        center=False)))
    lift.add(rot)
    return _colour(lift, color, name) if color else lift


def _kf_port(inlet, x, z, length, color=None):
    """A KF hose port pointing +Z: a tube capped by a clamp disc."""
    grp = CadNode("union", "KF port")
    grp.add(_cyl("Port tube", inlet["tube_od"] / 2.0, length, x=x, z=z,
                 segments=32))
    grp.add(_cyl("Port flange", inlet["flange_od"] / 2.0,
                 inlet["thickness"], x=x, z=z + length, segments=48))
    return _colour(grp, color, "KF port") if color else grp


def rotary_pump(inlet=None, body_l=200.0, body_d=100.0,
                motor_l=150.0, motor_d=115.0) -> CadNode:
    """A two-stage oil-sealed rotary vane (roughing) pump: motor,
    oil-box body, sight glass, KF inlet on top, oil-mist-filter exhaust
    and a carry handle, on feet."""
    foot_h = 18.0
    zc = foot_h + body_d / 2.0                # body axis height
    part = CadNode("union", "Rotary vane pump")
    # base rails + feet
    part.add(_colour(CadNode("cube", "Base", dict(
        x=-motor_l - 10.0, y=-body_d / 2.0 - 6.0, z=0.0,
        width=motor_l + body_l + 30.0, depth=body_d + 12.0,
        height=foot_h, center=False)), _PUMP_TRIM, "Base"))
    # motor (with fan cowl) then the oil-box body
    part.add(_horiz_cyl("Motor", motor_d / 2.0, motor_l, x=-motor_l,
                        z=zc, color=_PUMP_MOTOR))
    part.add(_horiz_cyl("Fan cowl", motor_d / 2.0 + 6.0, 16.0,
                        x=-motor_l - 16.0, z=zc, color=_PUMP_TRIM))
    part.add(_horiz_cyl("Oil-box body", body_d / 2.0, body_l, x=0.0,
                        z=zc, color=_PUMP_BODY))
    part.add(_horiz_cyl("End cap", body_d / 2.0 + 4.0, 10.0,
                        x=body_l - 10.0, z=zc, color=_PUMP_TRIM))
    # oil sight glass: a short amber window on the +Y face
    sight = CadNode("rotate", "Sight axis", dict(x=-90.0, y=0.0, z=0.0))
    sight.add(_cyl("Sight glass", body_d * 0.14, 16.0, segments=24))
    part.add(_colour(_lift_xy(sight, body_l * 0.55, body_d / 2.0 - 8.0,
                              zc), _PUMP_OIL, "Sight glass"))
    # KF inlet up near the motor end; oil-mist exhaust canister at far end
    part.add(_kf_port(inlet or KF_SIZES["KF25 (DN25)"], body_l * 0.28,
                      zc + body_d / 2.0, body_d * 0.35, _PUMP_BODY))
    part.add(_colour(_cyl("Mist filter", body_d * 0.24, body_d * 0.9,
                          x=body_l * 0.8, z=zc + body_d / 2.0,
                          segments=32), _PUMP_TRIM, "Mist filter"))
    # carry handle (inverted U) over the top
    hz = zc + body_d / 2.0 + body_d * 0.5
    part.add(_colour(_horiz_cyl("Handle bar", 8.0, body_l * 0.6,
                                x=body_l * 0.2, z=hz, segments=20),
                     _PUMP_MOTOR, "Handle"))
    for hx in (body_l * 0.2, body_l * 0.8):
        part.add(_colour(_cyl("Handle post", 8.0, body_d * 0.5,
                              x=hx, z=zc + body_d / 2.0, segments=16),
                         _PUMP_MOTOR, "Handle post"))
    return part


def scroll_pump(inlet=None, body_l=200.0, body_d=130.0,
                motor_l=160.0) -> CadNode:
    """A dry scroll (backing) pump: finned scroll housing + motor with
    a fan cowl, KF inlet on top and a side exhaust — no oil box."""
    foot_h = 18.0
    zc = foot_h + body_d / 2.0
    part = CadNode("union", "Scroll pump")
    part.add(_colour(CadNode("cube", "Base", dict(
        x=-motor_l - 10.0, y=-body_d / 2.0 - 6.0, z=0.0,
        width=motor_l + body_l + 30.0, depth=body_d + 12.0,
        height=foot_h, center=False)), _PUMP_TRIM, "Base"))
    part.add(_horiz_cyl("Motor", body_d * 0.42, motor_l, x=-motor_l,
                        z=zc, color=_PUMP_MOTOR))
    part.add(_horiz_cyl("Fan cowl", body_d * 0.42 + 6.0, 16.0,
                        x=-motor_l - 16.0, z=zc, color=_PUMP_TRIM))
    part.add(_horiz_cyl("Scroll housing", body_d / 2.0, body_l, x=0.0,
                        z=zc, color=_PUMP_BODY))
    # cooling fins around the housing (the dry-pump signature)
    nfins = max(int(body_l / 14.0), 3)
    fins = CadNode("for_loop", "Cooling fins", dict(
        variable="i", start=0.0, end=float(nfins - 1), step=1.0))
    fins.add(_horiz_cyl("Fin", body_d / 2.0 + 7.0, 3.0,
                        x=f"6 + i*{body_l / nfins}", z=zc, segments=48))
    part.add(_colour(fins, _PUMP_TRIM, "Cooling fins"))
    part.add(_horiz_cyl("End cap", body_d / 2.0 + 4.0, 10.0,
                        x=body_l - 10.0, z=zc, color=_PUMP_TRIM))
    # KF inlet up, exhaust out the far end
    part.add(_kf_port(inlet or KF_SIZES["KF40 (DN40)"], body_l * 0.35,
                      zc + body_d / 2.0, body_d * 0.3, _PUMP_BODY))
    part.add(_horiz_cyl("Exhaust", body_d * 0.12, body_d * 0.5,
                        x=body_l, z=zc, color=_PUMP_TRIM))
    return part


def _lift_xy(node, x, y, z):
    t = CadNode("translate", "Place", dict(x=x, y=y, z=z))
    t.add(node)
    return t


# ----------------------------------------------------------------- parts

#: hemispherical analyser classes (mean radius / mount flange).
ANALYSER_SIZES = {
    "R150 (CF160 mount)": dict(r_out=150.0, r_in=75.0,
                               mount="CF160 (DN160)"),
    "R100 (CF100 mount)": dict(r_out=100.0, r_in=50.0,
                               mount="CF100 (DN100)"),
}

#: rotary vane (roughing) pump classes.
ROTARY_SIZES = {
    "Small (KF16)": dict(inlet="KF16 (DN16)", body_l=160.0,
                         body_d=80.0, motor_l=120.0, motor_d=95.0),
    "Medium (KF25)": dict(inlet="KF25 (DN25)", body_l=200.0,
                          body_d=100.0, motor_l=150.0, motor_d=115.0),
}
#: dry scroll (backing) pump classes.
SCROLL_SIZES = {
    "Small (KF25)": dict(inlet="KF25 (DN25)", body_l=180.0,
                         body_d=110.0, motor_l=140.0),
    "Medium (KF40)": dict(inlet="KF40 (DN40)", body_l=230.0,
                          body_d=140.0, motor_l=170.0),
}

#: XYZ(R1) manipulator classes — the size is the bellows Z travel.
MANIP_SIZES = {
    "Z25 (CF40)": dict(z_travel=25.0, xy_travel=12.5,
                       mount="CF40 (DN40)"),
    "Z50 (CF40)": dict(z_travel=50.0, xy_travel=25.0,
                       mount="CF40 (DN40)"),
    "Z100 (CF63)": dict(z_travel=100.0, xy_travel=25.0,
                        mount="CF63 (DN63)"),
    "Z150 (CF63)": dict(z_travel=150.0, xy_travel=25.0,
                        mount="CF63 (DN63)"),
    "Z300 (CF63)": dict(z_travel=300.0, xy_travel=25.0,
                        mount="CF63 (DN63)"),
}

#: editable dimensions per family.
_CF_FIELDS = [("flange_od", "Flange OD"), ("thickness", "Thickness"),
              ("bolt_circle", "Bolt circle Ø"), ("bolts", "Bolt count"),
              ("bolt_hole", "Bolt hole Ø"), ("bore", "Bore Ø"),
              ("tube_od", "Tube OD"), ("gasket_od", "Gasket OD"),
              ("port_length", "Port length")]
_KF_FIELDS = [("flange_od", "Flange OD"), ("thickness", "Thickness"),
              ("bore", "Bore Ø"), ("tube_od", "Tube OD"),
              ("port_length", "Tube length")]
_BOLT_FIELDS = [("d", "Thread Ø"), ("pitch", "Pitch"),
                ("length", "Length"), ("af", "Across flats"),
                ("head_h", "Head height")]
_SCREW_FIELDS = [("d", "Thread Ø"), ("pitch", "Pitch"),
                 ("length", "Length"), ("socket", "Hex key size")]
_NUT_FIELDS = [("d", "Thread Ø"), ("pitch", "Pitch"),
               ("af", "Across flats"), ("nut_h", "Thickness")]

_VAC = "Vacuum"
_FASTENERS = "Fasteners"

#: part id -> label, category, size table, editable fields (and an
#: optional `build` callable(dims)->CadNode for parts from other
#: modules). Ordering is the display order within each category.
PARTS = {
    "cf_flange": dict(label="CF flange (knife edge, tube stub)",
                      category=_VAC, sizes=CF_SIZES, fields=_CF_FIELDS),
    "cf_blank": dict(label="CF blank flange (knife edge)",
                     category=_VAC, sizes=CF_SIZES, fields=_CF_FIELDS),
    "cf_nipple": dict(label="CF nipple (straight tube)",
                      category=_VAC, sizes=CF_SIZES, fields=_CF_FIELDS),
    "cf_elbow": dict(label="CF elbow (90°, 2 ports)",
                     category=_VAC, sizes=CF_SIZES, fields=_CF_FIELDS),
    "cf_tee": dict(label="CF tee (3 ports)", category=_VAC,
                   sizes=CF_SIZES, fields=_CF_FIELDS),
    "cf_cross": dict(label="CF cross (4 ports)", category=_VAC,
                     sizes=CF_SIZES, fields=_CF_FIELDS),
    "cf_feedthrough": dict(label="CF electrical feedthrough",
                           category=_VAC, sizes=CF_SIZES,
                           fields=_CF_FIELDS),
    "kf_flange": dict(label="KF flange (with tube)", category=_VAC,
                      sizes=KF_SIZES, fields=_KF_FIELDS),
    "kf_nipple": dict(label="KF nipple (straight tube)", category=_VAC,
                      sizes=KF_SIZES, fields=_KF_FIELDS),
    "kf_elbow": dict(label="KF elbow (90°, 2 ports)", category=_VAC,
                     sizes=KF_SIZES, fields=_KF_FIELDS),
    "kf_tee": dict(label="KF tee (3 ports)", category=_VAC,
                   sizes=KF_SIZES, fields=_KF_FIELDS),
    "kf_feedthrough": dict(label="KF electrical feedthrough",
                           category=_VAC, sizes=KF_SIZES,
                           fields=_KF_FIELDS),
    "valve_angle": dict(label="Right-angle valve (CF)", category=_VAC,
                        sizes=CF_SIZES, fields=_CF_FIELDS),
    "valve_gate": dict(label="Gate valve (CF, VAT style)",
                       category=_VAC, sizes=CF_SIZES, fields=_CF_FIELDS),
    "turbo": dict(label="Turbo pump (simplified shell)", category=_VAC,
                  sizes=TURBO_SIZES,
                  fields=[("body_od", "Body OD"),
                          ("body_height", "Body height")]),
    "pump_rotary": dict(label="Rotary vane pump (roughing)",
                        category=_VAC, sizes=ROTARY_SIZES,
                        fields=[("body_l", "Body length"),
                                ("body_d", "Body Ø"),
                                ("motor_l", "Motor length"),
                                ("motor_d", "Motor Ø")]),
    "pump_scroll": dict(label="Scroll pump (dry backing)",
                        category=_VAC, sizes=SCROLL_SIZES,
                        fields=[("body_l", "Body length"),
                                ("body_d", "Body Ø"),
                                ("motor_l", "Motor length")]),
    "analyser_hsa": dict(label="Hemispherical analyser (HSA)",
                         category=_VAC, sizes=ANALYSER_SIZES,
                         fields=[("r_out", "Outer radius"),
                                 ("r_in", "Inner radius")]),
    "manipulator": dict(label="XYZ(R1) manipulator", category=_VAC,
                        sizes=MANIP_SIZES,
                        fields=[("z_travel", "Z travel (bellows)"),
                                ("xy_travel", "XY travel")]),
    "bolt_hex": dict(label="Hex bolt, threaded (DIN 933)",
                     category=_FASTENERS, sizes=BOLT_SIZES,
                     fields=_BOLT_FIELDS),
    "bolt_socket": dict(label="Socket head cap screw (DIN 912)",
                        category=_FASTENERS, sizes=BOLT_SIZES,
                        fields=_SCREW_FIELDS),
    "nut_hex": dict(label="Hex nut, threaded (DIN 934)",
                    category=_FASTENERS, sizes=BOLT_SIZES,
                    fields=_NUT_FIELDS),
}

# parts contributed by sibling modules (chemistry, room & furniture);
# each entry carries its own `build` callable, dispatched by build_part.
from . import library_chem, library_room       # noqa: E402
PARTS.update(library_chem.PARTS)
PARTS.update(library_room.PARTS)


def build_part(part_id: str, dims: dict) -> CadNode:
    """Build the requested part from (possibly customised) *dims*."""
    spec = PARTS.get(part_id)
    if spec and callable(spec.get("build")):     # parts from other modules
        return spec["build"](dict(dims))
    p = dict(dims)
    length = p.pop("port_length", 60.0)
    if part_id in ("bolt_hex", "bolt_socket", "nut_hex"):
        defaults = dict(BOLT_SIZES["M6"])
        defaults.update(p)
        p = defaults
    if part_id == "cf_flange":
        return cf_flange(p, tube_length=max(length - p["thickness"],
                                            0.0))
    if part_id == "cf_blank":
        blank = dict(p)
        blank["bore"] = 0.0
        return cf_flange(blank, "CF blank flange", tube_length=0.0)
    if part_id == "cf_nipple":
        return cf_fitting(p, ["+Z", "-Z"], "CF nipple", length)
    if part_id == "cf_tee":
        return cf_fitting(p, ["+X", "-X", "+Z"], "CF tee", length)
    if part_id == "cf_cross":
        return cf_fitting(p, ["+X", "-X", "+Z", "-Z"], "CF cross",
                          length)
    if part_id == "cf_elbow":
        return cf_fitting(p, ["+Z", "+X"], "CF elbow", length)
    if part_id == "cf_feedthrough":
        return feedthrough(p, "cf")
    if part_id == "kf_flange":
        return kf_flange(p, tube_length=max(length - p["thickness"],
                                            0.0))
    if part_id == "kf_nipple":
        return kf_fitting(p, ["+Z", "-Z"], "KF nipple", length)
    if part_id == "kf_elbow":
        return kf_fitting(p, ["+Z", "+X"], "KF elbow", length)
    if part_id == "kf_tee":
        return kf_fitting(p, ["+X", "-X", "+Z"], "KF tee", length)
    if part_id == "kf_feedthrough":
        return feedthrough(p, "kf")
    if part_id == "analyser_hsa":
        entry = ANALYSER_SIZES.get(p.pop("_size", ""),
                                   ANALYSER_SIZES["R150 (CF160 mount)"])
        return hemispherical_analyser(
            r_out=p.get("r_out", entry["r_out"]),
            r_in=p.get("r_in", entry["r_in"]),
            mount=CF_SIZES[entry["mount"]])
    if part_id == "manipulator":
        entry = MANIP_SIZES.get(p.pop("_size", ""),
                                MANIP_SIZES["Z50 (CF40)"])
        return manipulator(
            z_travel=p.get("z_travel", entry["z_travel"]),
            xy_travel=p.get("xy_travel", entry["xy_travel"]),
            mount=CF_SIZES[entry["mount"]])
    if part_id == "pump_rotary":
        entry = ROTARY_SIZES.get(p.pop("_size", ""),
                                 ROTARY_SIZES["Medium (KF25)"])
        return rotary_pump(
            inlet=KF_SIZES[entry["inlet"]],
            body_l=p.get("body_l", entry["body_l"]),
            body_d=p.get("body_d", entry["body_d"]),
            motor_l=p.get("motor_l", entry["motor_l"]),
            motor_d=p.get("motor_d", entry["motor_d"]))
    if part_id == "pump_scroll":
        entry = SCROLL_SIZES.get(p.pop("_size", ""),
                                 SCROLL_SIZES["Medium (KF40)"])
        return scroll_pump(
            inlet=KF_SIZES[entry["inlet"]],
            body_l=p.get("body_l", entry["body_l"]),
            body_d=p.get("body_d", entry["body_d"]),
            motor_l=p.get("motor_l", entry["motor_l"]))
    if part_id == "valve_angle":
        return angle_valve(p, port_length=length)
    if part_id == "valve_gate":
        return gate_valve(p)
    if part_id == "bolt_hex":
        return hex_bolt(p, p["length"])
    if part_id == "bolt_socket":
        return socket_screw(p, p["length"])
    if part_id == "nut_hex":
        return hex_nut(p)
    if part_id == "turbo":
        entry = TURBO_SIZES.get(p.pop("_size", ""),
                                TURBO_SIZES["DN100 CF (~300 l/s)"])
        return turbo_pump(
            inlet=CF_SIZES[entry["inlet"]],
            exhaust=KF_SIZES[entry["exhaust"]],
            body_od=p.get("body_od", entry["body_od"]),
            body_height=p.get("body_height", entry["body_height"]))
    raise ValueError(f"unknown part: {part_id}")


def default_part(part_id: str) -> CadNode:
    """Build a part at its default size — the same choice the dialog
    pre-selects — for one-click insertion from the Library menu."""
    spec = PARTS[part_id]
    sizes = spec.get("sizes") or {}
    dims, size_key = {}, ""
    if sizes:
        keys = list(sizes)
        size_key = keys[1] if len(keys) > 1 else keys[0]
        dims = dict(sizes[size_key])
        dims["_size"] = size_key
    node = build_part(part_id, dims)
    label = size_key.split(" ")[0] if size_key else ""
    if label and not node.name.startswith(label):
        node.name = f"{label} {node.name}"
    return node


# ---------------------------------------------------------------- dialog

class PartLibraryDialog(QDialog):
    """Insert > Part Library: pick a part, a standard size, tweak the
    dimensions, insert into the document. Non-modal — it stays open
    while you keep working in the main window."""

    part_inserted = pyqtSignal(object)        # the inserted CadNode

    def __init__(self, model: DocumentModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("Part library")
        self.setModal(False)
        self.resize(560, 420)

        # category filter above the part list (keeps 30+ parts navigable)
        self._category = QComboBox()
        cats = []
        for spec in PARTS.values():
            cat = spec.get("category", "Other")
            if cat not in cats:
                cats.append(cat)
        self._category.addItem("All")
        self._category.addItems(cats)
        self._category.currentTextChanged.connect(self._populate_parts)

        self._parts = QListWidget()
        self._visible_ids = []
        self._parts.currentRowChanged.connect(self._part_changed)

        self._size = QComboBox()
        self._size.currentTextChanged.connect(self._size_changed)

        self._form = QFormLayout()
        self._fields = {}

        left = QVBoxLayout()
        left.addWidget(QLabel("Category:"))
        left.addWidget(self._category)
        left.addWidget(self._parts, 1)

        right = QVBoxLayout()
        right.addWidget(QLabel("Standard size:"))
        right.addWidget(self._size)
        right.addLayout(self._form)
        right.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.Apply
                                   | QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Apply).setText("Insert")
        buttons.button(QDialogButtonBox.Apply).setDefault(True)
        buttons.button(QDialogButtonBox.Apply).clicked.connect(
            self._insert)
        buttons.rejected.connect(self.close)
        right.addWidget(buttons)

        layout = QHBoxLayout(self)
        layout.addLayout(left, 1)
        layout.addLayout(right, 1)
        self._populate_parts()

    # ------------------------------------------------------------ state
    def _populate_parts(self, _cat=None):
        """Fill the part list with the entries in the chosen category."""
        want = self._category.currentText()
        self._visible_ids = [pid for pid, spec in PARTS.items()
                             if want == "All"
                             or spec.get("category", "Other") == want]
        self._parts.blockSignals(True)
        self._parts.clear()
        for pid in self._visible_ids:
            self._parts.addItem(PARTS[pid]["label"])
        self._parts.blockSignals(False)
        if self._visible_ids:
            self._parts.setCurrentRow(0)      # fires _part_changed

    def _part_id(self):
        row = self._parts.currentRow()
        if 0 <= row < len(self._visible_ids):
            return self._visible_ids[row]
        return self._visible_ids[0] if self._visible_ids else None

    def _part_changed(self, _row):
        part_id = self._part_id()
        if part_id is None:
            return
        sizes = PARTS[part_id]["sizes"]
        self._size.blockSignals(True)
        self._size.clear()
        if sizes:
            self._size.addItems(list(sizes))
            default = 1 if len(sizes) > 1 else 0
            self._size.setCurrentIndex(default)
        self._size.setEnabled(bool(sizes))
        self._size.blockSignals(False)
        self._rebuild_form()

    def _size_changed(self, _text):
        self._load_size()

    def _rebuild_form(self):
        while self._form.count():
            item = self._form.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._fields.clear()
        part_id = self._part_id()
        if part_id is None:
            return
        spec = PARTS[part_id]
        if not spec["sizes"]:
            self._form.addRow(QLabel("Built-in dimensions"))
            return
        for key, label in spec["fields"]:
            if key == "bolts":
                box = QSpinBox()
                box.setRange(1, 64)
            else:
                box = QDoubleSpinBox()
                box.setRange(0.0, 2000.0)
                box.setDecimals(2)
                box.setSuffix(" mm")
            self._fields[key] = box
            self._form.addRow(label, box)
        self._load_size()

    def _load_size(self):
        part_id = self._part_id()
        if part_id is None:
            return
        sizes = PARTS[part_id]["sizes"]
        if not sizes or not self._fields:
            return
        dims = dict(sizes.get(self._size.currentText(),
                              next(iter(sizes.values()))))
        dims.setdefault("port_length",
                        60.0 if sizes is CF_SIZES else 30.0)
        for key, box in self._fields.items():
            if key in dims:
                box.setValue(dims[key])

    # ------------------------------------------------------------ insert
    def _insert(self):
        part_id = self._part_id()
        if part_id is None:
            return
        dims = {key: box.value() for key, box in self._fields.items()}
        if self._size.isEnabled():
            dims["_size"] = self._size.currentText()
        node = build_part(part_id, dims)
        size = self._size.currentText().split(" ")[0] \
            if self._size.isEnabled() else ""
        if size:
            node.name = f"{size} {node.name}" \
                if not node.name.startswith(size) else node.name
        self.model.root.add(node)
        self.model.structure_changed.emit()
        self.inserted = node
        self.part_inserted.emit(node)
