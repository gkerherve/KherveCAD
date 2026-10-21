"""SolidWorks' Edit Sketch / Normal To (2026-10-21, the user: "when we
select the polygon or a 2D face, there's this movement from 3D to 2D ...
the 3D becomes the 2D view with everything we've done in the 2D view").

`edit(window, node)`: the 3D camera turns, over `DURATION_MS`, until it
looks straight at the plane the selected 2D shape lies in (Top, Front or
Right), going orthographic; then the 2D sketch takes its place at the SAME
scale and centre, so the model seems to flatten into the sketch. On
Finish, `back` does the reverse: the 3D view starts square on, at the
sketch's scale and centre, and turns back to the camera it had.

`plane_of` and `angles_for` are Qt-free.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

DURATION_MS = 450
STEP_MS = 16
#: view2d plane -> (3D yaw, pitch) looking square on, the 2D view's axes
#: matching the screen's (Top: x right, y up; Front: x, z; Side: y, z)
CAMERA = {"Top (XY)": (-90.0, 90.0), "Front (XZ)": (-90.0, 0.0),
          "Side (YZ)": (0.0, 0.0)}
#: view2d plane -> the world axes its 2D (a, b) are
AXES = {"Top (XY)": (0, 1), "Front (XZ)": (0, 2), "Side (YZ)": (1, 2)}


def plane_of(normal):
    """The view2d plane a 2D shape with this world *normal* lies in, or
    None when it is tilted."""
    n = [float(c) for c in normal]
    length = math.sqrt(sum(c * c for c in n)) or 1.0
    n = [c / length for c in n]
    for plane, axis in (("Top (XY)", 2), ("Front (XZ)", 1),
                        ("Side (YZ)", 0)):
        if abs(abs(n[axis]) - 1.0) < 1e-6:
            return plane
    return None


def _ease(t):
    return t * t * (3 - 2 * t)                 # smoothstep


def _lerp_angle(a, b, t):
    d = (b - a + 180.0) % 360.0 - 180.0
    return a + d * t


def shape_frame(window, node):
    """(plane, world centre) of the 2D shape *node*, or None."""
    from . import mesh
    scene = window.view2d.scene()
    m = scene._world_matrix(node)
    normal = (m[0][2], m[1][2], m[2][2])
    plane = plane_of(normal)
    if plane is None:
        return None
    try:
        tris = mesh.tessellate(node)
    except Exception:
        tris = []
    pts = [p for t in tris for p in t]
    if pts:
        lo = [min(p[i] for p in pts) for i in range(3)]
        hi = [max(p[i] for p in pts) for i in range(3)]
        local = [(lo[i] + hi[i]) / 2 for i in range(3)]
    else:
        local = [0.0, 0.0, 0.0]
    centre = [sum(m[r][c] * local[c] for c in range(3)) + m[r][3]
              for r in range(3)]
    return plane, centre


def sketch_node(window):
    """The 2D shape the selection means: a 2D shape, or the first one
    inside a selected extrude / group."""
    from .model import SHAPE_2D
    nodes = window.builder.active_tree().selected_nodes()
    for n in nodes:
        if n.category == SHAPE_2D:
            return n
        for c in n.walk():
            if c.category == SHAPE_2D:
                return c
    return None


# =================================================================== Qt

def _animate(window, view, goal, done):
    """Move the 3D camera to *goal* {yaw, pitch, target, distance}."""
    from PyQt5.QtCore import QElapsedTimer, QTimer
    start = dict(yaw=view.yaw, pitch=view.pitch,
                 target=list(view.target), distance=view.distance)
    clock = QElapsedTimer()
    clock.start()
    timer = QTimer(view)
    timer.setInterval(STEP_MS)

    def tick():
        t = min(1.0, clock.elapsed() / float(DURATION_MS))
        e = _ease(t)
        view.yaw = _lerp_angle(start["yaw"], goal["yaw"], e)
        view.pitch = start["pitch"] + (goal["pitch"] - start["pitch"]) * e
        view.target = [start["target"][i] + (goal["target"][i]
                                             - start["target"][i]) * e
                       for i in range(3)]
        view.distance = start["distance"] + (goal["distance"]
                                             - start["distance"]) * e
        view.update()
        if t >= 1.0:
            timer.stop()
            timer.deleteLater()
            done()
    timer.timeout.connect(tick)
    window._normal_to_timer = timer
    from PyQt5.QtGui import QGuiApplication
    if not view.isVisible() or DURATION_MS <= 0 or \
            QGuiApplication.platformName() == "offscreen":   # no screen
        for k in ("yaw", "pitch", "distance"):
            setattr(view, k, goal[k])
        view.target = list(goal["target"])
        timer.deleteLater()
        done()
        return
    timer.start()


def edit(window, node=None):
    """Edit Sketch: turn to the shape's plane, then sketch there."""
    from . import language, sketch_mode
    node = node or sketch_node(window)
    if node is None:
        return pick(window)                    # click the shape in 3D
    from . import face_sketch
    group = face_sketch.group_of(node)
    if group is not None:                      # drawn on a face
        return face_sketch.open_sketch(window, group)
    got = shape_frame(window, node)
    if got is None:
        window.statusBar().showMessage(language.tr(
            "That shape is on a tilted plane — sketching on any face is "
            "the next step; for now Top, Front and Right planes."), 6000)
        if sketch_mode.active(window):
            sketch_mode.enter(window)
        return False
    plane, _centre = got
    return turn_to(window, plane, node)


