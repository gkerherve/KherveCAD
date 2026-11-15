"""SolidWorks' **Fill Pattern** (2026-11-15, the user, from the "Deform
feature" video: "build a real Fill Pattern tool: pick a face, a layout,
spacing, margin, direction, seed cut").

Click a flat face: its outline, held in by the MARGIN, is filled with
copies of a seed cut — a square, circle, diamond or polygon — laid out
as concentric LOOPS (Circular), a GRID (Square) or staggered rows
(Perforation), turned to a DIRECTION (a sketch line, or an angle). The
whole fill is ONE feature: a Group "Fill Pattern" cut by a Difference
round the part, holding `translate · rotate · linear_extrude · polygon`
— one polygon with a path per instance, so the program is plain
OpenSCAD and the counts are real. The settings ride on the Group as
`params["fill_pattern"]`; the face is found again on the part as it is
now, so a resized part refills.

The Circular rule was read off the video's 181 squares (a Ø80 face,
loop and instance spacing 5, margin 1, 2 mm squares): the centre one,
then a loop every `loop_spacing` mm holding the next EVEN number of
instances that keeps the arc between neighbours within `spacing` — 6,
14, 20, 26, 32, 38, 44 — the first loop a hexagon; the first instance
of every loop lies along the direction, and an instance stays only
where its seed is wholly inside the face held in by the margin.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

KEY = "fill_pattern"
LAYOUTS = [("circular", "Circular"), ("square", "Square"),
           ("perforation", "Perforation")]
SHAPES = [("square", "Square"), ("circle", "Circle"),
          ("diamond", "Diamond"), ("polygon", "Polygon")]
MAX_INSTANCES = 4000
EXTRA = 0.5                  # the cutter starts this far above the face
DEFAULT = dict(layout="circular", loop_spacing=5.0, spacing=5.0,
               margin=1.0, shape="square", size=2.0, rotation=0.0,
               sides=6, angle=0.0, direction=None, reverse=False,
               end="Through all", depth=5.0, face=None)


def spec_of(spec=None):
    return dict(DEFAULT, **(spec or {}))


# ----------------------------------------------------------- layouts
def loop_count(radius, spacing):
    """Instances on a loop of *radius*: the next even number keeping the
    arc between neighbours within *spacing*; the first loop (a ring one
    spacing out) is the hexagon."""
    if radius <= spacing * 1.0001:
        return 6
    n = int(math.ceil(2 * math.pi * radius / spacing - 1e-9))
    return n + (n % 2)


def candidates(spec, reach):
    """Instance centres (u, v) about the layout centre, within *reach*,
    for the layout, before the face and margin choose."""
    spec = spec_of(spec)
    ls = max(float(spec["loop_spacing"]), 1e-3)
    sp = max(float(spec["spacing"]), 1e-3)
    out = []
    if spec["layout"] == "circular":
        out.append((0.0, 0.0))
        k = 1
        while k * ls <= reach and len(out) < MAX_INSTANCES:
            r = k * ls
            n = loop_count(r, sp)
            for j in range(n):
                # the first instance lies along +v (turned by the
                # direction later)
                a = math.pi / 2 + 2 * math.pi * j / n
                out.append((r * math.cos(a), r * math.sin(a)))
            k += 1
        return out
    # grid / staggered rows: i along the direction, j across
    nj = int(reach / ls) + 1
    ni = int(reach / sp) + 1
    for j in range(-nj, nj + 1):
        shift = 0.5 * sp if (spec["layout"] == "perforation" and j % 2) \
            else 0.0
        for i in range(-ni - 1, ni + 2):
            u, v = (i * sp + shift), j * ls
            if math.hypot(u, v) <= reach:
                out.append((v, u))
    return out[:MAX_INSTANCES]


def seed_loop(spec, turn=0.0):
    """The seed cut as a closed loop about its centre, in mm."""
    spec = spec_of(spec)
    s = float(spec["size"])
    shape = spec["shape"]
    a0 = math.radians(float(spec["rotation"]) + turn)
    if shape == "circle":
        pts = [(s / 2 * math.cos(2 * math.pi * k / 24),
                s / 2 * math.sin(2 * math.pi * k / 24)) for k in range(24)]
        return pts
    if shape == "polygon":
        n = max(3, int(spec["sides"]))
        base = [(s / 2 * math.cos(2 * math.pi * k / n),
                 s / 2 * math.sin(2 * math.pi * k / n)) for k in range(n)]
    elif shape == "diamond":
        h = s / 2
        base = [(h, 0.0), (0.0, h), (-h, 0.0), (0.0, -h)]
    else:
        h = s / 2
        base = [(h, h), (-h, h), (-h, -h), (h, -h)]
    c, sn = math.cos(a0), math.sin(a0)
    return [(x * c - y * sn, x * sn + y * c) for x, y in base]


# -------------------------------------------------------------- faces
def _norm(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return [c / n for c in v]


def basis(normal):
    """(ry, rz, ex, ey, n) of `rotate([0, ry, rz])` taking +Z onto
    *normal*: its local x / y axes are the face's u / v."""
    from . import hole_wizard
    ry, rz = hole_wizard._turn(normal)
    cy, sy = math.cos(math.radians(ry)), math.sin(math.radians(ry))
    cz, sz = math.cos(math.radians(rz)), math.sin(math.radians(rz))
    # Rz(rz) · Ry(ry)
    ex = [cz * cy, sz * cy, -sy]
    ey = [-sz, cz, 0.0]
    n = [cz * sy, sz * sy, cy]
    return ry, rz, ex, ey, n


