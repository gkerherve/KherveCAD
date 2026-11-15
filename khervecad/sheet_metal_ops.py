"""Sheet metal commands on the document (Qt-free): what the SHEET METAL
ribbon tab and the MCP `sheet_metal` tool both call, so a click and a
tool call are the same edit. After SolidCraft's commands: Base Flange,
Convert to Sheet Metal, Flange, Fold, Hem, Path Flange, Perforate,
Create Flat Pattern, Unfold / Refold, Sheet Metal Rules and the bend
table / DXF exports. Geometry is in sheet_body.py.

Rules are DOCUMENT VARIABLES (`smr_<Name>_t`, `_r`, `_k`, `_hem`):
applying one writes those names into the body's thickness, radius,
K-factor and hem gap, so the program stays plain parametric OpenSCAD
and editing the rule's variable changes every body that uses it.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
import re

from . import sheet_body

KIND = sheet_body.KIND
RULE_PREFIX = "smr_"
#: rule field -> (variable suffix, body parameter, default)
RULE_FIELDS = {"thickness": ("t", "thickness", 2.0),
               "bend_radius": ("r", "radius", 2.0),
               "k_factor": ("k", "k_factor", 0.44),
               "hem_gap": ("hem", "hem_gap", 1.0)}


def _env(model):
    from . import anchors
    return anchors.doc_env(model)


def find_body(node):
    """The sheet metal body at or inside *node* (or above it)."""
    if node is None:
        return None
    for n in node.walk():
        if n.type == KIND:
            return n
    p = node.parent
    while p is not None:
        if p.type == KIND:
            return p
        p = p.parent
    return None


def built(model, node):
    return sheet_body.build(node.params, _env(model))


def _rows(node, key):
    return [list(r) for r in node.params.get(key) or []
            if isinstance(r, list)]


def _set(model, node, key, value):
    """Set *key*, refused (and put back) when it makes the body fail."""
    before = list(built(model, node).errors)
    old = node.params.get(key)
    model.set_param(node, key, value)
    errors = [e for e in built(model, node).errors if e not in before]
    if errors:
        model.set_param(node, key, old)
        raise ValueError("Sheet metal: " + errors[0])


# ============================================================ create
def insert_base(model, outline=None, parent=None, name="Sheet metal",
                thickness=None, radius=None):
    """A new flat base flange (Base Flange/Tab), 100 x 60 by default."""
    params = {k: (list(map(list, v)) if isinstance(v, list) else v)
              for k, v in sheet_body._DEFAULTS.items()}
    if outline:
        params["outline"] = [[float(p[0]), float(p[1])] for p in outline]
    if thickness is not None:
        params["thickness"] = thickness
    if radius is not None:
        params["radius"] = radius
    return model.add_node(KIND, params, parent=parent, name=name)


def insert_contour(model, points, width, parent=None, name="Sheet metal"):
    """A body made from an open chain in the XZ plane (Flange, contour
    mode): one bend at every corner."""
    if len(points) < 2:
        raise ValueError("a contour needs two points or more")
    node = insert_base(model, parent=parent, name=name)
    model.set_param(node, "contour",
                    [[float(p[0]), float(p[1])] for p in points])
    model.set_param(node, "width", float(width))
    return node


def arch_outline(width, below, step=5.0):
    """The outline of an arch plate: *width* wide, a half circle of
    radius width / 2 on top (its centre at the origin) over *below* mm of
    straight sides — a bracket's back plate. Points run counter-clockwise
    from the bottom left; the arch is faceted every *step* degrees."""
    r = width / 2.0
    pts = [[-r, -below], [r, -below], [r, 0.0]]
    a = step
    while a < 180.0 - 1e-9:
        pts.append([round(r * math.cos(math.radians(a)), 4),
                    round(r * math.sin(math.radians(a)), 4)])
        a += step
    pts.append([-r, 0.0])
    return pts


def outline_of(node, env=None):
    """A sketch shape's outline in its own frame: rect, polygon, circle
    (as 24 sides) — what Base Flange and Convert read."""
    from . import mesh
    env = env or {}
    p = node.params
    if node.type == "rect":
        x, y = mesh.rv(p.get("x", 0), env), mesh.rv(p.get("y", 0), env)
        w = mesh.rv(p.get("width", 10), env)
        h = mesh.rv(p.get("height", 10), env)
        if p.get("center"):
            x, y = x - w / 2, y - h / 2
        return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
    if node.type == "polygon":
        x, y = mesh.rv(p.get("x", 0), env), mesh.rv(p.get("y", 0), env)
        return [[x + mesh.rv(q[0], env), y + mesh.rv(q[1], env)]
                for q in p.get("points") or []]
    if node.type == "circle":
        x, y = mesh.rv(p.get("x", 0), env), mesh.rv(p.get("y", 0), env)
        r = mesh.rv(p.get("radius", 5), env)
        return [[x + r * math.cos(2 * math.pi * i / 24),
                 y + r * math.sin(2 * math.pi * i / 24)] for i in range(24)]
    return None


def convert(model, node):
    """Convert to Sheet Metal: a cube (its thinnest side the thickness,
    turned so that side is up), a linear extrude of one rect / polygon /
    circle, or an old four-flange sheet metal part becomes a body in its
    place. Returns the body."""
    env = _env(model)
    from . import mesh
    parent = node.parent
    index = parent.children.index(node)
    rot = None
    if node.type == "cube":
        # a Cube's sides are width / depth / height (an older "size"
        # is still read): reading only "size" made every plate a
        # 10 mm cube
        size = node.params.get("size")
        if size is None:
            size = [node.params.get(k, 20.0)
                    for k in ("width", "depth", "height")]
        elif not isinstance(size, list):
            size = [size] * 3
        sx, sy, sz = (mesh.rv(v, env, 10.0) for v in size)
        place = [node.params.get(k, 0.0) for k in ("x", "y", "z")]
        dims = [sx, sy, sz]
        thin = dims.index(min(dims))
        if thin == 2:
            w, d, t = sx, sy, sz
        elif thin == 1:                    # thin along y: stand it up
            w, d, t, rot = sx, sz, sy, [90.0, 0.0, 0.0]
        else:                              # thin along x
            w, d, t, rot = sz, sy, sx, [0.0, -90.0, 0.0]
        outline = [[0, 0], [w, 0], [w, d], [0, d]]
        # turned up on edge, the sheet's thickness runs the other way:
        # start it a thickness back so it stays where the cube was
        shift = -t if rot else 0.0
        if node.params.get("center"):
            outline = [[x - w / 2, y - d / 2] for x, y in outline]
            shift = -t / 2
        body = insert_base(model, outline, parent=parent, name=node.name,
                           thickness=round(t, 6))
    elif node.type == "linear_extrude":
        shapes = [c for c in node.children if outline_of(c, env)]
        if len(shapes) != 1:
            raise ValueError("Convert to Sheet Metal: the extrude must "
                             "hold one rectangle, polygon or circle")
        t = mesh.rv(node.params.get("height", 2.0), env, 2.0)
        body = insert_base(model, outline_of(shapes[0], env), parent=parent,
                           name=node.name, thickness=round(t, 6))
        shift = -t / 2 if node.params.get("center") else 0.0
    elif node.type == "sheet_metal":
        body = _from_old(model, node, parent, env)
        shift = 0.0
    else:
        raise ValueError(f"Convert to Sheet Metal takes a plate (a cube, "
                         f"an extruded sketch shape) — not a {node.type}")
    model.move_node(body, parent, index)
    inner = body
    where = place if node.type == "cube" and any(
        isinstance(v, str) or abs(v) > 1e-12 for v in place) else None
    for kind, vec in (("translate", [0.0, 0.0, shift] if shift else None),
                      ("rotate", rot), ("translate", where)):
        if vec is None:
            continue
        holder = model.add_node(kind, dict(x=vec[0], y=vec[1], z=vec[2]),
                                parent=parent, name="Place")
        model.move_node(holder, parent, index)
        model.move_node(inner, holder)
        inner = holder
    model.remove_node(node)
    return body


def _from_old(model, node, parent, env):
    """The old four-flange part (sheetmetal.py) as a body: the plate is
    the outline, each flange's outer length its height."""
    from . import mesh
    p = node.params

    def v(key, default):
        return mesh.rv(p.get(key, default), env, default)
    w, d = v("width", 80.0), v("depth", 60.0)
    body = insert_base(model, [[0, 0], [w, 0], [w, d], [0, d]],
                       parent=parent, name=node.name,
                       thickness=p.get("thickness", 1.5),
                       radius=p.get("radius", 1.5))
    model.set_param(body, "k_factor", p.get("kfactor", 0.44))
    flanges = []
    for key, edge in (("s", 0), ("e", 1), ("n", 2), ("w", 3)):
        length = v(f"{key}_length", 0.0)
        if length > 0:
            flanges.append([0, edge, length, v(f"{key}_angle", 90.0),
                            0, 0, 0])
    model.set_param(body, "flanges", flanges)
    return body


