"""WHICH sketch the 2D view is on (2026-11-10, the user: "often in the
2D view there are some random circles overclashing because it seems that
we create a sketch in a different plane and this ends up appearing ...
only show the plane that we've selected").

The 2D view was made as an overview: every 2D shape lying square on to
the plane on show was drawn, whatever its height and whichever feature
it belonged to — the base's outline, a boss's sketch a millimetre above
it, a pocket's circle, each with its relation marks and dimensions, one
over the other. In SolidWorks a sketch shows the model and THAT sketch.

`current(window)` says what is being sketched while Sketch Mode is on in
the one-canvas styles (SolidWorks, Fusion), or None (the classic layout
keeps its overview):

- **group** — a sketch on a face or a reference plane (its Group); the
  scene is already inside it;
- **container** — Edit Sketch on a shape of a main plane: the node
  holding that shape and its siblings (an extrude, a Regions);
- **plane** — a new sketch on the Front / Top / Right plane: the loose
  shapes lying ON that plane (through the origin), not yet used by any
  feature.

A `Focus` answers `shows(scene, node)` for the scene's rebuild, gives the
camera that looks square on at the sketch (`camera`) and the part to
show behind it (`mesh`): what was built BEFORE the sketch for a group or
container — the part rolled back to it, as SolidWorks does — the whole
part for a new plane sketch. sketch_backdrop paints it.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

#: on the plane: a shape's own plane this near it (mm)
ON_PLANE = 1e-6
#: what makes a sketch shape USED by a feature
FEATURES = ("linear_extrude", "rotate_extrude", "regions", "sweep",
            "section_loft", "offset", "hull", "difference",
            "intersection", "minkowski", "curve_surface")


class Focus:
    def __init__(self, window, kind, plane, group=None, container=None):
        self.window = window
        self.kind = kind
        self.plane = plane
        self.group = group
        self.container = container

    # ------------------------------------------------------ the shapes
    def _scope(self):
        root = self.window._render_scope()[0]
        return root

    def _loose(self, node):
        """Not used by a feature, not in a face sketch."""
        from . import face_sketch
        scope = self._scope()
        probe = node.parent
        while probe is not None and probe is not scope:
            if probe.type in FEATURES or probe.params.get(face_sketch.KEY):
                return False
            probe = probe.parent
        return True

    def _on_plane(self, scene, node):
        from .view2d import PLANES
        (ai, bi), _keys = PLANES.get(scene.plane, PLANES["Top (XY)"])
        ni = 3 - ai - bi
        m = scene._world_matrix(node)
        return abs(m[ni][3]) < ON_PLANE

    def shows(self, scene, node):
        """Is 2D shape *node* part of the sketch on show?"""
        if self.kind == "group":
            return True                    # the scene is inside the Group
        if self.kind == "container":
            probe = node
            while probe is not None:
                if probe is self.container:
                    return True
                probe = probe.parent
        return self._loose(node) and self._on_plane(scene, node)

    def parent_for_new(self, scene):
        """Where a shape drawn now goes, or None for the usual place."""
        if self.kind != "container" or not self.container.children:
            return None
        from . import view2d_edit
        try:
            if view2d_edit.frame_transform(
                    scene, self.container.children[0]) is None:
                return self.container       # same frame as the plane
        except Exception:
            pass
        return None

    # ------------------------------------------------------ the camera
    def to_world(self, x, y):
        """Sketch (x, y) on show -> the scope's world."""
        if self.kind == "group":
            from . import face_sketch
            return [float(v) for v in face_sketch.to_world(self.group, x, y)]
        from .view2d import PLANES
        (ai, bi), _keys = PLANES.get(self.plane, PLANES["Top (XY)"])
        w = [0.0, 0.0, 0.0]
        w[ai], w[bi] = float(x), float(y)
        return w

    def angles(self):
        """(yaw, pitch) looking square on at the sketch."""
        if self.kind == "group":
            from . import face_sketch
            return face_sketch.camera_for(face_sketch._normal_of(self.group))
        from . import normal_to
        return normal_to.CAMERA.get(self.plane, normal_to.CAMERA["Top (XY)"])

    # -------------------------------------------------------- the part
    def mesh(self):
        """(triangles, colours) of the part to show behind the sketch."""
        from . import sketch_backdrop
        window = self.window
        if self.kind == "group":
            return sketch_backdrop.built_before(window, self.group)
        if self.kind == "container":
            return sketch_backdrop.built_before(window, self.container)
        from .view2d import _produces_3d
        scope = self._scope()
        nodes = [c for c in scope.children if c.visible
                 and c.type not in ("assign", "variables")
                 and _produces_3d(c)]
        return sketch_backdrop.tessellate(window, nodes)

    def key(self):
        return (self.kind, self.plane, id(self.group), id(self.container))


def current(window):
    """The `Focus` of the sketch being edited, or None."""
    from . import sketch_mode
    if not sketch_mode.active(window) or not sketch_mode.sketching(window):
        return None
    scene = window.view2d.scene()
    plane = getattr(scene, "plane", "Top (XY)")
    from . import face_sketch
    group = face_sketch.current(window)
    if group is not None and group.parent is not None:
        return Focus(window, "group", plane, group=group)
    node = getattr(window, "_sketch_edit_node", None)
    if node is not None and node.parent is not None:
        try:
            from . import view2d_edit
            if view2d_edit.on_view_plane(scene, node):
                return Focus(window, "container", plane,
                             container=node.parent)
        except Exception:
            pass
    return Focus(window, "plane", plane)