def face_region(tris, seed, normal, tol=1e-3):
    """The flat face of *tris* (3-point triangles) facing *normal*
    nearest *seed*: its triangles grown over coplanar neighbours."""
    from . import anchors
    n = _norm(normal)
    cands = [t for t in tris if sum(anchors._tri_normal(t)[i] * n[i]
                                    for i in range(3)) > 0.999]
    if not cands:
        return []

    def dist(t):
        c = [(t[0][i] + t[1][i] + t[2][i]) / 3.0 for i in range(3)]
        off = sum((seed[i] - t[0][i]) * n[i] for i in range(3))
        return abs(off) * 10.0 + math.dist(c, seed)
    start = min(cands, key=dist)
    plane = sum(start[0][i] * n[i] for i in range(3))
    flat = [t for t in cands
            if abs(sum(t[0][i] * n[i] for i in range(3)) - plane) < tol]
    keys = {anchors._vkey(v) for v in start}
    region, rest = [start], [t for t in flat if t is not start]
    grew = True
    while grew:
        grew = False
        keep = []
        for t in rest:
            if any(anchors._vkey(v) in keys for v in t):
                region.append(t)
                keys.update(anchors._vkey(v) for v in t)
                grew = True
            else:
                keep.append(t)
        rest = keep
    return region


def _section(region, origin, ex, ey):
    """The face as a Manifold cross-section in (u, v)."""
    import manifold3d as m
    loops = []
    for t in region:
        pts = [((p[0] - origin[0]) * ex[0] + (p[1] - origin[1]) * ex[1]
                + (p[2] - origin[2]) * ex[2],
                (p[0] - origin[0]) * ey[0] + (p[1] - origin[1]) * ey[1]
                + (p[2] - origin[2]) * ey[2]) for p in t[:3]]
        area = sum(pts[i][0] * pts[(i + 1) % 3][1]
                   - pts[(i + 1) % 3][0] * pts[i][1] for i in range(3))
        if abs(area) < 1e-12:
            continue
        loops.append(pts if area > 0 else pts[::-1])
    cs = None
    for lp in loops:
        one = m.CrossSection([lp], m.FillRule.Positive)
        cs = one if cs is None else cs + one
    return cs


def _centroid(cs):
    """Area centroid of a cross-section (its biggest outline's weighted
    mean over all loops)."""
    ax = ay = a = 0.0
    for loop in cs.to_polygons():
        n = len(loop)
        for i in range(n):
            x0, y0 = loop[i]
            x1, y1 = loop[(i + 1) % n]
            w = x0 * y1 - x1 * y0
            a += w
            ax += (x0 + x1) * w
            ay += (y0 + y1) * w
    if abs(a) < 1e-12:
        return (0.0, 0.0)
    return (ax / (3 * a), ay / (3 * a))


