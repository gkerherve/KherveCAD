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
import shutil
import uuid
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


#: the usual areas of work, each with words that point to it — a save
#: without a section, or with a synonym ("football", "sports", "unit
#: cell"), lands in the right one; anything else becomes a new folder
AREAS = {
    "Sport": ("sport", "stadium", "football", "soccer", "rugby", "tennis",
              "basketball", "badminton", "volleyball", "handball", "arena",
              "pitch", "court", "goal", "athletic", "gym", "dugout"),
    "House & home": ("house", "home", "room", "furniture", "chair", "table",
                     "sofa", "bed", "kitchen", "bathroom", "shelf", "lamp",
                     "cupboard", "wardrobe", "desk", "door", "window"),
    "Garden & outdoor": ("fence", "gate", "porch", "veranda", "patio",
                         "decking", "deck", "pergola", "gazebo", "hedge",
                         "lawn", "grass", "paving", "planter", "trellis",
                         "bench"),
    "Buildings": ("building", "library", "church", "tower", "skyscraper",
                  "bridge", "shed", "barn", "office", "school", "museum"),
    "Trees & plants": ("tree", "leaf", "leaves", "plant", "flower", "bush",
                       "shrub", "garden", "forest", "branch", "needle"),
    "Molecules": ("molecule", "compound", "smiles", "protein", "peptide",
                  "chemical", "caffeine", "reaction"),
    "Unit cells & crystals": ("unit cell", "crystal", "lattice",
                              "supercell", "nanotube", "graphene",
                              "surface slab", "perovskite", "quartz"),
    "Mechanical": ("gear", "bearing", "shaft", "pulley", "mechanism",
                   "hinge", "spring", "piston", "cam", "linkage", "motor"),
    "Fasteners & brackets": ("bolt", "screw", "nut", "washer", "bracket",
                             "hook", "clip", "fastener", "rivet"),
    "Electronics": ("electronic", "pcb", "arduino", "raspberry", "circuit",
                    "resistor", "enclosure", "sensor", "connector"),
    "Vacuum & UHV": ("vacuum", "uhv", "flange", "chamber", "manipulator",
                     "pump", "valve", "cf40", "kf"),
    "Vehicles": ("car", "vehicle", "truck", "bike", "bicycle", "boat",
                 "plane", "aircraft", "train", "wheel"),
    "Characters & animals": ("character", "person", "human", "figure",
                             "animal", "dog", "cat", "hero", "robot"),
    "3D printing": ("print", "printable", "snap-fit", "gridfinity",
                    "dovetail", "insert boss"),
    "Tools": ("tool", "spanner", "wrench", "hammer", "plier",
              "screwdriver", "saw"),
    "Toys & games": ("lego", "toy", "game", "card", "brick", "puzzle"),
    "Kitchen & tableware": ("cup", "mug", "plate", "bowl", "glass",
                            "teapot", "cutlery"),
    "Music": ("instrument", "guitar", "piano", "drum", "violin", "music"),
    "Science & space": ("planet", "moon", "orrery", "solar", "telescope",
                        "lab", "experiment"),
}


def _norm(name: str) -> str:
    """For matching area names: lower case, '&' / 'and' and plural s
    folded ('Sports' = 'sport', 'Trees and plants' = 'trees & plants')."""
    text = re.sub(r"\band\b", "&", str(name).lower())
    text = re.sub(r"[^a-z0-9&]+", " ", text).strip()
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") else w
                    for w in text.split())


def existing_sections() -> list:
    root = folder()
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir()
                  if p.is_dir() and not p.name.startswith((".", "_")))


def _keyword_area(text: str):
    text = f" {str(text).lower()} "
    best, score = None, 0
    for area, words in AREAS.items():
        hits = sum(1 for w in words
                   if re.search(rf"(?<![a-z]){re.escape(w)}", text))
        if hits > score:
            best, score = area, hits
    return best


