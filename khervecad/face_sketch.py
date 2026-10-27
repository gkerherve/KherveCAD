"""Sketch on ANY flat face (2026-10-21, step 2 of SolidWorks' Edit
Sketch, the user: "sketch on any face").

`start(window)`: click a flat face of a part in the 3D view. A Group
"Sketch on <part>" is made, placed at the clicked point and turned so
its own XY lies on the face — its X / Y the camera's right / up as it
will look square on, Z the face's outward normal. The 3D view turns to
look straight at the face (the angle only, as Create Sketch), and the 2D
sketch opens INSIDE that Group, in its own frame (the scene isolates it
like the Object tab isolates an Object), at the same scale: everything
drawn there lies on the face, ready to extrude (the drag arrow pulls it
out along the normal) or cut.

`params["face_sketch"]` marks the Group; Edit Sketch on a shape inside
it opens the same face again. An empty face sketch is removed on Exit.

`frame_for(normal)` is Qt-free.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

KEY = "face_sketch"


def _unit(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return [c / n for c in v]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]


def camera_for(normal):
    """(yaw, pitch) of a 3D camera looking straight at a face whose
    outward normal is *normal* (View3D's convention: forward = -n)."""
    n = _unit(normal)
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, n[2]))))
    if abs(n[2]) > 0.999999:
        yaw = -90.0                          # a top / bottom face: x right
    else:
        yaw = math.degrees(math.atan2(n[1], n[0]))
    return yaw, pitch


def frame_for(normal):
    """(right, up, n): the face's sketch axes — what the camera square on
    shows as right and up — and its normal."""
    yaw, pitch = camera_for(normal)
    y, p = math.radians(yaw), math.radians(pitch)
    forward = [-math.cos(p) * math.cos(y), -math.cos(p) * math.sin(y),
               -math.sin(p)]
    right = [-math.sin(y), math.cos(y), 0.0]
    up = _cross(right, forward)
    return _unit(right), _unit(up), _unit(normal)


def euler_for(normal):
    """rotate([rx, ry, rz]) taking X, Y, Z onto right, up, n."""
    from .mates import _euler_zyx
    r, u, n = frame_for(normal)
    m = [[r[i], u[i], n[i]] for i in range(3)]
    return _euler_zyx(m)


def _inside(node, outer):
    probe = node.parent
    while probe is not None:
        if probe is outer:
            return True
        probe = probe.parent
    return False


def group_of(node):
    probe = node
    while probe is not None:
        if probe.type == "union" and probe.params.get(KEY):
            return probe
        probe = probe.parent
    return None


# =================================================================== Qt

def start(window, only=None):
    """Click a face, then sketch on it (of the parts *only* holds, when
    given — the selected part)."""
    from . import language, meshedit_ui
    parts = meshedit_ui._parts(window)
    if only:
        keep = [p for p in parts if any(p[0] is n or _inside(n, p[0])
                                        or _inside(p[0], n) for n in only)]
        parts = keep or parts
    if not parts:
        window.statusBar().showMessage(language.tr(
            "No part to sketch on yet."), 5000)
        return False

    def picked(desc, node):
        if desc is None or node is None:
            return
        window.view3d.cancel_pick()
        if desc.get("kind") != "face":
            window.statusBar().showMessage(language.tr(
                "Click a flat FACE (not an edge) to sketch on."), 5000)
            start(window)
            return
        make(window, node, desc["pos"], desc["dir"])
    window.statusBar().showMessage(language.tr(
        "Sketch on Face: click a flat face of a part in the 3D view."),
        8000)
    window.view3d.start_pick(
        picked, groups=parts,
        banner=language.tr("Click the face to sketch on · Esc cancels"),
        labeler=lambda desc, node: getattr(node, "name", ""))
    return True


def make(window, part, point, normal):
    """The face sketch Group at *point* on a face of *part*, then open
    it. Returns the Group."""
    model = window.model
    scope = window.builder.isolated_component() or model.root
    rx, ry, rz = euler_for(normal)
    group = model.add_node("union", dict(
        x=round(float(point[0]), 4), y=round(float(point[1]), 4),
        z=round(float(point[2]), 4), rx=rx, ry=ry, rz=rz), parent=scope)
    group.params[KEY] = True
    model.rename(group, "Sketch on " + getattr(part, "name", "face"))
    group._outline_part = part
    open_sketch(window, group)
    return group


def current(window):
    """The face sketch open now — found again in the restored tree after
    an undo (the tree is rebuilt from a snapshot: the old Group object
    is gone, and the 2D view kept drawing what the undo removed)."""
    group = getattr(window, "_face_sketch", None)
    if group is None:
        return None
    root = window.model.root
    probe = group
    while probe.parent is not None:
        probe = probe.parent
    if probe is root:
        return group
    old = getattr(window.model, "_previous_root", None)
    path, node = [], group
    while node.parent is not None:
        path.append(node.parent.children.index(node))
        node = node.parent
    if node is not old:
        return group
    found = root
    for i in reversed(path):
        if i >= len(found.children):
            found = None
            break
        found = found.children[i]
    if found is not None and found.params.get(KEY):
        window._face_sketch = found
        return found
    return group


