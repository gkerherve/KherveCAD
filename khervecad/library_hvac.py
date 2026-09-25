"""Air conditioning for the parts library (2026-09-25, the user's
request): a wall-mounted split-system INDOOR unit, its OUTDOOR
condenser, and a SPLIT SYSTEM that places both apart and pipes them
together.

A split system's refrigerant liquid line, its insulated gas
(suction) line and the condensate drain always run the same way in
real installations: out of the indoor unit's BACK (mounted high, near
the ceiling), straight through a short wall sleeve, DOWN the outside
wall face, then across to the outdoor unit's service valves (standing
on the ground outside). `_indoor_ports`/`_outdoor_ports` name those
three line ends in each unit's OWN frame, at the same relative
offsets in both, so `build_split_system` only has to bend a
wall / drop / run capsule chain between them. Kept in one module so
the two builders and the MCP instructions never drift apart (see
`mcp_server._INSTRUCTIONS`, "Air conditioning:").

Like the rest of the everyday-things drawer, every piece is a
multi-coloured union of boxes, rounded boxes, cylinders, capsules and
one revolved fan-guard ring, with NO booleans, so each part keeps its
own colour in the built-in preview. The front faces -Y, the back
(the wall side) +Y; both units stand with z = 0 at the floor (the
outdoor unit's feet, the indoor unit's own origin — its mounting
height is set by whatever places it, `rest_z` or a split system's own
`indoor_height`).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .library_home import _ball, _box, _dims, _paint, _rod
from .model import CadNode

CATEGORY = "Air conditioning"

WHITE = "#f2f0ea"
LIGHT_GREY = "#dedad0"
CASING_STEEL = "#c7cad0"
GRILLE_GREY = "#4d5257"
DARK = "#26282c"
ACCENT = "#9aa0a6"
COPPER = "#c8834a"
FOAM_BLACK = "#22242a"
DRAIN_WHITE = "#e7e4da"
LED_BLUE = "#3fd0ff"

#: BTU class -> published-style outline (mm) for both halves of the
#: system, so picking one size fills in a matched indoor + outdoor pair
AC_SIZES = {
    "9,000 BTU (2.5 kW)": dict(iw=799.0, ih=299.0, idp=199.0,
                               ow=700.0, oh=495.0, odp=245.0),
    "12,000 BTU (3.5 kW)": dict(iw=899.0, ih=299.0, idp=199.0,
                                ow=780.0, oh=540.0, odp=290.0),
    "18,000 BTU (5.0 kW)": dict(iw=999.0, ih=327.0, idp=224.0,
                                ow=845.0, oh=700.0, odp=320.0),
    "24,000 BTU (7.0 kW)": dict(iw=1080.0, ih=327.0, idp=224.0,
                                ow=900.0, oh=810.0, odp=320.0),
}

#: outdoor cabinet stands this high on rubber feet before its own body
FOOT_H = 30.0


# --------------------------------------------------------------- helpers
def _ring_y(name, x, y, z, r_in, r_out, t, color, material="Default",
            seg=48):
    """A flat annulus facing -Y, from *y* to *y* - *t* (a fan guard
    ring) — a revolved profile, no boolean; same nesting as
    `library_home._disc_y`."""
    move = CadNode("translate", name, dict(x=x, y=y, z=z))
    turn = CadNode("rotate", name, dict(x=90.0, y=0.0, z=0.0))
    ext = CadNode("rotate_extrude", name, dict(angle=360.0, segments=seg))
    ext.add(CadNode("polygon", f"{name} profile", dict(
        x=0.0, y=0.0, points=[[r_in, 0.0], [r_out, 0.0],
                              [r_out, t], [r_in, t]])))
    turn.add(ext)
    move.add(turn)
    return _paint(move, color, material)


def _object(name, node):
    """One piece of a multi-part assembly as its own Object, so it
    gets an exact render and keeps its own colour (see
    `library_vacuum._object`)."""
    comp = CadNode("component", name, dict(
        x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0, color="", alpha=1.0))
    comp.add(node)
    return comp


def _indoor_ports(w, d, h):
    """local (x, y, z) of the indoor unit's liquid / gas / drain line
    ends, at the BACK (y = d, flush with the wall)."""
    x0 = -w / 2 + 70.0
    z0 = min(30.0, h * 0.12)
    return {"liquid": (x0 - 16.0, d, z0), "gas": (x0 + 4.0, d, z0),
            "drain": (x0 + 30.0, d, z0 - 8.0)}


def _outdoor_ports(w, d, h):
    """local (x, y, z) of the outdoor unit's service-valve ends, at
    the BACK (y = d) — the far end of the same three lines, in the
    unit's own frame (z = 0 at the floor, feet included)."""
    x0 = -w / 2 + 70.0
    z0 = FOOT_H + min(70.0, h * 0.18)
    return {"liquid": (x0 - 16.0, d, z0), "gas": (x0 + 4.0, d, z0),
            "drain": (x0 + 30.0, d, z0 - 8.0)}


