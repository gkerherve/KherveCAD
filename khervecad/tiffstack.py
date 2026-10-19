"""TIFF image stacks as solids (2026-10-19, the user: "import TIFF files
made of multiple images ... a three-dimensional block of images"). A
stack of slices — a multi-page TIFF from a microscope, a CT or MRI scan,
ImageJ — or a folder / list of single images, is a VOLUME of values;
everything brighter than a threshold is solid, and its surface is the
part. Qt-free; numpy.

- `read_stack(paths)` -> `Stack`: values (z, y, x) float32, page 0 at
  the bottom, row 0 of an image at the top (it is flipped so +y is up),
  the bit depth and the voxel size when the file says it (ImageJ's
  `spacing=` / `unit=` and the X/Y resolution tags).
  Reads classic TIFF and BigTIFF, either byte order, strips or tiles,
  uncompressed / Deflate / LZW / PackBits, horizontal predictor,
  1/8/16/32-bit integers, 32/64-bit floats, grey, RGB(A) (as luminance),
  palette and WhiteIsZero. Thumbnails (pages of another size) are
  skipped.
- `otsu(values)` the automatic threshold; `auto_step` the down-sampling
  that keeps the grid under `TARGET_VOXELS`.
- `surface(stack, threshold, ...)` -> triangles in millimetres: block
  averaged by `step`, optionally smoothed, padded by one voxel of
  background so the solid is CLOSED where the object touches the edge of
  the block, then `sdf.mesh_values_np` (marching tetrahedra, outward
  winding).
- `write_stl(tris, path)` a binary STL in one numpy write.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import re
import struct
import zlib
from pathlib import Path

import numpy as np

from . import geotiff

#: the grid size `auto_step` aims under (a few seconds to mesh)
TARGET_VOXELS = 3_000_000
#: never more than this, whatever the step
MAX_VOXELS = 16_000_000
EXTS = (".tif", ".tiff")
#: unit words -> millimetres
UNITS = {"mm": 1.0, "millimeter": 1.0, "millimetre": 1.0, "cm": 10.0,
         "m": 1000.0, "micron": 1e-3, "um": 1e-3, "µm": 1e-3,
         "\\u00b5m": 1e-3, "nm": 1e-6, "nanometer": 1e-6, "inch": 25.4,
         "in": 25.4, "pixel": None, "px": None}


class StackError(ValueError):
    """A stack that cannot be read (the message says why)."""


class Stack:
    def __init__(self, values, bits, spacing=None, unit=None, sources=()):
        self.values = values            # (nz, ny, nx) float32, y up
        self.bits = bits
        self.spacing = spacing          # (dx, dy, dz) mm or None
        self.unit = unit                # what the file called its unit
        self.sources = list(sources)

    @property
    def shape(self):
        nz, ny, nx = self.values.shape
        return nx, ny, nz

    def describe(self):
        nx, ny, nz = self.shape
        lo, hi = float(self.values.min()), float(self.values.max())
        return (f"{nx} × {ny} pixels × {nz} slices, {self.bits}-bit, "
                f"values {lo:g} – {hi:g}")


# --------------------------------------------------------------- TIFF
_TYPES = {1: ("B", 1), 2: ("c", 1), 3: ("H", 2), 4: ("I", 4),
          5: ("II", 8), 6: ("b", 1), 7: ("B", 1), 8: ("h", 2),
          9: ("i", 4), 10: ("ii", 8), 11: ("f", 4), 12: ("d", 8),
          13: ("I", 4), 16: ("Q", 8), 17: ("q", 8), 18: ("Q", 8)}


def _ifds(data):
    """Every image directory of a TIFF: [(tags, byte order)]."""
    if data[:2] == b"II":
        bo = "<"
    elif data[:2] == b"MM":
        bo = ">"
    else:
        raise StackError("not a TIFF file")
    magic = struct.unpack(bo + "H", data[2:4])[0]
    big = magic == 43
    if magic not in (42, 43):
        raise StackError("unknown TIFF variant")
    if big:
        off = struct.unpack(bo + "Q", data[8:16])[0]
        head, entry, cnt_fmt, ptr_fmt, inline = 8, 20, "Q", "Q", 8
    else:
        off = struct.unpack(bo + "I", data[4:8])[0]
        head, entry, cnt_fmt, ptr_fmt, inline = 2, 12, "H", "I", 4
    seen = set()
    out = []
    while off and off not in seen and off < len(data):
        seen.add(off)
        count = struct.unpack(bo + cnt_fmt, data[off:off + head])[0]
        tags = {}
        for k in range(count):
            p = off + head + entry * k
            if big:
                tag, typ, n = struct.unpack(bo + "HHQ", data[p:p + 12])
                field = data[p + 12:p + 20]
            else:
                tag, typ, n = struct.unpack(bo + "HHI", data[p:p + 8])
                field = data[p + 8:p + 12]
            fmt, size = _TYPES.get(typ, ("B", 1))
            total = size * n
            if total <= inline:
                raw = field[:total]
            else:
                where = struct.unpack(bo + ptr_fmt, field)[0]
                raw = data[where:where + total]
            if typ == 2:
                tags[tag] = raw.split(b"\0")[0].decode("latin-1", "replace")
            else:
                letter, per = fmt[0], len(fmt)
                try:
                    tags[tag] = list(struct.unpack(
                        bo + letter * (n * per), raw[:total]))
                except struct.error:
                    tags[tag] = []
        out.append((tags, bo))
        p = off + head + entry * count            # the next directory
        width = 8 if big else 4
        off = struct.unpack(bo + ptr_fmt, data[p:p + width])[0] \
            if p + width <= len(data) else 0
    return out


def _one(tags, tag, default=None):
    v = tags.get(tag)
    return v[0] if isinstance(v, list) and v else default


def _decode(chunk, compression):
    if compression in (1, None):
        return chunk
    if compression in (8, 32946):
        return zlib.decompress(chunk)
    if compression == 5:
        return geotiff._lzw(chunk)
    if compression == 32773:
        return geotiff._packbits(chunk)
    raise StackError(f"unsupported TIFF compression {compression} "
                     "(JPEG and others are not read)")


def _page(data, tags, bo):
    """One page as a float32 (height, width) array, row 0 at the top."""
    width, height = _one(tags, 256), _one(tags, 257)
    if not width or not height:
        raise StackError("a page has no image size")
    spp = _one(tags, 277, 1)
    bits = _one(tags, 258, 8)
    fmt_code = _one(tags, 339, 1)
    compression = _one(tags, 259, 1)
    predictor = _one(tags, 317, 1)
    planar = _one(tags, 284, 1)
    photometric = _one(tags, 262, 1)
    if bits == 1:
        dtype = None
    else:
        dtype = {(1, 8): "u1", (1, 16): "u2", (1, 32): "u4",
                 (2, 8): "i1", (2, 16): "i2", (2, 32): "i4",
                 (3, 32): "f4", (3, 64): "f8"}.get((fmt_code, bits))
        if dtype is None:
            raise StackError(f"unsupported sample format {fmt_code}/{bits}")
        dtype = np.dtype(bo + dtype)
    per_px = 1 if planar == 2 else spp     # samples stored per pixel

    if 324 in tags:                                         # tiles
        tw, th = _one(tags, 322), _one(tags, 323)
        offs, cnts = tags[324], tags[325]
        across = (width + tw - 1) // tw
        down = (height + th - 1) // th
        if planar == 2:                    # the first plane's tiles
            offs, cnts = offs[:across * down], cnts[:across * down]
        blocks = [(k % across * tw, k // across * th, tw, th, o, c)
                  for k, (o, c) in enumerate(zip(offs, cnts))]
    else:                                                   # strips
        rps = min(_one(tags, 278, height) or height, height)
        offs, cnts = tags.get(273, []), tags.get(279, [])
        if not offs:
            raise StackError("a page has no image data")
        strips = (height + rps - 1) // rps
        if planar == 2:
            offs, cnts = offs[:strips], cnts[:strips]
        blocks = [(0, k * rps, width, min(rps, height - k * rps), o, c)
                  for k, (o, c) in enumerate(zip(offs, cnts))]
    img = np.zeros((height, width, per_px), dtype=np.float32)
    for bx, by, bw, bh, o, c in blocks:
        raw = _decode(data[o:o + c], compression)
        if bits == 1:
            row_bytes = (bw * per_px + 7) // 8
            rows = len(raw) // row_bytes
            arr = np.unpackbits(np.frombuffer(raw[:rows * row_bytes],
                                              np.uint8).reshape(rows,
                                                                row_bytes),
                                axis=1)[:, :bw * per_px]
            arr = arr.reshape(rows, bw, per_px).astype(np.float32)
        else:
            if predictor == 3 and fmt_code == 3:
                rows = len(raw) // (bw * per_px * dtype.itemsize)
                raw = geotiff._float_predictor(raw, bw * per_px, rows,
                                               dtype.itemsize, bo)
                dtype_now = dtype.newbyteorder(">")
            else:
                dtype_now = dtype
            n = len(raw) // dtype_now.itemsize
            rows = n // (bw * per_px)
            arr = np.frombuffer(raw[:rows * bw * per_px * dtype_now.itemsize],
                                dtype_now).reshape(rows, bw, per_px)
            if predictor == 2:
                arr = np.cumsum(arr, axis=1, dtype=dtype_now.newbyteorder(
                    "=")).astype(dtype_now.newbyteorder("="))
            arr = arr.astype(np.float32)
        h = min(bh, rows, height - by)
        w = min(bw, width - bx)
        if h > 0 and w > 0:
            img[by:by + h, bx:bx + w] = arr[:h, :w]
    if photometric == 3 and 320 in tags:                    # palette
        cmap = np.asarray(tags[320], np.float32).reshape(3, -1)
        idx = np.clip(img[..., 0].astype(np.int64), 0, cmap.shape[1] - 1)
        rgb = cmap[:, idx]
        return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
    if per_px >= 3:
        grey = 0.299 * img[..., 0] + 0.587 * img[..., 1] \
            + 0.114 * img[..., 2]
    else:
        grey = img[..., 0]
    if photometric == 0:                                    # WhiteIsZero
        top = float((1 << bits) - 1) if fmt_code == 1 else float(
            grey.max())
        grey = top - grey
    return grey


def _rational(tags, tag):
    v = tags.get(tag)
    if isinstance(v, list) and len(v) >= 2 and v[1]:
        return v[0] / v[1]
    return None


def _spacing(tags):
    """(dx, dy, dz) in mm, the unit word, from ImageJ's description and
    the resolution tags; (None, None) when the file does not say."""
    desc = tags.get(270) if isinstance(tags.get(270), str) else ""
    unit = None
    m = re.search(r"^unit=(.+)$", desc, re.M)
    if m:
        unit = m.group(1).strip()
    per_mm = None
    if unit is not None:
        per_mm = UNITS.get(unit.lower())
    xres, yres = _rational(tags, 282), _rational(tags, 283)
    if per_mm is None and unit is None:
        res_unit = _one(tags, 296, 2)
        per_mm = {2: 25.4, 3: 10.0}.get(res_unit)
        # a plain 72 / 96 dpi is a screen picture's, not a scale
        if xres in (None, 72.0, 96.0, 300.0) and per_mm == 25.4:
            per_mm = None
    if per_mm is None or not xres:
        return None, unit
    dx = per_mm / xres
    dy = per_mm / yres if yres else dx
    dz = dx
    m = re.search(r"^spacing=([0-9.eE+-]+)$", desc, re.M)
    if m:
        try:
            dz = float(m.group(1)) * per_mm
        except ValueError:
            pass
    return (dx, dy, dz), unit


def _natural(path):
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", Path(path).name)]


def stack_files(paths):
    """The image files a selection means: a folder's TIFFs, or the
    files given, in natural order (slice2 before slice10)."""
    if isinstance(paths, (str, Path)):
        paths = [paths]
    files = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            files += [q for q in p.iterdir()
                      if q.suffix.lower() in EXTS and not
                      q.name.startswith(".")]
        else:
            files.append(p)
    return sorted(files, key=_natural) if len(files) > 1 else files


def read_stack(paths) -> Stack:
    """Every page of every file, as one volume."""
    files = stack_files(paths)
    if not files:
        raise StackError("no TIFF files there")
    slices, bits, spacing, unit, size = [], 8, None, None, None
    for f in files:
        try:
            data = Path(f).read_bytes()
        except OSError as exc:
            raise StackError(f"cannot read {f}: {exc}")
        for tags, bo in _ifds(data):
            w, h = _one(tags, 256), _one(tags, 257)
            if size is None:
                size = (w, h)
                bits = _one(tags, 258, 8)
                spacing, unit = _spacing(tags)
            elif (w, h) != size:
                continue                   # a thumbnail or another series
            slices.append(_page(data, tags, bo))
    if not slices:
        raise StackError("the TIFF holds no image")
    values = np.stack(slices)[:, ::-1, :]  # y up: image row 0 on top
    return Stack(np.ascontiguousarray(values, dtype=np.float32), bits,
                 spacing, unit, files)


# ------------------------------------------------------------- volume
def otsu(values, bins=256):
    """The threshold that best splits the values in two (Otsu)."""
    v = np.asarray(values, np.float64).ravel()
    if v.size > 2_000_000:
        v = v[:: v.size // 2_000_000 + 1]
    lo, hi = float(v.min()), float(v.max())
    if hi <= lo:
        return lo
    hist, edges = np.histogram(v, bins=bins, range=(lo, hi))
    centres = (edges[:-1] + edges[1:]) / 2.0
    w0 = np.cumsum(hist)
    w1 = w0[-1] - w0
    s0 = np.cumsum(hist * centres)
    m0 = s0 / np.maximum(w0, 1)
    m1 = (s0[-1] - s0) / np.maximum(w1, 1)
    between = (w0 * w1 * (m0 - m1) ** 2)[:-1]
    # a two-valued volume has a flat optimum all the way between its
    # two peaks: take its middle, not its first bin (next to the
    # background)
    best = np.flatnonzero(between >= between.max() * (1 - 1e-9))
    return float(edges[int(round((best[0] + best[-1]) / 2.0)) + 1])


def grid_size(shape, step):
    nx, ny, nz = shape
    return (max(nx // step, 1), max(ny // step, 1), max(nz // step, 1))


def auto_step(shape, target=TARGET_VOXELS):
    """The smallest down-sampling keeping the grid under *target*."""
    step = 1
    while True:
        gx, gy, gz = grid_size(shape, step)
        if gx * gy * gz <= target or step >= 64:
            return step
        step += 1


def _blocks(values, step):
    """*values* averaged over step³ blocks (edges trimmed)."""
    if step <= 1:
        return values
    nz, ny, nx = values.shape
    sz = max(nz // step, 1)
    zs = min(step, nz)
    v = values[:sz * zs, :ny // step * step, :nx // step * step]
    return v.reshape(sz, zs, ny // step, step, nx // step,
                     step).mean(axis=(1, 3, 5))


def _smooth(values):
    """One 3 x 3 x 3 box blur (noise specks fall below the threshold)."""
    p = np.pad(values, 1, mode="edge")
    out = np.zeros_like(values)
    nz, ny, nx = values.shape
    for dz in range(3):
        for dy in range(3):
            for dx in range(3):
                out += p[dz:dz + nz, dy:dy + ny, dx:dx + nx]
    return out / 27.0


def surface(stack, threshold, spacing=(1.0, 1.0, 1.0), step=1,
            invert=False, smooth=True, z_step=None):
    """The solid's triangles (mm): voxels above *threshold* (below it
    with *invert*), each voxel `spacing` mm, the grid down-sampled by
    *step*. Centred on x / y, standing on z = 0."""
    from . import sdf
    step = max(int(step), 1)
    vals = _blocks(stack.values.astype(np.float32), step)
    nz, ny, nx = vals.shape
    if nx * ny * nz > MAX_VOXELS:
        raise StackError(f"{nx} × {ny} × {nz} voxels is too many — raise "
                         "the step (down-sampling)")
    if smooth and min(nx, ny, nz) >= 3:
        vals = _smooth(vals)
    field = (vals - threshold) if invert else (threshold - vals)
    field = np.where(field == 0.0, 1e-6, field)
    # one voxel of background all round: the surface closes at the
    # edge. Each pad voxel mirrors its neighbour (|value|), so the
    # surface crosses half a voxel out — the block's true edge; a fixed
    # pad value put it nearly a whole voxel out on every side
    inner = field
    field = np.abs(np.pad(inner, 1, mode="edge"))
    field[1:-1, 1:-1, 1:-1] = inner
    dx, dy, dz = (float(s) * step for s in spacing)
    xs = (np.arange(nx + 2) - 1 - (nx - 1) / 2.0) * dx
    ys = (np.arange(ny + 2) - 1 - (ny - 1) / 2.0) * dy
    zs = (np.arange(nz + 2) - 1) * dz
    if not (field < 0).any():
        return []
    tris = sdf.mesh_values_np(field.ravel(), xs, ys, zs)
    if not tris:
        return []
    arr = np.asarray(tris, dtype=np.float64)
    arr[..., 2] -= arr[..., 2].min()             # stand it on z = 0
    return arr


def write_stl(tris, path, name="KherveCAD image stack"):
    """A binary STL of *tris*, in one numpy write."""
    arr = np.asarray(tris, dtype=np.float32).reshape(-1, 3, 3)
    n = np.cross(arr[:, 1] - arr[:, 0], arr[:, 2] - arr[:, 0])
    length = np.linalg.norm(n, axis=1, keepdims=True)
    n = n / np.where(length == 0, 1.0, length)
    rec = np.zeros(len(arr), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)),
                                    ("a", "<u2")])
    rec["n"], rec["v"] = n, arr
    with open(path, "wb") as fh:
        fh.write(name.encode()[:80].ljust(80, b"\0"))
        fh.write(struct.pack("<I", len(arr)))
        fh.write(rec.tobytes())
