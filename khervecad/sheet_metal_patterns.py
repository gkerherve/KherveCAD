"""Patterns and Mirror of sheet metal features (Qt-free): what the SHEET
METAL tab's Linear Pattern, Circular Pattern and Mirror do (Exercise 135:
Mirror1 of an ear and its hole, CirPattern1 of a tab and its jog,
LPattern1 of a gusset). A feature of a body is one row of one of its
tables (holes, tabs, jogs, gussets, corners, flanges with an ear), so a
pattern writes the copies' rows — the body stays plain parameters and
every copy can be edited or removed on its own.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from . import sheet_body
from . import sheet_metal_ops as ops

#: tables a pattern can copy, with the name shown for a row
KINDS = {"pholes": "Hole", "tabs": "Tab", "tabjogs": "Jog",
         "gussets": "Gusset", "corners": "Corner", "ears": "Ear"}
FAR = 1e5            # a "fixed point" this far out means "not given"


def features(model, node):
    """Every copyable feature of a body: dicts kind, index, label."""
    out = []
    for kind in ("pholes", "tabs", "tabjogs", "gussets", "corners"):
        for i, _row in enumerate(node.params.get(kind) or []):
            out.append(dict(kind=kind, index=i,
                            label=f"{KINDS[kind]} {i + 1}"))
    n = 0
    for i, row in enumerate(node.params.get("flanges") or []):
        if len(row) > 7 and row[7] == 1:
            n += 1
            out.append(dict(kind="ears", index=i, label=f"Ear {n}"))
    return out


def _row(node, kind, index):
    table = "flanges" if kind == "ears" else kind
    rows = [list(r) for r in node.params.get(table) or []]
    if not 0 <= index < len(rows):
        raise ValueError(f"no {kind} {index + 1}")
    return rows[index]


def _rot(p, c, phi):
    s, k = math.sin(phi), math.cos(phi)
    x, y = p[0] - c[0], p[1] - c[1]
    return (c[0] + x * k - y * s, c[1] + x * s + y * k)


def _far(row, i):
    return abs(row[i]) >= FAR or abs(row[i + 1]) >= FAR


def _append(model, node, table, new_rows):
    rows = ops._rows(node, table) + [list(map(_clean, r)) for r in new_rows]
    ops._set(model, node, table, rows)


def _clean(v):
    return round(float(v), 6) if isinstance(v, float) else v


def _copies(kind, row, fn, count):
    """*count* - 1 new rows of kind: fn(row, k) for k = 1 .. count - 1."""
    return [fn(list(row), k) for k in range(1, int(count))]


# ================================================================ linear
def linear(model, node, kind, index, count, dx, dy=0.0):
    """Copies of a feature stepped (dx, dy) in its panel's own frame —
    for a gusset dx is the spacing along its bend, for an ear the step
    along its edge. *count* includes the original. Returns the number of
    rows added."""
    if count < 2:
        raise ValueError("a pattern needs two instances or more")
    row = _row(node, kind, index)
    if kind == "tabs":
        def step(r, k):
            r[1] += dx * k
            r[2] += dy * k
            return r
    elif kind == "pholes":
        def step(r, k):
            r[1] += dx * k
            r[2] += dy * k
            return r
    elif kind == "corners":
        def step(r, k):
            r[1] += dx * k
            r[2] += dy * k
            return r
    elif kind == "tabjogs":
        def step(r, k):
            for i in (1, 3, 8):
                r[i] += dx * k
            for i in (2, 4, 9):
                r[i] += dy * k
            return r
    elif kind == "gussets":
        def step(r, k):
            r[1] += dx * k
            return r
    elif kind == "ears":
        def step(r, k):
            r[5] += dx * k
            r[6] -= dx * k
            return r
    else:
        raise ValueError(f"cannot pattern {kind}")
    new = _copies(kind, row, step, count)
    if kind == "tabjogs":
        for r in new:
            row0 = row
            for i in (8, 9):
                if abs(row0[i]) >= FAR:
                    r[i] = row0[i]
    table = "flanges" if kind == "ears" else kind
    _append(model, node, table, new)
    if kind == "ears":
        _copy_ear_holes(model, node, index, len(new), new, dx)
    return len(new)


def _copy_ear_holes(model, node, index, n, new_rows, dx):
    """Holes sitting on an ear's panel come with each copy."""
    body = ops.built(model, node)
    flanges = [list(r) for r in node.params.get("flanges") or []]
    first = len(flanges) - n
    # panel number of the original ear = base + flanges before it
    orig_panel = 1 + index
    holes = [r for r in ops._rows(node, "pholes") if int(r[0]) == orig_panel]
    rows = []
    for k in range(n):
        panel = 1 + first + k
        for h in holes:
            rows.append([panel, h[1] - dx * (k + 1), h[2], h[3]])
    if rows:
        _append(model, node, "pholes", rows)