def direction_angle(spec, ex, ey):
    """The direction in the face's (u, v), degrees: the picked vector
    (feature frame) projected on the face, or `angle`, plus 180 when
    reversed."""
    spec = spec_of(spec)
    d = spec.get("direction")
    if d:
        a = math.degrees(math.atan2(sum(d[i] * ey[i] for i in range(3)),
                                    sum(d[i] * ex[i] for i in range(3))))
    else:
        a = float(spec["angle"])
    return a + (180.0 if spec["reverse"] else 0.0)


def fill_points(tris, seed, normal, spec):
    """Everything about one fill: ``dict(centres, loops, frame)`` —
    *centres* the kept instance centres (u, v), *loops* the seed polygon
    of each, `frame` = (origin, ry, rz, ex, ey, n). *seed* is any point
    on the face (feature frame), *normal* its outward normal."""
    import manifold3d as m
    spec = spec_of(spec)
    ry, rz, ex, ey, n = basis(normal)
    region = face_region(tris, seed, normal)
    if not region:
        return None
    origin = [sum(p[i] for t in region for p in t[:3]) / (3 * len(region))
              for i in range(3)]
    plane = sum(region[0][0][i] * n[i] for i in range(3))
    origin = [origin[i] + n[i] * (plane - sum(origin[k] * n[k]
                                              for k in range(3)))
              for i in range(3)]
    cs = _section(region, origin, ex, ey)
    if cs is None or cs.is_empty():
        return None
    cu, cv = _centroid(cs)
    inset = cs.offset(-float(spec["margin"]), m.JoinType.Miter, 2.0) \
        if spec["margin"] > 0 else cs
    angle = direction_angle(spec, ex, ey)
    # the layout runs along the direction: +v of the layout = the angle
    turn = angle - 90.0
    c, s = math.cos(math.radians(turn)), math.sin(math.radians(turn))
    xmin, ymin, xmax, ymax = cs.bounds()
    reach = max(math.hypot(x - cu, y - cv)
                for x in (xmin, xmax) for y in (ymin, ymax))
    seed_pts = seed_loop(spec, angle - 90.0 + 90.0)
    seed_cs = m.CrossSection([seed_pts], m.FillRule.Positive)
    seed_area = seed_cs.area()
    kept = []
    for (u, v) in candidates(spec, reach):
        x, y = cu + u * c - v * s, cv + u * s + v * c
        probe = seed_cs.translate((x, y))
        if (probe - inset).area() < 1e-7 * max(seed_area, 1e-9) and \
                not inset.is_empty():
            kept.append((x, y))
    return dict(centres=kept, loops=seed_pts, frame=(origin, ry, rz, ex,
                                                     ey, n), face=region,
                bounds=(xmin, ymin, xmax, ymax), centre=(cu, cv))


def count(tris, seed, normal, spec):
    """How many instances a fill would hold (SolidWorks' Validate
    Count)."""
    r = fill_points(tris, seed, normal, spec)
    return len(r["centres"]) if r else 0


# -------------------------------------------------------------- model
def _frame_inv(model, feature, scope):
    import numpy as np
    from . import mesh
    m = np.array(mesh.ancestor_matrix(feature, stop=scope), dtype=float)
    return m, np.linalg.inv(m)


def _tris_in(feature_frame_inv, tris):
    import numpy as np
    out = []
    for t in tris:
        out.append([tuple(float(c) for c in (feature_frame_inv
                    @ np.array([p[0], p[1], p[2], 1.0]))[:3])
                    for p in t[:3]])
    return out


def _depth(model, part, spec):
    if spec["end"] == "Through all":
        from . import hole_wizard
        return hole_wizard._through(model, part)
    return float(spec["depth"])


_BUSY = []        # a build in progress: its edits must not refresh


def cutter_nodes(model, feature, spec, result, depth):
    """(Re)build the cutter under *feature* from a fill_points result."""
    _BUSY.append(feature)
    try:
        return _cutter_nodes(model, feature, spec, result, depth)
    finally:
        _BUSY.pop()


