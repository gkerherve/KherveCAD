"""The City Builder's buildings (Qt-free): the OUTSIDE of a building,
detailed, and nothing inside.

A building is centred on its origin with its front facing -Y. Walls
wear a surface material the OpenGL shader textures from world position
(`glrender.SURFACES`: Brick, Concrete, Render, Stone; roofs Roof tiles
and Slate), so a brick wall has real courses and bonds at no triangle
cost. The detail that must be geometry is built from boxes, cylinders
and hulls — no booleans, so the preview is exact:

- punched windows: a white frame, the glass, a mullion and transom and
  a stone sill, all ONE loop body per facade (floor f × column c);
- curtain walls for blocks and towers: a glass ribbon per floor, metal
  fins per column, balconies on blocks;
- a plinth, a cornice, a door with its step and canopy, a shop front
  with sign and awning;
- pitched roofs: two tiled slopes, the gable walls, a ridge cap,
  fascia boards, gutters, bargeboards, chimneys with pots and a dormer;
  flat roofs: a parapet with coping, a stair housing, plant units and a
  water tank; a slate cone or a church spire with a cross.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from .model import CadNode

FLOOR_HEIGHT = 3000.0

#: style -> (floors range, roof, glazing, wall material)
STYLES = {
    "cottage": ((1, 2), "gable", "windows", "stone"),
    "house": ((2, 2), "hip", "windows", "brick"),
    "terrace": ((2, 3), "gable", "windows", "brick"),
    "shop": ((1, 2), "flat", "shopfront", "render"),
    "block": ((3, 7), "flat", "bands", "brick"),
    "tower": ((10, 30), "flat", "curtain", "concrete"),
    "round tower": ((3, 12), "cone", "bands", "concrete"),
    "L-shape": ((2, 3), "gable", "windows", "render"),
    "church": ((2, 2), "gable", "windows", "stone"),
}

ROOF_KINDS = ("gable", "hip", "flat", "cone")

#: wall kind -> (shader material, colour palette)
WALLS = {
    "brick": ("Brick", ["#9c4a32", "#a8583c", "#b5694a", "#8a3f2c",
                        "#c07a55", "#7d4636"]),
    "concrete": ("Concrete", ["#b9b6b0", "#a8a59f", "#c7c3bb", "#9b9993"]),
    "render": ("Render", ["#f2e6d0", "#e8d2b0", "#f4f1ea", "#e3b7a0",
                          "#d6c38f", "#b7c4c9", "#cfdcc8"]),
    "stone": ("Stone", ["#c9b99a", "#b8a888", "#d4c7ad", "#a89c86"]),
}
#: roof material -> palette
ROOFS = {
    "tiles": ("Roof tiles", ["#9a4a32", "#8d4a36", "#a65a3a", "#7a3b2e"]),
    "slate": ("Slate", ["#4e5156", "#5a5f66", "#3f4449"]),
}

WHITE = "#f3f1ec"
#: window glass is opaque and glossy: the Glass material caps alpha at
#: 0.45, and a dark pane over brick then simply vanished into the wall
GLASS = "#2f4556"
SILL = "#d8d2c4"
METAL = "#6d737a"
DOOR = "#5b3a29"
TRIM = "#e9e6df"
AWNINGS = ["#b83b3b", "#2f6f8f", "#3f8f4f", "#c8902e"]


class BuildingError(ValueError):
    """A building spec that cannot be built."""


def _f(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _num(v):
    v = round(float(v), 1)
    return str(int(v)) if v == int(v) else str(v)


def color(node, colour, material="Default", alpha=1.0, name=None):
    c = CadNode("color", name or node.name,
                dict(color=colour, alpha=alpha, material=material))
    c.add(node)
    return c


def group(name, children=()):
    g = CadNode("union", name, {})
    for ch in children:
        g.add(ch)
    return g


def box(name, x, y, z, w, d, h):
    return CadNode("cube", name, dict(x=x, y=y, z=z, width=w, depth=d,
                                      height=h, center=False))


def cyl(name, x, y, z, h, r0, r1=None, seg=8):
    return CadNode("cylinder", name, dict(
        x=x, y=y, z=z, height=h, radius_bottom=r0,
        radius_top=r0 if r1 is None else r1, segments=seg, center=False))


def turn(node, x=0.0, y=0.0, z=0.0, name="Turn"):
    r = CadNode("rotate", name, dict(x=x, y=y, z=z))
    r.add(node)
    return r


def move(node, x=0.0, y=0.0, z=0.0, name=None):
    t = CadNode("translate", name or node.name, dict(x=x, y=y, z=z))
    t.add(node)
    return t


def _hull(name, parts):
    h = CadNode("hull", name, {})
    for p in parts:
        h.add(p)
    return h


def loop(name, var, count, children):
    node = CadNode("for_loop", name, dict(variable=var, start=0.0,
                                          end=max(count - 1, 0), step=1.0,
                                          values=""))
    for ch in children:
        node.add(ch)
    return node


# ------------------------------------------------------------- facades
class Facade:
    """One wall face of a box wing: u runs along it (centred), `out`
    measures proud of the wall. Makes boxes in the building's frame."""

    def __init__(self, side, x0, y0, w, d):
        self.side = side
        self.x0, self.y0, self.w, self.d = x0, y0, w, d
        self.length = w if side in ("front", "back") else d

    def box(self, name, u, z, du, dz, out, depth=None):
        """A box spanning u..u+du along the face, z..z+dz up it, from
        `out - depth` to `out` proud of the wall (u, z may be
        expressions: strings are offset symbolically)."""
        depth = out if depth is None else depth
        x0, y0, w, d = self.x0, self.y0, self.w, self.d
        cu = _expr_add(u, (x0 + w / 2) if self.side in ("front", "back")
                       else (y0 + d / 2))
        if self.side == "front":
            return box(name, cu, y0 - out, z, du, depth, dz)
        if self.side == "back":
            return box(name, cu, y0 + d + out - depth, z, du, depth, dz)
        if self.side == "left":
            return box(name, x0 - out, cu, z, depth, du, dz)
        return box(name, x0 + w + out - depth, cu, z, depth, du, dz)