def choose_section(section="", title="", description="", tags=()) -> str:
    """The folder a part goes in: the area named (matched to an existing
    folder or a usual area whatever its case, plural or synonym), else
    the area its title / tags / description point to, else General. A
    new area name is kept as given and becomes a new folder."""
    wanted = str(section or "").strip()
    if wanted:
        key = _norm(wanted)
        for name in existing_sections() + list(AREAS):
            if _norm(name) == key:
                return name
        for name in existing_sections() + list(AREAS):
            if key and (key in _norm(name).split(" & ") or
                        _norm(name).startswith(key + " ")):
                return name
        area = _keyword_area(wanted)
        if area and _norm(wanted) in [_norm(w) for w in AREAS[area]]:
            return area                    # "football" -> Sport
        return _safe_name(wanted[:1].upper() + wanted[1:])
    # the title says what it is; tags next; the description (which may
    # list the parts it is made of — a school full of tables) last
    for text in (title, " ".join(tags), description):
        guess = _keyword_area(str(text))
        if guess:
            return guess
    return DEFAULT_SECTION


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
         global_fn: int = 45, uid: str = "") -> dict:
    """Write *node* as a library part. An instance is saved as the Object
    it places. *uid* ties the file to one Object: saving it again under
    a new title or area replaces the old file instead of leaving it
    behind. Returns {part_id, path, category, title, uid}."""
    from .document import FORMAT_VERSION, node_to_dict
    from .meshimport import relative_for_save
    title = str(title or "").strip()
    if not title:
        raise ValueError("A library part needs a title that says what "
                         "it is.")
    if not uid and node.type == "component":
        uid = meta_of(node).get("uid", "")
    if node.type == "reference" and root is not None:
        target = next((n for n in root.walk() if n.type == "component"
                       and n.name == node.params.get("ref")), None)
        node = target or node
    tags = [str(t).strip() for t in tags if str(t).strip()]
    section = choose_section(section, title, description, tags)
    uid = uid or uuid.uuid4().hex
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
                "source": source, "uid": uid,
                "created": datetime.datetime.now().isoformat(
                    timespec="seconds")}}
    relative_for_save(data["tree"], str(path))
    for old in files():               # the same Object, renamed or moved
        if old != path and read_info(old).get("uid") == uid:
            old.unlink()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)
    info = read_info(path)
    return {"part_id": part_id(info), "path": str(path),
            "category": category(info["section"]), "title": title,
            "uid": uid, "section": section}


def matches(spec: dict, pid: str, words) -> bool:
    """Whether every search word is in the part's id, label, category,
    description or tags."""
    text = " ".join([pid, spec.get("label", ""), spec.get("category", ""),
                     spec.get("description", "")]
                    + list(spec.get("tags") or [])).lower()
    return all(w in text for w in words)


# ------------------------------------------------------------ managing
IGNORED_FILE = ".ignored.json"


def ignored() -> set:
    """Object uids the user deleted from the library: autosave must not
    bring them back."""
    try:
        with open(folder() / IGNORED_FILE, encoding="utf-8") as fh:
            return set(json.load(fh))
    except (OSError, ValueError):
        return set()


def _ignore(uids):
    uids = {u for u in uids if u}
    if not uids:
        return
    folder().mkdir(parents=True, exist_ok=True)
    with open(folder() / IGNORED_FILE, "w", encoding="utf-8") as fh:
        json.dump(sorted(ignored() | uids), fh)


def unignore(uid):
    keep = ignored() - {uid}
    if folder().is_dir():
        with open(folder() / IGNORED_FILE, "w", encoding="utf-8") as fh:
            json.dump(sorted(keep), fh)


def _check_inside(path) -> Path:
    path = Path(path).resolve()
    root = folder().resolve()
    if root not in path.parents and path != root:
        raise ValueError(f"{path} is not in My Library.")
    return path


def remove(path, trash=None):
    """Take a part (a .kcad) or a whole section (a folder) out of the
    library. *trash(path) -> bool* moves it to the system trash when it
    can (the Qt side passes QFile.moveToTrash); otherwise it is deleted.
    Its Objects are remembered so autosave leaves them out."""
    path = _check_inside(path)
    if path == folder().resolve():
        raise ValueError("That is the whole library.")
    targets = [path] if path.is_file() else sorted(path.glob("*.kcad"))
    _ignore(read_info(p).get("uid") for p in targets)
    if trash is not None and trash(str(path)):
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def add_section(name) -> Path:
    name = _safe_name(str(name).strip())
    if not name or name == DEFAULT_SECTION:
        raise ValueError("Give the section a name.")
    path = folder() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def rename_section(old, new) -> Path:
    src = _check_inside(folder() / old)
    dst = folder() / _safe_name(str(new).strip())
    if not src.is_dir():
        raise ValueError(f"No section {old!r}.")
    if dst.exists() and dst.resolve() != src:
        raise ValueError(f"There is already a section {new!r}.")
    src.rename(dst)
    return dst


