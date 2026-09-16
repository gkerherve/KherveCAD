"""Buildings from a real outline, and the light building (Qt-free).

A building spec with ``footprint`` — a polygon in the building's own
frame (mm, centred on its x, y, before rz turns it), as the map import
writes from OpenStreetMap — is built here instead of as a box:

- walls: the outline extruded to the building's height (``height`` mm
  when known, else floors × floor height);
- windows (full detail): each wall edge long enough gets a loop of
  framed panes per floor, set proud on its OUTSIDE (the outline is kept
  counter-clockwise, so outside is to the right of each edge), and the
  longest edge a door;
- roof: a pitched roof (gable / hip from `city_buildings.pitched_roof`)
  over the minimum rectangle when the outline nearly fills it, else a
  flat roof slab and coping — a pitched hull over an L would overhang
  its inside corner.

``detail`` "low" is the light building a whole village is made of:
walls and roof only, no windows, gutters, chimneys or dormers — about a
tenth of the triangles. `build_low` does that for the box styles too,
by treating their rectangle as the outline.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from . import city_buildings as B
from .city_buildings import (GLASS, SILL, WHITE, _num, box, color, cyl,
                             group, loop)
from .model import CadNode

#: an outline filling at least this much of its minimum rectangle gets
#: a pitched roof over that rectangle
RECTANGULAR = 0.8
LOW_DETAIL_ABOVE = 150              # buildings: "auto" detail goes low


def _area(poly):
    return sum(poly[k][0] * poly[(k + 1) % len(poly)][1]
               - poly[(k + 1) % len(poly)][0] * poly[k][1]
               for k in range(len(poly))) / 2.0


def outline(b):
    """The footprint as a counter-clockwise list of (x, y) floats, or
    None when there is no usable one."""
    fp = b.get("footprint")
    if not fp:
        return None
    try:
        pts = [(float(p[0]), float(p[1])) for p in fp]
    except (TypeError, ValueError, IndexError):
        return None
    if len(pts) < 3 or abs(_area(pts)) < 1e5:
        return None
    if _area(pts) < 0:
        pts.reverse()
    return pts


def _poly(name, pts):
    return CadNode("polygon", name, dict(
        x=0.0, y=0.0, points=[[round(x, 1), round(y, 1)] for x, y in pts]))


def _extrude(name, pts, z, h):
    e = CadNode("linear_extrude", name, dict(height=h, twist=0.0, scale=1.0,
                                             center=False, segments=0))
    e.add(_poly("Outline", pts))
    if not z:
        return e
    t = CadNode("translate", name, dict(x=0.0, y=0.0, z=z))
    t.add(e)
    return t


def _height(b):
    h = B._f(b.get("height"), 0.0)
    return h if h > 2000.0 else b["floors"] * b["floor_height"]


def _edge_windows(pts, floors, fh, H):
    """One loop per wall edge: panes per floor along its outside."""
    glass, frames = [], []
    pitch, ww, wh = 2800.0, 1200.0, 1500.0
    n = len(pts)
    for k in range(n):
        (x1, y1), (x2, y2) = pts[k], pts[(k + 1) % n]
        length = math.hypot(x2 - x1, y2 - y1)
        cols = int((length - 900.0) // pitch)
        if cols < 1:
            continue
        a = math.degrees(math.atan2(y2 - y1, x2 - x1))
        start = (length - (cols - 1) * pitch) / 2 - ww / 2
        rows = max(1, min(floors, int((H - 900) // fh) + 1))
        u = f"{_num(start)} + c * {_num(pitch)}"
        z = f"900 + fl * {_num(fh)}"
        pane = loop("Floors", "fl", rows, [loop("Columns", "c", cols, [
            box("Glass", u, -60.0, z, ww, 60.0, wh)])])
        frame = loop("Floors", "fl", rows, [loop("Columns", "c", cols, [
            box("Frame", f"{u} - 70", -40.0, f"{z} - 70", ww + 140, 40.0,
                wh + 140)])])
        for target, body in ((glass, pane), (frames, frame)):
            turn = CadNode("rotate", "Along wall", dict(x=0.0, y=0.0, z=a))
            turn.add(body)
            t = CadNode("translate", f"Wall {k + 1}", dict(x=x1, y=y1, z=0.0))
            t.add(turn)
            target.append(t)
    out = []
    if frames:
        out.append(color(group("Window frames", frames), WHITE, "Matte"))
    if glass:
        out.append(color(group("Windows", glass), GLASS, "Plastic"))
    return out


def _door(pts, wall_colour):
    n = len(pts)
    k = max(range(n), key=lambda i: math.hypot(
        pts[(i + 1) % n][0] - pts[i][0], pts[(i + 1) % n][1] - pts[i][1]))
    (x1, y1), (x2, y2) = pts[k], pts[(k + 1) % n]
    length = math.hypot(x2 - x1, y2 - y1)
    a = math.degrees(math.atan2(y2 - y1, x2 - x1))
    body = group("Entrance", [
        color(box("Door", length / 2 - 550, -80.0, 0.0, 1100, 80.0, 2150),
              B.DOOR, "Matte"),
        color(box("Step", length / 2 - 900, -500.0, 0.0, 1800, 500.0, 150),
              SILL, "Stone")])
    turn = CadNode("rotate", "Along wall", dict(x=0.0, y=0.0, z=a))
    turn.add(body)
    t = CadNode("translate", "Door", dict(x=x1, y=y1, z=0.0))
    t.add(turn)
    return t


def _roof(b, pts, H, low):
    roof = b["roof"]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    w, d = max(xs) - min(xs), max(ys) - min(ys)
    fill = abs(_area(pts)) / max(w * d, 1.0)
    roof_mat = B.ROOFS[b["roof_material"]][0]
    wall_mat = B.WALLS[b["wall"]][0]
    if roof in ("gable", "hip") and fill >= RECTANGULAR:
        node = B.pitched_roof(roof, w, d, H, b["roof_color"], roof_mat,
                              b["color"], wall_mat, chimney=not low,
                              dormer=False,
                              pitch=B._f(b.get("roof_pitch"), 35.0))
        if low:
            node.children = [c for c in node.children if c.name not in (
                "Fascia", "Gutters", "Bargeboards", "Ridge cap")]
            for c in node.children:
                c.parent = node
        t = CadNode("translate", "Roof", dict(x=(max(xs) + min(xs)) / 2,
                                              y=(max(ys) + min(ys)) / 2,
                                              z=0.0))
        t.add(node)
        return t
    if roof == "cone":
        r = max(w, d) / 2
        return color(cyl("Cone roof", (max(xs) + min(xs)) / 2,
                         (max(ys) + min(ys)) / 2, H, r * 0.9, r, 0.0, seg=8),
                     b["roof_color"], roof_mat)
    parts = [color(_extrude("Roof slab", pts, H, 250.0), "#8a8580",
                   "Concrete")]
    if not low:
        parts.append(color(_extrude("Coping", pts, H + 250.0, 120.0),
                           SILL, "Stone"))
    return group("Roof", parts)


def build(b, low=False):
    """The unplaced body of a resolved building with a footprint (or a
    rectangle standing in for one)."""
    pts = outline(b)
    if pts is None:
        w, d = b["w"], b["d"]
        pts = [(-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2),
               (-w / 2, d / 2)]
    H = _height(b)
    wall_mat = B.WALLS[b["wall"]][0]
    body = group(b["name"])
    body.add(color(_extrude("Walls", pts, 0.0, H), b["color"], wall_mat))
    if not low:
        for part in _edge_windows(pts, b["floors"], b["floor_height"], H):
            body.add(part)
        body.add(_door(pts, b["color"]))
    body.add(_roof(b, pts, H, low))
    return body


def build_low(b):
    """The light version of any resolved building."""
    if b["style"] == "round tower":
        r = min(b["w"], b["d"]) / 2
        H = _height(b)
        return group(b["name"], [
            color(cyl("Walls", 0, 0, 0, H, r, seg=12), b["color"],
                  B.WALLS[b["wall"]][0]),
            color(cyl("Cone roof", 0, 0, H, r * 1.2, r + 150, 0.0, seg=12),
                  b["roof_color"], B.ROOFS[b["roof_material"]][0])])
    spec = dict(b)
    if spec["roof"] not in ("gable", "hip", "flat", "cone"):
        spec["roof"] = "flat"
    return build(spec, low=True)


def auto_detail(spec_detail, count):
    """"low" / "full" from a spec's ``detail`` and the building count."""
    if spec_detail in ("low", "full"):
        return spec_detail
    return "low" if count > LOW_DETAIL_ABOVE else "full"