def create(window):
    """Create Sketch: on the selected shape's plane, else on the plane
    the sketch shows — the camera only turns (the user)."""
    node = sketch_node(window)
    if node is not None and shape_frame(window, node) is not None:
        return edit(window, node)
    plane = getattr(window.view2d.scene(), "plane", "Top (XY)")
    return turn_to(window, plane if plane in CAMERA else "Top (XY)")


def turn_to(window, plane, node=None, camera=None, face=None):
    """Turn the 3D camera square on to *plane* — ONLY the angle: the
    target and distance stay, so nothing zooms or slides (the user: "it
    just changes angle ... the same size as the 2D") — then hand over to
    the sketch at that same scale and centre."""
    from . import language, sketch_mode
    one_canvas = sketch_mode.active(window)
    view = window.view3d
    window._normal_to_saved = dict(
        yaw=view.yaw, pitch=view.pitch, projection=view.projection)
    yaw, pitch = camera if camera is not None else CAMERA[plane]
    view.projection = "Orthographic"
    centre = list(view.target)
    if face is not None:
        # the sketch is the face Group's own XY: where the camera's
        # target falls on it is the 2D view's centre
        from . import face_sketch
        lx, ly = face_sketch.to_local(face, view.target)
        centre = [lx, ly, 0.0]
    goal = dict(yaw=yaw, pitch=pitch, target=centre,
                distance=view.distance)

    def arrived():
        scale = view._focal() / max(view.distance, 1e-6)  # px per mm
        window._normal_to_scale = scale
        window._set_plane(plane)
        if node is not None:
            window.builder.active_tree().select_nodes([node])
        if face is not None:
            window._face_sketch = face        # the scene draws inside it
            window.view2d.scene().rebuild()
        if not one_canvas:
            # the classic layout shows both: the 3D view stays square on,
            # the sketch beside it shows the same plane
            window._normal_to_saved = None
            if node is not None:
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(0, lambda: _frame_shape(window, node))
            window.statusBar().showMessage(language.tr(
                "Sketching on the {plane} plane — draw in the 2D view."
                ).format(plane=plane.split()[0]), 6000)
            return
        sketch_mode.enter(window)
        a, b = AXES[plane]
        from PyQt5.QtCore import QTimer

        def match():
            v2 = window.view2d
            v2.resetTransform()
            v2.scale(scale, -scale)
            scene = v2.scene()
            if hasattr(scene, "fit_scene_rect"):
                scene.fit_scene_rect()
            v2.centerOn(centre[a], centre[b])
            v2.zoom_changed.emit(v2.px_per_mm())
        # after enter()'s own framing (also a 0 ms timer)
        QTimer.singleShot(0, lambda: QTimer.singleShot(0, match))
    _animate(window, view, goal, arrived)
    return True


def _frame_shape(window, node):
    scene = window.view2d.scene()
    rect = None
    for item in scene.items():
        if getattr(item, "node", None) is node:
            rect = item.sceneBoundingRect()
            break
    if rect is not None and not rect.isEmpty():
        window.view2d.frame_rect(rect.adjusted(-rect.width(), -rect.height(),
                                               rect.width(), rect.height()))


