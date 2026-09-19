"""The **Sport** library: fields, equipment and seating (Library ▸
Buildings & places ▸ Sport; the stadiums themselves are `stadium.py`).

- Pitches & courts not already in Park & sport, at their governing
  bodies' sizes: rugby union (100 x 70 m + in-goals, H posts), badminton
  (13.40 x 6.10 m), volleyball (18 x 9 m, free zone, net 2.43 m),
  handball / futsal (40 x 20 m, 6 m and dashed 9 m arcs, 3 x 2 m goals),
  a 400 m athletics track (8 lanes of 1.22 m, 84.39 m straights, 36.5 m
  bends) with a football pitch inside, and a tennis show court (the Park
  court without its chain-link fence).
- Equipment: rugby posts, handball goal, volleyball and badminton nets,
  tennis umpire chair, floodlight mast, video scoreboard, awards podium.
- Seating: tip-up stadium seats, padded VIP seats, and the **players'
  bucket seat** — the sculpted, high-backed, leather racing-style seat a
  top club puts in its dugout, on a swivel plinth — plus a glazed
  dugout holding a row of them.

Same rules as library_park: true size in mm, on z = 0, centred, boxes /
cylinders / hulls and 2D markings under one extrude — no booleans, so
the preview is exact. Repeated pieces are for-loops.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from .city_buildings import _f, _num, box, color, cyl, group, loop, move, turn
from .library_lighting import hull, sphere
from .library_park import (GRASS_DARK, GRASS_LIGHT, LINE, _poly, arc,
                           build_football, build_tennis, extrude, goal, net,
                           rect_lines, seg, spot)

FIELDS = "Sport: pitches & courts"
EQUIPMENT = "Sport: equipment"
SEATING = "Sport: seating"

#: seat colours shared with the stadiums (colour combo name -> hex)
SEAT_COLORS = {"Red": "#c8102e", "Blue": "#1d3f8f", "Sky blue": "#6cabdd",
               "Claret": "#7a263a", "Yellow": "#f2c200", "Green": "#1f7a3a",
               "White": "#eeeeee", "Black": "#1b1b1d", "Orange": "#e8601c",
               "Grey": "#8a8f94"}
#: bucket-seat looks: (shell, cushion, stitching)
BUCKET_LOOKS = {"Black & red": ("#1a1a1c", "#c8102e", "#f2f2f2"),
                "Black & white": ("#1a1a1c", "#f2f2f2", "#c8102e"),
                "Red & white": ("#c8102e", "#f2f2f2", "#1a1a1c"),
                "Blue & white": ("#1d3f8f", "#f2f2f2", "#6cabdd"),
                "Claret & blue": ("#7a263a", "#6cabdd", "#f2f2f2"),
                "All black": ("#1a1a1c", "#2a2a2e", "#8a8f94")}
STEEL = "#9aa0a6"
DARK = "#2b2e33"


def _seat_colour(dims, default="Red"):
    return SEAT_COLORS.get(dims.get("_color") or default,
                           SEAT_COLORS[default])


def _floor(name, w, d, colour, h=30, z=0.0, material="Matte"):
    return color(box(name, -w / 2, -d / 2, z, w, d, h), colour, material)


def _dashes(x0, y0, x1, y1, dash=1000.0, gap=1000.0, w=100.0):
    """A dashed straight line as separate 2D quads."""
    length = math.hypot(x1 - x0, y1 - y0) or 1.0
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    out, s = [], 0.0
    while s < length:
        e = min(s + dash, length)
        out.append(seg(x0 + ux * s, y0 + uy * s, x0 + ux * e, y0 + uy * e, w))
        s = e + gap
    return out


def _dashed_arc(cx, cy, r, a0, a1, dash_deg=8.0, w=50.0):
    out, a = [], a0
    while a < a1:
        out += arc(cx, cy, r, a, min(a + dash_deg, a1), w=w, steps=3)
        a += 2 * dash_deg
    return out


# ------------------------------------------------------------- rugby
def rugby_posts(height=16000.0, width=5600.0, bar=3000.0):
    """H posts on the try line at x = 0, uprights along y, padded feet."""
    parts = [color(group("Frame", [
        cyl("Upright", 0, -width / 2, 0, height, 90, 70, seg=12),
        cyl("Upright", 0, width / 2, 0, height, 90, 70, seg=12),
        move(turn(cyl("Crossbar", 0, 0, 0, width, 80, seg=12), x=-90.0),
             0, -width / 2, bar, "Crossbar")]), "#f7f7f5", "Plastic"),
        color(group("Pads", [
            box("Pad", -350, -width / 2 - 350, 0, 700, 700, 2000),
            box("Pad", -350, width / 2 - 350, 0, 700, 700, 2000)]),
            "#1d3f8f", "Matte")]
    return group("Rugby posts", parts)


def build_rugby(dims):
    L = _f(dims.get("length"), 100000)        # try line to try line
    W = _f(dims.get("width"), 70000)
    ig = _f(dims.get("in_goal"), 10000)
    run = 5000.0
    total = L + 2 * ig + 2 * run
    stripes = 12
    sw = total / stripes
    parts = [
        _floor("Run-off", total, W + 2 * run, GRASS_DARK, h=20),
        color(loop("Light stripes", "i", stripes // 2, [
            box("Stripe", f"{_num(-total / 2)} + i * {_num(2 * sw)}",
                -W / 2 - run, 20, sw, W + 2 * run, 5)]), GRASS_LIGHT,
            "Matte")]
    x_try, x_dead = L / 2, L / 2 + ig
    lines = rect_lines(-x_dead, -W / 2, x_dead, W / 2)
    lines += [seg(0, -W / 2, 0, W / 2)]
    for s in (-1, 1):
        lines += [seg(s * x_try, -W / 2, s * x_try, W / 2),
                  seg(s * (x_try - 22000), -W / 2, s * (x_try - 22000),
                      W / 2)]
        lines += _dashes(s * 10000, -W / 2, s * 10000, W / 2)
        for yy in (-W / 2 + 5000, W / 2 - 5000, -W / 2 + 15000,
                   W / 2 - 15000):      # the 5 m and 15 m dashes
            lines += _dashes(-x_try, yy, x_try, yy, 500, 4500)
    lines += _dashes(-500, 0, 500, 0, 1000, 1000)
    parts.append(extrude(lines, 6, "Markings", LINE, z=25))
    for s in (-1, 1):
        parts.append(move(rugby_posts(), s * x_try, 0, 25, "Rugby posts"))
    flags = [color(cyl("Flag post", sx * x, sy * W / 2, 25, 1200, 40, seg=8),
                   "#f2c200", "Matte")
             for sx in (-1, 1) for sy in (-1, 1)
             for x in (x_try, x_dead, x_try - 22000)]
    parts.append(group("Flag posts", flags))
    return group("Rugby pitch", parts)


# ---------------------------------------------------------- badminton
def badminton_net(width=6100.0):
    posts = color(group("Posts", [
        box("Foot", -300, -width / 2 - 300, 0, 600, 600, 60),
        box("Foot", -300, width / 2 - 300, 0, 600, 600, 60),
        cyl("Post", 0, -width / 2, 0, 1550, 25, seg=10),
        cyl("Post", 0, width / 2, 0, 1550, 25, seg=10)]), DARK, "Metal")
    mesh = color(loop("Mesh", "i", int(width // 60), [
        box("Thread", -3, f"{_num(-width / 2)} + i * 60", 764, 6, 6, 760)]),
        "#202224", "Matte", alpha=0.8)
    tape = color(box("Tape", -20, -width / 2, 1490, 40, width, 34), LINE,
                 "Matte")
    return group("Badminton net", [posts, mesh, tape])


def build_badminton(dims):
    L, W = 13400.0, 6100.0
    fw, fd = _f(dims.get("length"), 17400), _f(dims.get("width"), 10100)
    parts = [_floor("Sports floor", fw, fd, "#2f6a4a"),
             _floor("Court", L + 80, W + 80, "#2f7a55", h=3, z=30)]
    sw = 5180.0
    lines = rect_lines(-L / 2, -W / 2, L / 2, W / 2, 40)
    lines += [seg(-L / 2, -sw / 2, L / 2, -sw / 2, 40),
              seg(-L / 2, sw / 2, L / 2, sw / 2, 40)]
    for s in (-1, 1):
        lines += [seg(s * 1980, -W / 2, s * 1980, W / 2, 40),
                  seg(s * (L / 2 - 760), -W / 2, s * (L / 2 - 760), W / 2,
                      40),
                  seg(s * 1980, 0, s * L / 2, 0, 40)]
    parts.append(extrude(lines, 3, "Lines", LINE, z=33))
    parts.append(move(badminton_net(W), 0, 0, 33, "Net"))
    return group("Badminton court", parts)


# --------------------------------------------------------- volleyball
def volleyball_net(width=10000.0, top=2430.0):
    posts = color(group("Posts", [
        cyl("Post", 0, -width / 2 - 500, 0, 2550, 50, seg=12),
        cyl("Post", 0, width / 2 + 500, 0, 2550, 50, seg=12)]), DARK,
        "Metal")
    pads = color(group("Post pads", [
        cyl("Pad", 0, -width / 2 - 500, 0, 1900, 120, seg=12),
        cyl("Pad", 0, width / 2 + 500, 0, 1900, 120, seg=12)]),
        "#1d3f8f", "Matte")
    mesh = color(loop("Mesh", "i", int(width // 100), [
        box("Thread", -3, f"{_num(-width / 2)} + i * 100", top - 1000, 6, 6,
            1000)]), "#202224", "Matte", alpha=0.8)
    bands = color(group("Bands", [
        box("Top band", -25, -width / 2, top - 70, 50, width, 70),
        box("Bottom band", -25, -width / 2, top - 1000, 50, width, 50)]),
        LINE, "Matte")
    antennae = color(group("Antennae", [
        cyl("Antenna", 0, -4500, top - 1000, 1800, 5, seg=6),
        cyl("Antenna", 0, 4500, top - 1000, 1800, 5, seg=6)]), "#c8102e",
        "Plastic")
    return group("Volleyball net", [posts, pads, mesh, bands, antennae])


def referee_stand(h=1800.0):
    return color(group("Referee stand", [
        box("Platform", -400, -400, h - 60, 800, 800, 60),
        cyl("Leg", -350, -350, 0, h, 30, seg=8),
        cyl("Leg", 350, -350, 0, h, 30, seg=8),
        cyl("Leg", -350, 350, 0, h, 30, seg=8),
        cyl("Leg", 350, 350, 0, h, 30, seg=8),
        box("Step", -300, 400, 600, 600, 250, 40),
        box("Step", -300, 400, 1200, 600, 250, 40),
        box("Rail", -400, -400, h, 60, 800, 900)]), DARK, "Metal")


def build_volleyball(dims):
    L, W = 18000.0, 9000.0
    fw, fd = _f(dims.get("length"), 24000), _f(dims.get("width"), 15000)
    parts = [_floor("Free zone", fw, fd, "#c8793a"),
             _floor("Court", L, W, "#2f5f9e", h=3, z=30)]
    lines = rect_lines(-L / 2, -W / 2, L / 2, W / 2, 50)
    lines += [seg(0, -W / 2, 0, W / 2, 50),
              seg(-3000, -W / 2, -3000, W / 2, 50),
              seg(3000, -W / 2, 3000, W / 2, 50)]
    parts.append(extrude(lines, 3, "Lines", LINE, z=33))
    parts.append(move(volleyball_net(), 0, 0, 33, "Net"))
    parts.append(move(referee_stand(), 0, -W / 2 - 1500, 33,
                      "Referee stand"))
    return group("Volleyball court", parts)


# ------------------------------------------------ handball / futsal
def build_handball(dims):
    L, W = _f(dims.get("length"), 40000), _f(dims.get("width"), 20000)
    run = 2000.0
    parts = [_floor("Surround", L + 2 * run, W + 2 * run, "#2f5f9e"),
             _floor("Court", L, W, "#c8793a", h=3, z=30)]
    lines = rect_lines(-L / 2, -W / 2, L / 2, W / 2, 50)
    lines += [seg(0, -W / 2, 0, W / 2, 50)] + arc(0, 0, 3000, w=50)
    areas = []
    for s in (-1, 1):
        gx = s * L / 2
        mid = 180.0 if s > 0 else 0.0
        # the 6 m goal area: quarter circles on each post and a 3 m line
        pts = [(gx, -1500 - 6000)]
        for a in range(0, 91, 10):
            pts.append((gx - s * 6000 * math.sin(math.radians(a)),
                        -1500 - 6000 * math.cos(math.radians(a))))
        for a in range(90, -1, -10):
            pts.append((gx - s * 6000 * math.sin(math.radians(a)),
                        1500 + 6000 * math.cos(math.radians(a))))
        pts.append((gx, 1500 + 6000))
        areas.append(_poly(pts, "Goal area"))
        lines += _dashed_arc(gx, -1500, 9000, mid - 90 if s > 0 else -90,
                             mid if s > 0 else 0)
        lines += _dashed_arc(gx, 1500, 9000, mid if s > 0 else 0,
                             mid + 90 if s > 0 else 90)
        lines += _dashes(gx - s * 9000, -1500, gx - s * 9000, 1500, 1000,
                         1000, 50)
        lines += [seg(gx - s * 7000, -500, gx - s * 7000, 500, 50)]
    parts.append(extrude(areas, 2, "Goal areas", "#2f5f9e", z=33))
    parts.append(extrude(lines, 3, "Lines", LINE, z=35))
    for s in (-1, 1):
        parts.append(move(goal(3000.0, 2000.0, 1000.0, mirror=s > 0),
                          s * L / 2, 0, 33, "Goal"))
    return group("Handball court", parts)


# ------------------------------------------------------- athletics
TRACK_STRAIGHT, TRACK_R, LANE = 84390.0, 36500.0, 1220.0


def track_outline(r, straight=TRACK_STRAIGHT, steps=24):
    """A 400 m track's shape offset to radius *r*: two straights and
    two semicircles, counter-clockwise from the home straight."""
    h = straight / 2
    pts = []
    for i in range(steps + 1):          # east bend
        a = -90 + 180 * i / steps
        pts.append((h + r * math.cos(math.radians(a)),
                    r * math.sin(math.radians(a))))
    for i in range(steps + 1):          # west bend
        a = 90 + 180 * i / steps
        pts.append((-h + r * math.cos(math.radians(a)),
                    r * math.sin(math.radians(a))))
    return pts


def _band(r0, r1, name):
    outer, inner = track_outline(r1), track_outline(r0)
    n = len(outer)
    poly = _poly(outer + inner, name)
    poly.params["paths"] = [list(range(n)), list(range(n, 2 * n))]
    return poly


def build_track(dims):
    lanes = int(_f(dims.get("lanes"), 8))
    with_pitch = _f(dims.get("with_pitch"), 1) >= 0.5
    r_out = TRACK_R + lanes * LANE
    parts = [color(move(_ext([_band(TRACK_R - 300, r_out + 1500,
                                    "Track")], 30), 0, 0, 0, "Track"),
                   "#b5452f", "Matte"),
             color(move(_ext([_poly(track_outline(TRACK_R - 300),
                                    "Infield")], 20), 0, 0, 0, "Infield"),
                   GRASS_DARK, "Matte")]
    lane_lines = [_band(TRACK_R + i * LANE - 25, TRACK_R + i * LANE + 25,
                        "Lane line") for i in range(lanes + 1)]
    lane_lines.append(seg(0, -r_out, 0, -TRACK_R, 100))          # finish
    parts.append(extrude(lane_lines, 3, "Lane lines", LINE, z=30))
    kerb = _band(TRACK_R - 80, TRACK_R, "Kerb")
    parts.append(color(move(_ext([kerb], 50), 0, 0, 30, "Kerb"), "#f2f2f2",
                       "Plastic"))
    if with_pitch:
        pitch = build_football(dict(length=105000, width=68000))
        for child in list(pitch.children):     # the infield is its grass
            if child.name in ("Run-off", "Light stripes"):
                pitch.remove(child)
        parts.append(move(pitch, 0, 0, 20, "Football pitch"))
    return group("Athletics track", parts)


def _ext(shapes, h):
    """*shapes* under one linear_extrude, uncoloured."""
    from .model import CadNode
    ex = CadNode("linear_extrude", "Extrude", dict(
        height=h, twist=0.0, scale=1.0, center=False, segments=0))
    for shape in shapes:
        ex.add(shape)
    return ex


def build_show_court(dims):
    """The Park tennis court without its chain-link fence: a show court
    for a stadium."""
    court = build_tennis(dims)
    for child in list(court.children):
        if child.name == "Fence":
            court.remove(child)
    court.name = "Tennis show court"
    return court


# ---------------------------------------------------------- equipment
def build_rugby_posts(dims):
    return rugby_posts(_f(dims.get("h"), 16000), _f(dims.get("w"), 5600))


def build_handball_goal(dims):
    # the goal's ground bar dips 25 mm under its line, as on a pitch
    return move(goal(_f(dims.get("w"), 3000), _f(dims.get("h"), 2000),
                     _f(dims.get("d"), 1000)), 0, 0, 25, "Handball goal")


def build_volleyball_net(dims):
    return group("Volleyball net", [volleyball_net(_f(dims.get("w"), 10000),
                                                   _f(dims.get("h"), 2430)),
                                    move(referee_stand(), 0, -7000, 0,
                                         "Referee stand")])


def build_badminton_net(dims):
    return badminton_net(_f(dims.get("w"), 6100))


def build_umpire_chair(dims):
    h = _f(dims.get("h"), 1800)
    return group("Umpire chair", [color(group("Frame", [
        cyl("Leg", 0, 0, 0, h, 30, seg=8), cyl("Leg", 600, 0, 0, h, 30,
                                               seg=8),
        cyl("Leg", 0, 600, 0, h, 30, seg=8), cyl("Leg", 600, 600, 0, h, 30,
                                                 seg=8),
        box("Seat", -50, -50, h, 700, 700, 60),
        box("Back", -50, 580, h + 60, 700, 60, 600),
        box("Rung", 0, -20, h * 0.35, 600, 40, 40),
        box("Rung", 0, -20, h * 0.7, 600, 40, 40)]), "#2d4f3a", "Metal"),
        color(box("Sun shade", -150, -150, h + 1000, 1000, 1000, 40),
              "#f2f2f2", "Plastic")])


def floodlight_mast(h=40000.0, lamps=(6, 4)):
    """A tapered mast with a tilted head of lamps facing +x."""
    cols, rows = lamps
    w, d = cols * 700.0, rows * 700.0
    head = [color(box("Head frame", -200, -w / 2, 0, 400, w, d), DARK,
                  "Metal"),
            color(loop("Lamp rows", "j", rows, [loop("Lamps", "i", cols, [
                box("Lamp", 200, f"{_num(-w / 2 + 50)} + i * 700",
                    "50 + j * 700", 80, 600, 600)])]), "#fffbe8",
                "Emissive")]
    return group("Floodlight mast", [
        color(cyl("Mast", 0, 0, 0, h, 900, 450, seg=16), STEEL, "Metal"),
        color(cyl("Base", 0, 0, 0, 1200, 1500, seg=16), "#8a8f94",
              "Concrete"),
        move(turn(group("Head", head), y=-20.0), 300, 0, h - d, "Head")])


def build_floodlight(dims):
    return floodlight_mast(_f(dims.get("h"), 40000))


def video_screen(w=12000.0, h=6000.0, legs=True):
    """A video scoreboard facing -y: frame, lit screen, score strip."""
    parts = [color(box("Frame", -w / 2 - 300, 0, 0, w + 600, 800, h + 600),
                   "#1b1b1d", "Metal"),
             color(box("Screen", -w / 2, -20, 300, w, 30, h), "#1f4fa0",
                   "Emissive"),
             color(box("Score strip", -w / 2, -40, 300, w, 30, h * 0.18),
                   "#f2c200", "Emissive")]
    if legs:
        return group("Video scoreboard", [move(group("Screen", parts), 0, 0,
                                               4000, "Screen"),
                                          color(group("Legs", [
                                              box("Leg", -w / 3, 200, 0, 500,
                                                  400, 4000),
                                              box("Leg", w / 3 - 500, 200, 0,
                                                  500, 400, 4000)]), STEEL,
                                              "Metal")])
    return group("Video scoreboard", parts)


def build_scoreboard(dims):
    return video_screen(_f(dims.get("w"), 12000), _f(dims.get("h"), 6000),
                        legs=_f(dims.get("legs"), 1) >= 0.5)


def build_podium(dims):
    """The 1-2-3 awards podium: gold in the middle, numbers on the
    front (-y)."""
    w = _f(dims.get("w"), 1200)
    steps = [(0, 900, "#d4af37", "1"), (-w, 600, "#c0c0c0", "2"),
             (w, 400, "#cd7f32", "3")]
    parts = []
    for x, h, tone, label in steps:
        parts.append(color(box(f"Step {label}", x - w / 2, -500, 0, w, 1000,
                               h), "#f2f2f2", "Plastic"))
        parts.append(color(box(f"Band {label}", x - w / 2, -505, h - 120, w,
                               10, 80), tone, "Metal"))
        txt = move(turn(CadNode_text(label, w * 0.35), x=90.0),
                   x - w * 0.1, -506, h * 0.3, f"Number {label}")
        parts.append(color(txt, tone, "Metal"))
    return group("Awards podium", parts)


def CadNode_text(text, size):
    from .model import CadNode
    ex = CadNode("linear_extrude", "Number", dict(height=4.0, twist=0.0,
                                                  scale=1.0, center=False,
                                                  segments=0))
    ex.add(CadNode("text", "Number", dict(x=0.0, y=0.0, text=text,
                                          size=size)))
    return ex


# ------------------------------------------------------------ seating
def stadium_seat(colour, name="Stadium seat"):
    """One tip-up plastic seat on its bracket, facing -y, 500 mm wide."""
    return group(name, [
        color(group("Shell", [
            hull("Seat pan", [box("Front", -220, -380, 400, 440, 60, 40),
                              box("Back", -220, -60, 420, 440, 60, 40)]),
            hull("Back", [box("Low", -210, -40, 470, 420, 40, 60),
                          box("High", -200, 0, 800, 400, 40, 40)])]),
            colour, "Plastic"),
        color(group("Bracket", [box("Riser", -20, -60, 0, 40, 80, 470),
                                box("Foot", -80, -120, 0, 160, 200, 10)]),
              STEEL, "Metal")])


def build_seat_row(dims):
    n = int(_f(dims.get("seats"), 10))
    pitch = _f(dims.get("pitch"), 500)
    colour = _seat_colour(dims)
    return group("Row of stadium seats", [loop("Seats", "i", n, [move(
        stadium_seat(colour), f"{_num(-(n - 1) * pitch / 2)} + i * "
                              f"{_num(pitch)}", 0, 0, "Seat")])])


def vip_seat(colour, name="VIP seat"):
    """A padded hospitality seat with armrests, 600 mm wide."""
    return group(name, [
        color(group("Cushions", [
            hull("Seat cushion", [box("F", -240, -430, 420, 480, 60, 90),
                                  sphere("C", 0, -250, 470, 200, 12),
                                  box("B", -240, -80, 430, 480, 60, 90)]),
            hull("Back cushion", [box("L", -240, -40, 520, 480, 90, 60),
                                  box("H", -230, 0, 1000, 460, 80, 60)])]),
            colour, "Clay"),
        color(group("Frame", [
            box("Arm", -300, -420, 400, 60, 440, 250),
            box("Arm", 240, -420, 400, 60, 440, 250),
            box("Base", -300, -300, 0, 600, 300, 400)]), "#2a2a2e",
            "Metal")])


def build_vip_row(dims):
    n = int(_f(dims.get("seats"), 8))
    colour = _seat_colour(dims)
    return group("Row of VIP seats", [loop("Seats", "i", n, [move(
        vip_seat(colour), f"{_num(-(n - 1) * 300)} + i * 600", 0, 0,
        "Seat")])])


def bucket_seat(look="Black & red", name="Players' bucket seat"):
    """The star player's dugout seat: a sculpted racing shell (tall back,
    side bolsters, headrest opening), a leather cushion with a centre
    panel and contrast stitching, on a swivel column and plinth. Faces
    -y, 620 mm wide, 1.3 m tall."""
    shell, cushion, stitch = BUCKET_LOOKS.get(look,
                                              BUCKET_LOOKS["Black & red"])
    back = hull("Back shell", [
        sphere("Hip L", -250, 150, 560, 70, 12),
        sphere("Hip R", 250, 150, 560, 70, 12),
        sphere("Shoulder L", -265, 170, 1050, 70, 12),
        sphere("Shoulder R", 265, 170, 1050, 70, 12),
        sphere("Head", 0, 170, 1320, 110, 12)])
    wings = [hull("Bolster", [
        sphere("Low", s * 300, -380, 520, 55, 10),
        sphere("Mid", s * 305, -40, 620, 60, 10),
        sphere("High", s * 300, 130, 1000, 55, 10)]) for s in (-1, 1)]
    pan = hull("Seat shell", [
        sphere("FL", -260, -420, 470, 60, 10),
        sphere("FR", 260, -420, 470, 60, 10),
        sphere("BL", -260, 0, 440, 60, 10),
        sphere("BR", 260, 0, 440, 60, 10)])
    cushions = [
        hull("Seat cushion", [sphere("FL", -190, -400, 520, 45, 10),
                              sphere("FR", 190, -400, 520, 45, 10),
                              sphere("BL", -190, -40, 500, 45, 10),
                              sphere("BR", 190, -40, 500, 45, 10)]),
        hull("Back cushion", [sphere("LL", -180, 40, 600, 45, 10),
                              sphere("LR", 180, 40, 600, 45, 10),
                              sphere("HL", -170, 100, 1000, 45, 10),
                              sphere("HR", 170, 100, 1000, 45, 10)]),
        hull("Headrest", [sphere("TL", -120, 90, 1330, 45, 10),
                          sphere("TR", 120, 90, 1330, 45, 10),
                          sphere("BL", -120, 90, 1150, 45, 10),
                          sphere("BR", 120, 90, 1150, 45, 10)])]
    cushions += [hull("Side bolster", [
        sphere("Front", s * 230, -380, 575, 42, 10),
        sphere("Rear", s * 235, 0, 640, 42, 10),
        sphere("Top", s * 235, 110, 960, 42, 10)]) for s in (-1, 1)]
    stitching = [
        box("Stitch", -110, -440, 560, 8, 400, 12),
        box("Stitch", 102, -440, 560, 8, 400, 12),
        hull("Stitch", [box("L", -110, -10, 640, 8, 12, 12),
                        box("H", -105, 50, 1000, 8, 12, 12)]),
        hull("Stitch", [box("L", 102, -10, 640, 8, 12, 12),
                        box("H", 97, 50, 1000, 8, 12, 12)]),
        move(turn(cyl("Crest", 0, 0, 0, 12, 60, seg=24), x=-90.0), 0, 44,
             1240, "Crest")]
    base = [cyl("Swivel", 0, -150, 150, 280, 60, seg=16),
            cyl("Plinth", 0, -150, 0, 150, 280, 240, seg=24)]
    return group(name, [
        color(group("Shell", [back, pan] + wings), shell, "Plastic"),
        color(group("Leather", cushions), cushion, "Matte"),
        color(group("Stitching", stitching), stitch, "Matte"),
        color(group("Base", base), "#3a3d42", "Metal")])


def build_bucket_seat(dims):
    return bucket_seat(dims.get("_color") or "Black & red")


def dugout(seats=8, look="Black & red", pitch=750.0):
    """A glazed dugout facing -y (the pitch): a curved canopy of glass
    panels on a steel frame, a back wall, a raised floor and a row of
    players' bucket seats."""
    w = seats * pitch + 1000
    depth, h = 2200.0, 2500.0
    arcs = []
    for i in range(10):            # the canopy: a quarter curve of panes
        a0, a1 = math.radians(i * 9), math.radians((i + 1) * 9)
        y0, z0 = depth - depth * math.sin(a0), h * math.cos(a0) + 400
        y1, z1 = depth - depth * math.sin(a1), h * math.cos(a1) + 400
        arcs.append(hull("Pane", [box("A", -w / 2, y0 - 10, z0, w, 20, 20),
                                  box("B", -w / 2, y1 - 10, z1, w, 20, 20)]))
    frame = [box("Rib", -w / 2 - 60, 0, 0, 60, depth, 150),
             box("Rib", w / 2, 0, 0, 60, depth, 150),
             box("Post", -w / 2 - 60, depth - 60, 0, 60, 60, h + 400),
             box("Post", w / 2, depth - 60, 0, 60, 60, h + 400)]
    return group("Dugout", [
        color(box("Floor", -w / 2, 0, 0, w, depth, 150), "#6e7479",
              "Concrete"),
        color(box("Back wall", -w / 2, depth, 0, w, 150, h + 400), "#1b1b1d",
              "Matte"),
        color(group("Canopy", arcs), "#bcd4e6", "Glass", alpha=0.35),
        color(group("Frame", frame), STEEL, "Metal"),
        loop("Seats", "i", seats, [move(
            bucket_seat(look), f"{_num(-(seats - 1) * pitch / 2)} + i * "
                               f"{_num(pitch)}", depth - 250, 150, "Seat")])])


