"""Render ``packaging/khervecad.png`` into a macOS ``.icns``.

The macOS counterpart of ``make_icon.py``: same source mark, different
container. Written to an explicit path (the spec puts it under
``build/``) rather than committed, so no binary that only one platform
ever reads sits in the tree:

    python packaging/make_icns.py build/KherveCAD.icns

Uses ``sips`` and ``iconutil`` — both part of macOS — rather than Pillow,
so a Mac build needs nothing installed beyond the app's own
requirements. Falls back to Pillow's ICNS writer off macOS so the script
is at least testable there.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SRC = _HERE / "khervecad.png"

#: (pixel size, name) for every slot in an iconset. macOS picks the @2x
#: variant on a Retina display, so each logical size is listed twice.
_SLOTS = [
    (16, "icon_16x16.png"), (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"), (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"), (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"), (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"), (1024, "icon_512x512@2x.png"),
]


def build_icns(out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform != "darwin":
        _build_with_pillow(out)
        return

    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "KherveCAD.iconset"
        iconset.mkdir()
        for size, name in _SLOTS:
            subprocess.run(
                ["sips", "-z", str(size), str(size), str(_SRC),
                 "--out", str(iconset / name)],
                check=True, stdout=subprocess.DEVNULL,
            )
        subprocess.run(["iconutil", "-c", "icns", str(iconset),
                        "-o", str(out)], check=True)


def _build_with_pillow(out: Path) -> None:
    """Off-macOS fallback — no sips/iconutil, so use Pillow."""
    from PIL import Image

    image = Image.open(_SRC).convert("RGBA")
    image.save(out, format="ICNS",
               sizes=[(s, s) for s in (16, 32, 64, 128, 256, 512, 1024)])


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else _HERE.parent / "build" / "KherveCAD.icns"
    build_icns(out)
    print(f"{out}  <-  {_SRC.name}")


if __name__ == "__main__":
    main()