# ============================================================ edit
def add_flange(model, node, panel, edge, height, angle=90.0, radius=0.0,
               inset_a=0.0, inset_b=0.0, then=()):
    """A flange on (panel, edge); *then* = [(height, angle), ...] more
    flanges chained on each new one's far edge. Returns the panel
    numbers made."""
    rows = _rows(node, "flanges")
    made = []
    body = built(model, node)
    first = len(body.panels)
    rows.append([int(panel), edge if isinstance(edge, str) else int(edge),
                 float(height), float(angle), float(radius),
                 float(inset_a), float(inset_b)])
    made.append(first)
    for k, (h, a) in enumerate(then):
        rows.append([first + k, 2, float(h), float(a), float(radius), 0, 0])
        made.append(first + k + 1)
    _set(model, node, "flanges", rows)
    return made


def add_ear(model, node, panel, edge, center, width, height, angle=90.0,
            radius=0.0, hole=0.0, from_end=False):
    """Edge Flange with an edited profile, the common one: an ear — a
    strip *width* wide centred *center* mm along the edge (from its
    start), *height* to the outside, its far end a full round, with an
    optional hole of diameter *hole* at the centre of that round. Returns
    the ear's panel number."""
    body = built(model, node)
    pan = body.panels[panel] if 0 <= panel < len(body.panels) else None
    if pan is None or pan.edge(edge) is None:
        raise ValueError(f"panel {panel} has no edge {edge}")
    # the edge as it stands once the other bends have set it back:
    # measure it with a provisional ear (which notches, not trims)
    trial = dict(node.params)
    trial["flanges"] = _rows(node, "flanges") + [
        [int(panel), int(edge), float(height), float(angle),
         float(radius), 0.0, 0.0, 1]]
    after = sheet_body.build(trial, _env(model))
    held = after.panels[panel].edge(edge) if after.panels[panel] else None
    ln = held[2] if held else pan.edge(edge)[2]
    if from_end:
        center = ln - center
    lo, hi = center - width / 2.0, center + width / 2.0
    if lo < -1e-9 or hi > ln + 1e-9:
        raise ValueError(f"Ear: it runs off the edge ({ln:.2f} mm long)")
    rows = _rows(node, "flanges")
    index = len(body.panels)
    rows.append([int(panel), int(edge), float(height), float(angle),
                 float(radius), round(lo, 6), round(ln - hi, 6), 1])
    _set(model, node, "flanges", rows)
    if hole > 0:
        r = radius or sheet_body._num(node.params.get("radius", 2.0),
                                      _env(model), 2.0)
        leg = height - (r + body.t) * math.tan(math.radians(angle) / 2)
        add_panel_hole(model, node, index, -center, leg - width / 2.0, hole)
    return index


