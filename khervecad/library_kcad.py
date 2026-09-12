"""The "KCAD files" library category: every `.kcad` document in
`khervecad/parts/` offered as a library part.

A finished model saved from KherveCAD — a phone stand, a bracket, a
Minecraft cow — drops into any assembly as one Object, next to a
flange or a Lego set, without leaving the app to open it. The folder
is read once at import; a file's stem is the part's label, and the
document's top-level nodes (variables and masters included) become
the part's contents, so the model stays parametric and editable in
the Object tab.

Files land in the folder through the `/add-kcad-library` skill (see
`.claude/skills/add-kcad-library/SKILL.md`), which copies new
documents from the user's KCAD folder, checks that each loads, and
commits; the installer ships the folder through the spec's `datas`.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import os
import re
from pathlib import Path

CATEGORY = "KCAD files"

#: the shipped folder (beside this module — the spec copies it there)
PARTS_DIR = Path(__file__).resolve().parent / "parts"


def part_id(stem: str) -> str:
    """kcad_<slug> — stable across renames of spaces and case."""
    slug = re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_")
    return f"kcad_{slug or 'part'}"


def label(stem: str) -> str:
    return re.sub(r"[_\s]+", " ", stem).strip()


def files(folder=None) -> list:
    """The `.kcad` files of *folder* (PARTS_DIR by default), sorted."""
    folder = Path(folder) if folder else PARTS_DIR
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir()
                  if p.suffix.lower() == ".kcad" and p.is_file())


def load_part(path) -> "CadNode":
    """The document at *path* as one node: a Group holding its top-level
    nodes, mesh paths resolved beside the file."""
    from .document import node_from_dict
    from .meshimport import resolve_paths
    from .model import CadNode
    path = Path(path)
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("format") != "kcad":
        raise ValueError(f"{path.name} is not a KherveCAD document")
    root = node_from_dict(data["tree"])
    resolve_paths(root, os.path.dirname(os.path.abspath(path)))
    part = CadNode("union", label(path.stem))
    for child in list(root.children):
        root.remove(child)
        part.add(child)
    if not part.children:
        raise ValueError(f"{path.name} holds no objects")
    return part


def _builder(path):
    return lambda _dims: load_part(path)


PARTS = {
    part_id(p.stem): dict(label=label(p.stem), category=CATEGORY, sizes={},
                          fields=[], build=_builder(p), path=str(p))
    for p in files()
}
