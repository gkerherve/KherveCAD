"""Build the ``khervecad/solar/<key>.kmap.gz`` maps `solar_raster`
reads — an albedo class raster quantised from a mission mosaic and,
for the Moon and Mars, an elevation raster — from NASA / USGS public
domain data:

    python -m khervecad.tools.planet_maps [--src DIR] [keys...]

Each source is downloaded into DIR (default a ``planet_maps`` folder
in the temp dir) unless already there. SOURCES lists what and where:
the Moon's LOLA 4 pixel/degree DEM and LROC colour from NASA SVS's
"CGI Moon Kit", Mars' MOLA MEGDR 4 pixel/degree grid from the PDS and
the Viking MDIM 2.1 colour mosaic, and the USGS Astrogeology map
server's mosaics (MESSENGER, Magellan, Galileo / Voyager, Cassini,
New Horizons) for the rest. A greyscale mosaic is tinted with the
body's colour; every mosaic is reduced to a handful of classes by
k-means, the palette being the class means.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os
import random
import struct
import sys
import tempfile
import urllib.request
from pathlib import Path

USGS = ("https://planetarymaps.usgs.gov/cgi-bin/mapserv?map=/maps/{planet}/"
        "{body}_simp_cyl.map&SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&"
        "LAYERS={layer}&STYLES=&SRS=EPSG:4326&BBOX=-180,-90,180,90&"
        "WIDTH={w}&HEIGHT={h}&FORMAT=image/png")
SVS = "https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/"
PDS_MOLA = ("https://pds-geosciences.wustl.edu/mgs/mgs-m-mola-5-megdr-l3-v1/"
            "mgsl_300x/meg004/megt90n000cb.img")


def usgs(planet, body, layer, w, h):
    return USGS.format(planet=planet, body=body, layer=layer, w=w, h=h)


#: key -> dict(size, classes, colour source, tint, elevation source)
SOURCES = {
    "moon": dict(size=(720, 360), classes=6,
                 color=("moon_color.jpg", SVS + "lroc_color_poles_1k.jpg"),
                 elevation=("moon_ldem_4.tif", SVS + "ldem_4.tif", "tif_km")),
    "mars": dict(size=(720, 360), classes=6,
                 color=("mars_color.png",
                        usgs("mars", "mars", "MDIM21_color", 1440, 720)),
                 elevation=("mars_megt.img", PDS_MOLA, "pds16")),
    "mercury": dict(size=(720, 360), classes=5,
                    color=("mercury_color.png",
                           usgs("mercury", "mercury", "MESSENGER_Color",
                                1440, 720))),
    "venus": dict(size=(720, 360), classes=5, tint="#e6cf9d",
                  color=("venus_color.png",
                         usgs("venus", "venus", "MAGELLAN_color", 1440,
                              720))),
    "pluto": dict(size=(720, 360), classes=5, tint="#c9a88a",
                  color=("pluto_color.png",
                         usgs("pluto", "pluto", "NEWHORIZONS_PLUTO_MOSAIC",
                              1440, 720))),
    "charon": dict(size=(720, 360), classes=4, tint="#b5aaa2",
                   color=("charon_color.png",
                          usgs("pluto", "charon",
                               "NEWHORIZONS_CHARON_MOSAIC", 720, 360))),
    "io": dict(size=(720, 360), classes=6,
               color=("io_color.png", usgs("jupiter", "io", "SSI_color",
                                           1440, 720))),
    "europa": dict(size=(720, 360), classes=4, tint="#d9cdb6",
                   color=("europa_color.png",
                          usgs("jupiter", "europa", "GALILEO_VOYAGER", 720,
                               360))),
    "ganymede": dict(size=(720, 360), classes=4, tint="#9c8f7e",
                     color=("ganymede_color.png",
                            usgs("jupiter", "ganymede", "GALILEO_VOYAGER",
                                 720, 360))),
    "callisto": dict(size=(720, 360), classes=4, tint="#625850",
                     color=("callisto_color.png",
                            usgs("jupiter", "callisto", "GALILEO_VOYAGER",
                                 720, 360))),
    "mimas": dict(size=(720, 360), classes=4, tint="#c8c6c2",
                  color=("mimas_color.png",
                         usgs("saturn", "mimas", "CASSINI_MIMAS_MOSAIC", 720,
                              360))),
    "enceladus": dict(size=(720, 360), classes=4, tint="#f2f4f6",
                      color=("enceladus_color.png",
                             usgs("saturn", "enceladus", "CASSINI", 720,
                                  360))),
    "tethys": dict(size=(720, 360), classes=4, tint="#dcd9d3",
                   color=("tethys_color.png",
                          usgs("saturn", "tethys", "CASSINI", 720, 360))),
    "dione": dict(size=(720, 360), classes=4, tint="#cfcac3",
                  color=("dione_color.png",
                         usgs("saturn", "dione", "CASSINI_VOYAGER", 720,
                              360))),
    "rhea": dict(size=(720, 360), classes=4, tint="#c6c1ba",
                 color=("rhea_color.png",
                        usgs("saturn", "rhea", "CASSINI_VOYAGER", 720, 360))),
    "titan": dict(size=(720, 360), classes=4, tint="#d4912f",
                  color=("titan_color.png",
                         usgs("saturn", "titan", "CASSINI", 720, 360))),
    "iapetus": dict(size=(720, 360), classes=4, tint="#d8d2c8",
                    color=("iapetus_color.png",
                           usgs("saturn", "iapetus", "CASSINI_VOYAGER", 720,
                                360))),
    "triton": dict(size=(720, 360), classes=4, tint="#d5c8be",
                   color=("triton_color.png",
                          usgs("neptune", "triton", "TRITON_VOYAGER2", 720,
                               360))),
    "phobos": dict(size=(720, 360), classes=3, tint="#6f645b",
                   color=("phobos_color.png",
                          usgs("mars", "phobos", "VIKING", 720, 360))),
    "deimos": dict(size=(720, 360), classes=3, tint="#7b7169",
                   color=("deimos_color.png",
                          usgs("mars", "deimos", "VIKING", 720, 360))),
}


def fetch(src_dir: Path, name: str, url: str) -> Path:
    path = src_dir / name
    if not path.exists():
        print("downloading", url)
        req = urllib.request.Request(url, headers={"User-Agent": "KherveCAD"})
        with urllib.request.urlopen(req, timeout=600) as resp:
            path.write_bytes(resp.read())
    return path


# --------------------------------------------------------- elevation

def _tiff_float32(data: bytes):
    """A plain uncompressed float32 TIFF (NASA SVS's ldem_4.tif has no
    georeference, so the GeoTIFF reader refuses it): (width, height,
    rows)."""
    bo = "<" if data[:2] == b"II" else ">"
    (ifd,) = struct.unpack(bo + "I", data[4:8])
    (count,) = struct.unpack(bo + "H", data[ifd:ifd + 2])
    tags = {}
    sizes = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8,
             11: 4, 12: 8, 16: 8}
    for i in range(count):
        entry = ifd + 2 + 12 * i
        tag, typ, n, value = struct.unpack(bo + "HHII", data[entry:entry + 12])
        if typ not in (3, 4):
            continue                          # only counts and offsets matter
        size = sizes[typ]
        if n * size <= 4:
            if typ == 3:
                value = struct.unpack(bo + "H", data[entry + 8:entry + 10])[0]
            tags[tag] = [value]
        else:
            fmt = {3: "H", 4: "I"}[typ]
            tags[tag] = list(struct.unpack(
                bo + fmt * n, data[value:value + n * size]))
    width, height = tags[256][0], tags[257][0]
    assert tags.get(259, [1])[0] == 1, "compressed TIFF"
    assert tags.get(258, [32])[0] == 32 and tags.get(339, [3])[0] == 3, \
        "expected float32 samples"
    offsets, counts = tags[273], tags[279]
    raw = b"".join(data[o:o + c] for o, c in zip(offsets, counts))
    values = struct.unpack(bo + "f" * (width * height), raw[:width * height * 4])
    return width, height, [values[j * width:(j + 1) * width]
                           for j in range(height)]


def read_elevation(path: Path, kind: str, size):
    """Metres as a row-major list at *size* (nearest resampling)."""
    w, h = size
    if kind == "tif_km":
        sw, sh, rows = _tiff_float32(path.read_bytes())
        scale = 1000.0
    elif kind == "pds16":
        data = path.read_bytes()
        sw, sh = 1440, 720
        vals = struct.unpack(">" + "h" * (sw * sh), data[:sw * sh * 2])
        # a MEGDR global grid starts at 0° E: roll it to start at 180° W
        rows = [vals[j * sw + sw // 2:(j + 1) * sw] + vals[j * sw:j * sw + sw // 2]
                for j in range(sh)]
        scale = 1.0
    else:
        raise ValueError(kind)
    out = []
    for j in range(h):
        row = rows[min(int(j * sh / h), sh - 1)]
        for i in range(w):
            v = row[min(int(i * sw / w), sw - 1)] * scale
            out.append(int(round(max(min(v, 32767), -32768))))
    return out


# ------------------------------------------------------------ albedo

def read_colour(path: Path, size):
    """The mosaic resampled to *size*: a flat list of (r, g, b)."""
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QImage
    img = QImage(str(path))
    if img.isNull():
        raise ValueError(f"cannot read {path}")
    w, h = size
    img = img.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    img = img.convertToFormat(QImage.Format_RGB32)
    out = []
    for j in range(h):
        for i in range(w):
            p = img.pixel(i, j)
            out.append(((p >> 16) & 255, (p >> 8) & 255, p & 255))
    return out


def fill_gaps(pixels, w, h, dark=24):
    """Unmapped ground in a mosaic is black (Io's poles, the half of
    Pluto New Horizons never saw): each black cell takes the nearest
    mapped cell along its row, a wholly black row the nearest mapped
    row, so no-data never becomes a black class."""
    cells = list(pixels)
    mapped = [sum(p) > dark for p in cells]
    last_row = None
    for j in range(h):
        row = j * w
        if not any(mapped[row:row + w]):
            continue
        last_row = j
        prev = None
        for i in range(w):
            if mapped[row + i]:
                prev = cells[row + i]
            elif prev is not None:
                cells[row + i] = prev
        nxt = None
        for i in range(w - 1, -1, -1):
            if mapped[row + i]:
                nxt = cells[row + i]
            elif not sum(cells[row + i]) > dark and nxt is not None:
                cells[row + i] = nxt
    # rows with nothing mapped copy the nearest mapped row
    good = [j for j in range(h) if any(mapped[j * w:(j + 1) * w])]
    for j in range(h):
        if j in good or not good:
            continue
        src = min(good, key=lambda g: abs(g - j))
        cells[j * w:(j + 1) * w] = cells[src * w:(src + 1) * w]
    return cells


def quantise(pixels, k, seed=1, iterations=14):
    """k-means over the pixels: (palette [(r, g, b)], class per pixel),
    the palette sorted darkest first."""
    rng = random.Random(seed)
    sample = pixels if len(pixels) <= 40000 else rng.sample(pixels, 40000)
    centres = [list(c) for c in rng.sample(sample, k)]
    for _ in range(iterations):
        sums = [[0.0, 0.0, 0.0, 0] for _ in centres]
        for p in sample:
            best = min(range(k), key=lambda n: (p[0] - centres[n][0]) ** 2
                       + (p[1] - centres[n][1]) ** 2
                       + (p[2] - centres[n][2]) ** 2)
            s = sums[best]
            s[0] += p[0]
            s[1] += p[1]
            s[2] += p[2]
            s[3] += 1
        for n, s in enumerate(sums):
            if s[3]:
                centres[n] = [s[0] / s[3], s[1] / s[3], s[2] / s[3]]
    centres.sort(key=lambda c: c[0] + c[1] + c[2])
    classes = bytes(min(range(k), key=lambda n: (p[0] - centres[n][0]) ** 2
                        + (p[1] - centres[n][1]) ** 2
                        + (p[2] - centres[n][2]) ** 2) for p in pixels)
    return [tuple(int(round(v)) for v in c) for c in centres], classes


def smooth(classes, w, h, radius=2, passes=2):
    """A majority filter over a (2 radius + 1) square, wrapping in
    longitude: k-means leaves single-cell speckle, and on the globe each
    speck of a class is an island needing walls of its own — Iapetus
    came out at 80k triangles from speckle alone."""
    cells = bytearray(classes)
    for _ in range(passes):
        out = bytearray(cells)
        for j in range(h):
            j0, j1 = max(j - radius, 0), min(j + radius, h - 1)
            for i in range(w):
                counts = {}
                for jj in range(j0, j1 + 1):
                    row = jj * w
                    for di in range(-radius, radius + 1):
                        c = cells[row + (i + di) % w]
                        counts[c] = counts.get(c, 0) + 1
                best = max(counts.items(), key=lambda kv: (kv[1], kv[0]
                                                           == cells[j * w + i]))
                out[j * w + i] = best[0]
        cells = out
    return bytes(cells)


def tinted(palette, tint):
    """A greyscale palette coloured like *tint* (#rrggbb): each class
    keeps its brightness relative to the palette's mean."""
    base = [int(tint[k:k + 2], 16) for k in (1, 3, 5)]
    lum = [sum(c) / 3 for c in palette]
    mean = sum(lum) / len(lum) or 1.0
    out = []
    for value in lum:
        f = value / mean
        out.append(tuple(min(255, int(round(b * f))) for b in base))
    return out


def build(key: str, src_dir: Path):
    from khervecad import solar_raster
    spec = SOURCES[key]
    size = spec["size"]
    name, url = spec["color"][:2]
    pixels = fill_gaps(read_colour(fetch(src_dir, name, url), size), *size)
    palette, classes = quantise(pixels, spec["classes"])
    classes = smooth(classes, size[0], size[1])
    if spec.get("tint"):
        palette = tinted(palette, spec["tint"])
    elevation = None
    if spec.get("elevation"):
        ename, eurl, kind = spec["elevation"]
        elevation = read_elevation(fetch(src_dir, ename, eurl), kind, size)
    out = solar_raster.path_of(key)
    solar_raster.write(out, size[0], size[1],
                       [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in palette],
                       elevation, classes)
    print(f"{key}: {size[0]}x{size[1]}, {len(palette)} classes"
          f"{', elevation' if elevation else ''} -> {out.stat().st_size} bytes")


def main(argv):
    src = Path(tempfile.gettempdir()) / "planet_maps"
    keys = []
    it = iter(argv)
    for arg in it:
        if arg == "--src":
            src = Path(next(it))
        else:
            keys.append(arg)
    src.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt5.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    for key in keys or list(SOURCES):
        build(key, src)


if __name__ == "__main__":
    main(sys.argv[1:])
