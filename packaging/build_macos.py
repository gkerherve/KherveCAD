"""One-shot macOS build: .app + bundled OpenSCAD + ad-hoc signature + DMG.

The macOS counterpart of ``build_installer.py``. Run from the project
root, on a Mac, with the interpreter that has PyInstaller:

    python packaging/build_macos.py                  # everything
    python packaging/build_macos.py --skip-freeze    # reuse dist/KherveCAD.app

Produces, in ``dist/``:

* ``KherveCAD-<version>-macOS-<arch>.dmg`` — drag-to-install disk image
* ``KherveCAD-macOS-<arch>.dmg``           — stable-name copy, the name a
                                             "latest release" link can use
* ``openscad-<osver>.src.tar.gz``          — OpenSCAD's source, which the
                                             GPL requires us to ship with
                                             the binary we redistribute

The steps, in order:

1. Resolve the version from git and write ``khervecad/VERSION`` (shared
   with the Windows build — a frozen bundle has no ``.git``).
2. Freeze with PyInstaller. On macOS the spec ends in ``BUNDLE``, so this
   yields ``dist/KherveCAD.app``, not a bare folder.
3. Drop the official **OpenSCAD.app** into
   ``KherveCAD.app/Contents/Resources/openscad/`` so the engine is
   guaranteed present (``engine.bundled_openscad()`` looks there). The
   Windows build unpacks a portable ZIP; macOS ships disk images, so this
   mounts one and copies the app out. Which build is used is discovered
   from OpenSCAD's own index, because the last *stable* release (2021.01)
   predates Apple Silicon and has no arm64 binary — only the snapshots do.
4. Ad-hoc sign. Apple Silicon refuses to execute an unsigned Mach-O at
   all, and dropping OpenSCAD into the tree invalidates whatever
   PyInstaller signed, so the finished bundle is re-signed as a whole.
   This is not notarization — see ``README.macos.md``.
5. Seal it into a DMG with the ``/Applications`` symlink that makes the
   mounted window a drag-install.

There is no installer to compile: on macOS a drag-install replaces the
whole bundle atomically, so the upgrade problems ``khervecad.iss`` works
around cannot happen here.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

_HERE = Path(__file__).resolve().parent          # packaging/
_ROOT = _HERE.parent                             # project root
_DIST = _ROOT / "dist"
_APP = "KherveCAD"

sys.path.insert(0, str(_HERE))
from build_installer import write_version        # noqa: E402  (shared step)

#: Where OpenSCAD publishes its builds. The stable directory holds
#: 2021.01, whose only macOS binary is x86_64 — an Apple Silicon Mac
#: would need Rosetta to run it, which defeats the point of bundling the
#: engine at all. The arm64 builds live in snapshots/, so that is where
#: we look first.
_OPENSCAD_INDEXES = [
    "https://files.openscad.org/snapshots/",
    "https://files.openscad.org/",
]

#: Set either to pin an exact build instead of taking the newest one.
_URL_OVERRIDE = os.environ.get("KHERVECAD_OPENSCAD_DMG", "")
_SRC_OVERRIDE = os.environ.get("KHERVECAD_OPENSCAD_SRC", "")

#: What the arch is called in an OpenSCAD filename.
_ARCH_TOKENS = {"arm64": ("arm64",), "x86_64": ("x86_64", "x86-64")}

#: A *dated* macOS image: ``OpenSCAD-2026.06.12.dmg``, optionally with a
#: build suffix and an architecture. The date is what makes this
#: trustworthy — the snapshots index also carries branch builds
#: (``OpenSCAD-tests2.dmg``, ``OpenSCAD-c++11.dmg``) which sort *after*
#: every real snapshot and would otherwise win.
#: The day is optional so the stable ``OpenSCAD-2021.01.dmg`` matches too.
_DATED_DMG = re.compile(
    r"^OpenSCAD-(\d{4}\.\d{2}(?:\.\d{2})?(?:\.[A-Za-z0-9]+)?)"
    r"(?:-(arm64|x86[-_]64))?\.dmg$")

#: What a source archive can be called. The stable index uses
#: ``openscad-<ver>.src.tar.gz``; snapshots have varied.
_SOURCE_SUFFIXES = (".src.tar.gz", ".tar.gz", ".tar.xz", ".tgz")


def _run(cmd, **kwargs):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kwargs)


def _fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read().decode("utf-8", "replace")


# -------------------------------------------------------------- freeze

def freeze() -> None:
    _run([sys.executable, "-m", "PyInstaller",
          _HERE / f"{_APP}.spec", "--noconfirm"], cwd=_ROOT)


# ------------------------------------------------------------ openscad

def _find_source(index: str, names: list[str], version: str) -> str:
    """URL of the source archive matching *version*, or '' if absent."""
    exact = f"openscad-{version}.src.tar.gz"
    if exact in names:
        return index + exact
    # Snapshot sources have not always used the .src infix, so fall back to
    # anything that carries the same version and is plainly a source
    # tarball. The version match is what keeps this honest: the GPL
    # obligation is the source *corresponding* to the binary we ship.
    pattern = re.compile(rf"(?i)^openscad[-_]{re.escape(version)}\b.*$")
    for name in sorted(names):
        if pattern.match(name) and name.endswith(_SOURCE_SUFFIXES):
            return index + name
    return ""


def resolve_openscad(arch: str) -> tuple[str, str]:
    """Return ``(dmg_url, src_url)`` for the newest usable macOS build.

    Both are discovered from OpenSCAD's directory index rather than
    hard-coded, because the snapshot filenames carry a build date and a
    revision that change under us. The chosen pair is printed, so a
    release can be reproduced later by feeding the two URLs back in
    through ``KHERVECAD_OPENSCAD_DMG`` / ``KHERVECAD_OPENSCAD_SRC``.

    The filename is *not* treated as proof of architecture. OpenSCAD's
    macOS images are mostly untagged (a single universal binary), so an
    arch-tagged name is only preferred, never required —
    ``_check_arch()`` on the extracted binary is what actually decides
    whether the build is usable.
    """
    if _URL_OVERRIDE and _SRC_OVERRIDE:
        return _URL_OVERRIDE, _SRC_OVERRIDE

    tokens = _ARCH_TOKENS[arch]
    tried = []
    for index in _OPENSCAD_INDEXES:
        page = _fetch(index)
        names = re.findall(r'href="([^"?/]+)"', page)
        # (version, name) for every dated image not built for another arch.
        dated = []
        for name in names:
            match = _DATED_DMG.match(name)
            if match and (match.group(2) is None
                          or any(t in match.group(2) for t in tokens)):
                dated.append((match.group(1), name))
        dated.sort()
        print(f"{index}: {len(names)} entries, {len(dated)} dated macOS images",
              flush=True)
        for _, name in dated[-3:]:
            print(f"  {name}", flush=True)
        if not dated:
            tried.append(f"{index} (no dated image)")
            continue

        version, dmg = dated[-1]
        src_url = _SRC_OVERRIDE or _find_source(index, names, version)
        if not src_url:
            sources = [n for n in sorted(names)
                       if n.endswith(_SOURCE_SUFFIXES)][-6:]
            print(f"  source archives here: {', '.join(sources) or 'none'}",
                  flush=True)
            tried.append(f"{index} (no source for {version})")
            continue
        return _URL_OVERRIDE or (index + dmg), src_url

    # The GPL obligation is the *corresponding* source for the binary we
    # ship, so a build with no source to attach stops rather than guesses.
    raise SystemExit(
        "no macOS OpenSCAD build with a matching source archive:\n  "
        + "\n  ".join(tried)
        + "\nSet KHERVECAD_OPENSCAD_DMG and KHERVECAD_OPENSCAD_SRC to pin both."
    )


def _download(url: str, dest: Path) -> Path:
    if dest.is_file():
        print(f"cached {dest.name}", flush=True)
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {url}", flush=True)
    urllib.request.urlretrieve(url, dest)
    return dest


def bundle_openscad(app: Path, arch: str) -> str:
    """Copy OpenSCAD.app into *app*'s Resources; return the version used."""
    dmg_url, src_url = resolve_openscad(arch)
    print(f"OpenSCAD: {dmg_url}", flush=True)
    dmg = _download(dmg_url, _HERE / "vendor" / dmg_url.rsplit("/", 1)[-1])
    version = _version_of(dmg.name) or "unknown"

    # The source archive is a release asset, not part of the bundle: it
    # goes to dist/ for whoever uploads the release to attach.
    src = _download(src_url, _DIST / src_url.rsplit("/", 1)[-1])

    target = app / "Contents" / "Resources" / "openscad"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    mount = _DIST / "openscad-mount"
    if mount.exists():
        _run(["hdiutil", "detach", mount, "-force"])
    _run(["hdiutil", "attach", dmg, "-nobrowse", "-readonly",
          "-mountpoint", mount])
    try:
        inner = next(mount.glob("*.app"), None)
        if inner is None:
            raise SystemExit(f"no .app inside {dmg.name}")
        # -R follows nothing and preserves the symlinks inside the
        # framework tree; ditto is the macOS tool that gets that right.
        _run(["ditto", inner, target / "OpenSCAD.app"])
    finally:
        _run(["hdiutil", "detach", mount, "-force"])

    binary = target / "OpenSCAD.app" / "Contents" / "MacOS" / "OpenSCAD"
    if not binary.is_file():
        raise SystemExit(f"no OpenSCAD binary at {binary}")
    binary.chmod(0o755)
    _check_arch(binary, arch)

    # GPL: we are redistributing OpenSCAD's binary, so its licence ships
    # with it and the release carries the matching source archive.
    shutil.copy2(_HERE / "openscad-COPYING.txt", target / "COPYING.txt")
    (target / "README-OpenSCAD.txt").write_text(
        f"OpenSCAD {version} ({arch} macOS build)\n{dmg_url}\n\n"
        "OpenSCAD is free software licensed GPL-2.0-or-later; its licence is\n"
        "in COPYING.txt beside this file. KherveCAD runs it as a separate\n"
        "process and does not link against it. The corresponding source is\n"
        f"attached to the KherveCAD release as {src.name} and available at\n"
        f"{src_url}\n",
        encoding="utf-8",
    )
    size = sum(f.stat().st_size for f in target.rglob("*") if f.is_file())
    print(f"bundled OpenSCAD {version}  ({size / 1e6:.0f} MB)")
    return version