def _cutter_nodes(model, feature, spec, result, depth):
    spec = spec_of(spec)
    origin, ry, rz, ex, ey, n = result["frame"]
    for child in list(feature.children):
        model.remove_node(child)
    base = [origin[i] - n[i] * depth for i in range(3)]
    move = model.add_node("translate", dict(
        x=round(base[0], 5), y=round(base[1], 5), z=round(base[2], 5)),
        parent=feature)
    turn = model.add_node("rotate", dict(x=0.0, y=ry, z=rz), parent=move)
    ext = model.add_node("linear_extrude", dict(
        height=round(depth + EXTRA, 5)), parent=turn)
    points, paths = [], []
    for (u, v) in result["centres"]:
        ring = []
        for (a, b) in result["loops"]:
            ring.append(len(points))
            points.append([round(u + a, 5), round(v + b, 5)])
        paths.append(ring)
    poly = model.add_node("polygon", dict(points=points, paths=paths),
                          parent=ext)
    model.rename(poly, "Seed cut x%d" % len(paths))
    return poly


def title(spec, n=None):
    spec = spec_of(spec)
    word = dict(LAYOUTS)[spec["layout"]]
    return "Fill Pattern (%s%s)" % (word.lower(), "" if n is None
                                    else ", %d" % n)


def feature_for(model, part):
    """A Fill Pattern feature cutting *part* (its Difference), or None."""
    parent = part.parent
    if parent is not None and parent.type == "difference" and \
            parent.children and parent.children[0] is part:
        for child in parent.children[1:]:
            if child.type == "union" and KEY in child.params:
                return child
    return None


def new_feature(model, part):
    """A fresh empty Fill Pattern Group cutting *part*; (feature,
    created_difference)."""
    made = False
    if part.parent is not None and part.parent.type == "difference" \
            and part.parent.children[0] is part:
        diff = part.parent
    else:
        diff = model.wrap_nodes([part], "difference")
        made = True
    feature = model.add_node("union", {}, parent=diff)
    return feature, made


def build(model, feature, part, spec, tris_feature):
    """Fill *feature* from the face recorded in *spec* (``face`` =
    {seed, normal} in the feature's frame) on the triangles of the part
    in the same frame. Returns the instance count (0 = nothing fits)."""
    spec = spec_of(spec)
    face = spec["face"]
    res = fill_points(tris_feature, face["seed"], face["normal"], spec)
    if res is None:
        return 0
    cutter_nodes(model, feature, spec, res, _depth(model, part, spec))
    feature.params[KEY] = dict(spec)
    model.rename(feature, title(spec, len(res["centres"])))
    return len(res["centres"])


def part_tris(part, feature=None):
    """The part's triangles in the frame of *feature* (the cut's own
    frame, the Difference's parent chain)."""
    from . import mesh
    try:
        return mesh.tessellate(part)
    except Exception:
        return []


def add_fill(model, part, point, normal, spec, tris=None, scope=None):
    """Fill the face at the scope-frame *point* / *normal* of *part*.
    *tris* are the part's triangles in the same frame (default: the
    part's own). Returns (feature, count)."""
    spec = spec_of(spec)
    if part.type in ("component", "reference"):
        from . import anchors, hole_wizard, mates
        env = anchors.doc_env(model)
        loc = lambda p: anchors.to_local(part, p, env)        # noqa: E731
        point = loc(point)
        normal = anchors.dir_to_local(part, normal, env)
        if tris is not None:
            tris = [[loc(p) for p in t[:3]] for t in tris]
        part = hole_wizard.body_of(model, part)
    body_tris = part_tris(part)
    feature, made = new_feature(model, part)
    # the click is in the scope's frame; the cutter lives in the
    # feature's (the part's own) frame
    import numpy as np
    _m, inv = _frame_inv(model, feature, scope)
    p = inv @ np.array([point[0], point[1], point[2], 1.0])
    nv = np.linalg.inv(_m[:3, :3]).T @ np.array(normal, dtype=float)
    nv = nv / (np.linalg.norm(nv) or 1.0)
    spec["face"] = dict(seed=[round(float(c), 5) for c in p[:3]],
                        normal=[round(float(c), 6) for c in nv])
    n = build(model, feature, part, spec, body_tris)
    return feature, n, made


def regenerate(model, feature):
    """Fill again from the part as it is now (a resized part refills);
    the number of instances."""
    spec = spec_of(feature.params.get(KEY))
    diff = feature.parent
    if diff is None or not diff.children or not spec["face"]:
        return 0
    part = diff.children[0]
    return build(model, feature, part, spec, part_tris(part))


