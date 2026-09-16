"""The **Park & sport** library: pitches, courts, water, play and park
furniture, and a complete park made of them.

- Football pitch (full size, 7-a-side, 5-a-side): mown stripes, every
  marking (touch and goal lines, halfway line, centre circle and spot,
  penalty and goal areas, penalty spots and arcs, corner arcs), goals
  with posts, crossbar, stanchions and a net of threads, corner flags.
- Tennis court (hard, clay or grass): the run-off surround, singles and
  doubles lines, service boxes and centre marks, a net with posts, tape
  and mesh, a chain-link fence of posts and wires round it.
- Basketball court: the painted keys, free-throw circles, three-point
  lines, centre circle; hoops on a padded pole with an overhang arm,
  backboard with its target square, orange rim and a net.
- Lake and pond: an irregular shore (seeded), a sandy margin, a dark bed
  under translucent water, reeds, lily pads, and a timber jetty on
  piles (lake).
- Playground (swings, slide on a tower with a ladder, roundabout,
  sandpit, safety surface), park bench, picnic table, litter bin,
  tiered fountain, gazebo.
- Park (complete): paths, a lake, a football pitch, tennis and basketball
  courts, a playground, benches, lamps and grown trees.

Markings are 2D polygons under ONE linear_extrude, and every repeated
thread, slat, picket and reed is a for-loop — a tennis court is a few
dozen nodes. Boxes, cylinders and hulls, no booleans. True sizes in mm,
standing on z = 0 and centred.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
import random

from .city_buildings import _f, _num, box, color, cyl, group, loop, move, turn
from .library_lighting import hull, sphere
from .model import CadNode

CATEGORY = "Park & sport"

LINE = "#f4f4f0"
LINE_W = 100.0
TIMBER = "#8a6240"
STEEL = "#9aa0a6"
GRASS_DARK, GRASS_LIGHT = "#4f8f3a", "#5f9f45"


# ------------------------------------------------------------ markings
def _poly(points, name="Line"):
    return CadNode("polygon", name, dict(x=0.0, y=0.0,
                                         points=[[round(x, 1), round(y, 1)]
                                                 for x, y in points]))


def seg(x0, y0, x1, y1, w=LINE_W):
    """A straight line of width *w* as a 2D quad."""
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length * w / 2, dx / length * w / 2
    return _poly([(x0 + nx, y0 + ny), (x0 - nx, y0 - ny),
                  (x1 - nx, y1 - ny), (x1 + nx, y1 + ny)])


def rect_lines(x0, y0, x1, y1, w=LINE_W):
    """The outline of a rectangle, the lines inside it."""
    return [seg(x0, y0 + w / 2, x1, y0 + w / 2, w),
            seg(x0, y1 - w / 2, x1, y1 - w / 2, w),
            seg(x0 + w / 2, y0, x0 + w / 2, y1, w),
            seg(x1 - w / 2, y0, x1 - w / 2, y1, w)]


def arc(cx, cy, r, a0=0.0, a1=360.0, w=LINE_W, steps=None):
    """A ring sector of width *w* centred on radius *r*, degrees."""
    steps = steps or max(8, int(abs(a1 - a0) / 6))
    outer, inner = [], []
    for i in range(steps + 1):
        a = math.radians(a0 + (a1 - a0) * i / steps)
        outer.append((cx + math.cos(a) * (r + w / 2),
                      cy + math.sin(a) * (r + w / 2)))
        inner.append((cx + math.cos(a) * (r - w / 2),
                      cy + math.sin(a) * (r - w / 2)))
    if abs(a1 - a0) >= 359.9:                  # a full ring: two halves
        half = steps // 2
        return [_poly(outer[:half + 1] + inner[:half + 1][::-1]),
                _poly(outer[half:] + inner[half:][::-1])]
    return [_poly(outer + inner[::-1])]


def spot(cx, cy, r=110.0):
    return _poly([(cx + math.cos(a) * r, cy + math.sin(a) * r)
                  for a in (i * math.pi / 8 for i in range(16))])


def extrude(shapes, h, name, colour, material="Matte", z=0.0):
    ex = CadNode("linear_extrude", name, dict(height=h, twist=0.0, scale=1.0,
                                              center=False, segments=0))
    for s in shapes:
        ex.add(s)
    return color(move(ex, 0, 0, z, name), colour, material)


def ring(name, r, width, height, z=0.0, seg=48):
    """A flat ring (a coping, a rail): a revolved rectangle — hollow
    without a boolean."""
    rx = CadNode("rotate_extrude", name, dict(angle=360.0, segments=seg))
    rx.add(_poly([(r - width / 2, 0.0), (r + width / 2, 0.0),
                  (r + width / 2, height), (r - width / 2, height)], name))
    return move(rx, 0, 0, z, name)


# -------------------------------------------------------------- football
def goal(width, height, depth, mirror=False):
    """A goal on the goal line at x = 0, opening towards +x (or -x):
    posts and crossbar, back stanchions, and a net of threads."""
    sgn = -1 if mirror else 1
    r = 60.0
    frame = [cyl("Post", 0, -width / 2, 0, height, r, seg=12),
             cyl("Post", 0, width / 2, 0, height, r, seg=12),
             move(turn(cyl("Crossbar", 0, 0, 0, width, r, seg=12), x=-90.0),
                  0, -width / 2, height, "Crossbar")]
    back = -sgn * depth
    stays = [hull("Stanchion", [sphere("Top", 0, s * width / 2, height, 25, 8),
                                sphere("Foot", back, s * width / 2, 0, 25,
                                       8)])
             for s in (-1, 1)]
    stays.append(hull("Ground bar", [sphere("A", back, -width / 2, 20, 20, 6),
                                     sphere("B", back, width / 2, 20, 20,
                                            6)]))
    step = 150.0
    nx = int(width // step)
    # the net: the back sheet's uprights and cross threads, the roof
    net = [
        loop("Net uprights", "i", nx + 1, [hull("Thread", [
            sphere("T", 0, f"{_num(-width / 2)} + i * {_num(width / nx)}",
                   height, 8, 4),
            sphere("B", back, f"{_num(-width / 2)} + i * {_num(width / nx)}",
                   0, 8, 4)])]),
        loop("Net rows", "j", int(height // step) + 1, [hull("Thread", [
            sphere("A", f"{_num(back)} * j * {_num(step / height)}",
                   -width / 2, f"{_num(height)} - j * {_num(step)}", 8, 4),
            sphere("B", f"{_num(back)} * j * {_num(step / height)}",
                   width / 2, f"{_num(height)} - j * {_num(step)}", 8,
                   4)])]),
    ]
    return group("Goal", [color(group("Frame", frame), "#f7f7f5", "Plastic"),
                          color(group("Back frame", stays), STEEL, "Metal"),
                          color(group("Net", net), "#e8e8e8", "Matte",
                                alpha=0.8)])


def build_football(dims):
    L = _f(dims.get("length"), 105000)
    W = _f(dims.get("width"), 68000)
    full = L >= 90000
    run = 4000.0 if full else 2000.0
    k = L / 105000.0
    stripes = int(max(6, round(L / (5500 * max(k, 0.4)))))
    sw = (L + 2 * run) / stripes
    parts = [
        color(box("Run-off", -L / 2 - run, -W / 2 - run, 0, L + 2 * run,
                  W + 2 * run, 20), GRASS_DARK, "Matte"),
        color(loop("Light stripes", "i", (stripes + 1) // 2, [
            box("Stripe", f"{_num(-L / 2 - run)} + i * {_num(2 * sw)}",
                -W / 2 - run, 20, sw, W + 2 * run, 5)]), GRASS_LIGHT,
            "Matte")]
    x0, x1, y0, y1 = -L / 2, L / 2, -W / 2, W / 2
    s = k if not full else 1.0
    pen_d, pen_w = 16500 * s, 40300 * min(1.0, W / 68000)
    ga_d, ga_w = 5500 * s, 18320 * min(1.0, W / 68000)
    circle_r = 9150 * s
    lines = rect_lines(x0, y0, x1, y1)
    lines += [seg(0, y0, 0, y1)] + arc(0, 0, circle_r) + [spot(0, 0)]
    for sgn in (-1, 1):
        gx = sgn * L / 2
        lines += [seg(gx, -pen_w / 2, gx - sgn * pen_d, -pen_w / 2),
                  seg(gx, pen_w / 2, gx - sgn * pen_d, pen_w / 2),
                  seg(gx - sgn * pen_d, -pen_w / 2, gx - sgn * pen_d,
                      pen_w / 2),
                  seg(gx, -ga_w / 2, gx - sgn * ga_d, -ga_w / 2),
                  seg(gx, ga_w / 2, gx - sgn * ga_d, ga_w / 2),
                  seg(gx - sgn * ga_d, -ga_w / 2, gx - sgn * ga_d, ga_w / 2),
                  spot(gx - sgn * 11000 * s, 0)]
        # the penalty arc: the part of the 9.15 m circle outside the box
        px = gx - sgn * 11000 * s
        half = math.degrees(math.acos(min(1.0, (pen_d - 11000 * s)
                                          / circle_r)))
        mid = 180.0 if sgn > 0 else 0.0
        lines += arc(px, 0, circle_r, mid - half, mid + half)
        for cy, a0 in ((y0, 0.0 if sgn < 0 else 90.0),
                       (y1, 270.0 if sgn < 0 else 180.0)):
            lines += arc(gx, cy, 1000.0, a0, a0 + 90.0, steps=8)
    parts.append(extrude(lines, 6, "Markings", LINE, z=25))
    gw, gh = (7320.0, 2440.0) if full else (5000.0, 2000.0)
    for sgn in (-1, 1):
        parts.append(move(goal(gw, gh, 2000.0, mirror=sgn > 0),
                          sgn * L / 2, 0, 25, "Goal"))
    flags = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            flags.append(group("Corner flag", [
                color(cyl("Pole", sx * L / 2, sy * W / 2, 25, 1500, 20,
                          seg=8), "#f2f2f2", "Plastic"),
                color(hull("Flag", [
                          box("Hoist", sx * L / 2, sy * W / 2 - 5, 1200, 10,
                              10, 300),
                          box("Fly", sx * L / 2 - sx * 400, sy * W / 2 - 5,
                              1300, 10, 10, 120)]), "#f2c200", "Matte")]))
    parts += flags
    return group("Football pitch", parts)


# ---------------------------------------------------------------- tennis
SURFACES = {"Hard (blue)": ("#2f5f9e", "#3f7a4a"),
            "Clay": ("#c2643a", "#b35a33"),
            "Grass": ("#5d9a45", "#4f8a3c"),
            "Hard (green)": ("#3f7a4a", "#6a4a3a")}


def net(width, height, posts=True):
    """A net across y at x = 0: posts, cable, top tape and a mesh of
    threads (two loops)."""
    step = 90.0
    n = int(width // step)
    parts = [color(loop("Mesh verticals", "i", n + 1, [
        box("Thread", -4, f"{_num(-width / 2)} + i * {_num(width / n)}", 150,
            8, 8, height - 200)]), "#202224", "Matte"),
        color(loop("Mesh rows", "j", int((height - 200) // step), [
            box("Thread", -4, -width / 2, f"150 + j * {_num(step)}", 8, width,
                8)]), "#202224", "Matte"),
        color(box("Tape", -25, -width / 2, height - 70, 50, width, 70),
              LINE, "Matte")]
    if posts:
        parts.append(color(group("Posts", [
            cyl("Post", 0, -width / 2 - 100, 0, height + 60, 50, seg=12),
            cyl("Post", 0, width / 2 + 100, 0, height + 60, 50, seg=12)]),
            "#2d4f3a", "Metal"))
    return group("Net", parts)


def fence(w, d, h, gate=True):
    """A chain-link fence round a w x d rectangle: posts, top rail and a
    diamond-like mesh of wires in both directions."""
    posts, rails, wires = [], [], []
    for sgn in (-1, 1):
        n = int(w // 3000)
        posts.append(loop("Posts", "i", n + 1, [cyl(
            "Post", f"{_num(-w / 2)} + i * {_num(w / n)}", sgn * d / 2, 0, h,
            40, seg=8)]))
        m = int(d // 3000)
        posts.append(loop("Posts", "i", m + 1, [cyl(
            "Post", sgn * w / 2, f"{_num(-d / 2)} + i * {_num(d / m)}", 0, h,
            40, seg=8)]))
        rails += [box("Rail", -w / 2, sgn * d / 2 - 20, h - 40, w, 40, 40),
                  box("Rail", sgn * w / 2 - 20, -d / 2, h - 40, 40, d, 40)]
        step = 250.0
        wires.append(loop("Mesh", "i", int(w // step), [box(
            "Wire", f"{_num(-w / 2)} + i * {_num(step)}", sgn * d / 2 - 3, 0,
            6, 6, h)]))
        wires.append(loop("Mesh", "i", int(d // step), [box(
            "Wire", sgn * w / 2 - 3, f"{_num(-d / 2)} + i * {_num(step)}", 0,
            6, 6, h)]))
        for zz in range(1, int(h // 500)):
            wires += [box("Strand", -w / 2, sgn * d / 2 - 3, zz * 500, w, 6,
                          6),
                      box("Strand", sgn * w / 2 - 3, -d / 2, zz * 500, 6, d,
                          6)]
    return group("Fence", [
        color(group("Posts and rails", posts + rails), "#2d4f3a", "Metal"),
        color(group("Chain link", wires), "#3d5f4a", "Metal", alpha=0.7)])


def build_tennis(dims):
    L, W = 23770.0, 10970.0
    surround_l = _f(dims.get("length"), 36000)
    surround_w = _f(dims.get("width"), 18000)
    court, outer = SURFACES.get(dims.get("_color") or "Hard (blue)",
                                SURFACES["Hard (blue)"])
    parts = [color(box("Surround", -surround_l / 2, -surround_w / 2, 0,
                       surround_l, surround_w, 30), outer, "Matte"),
             color(box("Court", -L / 2 - 50, -W / 2 - 50, 30, L + 100,
                       W + 100, 4), court, "Matte")]
    sw = 8230.0
    lines = rect_lines(-L / 2, -W / 2, L / 2, W / 2, 50)
    lines += [seg(-L / 2, -sw / 2, L / 2, -sw / 2, 50),
              seg(-L / 2, sw / 2, L / 2, sw / 2, 50),
              seg(-6400, -sw / 2, -6400, sw / 2, 50),
              seg(6400, -sw / 2, 6400, sw / 2, 50),
              seg(-6400, 0, 6400, 0, 50),
              seg(-L / 2, 0, -L / 2 + 150, 0, 50),
              seg(L / 2 - 150, 0, L / 2, 0, 50)]
    parts.append(extrude(lines, 4, "Lines", LINE, z=34))
    parts.append(move(net(W + 1830, 1070), 0, 0, 34, "Net"))
    parts.append(fence(surround_l, surround_w, 3000))
    parts.append(move(group("Umpire chair", [
        color(group("Frame", [
            cyl("Leg", 0, 0, 0, 1800, 30, seg=8),
            cyl("Leg", 600, 0, 0, 1800, 30, seg=8),
            cyl("Leg", 0, 600, 0, 1800, 30, seg=8),
            cyl("Leg", 600, 600, 0, 1800, 30, seg=8),
            box("Seat", -50, -50, 1800, 700, 700, 60),
            box("Back", -50, 580, 1860, 700, 60, 600)]), "#2d4f3a",
            "Metal")]), -300, W / 2 + 1400, 34, "Umpire chair"))
    return group("Tennis court", parts)


# ------------------------------------------------------------ basketball
def hoop(facing=1):
    """A hoop on a padded pole, the board facing +x (or -x)."""
    s = facing
    pole = color(group("Pole", [
        box("Base", -s * 1900 - 400, -400, 0, 800, 800, 400),
        box("Pole", -s * 1700 - 100, -100, 400, 200, 200, 2900),
        hull("Arm", [box("Root", -s * 1700 - 90, -60, 3200, 180, 120, 200),
                     box("Tip", -s * 150 - 60, -60, 3350, 120, 120, 150)])]),
        "#2b2e33", "Metal")
    pad = color(box("Pole pad", -s * 1700 - 140, -140, 400, 280, 280, 1800),
                "#1f4fa0", "Matte")
    board = color(box("Backboard", -s * 30 - 15, -900, 2900, 30, 1800, 1050),
                  "#f5f5f5", "Plastic")
    face = -s * 32                               # the court side
    target = color(group("Target square", [
        box("Top", face - 3, -295, 3445, 6, 590, 50),
        box("Bottom", face - 3, -295, 3000, 6, 590, 50),
        box("Left", face - 3, -295, 3000, 6, 50, 495),
        box("Right", face - 3, 245, 3000, 6, 50, 495)]), "#d8261b", "Matte")
    rim_ring = CadNode("rotate_extrude", "Rim", dict(angle=360.0, segments=32))
    rim_ring.add(CadNode("circle", "Rim tube", dict(x=230.0, y=0.0,
                                                    radius=12.0, angle=360.0,
                                                    start_angle=0.0,
                                                    segments=8)))
    rim = color(move(rim_ring, s * 270, 0, 3050, "Rim"), "#e2571f", "Metal")
    net_threads = loop("Net", "i", 12, [turn(hull("Thread", [
        sphere("Top", 225, 0, 3040, 6, 4), sphere("Bottom", 140, 0, 2600, 6,
                                                   4)]),
        z="i * 30", name="Thread")])
    net_node = color(move(net_threads, s * 270, 0, 0, "Net"), "#f4f4f4",
                     "Matte")
    return group("Hoop", [pole, pad, board, target, rim, net_node])


def build_basketball(dims):
    L = _f(dims.get("length"), 28000)
    W = _f(dims.get("width"), 15000)
    court = dims.get("_color") or "Orange"
    tones = {"Orange": ("#c8793a", "#1f4fa0"), "Blue": ("#2f5f9e", "#c8793a"),
             "Green": ("#3f7a4a", "#b35a33"), "Grey": ("#6e7479", "#c8413a")}
    floor, paint = tones.get(court, tones["Orange"])
    k = min(1.0, L / 28000.0, W / 15000.0)     # a smaller court's markings
    key_w, key_l, ft_r = 2450 * k, 5800 * k, 1800 * k
    three, to_basket = 6750 * k, 1575 * k
    run = 2000.0
    parts = [color(box("Surround", -L / 2 - run, -W / 2 - run, 0, L + 2 * run,
                       W + 2 * run, 30), "#5a5f63", "Concrete"),
             color(box("Court", -L / 2, -W / 2, 30, L, W, 4), floor,
                   "Matte")]
    keys = []
    for sgn in (-1, 1):
        gx = sgn * L / 2
        keys.append(_poly([(gx, -key_w), (gx - sgn * key_l, -key_w),
                           (gx - sgn * key_l, key_w), (gx, key_w)], "Key"))
    parts.append(extrude(keys, 3, "Keys", paint, z=34))
    lines = rect_lines(-L / 2, -W / 2, L / 2, W / 2, 50)
    lines += [seg(0, -W / 2, 0, W / 2, 50)] + arc(0, 0, ft_r, w=50)
    for sgn in (-1, 1):
        gx = sgn * L / 2
        basket = gx - sgn * to_basket
        lines += [seg(gx, -key_w, gx - sgn * key_l, -key_w, 50),
                  seg(gx, key_w, gx - sgn * key_l, key_w, 50),
                  seg(gx - sgn * key_l, -key_w, gx - sgn * key_l, key_w, 50)]
        lines += arc(gx - sgn * key_l, 0, ft_r, 90 if sgn > 0 else -90,
                     270 if sgn > 0 else 90, w=50)
        corner = W / 2 - 900 * k
        reach = math.degrees(math.asin(min(1.0, corner / three)))
        mid = 180.0 if sgn > 0 else 0.0
        lines += arc(basket, 0, three, mid - reach, mid + reach, w=50,
                     steps=36)
        cx = basket - sgn * three * math.cos(math.radians(reach))
        lines += [seg(gx, -corner, cx, -corner, 50),
                  seg(gx, corner, cx, corner, 50)]
    parts.append(extrude(lines, 4, "Lines", LINE, z=37))
    for sgn in (-1, 1):
        parts.append(move(hoop(-sgn), sgn * (L / 2 - 1200), 0, 34, "Hoop"))
    return group("Basketball court", parts)


# ----------------------------------------------------------------- water
def shore(radius_x, radius_y, seed, steps=48, wobble=0.18):
    """An irregular closed outline: an ellipse with seeded low-frequency
    bumps, counter-clockwise."""
    rng = random.Random(seed)
    waves = [(rng.randint(2, 5), rng.uniform(0, 2 * math.pi),
              rng.uniform(0.3, 1.0)) for _ in range(3)]
    total = sum(w[2] for w in waves)
    pts = []
    for i in range(steps):
        a = 2 * math.pi * i / steps
        bump = sum(amp * math.sin(k * a + ph) for k, ph, amp in waves) / total
        f = 1.0 + wobble * bump
        pts.append((math.cos(a) * radius_x * f, math.sin(a) * radius_y * f))
    return pts


def _scaled(points, k, dx=0.0, dy=0.0):
    return [(x * k + dx, y * k + dy) for x, y in points]


def build_water(dims, jetty=True):
    L = _f(dims.get("length"), 40000)
    W = _f(dims.get("width"), 25000)
    seed = int(_f(dims.get("seed"), 1))
    rng = random.Random(seed)
    edge = shore(L / 2, W / 2, seed)
    parts = [
        extrude([_poly(_scaled(edge, 1.0 + 3000.0 / max(L, W)))], 25,
                "Shore", "#c9b48a", "Stone"),
        extrude([_poly(edge)], 30, "Lakebed", "#3a4a3a", "Matte"),
        # opaque and glossy: translucent water showed the bed's long fan
        # triangles through it as streaks
        extrude([_poly(_scaled(edge, 0.985))], 30, "Water", "#35779a",
                "Plastic", z=180)]
    # reeds in clumps along the margin
    reeds, pads = [], []
    for _clump in range(max(3, int(L // 8000))):
        i = rng.randrange(len(edge))
        cx, cy = edge[i]
        for _k in range(9):
            reeds.append((cx * 0.95 + rng.uniform(-500, 500),
                          cy * 0.95 + rng.uniform(-500, 500),
                          rng.uniform(900, 1700), rng.uniform(-12, 12)))
    for _k in range(max(5, int(L * W / 60e6))):
        a = rng.uniform(0, 2 * math.pi)
        f = rng.uniform(0.3, 0.8)
        pads.append((math.cos(a) * L / 2 * f, math.sin(a) * W / 2 * f,
                     rng.uniform(250, 500)))

    def rows(values):
        return ", ".join("[" + ", ".join(_num(v) for v in row) + "]"
                         for row in values)
    reed = CadNode("for_loop", "Reeds", dict(variable="p", start=0.0, end=0.0,
                                             step=1.0, values=rows(reeds)))
    reed.add(move(turn(cyl("Reed", 0, 0, 0, "p[2]", 18, 4, seg=4), x="p[3]"),
                  "p[0]", "p[1]", 150, "Reed"))
    parts.append(color(reed, "#6f8d3a", "Leaves"))
    heads = CadNode("for_loop", "Bulrush heads", dict(
        variable="p", start=0.0, end=0.0, step=1.0,
        values=rows(reeds[::3])))
    heads.add(move(turn(cyl("Head", 0, 0, 0, 220, 30, 28, seg=6), x="p[3]"),
                   "p[0]", "p[1]", "p[2] - 150", "Head"))
    parts.append(color(heads, "#5a3a24", "Matte"))
    pad = CadNode("for_loop", "Lily pads", dict(variable="p", start=0.0,
                                                end=0.0, step=1.0,
                                                values=rows(pads)))
    pad.add(cyl("Pad", "p[0]", "p[1]", 212, 8, "p[2]", seg=10))
    parts.append(color(pad, "#4c8a3a", "Leaves"))
    if jetty:
        ex, ey = edge[len(edge) * 3 // 4]
        length = W * 0.25
        deck = []
        n = int(length // 150)
        deck.append(loop("Deck boards", "i", n, [box(
            "Board", -800, f"i * 150", 700, 1600, 130, 50)]))
        piles = [cyl("Pile", sx * 750, f"i * {_num(length / 4)}", -200, 1000,
                     90, seg=8) for sx in (-1, 1)]
        deck.append(loop("Piles", "i", 5, piles))
        deck += [box("Joist", -700, 0, 600, 100, length, 100),
                 box("Joist", 600, 0, 600, 100, length, 100)]
        rails = [box("Rail", sx * 780 - 30, 0, 1600, 60, length, 60)
                 for sx in (-1, 1)]
        rails.append(loop("Balusters", "i", int(length // 1200) + 1, [
            box("Baluster", -810, f"i * 1200", 750, 60, 60, 850),
            box("Baluster", 750, f"i * 1200", 750, 60, 60, 850)]))
        parts.append(color(move(group("Jetty", deck + rails), ex * 0.9,
                                ey * 0.9 - 400, 0, "Jetty"), TIMBER, "Matte"))
    return group("Lake" if jetty else "Pond", parts)


# -------------------------------------------------------------- play
def build_swings(dims):
    w = _f(dims.get("w"), 3600)
    h = _f(dims.get("h"), 2400)
    frame = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            frame.append(hull("Leg", [
                sphere("Top", sx * w / 2, 0, h, 45, 8),
                sphere("Foot", sx * w / 2, sy * 900, 0, 45, 8)]))
    frame.append(move(turn(cyl("Top bar", 0, 0, 0, w, 50, seg=12), y=90.0),
                      -w / 2, 0, h, "Top bar"))
    seats, chains = [], []
    for sx in (-0.25, 0.25):
        x = sx * w
        chains += [box("Chain", x - 200, -8, 450, 16, 16, h - 450),
                   box("Chain", x + 185, -8, 450, 16, 16, h - 450)]
        seats.append(box("Seat", x - 230, -110, 420, 460, 220, 40))
    return group("Swings", [color(group("Frame", frame), "#2f7a4a", "Metal"),
                            color(group("Chains", chains), STEEL, "Metal"),
                            color(group("Seats", seats), "#1c1c1c",
                                  "Rubber")])


def build_slide(dims):
    h = _f(dims.get("h"), 1800)
    tower = [cyl("Post", sx * 500, sy * 500, 0, h + 1000, 50, seg=8)
             for sx in (-1, 1) for sy in (-1, 1)]
    tower += [box("Deck", -550, -550, h, 1100, 1100, 60),
              box("Roof ridge", -600, -600, h + 1000, 1200, 1200, 40)]
    ladder = [hull("Rail", [sphere("Top", sx * 250, -550, h, 30, 6),
                            sphere("Foot", sx * 250, -1500, 0, 30, 6)])
              for sx in (-1, 1)]
    ladder.append(loop("Rungs", "i", int(h // 280), [box(
        "Rung", -250, f"-1500 + i * {_num(950 * 280 / h)}", f"i * 280 + 200",
        500, 40, 40)]))
    chute = hull("Chute", [box("Top", -300, 550, h - 20, 600, 60, 80),
                           box("Run-out", -300, 550 + h * 1.4, 250, 600, 400,
                               60)])
    sides = [hull("Side", [box("Top", sx * 320 - 25, 550, h + 40, 50, 60,
                               300),
                           box("Low", sx * 320 - 25, 550 + h * 1.4, 300, 50,
                               400, 250)]) for sx in (-1, 1)]
    roof = hull("Roof", [box("Eaves", -650, -650, h + 1000, 1300, 1300, 40),
                         box("Peak", -40, -40, h + 1500, 80, 80, 40)])
    return group("Slide", [
        color(group("Tower", tower + ladder), TIMBER, "Matte"),
        color(roof, "#c0392b", "Plastic"),
        color(group("Chute", [chute] + sides), "#f2b705", "Plastic")])


def build_roundabout(dims):
    d = _f(dims.get("d"), 2000)
    return group("Roundabout", [
        color(cyl("Hub", 0, 0, 0, 300, 150, seg=16), STEEL, "Metal"),
        color(cyl("Platform", 0, 0, 300, 60, d / 2, seg=32), "#d64541",
              "Plastic"),
        color(loop("Handles", "i", 4, [turn(hull("Handle", [
            sphere("Base", d * 0.2, 0, 360, 25, 6),
            sphere("Top", d * 0.35, 0, 1000, 25, 6)]), z="i * 90",
            name="Handle")]), "#f2b705", "Metal"),
        color(ring("Top ring", d * 0.36, 40, 40, 980, seg=24), "#f2b705",
              "Metal")])


def build_playground(dims):
    w = _f(dims.get("w"), 16000)
    d = _f(dims.get("d"), 12000)
    parts = [color(box("Safety surface", -w / 2, -d / 2, 0, w, d, 40),
                   "#b0503a", "Rubber"),
             color(group("Edging", rect_lines_box(w, d)), TIMBER, "Matte"),
             move(build_swings({}), -w / 4, d / 4, 40, "Swings"),
             move(build_slide({}), w / 4, -d / 4, 40, "Slide"),
             move(build_roundabout({}), -w / 4, -d / 4, 40, "Roundabout"),
             color(box("Sandpit", w / 8, d / 8, 0, 3000, 3000, 250),
                   "#d9c38f", "Stone"),
             color(group("Sandpit edge", [
                 box("Edge", w / 8 - 150, d / 8 - 150, 0, 3300, 150, 350),
                 box("Edge", w / 8 - 150, d / 8 + 3000, 0, 3300, 150, 350),
                 box("Edge", w / 8 - 150, d / 8, 0, 150, 3000, 350),
                 box("Edge", w / 8 + 3000, d / 8, 0, 150, 3000, 350)]),
                   TIMBER, "Matte")]
    return group("Playground", parts)


def rect_lines_box(w, d, t=150.0, h=150.0):
    return [box("Edge", -w / 2 - t, -d / 2 - t, 0, w + 2 * t, t, h),
            box("Edge", -w / 2 - t, d / 2, 0, w + 2 * t, t, h),
            box("Edge", -w / 2 - t, -d / 2, 0, t, d, h),
            box("Edge", w / 2, -d / 2, 0, t, d, h)]


# --------------------------------------------------------- furniture
def build_bench(dims):
    w = _f(dims.get("w"), 1800)
    wood = TIMBER
    ends = []
    for sx in (-1, 1):
        x = sx * (w / 2 - 150)
        ends.append(group("Cast end", [
            hull("Front leg", [box("Top", x - 30, -250, 420, 60, 60, 20),
                               box("Foot", x - 30, -300, 0, 60, 80, 20)]),
            hull("Back leg", [box("Seat", x - 30, 150, 420, 60, 60, 20),
                              box("Top", x - 30, 280, 850, 60, 60, 20),
                              box("Foot", x - 30, 200, 0, 60, 80, 20)]),
            box("Arm", x - 30, -300, 620, 60, 450, 50)]))
    slats = [loop("Seat slats", "i", 4, [box(
        "Slat", -w / 2, f"-280 + i * 110", 440, w, 90, 40)]),
        loop("Back slats", "i", 3, [box(
            "Slat", -w / 2, f"210 + i * 25", f"540 + i * 120", w, 40, 90)])]
    return group("Park bench", [color(group("Ends", ends), "#2b2e33",
                                         "Metal"),
                                color(group("Slats", slats), wood, "Matte")])


def build_picnic(dims):
    w = _f(dims.get("w"), 1800)
    parts = [loop("Top boards", "i", 5, [box(
        "Board", -w / 2, f"-375 + i * 150", 720, w, 140, 40)])]
    for sy in (-1, 1):
        parts.append(loop("Seat boards", "i", 2, [box(
            "Board", -w / 2, f"{_num(sy * 600 - 140)} + i * 140", 440, w,
            130, 40)]))
    for sx in (-1, 1):
        x = sx * (w / 2 - 250)
        parts += [hull("A-leg", [box("Top", x - 40, -300, 700, 80, 80, 20),
                                 box("Foot", x - 40, -850, 0, 80, 80, 20)]),
                  hull("A-leg", [box("Top", x - 40, 220, 700, 80, 80, 20),
                                 box("Foot", x - 40, 770, 0, 80, 80, 20)]),
                  box("Cross bar", x - 40, -760, 400, 80, 1520, 40)]
    return color(group("Picnic table", parts), TIMBER, "Matte")


def build_bin(dims):
    h = _f(dims.get("h"), 900)
    return group("Litter bin", [
        color(cyl("Body", 0, 0, 0, h, 260, 280, seg=24), "#1e3d2f", "Metal"),
        color(cyl("Lid", 0, 0, h, 80, 300, 240, seg=24), "#1e3d2f", "Metal"),
        color(cyl("Band", 0, 0, h * 0.6, 60, 285, seg=24), "#c9a54a", "Gold"),
        color(box("Opening", -150, -300, h - 50, 300, 30, 100), "#111",
              "Matte")])


def build_fountain(dims):
    d = _f(dims.get("d"), 6000)
    r = d / 2
    parts = [
        color(ring("Basin wall", r - 150, 300, 600), "#cfc8b8", "Stone"),
        color(cyl("Basin floor", 0, 0, 0, 480, r - 150, seg=48), "#9fb8c0",
              "Concrete"),
        color(cyl("Basin water", 0, 0, 480, 20, r - 250, seg=48), "#4f9fc4",
              "Plastic"),
        color(ring("Coping", r - 40, 320, 80, 580), "#e0dacb", "Stone"),
        color(cyl("Column", 0, 0, 0, 1600, 250, 180, seg=24), "#cfc8b8",
              "Stone"),
        color(cyl("Middle bowl", 0, 0, 1500, 250, r * 0.2, r * 0.42, seg=32),
              "#d8d2c4", "Stone"),
        color(cyl("Middle water", 0, 0, 1700, 20, r * 0.38, seg=32),
              "#4f9fc4", "Plastic"),
        color(cyl("Upper column", 0, 0, 1750, 900, 140, 100, seg=16),
              "#cfc8b8", "Stone"),
        color(cyl("Top bowl", 0, 0, 2600, 180, r * 0.1, r * 0.2, seg=24),
              "#d8d2c4", "Stone"),
        color(group("Jets", [
            cyl("Jet", 0, 0, 2780, 900, 60, 10, seg=8),
            loop("Spill", "i", 12, [turn(hull("Spill", [
                sphere("Rim", r * 0.4, 0, 1700, 20, 4),
                sphere("Fall", r * 0.62, 0, 650, 30, 4)]), z="i * 30",
                name="Spill")])]), "#bfe4f2", "Glass", alpha=0.6)]
    return group("Fountain", parts)


def build_gazebo(dims):
    d = _f(dims.get("d"), 4000)
    r = d / 2
    posts = [cyl("Post", math.cos(a) * r * 0.9, math.sin(a) * r * 0.9, 300,
                 2400, 70, seg=8)
             for a in (i * math.pi / 3 for i in range(6))]
    rails = [ring("Rail", r * 0.9, 80, 60, 1100, seg=6),
             ring("Bottom rail", r * 0.9, 80, 60, 400, seg=6)]
    return group("Gazebo", [
        color(cyl("Base", 0, 0, 0, 300, r * 1.05, seg=6), "#cfc8b8", "Stone"),
        color(group("Frame", posts + rails), "#f1efe9", "Plastic"),
        color(cyl("Roof", 0, 0, 2700, 1400, r * 1.2, 80, seg=6), "#4e5156",
              "Slate"),
        color(sphere("Finial", 0, 0, 4150, 90, 12), "#c9a54a", "Gold")])


# ------------------------------------------------------------- the park
def build_park(dims):
    """A park laid out round a lake: a path loop round the water and a
    promenade with a fountain, and clear of both a football pitch,
    tennis and basketball courts and a playground; benches and lamps
    along the loop and grown trees on the open lawn."""
    from . import treegen
    from .library_lighting import build_park_lamp
    w = _f(dims.get("w"), 220000)
    d = _f(dims.get("d"), 150000)
    seed = int(_f(dims.get("seed"), 1))
    rng = random.Random(seed)
    kx, ky = w / 220000.0, d / 150000.0
    parts = [color(box("Lawn", -w / 2, -d / 2, -60, w, d, 60), "#5e9b46",
                   "Matte")]
    lake_c = (-30000 * kx, 12000 * ky)
    lake_w, lake_d = 52000 * kx, 32000 * ky
    loop_rx, loop_ry = lake_w / 2 + 12000 * kx, lake_d / 2 + 11000 * ky
    prom_y = -d / 2 + 18000 * ky
    # (x, y, half width, half depth) of everything trees keep off
    keep = []

    def place(node, x, y, hw, hd, name):
        keep.append((x, y, hw + 8000, hd + 8000))
        parts.append(move(node, x, y, 0, name))

    path = shore(loop_rx, loop_ry, seed + 7, steps=40, wobble=0.06)
    path = [(x + lake_c[0], y + lake_c[1]) for x, y in path]
    ways = [seg(x0, y0, x1, y1, 3000) for (x0, y0), (x1, y1) in
            zip(path, path[1:] + path[:1])]
    ways.append(seg(-w / 2, prom_y, w / 2, prom_y, 4000))
    low = min(y for _x, y in path)
    ways.append(seg(lake_c[0], prom_y, lake_c[0], low + 1000, 3000))
    parts.append(extrude(ways, 25, "Paths", "#c9b89a", "Stone"))
    parts.append(move(build_water(dict(length=lake_w, width=lake_d,
                                       seed=seed)), lake_c[0], lake_c[1], 0,
                      "Lake"))
    place(build_football(dict(length=60000 * min(kx, 1.0),
                              width=40000 * min(ky, 1.0))),
          62000 * kx, -8000 * ky, 32000 * kx, 22000 * ky, "Football pitch")
    place(build_tennis(dict(length=36000, width=18000)), 62000 * kx,
          50000 * ky, 18000, 9000, "Tennis court")
    place(turn(build_basketball(dict(length=28000, width=15000)), z=90.0),
          -88000 * kx, 38000 * ky, 9500, 16000, "Basketball court")
    place(build_playground({}), -80000 * kx, -30000 * ky, 8000, 6000,
          "Playground")
    place(build_fountain({}), lake_c[0], prom_y, 3200, 3200, "Fountain")
    benches, lamps = [], []
    for i in range(0, len(path), 4):
        x, y = path[i]
        ang = math.degrees(math.atan2(y - lake_c[1], x - lake_c[0]))
        out = (math.cos(math.radians(ang)), math.sin(math.radians(ang)))
        benches.append(move(turn(build_bench({}), z=ang - 90),
                            x + out[0] * 2600, y + out[1] * 2600, 0,
                            "Bench"))
        lamps.append(move(build_park_lamp({}), x - out[0] * 2200,
                          y - out[1] * 2200, 0, "Park lamp"))
    for i in range(7):
        x = -w / 2 + (i + 0.5) * w / 7
        lamps.append(move(build_park_lamp({}), x, prom_y + 3000, 0,
                          "Park lamp"))
    parts.append(group("Benches", benches))
    parts.append(group("Park lamps", lamps))

    def clear(x, y):
        for cx, cy, hw, hd in keep:
            if abs(x - cx) < hw and abs(y - cy) < hd:
                return False
        rx, ry = x - lake_c[0], y - lake_c[1]
        if (rx / (loop_rx + 4000)) ** 2 + (ry / (loop_ry + 4000)) ** 2 < 1.0:
            return abs((rx / loop_rx) ** 2 + (ry / loop_ry) ** 2 - 1.0) > 9e9
        if abs(y - prom_y) < 5000 or abs(x) > w / 2 - 2000 or \
                abs(y) > d / 2 - 2000:
            return False
        return True
    kinds = ["oak", "maple", "lime", "birch", "cherry", "willow", "spruce",
             "pine"]
    grown = {k: treegen.build(k, detail="city", seed=1) for k in kinds}
    by_kind = {}
    wanted = int(w * d / 1.0e9)
    tries = 0
    while sum(len(v) for v in by_kind.values()) < wanted and tries < 20000:
        tries += 1
        x, y = rng.uniform(-w / 2, w / 2), rng.uniform(-d / 2, d / 2)
        if clear(x, y):
            k = rng.choice(kinds)
            by_kind.setdefault(k, []).append(
                (x, y, rng.uniform(0.7, 1.2), rng.uniform(0, 360)))
    trees = group("Trees")
    for k, rows in by_kind.items():
        values = ", ".join(f"[{_num(x)}, {_num(y)}, {s:.2f}, {_num(rz)}]"
                           for x, y, s, rz in rows)
        if len(rows) == 1:
            values = f"[{values}]"
        lp = CadNode("for_loop", treegen.SPECIES[k]["label"],
                     dict(variable="p", start=0.0, end=0.0, step=1.0,
                          values=values))
        sc = CadNode("scale", "Size", dict(x="p[2]", y="p[2]", z="p[2]"))
        sc.add(turn(grown[k], z="p[3]"))
        lp.add(move(sc, "p[0]", "p[1]", 0, "At"))
        trees.add(lp)
    parts.append(trees)
    return group("Park", parts)


# ------------------------------------------------------------- parts
def _entry(label, build, sizes, fields, colors=None):
    entry = dict(label=label, category=CATEGORY, sizes=sizes, build=build,
                 fields=fields)
    if colors:
        entry["colors"] = list(colors)
    return entry


_LW = [("length", "Length"), ("width", "Width")]
PARTS = {
    "park_complete": _entry("Park (complete)", build_park,
                            {"Small": dict(w=160000, d=120000, seed=1),
                             "Large": dict(w=220000, d=150000, seed=1)},
                            [("w", "Width"), ("d", "Depth"),
                             ("seed", "Variation")]),
    "park_football": _entry("Football pitch", build_football,
                            {"5-a-side (40 x 20 m)": dict(length=40000,
                                                          width=20000),
                             "7-a-side (60 x 40 m)": dict(length=60000,
                                                          width=40000),
                             "Full size (105 x 68 m)": dict(length=105000,
                                                            width=68000)},
                            _LW),
    "park_tennis": _entry("Tennis court", build_tennis,
                          {"Club (36 x 18 m)": dict(length=36000,
                                                    width=18000)},
                          [("length", "Fenced length"),
                           ("width", "Fenced width")], SURFACES),
    "park_basketball": _entry("Basketball court", build_basketball,
                              {"Junior (22 x 12 m)": dict(length=22000,
                                                          width=12000),
                               "Full size (28 x 15 m)": dict(length=28000,
                                                             width=15000)},
                              _LW, ("Orange", "Blue", "Green", "Grey")),
    "park_lake": _entry("Lake with jetty", build_water,
                        {"Pond-sized lake (25 x 15 m)": dict(length=25000,
                                                            width=15000,
                                                            seed=1),
                         "Lake (40 x 25 m)": dict(length=40000, width=25000,
                                                  seed=1),
                         "Large lake (80 x 50 m)": dict(length=80000,
                                                        width=50000, seed=1)},
                        _LW + [("seed", "Shape")]),
    "park_pond": _entry("Pond", lambda d: build_water(d, jetty=False),
                        {"Small (6 x 4 m)": dict(length=6000, width=4000,
                                                 seed=2),
                         "Medium (12 x 8 m)": dict(length=12000, width=8000,
                                                   seed=2)},
                        _LW + [("seed", "Shape")]),
    "park_playground": _entry("Playground", build_playground,
                              {"Standard (16 x 12 m)": dict(w=16000,
                                                            d=12000)},
                              [("w", "Width"), ("d", "Depth")]),
    "park_swings": _entry("Swings", build_swings,
                          {"Double": dict(w=3600, h=2400)},
                          [("w", "Width"), ("h", "Height")]),
    "park_slide": _entry("Slide with tower", build_slide,
                         {"Standard": dict(h=1800)}, [("h", "Deck height")]),
    "park_roundabout": _entry("Roundabout", build_roundabout,
                              {"Standard": dict(d=2000)}, [("d", "Diameter")]),
    "park_bench": _entry("Park bench", build_bench,
                         {"1.5 m": dict(w=1500), "1.8 m": dict(w=1800)},
                         [("w", "Width")]),
    "park_picnic": _entry("Picnic table", build_picnic,
                          {"1.8 m": dict(w=1800)}, [("w", "Length")]),
    "park_bin": _entry("Litter bin", build_bin, {"Standard": dict(h=900)},
                       [("h", "Height")]),
    "park_fountain": _entry("Fountain", build_fountain,
                            {"4 m": dict(d=4000), "6 m": dict(d=6000),
                             "10 m": dict(d=10000)}, [("d", "Basin diameter")]),
    "park_gazebo": _entry("Gazebo / bandstand", build_gazebo,
                          {"4 m": dict(d=4000), "7 m": dict(d=7000)},
                          [("d", "Diameter")]),
}

COUNT_FIELDS = {"seed"}
