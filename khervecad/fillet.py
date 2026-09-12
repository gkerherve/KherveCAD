"""Fillet / chamfer chosen edges — SolidWorks' Fillet feature (Qt-free).

OpenSCAD has no edges, only solids, so "round this edge" has to be
built from what a solid can do: subtract material along a convex edge,
add it along a concave one. That is exactly the rolling-ball fillet:

- The part's mesh is scanned for **crease edges** — edges where two
  faces meet at more than `MIN_ANGLE` (`crease_edges`), each knowing
  its two faces and whether it is convex (a box corner) or concave (an
  inside corner).
- A picked edge is **propagated** along tangent-continuous creases
  (`chain`): one click on a cylinder's rim takes the whole rim, one
  click on a box edge stops at the corners where three creases meet.
- Along each chain a **strip** is built (`strip`): at every vertex the
  cross-section is the kite between the edge and the fillet circle
  tangent to both faces (`profile`) — for a chamfer, the triangle
  between the two setback lines — mitred at the chain's corners and
  capped at its ends.
- Convex chains become **cuts** (difference), concave ones **adds**
  (union). `compute()` returns both as triangle lists; codegen writes
  them as polyhedra into ``kcad_fillet(...) { children }`` whose helper
  does the boolean, so the exact OpenSCAD render and the STL are truly
  filleted. The built-in preview cannot cut, so it shows the children
  plus the concave fillers (the exact per-part render lands a moment
  later, as it does for any difference).

Edges are remembered as geometry — the seed segment's two endpoints in
the part's own frame — and re-found by nearest match each time the
part is regenerated, so editing the part keeps its fillets; an edge
that no longer exists is reported by validation, never guessed.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import math

#: two faces meeting at less than this (degrees) are one smooth surface
#: — a cylinder's facets, a sphere's — not an edge to fillet
MIN_ANGLE = 20.0

#: a chain follows the next crease while the turn between consecutive
#: edges stays under this (degrees): round a rim, stop at a corner
MAX_TURN = 35.0

#: how far (mm, plus this fraction of the part's size) a remembered
#: edge may drift from a crease and still be the same edge
FIND_TOL = 0.5
FIND_FRAC = 0.01

KINDS = ("round", "chamfer")

OPERATION = "op"

NODE_TYPES = {
    "fillet": dict(
        label="Fillet edges", category=OPERATION,
        icon="mdi.rounded-corner",
        params=dict(radius=2.0, kind="round", detail=6, edges=[]),
        schema=[("radius", "Radius (chamfer: setback)", "float",
                 0.01, 1e4),
                ("kind", "Kind", "choice", list(KINDS), None),
                ("detail", "Segments across the round", "int", 1, 64),
                ("edges", "Edges (a click adds one; start x y z, "
                          "end x y z)", "rows",
                 ["X1", "Y1", "Z1", "X2", "Y2", "Z2"], None)]),
}

#: OpenSCAD: the boolean the fillet compiles to. The polyhedra are
#: baked by this module; the importer ignores them and rebuilds the
#: node from radius / kind / detail / edges and the children.
HELPER = """\
module kcad_fillet(radius = 2, kind = "round", detail = 6, edges = [],
                   cuts = [], adds = []) {
    union() {
        difference() {
            children();
            for (c = cuts)
                polyhedron(points = c[0], faces = c[1], convexity = 4);
        }
        for (a = adds)
            polyhedron(points = a[0], faces = a[1], convexity = 4);
    }
}"""


# ----------------------------------------------------------- vectors
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _len(a):
    return math.sqrt(_dot(a, a))


def _unit(a):
    n = _len(a)
    return _mul(a, 1.0 / n) if n > 1e-12 else (0.0, 0.0, 0.0)


def _vkey(v):
    return (round(v[0], 5), round(v[1], 5), round(v[2], 5))


def _normal(tri):
    a, b, c = tri
    return _unit(_cross(_sub(b, a), _sub(c, a)))


# ------------------------------------------------------ crease edges
class Edge:
    """A crease: ``a -> b`` as traversed by face L (counter-clockwise),
    face R traverses it the other way. *angle* is the dihedral in
    degrees, *convex* True for an outside corner."""

    __slots__ = ("a", "b", "nl", "nr", "angle", "convex")

    def __init__(self, a, b, nl, nr, angle, convex):
        self.a, self.b, self.nl, self.nr = a, b, nl, nr
        self.angle, self.convex = angle, convex

    @property
    def mid(self):
        return _mul(_add(self.a, self.b), 0.5)

    @property
    def direction(self):
        return _unit(_sub(self.b, self.a))

    @property
    def length(self):
        return _len(_sub(self.b, self.a))


def crease_edges(tris, min_angle: float = MIN_ANGLE) -> list:
    """Every edge of *tris* (counter-clockwise triangles) shared by two
    faces meeting at more than *min_angle* degrees."""
    normals = [_normal(t) for t in tris]
    directed = {}
    for i, tri in enumerate(tris):
        keys = [_vkey(v) for v in tri]
        for k in range(3):
            directed[(keys[k], keys[(k + 1) % 3])] = (i, tri[k],
                                                      tri[(k + 1) % 3])
    cos_min = math.cos(math.radians(min_angle))
    out = []
    for (ka, kb), (i, a, b) in directed.items():
        if ka >= kb:
            continue                     # each undirected edge once
        other = directed.get((kb, ka))
        if other is None:
            continue                     # an open border, not an edge
        j = other[0]
        nl, nr = normals[i], normals[j]
        cos = max(-1.0, min(1.0, _dot(nl, nr)))
        if cos > cos_min:
            continue
        angle = math.degrees(math.acos(cos))
        convex = _dot(_cross(nl, nr), _sub(b, a)) > 0.0
        out.append(Edge(a, b, nl, nr, angle, convex))
    return out


def _turn(d0, d1) -> float:
    return math.degrees(math.acos(max(-1.0, min(1.0, _dot(d0, d1)))))


def chain(edges, seed, max_turn: float = MAX_TURN) -> dict:
    """The tangent-continuous run of creases through *seed* (an Edge
    from *edges*): ``{"points": [...], "edges": [Edge...], "closed":
    bool, "convex": bool}`` with the edges oriented along the run.
    At a vertex the crease that turns least is followed, while the
    turn stays under *max_turn* and the convexity matches."""
    by_vertex = {}
    for e in edges:
        by_vertex.setdefault(_vkey(e.a), []).append(e)
        by_vertex.setdefault(_vkey(e.b), []).append(e)

    def oriented(e, start_key):
        """*e* as (Edge traversed from start_key, direction)."""
        if _vkey(e.a) == start_key:
            return e, e.direction
        flipped = Edge(e.b, e.a, e.nr, e.nl, e.angle, e.convex)
        return flipped, flipped.direction

    used = {id(seed)}                    # shared: a run never doubles back

    def walk(start_edge, forward):
        """Edges continuing from one end of the seed, in order, and
        whether the run came round to the seed again (a closed rim)."""
        run = []
        cur = start_edge if forward else \
            Edge(start_edge.b, start_edge.a, start_edge.nr,
                 start_edge.nl, start_edge.angle, start_edge.convex)
        while True:
            end_key = _vkey(cur.b)
            best, best_turn = None, max_turn
            for cand in by_vertex.get(end_key, ()):
                if cand.convex != seed.convex:
                    continue
                o, d = oriented(cand, end_key)
                turn = _turn(cur.direction, d)
                if cand is seed:
                    if forward and turn < max_turn and run:
                        return run, True     # back at the seed: closed
                    continue
                if id(cand) in used:
                    continue
                if turn < best_turn:
                    best, best_turn = (cand, o), turn
            if best is None:
                return run, False
            cand, o = best
            used.add(id(cand))
            run.append(o)
            cur = o

    ahead, closed = walk(seed, True)
    if closed:
        ordered = [seed] + ahead
    else:
        behind, _ = walk(seed, False)
        # behind is oriented away from the seed: flip it back
        behind = [Edge(e.b, e.a, e.nr, e.nl, e.angle, e.convex)
                  for e in reversed(behind)]
        ordered = behind + [seed] + ahead
    points = [e.a for e in ordered]
    if not closed:
        points.append(ordered[-1].b)
    return dict(points=points, edges=ordered, closed=closed,
                convex=seed.convex)


# ----------------------------------------------------------- profile
def profile(edge, radius: float, kind: str, detail: int) -> tuple:
    """The cutter's cross-section for *edge*: ``(u, v, points2d)`` —
    a frame perpendicular to the edge (u into face L, v = t x u, so
    u x v = t) and the polygon in it: the edge point E, the tangent
    point on L, the arc (or nothing, for a chamfer) and the tangent
    point on R. The polygon is oriented counter-clockwise in (u, v)."""
    t = edge.direction
    dl = _unit(_cross(edge.nl, t))         # into face L, away from the edge
    dr = _unit(_cross(t, edge.nr))         # into face R
    u = dl
    v = _unit(_cross(t, u))
    x_r, y_r = _dot(dr, u), _dot(dr, v)
    beta = math.acos(max(-1.0, min(1.0, _dot(dl, dr))))   # between faces
    beta = max(beta, math.radians(1.0))
    if kind == "chamfer":
        s = radius
        pts = [(0.0, 0.0), (s, 0.0), (s * x_r, s * y_r)]
    else:
        s = radius / math.tan(beta / 2.0)
        cx, cy = _mul_2d(_unit_2d((1.0 + x_r, y_r)),
                         radius / math.sin(beta / 2.0))
        tl, tr = (s, 0.0), (s * x_r, s * y_r)
        a0 = math.atan2(tl[1] - cy, tl[0] - cx)
        a1 = math.atan2(tr[1] - cy, tr[0] - cx)
        sweep = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi  # short way
        n = max(int(detail), 1)
        pts = [(0.0, 0.0), tl]
        for k in range(1, n):
            a = a0 + sweep * k / n
            pts.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))
        pts.append(tr)
    if _area2d(pts) < 0:
        pts = [pts[0]] + pts[1:][::-1]
    return u, v, pts


def _mul_2d(p, k):
    return (p[0] * k, p[1] * k)


def _unit_2d(p):
    n = math.hypot(*p)
    return (p[0] / n, p[1] / n) if n > 1e-12 else (1.0, 0.0)


def _area2d(pts):
    total = 0.0
    for i, (x1, y1) in enumerate(pts):
        x2, y2 = pts[(i + 1) % len(pts)]
        total += x1 * y2 - x2 * y1
    return total / 2.0


# ------------------------------------------------------------- strip
def strip(run: dict, radius: float, kind: str, detail: int) -> list:
    """Counter-clockwise triangles of the cutter (or filler) along a
    chain: one ring per chain vertex, mitred between its two edges,
    walls between rings, caps at open ends."""
    edges = run["edges"]
    profiles = [profile(e, radius, kind, detail) for e in edges]
    m = len(profiles[0][2])
    if any(len(p[2]) != m for p in profiles):
        return []                          # pragma: no cover

    def offsets(i):
        u, v, pts = profiles[i]
        return [_add(_mul(u, x), _mul(v, y)) for x, y in pts]

    def mitre(o0, o1, t0, t1):
        k = 1.0 + _dot(t0, t1)
        if k < 0.2:                        # a hairpin: just average
            return [_mul(_add(a, b), 0.5) for a, b in zip(o0, o1)]
        return [_mul(_add(a, b), 1.0 / k) for a, b in zip(o0, o1)]

    dirs = [e.direction for e in edges]
    offs = [offsets(i) for i in range(len(edges))]
    rings = []
    n = len(edges)
    if run["closed"]:
        for i in range(n):
            prev = (i - 1) % n
            o = mitre(offs[prev], offs[i], dirs[prev], dirs[i])
            rings.append([_add(edges[i].a, p) for p in o])
    else:
        rings.append([_add(edges[0].a, p) for p in offs[0]])
        for i in range(1, n):
            o = mitre(offs[i - 1], offs[i], dirs[i - 1], dirs[i])
            rings.append([_add(edges[i].a, p) for p in o])
        rings.append([_add(edges[-1].b, p) for p in offs[-1]])
    tris = []
    spans = list(zip(rings, rings[1:]))
    if run["closed"]:
        spans.append((rings[-1], rings[0]))
    for lower, upper in spans:
        for k in range(m):
            k1 = (k + 1) % m
            a, b, c, d = lower[k], lower[k1], upper[k1], upper[k]
            tris.append((a, b, c))
            tris.append((a, c, d))
    if not run["closed"]:
        from .mesh import triangulate
        for ring, pts2d, reverse in ((rings[0], profiles[0][2], True),
                                     (rings[-1], profiles[-1][2], False)):
            for a, b, c in triangulate(pts2d):
                idx = [pts2d.index(p) for p in (a, b, c)]
                pa, pb, pc = (ring[i] for i in idx)
                tris.append((pa, pc, pb) if reverse else (pa, pb, pc))
    return tris


# ------------------------------------------------------------ compute
def find_edge(edges, seed, size: float):
    """The crease nearest the remembered segment *seed* (6 numbers),
    or None: closest midpoint within tolerance, roughly parallel."""
    a, b = tuple(seed[:3]), tuple(seed[3:6])
    mid = _mul(_add(a, b), 0.5)
    d = _unit(_sub(b, a))
    tol = FIND_TOL + FIND_FRAC * size
    best, best_dist = None, None
    for e in edges:
        dist = _len(_sub(e.mid, mid))
        if dist > tol or abs(_dot(e.direction, d)) < 0.9:
            continue
        if best_dist is None or dist < best_dist:
            best, best_dist = e, dist
    return best


def mesh_size(tris) -> float:
    if not tris:
        return 0.0
    pts = [v for t in tris for v in t]
    return max(max(p[i] for p in pts) - min(p[i] for p in pts)
               for i in range(3))


def compute(tris, seeds, radius: float, kind: str = "round",
            detail: int = 6, min_angle: float = MIN_ANGLE) -> dict:
    """``{"cuts": [tris...], "adds": [tris...], "missing": [seed...],
    "chains": n}`` for the remembered *seeds* on the mesh *tris*."""
    edges = crease_edges(tris, min_angle)
    size = mesh_size(tris)
    cuts, adds, missing, seen = [], [], [], set()
    for seed in seeds:
        try:
            values = [float(v) for v in seed]
        except (TypeError, ValueError):
            missing.append(seed)
            continue
        if len(values) != 6:
            missing.append(seed)
            continue
        e = find_edge(edges, values, size)
        if e is None:
            missing.append(seed)
            continue
        run = chain(e, edges) if False else chain(edges, e)
        key = frozenset(_vkey(p) for p in run["points"])
        if key in seen:
            continue
        seen.add(key)
        body = strip(run, float(radius), kind, int(detail))
        if not body:
            continue
        (cuts if run["convex"] else adds).append(body)
    return dict(cuts=cuts, adds=adds, missing=missing, chains=len(seen))


def chains(tris, min_angle: float = MIN_ANGLE) -> list:
    """Every distinct crease chain of *tris*, for listing (an assistant
    picks by geometry, a person by clicking): dicts with the seed
    segment, ends, length, dihedral, convexity, closed and centre."""
    edges = crease_edges(tris, min_angle)
    out, seen = [], set()
    for e in edges:
        run = chain(edges, e)
        key = frozenset(_vkey(p) for p in run["points"])
        if key in seen:
            continue
        seen.add(key)
        pts = run["points"]
        length = sum(x.length for x in run["edges"])
        centre = [sum(p[i] for p in pts) / len(pts) for i in range(3)]
        out.append(dict(
            seed=[round(v, 4) for v in (*e.a, *e.b)],
            start=[round(v, 4) for v in pts[0]],
            end=[round(v, 4) for v in pts[-1]],
            segments=len(run["edges"]), length=round(length, 3),
            angle=round(sum(x.angle for x in run["edges"])
                        / len(run["edges"]), 1),
            convex=run["convex"], closed=run["closed"],
            centre=[round(v, 4) for v in centre]))
    out.sort(key=lambda c: (-c["length"], c["centre"]))
    return out


# ---------------------------------------------------- node integration
_CACHE = {}
_CACHE_SIZE = 16


def _num(value, env, default):
    from .mesh import rv
    return rv(value, env, default)


def baked(node, env) -> dict:
    """compute() for a fillet node, cached by content: the children's
    local mesh and the node's parameters."""
    from . import bake, document, mesh
    key = json.dumps([document.node_to_dict(node),
                      sorted((k, repr(v)) for k, v in env.items())],
                     sort_keys=True, default=str)
    hit = _CACHE.get(key)
    if hit is None:
        p = node.params
        src = [tri for tri, _c, _s in
               mesh._children_mesh(node, env, None, frozenset(), False)]
        result = compute(src, p.get("edges") or [],
                         _num(p.get("radius", 2.0), env, 2.0),
                         str(p.get("kind", "round")),
                         int(_num(p.get("detail", 6), env, 6.0)))
        result["cut_polys"] = [bake.to_polyhedron(t) for t in result["cuts"]]
        result["add_polys"] = [bake.to_polyhedron(t) for t in result["adds"]]
        hit = _CACHE[key] = result
        while len(_CACHE) > _CACHE_SIZE:
            _CACHE.pop(next(iter(_CACHE)))
    return hit


