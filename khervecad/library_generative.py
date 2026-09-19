"""Lego Technic pieces and generative panels (Technic.scad; dotSCAD's
voronoi, maze and space-filling curves).

Technic, at the real dimensions (8 mm pitch, 7.2 mm beam, Ø4.8 pin
holes with Ø6.2 × 0.8 counterbores, the + axle of 4.8 mm with 1.8 mm
arms): a studless beam of n holes, a cross axle of n units, a friction
pin, and a gear (module 1 — 8, 16, 24 or 40 teeth, which is exactly
Technic's spacing) with an axle hole.

Generative panels, seeded so they are the same every time (the maze's
default seed 0 draws a NEW maze at every insert instead): a Voronoi
panel (cells from seeded points by Bowyer–Watson Delaunay, walls by
insetting each cell), a maze (recursive backtracker on a grid, walls as
blocks — optionally rounded, and optionally CHANGING: several seeded
mazes on one slider, walls rising and falling between them) and a Hilbert-curve plate (a single raised path). Their cells,
walls and paths are written out as ordinary polygons, lines and cubes,
so the result is editable.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
import random

from .library_print import (_cube, _cyl, _extrude, _group, _move, _polygon,
                            _vbox)
from .model import CadNode

TECHNIC = "Lego Technic"
GENERATIVE = "Generative"

PITCH = 8.0
HOLE = 4.8
BORE = 6.2
COLORS = {"Light grey": "#a0a5a9", "Black": "#1b2a34", "Red": "#c91a09",
          "Yellow": "#f2cd37", "Blue": "#0055bf", "Tan": "#e4cd9e"}


def _paint(node, dims, default):
    col = CadNode("color", node.name, dict(
        color=COLORS.get(dims.get("_color") or default,
                         COLORS[default]), alpha=1.0, material="Plastic"))
    col.add(node)
    return col


def _d(dims, sizes):
    entry = dict(sizes.get(dims.get("_size", ""), next(iter(sizes.values()))))
    entry.update({k: v for k, v in dims.items()
                  if not k.startswith("_") and v is not None})
    return entry


def _axle_cross(name, length, z=0.0, clearance=0.0):
    arm = 1.8 + clearance
    size = HOLE + clearance
    return _group(name,
                  _cube("Arm X", -size / 2, -arm / 2, z, size, arm, length),
                  _cube("Arm Y", -arm / 2, -size / 2, z, arm, size, length))


# ---------------------------------------------------------------- Technic

BEAM_SIZES = {f"{n} holes": dict(holes=n) for n in (3, 5, 7, 9, 11, 15)}


def build_technic_beam(dims):
    """A studless Technic beam: rounded ends, a pin hole every 8 mm
    through its 7.2 mm width, counterbored both faces."""
    p = _d(dims, BEAM_SIZES)
    n = max(int(p["holes"]), 1)
    w = 7.2
    length = (n - 1) * PITCH
    body = _group("Beam", _vbox("Body", -w / 2, -w / 2, 0,
                                length + w, w, w, w / 2),
                  kind="difference")
    for i in range(n):
        x = i * PITCH
        body.add(_cyl(f"Hole {i + 1}", x, 0, -1, w + 2, HOLE / 2, seg=32))
        body.add(_cyl("Counterbore", x, 0, -1, 1.8, BORE / 2, seg=32))
        body.add(_cyl("Counterbore", x, 0, w - 0.8, 1.8, BORE / 2, seg=32))
    return _paint(_move(body, x=w / 2 - w / 2), dims, "Light grey")


AXLE_SIZES = {f"{n} units": dict(units=n) for n in (2, 3, 4, 6, 8, 10)}


def build_technic_axle(dims):
    """A cross axle n × 8 mm long."""
    p = _d(dims, AXLE_SIZES)
    return _paint(_axle_cross("Axle", max(int(p["units"]), 1) * PITCH),
                  dims, "Black")


PIN_SIZES = {"Friction pin": dict(length=15.8)}


def build_technic_pin(dims):
    """A Technic pin: two split shafts that fit Ø4.8 holes, a collar in
    the middle."""
    p = _d(dims, PIN_SIZES)
    half = p["length"] / 2
    pin = _group("Pin",
                 _group("Shaft", _cyl("Shaft", 0, 0, 0, p["length"], 2.4,
                                      seg=32),
                        _cyl("Bore", 0, 0, -1, p["length"] + 2, 1.5, seg=24),
                        _cube("Slot", -3, -0.4, -1, 6, 0.8, 4),
                        _cube("Slot", -3, -0.4, p["length"] - 3, 6, 0.8, 4),
                        kind="difference"),
                 _group("Collar", _cyl("Collar", 0, 0, half - 0.5, 1.0, 3.1,
                                       seg=32),
                        _cyl("Bore", 0, 0, half - 1, 2.0, 1.5, seg=24),
                        kind="difference"))
    return _paint(pin, dims, "Black")


TGEAR_SIZES = {f"{t} teeth": dict(teeth=t) for t in (8, 16, 24, 40)}


def build_technic_gear(dims):
    """A Technic spur gear: module 1 (a 24-tooth gear is 24 mm across its
    pitch circle, meshing with another on holes 3 apart), 4 mm thick,
    with a cross axle hole."""
    p = _d(dims, TGEAR_SIZES)
    gear = CadNode("gear", "Gear", dict(
        kind="spur", m=1.0, teeth=max(int(p["teeth"]), 8),
        pressure_angle=20.0, thickness=4.0, helix=0.0, bore=0.0,
        backlash=0.1, clearance=0.25, rim=2.0, mate_teeth=24, length=10.0,
        worm_diameter=10.0, detail=5))
    cut = _group("Technic gear", gear,
                 _axle_cross("Axle hole", 6.0, z=-1, clearance=0.15),
                 kind="difference")
    return _paint(cut, dims, "Light grey")


# ------------------------------------------------------------- generative

def _circumcircle(a, b, c):
    ax, ay = a
    bx, by = b
    cx, cy = c
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return None
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay)
          + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx)
          + (cx * cx + cy * cy) * (bx - ax)) / d
    return ux, uy, (ax - ux) ** 2 + (ay - uy) ** 2


def delaunay(points):
    """Bowyer–Watson triangulation: triangles as index triples."""
    big = 1e6
    pts = list(points) + [(-big, -big), (big, -big), (0.0, big)]
    n = len(points)
    tris = [(n, n + 1, n + 2)]
    for i, p in enumerate(points):
        bad = []
        for t in tris:
            cc = _circumcircle(pts[t[0]], pts[t[1]], pts[t[2]])
            if cc and (p[0] - cc[0]) ** 2 + (p[1] - cc[1]) ** 2 < cc[2]:
                bad.append(t)
        edges = {}
        for t in bad:
            for e in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
                key = tuple(sorted(e))
                edges[key] = edges.get(key, 0) + 1
        tris = [t for t in tris if t not in bad]
        for (a, b), count in edges.items():
            if count == 1:
                tris.append((a, b, i))
    return [t for t in tris if max(t) < n]


def _clip(poly, a, b, c):
    """Keep the part of *poly* where a x + b y <= c."""
    out = []
    for i, p in enumerate(poly):
        q = poly[(i + 1) % len(poly)]
        fp, fq = a * p[0] + b * p[1] - c, a * q[0] + b * q[1] - c
        if fp <= 0:
            out.append(p)
        if (fp < 0 < fq) or (fq < 0 < fp):
            t = fp / (fp - fq)
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return out


def voronoi_cells(width, height, count, seed, wall):
    """Each seeded point's Voronoi cell inside the panel, inset by half the
    wall (half-plane clipping against every Delaunay neighbour)."""
    rng = random.Random(seed)
    pts = [(rng.uniform(0, width), rng.uniform(0, height))
           for _ in range(max(int(count), 2))]
    neighbours = {i: set() for i in range(len(pts))}
    for a, b, c in delaunay(pts):
        neighbours[a] |= {b, c}
        neighbours[b] |= {a, c}
        neighbours[c] |= {a, b}
    cells = []
    for i, (px, py) in enumerate(pts):
        poly = [(wall, wall), (width - wall, wall),
                (width - wall, height - wall), (wall, height - wall)]
        for j in neighbours[i]:
            qx, qy = pts[j]
            nx, ny = qx - px, qy - py
            length = math.hypot(nx, ny)
            if length < 1e-9:
                continue
            nx, ny = nx / length, ny / length
            mid = ((px + qx) / 2 - nx * wall / 2, (py + qy) / 2 - ny * wall / 2)
            poly = _clip(poly, nx, ny, nx * mid[0] + ny * mid[1])
            if len(poly) < 3:
                break
        if len(poly) >= 3:
            cells.append(poly)
    return cells


VORONOI_SIZES = {"100 × 70 mm": dict(width=100.0, depth=70.0, thickness=2.0,
                                     cells=24, wall=1.6, seed=7)}


def build_voronoi(dims):
    """A panel pierced by Voronoi cells — a frame and organic walls."""
    p = _d(dims, VORONOI_SIZES)
    w, d, t = p["width"], p["depth"], p["thickness"]
    panel = _group("Voronoi panel", _cube("Plate", 0, 0, 0, w, d, t),
                   kind="difference")
    for k, cell in enumerate(voronoi_cells(w, d, p["cells"], p["seed"],
                                           p["wall"])):
        panel.add(_move(_extrude(f"Cell {k + 1}", _polygon("Cell", cell),
                                 t + 2), z=-1))
    return _paint(panel, dims, "Tan")


def maze_walls(cols, rows, seed):
    """A perfect maze by recursive backtracking: the set of open passages
    between neighbouring cells."""
    rng = random.Random(seed)
    opened, seen = set(), {(0, 0)}
    stack = [(0, 0)]
    while stack:
        x, y = stack[-1]
        options = [(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1),
                                                   (0, -1))
                   if 0 <= x + dx < cols and 0 <= y + dy < rows
                   and (x + dx, y + dy) not in seen]
        if not options:
            stack.pop()
            continue
        nxt = rng.choice(options)
        opened.add(frozenset(((x, y), nxt)))
        seen.add(nxt)
        stack.append(nxt)
    return opened


MAZE_SIZES = {"10 × 10 cells": dict(cols=10, rows=10, cell=8.0, wall=1.6,
                                    height=6.0, base=2.0, seed=0,
                                    rounding=0.0, mazes=1)}
MAX_MAZES = 12


def new_seed():
    """A fresh maze: seed 0 asks for one never seen before."""
    return random.SystemRandom().randrange(1, 1_000_000)


def _maze_segments(cols, rows, opened):
    """The closed walls of one maze as {(axis, line, index)}: axis "x" is
    a wall between (x, y) and (x + 1, y) — on line x + 1 at row y — and
    "y" one between (x, y) and (x, y + 1)."""
    closed = set()
    for x in range(cols):
        for y in range(rows):
            if x + 1 < cols and frozenset(((x, y), (x + 1, y))) not in opened:
                closed.add(("x", x + 1, y))
            if y + 1 < rows and frozenset(((x, y), (x, y + 1))) not in opened:
                closed.add(("y", y + 1, x))
    return closed


def maze_runs(cols, rows, seeds):
    """The walls of a maze that changes through one maze per seed:
    [(axis, line, first, last, on)] where *on* says, per maze, whether
    the wall stands. Neighbouring segments on one line that stand in
    the same mazes join into ONE run — one box, so a rounded wall has no
    dip at every cell."""
    frames = [_maze_segments(cols, rows, maze_walls(cols, rows, s))
              for s in seeds]
    pattern = {}
    for i, closed in enumerate(frames):
        for seg in closed:
            pattern.setdefault(seg, [0] * len(frames))[i] = 1
    runs = []
    for (axis, line, index), on in sorted(pattern.items()):
        last = runs[-1] if runs else None
        if last and last[:2] == (axis, line) and last[3] == index - 1 \
                and last[4] == on:
            runs[-1] = (axis, line, last[2], index, on)
        else:
            runs.append((axis, line, index, index, on))
    return [(a, ln, i, j, tuple(on)) for a, ln, i, j, on in runs]


def _block(name, x, y, z, w, d, h, r):
    """A wall block: a cube, or a box with every edge rounded."""
    if r <= 0.01:
        return _cube(name, x, y, z, w, d, h)
    return CadNode("rounded_box", name, dict(
        x=x, y=y, z=z, width=w, depth=d, height=h,
        radius=min(r, w / 2, d / 2, h / 2), center=False, segments=8))


def maze_variables(prefix, count):
    """The Customizer variables that drive a changing maze: a ``<prefix>_t``
    slider (0 → one maze per step; play sweeps through them) and the
    hidden maze index and eased blend it feeds."""
    t, k, u = (f"{prefix}_t", f"{prefix}_k", f"{prefix}_u")
    return [
        CadNode("assign", t, dict(
            variable=t, value="0", options=f"0:0.05:{count}",
            description="Maze morph — press play and the walls rise and "
                        "fall into the next maze", group="Maze · Motion")),
        CadNode("assign", k, dict(variable=k,
                                  value=f"floor({t}) % {count}",
                                  group="Hidden")),
        CadNode("assign", u, dict(
            variable=u, value=f"({t} - floor({t})) * ({t} - floor({t}))"
                              f" * (3 - 2 * ({t} - floor({t})))",
            group="Hidden")),
    ]


def build_maze(dims, prefix="maze", variables=True):
    """A printable maze: a base plate and walls between cells a
    backtracker left closed; the entrance and exit are open.

    Seed 0 (the default) draws a new maze every time; the seed used is
    in the part's name, so typing it back rebuilds that maze.
    ``rounding`` > 0 rounds every wall edge (each straight run is one
    rounded box, sunk into the base so no groove shows at its foot).
    ``mazes`` ≥ 2 makes it CHANGE: one maze per seed from ``seed`` on,
    every wall scaled by how much it stands at ``<prefix>_t``, so playing
    that slider raises and lowers walls into each maze in turn."""
    p = _d(dims, MAZE_SIZES)
    cols, rows = max(int(p["cols"]), 2), max(int(p["rows"]), 2)
    s, wall, h, base = p["cell"], p["wall"], p["height"], p["base"]
    count = min(max(int(p.get("mazes") or 1), 1), MAX_MAZES)
    r = max(min(float(p.get("rounding") or 0.0), wall / 2, base / 2, h / 2),
            0.0)
    seed = int(p["seed"]) or new_seed()
    # sunk into the base: hides a rounded foot, and a lowered wall
    sink = 2 * r if r > 0.01 else (min(0.2, base / 2) if count > 1 else 0.0)
    W, D = cols * s + wall, rows * s + wall
    k, u = f"{prefix}_k", f"{prefix}_u"
    walls = _group("Walls")
    for axis, line, i, j, on in maze_runs(cols, rows,
                                          range(seed, seed + count)):
        if axis == "x":
            x, y, w, d = line * s, i * s, wall, (j - i + 1) * s + wall
        else:
            x, y, w, d = i * s, line * s, (j - i + 1) * s + wall, wall
        if all(on):
            walls.add(_block("Wall", x, y, base - sink, w, d, h + sink, r))
            continue
        pattern = "[" + ", ".join(map(str, on)) + "]"
        rise = CadNode("scale", "Rise", dict(
            x=1.0, y=1.0, z=f"max(0.001, {pattern}[{k}] * (1 - {u}) + "
                            f"{pattern}[({k} + 1) % {count}] * {u})"))
        rise.add(_block("Wall", 0, 0, 0, w, d, h + sink, r))
        walls.add(_move(rise, x=x, y=y, z=base - sink))
    border = _group("Border",
                    _block("South", s, 0, base - sink, W - s, wall,
                           h + sink, r),
                    _block("North", 0, D - wall, base - sink, W - s, wall,
                           h + sink, r),
                    _block("West", 0, 0, base - sink, wall, D, h + sink, r),
                    _block("East", W - wall, 0, base - sink, wall, D,
                           h + sink, r))
    maze = _group(("Changing maze" if count > 1 else "Maze")
                  + f" (seed {seed})",
                  _block("Base", 0, 0, 0, W, D, base, r), border, walls)
    if count > 1 and variables:
        for n, var in enumerate(maze_variables(prefix, count)):
            maze.add(var, n)
    return _paint(maze, dims, "Blue")


def insert_maze(model, dims):
    """Library insert: a still maze is one Object; a changing one also
    puts its slider among the document's variables (``maze_t``, then
    ``maze2_t``…) so the Customizer's play — or play_motion — runs it."""
    from . import library_motion
    p = _d(dims, MAZE_SIZES)
    count = min(max(int(p.get("mazes") or 1), 1), MAX_MAZES)
    dims = dict(dims, seed=int(p["seed"]) or new_seed())
    prefix = "maze"
    if count > 1:
        prefix = library_motion.free_prefix(model, "maze")
        holder = CadNode("union", "Variables")
        for var in maze_variables(prefix, count):
            holder.add(var)
        library_motion.place(model, holder)
    node = build_maze(dims, prefix=prefix, variables=False)
    model.root.add(node)
    model.structure_changed.emit()
    return [model.enclose_as_part(node)]