def add_hem(model, node, panel, edge, length, flip=False):
    rows = _rows(node, "hems")
    rows.append([int(panel), int(edge), float(length), 1 if flip else 0])
    _set(model, node, "hems", rows)


def add_fold(model, node, p1, p2, angle=90.0, radius=0.0):
    rows = _rows(node, "folds")
    rows.append([float(p1[0]), float(p1[1]), float(p2[0]), float(p2[1]),
                 float(angle), float(radius)])
    try:
        _set(model, node, "folds", rows)
    except ValueError:
        if _rows(node, "flanges") or _rows(node, "hems"):
            # (it read "flange 1: panel 0 has no edge 1")
            raise ValueError(
                "Fold: this sheet already has flanges or hems, and a fold "
                "changes the edges they sit on. Fold the flat sheet first, "
                "then add the flanges (Ctrl+Z takes them back).")
        raise


def jog_row(p1, p2, offset=20.0, angle=60.0, radius=0.0, dim=0, pos=3,
            side=-1, direction=1):
    """One row of the body's `jogs` (see sheet_jog)."""
    return [float(p1[0]), float(p1[1]), float(p2[0]), float(p2[1]),
            float(offset), float(angle), float(radius), int(dim), int(pos),
            1 if side >= 0 else -1, 1 if direction >= 0 else -1]


