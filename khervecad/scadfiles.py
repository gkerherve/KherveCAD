"""Geometry OpenSCAD reads from files, as tree nodes: ``surface()``
height maps and ``import()`` of 2D SVG / DXF drawings.

- **surface** — a height map from a ``.dat`` text matrix (rows along Y,
  columns along X, a value per cell) or a picture (luminance 0..100,
  ``invert`` flips it). The solid runs down to one below the lowest
  value (0 for a picture of pure black), as OpenSCAD builds it. A
  lithophane, a terrain tile, an embossed logo.
- **import_2d** — the outlines of an SVG or DXF file (svgdxf.py) as a
  2D shape to extrude: a logo, a laser-cut profile, a gasket drawn in a
  2D CAD program. ``center``, ``dpi`` (pixel-sized SVGs), ``layer`` and
  ``id`` are OpenSCAD's own parameters; x/y place it.

Both compile to OpenSCAD's own calls — `surface(file = …)` and
`translate([x, y]) import(file = …)` — and scadparse reads them back
(scadparse._b_import sends .svg/.dxf here, `surface` has its builder).
File paths save relative to the document like a mesh's
(meshimport.PATH_PARAMS). The preview samples a large picture down to
`PREVIEW_CELLS` per side; the exact render uses every pixel.

Registered from organic.py; no package imports at module level.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os

SHAPE_2D = "2d"
SHAPE_3D = "3d"

#: most cells a side the built-in preview of a surface uses
PREVIEW_CELLS = 160
#: extensions import_2d reads
DRAWING_EXTS = (".svg", ".dxf")
#: extensions surface reads as pictures (anything else is a .dat matrix)
PICTURE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".gif")

NODE_TYPES = {
    "surface": dict(
        label="Surface (height map)", category=SHAPE_3D,
        icon="mdi.image-filter-hdr",
        params=dict(file="", center=False, invert=False, convexity=1),
        schema=[("file", "Height map (.dat or picture)", "str", None, None),
                ("center", "Center", "bool", None, None),
                ("invert", "Invert (pictures)", "bool", None, None),
                ("convexity", "Convexity", "int", 1, 100)]),
    "import_2d": dict(
        label="Import 2D drawing (SVG / DXF)", category=SHAPE_2D,
        icon="mdi.svg",
        params=dict(path="", x=0.0, y=0.0, center=False, dpi=72.0,
                    layer="", id="", segments=32),
        schema=[("path", "Drawing file (.svg / .dxf)", "str", None, None),
                ("x", "X", "float", -1e6, 1e6),
                ("y", "Y", "float", -1e6, 1e6),
                ("center", "Center", "bool", None, None),
                ("dpi", "DPI (pixel-sized SVG)", "float", 1.0, 10000.0),
                ("layer", "Layer (empty = all)", "str", None, None),
                ("id", "SVG element id (empty = all)", "str", None, None),
                ("segments", "Curve segments ($fn)", "int", 3, 512)]),
}
TYPES = frozenset(NODE_TYPES)
LEAVES = frozenset(NODE_TYPES)
#: params mesh.rp keeps as text
TEXT_PARAMS = frozenset({"file", "layer", "id"})
#: path params saved relative to the document
PATH_PARAMS = {"surface": ("file",), "import_2d": ("path",)}


def preamble(root) -> list:
    return []


# --------------------------------------------------------------- reading

def read_heights(path, invert=False):
    """The height grid of a surface file: rows[y][x], y = 0 the first
    .dat row / the BOTTOM picture row. Raises ValueError."""
    lower = str(path).lower()
    if lower.endswith(PICTURE_EXTS):
        from . import paint
        picture = paint.load(path)
        if picture is None:
            raise ValueError(f"cannot read picture {os.path.basename(path)}")
        rows = []
        for row in reversed(picture.rows):         # the picture's top is +y
            out = []
            for r, g, b in row:
                lum = (0.2126 * _linear(r) + 0.7152 * _linear(g)
                       + 0.0722 * _linear(b))
                lum = _gamma(lum)
                out.append(100.0 * ((1.0 - lum) if invert else lum))
            rows.append(out)
        return rows
    rows = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            try:
                rows.append([float(v) for v in line.replace(",", " ").split()])
            except ValueError:
                raise ValueError(f"{os.path.basename(path)}: not a number "
                                 f"matrix") from None
    if not rows:
        raise ValueError(f"{os.path.basename(path)} holds no heights")
    width = min(len(r) for r in rows)
    return [r[:width] for r in rows]


def _linear(channel):
    c = channel / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gamma(value):
    return value * 12.92 if value <= 0.0031308 else \
        1.055 * value ** (1 / 2.4) - 0.055


_HEIGHT_CACHE = {}


def heights(path, invert=False):
    """read_heights cached by path, mtime and invert."""
    try:
        key = (str(path), os.path.getmtime(path), bool(invert))
    except OSError:
        raise ValueError(f"file not found: {path}") from None
    hit = _HEIGHT_CACHE.get(key)
    if hit is None:
        hit = read_heights(path, invert)
        if len(_HEIGHT_CACHE) > 8:
            _HEIGHT_CACHE.clear()
        _HEIGHT_CACHE[key] = hit
    return hit


def surface_mesh(grid, center=False, cells=PREVIEW_CELLS):
    """A closed solid over a height grid: the top surface, walls round
    the edge and a flat base one below the lowest height (never above
    0). A grid wider than *cells* is sampled down."""
    rows, cols = len(grid), len(grid[0]) if grid else 0
    if rows < 2 or cols < 2:
        return []
    step_y = max((rows - 1) / (cells - 1), 1.0) if rows > cells else 1.0
    step_x = max((cols - 1) / (cells - 1), 1.0) if cols > cells else 1.0
    ys = sorted({min(int(round(k * step_y)), rows - 1)
                 for k in range(int((rows - 1) / step_y) + 1)} | {rows - 1})
    xs = sorted({min(int(round(k * step_x)), cols - 1)
                 for k in range(int((cols - 1) / step_x) + 1)} | {cols - 1})
    lowest = min(min(r) for r in grid)
    base = min(0.0, lowest - 1.0)
    ox = -(cols - 1) / 2.0 if center else 0.0
    oy = -(rows - 1) / 2.0 if center else 0.0

    def top(i, j):
        return (xs[i] + ox, ys[j] + oy, grid[ys[j]][xs[i]])

    def bottom(i, j):
        return (xs[i] + ox, ys[j] + oy, base)
    tris = []
    nx, ny = len(xs), len(ys)
    for j in range(ny - 1):
        for i in range(nx - 1):
            a, b = top(i, j), top(i + 1, j)
            c, d = top(i + 1, j + 1), top(i, j + 1)
            tris += [(a, b, c), (a, c, d)]            # up, counter-clockwise
            a, b = bottom(i, j), bottom(i + 1, j)
            c, d = bottom(i + 1, j + 1), bottom(i, j + 1)
            tris += [(a, c, b), (a, d, c)]            # down
    for i in range(nx - 1):                           # front (y min), back
        tris += [(bottom(i, 0), bottom(i + 1, 0), top(i + 1, 0)),
                 (bottom(i, 0), top(i + 1, 0), top(i, 0))]
        j = ny - 1
        tris += [(bottom(i + 1, j), bottom(i, j), top(i, j)),
                 (bottom(i + 1, j), top(i, j), top(i + 1, j))]
    for j in range(ny - 1):                           # left (x min), right
        tris += [(bottom(0, j + 1), bottom(0, j), top(0, j)),
                 (bottom(0, j + 1), top(0, j), top(0, j + 1))]
        i = nx - 1
        tris += [(bottom(i, j), bottom(i, j + 1), top(i, j + 1)),
                 (bottom(i, j), top(i, j + 1), top(i, j))]
    return tris


def drawing_outlines(node, env=None):
    """import_2d's outlines, placed (x/y, center)."""
    from . import mesh, svgdxf
    p = node.params
    path = str(p.get("path", "")).strip()
    if not path or not os.path.isfile(path):
        return []
    segments = max(int(mesh.rv(p.get("segments", 32), env, 32)), 3)
    try:
        outs = _drawing_cache(path, segments,
                              mesh.rv(p.get("dpi", 72.0), env, 72.0),
                              str(p.get("layer", "") or ""),
                              str(p.get("id", "") or ""))
    except Exception:
        return []
    dx, dy = mesh.rv(p.get("x", 0.0), env), mesh.rv(p.get("y", 0.0), env)
    if p.get("center") and outs:
        pts = [pt for o in outs for pt in o]
        cx = (min(x for x, _ in pts) + max(x for x, _ in pts)) / 2
        cy = (min(y for _, y in pts) + max(y for _, y in pts)) / 2
        dx, dy = dx - cx, dy - cy
    return [[(x + dx, y + dy) for x, y in o] for o in outs]


