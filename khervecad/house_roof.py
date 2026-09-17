"""The House Builder's roofs and chimneys (Qt-free).

A pitched roof is its SLOPES: each one a planar polygon on the plan
(two rectangles for a gable, trapezoids and triangles for a hip, four
triangles for a pyramid) lifted onto its plane and given a vertical
depth, as one `polyhedron` — the planes meet exactly at the ridge and
the hips, the plans tile the roof, and the attic under them stays
hollow over a ceiling. The covering is a shader surface (tiles, slate,
shingles, thatch, standing seam, solar), so its courses run up the
slope for no triangles.

Round it: fascia boards and soffits along the eaves, half-round gutters
with downpipes to the ground, bargeboards up each verge, gable walls in
the house's facing, and half-round ridge and hip tiles.

Chimneys (`chimneys`) rise from every fireplace: on an outside wall a
stack built against the facing from the ground; on an inside wall a
chimney breast through every floor above, then the stack through the
roof. Either way it ends a metre over the roof with a corbelled course,
a cap and clay pots.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from . import house_finishes as F
from .house_walls import (WallFrame, _color, _shade, _footprint,
                          wall_segments)
from .model import CadNode

ROOF_THICKNESS = 200.0
ROOF_STYLES = ("Flat", "Gable", "Hip", "Pyramid", "Lean-to")
ROOF_PITCH_RANGE = (5.0, 60.0)
GUTTER_COLOR = ("#2c2e31", "Plastic")
POT_COLOR = ("#b4613a", "Clay")
CAP_COLOR = ("#a9a79f", "Concrete")
#: how far a chimney stands over the roof where it comes through
CHIMNEY_CLEAR = 1000.0
CHIMNEYS = ("auto", "none", "ridge")


def roof_frame(roof, floor, bounds=None, attach=None):
    """(along_x, (u0, u1, v0, v1), high_v0): the roof's own frame, u
    along the ridge and v across it, over *bounds* (the floor's indoor
    rooms by default; None if it has none). *attach* — the side where a
    taller part of the house stands — turns the ridge to run along that
    wall and says which way a lean-to rises (*high_v0*: towards the low
    v, so the roof leans on that wall)."""
    b = bounds if bounds is not None else floor.indoor_bounds()
    if b is None:
        return None
    x0, y0, x1, y1 = b
    if attach in ("E", "W"):
        along_x = False
    elif attach in ("N", "S"):
        along_x = True
    else:
        along_x = roof.ridge == "x" or (roof.ridge != "y"
                                        and x1 - x0 >= y1 - y0)
    frame = (x0, x1, y0, y1) if along_x else (y0, y1, x0, x1)
    return along_x, frame, attach in ("W", "S")


def pitch_tan(roof) -> float:
    lo, hi = ROOF_PITCH_RANGE
    return math.tan(math.radians(min(max(float(roof.pitch), lo), hi)))


def _polyhedron(name, top, depth):
    """A convex polygon *top* of (x, y, z) points given a vertical
    *depth* below it, as one closed polyhedron."""
    area = sum(top[i - 1][0] * top[i][1] - top[i][0] * top[i - 1][1]
               for i in range(len(top)))
    if area < 0:
        top = top[::-1]
    n = len(top)
    points = [[round(p[0], 3), round(p[1], 3), round(p[2], 3)] for p in top]
    points += [[p[0], p[1], round(p[2] - depth, 3)] for p in top]
    faces = [list(range(n))[::-1], list(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, n + j, n + i])
    return CadNode("polyhedron", name, dict(points=points, faces=faces))


class RoofShape:
    """One roof over a rectangle: its frame, heights and planes."""

    def __init__(self, roof, floor, bounds=None, style=None, attach=None):
        frame = roof_frame(roof, floor, bounds, attach)
        self.ok = frame is not None
        if not self.ok:
            return
        self.along_x, (u0, u1, v0, v1), self.high_v0 = frame
        self.u0, self.u1, self.v0, self.v1 = u0, u1, v0, v1
        self.attach = attach
        style = style or roof.style
        self.style = style if style in ROOF_STYLES else "Flat"
        self.e = max(0.0, float(roof.overhang))
        self.hw = float(floor.wall_thickness) / 2.0
        self.tan = pitch_tan(roof)
        #: the wall head; the roof planes are measured from a datum over
        #: the centre line that puts them just ON the outer edge of the
        #: wall — from the wall head they would let its top show through
        self.Hw = float(floor.wall_height)
        self.H = self.Hw + self.hw * self.tan + 20.0
        self.L, self.span = u1 - u0, v1 - v0
        self.vc, self.uc = (v0 + v1) / 2.0, (u0 + u1) / 2.0
        # a lean-to leaning on a taller wall has no overhang into it
        self.he = 0.0 if attach else self.e
        self.depth = max(150.0, 2.0 * self.hw * self.tan + 80.0)
        self.eave_z = self.H - self.e * self.tan
        if self.style == "Pyramid":
            # the steeper faces take the pitch; the eave is set so the
            # shallower ones still clear the outer edge of the wall
            drop = (min(self.L, self.span) / 2.0 + self.e) * self.tan
            slopes = (drop / (self.L / 2.0 + self.e),
                      drop / (self.span / 2.0 + self.e))
            need = max((self.hw - self.e) * sl for sl in slopes)
            self.eave_z = self.Hw + 20.0 + need
            self.rise = self.eave_z + drop - self.H
        elif self.style == "Hip":
            self.rise = min(self.L, self.span) / 2.0 * self.tan
        elif self.style == "Gable":
            self.rise = self.span / 2.0 * self.tan
        elif self.style == "Lean-to":
            self.rise = self.span * self.tan
        else:
            self.rise = 0.0

    def xy(self, u, v):
        return (u, v) if self.along_x else (v, u)

    def uv(self, x, y):
        return (x, y) if self.along_x else (y, x)

    def z(self, u, v):
        """The roof's top surface over (u, v) (clamped to the eaves)."""
        H, t = self.H, self.tan
        if self.style == "Flat":
            return self.Hw + ROOF_THICKNESS
        if self.style == "Gable":
            return H + t * min(v - self.v0, self.v1 - v)
        if self.style == "Lean-to":
            return H + t * ((self.v1 - v) if self.high_v0 else (v - self.v0))
        du = min(u - self.u0, self.u1 - u)
        dv = min(v - self.v0, self.v1 - v)
        if self.style == "Hip":
            return min(H + t * min(du, dv), H + self.rise)
        ze = self.eave_z
        fu = abs(u - self.uc) / (self.L / 2.0 + self.e)
        fv = abs(v - self.vc) / (self.span / 2.0 + self.e)
        return ze + (H + self.rise - ze) * (1.0 - min(1.0, max(fu, fv)))

    def slab(self, name, uv_points, heights):
        top = [self.xy(u, v) + (h,) for (u, v), h in zip(uv_points, heights)]
        return _polyhedron(name, top, self.depth)


