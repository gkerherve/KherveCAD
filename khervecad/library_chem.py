"""Chemistry & lab-glassware parts for the parts library.

Beakers, flasks, test tubes, graduated cylinders, funnels, a Petri
dish, a watch glass, a burette, a test-tube rack and a retort stand.
Glassware is a revolved thin-wall cross-section (rotate_extrude of a
wall profile), so each vessel is genuinely hollow *without* a boolean
— which means the built-in preview shows it correctly even when
OpenSCAD is not installed. Parts are ordinary node subtrees and stay
fully editable after insertion.

Registered into ``library.PARTS`` via ``PARTS`` here, each entry
carrying a ``build`` callable, so ``library.build_part`` dispatches to
it. Sizes pre-fill common volumes; any dimension can be edited first.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from .model import CadNode

CATEGORY = "Chemistry"

#: material colours.
GLASS = "#cfe8ee"        # pale borosilicate
METAL = "#9aa0a8"
METAL_DK = "#5f646c"
WOOD = "#c8a06a"
WHITE = "#eef1f3"
RUBBER = "#37393d"       # dropper bulb / tubing
PLASTIC = "#e6ebee"      # wash-bottle body
CERAMIC = "#d8cbb0"      # wire-gauze centre
DARK = "#2b2e33"         # hotplate top / screens
BRASS = "#c69a4c"        # burner / fittings


# ----------------------------------------------------------- primitives

def _cyl(name, radius, height, z=0.0, x=0.0, y=0.0, r2=None,
         segments=96):
    return CadNode("cylinder", name, dict(
        x=x, y=y, z=z, height=height, radius_bottom=radius,
        radius_top=radius if r2 is None else r2,
        segments=segments, center=False))


def _col(node, color, name=None, alpha=1.0):
    """Wrap *node* in an OpenSCAD color() node."""
    c = CadNode("color", name or "Colour",
                dict(color=color, alpha=alpha))
    c.add(node)
    return c


def _revolve(name, profile, color=GLASS, segments=120, alpha=1.0):
    """A colour-wrapped rotate_extrude of a (radius, height) profile."""
    rev = CadNode("rotate_extrude", name,
                  dict(angle=360.0, segments=segments))
    rev.add(CadNode("polygon", f"{name} profile",
                    dict(x=0.0, y=0.0,
                         points=[[round(r, 4), round(z, 4)]
                                 for r, z in profile])))
    return _col(rev, color, name=f"{name} glass", alpha=alpha)


def _arc(cx, cz, radius, a0, a1, n):
    """Points on a circle arc (degrees), inclusive."""
    return [(cx + radius * math.cos(math.radians(a)),
             cz + radius * math.sin(math.radians(a)))
            for a in [a0 + (a1 - a0) * i / n for i in range(n + 1)]]


def _dims(dims, sizes):
    """Size-table defaults overlaid with any edited field values."""
    entry = sizes.get(dims.get("_size", ""),
                      next(iter(sizes.values())))
    out = dict(entry)
    out.update({k: v for k, v in dims.items()
                if k != "_size" and v is not None})
    return out


# --------------------------------------------------------------- vessels

def _cup_profile(r_out, height, wall, floor):
    """A straight-walled hollow cup (beaker / cylinder body)."""
    r_in = max(r_out - wall, 0.1)
    return [(0.0, 0.0), (r_out, 0.0), (r_out, height),
            (r_in, height), (r_in, floor), (0.0, floor)]


def build_beaker(dims):
    p = _dims(dims, BEAKER_SIZES)
    r = p["d"] / 2.0
    prof = _cup_profile(r, p["h"], p["wall"], p["wall"])
    # a small pour rim: flare the top lip out slightly
    prof[3] = (r - p["wall"] * 0.5, p["h"])
    return _revolve("Beaker", prof)


def build_graduated_cylinder(dims):
    p = _dims(dims, CYLINDER_SIZES)
    r = p["d"] / 2.0
    foot = p["d"] * 0.85
    prof = [(0.0, 0.0), (foot, 0.0), (foot, 4.0),
            (r + p["wall"], 6.0), (r, p["h"]),
            (r - p["wall"], p["h"]), (r - p["wall"], 6.0),
            (0.0, 6.0)]
    return _revolve("Graduated cylinder", prof)


def build_test_tube(dims):
    p = _dims(dims, TUBE_SIZES)
    r, h, w = p["d"] / 2.0, p["h"], p["wall"]
    # hemispherical bottom, straight body, open top
    outer = _arc(0.0, r, r, -90.0, 0.0, 16) + [(r, h)]
    inner = [(r - w, h)] + _arc(0.0, r, r - w, 0.0, -90.0, 16)
    return _revolve("Test tube", outer + inner, segments=64)


def build_erlenmeyer(dims):
    p = _dims(dims, FLASK_SIZES)
    rb, rn, h, w = p["d"] / 2.0, p["neck"] / 2.0, p["h"], p["wall"]
    hn = p["h"] * 0.28                    # neck height
    outer = [(0.0, 0.0), (rb, 0.0), (rn, h - hn), (rn, h)]
    inner = [(rn - w, h), (rn - w, h - hn), (rb - w, w), (0.0, w)]
    return _revolve("Erlenmeyer flask", outer + inner)


def build_round_flask(dims):
    p = _dims(dims, FLASK_SIZES)
    rb, rn, h, w = p["d"] / 2.0, p["neck"] / 2.0, p["h"], p["wall"]
    a_top = math.degrees(math.acos(min(rn / rb, 0.999)))
    outer = _arc(0.0, rb, rb, -90.0, a_top, 28) + [(rn, h)]
    ri = rb - w
    a_top_i = math.degrees(math.acos(min((rn - w) / ri, 0.999)))
    inner = [(rn - w, h)] + _arc(0.0, rb, ri, a_top_i, -90.0, 28)
    return _revolve("Round-bottom flask", outer + inner)


def build_funnel(dims):
    p = _dims(dims, FUNNEL_SIZES)
    rc, rs, w = p["d"] / 2.0, p["stem"] / 2.0, p["wall"]
    cone_h, stem_h = p["h"] * 0.55, p["h"] * 0.45
    outer = [(rs, 0.0), (rs, stem_h), (rc, stem_h + cone_h)]
    inner = [(rc - w, stem_h + cone_h), (rs - w, stem_h),
             (rs - w, 0.0)]
    return _revolve("Funnel", outer + inner)


def build_burette(dims):
    p = _dims(dims, BURETTE_SIZES)
    r, h, w = p["d"] / 2.0, p["h"], p["wall"]
    tip_h = 14.0
    outer = [(0.0, 0.0), (0.8, 0.0), (r * 0.35, tip_h),   # tapered tip
             (r, tip_h + 6.0), (r, h), (r - w, h),
             (r - w, tip_h + 6.0), (r * 0.35 - w * 0.4, tip_h),
             (0.0, tip_h)]
    part = CadNode("union", "Burette")
    part.add(_revolve("Burette", outer, segments=64))
    # PTFE stopcock: a small barrel across the tube near the tip
    barrel = CadNode("rotate", "Stopcock body", dict(x=0.0, y=90.0,
                                                     z=0.0))
    barrel.add(_cyl("Barrel", r * 0.7, r * 3.0, x=0.0, z=-r * 1.5,
                    segments=32))
    lift = CadNode("translate", "Stopcock at tip",
                   dict(x=0.0, y=0.0, z=tip_h + 3.0))
    lift.add(barrel)
    part.add(_col(lift, WHITE, name="Stopcock"))
    return part


def build_petri_dish(dims):
    p = _dims(dims, PETRI_SIZES)
    r, h, w = p["d"] / 2.0, p["h"], 1.5
    base = _cup_profile(r, h, w, w)
    lid = _cup_profile(r + 1.2, h * 0.8, w, w)
    part = CadNode("union", "Petri dish")
    part.add(_revolve("Dish", base, alpha=1.0))
    lift = CadNode("translate", "Lid on top",
                   dict(x=0.0, y=0.0, z=h + h * 0.8))
    inverted = CadNode("rotate", "Invert lid", dict(x=180.0, y=0.0,
                                                    z=0.0))
    inverted.add(_revolve("Lid", lid, alpha=1.0))
    lift.add(inverted)
    part.add(lift)
    return part


def build_watch_glass(dims):
    p = _dims(dims, PETRI_SIZES)
    r = p["d"] / 2.0
    # shallow spherical cap (a flat sphere); rim on the z=0 plane
    sr = r * 2.5
    cz = -math.sqrt(max(sr ** 2 - r ** 2, 0.0))
    rim_a = math.degrees(math.atan2(-cz, r))
    top = _arc(0.0, cz, sr, rim_a, 90.0, 28)     # (r,0) up to (0,rise)
    return _revolve("Watch glass", [(0.0, 0.0)] + top, segments=64)


# ----------------------------------------------------------- lab hardware

def build_test_tube_rack(dims):
    p = _dims(dims, RACK_SIZES)
    n = max(int(p["holes"]), 1)
    hole_d = p["hole_d"]
    pitch = hole_d + 8.0
    length = pitch * n + 8.0
    width = hole_d + 16.0
    part = CadNode("difference", "Test-tube rack")
    body = CadNode("union", "Rack body")
    part.add(body)
    # top plate with holes + base plate + end posts
    body.add(CadNode("cube", "Top plate", dict(
        x=-length / 2.0, y=-width / 2.0, z=55.0, width=length,
        depth=width, height=8.0, center=False)))
    body.add(CadNode("cube", "Base plate", dict(
        x=-length / 2.0, y=-width / 2.0, z=0.0, width=length,
        depth=width, height=8.0, center=False)))
    for sx in (-1.0, 1.0):
        body.add(CadNode("cube", "End post", dict(
            x=sx * (length / 2.0 - 8.0), y=-width / 2.0, z=0.0,
            width=8.0, depth=width, height=63.0, center=False)))
    holes = CadNode("for_loop", "Tube holes", dict(
        variable="i", start=0.0, end=float(n - 1), step=1.0))
    holes.add(_cyl("Hole", hole_d / 2.0, 12.0,
                   x=f"{pitch} * (i - {(n - 1) / 2.0})",
                   z=53.0, segments=32))
    part.add(holes)
    return _col(part, WOOD, name="Rack")


def build_retort_stand(dims):
    p = _dims(dims, STAND_SIZES)
    base_l, base_w, base_t = p["base"], p["base"] * 0.62, 12.0
    rod_h, rod_d = p["h"], 12.0
    part = CadNode("union", "Retort stand")
    part.add(_col(CadNode("cube", "Base", dict(
        x=-base_l * 0.3, y=-base_w / 2.0, z=0.0, width=base_l,
        depth=base_w, height=base_t, center=False)), METAL_DK,
        name="Base"))
    part.add(_col(_cyl("Rod", rod_d / 2.0, rod_h,
                       x=-base_l * 0.3 + rod_d, z=base_t), METAL,
                  name="Rod"))
    # a boss head + clamp arm near the top
    boss = CadNode("union", "Clamp")
    boss.add(_cyl("Boss", rod_d, rod_d * 1.6,
                  x=-base_l * 0.3 + rod_d, z=rod_h * 0.75,
                  segments=32))
    arm = CadNode("rotate", "Arm", dict(x=0.0, y=90.0, z=0.0))
    arm.add(_cyl("Arm rod", rod_d * 0.4, base_l * 0.55,
                 x=0.0, z=-base_l * 0.5, segments=24))
    lift = CadNode("translate", "Arm at boss",
                   dict(x=-base_l * 0.3 + rod_d, y=0.0,
                        z=rod_h * 0.75 + rod_d * 0.8))
    lift.add(arm)
    boss.add(lift)
    part.add(_col(boss, METAL, name="Clamp"))
    return part


# ------------------------------------------------ more glass + equipment

def _arm(name, radius, length, at_z, angle=45.0, color=GLASS):
    """A tube leaving the axis at *angle* (deg from vertical), based at
    height *at_z* — condenser side arms, wash-bottle nozzles, etc."""
    base = CadNode("translate", f"{name} base", dict(x=0.0, y=0.0,
                                                     z=at_z))
    rot = CadNode("rotate", f"{name} angle", dict(x=0.0, y=angle,
                                                  z=0.0))
    rot.add(_cyl(name, radius, length, segments=24))
    base.add(rot)
    return _col(base, color, name)


def build_volumetric_flask(dims):
    p = _dims(dims, VOLU_SIZES)
    rb, rn, h, w = p["d"] / 2.0, p["neck"] / 2.0, p["h"], p["wall"]
    base_r, bz = rb * 0.5, h * 0.30
    sh = h * 0.5                          # shoulder
    outer = [(0.0, 0.0), (base_r, 0.0), (rb, bz), (rb, bz + h * 0.06),
             (rn, sh), (rn, h)]
    inner = [(rn - w, h), (rn - w, sh), (rb - w, bz + h * 0.06),
             (rb - w, bz), (base_r - w, w), (0.0, w)]
    return _revolve("Volumetric flask", outer + inner, segments=96)


def build_separating_funnel(dims):
    p = _dims(dims, SEP_SIZES)
    r, h, w = p["d"] / 2.0, p["h"], 1.6
    stem_h = h * 0.16
    rs = max(r * 0.14, 2.0)
    top = h
    outer = [(rs, 0.0), (rs, stem_h), (r, top * 0.55), (r, top)]
    inner = [(r - w, top), (r - w, top * 0.55),
             (max(rs - w, 0.6), stem_h), (max(rs - w, 0.6), 0.0)]
    part = CadNode("union", "Separating funnel")
    part.add(_revolve("Funnel body", outer + inner, segments=80))
    # PTFE stopcock across the neck + conical stopper on top
    barrel = CadNode("rotate", "Stopcock", dict(x=0.0, y=90.0, z=0.0))
    barrel.add(_cyl("Barrel", rs * 1.6, r * 1.1, x=0.0, z=-r * 0.55,
                    segments=24))
    lift = CadNode("translate", "Stopcock pos",
                   dict(x=0.0, y=0.0, z=stem_h + 6.0))
    lift.add(barrel)
    part.add(_col(lift, WHITE, "Stopcock"))
    part.add(_col(_cyl("Stopper", r * 0.5, r * 0.4, z=top, r2=r * 0.34,
                       segments=32), GLASS, "Stopper"))
    return part


def build_condenser(dims):
    p = _dims(dims, CONDENSER_SIZES)
    L, rj, ri, w = p["length"], p["jacket_d"] / 2.0, \
        p["inner_d"] / 2.0, 1.4
    js, je = L * 0.12, L * 0.88
    part = CadNode("union", "Liebig condenser")
    # outer water jacket (open-ended shell) + full-length inner tube
    part.add(_revolve("Jacket", [(rj - w, js), (rj, js), (rj, je),
                                 (rj - w, je)], segments=64))
    part.add(_revolve("Inner tube", [(ri - w, 0.0), (ri, 0.0), (ri, L),
                                     (ri - w, L)], segments=48))
    # two water side-arms near the ends
    part.add(_arm("Water out", ri * 0.7, rj * 1.6, je - rj * 0.4, 55.0))
    part.add(_arm("Water in", ri * 0.7, rj * 1.6, js + rj * 0.4, 125.0))
    return part


def build_pipette(dims):
    p = _dims(dims, PIPETTE_SIZES)
    L, rb, rt, w = p["length"], p["bulb_d"] / 2.0, p["tip_d"] / 2.0, 0.8
    lower, bc = L * 0.32, L * 0.5
    hb = rb * 0.7
    outer = [(0.6, 0.0), (rt, L * 0.05), (rt, lower), (rb, bc - hb),
             (rb, bc + hb), (rt, bc + hb + 6.0), (rt, L)]
    inner = [(rt - w, L), (rt - w, bc + hb + 6.0), (rb - w, bc + hb),
             (rb - w, bc - hb), (rt - w, lower), (rt - w, L * 0.05),
             (0.6, 0.0)]
    return _revolve("Volumetric pipette", outer + inner, segments=64)


def build_dropper(dims):
    p = _dims(dims, DROPPER_SIZES)
    L, rt = p["length"], p["tube_d"] / 2.0
    part = CadNode("union", "Dropper")
    # thin glass tube, tapered tip
    prof = [(0.5, 0.0), (rt, L * 0.08), (rt, L * 0.72),
            (rt - 0.6, L * 0.72), (rt - 0.6, L * 0.1), (0.5, 0.0)]
    part.add(_revolve("Glass tube", prof, segments=32))
    # rubber teat bulb on top
    bulb = _cyl("Bulb", rt * 2.4, L * 0.24, z=L * 0.72, r2=rt * 1.4,
                segments=32)
    part.add(_col(bulb, RUBBER, "Bulb"))
    return part


def build_bunsen_burner(dims):
    p = _dims(dims, BURNER_SIZES)
    base_r, h, br = p["base"] / 2.0, p["h"], p["barrel"] / 2.0
    part = CadNode("union", "Bunsen burner")
    part.add(_col(_cyl("Base", base_r, 12.0, r2=base_r * 0.6,
                       segments=48), METAL_DK, "Base"))
    part.add(_col(_cyl("Barrel", br, h - 12.0, z=12.0, segments=32),
                  METAL, "Barrel"))
    # gas inlet spigot at the base + needle valve
    part.add(_arm("Gas inlet", br * 0.5, base_r * 1.4, 16.0, 90.0,
                  BRASS))
    part.add(_col(_cyl("Collar", br * 1.25, 14.0, z=20.0, segments=32),
                  METAL_DK, "Air collar"))
    return part


def build_hotplate(dims):
    p = _dims(dims, HOTPLATE_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    plate_r = p["plate"] / 2.0
    part = CadNode("union", "Hotplate stirrer")
    part.add(_col(CadNode("cube", "Body", dict(
        x=-w / 2.0, y=-d / 2.0, z=0.0, width=w, depth=d, height=h,
        center=False)), METAL, "Body"))
    part.add(_col(_cyl("Top plate", plate_r, 6.0, y=-d * 0.15, z=h,
                       segments=48), DARK, "Top plate"))
    # two control knobs on the front face
    for sx in (-1.0, 1.0):
        knob = CadNode("rotate", "Knob axis", dict(x=-90.0, y=0.0,
                                                   z=0.0))
        knob.add(_cyl("Knob", 12.0, 10.0, segments=24))
        lift = CadNode("translate", "Knob pos",
                       dict(x=sx * w * 0.25, y=-d / 2.0, z=h * 0.35))
        lift.add(knob)
        part.add(_col(lift, DARK, "Knob"))
    return part


def build_tripod(dims):
    p = _dims(dims, TRIPOD_SIZES)
    r, h = p["ring_d"] / 2.0, p["h"]
    part = CadNode("union", "Tripod")
    # top ring (thin annular disc)
    part.add(_revolve("Ring", [(r - 4.0, h), (r + 4.0, h),
                               (r + 4.0, h + 6.0), (r - 4.0, h + 6.0)],
                      color=METAL, segments=48))
    legs = CadNode("for_loop", "Legs", dict(variable="a", start=0.0,
                   end=240.0, step=120.0))
    rot = CadNode("rotate", "Leg angle", dict(x=0.0, y=0.0, z="a"))
    leg = CadNode("rotate", "Splay", dict(x=0.0, y=12.0, z=0.0))
    leg.add(_cyl("Leg", 5.0, h + 4.0, x=r * 0.9, segments=16))
    rot.add(leg)
    legs.add(rot)
    part.add(_col(legs, METAL, "Legs"))
    return part


def build_wire_gauze(dims):
    p = _dims(dims, GAUZE_SIZES)
    s = p["side"]
    part = CadNode("union", "Wire gauze")
    part.add(_col(CadNode("cube", "Mesh", dict(
        x=-s / 2.0, y=-s / 2.0, z=0.0, width=s, depth=s, height=1.2,
        center=False)), METAL, "Mesh"))
    part.add(_col(_cyl("Ceramic centre", s * 0.32, 1.6, z=0.6,
                       segments=48), CERAMIC, "Ceramic"))
    return part


def build_gas_cylinder(dims):
    p = _dims(dims, GAS_SIZES)
    r, h = p["d"] / 2.0, p["h"]
    color = GAS_COLORS.get(dims.get("_size", ""), "#3b7a4b")
    part = CadNode("union", "Gas cylinder")
    # body + rounded shoulder (revolved) so no boolean, colour-coded
    shoulder = r * 0.9
    prof = [(0.0, 0.0), (r, 0.0), (r, h),
            (r * 0.55, h + shoulder), (r * 0.28, h + shoulder)]
    part.add(_revolve("Bottle", prof, color=color, segments=64))
    # neck + valve + guard
    part.add(_col(_cyl("Neck", r * 0.28, 30.0, z=h + shoulder,
                       segments=24), METAL_DK, "Neck"))
    part.add(_col(_cyl("Valve", r * 0.16, 26.0, z=h + shoulder + 30.0,
                       segments=16), BRASS, "Valve"))
    part.add(_arm("Outlet", r * 0.08, r * 0.6, h + shoulder + 40.0,
                  90.0, BRASS))
    return part


def build_balance(dims):
    p = _dims(dims, BALANCE_SIZES)
    w, d, h = p["w"], p["d"], p["h"]
    part = CadNode("union", "Analytical balance")
    # base with a sloped display block
    part.add(_col(CadNode("cube", "Base", dict(
        x=-w / 2.0, y=-d / 2.0, z=0.0, width=w, depth=d,
        height=h * 0.34, center=False)), METAL, "Base"))
    part.add(_col(CadNode("cube", "Display", dict(
        x=-w * 0.34, y=-d / 2.0 - 6.0, z=8.0, width=w * 0.68,
        depth=8.0, height=h * 0.16, center=False)), DARK, "Display"))
    # glass draught shield + weighing pan inside
    part.add(_col(CadNode("cube", "Draught shield", dict(
        x=-w / 2.0, y=-d * 0.18, z=h * 0.34, width=w,
        depth=d * 0.8, height=h * 0.66, center=False)), GLASS,
        "Shield"))
    part.add(_col(_cyl("Pan", w * 0.22, 4.0, y=d * 0.1,
                       z=h * 0.34 + 4.0, segments=48), METAL,
                  "Pan"))
    return part


def build_wash_bottle(dims):
    p = _dims(dims, WASH_SIZES)
    r, h, w = p["d"] / 2.0, p["h"], 1.6
    part = CadNode("union", "Wash bottle")
    body = [(0.0, 0.0), (r, 0.0), (r, h * 0.72),
            (r * 0.55, h * 0.86), (r * 0.55, h),
            (r * 0.55 - w, h), (r * 0.55 - w, h * 0.86),
            (r - w, h * 0.72), (r - w, w), (0.0, w)]
    part.add(_revolve("Bottle", body, color=PLASTIC, segments=64))
    part.add(_col(_cyl("Cap", r * 0.62, 14.0, z=h, segments=32),
                  DARK, "Cap"))
    # bent delivery nozzle out of the cap
    part.add(_arm("Nozzle up", r * 0.14, h * 0.5, h + 10.0, 8.0,
                  PLASTIC))
    part.add(_arm("Nozzle tip", r * 0.14, r * 1.4,
                  h + 10.0 + h * 0.48, 100.0, PLASTIC))
    return part


# --------------------------------------------------------------- registry

BEAKER_SIZES = {
    "50 mL": dict(d=42.0, h=60.0, wall=1.2),
    "100 mL": dict(d=50.0, h=70.0, wall=1.3),
    "250 mL": dict(d=70.0, h=95.0, wall=1.5),
    "500 mL": dict(d=85.0, h=120.0, wall=1.6),
    "1 L": dict(d=105.0, h=145.0, wall=1.8),
}
CYLINDER_SIZES = {
    "10 mL": dict(d=15.0, h=140.0, wall=1.2),
    "50 mL": dict(d=24.0, h=195.0, wall=1.3),
    "100 mL": dict(d=30.0, h=250.0, wall=1.5),
    "250 mL": dict(d=40.0, h=320.0, wall=1.6),
}
TUBE_SIZES = {
    "12 × 75 mm": dict(d=12.0, h=75.0, wall=0.9),
    "16 × 100 mm": dict(d=16.0, h=100.0, wall=1.0),
    "18 × 150 mm": dict(d=18.0, h=150.0, wall=1.1),
}
FLASK_SIZES = {
    "100 mL": dict(d=64.0, neck=22.0, h=105.0, wall=1.4),
    "250 mL": dict(d=85.0, neck=28.0, h=145.0, wall=1.6),
    "500 mL": dict(d=105.0, neck=34.0, h=180.0, wall=1.8),
}
FUNNEL_SIZES = {
    "Small (50 mm)": dict(d=50.0, stem=8.0, h=90.0, wall=1.2),
    "Medium (75 mm)": dict(d=75.0, stem=10.0, h=130.0, wall=1.4),
    "Large (100 mm)": dict(d=100.0, stem=12.0, h=170.0, wall=1.5),
}
BURETTE_SIZES = {
    "25 mL": dict(d=13.0, h=350.0, wall=1.1),
    "50 mL": dict(d=15.0, h=520.0, wall=1.2),
}
PETRI_SIZES = {
    "60 mm": dict(d=60.0, h=15.0),
    "90 mm": dict(d=90.0, h=16.0),
    "100 mm": dict(d=100.0, h=18.0),
}
RACK_SIZES = {
    "6 × 16 mm": dict(holes=6.0, hole_d=17.0),
    "12 × 16 mm": dict(holes=12.0, hole_d=17.0),
    "6 × 20 mm": dict(holes=6.0, hole_d=21.0),
}
STAND_SIZES = {
    "Standard": dict(base=160.0, h=450.0),
    "Tall": dict(base=200.0, h=750.0),
}
VOLU_SIZES = {
    "100 mL": dict(d=62.0, neck=15.0, h=170.0, wall=1.3),
    "250 mL": dict(d=80.0, neck=17.0, h=220.0, wall=1.4),
    "500 mL": dict(d=100.0, neck=19.0, h=270.0, wall=1.5),
}
SEP_SIZES = {
    "100 mL": dict(d=58.0, h=200.0),
    "250 mL": dict(d=78.0, h=260.0),
    "500 mL": dict(d=95.0, h=320.0),
}
CONDENSER_SIZES = {
    "Liebig 200 mm": dict(length=280.0, jacket_d=30.0, inner_d=12.0),
    "Liebig 300 mm": dict(length=400.0, jacket_d=32.0, inner_d=13.0),
}
PIPETTE_SIZES = {
    "10 mL": dict(length=330.0, bulb_d=18.0, tip_d=4.0),
    "25 mL": dict(length=400.0, bulb_d=24.0, tip_d=5.0),
}
DROPPER_SIZES = {
    "Pasteur 150 mm": dict(length=150.0, tube_d=6.0),
    "Pasteur 230 mm": dict(length=230.0, tube_d=7.0),
}
BURNER_SIZES = {
    "Standard": dict(base=65.0, h=130.0, barrel=13.0),
}
HOTPLATE_SIZES = {
    "Standard": dict(w=220.0, d=260.0, h=110.0, plate=150.0),
    "Large": dict(w=300.0, d=340.0, h=130.0, plate=200.0),
}
TRIPOD_SIZES = {
    "Standard": dict(ring_d=110.0, h=200.0),
    "Tall": dict(ring_d=130.0, h=300.0),
}
GAUZE_SIZES = {
    "125 mm": dict(side=125.0),
    "150 mm": dict(side=150.0),
}
#: gas cylinders are colour-coded like the carpet squares.
GAS_COLORS = {
    "Nitrogen (black)": "#2b2e33", "Oxygen (white)": "#e6ebee",
    "Argon (green)": "#3b9a5a", "Helium (brown)": "#7a5230",
    "CO₂ (grey)": "#8a9099", "Hydrogen (red)": "#c0392b",
}
GAS_SIZES = {name: dict(d=230.0, h=1200.0, color=hexcol)
             for name, hexcol in GAS_COLORS.items()}
BALANCE_SIZES = {
    "Analytical": dict(w=230.0, d=340.0, h=340.0),
}
WASH_SIZES = {
    "250 mL": dict(d=64.0, h=150.0),
    "500 mL": dict(d=78.0, h=185.0),
}

_D = [("d", "Diameter")]
PARTS = {
    "chem_beaker": dict(label="Beaker (Griffin)", category=CATEGORY,
                        sizes=BEAKER_SIZES, build=build_beaker,
                        fields=_D + [("h", "Height"), ("wall", "Wall")]),
    "chem_cylinder": dict(label="Graduated cylinder", category=CATEGORY,
                          sizes=CYLINDER_SIZES,
                          build=build_graduated_cylinder,
                          fields=_D + [("h", "Height"),
                                       ("wall", "Wall")]),
    "chem_test_tube": dict(label="Test tube", category=CATEGORY,
                           sizes=TUBE_SIZES, build=build_test_tube,
                           fields=_D + [("h", "Length"),
                                        ("wall", "Wall")]),
    "chem_erlenmeyer": dict(label="Erlenmeyer (conical) flask",
                            category=CATEGORY, sizes=FLASK_SIZES,
                            build=build_erlenmeyer,
                            fields=_D + [("neck", "Neck Ø"),
                                         ("h", "Height"),
                                         ("wall", "Wall")]),
    "chem_round_flask": dict(label="Round-bottom flask",
                             category=CATEGORY, sizes=FLASK_SIZES,
                             build=build_round_flask,
                             fields=_D + [("neck", "Neck Ø"),
                                          ("h", "Height"),
                                          ("wall", "Wall")]),
    "chem_funnel": dict(label="Funnel", category=CATEGORY,
                        sizes=FUNNEL_SIZES, build=build_funnel,
                        fields=_D + [("stem", "Stem Ø"),
                                     ("h", "Height"), ("wall", "Wall")]),
    "chem_burette": dict(label="Burette (with stopcock)",
                         category=CATEGORY, sizes=BURETTE_SIZES,
                         build=build_burette,
                         fields=_D + [("h", "Length"), ("wall", "Wall")]),
    "chem_petri": dict(label="Petri dish (with lid)", category=CATEGORY,
                       sizes=PETRI_SIZES, build=build_petri_dish,
                       fields=_D + [("h", "Height")]),
    "chem_watch_glass": dict(label="Watch glass", category=CATEGORY,
                             sizes=PETRI_SIZES, build=build_watch_glass,
                             fields=_D),
    "chem_rack": dict(label="Test-tube rack", category=CATEGORY,
                      sizes=RACK_SIZES, build=build_test_tube_rack,
                      fields=[("holes", "Holes"),
                              ("hole_d", "Hole Ø")]),
    "chem_stand": dict(label="Retort stand + clamp", category=CATEGORY,
                       sizes=STAND_SIZES, build=build_retort_stand,
                       fields=[("base", "Base length"),
                               ("h", "Rod height")]),
    "chem_volumetric": dict(label="Volumetric flask", category=CATEGORY,
                            sizes=VOLU_SIZES,
                            build=build_volumetric_flask,
                            fields=_D + [("neck", "Neck Ø"),
                                         ("h", "Height"),
                                         ("wall", "Wall")]),
    "chem_sep_funnel": dict(label="Separating funnel", category=CATEGORY,
                            sizes=SEP_SIZES,
                            build=build_separating_funnel,
                            fields=_D + [("h", "Height")]),
    "chem_condenser": dict(label="Condenser (Liebig)", category=CATEGORY,
                           sizes=CONDENSER_SIZES, build=build_condenser,
                           fields=[("length", "Length"),
                                   ("jacket_d", "Jacket Ø"),
                                   ("inner_d", "Inner Ø")]),
    "chem_pipette": dict(label="Pipette (volumetric)", category=CATEGORY,
                         sizes=PIPETTE_SIZES, build=build_pipette,
                         fields=[("length", "Length"),
                                 ("bulb_d", "Bulb Ø"),
                                 ("tip_d", "Tube Ø")]),
    "chem_dropper": dict(label="Dropper (Pasteur)", category=CATEGORY,
                         sizes=DROPPER_SIZES, build=build_dropper,
                         fields=[("length", "Length"),
                                 ("tube_d", "Tube Ø")]),
    "chem_bunsen": dict(label="Bunsen burner", category=CATEGORY,
                        sizes=BURNER_SIZES, build=build_bunsen_burner,
                        fields=[("base", "Base Ø"), ("h", "Height"),
                                ("barrel", "Barrel Ø")]),
    "chem_hotplate": dict(label="Hotplate stirrer", category=CATEGORY,
                          sizes=HOTPLATE_SIZES, build=build_hotplate,
                          fields=[("w", "Width"), ("d", "Depth"),
                                  ("h", "Height"), ("plate", "Plate Ø")]),
    "chem_tripod": dict(label="Tripod", category=CATEGORY,
                        sizes=TRIPOD_SIZES, build=build_tripod,
                        fields=[("ring_d", "Ring Ø"),
                                ("h", "Height")]),
    "chem_gauze": dict(label="Wire gauze", category=CATEGORY,
                       sizes=GAUZE_SIZES, build=build_wire_gauze,
                       fields=[("side", "Side")]),
    "chem_gas_cylinder": dict(label="Gas cylinder (pick gas)",
                              category=CATEGORY, sizes=GAS_SIZES,
                              build=build_gas_cylinder,
                              fields=_D + [("h", "Body height")]),
    "chem_balance": dict(label="Analytical balance", category=CATEGORY,
                         sizes=BALANCE_SIZES, build=build_balance,
                         fields=[("w", "Width"), ("d", "Depth"),
                                 ("h", "Height")]),
    "chem_wash_bottle": dict(label="Wash bottle", category=CATEGORY,
                             sizes=WASH_SIZES, build=build_wash_bottle,
                             fields=_D + [("h", "Height")]),
}