def add_jog(model, node, p1, p2, offset=20.0, angle=60.0, radius=0.0,
            dim=0, pos=3, side=-1, direction=1):
    """Jog: two opposite bends from the line p1-p2 across the base; the
    *side* of the line (1 left, -1 right of p1 -> p2) stays fixed."""
    rows = _rows(node, "jogs")
    rows.append(jog_row(p1, p2, offset, angle, radius, dim, pos, side,
                        direction))
    _set(model, node, "jogs", rows)
    return len(rows) - 1


def set_jog(model, node, index, row):
    rows = _rows(node, "jogs")
    if not 0 <= index < len(rows):
        raise ValueError(f"no jog {index}")
    rows[index] = [float(v) for v in row]
    _set(model, node, "jogs", rows)


def add_hole(model, node, x, y, diameter):
    """A hole in the flat plate (Simple Hole / Cut-Extrude): it follows
    its panel through any jog."""
    if diameter <= 0:
        raise ValueError("Hole: the diameter must be more than 0")
    rows = _rows(node, "holes")
    rows.append([float(x), float(y), float(diameter)])
    _set(model, node, "holes", rows)


def add_slot(model, node, p1, p2, width):
    if width <= 0:
        raise ValueError("Slot: the width must be more than 0")
    rows = _rows(node, "slots")
    rows.append([float(p1[0]), float(p1[1]), float(p2[0]), float(p2[1]),
                 float(width)])
    _set(model, node, "slots", rows)


def path_flange(model, node, panel, edge, path):
    """Path Flange: flanges along a chain drawn across an edge — *path*
    = [(length, angle), ...], one bend per corner."""
    path = list(path)
    if not path:
        raise ValueError("Path Flange: give at least one segment")
    (h, a), rest = path[0], path[1:]
    return add_flange(model, node, panel, edge, h, a, then=rest)


def perforate(model, node, diameter, pitch, margin=0.0, square=False):
    if diameter <= 0 or pitch <= diameter:
        raise ValueError("Perforate: the pitch must be more than the "
                         "diameter")
    _set(model, node, "perforate",
         [[float(diameter), float(pitch), float(margin), 1 if square else 0]]
         if diameter else [])


