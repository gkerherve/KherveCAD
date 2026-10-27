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
        size = node.params.get("size", [10, 10, 10])
        if not isinstance(size, list):
            size = [size] * 3
        sx, sy, sz = (mesh.rv(v, env, 10.0) for v in size)
        dims = [sx, sy, sz]
        thin = dims.index(min(dims))
        if thin == 2:
            w, d, t = sx, sy, sz
        elif thin == 1:                    # thin along y: stand it up
            w, d, t, rot = sx, sz, sy, [90.0, 0.0, 0.0]
        else:                              # thin along x
            w, d, t, rot = sz, sy, sx, [0.0, -90.0, 0.0]
        outline = [[0, 0], [w, 0], [w, d], [0, d]]
        shift = 0.0
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
    for kind, vec in (("translate", [0.0, 0.0, shift] if shift else None),
                      ("rotate", rot)):
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


def add_hem(model, node, panel, edge, length, flip=False):
    rows = _rows(node, "hems")
    rows.append([int(panel), int(edge), float(length), 1 if flip else 0])
    _set(model, node, "hems", rows)


def add_fold(model, node, p1, p2, angle=90.0, radius=0.0):
    rows = _rows(node, "folds")
    rows.append([float(p1[0]), float(p1[1]), float(p2[0]), float(p2[1]),
                 float(angle), float(radius)])
    _set(model, node, "folds", rows)


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


def set_flat(model, node, flat=True):
    """Unfold (flat = True) / Refold (False) — the same body, shown as
    its flat pattern or folded."""
    _set(model, node, "flat", bool(flat))


def remove(model, node, what, index):
    """Drop row *index* of flanges / hems / folds / perforate."""
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
        flat_size=[round(pat["width"], 3), round(pat["height"], 3)],
        holes=len(pat["holes"]),
        bend_table=[{k: v for k, v in b.items() if k != "line"}
                    for b in pat["bend_table"]],
        edges=[{k: v for k, v in e.items() if k != "mids"}
               for e in edge_list(model, node)])