def build_dugout(dims):
    return dugout(int(_f(dims.get("seats"), 8)),
                  dims.get("_color") or "Black & red")


def build_grandstand(dims):
    """A straight block of stepped terraces with tip-up seats, facing -y,
    optionally under a cantilever roof — the piece to line a pitch with."""
    rows = int(_f(dims.get("rows"), 12))
    length = _f(dims.get("length"), 30000)
    tread, riser = 800.0, 400.0
    colour = _seat_colour(dims)
    n = int(length // 500)
    parts = [color(loop("Terraces", "r", rows, [box(
        "Terrace", -length / 2, "r * 800", 0, length, tread,
        "(r + 1) * 400")]), "#8a8f94", "Concrete"),
        loop("Seat rows", "r", rows, [move(loop("Seats", "i", n, [move(
            stadium_seat(colour), f"{_num(-length / 2 + 250)} + i * 500", 0,
            0, "Seat")]), 0, "r * 800 + 450", "(r + 1) * 400", "Row")]),
        color(box("Back wall", -length / 2, rows * tread, 0, length, 200,
                  rows * riser + 1200), "#8a8f94", "Concrete")]
    if _f(dims.get("roof"), 1) >= 0.5:
        top = rows * riser + 4000
        parts += [
            color(hull("Roof", [box("Back", -length / 2, rows * tread - 200,
                                    top + 1200, length, 400, 300),
                                box("Front", -length / 2, -1500, top, length,
                                    400, 150)]), "#e8eaec", "Metal"),
            color(loop("Columns", "i", int(length // 10000) + 1, [box(
                "Column", f"{_num(-length / 2)} + i * "
                          f"{_num(length / max(1, int(length // 10000)))}"
                          " - 200", rows * tread, 0, 400, 400, top + 1200)]),
                  STEEL, "Metal")]
    return group("Grandstand", parts)