def _expr_add(u, k):
    if isinstance(u, str):
        return f"{u} + {_num(k)}" if abs(k) > 1e-9 else u
    return u + k


def punched_windows(f: Facade, floors, fh, z0=900.0, skip_door=False,
                    ww=1200.0, wh=1500.0, pitch=2800.0):
    """Framed windows with a sill, a mullion and a transom — one loop
    body per facade, so forty windows are a handful of nodes. Returns
    (loop, door_u) — door_u the gap the door takes on a front."""
    cols = int((f.length - 900.0) // pitch)
    if cols < 1 or floors < 1:
        return None, 0.0
    start = -(cols - 1) * pitch / 2.0 - ww / 2.0
    u = f"{_num(start)} + c * {_num(pitch)}"
    z = f"{_num(z0)} + fl * {_num(fh)}"
    zs = f"{_num(z0 - 90)} + fl * {_num(fh)}"
    zt = f"{_num(z0 + wh * 0.68)} + fl * {_num(fh)}"
    um = f"{_num(start + ww / 2 - 30)} + c * {_num(pitch)}"
    body = [
        color(f.box("Frame", _expr_add(u, -70), _zexpr(z, -70), ww + 140,
                    wh + 140, 45), WHITE, "Matte"),
        color(f.box("Glass", u, z, ww, wh, 55, 20), GLASS, "Plastic"),
        color(group("Glazing bars", [
            f.box("Mullion", um, z, 60, wh, 70, 30),
            f.box("Transom", u, zt, ww, 60, 70, 30)]), WHITE, "Matte"),
        color(f.box("Sill", _expr_add(u, -110), zs, ww + 220, 90, 140),
              SILL, "Stone"),
    ]
    inner = loop("Columns", "c", cols, body)
    outer = loop(f"{f.side.capitalize()} windows", "fl", floors, [inner])
    door_u = 0.0
    if skip_door:
        door_u = start + ww / 2 + pitch / 2 if cols >= 2 else (
            start + ww + 900 if start + ww + 1500 < f.length / 2 else 0.0)
    return outer, door_u


def _zexpr(z, k):
    return f"{z} + {_num(k)}" if k >= 0 else f"{z} - {_num(-k)}"


def curtain_wall(wings, floors, fh, fins=True, spandrel=None):
    """A glass ribbon round each wing per floor (one box a floor) and
    metal fins per column, full height (one box a column)."""
    glass, metal = [], []
    for x0, y0, w, d in wings:
        z = f"950 + fl * {_num(fh)}"
        glass.append(loop("Glass floors", "fl", floors, [
            box("Ribbon", x0 - 35, y0 - 35, z, w + 70, d + 70,
                fh * (0.55 if spandrel else 0.72))]))
        if not fins:
            continue
        H = floors * fh
        for side in ("front", "back", "left", "right"):
            fac = Facade(side, x0, y0, w, d)
            n = int(fac.length // 1500)
            if n < 2:
                continue
            step = fac.length / n
            u = f"{_num(-fac.length / 2 + step)} + c * {_num(step)} - 40"
            metal.append(loop(f"{side.capitalize()} fins", "c", n - 1, [
                fac.box("Fin", u, 0.0, 80, H, 160)]))
    out = [color(group("Curtain glass", glass), GLASS, "Plastic")]
    if metal:
        out.append(color(group("Fins", metal), METAL, "Metal"))
    return out


def door(f: Facade, u, wall_colour):
    """A panelled door in a white frame, a step and a small canopy."""
    return group("Entrance", [
        color(f.box("Door frame", u - 700, 0.0, 1400, 2400, 50), WHITE,
              "Matte"),
        color(f.box("Door", u - 550, 150.0, 1100, 2150, 70, 30), DOOR,
              "Matte"),
        color(f.box("Handle", u + 350, 1100.0, 60, 60, 110, 40), "#c9a54a",
              "Gold"),
        color(f.box("Step", u - 900, 0.0, 1800, 150, 500), SILL, "Stone"),
        color(f.box("Canopy", u - 900, 2550.0, 1800, 120, 800), wall_colour,
              "Matte"),
    ])


# --------------------------------------------------------------- roofs
def pitched_roof(kind, w, d, H, roof_col, roof_mat, wall_col, wall_mat,
                 chimney=True, dormer=False, pitch=35.0):
    """A gable or hip roof over a w x d footprint centred on the origin,
    the walls' top at H."""
    e = 450.0                                   # eave overhang
    t = 160.0                                   # tile layer
    along_x = w >= d
    span, length = (d, w) if along_x else (w, d)
    tan = math.tan(math.radians(pitch))
    rise = span / 2.0 * tan
    top = H + rise
    eave_z = H - e * tan

    def b(name, u, v, z, du, dv, h):
        return (box(name, u, v, z, du, dv, h) if along_x
                else box(name, v, u, z, dv, du, h))

    def c_along(name, u, v, z, du, r, seg=8):
        c = cyl(name, 0.0, 0.0, 0.0, du, r, seg=seg)
        if along_x:
            return move(turn(c, y=90.0), u, v, z, name)
        return move(turn(c, x=-90.0), v, u, z, name)

    parts = []
    if kind == "gable":
        ul, ll = -length / 2 - e, length + 2 * e
        slopes = group("Slopes", [
            _hull("Front slope", [b("Eave", ul, -span / 2 - e, eave_z, ll,
                                    1.0, t),
                                  b("Ridge", ul, -1.0, top, ll, 1.0, t)]),
            _hull("Back slope", [b("Eave", ul, span / 2 + e - 1, eave_z, ll,
                                   1.0, t),
                                 b("Ridge", ul, 0.0, top, ll, 1.0, t)])])
        parts.append(color(slopes, roof_col, roof_mat))
        gables = _hull("Gable walls", [
            b("Wall plate", -length / 2, -span / 2, H - 1, length, span, 1.0),
            b("Apex", -length / 2, -1.0, top - 2, length, 2.0, 1.0)])
        parts.append(color(gables, wall_col, wall_mat))
        barge = []
        for su in (-1, 1):
            uu = su * (length / 2 + e) - (60 if su > 0 else 0)
            for sv in (-1, 1):
                barge.append(_hull("Bargeboard", [
                    b("Low", uu, sv * (span / 2 + e) - (1 if sv > 0 else 0),
                      eave_z - 120, 60, 1.0, 260),
                    b("High", uu, -0.5, top - 120, 60, 1.0, 260 + t)]))
        parts.append(color(group("Bargeboards", barge), WHITE, "Matte"))
        ridge_len = ll
        ridge_u = ul
    else:                                       # hip
        rl = max(length - span, 10.0)
        parts.append(color(_hull("Hipped roof", [
            b("Eaves", -length / 2 - e, -span / 2 - e, eave_z, length + 2 * e,
              span + 2 * e, t),
            b("Ridge", -rl / 2, -1.0, top, rl, 2.0, t)]), roof_col, roof_mat))
        ridge_len, ridge_u = rl, -rl / 2
    # ridge cap, fascia and gutters along both eaves
    parts.append(color(c_along("Ridge cap", ridge_u, 0.0, top + t * 0.8,
                               ridge_len, 130.0), roof_col, "Matte"))
    trims, gutters = [], []
    fl = length + 2 * e
    for sv in (-1, 1):
        v = sv * (span / 2 + e) - (50 if sv > 0 else 0)
        trims.append(b("Fascia", -length / 2 - e, v, eave_z - 220, fl, 50,
                       240))
        gutters.append(c_along("Gutter", -length / 2 - e,
                               sv * (span / 2 + e + 60), eave_z - 160, fl,
                               75.0, seg=6))
    parts.append(color(group("Fascia", trims), WHITE, "Matte"))
    parts.append(color(group("Gutters", gutters), METAL, "Metal"))
    if chimney:
        cu = length * 0.28 - 350
        cz = H + rise * 0.35
        parts.append(color(b("Chimney", cu, -350, cz, 700, 700,
                             top - cz + 900), "#9c4a32", "Brick"))
        parts.append(color(b("Chimney cap", cu - 60, -410, top + 900, 820,
                             820, 110), SILL, "Stone"))
        for du in (200.0, 500.0):
            pot = cyl("Pot", 0.0, 0.0, top + 1010, 380, 110, 90)
            parts.append(color(move(pot, *((cu + du, 0.0) if along_x
                                           else (0.0, cu + du)), 0.0,
                                    name="Pot"), "#a65a3a", "Clay"))
    if dormer and length >= 8000 and span >= 6500:
        dv = -span / 2 + span * 0.18          # front edge on the slope
        dz = H + (dv + span / 2) * tan
        dw, dd, dh = 1900.0, span * 0.26, 1500.0
        dor = [
            color(b("Dormer cheeks", -dw / 2, dv, dz - 400, dw, dd, dh + 400),
                  wall_col, wall_mat),
            color(_hull("Dormer roof", [
                b("Eave", -dw / 2 - 150, dv - 150, dz + dh - 60, dw + 300,
                  dd + 150, 80),
                b("Ridge", -60, dv - 150, dz + dh + 600, 120, dd + 150, 80)]),
                roof_col, roof_mat),
            color(b("Dormer window", -dw / 2 + 250, dv - 40, dz + 100,
                    dw - 500, 60, dh - 350), GLASS, "Plastic"),
            color(b("Dormer frame", -dw / 2 + 180, dv - 25, dz + 30,
                    dw - 360, 30, dh - 210), WHITE, "Matte"),
        ]
        parts.extend(dor)
    return group("Roof", parts)


def flat_roof(w, d, H, tall=False, index=0):
    """Roof slab, a parapet with coping, a stair housing and plant."""
    pt, ph = 250.0, 900.0
    parts = [color(box("Roof slab", -w / 2, -d / 2, H, w, d, 200),
                   "#8a8580", "Concrete")]
    par = [box("Parapet", -w / 2, -d / 2, H, w, pt, ph),
           box("Parapet", -w / 2, d / 2 - pt, H, w, pt, ph),
           box("Parapet", -w / 2, -d / 2, H, pt, d, ph),
           box("Parapet", w / 2 - pt, -d / 2, H, pt, d, ph)]
    parts.append(color(group("Parapet", par), "#a8a59f", "Concrete"))
    cop = [box("Coping", -w / 2 - 60, -d / 2 - 60, H + ph, w + 120, pt + 120,
               80),
           box("Coping", -w / 2 - 60, d / 2 - pt - 60, H + ph, w + 120,
               pt + 120, 80),
           box("Coping", -w / 2 - 60, -d / 2 - 60, H + ph, pt + 120, d + 120,
               80),
           box("Coping", w / 2 - pt - 60, -d / 2 - 60, H + ph, pt + 120,
               d + 120, 80)]
    parts.append(color(group("Coping", cop), SILL, "Stone"))
    if w > 7000 and d > 6000:
        sx = w / 2 - 3600
        parts.append(color(box("Stair housing", sx, d / 2 - 3200, H + 200,
                               2600, 2400, 2600), "#b9b6b0", "Concrete"))
        units = []
        for k in range(2 if w > 12000 else 1):
            ux = -w / 2 + 1200 + k * 2200
            units.append(box("Plant unit", ux, -d / 2 + 1200, H + 200, 1600,
                             1100, 1100))
        parts.append(color(group("Plant", units), "#c9ccd0", "Metal"))
        fans = [cyl("Fan", -w / 2 + 2000 + k * 2200, -d / 2 + 1750, H + 1300,
                    40, 380, seg=8) for k in range(len(units))]
        parts.append(color(group("Fans", fans), "#50555b", "Metal"))
        if tall:
            parts.append(color(group("Water tank", [
                cyl("Tank", -w / 2 + 2600, d / 2 - 2600, H + 1400, 2200,
                    1100, seg=12),
                cyl("Tank lid", -w / 2 + 2600, d / 2 - 2600, H + 3600, 500,
                    1150, 200, seg=12)]), "#8f6b4e", "Matte"))
            legs = [box("Leg", -w / 2 + 2600 + sx_ * 700 - 60,
                        d / 2 - 2600 + sy * 700 - 60, H + 200, 120, 120,
                        1200) for sx_ in (-1, 1) for sy in (-1, 1)]
            parts.append(color(group("Tank legs", legs), METAL, "Metal"))
    return group("Roof", parts)


# ----------------------------------------------------------- buildings
def resolve(b: dict, index: int = 0) -> dict:
    """The building with every default filled in — what the dialog
    shows and what `build_building` reads."""
    style = b.get("style", "house")
    if style not in STYLES:
        raise BuildingError(f'Unknown building style "{style}"; use one of '
                            + ", ".join(STYLES))
    (lo, _hi), roof, _glazing, wall = STYLES[style]
    wall = b.get("wall") or wall
    if wall not in WALLS:
        raise BuildingError(f'Unknown wall "{wall}"; use one of '
                            + ", ".join(WALLS))
    roof = b.get("roof") or roof
    if roof not in ROOF_KINDS:
        raise BuildingError(f'Unknown roof "{roof}"; use one of '
                            + ", ".join(ROOF_KINDS))
    roof_mat = b.get("roof_material") or ("slate" if style in (
        "church", "round tower") or index % 3 == 2 else "tiles")
    if roof_mat not in ROOFS:
        roof_mat = "tiles"
    wall_pal, roof_pal = WALLS[wall][1], ROOFS[roof_mat][1]
    out = dict(b)
    out.update(
        style=style, wall=wall, roof=roof, roof_material=roof_mat,
        x=_f(b.get("x")), y=_f(b.get("y")), rz=_f(b.get("rz")),
        w=max(2000.0, _f(b.get("w"), 9000.0)),
        d=max(2000.0, _f(b.get("d"), 8000.0)),
        floors=max(1, int(_f(b.get("floors"), lo))),
        floor_height=max(2200.0, _f(b.get("floor_height"), FLOOR_HEIGHT)),
        color=b.get("color") or wall_pal[index % len(wall_pal)],
        roof_color=b.get("roof_color") or roof_pal[index % len(roof_pal)],
        name=b.get("name") or f"{style.capitalize()} {index + 1}")
    return out


def build_building(spec: dict, index: int = 0) -> CadNode:
    """One building's outside, placed and turned."""
    b = resolve(spec, index)
    style = b["style"]
    w, d, floors, fh = b["w"], b["d"], b["floors"], b["floor_height"]
    H = floors * fh
    wall_mat = WALLS[b["wall"]][0]
    wall_col, roof_col = b["color"], b["roof_color"]
    roof_mat = ROOFS[b["roof_material"]][0]
    glazing = STYLES[style][2]
    body = group(b["name"])

    if style == "round tower":
        r = min(w, d) / 2.0
        body.add(color(cyl("Walls", 0, 0, 0, H, r, seg=24), wall_col,
                       wall_mat))
        body.add(color(cyl("Plinth", 0, 0, 0, 500, r + 60, seg=24),
                       "#7b766e", "Stone"))
        body.add(color(loop("Glass floors", "fl", floors, [
            cyl("Ribbon", 0, 0, f"950 + fl * {_num(fh)}", fh * 0.5, r + 35,
                seg=24)]), GLASS, "Plastic"))
        body.add(color(loop("Floor bands", "fl", floors, [
            cyl("Band", 0, 0, f"{_num(fh - 120)} + fl * {_num(fh)}", 160,
                r + 90, seg=24)]), TRIM, "Concrete"))
        body.add(color(cyl("Cornice", 0, 0, H, 350, r + 250, r + 150, seg=24),
                       TRIM, "Stone"))
        body.add(color(cyl("Cone roof", 0, 0, H + 350, r * 1.3, r + 150, 0.0,
                           seg=24), roof_col, roof_mat))
        body.add(color(cyl("Finial", 0, 0, H + 350 + r * 1.3, 900, 60, 20),
                       "#c9a54a", "Gold"))
        f = Facade("front", -r, -r, 2 * r, 2 * r)
        body.add(door(f, 0.0, wall_col))
        return _placed(body, b)

    wings = [(-w / 2, -d / 2, w, d)]
    if style == "L-shape":
        wd = d * 0.5
        wings = [(-w / 2, -d / 2, w, wd), (-w / 2, -d / 2 + wd, w * 0.45,
                                           d - wd)]
    for i, (x0, y0, ww, dd) in enumerate(wings):
        body.add(color(box("Walls" if i == 0 else "Wing walls", x0, y0, 0.0,
                           ww, dd, H), wall_col, wall_mat))
        body.add(color(box("Plinth", x0 - 50, y0 - 50, 0.0, ww + 100,
                           dd + 100, 520), "#7b766e", "Stone"))
        if glazing in ("bands", "curtain"):
            spandrel = glazing == "bands"
            for part in curtain_wall([(x0, y0, ww, dd)], floors, fh,
                                     fins=not spandrel or b["wall"] ==
                                     "concrete", spandrel=spandrel):
                body.add(part)
            body.add(color(loop("Floor bands", "fl", floors, [
                box("Band", x0 - 70, y0 - 70, f"{_num(fh - 150)} + fl * "
                    f"{_num(fh)}", ww + 140, dd + 140, 200)]), TRIM,
                "Concrete"))
            if style == "block" and i == 0 and floors > 1:
                n = max(1, int(ww // 4500))
                pitch = ww / n
                u0 = x0 + pitch / 2 - 1300
                bal = [box("Balcony slab", f"{_num(u0)} + c * {_num(pitch)}",
                           y0 - 1300, "fl * %s + %s" % (_num(fh), _num(fh)),
                           2600, 1300, 180)]
                rail = [box("Railing", f"{_num(u0)} + c * {_num(pitch)}",
                            y0 - 1300, "fl * %s + %s" % (_num(fh),
                                                        _num(fh + 180)),
                            2600, 40, 1000)]
                body.add(color(loop("Balconies", "fl", floors - 1, [
                    loop("Bays", "c", n, bal)]), TRIM, "Concrete"))
                body.add(color(loop("Railings", "fl", floors - 1, [
                    loop("Bays", "c", n, rail)]), "#9fb8c4", "Glass", 0.55))
        else:
            first = 1 if glazing == "shopfront" else 0
            for side in ("front", "back", "left", "right"):
                fac = Facade(side, x0, y0, ww, dd)
                lp, door_u = punched_windows(
                    fac, floors - first, fh, z0=900.0 + first * fh,
                    skip_door=(side == "front" and i == 0 and not first))
                if lp is not None:
                    body.add(lp)
                if side == "front" and i == 0 and not first:
                    body.add(door(fac, door_u if lp is not None else 0.0,
                                  wall_col))
        # cornice under a flat roof, a string course between floors
        if b["roof"] == "flat":
            body.add(color(box("Cornice", x0 - 150, y0 - 150, H - 300,
                               ww + 300, dd + 300, 300), TRIM, "Stone"))
            body.add(move(flat_roof(ww, dd, H, tall=floors > 8, index=index),
                          x0 + ww / 2, y0 + dd / 2, 0.0, "Roof"))
        elif b["roof"] == "cone":
            r = max(ww, dd) / 2 * 1.2
            body.add(color(cyl("Cone roof", x0 + ww / 2, y0 + dd / 2, H,
                               r * 1.1, r, 0.0, seg=4), roof_col, roof_mat))
        else:
            body.add(move(pitched_roof(
                b["roof"], ww, dd, H, roof_col, roof_mat, wall_col, wall_mat,
                chimney=(i == 0 and style != "church"),
                dormer=(i == 0 and style in ("house", "cottage", "terrace"))),
                x0 + ww / 2, y0 + dd / 2, 0.0, "Roof"))
        if floors > 1 and glazing == "windows":
            body.add(color(loop("String courses", "fl", floors - 1, [
                box("String course", x0 - 40, y0 - 40,
                    f"{_num(fh - 100)} + fl * {_num(fh)}", ww + 80, dd + 80,
                    120)]), TRIM, "Stone"))
    if style == "shop":
        f = Facade("front", -w / 2, -d / 2, w, d)
        n = max(1, int((w - 1200) // 2000))
        pane = (w - 1200) / n
        body.add(color(f.box("Shop glass", -w / 2 + 600, 300.0, w - 1200,
                             2500, 60, 20), GLASS, "Plastic"))
        body.add(color(group("Shop frame", [
            f.box("Stall riser", -w / 2 + 500, 0.0, w - 1000, 320, 90),
            f.box("Head", -w / 2 + 500, 2800.0, w - 1000, 150, 90),
            loop("Mullions", "c", n + 1, [
                f.box("Mullion", f"{_num(-w / 2 + 560)} + c * {_num(pane)}",
                      300.0, 80, 2500, 80)])]), "#2d3136", "Metal"))
        body.add(color(f.box("Fascia sign", -w / 2 + 400, 2950.0, w - 800,
                             700, 160), AWNINGS[(index + 1) % len(AWNINGS)],
                       "Matte"))
        aw = AWNINGS[index % len(AWNINGS)]
        body.add(color(_hull("Awning", [
            f.box("Top", -w / 2 + 500, 2900.0, w - 1000, 40, 60),
            f.box("Edge", -w / 2 + 500, 2350.0, w - 1000, 40, 1500, 60)]),
            aw, "Matte"))
        body.add(color(f.box("Shop door", -600.0, 300.0, 1200, 2400, 75, 20),
                       DOOR, "Matte"))
    if style == "church":
        tw = min(w, d) * 0.45
        tx = -w / 2 - tw * 0.6
        th = H * 2.3
        body.add(color(box("Bell tower", tx, -tw / 2, 0.0, tw, tw, th),
                       wall_col, wall_mat))
        body.add(color(box("Tower cornice", tx - 120, -tw / 2 - 120, th - 250,
                           tw + 240, tw + 240, 250), TRIM, "Stone"))
        lv = []
        for side in ("front", "back", "left", "right"):
            fac = Facade(side, tx, -tw / 2, tw, tw)
            lv.append(fac.box("Louvre", -tw * 0.2, th - 2600, tw * 0.4,
                              1600, 40))
        body.add(color(group("Belfry louvres", lv), "#2d2a26", "Matte"))
        body.add(color(cyl("Spire", tx + tw / 2, 0.0, th, tw * 2.6,
                           tw * 0.74, 0.0, seg=8), roof_col, roof_mat))
        top = th + tw * 2.6
        body.add(color(group("Cross", [
            box("Upright", tx + tw / 2 - 40, -40, top, 80, 80, 1400),
            box("Arm", tx + tw / 2 - 350, -40, top + 850, 700, 80, 80)]),
            "#c9a54a", "Gold"))
        f = Facade("left", tx, -tw / 2, tw, tw)
        body.add(door(f, 0.0, wall_col))
    return _placed(body, b)


def _placed(body, b):
    inner = body
    if b["rz"]:
        inner = turn(body, z=b["rz"])
    return move(inner, b["x"], b["y"], 0.0, b["name"])


def footprint(b: dict, index: int = 0):
    """(x, y, w, d, rz) of the resolved building — what the 2D plan
    draws — plus the L-shape's wings in the building's own frame."""
    r = resolve(b, index)
    wings = [(-r["w"] / 2, -r["d"] / 2, r["w"], r["d"])]
    if r["style"] == "L-shape":
        wd = r["d"] * 0.5
        wings = [(-r["w"] / 2, -r["d"] / 2, r["w"], wd),
                 (-r["w"] / 2, -r["d"] / 2 + wd, r["w"] * 0.45, r["d"] - wd)]
    return r, wings