def edge_position(model, node, panel, edge, along, across):
    """A spot in a panel's own (u, v) given from one of its edges:
    *along* mm from the edge's start toward its end, *across* mm
    inward from the edge (how a drawing dimensions a hole)."""
    body = built(model, node)
    pan = body.panels[panel] if 0 <= panel < len(body.panels) else None
    found = pan.edge(edge) if pan is not None else None
    if found is None:
        raise ValueError(f"panel {panel} has no edge {edge}")
    a, b, ln = found
    d = ((b[0] - a[0]) / ln, (b[1] - a[1]) / ln)
    inward = (-d[1], d[0])                 # polygons run CCW: inside = left
    return (a[0] + d[0] * along + inward[0] * across,
            a[1] + d[1] * along + inward[1] * across)


def add_panel_hole(model, node, panel, u, v, diameter):
    """Simple Hole: a round hole through *panel* at (u, v) of its own
    frame — cut in the folded part and in the flat pattern."""
    if diameter <= 0:
        raise ValueError("Hole: the diameter must be more than 0")
    rows = _rows(node, "pholes")
    rows.append([int(panel), round(float(u), 6), round(float(v), 6),
                 float(diameter)])
    _set(model, node, "pholes", rows)
    return len(rows) - 1


def add_tab(model, node, panel, u, v, width, length, angle=90.0, hole=0.0):
    """Base Flange/Tab: a round-ended strip *width* wide merged into
    *panel* — its round end centred at (u, v), running *length* mm toward
    *angle* degrees (0 = +U), with an optional hole of diameter *hole* at
    the centre of the round end. Material the panel already lacks (an
    opening) stays open around it."""
    if width <= 0 or length <= 0:
        raise ValueError("Tab: width and length must be more than 0")
    rows = _rows(node, "tabs")
    rows.append([int(panel), round(float(u), 6), round(float(v), 6),
                 float(width), float(length), float(angle), float(hole)])
    _set(model, node, "tabs", rows)
    return len(rows) - 1


def jog_span(model, node, panel, p1, p2, margin=0.5):
    """The sketched jog line p1 -> p2 stretched to the whole run it makes
    across the material of *panel* (the part of the line inside the
    sheet nearest their midpoint) plus *margin* mm of air each side — so
    two clicks on a tab give a line that really crosses it."""
    from . import csg
    body = built(model, node)
    pan = body.panels[panel] if 0 <= panel < len(body.panels) else None
    if pan is None or not csg.available():
        return p1, p2
    length = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    if length < 1e-9:
        raise ValueError("Jog: the line has no length")
    d = ((p2[0] - p1[0]) / length, (p2[1] - p1[1]) / length)
    m = csg._m
    far = 1e4
    quad = [(p1[0] - d[0] * far - d[1] * 1e-3, p1[1] - d[1] * far + d[0] * 1e-3),
            (p1[0] + d[0] * far - d[1] * 1e-3, p1[1] + d[1] * far + d[0] * 1e-3),
            (p1[0] + d[0] * far + d[1] * 1e-3, p1[1] + d[1] * far - d[0] * 1e-3),
            (p1[0] - d[0] * far + d[1] * 1e-3, p1[1] - d[1] * far - d[0] * 1e-3)]
    strip = m.CrossSection([[list(q) for q in sheet_body._ccw(quad)]],
                           m.FillRule.Positive)
    cross = sheet_body.panel_region(pan) ^ strip
    mid = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
    mid_t = 0.0
    best = None
    for part in cross.decompose():
        ts = [(q[0] - p1[0]) * d[0] + (q[1] - p1[1]) * d[1]
              for lp in part.to_polygons() for q in lp]
        if not ts:
            continue
        lo, hi = min(ts), max(ts)
        dist = 0.0 if lo <= mid_t + length / 2 <= hi else min(
            abs(lo - length / 2), abs(hi - length / 2))
        if best is None or dist < best[0]:
            best = (dist, lo, hi)
    if best is None:
        raise ValueError("Jog: that line crosses no material of the panel")
    lo, hi = best[1] - margin, best[2] + margin
    return ((p1[0] + d[0] * lo, p1[1] + d[1] * lo),
            (p1[0] + d[0] * hi, p1[1] + d[1] * hi))