def statement(node, fmt) -> str:
    from . import bake
    p = node.params
    try:
        result = baked(node, bake._codegen_env(node))
        cut_polys, add_polys = result["cut_polys"], result["add_polys"]
    except Exception:                       # validation has flagged it
        cut_polys, add_polys = [], []

    def polys(items):
        if not items:
            return "[]"
        return "[\n    " + ",\n    ".join(
            f"[{bake._rows_wrapped(pts, fmt)}, {bake._rows_wrapped(fcs, fmt)}]"
            for pts, fcs in items) + "\n    ]"
    kind = p.get("kind", "round") if p.get("kind") in KINDS else "round"
    return (f"kcad_fillet(radius = {fmt(p.get('radius', 2.0))}, "
            f'kind = "{kind}", detail = {fmt(p.get("detail", 6))}, '
            f"edges = {bake._rows(p.get('edges') or [], fmt)},\n"
            f"    cuts = {polys(cut_polys)},\n"
            f"    adds = {polys(add_polys)})")


def build(parser, positional, named):
    """scadparse builder for kcad_fillet: parameters back, baked
    polyhedra ignored (the children in the block rebuild them)."""
    from .model import CadNode
    from .scadparse import _num as num
    edges = named.get("edges", [])
    rows = ([[num(v) for v in row] for row in edges
             if isinstance(row, list) and len(row) == 6]
            if isinstance(edges, list) else [])
    kind = named.get("kind", "round")
    try:
        detail = int(num(named.get("detail", 6), 6))
    except (TypeError, ValueError):
        detail = 6
    return CadNode("fillet", NODE_TYPES["fillet"]["label"], dict(
        radius=num(named.get("radius", 2.0), 2.0),
        kind=kind if kind in KINDS else "round", detail=detail,
        edges=rows))


