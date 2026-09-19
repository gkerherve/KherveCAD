"""**Stadiums** (Qt-free): a whole ground built round any sport's field,
in the shape real grounds come in — the parts in Library ▸ Buildings &
places ▸ Sport ▸ Stadiums, and what an assistant inserts to get a good
stadium in one call.

Shapes (`SHAPES`):
- rounded   — a bowl that hugs the pitch in a rounded rectangle
              (Emirates, most new football grounds);
- oval      — an elliptical bowl (athletics, older multi-sport grounds);
- circular  — a round bowl;
- horseshoe — the rounded bowl left open at one end;
- rectangular — four separate straight stands with open corners
              (a traditional English ground);
- arena     — an indoor hall: a rounded bowl under a closed roof.

A bowl is a stack of RINGS offset outward from the field's outline, a
superellipse |x/a|^p + |y/b|^p = 1 whose a, b grow by the row's depth —
p = 2 is the ellipse, larger p squares it. Each ring is ONE 2D polygon
(outer loop + inner hole, or a C shape where the players' tunnel or the
horseshoe's open end cuts it) under a linear_extrude, so a 55-row bowl
is a few hundred nodes and needs no boolean. Each row: a concrete step
from the ground, a seat strip and a seat-back strip. Two tiers when
`upper_rows` > 0, with a glazed ring of executive boxes between them.
Then the facade, the roof (`roof` 0 open, 1 over the stands, 2 closed),
lights, video scoreboards, the dugouts of players' bucket seats, and
the changing rooms — built by the House Builder (`house.house_from_spec`)
behind the south stand, reached by a tunnel through the lower tier.

The build's name carries the seat count (`capacity`), so an assistant
can tell a 20 000 ground from a 60 000 one without measuring.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from . import library_park as park
from . import library_sport as sport
from .city_buildings import _f, box, color, cyl, group, move, turn
from .model import CadNode

CATEGORY = "Sport: stadiums"
TREAD, RISER, UPPER_RISER = 800.0, 400.0, 550.0
FRONT_WALL = 1000.0          # the lower tier starts behind a 1 m wall
TUNNEL = 3200.0              # players' tunnel width
SEAT_PITCH = 500.0
SAMPLES = 72                 # points per ring outline
CONCRETE, FASCIA = "#9a9ea3", "#f2f2f2"


# ------------------------------------------------------------- sports
def _football(d):
    return park.build_football(dict(length=105000, width=68000))


def _basketball(d):
    return park.build_basketball(dict(length=28000, width=15000))


#: sport -> field builder, half size of the field and its run-off (the
#: outline the bowl hugs), gap to the first row, whether it has dugouts
SPORTS = {
    "Football": dict(build=_football, hx=56500, hy=38000, margin=3000,
                     dugouts=True),
    "Rugby": dict(build=sport.build_rugby, hx=65000, hy=40000, margin=3000,
                  dugouts=True),
    "Athletics": dict(build=sport.build_track, hx=89000, hy=47500,
                      margin=1500, dugouts=False),
    "Tennis": dict(build=lambda d: sport.build_show_court(
        dict(length=40000, width=20000)), hx=20000, hy=10000, margin=2000,
        dugouts=False),
    "Basketball": dict(build=_basketball, hx=16000, hy=9500, margin=1500,
                       dugouts=False),
    "Volleyball": dict(build=lambda d: sport.build_volleyball({}),
                       hx=12000, hy=7500, margin=1500, dugouts=False),
    "Badminton": dict(build=lambda d: sport.build_badminton({}), hx=8700,
                      hy=5050, margin=1500, dugouts=False),
    "Handball": dict(build=lambda d: sport.build_handball({}), hx=22000,
                     hy=12000, margin=1500, dugouts=False),
}

#: shape -> superellipse exponent (None = straight stands), roof default
SHAPES = {"rounded": 5.0, "oval": 2.0, "circular": 2.0, "horseshoe": 5.0,
          "rectangular": None, "arena": 4.0}


# ------------------------------------------------------------ geometry
def base_axes(shape, hx, hy):
    """The superellipse through the field's corners: a, b, p."""
    p = SHAPES[shape]
    if shape == "circular":
        r = math.hypot(hx, hy)
        return r, r, 2.0
    k = 2.0 ** (1.0 / p)
    return hx * k, hy * k, p


def point(a, b, p, t):
    c, s = math.cos(math.radians(t)), math.sin(math.radians(t))
    e = 2.0 / p
    return (a * math.copysign(abs(c) ** e, c),
            b * math.copysign(abs(s) ** e, s))


