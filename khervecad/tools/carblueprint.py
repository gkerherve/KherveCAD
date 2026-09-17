"""Measure a car's shape off a multi-view blueprint (numpy + Pillow).

A brochure gives four numbers; a drawing gives the whole shape. This
reads a blueprint sheet — the usual side / top / front / rear
arrangement — and turns it into NUMBERS the Car Builder can use:

- `ink` thresholds the sheet by Otsu's method, so a clean line drawing
  and a grey scan both read correctly with no hand-set level;
- `components` labels the connected ink (union-find over the grid). The
  biggest piece in a view is the car, which is how a title, a dimension
  line or an arrowhead is kept out of the outline;
- `silhouette` takes the first and last inked row of every column;
- `section` does the same by height on a front or rear view — the car's
  cross-section envelope;
- `windows` floods the white INSIDE the side view's outline and keeps
  the cells that are glass: the real windscreen rake, roof line and
  backlight, which a shape preset can only guess at;
- `measure` scales all of it into the car's own units and `read` writes
  a `car_profiles` entry.

The drawing itself is never kept or shipped: only the measured curves,
which are facts about the car's shape.

Run it as::

    python -m khervecad.tools.carblueprint sheet.png --key ferrari_f40 \\
        --side x0,y0,x1,y1 --top ... --face ... --back ...

numpy and Pillow are needed by this tool only, never by the app.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import argparse

import numpy as np

#: how many points each measured curve keeps
SAMPLES = 60
#: a piece smaller than this much of the biggest is not the car
MIN_PIECE = 0.02
#: a window is at least this much of the side view's area
MIN_WINDOW = 0.004
#: and at most this much: a bigger white cell is the car's whole
#: interior, where the drawing's inner lines do not close the cabin off
MAX_WINDOW = 0.10
#: a pane starts within this much of the car's height below the crown
GLASS_TOP_BAND = 0.22
#: and is between these fractions of the height deep
GLASS_MIN_DEEP, GLASS_MAX_DEEP = 0.08, 0.45


def load(path):
    """The sheet as a 2D float array, 0 (black) to 255 (white)."""
    from PIL import Image
    with Image.open(path) as im:
        return np.asarray(im.convert("L"), dtype=np.float32)


def otsu(gray):
    """The threshold that best splits ink from paper."""
    hist, _ = np.histogram(gray, bins=256, range=(0, 256))
    total = hist.sum()
    if not total:
        return 128.0
    levels = np.arange(256)
    weight_b = np.cumsum(hist)
    weight_f = total - weight_b
    good = (weight_b > 0) & (weight_f > 0)
    sum_all = float((hist * levels).sum())
    sum_b = np.cumsum(hist * levels)
    mean_b = np.divide(sum_b, weight_b, out=np.zeros(256), where=good)
    mean_f = np.divide(sum_all - sum_b, weight_f, out=np.zeros(256),
                       where=good)
    between = weight_b * weight_f * (mean_b - mean_f) ** 2
    between[~good] = 0
    return float(levels[int(np.argmax(between))])


def ink(gray, level=None):
    """A boolean mask of the inked pixels."""
    return gray <= (otsu(gray) if level is None else level)


def components(mask, gap=2):
    """(labels, sizes) of the mask's connected pieces, 0 = background.
    *gap* dilates first, so a line broken by a pixel or two still reads
    as one piece."""
    grown = mask.copy()
    for dy in range(-gap, gap + 1):
        for dx in range(-gap, gap + 1):
            if dy or dx:
                grown |= np.roll(np.roll(mask, dy, 0), dx, 1)
    h, w = grown.shape
    labels = np.zeros((h, w), dtype=np.int32)
    parent = [0]

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    for y in range(h):
        row = grown[y]
        if not row.any():
            continue
        out = labels[y]
        above = labels[y - 1] if y else None
        for x in np.flatnonzero(row):
            near = []
            if x and out[x - 1]:
                near.append(int(out[x - 1]))
            if above is not None:
                for xx in (x - 1, x, x + 1):
                    if 0 <= xx < w and above[xx]:
                        near.append(int(above[xx]))
            if near:
                out[x] = min(near)
                for n in near:
                    union(int(out[x]), n)
            else:
                parent.append(len(parent))
                out[x] = len(parent) - 1
    flat = np.array([find(i) for i in range(len(parent))], dtype=np.int32)
    labels = flat[labels]
    labels[~mask] = 0
    return labels, np.bincount(labels.ravel())


def car_mask(gray, box, whole=False):
    """The inked pixels of the CAR inside *box*: its biggest connected
    piece plus anything nearly as big (an outline drawn as a few long
    runs), never the sheet's furniture. *whole* keeps every inked pixel,
    for a view whose outline is too broken to trust — the box must then
    be tight."""
    x0, y0, x1, y1 = box
    mask = ink(gray[y0:y1 + 1, x0:x1 + 1])
    if whole or not mask.any():
        return mask
    labels, sizes = components(mask)
    if sizes.size < 2:
        return mask
    sizes[0] = 0
    keep = np.flatnonzero(sizes >= max(MIN_PIECE * sizes.max(), 12))
    return np.isin(labels, keep)


def _median(values, window=5):
    """A running median, NaN meaning 'nothing in this column'."""
    arr = np.asarray(values, dtype=np.float64)
    pad = window // 2
    wide = np.pad(arr, pad, constant_values=np.nan)
    stack = np.stack([wide[i:i + arr.size] for i in range(window)])
    with np.errstate(all="ignore"):
        return np.nanmedian(stack, axis=0)


def silhouette(gray, box, whole=False):
    """(upper, lower) inked row per column of the car in *box*."""
    mask = car_mask(gray, box, whole)
    any_ink = mask.any(axis=0)
    upper = np.where(any_ink, np.argmax(mask, axis=0), np.nan)
    lower = np.where(any_ink,
                     mask.shape[0] - 1 - np.argmax(mask[::-1], axis=0),
                     np.nan)
    return _median(upper), _median(lower)


def section(gray, box, levels=SAMPLES, whole=False):
    """A FRONT or REAR view's half width at *levels* heights, ground to
    roof, as fractions of the widest point."""
    mask = car_mask(gray, box, whole)
    if not mask.any():
        return None
    ys = np.flatnonzero(mask.any(axis=1))
    lo, hi = int(ys[-1]), int(ys[0])
    span = max(1, lo - hi)
    out = []
    for k in range(levels):
        y = int(round(lo - (k / (levels - 1)) * span))
        xs = np.flatnonzero(mask[max(0, y - 1):y + 2].any(axis=0))
        out.append((xs[-1] - xs[0]) / 2.0 if xs.size else 0.0)
    arr = np.nan_to_num(_median(np.array(out, dtype=np.float64), 5))
    widest = arr.max() or 1.0
    return [float(v / widest) for v in arr / widest * widest]


def windows(gray, box):
    """The glass of a side view as (top, bottom) rows per column.

    The panes are white cells INSIDE the car's outline, high up and
    large. Flooding the paper in from the edges leaves the inside cells;
    the ones whose middle is above the beltline are the glass — which
    gives the windscreen's rake, the roof and the backlight exactly as
    the drawing has them."""
    mask = car_mask(gray, box)
    if not mask.any():
        return None, None
    h, w = mask.shape
    labels, sizes = components(~mask, gap=0)
    outside = set(labels[0].tolist()) | set(labels[-1].tolist()) \
        | set(labels[:, 0].tolist()) | set(labels[:, -1].tolist())
    ys = np.flatnonzero(mask.any(axis=1))
    top, bottom = int(ys[0]), int(ys[-1])
    height = max(1, bottom - top)
    any_ink = mask.any(axis=0)
    roof = np.where(any_ink, np.argmax(mask, axis=0), np.nan)
    glass = np.zeros((h, w), dtype=bool)
    for lab in range(1, sizes.size):
        if lab in outside or sizes[lab] < MIN_WINDOW * mask.size:
            continue
        cell = labels == lab
        cols = np.flatnonzero(cell.any(axis=0))
        rows_in = np.flatnonzero(cell.any(axis=1))
        cell_top = np.argmax(cell[:, cols], axis=0)
        near_roof = np.mean(np.abs(cell_top - roof[cols])
                            < 0.10 * height)
        deep = (rows_in[-1] - rows_in[0]) / height
        high = (rows_in[0] - top) / height
        # a pane hangs from the ROOF (its top follows the car's own
        # upper line, and it starts near the crown) and is a window's
        # depth. The white under a bonnet starts a third of the way
        # down; the interior of a car whose inner lines never close
        # runs the whole depth of the body.
        if (near_roof > 0.5 and high < GLASS_TOP_BAND
                and GLASS_MIN_DEEP < deep < GLASS_MAX_DEEP
                and sizes[lab] < MAX_WINDOW * mask.size):
            glass |= cell
    if not glass.any():
        return None, None
    any_glass = glass.any(axis=0)
    hi = np.where(any_glass, np.argmax(glass, axis=0), np.nan)
    lo = np.where(any_glass, h - 1 - np.argmax(glass[::-1], axis=0), np.nan)
    return _median(hi), _median(lo)


def spoiler_gap(gray, box):
    """The DECK line under a rear wing, per column, or None.

    A whale tail or a rear wing stands over the engine lid with
    daylight under it, and that gap is a white cell inside the car's
    outline: wide, thin, in the back half, with the roof line just
    above it. Its underside IS the body's own top there — without it a
    traced roof line makes the whole tail a brick."""
    mask = car_mask(gray, box)
    if not mask.any():
        return None
    h, w = mask.shape
    labels, sizes = components(~mask, gap=0)
    outside = set(labels[0].tolist()) | set(labels[-1].tolist()) \
        | set(labels[:, 0].tolist()) | set(labels[:, -1].tolist())
    ys = np.flatnonzero(mask.any(axis=1))
    top, bottom = int(ys[0]), int(ys[-1])
    height = max(1, bottom - top)
    cols_in = np.flatnonzero(mask.any(axis=0))
    back = cols_in[0] + 0.55 * (cols_in[-1] - cols_in[0])
    deck = np.full(w, np.nan)
    for lab in range(1, sizes.size):
        if lab in outside or sizes[lab] < MIN_WINDOW * mask.size:
            continue
        cell = labels == lab
        cols = np.flatnonzero(cell.any(axis=0))
        rows_in = np.flatnonzero(cell.any(axis=1))
        wide = (cols[-1] - cols[0]) > 2.5 * (rows_in[-1] - rows_in[0])
        if (wide and cols.mean() > back
                and rows_in[0] < top + GLASS_TOP_BAND * height):
            floor = h - 1 - np.argmax(cell[::-1], axis=0)
            deck[cols] = np.fmin(deck[cols], floor[cols])
    return deck if not np.isnan(deck).all() else None


def _resample(values, n=SAMPLES):
    """*values* (NaN where blank) resampled to *n* points."""
    arr = np.asarray(values, dtype=np.float64)
    good = np.flatnonzero(~np.isnan(arr))
    if good.size < 2:
        return None
    want = np.linspace(good[0], good[-1], n)
    return [float(v) for v in np.interp(want, good, arr[good])]


def _on_span(values, first, last, n=SAMPLES):
    """*values* sampled over the CAR's own columns, 0 where there is
    nothing there — a window band must line up with the roof line, not
    be stretched over the whole car."""
    arr = np.asarray(values, dtype=np.float64)
    want = np.linspace(first, last, n)
    out = []
    for x in want:
        i = int(round(x))
        out.append(0.0 if i < 0 or i >= arr.size or np.isnan(arr[i])
                   else float(arr[i]))
    return out


def measure(gray, side, top, faces=(None, None)):
    """Every curve of the car, in its own units."""
    up, low = silhouette(gray, side)
    if np.isnan(up).all():
        raise SystemExit("the side view has no outline")
    lo_y, hi_y = np.nanmax(low), np.nanmin(up)
    span = max(1.0, lo_y - hi_y)
    got = dict(roof=_resample((lo_y - up) / span),
               floor=_resample((lo_y - low) / span))
    on = np.flatnonzero(~np.isnan(up))
    first, last = int(on[0]), int(on[-1])
    g_hi, g_lo = windows(gray, side)
    got["glass_top"] = (_on_span((lo_y - g_hi) / span, first, last)
                        if g_hi is not None else None)
    got["glass_bottom"] = (_on_span((lo_y - g_lo) / span, first, last)
                           if g_lo is not None else None)
    if top is not None:
        tup, tlow = silhouette(gray, top, whole=True)
        half = (tlow - tup) / 2.0
        widest = np.nanmax(half) or 1.0
        got["width"] = _resample(half / widest)
    else:
        got["width"] = None
    gap = spoiler_gap(gray, side)
    got["deck"] = (_on_span((lo_y - gap) / span, first, last)
                   if gap is not None else None)
    got["nose"] = section(gray, faces[0]) if faces[0] else None
    got["tail"] = section(gray, faces[1]) if faces[1] else None
    return got


def read(path, key, boxes=(None, None), flip=False, faces=(None, None)):
    side, top = boxes
    if side is None:
        raise SystemExit("--side is required: the side view's box")
    got = measure(load(path), side, top, faces)
    if flip:
        for name in ("roof", "floor", "width", "glass_top",
                     "glass_bottom", "deck"):
            if got[name]:
                got[name] = got[name][::-1]
    got["key"] = key
    return got


#: every curve an entry carries, in the order they are written
CURVES = ("roof", "floor", "width", "nose", "tail", "glass_top",
          "glass_bottom", "deck")


def _fmt(name, values):
    if not values:
        return f"    {name}=None,"
    return f"    {name}=[" + ", ".join(f"{v:.4f}" for v in values) + "],"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sheet")
    ap.add_argument("--key", required=True, help="the car's catalogue key")
    ap.add_argument("--side", required=True,
                    help="x0,y0,x1,y1 of the side view")
    ap.add_argument("--top", help="x0,y0,x1,y1 of the top view")
    ap.add_argument("--face", help="x0,y0,x1,y1 of the FRONT view")
    ap.add_argument("--back", help="x0,y0,x1,y1 of the REAR view")
    ap.add_argument("--flip", action="store_true",
                    help="the drawing faces right; the builder measures "
                         "from the nose")
    args = ap.parse_args(argv)

    def box(text):
        return tuple(int(v) for v in text.split(",")) if text else None
    got = read(args.sheet, args.key, (box(args.side), box(args.top)),
               args.flip, (box(args.face), box(args.back)))
    print(f'"{args.key}": dict(')
    for name in CURVES:
        print(_fmt(name, got[name]))
    print("),")


if __name__ == "__main__":
    main()
