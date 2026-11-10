"""SolidWorks' CUT features (2026-10-25, the user: "extruded cut,
revolved cut, swept cut, lofted cut, boundary cut — like the Hole
Wizard we click on a face … create a slot, a circle, choose its centre,
add dimensions").

`start(window, kind)`: with a face sketch (Sketch on Face's Group)
holding shapes selected, cut at once; otherwise click a face of a part,
sketch on it (any tool, Smart Dimensions), and the cut is made when you
leave the sketch (`face_sketch.close` calls `finish`). `apply` turns the
sketch Group into the tool and wraps the part with it in a Difference:

- Extruded Cut: `mirror([0, 0, 1]) linear_extrude(depth)` — into the
  part from the face (the drag arrow sets the depth afterwards).
- Revolved Cut: the profile turned about the sketch's own Y axis
  (`rotate([-90, 0, 0]) rotate_extrude()`): draw it right of the axis.
- Swept Cut: a Sweep of the profile (its path edited in Properties).
- Lofted / Boundary Cut: a Loft through sections of the sketch's shapes
  (one height per shape, in Properties).

Everything stays ordinary editable nodes, so the sketch keeps its
dimensions and the cut follows them.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

#: action key -> (label, the node that makes the tool, glyph)
KINDS = {
    "extruded_cut": ("Extruded Cut", "linear_extrude",
                     "mdi.arrow-collapse-down"),
    "revolved_cut": ("Revolved Cut", "rotate_extrude", "mdi.rotate-orbit"),
    "swept_cut": ("Swept Cut", "sweep", "mdi.vector-curve"),
    "lofted_cut": ("Lofted Cut", "section_loft", "mdi.layers-outline"),
    "boundary_cut": ("Boundary Cut", "section_loft",
                     "mdi.vector-square-remove"),
}
#: Extruded Boss/Base on a face (not on the Cut panel): the same flow,
#: the sketch pulled OUT of the face and joined to the part
BOSS = {"extruded_boss": ("Extruded Boss/Base", "linear_extrude",
                          "mdi.arrow-expand-up")}
ALL = dict(KINDS, **BOSS)
DEPTH = 10.0
KEY = "cut"                  # on the face sketch Group: the cut it makes


def _shapes(group):
    from .model import SHAPE_2D

    def flat(c):
        # an ELLIPSE is a circle under a scale: a sketch shape too (it
        # was left out — an ellipse drawn for a cut or boss made nothing)
        return c.category == SHAPE_2D or c.type == "regions" or (
            c.type == "scale" and c.children and
            all(k.category == SHAPE_2D for k in c.children))
    return [c for c in group.children if flat(c)]


def apply(model, group, part, kind):
    """Cut the sketch *group* into *part*. Returns the Difference."""
    shapes = _shapes(group)
    if not shapes or part is None or group.parent is None or \
            not _inside(part, group.parent):
        return None
    label, op, _g = ALL[kind]
    tool = model.wrap_nodes(shapes, op)
    if tool is None:
        return None
    tool.name = label
    if kind in BOSS:
        # out of the face (+Z), beside the part in the same Object: the
        # Object's union joins them — no Difference
        tool.params["height"] = DEPTH
        group.params.pop(KEY, None)
        group.name = "Boss sketch"
        model.node_changed.emit(tool)
        return tool
    if op == "linear_extrude":
        # blind, DEPTH into the face (Reverse Direction: down -Z); one
        # node, no mirror (a simpler tree). Its depth is the user's to
        # set — Through All is a choice in Properties (End condition)
        # (2026-11-01, the user: one side, blind, 10 mm by default)
        tool.params["height"] = DEPTH
        tool.params["reverse"] = True
    elif op == "rotate_extrude":
        outer = model.wrap_nodes([tool], "rotate")     # about sketch Y
        outer.params.update(x=-90.0, y=0.0, z=0.0)
        outer.name = label + " (about the sketch's Y axis)"
    elif op == "section_loft":
        tool.params["heights"] = [i * DEPTH for i in range(len(shapes))]
        outer = model.wrap_nodes([tool], "mirror")
        outer.params.update(x=0.0, y=0.0, z=1.0)
    group.params.pop(KEY, None)
    if group.parent is part.parent:
        diff = model.wrap_nodes([part, group], "difference")
    else:
        # a part nested deeper (inside an Object's groups): the cut goes
        # round the part, the sketch carried into the part's own frame
        diff = model.wrap_nodes([part], "difference")
        if diff is None:
            return None
        frame = model.add_node("multmatrix", {
            "matrix": _to_frame(part, group.parent)}, parent=diff,
            name=label + " (to the part's frame)")
        model.move_node(group, frame)
    if diff is not None:
        diff.name = label
        group.name = "Cut sketch"
        if op == "linear_extrude":
            from . import extent
            extent.refresh(model)
        model.node_changed.emit(diff)
    return diff


def _inside(node, scope):
    while node is not None:
        if node is scope:
            return True
        node = node.parent
    return False


def _to_frame(part, scope):
    """The 4x4 matrix taking *scope*'s coordinates (where the face
    sketch sits) into the frame *part* lives in."""
    import numpy as np
    from . import mesh
    m = np.array(mesh.ancestor_matrix(part, {}, stop=scope), dtype=float)
    inv = np.linalg.inv(m)
    return [[round(float(v), 9) for v in row] for row in inv]


# =================================================================== Qt
def finish(window, group):
    """Leaving a face sketch made for a cut: cut it."""
    kind = group.params.get(KEY) if group is not None else None
    if not kind or group.parent is None:
        return None
    part = getattr(window, "_cut_parts", {}).pop(id(group), None)
    if part is None:                     # (after a restart: the face's part)
        from . import face_sketch
        part = face_sketch.part_of(group)
    if kind in ("extruded_boss", "extruded_cut") and \
            _closes_with_model_edges(window, group, kind):
        return None
    diff = apply(window.model, group, part, kind)
    label = ALL[kind][0]
    if diff is None:
        window.statusBar().showMessage(
            "%s: nothing made — draw a shape on the face." % label, 6000)
    else:
        window.statusBar().showMessage(
            "%s made — its sketch keeps its dimensions; drag the arrow or "
            "set the depth in Properties." % label, 6000)
        if kind in BOSS:
            try:
                from . import drag_feature
                drag_feature.start(window, diff, quiet=True,
                                   panel=True)  # 10 mm kept
            except Exception:
                pass
    return diff


def paint_chosen_face(window, painter, project):
    """The face chosen for a cut or boss, in green, while it is worked
    on (2026-11-01, the user)."""
    from PyQt5.QtCore import QPointF, Qt
    from PyQt5.QtGui import QColor, QPolygonF
    tris = getattr(window, "_chosen_face", None)
    if not tris:
        return
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(60, 190, 80, 110))
    for t in tris:
        pts = [project(v) for v in t[:3]]
        if all(p is not None and p[2] > 0 for p in pts):
            painter.drawPolygon(QPolygonF(
                [QPointF(p[0], p[1]) for p in pts]))


def _forward(yaw, pitch):
    import math
    y, p = math.radians(yaw), math.radians(pitch)
    return (-math.cos(p) * math.cos(y), -math.cos(p) * math.sin(y),
            -math.sin(p))


def show_depth(window):
    """The sketch was drawn looking straight at its face; from there the
    extrude's arrow is seen end-on and its depth not at all. As
    SolidWorks does on leaving a sketch, the view goes back to where the
    face was chosen from (tilted, had that been square on too) — unless
    the user has turned the view since."""
    before = window.__dict__.pop("_cut_view_before", None)
    if before is None:
        return False
    view = window.view3d
    fy, fp = before["face"]
    now = _forward(view.yaw, view.pitch)
    if sum(a * b for a, b in zip(now, _forward(fy, fp))) < 0.9995:
        return False                     # turned by hand: left alone
    yaw, pitch = before["yaw"], before["pitch"]
    if sum(a * b for a, b in zip(now, _forward(yaw, pitch))) > 0.9:
        yaw = fy + 35.0
        pitch = fp - 55.0 if fp > 45 else fp + 55.0 if fp < -45 \
            else fp + 30.0
    from . import view_anim
    view_anim.glide_3d(view, dict(yaw=yaw, pitch=pitch,
                                  target=list(view.target),
                                  distance=view.distance))
    return True


def clear_chosen_face(window):
    window._chosen_face = None
    window.view3d.update()


#: a face sketch for a cut or boss is drawn in the 3D view
IN_3D = True

#: a line this thin (mm) is a sketch line; wider it is a band to cut
THIN_LINE = 0.5


def _closes_with_model_edges(window, group, kind):
    """SolidWorks' "close sketch with model edges" (2026-10-31, the
    user's triangle: one line from edge to edge on a face): loose lines
    that close nothing by themselves are not extruded as thin strips —
    the areas they make WITH the face's edges are offered in 3D instead.
    True when that pick was started."""
    from . import slot2d, sketch_regions
    # construction shapes (a centerline, a reference point on the
    # origin) close nothing: with one in the sketch, a loop of lines was
    # extruded as four thin strips
    shapes = [s for s in _shapes(group) if s.params.get("modifier") != "%"]
    def thin(s):
        # a sketch line (0.2 mm), not a band drawn as a thick line
        try:
            return float(s.params.get("width", 0.2) or 0.2) <= THIN_LINE
        except (TypeError, ValueError):
            return False
    if not any(s.type == "line" and not slot2d.is_slot(s) and thin(s)
               for s in shapes):
        return False
    if not all(s.type == "line" for s in shapes):
        try:
            if sketch_regions.solid_faces(shapes,
                                          sketch_regions.faces(shapes)):
                return False              # they close an area themselves
        except Exception:
            pass
    group.params.pop(KEY, None)
    try:
        started = sketch_regions.start_3d(window, group,
                                          cut=kind == "extruded_cut",
                                          window_at_once=True,
                                          on_nothing=lambda: _back_to_sketch(
                                              window, group, kind))
    except Exception:
        started = False
    if started:
        window.statusBar().showMessage(
            "Click the area your lines close with the part's edges: its "
            "window opens (Shift+click to take several, then Done).", 8000)
    else:
        group.params[KEY] = kind
    return bool(started)


def _back_to_sketch(window, group, kind):
    """No area chosen: nothing is made, and the sketch stays open rather
    than lines left behind with no feature."""
    from . import sketch3d
    group.params[KEY] = kind
    tool = sketch3d.Sketch3DTool(window, "line")
    window.view3d.edit_tool = tool
    tool.use_group(group)
    tool.begin()
    window.view3d.flash("No area chosen — nothing was cut. The sketch is "
                        "still open.", 8000)


def start(window, kind):
    """Extruded Cut and the others: a selected face sketch is cut at
    once; else click a face, sketch, leave the sketch."""
    from . import face_sketch, sketch_regions
    tree = window.builder.active_tree()
    nodes = tree.selected_nodes()
    for n in nodes:
        group = face_sketch.group_of(n)
        part = _part_below(window, group) if group is not None else None
        # (a sketch already made into a feature — the Boss sketch — is
        # not one to cut with now)
        if group is not None and part is not None and _shapes(group) \
                and not any(sketch_regions.used(s) for s in _shapes(group)):
            group.params[KEY] = kind
            return apply(window.model, group, part, kind)
    if kind == "extruded_cut" and nodes and \
            sketch_regions.extrude_selection(window, nodes, cut=True):
        return None                     # the selected shapes, cut whole
    if kind == "extruded_cut":
        # a sketch whose lines split the part's section (a line across
        # the lever): click the areas to cut away (the user)
        try:
            container = sketch_regions.overlap_container(window, nodes)
            if container is not None and sketch_regions.start_3d(
                    window, container, cut=True):
                return None
        except Exception:
            pass
    from . import meshedit_ui
    parts = meshedit_ui._parts(window)
    if not parts:
        window.statusBar().showMessage("Nothing to cut yet.", 5000)
        return None
    # a fresh sketch: nothing left selected from before (the Boss
    # sketch's rectangle, still selected, was drawn in the new sketch at
    # its own place — the user's confusing picture)
    try:
        tree.clearSelection()
        window.view2d.scene().clearSelection()
    except Exception:
        pass
    label = ALL[kind][0]
    verb = "extrude from" if kind in BOSS else "cut into"
    end = "to extrude it" if kind in BOSS else "to cut"

    def picked(desc, node):
        if desc is None or node is None:
            return
        window.view3d.cancel_pick()
        if desc.get("kind") != "face":
            window.statusBar().showMessage(
                "%s: click a flat FACE to sketch on." % label, 5000)
            start(window, kind)
            return
        group = face_sketch.make(window, node, desc["pos"], desc["dir"],
                                 open_2d=not IN_3D)
        group.params[KEY] = kind
        window.__dict__.setdefault("_cut_parts", {})[id(group)] = node
        if IN_3D:
            # drawn ON the face, where the user is looking (2026-11-01,
            # the user: going to the 2D view and back loses them)
            from . import sketch3d
            window._chosen_face = list(desc.get("tris") or [])
            view = window.view3d          # looking straight at the face
            yaw, pitch = face_sketch.camera_for(desc["dir"])
            view.user_moved = True
            # (where the user was looking: back there for the depth)
            window._cut_view_before = dict(
                yaw=view.yaw, pitch=view.pitch, face=(yaw, pitch))
            from . import view_anim
            view_anim.glide_3d(view, dict(
                yaw=yaw, pitch=pitch, target=list(view.target),
                distance=view.distance))
            tool = sketch3d.Sketch3DTool(window, "rect")
            tool.use_group(group)
            window.view3d.edit_tool = tool
            tool.begin()
            ribbon = getattr(window, "ribbon", None)
            if ribbon is not None:
                ribbon.show_tab("sketch")
            return
        window.statusBar().showMessage(
            "%s: draw the shape (circle, slot, rectangle…), dimension "
            "it, then leave the sketch %s." % (label, end), 10000)
    window.statusBar().showMessage(
        "%s: click the face of the part to %s." % (label, verb), 10000)
    window.view3d.start_pick(
        picked, groups=parts,
        banner="%s: click the face to %s · Esc cancels" % (label, verb),
        labeler=lambda desc, node: getattr(node, "name", ""), done=False)
    return None


def _part_below(window, group):
    """The part a face sketch sits beside: the previous visible sibling
    with geometry."""
    parent = group.parent
    if parent is None:
        return None
    i = parent.children.index(group)
    for n in reversed(parent.children[:i]):
        if n.visible and n.type not in ("assign", "variables"):
            return n
    return None


_HOW = {
    "revolved_cut": "the profile is turned about the sketch's own Y axis "
                    "— draw it to the right of that axis",
    "swept_cut": "the profile is swept along a path you then set in "
                 "Properties",
    "lofted_cut": "the cut runs through the sketch's shapes as sections, "
                  "one height each (Properties)",
    "boundary_cut": "the cut runs through the sketch's shapes as "
                    "sections, one height each (Properties)",
}
TIPS = {k: (v[0], "Cuts a shape sketched on a face into the part "
            "(SolidWorks' %s): %s." % (v[0], _HOW[k]),
            ["Click the button, then the flat face to cut into: the view "
             "turns to face it and the Sketch tab opens.",
             "Draw the shape on the face — the Rectangle is ready; "
             "Circle, Slot and Line are on the Sketch tab. Points snap "
             "to the face's corners, middles and edges.",
             "A rectangle, circle or slot is cut as soon as it is drawn; "
             "lines once they close an area (the green button, or "
             "right-click).",
             "Set its numbers in Properties; Smart Dimension places and "
             "sizes the sketch."],
            "Or select a face sketch you already drew and click it.")
        for k, v in KINDS.items() if k in _HOW}
TIPS["extruded_cut"] = (
    "Extruded Cut",
    "Cuts a shape sketched on a face straight into the part, as "
    "SolidWorks' Extruded Cut: pick the face, draw, set the depth.",
    ["Click Extruded Cut, then the flat face to cut into (it lights up "
     "under the mouse): the view turns to face it and the Sketch tab "
     "opens.",
     "Draw the shape on the face — the Rectangle is ready (click two "
     "corners); Circle, Slot and Line are on the Sketch tab. Points "
     "snap to the face's corners, middles and edges.",
     "A rectangle, circle or slot is cut as soon as it is drawn; lines "
     "once they close an area, alone or with the face's edges (the "
     "green button, or right-click).",
     "The view turns back and the Extruded Cut window opens: drag the "
     "blue arrow or type the Distance, choose Through all under End "
     "condition, tick Reverse direction to go the other way.",
     "Smart Dimension still works now, to place and size the shape. "
     "OK or Enter keeps the cut; Cancel or Esc takes it away."],
    "With sketch shapes already selected, Extruded Cut cuts them at "
    "once. While drawing a Line, bring the mouse back onto the last "
    "point and out again (or press A) for a tangent arc.")


def actions(win):
    acts = getattr(win, "_cut_actions", None)
    if acts is not None:
        return acts
    from PyQt5.QtWidgets import QAction
    from . import icons, language, toolbars, tooltips
    tooltips.TIPS.update(TIPS)
    acts = []
    for key, (label, _op, glyph) in KINDS.items():
        act = QAction(icons.icon(glyph, icons.family_color("combine")),
                      language.tr(label), win)
        act.setData(key)
        toolbars.remember_glyph(act, glyph, "combine")
        tooltips.apply(act, key)
        act.triggered.connect(lambda _=False, k=key: start(win, k))
        acts.append(act)
    win._cut_actions = acts
    return acts
