"""One-shot Windows build: frozen app + bundled OpenSCAD + installer + zip.

Run from the project root, with the interpreter that has PyInstaller:

    python packaging/build_installer.py            # everything
    python packaging/build_installer.py --skip-freeze   # reuse dist/KherveCAD

Produces, in ``dist/``:

* ``KherveCAD-Setup-<version>.exe``   — per-user Inno Setup installer
* ``KherveCAD-<version>-portable.zip`` — the same folder, copy and run
* ``KherveCAD-Setup.exe``            — stable-name copy; the website links
                                       to it by filename via the GitHub
                                       "latest release" URL, so it must
                                       exist on every release

The steps, in order:

1. Resolve the version from git and write ``khervecad/VERSION``, which the
   spec bundles — a frozen build has no ``.git`` and would otherwise report
   the ``0.1.0`` placeholder.
2. Freeze with PyInstaller (one folder).
3. Unpack the official OpenSCAD portable ZIP into ``dist/KherveCAD/openscad/``
   so the engine is guaranteed present (``engine.bundled_openscad()`` looks
   there). The ZIP is cached in ``packaging/vendor/`` and downloaded on
   first use. Shipping OpenSCAD's binary makes this a redistribution, so
   its GPL licence text goes in beside it — and the matching OpenSCAD
   source archive must be attached to the GitHub release.
4. Zip the folder, compile the installer, copy the stable name.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent          # packaging/
_ROOT = _HERE.parent                             # project root
_DIST = _ROOT / "dist"
_APP = "KherveCAD"

#: The OpenSCAD build bundled with the app. Bump both together, and attach
#: the matching source archive to the release (GPL-2.0-or-later).
OPENSCAD_VERSION = "2021.01"
OPENSCAD_ZIP = f"OpenSCAD-{OPENSCAD_VERSION}-x86-64.zip"
OPENSCAD_URL = f"https://files.openscad.org/{OPENSCAD_ZIP}"
OPENSCAD_SRC_URL = f"https://files.openscad.org/openscad-{OPENSCAD_VERSION}.src.tar.gz"

_ISCC = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe"


def _run(cmd, **kwargs):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kwargs)


# ------------------------------------------------------------- version

def write_version() -> str:
    """Write ``khervecad/VERSION`` from git; return the numeric part.

    The file holds the full ``0.1.N+sha`` string (what the title bar and
    About box show); the number alone names the artifacts and the tag.
    """
    sys.path.insert(0, str(_ROOT))
    from khervecad._version import get_version

    get_version.cache_clear()
    full = get_version()
    if full == "0.1.0":
        raise SystemExit(
            "refusing to build: version resolved to the 0.1.0 placeholder — "
            "is this a git checkout with git on PATH?"
        )
    (_ROOT / "khervecad" / "VERSION").write_text(full + "\n", encoding="utf-8")
    numeric = re.match(r"[0-9.]+", full).group(0)
    print(f"{_APP} {full}")
    return numeric


# -------------------------------------------------------------- freeze

def freeze() -> None:
    _run([sys.executable, "-m", "PyInstaller",
          _HERE / f"{_APP}.spec", "--noconfirm"], cwd=_ROOT)


# ------------------------------------------------------------ openscad

def bundle_openscad() -> None:
    """Unpack the portable OpenSCAD into dist/KherveCAD/openscad/."""
    cache = _HERE / "vendor" / OPENSCAD_ZIP
    if not cache.is_file():
        cache.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {OPENSCAD_URL}", flush=True)
        urllib.request.urlretrieve(OPENSCAD_URL, cache)

    target = _DIST / _APP / "openscad"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    with zipfile.ZipFile(cache) as archive:
        names = archive.namelist()
        # The ZIP holds one top-level folder (openscad-<version>/); strip it
        # so openscad.exe lands directly in openscad/.
        top = names[0].split("/")[0] + "/"
        if not all(n.startswith(top) for n in names):
            raise SystemExit(f"unexpected layout in {OPENSCAD_ZIP}")
        for name in names:
            rel = name[len(top):]
            if not rel:
                continue
            dest = target / rel
            if name.endswith("/"):
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name) as src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out)

    exe = target / "openscad.exe"
    if not exe.is_file():
        raise SystemExit(f"no openscad.exe in {OPENSCAD_ZIP}")

    # GPL: we are redistributing OpenSCAD's binary, so its licence ships
    # with it and the release carries the matching source archive.
    shutil.copy2(_HERE / "openscad-COPYING.txt", target / "COPYING.txt")
    (target / "README-OpenSCAD.txt").write_text(
        f"OpenSCAD {OPENSCAD_VERSION} (x86-64 portable build)\n"
        f"{OPENSCAD_URL}\n\n"
        "OpenSCAD is free software licensed GPL-2.0-or-later; its licence is\n"
        "in COPYING.txt beside this file. KherveCAD runs it as a separate\n"
        "process and does not link against it. The corresponding source is\n"
        f"attached to the KherveCAD release and available at\n{OPENSCAD_SRC_URL}\n",
        encoding="utf-8",
    )
    size = sum(f.stat().st_size for f in target.rglob("*") if f.is_file())
    print(f"bundled OpenSCAD {OPENSCAD_VERSION}  ({size / 1e6:.0f} MB)")


# ------------------------------------------------------- zip + installer

def build_zip(version: str) -> Path:
    out = _DIST / f"{_APP}-{version}-portable.zip"
    if out.exists():
        out.unlink()
    root = _DIST / _APP
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                # zip root is the app folder, so it extracts as KherveCAD/
                archive.write(path, Path(_APP) / path.relative_to(root))
    return out


def build_installer(version: str) -> Path:
    if not _ISCC.is_file():
        raise SystemExit(f"Inno Setup not found at {_ISCC}")
    _run([_ISCC,
          f"/DAPP_VERSION={version}",
          f"/DSRC_DIR={_DIST / _APP}",
          f"/DOUT_DIR={_DIST}",
          _HERE / "khervecad.iss"])
    out = _DIST / f"{_APP}-Setup-{version}.exe"
    if not out.is_file():
        raise SystemExit(f"installer not produced: {out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-freeze", action="store_true",
                        help="reuse the existing dist/KherveCAD folder")
    args = parser.parse_args()

    version = write_version()
    if not args.skip_freeze:
        freeze()
    bundle_openscad()

    zip_path = build_zip(version)
    exe_path = build_installer(version)
    stable = _DIST / f"{_APP}-Setup.exe"
    shutil.copy2(exe_path, stable)

    print()
    for path in (exe_path, zip_path, stable):
        print(f"{path.name:<40} {path.stat().st_size / 1e6:>7.1f} MB")


if __name__ == "__main__":
    main()
