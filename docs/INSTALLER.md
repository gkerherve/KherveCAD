# Installer — how KherveCAD is packaged

**Decision reversed August 2026.** This file used to say "no installer
yet, parked until KherveCAD is a finished product". KherveCAD now ships
a Windows installer; what follows is how it is built and why it is built
that way. Running from a git checkout (`python KherveCAD.py`, deps in
`requirements.txt`) still works and is unchanged.

## Goal

One download that guarantees the OpenSCAD engine is present, so no user
ever lands silently in approximate-boolean preview mode.

## What ships

`python packaging/build_installer.py` (from the project root, with the
interpreter that has PyInstaller) does the whole thing and writes three
files into `dist/`:

| Artifact | What it is |
|---|---|
| `KherveCAD-Setup-<ver>.exe` | per-user Inno Setup installer, no admin |
| `KherveCAD-<ver>-portable.zip` | the same folder, copy and run |
| `KherveCAD-Setup.exe` | stable-name copy the website links to |

The steps it runs, and the reason each exists:

1. **Write `khervecad/VERSION`.** The version is derived from
   `git rev-list --count HEAD`, and a PyInstaller bundle ships no `.git`
   — without this file the installed app reports the `0.1.0` fallback.
   `_version.py` reads it first; the spec bundles it; `.gitignore`
   ignores it. The build refuses to run if the version resolves to the
   placeholder.
2. **Freeze** with PyInstaller, one *folder* not one file: it starts
   faster, and OpenSCAD can sit next to the exe. `packaging/KherveCAD.spec`
   pulls the whole `khervecad` package in with `collect_submodules` —
   the `examples_*` and `library_*` modules register themselves by import
   side effect, so nothing static references them.
3. **Bundle OpenSCAD** from the official *portable ZIP* (cached in
   `packaging/vendor/`, downloaded on first use), unpacked into an
   `openscad/` subfolder of the frozen app. `OPENSCAD_VERSION` in
   `build_installer.py` is the single place that decides which build.
4. **Zip**, then compile `packaging/khervecad.iss`, then copy the stable
   name.

`engine.bundled_openscad()` is what makes step 3 pay off: it looks in
`openscad/` beside the executable (`sys.executable`, and `sys._MEIPASS`
for a one-file build) and beside the project root when running from a
checkout. `find_openscad()` tries the user's explicitly located binary
first, *then* the bundle, then PATH and the usual install directories —
the bundle beats discovery, but not a path the user deliberately chose,
or Edit > Locate OpenSCAD would silently do nothing in an installed
build.

Rejected alternatives, for the record:

- *first-run downloader* (app offers to fetch the portable ZIP into
  app-data) — lighter, but needs internet and a URL kept current;
  acceptable fallback if installer size ever becomes a problem.
- *prerequisite check only* (`winget install OpenSCAD.OpenSCAD`) —
  cheapest, but does not actually guarantee the engine.

## Licensing (GPL) — obligations, not preferences

- OpenSCAD is GPL-2.0-or-later; KherveCAD is GPL-3.0 — compatible.
- We invoke it as a **separate process** (QProcess), no linking.
- Shipping the binary makes us a redistributor, so:
  - its licence text installs beside it as `openscad/COPYING.txt`
    (vendored at `packaging/openscad-COPYING.txt`), with
    `openscad/README-OpenSCAD.txt` naming the version and where it came
    from, and
  - the matching **OpenSCAD source archive must be attached to the same
    GitHub release** (`OPENSCAD_SRC_URL` in `build_installer.py`).

If `OPENSCAD_VERSION` is ever bumped, re-vendor `openscad-COPYING.txt`
from that tag and attach that version's source archive.

## macOS

Same goal, same obligations, different container: `packaging/build_macos.py`
produces `dist/KherveCAD-<ver>-macOS-arm64.dmg`. It is the counterpart of
`build_installer.py` and shares its first step (write `khervecad/VERSION`),
then diverges where the platform does:

- **`.app`, not a folder.** The spec ends in `BUNDLE` on macOS, so
  PyInstaller's collected tree is wrapped into `dist/KherveCAD.app` with
  the `Info.plist` that gives it a Dock icon and the `.kcad` / `.scad` /
  mesh document associations. The icon is an `.icns` generated from the
  same PNG by `packaging/make_icns.py`.
- **OpenSCAD comes from a disk image**, not a portable ZIP, so the build
  mounts it and `ditto`s `OpenSCAD.app` into
  `KherveCAD.app/Contents/Resources/openscad/`. `bundled_openscad()`
  knows both layouts.
- **arm64 only**, because the last stable OpenSCAD (2021.01) has no
  Apple Silicon binary — the engine has to come from a snapshot, which
  the build discovers from OpenSCAD's index rather than pinning. The
  build verifies the architecture and refuses a Rosetta-only pair.
- **Ad-hoc signing is mandatory and goes last.** Apple Silicon will not
  execute an unsigned Mach-O, and dropping OpenSCAD in invalidates the
  signature PyInstaller applied.
- **No installer to compile.** A drag-install replaces the bundle
  atomically, so nothing `khervecad.iss` guards against applies.

`.github/workflows/macos-build.yml` runs all of it on a `macos-14`
runner and publishes the DMG plus OpenSCAD's source archive under a
`macos-v<ver>` tag — created with `--latest=false` so `releases/latest`
stays on the Windows release the website's download button points at.
Full detail in `README.macos.md`.

## Not done yet

- Both builds are **unsigned** in the sense that matters: SmartScreen
  warns on Windows, and the macOS DMG is ad-hoc signed but not
  notarized, so Gatekeeper quarantines it. Code signing is an open
  problem across the whole Kherve family.
- Linux would need its own OpenSCAD bundle and container (AppImage).