def part_of(group):
    """The part a face sketch was drawn on: the one its cut cuts (the
    Difference's first child), else the sibling before it."""
    part = getattr(group, "_outline_part", None)
    if part is not None and part.parent is not None:
        return part
    probe = group.parent
    child = group
    while probe is not None:
        if probe.type == "difference" and probe.children and \
                probe.children[0] is not child:
            return probe.children[0]
        child, probe = probe, probe.parent
    parent = group.parent
    if parent is None:
        return None
    i = parent.children.index(group)
    return next((n for n in reversed(parent.children[:i]) if n.visible),
                None)


def open_sketch(window, group):
    """Turn to the face and sketch inside *group*."""
    from . import face_outline, normal_to
    try:                                 # the face itself, in the sketch
        if not face_outline.show(window, group, part_of(group)):
            # no face there (a reference plane): the part CUT by it
            from . import section_outline
            section_outline.for_group(window, group)
    except Exception:                    # never stop the sketch opening
        import traceback
        traceback.print_exc()
    window._face_sketch = group
    normal = _normal_of(group)
    window._face_sketch_info = dict(group=group)
    normal_to.turn_to(window, "Top (XY)", camera=camera_for(normal),
                      face=group)
    return True


def _normal_of(group):
    """The face's outward normal: the Group's +Z in the scope."""
    o = to_world(group, 0.0, 0.0)
    rx, ry, rz = (math.radians(float(group.params.get(k, 0.0)))
                  for k in ("rx", "ry", "rz"))
    ca, sa = math.cos(rx), math.sin(rx)
    cb, sb = math.cos(ry), math.sin(ry)
    cc, sc = math.cos(rz), math.sin(rz)
    del o
    # third column of Rz·Ry·Rx
    return [cc * sb * ca + sc * sa, sc * sb * ca - cc * sa, cb * ca]


def to_world(group, lx, ly):
    """A point of the face sketch's plane, in the scope's frame."""
    rx, ry, rz = (math.radians(float(group.params.get(k, 0.0)))
                  for k in ("rx", "ry", "rz"))
    ca, sa = math.cos(rx), math.sin(rx)
    cb, sb = math.cos(ry), math.sin(ry)
    cc, sc = math.cos(rz), math.sin(rz)
    # columns of Rz·Ry·Rx
    xcol = [cc * cb, sc * cb, -sb]
    ycol = [cc * sb * sa - sc * ca, sc * sb * sa + cc * ca, cb * sa]
    o = [float(group.params.get(k, 0.0)) for k in ("x", "y", "z")]
    return [o[i] + xcol[i] * lx + ycol[i] * ly for i in range(3)]


def to_local(group, p):
    rx, ry, rz = (math.radians(float(group.params.get(k, 0.0)))
                  for k in ("rx", "ry", "rz"))
    ca, sa = math.cos(rx), math.sin(rx)
    cb, sb = math.cos(ry), math.sin(ry)
    cc, sc = math.cos(rz), math.sin(rz)
    xcol = [cc * cb, sc * cb, -sb]
    ycol = [cc * sb * sa - sc * ca, sc * sb * sa + cc * ca, cb * sa]
    o = [float(group.params.get(k, 0.0)) for k in ("x", "y", "z")]
    d = [p[i] - o[i] for i in range(3)]
    return (sum(d[i] * xcol[i] for i in range(3)),
            sum(d[i] * ycol[i] for i in range(3)))


def close(window):
    """Leaving: the scene stops isolating the face; an empty face sketch
    goes."""
    group = getattr(window, "_face_sketch", None)
    window._face_sketch = None
    from . import face_outline, section_outline
    face_outline.clear(window)
    section_outline.schedule(window)     # back on a main plane: its cut
    if group is not None and group.parent is not None and \
            not group.children:
        window.model.remove_node(group)
    elif group is not None and group.params.get("cut"):
        from . import cut_feature          # a cut's sketch: cut it now
        cut_feature.finish(window, group)
    return group


def action(window):
    """Sketch on Face, for the ribbon."""
    act = getattr(window, "_face_sketch_act", None)
    if act is not None:
        return act
    from PyQt5.QtWidgets import QAction
    from . import icons, language, toolbars, tooltips
    tooltips.TIPS.setdefault("face_sketch", (
        "Sketch on Face",
        "Click any flat face of a part — the top of a block, a slanted "
        "side — and sketch straight on it: the view turns to face it and "
        "what you draw lies on that face, ready to extrude or cut.",
        ["Click this, then a flat face in the 3D view.",
         "Draw: lines, rectangles, polygons, constraints.",
         "Exit Sketch (or Select) to turn back; pull the shape out with "
         "the extrude arrow."],
        "Edit Sketch on a shape drawn there opens the same face again."))
    act = QAction(icons.icon("mdi.vector-square-edit"),
                  language.tr("Sketch on Face"), window)
    act.setData("face_sketch")
    toolbars.remember_glyph(act, "mdi.vector-square-edit", "draw")
    tooltips.apply(act, "face_sketch")
    act.triggered.connect(lambda _=False: start(window))
    window._face_sketch_act = act
    return act
