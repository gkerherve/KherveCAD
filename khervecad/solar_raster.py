"""Real maps for the Moon, Mars and the other mapped bodies (Qt-free):
a shipped grid per body in ``khervecad/solar/<key>.kmap.gz`` — an
optional elevation raster (int16 metres) and an albedo class raster
(one byte a cell, a palette of a few colours quantised from the
mission mosaic), built by `khervecad.tools.planet_maps` from NASA and
USGS public-domain data (LOLA, MOLA, MESSENGER, Magellan, New
Horizons, Voyager and Galileo mosaics).

`globe_nodes` turns one into a globe the way `solar_earth` builds the
Earth's land: a (lon, lat) grid refined where the ground climbs, each
triangle classed by the albedo map, every class ONE closed polyhedron
lifted by *relief* times the elevation, polar caps closing the top and
bottom rows. So the Moon's maria and Tycho's basin, Mars' Tharsis
bulge, Valles Marineris and Hellas, Mercury's Caloris and Pluto's
heart come from the data, not from hand-placed blobs.

File format: ``KCADMAP1`` + width, height (uint32) + has_elevation,
n_classes (uint8) + palette (n × RGB bytes) + int16 elevation (if any)
+ uint8 classes, row-major from 90° N, 180° W, gzipped.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import gzip
import math
import struct
from array import array
from functools import lru_cache
from pathlib import Path

from . import solar_data as D
from .model import CadNode
from .solar_earth import _flip_delaunay, _refine, _shell
from .solar_surface import band, col, point

DATA_DIR = Path(__file__).resolve().parent / "solar"
MAGIC = b"KCADMAP1"

#: default height exaggeration per mapped body (Earth's is in
#: solar_earth): the Moon's 18 km of range on a 1737 km radius shows at
#: 10x, Mars' 29 km on 3390 km at 8x, the way a raised-relief globe does
RELIEF = {"moon": 10.0, "mars": 8.0, "mercury": 12.0, "venus": 12.0,
          "pluto": 12.0}
#: the mesh: base grid step, chord everywhere, chord where the ground
#: climbs (fractions of the radius), and the metres that count as
#: climbing, for fine and coarse globes
FINE = dict(step=10.0, chord=0.1, fine_chord=0.045, climb=250.0)
COARSE = dict(step=20.0, chord=0.2, fine_chord=0.12, climb=600.0)
CAP_LAT = 80.0              # the grid's rows stop here, caps above
#: inner and outer radius of the shells and the base sphere under them,
#: of r: the sphere overlaps the shells even in a basin (Hellas at 8x
#: drops the shell 1.4 %), so the globe is one solid with no cavity
SHELL = (0.95, 1.0)
BASE = 0.965


class PlanetMap:
    def __init__(self, width, height, palette, elevation, classes):
        self.width, self.height = width, height
        self.palette = palette                  # ["#rrggbb", ...]
        self.elevation = elevation              # array('h') or None
        self.classes = classes                  # bytes

    def _cell(self, lat, lon):
        u = (lon + 180.0) / 360.0 * self.width
        v = (90.0 - lat) / 180.0 * self.height
        return u, v

    def elev(self, lat, lon) -> float:
        """Metres above the reference sphere, bilinear; 0 without a
        height model."""
        if self.elevation is None:
            return 0.0
        u, v = self._cell(lat, lon)
        u -= 0.5
        v -= 0.5
        i, j = math.floor(u), math.floor(v)
        fu, fv = u - i, v - j
        w, h = self.width, self.height
        j0, j1 = min(max(j, 0), h - 1), min(max(j + 1, 0), h - 1)
        i0, i1 = i % w, (i + 1) % w
        g = self.elevation
        top = g[j0 * w + i0] * (1 - fu) + g[j0 * w + i1] * fu
        bottom = g[j1 * w + i0] * (1 - fu) + g[j1 * w + i1] * fu
        return top * (1 - fv) + bottom * fv

    def klass(self, lat, lon) -> int:
        u, v = self._cell(lat, lon)
        i = int(u) % self.width
        j = min(max(int(v), 0), self.height - 1)
        return self.classes[j * self.width + i]


def path_of(key: str) -> Path:
    return DATA_DIR / f"{key}.kmap.gz"


def has_map(key: str) -> bool:
    return path_of(key).exists()


def write(path, width, height, palette, elevation, classes):
    """Write a map file (the tool's half of the format)."""
    with gzip.open(path, "wb") as f:
        f.write(MAGIC + struct.pack("<IIBB", width, height,
                                    1 if elevation is not None else 0,
                                    len(palette)))
        for colour in palette:
            f.write(bytes(int(colour[k:k + 2], 16) for k in (1, 3, 5)))
        if elevation is not None:
            grid = array("h", elevation)
            if __import__("sys").byteorder != "little":
                grid.byteswap()
            f.write(grid.tobytes())
        f.write(bytes(classes))


@lru_cache(maxsize=None)
def load(key: str) -> PlanetMap:
    with gzip.open(path_of(key), "rb") as f:
        head = f.read(8 + 4 + 4 + 1 + 1)
        if head[:8] != MAGIC:
            raise ValueError(f"{key}: not a planet map")
        width, height, has_elev, n = struct.unpack("<IIBB", head[8:])
        palette = []
        for _ in range(n):
            r, g, b = f.read(3)
            palette.append(f"#{r:02x}{g:02x}{b:02x}")
        elevation = None
        if has_elev:
            elevation = array("h")
            elevation.frombytes(f.read(width * height * 2))
            if __import__("sys").byteorder != "little":
                elevation.byteswap()
        classes = f.read(width * height)
    if len(classes) != width * height:
        raise ValueError(f"{key}: map is truncated")
    return PlanetMap(width, height, palette, elevation, classes)


# ---------------------------------------------------------------- globe

def _grid(step, cap):
    """A (lon, lat) rectangle from 180° W to 180° E between the caps as
    counter-clockwise triangles."""
    lons = [-180.0 + step * i for i in range(int(round(360 / step)) + 1)]
    lats = [-cap + (2 * cap) * j / int(round(2 * cap / step))
            for j in range(int(round(2 * cap / step)) + 1)]
    pts = [(x, y) for y in lats for x in lons]
    n = len(lons)
    tris = []
    for j in range(len(lats) - 1):
        for i in range(n - 1):
            a, b = j * n + i, j * n + i + 1
            c, d = (j + 1) * n + i + 1, (j + 1) * n + i
            tris.append((a, b, c))
            tris.append((a, c, d))
    return pts, tris


def _groups(palette, count):
    """(class -> group, group palette): the palette's classes merged
    into *count* tones by brightness (None keeps every class)."""
    if count is None or count >= len(palette):
        return list(range(len(palette))), list(palette)
    lum = [sum(int(c[k:k + 2], 16) for k in (1, 3, 5)) for c in palette]
    order = sorted(range(len(palette)), key=lambda i: lum[i])
    group = [0] * len(palette)
    for rank, i in enumerate(order):
        group[i] = min(rank * count // len(palette), count - 1)
    colours = []
    for g in range(count):
        members = [i for i in range(len(palette)) if group[i] == g]
        rgb = [sum(int(palette[i][k:k + 2], 16) for i in members)
               // len(members) for k in (1, 3, 5)]
        colours.append("#%02x%02x%02x" % tuple(rgb))
    return group, colours


def globe_nodes(key: str, r: float, relief=None, fine=True) -> list:
    """The mapped body's surface: one coloured polyhedron per albedo
    class, in relief, plus the two polar caps."""
    body = D.BY_KEY[key]
    pmap = load(key)
    if relief is None:
        relief = RELIEF.get(key, 10.0)
    k = relief * r / (body["radius"] * 1000.0)
    setting = FINE if fine else COARSE

    def climb(lat, lon):
        return pmap.elev(lat, lon)

    def lift(p):
        lat = math.degrees(math.atan2(p[2], math.hypot(p[0], p[1])))
        lon = math.degrees(math.atan2(p[1], p[0]))
        return k * pmap.elev(lat, lon)
    pts, tris = _grid(setting["step"], CAP_LAT)
    plane = list(pts)
    tris = _flip_delaunay(plane, tris)
    chord, fine_chord = setting["chord"] * r, setting["fine_chord"] * r
    if pmap.elevation is None:
        fine_chord = chord
    from . import solar_earth
    saved = solar_earth.RELIEF_STEP
    solar_earth.RELIEF_STEP = setting["climb"]
    try:
        for _ in range(16):
            before = len(tris)
            tris = _refine(pts, tris, r, chord, fine_chord, climb)
            if len(tris) == before:
                break
            plane.extend(pts[len(plane):])
            tris = _flip_delaunay(plane, tris, passes=4)
    finally:
        solar_earth.RELIEF_STEP = saved
    sphere = [point(r, y, x) for x, y in pts]
    # a coarse globe (an orrery's 5 mm moon) keeps two tones, dark and
    # bright: every class boundary costs walls, and an albedo map's
    # boundaries are long
    group, palette = _groups(pmap.palette, 2 if not fine else None)
    by_class = {}
    for a, b, c in tris:
        lat = (pts[a][1] + pts[b][1] + pts[c][1]) / 3
        lon = (pts[a][0] + pts[b][0] + pts[c][0]) / 3
        by_class.setdefault(group[pmap.klass(lat, lon)], []).append(
            (sphere[a], sphere[b], sphere[c]))
    nodes = []
    for index in sorted(by_class):
        points, faces = _shell(by_class[index], r * SHELL[1], r * SHELL[0],
                               lift if pmap.elevation is not None else None)
        name = f"{body['label']} terrain {index + 1}"
        nodes.append(col(name, palette[index], CadNode(
            "polyhedron", name, dict(points=points, faces=faces))))
    for sign, name in ((1, "North polar cap"), (-1, "South polar cap")):
        colour = palette[group[pmap.klass(sign * 89.0, 0.0)]]
        lift_cap = 1.0 + k * pmap.elev(sign * 89.0, 0.0) / r
        nodes.append(band(name, r, sign * (CAP_LAT - 0.5), sign * 90.0,
                          colour, lift=max(lift_cap, 0.9)))
    return nodes
