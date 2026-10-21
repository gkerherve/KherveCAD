"""Animated fit / back on double-click (2026-10-21, the user: "a small
animation when we double click the 3D model — it fits it, then
double-click again puts it back, with an animation; the same for 2D").

- 3D: `toggle_3d(view)` — the first double-click glides the camera
  (target, distance) to `View3D.fit()`'s framing, the next glides back
  to where it was.
- 2D: `toggle_2d(view)` — the same with the sketch's zoom and centre,
  on empty paper with the Select tool.

`DURATION_MS` long, smoothstep eased; instant without a screen
(offscreen tests).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

DURATION_MS = 320
STEP_MS = 16


def _ease(t):
    return t * t * (3 - 2 * t)


def _run(widget, apply, done=None):
    """Call apply(e) for e in 0..1 over DURATION_MS (e eased)."""
    from PyQt5.QtCore import QElapsedTimer, QTimer
    from PyQt5.QtGui import QGuiApplication
    old = getattr(widget, "_kc_anim", None)
    if old is not None:
        old.stop()
        old.deleteLater()
    if not widget.isVisible() or DURATION_MS <= 0 or \
            QGuiApplication.platformName() == "offscreen":
        apply(1.0)
        if done:
            done()
        return
    clock = QElapsedTimer()
    clock.start()
    timer = QTimer(widget)
    timer.setInterval(STEP_MS)

    def tick():
        t = min(1.0, clock.elapsed() / float(DURATION_MS))
        apply(_ease(t))
        if t >= 1.0:
            timer.stop()
            timer.deleteLater()
            widget._kc_anim = None
            if done:
                done()
    timer.timeout.connect(tick)
    widget._kc_anim = timer
    timer.start()


# ------------------------------------------------------------------ 3D
def toggle_3d(view):
    saved = getattr(view, "_kc_before_fit", None)
    start = dict(target=list(view.target), distance=view.distance)
    if saved is not None:
        view._kc_before_fit = None
        goal = saved
    else:
        view._kc_before_fit = dict(start)
        view.fit()                          # where Fit would put it
        goal = dict(target=list(view.target), distance=view.distance)
        view.target, view.distance = start["target"], start["distance"]

    def apply(e):
        view.target = [start["target"][i] + (goal["target"][i]
                                             - start["target"][i]) * e
                       for i in range(3)]
        view.distance = start["distance"] + (goal["distance"]
                                             - start["distance"]) * e
        view.update()
    _run(view, apply)


# ------------------------------------------------------------------ 2D
def _state_2d(view):
    c = view.mapToScene(view.viewport().rect().center())
    return dict(scale=view.px_per_mm(), cx=c.x(), cy=c.y())


def _set_2d(view, scale, cx, cy):
    view.resetTransform()
    view.scale(scale, -scale)
    scene = view.scene()
    if hasattr(scene, "fit_scene_rect"):
        scene.fit_scene_rect()
    view.centerOn(cx, cy)


#: how much a double-click zooms the sketch in
ZOOM_2D = 3.0


def toggle_2d(view, at=None):
    """Double-click: zoom in ZOOM_2D times on *at* (a scene point, else
    the centre) — or fit the drawing when *at* is None and it is off
    screen — and back out on the next one (the user)."""
    saved = getattr(view, "_kc_before_fit", None)
    start = _state_2d(view)
    if saved is not None:
        view._kc_before_fit = None
        goal = saved
    else:
        view._kc_before_fit = dict(start)
        if at is not None:
            goal = dict(scale=start["scale"] * ZOOM_2D, cx=at.x(),
                        cy=at.y())
        else:
            view.fit_content()
            goal = _state_2d(view)
            _set_2d(view, start["scale"], start["cx"], start["cy"])

    def apply(e):
        # zoom in log space so it feels even
        import math
        s = math.exp(math.log(start["scale"]) + (math.log(goal["scale"])
                                                 - math.log(start["scale"]))
                     * e)
        _set_2d(view, s, start["cx"] + (goal["cx"] - start["cx"]) * e,
                start["cy"] + (goal["cy"] - start["cy"]) * e)

    def done():
        view.zoom_changed.emit(view.px_per_mm())
    _run(view, apply, done)
