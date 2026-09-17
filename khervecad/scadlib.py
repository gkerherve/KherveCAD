"""OpenSCAD libraries: where ``use <...>`` / ``include <...>`` look, and
installing the well-known community libraries.

OpenSCAD resolves a library path against the including file's folder,
then every folder of ``OPENSCADPATH``, then the user library folder
(``~/Documents/OpenSCAD/libraries`` on macOS and Windows,
``~/.local/share/OpenSCAD/libraries`` on Linux), then its own bundled
libraries. KherveCAD renders from a temporary folder, so the engine is
given an ``OPENSCADPATH`` holding the open document's folder plus those
folders (`process_environment`), and the importer resolves the same way
(`resolve`) — so a library installed for OpenSCAD works here too, and
one installed from here works in OpenSCAD.

`KNOWN` lists the libraries of the OpenSCAD manual and openscad.org
whose licences allow use from GPL code, with the file a program
includes. Installing downloads the project's archive from GitHub into
the user library folder — only when the user asks, from Library ▸
OpenSCAD Libraries.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import io
import os
import shutil
import sys
import zipfile
from dataclasses import dataclass

#: the open document's folder (set by the main window when its path
#: changes); searched first after the including file's own folder
DOCUMENT_DIR = None
#: folders imported .scad files read their own libraries from — the
#: engine renders from a temporary folder, so it is told about them
IMPORT_DIRS = []


@dataclass(frozen=True)
class Library:
    key: str            # folder name under the library folder
    title: str
    blurb: str
    repo: str           # GitHub owner/name
    branch: str
    include: str        # what a program writes: include <...> / use <...>
    licence: str


KNOWN = [
    Library("BOSL2", "BOSL2 (Belfry OpenSCAD Library v2)",
            "Attachments, rounding, gears, threads, screws, hinges, "
            "joiners, beziers, textures, sweeps and skins.",
            "BelfrySCAD/BOSL2", "master", "include <BOSL2/std.scad>",
            "BSD-2-Clause"),
    Library("MCAD", "MCAD", "OpenSCAD's classic mechanical library: "
            "involute gears, nuts and bolts, bearings, motors, regular "
            "shapes, teardrops.",
            "openscad/MCAD", "master", "use <MCAD/involute_gears.scad>",
            "LGPL-2.1"),
    Library("NopSCADlib", "NopSCADlib", "Vitamins for 3D printers and "
            "electronics enclosures: motors, extrusions, rails, fans, "
            "PCBs, fasteners, boxes.",
            "nophead/NopSCADlib", "master", "include <NopSCADlib/lib.scad>",
            "GPL-3.0"),
    Library("Round-Anything", "Round Anything", "polyRound: polygons "
            "with a radius at every corner, rounded extrudes and shells.",
            "Irev-Dev/Round-Anything", "master",
            "include <Round-Anything/polyround.scad>", "MIT"),
    Library("dotSCAD", "dotSCAD", "Mathematical and generative shapes: "
            "voronoi, mazes, L-systems, turtle graphics, curves, sweeps.",
            "JustinSDK/dotSCAD", "master", "use <dotSCAD/src/...>",
            "LGPL-3.0"),
    Library("threads-scad", "threads.scad", "ISO metric threads, "
            "screws, nuts and threaded holes.",
            "rcolyer/threads-scad", "master",
            "use <threads-scad/threads.scad>", "CC0-1.0"),
    Library("Catch-n-Hole", "Catch'n'Hole", "Nut catches, screw holes "
            "and countersinks for printed parts.",
            "mmalecki/catchnhole", "latest",
            "use <Catch-n-Hole/catchnhole.scad>", "MIT"),
    Library("gridfinity-rebuilt-openscad", "Gridfinity Rebuilt",
            "Gridfinity bins and baseplates.",
            "kennetek/gridfinity-rebuilt-openscad", "main",
            "use <gridfinity-rebuilt-openscad/...>", "MIT"),
]


def user_library_dir() -> str:
    """OpenSCAD's per-user library folder for this platform."""
    home = os.path.expanduser("~")
    if sys.platform.startswith("linux"):
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(
            home, ".local", "share")
        return os.path.join(base, "OpenSCAD", "libraries")
    return os.path.join(home, "Documents", "OpenSCAD", "libraries")


