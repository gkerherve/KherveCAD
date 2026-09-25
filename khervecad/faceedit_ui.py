"""Push / pull by clicking — each click on a flat face of the part adds
a row to the push_pull node (5 mm out; edit the distance, or a negative
one for a pocket, and the inset in Properties). Esc finishes.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import language, mesh
from .physics import _invert

DEFAULT_DISTANCE = 5.0


def local_point(node, world, env=None):
    """*world* (xyz) in the push_pull node's own frame (its children's)."""
    return mesh.mat_apply(_invert(mesh.ancestor_matrix(node, env)), world)


def start(window, node):
    view = window.view3d
    model = window.model

    def banner():
        n = len(node.params.get("pushes") or [])
        text = language.tr(
            "Push / pull: click a flat face to push it {distance:g} "
            "mm (edit the distance in Properties; negative cuts a "
            "pocket)").format(distance=DEFAULT_DISTANCE)
        if n:
            text += " · " + language.tr("{count} face(s)").format(count=n)
        return text + " · " + language.tr("Esc when done")

    def on_pick(desc, _key=None):
        if desc is None:
            window.builder.active_tree().select_nodes([node])
            return
        from . import anchors
        env = anchors.doc_env(model)
        p = [round(v, 4) for v in local_point(node, desc["point"], env)]
        rows = [list(r) for r in (node.params.get("pushes") or [])]
        model.set_param(node, "pushes", rows + [p + [DEFAULT_DISTANCE, 0.0]])
        arm()

    def arm():
        view.start_pick(on_pick, banner=banner())
    arm()
