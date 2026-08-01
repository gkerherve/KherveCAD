"""Regenerate ``packaging/khervecad.ico`` from ``packaging/khervecad.png``.

The PNG is the same mark the website serves as /icons/khervecad.png.
Windows needs a multi-resolution .ico for the exe, the installer and the
Start-menu shortcut to all look sharp, so this writes every size in one
file. Run after changing the mark:

    python packaging/make_icon.py

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from pathlib import Path

from PIL import Image

_HERE = Path(__file__).resolve().parent
_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> None:
    src = _HERE / "khervecad.png"
    out = _HERE / "khervecad.ico"
    image = Image.open(src).convert("RGBA")
    image.save(out, format="ICO", sizes=_SIZES)
    print(f"{out.name}  <-  {src.name} {image.size}")


if __name__ == "__main__":
    main()