def refresh(model):
    """Every fill follows its part after an edit (as the holes do);
    nothing changes when the face and the count are as they were."""
    if _BUSY:
        return
    for feature in list(model.root.walk()):
        if feature.type != "union" or not isinstance(
                feature.params.get(KEY), dict):
            continue
        try:
            before = [[tuple(p) for p in c.params.get("points") or []]
                      for c in feature.walk() if c.type == "polygon"]
            spec = spec_of(feature.params.get(KEY))
            diff = feature.parent
            if diff is None or diff.type != "difference" or not spec["face"]:
                continue
            part = diff.children[0]
            res = fill_points(part_tris(part), spec["face"]["seed"],
                              spec["face"]["normal"], spec)
            if res is None:
                continue
            pts = []
            for (u, v) in res["centres"]:
                for (a, b) in res["loops"]:
                    pts.append((round(u + a, 5), round(v + b, 5)))
            if before and before[0] == pts:
                continue
            cutter_nodes(model, feature, spec, res, _depth(model, part,
                                                           spec))
            model.rename(feature, title(spec, len(res["centres"])))
        except Exception:               # a stale face: leave it be
            continue


# --------------------------------------------------------------- MCP
def run_mcp(window, params):
    """MCP `fill_pattern`: fill a face (world point + normal from
    probe_surface) with seed cuts, or change a fill (action update)."""
    model = window.model
    keys = ("layout", "loop_spacing", "spacing", "margin", "shape", "size",
            "rotation", "sides", "angle", "direction", "reverse", "end",
            "depth")
    spec = {k: params[k] for k in keys if k in params}
    if spec.get("layout") not in (None, *[k for k, _ in LAYOUTS]):
        raise ValueError("layout must be one of %s." %
                         [k for k, _ in LAYOUTS])
    if spec.get("shape") not in (None, *[k for k, _ in SHAPES]):
        raise ValueError("shape must be one of %s." %
                         [k for k, _ in SHAPES])
    node = model.find(int(params["node_id"]))
    if node is None:
        raise ValueError("No node with id %r." % params["node_id"])
    if params.get("action") == "update":
        feature = node
        while feature is not None and KEY not in feature.params:
            feature = feature.parent
        if feature is None:
            raise ValueError("%s is not in a Fill Pattern." % node.name)
        feature.params[KEY] = dict(spec_of(feature.params[KEY]), **spec)
        n = regenerate(model, feature)
    elif params.get("action") == "count":
        pt = params.get("point") or [0, 0, 0]
        normal = params.get("normal") or [0, 0, 1]
        scope = window._render_scope()[0]
        return dict(count=count(part_tris(node), pt, normal,
                                dict(spec_of(spec), face=None)))
    else:
        pt = params.get("point")
        if not pt:
            raise ValueError("Give point [x, y, z] on the face and its "
                             "normal.")
        normal = params.get("normal") or [0, 0, 1]
        feature, n, _made = add_fill(model, node, pt, normal, spec)
    return dict(feature_id=feature.id, name=feature.name, count=n,
                spec=feature.params[KEY])


def line_vector(model, line, feature, scope=None):
    """The direction of a sketch *line* as a unit vector in *feature*'s
    frame (the pattern direction a picked sketch line gives)."""
    import numpy as np
    from . import mesh
    ml = np.array(mesh.ancestor_matrix(line, stop=scope), dtype=float)
    _m, inv = _frame_inv(model, feature, scope)
    p = lambda x, y: inv @ ml @ np.array([x, y, 0.0, 1.0])   # noqa: E731
    a = p(float(line.params.get("x1", 0.0)), float(line.params.get("y1", 0.0)))
    b = p(float(line.params.get("x2", 0.0)), float(line.params.get("y2", 0.0)))
    d = (b - a)[:3]
    n = np.linalg.norm(d)
    return [round(float(c), 6) for c in (d / n if n > 1e-12 else d)]


def update_feature(model, feature, spec):
    """Settings changed: fill again. The instance count."""
    feature.params[KEY] = dict(spec_of(spec))
    diff = feature.parent
    part = diff.children[0]
    return build(model, feature, part, spec_of(spec), part_tris(part))
