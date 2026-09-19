"""Collections — Blender's outliner collections for KherveCAD (Qt-free).

A collection is a named set of parts that is shown or hidden, and locked
or unlocked, as one — "Walls", "Roof", "Furniture" in a house, "Moving
parts" in a mechanism — whatever the tree's own structure. The tree is
how a model is BUILT; collections are how it is LOOKED AT.

- The collections themselves are `DocumentModel.collections`, a list of
  ``{"name", "visible", "locked"}`` in display order — saved in the .kcad
  (FORMAT_VERSION 13) and in the undo snapshots.
- Membership is on the part: ``params["collection"] = name``. A part
  belongs to at most one collection (Blender allows several; one is
  what a user can reason about in a CAD tree), and everything under it
  belongs with it. A node outside every collection is always shown.
- **Hidden is a view setting, like Blender's eye**: the 3D and 2D views
  and the exact OpenSCAD render leave the members out (`hiding`), but
  the program, the Code tab and every export keep them — the part is
  still in the design. A node's own visibility (`visible`, OpenSCAD's
  `*`) is untouched.
- **Locked** (Blender's "disable selection"): the members cannot be
  picked or dragged in the 2D view; the tree still selects them.

Every change emits `structure_changed`, so it is one undo step and the
views redraw.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from contextlib import contextmanager

KEY = "collection"
DEFAULT_NAME = "Collection"


class CollectionError(ValueError):
    pass


# ------------------------------------------------------------- reading
def names(model) -> list:
    return [c["name"] for c in model.collections]


def get(model, name):
    for c in model.collections:
        if c["name"] == name:
            return c
    return None


def own(node):
    """The collection *node* itself is put in ("" for none)."""
    return str((node.params or {}).get(KEY, "") or "")


def of(node) -> str:
    """The collection *node* belongs to — its own, else the nearest
    ancestor's ("" for none)."""
    while node is not None:
        name = own(node)
        if name:
            return name
        node = node.parent
    return ""


def members(model, name) -> list:
    """The nodes put in *name*, in document order (outermost only: a
    member's descendants belong through it)."""
    out = []

    def walk(node):
        for child in node.children:
            if own(child) == name:
                out.append(child)
            else:
                walk(child)
    walk(model.root)
    return out


def _flag_set(model, key, value):
    return {c["name"] for c in model.collections
            if bool(c.get(key, key == "visible")) == value}


def hidden_names(model) -> set:
    return _flag_set(model, "visible", False)


def locked_names(model) -> set:
    return _flag_set(model, "locked", True)


def is_hidden(model, node) -> bool:
    hidden = hidden_names(model)          # empty: no walk (every tree row
    return bool(hidden) and of(node) in hidden      # asks this)


def is_locked(model, node) -> bool:
    locked = locked_names(model)
    return bool(locked) and of(node) in locked


def summary(model) -> list:
    """What an assistant or a test reads: every collection with its
    flags and the names and ids of its members."""
    return [{"name": c["name"], "visible": bool(c.get("visible", True)),
             "locked": bool(c.get("locked", False)),
             "members": [{"id": n.id, "name": n.name}
                         for n in members(model, c["name"])]}
            for c in model.collections]


# ------------------------------------------------------------- editing
def _changed(model):
    model.structure_changed.emit()


def unique_name(model, base=DEFAULT_NAME) -> str:
    taken = set(names(model))
    base = (base or DEFAULT_NAME).strip() or DEFAULT_NAME
    if base not in taken:
        return base
    i = 2
    while f"{base} {i}" in taken:
        i += 1
    return f"{base} {i}"


def create(model, name: str = "", nodes=()) -> str:
    """A new collection (a unique name from *name*), optionally holding
    *nodes*. Returns its name."""
    name = unique_name(model, name)
    model.collections.append({"name": name, "visible": True,
                              "locked": False})
    for node in nodes:
        _put(node, name)
    _changed(model)
    return name


def rename(model, old: str, new: str) -> str:
    c = get(model, old)
    if c is None:
        raise CollectionError(f"No collection '{old}'.")
    new = (new or "").strip()
    if not new or new == old:
        return old
    if get(model, new) is not None:
        raise CollectionError(f"A collection '{new}' already exists.")
    c["name"] = new
    for node in model.root.walk():
        if own(node) == old:
            node.params[KEY] = new
    _changed(model)
    return new


def remove(model, name: str):
    """Delete the collection; its parts stay in the document, in no
    collection (Blender's "Delete" of a collection keeps the objects
    in the parent collection)."""
    c = get(model, name)
    if c is None:
        raise CollectionError(f"No collection '{name}'.")
    model.collections.remove(c)
    for node in model.root.walk():
        if own(node) == name:
            node.params.pop(KEY, None)
    _changed(model)


def move(model, name: str, index: int):
    c = get(model, name)
    if c is None:
        raise CollectionError(f"No collection '{name}'.")
    model.collections.remove(c)
    index = max(0, min(int(index), len(model.collections)))
    model.collections.insert(index, c)
    _changed(model)


def _put(node, name):
    if name:
        node.params[KEY] = name
    else:
        node.params.pop(KEY, None)
    # one collection per part: what is inside follows it
    for inner in list(node.walk())[1:]:
        inner.params.pop(KEY, None)


def assign(model, nodes, name) -> int:
    """Put *nodes* in collection *name* (created if new); "" or None
    takes them out of any. Returns how many moved."""
    name = (name or "").strip()
    if name and get(model, name) is None:
        model.collections.append({"name": name, "visible": True,
                                  "locked": False})
    count = 0
    for node in nodes:
        if node is None or node.parent is None:
            continue
        _put(node, name)
        count += 1
    _changed(model)
    return count


def set_flag(model, name: str, key: str, value: bool):
    c = get(model, name)
    if c is None:
        raise CollectionError(f"No collection '{name}'.")
    c[key] = bool(value)
    _changed(model)


def set_visible(model, name, visible=True):
    set_flag(model, name, "visible", visible)


def set_locked(model, name, locked=True):
    set_flag(model, name, "locked", locked)


def solo(model, name: str):
    """Show *name* alone (Ctrl+click on Blender's eye) — or, when it
    already is, show everything again."""
    if get(model, name) is None:
        raise CollectionError(f"No collection '{name}'.")
    alone = all(bool(c.get("visible", True)) == (c["name"] == name)
                for c in model.collections)
    for c in model.collections:
        c["visible"] = True if alone else c["name"] == name
    _changed(model)


def forget_missing(model):
    """Drop membership that names no collection (a part pasted from
    another document); keeps the part visible."""
    known = set(names(model))
    for node in model.root.walk():
        if own(node) and own(node) not in known:
            node.params.pop(KEY, None)


# ----------------------------------------------------------- the views
@contextmanager
def hiding(model):
    """While inside, every member of a hidden collection reads as hidden
    (``visible = False``), so tessellation, the 2D view and the exact
    render leave it out. Restored on the way out, whatever happens —
    the document itself never changes."""
    hidden = hidden_names(model)
    turned = []
    if hidden:
        for node in model.root.walk():
            if node.visible and own(node) in hidden:
                node.visible = False
                turned.append(node)
    try:
        yield bool(turned)
    finally:
        for node in turned:
            node.visible = True
