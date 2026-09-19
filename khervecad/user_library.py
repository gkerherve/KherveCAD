"""**My Library** (Qt-free): the user's own parts on disk, so what was
designed once — by the user or by an assistant — is found and reused
the next time instead of being modelled again.

Each part is a `.kcad` document in the library folder (`folder()`:
`~/Documents/KherveCAD Library`, or $KHERVECAD_USER_LIBRARY), one
subfolder per section. Beside the tree the file carries a top-level
``"library"`` block — ``title``, ``description``, ``tags``, ``source``
(user / assistant), ``created`` — which is what makes it findable: the
title says what the part is and its key size, the description what it
is for, how big it is, what its parameters do and how it is built.
`list_parts` searches title, description and tags, so an assistant
asked for "a hook for a bike" finds the "Wall-mounted bike hook" it
designed last week.

`parts()` lists the folder as Library parts (`user_<slug>`, category
"My library: <section>", built by `library_kcad.load_part`, so a part
drops in as one editable group); `refresh(PARTS)` re-reads the folder
into the live table after a save. `save()` writes a node — with the
Objects it instances, or it would render nothing — as a standalone
document.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import copy
import datetime
import json
import os
import re
from pathlib import Path

PREFIX = "My library"
DEFAULT_SECTION = "General"
ID_PREFIX = "user_"


def folder() -> Path:
    """Where the user's library lives (not created until a save)."""
    env = os.environ.get("KHERVECAD_USER_LIBRARY")
    return Path(env) if env else Path.home() / "Documents" / \
        "KherveCAD Library"


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_") or "part"


def _safe_name(text: str) -> str:
    """A title as a file / folder name: readable, no path separators."""
    name = re.sub(r'[\\/:*?"<>|]+', "-", str(text)).strip(" .")
    return name[:120] or "Part"


def category(section: str) -> str:
    return f"{PREFIX}: {section or DEFAULT_SECTION}"


# ------------------------------------------------------------ reading
def files():
    """Every part file: the folder's own (section General) and one level
    of subfolders (a section each)."""
    root = folder()
    if not root.is_dir():
        return []
    found = sorted(p for p in root.glob("*.kcad") if p.is_file())
    for sub in sorted(p for p in root.iterdir()
                      if p.is_dir() and not p.name.startswith((".", "_"))):
        found += sorted(p for p in sub.glob("*.kcad") if p.is_file())
    return found


def read_info(path) -> dict:
    """The part's title, description, tags and section; a file saved
    without a library block still lists, under its file name."""
    path = Path(path)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    if data.get("format") != "kcad":
        return {}
    info = dict(data.get("library") or {})
    info.setdefault("title", path.stem)
    info.setdefault("description", "")
    info["tags"] = [str(t) for t in info.get("tags") or []]
    section = path.parent.name if path.parent != folder() else \
        DEFAULT_SECTION
    info["section"] = section
    info["unit"] = data.get("unit", "mm")
    info["path"] = str(path)
    return info


def part_id(info) -> str:
    return ID_PREFIX + slug(f"{info['section']} {info['title']}")


def _builder(path, title):
    def build(_dims):
        from .library_kcad import load_part
        node = load_part(path)
        node.name = title
        return node
    return build


def parts() -> dict:
    """The folder as Library part specs."""
    out = {}
    for path in files():
        info = read_info(path)
        if not info:
            continue
        out[part_id(info)] = dict(
            label=info["title"], category=category(info["section"]),
            sizes={}, fields=[], build=_builder(path, info["title"]),
            description=info["description"], tags=info["tags"],
            unit=info["unit"], path=str(path), user=True)
    return out


def refresh(table: dict) -> dict:
    """Re-read the folder into *table* (library.PARTS) in place: saved
    parts appear, deleted ones go. Returns the user parts."""
    for key in [k for k in table if k.startswith(ID_PREFIX)]:
        del table[key]
    mine = parts()
    table.update(mine)
    return mine


# ------------------------------------------------------------ writing
def definitions_for(node, root) -> list:
    """The Objects *node* instances (by name, at any depth, and the ones
    those instance), found under *root* — a placed call of a module the
    file does not define would render nothing."""
    by_name = {n.name: n for n in root.walk() if n.type == "component"}
    need, seen = [], set()
    stack = [node]
    while stack:
        cur = stack.pop()
        for n in cur.walk():
            if n.type == "reference":
                ref = n.params.get("ref")
                target = by_name.get(ref)
                if target is not None and ref not in seen \
                        and target is not node:
                    seen.add(ref)
                    need.append(target)
                    stack.append(target)
    return need


def save(node, title: str, description: str, section: str = "",
         tags=(), root=None, unit: str = "mm", source: str = "assistant",
         global_fn: int = 45) -> dict:
    """Write *node* as a library part. An instance is saved as the Object
    it places. Returns {part_id, path, category, title}."""
    from .document import FORMAT_VERSION, node_to_dict
    from .meshimport import relative_for_save
    title = str(title or "").strip()
    if not title:
        raise ValueError("A library part needs a title that says what "
                         "it is.")
    if node.type == "reference" and root is not None:
        target = next((n for n in root.walk() if n.type == "component"
                       and n.name == node.params.get("ref")), None)
        node = target or node
    section = _safe_name(section.strip()) if section and section.strip() \
        else DEFAULT_SECTION
    base = folder() if section == DEFAULT_SECTION else folder() / section
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{_safe_name(title)}.kcad"
    pieces = [copy.deepcopy(node)]
    if root is not None:
        for d in definitions_for(node, root):
            dd = copy.deepcopy(d)
            dd.visible = False            # a definition, placed by the call
            pieces.insert(0, dd)
    if pieces[-1].type == "component":
        pieces[-1].visible = True
        for key in ("x", "y", "z", "rx", "ry", "rz"):   # at its own origin
            if key in pieces[-1].params:
                pieces[-1].params[key] = 0.0
    tree = {"type": "root", "name": "root", "visible": True, "params": {},
            "children": [node_to_dict(p) for p in pieces]}
    data = {"format": "kcad", "version": FORMAT_VERSION,
            "global_fn": int(global_fn), "global_fn_on": True, "unit": unit,
            "tree": tree,
            "library": {
                "title": title,
                "description": str(description or "").strip(),
                "tags": [str(t).strip() for t in tags if str(t).strip()],
                "source": source,
                "created": datetime.datetime.now().isoformat(
                    timespec="seconds")}}
    relative_for_save(data["tree"], str(path))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)
    info = read_info(path)
    return {"part_id": part_id(info), "path": str(path),
            "category": category(info["section"]), "title": title}


def matches(spec: dict, pid: str, words) -> bool:
    """Whether every search word is in the part's id, label, category,
    description or tags."""
    text = " ".join([pid, spec.get("label", ""), spec.get("category", ""),
                     spec.get("description", "")]
                    + list(spec.get("tags") or [])).lower()
    return all(w in text for w in words)
