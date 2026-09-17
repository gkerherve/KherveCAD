"""The House Builder's walls, openings and room linings (Qt-free).

A floor's walls are found on the PLAN (`wall_segments`): every room
edge is split where another edge starts or stops on the same line, and
each piece knows what stands on either side of it — two rooms (an
inside wall, `Floor.inner_wall_thickness`) or one room and the outdoors
(an outside wall, `Floor.wall_thickness`, and which way is out). So an
L-shaped house gets its outside walls right, and the part of a room's
edge shared with a neighbour is a thin partition while the rest is a
cavity wall.

An outside wall is TWO leaves: the facing (brick, stone, render,
cladding) and the plaster lining inside. Each leaf is ONE solid — its
elevation drawn as an outline with the windows as holes and the doors
as notches (`region_loops`), extruded through its depth — so a facade
has no seams across it, the reveals of every opening are real, and
nothing is booleaned (the built-in preview shows it exactly). The
facing leaf wraps each outside corner (`Segment.ext_a/ext_b`) and runs
down past the slab, so storeys and corners meet like masonry.

Openings get joinery: window frames with mullions and a transom, stone
sills and lintels, an internal window board; front doors with a panelled
leaf, glazing, a letter plate, a step and a canopy; inside doors with a
lining, architraves and a four-panel leaf; sectional garage doors. A
room gets its floor covering, skirting boards, and tiles where tiles go
— full height behind a bath or a shower, a splashback behind worktops
(`house_finishes`).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import house_finishes as F
from .model import CadNode

GLASS_COLOR = "#bfe0e8"
GLASS_ALPHA = 0.3                     # see-through in preview and render
#: a door's glazing is clearer than a window's (glrender's floor)
DOOR_GLASS_ALPHA = 0.15
GLASS_THICKNESS = 6.0
GARAGE_DOOR_COLOR = F.GARAGE_DOORS[0]
GARAGE_DOOR_THICKNESS = 40.0

#: headroom a canopy over a front door needs under the floor above
CEILING = 120.0
#: the plinth course at the foot of a ground-floor wall: its top above
#: the floor, how far below the slab it goes, how proud it stands
PLINTH_TOP = 150.0
PLINTH_DOWN = 150.0
PLINTH_PROUD = 15.0
SKIRTING_H = 120.0
SKIRTING_T = 18.0
ARCHITRAVE_W = 65.0
ARCHITRAVE_T = 18.0
FRAME_W = 60.0
FRAME_DEPTH = 70.0
#: how far a window or door frame is set back from the outside face
REVEAL = 90.0


def _color(node, color, material="Default", alpha=1.0):
    c = CadNode("color", node.name, dict(color=color, alpha=alpha,
                                         material=material))
    c.add(node)
    return c


def _shade(hexcol: str, k: float) -> str:
    h = hexcol.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v * k)))
                                   for v in (r, g, b))


# ------------------------------------------------------------- the plan
@dataclass
class Segment:
    """One straight wall on the plan: on the line ``c`` (y for a
    *horizontal* wall, x for a vertical one) from ``a`` to ``b`` along
    it, both centre-line coordinates. *outside* is +1 / -1 — the side
    of the line that is outdoors — or 0 for a wall between rooms.
    *openings* are (offset from a, width, height, sill, kind)."""
    horizontal: bool
    c: float
    a: float
    b: float
    outside: int
    thickness: float
    openings: list = field(default_factory=list)
    #: how far the facing leaf runs past a and b to wrap a corner
    ext_a: float = 0.0
    ext_b: float = 0.0
    #: a balustrade, not a wall: the open edge of a stairwell
    rail: bool = False

    @property
    def interior(self) -> bool:
        return self.outside == 0

    @property
    def length(self) -> float:
        return self.b - self.a

    def point(self, u):
        return (u, self.c) if self.horizontal else (self.c, u)

    @property
    def p1(self):
        return self.point(self.a)

    @property
    def p2(self):
        return self.point(self.b)


def _r(v):
    return round(float(v), 1)


def _room_lines(room):
    """(horizontal, line, lo, hi, room side) for each edge of *room*:
    the room lies on the +1 (high) or -1 (low) side of its line."""
    x, y, w, d = room.x, room.y, room.w, room.d
    return {"S": (True, y, x, x + w, +1), "N": (True, y + d, x, x + w, -1),
            "W": (False, x, y, y + d, +1), "E": (False, x + w, y, y + d, -1)}


def _is_void(room) -> bool:
    return getattr(room, "surface", "indoor") == "void"


def wall_segments(floor) -> list:
    """Every wall of *floor*'s indoor rooms as `Segment`s: edges split
    where another edge on the same line starts or stops, classified by
    what lies on each side, and merged back into the longest runs of the
    same kind — plus each run's openings and its corner wraps.

    Two rooms with the SAME NAME are one open space (an L-shaped landing,
    a kitchen-diner drawn as two rectangles): no wall between them. A
    stairwell ("void" surface, no floor) is open towards a hall, landing
    or corridor — a balustrade (`rail`) — and walled towards anything
    else."""
    from .house_finishes import room_kind
    lines = {}
    rooms = [r for r in floor.rooms if r.indoor]
    for room in rooms:
        for side, (hor, c, lo, hi, s) in _room_lines(room).items():
            lines.setdefault((hor, _r(c)), []).append(
                (_r(lo), _r(hi), s, room))
    t_out = float(floor.wall_thickness)
    t_in = float(getattr(floor, "inner_wall_thickness", t_out))
    segments = []
    for (hor, c), edges in sorted(lines.items()):
        cuts = sorted({v for lo, hi, _s, _r2 in edges for v in (lo, hi)})
        run = None
        for p, q in zip(cuts, cuts[1:]):
            mid = (p + q) / 2.0
            high = [r for lo, hi, s, r in edges if lo < mid < hi and s > 0]
            low = [r for lo, hi, s, r in edges if lo < mid < hi and s < 0]
            if not (high or low):
                run = None
                continue
            rail = False
            if high and low:
                a, b = high[0], low[0]
                if a.name == b.name and _is_void(a) == _is_void(b):
                    run = None                  # one open space
                    continue
                if _is_void(a) != _is_void(b):
                    void, other = (a, b) if _is_void(a) else (b, a)
                    # a stairwell is open to the landing; a lift shaft
                    # (or any other void) is walled
                    rail = room_kind(void.name) == "hall" and \
                        room_kind(other.name) == "hall"
            outside = 0 if (high and low) else (-1 if high else +1)
            if run is not None and run.outside == outside \
                    and run.rail == rail and abs(run.b - p) < 1e-6:
                run.b = q
                continue
            run = Segment(hor, c, p, q, outside,
                          t_in if outside == 0 else t_out, rail=rail)
            segments.append(run)
    for room in rooms:
        lines_of = _room_lines(room)
        for op in room.openings:
            hor, c, lo, _hi, _s = lines_of[op.side]
            centre = lo + op.offset + op.width / 2.0
            host = [sg for sg in segments if sg.horizontal == hor
                    and abs(sg.c - _r(c)) < 1e-6
                    and sg.a - 1e-6 <= centre <= sg.b + 1e-6]
            if host:
                sg = host[0]
                sg.openings.append((lo + op.offset - sg.a, op.width,
                                    op.height, op.sill, op.kind))
    _corner_wraps(segments)
    return segments


def _corner_wraps(segments):
    """Set how far each wall runs past its ends. An outside wall's
    facing wraps a CONVEX corner (the other wall there is outside too
    and faces the way this one continues) by that wall's half
    thickness; at a reflex corner it stops, or it would show through
    the plaster of the room inside. An inside wall that ends where
    other walls end (an L, not a T into a through wall) runs on by
    their half thickness, so the corner has no notch."""
    for sg in segments:
        for end, direction in ((sg.a, -1), (sg.b, +1)):
            ext = 0.0
            perpendicular = [o for o in segments
                             if o.horizontal != sg.horizontal
                             and abs(o.c - end) < 1e-6
                             and o.a - 1e-6 <= sg.c <= o.b + 1e-6]
            if sg.outside:
                for o in perpendicular:
                    if o.outside == direction and \
                            (abs(o.a - sg.c) < 1e-6 or abs(o.b - sg.c) < 1e-6):
                        ext = max(ext, o.thickness / 2.0)
            elif perpendicular and not any(
                    o.a + 1e-6 < sg.c < o.b - 1e-6 for o in perpendicular):
                ext = max(o.thickness / 2.0 for o in perpendicular)
            if direction < 0:
                sg.ext_a = ext
            else:
                sg.ext_b = ext


def opening_spans(openings, length, height):
    """*openings* clamped into a wall of *length* x *height* and made
    disjoint along it: sorted (start, end, sill, top, kind) spans — an
    opening overlapping the one before it starts where that one ends."""
    spans = []
    for offset, ow, oh, sill, kind in sorted(openings):
        ow = min(ow, length)
        start = max(0.0, min(offset, length - ow))
        end = start + ow
        if spans:
            start = max(start, spans[-1][1])
        sill = max(0.0, min(sill, height))
        top = min(sill + oh, height)
        if end - start > 1e-6 and top - sill > 1e-6:
            spans.append((start, end, sill, top, kind))
    return spans


# ------------------------------------------------------ elevation outlines
def region_loops(add, sub=()):
    """The union of the *add* rectangles minus the *sub* ones, each
    (u0, z0, u1, z1), as polygons: [(outline, [holes])], outlines
    counter-clockwise and holes clockwise, collinear points dropped.
    Rectilinear, so it is exact on the grid of every rectangle edge; a
    corner where two solid cells only touch diagonally is split into
    two outlines rather than pinched."""
    add = [r for r in add if r[2] - r[0] > 1e-6 and r[3] - r[1] > 1e-6]
    if not add:
        return []
    rects = list(add) + [r for r in sub]
    us = sorted({round(v, 4) for r in rects for v in (r[0], r[2])})
    zs = sorted({round(v, 4) for r in rects for v in (r[1], r[3])})

    def inside(rs, u, z):
        return any(r[0] < u < r[2] and r[1] < z < r[3] for r in rs)

    nu, nz = len(us) - 1, len(zs) - 1
    filled = [[False] * nz for _ in range(nu)]
    for i in range(nu):
        cu = (us[i] + us[i + 1]) / 2.0
        for j in range(nz):
            cz = (zs[j] + zs[j + 1]) / 2.0
            filled[i][j] = inside(add, cu, cz) and not inside(sub, cu, cz)

    def full(i, j):
        return 0 <= i < nu and 0 <= j < nz and filled[i][j]

    edges = {}
    for i in range(nu):
        for j in range(nz):
            if not filled[i][j]:
                continue
            if not full(i, j - 1):
                edges.setdefault((i, j), []).append((i + 1, j))
            if not full(i + 1, j):
                edges.setdefault((i + 1, j), []).append((i + 1, j + 1))
            if not full(i, j + 1):
                edges.setdefault((i + 1, j + 1), []).append((i, j + 1))
            if not full(i - 1, j):
                edges.setdefault((i, j + 1), []).append((i, j))
    loops = []
    while edges:
        start = next(iter(edges))
        loop = [start]
        prev, cur = start, edges[start].pop()
        if not edges[start]:
            del edges[start]
        while cur != start:
            loop.append(cur)
            options = edges.get(cur)
            if not options:
                break
            dx, dz = cur[0] - prev[0], cur[1] - prev[1]
            if len(options) > 1:                # a pinch: turn left
                def turn(o):
                    ox, oz = o[0] - cur[0], o[1] - cur[1]
                    cross = dx * oz - dz * ox
                    return -cross
                options.sort(key=turn)
            nxt = options.pop(0)
            if not options:
                del edges[cur]
            prev, cur = cur, nxt
        pts = [(us[i], zs[j]) for i, j in loop]
        simple = []
        n = len(pts)
        for k in range(n):
            a, b, c = pts[k - 1], pts[k], pts[(k + 1) % n]
            if abs((b[0] - a[0]) * (c[1] - b[1])
                   - (b[1] - a[1]) * (c[0] - b[0])) > 1e-9:
                simple.append(b)
        if len(simple) >= 3:
            loops.append(simple)

    def area(p):
        return sum(p[k - 1][0] * p[k][1] - p[k][0] * p[k - 1][1]
                   for k in range(len(p))) / 2.0

    def contains(p, pt):
        x, y, hit = pt[0], pt[1], False
        for k in range(len(p)):
            (x1, y1), (x2, y2) = p[k - 1], p[k]
            if (y1 > y) != (y2 > y) and \
                    x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                hit = not hit
        return hit

    outers = [p for p in loops if area(p) > 0]
    holes = [p for p in loops if area(p) < 0]
    result = [(p, []) for p in outers]
    for h in holes:
        probe = ((h[0][0] + h[1][0]) / 2.0 + 1e-3 * (h[1][1] - h[0][1]),
                 (h[0][1] + h[1][1]) / 2.0 - 1e-3 * (h[1][0] - h[0][0]))
        owners = [r for r in result if contains(r[0], probe)]
        if owners:
            min(owners, key=lambda r: area(r[0]))[1].append(h)
    return result


class WallFrame:
    """Boxes and extruded outlines in a wall's own frame: u along the
    wall, n across it (world y for a horizontal wall, x for a vertical
    one), z up."""

    def __init__(self, horizontal: bool):
        self.horizontal = horizontal

    def box(self, name, u0, u1, n0, n1, z0, z1):
        u0, u1 = sorted((u0, u1))
        n0, n1 = sorted((n0, n1))
        z0, z1 = sorted((z0, z1))
        if self.horizontal:
            place = dict(x=u0, y=n0, width=u1 - u0, depth=n1 - n0)
        else:
            place = dict(x=n0, y=u0, width=n1 - n0, depth=u1 - u0)
        return CadNode("cube", name, dict(z=z0, height=max(z1 - z0, 0.01),
                                          center=False, **place))

    def slab(self, name, loops, n0, n1):
        """*loops* (from `region_loops`, in (u, z)) extruded from n0 to
        n1 across the wall; None when there is nothing to extrude."""
        if not loops:
            return None
        n0, n1 = sorted((n0, n1))
        ext = CadNode("linear_extrude", name, dict(height=n1 - n0))
        for outline, holes in loops:
            shape = CadNode("polygon", "Outline", dict(
                points=[[round(u, 3), round(z, 3)] for u, z in outline]))
            if holes:
                cut = CadNode("difference", "Openings", {})
                cut.add(shape)
                for h in holes:
                    cut.add(CadNode("polygon", "Opening", dict(
                        points=[[round(u, 3), round(z, 3)] for u, z in h])))
                ext.add(cut)
            else:
                ext.add(shape)
        if self.horizontal:
            rot = CadNode("rotate", name, dict(x=90.0, y=0.0, z=0.0))
            move = CadNode("translate", name, dict(x=0.0, y=n1, z=0.0))
        else:
            rot = CadNode("rotate", name, dict(x=90.0, y=0.0, z=90.0))
            move = CadNode("translate", name, dict(x=n0, y=0.0, z=0.0))
        rot.add(ext)
        move.add(rot)
        return move


# ---------------------------------------------------------------- walls
@dataclass
class Look:
    """Everything a floor's walls are finished with."""
    outside: tuple = (F.WALL_COLOR, "Render")
    inside: tuple = (F.WALL_COLOR, "Plaster")
    detail: dict = field(default_factory=lambda: F.outside_detail(""))
    joinery: tuple = F.JOINERY["White"]
    roof: tuple = ("#6b4a3a", "Roof tiles")
    key: str = ""