def move(path, section) -> Path:
    """Move a part into another section (made if new)."""
    path = _check_inside(path)
    base = folder() if not section or section == DEFAULT_SECTION else \
        add_section(section)
    dst = base / path.name
    if dst.resolve() != path:
        if dst.exists():
            raise ValueError(f"{section} already has a {path.stem!r}.")
        path.rename(dst)
    return dst


def update_info(path, title=None, description=None, tags=None) -> Path:
    """Edit a part's title / description / tags; a new title renames
    the file to match."""
    path = _check_inside(path)
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    lib = data.setdefault("library", {})
    if title is not None and str(title).strip():
        lib["title"] = str(title).strip()
    if description is not None:
        lib["description"] = str(description).strip()
    if tags is not None:
        lib["tags"] = [str(t).strip() for t in tags if str(t).strip()]
    dst = path.with_name(f"{_safe_name(lib.get('title') or path.stem)}.kcad")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)
    if dst != path:
        if dst.exists():
            raise ValueError(f"There is already a {dst.stem!r} here.")
        path.rename(dst)
    return dst


def import_file(src, section="") -> Path:
    """Copy a .kcad from anywhere into the library (a section, or where
    its content points)."""
    src = Path(src)
    info = read_info(src)
    if not info:
        raise ValueError(f"{src.name} is not a KherveCAD document.")
    title = info.get("title") or src.stem
    section = choose_section(section, title, info.get("description", ""),
                             info.get("tags", []))
    base = folder() if section == DEFAULT_SECTION else add_section(section)
    dst = base / src.name
    shutil.copy2(src, dst)
    return dst


# ------------------------------------------------------------ autosave
GENERIC = re.compile(r"^(object|group|union|part|component|body|move|"
                     r"color|colour|translate|rotate)( ?\d+)?$", re.I)
#: an Object carrying one of these was built by a Library part or a
#: builder (house, city, car, character...) — it is not the user's design
BUILT_BY = ("library_part", "house", "city", "car", "character", "lego")


def eligible(node) -> bool:
    """An Object worth keeping: named, not generic, not from the Library
    or a builder, holding geometry."""
    if node.type != "component":
        return False
    if any(k in node.params for k in BUILT_BY):
        return False
    kids = [c for c in node.children if c.type not in ("assign",
                                                       "variables")]
    if len(kids) == 1 and "library_part" in kids[0].params:
        return False                  # a Library part wrapped as an Object
    name = node.name.strip()
    if not name or GENERIC.match(name):
        return False
    return any(n is not node and n.type not in (
        "assign", "variables", "union", "component", "color", "translate",
        "rotate") for n in node.walk())


def describe(node) -> str:
    """A generated description: overall size, what it is built from, its
    variables — until the user or an assistant writes a better one."""
    from . import mesh
    counts = {}
    names = []
    for n in node.walk():
        if n is node:
            continue
        counts[n.type] = counts.get(n.type, 0) + 1
        if n.type == "assign":
            names.append(n.name.rstrip(" ="))
    try:
        tris = mesh.tessellate(node, fn=12)
        xs = [p[0] for t in tris for p in t]
        ys = [p[1] for t in tris for p in t]
        zs = [p[2] for t in tris for p in t]
        size = (f"{max(xs) - min(xs):.0f} x {max(ys) - min(ys):.0f} x "
                f"{max(zs) - min(zs):.0f}") if tris else ""
    except Exception:
        size = ""
    kinds = ", ".join(f"{v} {k}" for k, v in sorted(
        counts.items(), key=lambda kv: -kv[1])[:6])
    text = f"{node.name}."
    if size:
        text += f" Overall size {size} (document units)."
    text += f" Built from {kinds}."
    if names:
        text += f" Parameters: {', '.join(names[:12])}."
    return text + " (Description generated automatically.)"


def meta_of(node) -> dict:
    """The library info an Object carries (params["library"])."""
    meta = node.params.get("library")
    return dict(meta) if isinstance(meta, dict) else {}