_DRAWING_CACHE = {}


def _drawing_cache(path, segments, dpi, layer, ident):
    from . import svgdxf
    key = (path, os.path.getmtime(path), segments, dpi, layer, ident)
    hit = _DRAWING_CACHE.get(key)
    if hit is None:
        hit = svgdxf.outlines(path, segments, dpi, layer, ident)
        if len(_DRAWING_CACHE) > 16:
            _DRAWING_CACHE.clear()
        _DRAWING_CACHE[key] = hit
    return hit


# ---------------------------------------------------------------- codegen

def statement(node, fmt, fn) -> str:
    from .model import scad_str
    p = node.params
    if node.type == "surface":
        args = [f"file = {scad_str(str(p.get('file', '')))}"]
        if p.get("center"):
            args.append("center = true")
        if p.get("invert"):
            args.append("invert = true")
        conv = p.get("convexity", 1)
        if conv not in (1, 1.0):
            args.append(f"convexity = {fmt(conv)}")
        return f"surface({', '.join(args)})"
    args = [f"file = {scad_str(str(p.get('path', '')))}"]
    if p.get("center"):
        args.append("center = true")
    dpi = p.get("dpi", 72.0)
    if str(p.get("path", "")).lower().endswith(".svg") and \
            dpi not in (72, 72.0):
        args.append(f"dpi = {fmt(dpi)}")
    for key in ("layer", "id"):
        if str(p.get(key, "") or ""):
            args.append(f"{key} = {scad_str(str(p[key]))}")
    args.append(f"$fn = {fmt(p.get('segments', 32))}")
    return (f"translate([{fmt(p.get('x', 0.0))}, {fmt(p.get('y', 0.0))}]) "
            f"import({', '.join(args)})")


