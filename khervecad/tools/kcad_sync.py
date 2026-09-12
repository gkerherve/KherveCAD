"""Sync the user's .kcad documents into the KCAD-file library folder.

    python -m khervecad.tools.kcad_sync --list [folder ...]
    python -m khervecad.tools.kcad_sync --add file.kcad [file.kcad ...]

`--list` prints the documents in the folders (default: ~/Documents/KCAD
Projects and ~/Documents) that are not yet in khervecad/parts/;
`--add` copies the given files in, with the meshes they reference,
and drops any that fail to load. Driven by the /add-kcad-library
skill; runs offscreen (no window).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")

DEFAULT_FOLDERS = [Path.home() / "Documents" / "KCAD Projects",
                   Path.home() / "Documents"]
MESH_EXTS = (".stl", ".obj", ".off", ".3mf")


def _app():
    from PyQt5.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def existing_ids():
    from khervecad import library_kcad
    return {library_kcad.part_id(p.stem) for p in library_kcad.files()}


def candidates(folders):
    from khervecad import library_kcad
    have = existing_ids()
    out = []
    for folder in folders:
        folder = Path(folder).expanduser()
        for p in library_kcad.files(folder):
            if library_kcad.part_id(p.stem) not in have:
                out.append(p)
    return out


def describe(path):
    """(objects, errors) of the document, or (None, message)."""
    from khervecad import library_kcad
    from khervecad.model import validate
    try:
        part = library_kcad.load_part(path)
    except Exception as exc:                  # any broken file
        return None, str(exc)
    from khervecad.model import CadNode
    root = CadNode("root")
    root.add(part)
    errors = validate(root)
    return sum(1 for _n in part.walk()) - 1, "; ".join(errors.values())


def cmd_list(folders):
    _app()
    found = candidates(folders)
    if not found:
        print("Nothing new: every .kcad in the folder(s) is in the "
              "library already.")
        return 0
    for p in found:
        count, errors = describe(p)
        size = p.stat().st_size // 1024
        if count is None:
            print(f"SKIP  {p}  ({size} KB) — cannot load: {errors}")
        else:
            flag = f" — errors: {errors}" if errors else ""
            print(f"NEW   {p}  ({size} KB, {count} nodes){flag}")
    return 0


def referenced_meshes(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []                    # describe() reports the real error
    out = []
    stack = [data.get("tree", {})]
    while stack:
        d = stack.pop()
        stack.extend(d.get("children", []))
        if d.get("type") == "stl_import":
            raw = str(d.get("params", {}).get("path", ""))
            if raw:
                out.append(raw)
    return out


def cmd_add(paths):
    _app()
    from khervecad import library_kcad
    dest = library_kcad.PARTS_DIR
    dest.mkdir(exist_ok=True)
    added = []
    for raw in paths:
        src = Path(raw).expanduser()
        if src.suffix.lower() != ".kcad" or not src.is_file():
            print(f"SKIP  {src}: not a .kcad file")
            continue
        target = dest / src.name
        shutil.copy2(src, target)
        for mesh in referenced_meshes(src):
            m = Path(mesh)
            if not m.is_absolute():
                m = src.parent / m
            if m.is_file() and m.suffix.lower() in MESH_EXTS:
                shutil.copy2(m, dest / m.name)
        count, errors = describe(target)
        if count is None:
            target.unlink()
            print(f"DROP  {src.name}: {errors}")
            continue
        print(f"ADDED {target.name} ({count} nodes)"
              + (f" — errors: {errors}" if errors else ""))
        added.append(target.name)
    print(f"{len(added)} added; the library now holds "
          f"{len(library_kcad.files())} KCAD parts.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", nargs="*", metavar="FOLDER")
    ap.add_argument("--add", nargs="+", metavar="FILE")
    args = ap.parse_args(argv)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    if args.add:
        return cmd_add(args.add)
    folders = args.list if args.list else DEFAULT_FOLDERS
    return cmd_list(folders)


if __name__ == "__main__":
    sys.exit(main())
