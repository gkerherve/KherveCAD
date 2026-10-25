"""A straight SLOT as the user sees it (2026-10-25, the user: "why is a
slot called a line? we need to change its radius, its width, its
length"). Stored as OpenSCAD's own thick `line` (hull of two circles:
what the sketch constraints, cuts and the importer already know), but
shown as a slot: named "Slot n", its own icon, and in Properties its
centre-to-centre Length, end Radius, Width, Angle and centre X / Y —
`read` works them out, `write` turns one typed value back into the
line's ends and width.

`params["slot"]` marks it (set by the Slot tool); a line named "Slot…"
counts too, so a slot re-imported from OpenSCAD code stays one.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

#: (key, label) of the slot's own fields in Properties
FIELDS = [("length", "Length (centre to centre)"), ("radius", "Radius"),
          ("width", "Width"), ("angle", "Angle (°)"),
          ("cx", "Centre X"), ("cy", "Centre Y")]
ICON = "mdi.pill"


def is_slot(node):
    return node is not None and node.type == "line" and (
        bool(node.params.get("slot"))
        or str(node.name or "").startswith("Slot"))


def _num(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def read(node):
    p = node.params
    x1, y1 = _num(p.get("x1")), _num(p.get("y1"))
    x2, y2 = _num(p.get("x2")), _num(p.get("y2"))
    w = _num(p.get("width"), 1.0)
    return dict(length=round(math.hypot(x2 - x1, y2 - y1), 6),
                radius=round(w / 2.0, 6), width=round(w, 6),
                angle=round(math.degrees(math.atan2(y2 - y1, x2 - x1)), 6),
                cx=round((x1 + x2) / 2.0, 6), cy=round((y1 + y2) / 2.0, 6))


def geometry(length, width, angle, cx, cy):
    """The line params of a slot."""
    a = math.radians(angle)
    hx, hy = math.cos(a) * length / 2.0, math.sin(a) * length / 2.0
    return dict(x1=round(cx - hx, 6), y1=round(cy - hy, 6),
                x2=round(cx + hx, 6), y2=round(cy + hy, 6),
                width=round(width, 6))


def _driving(node, key):
    """(container, row index) of the Smart Dimension that drives *key*
    of this slot (its length, or its end radius for radius / width)."""
    from . import sketch_constraints as sc
    cont = node.parent
    if cont is None:
        return None
    try:
        me = str(cont.children.index(node))
    except ValueError:
        return None
    want = {"length": ("length", ("l",)),
            "radius": ("radius", ("a1", "a2")),
            "width": ("radius", ("a1", "a2"))}.get(key)
    if want is None:
        return None
    for i, row in enumerate(sc.rows(cont)):
        refs = row.get("refs") or []
        if row.get("kind") == want[0] and len(refs) == 1:
            idx, _, name = refs[0].partition(".")
            if idx == me and name in want[1]:
                return cont, i
    return None


def write(model, node, key, value):
    """Set one of the slot's fields; the rest stay. A field a Smart
    Dimension drives is changed THROUGH that dimension (else the solver
    would put the old value back at once)."""
    s = read(node)
    value = _num(value, s.get(key, 0.0))
    drive = _driving(node, key)
    if drive is not None:
        from . import sketch_constraints as sc
        sc.set_value(model, drive[0], drive[1],
                     value / 2.0 if key == "width" else value)
        return
    if key == "radius":
        s["width"] = 2.0 * value
    elif key in s:
        s[key] = value
    s["length"] = max(s["length"], 0.0)
    s["width"] = max(s["width"], 1e-4)
    node.params.update(geometry(s["length"], s["width"], s["angle"],
                                s["cx"], s["cy"]))
    model.node_changed.emit(node)


def mark(model, node):
    """A shape the Slot tool just made: flag and name it."""
    node.params["slot"] = True
    taken = {n.name for n in model.root.walk()}
    i = 1
    while "Slot %d" % i in taken:
        i += 1
    node.name = "Slot %d" % i
