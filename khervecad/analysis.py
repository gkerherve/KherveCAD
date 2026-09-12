"""Checking a part (Qt-free): mass properties, a 3D-print check and an
interference check — Blender's 3D-Print Toolbox and SolidWorks' Mass
Properties, on the triangle meshes the app already has.

- `mass_properties` — volume (divergence theorem), surface area, centre
  of mass, bounding box; `mass`/`cost` from a material table and a
  price per kilogram; `print_time` is a rough figure from the volume.
- `print_check` — watertight (every edge shared by two faces, wound
  opposite ways), overhangs (faces looking down more than the angle a
  printer bridges), thin walls (a ray from a face inward hits the
  opposite face within the minimum wall), footprint on the plate
  (tip-over / adhesion), each pass / warn / fail with the offending
  triangles so the 3D view can show them.
- `interference` — for every pair of parts: do they intersect (a
  triangle edge of one crosses a face of the other, found through a
  grid over the overlap box), is one inside the other (ray parity), or
  are they clear.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
from collections import Counter

#: g/cm³
MATERIALS = {
    "PLA": 1.24, "PETG": 1.27, "ABS": 1.04, "ASA": 1.07, "TPU": 1.21,
    "Nylon": 1.14, "Resin": 1.10, "Aluminium": 2.70, "Steel": 7.85,
    "Brass": 8.40, "Titanium": 4.43,
}
DEFAULT_MATERIAL = "PLA"
DEFAULT_PRICE = 20.0                     # per kg
DEFAULT_CURRENCY = "€"

#: the rough print-time model: a printer lays down this much of the
#: part's volume per second (0.2 mm layers, 15 % infill, 3 walls) —
#: honest to a factor of two, no more
PRINT_MM3_PER_S = 3.0

#: faces looking down more than this below horizontal need support
DEFAULT_OVERHANG = 45.0
#: thinnest wall most printers make (two extrusion widths)
DEFAULT_MIN_WALL = 0.8

#: thin-wall sampling: at most this many faces are probed
THIN_SAMPLES = 2000

#: a footprint smaller than this fraction of (height)² tips over
FOOTPRINT_RATIO = 0.15


# ------------------------------------------------------------ vectors
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _normal_area(tri):
    a, b, c = tri
    n = _cross(_sub(b, a), _sub(c, a))
    length = math.sqrt(_dot(n, n))
    if length < 1e-15:
        return (0.0, 0.0, 0.0), 0.0
    return (n[0] / length, n[1] / length, n[2] / length), length / 2.0


def _key(v):
    return (round(v[0], 5), round(v[1], 5), round(v[2], 5))


# ----------------------------------------------------- mass properties
def bounds(tris):
    pts = [v for t in tris for v in t]
    if not pts:
        return None, None
    return ([min(p[i] for p in pts) for i in range(3)],
            [max(p[i] for p in pts) for i in range(3)])


def mass_properties(tris) -> dict:
    """Volume (mm³), area (mm²), centre of mass, box — from a closed
    outward mesh. An open mesh gives a volume that is only a guess."""
    if not tris:
        return dict(volume=0.0, area=0.0, centroid=[0.0, 0.0, 0.0],
                    min=[0.0] * 3, max=[0.0] * 3, size=[0.0] * 3)
    volume = 0.0
    area = 0.0
    cx = cy = cz = 0.0
    for a, b, c in tris:
        det = _dot(a, _cross(b, c))
        volume += det
        # centroid of the tetrahedron (origin, a, b, c) weighted by it
        cx += det * (a[0] + b[0] + c[0])
        cy += det * (a[1] + b[1] + c[1])
        cz += det * (a[2] + b[2] + c[2])
        area += _normal_area((a, b, c))[1]
    volume /= 6.0
    if abs(volume) > 1e-12:
        centroid = [cx / (24.0 * volume), cy / (24.0 * volume),
                    cz / (24.0 * volume)]
    else:
        lo, hi = bounds(tris)
        centroid = [(lo[i] + hi[i]) / 2 for i in range(3)]
    lo, hi = bounds(tris)
    return dict(volume=volume, area=area, centroid=centroid, min=lo,
                max=hi, size=[hi[i] - lo[i] for i in range(3)])


def mass(volume_mm3: float, material: str = DEFAULT_MATERIAL) -> float:
    """Grams, solid (a print with infill weighs less)."""
    return volume_mm3 / 1000.0 * MATERIALS.get(material, MATERIALS["PLA"])


def cost(grams: float, price_per_kg: float = DEFAULT_PRICE) -> float:
    return grams / 1000.0 * price_per_kg


def print_time(volume_mm3: float) -> float:
    """Hours — a rough figure (see PRINT_MM3_PER_S)."""
    return volume_mm3 / PRINT_MM3_PER_S / 3600.0


# ---------------------------------------------------------- watertight
def watertight(tris) -> dict:
    """{"ok", "boundary_edges", "reversed_edges", "at"}: every edge of
    a closed outward mesh is used once each way."""
    count = Counter()
    for a, b, c in tris:
        for u, w in ((a, b), (b, c), (c, a)):
            count[(_key(u), _key(w))] += 1
    boundary = reversed_ = 0
    at = None
    for (u, w), n in count.items():
        back = count.get((w, u), 0)
        if n > 1:
            reversed_ += 1
            at = at or u
        elif back == 0:
            boundary += 1
            at = at or u
    return dict(ok=boundary == 0 and reversed_ == 0,
                boundary_edges=boundary, reversed_edges=reversed_,
                at=list(at) if at else None)


# ------------------------------------------------------------ the grid
class _Grid:
    """Triangles bucketed by the cells their boxes touch."""

    def __init__(self, tris, cells: int = 24):
        self.tris = tris
        lo, hi = bounds(tris)
        self.lo = lo or [0.0] * 3
        size = [max(hi[i] - lo[i], 1e-9) for i in range(3)] if lo \
            else [1.0] * 3
        self.cell = max(size) / cells
        self.buckets = {}
        for i, tri in enumerate(tris):
            for c in self._cells_of(tri):
                self.buckets.setdefault(c, []).append(i)

    def _coord(self, p):
        return tuple(int(math.floor((p[k] - self.lo[k]) / self.cell))
                     for k in range(3))

    def _cells_of(self, tri):
        los = [min(v[k] for v in tri) for k in range(3)]
        his = [max(v[k] for v in tri) for k in range(3)]
        c0, c1 = self._coord(los), self._coord(his)
        return [(x, y, z) for x in range(c0[0], c1[0] + 1)
                for y in range(c0[1], c1[1] + 1)
                for z in range(c0[2], c1[2] + 1)]

    def near(self, p, q):
        """Indices of triangles in the cells the segment p-q touches."""
        los = [min(p[k], q[k]) for k in range(3)]
        his = [max(p[k], q[k]) for k in range(3)]
        c0, c1 = self._coord(los), self._coord(his)
        out = set()
        for x in range(c0[0], c1[0] + 1):
            for y in range(c0[1], c1[1] + 1):
                for z in range(c0[2], c1[2] + 1):
                    out.update(self.buckets.get((x, y, z), ()))
        return out


def _ray_hit(orig, direction, tri, strict=False):
    """Distance along the ray to *tri* (Möller-Trumbore), or None.
    *strict* rejects hits on the triangle's border, so an edge that
    merely touches a face (two boxes side by side) is not a crossing."""
    a, b, c = tri
    e1, e2 = _sub(b, a), _sub(c, a)
    p = _cross(direction, e2)
    det = _dot(e1, p)
    if abs(det) < 1e-12:
        return None
    inv = 1.0 / det
    t = _sub(orig, a)
    u = _dot(t, p) * inv
    eps = 1e-6 if strict else -1e-9
    if u < eps or u > 1 - eps:
        return None
    q = _cross(t, e1)
    v = _dot(direction, q) * inv
    if v < eps or u + v > 1 - eps:
        return None
    dist = _dot(e2, q) * inv
    return dist if dist > 1e-9 else None


# ---------------------------------------------------------- print check
def print_check(tris, overhang_deg: float = DEFAULT_OVERHANG,
                min_wall: float = DEFAULT_MIN_WALL,
                layer: float = 0.2) -> dict:
    """The report: per check a status (pass / warn / fail), a message,
    numbers, and the triangles at fault for highlighting."""
    if not tris:
        return dict(checks=[], overhang_tris=[], thin_tris=[],
                    summary="nothing to check")
    lo, hi = bounds(tris)
    height = hi[2] - lo[2]
    checks = []

    water = watertight(tris)
    if water["ok"]:
        checks.append(dict(name="Watertight", status="pass",
                           message="Closed surface, consistently wound."))
    else:
        checks.append(dict(
            name="Watertight", status="fail",
            message=f"{water['boundary_edges']} open edge(s) and "
                    f"{water['reversed_edges']} doubled edge(s) — a "
                    "slicer may fill or drop parts of it. First at "
                    f"{[round(v, 2) for v in water['at']]}."))

    sin_over = math.sin(math.radians(overhang_deg))
    total = 0.0
    over_area = 0.0
    over_tris = []
    plate_area = 0.0
    for tri in tris:
        n, area = _normal_area(tri)
        total += area
        on_plate = all(v[2] - lo[2] <= layer / 2 for v in tri)
        if on_plate and n[2] < -0.5:
            plate_area += area
            continue
        if -n[2] > sin_over:
            over_area += area
            over_tris.append(tri)
    frac = over_area / total if total else 0.0
    if frac < 0.005:
        checks.append(dict(name="Overhangs", status="pass",
                           message=f"No faces steeper than {overhang_deg:g}° "
                                   "below horizontal."))
    else:
        checks.append(dict(
            name="Overhangs", status="warn" if frac < 0.15 else "fail",
            message=f"{frac * 100:.0f} % of the surface looks down more "
                    f"than {overhang_deg:g}° — needs supports, or "
                    "re-orient the part."))

    grid = _Grid(tris)
    stride = max(1, len(tris) // THIN_SAMPLES)
    thin_tris = []
    thinnest = None
    for i in range(0, len(tris), stride):
        tri = tris[i]
        n, area = _normal_area(tri)
        if area <= 0:
            continue
        a, b, c = tri
        centroid = ((a[0] + b[0] + c[0]) / 3, (a[1] + b[1] + c[1]) / 3,
                    (a[2] + b[2] + c[2]) / 3)
        direction = (-n[0], -n[1], -n[2])
        far = tuple(centroid[k] + direction[k] * min_wall * 1.01
                    for k in range(3))
        best = None
        for j in grid.near(centroid, far):
            if j == i:
                continue
            d = _ray_hit(centroid, direction, tris[j])
            if d is not None and d <= min_wall * 1.01 and \
                    (best is None or d < best):
                best = d
        if best is not None:
            thin_tris.append(tri)
            thinnest = best if thinnest is None else min(thinnest, best)
    if thinnest is None:
        checks.append(dict(name="Wall thickness", status="pass",
                           message=f"No wall thinner than {min_wall:g} mm "
                                   "found."))
    else:
        checks.append(dict(
            name="Wall thickness",
            status="fail" if thinnest < min_wall * 0.6 else "warn",
            message=f"Walls down to {thinnest:.2f} mm (minimum "
                    f"{min_wall:g}) — may not print, or breaks."))

    if height > 0:
        ratio = plate_area / (height * height)
        if plate_area <= 0:
            checks.append(dict(name="Footprint", status="fail",
                               message="Nothing flat on the build plate — "
                                       "lay the part on a face."))
        elif ratio < FOOTPRINT_RATIO:
            checks.append(dict(
                name="Footprint", status="warn",
                message=f"{plate_area:.0f} mm² on the plate for a "
                        f"{height:.0f} mm tall part — may tip or peel; "
                        "add a brim or lay it flat."))
        else:
            checks.append(dict(name="Footprint", status="pass",
                               message=f"{plate_area:.0f} mm² on the plate."))
    worst = "pass"
    for c in checks:
        if c["status"] == "fail":
            worst = "fail"
        elif c["status"] == "warn" and worst == "pass":
            worst = "warn"
    return dict(checks=checks, overhang_tris=over_tris,
                thin_tris=thin_tris, summary=worst,
                overhang_fraction=frac, thinnest=thinnest,
                plate_area=plate_area, height=height)


# -------------------------------------------------------- interference
def _boxes_overlap(a, b, pad=0.0):
    lo_a, hi_a = a
    lo_b, hi_b = b
    return all(lo_a[k] - pad <= hi_b[k] and lo_b[k] - pad <= hi_a[k]
               for k in range(3))


def _edge_crosses(p, q, tri):
    """Does segment p-q cross triangle *tri*?"""
    d = _sub(q, p)
    length = math.sqrt(_dot(d, d))
    if length < 1e-12:
        return False
    unit = (d[0] / length, d[1] / length, d[2] / length)
    # border hits count (an axis-aligned box's edge meets the other
    # box's face on its diagonal exactly), but the crossing must lie
    # strictly between the segment's ends: an endpoint ON the face is
    # two parts touching, not overlapping
    t = _ray_hit(p, unit, tri)
    return t is not None and 1e-6 * length < t < length * (1 - 1e-6)


def _tris_cross(t1, t2):
    for k in range(3):
        if _edge_crosses(t1[k], t1[(k + 1) % 3], t2):
            return True
        if _edge_crosses(t2[k], t2[(k + 1) % 3], t1):
            return True
    return False


#: the parity ray leans a little off the X axis so it does not run
#: along a triangle edge or through a vertex of an axis-aligned part
#: (a shared edge would count twice)
_PROBE = (0.93781, 0.24697, 0.24549)


def point_inside(p, tris) -> bool:
    """Ray parity (an odd number of crossings = inside)."""
    hits = 0
    for tri in tris:
        if max(v[0] for v in tri) < p[0]:
            continue
        if _ray_hit(p, _PROBE, tri) is not None:
            hits += 1
    return hits % 2 == 1


def _probe_point(tris):
    """A point of the surface that is not a vertex: a face centroid."""
    a, b, c = tris[0]
    return ((a[0] + b[0] + c[0]) / 3, (a[1] + b[1] + c[1]) / 3,
            (a[2] + b[2] + c[2]) / 3)


def interference(parts, max_points: int = 5) -> list:
    """*parts* = [(name, tris)]. One dict per pair: names, status
    ("intersect" | "contains" | "inside" | "clear"), the overlap box
    and a few crossing points."""
    boxes = [bounds(t) for _n, t in parts]
    out = []
    for i in range(len(parts)):
        for j in range(i + 1, len(parts)):
            name_a, ta = parts[i]
            name_b, tb = parts[j]
            if not ta or not tb or not _boxes_overlap(boxes[i], boxes[j]):
                out.append(dict(a=name_a, b=name_b, status="clear"))
                continue
            lo = [max(boxes[i][0][k], boxes[j][0][k]) for k in range(3)]
            hi = [min(boxes[i][1][k], boxes[j][1][k]) for k in range(3)]
            inside_box = lambda t: all(  # noqa: E731
                max(v[k] for v in t) >= lo[k] - 1e-9
                and min(v[k] for v in t) <= hi[k] + 1e-9 for k in range(3))
            cand_a = [t for t in ta if inside_box(t)]
            cand_b = [t for t in tb if inside_box(t)]
            points = []
            if cand_a and cand_b:
                grid = _Grid(cand_b)
                for t in cand_a:
                    tlo = [min(v[k] for v in t) for k in range(3)]
                    thi = [max(v[k] for v in t) for k in range(3)]
                    for jdx in grid.near(tlo, thi):
                        if _tris_cross(t, cand_b[jdx]):
                            points.append([round(sum(v[k] for v in t) / 3, 3)
                                           for k in range(3)])
                            break
                    if len(points) >= max_points:
                        break
            if points:
                status = "intersect"
            elif point_inside(_probe_point(ta), tb):
                status = "inside"                # a is inside b
            elif point_inside(_probe_point(tb), ta):
                status = "contains"              # b is inside a
            else:
                status = "clear"
            entry = dict(a=name_a, b=name_b, status=status)
            if status != "clear":
                entry["overlap_min"] = [round(v, 3) for v in lo]
                entry["overlap_max"] = [round(v, 3) for v in hi]
                entry["points"] = points
            out.append(entry)
    return out
