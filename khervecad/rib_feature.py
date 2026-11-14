"""SolidWorks' **Rib** (2026-11-14, the user's Exercise 6 video, "Rib
Tool": a cradle and a pillow block, each braced by one).

A rib is ONE open sketch line (or a few) on a plane through the part:
the area it closes with the part's outline on that plane is filled and
given a thickness about the plane — SolidWorks' Rib with "both sides"
and the extrusion parallel to the sketch. It is built from what Extruded
Boss already uses: the part's section on the sketch plane
(`sketch_section.with_section`) splits the plane into areas with the
line (`sketch_regions.faces`); the areas the line borders that lie
OUTSIDE the part are the rib. They become a Regions node (seeds, so a
moved line or a resized part re-finds the area) under a Linear extrude,
centred, `height` = thickness, named "Rib n", `params["rib"]` marking
it. Plain OpenSCAD: a centred linear_extrude of the area.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

KEY = "rib"
THICKNESS = 10.0
#: how far beside a line its two sides are probed (mm): beyond the
#: line's own drawn width, well inside any real area
PROBE = 0.25


def is_rib(node):
    return node is not None and node.type == "linear_extrude" and \
        isinstance(node.params.get(KEY), dict)


def _lines(group):
    from . import sketch_regions
    return [s for s in sketch_regions.shapes_of(group)
            if s.type == "line" and s.params.get("modifier") != "%"]


def _probes(line):
    """Points just either side of *line*, along its length."""
    p = line.params
    try:
        x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
    except (KeyError, TypeError, ValueError):
        return []
    dx, dy = x2 - x1, y2 - y1
    n = math.hypot(dx, dy)
    if n < 1e-9:
        return []
    nx, ny = -dy / n, dx / n
    off = PROBE + float(p.get("width", 0) or 0) / 2
    out = []
    for t in (0.25, 0.5, 0.75):
        mx, my = x1 + dx * t, y1 + dy * t
        out.append((mx + nx * off, my + ny * off))
        out.append((mx - nx * off, my - ny * off))
    return out


def rib_faces(face_list, lines, ghost):
    """Indices of the areas *lines* border that lie outside the part
    (not inside the section polygon *ghost*)."""
    from . import sketch_regions
    picked = set()
    for line in lines:
        for pt in _probes(line):
            i = sketch_regions.face_at(face_list, pt)
            if i is None:
                continue
            inside = face_list[i][2] if len(face_list[i]) > 2 else []
            if ghost is not None and any(s is ghost for s in inside):
                continue
            picked.add(i)
    return sorted(picked)


def _next_name(model):
    used = {n.name for n in model.root.walk()}
    k = 1
    while "Rib%d" % k in used:
        k += 1
    return "Rib%d" % k


def make(window, group, thickness=THICKNESS):
    """The rib the open lines of the sketch *group* make with the part:
    a centred Linear extrude of a Regions, or None when the lines close
    no area against the part."""
    from . import sketch_regions, sketch_section
    lines = _lines(group)
    if not lines:
        return None
    try:
        shapes, ghost = sketch_section.with_section(
            window, group, sketch_regions.shapes_of(group))
        face_list = sketch_regions.faces(shapes)
    except Exception:                         # no Manifold, odd shapes
        return None
    if ghost is None:
        return None                           # the plane misses the part
    picked = rib_faces(face_list, lines, ghost)
    if not picked:
        return None
    model = window.model
    real = sketch_section.keep(model, group, ghost)
    hide = [real if s is ghost else s for s in shapes]
    reg = sketch_regions.make(model, group, face_list, picked, hide=hide)
    if reg is None:
        return None
    reg.params["fuse"] = True        # pushed into the part, as a boss's
    ext = model.wrap_nodes([reg], "linear_extrude")
    if ext is None:
        return None
    ext.params.update(height=float(thickness), center=True)
    ext.params[KEY] = {"thickness": float(thickness)}
    ext.name = _next_name(model)
    model.node_changed.emit(reg)
    model.node_changed.emit(ext)
    return ext


def run_mcp(window, args):
    """MCP `rib`: node_id = the sketch (a plane / face sketch Group, or
    any container) holding the line(s); thickness (default 10)."""
    node = window.model.find(int(args.get("node_id", -1))) \
        if hasattr(window.model, "find") else None
    if node is None:
        node = next((n for n in window.model.root.walk()
                     if n.id == args.get("node_id")), None)
    if node is None:
        return {"error": "no node with id %r" % args.get("node_id")}
    if not _lines(node):
        return {"error": "the sketch holds no line: draw the rib's line "
                         "(open, from the part to the part) first"}
    rib = make(window, node, float(args.get("thickness", THICKNESS)))
    if rib is None:
        return {"error": "the line closes no area against the part on "
                         "this plane — make it start and end on the "
                         "part's edges"}
    return {"rib_id": rib.id, "name": rib.name,
            "thickness": rib.params["height"]}


TIP = ("Rib",
       "A thin brace between a wall and a base, from ONE open line: the "
       "area the line closes with the part on its plane, given a "
       "thickness about that plane (SolidWorks' Rib).",
       ["Click Rib (or select a sketch holding the line, then Rib).",
        "Click a plane through the part — Front, Top or Right in 3D — or "
        "a face.",
        "Draw one Line from a point on the part's edge to another (e.g. "
        "from the top of a wall down to the far edge of the base); "
        "dimension it if you like.",
        "Leave the sketch: the rib fills the triangle the line closes, "
        "10 mm thick, centred on the plane.",
        "Change Thickness (height) in Properties; Mirror it to the other "
        "side with Mirror."],
       "The line must START and END on the part: it closes the area with "
       "the part's edges on that plane.")


def start(window):
    """The Rib button: a selected sketch with a line makes the rib at
    once; else the Boss / Cut toggles, with the planes on, and one click
    on a plane or face opens the rib's sketch."""
    try:
        nodes = window.builder.active_tree().selected_nodes()
    except Exception:
        nodes = []
    from . import face_sketch
    for n in nodes:
        group = face_sketch.group_of(n) or (n if n.children else None)
        if group is not None and _lines(group):
            rib = make(window, group)
            if rib is not None:
                window.builder.active_tree().select_nodes([rib])
                window.statusBar().showMessage(
                    "%s made from %s." % (rib.name, group.name), 6000)
                return rib
    from . import feature_pick
    feature_pick.start(window, "rib")
    return None


def action(window):
    act = getattr(window, "_rib_act", None)
    if act is not None:
        return act
    from PyQt5.QtWidgets import QAction
    from . import icons, language, toolbars, tooltips
    tooltips.TIPS.setdefault("rib", TIP)
    glyph = "mdi.triangle-outline"
    act = QAction(icons.icon(glyph), language.tr("Rib"), window)
    act.setData("rib")
    toolbars.remember_glyph(act, glyph, "finish")
    tooltips.apply(act, "rib")
    act.triggered.connect(lambda _=False: start(window))
    window._rib_act = act
    return act
