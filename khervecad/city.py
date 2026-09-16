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
ROAD_THICKNESS = 100.0
KERB = 150.0
ASPHALT = "#3d3f43"
PAVEMENT = "#b8b3aa"
DASH = "#f1efe6"
GRASS = "#6aa84f"

ROAD_KINDS = {                  # width, pavement each side, centre dashes
    "avenue": (12000.0, 3500.0, True),
    "street": (7000.0, 2500.0, True),
    "lane": (4500.0, 1500.0, False),
    "path": (2000.0, 0.0, False),
}

from .city_buildings import STYLES, BuildingError, build_building  # noqa
from .city_trees import TREE_KINDS, build_lights, build_trees  # noqa

MAX_BUILDINGS = 2000
#: the ground and long road strips are laid in tiles no longer than
#: this: the software painter sorts faces by centre, and one 400 m face
#: painted over every house standing on it
TILE = 20000.0
ROAD_TILE = 5000.0


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


def _loop_n(name, count, child, var="k"):
    loop = CadNode("for_loop", name, dict(variable=var, start=0.0,
                                          end=count - 1, step=1.0, values=""))
    loop.add(child)
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
    """Tarmac strips with a raised pavement strip on each side, a disc
    at every vertex so bends close, and a loop of centre dashes per
    street segment. Pavements lie BESIDE the tarmac, never under it,
    and a pavement tile standing on another road is left out, so a
    crossing is open tarmac — in OpenGL and in the software painter,
    which sorts whole faces and interleaved stacked slabs."""
    asphalt, pavement, dashes = [], [], []
    ribbons = []
    for r_i, road in enumerate(roads):
        width, walk, _ = road_style(road)
        for a, b in _segments(road):
            ribbons.append((r_i, (a[0], a[1], b[0], b[1], width / 2)))
    for r_i, road in enumerate(roads):
        width, walk, dashed = road_style(road)
        others = [rb for i, rb in ribbons if i != r_i]
        for a, b in _segments(road):
            length = math.hypot(b[0] - a[0], b[1] - a[1])
            ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
            ang = math.degrees(math.atan2(uy, ux))
            pieces = max(1, math.ceil(length / ROAD_TILE))
            piece = length / pieces
            asphalt.append(_place(_loop_n(
                "Tarmac tiles", pieces, _box(
                    "Tarmac", f"k * {_num(piece)}", -width / 2, 0.0, piece,
                    width, ROAD_THICKNESS)), a[0], a[1], ang))
            if walk > 0:
                for side, v in ((1, width / 2), (-1, -width / 2 - walk)):
                    off = side * (width / 2 + walk / 2)
                    keep = []
                    for k in range(pieces):
                        s_mid = (k + 0.5) * piece
                        cx = a[0] + ux * s_mid - uy * off
                        cy = a[1] + uy * s_mid + ux * off
                        if not others or _road_distance(cx, cy, others) > \
                                walk / 2:
                            keep.append(k * piece)
                    if not keep:
                        continue
                    values = ", ".join(_num(u) for u in keep)
                    loop = CadNode("for_loop", "Pavement tiles", dict(
                        variable="u", start=0.0, end=0.0, step=1.0,
                        values=values if len(keep) > 1 else f"[{values}]"))
                    loop.add(_box("Pavement", "u", v, 0.0, piece, walk,
                                  KERB))
                    pavement.append(_place(loop, a[0], a[1], ang))
            n = int(length // 6000)
            if dashed and n >= 1:
                dash = _box("Dash", "i * 6000 + 1500", -75.0, ROAD_THICKNESS,
                            3000.0, 150.0, 5.0)
                loop = CadNode("for_loop", "Centre line",
                               dict(variable="i", start=0.0, end=n - 1,
                                    step=1.0, values=""))
                loop.add(dash)
                dashes.append(_place(loop, a[0], a[1], ang))
        for x, y in [(_f(p[0]), _f(p[1])) for p in road.get("points") or []]:
            asphalt.append(CadNode("cylinder", "Bend", dict(
                x=x, y=y, z=0.0, height=ROAD_THICKNESS - 1.0,
                radius_bottom=width / 2, radius_top=width / 2, segments=16,
                center=False)))
    group = _group("Roads")
    if pavement:
        group.add(_color(_group("Pavements", pavement), PAVEMENT, "Stone"))
    group.add(_color(_group("Tarmac", asphalt), ASPHALT, "Concrete"))
    if dashes:
        group.add(_color(_group("Markings", dashes), DASH, "Matte"))
    return group


def along_roads(roads, spacing, offset_extra=0.0, phase=0.0):
    """Points on both pavements of every road, *spacing* apart and
    staggered side to side: (x, y, rz) with rz facing the road. A point
    that would stand on another road (a crossing) is left out."""
    out = []
    spacing = max(2000.0, float(spacing))
    ribbons = []
    for r_i, road in enumerate(roads):
        width, walk, _ = road_style(road)
        for a, b in _segments(road):
            ribbons.append((r_i, (a[0], a[1], b[0], b[1], width / 2 + walk)))
    for r_i, road in enumerate(roads):
        width, walk, _ = road_style(road)
        if walk <= 0:
            continue
        others = [rb for i, rb in ribbons if i != r_i]
        off = width / 2 + walk * 0.35 + offset_extra
        for a, b in _segments(road):
            length = math.hypot(b[0] - a[0], b[1] - a[1])
            ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
            ang = math.degrees(math.atan2(uy, ux))
            s, side = spacing * (0.5 + phase), 1
            while s < length - spacing * 0.25:
                nx, ny = -uy * side, ux * side
                x, y = a[0] + ux * s + nx * off, a[1] + uy * s + ny * off
                if not others or _road_distance(x, y, others) > 500.0:
                    out.append((x, y, ang - 90.0 if side > 0
                                else ang + 90.0))
                s += spacing / 2.0
                side = -side
    return out


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
            (lo, hi) = STYLES[style][0]
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
                (lo, hi) = STYLES[style][0]
                off = 3500 + 2500 + rng.uniform(2000, 5000)
                buildings.append(dict(style=style, x=x + w / 2,
                                      y=side * (off + 4500), w=w, d=8000,
                                      rz=0.0 if side < 0 else 180.0,
                                      floors=rng.randint(lo, hi)))
                if rng.random() < 0.5:
                    trees.append(dict(x=x + w / 2, y=side * (off + 14000),
                                      kind=rng.choice(list(TREE_KINDS)),
                                      height=rng.uniform(5000, 9000)))
                x += w + rng.uniform(3000, 9000)
        buildings.append(dict(style="church", name="Church", x=-18000,
                              y=22000, w=22000, d=11000, rz=180.0,
                              floors=2))
        for _ in range(12 * n):
            x, y = rng.uniform(-span, span), rng.choice((-1, 1)) * \
                rng.uniform(30000, 45000)
            trees.append(dict(x=x, y=y, kind=rng.choice(list(TREE_KINDS)),
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
                                      kind=rng.choice(list(TREE_KINDS)),
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


def _extent(spec):
    xs, ys = [], []
    for r in spec.get("roads") or []:
        for p in r.get("points") or []:
            xs.append(_f(p[0]))
            ys.append(_f(p[1]))
    for item in (spec.get("buildings") or []) + (spec.get("trees") or []):
        xs.append(_f(item.get("x")))
        ys.append(_f(item.get("y")))
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def resolve(spec: dict) -> dict:
    """*spec* with everything made explicit: a `layout` expanded into its
    roads, buildings and trees (the caller's own added on top), lights
    and street trees given as a spacing turned into positions, every
    building's defaults filled in. This is what is stored on the
    document and what the City Builder window edits piece by piece."""
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
    roads = [dict(r, points=[[_f(p[0]), _f(p[1])] for p in
                             r.get("points") or []])
             for r in spec.get("roads") or []]
    if len(spec.get("buildings") or []) > MAX_BUILDINGS:
        raise CityError(f"{len(spec['buildings'])} buildings — at most "
                        f"{MAX_BUILDINGS} in one build.")
    try:
        from .city_buildings import resolve as resolve_building
        buildings = [resolve_building(b, i) for i, b in
                     enumerate(spec.get("buildings") or [])]
    except BuildingError as exc:
        raise CityError(str(exc))
    lights = spec.get("lights")
    if isinstance(lights, dict):
        lights = [dict(x=x, y=y, rz=rz) for x, y, rz in
                  along_roads(roads, _f(lights.get("spacing"), 30000))]
    else:                 # {x, y, rz} dicts, or [x, y, rz] rows
        lights = [dict(x=_f(p.get("x")), y=_f(p.get("y")),
                       rz=_f(p.get("rz"))) if isinstance(p, dict) else
                  dict(x=_f(p[0]), y=_f(p[1]),
                       rz=_f(p[2]) if len(p) > 2 else 0.0)
                  for p in lights or []]
    trees = []
    for t in spec.get("trees") or []:
        kind = t.get("kind", "broadleaf")
        if kind not in TREE_KINDS:
            raise CityError(f'Unknown tree kind "{kind}"; use one of '
                            + ", ".join(TREE_KINDS))
        trees.append(dict(x=_f(t.get("x")), y=_f(t.get("y")),
                          z=_f(t.get("z")), rz=_f(t.get("rz")), kind=kind,
                          height=_f(t.get("height"), TREE_KINDS[kind])))
    st = spec.get("street_trees")
    if isinstance(st, dict):
        kind = st.get("kind", "round")
        kind = kind if kind in TREE_KINDS else "round"
        for x, y, rz in along_roads(roads, _f(st.get("spacing"), 30000),
                                    phase=0.5):
            trees.append(dict(x=x, y=y, z=KERB, rz=rz, kind=kind,
                              height=_f(st.get("height"), TREE_KINDS[kind])))
    ground = spec.get("ground", {"margin": 20000})
    if ground is not None:
        ground = dict(margin=_f(ground.get("margin"), 20000),
                      color=ground.get("color", GRASS))
    return dict(name=spec.get("name", "City"), roads=roads,
                buildings=buildings, lights=lights, trees=trees,
                ground=ground)


def _road_distance(x, y, ribbons):
    """(distance to the nearest road centre-line - its half width)."""
    best = float("inf")
    for (ax, ay, bx, by, half) in ribbons:
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((x - ax) * dx
                                                   + (y - ay) * dy) / l2))
        d = math.hypot(ax + t * dx - x, ay + t * dy - y) - half
        best = min(best, d)
    return best


def ground_tiles(spec):
    """The grass as square tiles that leave the roads out: TILE squares
    away from roads, refined to ROAD_TILE beside them, and none whose
    centre lies on a road. Grass under a road is never seen, and the
    software painter — sorting whole faces by centre — used to paint it
    over the tarmac. Returns ((size, [(x, y), ...]), ...)."""
    ext = _extent(spec)
    g = spec.get("ground")
    if not g or not ext:
        return ()
    m = g["margin"]
    x0, y0, x1, y1 = ext
    x0, y0 = TILE * math.floor((x0 - m) / TILE), TILE * math.floor(
        (y0 - m) / TILE)
    x1, y1 = x1 + m, y1 + m
    ribbons = []
    for road in spec.get("roads") or []:
        width, walk, _ = road_style(road)
        for a, b in _segments(road):
            ribbons.append((a[0], a[1], b[0], b[1], width / 2 + walk))
    big, small = [], []
    reach = TILE * 0.75
    y = y0
    while y < y1:
        x = x0
        while x < x1:
            cx, cy = x + TILE / 2, y + TILE / 2
            if ribbons and _road_distance(cx, cy, ribbons) < reach:
                n = int(round(TILE / ROAD_TILE))
                for i in range(n):
                    for j in range(n):
                        sx, sy = x + i * ROAD_TILE, y + j * ROAD_TILE
                        if _road_distance(sx + ROAD_TILE / 2,
                                          sy + ROAD_TILE / 2,
                                          ribbons) > -ROAD_TILE * 0.3:
                            small.append((sx, sy))
            else:
                big.append((x, y))
            x += TILE
        y += TILE
    return tuple((size, cells) for size, cells in ((TILE, big),
                                                   (ROAD_TILE, small))
                 if cells)


def build_ground(spec):
    tiles = ground_tiles(spec)
    if not tiles:
        return None
    parts = []
    for size, cells in tiles:
        values = ", ".join(f"[{_num(x)}, {_num(y)}]" for x, y in cells)
        if len(cells) == 1:
            values = f"[{values}]"
        loop = CadNode("for_loop", f"Grass {_num(size / 1000)} m", dict(
            variable="p", start=0.0, end=0.0, step=1.0, values=values))
        loop.add(_box("Tile", "p[0]", "p[1]", -200.0, size, size, 200.0))
        parts.append(loop)
    return _color(_group("Ground", parts), spec["ground"]["color"], "Matte",
                  name="Ground")


def build(spec: dict) -> dict:
    """The spec compiled to nodes: {object name: node}, plus counts and
    the resolved spec."""
    spec = resolve(spec)
    if not (spec["roads"] or spec["buildings"] or spec["trees"]):
        raise CityError("Nothing to build: give roads, buildings or trees, "
                        'or a layout ("village", "town", "city").')
    nodes = {}
    ground = build_ground(spec)
    if ground is not None:
        nodes["City ground"] = ground
    if spec["roads"]:
        nodes["City roads"] = build_roads(spec["roads"])
    if spec["buildings"]:
        g = _group("Buildings")
        for i, b in enumerate(spec["buildings"]):
            g.add(build_building(b, i))
        nodes["City buildings"] = g
    if spec["lights"]:
        nodes["Street lights"] = build_lights(
            [(p["x"], p["y"], p["rz"]) for p in spec["lights"]], KERB)
    if spec["trees"]:
        nodes["City trees"] = build_trees(spec["trees"])
    return dict(nodes=nodes, spec=spec, counts=dict(
        roads=len(spec["roads"]), buildings=len(spec["buildings"]),
        lights=len(spec["lights"]), trees=len(spec["trees"])),
        name=spec["name"])


def remove_built(model) -> int:
    names = set((model.city or {}).get("objects") or OBJECT_NAMES)
    gone = [c for c in list(model.root.children)
            if c.type == "component" and c.name in names]
    for comp in gone:
        model.root.remove(comp)
    return len(gone)


def apply(model, spec: dict, replace: bool = True) -> dict:
    """Insert the city as a few Objects and store the resolved design as
    ``model.city`` (saved in the .kcad, in the undo snapshots). With
    *replace* the Objects the last build made are removed first, so
    building again UPDATES the city. One call = one undo step."""
    result = build(spec)
    if replace:
        remove_built(model)
    inserted = []
    for name, node in result["nodes"].items():
        model.root.add(node)
        inserted.append(model.enclose_as_part(node, name=name))
    model.city = dict(result["spec"], objects=[c.name for c in inserted])
    model.structure_changed.emit()
    return dict(result, inserted=inserted)


def build_city(window, params: dict) -> dict:
    """The build_city MCP tool."""
    params = dict(params or {})
    replace = params.pop("replace", True)
    if params.pop("dry_run", False):
        r = build(params)
        return {"dry_run": True, "counts": r["counts"],
                "objects": list(r["nodes"])}
    r = apply(window.model, params, replace=replace)
    window.view3d.fit()
    panel = getattr(window, "_city_builder", None)
    if panel is not None:
        panel.load_from_document(force=True)
    return {"objects": [{"id": c.id, "name": c.name}
                        for c in r["inserted"]],
            "counts": r["counts"]}