# ------------------------------------------------------------- parts
def _entry(label, category, build, sizes, fields, colors=None):
    e = dict(label=label, category=category, sizes=sizes, build=build,
             fields=fields)
    if colors:
        e["colors"] = list(colors)
    return e


_SEATS = list(SEAT_COLORS)
_LOOKS = list(BUCKET_LOOKS)
PARTS = {
    "sport_rugby": _entry("Rugby pitch", FIELDS, build_rugby,
                          {"Union (100 x 70 m)": dict(length=100000,
                                                      width=70000,
                                                      in_goal=10000)},
                          [("length", "Length"), ("width", "Width"),
                           ("in_goal", "In-goal depth")]),
    "sport_badminton": _entry("Badminton court", FIELDS, build_badminton,
                              {"Competition": dict(length=17400,
                                                   width=10100)},
                              [("length", "Floor length"),
                               ("width", "Floor width")]),
    "sport_volleyball": _entry("Volleyball court", FIELDS, build_volleyball,
                               {"Indoor (18 x 9 m)": dict(length=24000,
                                                          width=15000)},
                               [("length", "Floor length"),
                                ("width", "Floor width")]),
    "sport_handball": _entry("Handball / futsal court", FIELDS,
                             build_handball,
                             {"Standard (40 x 20 m)": dict(length=40000,
                                                           width=20000)},
                             [("length", "Length"), ("width", "Width")]),
    "sport_track": _entry("Athletics track (400 m)", FIELDS, build_track,
                          {"8 lanes with pitch": dict(lanes=8, with_pitch=1),
                           "8 lanes, grass infield": dict(lanes=8,
                                                          with_pitch=0),
                           "6 lanes with pitch": dict(lanes=6,
                                                      with_pitch=1)},
                          [("lanes", "Lanes"),
                           ("with_pitch", "Football pitch")]),
    "sport_tennis_show": _entry("Tennis show court", FIELDS,
                                build_show_court,
                                {"Show court (40 x 20 m)": dict(
                                    length=40000, width=20000)},
                                [("length", "Surround length"),
                                 ("width", "Surround width")],
                                ("Hard (blue)", "Clay", "Grass",
                                 "Hard (green)")),
    "sport_rugby_posts": _entry("Rugby posts", EQUIPMENT, build_rugby_posts,
                                {"Standard": dict(h=16000, w=5600)},
                                [("h", "Height"), ("w", "Width")]),
    "sport_handball_goal": _entry("Handball / futsal goal", EQUIPMENT,
                                  build_handball_goal,
                                  {"3 x 2 m": dict(w=3000, h=2000, d=1000)},
                                  [("w", "Width"), ("h", "Height"),
                                   ("d", "Depth")]),
    "sport_volleyball_net": _entry("Volleyball net & referee stand",
                                   EQUIPMENT, build_volleyball_net,
                                   {"Men (2.43 m)": dict(w=10000, h=2430),
                                    "Women (2.24 m)": dict(w=10000,
                                                           h=2240)},
                                   [("w", "Net width"), ("h", "Net top")]),
    "sport_badminton_net": _entry("Badminton net", EQUIPMENT,
                                  build_badminton_net,
                                  {"Standard": dict(w=6100)},
                                  [("w", "Width")]),
    "sport_umpire_chair": _entry("Tennis umpire chair", EQUIPMENT,
                                 build_umpire_chair,
                                 {"Standard": dict(h=1800)},
                                 [("h", "Seat height")]),
    "sport_floodlight": _entry("Floodlight mast", EQUIPMENT,
                               build_floodlight,
                               {"Stadium (40 m)": dict(h=40000),
                                "Club (18 m)": dict(h=18000)},
                               [("h", "Height")]),
    "sport_scoreboard": _entry("Video scoreboard", EQUIPMENT,
                               build_scoreboard,
                               {"Stadium (12 x 6 m)": dict(w=12000, h=6000,
                                                           legs=1),
                                "Arena (6 x 3.5 m)": dict(w=6000, h=3500,
                                                          legs=0)},
                               [("w", "Width"), ("h", "Height"),
                                ("legs", "On legs")]),
    "sport_podium": _entry("Awards podium (1-2-3)", EQUIPMENT, build_podium,
                           {"Standard": dict(w=1200)}, [("w", "Step width")]),
    "sport_seat": _entry("Stadium seats (row)", SEATING, build_seat_row,
                         {"10 seats": dict(seats=10, pitch=500),
                          "1 seat": dict(seats=1, pitch=500),
                          "20 seats": dict(seats=20, pitch=500)},
                         [("seats", "Seats"), ("pitch", "Seat width")],
                         _SEATS),
    "sport_vip_seat": _entry("VIP padded seats (row)", SEATING,
                             build_vip_row,
                             {"8 seats": dict(seats=8), "1 seat":
                              dict(seats=1)}, [("seats", "Seats")], _SEATS),
    "sport_bucket_seat": _entry("Players' bucket seat", SEATING,
                                build_bucket_seat, {"Standard": {}}, [],
                                _LOOKS),
    "sport_dugout": _entry("Dugout with players' seats", SEATING,
                           build_dugout,
                           {"8 seats": dict(seats=8),
                            "12 seats": dict(seats=12),
                            "16 seats": dict(seats=16)},
                           [("seats", "Seats")], _LOOKS),
    "sport_grandstand": _entry("Grandstand (seat block)", SEATING,
                               build_grandstand,
                               {"Small (30 m, 12 rows)": dict(length=30000,
                                                              rows=12,
                                                              roof=1),
                                "Large (60 m, 20 rows)": dict(length=60000,
                                                              rows=20,
                                                              roof=1)},
                               [("length", "Length"), ("rows", "Rows"),
                                ("roof", "Roof")], _SEATS),
}

COUNT_FIELDS = {"lanes", "with_pitch", "seats", "rows", "roof", "legs"}