def gap_for(shape, a, p, tunnel):
    """The t interval (degrees) cut out of a ring of semi-axis *a*: the
    tunnel on the south side, the open end of a horseshoe, or None."""
    if shape == "horseshoe":
        return (-38.0, 38.0)
    if tunnel:
        half = math.degrees(math.asin(min(1.0, (TUNNEL / 2 / a) ** (p / 2))))
        return (270.0 - half, 270.0 + half)
    return None


def _arc(a, b, p, t0, t1, n):
    return [point(a, b, p, t0 + (t1 - t0) * i / n) for i in range(n + 1)]


def ring_polygon(shape, a, b, p, d0, d1, tunnel=False, name="Ring"):
    """The band between offsets d0 and d1 as ONE polygon: a loop with a
    hole, or a C shape when a gap cuts it."""
    ai, bi, ao, bo = a + d0, b + d0, a + d1, b + d1
    gi, go = gap_for(shape, ai, p, tunnel), gap_for(shape, ao, p, tunnel)
    if gi is None:
        outer = _arc(ao, bo, p, 0.0, 360.0, SAMPLES)[:-1]
        inner = _arc(ai, bi, p, 0.0, 360.0, SAMPLES)[:-1]
        poly = park._poly(outer + inner, name)
        n = len(outer)
        poly.params["paths"] = [list(range(n)), list(range(n, 2 * n))]
        return poly
    outer = _arc(ao, bo, p, go[1], go[0] + 360.0, SAMPLES)
    inner = _arc(ai, bi, p, gi[1], gi[0] + 360.0, SAMPLES)[::-1]
    return park._poly(outer + inner, name)


def disc_polygon(a, b, p, d, name="Disc"):
    return park._poly(_arc(a + d, b + d, p, 0.0, 360.0, SAMPLES)[:-1], name)


def _ext(shape_node, z0, h, name):
    ex = CadNode("linear_extrude", name, dict(height=max(h, 1.0), twist=0.0,
                                              scale=1.0, center=False,
                                              segments=0))
    ex.add(shape_node)
    return move(ex, 0, 0, z0, name)


def perimeter(a, b, p, d, gap=None):
    pts = _arc(a + d, b + d, p, 0.0, 360.0, 180)
    length = sum(math.dist(pts[i], pts[i + 1]) for i in range(180))
    if gap:
        length *= 1.0 - (gap[1] - gap[0]) / 360.0
    return length