def build_roof(roof, floor, bounds=None, style=None, attach=None,
               name="Roof", wall_style=None, look=None,
               ground_z=-400.0) -> list:
    """The roof over *bounds* (the floor's indoor rooms by default) as
    coloured nodes — slopes, ceiling, gable walls, eaves joinery, gutters
    and downpipes to *ground_z*, ridge tiles. *style* overrides the
    roof's own; with *attach* — the side where a taller part of the
    house stands — a lean-to rises towards it and keeps its overhang out
    of it. Empty when there is nothing to cover."""
    from .house import ROOF_COLORS
    sh = RoofShape(roof, floor, bounds, style, attach)
    if not sh.ok:
        return []
    colour, material = ROOF_COLORS.get(roof.color,
                                       ROOF_COLORS["Brown tiles"])
    wall_colour, wall_material = wall_style or (F.WALL_COLOR, "Render")
    joinery = look.joinery if look is not None else F.JOINERY["White"]
    inside = look.inside if look is not None else (F.WALL_COLOR, "Plaster")
    H, e, hw, t = sh.H, sh.e, sh.hw, sh.tan
    u0, u1, v0, v1 = sh.u0, sh.u1, sh.v0, sh.v1
    ue0, ue1 = u0 - e, u1 + e

    def cube(label, ua, ub, va, vb, za, zb):
        xa, ya = sh.xy(min(ua, ub), min(va, vb))
        xb, yb = sh.xy(max(ua, ub), max(va, vb))
        return CadNode("cube", label, dict(
            x=min(xa, xb), y=min(ya, yb), z=min(za, zb),
            width=abs(xb - xa), depth=abs(yb - ya),
            height=max(abs(zb - za), 0.01), center=False))

    out = []
    if sh.style == "Flat":
        H = sh.Hw
        E = max(e, 40.0)
        out.append(_color(cube(name, u0 - hw - E, u1 + hw + E, v0 - hw - E,
                               v1 + hw + E, H, H + ROOF_THICKNESS - 30.0),
                          *joinery))
        deck = "#3b3d40" if material in ("Roof tiles", "Slate", "Default",
                                         "Shingles", "Thatch", "Clay") \
            else colour
        deck_mat = "Concrete" if deck != colour else material
        out.append(_color(cube(f"{name} covering", u0 - hw - E + 50.0,
                               u1 + hw + E - 50.0, v0 - hw - E + 50.0,
                               v1 + hw + E - 50.0,
                               H + ROOF_THICKNESS - 40.0,
                               H + ROOF_THICKNESS), deck, deck_mat))
        return out

    # the ceiling closes the attic over the rooms
    out.append(_color(cube("Ceiling", u0, u1, v0, v1, sh.Hw, sh.Hw + 12.0),
                      *inside))
    slopes = []
    if sh.style == "Gable":
        z_e, top = H - e * t, H + sh.rise
        slopes = [([(ue0, v0 - e), (ue1, v0 - e), (ue1, sh.vc),
                    (ue0, sh.vc)], [z_e, z_e, top, top]),
                  ([(ue0, sh.vc), (ue1, sh.vc), (ue1, v1 + e),
                    (ue0, v1 + e)], [top, top, z_e, z_e])]
    elif sh.style == "Lean-to":
        if sh.high_v0:
            lo_v, hi_v = v1 + e, v0 - sh.he
            z_lo, z_hi = H - e * t, H + (v1 - v0 + sh.he) * t
        else:
            lo_v, hi_v = v0 - e, v1 + sh.he
            z_lo, z_hi = H - e * t, H + (v1 - v0 + sh.he) * t
        slopes = [([(ue0, lo_v), (ue1, lo_v), (ue1, hi_v), (ue0, hi_v)],
                   [z_lo, z_lo, z_hi, z_hi])]
    else:
        z_e, apex = sh.eave_z, H + sh.rise
        half = max(sh.L - sh.span, 0.0) / 2.0 if sh.style == "Hip" else 0.0
        r0, r1 = (sh.uc - half, sh.vc), (sh.uc + half, sh.vc)
        c00, c10 = (ue0, v0 - e), (ue1, v0 - e)
        c11, c01 = (ue1, v1 + e), (ue0, v1 + e)
        if half > 1e-6:
            slopes = [([c00, c10, r1, r0], [z_e, z_e, apex, apex]),
                      ([c11, c01, r0, r1], [z_e, z_e, apex, apex]),
                      ([c01, c00, r0], [z_e, z_e, apex]),
                      ([c10, c11, r1], [z_e, z_e, apex])]
        else:
            slopes = [([c00, c10, r0], [z_e, z_e, apex]),
                      ([c10, c11, r0], [z_e, z_e, apex]),
                      ([c11, c01, r0], [z_e, z_e, apex]),
                      ([c01, c00, r0], [z_e, z_e, apex])]
    for pts, heights in slopes:
        out.append(_color(sh.slab(f"{name} slope", pts, heights), colour,
                          material))
    out += _gables(sh, cube, wall_colour, wall_material)
    out += _eaves(sh, name, joinery, ground_z)
    out += _ridge_tiles(sh, colour, material)
    return out