def add_tab_jog(model, node, panel, p1, p2, offset=10.0, angle=90.0,
            radius=0.0, fixed=None, extend=False):
    """Jog: two bends along the line p1 -> p2 (the panel's own frame)
    step what lies beyond it *offset* mm out of the plane — up when
    *angle* is positive, down when negative; the piece holding *fixed*
    (else the biggest) stays. *extend* stretches the line across the
    material it crosses first (jog_span). Returns the jog's number."""
    if extend:
        p1, p2 = jog_span(model, node, panel, p1, p2)
    if angle < 0:
        offset = -abs(offset)
    else:
        offset = abs(offset)
    fx, fy = fixed if fixed else (1e6, 1e6)
    rows = _rows(node, "tabjogs")
    rows.append([int(panel), round(p1[0], 6), round(p1[1], 6),
                 round(p2[0], 6), round(p2[1], 6), float(offset),
                 float(angle), float(radius), fx, fy])
    _set(model, node, "tabjogs", rows)
    return len(rows) - 1


def add_gusset(model, node, bend, offset, d1=10.0, d2=10.0, width=7.5,
               draft=20.0):
    """Sheet Metal Gusset: a stamped rib across the inside of bend number
    *bend* (as numbered in the bend table, from 1), its centre *offset* mm
    along the bend from its start, rising *d1* up the first face and *d2*
    up the second, *width* across at the corner, its sides drafted
    *draft* degrees. Returns the gusset's number."""
    built_body = built(model, node)
    if not 1 <= int(bend) <= len(built_body.bends):
        raise ValueError(f"Gusset: bend {bend} does not exist "
                         f"({len(built_body.bends)} bends)")
    rows = _rows(node, "gussets")
    rows.append([int(bend) - 1, round(float(offset), 6), float(d1),
                 float(d2), float(width), float(draft)])
    _set(model, node, "gussets", rows)
    return len(rows) - 1


def nearest_bend(model, node, point, matrix=None):
    """The number (from 1) and the distance along it of the bend whose
    line lies nearest *point* (world; *matrix* takes the body's frame to
    world)."""
    from . import mesh
    body = built(model, node)
    best = None
    for i, b in enumerate(body.bends):
        a0 = b["a"]
        a1 = sheet_body._add(a0, sheet_body._mul(b["e"], b["span"]))
        if matrix:
            a0, a1 = mesh.mat_apply(matrix, a0), mesh.mat_apply(matrix, a1)
        seg = [a1[k] - a0[k] for k in range(3)]
        ln2 = sum(c * c for c in seg) or 1.0
        t = max(0.0, min(1.0, sum((point[k] - a0[k]) * seg[k]
                                  for k in range(3)) / ln2))
        q = [a0[k] + seg[k] * t for k in range(3)]
        dist = sum((point[k] - q[k]) ** 2 for k in range(3))
        if best is None or dist < best[0]:
            best = (dist, i + 1, t * b["span"])
    if best is None:
        raise ValueError("Gusset: this body has no bend")
    return best[1], best[2]


def add_corner(model, node, panel, u, v, size, chamfer=False):
    """Break Corner: round (or chamfer) the convex corner of *panel*
    nearest (u, v) by *size* mm — in the folded part and the flat
    pattern."""
    if size <= 0:
        raise ValueError("Break Corner: the size must be more than 0")
    rows = _rows(node, "corners")
    rows.append([int(panel), round(float(u), 6), round(float(v), 6),
                 float(size), 1 if chamfer else 0])
    _set(model, node, "corners", rows)
    return len(rows) - 1


