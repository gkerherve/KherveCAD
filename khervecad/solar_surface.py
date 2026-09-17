"""Surface features for planets and moons (Qt-free): the toolkit
`solar_bodies` paints a globe with. Everything is a solid stood ON the
sphere — no boolean, so the built-in preview shows every body exactly
and each feature keeps its own colour:

- `band` — a latitude band, one revolved arc slice (Jupiter's belts,
  polar caps); `hemisphere` — half a globe (Iapetus' two faces);
- `patch` — an ellipsoid buried to its rim, a smooth blob on the
  surface (a mare, the Great Red Spot, a dark albedo region);
- `crater` — a rim ring (a revolved circle) half sunk in the surface;
  `mountain` — a shield-volcano cone; `arc_line` — a great-circle line
  of capsules (Europa's lineae, Valles Marineris, crater rays);
- `rings` — flat annuli (Saturn); `haze` — a translucent Glass shell
  (an atmosphere); `map_shells` — a coarse lat/lon character map
  (`solar_maps`) as one polyhedron per class, each run of like cells
  a closed curved slab, so a continent is a few hundred triangles.

Positions are (latitude, longitude) in degrees, east positive, on a
sphere of radius *r* mm; feature sizes are degrees of arc, so a body
built at any diameter carries the same map. `on_surface` puts a node
built at the north pole (+Z, standing at height r) onto that point.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from .model import CadNode

SEG = 64          # the document's $fn replaces it anyway


# ---------------------------------------------------------------- basics

def group(name, *children) -> CadNode:
    node = CadNode("union", name)
    for child in children:
        if child is not None:
            node.add(child)
    return node


def col(name, colour, child, material="Plastic", alpha=1.0) -> CadNode:
    node = CadNode("color", name, dict(color=colour, alpha=float(alpha),
                                       material=material))
    node.add(child)
    return node


def sphere(name, r, colour, material="Plastic", alpha=1.0,
           seg=SEG) -> CadNode:
    return col(name, colour, CadNode("sphere", name, dict(
        x=0.0, y=0.0, z=0.0, radius=float(r), segments=seg)),
        material, alpha)


def poly_sphere(name, radii, colour, material="Plastic", seg=16) -> CadNode:
    """A sphere (or ellipsoid, *radii* (a, b, c)) baked as a polyhedron
    of *seg* meridians: its facet count is its own, where a sphere node
    takes the document's $fn — a 1 mm moon in an orrery needs no 1890
    triangles."""
    a, b, c = radii
    n, m = max(int(seg), 6), max(int(seg) // 2, 3)
    points = [[0.0, 0.0, float(c)]]
    for i in range(1, m):
        lat = math.pi / 2 - math.pi * i / m
        for j in range(n):
            lon = 2 * math.pi * j / n
            points.append([round(a * math.cos(lat) * math.cos(lon), 5),
                           round(b * math.cos(lat) * math.sin(lon), 5),
                           round(c * math.sin(lat), 5)])
    points.append([0.0, 0.0, -float(c)])
    south = len(points) - 1
    faces = []

    def at(i, j):
        return 1 + (i - 1) * n + (j % n)
    for j in range(n):
        faces.append([0, at(1, j + 1), at(1, j)])
    for i in range(1, m - 1):
        for j in range(n):
            faces.append([at(i, j), at(i, j + 1), at(i + 1, j + 1)])
            faces.append([at(i, j), at(i + 1, j + 1), at(i + 1, j)])
    for j in range(n):
        faces.append([at(m - 1, j), at(m - 1, j + 1), south])
    return col(name, colour, CadNode("polyhedron", name, dict(
        points=points, faces=faces)), material)


def ellipsoid(name, radii, colour, material="Plastic", seg=SEG) -> CadNode:
    a, b, c = radii
    return col(name, colour, CadNode("ellipsoid", name, dict(
        x=0.0, y=0.0, z=0.0, rx=float(a), ry=float(b), rz=float(c),
        segments=seg)), material)


def haze(name, r, colour, alpha=0.2) -> CadNode:
    """A translucent atmosphere shell."""
    return sphere(name, r, colour, "Glass", alpha)


def flatten(node, f) -> CadNode:
    """*node* squashed along Z by *f* (an oblate planet)."""
    if abs(f - 1.0) < 1e-6:
        return node
    s = CadNode("scale", "Oblateness", dict(x=1.0, y=1.0, z=float(f)))
    s.add(node)
    return s


def point(r, lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    return (r * math.cos(la) * math.cos(lo), r * math.cos(la) * math.sin(lo),
            r * math.sin(la))


def on_surface(node, lat, lon) -> CadNode:
    """*node*, built at the north pole standing on +Z, moved to (lat,
    lon): OpenSCAD's rotate([0, b, c]) turns about Y then Z."""
    rot = CadNode("rotate", node.name, dict(x=0.0, y=90.0 - float(lat),
                                            z=float(lon)))
    rot.add(node)
    return rot