def _gables(sh, cube, colour, material):
    """The triangles of wall a gable or lean-to closes, in the facing."""
    H, hw, t = sh.H, sh.hw, sh.tan
    out = []
    if sh.style == "Gable":
        base = H - hw * t - sh.depth / 2.0
        apex = H + sh.rise - sh.depth / 2.0
        prof = [(sh.v0 - hw, base), (sh.v1 + hw, base), (sh.vc, apex)]
    elif sh.style == "Lean-to":
        base = H - hw * t - sh.depth / 2.0
        high = H + (sh.span + hw) * t - sh.depth / 2.0
        if sh.high_v0:
            prof = [(sh.v1 + hw, base), (sh.v0 - hw, high),
                    (sh.v0 - hw, base)]
        else:
            prof = [(sh.v0 - hw, base), (sh.v1 + hw, base),
                    (sh.v1 + hw, high)]
        if not sh.attach:                  # the high wall under the eave
            hv = sh.v0 if sh.high_v0 else sh.v1
            node = CadNode("hull", "Wedge", {})
            node.add(cube("High wall", sh.u0 - hw, sh.u1 + hw, hv - hw,
                          hv + hw, sh.Hw - 1.0, sh.Hw))
            node.add(cube("High wall top", sh.u0 - hw, sh.u1 + hw, hv - hw,
                          hv + hw, high - 1.0, high))
            out.append(_color(node, colour, material))
    else:
        return []
    # a profile in (v, z) extruded through the wall at each end
    fr = WallFrame(horizontal=not sh.along_x)
    for uc in (sh.u0, sh.u1):
        node = fr.slab("Gable", [([(v, z) for v, z in prof], [])],
                       uc - hw, uc + hw)
        out.append(_color(node, colour, material))
    return out