def installation_library_dirs() -> list:
    """The libraries an OpenSCAD installation ships (MCAD), where the
    engine finds them by itself — the importer has to be told."""
    import glob
    here = os.path.dirname(os.path.abspath(sys.executable))
    patterns = [
        "/Applications/OpenSCAD*.app/Contents/Resources/libraries",
        os.path.expanduser(
            "~/Applications/OpenSCAD*.app/Contents/Resources/libraries"),
        "/usr/share/openscad/libraries", "/usr/local/share/openscad/libraries",
        "/opt/homebrew/share/openscad/libraries",
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                     "OpenSCAD*", "libraries"),
        # the engine bundled beside a frozen KherveCAD
        os.path.join(here, "openscad", "libraries"),
        os.path.join(here, "..", "Resources", "openscad", "OpenSCAD.app",
                     "Contents", "Resources", "libraries"),
    ]
    out = []
    for pattern in patterns:
        out.extend(sorted(glob.glob(pattern)))
    return out


def search_dirs(base_dir=None) -> list:
    """The folders a library path is looked up in, in OpenSCAD's order
    (existing ones only, no repeats)."""
    candidates = [base_dir, DOCUMENT_DIR] + IMPORT_DIRS
    candidates += [p for p in os.environ.get("OPENSCADPATH", "")
                   .split(os.pathsep) if p]
    candidates.append(user_library_dir())
    candidates += installation_library_dirs()
    out = []
    for folder in candidates:
        if folder and os.path.isdir(folder):
            folder = os.path.abspath(folder)
            if folder not in out:
                out.append(folder)
    return out


def remember_import_dir(folder):
    """Search *folder* from now on (an imported file's own libraries)."""
    folder = os.path.abspath(folder)
    if folder not in IMPORT_DIRS:
        IMPORT_DIRS.append(folder)


def resolve(name: str, base_dir=None):
    """The absolute path *name* (as written in ``use <name>``) refers to,
    or None when no search folder holds it."""
    name = str(name or "").strip()
    if not name:
        return None
    if os.path.isabs(name):
        return name if os.path.isfile(name) else None
    for folder in search_dirs(base_dir):
        path = os.path.join(folder, name)
        if os.path.isfile(path):
            return os.path.abspath(path)
    return None


def process_environment():
    """A QProcessEnvironment whose OPENSCADPATH holds every search folder,
    so the engine, running in a temporary folder, finds what the
    document uses."""
    from PyQt5.QtCore import QProcessEnvironment
    env = QProcessEnvironment.systemEnvironment()
    dirs = search_dirs()
    if dirs:
        env.insert("OPENSCADPATH", os.pathsep.join(dirs))
    return env


def installed(lib: Library) -> bool:
    return os.path.isdir(os.path.join(user_library_dir(), lib.key))


def archive_url(lib: Library) -> str:
    return (f"https://codeload.github.com/{lib.repo}/zip/refs/heads/"
            f"{lib.branch}")


def install(lib: Library, opener=None, progress=None) -> str:
    """Download *lib*'s archive and unpack it as ``<library folder>/<key>``.
    Returns the folder. *opener* (url -> bytes) is injectable for tests."""
    if opener is None:
        from .geo import urlopen

        def opener(url):
            with urlopen(url, timeout=120) as response:
                return response.read()
    if progress:
        progress(f"Downloading {lib.title}…")
    data = opener(archive_url(lib))
    target_root = user_library_dir()
    os.makedirs(target_root, exist_ok=True)
    target = os.path.join(target_root, lib.key)
    staging = target + ".partial"
    shutil.rmtree(staging, ignore_errors=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        top = names[0].split("/")[0] + "/" if names else ""
        for info in archive.infolist():
            if not info.filename.startswith(top) or info.is_dir():
                continue
            rel = info.filename[len(top):]
            if not rel or ".." in rel.split("/"):
                continue
            dest = os.path.join(staging, *rel.split("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with archive.open(info) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)
    shutil.rmtree(target, ignore_errors=True)
    os.replace(staging, target)
    if progress:
        progress(f"Installed {lib.title} in {target}")
    return target
