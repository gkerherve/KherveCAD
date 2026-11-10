"""The rest of SolidWorks' Smart Dimension (2026-11-10, the user: "add,
for the smart dimension, everything that SolidWorks has").

What two picks mean can depend on WHERE THE NUMBER IS PLACED, so some
dimensions now wait for one more click:

- **two points not level with each other** — placed above or below the
  pair: the HORIZONTAL distance; left or right of it: the VERTICAL one;
  between them (or off a corner): the straight (aligned) distance;
- **the two ends of one arc** — the placing click ON the arc: its ARC
  LENGTH (else as any two points);
- **a point or line and a CENTERLINE** — placed on the far side of the
  centerline: the DOUBLED distance, a diameter (Ø), as a revolve's
  profile is dimensioned.

`needs_place` says when to wait, `refine` turns the placing point into
the kind and its options. Dimensions whose picks leave no choice are
made at the second click as before.

Also here: what a dimension's value reads (`text`: Ø for a doubled one,
brackets for a DRIVEN one), and the near / far side of a circle
(`rim_for`, Shift+click on a circle: SolidWorks' min / max arc
condition).

Qt-free. Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from . import sketch_constraints as sc

#: two points this near level (mm) leave no horizontal / vertical choice
LEVEL = 1e-6
#: a placing click this near the arc (as a fraction of its chord, at
#: least `ARC_MM`) means the arc itself
ARC_NEAR = 0.08
ARC_MM = 0.5


def is_centerline(node):
    """A construction LINE the user drew (not a reference copied from
    the model or another sketch)."""
    p = node.params
    return node.type == "line" and p.get("modifier") == "%" and \
        not (p.get("ref_source") or p.get("ref_world") or p.get("ref_face")) \
        and not str(node.name).startswith("Reference")


def _same_arc(chosen):
    (a, an, _), (b, bn, _) = chosen
    if a is b and a.type == "line" and {an, bn} == {"p1", "p2"}:
        try:
            if abs(float(a.params.get("bulge") or 0.0)) > 1e-9:
                return a
        except (TypeError, ValueError):
            return None
    return None


def needs_place(made):
    """Does (kind, chosen) from the picks wait for the placing click?"""
    if made is None:
        return False
    kind, chosen = made
    try:
        if kind == "distance":
            if _same_arc(chosen) is not None:
                return True
            pa = sc._point(chosen[0][0], chosen[0][1], {})
            pb = sc._point(chosen[1][0], chosen[1][1], {})
            return abs(pa[0] - pb[0]) > LEVEL and abs(pa[1] - pb[1]) > LEVEL
        if kind == "point_line":
            return is_centerline(chosen[1][0])
    except (KeyError, ValueError, IndexError, TypeError):
        return False
    return False


def _arc_distance(node, at):
    """How far *at* is from the arc of line *node*."""
    from . import sketch_arc
    p = node.params
    run = sketch_arc.points(float(p["x1"]), float(p["y1"]), float(p["x2"]),
                            float(p["y2"]), sketch_arc.bulge_of(p))
    return min(math.dist(at, q) for q in run)


def refine(made, at):
    """(kind, chosen, extra) for (kind, chosen) placed at *at* (x, y in
    the sketch)."""
    kind, chosen = made
    extra = {}
    if at is None:
        return kind, chosen, extra
    if kind == "distance":
        arc = _same_arc(chosen)
        pa = sc._point(chosen[0][0], chosen[0][1], {})
        pb = sc._point(chosen[1][0], chosen[1][1], {})
        if arc is not None:
            reach = max(ARC_MM, ARC_NEAR * math.dist(pa, pb))
            if _arc_distance(arc, at) <= reach:
                return "arc_length", [(arc, "l", "line")], extra
        if abs(pa[0] - pb[0]) > LEVEL and abs(pa[1] - pb[1]) > LEVEL:
            in_x = min(pa[0], pb[0]) <= at[0] <= max(pa[0], pb[0])
            in_y = min(pa[1], pb[1]) <= at[1] <= max(pa[1], pb[1])
            if in_x and not in_y:
                return "hdistance", chosen, extra
            if in_y and not in_x:
                return "vdistance", chosen, extra
        return kind, chosen, extra
    if kind == "point_line" and is_centerline(chosen[1][0]):
        p = sc._point(chosen[0][0], chosen[0][1], {})
        line = sc._line(chosen[1][0], chosen[1][1], {})
        side_p = sc._pl_dist(p, line)
        side_at = sc._pl_dist(at, line)
        if abs(side_p) > LEVEL and side_p * side_at < 0:
            extra["double"] = True         # across the centerline: Ø
    return kind, chosen, extra


def place_prompt(made):
    kind, chosen = made
    if kind == "point_line":
        return ("click where the number goes — beyond the centerline for "
                "a diameter (Ø), on the point's side for the distance.")
    if _same_arc(chosen) is not None:
        return ("click where the number goes — ON the arc for its arc "
                "length, else above / below for horizontal, left / right "
                "for vertical.")
    return ("click where the number goes — above or below the two points "
            "for the horizontal distance, left or right for the vertical, "
            "between them for the straight one.")


def rim_for(chosen, clicks):
    """{ref index: "min" | "max"} for a dimension between *chosen* (two
    picks) where a circle was Shift+clicked: *clicks* {id(circle node):
    (x, y) clicked, in the sketch}. Clicked on the side facing the other
    pick it is the circle's NEAR side (min), else its FAR side (max)."""
    out = {}
    if len(chosen) != 2:
        return out
    for i, pick in enumerate(chosen):
        at = clicks.get(id(pick[0]))
        if at is None or pick[0].type != "circle":
            continue
        other = chosen[1 - i]
        try:
            c = sc._point(pick[0], "c", {})
            if other[2] == "line":
                a, b = sc._line(other[0], other[1], {})
                dx, dy = b[0] - a[0], b[1] - a[1]
                t = ((c[0] - a[0]) * dx + (c[1] - a[1]) * dy) / \
                    (dx * dx + dy * dy or 1.0)
                o = (a[0] + dx * t, a[1] + dy * t)
            else:
                o = sc._point(other[0], "c" if other[0].type == "circle"
                              else other[1], {})
        except (KeyError, ValueError, IndexError, TypeError):
            continue
        toward = (o[0] - c[0], o[1] - c[1])
        click = (at[0] - c[0], at[1] - c[1])
        out[str(i)] = "min" if toward[0] * click[0] + \
            toward[1] * click[1] >= 0 else "max"
    return out


def add(model, container, kind, refs, value, extra=None):
    """Add the dimension; one the sketch cannot take as DRIVING (it is
    already fully defined) is added DRIVEN instead, as SolidWorks offers.
    Returns (report, scaled, driven)."""
    try:
        report, scaled = sc.add_dimension(model, container, kind, refs,
                                          value, extra=extra)
        return report, scaled, False
    except sc.Conflict:
        report = sc.add(model, container, kind, refs, None,
                        extra=dict(extra or {}, driven=True))
        return report, False, True


def text(row):
    """What a dimension's value reads: R / Ø, the unit sign of an angle,
    brackets when it is driven."""
    unit = "°" if row["kind"] == "angle" else ""
    prefix = {"radius": "R", "diameter": "Ø"}.get(row["kind"], "")
    if row.get("double"):
        prefix = "Ø"
    value = row.get("value")
    if isinstance(value, (int, float)):
        from . import units
        value = units.number(value)
    out = "%s%s%s" % (prefix, value, unit)
    return "(%s)" % out if row.get("driven") else out