# ---------------------------------------------------------------- indoor
def build_indoor_unit(dims):
    """Wall-mounted split-system indoor unit: front faces -Y, back
    (y = d) flush against the wall it hangs on."""
    p = _dims(dims, AC_SIZES)
    w, h, d = p["iw"], p["ih"], p["idp"]
    part = CadNode("union", "AC indoor unit")
    part.add(_box("Cabinet", -w / 2, 0.0, 0.0, w, d, h, WHITE, r=18))
    part.add(_box("Intake lip", -w / 2 + 8, d - 4.0, h - 12.0, w - 16,
                  4.0, 12.0, LIGHT_GREY, r=4))
    vent_h = h * 0.30
    part.add(_box("Vent recess", -w / 2 + 24, -3.0, 8.0, w - 48, 5.0,
                  vent_h, LIGHT_GREY, r=8))
    fins = 6
    for i in range(fins):
        fz = 14.0 + i * (vent_h - 24.0) / (fins - 1)
        part.add(_box("Louvre", -w / 2 + 30, -5.0, fz, w - 60, 4.0, 3.0,
                      GRILLE_GREY))
    part.add(_box("Display", w * 0.26, -3.0, h * 0.46, 46.0, 4.0, 13.0,
                  DARK))
    part.add(_ball("LED", w * 0.26 + 10.0, -4.0, h * 0.46 + 6.5, 2.2,
                   LED_BLUE, material="Emissive"))
    part.add(_ball("Sensor", -w * 0.34, -1.0, h * 0.52, 3.0, DARK))
    part.add(_box("Accent strip", -w / 2 + 14, -4.0, h - 46.0, w - 28,
                  3.0, 4.0, ACCENT))
    part.add(_box("Wall bracket", -w / 2 + 20, d - 6.0, h * 0.5 - 12.0,
                  w - 40, 6.0, 24.0, "#8a8d92", material="Metal"))
    ports = _indoor_ports(w, d, h)
    for key, r, colour, material in (("liquid", 5.0, COPPER, "Metal"),
                                     ("gas", 9.5, FOAM_BLACK, "Rubber"),
                                     ("drain", 6.0, DRAIN_WHITE,
                                      "Default")):
        x, y, z = ports[key]
        part.add(_rod(f"{key.capitalize()} stub", (x, y - 20.0, z),
                      (x, y + 4.0, z), r, colour, material))
    return part


# --------------------------------------------------------------- outdoor
def build_outdoor_unit(dims):
    """Split-system outdoor condenser: front (the fan) faces -Y, back
    (y = d, the service valves) faces the wall it is piped through.
    Stands on four rubber feet, `FOOT_H` above z = 0."""
    p = _dims(dims, AC_SIZES)
    w, h, d = p["ow"], p["oh"], p["odp"]
    upper = CadNode("union", "AC outdoor unit")
    upper.add(_box("Cabinet", -w / 2, 0.0, 0.0, w, d, h, CASING_STEEL,
                   r=12, material="Metal"))
    fan_r = min(w, h) * 0.33
    fx, fz = 0.0, h * 0.52
    upper.add(_ring_y("Fan housing", fx, -2.0, fz, fan_r * 0.94,
                      fan_r + 10.0, 10.0, "#9a9ea4", "Metal"))
    for ring_r in (fan_r * 0.42, fan_r * 0.68, fan_r * 0.92):
        upper.add(_ring_y("Guard ring", fx, -8.0, fz, ring_r - 2.6,
                          ring_r, 3.0, GRILLE_GREY, "Metal"))
    spokes = 8
    for i in range(spokes):
        ang = math.radians(360.0 * i / spokes)
        ex = fx + math.cos(ang) * fan_r
        ez = fz + math.sin(ang) * fan_r
        upper.add(_rod("Spoke", (fx, -8.0, fz), (ex, -8.0, ez), 2.6,
                       GRILLE_GREY, "Metal"))
    upper.add(_ball("Hub", fx, -8.0, fz, fan_r * 0.16, GRILLE_GREY,
                    "Metal"))
    side_h = h * 0.6
    for i in range(10):
        yy = 8.0 + i * (d - 16.0) / 9.0
        upper.add(_box("Fin", w / 2 - 3.0, yy, h * 0.2, 3.0, 2.0, side_h,
                       "#b6bac0"))
    upper.add(_box("Nameplate", -w * 0.3, -2.0, h * 0.14, 60.0, 2.0, 20.0,
                   "#c7cad0"))
    ports = _outdoor_ports(w, d, h)
    for key, r, colour, material in (("liquid", 8.0, COPPER, "Metal"),
                                     ("gas", 12.0, COPPER, "Metal"),
                                     ("drain", 6.0, DRAIN_WHITE,
                                      "Default")):
        x, y, z = ports[key]
        zl = z - FOOT_H
        upper.add(_rod(f"{key.capitalize()} valve", (x, y - 24.0, zl),
                       (x, y + 4.0, zl), r, colour, material))
        if key != "drain":
            upper.add(_ball(f"{key.capitalize()} cap", x, y - 26.0, zl,
                            r * 1.3, DARK, "Metal"))
    lift = CadNode("translate", "AC outdoor unit",
                   dict(x=0.0, y=0.0, z=FOOT_H))
    lift.add(upper)
    part = CadNode("union", "AC outdoor unit")
    part.add(lift)
    for sx in (-1, 1):
        for sy in (0.18, 0.82):
            part.add(_box("Foot", sx * (w / 2 - 40) - 15.0, sy * d - 15.0,
                          0.0, 30.0, 30.0, FOOT_H, DARK, r=4))
    return part