def _gutter_profile(v_out, z_top, sign):
    """A half-round gutter's cross-section in (v, z): open at the top,
    its back against the fascia at *v_out*, hanging on the *sign* side."""
    r, t = 58.0, 4.0
    cv = v_out + sign * r
    outer = [(cv + r * math.cos(a), z_top + r * math.sin(a))
             for a in [math.pi + k * math.pi / 8 for k in range(9)]]
    inner = [(cv + (r - t) * math.cos(a), z_top + (r - t) * math.sin(a))
             for a in [2 * math.pi - k * math.pi / 8 for k in range(9)]]
    pts = outer + inner
    area = sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1]
               for i in range(len(pts)))
    return pts if area > 0 else pts[::-1]


def _eaves(sh, name, joinery, ground_z):
    """Fascia, soffit, gutter and downpipes along every eave, and
    bargeboards up every verge."""
    H, e, hw, t, d = sh.H, sh.e, sh.hw, sh.tan, sh.depth
    out = []
    z_e = sh.eave_z
    ue0, ue1 = sh.u0 - e, sh.u1 + e
    ve0, ve1 = sh.v0 - e, sh.v1 + e
    along = WallFrame(horizontal=sh.along_x)      # u along, v across
    across = WallFrame(horizontal=not sh.along_x)  # v along, u across
    # (frame along the eave, frame across it, edge, outward sign,
    #  eave from, to, wall face, downpipes?, coordinate order)
    eaves = []
    if sh.style == "Gable":
        eaves = [(along, across, ve0, -1, ue0, ue1, sh.v0 - hw, True, False),
                 (along, across, ve1, +1, ue0, ue1, sh.v1 + hw, True, False)]
    elif sh.style == "Lean-to":
        eaves = [(along, across, ve1, +1, ue0, ue1, sh.v1 + hw, True, False)
                 if sh.high_v0 else
                 (along, across, ve0, -1, ue0, ue1, sh.v0 - hw, True, False)]
    elif sh.style in ("Hip", "Pyramid"):
        eaves = [(along, across, ve0, -1, ue0, ue1, sh.v0 - hw, True, False),
                 (along, across, ve1, +1, ue0, ue1, sh.v1 + hw, True, False),
                 (across, along, ue0, -1, ve0, ve1, sh.u0 - hw, False, True),
                 (across, along, ue1, +1, ve0, ve1, sh.u1 + hw, False, True)]
    for fr, perp, edge, s, lo, hi, wall_face, pipes, swapped in eaves:
        out.append(_color(fr.box("Fascia", lo, hi, edge, edge + s * 25.0,
                                 z_e - d - 20.0, z_e + 5.0), *joinery))
        if e > hw + 30.0:
            out.append(_color(fr.box("Soffit", lo, hi, edge, wall_face,
                                     z_e - d - 20.0, z_e - d - 5.0),
                              *joinery))
        gz = z_e - 40.0
        prof = _gutter_profile(edge + s * 25.0, gz, s)
        out.append(_color(perp.slab("Gutter", [(prof, [])], lo, hi),
                          *GUTTER_COLOR))
        if not pipes:
            continue
        pipe_n = wall_face + s * 60.0
        a0, a1 = (sh.v0, sh.v1) if swapped else (sh.u0, sh.u1)
        for pa in (a0 + 250.0, a1 - 250.0):
            x, y = sh.xy(pipe_n, pa) if swapped else sh.xy(pa, pipe_n)
            out.append(_color(CadNode("cylinder", "Downpipe", dict(
                x=x, y=y, z=ground_z, height=gz - 180.0 - ground_z,
                radius_bottom=34.0, radius_top=34.0, segments=16,
                center=False)), *GUTTER_COLOR))
            neck = CadNode("hull", "Swan neck", {})
            neck.add(fr.box("Neck top", pa - 30.0, pa + 30.0,
                            edge + s * 55.0, edge + s * 95.0,
                            gz - 60.0, gz - 20.0))
            neck.add(fr.box("Neck foot", pa - 30.0, pa + 30.0,
                            pipe_n - 30.0, pipe_n + 30.0, gz - 200.0,
                            gz - 160.0))
            out.append(_color(neck, *GUTTER_COLOR))
    if sh.style in ("Gable", "Lean-to"):
        for uc, side in ((ue0, -1), (ue1, +1)):
            for edge, top_v in _verges(sh):
                board = CadNode("hull", "Bargeboard", {})
                z_lo, z_hi = _verge_z(sh, edge), _verge_z(sh, top_v)
                board.add(across.box("Verge low", edge - 0.5, edge + 0.5,
                                     uc, uc + side * 25.0, z_lo - d - 60.0,
                                     z_lo + 15.0))
                board.add(across.box("Verge high", top_v - 0.5, top_v + 0.5,
                                     uc, uc + side * 25.0, z_hi - d - 60.0,
                                     z_hi + 15.0))
                out.append(_color(board, *joinery))
    return out


