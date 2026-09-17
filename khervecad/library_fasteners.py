"""Fasteners for the parts library — the drawer of screws, nuts,
washers, pins and clips that every assembly needs.

`library.py` holds the three originals (DIN 933 hex bolt, DIN 912
socket cap screw, DIN 934 hex nut) and the dimensional tables; this
module adds the rest of the drawer at the same standards, all off
`library.BOLT_SIZES` so an M6 washer fits an M6 bolt:

- **screws**: part-threaded hex bolt (DIN 931), countersunk and button
  socket screws (ISO 10642 / 7380), slotted and cross-recessed pan
  heads, slotted countersunk, grub screw (ISO 4029), shoulder screw
  (ISO 7379), knurled thumb screw, eye bolt (DIN 580), U-bolt,
  carriage bolt (DIN 603), coach screw, wood screw, self-tapper,
  threaded rod and a hanger bolt;
- **nuts**: nyloc (DIN 985), wing (DIN 315), dome (DIN 1587), square,
  flanged (DIN 6923), castle (DIN 935), thin lock (DIN 439), coupler,
  T-slot nut, rivet nut and a heat-set insert;
- **washers**: flat (DIN 125), penny, split spring, external star and
  Belleville;
- **pins and clips**: dowel, clevis, split (cotter), R-clip, external
  and internal circlips, solid and blind rivets;
- **spacers**: hex standoff (male-female) and a round spacer.

Threads are the real helix (`library.thread_solid`), so a nut screws
onto its bolt. Rings are revolved profiles rather than a cylinder
minus a cylinder, and slots and cross recesses are unions of sectors,
so most parts preview exactly without waiting for OpenSCAD; where a
recess really must be cut (a hex socket, a tapped hole) the part is a
`difference()` and the per-part exact render finishes it.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .library import (BOLT_SIZES, _cyl, _hex, _hex_head, _thread_tip,
                      thread_solid)
from .library_room import _dims
from .model import CadNode

CATEGORY = "Fasteners"

STEEL = "#b9bec6"
DARK_STEEL = "#7d838c"
BRASS = "#c9a24a"
NYLON = "#3f63c2"
ALU = "#d0d4d8"


# ----------------------------------------------------------- helpers

def _paint(node, colour=STEEL, material="Metal"):
    col = CadNode("color", node.name, dict(color=colour, alpha=1.0,
                                           material=material))
    col.add(node)
    return col


def _rev(name, points, angle=360.0, segments=96):
    """A revolved profile: (radius, z) points spun about Z. This is how
    every ring here is made — an annulus with no boolean."""
    ext = CadNode("rotate_extrude", name, dict(angle=angle,
                                               segments=segments))
    ext.add(CadNode("polygon", f"{name} profile", dict(
        x=0.0, y=0.0, points=[[round(r, 4), round(z, 4)]
                              for r, z in points])))
    return ext


def _ring(name, r_in, r_out, z, h, angle=360.0):
    return _rev(name, [(r_in, z), (r_out, z), (r_out, z + h),
                       (r_in, z + h)], angle)


def _torus(name, major, minor, angle=360.0, n=16):
    """A round bar bent into a ring (or an arc of one): the section
    circle sits at radius *major*, so the profile never crosses the
    axis. The ring lies in the XY plane — turn it to stand up."""
    pts = [(major + minor * math.cos(2 * math.pi * k / n),
            minor * math.sin(2 * math.pi * k / n)) for k in range(n)]
    return _rev(name, pts, angle)


def _sector(name, r, h, z, angle, start, segments=48):
    """A pie slice, extruded: the pieces a slot or a cross recess
    leaves behind, so the drive is modelled without cutting it."""
    ext = CadNode("linear_extrude", name, dict(
        height=h, twist=0.0, scale=1.0, center=False, segments=1))
    ext.add(CadNode("circle", f"{name} face", dict(
        x=0.0, y=0.0, radius=r, angle=angle, start_angle=start,
        segments=segments)))
    return _at(ext, z=z)


def _at(node, x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0):
    """*node* moved (and optionally turned first)."""
    inner = node
    if rx or ry or rz:
        rot = CadNode("rotate", node.name, dict(x=rx, y=ry, z=rz))
        rot.add(node)
        inner = rot
    if x or y or z:
        mv = CadNode("translate", node.name, dict(x=x, y=y, z=z))
        mv.add(inner)
        return mv
    return inner


def _box(name, w, d, h, x=0.0, y=0.0, z=0.0):
    return CadNode("cube", name, dict(x=x - w / 2.0, y=y - d / 2.0, z=z,
                                      width=w, depth=d, height=h,
                                      center=False))


def _thread(p, length, z=0.0, name="Thread", pitch=None, clearance=0.0):
    return _at(thread_solid(p["d"], pitch or p["pitch"], length,
                            clearance=clearance, name=name), z=z)


def _tapped(p, z, depth, clearance=0.18):
    """The thread to subtract for a tapped hole."""
    return _at(thread_solid(p["d"], p["pitch"], depth,
                            clearance=clearance, name="Tapped hole"),
               z=z)


def _socket(p, z, depth, af=None):
    """A hex drive recess, open upwards from *z*."""
    return _hex("Hex socket", af or p["socket"], depth + 1.0, z=z)


def _point(d, length, z=0.0, name="Point"):
    """A sharpened tip, for wood and self-tapping screws."""
    return _cyl(name, 0.12 * d, length, z=z, r2=d / 2.0, segments=32)


def _cut(name, solid, *holes):
    part = CadNode("difference", name)
    part.add(solid)
    for h in holes:
        part.add(h)
    return part


def _dome(name, r, h, base):
    """A dome sitting on z = *base*: apex first, then out to the rim."""
    pts = [(r * math.sin(math.radians(a)),
            base + h * math.cos(math.radians(a)))
           for a in range(0, 91, 10)]
    return _rev(name, pts + [(0.0, base)])


def _knurl_ring(name, r, z, h, teeth=24, depth=None):
    """A knurled band: small ridges round a cylinder, by for-loop —
    the grip on a thumb screw, insert or rivet nut."""
    depth = depth or max(r * 0.09, 0.2)
    loop = CadNode("for_loop", name, dict(
        variable="a", start=0.0, end=teeth - 1.0, step=1.0,
        values=", ".join(str(round(360.0 * k / teeth, 2))
                         for k in range(teeth))))
    rot = CadNode("rotate", "Ridge", dict(x=0.0, y=0.0, z="a"))
    rot.add(_box("Ridge", depth * 2, depth * 1.4, h, x=r, z=z))
    loop.add(rot)
    return loop


# ------------------------------------------------------------ screws

def bolt_hex_partial(p):
    """DIN 931: a hex bolt with a plain shank under the head, threaded
    only for the last stretch — what holds a bearing in shear."""
    length, d = p["length"], p["d"]
    thread = min(2.0 * d + 6.0, length - d * 0.5)
    part = CadNode("union", "Hex bolt (part threaded)")
    part.add(_thread(p, thread))
    part.add(_thread_tip(d, p["pitch"]))
    part.add(_cyl("Shank", d / 2.0, length - thread, z=thread))
    part.add(_hex_head(p["af"], p["head_h"], z=length))
    return _paint(part)


def screw_countersunk(p):
    """ISO 10642: a 90° countersunk head with a hex socket, so it sits
    flush in a chamfered hole."""
    length, d = p["length"], p["d"]
    head_d, head_h = 2.0 * d, 0.55 * d
    solid = CadNode("union", "Screw body")
    solid.add(_thread(p, length))
    solid.add(_thread_tip(d, p["pitch"]))
    solid.add(_cyl("Countersunk head", d / 2.0, head_h, z=length,
                   r2=head_d / 2.0))
    return _paint(_cut("Countersunk socket screw", solid,
                       _socket(p, length + head_h - 0.6 * d,
                               0.6 * d, af=p["socket"] * 0.85)))


def screw_button(p):
    """ISO 7380: the low dome head, hex socket."""
    length, d = p["length"], p["d"]
    head_d, head_h = 1.9 * d, 0.55 * d
    solid = CadNode("union", "Screw body")
    solid.add(_thread(p, length))
    solid.add(_thread_tip(d, p["pitch"]))
    solid.add(_dome("Button head", head_d / 2.0, head_h, length))
    return _paint(_cut("Button head screw", solid,
                       _socket(p, length + head_h - 0.45 * d, 0.45 * d,
                               af=p["socket"] * 0.8)))


def _slot_head(name, r, h, z, slot_w, depth):
    """A head whose slot is what is NOT there: the two pieces either
    side of the slot standing on a solid base."""
    head = CadNode("union", name)
    head.add(_cyl("Head base", r, h - depth, z=z))
    for side in (0, 180):
        piece = _sector("Slot land", r, depth, z + h - depth, 180.0 - 0.0,
                        side)
        head.add(_at(piece, y=(slot_w / 2.0) * (1 if side == 0 else -1)))
    return head


def _cross_head(name, r, h, z, slot_w, depth):
    """The four quadrants a Phillips recess leaves standing."""
    head = CadNode("union", name)
    head.add(_cyl("Head base", r, h - depth, z=z))
    for k, (dx, dy) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
        piece = _sector("Recess land", r, depth, z + h - depth, 90.0,
                        90.0 * k)
        head.add(_at(piece, x=dx * slot_w / 2.0, y=dy * slot_w / 2.0))
    return head


def screw_pan_slotted(p):
    """A slotted pan head machine screw (DIN 85)."""
    length, d = p["length"], p["d"]
    head_d, head_h = 1.9 * d, 0.6 * d
    part = CadNode("union", "Slotted pan screw")
    part.add(_thread(p, length))
    part.add(_thread_tip(d, p["pitch"]))
    part.add(_slot_head("Pan head", head_d / 2.0, head_h, length,
                        max(0.17 * d, 0.5), head_h * 0.5))
    return _paint(part)


def screw_pan_cross(p):
    """A cross-recessed (Phillips) pan head machine screw."""
    length, d = p["length"], p["d"]
    head_d, head_h = 1.9 * d, 0.6 * d
    part = CadNode("union", "Cross pan screw")
    part.add(_thread(p, length))
    part.add(_thread_tip(d, p["pitch"]))
    part.add(_cross_head("Pan head", head_d / 2.0, head_h, length,
                         max(0.16 * d, 0.5), head_h * 0.55))
    return _paint(part)


def screw_countersunk_slotted(p):
    """A slotted countersunk machine screw (DIN 963) — the flush head
    of a hinge or a switch plate."""
    length, d = p["length"], p["d"]
    head_d, head_h = 2.0 * d, 0.55 * d
    slot = max(0.17 * d, 0.5)
    part = CadNode("union", "Slotted countersunk screw")
    part.add(_thread(p, length))
    part.add(_thread_tip(d, p["pitch"]))
    part.add(_cyl("Countersunk head", d / 2.0, head_h * 0.55, z=length,
                  r2=head_d / 2.0 * 0.78))
    # the slotted top: two cone sectors either side of the slot
    for side, sign in ((0.0, 1), (180.0, -1)):
        land = _sector("Slot land", head_d / 2.0, head_h * 0.45,
                       length + head_h * 0.55, 180.0, side)
        part.add(_at(land, y=sign * slot / 2.0))
    return _paint(part)


def d_of(p):
    return p["d"]


def set_screw(p):
    """ISO 4029 grub screw: all thread, hex socket, cup point — what
    clamps a pulley on a shaft."""
    length, d = max(p["length"] * 0.5, 1.5 * d_of(p)), p["d"]
    solid = CadNode("union", "Grub screw body")
    solid.add(_thread(p, length, name="Grub thread"))
    solid.add(_cyl("Core", d / 2.0 - 0.6134 * p["pitch"], length))
    return _paint(_cut("Grub screw", solid,
                       _socket(p, length - 0.55 * d, 0.55 * d,
                               af=p["socket"] * 0.8),
                       _cyl("Cup point", d * 0.36, d * 0.25, z=-0.01)))


def shoulder_screw(p):
    """ISO 7379: a ground shoulder for a bearing or a linkage to turn
    on, a cap head above and a smaller thread below."""
    d = p["d"]
    shoulder_d, shoulder = 1.33 * d, p["length"]
    head_d, head_h = 1.75 * shoulder_d, 0.55 * shoulder_d
    thread_len = 1.3 * d
    solid = CadNode("union", "Shoulder screw body")
    solid.add(_thread(p, thread_len))
    solid.add(_thread_tip(d, p["pitch"]))
    solid.add(_cyl("Shoulder", shoulder_d / 2.0, shoulder, z=thread_len))
    solid.add(_cyl("Head", head_d / 2.0, head_h,
                   z=thread_len + shoulder))
    top = thread_len + shoulder + head_h
    return _paint(_cut("Shoulder screw", solid,
                       _socket(p, top - 0.5 * d, 0.5 * d)))


def thumb_screw(p):
    """A knurled thumb screw: turned by hand, no tool."""
    length, d = p["length"], p["d"]
    head_d, head_h = 3.2 * d, 1.1 * d
    part = CadNode("union", "Thumb screw")
    part.add(_thread(p, length))
    part.add(_thread_tip(d, p["pitch"]))
    part.add(_rev("Knurled head", [
        (0.0, length), (head_d / 2.0 - 0.4, length),
        (head_d / 2.0, length + 0.4),
        (head_d / 2.0, length + head_h - 0.4),
        (head_d / 2.0 - 0.4, length + head_h), (0.0, length + head_h)]))
    part.add(_knurl_ring("Knurl", head_d / 2.0 - 0.1, length + 0.4,
                         head_h - 0.8, teeth=int(head_d * 1.6)))
    return _paint(part)


def eye_bolt(p):
    """DIN 580 style lifting eye: a forged ring over a threaded shank."""
    d = p["d"]
    length = p["length"] * 0.8
    ring_r, wire = 1.6 * d, 0.55 * d
    part = CadNode("union", "Eye bolt")
    part.add(_thread(p, length))
    part.add(_thread_tip(d, p["pitch"]))
    part.add(_cyl("Collar", 1.5 * d / 2.0 + wire / 2.0, 0.35 * d,
                  z=length))
    neck = length + 0.35 * d
    part.add(_cyl("Neck", wire * 0.9, ring_r * 0.6, z=neck))
    ring = _torus("Eye", ring_r, wire, n=20)
    part.add(_at(ring, rx=90.0, z=neck + ring_r * 0.6 + ring_r))
    return _paint(part)


def u_bolt(p):
    """A U-bolt: a bent bar threaded at both ends, for clamping a pipe
    to a rail. `length` is the straight leg."""
    d, leg = p["d"], p["length"]
    span = max(4.0 * d, 20.0)
    bend = span / 2.0
    part = CadNode("union", "U-bolt")
    for sign in (1, -1):
        part.add(_at(_thread(p, 2.2 * d), x=sign * bend))
        part.add(_at(_thread_tip(d, p["pitch"]), x=sign * bend))
        part.add(_cyl("Leg", d / 2.0, leg, z=2.2 * d, x=sign * bend))
    arc = _torus("Bend", bend, d / 2.0, angle=180.0)
    part.add(_at(arc, rx=90.0, z=leg + 2.2 * d))
    return _paint(part)


def carriage_bolt(p):
    """DIN 603 coach bolt: a smooth dome head over a square neck that
    bites into timber so the bolt cannot turn."""
    d, length = p["d"], p["length"]
    head_d, head_h = 2.2 * d, 0.45 * d
    neck = 0.8 * d
    thread = min(2.0 * d + 6.0, length - neck - 1.0)
    part = CadNode("union", "Carriage bolt")
    part.add(_thread(p, thread))
    part.add(_thread_tip(d, p["pitch"]))
    part.add(_cyl("Shank", d / 2.0, length - thread, z=thread))
    part.add(_box("Square neck", d * 1.05, d * 1.05, neck, z=length))
    part.add(_dome("Dome head", head_d / 2.0, head_h,
                   length + neck))
    return _paint(part)


def coach_screw(p):
    """A coach (lag) screw: hex head, coarse wood thread, sharp point —
    driven into timber with a spanner."""
    d, length = p["d"], p["length"] * 1.5
    pitch = 0.42 * d
    thread = length * 0.7
    part = CadNode("union", "Coach screw")
    part.add(_at(thread_solid(d, pitch, thread, name="Wood thread"),
                 z=0.25 * d))
    part.add(_point(d, 0.9 * d, z=-0.6 * d))
    part.add(_cyl("Core", d * 0.42, thread + 0.3 * d, z=0.2 * d))
    part.add(_cyl("Shank", d / 2.0, length - thread - 0.25 * d,
                  z=thread + 0.25 * d))
    part.add(_hex_head(p["af"], p["head_h"], z=length))
    return _paint(part)


def wood_screw(p):
    """A countersunk wood screw: cross recess, coarse thread up a
    tapering core, sharp point."""
    d, length = p["d"], p["length"] * 1.6
    pitch = 0.45 * d
    head_d, head_h = 2.0 * d, 0.55 * d
    thread = length * 0.75
    part = CadNode("union", "Wood screw")
    part.add(_at(thread_solid(d, pitch, thread, name="Wood thread"),
                 z=0.3 * d))
    part.add(_point(d, d, z=-0.7 * d))
    part.add(_cyl("Core", d * 0.35, thread + 0.4 * d, z=0.2 * d,
                  r2=d * 0.42))
    part.add(_cyl("Shank", d * 0.42, length - thread - 0.3 * d,
                  z=thread + 0.3 * d))
    part.add(_cyl("Countersunk head", d * 0.42, head_h, z=length,
                  r2=head_d / 2.0))
    part.add(_cross_head("Head top", head_d / 2.0, 0.22 * d,
                         length + head_h - 0.22 * d,
                         max(0.16 * d, 0.5), 0.22 * d))
    return _paint(part)


def self_tapping_screw(p):
    """A pan-head self-tapper for sheet metal and plastic: sharp
    thread the whole way, cross recess."""
    d, length = p["d"], p["length"]
    pitch = 0.4 * d
    head_d, head_h = 1.9 * d, 0.55 * d
    part = CadNode("union", "Self-tapping screw")
    part.add(_at(thread_solid(d, pitch, length - 0.4 * d,
                              name="Sharp thread"), z=0.4 * d))
    part.add(_point(d, 1.1 * d, z=-0.6 * d))
    part.add(_cyl("Core", d * 0.36, length, z=0.0))
    part.add(_cross_head("Pan head", head_d / 2.0, head_h, length,
                         max(0.16 * d, 0.5), head_h * 0.55))
    return _paint(part)


def threaded_rod(p):
    """A length of studding, chamfered at both ends."""
    d, length = p["d"], p["length"] * 4.0
    part = CadNode("union", "Threaded rod")
    part.add(_thread(p, length))
    part.add(_thread_tip(d, p["pitch"]))
    part.add(_at(_thread_tip(d, p["pitch"], name="Top chamfer"),
                 rx=180.0, z=length - p["pitch"]))
    return _paint(part)


def hanger_bolt(p):
    """A hanger bolt (dowel screw): wood thread one end, machine
    thread the other, a plain waist to grip with pliers."""
    d, length = p["d"], p["length"]
    wood = length * 0.6
    part = CadNode("union", "Hanger bolt")
    part.add(_at(thread_solid(d, 0.45 * d, wood, name="Wood thread"),
                 z=0.3 * d))
    part.add(_point(d, d, z=-0.7 * d))
    part.add(_cyl("Core", d * 0.36, wood + 0.4 * d, z=0.2 * d))
    part.add(_cyl("Waist", d * 0.42, 0.8 * d, z=wood + 0.3 * d))
    part.add(_thread(p, length, z=wood + 1.1 * d))
    return _paint(part)


# -------------------------------------------------------------- nuts

def _nut_body(p, height=None, chamfer_bottom=True, name="Nut body"):
    return _hex_head(p["af"], height or p["nut_h"], name=name,
                     chamfer_bottom=chamfer_bottom)


def nut_nyloc(p):
    """DIN 985: a hex nut with a nylon insert that grips the thread and
    stops it shaking loose."""
    h = p["nut_h"] * 1.25
    body = _cut("Nyloc nut", _nut_body(p, h),
                _tapped(p, -0.5, h * 0.75 + 0.5))
    collar = _ring("Nylon collar", p["d"] * 0.44, p["af"] / 2.0 * 0.9,
                   h * 0.76, h * 0.24)
    part = CadNode("union", "Nyloc nut")
    part.add(_paint(body))
    part.add(_paint(collar, NYLON, "Plastic"))
    return part


def nut_wing(p):
    """DIN 315 wing nut: two forged wings, tightened by finger."""
    d, h = p["d"], p["nut_h"] * 1.4
    wing_l, wing_h, wing_t = 2.4 * d, 1.8 * d, 0.38 * d
    solid = CadNode("union", "Wing nut body")
    solid.add(_cyl("Boss", p["af"] / 2.0 * 0.95, h))
    solid.add(_cyl("Collar", p["af"] / 2.0 * 0.7, h * 1.5))
    for sign in (1, -1):
        blade = CadNode("union", "Wing")
        blade.add(_box("Blade", wing_t, wing_l * 0.9, wing_h * 0.9,
                       y=wing_l * 0.28, z=h * 0.2))
        blade.add(_box("Fillet", wing_t, wing_l * 0.4, wing_h * 0.45,
                       y=wing_l * 0.1, z=h * 0.1))
        solid.add(_at(blade, rz=90.0 if sign > 0 else 270.0))
    return _paint(_cut("Wing nut", solid, _tapped(p, -0.5, h * 1.5 + 1)))


def nut_dome(p):
    """DIN 1587 dome (acorn) nut: a blind thread under a smooth cap, so
    nothing catches on the bolt end."""
    d, h = p["d"], p["nut_h"]
    r = p["af"] / 2.0
    solid = CadNode("union", "Dome nut body")
    solid.add(_nut_body(p, h, name="Hex body"))
    solid.add(_dome("Dome", r, r * 0.85, h))
    return _paint(_cut("Dome nut", solid, _tapped(p, -0.5, h + 0.5)))


def nut_square(p):
    """A square nut — the one that sits in a slot and cannot turn."""
    af, h = p["af"], p["nut_h"]
    return _paint(_cut("Square nut", _box("Nut body", af, af, h),
                       _tapped(p, -0.5, h + 1.0)))


def nut_flange(p):
    """DIN 6923: a hex nut on a serrated flange that spreads the load
    and bites the surface, so no washer is needed."""
    d, h = p["d"], p["nut_h"]
    flange_d, flange_h = 2.3 * d, 0.22 * d
    solid = CadNode("union", "Flange nut body")
    solid.add(_rev("Flange", [(d * 0.45, 0.0), (flange_d / 2.0, 0.0),
                              (flange_d / 2.0, flange_h * 0.5),
                              (p["af"] / 2.0 * 0.95, flange_h * 1.6),
                              (d * 0.45, flange_h * 1.6)]))
    solid.add(_hex_head(p["af"], h, z=flange_h * 1.2, name="Hex body"))
    solid.add(_knurl_ring("Serrations", flange_d / 2.0 * 0.85, 0.0,
                          flange_h * 0.6, teeth=int(flange_d * 1.4)))
    return _paint(_cut("Flanged nut", solid,
                       _tapped(p, -0.5, h + flange_h * 2 + 1)))


def nut_castle(p):
    """DIN 935 castle nut: slots for the split pin through the bolt, so
    it can never undo — steering and axle work."""
    d, h = p["d"], p["nut_h"]
    crown = 0.6 * d
    solid = CadNode("union", "Castle nut body")
    solid.add(_nut_body(p, h, name="Hex body"))
    solid.add(_cyl("Crown", p["af"] / 2.0 * 0.92, crown, z=h))
    cuts = [_tapped(p, -0.5, h + crown + 1.0)]
    slots = CadNode("for_loop", "Slots", dict(
        variable="a", start=0.0, end=5.0, step=1.0,
        values=", ".join(str(k * 60.0) for k in range(6))))
    rot = CadNode("rotate", "Slot", dict(x=0.0, y=0.0, z="a"))
    rot.add(_box("Slot", p["af"] * 1.2, d * 0.26, crown * 0.55,
                 z=h + crown * 0.45))
    slots.add(rot)
    cuts.append(slots)
    return _paint(_cut("Castle nut", solid, *cuts))


def nut_thin(p):
    """DIN 439 jam nut: half height, locked against another nut."""
    h = p["nut_h"] * 0.55
    return _paint(_cut("Thin lock nut", _nut_body(p, h),
                       _tapped(p, -0.5, h + 1.0)))


def nut_coupler(p):
    """A coupling nut: three diameters long, joining two studs."""
    h = p["d"] * 3.0
    return _paint(_cut("Coupling nut", _nut_body(p, h),
                       _tapped(p, -0.5, h + 1.0)))


def nut_tslot(p):
    """A drop-in T-slot nut for aluminium extrusion: it turns a quarter
    in the slot and locks under the lips."""
    d = p["d"]
    w, ledge, length = 6.0, 9.6, 12.0
    if d >= 6:
        w, ledge, length = 7.5, 11.5, 14.0
    solid = CadNode("union", "T-nut body")
    solid.add(_box("Stem", w, length, 2.0))
    solid.add(_box("Ledge", ledge, length, 1.6, z=2.0))
    solid.add(_box("Lead-in", ledge * 0.6, length, 0.8, z=3.6))
    return _paint(_cut("T-slot nut", solid, _tapped(p, -0.5, 5.5)))


def nut_rivet(p):
    """A rivet nut (rivnut): a knurled body that collapses behind thin
    sheet and leaves a thread in it."""
    d = p["d"]
    body_d, body = 1.55 * d, 2.6 * d
    flange_d, flange = 2.2 * d, 0.22 * d
    solid = CadNode("union", "Rivet nut body")
    solid.add(_rev("Flange", [(d * 0.45, 0.0), (flange_d / 2.0, 0.0),
                              (flange_d / 2.0, flange),
                              (d * 0.45, flange)]))
    solid.add(_rev("Body", [(d * 0.45, flange), (body_d / 2.0, flange),
                            (body_d / 2.0, flange + body * 0.55),
                            (body_d / 2.0 * 0.86, flange + body * 0.62),
                            (body_d / 2.0, flange + body * 0.7),
                            (body_d / 2.0, flange + body),
                            (d * 0.45, flange + body)]))
    solid.add(_knurl_ring("Knurl", body_d / 2.0, flange, body * 0.5,
                          teeth=int(body_d * 2.4)))
    return _paint(_cut("Rivet nut", solid,
                       _tapped(p, flange + body * 0.55,
                               body * 0.5 + 1.0)))


def insert_heat_set(p):
    """A heat-set threaded insert: melted into a printed boss, its
    knurled bands and waist keying it into the plastic."""
    d = p["d"]
    od, h = 1.4 * d, 1.6 * d
    solid = CadNode("union", "Insert body")
    solid.add(_rev("Body", [
        (d * 0.4, 0.0), (od / 2.0, 0.0), (od / 2.0, h * 0.28),
        (od / 2.0 * 0.86, h * 0.42), (od / 2.0, h * 0.56),
        (od / 2.0, h * 0.84), (od / 2.0 * 0.9, h),
        (d * 0.4, h)]))
    for z, band in ((0.02, h * 0.24), (h * 0.58, h * 0.24)):
        solid.add(_knurl_ring("Knurl", od / 2.0, z, band,
                              teeth=int(od * 3)))
    return _paint(_cut("Heat-set insert", solid,
                       _tapped(p, -0.5, h + 1.0)), BRASS, "Gold")


# ----------------------------------------------------------- washers

def washer_flat(p):
    """DIN 125 flat washer: spreads the load under a nut."""
    d = p["d"]
    return _paint(_ring("Flat washer", d * 0.55, d * 1.1, 0.0,
                        max(0.16 * d, 0.5)))


def washer_penny(p):
    """A penny (fender) washer: a wide brim for soft or slotted
    material."""
    d = p["d"]
    return _paint(_ring("Penny washer", d * 0.55, d * 1.75, 0.0,
                        max(0.13 * d, 0.5)))


def washer_spring(p):
    """A split spring washer: one helical turn with a gap, so it
    presses the nut back as it loosens."""
    d = p["d"]
    r_in, r_out = d * 0.55, d * 0.85
    t = max(0.22 * d, 0.6)
    ext = CadNode("linear_extrude", "Spring washer", dict(
        height=t * 1.1, twist=-345.0, scale=1.0, center=False,
        segments=64))
    ext.add(CadNode("polygon", "Section", dict(
        x=0.0, y=0.0, points=[[round(r_in, 3), 0.0],
                              [round(r_out, 3), 0.0],
                              [round(r_out, 3), round(t, 3)],
                              [round(r_in, 3), round(t, 3)]])))
    return _paint(ext)


def washer_star(p):
    """An external tooth (star) lock washer: the teeth bite both the
    nut and the work."""
    d = p["d"]
    r_in, r_out, t = d * 0.55, d * 1.0, max(0.12 * d, 0.4)
    teeth = max(int(d * 1.6), 8)
    part = CadNode("union", "Star washer")
    part.add(_ring("Body", r_in, r_out * 0.78, 0.0, t))
    loop = CadNode("for_loop", "Teeth", dict(
        variable="a", start=0.0, end=teeth - 1.0, step=1.0,
        values=", ".join(str(round(360.0 * k / teeth, 2))
                         for k in range(teeth))))
    rot = CadNode("rotate", "Tooth", dict(x=0.0, y=0.0, z="a"))
    tooth = CadNode("linear_extrude", "Tooth", dict(
        height=t, twist=0.0, scale=1.0, center=False, segments=1))
    w = r_out * 0.34
    tooth.add(CadNode("polygon", "Tooth face", dict(
        x=0.0, y=0.0, points=[[round(r_out * 0.72, 3), round(-w, 3)],
                              [round(r_out, 3), round(-w * 0.45, 3)],
                              [round(r_out, 3), round(w * 0.45, 3)],
                              [round(r_out * 0.72, 3), round(w, 3)]])))
    rot.add(tooth)
    loop.add(rot)
    part.add(loop)
    return _paint(part)


def washer_belleville(p):
    """A Belleville (conical disc) spring washer: preload that survives
    thermal cycling."""
    d = p["d"]
    r_in, r_out = d * 0.55, d * 1.05
    t, rise = max(0.13 * d, 0.4), max(0.22 * d, 0.6)
    return _paint(_rev("Belleville washer", [
        (r_in, rise), (r_out, 0.0), (r_out, t), (r_in, rise + t)]))


# --------------------------------------------------- pins and clips

def pin_dowel(p):
    """A ground dowel pin: chamfered both ends, for locating two parts
    exactly."""
    d, length = p["d"], p["length"]
    cham = d * 0.12
    return _paint(_rev("Dowel pin", [
        (0.0, 0.0), (d / 2.0 - cham, 0.0), (d / 2.0, cham),
        (d / 2.0, length - cham), (d / 2.0 - cham, length),
        (0.0, length)]))


def pin_clevis(p):
    """A clevis pin: a head one end and a cross hole the other for a
    split pin or an R-clip."""
    d, length = p["d"], p["length"]
    head_d, head_h = 1.8 * d, 0.35 * d
    solid = CadNode("union", "Clevis pin body")
    solid.add(_cyl("Shank", d / 2.0, length))
    solid.add(_rev("Head", [(0.0, length), (head_d / 2.0, length),
                            (head_d / 2.0, length + head_h * 0.6),
                            (head_d / 2.0 - head_h * 0.4,
                             length + head_h),
                            (0.0, length + head_h)]))
    hole = _at(_cyl("Cross hole", d * 0.18, 2 * d, z=-d), rx=90.0,
               z=d * 0.55)
    return _paint(_cut("Clevis pin", solid, hole))


def pin_split(p):
    """A split (cotter) pin: two legs under an eye, spread open once
    it is through the hole."""
    d, length = p["d"] * 0.35, p["length"]
    part = CadNode("union", "Split pin")
    for sign in (1, -1):
        leg = _cyl("Leg", d / 2.0, length, z=0.0, x=sign * d * 0.52)
        part.add(leg)
        part.add(_cyl("Leg tip", d / 2.0, d, z=-d, x=sign * d * 0.52,
                      r2=d * 0.2))
    part.add(_at(_torus("Eye", d * 0.52, d / 2.0, n=14), rx=90.0,
                 z=length))
    return _paint(part, DARK_STEEL)


def _rod_xz(name, x0, z0, x1, z1, r):
    """A round bar between two points in the XZ plane."""
    dx, dz = x1 - x0, z1 - z0
    length = math.hypot(dx, dz)
    ang = math.degrees(math.atan2(dx, dz))
    return _at(_cyl(name, r, length, segments=16), ry=ang, x=x0, z=z0)


def pin_r(p):
    """An R-clip (hairpin cotter): the straight leg goes through the
    pin and the sprung leg snaps round it."""
    wire = p["d"] * 0.15
    length = p["length"]
    gap = p["d"] * 0.62
    part = CadNode("union", "R-clip")
    part.add(_cyl("Straight leg", wire, length, segments=16))
    part.add(_at(_torus("Eye", gap / 2.0, wire, n=16), rx=90.0,
                 x=gap / 2.0, z=length))
    # the sprung leg: down past the pin, in against it, then flicked out
    part.add(_rod_xz("Sprung leg", gap, length, gap * 0.55,
                     length * 0.45, wire))
    part.add(_rod_xz("Sprung tip", gap * 0.55, length * 0.45,
                     gap * 1.35, length * 0.1, wire))
    return _paint(part, DARK_STEEL)


def _circlip(p, internal):
    """A retaining ring: a split ring with two lugs drilled for the
    pliers. Internal ones close into a bore, external ones open onto a
    shaft."""
    d = p["d"]
    t = max(0.1 * d, 0.5)
    if internal:
        r_in, r_out = d * 0.5, d * 0.5 + max(0.13 * d, 0.6)
    else:
        r_out, r_in = d * 0.5, d * 0.5 - max(0.13 * d, 0.6)
    ring = _ring("Ring", r_in, r_out, 0.0, t, angle=290.0)
    solid = CadNode("union", "Circlip body")
    solid.add(ring)
    holes = []
    for k, a in ((0, 290.0), (1, 0.0)):
        lug_r = (r_out - r_in) * 1.1
        centre = (r_out + r_in) / 2.0
        lug = _cyl("Lug", lug_r, t, x=centre)
        solid.add(_at(lug, rz=a))
        holes.append(_at(_cyl("Eye", lug_r * 0.38, t + 2, x=centre,
                              z=-1.0), rz=a))
    name = "Internal circlip" if internal else "External circlip"
    return _paint(_cut(name, solid, *holes), DARK_STEEL)


def circlip_external(p):
    """DIN 471: the ring that holds a bearing on a shaft."""
    return _circlip(p, internal=False)


def circlip_internal(p):
    """DIN 472: the ring that holds a bearing in a housing."""
    return _circlip(p, internal=True)


def rivet_solid(p):
    """A solid rivet: a dome head over a plain shank, hammered over on
    the far side."""
    d, length = p["d"], p["length"]
    head_d, head_h = 1.8 * d, 0.55 * d
    part = CadNode("union", "Solid rivet")
    part.add(_cyl("Shank", d / 2.0, length))
    part.add(_dome("Dome head", head_d / 2.0, head_h, length))
    return _paint(part, ALU)


def rivet_blind(p):
    """A blind (pop) rivet as delivered: the aluminium body on its
    steel mandrel, which snaps off when it is set."""
    d, length = p["d"], p["length"]
    flange_d, flange = 2.0 * d, 0.2 * d
    body = CadNode("union", "Rivet body")
    body.add(_rev("Flange", [(0.0, 0.0), (flange_d / 2.0, 0.0),
                             (flange_d / 2.0, flange * 0.6),
                             (d / 2.0, flange),
                             (0.0, flange)]))
    body.add(_cyl("Body", d / 2.0, length, z=flange))
    stem = CadNode("union", "Mandrel")
    stem.add(_cyl("Stem", d * 0.28, length * 1.9, z=flange))
    stem.add(_cyl("Mandrel head", d * 0.45, d * 0.35, z=0.0,
                  r2=d * 0.28))
    part = CadNode("union", "Blind rivet")
    part.add(_paint(body, ALU))
    part.add(_paint(stem, DARK_STEEL))
    return part


# ---------------------------------------------------------- spacers

def standoff_hex(p):
    """A hex standoff, male-female: a tapped body with a threaded stud
    below — how a board is held off a chassis."""
    d = p["d"]
    h = max(6.0 * d, 10.0)
    stud = 1.6 * d
    solid = CadNode("union", "Standoff body")
    solid.add(_at(_hex("Body", p["af"] * 0.85, h), z=stud))
    solid.add(_thread(p, stud))
    solid.add(_thread_tip(d, p["pitch"]))
    return _paint(_cut("Hex standoff", solid,
                       _tapped(p, stud + h - 2.5 * d, 2.5 * d + 1.0)),
                  BRASS, "Gold")


def spacer_round(p):
    """A plain round spacer: no thread, just the right length."""
    d = p["d"]
    return _paint(_ring("Round spacer", d * 0.55, d * 1.0, 0.0,
                        max(3.0 * d, 5.0)), ALU)


# --------------------------------------------------------- registry

_SCREW_FIELDS = [("d", "Thread Ø"), ("pitch", "Pitch"),
                 ("length", "Length")]
_PLAIN_FIELDS = [("d", "Thread Ø"), ("pitch", "Pitch"),
                 ("af", "Across flats"), ("nut_h", "Thickness")]
_RING_FIELDS = [("d", "Bore Ø")]
_PIN_FIELDS = [("d", "Pin Ø"), ("length", "Length")]

#: label, builder, field list — every part takes the shared ISO size
#: table, so an M6 washer, nut and bolt belong together.
_PARTS = [
    ("bolt_hex_partial", "Hex bolt, part threaded (DIN 931)",
     bolt_hex_partial, _SCREW_FIELDS),
    ("screw_countersunk", "Countersunk socket screw (ISO 10642)",
     screw_countersunk, _SCREW_FIELDS),
    ("screw_button", "Button head socket screw (ISO 7380)",
     screw_button, _SCREW_FIELDS),
    ("screw_pan_slotted", "Pan head screw, slotted (DIN 85)",
     screw_pan_slotted, _SCREW_FIELDS),
    ("screw_pan_cross", "Pan head screw, cross recess",
     screw_pan_cross, _SCREW_FIELDS),
    ("screw_csk_slotted", "Countersunk screw, slotted (DIN 963)",
     screw_countersunk_slotted, _SCREW_FIELDS),
    ("screw_set", "Grub screw, cup point (ISO 4029)", set_screw,
     _SCREW_FIELDS),
    ("screw_shoulder", "Shoulder screw (ISO 7379)", shoulder_screw,
     _SCREW_FIELDS),
    ("screw_thumb", "Thumb screw, knurled", thumb_screw, _SCREW_FIELDS),
    ("bolt_eye", "Eye bolt (DIN 580)", eye_bolt, _SCREW_FIELDS),
    ("bolt_u", "U-bolt", u_bolt, _SCREW_FIELDS),
    ("bolt_carriage", "Carriage bolt (DIN 603)", carriage_bolt,
     _SCREW_FIELDS),
    ("screw_coach", "Coach screw (lag bolt)", coach_screw,
     _SCREW_FIELDS),
    ("screw_wood", "Wood screw, countersunk", wood_screw, _SCREW_FIELDS),
    ("screw_self_tapping", "Self-tapping screw, pan head",
     self_tapping_screw, _SCREW_FIELDS),
    ("rod_threaded", "Threaded rod (studding)", threaded_rod,
     _SCREW_FIELDS),
    ("bolt_hanger", "Hanger bolt (dowel screw)", hanger_bolt,
     _SCREW_FIELDS),
    ("nut_nyloc", "Nyloc nut (DIN 985)", nut_nyloc, _PLAIN_FIELDS),
    ("nut_wing", "Wing nut (DIN 315)", nut_wing, _PLAIN_FIELDS),
    ("nut_dome", "Dome nut (DIN 1587)", nut_dome, _PLAIN_FIELDS),
    ("nut_square", "Square nut", nut_square, _PLAIN_FIELDS),
    ("nut_flange", "Flanged nut, serrated (DIN 6923)", nut_flange,
     _PLAIN_FIELDS),
    ("nut_castle", "Castle nut (DIN 935)", nut_castle, _PLAIN_FIELDS),
    ("nut_thin", "Thin lock nut (DIN 439)", nut_thin, _PLAIN_FIELDS),
    ("nut_coupler", "Coupling nut", nut_coupler, _PLAIN_FIELDS),
    ("nut_tslot", "T-slot nut (extrusion)", nut_tslot, _RING_FIELDS),
    ("nut_rivet", "Rivet nut (rivnut)", nut_rivet, _RING_FIELDS),
    ("insert_heat_set", "Heat-set insert (brass)", insert_heat_set,
     _RING_FIELDS),
    ("washer_flat", "Flat washer (DIN 125)", washer_flat, _RING_FIELDS),
    ("washer_penny", "Penny (fender) washer", washer_penny,
     _RING_FIELDS),
    ("washer_spring", "Spring washer, split", washer_spring,
     _RING_FIELDS),
    ("washer_star", "Star washer, external teeth", washer_star,
     _RING_FIELDS),
    ("washer_belleville", "Belleville disc spring", washer_belleville,
     _RING_FIELDS),
    ("pin_dowel", "Dowel pin, ground", pin_dowel, _PIN_FIELDS),
    ("pin_clevis", "Clevis pin, holed", pin_clevis, _PIN_FIELDS),
    ("pin_split", "Split pin (cotter)", pin_split, _PIN_FIELDS),
    ("pin_r_clip", "R-clip (hairpin cotter)", pin_r, _PIN_FIELDS),
    ("circlip_external", "Circlip, external (DIN 471)",
     circlip_external, _RING_FIELDS),
    ("circlip_internal", "Circlip, internal (DIN 472)",
     circlip_internal, _RING_FIELDS),
    ("rivet_solid", "Rivet, solid dome head", rivet_solid, _PIN_FIELDS),
    ("rivet_blind", "Rivet, blind (pop)", rivet_blind, _PIN_FIELDS),
    ("standoff_hex", "Hex standoff, male-female", standoff_hex,
     _RING_FIELDS),
    ("spacer_round", "Round spacer, plain", spacer_round, _RING_FIELDS),
]


def _builder(func):
    def build(dims):
        return func(_dims(dims, BOLT_SIZES))
    return build


PARTS = {
    part_id: dict(label=label, category=CATEGORY, sizes=BOLT_SIZES,
                  fields=fields, build=_builder(func))
    for part_id, label, func, fields in _PARTS
}
