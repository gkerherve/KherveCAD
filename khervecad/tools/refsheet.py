"""Cut a blueprint sheet into its views, ready for set_reference_image.

    python -m khervecad.tools.refsheet SHEET.png --length 3054 \\
        --width 1410 --height 1346 \\
        --view side=12,8,380,210:mirror --view front=400,8,560,210 \\
        --view top=12,230,380,400

A blueprint of a car, an aircraft or a ship is one picture holding three
or four orthographic views. Each ``--view NAME=x0,y0,x1,y1`` gives a
rough pixel box around one view, read off the picture (x right, y down).
The box is trimmed to the drawing inside it — every pixel that differs
from the sheet's background, sampled on the box's border — so a loose
box is fine as long as it holds no other view or caption. ``:mirror``
flips the view left-right (a side view drawn nose-left, for a model
whose nose points to +X). Each view is saved beside the sheet as
``SHEET-NAME.png``.

The report (JSON) gives, per view, the set_reference_image arguments
that put it on its plane at TRUE SIZE: the width in mm is the real
dimension the view spans (a side or top view spans the length, a front
or back view the width) and the lower-left corner centres the object on
the origin, standing on z = 0 (a top view is centred in Y too). Its
``check`` compares the other dimension the picture implies with the
real one: more than a few per cent out means a bad crop or a sheet that
is not to scale.

Driven by the model-from-blueprint skill. Qt only (QImage), no Pillow.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

#: view -> (set_reference_image plane, dimension across it, dimension up)
VIEWS = {
    "side": ("Front", "length", "height"),
    "front": ("Side", "width", "height"),
    "back": ("Side", "width", "height"),
    "top": ("Top", "length", "width"),
    "bottom": ("Top", "length", "width"),
}


def _app():
    from PyQt5.QtGui import QGuiApplication
    return QGuiApplication.instance() or QGuiApplication(sys.argv[:1])


def _rgb(img, x, y):
    p = img.pixel(x, y)
    return (p >> 16) & 255, (p >> 8) & 255, p & 255


def background(img, box):
    """The commonest colour on *box*'s border (quantised), as RGB."""
    x0, y0, x1, y1 = box
    border = [(x, y0) for x in range(x0, x1)] + \
             [(x, y1 - 1) for x in range(x0, x1)] + \
             [(x0, y) for y in range(y0, y1)] + \
             [(x1 - 1, y) for y in range(y0, y1)]
    counts = Counter(tuple(c // 16 for c in _rgb(img, x, y))
                     for x, y in border)
    q = counts.most_common(1)[0][0]
    return tuple(c * 16 + 8 for c in q)


def trim(img, box, tol=60):
    """*box* (x0, y0, x1, y1; x1/y1 exclusive) shrunk to the pixels that
    differ from the background by more than *tol* (summed over RGB)."""
    x0, y0, x1, y1 = (max(0, box[0]), max(0, box[1]),
                      min(img.width(), box[2]), min(img.height(), box[3]))
    if x1 - x0 < 2 or y1 - y0 < 2:
        raise ValueError(f"box {box} is empty on a "
                         f"{img.width()}×{img.height()} sheet")
    bg = background(img, (x0, y0, x1, y1))
    xs, ys = [], []
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b = _rgb(img, x, y)
            if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) > tol:
                xs.append(x)
                ys.append(y)
    if not xs:
        raise ValueError(f"nothing drawn inside {box}")
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def placement(name, px_w, px_h, dims):
    """set_reference_image arguments for a *px_w* × *px_h* view."""
    plane, across, up = VIEWS[name]
    width = dims.get(across)
    if not width:
        raise ValueError(f"the {name} view needs --{across}")
    tall = width * px_h / px_w
    out = {"plane": plane, "width": round(width, 1),
           "x": round(-width / 2, 1),
           "y": 0.0 if up == "height" else round(-tall / 2, 1),
           "implied_" + up: round(tall, 1)}
    real = dims.get(up)
    if real:
        err = (tall - real) / real * 100
        out["check"] = (f"{up}: picture {tall:.0f} mm vs real {real:.0f} mm "
                        f"({err:+.1f} %)")
    return out


def parse_view(text):
    """'side=12,8,380,210:mirror' -> ('side', (12, 8, 380, 210), True)."""
    name, _, rest = text.partition("=")
    name = name.strip().lower()
    if name not in VIEWS:
        raise ValueError(f"unknown view {name!r}: use {', '.join(VIEWS)}")
    coords, _, flag = rest.partition(":")
    box = tuple(int(float(v)) for v in coords.split(","))
    if len(box) != 4:
        raise ValueError(f"{text!r}: a box is x0,y0,x1,y1")
    return name, box, flag.strip().lower() == "mirror"


def cut(sheet, views, dims, out_dir=None):
    """Crop, trim and save every view of *sheet*; the report list."""
    from PyQt5.QtCore import QRect
    from PyQt5.QtGui import QImage
    _app()
    img = QImage(str(sheet))
    if img.isNull():
        raise ValueError(f"cannot read {sheet}")
    img = img.convertToFormat(QImage.Format_RGB32)
    sheet = Path(sheet)
    out_dir = Path(out_dir) if out_dir else sheet.parent
    report = []
    for name, box, mirror in views:
        x0, y0, x1, y1 = trim(img, box)
        view = img.copy(QRect(x0, y0, x1 - x0, y1 - y0))
        if mirror:
            view = view.mirrored(True, False)
        path = out_dir / f"{sheet.stem}-{name}.png"
        view.save(str(path))
        entry = {"view": name, "path": str(path.resolve()),
                 "pixels": [x1 - x0, y1 - y0], "trimmed_box": [x0, y0, x1, y1],
                 "mirrored": mirror}
        entry["set_reference_image"] = dict(
            path=entry["path"], opacity=0.45,
            **{k: v for k, v in placement(name, x1 - x0, y1 - y0,
                                          dims).items()
               if k in ("plane", "width", "x", "y")})
        entry.update({k: v for k, v in placement(name, x1 - x0, y1 - y0,
                                                  dims).items()
                      if k.startswith(("implied_", "check"))})
        report.append(entry)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("sheet")
    ap.add_argument("--view", action="append", required=True,
                    metavar="NAME=x0,y0,x1,y1[:mirror]")
    ap.add_argument("--length", type=float)
    ap.add_argument("--width", type=float)
    ap.add_argument("--height", type=float)
    ap.add_argument("--out", help="folder for the views (default: beside "
                                  "the sheet)")
    args = ap.parse_args(argv)
    dims = dict(length=args.length, width=args.width, height=args.height)
    report = cut(args.sheet, [parse_view(v) for v in args.view], dims,
                 args.out)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