def autosave(node, root=None, unit="mm", global_fn=45) -> dict | None:
    """Save *node* as the user's part, reusing its uid, title, area and
    description from params["library"] when set (and storing them there
    when not). None when it is not eligible or was deleted by the user."""
    if not eligible(node):
        return None
    meta = meta_of(node)
    uid = meta.get("uid") or uuid.uuid4().hex
    if uid in ignored():
        return None
    title = meta.get("title") or node.name
    if meta.get("title") and meta.get("named") != node.name:
        title = node.name                 # renamed since: follow the tree
    description = meta.get("description") or describe(node)
    saved = save(node, title, description, meta.get("area", ""),
                 meta.get("tags") or [], root=root, unit=unit,
                 source=meta.get("source", "auto"), global_fn=global_fn,
                 uid=uid)
    meta.update(uid=uid, title=title, area=saved["section"],
                named=node.name)
    if meta.get("description"):
        meta["description"] = description
    node.params["library"] = meta
    return saved


def remember(node, saved, description="", tags=(), source="assistant"):
    """Record an explicit save on the Object itself, so later autosaves
    keep its title, area, description and file."""
    target = node
    meta = meta_of(target)
    meta.update(uid=saved["uid"], title=saved["title"],
                area=saved["section"], named=target.name, source=source)
    if description:
        meta["description"] = description
    if tags:
        meta["tags"] = [str(t) for t in tags]
    target.params["library"] = meta


# ------------------------------------------------ whole designs
def _design_uid(path) -> str:
    import hashlib
    return "doc-" + hashlib.sha1(
        str(Path(path).expanduser().resolve()).encode()).hexdigest()[:16]


def _find_uid(uid):
    for p in files():
        info = read_info(p)
        if info.get("uid") == uid:
            return p, info
    return None, {}


def describe_design(model, title) -> str:
    objects = [n.name for n in model.root.children if n.type == "component"]
    loose = [n for n in model.root.children
             if n.type not in ("component", "variables", "assign")]
    text = f"{title}: a whole design (every part of the document)."
    if getattr(model, "house", None):
        text += " Built with the House Builder."
    if objects:
        text += " Parts: " + ", ".join(objects[:20]) + "."
    if loose:
        text += f" Plus {len(loose)} loose pieces of geometry."
    try:
        from . import mesh
        tris = mesh.tessellate(model.root, fn=8)
        if tris:
            span = [max(p[i] for t in tris for p in t)
                    - min(p[i] for t in tris for p in t) for i in range(3)]
            text += (f" Overall size {span[0]:.0f} x {span[1]:.0f} x "
                     f"{span[2]:.0f} {getattr(model, 'unit', 'mm')}.")
    except Exception:
        pass
    return text + " (Description generated automatically.)"


def save_design(model, doc_path) -> dict | None:
    """Keep the whole document just saved at *doc_path* in My Library too,
    titled by its file name, in the area its name and parts point to —
    a design made of Library parts, builders and loose shapes has no
    single Object for the autosave to find. Title, description, area
    and tags edited in the library are kept on later saves; a design
    the user deleted from the library stays deleted."""
    from .document import save_kcad
    if not any(n.type not in ("variables", "assign")
               for n in model.root.children):
        return None
    uid = _design_uid(doc_path)
    if uid in ignored():
        return None
    old, info = _find_uid(uid)
    title = info.get("title") or Path(doc_path).stem
    auto = "generated automatically" in info.get("description", "") \
        or not info.get("description")
    description = describe_design(model, title) if auto else \
        info["description"]
    area = info.get("section") or choose_section(
        "", title, description, info.get("tags", []))
    base = folder() if area == DEFAULT_SECTION else add_section(area)
    path = base / f"{_safe_name(title)}.kcad"
    save_kcad(model, str(path))
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    data["library"] = {
        "title": title, "description": description,
        "tags": info.get("tags", []), "source": "design", "uid": uid,
        "document": str(doc_path),
        "created": datetime.datetime.now().isoformat(timespec="seconds")}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)
    if old is not None and Path(old) != path and Path(old).exists():
        Path(old).unlink()
    return {"title": title, "path": str(path), "section": area,
            "part_id": part_id(read_info(path)), "uid": uid}