def sag(r, w):
    """How far the sphere falls below its tangent plane *w* out."""
    return r - math.sqrt(max(r * r - w * w, 0.0))


def deg_of(km, radius_km):
    """Degrees of arc a length of *km* spans on a body."""
    return math.degrees(km / radius_km)


# --------------------------------------------------------- revolutions

def _revolve(name, points, angle=360.0, seg=SEG) -> CadNode:
    rev = CadNode("rotate_extrude", name, dict(angle=float(angle),
                                               segments=seg))
    rev.add(CadNode("polygon", name, dict(
        x=0.0, y=0.0, points=[[round(x, 5), round(y, 5)] for x, y in points],
        paths=[])))
    return rev


def _arc(r, lat0, lat1, step=4.0):
    n = max(int(math.ceil(abs(lat1 - lat0) / step)), 1)
    return [(r * math.cos(math.radians(lat0 + (lat1 - lat0) * i / n)),
             r * math.sin(math.radians(lat0 + (lat1 - lat0) * i / n)))
            for i in range(n + 1)]


def band(name, r, lat0, lat1, colour, material="Plastic", lift=1.0,
         seg=SEG, step=4.0) -> CadNode:
    """The slice of the globe between two latitudes, as one solid
    wedge to the axis. *lift* > 1 raises it over a base sphere; *step*
    is the profile's resolution in degrees."""
    lo, hi = sorted((float(lat0), float(lat1)))
    rr = r * lift
    pts = _arc(rr, lo, hi, step)
    if hi < 90.0:
        pts.append((0.0, rr * math.sin(math.radians(hi))))
    if lo > -90.0:
        pts.append((0.0, rr * math.sin(math.radians(lo))))
    return col(name, colour, _revolve(name, pts, seg=seg), material)


def bands(name, r, table, material="Plastic", lift=1.0,
          step=4.0) -> CadNode:
    """A whole globe of latitude bands: *table* rows (lat_from,
    lat_to, colour) from the north pole down."""
    node = CadNode("union", name)
    for i, (a, b, colour) in enumerate(table):
        node.add(band(f"{name} band {i + 1} ({a:g} to {b:g})", r, a, b,
                      colour, material, lift, step=step))
    return node


def hemisphere(name, r, colour, centre_lon, material="Plastic",
               lift=1.0) -> CadNode:
    """Half the globe, centred on longitude *centre_lon*."""
    rr = r * lift
    pts = _arc(rr, -90.0, 90.0)
    rev = _revolve(name, pts, angle=180.0)
    rot = CadNode("rotate", name, dict(x=0.0, y=0.0,
                                       z=float(centre_lon) - 90.0))
    rot.add(col(name, colour, rev, material))
    return rot


def rings(name, spans, thickness, material="Matte", seg=128) -> CadNode:
    """Flat annuli in the equatorial plane: *spans* rows (r_in, r_out,
    colour, alpha) in mm."""
    node = CadNode("union", name)
    t = float(thickness)
    for i, (r_in, r_out, colour, alpha) in enumerate(spans):
        pts = [(r_in, -t / 2), (r_out, -t / 2), (r_out, t / 2),
               (r_in, t / 2)]
        node.add(col(f"{name} {i + 1}", colour,
                     _revolve(f"{name} {i + 1}", pts, seg=seg), material,
                     alpha))
    return node


# ------------------------------------------------------------ features