def _verge_z(sh, v):
    if sh.style == "Gable":
        return sh.H + sh.tan * min(v - sh.v0, sh.v1 - v)
    return _lean_z(sh, v)


def _lean_z(sh, v):
    H, t = sh.H, sh.tan
    return H + t * ((sh.v1 - v) if sh.high_v0 else (v - sh.v0))


def _verges(sh):
    """(eave-end v, top v) of each sloping verge line."""
    e = sh.e
    if sh.style == "Gable":
        return [(sh.v0 - e, sh.vc), (sh.v1 + e, sh.vc)]
    if sh.high_v0:
        return [(sh.v1 + e, sh.v0 - sh.he)]
    return [(sh.v0 - e, sh.v1 + sh.he)]


def _ridge_tiles(sh, colour, material):
    """Half-round tiles along the ridge and down every hip."""
    tone = _shade(colour, 0.85)
    mat = "Clay" if material in ("Roof tiles", "Clay") else "Matte"
    out = []
    H, e, t = sh.H, sh.e, sh.tan
    across = WallFrame(horizontal=not sh.along_x)
    r = 105.0

    def cap(vc, zc, ua, ub):
        pts = [(vc + r * math.cos(k * math.pi / 8),
                zc + r * 0.8 * math.sin(k * math.pi / 8)) for k in range(9)]
        return _color(across.slab("Ridge tiles", [(pts, [])], ua, ub),
                      tone, mat)

    if sh.style == "Gable":
        out.append(cap(sh.vc, H + sh.rise - 20.0, sh.u0 - e - 20.0,
                       sh.u1 + e + 20.0))
    elif sh.style in ("Hip", "Pyramid"):
        half = max(sh.L - sh.span, 0.0) / 2.0 if sh.style == "Hip" else 0.0
        apex = H + sh.rise
        if half > 1e-6:
            out.append(cap(sh.vc, apex - 20.0, sh.uc - half - 60.0,
                           sh.uc + half + 60.0))
        z_e = sh.eave_z
        ends = [(sh.uc - half, sh.vc), (sh.uc + half, sh.vc)]
        for cu, cv in ((sh.u0 - e, sh.v0 - e), (sh.u1 + e, sh.v0 - e),
                       (sh.u1 + e, sh.v1 + e), (sh.u0 - e, sh.v1 + e)):
            ru, rv = ends[0] if cu < sh.uc else ends[1]
            hip = CadNode("hull", "Hip tiles", {})
            for (pu, pv), pz in (((cu, cv), z_e), ((ru, rv), apex)):
                x, y = sh.xy(pu, pv)
                hip.add(CadNode("sphere", "Hip end", dict(
                    x=x, y=y, z=pz - 15.0, radius=80.0, segments=8)))
            out.append(_color(hip, tone, mat))
    return out