def locate(model, node, point, matrix=None):
    """(panel, u, v) of the face under *point* (world; *matrix* takes the
    body's frame to world): the panel whose slab holds it, else the
    nearest one."""
    import numpy as np
    from . import mesh
    body = built(model, node)
    best = None
    for i, pan in enumerate(body.panels):
        if pan is None:
            continue
        f = pan.frame
        pts = [f.at((0.0, 0.0), 0.0), f.at((1.0, 0.0), 0.0),
               f.at((0.0, 1.0), 0.0), f.at((0.0, 0.0), 1.0)]
        if matrix:
            pts = [mesh.mat_apply(matrix, q) for q in pts]
        o = np.array(pts[0])
        basis = np.array([np.array(q) - o for q in pts[1:]]).T
        try:
            a, b, c = np.linalg.solve(basis, np.array(point) - o)
        except np.linalg.LinAlgError:
            continue
        inside = sheet_body._inside([pan.poly], a, b)
        # c is the height over the panel's bottom in thickness units
        off = abs(c * body.t - body.t / 2) - body.t / 2
        score = max(off, 0.0) + (0.0 if inside else 1e3)
        if best is None or score < best[0]:
            best = (score, i, float(a), float(b))
    if best is None:
        raise ValueError("Hole: this body has no panel")
    return best[1], best[2], best[3]


def set_flat(model, node, flat=True):
    """Unfold (flat = True) / Refold (False) — the same body, shown as
    its flat pattern or folded."""
    _set(model, node, "flat", bool(flat))


def remove(model, node, what, index):
    """Drop row *index* of flanges / hems / folds / perforate / holes /
    corners / tabs / jogs / gussets."""
    rows = _rows(node, what)
    if not 0 <= index < len(rows):
        raise ValueError(f"no {what} row {index}")
    rows.pop(index)
    _set(model, node, what, rows)


def pattern(model, node):
    env = _env(model)
    body = sheet_body.build(node.params, env)
    perf = None
    for row in node.params.get("perforate") or []:
        if isinstance(row, list) and len(row) >= 2:
            perf = [sheet_body._num(v, env, 0.0) for v in row]
    return sheet_body.flat_pattern(body, perf)


def flat_pattern_part(model, node, gap=20.0):
    """Create Flat Pattern: a flat copy of the body beside it (its own
    Object), which keeps following nothing — the body stays folded."""
    from . import document
    data = document.node_to_dict(node)
    data["params"]["flat"] = True
    copy = document.node_from_dict(data)
    copy.name = f"{node.name} flat pattern"
    model.root.add(copy)
    model.structure_changed.emit()
    comp = model.enclose_as_part(copy, f"{node.name} flat pattern")
    pat = pattern(model, node)
    model.set_param(comp, "y", round(-pat["height"] - gap, 3))
    return comp, pat


# ============================================================ edges
def edge_list(model, node):
    """Every edge a flange or hem can go on: (panel, edge, length,
    world-free midpoint in the body's frame, label)."""
    body = built(model, node)
    out = []
    for i, panel in enumerate(body.panels):
        if panel is None:
            continue
        n = len(panel.poly)
        seen = set()
        for j in range(n):
            tag = panel.tags[j]
            if tag in seen or isinstance(tag, str):
                continue
            seen.add(tag)
            found = panel.edge(tag)
            if found is None:
                continue
            a, b, ln = found
            mids = [panel.frame.at(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2),
                                   d) for d in (0.0, body.t)]
            what = "base" if i == 0 else f"flange {i}"
            if i and tag in (1, 3):
                name = "side"
            elif i and tag == 2:
                name = "far edge"
            elif i:
                name = "bend"
            else:
                name = f"edge {tag}"
            out.append(dict(panel=i, edge=tag, length=round(ln, 3),
                            mids=mids,
                            label=f"{what} · {name} ({ln:.1f} mm)"))
    return out


def nearest_edge(model, node, point, matrix=None):
    """The (panel, edge) whose line lies nearest *point* (world, through
    the body's *matrix* to world)."""
    from . import mesh
    best = None
    for item in edge_list(model, node):
        for m in item["mids"]:
            q = mesh.mat_apply(matrix, m) if matrix else m
            d = sum((q[k] - point[k]) ** 2 for k in range(3))
            if best is None or d < best[0]:
                best = (d, item)
    return best[1] if best else None