#: the least a feature may stand proud of the sphere, as a fraction of
#: its radius: the base sphere's facets dip r (1 - cos(180 / $fn)) below
#: the true surface — 0.0024 r at the document's 45 segments — and a
#: patch lower than that fought them and read as torn
MIN_BULGE = 0.006


def patch(name, r, lat, lon, ns_deg, ew_deg, colour, bulge=MIN_BULGE,
          material="Plastic", seg=32) -> CadNode:
    """An ellipsoid sunk to its rim: a smooth raised blob *bulge* × r
    proud of the surface, *ns_deg* by *ew_deg* across."""
    bulge = max(bulge, MIN_BULGE)
    wn = r * math.radians(ns_deg) / 2
    we = r * math.radians(ew_deg) / 2
    s = sag(r, max(wn, we))
    margin = 0.002 * r
    body = CadNode("ellipsoid", name, dict(
        x=0.0, y=0.0, z=r - s - margin, rx=wn, ry=we,
        rz=bulge * r + s + margin, segments=seg))
    return on_surface(col(name, colour, body, material), lat, lon)


def crater(name, r, lat, lon, diameter_deg, colour, material="Plastic",
           rim=None, seg=48) -> CadNode:
    """A rim ring half sunk in the surface. *rim* is the tube radius
    (default a tenth of the crater radius, never under 0.004 r)."""
    rr = r * math.radians(diameter_deg) / 2
    t = rim if rim else max(0.1 * rr, 0.004 * r)
    z = r - sag(r, rr) - 0.35 * t
    tube = CadNode("rotate_extrude", name, dict(angle=360.0, segments=seg))
    tube.add(CadNode("circle", name, dict(x=rr, y=0.0, radius=t,
                                          angle=360.0, start_angle=0.0,
                                          segments=8)))
    lift = CadNode("translate", name, dict(x=0.0, y=0.0, z=z))
    lift.add(col(name, colour, tube, material))
    return on_surface(lift, lat, lon)


def mountain(name, r, lat, lon, base_deg, height, colour,
             material="Plastic", top=0.15, seg=32) -> CadNode:
    """A shield volcano: a cone from below the surface to *height* mm
    above it."""
    rb = r * math.radians(base_deg) / 2
    s = sag(r, rb) + 0.002 * r
    cone = CadNode("cylinder", name, dict(
        x=0.0, y=0.0, z=r - s, height=s + float(height),
        radius_bottom=rb, radius_top=max(rb * top, 0.01), segments=seg,
        center=False))
    return on_surface(col(name, colour, cone, material), lat, lon)


def _slerp(p, q, t):
    dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(p, q))))
    omega = math.acos(dot)
    if omega < 1e-9:
        return p
    a, b = math.sin((1 - t) * omega) / math.sin(omega), \
        math.sin(t * omega) / math.sin(omega)
    return tuple(a * x + b * y for x, y in zip(p, q))


def arc_line(name, r, start, end, width, colour, material="Plastic",
             step_deg=8.0, seg=8) -> CadNode:
    """A great-circle line from (lat, lon) *start* to *end*, *width*
    mm thick, as short capsules riding just above the surface."""
    p = point(1.0, *start)
    q = point(1.0, *end)
    total = math.degrees(math.acos(max(-1.0, min(
        1.0, sum(a * b for a, b in zip(p, q))))))
    n = max(int(math.ceil(total / step_deg)), 1)
    rr = r + 0.4 * width
    pts = [_slerp(p, q, i / n) for i in range(n + 1)]
    node = CadNode("union", name)
    for i in range(n):
        a, b = pts[i], pts[i + 1]
        node.add(CadNode("capsule", f"{name} {i + 1}", dict(
            x1=a[0] * rr, y1=a[1] * rr, z1=a[2] * rr,
            x2=b[0] * rr, y2=b[1] * rr, z2=b[2] * rr,
            radius=float(width), segments=seg)))
    return col(name, colour, node, material)


# ---------------------------------------------------------- map shells

def _quad(faces, pts, a, b, c, d, outward):
    """Two triangles for the quad a-b-c-d, wound counter-clockwise seen
    from *outward*."""
    pa, pb, pc = pts[a], pts[b], pts[c]
    u = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
    v = (pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2])
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
         u[0] * v[1] - u[1] * v[0])
    if n[0] * outward[0] + n[1] * outward[1] + n[2] * outward[2] < 0:
        a, b, c, d = a, d, c, b
    faces.append([a, b, c])
    faces.append([a, c, d])