# ------------------------------------------------------------- chimneys
def _stack_top(nodes_cube, colour, material, x0, y0, x1, y1, top):
    """The top of a stack at *top*: a corbelled course, a cap and pots."""
    out = [_color(nodes_cube("Corbel", x0 - 50.0, y0 - 50.0, x1 + 50.0,
                             y1 + 50.0, top - 260.0, top - 150.0),
                  _shade(colour, 0.9), material),
           _color(nodes_cube("Chimney cap", x0 - 30.0, y0 - 30.0, x1 + 30.0,
                             y1 + 30.0, top - 20.0, top + 50.0), *CAP_COLOR)]
    long_x = x1 - x0 >= y1 - y0
    span = max(x1 - x0, y1 - y0)
    pots = max(1, min(4, round(span / 380.0)))
    for i in range(pots):
        f = (i + 0.5) / pots
        cx = x0 + (x1 - x0) * f if long_x else (x0 + x1) / 2.0
        cy = (y0 + y1) / 2.0 if long_x else y0 + (y1 - y0) * f
        out.append(_color(CadNode("cylinder", "Chimney pot", dict(
            x=cx, y=cy, z=top + 50.0, height=520.0, radius_bottom=115.0,
            radius_top=85.0, segments=24, center=False)), *POT_COLOR))
        out.append(_color(CadNode("cylinder", "Pot rim", dict(
            x=cx, y=cy, z=top + 520.0, height=50.0, radius_bottom=100.0,
            radius_top=100.0, segments=24, center=False)), *POT_COLOR))
    return out


def _cube(name, x0, y0, x1, y1, z0, z1):
    return CadNode("cube", name, dict(
        x=min(x0, x1), y=min(y0, y1), z=min(z0, z1), width=abs(x1 - x0),
        depth=abs(y1 - y0), height=max(abs(z1 - z0), 0.01), center=False))


def _covering_roof(house, index, x, y):
    """(RoofShape, floor index) of the roof over (x, y) — the main roof
    or a wing roof — or None."""
    from .house import wing_roofs
    floors = house.floors
    for k in range(len(floors) - 1, index - 1, -1):
        floor = floors[k]
        inside = any(r.indoor and r.x <= x <= r.x + r.w
                     and r.y <= y <= r.y + r.d for r in floor.rooms)
        if not inside:
            continue
        if k == len(floors) - 1:
            return RoofShape(house.roof, floor), k
        for bounds, attach in wing_roofs(house, k):
            if bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]:
                style = None if house.roof.wings == "Same as main" \
                    else house.roof.wings
                return RoofShape(house.roof, floor, bounds, style,
                                 attach), k
        return None, k
    return None, index


def _fireplaces(house):
    for i, floor in enumerate(house.floors):
        for room in floor.rooms:
            for f in room.furniture:
                pid = f.part_id.lower()
                if "fireplace" in pid or "stove" in pid:
                    yield i, floor, room, f


