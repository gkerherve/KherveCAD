"""OpenSCAD's Customizer annotations on variables — the comments that
turn a program's top variables into sliders, drop-downs and tabs (on
Thingiverse, Printables' customizers, OpenSCAD's own Customizer pane):

    /* [Size] */
    // Box width in mm
    width = 40;      // [10:5:200]
    lid = "snap";    // [snap, screw, none]
    wall = 2;        // [1.2:Thin, 2:Normal, 3:Strong]
    label = "Box";   // 12
    /* [Hidden] */
    $fn = 64;

An assign node keeps them as params — ``options`` (what is inside the
brackets, or a bare number for a text's length), ``description`` (the
comment line above) and ``group`` (the last ``/* [Tab] */``) — shown and
edited in Properties, turned into a control in the Variables sheet
(`widget`), written back by codegen (`lines_before`, `trailing`) and read
by scadparse (`annotate`), so a customizable program survives the round
trip and its controls work here.

Qt-free.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import bisect
import re

#: the group whose variables the Customizer does not show
HIDDEN = "Hidden"

#: schema rows the assign node gains (see model.NODE_TYPES["assign"])
SCHEMA = [
    ("options", "Customizer: [range] or [choices]", "str", None, None),
    ("description", "Customizer: description", "str", None, None),
    ("group", "Customizer: tab / group", "str", None, None),
]

_GROUP = re.compile(r"^/\*\s*\[([^\]]*)\]\s*\*/$", re.S)
_BRACKETS = re.compile(r"^\[(.*)\]$", re.S)


# ----------------------------------------------------------------- import

def annotate(parser, root):
    """Read the annotations of the program's top-level assignments into
    their nodes (after the parse)."""
    text = parser.text
    starts = [0] + [k + 1 for k, c in enumerate(text) if c == "\n"]

    def line_of(offset):
        return bisect.bisect_right(starts, offset) - 1
    groups = []                                   # (offset, name)
    whole_line = {}                               # line -> comment body
    trailing = {}                                 # line -> comment body
    for offset, body in parser.comments:
        match = _GROUP.match(body.strip())
        if match:
            groups.append((offset, match.group(1).strip()))
            continue
        if not body.startswith("//"):
            continue
        line = line_of(offset)
        if text[starts[line]:offset].strip():
            trailing[line] = body[2:].strip()
        else:
            whole_line[line] = body[2:].strip()
    top = {id(c) for c in root.children}
    for offset, end, node in parser._heads:
        if node.type != "assign" or id(node) not in top:
            continue
        last = line_of(end)
        note = trailing.get(last)
        if note is not None:
            options = parse_trailing(note)
            if options is not None:
                node.params["options"] = options
        above = whole_line.get(line_of(offset) - 1)
        if above and not _BRACKETS.match(above) and \
                line_of(offset) - 2 not in whole_line:
            node.params["description"] = above
        group = ""
        for g_offset, name in groups:
            if g_offset < offset:
                group = name
        if group:
            node.params["group"] = group


def parse_trailing(note):
    """The options a trailing comment gives: the inside of ``[...]``, or a
    bare whole number (a text box's maximum length); None otherwise (a
    plain remark)."""
    note = note.strip()
    match = _BRACKETS.match(note)
    if match:
        return match.group(1).strip()
    if re.fullmatch(r"\d+", note):
        return note
    return None


# ---------------------------------------------------------------- codegen

def group_of(node):
    return str(node.params.get("group") or "").strip()


def _previous_assign(node):
    parent = node.parent
    if parent is None:
        return None
    siblings = parent.children
    for sibling in reversed(siblings[:siblings.index(node)]):
        if sibling.type == "assign":
            return sibling
        if sibling.type != "variables":
            return None
    if parent.type == "variables" and parent.parent is not None:
        return _previous_assign(parent)
    return None


def lines_before(node):
    """The comment lines written above an assignment: a ``/* [Group] */``
    where the group changes, then its description."""
    out = []
    group = group_of(node)
    before = _previous_assign(node)
    if group and (before is None or group_of(before) != group):
        out.append(f"/* [{group}] */")
    description = str(node.params.get("description") or "").strip()
    if description:
        out.append("// " + " ".join(description.split()))
    return out


def trailing(node):
    """The trailing comment (``  // [0:10]``), or ""."""
    options = str(node.params.get("options") or "").strip()
    if not options:
        return ""
    if re.fullmatch(r"\d+", options):
        return f"  // {options}"
    return f"  // [{options}]"


# --------------------------------------------------------------- controls

def _number(text):
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    return int(value) if value == int(value) else value


def widget(node):
    """What control the variable gets:

    - ``{"kind": "slider", "min", "max", "step"}`` for ``[a:b]``,
      ``[a:s:b]`` or ``[max]``;
    - ``{"kind": "dropdown", "items": [(value source, label)]}`` for a
      list, labelled ``[10:Small, 20:Large]`` or not;
    - ``{"kind": "checkbox"}`` for a true / false value;
    - ``{"kind": "text", "max": n}`` for a string (with ``// n``);
    - None when it is a plain expression.
    """
    options = str(node.params.get("options") or "").strip()
    value = node.params.get("value")
    source = str(value).strip() if value is not None else ""
    is_string = source.startswith('"') and source.endswith('"')
    if re.fullmatch(r"\d+", options) and is_string:
        return {"kind": "text", "max": int(options)}
    if options:
        parts = [p.strip() for p in options.split(":")]
        numbers = [_number(p) for p in parts]
        if "," not in options and all(n is not None for n in numbers):
            if len(numbers) == 1:
                return {"kind": "slider", "min": 0, "max": numbers[0],
                        "step": 1}
            if len(numbers) == 2:
                return {"kind": "slider", "min": numbers[0],
                        "max": numbers[1], "step": 1}
            if len(numbers) == 3:
                return {"kind": "slider", "min": numbers[0],
                        "max": numbers[2], "step": numbers[1]}
        items = []
        from .scadlang import split_args
        for chunk in split_args(options):
            if ":" in chunk and not chunk.startswith('"'):
                raw, label = chunk.split(":", 1)
            else:
                raw, label = chunk, chunk
            raw, label = raw.strip(), label.strip().strip('"')
            if is_string and not raw.startswith('"'):
                raw = f'"{raw}"'
            items.append((raw, label))
        if items:
            return {"kind": "dropdown", "items": items}
    if source in ("true", "false") or isinstance(value, bool):
        return {"kind": "checkbox"}
    if is_string:
        return {"kind": "text", "max": 0}
    return None


def hidden(node):
    return group_of(node).lower() == HIDDEN.lower()