# --------------------------------------------------------- split system
def build_split_system(dims):
    """Both units of one split system, piped together THROUGH A WALL:
    the liquid and (insulated) gas refrigerant lines and the
    condensate drain run from the indoor unit's back (mounted high),
    straight through a wall sleeve, DOWN the outside wall face, then
    across to the outdoor unit's service valves (standing on the
    ground outside) — this is the geometry the MCP instructions point
    an assistant at for "connect the air conditioning through the
    wall"."""
    p = _dims(dims, AC_SIZES)
    iw, ih, idp = p["iw"], p["ih"], p["idp"]
    ow, oh, odp = p["ow"], p["oh"], p["odp"]
    wall_t = p.get("wall_thickness", 200.0)
    x_off = p.get("outdoor_offset", 250.0)
    gap = p.get("outdoor_gap", 400.0)
    mount_h = p.get("indoor_height", 1900.0)

    part = CadNode("union", "Split AC system")

    indoor_pos = CadNode("translate", "Indoor unit",
                         dict(x=0.0, y=0.0, z=mount_h))
    indoor_pos.add(_object("Indoor unit", build_indoor_unit(dims)))
    part.add(indoor_pos)

    # the outdoor unit stands on its own feet at z = 0 — the ground
    # outside, not the indoor unit's height
    out_x, out_y = x_off, idp + wall_t + gap - odp
    outdoor_pos = CadNode("translate", "Outdoor unit",
                         dict(x=out_x, y=out_y, z=0.0))
    outdoor_pos.add(_object("Outdoor unit", build_outdoor_unit(dims)))
    part.add(outdoor_pos)

    in_ports = _indoor_ports(iw, idp, ih)
    out_ports = _outdoor_ports(ow, odp, oh)
    wall_face = idp + wall_t                  # outside face of the wall
    for key, r, colour, material in (("liquid", 5.0, COPPER, "Metal"),
                                     ("gas", 9.5, FOAM_BLACK, "Rubber"),
                                     ("drain", 6.0, DRAIN_WHITE,
                                      "Default")):
        ix, iy, iz = in_ports[key]
        a = (ix, iy, iz + mount_h)                     # indoor, world
        ox, oy, oz = out_ports[key]
        b = (ox + out_x, oy + out_y, oz)               # outdoor, world
        through = (ix, wall_face, a[2])       # clears the wall
        drop = (ix, wall_face, b[2])          # down the outside face
        part.add(_rod(f"{key.capitalize()} line (wall)", a, through, r,
                      colour, material))
        part.add(_rod(f"{key.capitalize()} line (drop)", through, drop,
                      r, colour, material))
        part.add(_rod(f"{key.capitalize()} line (run)", drop, b, r,
                      colour, material))

    cz = mount_h + in_ports["liquid"][2]
    cx = (in_ports["liquid"][0] + in_ports["drain"][0]) / 2.0
    part.add(_rod("Wall sleeve", (cx, idp - 2.0, cz),
                  (cx, wall_face + 2.0, cz), 34.0, LIGHT_GREY))
    return part


def _spec(label, build, fields=(), rest_z=0.0):
    return dict(label=label, category=CATEGORY, build=build,
               sizes=AC_SIZES, fields=list(fields), rest_z=rest_z)


PARTS = {
    "hvac_indoor_unit": _spec(
        "Split AC indoor unit (wall-mounted)", build_indoor_unit,
        [("iw", "Width"), ("ih", "Height"), ("idp", "Depth")],
        rest_z=1900.0),
    "hvac_outdoor_unit": _spec(
        "Split AC outdoor unit (condenser)", build_outdoor_unit,
        [("ow", "Width"), ("oh", "Height"), ("odp", "Depth")]),
    "hvac_split_system": _spec(
        "Split AC system (indoor + outdoor, piped through a wall)",
        build_split_system,
        [("wall_thickness", "Wall thickness"),
         ("outdoor_offset", "Outdoor unit sideways offset"),
         ("outdoor_gap", "Outdoor unit clearance from wall"),
         ("indoor_height", "Indoor unit mounting height")]),
}