# ------------------------------------------------------------ the bowl
class Bowl:
    """The rows of one bowl and where everything else goes round it."""

    def __init__(self, shape, sp, rows, upper_rows, tunnel):
        self.shape, self.tunnel = shape, tunnel
        self.a, self.b, self.p = base_axes(shape, sp["hx"], sp["hy"])
        self.margin = sp["margin"]
        self.rows, self.upper_rows = rows, upper_rows
        self.lower_out = self.margin + rows * TREAD
        self.lower_top = FRONT_WALL + rows * RISER
        self.upper_in = self.lower_out + 1500.0 - 2500.0
        self.upper_base = self.lower_top + 4500.0
        if upper_rows:
            self.end = self.upper_in + upper_rows * TREAD
            self.top = self.upper_base + 1000.0 + upper_rows * UPPER_RISER
        else:
            self.end, self.top = self.lower_out, self.lower_top
        self.seats = 0

    def ring(self, d0, d1, z0, z1, name, tunnel=None):
        tun = self.tunnel if tunnel is None else tunnel
        return _ext(ring_polygon(self.shape, self.a, self.b, self.p, d0, d1,
                                 tun, name), z0, z1 - z0, name)

    def _count(self, d, tunnel):
        gap = gap_for(self.shape, self.a + d, self.p, tunnel)
        self.seats += int(perimeter(self.a, self.b, self.p, d, gap)
                          // SEAT_PITCH)

    def tier(self, colour):
        steps, seats = [], []
        for r in range(self.rows):
            d, top = self.margin + r * TREAD, FRONT_WALL + (r + 1) * RISER
            steps.append(self.ring(d, d + TREAD, 0.0, top, "Step"))
            seats += [self.ring(d + 250, d + 650, top, top + 420, "Seats"),
                      self.ring(d + 610, d + 670, top + 420, top + 800,
                                "Seat backs")]
            self._count(d + 450, self.tunnel)
        for r in range(self.upper_rows):
            d = self.upper_in + r * TREAD
            z0 = self.upper_base + r * UPPER_RISER * 0.5
            top = self.upper_base + 1000.0 + (r + 1) * UPPER_RISER
            steps.append(self.ring(d, d + TREAD, z0, top, "Upper step",
                                   tunnel=False))
            seats += [self.ring(d + 250, d + 650, top, top + 420, "Seats",
                                tunnel=False),
                      self.ring(d + 610, d + 670, top + 420, top + 800,
                                "Seat backs", tunnel=False)]
            self._count(d + 450, False)
        parts = [color(group("Terraces", steps), CONCRETE, "Concrete"),
                 color(group("Seats", seats), colour, "Plastic")]
        if self.upper_rows:
            parts += [
                color(self.ring(self.lower_out - 300, self.lower_out,
                                self.lower_top, self.upper_base,
                                "Executive boxes", tunnel=False),
                      "#10161f", "Glass", alpha=0.8),
                color(self.ring(self.upper_in - 200, self.upper_in + 200,
                                self.upper_base - 600, self.upper_base
                                + 1000, "Upper tier fascia", tunnel=False),
                      FASCIA, "Plastic")]
        return group("Seating bowl", parts)

    def xy(self, d, t):
        return point(self.a + d, self.b + d, self.p, t)


def build_bowl(shape, sp, dims, colour):
    rows = int(_f(dims.get("rows"), 25))
    upper = int(_f(dims.get("upper_rows"), 0))
    roof = int(_f(dims.get("roof"), 1))
    changing = _f(dims.get("changing"), 1) >= 0.5
    bowl = Bowl(shape, sp, rows, upper, tunnel=changing)
    parts = [bowl.tier(colour)]
    indoor = shape == "arena"
    face_d = bowl.end + 3000.0
    wall_h = bowl.top + 3000.0
    facade_col, facade_mat, alpha = (("#c9ccd1", "Concrete", 1.0) if indoor
                                     else ("#35506e", "Glass", 0.6))
    facade = [color(bowl.ring(face_d, face_d + 400, 0.0, wall_h,
                              "Facade", tunnel=False), facade_col,
                    facade_mat, alpha=alpha)]
    for z in (0.0, bowl.lower_top, wall_h - 1200):
        facade.append(color(bowl.ring(face_d + 400, face_d + 900, z,
                                      z + 1200, "Facade band",
                                      tunnel=False), FASCIA, "Plastic"))
    if indoor:
        facade.append(color(bowl.ring(face_d - 50, face_d + 450,
                                      bowl.lower_top, bowl.lower_top + 3500,
                                      "Glass band", tunnel=False),
                            "#35506e", "Glass", alpha=0.6))
    if shape != "horseshoe":
        parts.append(group("Facade", facade))
    roof_z = wall_h + 1500.0
    if roof >= 2 or indoor:
        parts.append(color(_ext(disc_polygon(bowl.a, bowl.b, bowl.p,
                                             face_d + 3000, "Roof"),
                                roof_z, 1200, "Roof"), "#e8eaec", "Metal"))
        parts.append(color(_ext(disc_polygon(bowl.a, bowl.b, bowl.p,
                                             bowl.margin - 4000,
                                             "Skylight"),
                                roof_z + 1200, 300, "Skylight"), "#bcd4e6",
                           "Glass", alpha=0.5))
    elif roof == 1:
        parts.append(color(bowl.ring(bowl.margin + 4000, face_d + 5000,
                                     roof_z, roof_z + 1000, "Roof",
                                     tunnel=False), "#e8eaec", "Metal"))
        parts.append(color(bowl.ring(bowl.margin - 3000, bowl.margin + 4000,
                                     roof_z + 200, roof_z + 800,
                                     "Translucent roof edge", tunnel=False),
                           "#d7e6f2", "Glass", alpha=0.45))
    if roof >= 1 or indoor:
        parts.append(color(bowl.ring(bowl.margin + 3000, bowl.margin + 3400,
                                     roof_z - 400, roof_z, "Roof lights",
                                     tunnel=False), "#fffbe8", "Emissive"))
        columns = []
        for i in range(16):
            x, y = bowl.xy(face_d + 1500, i * 22.5 + 11.25)
            columns.append(cyl("Roof column", x, y, 0, roof_z, 700, 500,
                               seg=12))
        parts.append(color(group("Roof columns", columns), "#c9ccd1",
                           "Metal"))
    else:
        masts = []
        for t in (45.0, 135.0, 225.0, 315.0):
            x, y = bowl.xy(face_d + 8000, t)
            rz = math.degrees(math.atan2(-y, -x))
            masts.append(move(turn(sport.floodlight_mast(bowl.top + 15000),
                                   z=rz), x, y, 0, "Floodlight mast"))
        parts.append(group("Floodlights", masts))
    parts += _screens(bowl, indoor, roof_z)
    return bowl, parts


def _screens(bowl, indoor, roof_z):
    if indoor:
        hung = move(group("Centre-hung scoreboard", [
            move(turn(sport.video_screen(6000, 3500, legs=False), z=a),
                 3100 * math.sin(math.radians(a)),
                 -3100 * math.cos(math.radians(a)), 0, "Face")
            for a in (0, 90, 180, 270)]), 0, 0, roof_z - 9000,
            "Centre-hung scoreboard")
        return [hung]
    boards = []
    d = bowl.upper_in if bowl.upper_rows else bowl.lower_out
    z = (bowl.lower_top + 800) if bowl.upper_rows else bowl.lower_top + 1500
    for s in (-1, 1):
        x, _ = bowl.xy(d, 0.0 if s > 0 else 180.0)
        boards.append(move(turn(sport.video_screen(12000, 6000, legs=False),
                                z=-90.0 * s), x, 0, z, "Video scoreboard"))
    if bowl.shape == "horseshoe":
        boards = boards[1:]
    return boards


# -------------------------------------------------- straight stands
def build_stands(sp, dims, colour):
    """Four straight stands with open corners, the south one split for
    the tunnel; each under its own cantilever roof."""
    rows = int(_f(dims.get("rows"), 25)) + int(_f(dims.get("upper_rows"), 0))
    roof = int(_f(dims.get("roof"), 1))
    changing = _f(dims.get("changing"), 1) >= 0.5
    hx, hy, m = sp["hx"], sp["hy"], sp["margin"]
    top = FRONT_WALL + rows * RISER
    depth = rows * TREAD
    stands, seat_count = [], 0

    def stand(name, length, splits):
        nonlocal seat_count
        pieces = []
        for x0, ln in splits:
            pieces += [
                color(group("Steps", [box("Step", x0, m + r * TREAD, 0, ln,
                                          TREAD, FRONT_WALL + (r + 1)
                                          * RISER)
                                      for r in range(rows)]),
                      CONCRETE, "Concrete"),
                color(group("Seats", [box("Seats", x0 + 100, m + r * TREAD
                                          + 250, FRONT_WALL + (r + 1)
                                          * RISER, ln - 200, 420, 800)
                                      for r in range(rows)]),
                      colour, "Plastic")]
            seat_count += rows * int((ln - 200) // SEAT_PITCH)
        if roof >= 1:
            pieces.append(color(group("Roof", [
                box("Roof", -length / 2, m - 3000, top + 6000, length,
                    depth + 3500, 600),
                box("Back wall", -length / 2, m + depth, 0, length, 300,
                    top + 6000)]), "#e8eaec", "Metal"))
        return group(name, pieces)

    long_x = hx * 2
    south = ([(-hx, hx - TUNNEL / 2), (TUNNEL / 2, hx - TUNNEL / 2)]
             if changing else [(-hx, long_x)])
    for name, rz, off, length, splits in (
            ("North stand", 0.0, hy, long_x, [(-hx, long_x)]),
            ("South stand", 180.0, hy, long_x, south),
            ("East stand", -90.0, hx, hy * 2, [(-hy, hy * 2)]),
            ("West stand", 90.0, hx, hy * 2, [(-hy, hy * 2)])):
        node = stand(name, length, splits)
        if rz == 180.0:     # the split must land on x = 0 after turning
            stands.append(move(turn(node, z=rz), 0, -off, 0, name))
        else:
            dx = -off * math.sin(math.radians(rz))
            dy = off * math.cos(math.radians(rz))
            stands.append(move(turn(node, z=rz), dx, dy, 0, name))
    stands_group = group("Stands", stands)
    masts = []
    if roof == 0:
        for sx in (-1, 1):
            for sy in (-1, 1):
                x, y = sx * (hx + m + 6000), sy * (hy + m + 6000)
                rz = math.degrees(math.atan2(-y, -x))
                masts.append(move(turn(sport.floodlight_mast(top + 15000),
                                       z=rz), x, y, 0, "Floodlight mast"))
    info = dict(south_edge=-(hy + m + depth), top=top, seats=seat_count)
    return info, [stands_group] + ([group("Floodlights", masts)]
                                   if masts else [])


# ------------------------------------------------- changing rooms etc.
def changing_rooms_spec(y_top):
    """Two teams' dressing rooms, showers and toilets, the referees', a
    physio room and a lounge, off a players' corridor whose north wall
    is at *y_top* (its door on x = 0 meets the tunnel)."""
    lockers = lambda wall, alongs: [dict(part_id="office_lockers", wall=wall,
                                         along=a) for a in alongs]
    showers = lambda alongs: [dict(part_id="home_shower", wall="S", along=a)
                              for a in alongs]
    y_c, y_r, y_s = y_top - 1500, y_top - 7500, y_top - 11500
    rooms = [
        dict(name="Players corridor", x=-16000, y=y_c, w=32000, d=1500,
             flooring="Polished concrete",
             openings=[dict(kind="door", side="N", offset=15000, width=2000,
                            height=2400)]),
        dict(name="Home dressing room", x=-16000, y=y_r, w=10000, d=6000,
             flooring="Grey porcelain",
             openings=[dict(kind="door", side="N", offset=8500, width=1200),
                       dict(kind="door", side="S", offset=2500, width=900),
                       dict(kind="door", side="S", offset=7500, width=900)],
             furniture=lockers("W", (1500, 3000, 4500))
             + lockers("N", (1500, 3000, 4500, 6000))
             + [dict(part_id="lab_whiteboard", wall="E", along=3000),
                dict(part_id="home_bench", x=5000, y=3000)]),
        dict(name="Home showers", x=-16000, y=y_s, w=6000, d=4000,
             finish="White tiles", furniture=showers((1000, 2500, 4000,
                                                      5300))),
        dict(name="Home toilets", x=-10000, y=y_s, w=4000, d=4000,
             furniture=[dict(part_id="home_toilet", wall="S", along=1000),
                        dict(part_id="home_toilet", wall="S", along=2500),
                        dict(part_id="home_washbasin", wall="E",
                             along=2500)]),
        dict(name="Referees room", x=-6000, y=y_r, w=6000, d=6000,
             flooring="Grey porcelain",
             openings=[dict(kind="door", side="N", offset=3000)],
             furniture=lockers("W", (3000,))
             + [dict(part_id="home_desk", wall="E", along=3000),
                dict(part_id="home_shower", wall="S", along=1000),
                dict(part_id="home_toilet", wall="S", along=3000),
                dict(part_id="home_washbasin", wall="S", along=4800)]),
        dict(name="Physio room", x=0, y=y_r, w=6000, d=6000,
             flooring="Vinyl",
             openings=[dict(kind="door", side="N", offset=3000)],
             furniture=[dict(part_id="home_bed", x=2000, y=3000),
                        dict(part_id="home_bed", x=4200, y=3000),
                        dict(part_id="lab_first_aid", wall="E", along=3000),
                        dict(part_id="home_fridge", wall="S", along=5000)]),
        dict(name="Players lounge", x=-6000, y=y_s, w=12000, d=4000,
             flooring="Oak floorboards",
             openings=[dict(kind="door", side="N", offset=3000),
                       dict(kind="door", side="N", offset=9000)],
             furniture=[dict(part_id="home_sofa", wall="S", along=3000),
                        dict(part_id="home_sofa", wall="S", along=9000)]),
        dict(name="Away dressing room", x=6000, y=y_r, w=10000, d=6000,
             flooring="Grey porcelain",
             openings=[dict(kind="door", side="N", offset=1500, width=1200),
                       dict(kind="door", side="S", offset=2500, width=900),
                       dict(kind="door", side="S", offset=7500, width=900)],
             furniture=lockers("E", (1500, 3000, 4500))
             + lockers("N", (4000, 5500, 7000, 8500))
             + [dict(part_id="lab_whiteboard", wall="W", along=3000),
                dict(part_id="home_bench", x=5000, y=3000)]),
        dict(name="Away toilets", x=6000, y=y_s, w=4000, d=4000,
             furniture=[dict(part_id="home_toilet", wall="S", along=1500),
                        dict(part_id="home_toilet", wall="S", along=3000),
                        dict(part_id="home_washbasin", wall="W",
                             along=2500)]),
        dict(name="Away showers", x=10000, y=y_s, w=6000, d=4000,
             finish="White tiles", furniture=showers((700, 2000, 3500,
                                                      5000))),
    ]
    return dict(walls=dict(outside="Grey cladding", inside="Soft grey",
                           joinery="Anthracite grey"),
                floors=[dict(name="Changing rooms", wall_height=3200,
                             rooms=rooms)])


def changing_rooms(y_top):
    from . import house
    built = house.build_house_floors(
        house.house_from_spec(changing_rooms_spec(y_top)))
    return group("Changing rooms", built)


def tunnel(y_from, y_to):
    length = y_from - y_to
    return group("Players tunnel", [
        color(group("Walls", [
            box("Wall", -TUNNEL / 2 - 100, y_to, 0, 100, length, 2800),
            box("Wall", TUNNEL / 2, y_to, 0, 100, length, 2800)]),
            "#f2c200", "Plastic"),
        color(box("Tunnel roof", -TUNNEL / 2 - 100, y_to, 2800,
                  TUNNEL + 200, length, 200), "#2b2e33", "Metal")])


def build_stadium(shape, dims):
    sport_name = dims.get("sport") or dims.get("_size") or "Football"
    sport_name = sport_name.split(" ")[0]
    sp = SPORTS.get(sport_name, SPORTS["Football"])
    colour = sport._seat_colour(dims)
    changing = _f(dims.get("changing"), 1) >= 0.5
    parts = [move(sp["build"](dims), 0, 0, 0, "Field")]
    if shape == "rectangular":
        info, built = build_stands(sp, dims, colour)
        south_edge, seats = info["south_edge"], info["seats"]
    else:
        bowl, built = build_bowl(shape, sp, dims, colour)
        south_edge = -(bowl.b + bowl.lower_out)
        seats = bowl.seats
    parts += built
    field_edge = -(sp["hy"])
    if sp["dugouts"]:
        for x in (-12000, 12000):
            parts.append(move(turn(sport.dugout(8), z=180.0), x,
                              field_edge + 2400, 0, "Dugout"))
    if changing:
        y_top = south_edge - 300
        parts.append(tunnel(field_edge - sp["margin"] + 500, y_top))
        parts.append(changing_rooms(y_top))
    label = f"{sport_name} stadium, {shape} ({capacity_text(seats)} seats)"
    return group(label, parts)


def capacity_text(seats):
    return f"{int(round(seats, -2)):,}".replace(",", " ")


# ---------------------------------------------------------------- parts
def _sizes(sports, rows, upper, roof):
    return {f"{s}": dict(sport=s, rows=rows, upper_rows=upper, roof=roof,
                         changing=1) for s in sports}


_OUTDOOR = ("Football", "Rugby", "Athletics", "Tennis")
_INDOOR = ("Basketball", "Volleyball", "Handball", "Badminton", "Tennis")
_FIELDS = [("rows", "Lower tier rows"), ("upper_rows", "Upper tier rows"),
           ("roof", "Roof (0 open, 1 stands, 2 closed)"),
           ("changing", "Changing rooms & tunnel")]


def _part(label, shape, sports, rows, upper, roof):
    return dict(label=label, category=CATEGORY,
                sizes=_sizes(sports, rows, upper, roof),
                fields=_FIELDS, colors=list(sport.SEAT_COLORS),
                build=lambda dims, s=shape: build_stadium(s, dims))


PARTS = {
    "stadium_rounded": _part("Stadium — rounded bowl, two tiers",
                             "rounded", _OUTDOOR, 26, 30, 1),
    "stadium_rounded_single": _part("Stadium — rounded bowl, one tier",
                                    "rounded", _OUTDOOR, 30, 0, 1),
    "stadium_oval": _part("Stadium — oval bowl", "oval",
                          ("Athletics", "Football", "Rugby"), 28, 20, 1),
    "stadium_circular": _part("Stadium — circular bowl", "circular",
                              ("Football", "Athletics", "Tennis"), 26, 24,
                              1),
    "stadium_horseshoe": _part("Stadium — horseshoe (open end)",
                               "horseshoe", _OUTDOOR, 26, 20, 1),
    "stadium_rectangular": _part("Stadium — four straight stands",
                                 "rectangular", ("Football", "Rugby",
                                                 "Tennis"), 20, 0, 1),
    "stadium_arena": _part("Indoor arena", "arena", _INDOOR, 18, 12, 2),
    "sport_changing_rooms": dict(
        label="Changing rooms (two teams)", category=CATEGORY,
        sizes={"Standard (32 x 11.5 m)": {}}, fields=[],
        build=lambda dims: move(changing_rooms(0.0), 0, 5750, 0,
                                "Changing rooms")),
}

COUNT_FIELDS = {"rows", "upper_rows", "roof", "changing"}
