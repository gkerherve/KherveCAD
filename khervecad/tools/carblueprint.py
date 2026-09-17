"""Measure a car's shape off a multi-view blueprint (Qt: QImage only).

A brochure gives four numbers; a drawing gives the whole shape. This
reads a blueprint sheet — the usual side / top / front / rear
arrangement — and turns two of its views into NUMBERS the Car Builder
can use:

- `panels` splits the sheet into its views by the white gutters between
  them, and picks the side view (widest, flattest) and the top view;
- `silhouette` walks each column of a view and records the first and
  last inked pixel, so a line drawing gives its own outline;
- `measure` turns those into curves in the car's own units: the roof
  line and the floor over the length (fractions of height), and the
  plan half width over the length (fractions of half the width), each
  resampled to `SAMPLES` points;
- `read` writes them as a `car_profiles` entry.

The drawing itself is never kept or shipped: only the measured curves,
which are facts about the car's shape.

Run it as::

    python -m khervecad.tools.carblueprint sheet.png --key ferrari_f40

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import argparse
import sys

#: how many points each measured curve keeps
SAMPLES = 60
#: a pixel darker than this counts as ink
INK = 150


def _gray(image):
    """The sheet as rows of 0-255 values (QImage, no numpy)."""
    from PyQt5.QtGui import QImage
    img = image.convertToFormat(QImage.Format_Grayscale8)
    w, h = img.width(), img.height()
    bits = img.bits()
    bits.setsize(img.byteCount())
    raw = bytes(bits)
    stride = img.bytesPerLine()
    return w, h, [raw[r * stride:r * stride + w] for r in range(h)]


def _runs(counts, gap):
    """Spans of non-empty entries separated by at least *gap* empties."""
    out, start, blank = [], None, 0
    for i, c in enumerate(counts):
        if c:
            if start is None:
                start = i
            blank = 0
        elif start is not None:
            blank += 1
            if blank >= gap:
                out.append((start, i - blank))
                start = None
    if start is not None:
        out.append((start, len(counts) - 1))
    return out


def panels(w, h, rows, gap_frac=0.02):
    """Every view on the sheet as (x0, y0, x1, y1)."""
    gap = max(6, int(h * gap_frac))
    row_ink = [sum(1 for v in row if v < INK) for row in rows]
    out = []
    for y0, y1 in _runs(row_ink, gap):
        cols = [0] * w
        for y in range(y0, y1 + 1):
            row = rows[y]
            for x in range(w):
                if row[x] < INK:
                    cols[x] += 1
        for x0, x1 in _runs(cols, max(6, int(w * gap_frac))):
            if (x1 - x0) > w * 0.08 and (y1 - y0) > h * 0.05:
                out.append((x0, y0, x1, y1))
    return out


def pick_views(views, w, h):
    """(side, top) of the panels found: the side view is the widest
    flat one near the top of the sheet, the top view the tallest wide
    one below it."""
    wide = [v for v in views if (v[2] - v[0]) > 2.0 * (v[3] - v[1])]
    if not wide:
        return None, None
    side = min(wide, key=lambda v: v[1])
    rest = [v for v in views if v is not side
            and (v[2] - v[0]) > 1.4 * (v[3] - v[1])]
    top = max(rest, key=lambda v: (v[2] - v[0]) * (v[3] - v[1])) \
        if rest else None
    return side, top


def largest_blob(rows, box):
    """The set of inked pixels of the biggest connected thing in *box*
    — the car. A sheet also carries its title, its dimension lines and
    their arrows, and those would otherwise BE the silhouette."""
    x0, y0, x1, y1 = box
    ink = set()
    for y in range(y0, y1 + 1):
        row = rows[y]
        for x in range(x0, x1 + 1):
            if row[x] < INK:
                ink.add((x, y))
    best, seen = set(), set()
    for start in ink:
        if start in seen:
            continue
        stack, blob = [start], set()
        seen.add(start)
        while stack:
            x, y = stack.pop()
            blob.add((x, y))
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    q = (x + dx, y + dy)
                    if q in ink and q not in seen:
                        seen.add(q)
                        stack.append(q)
        if len(blob) > len(best):
            best = blob
    return best


def _median(values, window=7):
    out = []
    for i, v in enumerate(values):
        near = [q for q in values[max(0, i - window // 2):i + window // 2 + 1]
                if q is not None]
        out.append(sorted(near)[len(near) // 2] if near else None)
    return out


def silhouette(rows, box):
    """(upper, lower) inked row per column of the car in *box*."""
    x0, _, x1, _ = box
    blob = largest_blob(rows, box)
    upper, lower = [], []
    for x in range(x0, x1 + 1):
        ys = [y for (bx, y) in blob if bx == x]
        upper.append(min(ys) if ys else None)
        lower.append(max(ys) if ys else None)
    return _median(upper), _median(lower)


def _resample(values, n=SAMPLES):
    """*values* (some None) resampled to *n* points, gaps bridged."""
    known = [(i, v) for i, v in enumerate(values) if v is not None]
    if len(known) < 2:
        return None
    out = []
    for k in range(n):
        want = known[0][0] + (known[-1][0] - known[0][0]) * k / (n - 1)
        prev = known[0]
        for point in known:
            if point[0] >= want:
                i0, v0 = prev
                i1, v1 = point
                t = 0.0 if i1 == i0 else (want - i0) / (i1 - i0)
                out.append(v0 + (v1 - v0) * t)
                break
            prev = point
        else:
            out.append(known[-1][1])
    return out


def measure(rows, side, top):
    """The car's own curves: roof (fraction of height over the length),
    floor, and plan half width (fraction of half the width)."""
    up, low = silhouette(rows, side)
    ink = [i for i, v in enumerate(up) if v is not None]
    if len(ink) < 10:
        raise SystemExit("the side view has no outline")
    lo_y = max(v for v in low if v is not None)
    hi_y = min(v for v in up if v is not None)
    span = max(1, lo_y - hi_y)
    roof = _resample([None if v is None else (lo_y - v) / span for v in up])
    floor = _resample([None if v is None else (lo_y - v) / span
                       for v in low])
    width = None
    if top is not None:
        tup, tlow = silhouette(rows, top)
        half = [None if (a is None or b is None) else (b - a) / 2.0
                for a, b in zip(tup, tlow)]
        widest = max(v for v in half if v is not None)
        width = _resample([None if v is None else v / widest for v in half])
    return roof, floor, width


def read(path, key, boxes=(None, None), flip=False):
    from PyQt5.QtGui import QImage
    from PyQt5.QtWidgets import QApplication
    if QApplication.instance() is None:
        QApplication([])                      # QImage wants an app
    image = QImage(path)
    if image.isNull():
        raise SystemExit(f"cannot read {path}")
    w, h, rows = _gray(image)
    views = panels(w, h, rows)
    side, top = pick_views(views, w, h)
    side = boxes[0] or side
    top = boxes[1] or top
    if side is None:
        raise SystemExit("no side view found on the sheet")
    roof, floor, width = measure(rows, side, top)
    if flip:
        roof, floor = roof[::-1], floor[::-1]
        width = width[::-1] if width else None
    return dict(key=key, roof=roof, floor=floor, width=width,
                views=len(views))


def _fmt(name, values):
    if values is None:
        return f"    {name}=None,"
    body = ", ".join(f"{v:.4f}" for v in values)
    return f"    {name}=[{body}],"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sheet")
    ap.add_argument("--key", required=True, help="the car's catalogue key")
    ap.add_argument("--side", help="x0,y0,x1,y1 of the side view, where "
                    "the sheet's own dimension lines defeat the split")
    ap.add_argument("--top", help="x0,y0,x1,y1 of the top view")
    ap.add_argument("--flip", action="store_true",
                    help="the drawing faces right; the builder measures "
                         "from the nose")
    args = ap.parse_args(argv)
    boxes = tuple(tuple(int(v) for v in b.split(","))
                  if b else None for b in (args.side, args.top))
    got = read(args.sheet, args.key, boxes, args.flip)
    print(f'"{args.key}": dict(', file=sys.stdout)
    print(_fmt("roof", got["roof"]))
    print(_fmt("floor", got["floor"]))
    print(_fmt("width", got["width"]))
    print("),")
    print(f"# {got['views']} views found on the sheet", file=sys.stderr)


if __name__ == "__main__":
    main()