# =============================================================== circular
def circular(model, node, kind, index, count, centre=(0.0, 0.0),
             total=360.0):
    """Copies of a tab, jog, hole or corner turned about *centre* (the
    panel's own frame): *count* instances in all spread equally over
    *total* degrees (360 = a full turn, the last never landing on the
    first; less spans it end to end)."""
    if count < 2:
        raise ValueError("a pattern needs two instances or more")
    row = _row(node, kind, index)
    full = abs(total) >= 360 - 1e-9
    step_deg = total / count if full else total / (count - 1)
    c = (float(centre[0]), float(centre[1]))

    def phi(k):
        return math.radians(step_deg * k)
    if kind in ("tabs", "pholes", "corners"):
        def make(r, k):
            r[1], r[2] = _rot((r[1], r[2]), c, phi(k))
            if kind == "tabs":
                r[5] += step_deg * k
            return r
    elif kind == "tabjogs":
        def make(r, k):
            r[1], r[2] = _rot((r[1], r[2]), c, phi(k))
            r[3], r[4] = _rot((r[3], r[4]), c, phi(k))
            if not _far(r, 8):
                r[8], r[9] = _rot((r[8], r[9]), c, phi(k))
            return r
    else:
        raise ValueError(f"a circular pattern turns tabs, jogs, holes and "
                         f"corners — not {kind}")
    new = _copies(kind, row, make, count)
    _append(model, node, kind, new)
    return len(new)


# ================================================================= mirror
def _mirror_pt(p, axis, at):
    q = list(p)
    q[axis] = 2 * at - q[axis]
    return tuple(q)


def mirror(model, node, items, plane="x", at=0.0):
    """Mirror features about the plane perpendicular to X ("x", the
    Right plane when the sheet lies in XY) or Y ("y") at coordinate *at*:
    *items* = [(kind, index), ...]. Holes and ears are found again on
    the mirrored edge / panel of the body; tabs, jogs and corners of the
    base are reflected. Returns the number of rows added."""
    axis = {"x": 0, "y": 1}.get(plane)
    if axis is None:
        raise ValueError("mirror plane: x or y")
    added = 0
    for kind, index in items:
        row = _row(node, kind, index)
        if kind == "tabs":
            r = list(row)
            r[1], r[2] = _mirror_pt((r[1], r[2]), axis, at)
            r[5] = (180.0 - r[5]) if axis == 0 else -r[5]
            _append(model, node, "tabs", [r])
        elif kind == "corners":
            r = list(row)
            r[1], r[2] = _mirror_pt((r[1], r[2]), axis, at)
            _append(model, node, "corners", [r])
        elif kind == "tabjogs":
            r = list(row)
            r[1], r[2] = _mirror_pt((r[1], r[2]), axis, at)
            r[3], r[4] = _mirror_pt((r[3], r[4]), axis, at)
            if not _far(r, 8):
                r[8], r[9] = _mirror_pt((r[8], r[9]), axis, at)
            _append(model, node, "tabjogs", [r])
        elif kind == "pholes":
            _mirror_hole(model, node, row, axis, at)
        elif kind == "ears":
            _mirror_ear(model, node, row, axis, at)
        else:
            raise ValueError(f"cannot mirror {kind}")
        added += 1
    return added