# ----------------------------------------------------------------- import

def _b_surface(parser, positional, named):
    from .model import CadNode
    from .scadparse import _num
    conv = _num(named.get("convexity", 1), 1.0)
    return CadNode("surface", "Surface", dict(
        file=str(named.get("file", positional[0] if positional else "")),
        center=bool(named.get("center", False)),
        invert=bool(named.get("invert", False)),
        convexity=conv if isinstance(conv, str) else max(int(conv), 1)))


def build_import_2d(parser, positional, named, path):
    from .model import CadNode
    from .scadparse import _num
    segments = _num(named.get("$fn", 32), 32.0)
    return CadNode("import_2d", "Import " + os.path.basename(path), dict(
        path=path, x=0.0, y=0.0, center=bool(named.get("center", False)),
        dpi=_num(named.get("dpi", 72.0), 72.0),
        layer=str(named.get("layer", "") or ""),
        id=str(named.get("id", "") or ""),
        segments=segments if isinstance(segments, str)
        else max(int(segments), 3)))


BUILDERS = {"surface": _b_surface}


# ------------------------------------------------------------- validation

def check(node, env):
    p = node.params
    if node.type == "surface":
        path = str(p.get("file", "")).strip()
        if not path:
            return "surface: choose a height map (.dat or a picture)"
        if not os.path.isfile(path):
            return f"file not found: {path}"
        try:
            grid = heights(path, bool(p.get("invert")))
        except ValueError as exc:
            return f"surface: {exc}"
        if len(grid) < 2 or len(grid[0]) < 2:
            return "surface: needs at least 2 x 2 values"
        return None
    path = str(p.get("path", "")).strip()
    if not path:
        return "import: choose an SVG or DXF drawing"
    if not path.lower().endswith(DRAWING_EXTS):
        return "import: 2D drawings are .svg or .dxf"
    if not os.path.isfile(path):
        return f"file not found: {path}"
    if not drawing_outlines(node, env):
        what = " on that layer" if p.get("layer") else ""
        return f"import: no closed outlines{what} in " \
               f"{os.path.basename(path)}"
    return None


# ----------------------------------------------------------- tessellation

def tess(node, env, color, sel, selected):
    from . import mesh
    if node.type == "surface":
        p = node.params
        path = str(p.get("file", "")).strip()
        try:
            grid = heights(path, bool(p.get("invert")))
        except (ValueError, OSError):
            return []
        return mesh._emit(surface_mesh(grid, bool(p.get("center"))),
                          color, selected)
    tris = []
    loops = mesh._oriented(node, mesh.node_outlines(node, env))
    for solid, holes in mesh.outline_regions(loops):
        tris.extend(((a[0], a[1], 0.0), (b[0], b[1], 0.0),
                     (c[0], c[1], 0.0))
                    for a, b, c in mesh._caps(solid, holes))
    return mesh._emit(tris, color, selected)
