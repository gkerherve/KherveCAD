"""2D outlines from SVG and DXF files — what OpenSCAD's ``import()``
reads for a 2D shape (a logo to extrude, a laser-cut profile, a
drawing's outline). Qt-free, standard library only.

SVG: paths (every command, relative and absolute, arcs included),
rect (rounded corners too), circle, ellipse, polygon and polyline, with
nested ``transform``s. User units become millimetres through the
document's width/height and viewBox, or through ``dpi`` when the size
is in pixels; y is flipped so the drawing reads upright, the lower-left
of the page at the origin, as OpenSCAD places it. ``id`` picks one
element; ``layer`` one Inkscape layer (a group's label or id).

DXF: LWPOLYLINE and POLYLINE (bulges become arcs), LINE, ARC, CIRCLE,
ELLIPSE and SPLINE, on every layer or one. Loose segments (lines and
arcs drawn end to end) are chained into closed outlines.

Curves are flattened to *segments* straight pieces per full turn (the
node's own $fn), so an arc reads as smooth as a circle of the same
setting. Outlines come back as lists of (x, y); orientation and holes
are left to mesh._oriented, which decides by nesting.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET

#: OpenSCAD's default resolution for pixel-sized SVG documents
DEFAULT_DPI = 72.0

_UNITS_MM = {"mm": 1.0, "cm": 10.0, "in": 25.4, "pt": 25.4 / 72.0,
             "pc": 25.4 / 6.0, "m": 1000.0}


# ================================================================== SVG

def _length(text, dpi):
    """An SVG length -> (mm, had_a_unit)."""
    match = re.match(r"\s*([-+]?[\d.]+(?:[eE][-+]?\d+)?)\s*([a-z%]*)",
                     str(text or ""))
    if not match:
        return None, False
    value, unit = float(match.group(1)), match.group(2)
    if unit in _UNITS_MM:
        return value * _UNITS_MM[unit], True
    return value * 25.4 / dpi, False             # px or unitless


def _mat_mul(a, b):
    """2D affine matrices as (a, b, c, d, e, f) — x' = a x + c y + e."""
    return (a[0] * b[0] + a[2] * b[1], a[1] * b[0] + a[3] * b[1],
            a[0] * b[2] + a[2] * b[3], a[1] * b[2] + a[3] * b[3],
            a[0] * b[4] + a[2] * b[5] + a[4],
            a[1] * b[4] + a[3] * b[5] + a[5])


_IDENT = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _numbers(text):
    return [float(v) for v in re.findall(
        r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", text or "")]


def parse_transform(text):
    m = _IDENT
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", text or ""):
        v = _numbers(args)
        if name == "matrix" and len(v) == 6:
            t = tuple(v)
        elif name == "translate" and v:
            t = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0.0)
        elif name == "scale" and v:
            t = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "rotate" and v:
            a = math.radians(v[0])
            r = (math.cos(a), math.sin(a), -math.sin(a), math.cos(a), 0, 0)
            if len(v) == 3:
                t = _mat_mul(_mat_mul((1, 0, 0, 1, v[1], v[2]), r),
                             (1, 0, 0, 1, -v[1], -v[2]))
            else:
                t = r
        elif name == "skewX" and v:
            t = (1, 0, math.tan(math.radians(v[0])), 1, 0, 0)
        elif name == "skewY" and v:
            t = (1, math.tan(math.radians(v[0])), 0, 1, 0, 0)
        else:
            continue
        m = _mat_mul(m, t)
    return m


def _apply(m, pts):
    return [(m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])
            for x, y in pts]


def _steps(sweep, segments):
    """Straight pieces for a curve turning *sweep* radians."""
    return max(int(math.ceil(abs(sweep) / (2 * math.pi) * segments)), 2)


