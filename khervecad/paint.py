"""Paint from a photo: a wrapper that colours every face of its
children from a picture projected onto an axis plane.

OpenSCAD has one colour per solid and no textures; the preview has a
colour per face. That is enough to lay a photo over a surface: the
``paint`` node projects each face's centre onto its plane (the same
placement a reference image has — lower-left corner, width, height on
Top / Front / Side), reads the picture there and gives the face that
colour. Faces outside the picture keep their own. Projection runs
straight through the part, so a front photo paints the back too,
mirrored — what one view can give.

Compiles to ``kcad_paint(...) { children }`` whose helper renders the
children unchanged (like kcad_material), and re-imports losslessly.
The picture is read by a small pure-Python PNG decoder, or by Qt for
other formats when it is present; ``Picture`` is cached per file.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import os
import struct
import zlib

#: plane -> (horizontal axis, vertical axis, normal axis)
PLANES = {"Top (XY)": (0, 1, 2), "Front (XZ)": (0, 2, 1),
          "Side (YZ)": (1, 2, 0)}
DEFAULT_PLANE = "Front (XZ)"

_CACHE = {}


class Picture:
    """RGB rows, top row first; ``at(s, t)`` samples with t up."""

    def __init__(self, width, height, rows):
        self.width, self.height, self.rows = width, height, rows

    def at(self, s, t) -> str:
        if not (0.0 <= s <= 1.0 and 0.0 <= t <= 1.0):
            return ""
        x = min(int(s * self.width), self.width - 1)
        y = min(int((1.0 - t) * self.height), self.height - 1)
        r, g, b = self.rows[y][x]
        return f"#{r:02x}{g:02x}{b:02x}"

    @property
    def aspect(self) -> float:
        return self.height / self.width if self.width else 1.0


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def read_png(path) -> Picture:
    """8-bit greyscale, RGB, RGBA, grey+alpha or palette PNG, not
    interlaced — what a photo saved by any tool is."""
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    at, idat, palette = 8, [], None
    width = height = depth = ctype = interlace = None
    while at + 8 <= len(data):
        length, kind = struct.unpack_from(">I4s", data, at)
        chunk = data[at + 8:at + 8 + length]
        if kind == b"IHDR":
            width, height, depth, ctype, _c, _f, interlace = \
                struct.unpack(">IIBBBBB", chunk)
        elif kind == b"PLTE":
            palette = [tuple(chunk[i:i + 3]) for i in range(0, len(chunk), 3)]
        elif kind == b"IDAT":
            idat.append(chunk)
        elif kind == b"IEND":
            break
        at += 12 + length
    if depth != 8 or interlace:
        raise ValueError("only 8-bit, non-interlaced PNG")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(b"".join(idat))
    stride = width * channels
    rows, prev, pos = [], bytearray(stride), 0
    for _y in range(height):
        f = raw[pos]
        line = bytearray(raw[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        for i in range(stride):
            a = line[i - channels] if i >= channels else 0
            b = prev[i]
            c = prev[i - channels] if i >= channels else 0
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                line[i] = (line[i] + _paeth(a, b, c)) & 255
        if ctype == 2 or ctype == 6:
            rows.append([tuple(line[i:i + 3])
                         for i in range(0, stride, channels)])
        elif ctype == 3:
            rows.append([palette[v] if palette and v < len(palette)
                         else (0, 0, 0) for v in line])
        else:
            rows.append([(line[i], line[i], line[i])
                         for i in range(0, stride, channels)])
        prev = line
    return Picture(width, height, rows)


def load(path) -> "Picture | None":
    """The picture at *path*, cached by name and modification time;
    None when it cannot be read."""
    try:
        key = (str(path), os.path.getmtime(path))
    except OSError:
        return None
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    picture = None
    try:
        picture = read_png(path)
    except Exception:
        try:                                     # JPEG and the rest
            from PyQt5.QtGui import QImage
            image = QImage(str(path))
            if not image.isNull():
                image = image.convertToFormat(QImage.Format_RGB888)
                rows = []
                for y in range(image.height()):
                    line = image.constScanLine(y).asstring(image.width() * 3)
                    rows.append([tuple(line[i:i + 3])
                                 for i in range(0, len(line), 3)])
                picture = Picture(image.width(), image.height(), rows)
        except Exception:
            picture = None
    if picture is not None:
        if len(_CACHE) > 8:
            _CACHE.clear()
        _CACHE[key] = picture
    return picture


def paint(items, picture, plane, x, y, width, height=0.0) -> list:
    """*items* — mesh tuples ``(triangle, colour, selected)`` — with
    each face's colour replaced by the picture's where its centre
    projects inside it; the colour's alpha and material are kept."""
    if picture is None or width <= 0:
        return items
    u, v, _n = PLANES.get(plane, PLANES[DEFAULT_PLANE])
    if height <= 0:
        height = width * picture.aspect
    out = []
    for tri, colour, selected in items:
        cu = (tri[0][u] + tri[1][u] + tri[2][u]) / 3.0
        cv = (tri[0][v] + tri[1][v] + tri[2][v]) / 3.0
        hexcol = picture.at((cu - x) / width, (cv - y) / height)
        if not hexcol:
            out.append((tri, colour, selected))
            continue
        if colour is None:
            painted = (hexcol, 1.0)
        else:
            painted = (hexcol,) + tuple(colour[1:])
        out.append((tri, painted, selected))
    return out
