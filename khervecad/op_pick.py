"""Hull, Split, Shell and Minkowski from the 3D view (2026-10-27, the
user: the tools beside Fillet and Chamfer should work like them).

With nothing selected they only said "select something": now a click
on a part in the 3D view picks it, as Fillet does. And each one must
SHOW something once applied:

- Minkowski of a lone part was the part unchanged — it gets the small
  sphere that makes it round the edges (`DocumentModel.round_edges`).
- Split (bisect) cut at z = 0, below a part standing on the floor, and
  kept everything: it now cuts through the part's middle, keeps both
  halves pulled apart, and a click on a face turns the cut parallel to
  that face.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import language, mesh

#: operations that pick their part in 3D when nothing is selected —
#: every tool that works on a solid (2026-10-27, the user: "all the
#: tools ... done the same way" as Fillet and the extrudes)
PICKED = ("hull", "bisect", "shell", "minkowski",
          "translate", "rotate", "scale", "resize", "multmatrix",
          "render", "pattern", "symmetry", "joint",
          "bevel", "blend", "subdivide", "subd", "decimate", "remesh",
          "wireframe", "bend", "twist", "taper", "lattice", "displace",
          "sculpt", "weathering", "paint", "vertex_paint", "hair_cap",
          "hair_strands", "shape_keys", "armature",
          "difference", "intersection", "union",
          "shrinkwrap", "scatter")
#: these take SEVERAL parts: the body first, then the others; Done
#: (or Esc) applies once enough are picked
MULTI = {"difference": 2, "intersection": 2, "union": 2,
         "shrinkwrap": 2, "scatter": 2}
_MULTI_BANNER = {
    "difference": "Combine ▸ Subtract: click the body to keep, then "
                  "the bodies to cut away · Done applies",
    "intersection": "Combine ▸ Common: click the bodies to intersect "
                    "· Done applies",
    "union": "Combine ▸ Add: click the bodies to join · Done applies",
    "shrinkwrap": "Shrinkwrap: click the part to wrap, then the "
                  "target · Done applies",
    "scatter": "Scatter: click the part to copy, then the surface to "
               "scatter it on · Done applies",
}
#: gap between the two halves of a new split, mm
SPLIT_GAP = 5.0
MINKOWSKI_RADIUS = 1.0


def has_parts(window):
    from . import meshedit_ui
    try:
        return bool(meshedit_ui._parts(window))
    except Exception:
        return False


def pick_part(window, op):
    """Nothing selected: a click on a part runs *op* on it."""
    from . import meshedit_ui
    parts = meshedit_ui._parts(window)
    if not parts:
        window.statusBar().showMessage(language.tr(
            "There is no solid in view — add a part first."), 6000)
        return

    need = MULTI.get(op, 1)
    chosen = []
    tree = window.builder.active_tree()

    def finish():
        tree.select_nodes(chosen)
        window._apply_operation(op)

    def picked(desc, node):
        if desc is None or node is None:
            if need > 1 and len(chosen) >= need:
                finish()
            else:
                window.statusBar().showMessage(language.tr(
                    "Cancelled."), 3000)
            return
        if node not in chosen:
            chosen.append(node)
        if need == 1:
            finish()
            return
        tree.select_nodes(chosen)            # the picks show as chosen
        arm()

    def arm():
        left = [(k, t) for k, t in parts if k not in chosen]
        if not left:
            finish()
            return
        banner = language.tr(_MULTI_BANNER.get(
            op, "Click the part to apply it to · Esc cancels"))
        if need > 1:
            banner += f"  ({len(chosen)} / {need}+)"
        window.view3d.start_pick(
            picked, groups=left, banner=banner,
            labeler=lambda desc, node: getattr(node, "name", ""))

    arm()


def _local_box(node, env, fn):
    tris = []
    for child in node.children:
        tris += mesh.tessellate(child, env=env, fn=fn) \
            if child.visible else []
    if not tris:
        return None
    pts = [v for t in tris for v in t]
    return ([min(p[k] for p in pts) for k in range(3)],
            [max(p[k] for p in pts) for k in range(3)])


def after_wrap(window, op, wrapper):
    """Make a freshly applied *op* do something visible."""
    model = window.model
    if op == "minkowski" and len(wrapper.children) == 1:
        from .model import CadNode
        sphere = CadNode("sphere", model.unique_name("sphere"),
                         dict(radius=MINKOWSKI_RADIUS, segments=24))
        wrapper.add(sphere)
        model.structure_changed.emit()
    elif op == "bisect":
        _centre_split(window, wrapper, (0.0, 0.0, 1.0))
        _arm_split(window, wrapper)


def _centre_split(window, wrapper, normal):
    from . import anchors
    model = window.model
    try:
        box = _local_box(wrapper, anchors.doc_env(model),
                         model.effective_fn())
    except Exception:
        box = None
    centre = [0.0, 0.0, 0.0] if box is None else \
        [round((a + b) / 2.0, 4) for a, b in zip(*box)]
    for key, value in zip(("px", "py", "pz", "nx", "ny", "nz"),
                          centre + [round(v, 6) for v in normal]):
        model.set_param(wrapper, key, value)
    model.set_param(wrapper, "keep", "both")
    model.set_param(wrapper, "gap", SPLIT_GAP)


def _arm_split(window, wrapper):
    """A click on a face turns the cut parallel to it (Esc keeps it)."""
    from . import anchors

    def on_pick(desc, _key=None):
        if desc is None or desc.get("kind") != "face":
            return
        d = desc.get("dir") or [0.0, 0.0, 1.0]
        m = mesh.ancestor_matrix(wrapper, anchors.doc_env(window.model))
        # world normal into the children's frame: the inverse transpose
        # of a rigid / scaled linear part is the transpose of its inverse;
        # for the usual rotations the transpose does it
        n = [sum(m[r][c] * d[r] for r in range(3)) for c in range(3)]
        length = sum(v * v for v in n) ** 0.5 or 1.0
        _centre_split(window, wrapper, [v / length for v in n])
        window.builder.active_tree().select_nodes([wrapper])

    window.view3d.start_pick(on_pick, banner=language.tr(
        "Split: cut through the middle — click a face to cut parallel "
        "to it · Esc keeps this cut"))
