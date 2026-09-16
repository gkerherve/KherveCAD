"""Aerial photographs under a map import.

Downloads the slippy-map tiles covering a latitude / longitude box from
a tile server (Esri World Imagery by default — its terms allow display
with attribution; any ``{z}/{y}/{x}`` template can be given), stitches
them with QImage, crops the mosaic to the box and saves one PNG. The
caller lays it on the Top plane as a reference image at the box's local
position, so the model can be checked against the photo (View ▸ Compare
to Reference Image draws it over the model as an onion skin).

Qt is only needed for the JPEG decode and the PNG write; the tile maths
is `geo`.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
import urllib.request

from .geo import urlopen as geo_urlopen

from . import geo

ESRI = ("https://server.arcgisonline.com/ArcGIS/rest/services/"
        "World_Imagery/MapServer/tile/{z}/{y}/{x}")
ATTRIBUTION = ("Imagery: Esri, Maxar, Earthstar Geographics and the GIS "
               "User Community")
USER_AGENT = "KherveCAD map import (https://khervetools.com)"
MAX_TILES = 400


class AerialError(RuntimeError):
    """The photographs could not be downloaded or stitched."""


def http_get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with geo_urlopen(req, timeout) as r:
        return r.read()


def fetch(bbox, path, template=ESRI, max_pixels=4096, opener=http_get):
    """Write the cropped mosaic to *path*; returns (width_px, height_px,
    zoom)."""
    from PyQt5.QtCore import QRect
    from PyQt5.QtGui import QImage, QPainter

    s, w, n, e = bbox
    z = geo.zoom_for(bbox, max_pixels)
    fx0, fy0 = geo.tile_xy(n, w, z)
    fx1, fy1 = geo.tile_xy(s, e, z)
    tx0, ty0 = int(math.floor(fx0)), int(math.floor(fy0))
    tx1, ty1 = int(math.floor(fx1)), int(math.floor(fy1))
    count = (tx1 - tx0 + 1) * (ty1 - ty0 + 1)
    if count > MAX_TILES:
        raise AerialError(f"{count} tiles is too many; import a smaller "
                          "area")
    mosaic = QImage((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256,
                    QImage.Format_RGB32)
    mosaic.fill(0x808080)
    painter = QPainter(mosaic)
    failed = 0
    try:
        for ty in range(ty0, ty1 + 1):
            for tx in range(tx0, tx1 + 1):
                try:
                    data = opener(template.format(z=z, x=tx, y=ty))
                except OSError:
                    failed += 1
                    continue
                tile = QImage()
                if not tile.loadFromData(data):
                    failed += 1
                    continue
                painter.drawImage((tx - tx0) * 256, (ty - ty0) * 256, tile)
    finally:
        painter.end()
    if failed == count:
        raise AerialError("No aerial tiles could be downloaded")
    crop = QRect(int(round((fx0 - tx0) * 256)), int(round((fy0 - ty0) * 256)),
                 max(1, int(round((fx1 - fx0) * 256))),
                 max(1, int(round((fy1 - fy0) * 256))))
    out = mosaic.copy(crop)
    if not out.save(path, "PNG"):
        raise AerialError(f"Could not write {path}")
    return out.width(), out.height(), z


def reference_for(bbox, projection, path, opacity=1.0, offset=-250.0):
    """The reference-image dict laying the photo over its ground."""
    s, w, n, e = bbox
    x0, y0 = projection.to_local(s, w)
    x1, y1 = projection.to_local(n, e)
    return dict(path=path, plane="Top (XY)", x=x0, y=y0, width=x1 - x0,
                height=y1 - y0, offset=offset, opacity=opacity, visible=True)
