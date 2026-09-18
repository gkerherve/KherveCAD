"""Read a COLOURED four-view car drawing into numbers (numpy, scipy,
scikit-image, Pillow — this tool only; the app never imports them).

A coloured sheet (body in one paint colour, glass light, trim and tyres
dark, tail lamps red — the-blueprints.com style) says far more than a
line drawing: every view is a clean solid silhouette, and the glass,
the lamps and the black trim are regions already separated by colour.
This turns one into a `car_sheets` entry:

- ``stations``: along the length, ``[y, floor, roof, half width]`` in
  mm — the side view's body (tyres taken out, so the floor IS the wheel
  arch over each wheel) and the top view's plan (mirrors taken out);
- ``front`` / ``rear``: the end views' half width at each height, as a
  fraction of half the car's width — the real cross-section shapes;
- ``wheels``: each wheel's centre along the car and its radius, fitted
  to the tyre + rim blob of the side view;
- ``decals``: for every view, the glass, lamp, dark-trim and tail-lamp
  regions as polygons in the car's own millimetres — where the windows
  and lamps ARE, not the picture of them;
- ``mirror``: where the door mirror stands (side and top views).

The drawing itself is never stored: only these measurements. Run::

    python -m khervecad.tools.carsheet SHEET --key porsche_930_turbo \\
        [--side x0,y0,x1,y1 --front ... --top ... --rear ...]

Views are found by themselves (the paint colour's four blobs) unless
boxes are given; the side and top views face LEFT (nose at x0).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import argparse
import json

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage import measure

#: stations kept along the car, and levels across an end view
STATIONS = 120
LEVELS = 60
#: a region smaller than this many pixels is noise (a watermark letter)
MIN_REGION = 6
#: how far below the lowest paint a sill or valance may run, in pixels
DARK_SKIRT = 2
#: polygon simplification, in pixels
SIMPLIFY = 0.8


def load(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(np.int32)


def paint_mask(rgb):
    """The body colour: the dominant saturated colour of the sheet."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    hi = np.maximum(np.maximum(r, g), b)
    lo = np.minimum(np.minimum(r, g), b)
    sat = (hi - lo) > 25
    if not sat.any():
        raise SystemExit("no paint colour on this sheet")
    colours = (rgb[sat] // 16).reshape(-1, 3)
    keys, counts = np.unique(colours, axis=0, return_counts=True)
    paint = keys[np.argmax(counts)]
    close = np.all(np.abs(rgb // 16 - paint) <= 1, axis=-1)
    return close


def find_views(rgb):
    """(side, front, top, rear) boxes from the paint colour's blobs."""
    paint = ndi.binary_dilation(paint_mask(rgb), iterations=4)
    lab, n = ndi.label(paint)
    # a view is its paint AND whatever ink is joined to it — tyres, a
    # black bumper, the underside — or an end view loses its bottom
    ink = np.min(rgb, axis=-1) < 205
    ink_lab, _ = ndi.label(ndi.binary_dilation(ink, iterations=1))
    boxes = []
    for i, sl in enumerate(ndi.find_objects(lab), start=1):
        ys, xs = sl
        w, h = xs.stop - xs.start, ys.stop - ys.start
        if w * h <= 0.01 * rgb.shape[0] * rgb.shape[1]:
            continue
        joined = np.unique(ink_lab[lab == i])
        joined = joined[joined > 0]
        region = np.isin(ink_lab, joined) | (lab == i)
        rys, rxs = np.nonzero(region)
        boxes.append((max(rxs.min(), xs.start - 40),
                      max(rys.min(), ys.start - 40),
                      min(rxs.max(), xs.stop + 40),
                      min(rys.max(), ys.stop + 40)))
    if len(boxes) < 4:
        raise SystemExit(f"found {len(boxes)} views, need 4: give boxes")
    boxes.sort(key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)
    boxes = boxes[:4]
    wide = sorted(boxes, key=lambda b: b[2] - b[0], reverse=True)
    side_top, ends = wide[:2], wide[2:]
    side = min(side_top, key=lambda b: b[3] - b[1])
    top = max(side_top, key=lambda b: b[3] - b[1])
    front = min(ends, key=lambda b: b[1])
    rear = max(ends, key=lambda b: b[1])
    return side, front, top, rear


def classes(rgb):
    """Per-pixel masks of one view: the car, and what it is made of."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    lo = np.minimum(np.minimum(r, g), b)
    hi = np.maximum(np.maximum(r, g), b)
    paint = paint_mask(rgb)
    ink = lo < 205
    solid = ndi.binary_fill_holes(ndi.binary_closing(ink, iterations=1))
    solid = _biggest(solid)
    red = (r > g + 50) & (r > b + 50) & solid
    dark = (hi < 120) & solid & ~red
    grey = (hi - lo < 18) & (lo >= 120) & (lo <= 205) & solid
    glass = (lo > 205) & ~paint & solid
    return dict(solid=solid, paint=paint & solid, red=red, dark=dark,
                grey=grey, glass=glass)


def _biggest(mask):
    lab, n = ndi.label(mask)
    if n <= 1:
        return mask
    sizes = ndi.sum(mask, lab, range(1, n + 1))
    return lab == (1 + int(np.argmax(sizes)))


def without_mirrors(solid, width=3):
    """The silhouette with thin protrusions (mirror stalks, aerials)
    opened away and what they held cut off."""
    opened = ndi.binary_opening(solid, structure=np.ones((width, width)))
    return _biggest(opened)


def crop(rgb, box, pad=2):
    x0, y0, x1, y1 = box
    return rgb[max(0, y0 - pad):y1 + pad + 1, max(0, x0 - pad):x1 + pad + 1]


def extent(mask):
    ys, xs = np.nonzero(mask)
    return xs.min(), xs.max(), ys.min(), ys.max()


class View:
    """One view's masks and its pixel <-> millimetre mapping."""

    def __init__(self, rgb, across_mm, up_mm, flip=False):
        self.m = classes(rgb)
        self.body = without_mirrors(self.m["solid"])
        x0, x1, y0, y1 = extent(self.body)
        self.x0, self.x1, self.y0, self.y1 = x0, x1, y0, y1
        self.sx = across_mm / max(1, x1 - x0)
        self.sy = up_mm / max(1, y1 - y0)
        self.across, self.up, self.flip = across_mm, up_mm, flip

    def u(self, px):
        """Pixel column -> mm across the view (from its left edge)."""
        return (px - self.x0) * self.sx

    def v(self, py):
        """Pixel row -> mm up the view (from its bottom edge)."""
        return (self.y1 - py) * self.sy


def wheel_blobs(view):
    """(centre column, centre row, radius px) of each wheel in a side
    view. The RIM is the thing to find — a round grey/light blob low in
    the view, which no body line runs into; the tyre is then the dark
    ring round it, whose reach along the rim's own row is the wheel's
    diameter, and whose bottom stands on the ground."""
    m = view.m
    low = np.arange(m["solid"].shape[0])[:, None] > (view.y0 + view.y1) / 2
    rim = (m["grey"] | (m["glass"] & ~m["paint"])) & low
    rim = ndi.binary_fill_holes(ndi.binary_closing(rim, iterations=2))
    lab, n = ndi.label(rim)
    found = []
    for i, sl in enumerate(ndi.find_objects(lab), start=1):
        ys, xs = sl
        w, h = xs.stop - xs.start, ys.stop - ys.start
        if h < 0.12 * (view.y1 - view.y0) or not 0.6 < w / h < 1.6:
            continue
        found.append(((xs.start + xs.stop - 1) / 2.0,
                      (ys.start + ys.stop - 1) / 2.0, w * h))
    found.sort(key=lambda f: -f[2])
    out = []
    tyre = m["dark"] | m["grey"] | (m["glass"] & ~m["paint"])
    for cx, cy, _ in found[:2]:
        # the wheel's radius: from its centre down to the ground
        r = view.y1 - cy
        out.append((cx, cy, r))
    out.sort()
    del tyre
    return out


def side_stations(view, wheels, length_mm):
    """[y, floor, roof] per station along the car, mm. The tyres are cut
    out of the side view first, so over each wheel the floor is the
    ARCH; mirrors are already gone."""
    body = view.body.copy()
    rows, cols = np.indices(body.shape)
    for cx, cy, r in wheels:
        body &= (cols - cx) ** 2 + (rows - cy) ** 2 > (r + 1.5) ** 2
    paint = view.m["paint"]
    out = []
    for k in range(STATIONS):
        px = view.x0 + (view.x1 - view.x0) * k / (STATIONS - 1)
        c = int(round(px))
        ys = np.flatnonzero(body[:, c])
        painted = np.flatnonzero(paint[:, c] & body[:, c])
        y_mm = -length_mm / 2 + view.u(px)
        if ys.size == 0:
            out.append([y_mm, None, None])
            continue
        # the underside is drawn dark right down to the ground line, so
        # the body's floor is the lowest PAINT, plus a sill's worth
        low = min(ys.max(), painted.max() + DARK_SKIRT) if painted.size \
            else ys.max()
        out.append([y_mm, view.v(low), view.v(ys.min())])
    return out


def plan_widths(view, length_mm):
    """Half width per station, mm (the top view faces left too)."""
    out = []
    for k in range(STATIONS):
        px = view.x0 + (view.x1 - view.x0) * k / (STATIONS - 1)
        ys = np.flatnonzero(view.body[:, int(round(px))])
        out.append(None if ys.size == 0 else
                   (ys.max() - ys.min()) * view.sy / 2.0)
    return out


def end_section(view, width_mm):
    """Half width at each of LEVELS heights, as a fraction of half the
    car's width — the cross-section an end view shows."""
    out = []
    for k in range(LEVELS):
        py = view.y1 - (view.y1 - view.y0) * k / (LEVELS - 1)
        xs = np.flatnonzero(view.body[int(round(py))])
        half = (xs.max() - xs.min()) * view.sx / 2.0 if xs.size else 0.0
        out.append(round(half / (width_mm / 2.0), 4))
    return out


def polygons(mask, to_mm, cls):
    """The mask's regions as simplified polygons in mm."""
    out = []
    lab, n = ndi.label(mask)
    for i in range(1, n + 1):
        region = lab == i
        if region.sum() < MIN_REGION:
            continue
        padded = np.pad(region, 1)
        for contour in measure.find_contours(padded.astype(float), 0.5):
            if len(contour) < 4:
                continue
            simple = measure.approximate_polygon(contour, SIMPLIFY)
            pts = [to_mm(c - 1, r - 1) for r, c in simple]
            out.append([cls, [[round(a, 1), round(b, 1)] for a, b in pts]])
    return out


def _solid_regions(mask, size):
    """*mask* without its thin parts: the drawing's outlines and panel
    lines are dark too, and a watermark's letters are light, but only
    a real region survives an opening."""
    return ndi.binary_opening(mask, structure=np.ones((size, size)))


def decals(view, to_mm, lamp_below=None, wheels=()):
    """Glass, lamp, dark-trim and tail-lamp regions of one view. The
    *wheels* (side view) are cut out first: a tyre is dark, and joined
    to the sills and bumpers it made one region from nose to tail that
    painted the whole flank."""
    m = view.m
    body = view.body.copy()
    if wheels:
        rows, cols = np.indices(body.shape)
        for cx, cy, r in wheels:
            body &= (cols - cx) ** 2 + (rows - cy) ** 2 > (r * 1.12) ** 2
    glass = _solid_regions(m["glass"] & body, 2)
    out = []
    if lamp_below is not None:
        rows = np.arange(glass.shape[0])[:, None]
        low = rows > lamp_below
        lab, n = ndi.label(glass)
        lamp = np.zeros_like(glass)
        for i in range(1, n + 1):
            region = lab == i
            if np.flatnonzero(region.any(axis=1)).min() > lamp_below:
                lamp |= region
        out += polygons(lamp, to_mm, "lamp")
        glass &= ~lamp
        del low
    out += polygons(glass, to_mm, "glass")
    out += polygons(_solid_regions(m["dark"] & body, 3), to_mm, "dark")
    out += polygons(_solid_regions(m["red"] & body, 2), to_mm, "tail")
    return out


def mirror(view, to_mm, band=(0.25, 0.55), upper=False):
    """Centre (mm) of the door mirror: the biggest thing the opening
    removed within *band* of the car's length from the nose — a
    spoiler's thin tip is removed too, and is not a mirror."""
    extra = view.m["solid"] & ~view.body
    lab, n = ndi.label(extra)
    best, best_size = None, 0
    span = max(1, view.x1 - view.x0)
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lab == i)
        f = (xs.mean() - view.x0) / span
        if upper and ys.mean() > (view.y0 + view.y1) / 2:
            continue                    # a side view's mirror is up high
        if band[0] <= f <= band[1] and xs.size > best_size:
            best, best_size = (xs.mean(), ys.mean()), xs.size
    if best is None:
        return None
    return [round(v, 1) for v in to_mm(*best)]


def read(path, L, W, H, boxes=None):
    rgb = load(path)
    side_b, front_b, top_b, rear_b = boxes or find_views(rgb)
    side = View(crop(rgb, side_b), L, H)
    top = View(crop(rgb, top_b), L, W)
    front = View(crop(rgb, front_b), W, H)
    rear = View(crop(rgb, rear_b), W, H)

    wheels_px = wheel_blobs(side)
    stations = side_stations(side, wheels_px, L)
    halves = plan_widths(top, L)
    rows = []
    for (y, lo, hi), half in zip(stations, halves):
        if lo is None or half is None:
            continue
        rows.append([round(y, 1), round(lo, 1), round(hi, 1),
                     round(min(half, W / 2), 1)])

    def side_mm(c, r):          # (along y, up z)
        return (-L / 2 + side.u(c), side.v(r))

    def top_mm(c, r):           # (along y, across x from the centre)
        return (-L / 2 + top.u(c), (top.y0 + top.y1) / 2 * top.sy
                - r * top.sy)

    def front_mm(c, r):         # (across x from the centre, up z)
        return (front.u(c) - W / 2, front.v(r))

    def rear_mm(c, r):
        return (rear.u(c) - W / 2, rear.v(r))

    # a front view's glass below half height is a lamp, not a window
    lamp_row = front.y0 + 0.45 * (front.y1 - front.y0)
    return dict(
        stations=rows,
        front=end_section(front, W),
        rear=end_section(rear, W),
        wheels=[[round(-L / 2 + side.u(cx), 1), round(r * side.sy, 1)]
                for cx, cy, r in wheels_px],
        decals=dict(side=decals(side, side_mm, wheels=wheels_px),
                    top=decals(top, top_mm),
                    front=decals(front, front_mm, lamp_below=lamp_row),
                    rear=decals(rear, rear_mm)),
        mirror=dict(side=mirror(side, side_mm, upper=True),
                    top=mirror(top, top_mm)),
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sheet")
    ap.add_argument("--key", required=True)
    ap.add_argument("--out", help="write the entry as JSON here")
    for name in ("side", "front", "top", "rear"):
        ap.add_argument(f"--{name}", help=f"x0,y0,x1,y1 of the {name} view")
    args = ap.parse_args(argv)
    from khervecad import car_models
    car = car_models.CARS[args.key]
    boxes = None
    if args.side:
        boxes = [tuple(int(v) for v in getattr(args, n).split(","))
                 for n in ("side", "front", "top", "rear")]
    got = read(args.sheet, car["L"], car["W"], car["H"], boxes)
    text = json.dumps(got, separators=(",", ":"))
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text)
    print(f"{args.key}: {len(got['stations'])} stations, "
          f"{len(got['wheels'])} wheels, "
          + ", ".join(f"{v}: {len(d)} regions"
                      for v, d in got["decals"].items()))


if __name__ == "__main__":
    main()
