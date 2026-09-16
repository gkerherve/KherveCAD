"""The City Builder's geometry (Qt-free): villages, towns and cities.

A house from the House Builder has rooms, walls on both sides and
furniture; a city of those would be millions of triangles. Here a
building is its OUTSIDE only — a shell box (or cylinder, or two wings)
with windows painted on its facades and a roof, nothing inside — so a
town of a hundred buildings stays a few hundred nodes.

The design is a JSON-shaped spec (all millimetres, Z up):

- ``roads``: polylines ``{"points": [[x, y], ...], "width", "kind",
  "sidewalk"}`` — asphalt over a raised pavement strip, a disc at every
  point so corners and junctions close, centre dashes on streets.
- ``buildings``: ``{"x", "y", "w", "d", "rz", "style", "floors",
  "color", "roof_color", "name"}`` centred on (x, y); `STYLES` gives
  cottage, house, terrace, shop, block, tower, round tower, L-shape and
  church.
- ``lights`` / ``trees``: explicit lists, or ``{"spacing": mm}`` to line
  every road with them.

Repeated things are LOOPS, not copies: every street light is one
iteration of a single `for_loop` over a value list of positions, the
same for each kind of tree and for each facade's windows — the program
reads as a city plan and the tree stays short. `generate` writes a
spec for a village, a town or a city from a seed; `apply` inserts it
as a handful of Objects (Ground, Roads, Buildings, Street lights,
Trees), replacing the ones the last build made.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
import random

from .model import CadNode

FLOOR_HEIGHT = 3000.0
ROAD_THICKNESS = 60.0
KERB = 150.0
ASPHALT = "#3d3f43"
PAVEMENT = "#b8b3aa"
DASH = "#f1efe6"
GRASS = "#6aa84f"
WINDOW = "#2f4a5c"
DOOR = "#5b3a29"

ROAD_KINDS = {                  # width, pavement each side, centre dashes
    "avenue": (12000.0, 3500.0, True),
    "street": (7000.0, 2500.0, True),
    "lane": (4500.0, 1500.0, False),
    "path": (2000.0, 0.0, False),
}

WALL_COLORS = ["#f2e6d0", "#e8d2b0", "#d9a58a", "#c9b79c", "#f4f1ea",
               "#b7c4c9", "#d6c38f", "#e3b7a0", "#a9b8a0", "#cfcac4"]
ROOF_COLORS = ["#7a3b2e", "#5d4037", "#8d4a36", "#4e5156", "#6b4a3a"]

#: style -> (floors range, roof, windows) — what `generate` draws from
STYLES = {
    "cottage": ((1, 2), "gable", "windows"),
    "house": ((2, 2), "hip", "windows"),
    "terrace": ((2, 3), "gable", "windows"),
    "shop": ((1, 2), "flat", "shopfront"),
    "block": ((3, 7), "flat", "bands"),
    "tower": ((10, 30), "flat", "bands"),
    "round tower": ((3, 12), "cone", "bands"),
    "L-shape": ((2, 3), "gable", "windows"),
    "church": ((2, 2), "gable", "windows"),
}

TREE_KINDS = ("broadleaf", "conifer", "round")
MAX_BUILDINGS = 2000


class CityError(ValueError):
    """A spec the City Builder cannot build (the message says why)."""


# ------------------------------------------------------------ helpers
def _f(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _color(node, color, material="Default", alpha=1.0, name=None):
    c = CadNode("color", name or node.name,
                dict(color=color, alpha=alpha, material=material))
    c.add(node)
    return c


def _group(name, children=()):
    g = CadNode("union", name, {})
    for ch in children:
        g.add(ch)
    return g


def _box(name, x, y, z, w, d, h):
    return CadNode("cube", name, dict(x=x, y=y, z=z, width=w, depth=d,
                                      height=h, center=False))


def _place(node, x, y, rz=0.0, name=None):
    """*node* turned *rz* about its own origin, then moved to (x, y)."""
    inner = node
    if rz:
        inner = CadNode("rotate", "Turn", dict(x=0.0, y=0.0, z=rz))
        inner.add(node)
    t = CadNode("translate", name or node.name, dict(x=x, y=y, z=0.0))
    t.add(inner)
    return t


def _loop(name, var, values, children):
    """One `for_loop` over an explicit value list — the copies of a
    repeated thing are iterations, not nodes."""
    text = ", ".join("[" + ", ".join(_num(v) for v in row) + "]"
                     if isinstance(row, (list, tuple)) else _num(row)
                     for row in values)
    loop = CadNode("for_loop", name, dict(variable=var, start=0.0, end=0.0,
                                          step=1.0, values=text))
    for ch in children:
        loop.add(ch)
    return loop


def _num(v):
    v = round(float(v), 1)
    return str(int(v)) if v == int(v) else str(v)


# -------------------------------------------------------------- roads
def _segments(road):
    pts = [(_f(p[0]), _f(p[1])) for p in road.get("points") or []]
    return [(a, b) for a, b in zip(pts, pts[1:])
            if math.hypot(b[0] - a[0], b[1] - a[1]) > 1.0]


def road_style(road):
    kind = road.get("kind", "street")
    width, walk, dashes = ROAD_KINDS.get(kind, ROAD_KINDS["street"])
    return (_f(road.get("width"), width), _f(road.get("sidewalk"), walk),
            dashes and bool(road.get("dashes", True)))


def build_roads(roads) -> CadNode:
    """Asphalt strips over pavement strips (the pavement a kerb higher,
    wider by a pavement each side), a disc at every vertex so bends and
    junctions close, and a loop of centre dashes per street segment."""
    asphalt, pavement, dashes = [], [], []
    for r_i, road in enumerate(roads):
        width, walk, dashed = road_style(road)
        for a, b in _segments(road):
            length = math.hypot(b[0] - a[0], b[1] - a[1])
            ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
            if walk > 0:
                pavement.append(_place(
                    _box("Pavement", 0.0, -width / 2 - walk, 0.0, length,
                         width + 2 * walk, KERB), a[0], a[1], ang))
            asphalt.append(_place(
                _box("Asphalt", 0.0, -width / 2, 0.0, length, width,
                     ROAD_THICKNESS), a[0], a[1], ang))
            n = int(length // 6000)
            if dashed and n >= 1:
                dash = _box("Dash", "i * 6000 + 1500", -75.0, ROAD_THICKNESS,
                            3000.0, 150.0, 5.0)
                loop = CadNode("for_loop", "Centre line",
                               dict(variable="i", start=0.0, end=n - 1,
                                    step=1.0, values=""))
                loop.add(dash)
                dashes.append(_place(loop, a[0], a[1], ang))
        pts = [(_f(p[0]), _f(p[1])) for p in road.get("points") or []]
        for x, y in pts:
            if walk > 0:
                pavement.append(CadNode("cylinder", "Corner", dict(
                    x=x, y=y, z=0.0, height=KERB,
                    radius_bottom=width / 2 + walk,
                    radius_top=width / 2 + walk, segments=16, center=False)))
            asphalt.append(CadNode("cylinder", "Junction", dict(
                x=x, y=y, z=0.0, height=ROAD_THICKNESS + 1.0,
                radius_bottom=width / 2, radius_top=width / 2, segments=16,
                center=False)))
    group = _group("Roads")
    if pavement:
        # asphalt sits on the pavement: kerb height plus its own
        group.add(_color(_group("Pavements", pavement), PAVEMENT, "Matte"))
    top = CadNode("translate", "On the kerb", dict(x=0.0, y=0.0, z=KERB))
    top.add(_color(_group("Asphalt", asphalt), ASPHALT, "Matte"))
    if dashes:
        top.add(_color(_group("Markings", dashes), DASH, "Matte"))
    group.add(top)
    return group


def along_roads(roads, spacing, offset_extra=0.0, phase=0.0):
    """Points on both pavements of every road, *spacing* apart and
    staggered side to side: (x, y, rz) with rz facing the road."""
    out = []
    spacing = max(2000.0, float(spacing))
    for road in roads:
        width, walk, _ = road_style(road)
        if walk <= 0:
            continue
        off = width / 2 + walk * 0.35 + offset_extra
        for a, b in _segments(road):
            length = math.hypot(b[0] - a[0], b[1] - a[1])
            ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
            ang = math.degrees(math.atan2(uy, ux))
            s, side = spacing * (0.5 + phase), 1
            while s < length - spacing * 0.25:
                nx, ny = -uy * side, ux * side
                out.append((a[0] + ux * s + nx * off,
                            a[1] + uy * s + ny * off,
                            ang - 90.0 if side > 0 else ang + 90.0))
                s += spacing / 2.0
                side = -side
    return out


# ------------------------------------------------------ lights, trees
def build_lights(points) -> CadNode:
    """Every light is one iteration of ONE loop: a pole, an arm reaching
    over the road (local -Y) and a glowing lamp head."""
    pole = _color(CadNode("cylinder", "Pole", dict(
        x=0.0, y=0.0, z=0.0, height=6000.0, radius_bottom=90.0,
        radius_top=60.0, segments=8, center=False)), "#3a3d40", "Metal")
    arm = _color(_box("Arm", -40.0, -1500.0, 5900.0, 80.0, 1500.0, 80.0),
                 "#3a3d40", "Metal")
    lamp = _color(_box("Lamp", -150.0, -1700.0, 5750.0, 300.0, 600.0, 150.0),
                  "#fff3c4", "Emissive")
    turn = CadNode("rotate", "Face the road", dict(x=0.0, y=0.0, z="p[2]"))
    for part in (pole, arm, lamp):
        turn.add(part)
    at = CadNode("translate", "At", dict(x="p[0]", y="p[1]", z=KERB))
    at.add(turn)
    return _group("Street lights", [_loop("Lights", "p", points, [at])])


def _tree_body(kind):
    """One tree at the origin, height 1 unit = scaled by p[2] (metres)."""
    if kind == "conifer":
        trunk = CadNode("cylinder", "Trunk", dict(
            x=0.0, y=0.0, z=0.0, height=800.0, radius_bottom=120.0,
            radius_top=100.0, segments=6, center=False))
        crown = CadNode("cylinder", "Crown", dict(
            x=0.0, y=0.0, z=600.0, height=5400.0, radius_bottom=1500.0,
            radius_top=0.0, segments=8, center=False))
        leaf = "#2e5e3a"
    else:
        trunk = CadNode("cylinder", "Trunk", dict(
            x=0.0, y=0.0, z=0.0, height=2600.0, radius_bottom=180.0,
            radius_top=130.0, segments=6, center=False))
        r = 1900.0 if kind == "broadleaf" else 1500.0
        crown = CadNode("sphere", "Crown", dict(
            x=0.0, y=0.0, z=2600.0 + r * 0.7, radius=r, segments=8))
        if kind == "broadleaf":
            crown = _group("Crown", [crown, CadNode("sphere", "Lobe", dict(
                x=r * 0.6, y=r * 0.2, z=2600.0 + r * 0.3, radius=r * 0.7,
                segments=8))])
        leaf = "#4f8a3a" if kind == "broadleaf" else "#6a9c3c"
    return [_color(trunk, "#6b4b33", "Matte"), _color(crown, leaf, "Matte")]


def build_trees(trees) -> CadNode:
    """One loop per kind over [x, y, scale, turn] rows (scale 1 = about
    6 m tall), so a park of fifty trees is three loops."""
    group = _group("Trees")
    by_kind = {}
    for t in trees:
        kind = t.get("kind", "broadleaf")
        kind = kind if kind in TREE_KINDS else "broadleaf"
        by_kind.setdefault(kind, []).append(
            (_f(t.get("x")), _f(t.get("y")),
             max(0.2, _f(t.get("height"), 6000.0) / 6000.0),
             _f(t.get("rz"), 0.0), _f(t.get("z"), 0.0)))
    for kind, rows in by_kind.items():
        sc = CadNode("scale", "Size", dict(x="p[2]", y="p[2]", z="p[2]"))
        turn = CadNode("rotate", "Turn", dict(x=0.0, y=0.0, z="p[3]"))
        for part in _tree_body(kind):
            turn.add(part)
        sc.add(turn)
        at = CadNode("translate", "At", dict(x="p[0]", y="p[1]", z="p[4]"))
        at.add(sc)
        group.add(_loop(f"{kind.capitalize()} trees", "p", rows, [at]))
    return group


# ---------------------------------------------------------- buildings
def _windows_on(name, length, floors, fh, depth_at, along_x, z0=900.0,
                pitch=3000.0, ww=1200.0, wh=1400.0, sign=1):
    """A facade's windows as two nested loops (floor f, column c) around
    ONE thin pane — a 40-window facade is four nodes."""
    cols = int((length - 1000.0) // pitch)
    if cols < 1 or floors < 1:
        return None
    start = (length - (cols - 1) * pitch) / 2.0 - ww / 2.0 - length / 2.0
    u = f"{_num(start)} + c * {_num(pitch)}"
    zexpr = f"{_num(z0)} + f * {_num(fh)}"
    t = 60.0
    v = depth_at if sign > 0 else depth_at - t
    pane = (_box("Window", u, v, zexpr, ww, t, wh) if along_x
            else _box("Window", v, u, zexpr, t, ww, wh))
    cl = CadNode("for_loop", "Columns", dict(variable="c", start=0.0,
                                             end=cols - 1, step=1.0,
                                             values=""))
    cl.add(pane)
    fl = CadNode("for_loop", name, dict(variable="f", start=0.0,
                                        end=floors - 1, step=1.0, values=""))
    fl.add(cl)
    return fl


def _roof(kind, w, d, z, color):
    """A roof over a w x d footprint centred on the origin, top of the
    walls at *z*: flat parapet slab, gable (hull of eaves and a ridge),
    hip (eaves hulled to a shorter ridge)."""
    e = 400.0
    if kind == "flat":
        return _color(_box("Roof", -w / 2 - 150, -d / 2 - 150, z, w + 300,
                           d + 300, 400.0), "#8a8580", "Matte")
    along_x = w >= d
    span, length = (d, w) if along_x else (w, d)
    rise = span / 2.0 * math.tan(math.radians(35 if kind == "gable" else 30))
    ridge_len = length + 2 * e if kind == "gable" else max(length - span, 10.0)

    def bar(u0, v0, zz, du, dv, h):
        return (_box("Board", u0, v0, zz, du, dv, h) if along_x
                else _box("Board", v0, u0, zz, dv, du, h))

    hull = CadNode("hull", "Roof", {})
    hull.add(bar(-length / 2 - e, -span / 2 - e, z - e * 0.5, length + 2 * e,
                 span + 2 * e, 120.0))
    hull.add(bar(-ridge_len / 2, -10.0, z + rise, ridge_len, 20.0, 120.0))
    return _color(hull, color, "Matte")


def build_building(b: dict, index: int = 0) -> CadNode:
    """One building's OUTSIDE as a placed group: shell, windows, a door,
    its roof — nothing inside."""
    style = b.get("style", "house")
    if style not in STYLES:
        raise CityError(f'Unknown building style "{style}"; use one of '
                        + ", ".join(STYLES))
    (lo, hi), roof_kind, glazing = STYLES[style]
    w = max(2000.0, _f(b.get("w"), 8000.0))
    d = max(2000.0, _f(b.get("d"), 8000.0))
    floors = max(1, int(_f(b.get("floors"), lo)))
    fh = max(2200.0, _f(b.get("floor_height"), FLOOR_HEIGHT))
    wall = b.get("color") or WALL_COLORS[index % len(WALL_COLORS)]
    roof_col = b.get("roof_color") or ROOF_COLORS[index % len(ROOF_COLORS)]
    roof_kind = b.get("roof", roof_kind)
    name = b.get("name") or f"{style.capitalize()} {index + 1}"
    H = floors * fh
    body = _group(name)
    glass = _group("Windows")

    if style == "round tower":
        r = min(w, d) / 2.0
        body.add(_color(CadNode("cylinder", "Walls", dict(
            x=0.0, y=0.0, z=0.0, height=H, radius_bottom=r, radius_top=r,
            segments=16, center=False)), wall, "Matte"))
        band = CadNode("cylinder", "Band", dict(
            x=0.0, y=0.0, z=f"900 + f * {_num(fh)}", height=1300.0,
            radius_bottom=r + 30, radius_top=r + 30, segments=16,
            center=False))
        fl = CadNode("for_loop", "Floors", dict(variable="f", start=0.0,
                                                end=floors - 1, step=1.0,
                                                values=""))
        fl.add(band)
        glass.add(fl)
        body.add(_color(glass, WINDOW, "Glass", 0.85))
        roof = CadNode("cylinder", "Roof", dict(
            x=0.0, y=0.0, z=H, height=r * 1.2, radius_bottom=r + 300,
            radius_top=0.0, segments=16, center=False))
        body.add(_color(roof, roof_col, "Matte"))
        return _place(body, _f(b.get("x")), _f(b.get("y")),
                      _f(b.get("rz")), name)

    wings = [(-w / 2, -d / 2, w, d)]
    if style == "L-shape":
        wing_d = d * 0.45
        wings = [(-w / 2, -d / 2, w, wing_d),
                 (-w / 2, -d / 2 + wing_d - 1, w * 0.45, d - wing_d + 1)]
    for i, (x0, y0, ww_, dd_) in enumerate(wings):
        body.add(_color(_box("Walls" if i == 0 else "Wing", x0, y0, 0.0,
                             ww_, dd_, H), wall, "Matte"))
        if glazing == "bands":
            ring = _box("Glazing", x0 - 30, y0 - 30, f"900 + f * {_num(fh)}",
                        ww_ + 60, dd_ + 60, fh * 0.45)
            fl = CadNode("for_loop", "Floors", dict(
                variable="f", start=0.0, end=floors - 1, step=1.0,
                values=""))
            fl.add(ring)
            wrap = CadNode("translate", "Wing", dict(x=0.0, y=0.0, z=0.0))
            wrap.add(fl)
            glass.add(wrap)
        else:
            first = 1 if glazing == "shopfront" else 0
            for label, length, pos, ax, sign in (
                    ("Front", ww_, y0, True, -1), ("Back", ww_, y0 + dd_,
                                                   True, 1),
                    ("Left", dd_, x0, False, -1), ("Right", dd_, x0 + ww_,
                                                   False, 1)):
                loop = _windows_on(f"{label} windows", length,
                                   floors - first, fh, pos, ax,
                                   z0=900.0 + first * fh, sign=sign)
                if loop is None:
                    continue
                shift = (dict(x=x0 + ww_ / 2, y=0.0, z=0.0) if ax
                         else dict(x=0.0, y=y0 + dd_ / 2, z=0.0))
                t = CadNode("translate", label, shift)
                t.add(loop)
                glass.add(t)
        if style == "church" and i == 0:
            tw = min(w, d) * 0.45
            body.add(_color(_box("Bell tower", -w / 2 - tw * 0.5, -tw / 2,
                                 0.0, tw, tw, H * 2.2), wall, "Matte"))
            body.add(_color(CadNode("cylinder", "Spire", dict(
                x=-w / 2, y=0.0, z=H * 2.2, height=tw * 2.5,
                radius_bottom=tw * 0.72, radius_top=0.0, segments=4,
                center=False)), roof_col, "Matte"))
        body.add(_place(_roof(roof_kind, ww_, dd_, H, roof_col),
                        x0 + ww_ / 2, y0 + dd_ / 2, name="Roof"))
    if style == "shop":
        body.add(_color(_box("Shop window", -w / 2 + 600, -d / 2 - 60, 300.0,
                             w - 1200, 60.0, 2200.0), WINDOW, "Glass", 0.85))
        body.add(_color(_box("Awning", -w / 2 + 300, -d / 2 - 1400, 2700.0,
                             w - 600, 1400.0, 120.0),
                        ["#b83b3b", "#2f6f8f", "#3f8f4f"][index % 3],
                        "Matte"))
    else:
        body.add(_color(_box("Door", -600.0, -d / 2 - 50, 0.0, 1200.0, 60.0,
                             2200.0), DOOR, "Matte"))
    if glass.children:
        body.add(_color(glass, WINDOW, "Glass", 0.85))
    return _place(body, _f(b.get("x")), _f(b.get("y")), _f(b.get("rz")), name)


# ----------------------------------------------------------- generator
def _lots(x0, y0, x1, y1, rng, styles, setback=1500.0):
    """Buildings round the edge of one block, fronts facing its roads."""
    out = []
    bw, bd = x1 - x0, y1 - y0
    if bw < 6000 or bd < 6000:
        return out
    depth = min(12000.0, bd / 2 - setback, bw / 2 - setback)
    if depth < 4000:
        return out
    # south and north rows (front faces the road), then the east/west gaps
    for row, (yc, rz) in enumerate(((y0 + setback + depth / 2, 0.0),
                                    (y1 - setback - depth / 2, 180.0))):
        x = x0 + setback
        while True:
            style = rng.choice(styles)
            (lo, hi), _, _ = STYLES[style]
            w = {"tower": rng.uniform(14000, 20000),
                 "block": rng.uniform(14000, 24000),
                 "church": 20000.0}.get(style, rng.uniform(7000, 12000))
            if x + w > x1 - setback:
                break
            d = depth if style not in ("round tower", "tower") else min(
                depth, w)
            if style in ("round tower", "church"):
                d = depth
            out.append(dict(style=style, x=x + w / 2, y=yc, w=w, d=d, rz=rz,
                            floors=rng.randint(lo, hi)))
            x += w + rng.uniform(400, 2500)
    return out


def generate(layout: str = "town", blocks: int = 0, seed: int = 1) -> dict:
    """A spec for a village (a crossroads with a church and cottages), a
    town (a street grid of houses, shops and blocks, a park) or a city
    (avenues, towers towards the centre, blocks outward, a park)."""
    rng = random.Random(seed)
    if layout not in ("village", "town", "city"):
        raise CityError('layout must be "village", "town" or "city"')
    if layout == "village":
        n = blocks or 2
        span = n * 40000.0
        roads = [dict(kind="street", points=[[-span, 0], [span, 0]]),
                 dict(kind="lane", points=[[0, -span], [0, span * 0.8]])]
        buildings, trees = [], []
        for side in (-1, 1):
            x = -span + 4000
            while x < span - 8000:
                if abs(x) < 9000:
                    x = 9000
                w = rng.uniform(7000, 11000)
                style = rng.choice(["cottage", "cottage", "house",
                                    "terrace", "shop"])
                (lo, hi), _, _ = STYLES[style]
                off = 3500 + 2500 + rng.uniform(2000, 5000)
                buildings.append(dict(style=style, x=x + w / 2,
                                      y=side * (off + 4500), w=w, d=8000,
                                      rz=0.0 if side < 0 else 180.0,
                                      floors=rng.randint(lo, hi)))
                if rng.random() < 0.5:
                    trees.append(dict(x=x + w / 2, y=side * (off + 14000),
                                      kind=rng.choice(TREE_KINDS),
                                      height=rng.uniform(5000, 9000)))
                x += w + rng.uniform(3000, 9000)
        buildings.append(dict(style="church", name="Church", x=-18000,
                              y=22000, w=22000, d=11000, rz=180.0,
                              floors=2))
        for _ in range(12 * n):
            x, y = rng.uniform(-span, span), rng.choice((-1, 1)) * \
                rng.uniform(30000, 45000)
            trees.append(dict(x=x, y=y, kind=rng.choice(TREE_KINDS),
                              height=rng.uniform(5000, 12000)))
        return dict(name="Village", roads=roads, buildings=buildings,
                    trees=trees, lights={"spacing": 40000},
                    ground=dict(margin=15000))
    n = blocks or (3 if layout == "town" else 5)
    pitch = 70000.0 if layout == "town" else 90000.0
    size = n * pitch
    kind = "street" if layout == "town" else "avenue"
    roads = []
    for i in range(n + 1):
        c = i * pitch - size / 2
        roads.append(dict(kind=kind, points=[[-size / 2, c], [size / 2, c]]))
        roads.append(dict(kind=kind, points=[[c, -size / 2], [c, size / 2]]))
    half = ROAD_KINDS[kind][0] / 2 + ROAD_KINDS[kind][1]
    park = (n // 2, n // 2 - (1 if n > 2 else 0))
    buildings, trees = [], []
    for i in range(n):
        for j in range(n):
            x0 = i * pitch - size / 2 + half
            y0 = j * pitch - size / 2 + half
            x1, y1 = x0 + pitch - 2 * half, y0 + pitch - 2 * half
            if (i, j) == park:
                for _ in range(int(pitch / 4000)):
                    trees.append(dict(x=rng.uniform(x0 + 3000, x1 - 3000),
                                      y=rng.uniform(y0 + 3000, y1 - 3000),
                                      kind=rng.choice(TREE_KINDS),
                                      height=rng.uniform(6000, 12000)))
                continue
            ring = max(abs(i - (n - 1) / 2), abs(j - (n - 1) / 2))
            if layout == "town":
                styles = (["shop", "block", "terrace"] if ring < 1
                          else ["house", "cottage", "terrace", "L-shape"])
            else:
                styles = (["tower", "tower", "round tower"] if ring < 1
                          else ["block", "tower", "shop"] if ring < 2
                          else ["block", "terrace", "shop", "house"])
            buildings.extend(_lots(x0, y0, x1, y1, rng, styles))
    if layout == "town":
        buildings.append(dict(style="church", name="Church",
                              x=-size / 2 - 20000, y=0.0, w=22000, d=11000,
                              rz=90.0))
    return dict(name=layout.capitalize(), roads=roads, buildings=buildings,
                trees=trees, lights={"spacing": 30000},
                street_trees={"spacing": 30000},
                ground=dict(margin=30000))


# --------------------------------------------------------------- apply
OBJECT_NAMES = ("City ground", "City roads", "City buildings",
                "Street lights", "City trees")


def _extent(spec, buildings):
    xs, ys = [], []
    for r in spec.get("roads") or []:
        for p in r.get("points") or []:
            xs.append(_f(p[0]))
            ys.append(_f(p[1]))
    for b in buildings:
        xs.append(_f(b.get("x")))
        ys.append(_f(b.get("y")))
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def build(spec: dict) -> dict:
    """The spec compiled to nodes: {object name: node}, plus counts."""
    spec = dict(spec or {})
    if spec.get("layout"):
        base = generate(spec["layout"], int(_f(spec.get("blocks"), 0)),
                        int(_f(spec.get("seed"), 1)))
        for key in ("roads", "buildings", "trees"):
            base[key] = base.get(key, []) + list(spec.get(key) or [])
        for key in ("lights", "street_trees", "ground", "name"):
            if key in spec:
                base[key] = spec[key]
        spec = base
    roads = list(spec.get("roads") or [])
    buildings = list(spec.get("buildings") or [])
    if len(buildings) > MAX_BUILDINGS:
        raise CityError(f"{len(buildings)} buildings — at most "
                        f"{MAX_BUILDINGS} in one build.")
    if not (roads or buildings):
        raise CityError("Nothing to build: give roads and/or buildings, "
                        'or a layout ("village", "town", "city").')
    nodes = {}
    ext = _extent(spec, buildings)
    ground = spec.get("ground", {"margin": 20000})
    if ground and ext:
        m = _f(ground.get("margin"), 20000)
        x0, y0, x1, y1 = ext
        nodes["City ground"] = _color(_box(
            "Ground", x0 - m, y0 - m, -200.0, x1 - x0 + 2 * m,
            y1 - y0 + 2 * m, 200.0), ground.get("color", GRASS), "Matte")
    if roads:
        nodes["City roads"] = build_roads(roads)
    if buildings:
        g = _group("Buildings")
        for i, b in enumerate(buildings):
            g.add(build_building(b, i))
        nodes["City buildings"] = g
    lights = spec.get("lights")
    points = (along_roads(roads, _f(lights.get("spacing"), 30000))
              if isinstance(lights, dict) else
              [(_f(p[0]), _f(p[1]), _f(p[2]) if len(p) > 2 else 0.0)
               for p in lights or []])
    if points:
        nodes["Street lights"] = build_lights(points)
    trees = [dict(t) for t in spec.get("trees") or []]
    st = spec.get("street_trees")
    if isinstance(st, dict):
        for x, y, rz in along_roads(roads, _f(st.get("spacing"), 30000),
                                    offset_extra=0.0, phase=0.5):
            trees.append(dict(x=x, y=y, z=KERB, rz=rz,
                              kind=st.get("kind", "round"),
                              height=_f(st.get("height"), 6000)))
    if trees:
        nodes["City trees"] = build_trees(trees)
    return dict(nodes=nodes, counts=dict(
        roads=len(roads), buildings=len(buildings), lights=len(points),
        trees=len(trees)), name=spec.get("name", "City"))


def apply(model, spec: dict, replace: bool = True) -> dict:
    """Insert the city as a few Objects; with *replace*, the Objects a
    previous City Builder build made (by name) are removed first, so
    building again UPDATES the city. One call = one undo step."""
    result = build(spec)
    if replace:
        for comp in list(model.root.children):
            if comp.type == "component" and comp.name in OBJECT_NAMES:
                model.root.remove(comp)
    inserted = []
    for name, node in result["nodes"].items():
        model.root.add(node)
        inserted.append(model.enclose_as_part(node, name=name))
    model.structure_changed.emit()
    return dict(result, inserted=inserted)


def build_city(window, params: dict) -> dict:
    """The build_city MCP tool."""
    params = dict(params or {})
    if params.pop("dry_run", False):
        r = build(params)
        return {"dry_run": True, "counts": r["counts"],
                "objects": list(r["nodes"])}
    r = apply(window.model, params, replace=params.pop("replace", True))
    window.view3d.fit()
    return {"objects": [{"id": c.id, "name": c.name}
                        for c in r["inserted"]],
            "counts": r["counts"]}