def pick(window):
    """Nothing selected: click the 2D shape in the 3D view, then turn to
    it (the user: "select a 2D shape in 3D, then Edit Sketch")."""
    from . import drag_feature, language, sketch_mode
    shapes = drag_feature.flat_shapes(window)
    if not shapes:
        if sketch_mode.active(window):
            sketch_mode.enter(window)          # an empty sketch
        window.statusBar().showMessage(language.tr(
            "No 2D shape yet to sketch on — draw one in the sketch."), 5000)
        return False

    def picked(desc, node):
        if desc is None or node is None:
            return
        window.view3d.cancel_pick()
        window.builder.active_tree().select_nodes([node])
        edit(window, node)
    window.view3d.start_pick(
        picked, groups=shapes,
        banner=language.tr("Click the 2D shape to sketch on · Esc cancels"),
        labeler=lambda desc, node: getattr(node, "name", ""))
    return True


def action(window):
    """Edit Sketch, for every layout's menus and the ribbon."""
    act = getattr(window, "_edit_sketch_act", None)
    if act is not None:
        return act
    from PyQt5.QtWidgets import QAction
    from . import icons, language, toolbars, tooltips
    tooltips.TIPS.setdefault("edit_sketch", (
        "Edit Sketch",
        "SolidWorks' Edit Sketch / Normal To: the 3D view turns to look "
        "straight at the 2D shape's plane and you sketch on it there.",
        ["Select a 2D shape (or an extrude), or click this and then the "
         "shape in the 3D view.",
         "The view turns square on to its plane and the sketch opens.",
         "Leave the sketch to turn back."],
        "Top, Front and Right planes for now."))
    act = QAction(icons.icon("mdi.pencil-box-multiple-outline"),
                  language.tr("Edit Sketch"), window)
    act.setData("edit_sketch")
    toolbars.remember_glyph(act, "mdi.pencil-box-multiple-outline", "draw")
    tooltips.apply(act, "edit_sketch")
    act.triggered.connect(lambda _=False: edit(window))
    window._edit_sketch_act = act
    return act


#: where the camera turns back to when the sketch was not opened here
DEFAULT_ANGLES = (-65.0, 35.0)


def back(window):
    """Leaving the sketch: the 3D view starts square on, at the sketch's
    scale and centre, and only TURNS back to the angle it had — no zoom,
    no slide (the user)."""
    saved = getattr(window, "_normal_to_saved", None) or dict(
        yaw=DEFAULT_ANGLES[0], pitch=DEFAULT_ANGLES[1],
        projection=window.view3d.projection
        if window.view3d.projection != "Orthographic" else "Perspective")
    window._normal_to_saved = None
    view = window.view3d
    v2 = window.view2d
    plane = getattr(v2.scene(), "plane", "Top (XY)")
    face = getattr(window, "_face_sketch", None)
    if face is not None:
        # leaving a face sketch: start square on to the face, at the
        # sketch's centre and size
        from . import face_sketch
        c = v2.mapToScene(v2.viewport().rect().center())
        scale = v2.px_per_mm() or 1.0
        view.projection = "Orthographic"
        view.yaw, view.pitch = face_sketch.camera_for(
            face_sketch._normal_of(face))
        view.target = face_sketch.to_world(face, c.x(), c.y())
        view.distance = view._focal() / scale
        face_sketch.close(window)
        v2.scene().rebuild()
    elif plane in CAMERA:
        yaw, pitch = CAMERA[plane]
        a, b = AXES[plane]
        c = v2.mapToScene(v2.viewport().rect().center())
        target = list(view.target)
        target[a], target[b] = c.x(), c.y()
        scale = v2.px_per_mm() or 1.0
        view.projection = "Orthographic"
        view.yaw, view.pitch = yaw, pitch
        view.target = target
        view.distance = view._focal() / scale
    goal = dict(yaw=saved["yaw"], pitch=saved["pitch"],
                target=list(view.target), distance=view.distance)

    def landed():
        view.projection = saved["projection"]
        view.update()
    _animate(window, view, goal, landed)
    return True