def _arc_points(x1, y1, rx, ry, phi, large, sweep, x2, y2, segments):
    """SVG elliptical arc (endpoint form) -> points after the start."""
    if rx == 0 or ry == 0:
        return [(x2, y2)]
    phi = math.radians(phi)
    cp, sp = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p, y1p = cp * dx + sp * dy, -sp * dx + cp * dy
    rx, ry = abs(rx), abs(ry)
    lam = x1p ** 2 / rx ** 2 + y1p ** 2 / ry ** 2
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx ** 2 * ry ** 2 - rx ** 2 * y1p ** 2 - ry ** 2 * x1p ** 2
    den = rx ** 2 * y1p ** 2 + ry ** 2 * x1p ** 2
    coef = math.sqrt(max(num / den, 0.0)) if den else 0.0
    if large == sweep:
        coef = -coef
    cxp, cyp = coef * rx * y1p / ry, -coef * ry * x1p / rx
    cx = cp * cxp - sp * cyp + (x1 + x2) / 2
    cy = sp * cxp + cp * cyp + (y1 + y2) / 2

    def angle(ux, uy, vx, vy):
        return math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
    t1 = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dt = angle((x1p - cxp) / rx, (y1p - cyp) / ry,
               (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    elif sweep and dt < 0:
        dt += 2 * math.pi
    n = _steps(dt, segments)
    out = []
    for i in range(1, n + 1):
        t = t1 + dt * i / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        out.append((cp * x - sp * y + cx, sp * x + cp * y + cy))
    return out


def _bezier(points, steps):
    out = []
    for i in range(1, steps + 1):
        t = i / steps
        pts = list(points)
        while len(pts) > 1:
            pts = [(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                   for a, b in zip(pts, pts[1:])]
        out.append(pts[0])
    return out


def parse_path(d, segments=32):
    """An SVG path's ``d`` -> subpaths (lists of points)."""
    tokens = re.findall(r"[MmLlHhVvCcSsQqTtAaZz]|"
                        r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", d or "")
    subpaths, current = [], []
    x = y = sx = sy = 0.0
    last_ctrl = None
    cmd = None
    i = 0
    curve_steps = max(segments // 4, 4)

    def nums(k):
        nonlocal i
        vals = []
        for _ in range(k):
            if i < len(tokens) and not tokens[i].isalpha():
                vals.append(float(tokens[i]))
                i += 1
            else:
                return None
        return vals
    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i]
            i += 1
            if cmd in "Zz":
                if len(current) >= 2:
                    subpaths.append(current)
                current = []
                x, y = sx, sy
                last_ctrl = None
                continue
        if cmd is None:
            i += 1
            continue
        rel = cmd.islower()
        c = cmd.upper()
        if c == "M":
            v = nums(2)
            if v is None:
                i += 1
                continue
            if len(current) >= 2:
                subpaths.append(current)
            x, y = (x + v[0], y + v[1]) if rel else (v[0], v[1])
            sx, sy = x, y
            current = [(x, y)]
            cmd = "l" if rel else "L"          # further pairs are lines
            last_ctrl = None
            continue
        if not current:
            current = [(x, y)]
        if c == "L":
            v = nums(2)
            if v is None:
                i += 1
                continue
            x, y = (x + v[0], y + v[1]) if rel else (v[0], v[1])
            current.append((x, y))
            last_ctrl = None
        elif c in "HV":
            v = nums(1)
            if v is None:
                i += 1
                continue
            if c == "H":
                x = x + v[0] if rel else v[0]
            else:
                y = y + v[0] if rel else v[0]
            current.append((x, y))
            last_ctrl = None
        elif c in "CS":
            v = nums(6 if c == "C" else 4)
            if v is None:
                i += 1
                continue
            if rel:
                v = [v[k] + (x if k % 2 == 0 else y) for k in range(len(v))]
            if c == "S":
                if last_ctrl and last_ctrl[0] == "C":
                    c1 = (2 * x - last_ctrl[1], 2 * y - last_ctrl[2])
                else:
                    c1 = (x, y)
                c2, end = (v[0], v[1]), (v[2], v[3])
            else:
                c1, c2, end = (v[0], v[1]), (v[2], v[3]), (v[4], v[5])
            current.extend(_bezier([(x, y), c1, c2, end], curve_steps))
            last_ctrl = ("C", c2[0], c2[1])
            x, y = end
        elif c in "QT":
            v = nums(4 if c == "Q" else 2)
            if v is None:
                i += 1
                continue
            if rel:
                v = [v[k] + (x if k % 2 == 0 else y) for k in range(len(v))]
            if c == "T":
                if last_ctrl and last_ctrl[0] == "Q":
                    q = (2 * x - last_ctrl[1], 2 * y - last_ctrl[2])
                else:
                    q = (x, y)
                end = (v[0], v[1])
            else:
                q, end = (v[0], v[1]), (v[2], v[3])
            current.extend(_bezier([(x, y), q, end], curve_steps))
            last_ctrl = ("Q", q[0], q[1])
            x, y = end
        elif c == "A":
            v = nums(7)
            if v is None:
                i += 1
                continue
            ex, ey = (x + v[5], y + v[6]) if rel else (v[5], v[6])
            current.extend(_arc_points(x, y, v[0], v[1], v[2], bool(v[3]),
                                       bool(v[4]), ex, ey, segments))
            x, y = ex, ey
            last_ctrl = None
        else:
            i += 1
    if len(current) >= 2:
        subpaths.append(current)
    return subpaths


def _ellipse(cx, cy, rx, ry, segments):
    n = max(int(segments), 3)
    return [(cx + rx * math.cos(2 * math.pi * k / n),
             cy + ry * math.sin(2 * math.pi * k / n)) for k in range(n)]


def _rounded_rect(x, y, w, h, rx, ry, segments):
    rx, ry = min(rx, w / 2), min(ry, h / 2)
    if rx <= 0 or ry <= 0:
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    quarter = max(segments // 4, 1)
    pts = []
    for cx, cy, start in ((x + w - rx, y + ry, -90), (x + w - rx, y + h - ry, 0),
                          (x + rx, y + h - ry, 90), (x + rx, y + ry, 180)):
        for k in range(quarter + 1):
            a = math.radians(start + 90 * k / quarter)
            pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    return pts


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _hidden(el):
    style = (el.get("style") or "").replace(" ", "")
    return el.get("display") == "none" or "display:none" in style


def svg_outlines(path, dpi=DEFAULT_DPI, segments=32, layer="", id=""):
    """Outlines of an SVG file in millimetres, y up, page lower-left at
    the origin."""
    tree = ET.parse(path)
    return svg_outlines_from_root(tree.getroot(), dpi, segments, layer, id)


def svg_outlines_from_root(root, dpi=DEFAULT_DPI, segments=32, layer="",
                           id=""):
    dpi = float(dpi) if dpi else DEFAULT_DPI
    view = _numbers(root.get("viewBox") or "")
    width_mm, _ = _length(root.get("width"), dpi)
    height_mm, _ = _length(root.get("height"), dpi)
    if len(view) == 4 and view[2] > 0 and view[3] > 0:
        sx = (width_mm / view[2]) if width_mm else 25.4 / dpi
        sy = (height_mm / view[3]) if height_mm else sx
        page_h = height_mm if height_mm else view[3] * sy
        base = (sx, 0.0, 0.0, sy, -view[0] * sx, -view[1] * sy)
    else:
        unit = 25.4 / dpi
        page_h = height_mm or 0.0
        base = (unit, 0.0, 0.0, unit, 0.0, 0.0)
    outlines = []

    def matches_layer(el):
        label = el.get("{http://www.inkscape.org/namespaces/inkscape}label")
        return layer in (label, el.get("id"))

    def walk(el, m, active):
        if _hidden(el):
            return
        tag = _local(el.tag)
        if tag in ("defs", "clipPath", "mask", "symbol", "style", "title",
                   "desc", "metadata", "text"):
            return
        m = _mat_mul(m, parse_transform(el.get("transform")))
        here = active or (bool(id) and el.get("id") == id) or \
            (bool(layer) and tag == "g" and matches_layer(el))
        want = (not id and not layer) or here
        shapes = []
        f = lambda k: float(_numbers(el.get(k, "0") or "0")[0]) \
            if _numbers(el.get(k, "0") or "0") else 0.0
        if tag == "path":
            shapes = parse_path(el.get("d"), segments)
        elif tag == "rect":
            w, h = f("width"), f("height")
            if w > 0 and h > 0:
                rx = f("rx") if el.get("rx") else f("ry")
                ry = f("ry") if el.get("ry") else rx
                shapes = [_rounded_rect(f("x"), f("y"), w, h, rx, ry,
                                        segments)]
        elif tag == "circle":
            if f("r") > 0:
                shapes = [_ellipse(f("cx"), f("cy"), f("r"), f("r"),
                                   segments)]
        elif tag == "ellipse":
            if f("rx") > 0 and f("ry") > 0:
                shapes = [_ellipse(f("cx"), f("cy"), f("rx"), f("ry"),
                                   segments)]
        elif tag in ("polygon", "polyline"):
            v = _numbers(el.get("points"))
            pts = list(zip(v[0::2], v[1::2]))
            if len(pts) >= 3:
                shapes = [pts]
        if want:
            for pts in shapes:
                if len(pts) >= 3:
                    outlines.append(_apply(m, pts))
        for child in el:
            walk(child, m, here)
    walk(root, base, False)
    # SVG y runs down the page: flip so the drawing reads upright
    return [[(x, page_h - y) for x, y in outline] for outline in outlines]


# ================================================================== DXF

def _dxf_pairs(text):
    lines = text.splitlines()
    for k in range(0, len(lines) - 1, 2):
        try:
            code = int(lines[k].strip())
        except ValueError:
            continue
        yield code, lines[k + 1].strip()


def _dxf_entities(text):
    """(type, [(code, value)]) of every entity in ENTITIES."""
    in_entities = False
    current = None
    out = []
    prev = None
    for code, value in _dxf_pairs(text):
        if code == 2 and prev == (0, "SECTION"):
            in_entities = value == "ENTITIES"
        prev = (code, value)
        if not in_entities:
            continue
        if code == 0:
            if current is not None:
                out.append(current)
            current = (value, []) if value not in ("ENDSEC", "EOF") else None
            continue
        if current is not None:
            current[1].append((code, value))
    if current is not None:
        out.append(current)
    return out


def _bulge_points(p0, p1, bulge, segments):
    """Points after p0 on a polyline segment with a bulge (tan of a
    quarter of the included angle)."""
    if abs(bulge) < 1e-12:
        return [p1]
    theta = 4 * math.atan(bulge)
    chord = math.dist(p0, p1)
    if chord < 1e-12:
        return [p1]
    radius = chord / (2 * math.sin(abs(theta) / 2))
    mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
    h = math.sqrt(max(radius ** 2 - (chord / 2) ** 2, 0.0))
    ux, uy = (p1[0] - p0[0]) / chord, (p1[1] - p0[1]) / chord
    side = 1 if (bulge > 0) == (abs(theta) < math.pi) else -1
    cx, cy = mid[0] - uy * h * side, mid[1] + ux * h * side
    a0 = math.atan2(p0[1] - cy, p0[0] - cx)
    n = _steps(theta, segments)
    return [(cx + radius * math.cos(a0 + theta * k / n),
             cy + radius * math.sin(a0 + theta * k / n))
            for k in range(1, n + 1)]


def _polyline(vertices, closed, segments):
    """[(x, y, bulge)] -> points."""
    if not vertices:
        return []
    pts = [vertices[0][:2]]
    count = len(vertices) if closed else len(vertices) - 1
    for k in range(count):
        a, b = vertices[k], vertices[(k + 1) % len(vertices)]
        pts.extend(_bulge_points(a[:2], b[:2], a[2], segments))
    if closed and len(pts) > 1 and math.dist(pts[0], pts[-1]) < 1e-9:
        pts.pop()
    return pts


def _bspline(control, knots, degree, samples):
    """De Boor evaluation of a clamped B-spline."""
    n = len(control)
    if n <= degree or len(knots) < n + degree + 1:
        return list(control)
    lo, hi = knots[degree], knots[n]
    out = []
    for s in range(samples + 1):
        t = lo + (hi - lo) * s / samples
        k = degree
        while k < n - 1 and t >= knots[k + 1]:
            k += 1
        d = [list(control[j]) for j in range(k - degree, k + 1)]
        for r in range(1, degree + 1):
            for j in range(degree, r - 1, -1):
                i = j + k - degree
                den = knots[i + degree - r + 1] - knots[i]
                a = (t - knots[i]) / den if den else 0.0
                d[j] = [(1 - a) * d[j - 1][c] + a * d[j][c] for c in (0, 1)]
        out.append(tuple(d[degree]))
    return out


def dxf_outlines(path, segments=32, layer=""):
    """Closed outlines of a DXF file's entities (drawing units, taken
    as millimetres)."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    return dxf_outlines_from_text(text, segments, layer)


def dxf_outlines_from_text(text, segments=32, layer=""):
    closed, loose = [], []
    entities = _dxf_entities(text)
    k = 0
    while k < len(entities):
        kind, pairs = entities[k]
        k += 1
        get = {}
        for code, value in pairs:
            get.setdefault(code, value)
        if layer and get.get(8, "0") != layer and kind != "VERTEX":
            if kind == "POLYLINE":            # skip its vertices too
                while k < len(entities) and entities[k][0] != "SEQEND":
                    k += 1
            continue

        def num(code, default=0.0):
            try:
                return float(get.get(code, default))
            except ValueError:
                return default
        if kind == "LWPOLYLINE":
            verts, cur = [], None
            for code, value in pairs:
                if code == 10:
                    cur = [float(value), 0.0, 0.0]
                    verts.append(cur)
                elif code == 20 and cur is not None:
                    cur[1] = float(value)
                elif code == 42 and cur is not None:
                    cur[2] = float(value)
            is_closed = int(num(70)) & 1
            pts = _polyline([tuple(v) for v in verts], is_closed, segments)
            (closed if is_closed else loose).append(pts)
        elif kind == "POLYLINE":
            is_closed = int(num(70)) & 1
            verts = []
            while k < len(entities) and entities[k][0] == "VERTEX":
                vg = {}
                for code, value in entities[k][1]:
                    vg.setdefault(code, value)
                verts.append((float(vg.get(10, 0)), float(vg.get(20, 0)),
                              float(vg.get(42, 0))))
                k += 1
            if k < len(entities) and entities[k][0] == "SEQEND":
                k += 1
            pts = _polyline(verts, is_closed, segments)
            (closed if is_closed else loose).append(pts)
        elif kind == "LINE":
            loose.append([(num(10), num(20)), (num(11), num(21))])
        elif kind == "CIRCLE":
            closed.append(_ellipse(num(10), num(20), num(40), num(40),
                                   segments))
        elif kind == "ARC":
            a0, a1 = math.radians(num(50)), math.radians(num(51))
            if a1 <= a0:
                a1 += 2 * math.pi
            n = _steps(a1 - a0, segments)
            cx, cy, r = num(10), num(20), num(40)
            loose.append([(cx + r * math.cos(a0 + (a1 - a0) * i / n),
                           cy + r * math.sin(a0 + (a1 - a0) * i / n))
                          for i in range(n + 1)])
        elif kind == "ELLIPSE":
            cx, cy, mx, my = num(10), num(20), num(11), num(21)
            ratio = num(40, 1.0)
            t0, t1 = num(41, 0.0), num(42, 2 * math.pi)
            if t1 <= t0:
                t1 += 2 * math.pi
            major = math.hypot(mx, my)
            rot = math.atan2(my, mx)
            full = abs((t1 - t0) - 2 * math.pi) < 1e-6
            n = _steps(t1 - t0, segments)
            pts = []
            for i in range(n if full else n + 1):
                t = t0 + (t1 - t0) * i / n
                x, y = major * math.cos(t), major * ratio * math.sin(t)
                pts.append((cx + x * math.cos(rot) - y * math.sin(rot),
                            cy + x * math.sin(rot) + y * math.cos(rot)))
            (closed if full else loose).append(pts)
        elif kind == "SPLINE":
            knots, control, fit = [], [], []
            cur = None
            for code, value in pairs:
                if code == 40:
                    knots.append(float(value))
                elif code == 10:
                    cur = [float(value), 0.0]
                    control.append(cur)
                elif code == 20 and cur is not None:
                    cur[1] = float(value)
                elif code == 11:
                    fit.append([float(value), 0.0])
                elif code == 21 and fit:
                    fit[-1][1] = float(value)
            degree = int(num(71, 3))
            pts = _bspline([tuple(c) for c in control], knots, degree,
                           max(segments, 8)) if control else \
                [tuple(f) for f in fit]
            is_closed = int(num(70)) & 1
            (closed if is_closed else loose).append(pts)
    closed.extend(chain(loose))
    return [o for o in closed if len(o) >= 3]


def chain(pieces, tolerance=1e-6):
    """Join open polylines that meet end to end into closed loops (a
    rectangle drawn as four LINEs). What never closes is dropped: an
    open line has no area to extrude."""
    pieces = [list(p) for p in pieces if len(p) >= 2]
    loops = []
    while pieces:
        loop = pieces.pop()
        grown = True
        while grown and math.dist(loop[0], loop[-1]) > tolerance:
            grown = False
            for j, piece in enumerate(pieces):
                if math.dist(loop[-1], piece[0]) <= tolerance:
                    loop.extend(piece[1:])
                elif math.dist(loop[-1], piece[-1]) <= tolerance:
                    loop.extend(piece[-2::-1])
                elif math.dist(loop[0], piece[-1]) <= tolerance:
                    loop[:0] = piece[:-1]
                elif math.dist(loop[0], piece[0]) <= tolerance:
                    loop[:0] = piece[:0:-1]
                else:
                    continue
                pieces.pop(j)
                grown = True
                break
        if math.dist(loop[0], loop[-1]) <= tolerance and len(loop) >= 4:
            loops.append(loop[:-1])
    return loops


def outlines(path, segments=32, dpi=DEFAULT_DPI, layer="", id=""):
    """Outlines of an SVG or DXF file, by extension."""
    lower = str(path).lower()
    if lower.endswith(".svg"):
        return svg_outlines(path, dpi, segments, layer, id)
    if lower.endswith(".dxf"):
        return dxf_outlines(path, segments, layer)
    raise ValueError(f"not an SVG or DXF file: {path}")
