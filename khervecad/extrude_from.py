"""SolidWorks' extrude **From: Offset** (2026-11-14, Exercise 55, the
control bracket: Cut-Extrude1 starts 8 mm off the Front plane and runs Up
To Surface, Cut-Extrude2 starts 13 mm off it the other way, Through All).

The start is a Move (`translate`) round the extrude — round its Reverse
mirror when it has one — marked ``params[KEY]`` = the offset in mm along
the extrude's own direction (negative = against it). It is plumbing, not a
feature (feature_list.is_plumbing), so History shows the extrude alone;
the end conditions (extent.py) measure through it like any ancestor, so
Up To Surface is what is left between the offset and the surface. Plain
OpenSCAD: `translate([0, 0, d]) linear_extrude(...)`; a .scad round trip
keeps the move, not the label.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

KEY = "extrude_from"
CHOICES = [("sketch", "Sketch Plane"), ("offset", "Offset")]
DEFAULT = 5.0


def _top(ext):
    """The extrude, or the Reverse mirror round it."""
    from . import drag_feature
    return drag_feature.reversed_of(ext) or ext


def holder_of(ext):
    top = _top(ext)
    p = top.parent
    if p is not None and p.type == "translate" and len(p.children) == 1 \
            and p.params.get(KEY) is not None:
        return p
    return None


def offset_of(ext):
    h = holder_of(ext)
    if h is None:
        return 0.0
    try:
        return float(h.params.get(KEY) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def mode_of(ext):
    return "offset" if holder_of(ext) is not None else "sketch"


def _sign(ext):
    from . import drag_feature
    down = drag_feature.reversed_of(ext) is not None or \
        bool(ext.params.get("reverse"))
    return -1.0 if down else 1.0


def set_offset(model, ext, distance):
    """Start *ext* *distance* mm along its direction (None = from the
    sketch plane again). Returns the holder or None."""
    holder = holder_of(ext)
    if distance is None:
        if holder is not None:
            model.ungroup(holder)
        return None
    d = float(distance)
    if holder is None:
        holder = model.wrap_nodes([_top(ext)], "translate")
        if holder is None:
            return None
        model.rename(holder, "From offset")
    holder.params[KEY] = d
    for k in ("x", "y"):
        holder.params[k] = 0.0
    model.set_param(holder, "z", round(_sign(ext) * d, 6))
    return holder


def follow(model, ext):
    """After Reverse: the start goes the extrude's new way."""
    holder = holder_of(ext)
    if holder is not None:
        set_offset(model, ext, offset_of(ext))