def _mirror_hole(model, node, row, axis, at):
    body = ops.built(model, node)
    panel_i = int(row[0])
    pan = body.panels[panel_i]
    world = pan.frame.at((row[1], row[2]))
    q = _mirror_pt(world, axis, at)
    f = pan.frame
    dv = sheet_body._sub(q, f.o)
    u, v = sheet_body._dot(dv, f.u), sheet_body._dot(dv, f.v)
    if abs(u - row[1]) < 1e-6 and abs(v - row[2]) < 1e-6:
        return                              # on the plane: its own mirror
    _append(model, node, "pholes", [[panel_i, u, v, row[3]]])


def _mirror_ear(model, node, row, axis, at):
    """The ear on the parent's mirrored edge, same width / height /
    angle, its holes mirrored with it."""
    body = ops.built(model, node)
    parent_i, edge = int(row[0]), int(row[1])
    pan = body.panels[parent_i]
    found = pan.edge(edge)
    if found is None:
        raise ValueError(f"panel {parent_i} has no edge {edge}")
    a, b, _ln = found
    ma = _mirror_pt(pan.frame.at(a), axis, at)
    mb = _mirror_pt(pan.frame.at(b), axis, at)
    target = None
    best = None
    mid = tuple((ma[i] + mb[i]) / 2 for i in range(3))
    want = sheet_body._unit(sheet_body._sub(mb, ma))
    for tag in set(pan.tags):
        e2 = pan.edge(tag)
        if e2 is None:
            continue
        pa, pb = pan.frame.at(e2[0]), pan.frame.at(e2[1])
        d2 = sheet_body._unit(sheet_body._sub(pb, pa))
        par = sheet_body._dot(want, d2)
        if abs(par) < 0.99 or e2[2] < 0.5 * _ln:
            continue                    # (a short facet of an arc)
        # how far the mirrored edge's middle lies off this edge's line
        # (the bends on other edges set it back a few mm)
        off = sheet_body._sub(mid, pa)
        along = sheet_body._dot(off, d2)
        lateral = math.sqrt(max(sheet_body._dot(off, off) - along ** 2, 0))
        score = lateral + 0.001 * abs(along)
        if best is None or score < best:
            best, target = score, (tag, par < 0)
    if target is None or best > 12.0:
        raise ValueError("Mirror: the ear's edge has no mirror image on "
                         "this panel")
    tag, reversed_ = target
    lo, hi = row[5], None
    # span from the original edge's own measure
    ear_ln = _trial_length(model, node, row)
    hi = ear_ln - row[6]
    width = hi - lo
    centre = (lo + hi) / 2
    # the hole(s) on the original ear panel
    ear_panel = _ear_panel(body, node, row)
    holes = [h for h in ops._rows(node, "pholes") if int(h[0]) == ear_panel]
    hole_d = holes[0][3] if holes else 0.0
    ops.add_ear(model, node, parent_i, tag, centre, width, row[2], row[3],
                row[4], hole_d, from_end=reversed_)


def _dist(p, q):
    return math.sqrt(sum((p[i] - q[i]) ** 2 for i in range(3)))


def _trial_length(model, node, row):
    """The length of the edge the ear row stands on, as that very bend
    leaves it (its inset A + width + inset B)."""
    body = ops.built(model, node)
    parent = body.panels[int(row[0])]
    found = parent.edge(int(row[1]))
    return found[2]


def _ear_panel(body, node, row):
    """The panel number of the flange row *row*."""
    rows = [list(r) for r in node.params.get("flanges") or []]
    for i, r in enumerate(rows):
        if r == list(row):
            return 1 + i
    return -1