def build_walls(floor, look: Look, ground: bool = True) -> list:
    """Every wall of *floor* with its openings' joinery, as coloured
    nodes in the floor's frame. *ground* adds the plinth, front steps and
    canopies."""
    out = []
    H = float(floor.wall_height)
    slab = float(floor.slab_thickness)
    ft = F.FLOOR_THICKNESS
    for sg in wall_segments(floor):
        fr = WallFrame(sg.horizontal)
        hw = sg.thickness / 2.0
        spans = opening_spans(sg.openings, sg.length, H)
        holes = [(sg.a + s0, sill, sg.a + s1, top)
                 for s0, s1, sill, top, _k in spans]
        tag = "Wall" if sg.outside else "Inner wall"
        if sg.rail:
            out += balustrade(fr, sg)
            continue
        if sg.outside:
            s = sg.outside
            # the roof sits on the wall head (house_roof puts its planes
            # on the outer edge), so the facing stops at H
            add = [(sg.a - sg.ext_a, -slab, sg.b + sg.ext_b, H)]
            node = fr.slab(tag, region_loops(add, holes), sg.c, sg.c + s * hw)
            out.append(_color(node, *look.outside))
            lining = fr.slab("Wall lining", region_loops(
                [(sg.a, -ft, sg.b, H)], holes), sg.c - s * hw, sg.c)
            out.append(_color(lining, *look.inside))
            if ground:
                plinth = fr.slab("Plinth", region_loops(
                    [(sg.a - sg.ext_a - PLINTH_PROUD, -slab - PLINTH_DOWN,
                      sg.b + sg.ext_b + PLINTH_PROUD, PLINTH_TOP)], holes),
                    sg.c + s * (hw - 1.0), sg.c + s * (hw + PLINTH_PROUD))
                out.append(_color(plinth, *look.detail["plinth"]))
        else:
            node = fr.slab(tag, region_loops(
                [(sg.a - sg.ext_a, -ft, sg.b + sg.ext_b, H)], holes),
                sg.c - hw, sg.c + hw)
            out.append(_color(node, *look.inside))
        for s0, s1, sill, top, kind in spans:
            out += opening_nodes(fr, sg, sg.a + s0, sg.a + s1, sill, top,
                                 kind, look, H, ground)
    return [n for n in out if n.children and n.children[0] is not None]


