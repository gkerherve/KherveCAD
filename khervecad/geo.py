"""Geographic helpers for the map import (Qt-free).

`Projection` maps WGS84 latitude / longitude to the document's local
millimetres and back: x east, y north, the origin at the area's centre.
It is a local tangent approximation (equirectangular about the centre,
radii from the WGS84 ellipsoid at that latitude) — within a couple of
kilometres it is right to a few centimetres, which is all a village
needs, and it has no dependency.

Also the bounding-box helpers every downloader shares, and slippy-map
tile arithmetic for the aerial photos.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

A = 6378137.0                    # WGS84 semi-major axis, m
E2 = 6.69437999014e-3            # first eccentricity squared


def urlopen(request, timeout=120):
    """urllib's urlopen with a CA bundle that works in a frozen build
    and on python.org's macOS Python (certifi when present, as the
    updater does)."""
    import ssl
    import urllib.request
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except Exception:
        pass
    return urllib.request.urlopen(request, timeout=timeout, context=ctx)


class GeoError(ValueError):
    """A location or area that cannot be used (the message says why)."""


class Projection:
    """Local metres (as mm) about (lat0, lon0)."""

    def __init__(self, lat0: float, lon0: float):
        self.lat0, self.lon0 = float(lat0), float(lon0)
        phi = math.radians(self.lat0)
        s = math.sin(phi)
        w = math.sqrt(1 - E2 * s * s)
        #: metres per degree of latitude and longitude here
        self.m_lat = math.radians(1) * A * (1 - E2) / w ** 3
        self.m_lon = math.radians(1) * A * math.cos(phi) / w

    def to_local(self, lat, lon):
        return ((lon - self.lon0) * self.m_lon * 1000.0,
                (lat - self.lat0) * self.m_lat * 1000.0)

    def to_latlon(self, x, y):
        return (self.lat0 + y / 1000.0 / self.m_lat,
                self.lon0 + x / 1000.0 / self.m_lon)

    def as_dict(self):
        return {"lat0": self.lat0, "lon0": self.lon0}


def bbox_from(params: dict):
    """(south, west, north, east) from ``bbox`` [s, w, n, e] or ``center``
    [lat, lon] with ``radius_m`` (a square that far each way)."""
    if params.get("bbox"):
        try:
            s, w, n, e = (float(v) for v in params["bbox"])
        except (TypeError, ValueError):
            raise GeoError("bbox must be [south, west, north, east] in "
                           "degrees")
    elif params.get("center"):
        try:
            lat, lon = (float(v) for v in params["center"])
        except (TypeError, ValueError):
            raise GeoError("center must be [latitude, longitude]")
        r = float(params.get("radius_m") or 300.0)
        p = Projection(lat, lon)
        s, w = p.to_latlon(-r * 1000, -r * 1000)
        n, e = p.to_latlon(r * 1000, r * 1000)
    else:
        raise GeoError("Give center [lat, lon] (+ radius_m) or bbox "
                       "[south, west, north, east].")
    if not (-90 <= s < n <= 90 and -180 <= w < e <= 180):
        raise GeoError("bbox corners are out of order or out of range")
    p = Projection((s + n) / 2, (w + e) / 2)
    x0, y0 = p.to_local(s, w)
    x1, y1 = p.to_local(n, e)
    if (x1 - x0) > 5e6 or (y1 - y0) > 5e6:
        raise GeoError("The area is more than 5 km across — import a "
                       "smaller piece (a village is a few hundred metres).")
    return s, w, n, e


def projection_for(bbox):
    s, w, n, e = bbox
    return Projection((s + n) / 2, (w + e) / 2)


# ------------------------------------------------------------ map tiles
def tile_xy(lat, lon, zoom):
    """Fractional slippy-map tile coordinates (Web Mercator)."""
    n = 2 ** zoom
    x = (lon + 180.0) / 360.0 * n
    lat = max(min(lat, 85.05112878), -85.05112878)
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def tile_latlon(x, y, zoom):
    """Latitude / longitude of fractional tile coordinates."""
    n = 2 ** zoom
    lon = x / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lat, lon


def zoom_for(bbox, max_pixels=4096, max_zoom=19):
    """The deepest zoom whose mosaic of the box stays within max_pixels
    on its longer side."""
    s, w, n, e = bbox
    for z in range(max_zoom, 0, -1):
        x0, y0 = tile_xy(n, w, z)
        x1, y1 = tile_xy(s, e, z)
        if max(x1 - x0, y1 - y0) * 256 <= max_pixels:
            return z
    return 1