# ============================================================ rules
_NAME = re.compile(r"[^A-Za-z0-9_]+")


def rule_slug(name):
    slug = _NAME.sub("_", str(name).strip()).strip("_")
    if not slug:
        raise ValueError("a rule needs a name")
    if slug[0].isdigit():
        slug = "R" + slug
    return slug


def rules(model):
    """{rule name: {field: value}} from the document's smr_ variables."""
    out = {}
    for node in model.global_assigns():
        var = str(node.params.get("variable", ""))
        if not var.startswith(RULE_PREFIX):
            continue
        for field, (suffix, _p, _d) in RULE_FIELDS.items():
            if var.endswith("_" + suffix):
                name = var[len(RULE_PREFIX):-len(suffix) - 1]
                if name:
                    out.setdefault(name, {})[field] = node.params.get(
                        "value")
    return out


def set_rule(model, name, **values):
    """Create or edit a rule: its document variables (missing fields
    take the defaults on creation)."""
    from .model import CadNode
    from .equalize import _first_index
    slug = rule_slug(name)
    have = {str(n.params.get("variable")): n for n in model.global_assigns()}
    for field, (suffix, _p, default) in RULE_FIELDS.items():
        var = f"{RULE_PREFIX}{slug}_{suffix}"
        value = values.get(field)
        if var in have:
            if value is not None:
                model.set_param(have[var], "value", value)
        else:
            node = CadNode("assign", var, dict(
                variable=var, value=default if value is None else value))
            model.root.add(node, _first_index(model))
    model.structure_changed.emit()
    return slug


def delete_rule(model, name):
    slug = rule_slug(name)
    gone = [n for n in model.global_assigns()
            if str(n.params.get("variable", "")).startswith(
                f"{RULE_PREFIX}{slug}_")]
    env = _env(model)
    for node in model.root.walk():
        if node.type == KIND and node.params.get("rule") == slug:
            for field, (suffix, param, _d) in RULE_FIELDS.items():
                model.set_param(node, param, env.get(
                    f"{RULE_PREFIX}{slug}_{suffix}",
                    sheet_body._DEFAULTS[param]))
            model.set_param(node, "rule", "")
    for n in gone:
        n.parent.remove(n)
    model.structure_changed.emit()


def apply_rule(model, node, name):
    """The body takes the rule: its thickness, radius, K-factor and hem
    gap become the rule's variables."""
    slug = rule_slug(name)
    if slug not in rules(model):
        raise ValueError(f"no sheet metal rule {name!r}")
    for field, (suffix, param, _d) in RULE_FIELDS.items():
        model.set_param(node, param, f"{RULE_PREFIX}{slug}_{suffix}")
    model.set_param(node, "rule", slug)


def _features(model, node):
    from . import sheet_metal_patterns
    return sheet_metal_patterns.features(model, node)


def describe(model, node):
    """A short report of a body: panels, bends, flat size, errors."""
    body = built(model, node)
    pat = pattern(model, node)
    return dict(
        id=node.id, name=node.name, thickness=round(body.t, 4),
        k_factor=round(body.k, 4), rule=node.params.get("rule", ""),
        flat=bool(node.params.get("flat")),
        panels=sum(1 for p in body.panels if p is not None),
        bends=len(body.bends), errors=body.errors,
        cut_holes=len(node.params.get("pholes") or []),
        corners=len(node.params.get("corners") or []),
        tabs=len(node.params.get("tabs") or []),
        tab_jogs=len(node.params.get("tabjogs") or []),
        gussets=len(node.params.get("gussets") or []),
        features=_features(model, node),
        flat_size=[round(pat["width"], 3), round(pat["height"], 3)],
        holes=len(pat["holes"]), cut_outs=len(pat.get("cuts") or []),
        bend_table=[{k: v for k, v in b.items() if k != "line"}
                    for b in pat["bend_table"]],
        edges=[{k: v for k, v in e.items() if k != "mids"}
               for e in edge_list(model, node)])
