"""Build ``khervecad/solar/earth_elevation.bin.gz`` from a global
GeoTIFF of ETOPO 2022 (NOAA, public domain), e.g. the 0.25° export of
the DEM_global_mosaic image service:

    python -m khervecad.tools.earth_elevation etopo_1440x720.tif

The file is the grid as little-endian int16 metres, ocean clamped to
0 (the globe only lifts land), after a 16-byte header: the magic
``KCADELEV``, then width and height as uint32. `solar_earth.elevation`
reads it back.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import gzip
import struct
import sys
from array import array
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "solar" / "earth_elevation.bin.gz"
MAGIC = b"KCADELEV"


def main(argv):
    from khervecad import geotiff
    if len(argv) != 1:
        sys.exit(__doc__)
    raster = geotiff.read(Path(argv[0]).read_bytes())
    a, _b, c, _d, e, f = raster.transform
    assert abs(c + 180) < 1e-6 and abs(f - 90) < 1e-6 and abs(
        a * raster.width - 360) < 1e-3 and abs(e * raster.height + 180) < 1e-3, \
        "expected a global grid from 180 W, 90 N"
    grid = array("h")
    for row in raster.values:
        grid.extend(int(round(max(min(v if raster.valid(v) else 0.0, 32000.0),
                                  0.0))) for v in row)
    if sys.byteorder != "little":
        grid.byteswap()
    with gzip.open(OUT, "wb") as fh:
        fh.write(MAGIC + struct.pack("<II", raster.width, raster.height))
        fh.write(grid.tobytes())
    print("wrote", OUT, OUT.stat().st_size, "bytes;", raster.width, "x",
          raster.height, "max", max(grid), "m")


if __name__ == "__main__":
    main(sys.argv[1:])