def _check_arch(binary: Path, arch: str) -> None:
    """Fail if the engine is not native — the whole point is no Rosetta."""
    out = subprocess.run(["file", "-b", str(binary)],
                         capture_output=True, text=True, check=True).stdout
    print(f"engine: {out.strip()}")
    if arch not in out:
        raise SystemExit(
            f"bundled OpenSCAD is not {arch}: {out.strip()}\n"
            "A non-native engine needs Rosetta, which defeats bundling it."
        )


# ------------------------------------------------------------ sign + dmg

def sign(app: Path) -> None:
    """Ad-hoc sign the finished tree.

    Not cosmetic: Apple Silicon kills an unsigned Mach-O at launch, and
    every post-freeze edit (OpenSCAD, the licence files) invalidates the
    signature PyInstaller applied, so this has to run last.
    """
    _run(["codesign", "--force", "--deep", "--sign", "-",
          "--timestamp=none", app])
    _run(["codesign", "--verify", "--deep", "--strict", app])


def build_dmg(app: Path, version: str, arch: str) -> Path:
    stage = _ROOT / "build" / "dmg"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    _run(["ditto", app, stage / app.name])
    # The /Applications symlink is what turns the mounted window into the
    # familiar drag-to-install gesture.
    (stage / "Applications").symlink_to("/Applications")

    out = _DIST / f"{_APP}-{version}-macOS-{arch}.dmg"
    out.unlink(missing_ok=True)
    _run(["hdiutil", "create", "-volname", _APP, "-srcfolder", stage,
          "-fs", "HFS+", "-format", "UDZO", "-imagekey", "zlib-level=9",
          "-ov", out])
    shutil.rmtree(stage)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-freeze", action="store_true",
                        help="reuse the existing dist/KherveCAD.app")
    args = parser.parse_args()

    if sys.platform != "darwin":
        raise SystemExit("build_macos.py only runs on macOS "
                         "(PyInstaller cannot cross-compile)")

    arch = platform.machine()
    if arch not in _ARCH_TOKENS:
        raise SystemExit(f"unsupported architecture {arch!r}")

    version = write_version()
    if not args.skip_freeze:
        freeze()

    app = _DIST / f"{_APP}.app"
    if not app.is_dir():
        raise SystemExit(f"{app} not found — did PyInstaller's BUNDLE run?")

    bundle_openscad(app, arch)
    sign(app)
    dmg = build_dmg(app, version, arch)

    stable = _DIST / f"{_APP}-macOS-{arch}.dmg"
    shutil.copy2(dmg, stable)

    print()
    for path in (dmg, stable):
        print(f"{path.name:<44} {path.stat().st_size / 1e6:>7.1f} MB")


if __name__ == "__main__":
    main()