def check(node, env):
    from .model import _contains_3d
    parent = node.parent
    while parent is not None:
        if parent.type in ("for_loop", "while_loop", "if_else"):
            kind = parent.type.replace("_", " ").replace(" loop", "")
            return ("a fillet is baked into the program, so it can't sit "
                    f"inside a {kind} — put the {kind} inside the fillet")
        parent = parent.parent
    if not any(c.type != "assign" for c in node.children):
        return "empty — put the solid to round inside"
    if not _contains_3d(node):
        return "a fillet rounds the edges of a solid — this holds only 2D"
    p = node.params
    if str(p.get("kind", "round")) not in KINDS:
        return "kind must be 'round' or 'chamfer'"
    rows = p.get("edges") or []
    if not isinstance(rows, list):
        return "edges: give rows of start x, y, z, end x, y, z"
    for number, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != 6:
            return f"edge {number} needs 6 values: start x y z, end x y z"
    if not rows:
        return None                          # nothing picked yet: fine
    try:
        result = baked(node, env)
    except Exception as exc:                 # pragma: no cover
        return f"fillet failed: {exc}"
    if result["missing"]:
        n = len(result["missing"])
        return (f"{n} of {len(rows)} edges not found on the part any "
                "more (it changed) — pick them again")
    return None


def tess(node, env, color, sel, selected):
    """Preview: the children plus the concave fillers. The convex cuts
    need a boolean the built-in tessellator cannot do — the exact
    OpenSCAD render shows them, as it does for any difference."""
    from . import mesh
    out = list(mesh._children_mesh(node, env, color, sel, selected))
    try:
        result = baked(node, env)
    except Exception:
        return out
    for body in result["adds"]:
        out.extend(mesh._emit(body, color, selected))
    return out


def uses_booleans(node) -> bool:
    """True when the exact render will differ from the preview — a
    convex edge is filleted by subtraction."""
    return bool(node.params.get("edges"))