def chimneys(house, levels, looks) -> dict:
    """{floor index: [nodes]} — the chimney of every fireplace, and one
    on the ridge when the roof asks for it. *levels* is each floor's z;
    *looks* each floor's `house_walls.Look`."""
    out = {}
    mode = getattr(house.roof, "chimney", "auto")
    if mode == "none":
        return out
    floors = house.floors
    stacks = []                             # (index, rect, external)
    if mode in ("auto", "ridge"):
        for i, floor, room, f in _fireplaces(house):
            box = _footprint(f)
            if box is None:
                continue
            a = math.radians(f.rz)
            bx, by = -math.sin(a), math.cos(a)
            side = ("E" if bx > 0 else "W") if abs(bx) > abs(by) \
                else ("N" if by > 0 else "S")
            hor = side in ("N", "S")
            line = {"S": room.y, "N": room.y + room.d, "W": room.x,
                    "E": room.x + room.w}[side]
            into = 1 if side in ("S", "W") else -1
            u = f.x if hor else f.y
            seg = next((sg for sg in wall_segments(floor)
                        if sg.horizontal == hor and abs(sg.c - line) < 0.2
                        and sg.a <= u <= sg.b), None)
            if seg is None:
                continue
            width = max(900.0, (box[2] - box[0] if hor else box[3] - box[1])
                        + 250.0)
            hw = seg.thickness / 2.0
            if seg.outside:
                n0, n1 = seg.c - into * hw, seg.c - into * (hw + 650.0)
            else:
                deep = (box[3] - box[1]) if hor else (box[2] - box[0])
                n0, n1 = seg.c - into * hw, seg.c + into * (hw + min(
                    deep, 450.0))
            ua, ub = u - width / 2.0, u + width / 2.0
            rect = (ua, min(n0, n1), ub, max(n0, n1)) if hor \
                else (min(n0, n1), ua, max(n0, n1), ub)
            fire_top = max((p[2] for t in _tris(f) for p in t), default=0.0)
            stacks.append((i, rect, bool(seg.outside), f.z + fire_top))
    if mode == "ridge" and not stacks:
        top = floors[-1]
        sh = RoofShape(house.roof, top)
        if sh.ok and sh.style != "Flat":
            u = sh.u0 + sh.L * 0.25
            x0, y0 = sh.xy(u - 450.0, sh.vc - 300.0)
            x1, y1 = sh.xy(u + 450.0, sh.vc + 300.0)
            stacks.append((len(floors) - 1, (min(x0, x1), min(y0, y1),
                                             max(x0, x1), max(y0, y1)),
                           False, None))
    for i, (x0, y0, x1, y1), external, fire_top in stacks:
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        probe = (cx, cy)
        if external:                        # the room side of the wall
            probe = _inside_probe(floors[i], x0, y0, x1, y1)
        sh, k = _covering_roof(house, i, *probe)
        if sh is not None and sh.ok:
            roof_top = max(sh.z(*sh.uv(px, py)) for px in (x0, x1)
                           for py in (y0, y1))
            peak = sh.H + sh.rise if sh.style != "Flat" \
                else sh.H + ROOF_THICKNESS
            top_k = max(roof_top, min(peak, roof_top + 600.0)) + CHIMNEY_CLEAR
        else:
            top_k = floors[k].wall_height + ROOF_THICKNESS + CHIMNEY_CLEAR
        top_world = levels[k] + top_k
        for j in range(i, k + 1):
            floor, look = floors[j], looks[j]
            base = levels[j]
            H = floor.wall_height
            facing = look.outside
            nodes = out.setdefault(j, [])
            z_top = top_world - base if j == k else H
            if external:
                z_bot = (-floor.slab_thickness - 150.0) if j == 0 \
                    else -floor.slab_thickness
                if j > i:
                    z_bot = -floor.slab_thickness
                nodes.append(_color(_cube("Chimney stack", x0, y0, x1, y1,
                                          z_bot, z_top), *facing))
            else:
                z_bot = fire_top if (j == i and fire_top is not None) \
                    else -floor.slab_thickness
                if fire_top is None and j == i:
                    z_bot = H
                inner_top = H if j < k else H
                if inner_top - z_bot > 1.0:
                    nodes.append(_color(_cube("Chimney breast", x0, y0, x1,
                                              y1, z_bot, inner_top),
                                        *look.inside))
                if j == k:
                    nodes.append(_color(_cube("Chimney stack", x0 + 40.0,
                                              y0 + 40.0, x1 - 40.0,
                                              y1 - 40.0, H, z_top),
                                        *facing))
            if j == k:
                inset = 0.0 if external else 40.0
                nodes += _stack_top(_cube, *facing, x0 + inset, y0 + inset,
                                    x1 - inset, y1 - inset, z_top)
    return out


def _tris(f):
    from .house import part_tris
    return part_tris(f.part_id, f.dims)


def _inside_probe(floor, x0, y0, x1, y1):
    """A point of an indoor room next to an outside stack's rectangle."""
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        px = cx + dx * ((x1 - x0) / 2.0 + 400.0)
        py = cy + dy * ((y1 - y0) / 2.0 + 400.0)
        if any(r.indoor and r.x <= px <= r.x + r.w and r.y <= py <= r.y + r.d
               for r in floor.rooms):
            return px, py
    return cx, cy
