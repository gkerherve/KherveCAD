"""Floating navigation bars on the 2D sketch and the 3D preview.

Both views could only be steered with the mouse — wheel to zoom,
middle-drag to pan — and a part that did not sit near the origin was
easy to lose. Each view now carries a small bar in its top-right
corner: pan arrows, zoom in / out (hold to repeat), **Focus** (frame
the selected part, or the whole model when nothing is selected) and
**Fit all**; the 3D bar also turns the camera left / right.

The bars are children of the views, placed by an event filter on
resize, so neither view needs to know about them: `attach_2d()` /
`attach_3d()` are called once by the main window.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtWidgets import (QAbstractScrollArea, QFrame, QHBoxLayout,
                             QToolButton, QWidget)

#: the same dark glass as the 3D view's lighting bar
_STYLE = (
    "#navBar { background: rgba(24, 27, 31, 175);"
    " border: 1px solid rgba(255, 255, 255, 40); border-radius: 6px; }"
    "#navBar QToolButton { color: #e6e9ec; background: transparent;"
    " border: none; border-radius: 4px; padding: 2px; font-size: 13px; }"
    "#navBar QToolButton:hover { background: rgba(255, 255, 255, 30); }"
    "#navBar QToolButton:pressed { background: rgba(255, 255, 255, 55); }"
    "#navBar QFrame { color: rgba(255, 255, 255, 45); }")

#: pan step, as a fraction of the view
PAN_STEP = 0.12
#: zoom factor per click
ZOOM_STEP = 1.25
#: turn per click of the 3D orbit buttons (degrees)
ORBIT_STEP = 15.0


class NavBar(QWidget):
    """A row of small buttons floating in a view's top-right corner.

    *buttons* is a list of (key, mdi glyph, fallback text, tooltip,
    slot, repeat) tuples, None for a separator; the buttons are kept in
    `self.buttons` by key."""

    def __init__(self, host, buttons):
        super().__init__(host)
        from . import icons
        self._host = host
        self.setObjectName("navBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(_STYLE)
        row = QHBoxLayout(self)
        row.setContentsMargins(4, 3, 4, 3)
        row.setSpacing(1)
        self.buttons = {}
        for spec in buttons:
            if spec is None:
                line = QFrame(self)
                line.setFrameShape(QFrame.VLine)
                row.addWidget(line)
                continue
            key, glyph, fallback, tip, slot, repeat = spec
            button = QToolButton(self)
            art = icons.icon(glyph, "#e6e9ec")
            if art.isNull():                   # qtawesome missing
                button.setText(fallback)
            else:
                button.setIcon(art)
            button.setToolTip(tip)
            if repeat:                         # hold to keep going
                button.setAutoRepeat(True)
                button.setAutoRepeatDelay(350)
                button.setAutoRepeatInterval(70)
            button.clicked.connect(slot)
            row.addWidget(button)
            self.buttons[key] = button
        host.installEventFilter(self)
        self.place()
        self.show()

    def eventFilter(self, obj, event):
        if obj is self._host and event.type() in (QEvent.Resize,
                                                  QEvent.Show):
            self.place()
        return False

    def _area(self):
        """The part of the host that shows content — a scroll area's
        viewport, so the bar never sits on a scroll bar."""
        host = self._host
        if isinstance(host, QAbstractScrollArea):
            return host.viewport().geometry()
        return host.rect()

    def place(self):
        self.adjustSize()
        area = self._area()
        self.move(area.right() - self.width() - 8, area.top() + 8)
        self.raise_()


# ------------------------------------------------------------------ 2D
def pan_2d(view, dx, dy):
    """Scroll the sketch by a fraction of its size (dx > 0 shows more to
    the right, dy > 0 more below)."""
    port = view.viewport()
    h, v = view.horizontalScrollBar(), view.verticalScrollBar()
    h.setValue(h.value() + int(round(dx * port.width())))
    v.setValue(v.value() + int(round(dy * port.height())))


def focus_2d(view):
    """Frame the selected part; with nothing selected, everything."""
    if view.scene().selectedItems():
        view.zoom_selection()
    else:
        view.fit_content()


def attach_2d(view):
    s = PAN_STEP
    bar = NavBar(view, [
        ("left", "mdi.chevron-left", "◀", "Scroll left (hold to keep "
         "going; middle-drag in the view pans freely)",
         lambda: pan_2d(view, -s, 0), True),
        ("up", "mdi.chevron-up", "▲", "Scroll up",
         lambda: pan_2d(view, 0, -s), True),
        ("down", "mdi.chevron-down", "▼", "Scroll down",
         lambda: pan_2d(view, 0, s), True),
        ("right", "mdi.chevron-right", "▶", "Scroll right",
         lambda: pan_2d(view, s, 0), True),
        None,
        ("zoom_in", "mdi.magnify-plus-outline", "+",
         "Zoom in (Ctrl++, or the mouse wheel)",
         lambda: view.zoom(ZOOM_STEP), True),
        ("zoom_out", "mdi.magnify-minus-outline", "−",
         "Zoom out (Ctrl+-, or the mouse wheel)",
         lambda: view.zoom(1 / ZOOM_STEP), True),
        None,
        ("focus", "mdi.image-filter-center-focus", "◎",
         "Focus: frame the selected part wherever it is — or the whole "
         "sketch when nothing is selected",
         lambda: focus_2d(view), False),
        ("fit", "mdi.arrow-expand-all", "⤢",
         "Fit all: show everything in the sketch (Ctrl+Shift+F)",
         view.fit_content, False),
    ])
    view.nav_bar = bar
    return bar


# ------------------------------------------------------------------ 3D
def pan_3d(view, dx, dy):
    """Slide the camera sideways / up by a fraction of the viewing
    distance (dx > 0 shows more to the right)."""
    _eye, right, up, _fwd = view._camera()
    step = view.distance * PAN_STEP
    for i in range(3):
        view.target[i] += (right[i] * dx + up[i] * dy) * step
    view.user_moved = True
    view.update()


def zoom_3d(view, factor):
    """factor > 1 moves in."""
    view.distance = max(2.0, min(5000.0, view.distance / factor))
    view.user_moved = True
    view.update()


def orbit_3d(view, degrees):
    view.yaw = (view.yaw + degrees) % 360.0
    view.user_moved = True
    view.update()


def focus_3d(view):
    """Frame the selected part (the tinted triangles), else the model."""
    verts = [v for tri in view.highlight_mesh for v in tri]
    view.fit(verts or None)
    view.user_moved = True
    view.update()


def attach_3d(view):
    s = PAN_STEP
    bar = NavBar(view, [
        ("orbit_left", "mdi.rotate-left", "↺",
         "Turn the model left (or left-drag in the view)",
         lambda: orbit_3d(view, -ORBIT_STEP), True),
        ("orbit_right", "mdi.rotate-right", "↻", "Turn the model right",
         lambda: orbit_3d(view, ORBIT_STEP), True),
        None,
        ("left", "mdi.chevron-left", "◀",
         "Pan left (hold to keep going; right- or middle-drag pans "
         "freely)", lambda: pan_3d(view, -1, 0), True),
        ("up", "mdi.chevron-up", "▲", "Pan up",
         lambda: pan_3d(view, 0, 1), True),
        ("down", "mdi.chevron-down", "▼", "Pan down",
         lambda: pan_3d(view, 0, -1), True),
        ("right", "mdi.chevron-right", "▶", "Pan right",
         lambda: pan_3d(view, 1, 0), True),
        None,
        ("zoom_in", "mdi.magnify-plus-outline", "+",
         "Zoom in (or the mouse wheel)",
         lambda: zoom_3d(view, ZOOM_STEP), True),
        ("zoom_out", "mdi.magnify-minus-outline", "−", "Zoom out",
         lambda: zoom_3d(view, 1 / ZOOM_STEP), True),
        None,
        ("focus", "mdi.image-filter-center-focus", "◎",
         "Focus: frame the selected part — or the whole model when "
         "nothing is selected", lambda: focus_3d(view), False),
        ("fit", "mdi.arrow-expand-all", "⤢",
         "Fit all: frame the whole model (Ctrl+F, or double-click)",
         lambda: (view.fit(), view.update()), False),
    ])
    view.nav_bar = bar
    return bar
