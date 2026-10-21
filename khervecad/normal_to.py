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
    if not view.isVisible() or DURATION_MS <= 0:
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
        sketch_mode.enter(window)              # nothing picked: as before
        return False
    got = shape_frame(window, node)
    if got is None:
        window.statusBar().showMessage(language.tr(
            "That shape is on a tilted plane — sketching on any face is "
            "the next step; for now Top, Front and Right planes."), 6000)
        sketch_mode.enter(window)
        return False
    plane, centre = got
    view = window.view3d
    window._normal_to_saved = dict(
        yaw=view.yaw, pitch=view.pitch, target=list(view.target),
        distance=view.distance, projection=view.projection)
    yaw, pitch = CAMERA[plane]
    view.projection = "Orthographic"
    goal = dict(yaw=yaw, pitch=pitch, target=centre,
                distance=view.distance)

    def arrived():
        scale = view._focal() / max(view.distance, 1e-6)  # px per mm
        window._normal_to_scale = scale
        window._set_plane(plane)
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


def back(window):
    """Leaving the sketch: start square on, at the sketch's scale and
    centre, and turn back to where the camera was. False when the sketch
    was not opened by `edit`."""
    saved = getattr(window, "_normal_to_saved", None)
    if not saved:
        return False
    window._normal_to_saved = None
    view = window.view3d
    v2 = window.view2d
    plane = getattr(v2.scene(), "plane", "Top (XY)")
    if plane in CAMERA:
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
                target=saved["target"], distance=saved["distance"])

    def landed():
        view.projection = saved["projection"]
        view.update()
    _animate(window, view, goal, landed)
    return True
