# Installer plan — parked until KherveCAD is a finished product

**Decision (July 2026): no installer yet.** KherveCAD runs from a
git checkout (`python KherveCAD.py`, deps in `requirements.txt`).
This file records the agreed plan so it isn't re-litigated later.

## Goal

One download that guarantees the OpenSCAD engine is present, so no
user ever lands silently in approximate-boolean preview mode.

## Chosen route (Windows first)

1. **Freeze** the app with PyInstaller (one-folder build, not
   one-file: faster start, and OpenSCAD sits alongside).
2. **Bundle OpenSCAD** from the official *portable ZIP*: copy
   `openscad.exe` + its DLLs into an `openscad/` subfolder of the
   frozen app.
3. **Wrap** both in an Inno Setup installer; per-user install
   (no admin), Start-menu shortcut, `.kcad` file association.
4. Publish on GitHub Releases.

Rejected alternatives, for the record:
- *first-run downloader* (app offers to fetch the portable ZIP into
  app-data) — lighter, but needs internet and a URL kept current;
  acceptable fallback if installer size ever becomes a problem.
- *prerequisite check only* (`winget install OpenSCAD.OpenSCAD`) —
  cheapest, but does not actually guarantee the engine.

## Licensing checklist (GPL)

- OpenSCAD is GPL-2.0-or-later; KherveCAD is GPL-3.0 — compatible.
- We invoke it as a **separate process** (QProcess), no linking.
- Shipping the binary makes us a redistributor: include OpenSCAD's
  licence text in the installer and attach the matching OpenSCAD
  **source ZIP** to the same GitHub Release.

## Code prerequisite (do this first, cheap now)

Teach `find_openscad()` in `khervecad/engine.py` to look **next to
the application first** — an `openscad/` subfolder beside the
executable (and `sys._MEIPASS` when frozen) — before QSettings,
PATH and the `_CANDIDATES` list. That one change makes a bundled
copy, a downloaded copy and a system install all resolve through
the same path, and is harmless while we are source-only.
