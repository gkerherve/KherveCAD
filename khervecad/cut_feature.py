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
    return [c for c in group.children if c.category == SHAPE_2D
            or c.type == "regions"]


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
                drag_feature.start(window, diff, quiet=True)  # 10 mm kept
            except Exception:
                pass
    return diff


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
        group = face_sketch.make(window, node, desc["pos"], desc["dir"])
        group.params[KEY] = kind
        window.__dict__.setdefault("_cut_parts", {})[id(group)] = node
        window.statusBar().showMessage(
            "%s: draw the shape (circle, slot, rectangle…), dimension "
            "it, then leave the sketch %s." % (label, end), 10000)
    window.statusBar().showMessage(
        "%s: click the face of the part to %s." % (label, verb), 10000)
    window.view3d.start_pick(
        picked, groups=parts,
        banner="%s: click the face to %s · Esc cancels" % (label, verb),
        labeler=lambda desc, node: getattr(node, "name", ""))
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


TIPS = {k: (v[0], "Cuts a shape sketched on a face into the part "
            "(SolidWorks' %s)." % v[0],
            ["Click the button, then the face to cut into.",
             "Draw the shape on it — circle, slot, rectangle — and add "
             "Smart Dimensions to place and size it.",
             "Leave the sketch: the cut is made."],
            "Or select a face sketch you already drew and click it.")
        for k, v in KINDS.items()}


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