def balustrade(fr, sg) -> list:
    """The open side of a stairwell: a handrail on square spindles over
    a base rail, 900 high."""
    wood, white = ("#8a6234", "Default"), F.SKIRTING
    out = [_color(fr.box("Handrail", sg.a, sg.b, sg.c - 35.0, sg.c + 35.0,
                         860.0, 920.0), *wood),
           _color(fr.box("Base rail", sg.a, sg.b, sg.c - 30.0, sg.c + 30.0,
                         -F.FLOOR_THICKNESS, 60.0), *white)]
    count = max(1, int((sg.b - sg.a) // 120.0))
    step = (sg.b - sg.a) / count
    for i in range(count + 1):
        u = sg.a + i * step
        u = min(max(u, sg.a + 20.0), sg.b - 20.0)
        out.append(_color(fr.box("Spindle", u - 16.0, u + 16.0,
                                 sg.c - 16.0, sg.c + 16.0, 60.0, 860.0),
                          *white))
    return out


# -------------------------------------------------------------- joinery
def _frame_loops(u0, u1, z0, z1, w, bottom=True):
    """A frame's outline: the rectangle minus its inside, open at the
    bottom for a door (*bottom* False)."""
    inner = (u0 + w, z0 + (w if bottom else -1.0), u1 - w, z1 - w)
    return region_loops([(u0, z0, u1, z1)], [inner])


def opening_nodes(fr, sg, u0, u1, sill, top, kind, look, H, ground):
    """The joinery filling one opening of wall *sg* from u0 to u1 and
    sill to top."""
    hw = sg.thickness / 2.0
    s = sg.outside or 1                    # interior walls: either way
    face = sg.c + s * hw                   # the outside (or +) face
    depth = min(FRAME_DEPTH, sg.thickness * 0.6)
    reveal = max(0.0, min(REVEAL, sg.thickness - depth - 10.0)) \
        if sg.outside else (sg.thickness - depth) / 2.0
    f_out = face - s * reveal              # frame's outer face
    f_in = f_out - s * depth
    width, height = u1 - u0, top - sill
    jc, jm = look.joinery
    out = []
    if kind == "window":
        fw = min(FRAME_W, width / 6.0, height / 6.0)
        out.append(_color(fr.slab("Window frame", _frame_loops(
            u0, u1, sill, top, fw), f_out, f_in), jc, jm))
        lights = max(1, round(width / 650.0))
        bars = []
        if height >= 1000.0:
            tz = top - fw - min(380.0, height * 0.3)
            bars.append(fr.box("Transom", u0 + fw, u1 - fw, f_out - s * 5,
                               f_in + s * 5, tz - 22.0, tz + 22.0))
        step = (width - 2 * fw) / lights
        for i in range(1, lights):
            m = u0 + fw + i * step
            bars.append(fr.box("Mullion", m - 22.0, m + 22.0, f_out - s * 5,
                               f_in + s * 5, sill + fw, top - fw))
        for b in bars:
            out.append(_color(b, jc, jm))
        mid = (f_out + f_in) / 2.0
        out.append(_color(fr.box("Glazing", u0 + fw, u1 - fw,
                                 mid - GLASS_THICKNESS / 2.0,
                                 mid + GLASS_THICKNESS / 2.0,
                                 sill + fw, top - fw),
                          GLASS_COLOR, "Glass", GLASS_ALPHA))
        if sg.outside and sill > 1.0:
            sc, sm = look.detail["sill"]
            out.append(_color(fr.box("Sill", u0 - 40.0, u1 + 40.0,
                                     f_out, face + s * 45.0,
                                     sill - 50.0, sill + 15.0), sc, sm))
            inner = sg.c - s * hw
            out.append(_color(fr.box("Window board", u0 - 30.0, u1 + 30.0,
                                     f_in, inner - s * 25.0, sill - 22.0,
                                     sill + 3.0), *F.SKIRTING))
        if sg.outside:
            out += _head(fr, sg, u0, u1, top, face, s, look, H)
        return out
    if kind == "garage door":
        fw = 50.0
        out.append(_color(fr.slab("Door frame", _frame_loops(
            u0, u1, sill, top, fw, bottom=False), f_out, f_in), jc, jm))
        colour = F.GARAGE_DOORS[hash(look.key) % len(F.GARAGE_DOORS)] \
            if look.key else GARAGE_DOOR_COLOR
        t = min(GARAGE_DOOR_THICKNESS, depth)
        back = fr.box("Garage door", u0 + fw, u1 - fw, f_out - s * (t - 4),
                      f_out - s * t, sill, top - fw)
        out.append(_color(back, _shade(colour, 0.55), "Metal"))
        sections = 4
        sh = (top - fw - sill) / sections
        for i in range(sections):
            z0 = sill + i * sh + (6.0 if i else 0.0)
            out.append(_color(fr.box("Door section", u0 + fw + 4, u1 - fw - 4,
                                     f_out - s * 6, f_out - s * (t - 4),
                                     z0, sill + (i + 1) * sh - 6.0),
                              colour, "Metal"))
        out += _threshold(fr, sg, u0, u1, look, ground)
        if sg.outside:
            out += _head(fr, sg, u0, u1, top, face, s, look, H)
        return out
    # a door
    if sg.outside:
        fw = min(FRAME_W, width / 5.0)
        out.append(_color(fr.slab("Door frame", _frame_loops(
            u0, u1, sill, top, fw, bottom=False), f_out, f_in), jc, jm))
        colour = F.front_door(look.key, sg.c, u0)
        out += _door_leaf(fr, u0 + fw + 3, u1 - fw - 3, sill + 12,
                          top - fw - 3, (f_out + f_in) / 2.0, s, 48.0,
                          colour, "Plastic", glazed=True, letter=True)
        out += _threshold(fr, sg, u0, u1, look, ground)
        out += _head(fr, sg, u0, u1, top, face, s, look, H)
        if ground and sill < 1.0:
            sc, sm = look.detail["sill"]
            out.append(_color(fr.box("Front step", u0 - 150.0, u1 + 150.0,
                                     face - s * 5.0, face + s * 320.0,
                                     -180.0, -20.0), sc, sm))
            if top + 380.0 < H + CEILING:
                rc, rm = look.roof
                roof = CadNode("hull", "Canopy", {})
                roof.add(fr.box("Canopy back", u0 - 300.0, u1 + 300.0,
                                face, face + s * 1.0, top + 300.0,
                                top + 360.0))
                roof.add(fr.box("Canopy front", u0 - 300.0, u1 + 300.0,
                                face + s * 750.0, face + s * 751.0,
                                top + 150.0, top + 210.0))
                out.append(_color(roof, rc, rm))
                out.append(_color(fr.box("Canopy fascia", u0 - 300.0,
                                         u1 + 300.0, face + s * 745.0,
                                         face + s * 770.0, top + 110.0,
                                         top + 215.0), jc, jm))
        return out
    lining = 30.0
    n0, n1 = sg.c - hw, sg.c + hw
    out.append(_color(fr.slab("Door lining", _frame_loops(
        u0, u1, sill, top, lining, bottom=False), n0, n1), *F.SKIRTING))
    for side in (-1, 1):
        wall_face = sg.c + side * hw
        arch = region_loops([(u0 - ARCHITRAVE_W, sill,
                              u1 + ARCHITRAVE_W,
                              min(top + ARCHITRAVE_W, H))],
                            [(u0, sill - 1.0, u1, top)])
        out.append(_color(fr.slab("Architrave", arch, wall_face,
                                  wall_face + side * ARCHITRAVE_T),
                          *F.SKIRTING))
    out += _door_leaf(fr, u0 + lining + 3, u1 - lining - 3, sill + 8,
                      top - lining - 3, sg.c, 1, 40.0, F.INTERIOR_DOOR[0],
                      F.INTERIOR_DOOR[1], glazed=False, letter=False)
    out += _threshold(fr, sg, u0, u1, look, ground)
    return out


def _head(fr, sg, u0, u1, top, face, s, look, H):
    """What spans the top of an opening outside: a stone lintel, a
    brick soldier course or a timber trim."""
    kind = look.detail["head"]
    if kind == "none":
        return []
    if kind == "timber":
        if top + 90.0 > H:
            return []
        return [_color(fr.box("Head trim", u0 - 60.0, u1 + 60.0,
                              face - s * 5.0, face + s * 22.0, top,
                              top + 90.0), *look.joinery)]
    h = 150.0 if kind == "stone" else 215.0
    if top + h > H:
        return []
    if kind == "stone":
        colour, material = look.detail["sill"]
    else:
        colour, material = _shade(look.outside[0], 0.82), "Brick"
    return [_color(fr.box("Lintel", u0 - 110.0, u1 + 110.0,
                          face - s * 60.0, face + s * 8.0, top, top + h),
                   colour, material)]


def _threshold(fr, sg, u0, u1, look, ground):
    hw = sg.thickness / 2.0
    return [_color(fr.box("Threshold", u0, u1, sg.c - hw, sg.c + hw,
                          -F.FLOOR_THICKNESS, 10.0), *F.THRESHOLD)]


def _door_leaf(fr, u0, u1, z0, z1, n_mid, s, t, colour, material,
               glazed, letter):
    """A panelled door leaf centred on n_mid: raised panels on both
    faces, a glazed top for a front door, lever handles, a letter
    plate."""
    out = []
    w, h = u1 - u0, z1 - z0
    rail = min(110.0, w / 6.0)
    holes = []
    if glazed and h > 1500.0:
        gz0, gz1 = z0 + h * 0.62, z1 - rail
        holes = [(u0 + rail, gz0, u1 - rail, gz1)]
    leaf = fr.slab("Door", region_loops([(u0, z0, u1, z1)], holes),
                   n_mid - t / 2.0, n_mid + t / 2.0)
    out.append(_color(leaf, colour, material))
    if holes:
        g = holes[0]
        out.append(_color(fr.box("Door glass", g[0], g[2], n_mid - 3.0,
                                 n_mid + 3.0, g[1], g[3]), GLASS_COLOR,
                          "Glass", DOOR_GLASS_ALPHA))
        panel_top = holes[0][1] - rail
        rows = [(z0 + rail, panel_top)]
    else:
        mid = z0 + h * 0.45
        rows = [(z0 + rail, mid - rail / 2.0), (mid + rail / 2.0, z1 - rail)]
    cols = [(u0 + rail, (u0 + u1) / 2.0 - rail / 2.0),
            ((u0 + u1) / 2.0 + rail / 2.0, u1 - rail)]
    for side in (-1, 1):
        face = n_mid + side * t / 2.0
        for pz0, pz1 in rows:
            for pu0, pu1 in cols:
                if pz1 - pz0 > 50.0 and pu1 - pu0 > 50.0:
                    out.append(_color(fr.box("Panel", pu0, pu1, face - side,
                                             face + side * 6.0, pz0, pz1),
                                      _shade(colour, 1.04), material))
        lever_u = u1 - 90.0
        out.append(_color(fr.box("Handle", lever_u - 20.0, lever_u + 20.0,
                                 face, face + side * 55.0, 1000.0,
                                 1060.0), "#c9ccd0", "Metal"))
        out.append(_color(fr.box("Lever", lever_u - 130.0, lever_u + 20.0,
                                 face + side * 40.0, face + side * 62.0,
                                 1015.0, 1045.0), "#c9ccd0", "Metal"))
    if letter:
        face = n_mid + s * t / 2.0
        cu = (u0 + u1) / 2.0
        out.append(_color(fr.box("Letter plate", cu - 150.0, cu + 150.0,
                                 face, face + s * 10.0, z0 + h * 0.36,
                                 z0 + h * 0.36 + 60.0), "#c8a650", "Gold"))
    return out


# -------------------------------------------------------- inside a room
def _faces_of(room, side, segments):
    """The pieces of wall *room* sees on its *side*: (u0, u1, face n,
    direction into the room, segment) — clipped to the room's inside
    between the walls on its other sides."""
    hor, c, lo, hi, into = _room_lines(room)[side]
    own = [sg for sg in segments if sg.horizontal == hor and not sg.rail
           and abs(sg.c - _r(c)) < 1e-6 and sg.b > lo + 1e-6
           and sg.a < hi - 1e-6]

    def half(end_side):
        h2, c2, lo2, hi2, _i = _room_lines(room)[end_side]
        near = [sg.thickness for sg in segments if sg.horizontal == h2
                and abs(sg.c - _r(c2)) < 1e-6 and sg.b > lo2 + 1e-6
                and sg.a < hi2 - 1e-6]
        return min(near) / 2.0 if near else 0.0

    ends = ("W", "E") if hor else ("S", "N")
    start, stop = lo + half(ends[0]), hi - half(ends[1])
    pieces = []
    for sg in own:
        u0, u1 = max(sg.a, start), min(sg.b, stop)
        if u1 - u0 > 1e-6:
            pieces.append((u0, u1, sg.c + into * sg.thickness / 2.0, into,
                           sg))
    return pieces


def room_inside(room) -> tuple:
    """(x0, y0, x1, y1) of *room*'s floor between its walls — needs the
    segments, so `room_nodes` computes it; this is the centre-line
    fallback."""
    return room.x, room.y, room.x + room.w, room.y + room.d


def _footprint(f):
    """The plan box of a placed piece of furniture."""
    from .house import part_tris
    tris = part_tris(f.part_id, f.dims)
    if not tris:
        return None
    xs = [p[0] for t in tris for p in t]
    ys = [p[1] for t in tris for p in t]
    a = math.radians(f.rz)
    ca, sa = math.cos(a), math.sin(a)
    pts = [(f.x + x * ca - y * sa, f.y + x * sa + y * ca)
           for x in (min(xs), max(xs)) for y in (min(ys), max(ys))]
    return (min(p[0] for p in pts), min(p[1] for p in pts),
            max(p[0] for p in pts), max(p[1] for p in pts))


def _fixture_ranges(room, side, face, into, words, reach=180.0):
    """The stretches (u0, u1) of *side* that a piece whose part id holds
    one of *words* stands against."""
    out = []
    hor = side in ("N", "S")
    for f in room.furniture:
        pid = f.part_id.lower()
        if not any(w in pid for w in words) or "cabinet" in pid:
            continue
        box = _footprint(f)
        if box is None:
            continue
        near = (box[1] - face if side == "S" else face - box[3]) if hor \
            else (box[0] - face if side == "W" else face - box[2])
        if near > reach:
            continue
        out.append((box[0] - 60.0, box[2] + 60.0) if hor
                   else (box[1] - 60.0, box[3] + 60.0))
    return out


def room_nodes(room, floor, segments=None) -> list:
    """What lines *room*: its floor covering, skirting boards, and tiles
    or panelling where they go (`house_finishes.finish_of` /
    `coverage_of`) — around every opening on its walls, whichever room
    the opening was drawn from."""
    if not room.indoor or _is_void(room):
        return []
    segments = segments if segments is not None else wall_segments(floor)
    H = float(floor.wall_height)
    ft = F.FLOOR_THICKNESS
    faces = {side: _faces_of(room, side, segments) for side in "SNWE"}

    def inner(side, default):
        return faces[side][0][2] if faces[side] else default

    x0, x1 = inner("W", room.x), inner("E", room.x + room.w)
    y0, y1 = inner("S", room.y), inner("N", room.y + room.d)
    colour, material = F.flooring_of(room)
    out = [_color(CadNode("cube", f"{room.name} floor", dict(
        x=x0, y=y0, z=-ft, width=max(x1 - x0, 1.0),
        depth=max(y1 - y0, 1.0), height=ft, center=False)),
        colour, material)]
    finish = F.finish_of(room)
    coverage = F.coverage_of(room) if finish else None
    wall_look = F.ROOM_FINISHES[finish][0] if finish else None
    for side in "SNWE":
        hor = side in ("N", "S")
        fr = WallFrame(hor)
        for u0, u1, face, into, sg in faces[side]:
            spans = opening_spans(sg.openings, sg.length, H)
            holes = [(sg.a + s0, sill, sg.a + s1, top)
                     for s0, s1, sill, top, _k in spans
                     if sg.a + s1 > u0 and sg.a + s0 < u1]
            doors = [(sg.a + s0, sg.a + s1, _k)
                     for s0, s1, sill, top, _k in spans if sill < 150.0]
            bands = []
            if coverage == "full":
                bands = [(u0, 0.0, u1, H)]
            elif coverage in ("half", "wet"):
                bands = [(u0, 0.0, u1, F.HALF_TILE)]
            if coverage == "wet":
                bands += [(max(a, u0), 0.0, min(b, u1), H) for a, b in
                          _fixture_ranges(room, side, face, into,
                                          F.WET_PARTS)]
            if coverage == "splash":
                z0, z1 = F.SPLASH
                bands += [(max(a, u0), z0, min(b, u1), z1) for a, b in
                          _fixture_ranges(room, side, face, into,
                                          F.SPLASH_PARTS)]
            lining = fr.slab("Wall tiles", region_loops(bands, holes),
                             face, face + into * F.TILE_THICKNESS)
            if lining is not None:
                out.append(_color(lining, *wall_look))
            if coverage in (None, "splash"):
                gaps = [(a - (ARCHITRAVE_W if k == "door" and sg.interior
                              else 0.0),
                         b + (ARCHITRAVE_W if k == "door" and sg.interior
                              else 0.0)) for a, b, k in doors]
                cursor = u0
                for a, b in sorted(gaps) + [(u1, u1)]:
                    if a - cursor > 20.0:
                        out.append(_color(fr.box(
                            "Skirting", cursor, min(a, u1), face,
                            face + into * SKIRTING_T, 0.0, SKIRTING_H),
                            *F.SKIRTING))
                    cursor = max(cursor, b)
    return out
