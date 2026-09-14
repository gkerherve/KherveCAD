"""2D engineering drawings of the model (Qt-free geometry).

What SolidWorks calls a *drawing*: the model projected into standard
third-angle views — Front, Top, Right and an isometric — with visible
edges solid and hidden edges dashed, overall dimensions, an optional
hatched section through the middle, laid out on an A4/A3 sheet at a
nice scale with a title block. `drawing_export.py` paints the result
to PDF/SVG/PNG and writes DXF for the export_drawing MCP tool; the
interactive drawing (File ▸ Blueprint…) is `blueprint.py`, which
projects its views with `view_lines` and the helpers at the bottom.

The lines of a view are the mesh's crease edges (faces meeting at more
than `shading.EDGE_ANGLE`, plus open borders) and its silhouette for
that view. Hidden-line removal is a **depth grid**: the triangles are
rasterised into a grid of nearest depths (`DepthGrid`), then every edge
is sampled along its length and each sample compared with the grid —
runs that lie behind the surface become the dashed hidden segments.
Coarse, but it needs no BSP and takes a second on a 30k-triangle
part.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from . import section, shading

#: the standard views: name -> (right, up, forward) unit vectors in
#: world coordinates (forward is the viewing direction). Third-angle
#: projection: Front looks along +Y, Top looks down -Z, Right looks
#: along -X.
VIEWS = {
    "Front": ((1, 0, 0), (0, 0, 1), (0, 1, 0)),
    "Top": ((1, 0, 0), (0, 1, 0), (0, 0, -1)),
    "Right": ((0, 1, 0), (0, 0, 1), (-1, 0, 0)),
    "Left": ((0, -1, 0), (0, 0, 1), (1, 0, 0)),
    "Back": ((-1, 0, 0), (0, 0, 1), (0, -1, 0)),
    "Bottom": ((1, 0, 0), (0, -1, 0), (0, 0, 1)),
}
_s = math.sqrt(1.0 / 3.0)
_ISO_F = (-_s, _s, -_s)                      # looks from front-right-top
_ISO_R = (1 / math.sqrt(2.0), 1 / math.sqrt(2.0), 0.0)
_ISO_U = (-_ISO_F[1] * _ISO_R[2] + _ISO_F[2] * _ISO_R[1],
          -_ISO_F[2] * _ISO_R[0] + _ISO_F[0] * _ISO_R[2],
          -_ISO_F[0] * _ISO_R[1] + _ISO_F[1] * _ISO_R[0])
VIEWS["Isometric"] = (_ISO_R, _ISO_U, _ISO_F)

#: sheet sizes (landscape), mm
SHEETS = {"A4": (297.0, 210.0), "A3": (420.0, 297.0),
          "A2": (594.0, 420.0), "A1": (841.0, 594.0),
          "A0": (1189.0, 841.0), "Letter": (279.4, 215.9),
          "Tabloid": (431.8, 279.4)}
#: the scales a drawing may use, as multipliers (2 = 2:1, 0.5 = 1:2)
SCALES = [10, 5, 2, 1, 0.5, 0.2, 0.1, 0.05, 0.02, 0.01]
#: hidden-line sampling: samples per edge, and the depth tolerance as a
#: fraction of the model's size
SAMPLES = 24
DEPTH_TOL = 0.004
#: depth-grid resolution across the model's longer side
GRID = 600


# ------------------------------------------------------------ projection

def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def project(point, view):
    """(u, v, depth) of a world point in *view* (parallel projection)."""
    right, up, forward = VIEWS[view]
    return _dot(point, right), _dot(point, up), _dot(point, forward)


class DepthGrid:
    """Nearest depth per cell over the projected mesh: a tiny z-buffer
    at grid resolution, filled by scan-converting every triangle."""

    def __init__(self, tris2d, bounds, cells, keep=None):
        """*keep*: per-triangle flags; a False triangle is left out (the
        back faces of a closed solid, which can never be the nearest)."""
        u0, v0, u1, v1 = bounds
        span = max(u1 - u0, v1 - v0, 1e-9)
        self.u0, self.v0 = u0, v0
        self.step = span / cells
        self.w = int((u1 - u0) / self.step) + 2
        self.h = int((v1 - v0) / self.step) + 2
        inf = float("inf")
        self.depth = [inf] * (self.w * self.h)
        #: which triangle is nearest in each cell (-1: none)
        self.owner = [-1] * (self.w * self.h)
        for index, (a, b, c) in enumerate(tris2d):
            if keep is None or keep[index]:
                self._raster(a, b, c, index)

    def _raster(self, a, b, c, index=-1):
        """Scan-convert one triangle: for each grid row, only the span of
        cell centres the row crosses, depth from the triangle's plane.
        Testing every cell of the bounding box took 28 s on a threaded
        bolt seen from above, whose flank facets are thin slanted
        slivers with nearly empty boxes."""
        s, u0, v0, w, h = self.step, self.u0, self.v0, self.w, self.h
        det = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(det) < 1e-15:
            return
        # depth as a plane over the view: d = c.d + kx (u - c.u) + ky (v - c.v)
        kx = ((b[1] - c[1]) * (a[2] - c[2])
              + (c[1] - a[1]) * (b[2] - c[2])) / det
        ky = ((c[0] - b[0]) * (a[2] - c[2])
              + (a[0] - c[0]) * (b[2] - c[2])) / det
        j0 = max(int(math.ceil((min(a[1], b[1], c[1]) - v0) / s - 0.5)), 0)
        j1 = min(int(math.floor((max(a[1], b[1], c[1]) - v0) / s - 0.5)),
                 h - 1)
        edges = ((a, b), (b, c), (c, a))
        depth, owner = self.depth, self.owner
        slack = s * 1e-6
        for j in range(j0, j1 + 1):
            py = v0 + (j + 0.5) * s
            lo, hi = float("inf"), -float("inf")
            for p, q in edges:
                if (p[1] - py) * (q[1] - py) > 0 or p[1] == q[1]:
                    continue
                x = p[0] + (py - p[1]) * (q[0] - p[0]) / (q[1] - p[1])
                lo, hi = min(lo, x), max(hi, x)
            if lo > hi:
                continue
            i0 = max(int(math.ceil((lo - slack - u0) / s - 0.5)), 0)
            i1 = min(int(math.floor((hi + slack - u0) / s - 0.5)), w - 1)
            if i0 > i1:
                continue
            row = j * w
            base = c[2] + ky * (py - c[1]) + kx * (u0 + 0.5 * s - c[0])
            step = kx * s
            for i in range(i0, i1 + 1):
                d = base + step * i
                if d < depth[row + i]:
                    depth[row + i] = d
                    owner[row + i] = index

    def at(self, u, v):
        i = int((u - self.u0) / self.step)
        j = int((v - self.v0) / self.step)
        if 0 <= i < self.w and 0 <= j < self.h:
            return self.depth[j * self.w + i]
        return float("inf")

    def owner_at(self, u, v):
        i = int((u - self.u0) / self.step)
        j = int((v - self.v0) / self.step)
        if 0 <= i < self.w and 0 <= j < self.h:
            return self.owner[j * self.w + i]
        return -1


def view_lines(tris, view, info=None, hidden_lines=True):
    """The drawing of one view: {"visible": [((u, v), (u, v))],
    "hidden": [...], "bounds": (u0, v0, u1, v1)} in model mm. Without
    *hidden_lines* the dashed segments are left out (a threaded part's
    thousands of facet edges swamp a drawing)."""
    if not tris:
        return {"visible": [], "hidden": [], "bounds": (0, 0, 0, 0)}
    info = info or shading.analyse(tris)
    right, up, forward = VIEWS[view]
    tris2d = [tuple(project(p, view) for p in tri) for tri in tris]
    us = [p[0] for t in tris2d for p in t]
    vs = [p[1] for t in tris2d for p in t]
    bounds = (min(us), min(vs), max(us), max(vs))
    size = max(bounds[2] - bounds[0], bounds[3] - bounds[1], 1e-9)
    # a closed, outward-wound solid (every edge shared by two faces)
    # never shows a back face nearest: leave those out of the grid. An
    # open mesh keeps them all — nothing behind a lone sheet may show.
    closed = 2 * len(info.neighbours) >= 3 * len(tris)
    keep = [_dot(n, forward) < 0.0 for n in info.normals] if closed \
        else None
    grid = DepthGrid(tris2d, bounds, GRID, keep)
    # the candidate edges: creases (plus borders) and this view's
    # silhouette, each with the faces it belongs to
    facing = [_dot(n, forward) < 0.0 for n in info.normals]
    edges, owners, adjacent, smooth = {}, {}, {}, {}
    cos_smooth = math.cos(math.radians(shading.EDGE_ANGLE))
    for i, j, p, q in info.neighbours:
        adjacent.setdefault(i, set()).add(j)
        adjacent.setdefault(j, set()).add(i)
        owners.setdefault(_edge_key(p, q), set()).update((i, j))
        if _dot(info.normals[i], info.normals[j]) >= cos_smooth:
            smooth.setdefault(i, []).append(j)
            smooth.setdefault(j, []).append(i)

    def beside(tri, point):
        """Is *tri* close enough to *point* in space to be a facet of
        the same curved surface seen edge-on? A few of its own sizes —
        so the thread hidden under a bolt's head, whose nearest face is
        the head, is hidden at once instead of walking the thread's
        flanks for every sample (28 s on an M10's top view)."""
        cx = (tri[0][0] + tri[1][0] + tri[2][0]) / 3.0
        cy = (tri[0][1] + tri[1][1] + tri[2][1]) / 3.0
        cz = (tri[0][2] + tri[1][2] + tri[2][2]) / 3.0
        reach = max(math.dist(tri[0], tri[1]), math.dist(tri[1], tri[2]),
                    math.dist(tri[2], tri[0]))
        return math.dist((cx, cy, cz), point) <= 3.0 * reach + tol

    def surroundings(ekey, rings=12, limit=150):
        """The faces an edge cannot be hidden by: its own, their direct
        neighbours, and the smooth surface around them (joined without
        a crease) for a few rings. At a curved silhouette the facets
        are seen edge-on — a quad at 45 segments can be a hundredth of
        a millimetre wide — so the grid cell beside the edge lands two
        or three facets round, a whole tolerance in front of it, and a
        cylinder's side came out dashed or missing."""
        own = set(owners.get(ekey, ()))
        # the smooth rings walk with their own visited set: seeding it
        # with the direct neighbours stopped the walk after one step
        reached, frontier = set(own), list(own)
        for _ in range(rings):
            nxt = []
            for face in frontier:
                for other in smooth.get(face, ()):
                    if other not in reached:
                        reached.add(other)
                        nxt.append(other)
            if not nxt or len(reached) >= limit:
                break
            frontier = nxt
        for face in own:
            reached |= adjacent.get(face, set())
        return reached
    for source in (info.creases, shading.silhouette(info, facing)):
        for face, segs in source.items():
            for p, q in segs:
                key = _edge_key(p, q)
                edges[key] = (p, q)
                owners.setdefault(key, set()).add(face)
    tol = size * DEPTH_TOL
    # edges that project onto the same line (a box's back edges under
    # its front edges) are one line in the drawing: keep the front-most
    projected = {}
    for ekey, (p, q) in edges.items():
        a, b = project(p, view), project(q, view)
        key = tuple(sorted(((round(a[0], 4), round(a[1], 4)),
                            (round(b[0], 4), round(b[1], 4)))))
        if key[0] == key[1]:
            continue                             # seen end-on: a point
        depth = a[2] + b[2]
        if key not in projected or depth < projected[key][0]:
            projected[key] = (depth, a, b, ekey, p, q)
    visible, hidden = [], []
    for _depth, a, b, ekey, p, q in projected.values():
        near = None                  # `surroundings`, only when needed
        # sample along the edge: in front of (or on) the surface, or behind
        runs = []
        state = None
        for n in range(SAMPLES + 1):
            t = n / SAMPLES
            u = a[0] + (b[0] - a[0]) * t
            v = a[1] + (b[1] - a[1]) * t
            d = a[2] + (b[2] - a[2]) * t
            seen = d <= grid.at(u, v) + tol
            if not seen:
                owner = grid.owner_at(u, v)
                point = (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t,
                         p[2] + (q[2] - p[2]) * t)
                if owner >= 0 and beside(tris[owner], point):
                    if near is None:
                        near = surroundings(ekey)
                    seen = owner in near
            if seen != state:
                runs.append([seen, t, t])
                state = seen
            else:
                runs[-1][2] = t
        # a run of one sample is grid aliasing along a facet edge, not a
        # real change: fold it into the run before it (a 20 MB SVG of
        # flicker otherwise)
        merged = []
        for seen, t0, t1 in runs:
            if merged and (t1 - t0) * SAMPLES < 1.5 and len(runs) > 1:
                merged[-1][2] = t1
            elif merged and merged[-1][0] == seen:
                merged[-1][2] = t1
            else:
                merged.append([seen, t0, t1])
        # an edge that is partly seen does not flicker into a hidden
        # sliver a hundredth of a millimetre long where it meets a curved
        # silhouette: runs under 0.2 % of the model join their neighbour
        # (an edge hidden along its whole length stays hidden)
        if len(merged) > 1:
            length = math.hypot(b[0] - a[0], b[1] - a[1])
            least = size * 0.002 / max(length, 1e-12)
            cleaned = []
            for run in merged:
                if cleaned and (run[2] - run[1] < least
                                or cleaned[-1][0] == run[0]):
                    cleaned[-1][2] = run[2]
                else:
                    cleaned.append(run)
            if len(cleaned) > 1 and cleaned[0][2] - cleaned[0][1] < least:
                cleaned[1][1] = cleaned[0][1]
                cleaned.pop(0)
            merged = cleaned
        for seen, t0, t1 in merged:
            if t1 - t0 < 1e-9:
                continue
            if not seen and not hidden_lines:
                continue
            seg = ((a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0),
                   (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1))
            (visible if seen else hidden).append(seg)
    if hidden and visible:
        hidden = _uncovered(hidden, visible, size * 1e-3)
    return {"visible": visible, "hidden": hidden, "bounds": bounds}


def _uncovered(hidden, visible, tol):
    """The parts of *hidden* that do not lie on a visible line. Drafting
    draws a visible edge over a hidden one, never both: the back half of
    a rim with an odd number of segments is not the front half's mirror,
    so it survived the projected-line dedupe and came out as dashes
    printed on top of the solid bottom line."""
    def direction(a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy)
        if n < 1e-12:
            return None
        ux, uy = dx / n, dy / n
        if ux < -1e-12 or (abs(ux) <= 1e-12 and uy < 0):
            ux, uy = -ux, -uy
        # half-degree buckets over (-90, 90]
        return round(math.degrees(math.atan2(uy, ux)) * 2), n
    buckets = {}
    for a, b in visible:
        d = direction(a, b)
        if d is not None:
            buckets.setdefault(d[0], []).append((a, b))
    out = []
    for a, b in hidden:
        d = direction(a, b)
        if d is None:
            continue
        key, n = d
        sx, sy = (b[0] - a[0]) / n, (b[1] - a[1]) / n
        spans = []
        for k in (key - 1, key, key + 1, key - 360, key + 360):
            for p, q in buckets.get(k, ()):
                if abs((p[0] - a[0]) * sy - (p[1] - a[1]) * sx) > tol or \
                        abs((q[0] - a[0]) * sy - (q[1] - a[1]) * sx) > tol:
                    continue
                t0 = (p[0] - a[0]) * sx + (p[1] - a[1]) * sy
                t1 = (q[0] - a[0]) * sx + (q[1] - a[1]) * sy
                lo, hi = min(t0, t1), max(t0, t1)
                if hi > 0.0 and lo < n:
                    spans.append((max(lo, 0.0), min(hi, n)))
        if not spans:
            out.append((a, b))
            continue
        spans.sort()
        t = 0.0

        def piece(t0, t1):
            return ((a[0] + sx * t0, a[1] + sy * t0),
                    (a[0] + sx * t1, a[1] + sy * t1))
        for lo, hi in spans:
            if lo - t > tol:
                out.append(piece(t, lo))
            t = max(t, hi)
        if n - t > tol:
            out.append(piece(t, n))
    return out


def _edge_key(p, q):
    a = (round(p[0], 4), round(p[1], 4), round(p[2], 4))
    b = (round(q[0], 4), round(q[1], 4), round(q[2], 4))
    return (a, b) if a <= b else (b, a)


# ------------------------------------------------------------- dimensions

def overall_dimensions(bounds, gap):
    """Width and height dimensions of a view's bounding box, placed
    *gap* mm (model units) below and to the right of it:
    [{"a": (u, v), "b": (u, v), "text", "offset": (du, dv)}]."""
    u0, v0, u1, v1 = bounds
    return [
        {"a": (u0, v0), "b": (u1, v0), "text": f"{u1 - u0:.4g}",
         "offset": (0.0, -gap)},
        {"a": (u1, v0), "b": (u1, v1), "text": f"{v1 - v0:.4g}",
         "offset": (gap, 0.0)},
    ]


# ------------------------------------------------------------------ sheet

def nice_scale(model_w, model_h, box_w, box_h):
    """The largest standard scale at which model_w x model_h fits in
    box_w x box_h (sheet mm)."""
    for s in SCALES:
        if model_w * s <= box_w and model_h * s <= box_h:
            return s
    return SCALES[-1]


def scale_label(s):
    return f"{s:g}:1" if s >= 1 else f"1:{1 / s:g}"


def layout(tris, *, sheet="A4", views=("Front", "Top", "Right",
                                       "Isometric"),
           dimensions=True, section_axis=None, title="Part", scale=None,
           info=None, hidden_lines=True, unit="mm"):
    """Everything the exporters need: the sheet, the scale, every view
    placed on it (sheet mm, y up from the bottom-left corner), the
    dimensions, the optional section and the title block text. *unit*
    is the document's (the model's numbers; the sheet stays mm) and
    only names the title block's UNITS cell."""
    from .units import symbol
    sheet_w, sheet_h = SHEETS[sheet]
    margin = 10.0
    block_h = 24.0                            # the title block strip
    inner_w = sheet_w - 2 * margin
    inner_h = sheet_h - 2 * margin - block_h
    info = info or (shading.analyse(tris) if tris else None)
    drawn = {name: view_lines(tris, name, info, hidden_lines)
             for name in views}
    if section_axis and tris:
        sec = section.section(tris, section_axis)
    else:
        sec = None
    # third-angle grid: Top over Front, Right beside Front, the
    # isometric (and a section) in the remaining corner
    def size(name):
        b = drawn[name]["bounds"]
        return b[2] - b[0], b[3] - b[1]
    front_w, front_h = size("Front") if "Front" in drawn else (0, 0)
    top_h = size("Top")[1] if "Top" in drawn else 0
    right_w = size("Right")[0] if "Right" in drawn else 0
    extra_w = max(size(n)[0] for n in drawn if n not in
                  ("Front", "Top", "Right")) if any(
        n not in ("Front", "Top", "Right") for n in drawn) else 0
    if sec is not None and sec["bounds"]:
        b = sec["bounds"]
        extra_w = max(extra_w, b[2] - b[0])
    gap_frac = 0.35                           # gap between views
    cols = [front_w, right_w, extra_w]
    cols = [c for c in cols if c > 0] or [max(size(n)[0] for n in drawn)]
    rows_h = [front_h, top_h] if top_h else [front_h or max(
        size(n)[1] for n in drawn)]
    model_w = sum(cols) * (1 + gap_frac * (len(cols) - 1))
    model_h = sum(rows_h) * (1 + gap_frac * (len(rows_h) - 1))
    dim_room = 1.25 if dimensions else 1.0
    s = scale or nice_scale(model_w * dim_room, model_h * dim_room,
                            inner_w, inner_h)
    gap = max(cols) * gap_frac
    # placements: each view's bounds origin lands at (x, y) on the sheet
    placed = []
    x = margin + (inner_w - model_w * s * dim_room) / 2 + gap * s * 0.3
    y = margin + block_h + (inner_h - model_h * s * dim_room) / 2 \
        + gap * s * 0.3
    col_x = [x]
    for c in cols[:-1]:
        col_x.append(col_x[-1] + (c + gap) * s)
    row_y = [y, y + (front_h + gap) * s]
    order = [n for n in ("Front", "Top", "Right") if n in drawn] + \
        [n for n in drawn if n not in ("Front", "Top", "Right")]
    col_of = {"Front": 0, "Top": 0, "Right": 1}
    for name in order:
        b = drawn[name]["bounds"]
        col = col_of.get(name, min(2, len(col_x) - 1))
        if name not in col_of and right_w == 0:
            col = min(1, len(col_x) - 1)
        row = 1 if name == "Top" else 0
        if name not in col_of and top_h:
            row = 1                           # the isometric sits high
        placed.append(dict(
            name=name, x=col_x[col], y=row_y[row] if row < len(row_y)
            else row_y[0], lines=drawn[name],
            dims=overall_dimensions(b, gap * 0.35) if dimensions and
            name in ("Front", "Top", "Right") else []))
    if sec is not None and sec["bounds"]:
        col = min(2, len(col_x) - 1)
        placed.append(dict(name=f"Section {section_axis.upper()}",
                           x=col_x[col], y=row_y[0], section=sec,
                           lines=None, dims=[]))
    return dict(sheet=sheet, width=sheet_w, height=sheet_h,
                margin=margin, block_h=block_h, scale=s,
                scale_label=scale_label(s), title=title, views=placed,
                units=symbol(unit))


def to_sheet(view, u, v, scale):
    """Model (u, v) of a placed *view* -> sheet mm."""
    b = view["lines"]["bounds"] if view.get("lines") else \
        view["section"]["bounds"]
    return view["x"] + (u - b[0]) * scale, view["y"] + (v - b[1]) * scale


# ---------------------------------------------------------------- circles

#: a chord turning more than this between two neighbours is a polygon's
#: corner, not a tessellated circle (a hex nut is not Ø-dimensioned)
MAX_TURN = 36.5
#: how far (fraction of the radius) a vertex may sit off the fitted circle
CIRCLE_TOL = 0.02


def _pkey(p):
    return (round(p[0], 4), round(p[1], 4))


def _chains(segments):
    """Polylines through vertices where exactly two segments meet:
    [(points, segment indices, closed)]. A round edge seen end-on is one
    such chain of short chords; a junction (a line meeting the circle)
    breaks it into arcs, which `find_circles` joins back up."""
    adj, unique = {}, {}
    for i, (a, b) in enumerate(segments):
        ka, kb = _pkey(a), _pkey(b)
        if ka == kb:
            continue
        pair = (ka, kb) if ka <= kb else (kb, ka)
        if pair in unique:
            continue
        unique[pair] = i
        adj.setdefault(ka, []).append((i, kb))
        adj.setdefault(kb, []).append((i, ka))
    used = set()

    def walk(cur, prev):
        out = []
        while True:
            nbrs = adj.get(cur, ())
            if len(nbrs) != 2:
                return out
            seg, nxt = nbrs[0] if nbrs[0][0] != prev else nbrs[1]
            if seg in used:
                return out
            used.add(seg)
            out.append((seg, nxt))
            prev, cur = seg, nxt

    chains = []
    for (ka, kb), seed in unique.items():
        if seed in used:
            continue
        used.add(seed)
        fwd = walk(kb, seed)
        closed = bool(fwd) and fwd[-1][1] == ka
        back = [] if closed else walk(ka, seed)
        points = [p for _s, p in reversed(back)] + [ka, kb] + \
            [p for _s, p in fwd]
        segs = [s for s, _p in reversed(back)] + [seed] + \
            [s for s, _p in fwd]
        if closed:
            points.pop()
        chains.append((points, segs, closed))
    return chains


def fit_circle(points):
    """Least-squares (Kåsa) circle through *points*: ((cx, cy), r), or
    None when they are collinear."""
    n = len(points)
    if n < 3:
        return None
    mx = sum(p[0] for p in points) / n
    my = sum(p[1] for p in points) / n
    suu = suv = svv = suuu = svvv = suvv = svuu = 0.0
    for x, y in points:
        u, v = x - mx, y - my
        uu, vv = u * u, v * v
        suu += uu
        svv += vv
        suv += u * v
        suuu += uu * u
        svvv += vv * v
        suvv += u * vv
        svuu += v * uu
    det = suu * svv - suv * suv
    if abs(det) < 1e-12:
        return None
    b1 = 0.5 * (suuu + suvv)
    b2 = 0.5 * (svvv + svuu)
    uc = (b1 * svv - b2 * suv) / det
    vc = (suu * b2 - suv * b1) / det
    r = math.sqrt(uc * uc + vc * vc + (suu + svv) / n)
    return (uc + mx, vc + my), r


def _arc(points, closed):
    """((cx, cy), r, start°, sweep°) when *points* lie on a circle as
    evenly turning chords, else None."""
    if len(points) < (8 if closed else 4):
        return None
    got = fit_circle(points)
    if got is None:
        return None
    (cx, cy), r = got
    if r < 1e-6:
        return None
    if max(abs(math.hypot(x - cx, y - cy) - r) for x, y in points) \
            > CIRCLE_TOL * r:
        return None
    angles = [math.degrees(math.atan2(y - cy, x - cx)) for x, y in points]
    if closed:
        angles.append(angles[0])
    steps = [((b - a + 180.0) % 360.0) - 180.0
             for a, b in zip(angles, angles[1:])]
    if not steps or any(abs(s) > MAX_TURN or abs(s) < 1e-6 for s in steps):
        return None
    if any((s > 0) != (steps[0] > 0) for s in steps):
        return None
    sweep = sum(steps)
    if not closed and abs(sweep) < 30.0:
        return None
    start = angles[0]
    if sweep < 0:                       # report counter-clockwise
        start, sweep = start + sweep, -sweep
    return (cx, cy), r, start % 360.0, min(sweep, 360.0)


def find_circles(segments):
    """Round edges among 2D *segments* [((u, v), (u, v))]: a hole or a
    boss seen end-on is a closed ring of short equal chords, a fillet an
    open run of them. Arcs of one circle broken by a junction are merged.
    Returns [{"centre": (u, v), "r", "closed", "start", "sweep",
    "segments": [indices]}], largest first."""
    found = []
    for points, segs, closed in _chains(segments):
        arc = _arc(points, closed)
        if arc is None:
            continue
        centre, r, start, sweep = arc
        for other in found:
            if math.hypot(other["centre"][0] - centre[0],
                          other["centre"][1] - centre[1]) \
                    <= CIRCLE_TOL * r * 2 \
                    and abs(other["r"] - r) <= CIRCLE_TOL * r * 2:
                other["segments"] += segs
                other["sweep"] = min(other["sweep"] + sweep, 360.0)
                other["closed"] = other["closed"] or \
                    other["sweep"] >= 359.0
                break
        else:
            found.append({"centre": centre, "r": r, "closed": closed,
                          "start": start, "sweep": sweep,
                          "segments": list(segs)})
    found.sort(key=lambda c: -c["r"])
    return found


def merge_collinear(segments, sin_tol=1e-4):
    """*segments* with every run of collinear pieces joined into one: a
    tessellated cylinder's rim seen side-on is dozens of tiny chords on
    one line, which would flood the snap points and the DXF."""
    out = []
    for points, _segs, closed in _chains(segments):
        pts = points + [points[0]] if closed else points
        keep = [pts[0]]
        for b, c in zip(pts[1:-1], pts[2:]):
            a = keep[-1]
            ux, uy = b[0] - a[0], b[1] - a[1]
            vx, vy = c[0] - b[0], c[1] - b[1]
            lu, lv = math.hypot(ux, uy), math.hypot(vx, vy)
            if lu * lv > 0 and abs(ux * vy - uy * vx) <= sin_tol * lu * lv \
                    and ux * vx + uy * vy > 0:
                continue                         # b is mid-line: drop it
            keep.append(b)
        keep.append(pts[-1])
        out += list(zip(keep, keep[1:]))
    return out


def clip_to_circle(segments, centre, radius):
    """The parts of *segments* inside the circle — a detail view's
    content."""
    cx, cy = centre
    out = []
    for a, b in segments:
        dx, dy = b[0] - a[0], b[1] - a[1]
        fx, fy = a[0] - cx, a[1] - cy
        qa = dx * dx + dy * dy
        if qa < 1e-18:
            continue
        qb = 2.0 * (fx * dx + fy * dy)
        qc = fx * fx + fy * fy - radius * radius
        disc = qb * qb - 4.0 * qa * qc
        if disc <= 0.0:
            if qc < 0.0:
                out.append((a, b))
            continue
        root = math.sqrt(disc)
        lo = max(0.0, (-qb - root) / (2.0 * qa))
        hi = min(1.0, (-qb + root) / (2.0 * qa))
        if hi - lo < 1e-9:
            continue
        out.append(((a[0] + dx * lo, a[1] + dy * lo),
                    (a[0] + dx * hi, a[1] + dy * hi)))
    return out


def hatch_segments(outlines, step=2.5, angle=45.0):
    """Section hatching: lines at *angle* every *step*, inside the closed
    *outlines* [[(x, y), ...]] by the even-odd rule, so holes stay
    clear. Returned as segments, the same for the screen and the DXF."""
    polys = [list(o) for o in outlines if len(o) >= 3]
    if not polys or step <= 0:
        return []
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    # turn the outlines so the hatch runs horizontally, scan, turn back
    rot = [[(x * ca + y * sa, -x * sa + y * ca) for x, y in poly]
           for poly in polys]
    ys = [p[1] for poly in rot for p in poly]
    y, top = (math.floor(min(ys) / step) + 0.5) * step, max(ys)
    out = []
    while y < top:
        xs = []
        for poly in rot:
            for (xa, ya), (xb, yb) in zip(poly, poly[1:] + poly[:1]):
                if (ya <= y < yb) or (yb <= y < ya):
                    xs.append(xa + (y - ya) * (xb - xa) / (yb - ya))
        xs.sort()
        for x0, x1 in zip(xs[0::2], xs[1::2]):
            out.append(((x0 * ca - y * sa, x0 * sa + y * ca),
                        (x1 * ca - y * sa, x1 * sa + y * ca)))
        y += step
    return out


# ------------------------------------------------------------ title block

#: the title block's fields, in the order the editor lists them
TITLE_FIELDS = (
    ("title", "Title"), ("number", "Drawing no."),
    ("material", "Material"), ("finish", "Finish"), ("mass", "Mass"),
    ("company", "Company"), ("drawn", "Drawn by"), ("date", "Date"),
    ("checked", "Checked by"), ("approved", "Approved by"),
    ("revision", "Revision"), ("tolerance", "General tolerances"),
    ("sheet_no", "Sheet"),
)
#: its size (mm): ISO 7200's 180 mm width, in the frame's bottom-right
TITLE_W, TITLE_H = 180.0, 42.0


def title_block_cells(fields, scale_label, sheet, units="mm"):
    """The title block's cells relative to its top-left corner (mm, y
    DOWN): [{"rect": (x, y, w, h), "label", "text", "size", "bold",
    "key"}]. Painted by the Blueprint window and by `drawing_export`, so
    a drawing saved either way carries the same block."""
    def f(key, default=""):
        value = fields.get(key)
        return default if value in (None, "") else str(value)
    row = 7.5
    spec = (
        ((0, 0, 70, 12), "COMPANY", f("company"), 3.6, True, "company"),
        ((70, 0, 110, 12), "TITLE", f("title"), 4.6, True, "title"),
        ((0, 12, 45, row), "DRAWN", f("drawn"), 2.5, False, "drawn"),
        ((45, 12, 25, row), "DATE", f("date"), 2.5, False, "date"),
        ((0, 19.5, 70, row), "CHECKED", f("checked"), 2.5, False,
         "checked"),
        ((0, 27, 70, row), "APPROVED", f("approved"), 2.5, False,
         "approved"),
        ((0, 34.5, 70, row), "GENERAL TOLERANCES", f("tolerance"), 2.5,
         False, "tolerance"),
        ((70, 12, 55, row), "MATERIAL", f("material"), 2.5, False,
         "material"),
        ((125, 12, 55, row), "FINISH", f("finish"), 2.5, False, "finish"),
        ((70, 19.5, 55, row), "MASS", f("mass"), 2.5, False, "mass"),
        ((125, 19.5, 55, row), "DWG NO.", f("number"), 2.8, True,
         "number"),
        ((70, 27, 24, row), "SCALE", scale_label, 2.5, False, "scale"),
        ((94, 27, 18, row), "SIZE", sheet, 2.5, False, "size"),
        ((112, 27, 18, row), "UNITS", units, 2.5, False, "units"),
        ((130, 27, 28, row), "SHEET", f("sheet_no", "1 / 1"), 2.5, False,
         "sheet_no"),
        ((158, 27, 22, 15), "THIRD ANGLE", "", 2.5, False, "projection"),
        ((70, 34.5, 24, row), "REV", f("revision"), 2.8, True, "revision"),
        ((94, 34.5, 64, row), "", "Drawn in KherveCAD", 2.0, False,
         "credit"),
    )
    return [dict(rect=r, label=label, text=text, size=size, bold=bold,
                 key=key) for r, label, text, size, bold, key in spec]


def projection_symbol(x, y, w, h):
    """ISO third-angle symbol centred in the box (y DOWN): a truncated
    cone's side view, large end left, and its end view — two circles —
    on the right, where third-angle puts the view from the right.
    Returns (lines [((x, y), (x, y))], circles [((cx, cy), r)],
    centre lines [((x, y), (x, y))])."""
    size = min(h * 0.62, w / 3.2)
    cy = y + h / 2.0
    left = x + w / 2.0 - size * 1.45
    big, small = size / 2.0, size / 4.0
    right = left + size * 1.2
    lines = [((left, cy - big), (left, cy + big)),
             ((right, cy - small), (right, cy + small)),
             ((left, cy - big), (right, cy - small)),
             ((left, cy + big), (right, cy + small))]
    ccx = right + size * 0.35 + big
    circles = [((ccx, cy), big), ((ccx, cy), small)]
    centre = [((left - size * 0.15, cy), (ccx + big + size * 0.15, cy)),
              ((ccx, cy - big - size * 0.15), (ccx, cy + big + size * 0.15))]
    return lines, circles, centre
