"""A placed part's own finish: colour and material (texture) overrides
kept in its dims as ``dims["_finish"]`` — a list of
``{"part": "Top" | None, "color": "#rrggbb", "material": "Wood"}``,
applied in order after the part is built (`library.build_part`), so a
later entry wins.

*part* picks components by name, case-insensitively and by substring:
"cushion" is every Seat cushion and Back cushion, "leg" every Leg;
none (or "") is the whole part. Only ``color`` nodes carry a finish,
and every library part paints its components through them.

Qt-free: the House Builder, KherveHouse's tree and the MCP tools share it.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import re

from .model import MATERIALS

KEY = "_finish"
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class FinishError(ValueError):
    pass


def _painted(node):
    """Every color node under *node* (itself included)."""
    return [n for n in node.walk() if n.type == "color"]


def components(node):
    """The part's component names, in build order, each once."""
    out = []
    for n in _painted(node):
        if n.name and n.name not in out:
            out.append(n.name)
    return out


def _matches(name, part):
    return not part or part.strip().lower() in (name or "").lower()


def check(entry):
    """*entry* cleaned ({part?, color?, material?}), or FinishError."""
    if not isinstance(entry, dict):
        raise FinishError("A finish is {part?, color?, material?}.")
    out = {}
    part = str(entry.get("part") or "").strip()
    if part:
        out["part"] = part
    color = str(entry.get("color") or "").strip()
    if color:
        if not _HEX.match(color):
            raise FinishError(f"Colour {color!r}: give #rrggbb.")
        out["color"] = color.lower()
    material = str(entry.get("material") or "").strip()
    if material:
        match = [m for m in MATERIALS if m.lower() == material.lower()]
        if not match:
            raise FinishError(f"No material {material!r}. Materials: "
                              f"{', '.join(MATERIALS)}.")
        out["material"] = match[0]
    if "color" not in out and "material" not in out:
        raise FinishError("A finish needs a colour, a material or both.")
    return out


def apply(node, finishes):
    """Paint *node*'s components by *finishes* (in place); *node*."""
    for entry in finishes or []:
        if not isinstance(entry, dict):
            continue
        for n in _painted(node):
            if _matches(n.name, entry.get("part")):
                if entry.get("color"):
                    n.params["color"] = entry["color"]
                if entry.get("material"):
                    n.params["material"] = entry["material"]
    return node


def add(dims, entry):
    """*dims* with *entry* appended to its finishes (a new dict). An
    entry for the same component replaces the earlier colour/material
    it sets, so the list does not grow on every tweak."""
    entry = check(entry)
    out = dict(dims or {})
    kept = []
    for old in out.get(KEY) or []:
        if (old.get("part") or "").lower() == \
                (entry.get("part") or "").lower():
            old = {k: v for k, v in old.items()
                   if k == "part" or k not in entry}
            if set(old) <= {"part"}:
                continue
        kept.append(old)
    out[KEY] = kept + [entry]
    return out


def clear(dims):
    out = dict(dims or {})
    out.pop(KEY, None)
    return out