def _run_shell(points, faces, r_in, r_out, lat_s, lat_n, lon0, cell,
               count, closed):
    """One closed slab over *count* cells from *lon0*, appended to
    *points*/*faces* (OpenSCAD winding: clockwise from outside)."""
    base = len(points)
    cols = count if closed else count + 1
    for k in range(cols):
        lon = lon0 + k * cell
        for lat in (lat_s, lat_n):
            for rad in (r_in, r_out):
                points.append([round(v, 4) for v in point(rad, lat, lon)])
    # index: column k, edge e (0 south, 1 north), radius q (0 in, 1 out)

    def idx(k, e, q):
        return base + (k % cols) * 4 + e * 2 + q
    local = []
    mid_lat = (lat_s + lat_n) / 2
    for k in range(count):
        lon_mid = lon0 + (k + 0.5) * cell
        radial = point(1.0, mid_lat, lon_mid)
        north = point(1.0, mid_lat + 90.0, lon_mid)
        _quad(local, points, idx(k, 0, 1), idx(k + 1, 0, 1),
              idx(k + 1, 1, 1), idx(k, 1, 1), radial)
        _quad(local, points, idx(k, 0, 0), idx(k + 1, 0, 0),
              idx(k + 1, 1, 0), idx(k, 1, 0),
              tuple(-v for v in radial))
        _quad(local, points, idx(k, 1, 0), idx(k + 1, 1, 0),
              idx(k + 1, 1, 1), idx(k, 1, 1), north)
        _quad(local, points, idx(k, 0, 0), idx(k + 1, 0, 0),
              idx(k + 1, 0, 1), idx(k, 0, 1),
              tuple(-v for v in north))
    if not closed:
        west = point(1.0, 0.0, lon0 - 90.0)
        _quad(local, points, idx(0, 0, 0), idx(0, 0, 1), idx(0, 1, 1),
              idx(0, 1, 0), west)
        east = point(1.0, 0.0, lon0 + count * cell + 90.0)
        _quad(local, points, idx(count, 0, 0), idx(count, 0, 1),
              idx(count, 1, 1), idx(count, 1, 0), east)
    faces.extend([f[0], f[2], f[1]] for f in local)     # clockwise


def map_shells(name, r, rows, palette, relief=0.008, cell=5.0,
               skip=1, material="Plastic", gap=0.02) -> CadNode:
    """*rows* are strings, one per latitude band from the north pole
    down, one character per *cell* degrees of longitude from -180
    east; *palette* maps a character to (colour, relief factor) — a
    character it lacks (".") is left to the base sphere. *skip* 2
    samples every other row and column (a coarser, lighter globe).
    Returns a union with one coloured polyhedron per class. A slab's
    underside sits just ABOVE the base sphere (over its facets' sag),
    never through it: a shell crossing the sphere's facets made the
    painter's BSP split it to shreds and give up."""
    step = cell * skip
    r_in = r * (1 + relief * 0.4)
    grid = [row[::skip] for row in rows[::skip]]
    n_rows, n_cols = len(grid), len(grid[0])
    node = CadNode("union", name)
    for char, (colour, factor) in palette.items():
        points, faces = [], []
        for i, row in enumerate(grid):
            lat_n = 90.0 - i * step - gap
            lat_s = 90.0 - (i + 1) * step + gap
            lat_n = min(lat_n, 90.0 - gap)
            lat_s = max(lat_s, -90.0 + gap)
            if all(ch == char for ch in row):
                _run_shell(points, faces, r_in, r * (1 + relief * factor), lat_s, lat_n,
                           -180.0, step, n_cols, True)
                continue
            k = 0
            while k < n_cols:
                if row[k] != char:
                    k += 1
                    continue
                start = k
                while k < n_cols and row[k] == char:
                    k += 1
                _run_shell(points, faces, r_in, r * (1 + relief * factor), lat_s, lat_n,
                           -180.0 + start * step, step, k - start, False)
        if faces:
            node.add(col(f"{name} {char}", colour, CadNode(
                "polyhedron", f"{name} {char}",
                dict(points=points, faces=faces)), material))
    return node
