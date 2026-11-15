"""Revolved Boss/Base on a sketch, as SolidWorks makes it (2026-11-10,
the user: "use a rotate extrude once" — a triangle of lines on the
Front plane came out as three hair-thin rings lying on their side).

Two things a plain ``rotate_extrude`` round the sketch got wrong:

- **the area, not the lines**: loose sketch lines that close an area are
  revolved as that area (a Regions node, as Extruded Boss makes), not
  each as a 0.2 mm band;
- **the axis lies IN the sketch**: OpenSCAD revolves about the Z of the
  frame the profile is in, which for a sketch on a plane or face is its
  normal — out of the paper. The revolve is turned so the axis is the
  sketch's own Y axis through its origin (the Revolved Cut's rule):
  draw the profile to the right of it.

A sketch in the classic layout (2D shapes in the XY plane, no sketch
Group) keeps OpenSCAD's own meaning.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

#: the name the turned revolve carries (the importer keeps the rotate)
AXIS_NAME = "Revolve (about the sketch's Y axis)"


def area_of_lines(model, container):
    """A Regions node of the area *container*'s loose lines close by
    themselves, or None (no lines, or they close nothing)."""
    from . import sketch_regions as sr, slot2d
    shapes = sr.shapes_of(container)
    if not any(s.type == "line" and not slot2d.is_slot(s) for s in shapes):
        return None
    try:
        face_list = sr.faces(shapes)
        keep = sr.solid_faces(shapes, face_list)
    except Exception:                          # no Manifold, odd shapes
        return None
    if not keep:
        return None
    return sr.make(model, container, face_list, keep, hide=shapes)


def axis_of(container, tool):
    """The axis of revolution a sketch names for itself (2026-11-15,
    "Deform Feature": SolidWorks revolves about the CONSTRUCTION LINE
    that is selected by default): ``(px, py, theta)`` = a point on the
    first construction centre line of *container* and its direction in
    degrees, pointing so that the profile *tool* revolves lies on its
    left; None when the sketch has no such line (the sketch's Y axis)."""
    import math
    from . import slot2d, mesh
    # (a Regions takes the sketch's construction shapes in with it)
    line = next((c for c in container.walk() if c.type == "line"
                 and c.params.get("modifier") == "%"
                 and not slot2d.is_slot(c)
                 and not c.params.get("reference")), None)
    if line is None:
        return None
    p = line.params
    try:
        x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
    except (TypeError, ValueError, KeyError):
        return None
    if math.hypot(x2 - x1, y2 - y1) < 1e-9:
        return None
    pts = []
    for kid in tool.children:
        try:
            for loop in mesh.collect_outlines(kid):
                pts.extend(loop)
        except Exception:
            continue
    theta = math.degrees(math.atan2(y2 - y1, x2 - x1))
    if pts:
        dx, dy = x2 - x1, y2 - y1
        side = sum(dx * (q[1] - y1) - dy * (q[0] - x1) for q in pts)
        if side < 0:                     # profile on the right: point back
            theta += 180.0
            x1, y1 = x2, y2
    return x1, y1, theta


def use_axis(model, tool, outer, container):
    """Turn the revolve *tool* (already inside *outer*, the rotate that
    makes its axis the sketch's Y) onto the sketch's construction line,
    when it has one: the profile is carried into the frame where that
    line is the Y axis and the finished solid carried back. Returns the
    outermost node (the tool's chain's top)."""
    ax = axis_of(container, tool)
    if ax is None or outer is None:
        return outer
    px, py, theta = ax
    phi = -90.0 - theta
    kids = list(tool.children)
    inner = kids
    if abs(px) > 1e-9 or abs(py) > 1e-9:
        mv = model.wrap_nodes(kids, "translate")
        mv.params.update(x=-px, y=-py, z=0.0)
        inner = [mv]
    spin = model.wrap_nodes(inner, "rotate")
    spin.params.update(x=0.0, y=0.0, z=phi)
    spin.name = "To the axis frame"
    back = model.wrap_nodes([outer], "rotate")
    back.params.update(x=0.0, y=0.0, z=-phi)
    back.name = "Revolve about the construction line"
    top = back
    if abs(px) > 1e-9 or abs(py) > 1e-9:
        top = model.wrap_nodes([back], "translate")
        top.params.update(x=px, y=py, z=0.0)
        top.name = "Revolve about the construction line (placed)"
    model.node_changed.emit(top)
    return top


def revolve(window, nodes):
    """Revolved Boss on the sketch content *nodes* (what
    sketch_regions.extrude_targets gave). The rotate_extrude, or None
    when this is not a sketch on a plane or face (the caller wraps the
    plain way)."""
    from . import face_sketch
    from .model import SHAPE_2D
    flat = [n for n in nodes if n.category == SHAPE_2D
            or n.type == "regions"]
    if not flat or len(flat) != len(nodes):
        return None
    container = flat[0].parent
    if container is None or any(n.parent is not container for n in flat):
        return None
    if face_sketch.group_of(container) is None:
        # a shape drawn straight on the Top plane (no sketch group): in
        # the SolidWorks / Fusion styles it is a sketch like any other —
        # revolved about its Y axis, lying in its plane (2026-11-12, the
        # user: OpenSCAD's own rotate_extrude stood the rectangle up and
        # spun it about Z). The classic style keeps OpenSCAD's meaning.
        from . import toolbar_style
        if toolbar_style.current(window) == toolbar_style.CLASSIC:
            return None
    model = window.model
    reg = area_of_lines(model, container)
    targets = [reg] if reg is not None else [
        n for n in flat if n.params.get("modifier") != "%"]
    if not targets:
        return None
    tool = model.wrap_nodes(targets, "rotate_extrude")
    if tool is None:
        return None
    outer = model.wrap_nodes([tool], "rotate")
    if outer is not None:
        outer.params.update(x=-90.0, y=0.0, z=0.0)
        outer.name = AXIS_NAME
        model.node_changed.emit(outer)
        use_axis(model, tool, outer, container)
    return tool
