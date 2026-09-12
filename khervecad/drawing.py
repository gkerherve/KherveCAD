"""2D engineering drawings of the model (Qt-free geometry).

What SolidWorks calls a *drawing*: the model projected into standard
third-angle views — Front, Top, Right and an isometric — with visible
edges solid and hidden edges dashed, overall dimensions, an optional
hatched section through the middle, laid out on an A4/A3 sheet at a
nice scale with a title block. `drawing_export.py` paints the result
to PDF/SVG/PNG and writes DXF; `drawing_dialog.py` is File ▸ Make
Drawing…

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
          "Letter": (279.4, 215.9)}
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

    def __init__(self, tris2d, bounds, cells):
        u0, v0, u1, v1 = bounds
        span = max(u1 - u0, v1 - v0, 1e-9)
        self.u0, self.v0 = u0, v0
        self.step = span / cells
        self.w = int((u1 - u0) / self.step) + 2
        self.h = int((v1 - v0) / self.step) + 2
        inf = float("inf")
        self.depth = [inf] * (self.w * self.h)
        for (a, b, c) in tris2d:
            self._raster(a, b, c)

    def _raster(self, a, b, c):
        s, u0, v0, w, h = self.step, self.u0, self.v0, self.w, self.h
        det = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(det) < 1e-15:
            return
        i0 = max(int((min(a[0], b[0], c[0]) - u0) / s), 0)
        i1 = min(int((max(a[0], b[0], c[0]) - u0) / s) + 1, w - 1)
        j0 = max(int((min(a[1], b[1], c[1]) - v0) / s), 0)
        j1 = min(int((max(a[1], b[1], c[1]) - v0) / s) + 1, h - 1)
        depth = self.depth
        for j in range(j0, j1 + 1):
            py = v0 + (j + 0.5) * s
            row = j * w
            for i in range(i0, i1 + 1):
                px = u0 + (i + 0.5) * s
                w0 = ((b[1] - c[1]) * (px - c[0])
                      + (c[0] - b[0]) * (py - c[1])) / det
                w1 = ((c[1] - a[1]) * (px - c[0])
                      + (a[0] - c[0]) * (py - c[1])) / det
                w2 = 1.0 - w0 - w1
                if w0 < -1e-6 or w1 < -1e-6 or w2 < -1e-6:
                    continue
                d = w0 * a[2] + w1 * b[2] + w2 * c[2]
                if d < depth[row + i]:
                    depth[row + i] = d

    def at(self, u, v):
        i = int((u - self.u0) / self.step)
        j = int((v - self.v0) / self.step)
        if 0 <= i < self.w and 0 <= j < self.h:
            return self.depth[j * self.w + i]
        return float("inf")


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
    grid = DepthGrid(tris2d, bounds, GRID)
    # the candidate edges: creases (plus borders) and this view's silhouette
    facing = [_dot(n, forward) < 0.0 for n in info.normals]
    edges = {}
    for face, segs in info.creases.items():
        for p, q in segs:
            edges[_edge_key(p, q)] = (p, q)
    for face, segs in shading.silhouette(info, facing).items():
        for p, q in segs:
            edges[_edge_key(p, q)] = (p, q)
    tol = size * DEPTH_TOL
    # edges that project onto the same line (a box's back edges under
    # its front edges) are one line in the drawing: keep the front-most
    projected = {}
    for p, q in edges.values():
        a, b = project(p, view), project(q, view)
        key = tuple(sorted(((round(a[0], 4), round(a[1], 4)),
                            (round(b[0], 4), round(b[1], 4)))))
        if key[0] == key[1]:
            continue                             # seen end-on: a point
        depth = a[2] + b[2]
        if key not in projected or depth < projected[key][0]:
            projected[key] = (depth, a, b)
    visible, hidden = [], []
    for _depth, a, b in projected.values():
        # sample along the edge: in front of (or on) the surface, or behind
        runs = []
        state = None
        for n in range(SAMPLES + 1):
            t = n / SAMPLES
            u = a[0] + (b[0] - a[0]) * t
            v = a[1] + (b[1] - a[1]) * t
            d = a[2] + (b[2] - a[2]) * t
            seen = d <= grid.at(u, v) + tol
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
        for seen, t0, t1 in merged:
            if t1 - t0 < 1e-9:
                continue
            if not seen and not hidden_lines:
                continue
            seg = ((a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0),
                   (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1))
            (visible if seen else hidden).append(seg)
    return {"visible": visible, "hidden": hidden, "bounds": bounds}


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
           info=None, hidden_lines=True):
    """Everything the exporters need: the sheet, the scale, every view
    placed on it (sheet mm, y up from the bottom-left corner), the
    dimensions, the optional section and the title block text."""
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
                scale_label=scale_label(s), title=title, views=placed)


def to_sheet(view, u, v, scale):
    """Model (u, v) of a placed *view* -> sheet mm."""
    b = view["lines"]["bounds"] if view.get("lines") else \
        view["section"]["bounds"]
    return view["x"] + (u - b[0]) * scale, view["y"] + (v - b[1]) * scale
