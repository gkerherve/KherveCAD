"""A small GeoTIFF reader (Qt-free, no third-party imports): enough for
the height rasters the map import downloads — the Environment Agency's
LiDAR composites and other WCS services.

Reads one band of a baseline TIFF (either byte order, BigTIFF not
supported): strips or tiles; uncompressed, Deflate (8 / 32946), LZW (5)
or PackBits (32773); horizontal predictor 2 for integers and 3 for
floats; 8/16/32-bit integers and 32/64-bit floats. The georeference is
the ModelTransformation tag (34264) or ModelPixelScale + ModelTiepoint
(33550 + 33922); the GDAL no-data tag (42113) is honoured.

`read(data)` -> `Raster`: `values[row][col]` (row 0 is the top edge),
`transform` (a, b, c, d, e, f) mapping pixel CORNER (col, row) to world
(x = a*col + b*row + c, y = d*col + e*row + f), and `nodata`.
`Raster.sample(x, y)` is bilinear between pixel centres and returns None
where any neighbour is no-data or outside.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
import struct
import zlib

_TYPES = {1: ("B", 1), 2: ("c", 1), 3: ("H", 2), 4: ("I", 4), 5: ("II", 8),
          6: ("b", 1), 7: ("B", 1), 8: ("h", 2), 9: ("i", 4), 10: ("ii", 8),
          11: ("f", 4), 12: ("d", 8), 16: ("Q", 8)}


class GeoTiffError(ValueError):
    """A file this reader cannot decode (the message says why)."""


class Raster:
    def __init__(self, width, height, values, transform, nodata):
        self.width, self.height = width, height
        self.values = values
        self.transform = transform
        self.nodata = nodata

    def world(self, col, row):
        a, b, c, d, e, f = self.transform
        return a * col + b * row + c, d * col + e * row + f

    def pixel(self, x, y):
        """(col, row) as floats of a world point (pixel corner frame)."""
        a, b, c, d, e, f = self.transform
        det = a * e - b * d
        if det == 0:
            raise GeoTiffError("degenerate georeference")
        dx, dy = x - c, y - f
        return (e * dx - b * dy) / det, (-d * dx + a * dy) / det

    def valid(self, v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return False
        return self.nodata is None or abs(v - self.nodata) > 1e-6 * max(
            1.0, abs(self.nodata))

    def sample(self, x, y):
        col, row = self.pixel(x, y)
        u, v = col - 0.5, row - 0.5
        i, j = math.floor(u), math.floor(v)
        if i < -1 or j < -1 or i > self.width - 1 or j > self.height - 1:
            return None
        i0, j0 = min(max(i, 0), self.width - 1), min(max(j, 0),
                                                      self.height - 1)
        i1, j1 = min(i0 + 1, self.width - 1), min(j0 + 1, self.height - 1)
        fu, fv = min(max(u - i, 0.0), 1.0), min(max(v - j, 0.0), 1.0)
        vals = self.values
        q = (vals[j0][i0], vals[j0][i1], vals[j1][i0], vals[j1][i1])
        if not all(self.valid(t) for t in q):
            good = [t for t in q if self.valid(t)]
            return sum(good) / len(good) if good else None
        return ((q[0] * (1 - fu) + q[1] * fu) * (1 - fv)
                + (q[2] * (1 - fu) + q[3] * fu) * fv)


def _lzw(data):
    out = bytearray()
    table = [bytes([i]) for i in range(256)] + [b"", b""]
    width, bitpos, prev = 9, 0, None
    nbits = len(data) * 8
    while bitpos + width <= nbits:
        byte = bitpos // 8
        chunk = int.from_bytes(data[byte:byte + 4].ljust(4, b"\0"), "big")
        code = (chunk >> (32 - width - (bitpos - byte * 8))) & (
            (1 << width) - 1)
        bitpos += width
        if code == 256:
            table = table[:258]
            width, prev = 9, None
            continue
        if code == 257:
            break
        if prev is None:
            entry = table[code]
        elif code < len(table):
            entry = table[code]
            table.append(prev + entry[:1])
        else:
            entry = prev + prev[:1]
            table.append(entry)
        out += entry
        prev = entry
        if len(table) + 1 >= (1 << width) and width < 12:
            width += 1
    return bytes(out)


def _packbits(data):
    out, i = bytearray(), 0
    while i < len(data):
        n = data[i]
        i += 1
        if n < 128:
            out += data[i:i + n + 1]
            i += n + 1
        elif n > 128:
            out += data[i:i + 1] * (257 - n)
            i += 1
    return bytes(out)


def read(data: bytes) -> Raster:
    if data[:2] == b"II":
        bo = "<"
    elif data[:2] == b"MM":
        bo = ">"
    else:
        raise GeoTiffError("not a TIFF file")
    magic = struct.unpack(bo + "H", data[2:4])[0]
    if magic != 42:
        raise GeoTiffError("BigTIFF or unknown TIFF variant")
    off = struct.unpack(bo + "I", data[4:8])[0]
    count = struct.unpack(bo + "H", data[off:off + 2])[0]
    tags = {}
    for k in range(count):
        p = off + 2 + 12 * k
        tag, typ, n = struct.unpack(bo + "HHI", data[p:p + 8])
        fmt, size = _TYPES.get(typ, ("B", 1))
        total = size * n
        raw = data[p + 8:p + 12] if total <= 4 else data[
            struct.unpack(bo + "I", data[p + 8:p + 12])[0]:][:total]
        if typ == 2:
            tags[tag] = raw.split(b"\0")[0].decode("latin-1")
        else:
            letter = fmt[0]
            per = len(fmt)
            vals = struct.unpack(bo + letter * (n * per), raw[:total])
            tags[tag] = list(vals)

    def one(tag, default=None):
        v = tags.get(tag)
        return v[0] if isinstance(v, list) and v else default

    width, height = one(256), one(257)
    if not width or not height:
        raise GeoTiffError("no image size")
    bits = one(258, 8)
    fmt_code = one(339, 1)
    compression = one(259, 1)
    predictor = one(317, 1)
    if one(277, 1) != 1 and one(284, 1) != 1:
        raise GeoTiffError("only single-band or planar rasters are read")
    spp = one(277, 1)
    letter = {(1, 8): "B", (1, 16): "H", (1, 32): "I", (2, 8): "b",
              (2, 16): "h", (2, 32): "i", (3, 32): "f",
              (3, 64): "d"}.get((fmt_code, bits))
    if letter is None:
        raise GeoTiffError(f"unsupported sample format {fmt_code}/{bits}")
    nbytes = bits // 8

    def decode(chunk):
        if compression in (1, None):
            return chunk
        if compression in (8, 32946):
            return zlib.decompress(chunk)
        if compression == 5:
            return _lzw(chunk)
        if compression == 32773:
            return _packbits(chunk)
        raise GeoTiffError(f"unsupported compression {compression}")

    if 324 in tags:                                         # tiles
        tw, th = one(322), one(323)
        offsets, counts = tags[324], tags[325]
        blocks = []
        across = (width + tw - 1) // tw
        for k, (o, c) in enumerate(zip(offsets, counts)):
            blocks.append((k % across * tw, k // across * th, tw, th,
                           data[o:o + c]))
    else:                                                   # strips
        rps = one(278, height)
        offsets, counts = tags[273], tags[279]
        blocks = [(0, k * rps, width, min(rps, height - k * rps),
                   data[o:o + c]) for k, (o, c) in
                  enumerate(zip(offsets, counts))]
    values = [[0.0] * width for _ in range(height)]
    for bx, by, bw, bh, chunk in blocks:
        raw = decode(chunk)
        rows = len(raw) // (bw * nbytes * spp)
        if predictor == 3 and fmt_code == 3:
            raw = _float_predictor(raw, bw, rows, nbytes, bo)
            nums = struct.unpack(">" + letter * (bw * rows * spp),
                                 raw[:bw * rows * spp * nbytes])
        else:
            nums = struct.unpack(bo + letter * (bw * rows * spp),
                                 raw[:bw * rows * spp * nbytes])
        for r in range(min(rows, bh)):
            y = by + r
            if y >= height:
                break
            base = r * bw * spp
            row = values[y]
            acc = 0
            for cidx in range(bw):
                x = bx + cidx
                v = nums[base + cidx * spp]
                if predictor == 2:
                    acc = v if cidx == 0 else acc + v
                    v = acc
                if x < width:
                    row[x] = v
    nodata = None
    if 42113 in tags:
        try:
            nodata = float(str(tags[42113]).strip())
        except ValueError:
            nodata = None
    if 34264 in tags:
        m = tags[34264]
        transform = (m[0], m[1], m[3], m[4], m[5], m[7])
    elif 33550 in tags and 33922 in tags:
        sx, sy = tags[33550][0], tags[33550][1]
        tp = tags[33922]
        i, j, x, y = tp[0], tp[1], tp[3], tp[4]
        transform = (sx, 0.0, x - i * sx, 0.0, -sy, y + j * sy)
    else:
        raise GeoTiffError("no georeference (not a GeoTIFF)")
    return Raster(width, height, values, transform, nodata)


def _float_predictor(raw, width, rows, nbytes, bo):
    """Undo TIFF predictor 3: bytes differenced per row, then stored
    most-significant first per sample."""
    out = bytearray(len(raw))
    stride = width * nbytes
    for r in range(rows):
        row = bytearray(raw[r * stride:(r + 1) * stride])
        for k in range(1, len(row)):
            row[k] = (row[k] + row[k - 1]) & 0xFF
        for c in range(width):
            for b in range(nbytes):
                out[r * stride + c * nbytes + b] = row[b * width + c]
    return bytes(out)