def hilbert(order):
    """Points of a Hilbert curve on a 2^order grid."""
    n = 2 ** order
    pts = []
    for d in range(n * n):
        x = y = 0
        t = d
        s = 1
        while s < n:
            rx = 1 & (t // 2)
            ry = 1 & (t ^ rx)
            if ry == 0:
                if rx == 1:
                    x, y = s - 1 - x, s - 1 - y
                x, y = y, x
            x += s * rx
            y += s * ry
            t //= 4
            s *= 2
        pts.append((x, y))
    return pts


HILBERT_SIZES = {"Order 4 (80 mm)": dict(order=4, size=80.0, line=1.6,
                                         height=1.5, base=1.5)}


def build_hilbert(dims):
    """A plate with a raised Hilbert curve — one continuous line of line
    segments (each a node you can edit)."""
    p = _d(dims, HILBERT_SIZES)
    order = min(max(int(p["order"]), 1), 6)
    pts = hilbert(order)
    step = p["size"] / (2 ** order)
    path = CadNode("union", "Hilbert curve")
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        path.add(CadNode("line", "Segment", dict(
            x1=(x1 + 0.5) * step, y1=(y1 + 0.5) * step,
            x2=(x2 + 0.5) * step, y2=(y2 + 0.5) * step, width=p["line"])))
    raised = _move(_extrude("Raised curve", path, p["height"]), z=p["base"])
    return _paint(_group("Hilbert plate",
                         _cube("Base", 0, 0, 0, p["size"], p["size"],
                               p["base"]), raised), dims, "Yellow")


def _spec(label, category, sizes, build, fields):
    return dict(label=label, category=category, sizes=sizes, build=build,
                fields=fields, colors=list(COLORS))


PARTS = {
    "technic_beam": _spec("Technic beam", TECHNIC, BEAM_SIZES,
                          build_technic_beam, [("holes", "Holes")]),
    "technic_axle": _spec("Technic axle", TECHNIC, AXLE_SIZES,
                          build_technic_axle, [("units", "Length units")]),
    "technic_pin": _spec("Technic friction pin", TECHNIC, PIN_SIZES,
                         build_technic_pin, [("length", "Length")]),
    "technic_gear": _spec("Technic gear", TECHNIC, TGEAR_SIZES,
                          build_technic_gear, [("teeth", "Teeth")]),
    "gen_voronoi": _spec("Voronoi panel", GENERATIVE, VORONOI_SIZES,
                         build_voronoi,
                         [("width", "Width"), ("depth", "Depth"),
                          ("thickness", "Thickness"), ("cells", "Cells"),
                          ("wall", "Wall"), ("seed", "Seed")]),
    "gen_maze": _spec("Maze", GENERATIVE, MAZE_SIZES, build_maze,
                      [("cols", "Columns"), ("rows", "Rows"),
                       ("cell", "Cell size"), ("wall", "Wall"),
                       ("height", "Wall height"), ("base", "Base"),
                       ("seed", "Seed (0 = new maze each time)"),
                       ("rounding", "Rounding"),
                       ("mazes", "Mazes (2+ = changing)")]),
    "gen_hilbert": _spec("Hilbert-curve plate", GENERATIVE, HILBERT_SIZES,
                         build_hilbert,
                         [("order", "Order"), ("size", "Size"),
                          ("line", "Line width"), ("height", "Raised by"),
                          ("base", "Base")]),
}

PARTS["gen_maze"].update(
    insert=insert_maze,
    insert_note="Added as one Object. With mazes >= 2 it is a changing "
                "maze: its maze_t slider (a document variable, prefixed "
                "for a second copy) morphs it from maze to maze — "
                "play_motion sets it running.")

COUNT_FIELDS = {"holes", "units", "cells", "seed", "cols", "rows", "order",
                "mazes"}
