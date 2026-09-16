"""Heights from LiDAR for the map import (Qt-free).

England's Environment Agency publishes its 1 m LiDAR composites free
(Open Government Licence) through a WCS: the DTM (bare ground) and the
first-return DSM (the top of whatever is there — roofs, tree crowns).
`Heights` downloads both for a latitude / longitude box (asking the
service to reproject into WGS84, so no National Grid maths is needed)
and answers three questions:

- `ground_grid`: the terrain under the model as a height field the City
  Builder levels roads and pads on;
- `building_height`: how tall a building is — a high percentile of
  DSM - DTM over its footprint, so chimneys and a stray tree over one
  corner do not decide it;
- `detect_trees`: tree tops in the canopy height model (DSM - DTM) —
  local maxima at least `MIN_TREE` high, off every building footprint,
  thinned so two tops are not closer than their crowns — with a crown
  radius measured from the canopy around each top.

Outside England (or where the survey has a gap) the service returns
no-data and the callers fall back: flat ground, OSM heights, OSM trees.
The downloader is injectable (`opener(url) -> bytes`) so tests never
touch the network.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
import urllib.parse
import urllib.request

from .geo import urlopen as geo_urlopen

from . import geotiff

SERVICE = "https://environment.data.gov.uk/spatialdata/{layer}/wcs"
LAYERS = {
    "dtm": ("lidar-composite-digital-terrain-model-dtm-1m",
            "13787b9a-26a4-4775-8523-806d13af58fc__"
            "Lidar_Composite_Elevation_DTM_1m"),
    "dsm": ("lidar-composite-digital-surface-model-first-return-dsm-1m",
            "df4e3ec3-315e-48aa-aaaf-b5ae74d7b2bb__"
            "Lidar_Composite_Elevation_FZ_DSM_1m"),
}
#: degrees per download chunk (~550 m north-south)
CHUNK = 0.005
MIN_TREE = 4.0                 # m, a canopy lower than this is a hedge
BUILDING_CLEAR = 1.5           # m kept clear round a footprint
USER_AGENT = "KherveCAD map import (https://khervetools.com)"


class LidarError(RuntimeError):
    """The survey could not be downloaded or read."""


def http_get(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with geo_urlopen(req, timeout) as r:
        return r.read()


def coverage_url(kind, s, w, n, e):
    layer, cov = LAYERS[kind]
    q = [("service", "WCS"), ("version", "2.0.1"),
         ("request", "GetCoverage"), ("CoverageId", cov),
         ("subset", f"Lat({s:.7f},{n:.7f})"),
         ("subset", f"Long({w:.7f},{e:.7f})"),
         ("subsettingCrs", "http://www.opengis.net/def/crs/EPSG/0/4326"),
         ("format", "image/tiff")]
    return SERVICE.format(layer=layer) + "?" + urllib.parse.urlencode(q)


class Mosaic:
    """Several rasters answering `sample(lon, lat)` together."""

    def __init__(self, rasters):
        self.rasters = rasters

    def sample(self, lon, lat):
        for r in self.rasters:
            v = r.sample(lon, lat)
            if v is not None and v > -1000:
                return v
        return None


def fetch(kind, bbox, opener=http_get):
    s, w, n, e = bbox
    rows = max(1, math.ceil((n - s) / CHUNK))
    cols = max(1, math.ceil((e - w) / (CHUNK * 1.6)))
    rasters = []
    for j in range(rows):
        for i in range(cols):
            cs, cn = s + (n - s) * j / rows, s + (n - s) * (j + 1) / rows
            cw, ce = w + (e - w) * i / cols, w + (e - w) * (i + 1) / cols
            pad = 0.00003                       # a few metres of overlap
            try:
                data = opener(coverage_url(kind, cs - pad, cw - pad,
                                           cn + pad, ce + pad))
                rasters.append(geotiff.read(data))
            except geotiff.GeoTiffError as exc:
                raise LidarError(f"The {kind.upper()} download could not "
                                 f"be read ({exc}); the area may be "
                                 "outside England's LiDAR survey.")
            except OSError as exc:
                raise LidarError(f"The {kind.upper()} download failed: "
                                 f"{exc}")
    return Mosaic(rasters)


class Heights:
    """The DTM and DSM of a box, fetched on first use."""

    def __init__(self, bbox, projection, opener=http_get):
        self.bbox = bbox
        self.proj = projection
        self.opener = opener
        self._dtm = self._dsm = None

    @property
    def dtm(self):
        if self._dtm is None:
            self._dtm = fetch("dtm", self.bbox, self.opener)
        return self._dtm

    @property
    def dsm(self):
        if self._dsm is None:
            self._dsm = fetch("dsm", self.bbox, self.opener)
        return self._dsm

    def ground(self, x, y):
        """Ground height in metres at local (x, y) mm, or None."""
        lat, lon = self.proj.to_latlon(x, y)
        return self.dtm.sample(lon, lat)

    def canopy(self, x, y):
        lat, lon = self.proj.to_latlon(x, y)
        g, top = self.dtm.sample(lon, lat), self.dsm.sample(lon, lat)
        if g is None or top is None:
            return None
        return top - g

    # --------------------------------------------------------- terrain
    def ground_grid(self, x0, y0, length, width, n):
        """(n+1) x (n+1) ground heights in mm over the rectangle, relative
        to the lowest point, plus that base (m) and how many samples were
        missing (filled from their neighbours)."""
        raw, missing = [], 0
        for j in range(n + 1):
            row = []
            for i in range(n + 1):
                v = self.ground(x0 + length * i / n, y0 + width * j / n)
                if v is None:
                    missing += 1
                row.append(v)
            raw.append(row)
        good = [v for row in raw for v in row if v is not None]
        if not good:
            raise LidarError("No LiDAR ground heights here — the area is "
                             "outside England's survey.")
        mean = sum(good) / len(good)
        for j in range(n + 1):
            for i in range(n + 1):
                if raw[j][i] is None:
                    near = [raw[jj][ii] for jj in range(max(0, j - 2),
                                                       min(n, j + 2) + 1)
                            for ii in range(max(0, i - 2), min(n, i + 2) + 1)
                            if raw[jj][ii] is not None]
                    raw[j][i] = sum(near) / len(near) if near else mean
        base = min(min(row) for row in raw)
        return [[(v - base) * 1000.0 for v in row] for row in raw], base, \
            missing

    # -------------------------------------------------------- buildings
    def building_shape(self, polygon, step=1000.0):
        """(eaves, ridge) heights in mm above the ground from DSM - DTM:
        the ridge is the 90th percentile over the footprint, the eaves
        the median of the samples within 1.5 m of the outline. None where
        the survey has too little."""
        xs = [p[0] for p in polygon]
        ys = [p[1] for p in polygon]
        edge, all_ = [], []
        x = min(xs) + step / 2
        while x < max(xs):
            y = min(ys) + step / 2
            while y < max(ys):
                if inside(polygon, x, y):
                    c = self.canopy(x, y)
                    if c is not None and c > 1.0:
                        all_.append(c)
                        if edge_distance(polygon, x, y) < 1500.0:
                            edge.append(c)
                y += step
            x += step
        if len(all_) < 4:
            return None
        all_.sort()
        ridge = all_[min(len(all_) - 1, int(len(all_) * 0.9))]
        edge.sort()
        eaves = edge[len(edge) // 2] if edge else ridge * 0.6
        return min(eaves, ridge) * 1000.0, ridge * 1000.0

    def building_height(self, polygon, step=1000.0):
        """Height (mm) of a building from DSM - DTM over its footprint
        (local mm polygon): the 85th percentile of the samples inside,
        or None where the survey has nothing."""
        xs = [p[0] for p in polygon]
        ys = [p[1] for p in polygon]
        vals = []
        x = min(xs) + step / 2
        while x < max(xs):
            y = min(ys) + step / 2
            while y < max(ys):
                if inside(polygon, x, y):
                    c = self.canopy(x, y)
                    if c is not None:
                        vals.append(c)
                y += step
            x += step
        if len(vals) < 3:
            c = self.canopy(sum(xs) / len(xs), sum(ys) / len(ys))
            vals = [c] if c is not None else []
        if not vals:
            return None
        vals.sort()
        h = vals[min(len(vals) - 1, int(len(vals) * 0.85))]
        return h * 1000.0 if h > 1.5 else None

    # ------------------------------------------------------------ trees
    def detect_trees(self, x0, y0, x1, y1, footprints=(), step=1000.0,
                     min_height=MIN_TREE, limit=3000):
        """Tree tops in the box: [{x, y, height (mm), crown (mm radius)}].
        *footprints* are local-mm polygons whose area (and a margin) holds
        no tree."""
        nx = int((x1 - x0) // step) + 1
        ny = int((y1 - y0) // step) + 1
        # building mask on the same grid
        blocked = set()
        clear = BUILDING_CLEAR * 1000.0
        for poly in footprints:
            px = [p[0] for p in poly]
            py = [p[1] for p in poly]
            i0 = max(0, int((min(px) - clear - x0) // step))
            i1 = min(nx - 1, int((max(px) + clear - x0) // step) + 1)
            j0 = max(0, int((min(py) - clear - y0) // step))
            j1 = min(ny - 1, int((max(py) + clear - y0) // step) + 1)
            for j in range(j0, j1 + 1):
                for i in range(i0, i1 + 1):
                    x, y = x0 + i * step, y0 + j * step
                    if inside(poly, x, y) or edge_distance(poly, x, y) < clear:
                        blocked.add((i, j))
        chm = [[None] * nx for _ in range(ny)]
        for j in range(ny):
            for i in range(nx):
                if (i, j) in blocked:
                    continue
                c = self.canopy(x0 + i * step, y0 + j * step)
                if c is not None and c >= min_height * 0.5:
                    chm[j][i] = c
        tops = []
        r = 2
        for j in range(ny):
            for i in range(nx):
                c = chm[j][i]
                if c is None or c < min_height:
                    continue
                peak = True
                for jj in range(max(0, j - r), min(ny, j + r + 1)):
                    for ii in range(max(0, i - r), min(nx, i + r + 1)):
                        o = chm[jj][ii]
                        if o is not None and (o > c or (o == c and
                                                        (jj, ii) < (j, i))):
                            peak = False
                            break
                    if not peak:
                        break
                if peak:
                    tops.append((c, i, j))
        tops.sort(reverse=True)
        kept = []
        for c, i, j in tops:
            crown = _crown(chm, i, j, c, nx, ny) * step
            x, y = x0 + i * step, y0 + j * step
            if any(math.hypot(x - k["x"], y - k["y"]) <
                   max(k["crown"], crown) * 0.8 for k in kept):
                continue
            kept.append(dict(x=x, y=y, height=c * 1000.0, crown=crown))
            if len(kept) >= limit:
                break
        return kept


def _crown(chm, i, j, peak, nx, ny):
    """Radius (cells) out to which the canopy stays above half the top,
    the mean over eight directions."""
    radii = []
    for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1),
                   (1, -1), (-1, 1)):
        k = 1
        while k < 15:
            ii, jj = i + di * k, j + dj * k
            if not (0 <= ii < nx and 0 <= jj < ny):
                break
            v = chm[jj][ii]
            if v is None or v < peak * 0.5:
                break
            k += 1
        radii.append(k * math.hypot(di, dj))
    return max(1.5, sum(radii) / len(radii))


def tree_kind(height_mm, crown_mm):
    """A species that looks like the measured tree: tall and narrow
    reads as a poplar or conifer, broad as an oak, small as fruit."""
    h, r = height_mm / 1000.0, crown_mm / 1000.0
    ratio = r / max(h, 1.0)
    if h < 6.0:
        return "maple" if ratio > 0.3 else "birch"
    if ratio < 0.15:
        return "poplar" if h > 16 else "cypress"
    if ratio < 0.22:
        return "spruce" if h > 12 else "birch"
    if h > 15:
        return "oak"
    return "maple" if ratio > 0.3 else "lime"


def inside(poly, x, y):
    """Even-odd point in polygon."""
    c = False
    n = len(poly)
    for k in range(n):
        ax, ay = poly[k]
        bx, by = poly[(k + 1) % n]
        if (ay > y) != (by > y):
            t = (y - ay) / (by - ay)
            if x < ax + t * (bx - ax):
                c = not c
    return c


def edge_distance(poly, x, y):
    best = float("inf")
    n = len(poly)
    for k in range(n):
        ax, ay = poly[k]
        bx, by = poly[(k + 1) % n]
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((x - ax) * dx +
                                                   (y - ay) * dy) / l2))
        best = min(best, math.hypot(ax + t * dx - x, ay + t * dy - y))
    return best
