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

from PyQt5.QtCore import QEvent, QPointF, Qt
from PyQt5.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import (QAbstractScrollArea, QFrame, QHBoxLayout,
                             QMenu, QToolButton, QWidget)

#: the same dark glass as the 3D view's lighting bar
_STYLE = (
    "#navBar { background: rgba(24, 27, 31, 175);"
    " border: 1px solid rgba(255, 255, 255, 40); border-radius: 6px; }"
    "#navBar QToolButton { color: #e6e9ec; background: transparent;"
    " border: none; border-radius: 4px; padding: 2px; font-size: 13px; }"
    "#navBar QToolButton:hover { background: rgba(255, 255, 255, 30); }"
    "#navBar QToolButton:pressed { background: rgba(255, 255, 255, 55); }"
    "#navBar QToolButton:checked { background: rgba(224, 123, 57, 170); }"
    "#navBar QFrame { color: rgba(255, 255, 255, 45); }"
    # a button with options (MenuButton): room for the painted chevron
    "#navBar QToolButton[popupMode=\"1\"] { padding-right: 12px; }"
    "#navBar QToolButton::menu-button { border: none;"
    " background: transparent; width: 10px; }"
    "#navBar QToolButton::menu-arrow { image: none; }")

#: pan step, as a fraction of the view
PAN_STEP = 0.12
#: zoom factor per click
ZOOM_STEP = 1.25
#: turn per click of the 3D orbit buttons (degrees)
ORBIT_STEP = 15.0


def set_tip(button, tip):
    """*tip* is a tooltips.TIPS key (rich help) or plain text."""
    from . import tooltips
    if tip in tooltips.TIPS:
        tooltips.apply(button, tip)
    else:
        button.setToolTip(tip)


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
            set_tip(button, tip)
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
        if getattr(self, "anchor", "top-right") == "bottom-centre":
            # Fusion's navigation bar: centred along the canvas' foot
            self.move(area.left() + (area.width() - self.width()) // 2,
                      area.bottom() - self.height() - 10)
        else:
            self.move(area.right() - self.width() - 8, area.top() + 8)
        self.raise_()


class MenuButton(QToolButton):
    """A bar button with options: a click on the icon switches the
    feature, the slim arrow beside it opens every option. The look of
    the main toolbar's GroupButton — the theme hides menu arrows, so
    the chevron is painted."""

    ARROW_W = 10

    def __init__(self, parent, menu):
        super().__init__(parent)
        self.setMenu(menu)
        self.setPopupMode(QToolButton.MenuButtonPopup)
        self.setCheckable(True)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(230, 233, 236, 200), 1.3))
        cx = self.width() - self.ARROW_W / 2.0 - 1.0
        cy = self.height() / 2.0 + 1.0
        painter.drawPolyline(QPolygonF([QPointF(cx - 2.5, cy - 1.3),
                                        QPointF(cx, cy + 1.3),
                                        QPointF(cx + 2.5, cy - 1.3)]))
        painter.end()


def add_menu_button(bar, key, glyph, fallback, tip, actions, on_click):
    """Append a separator and a MenuButton to *bar*. Its menu holds
    *actions* — pass a View menu's own, so a tick in one is a tick in
    the other; *on_click(checked)* runs for a click on the icon."""
    from . import icons
    menu = QMenu(bar)
    menu.addActions(list(actions))
    line = QFrame(bar)
    line.setFrameShape(QFrame.VLine)
    bar.layout().addWidget(line)
    button = MenuButton(bar, menu)
    art = icons.icon(glyph, "#e6e9ec")
    if art.isNull():                           # qtawesome missing
        button.setText(fallback)
    else:
        button.setIcon(art)
    set_tip(button, tip)
    button.clicked.connect(on_click)
    bar.layout().addWidget(button)
    bar.buttons[key] = button
    bar.place()
    return button


def add_options_button(bar, key, glyph, fallback, tip, actions):
    """Append a separator and a plain dropdown button to *bar*: any
    click opens *actions* — a View menu's own checkable actions, so a
    tick in one is a tick in the other. Unlike `add_menu_button` there
    is no single feature to switch from the icon itself (the actions
    are independent looks, not variations of one thing), so the whole
    button is the menu launcher."""
    from . import icons
    menu = QMenu(bar)
    menu.addActions(list(actions))
    line = QFrame(bar)
    line.setFrameShape(QFrame.VLine)
    bar.layout().addWidget(line)
    button = QToolButton(bar)
    button.setMenu(menu)
    button.setPopupMode(QToolButton.InstantPopup)
    art = icons.icon(glyph, "#e6e9ec")
    if art.isNull():                           # qtawesome missing
        button.setText(fallback)
    else:
        button.setIcon(art)
    set_tip(button, tip)
    bar.layout().addWidget(button)
    bar.buttons[key] = button
    bar.place()
    return button


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
        ("left", "mdi.chevron-left", "◀", "nav2d_left",
         lambda: pan_2d(view, -s, 0), True),
        ("up", "mdi.chevron-up", "▲", "nav2d_up",
         lambda: pan_2d(view, 0, -s), True),
        ("down", "mdi.chevron-down", "▼", "nav2d_down",
         lambda: pan_2d(view, 0, s), True),
        ("right", "mdi.chevron-right", "▶", "nav2d_right",
         lambda: pan_2d(view, s, 0), True),
        None,
        ("zoom_in", "mdi.magnify-plus-outline", "+",
         "nav2d_zoom_in",
         lambda: view.zoom(ZOOM_STEP), True),
        ("zoom_out", "mdi.magnify-minus-outline", "−",
         "nav2d_zoom_out",
         lambda: view.zoom(1 / ZOOM_STEP), True),
        None,
        ("focus", "mdi.image-filter-center-focus", "◎",
         "nav2d_focus",
         lambda: focus_2d(view), False),
        ("fit", "mdi.arrow-expand-all", "⤢",
         "nav2d_fit",
         view.fit_content, False),
    ])
    view.nav_bar = bar
    return bar


#: grid spacings offered by the sketch bar's grid menu (document units)
GRID_STEPS = (0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100)


def cube_icon(face, size=20):
    """A little isometric cube with one face lit: "top", "front" (the
    left face) or "side" (the right face) — the plane the sketch shows."""
    from PyQt5.QtGui import QIcon, QPixmap
    ratio = 2
    pix = QPixmap(size * ratio, size * ratio)
    pix.setDevicePixelRatio(ratio)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    c, r = size / 2.0, size * 0.46                 # centre, hex radius
    import math
    k = r * math.sin(math.radians(60))
    top = QPointF(c, c - r)
    ur, lr = QPointF(c + k, c - r / 2), QPointF(c + k, c + r / 2)
    bot, ll = QPointF(c, c + r), QPointF(c - k, c + r / 2)
    ul, mid = QPointF(c - k, c - r / 2), QPointF(c, c)
    faces = {"top": [top, ur, mid, ul], "front": [ul, mid, bot, ll],
             "side": [mid, ur, lr, bot]}
    painter.setPen(QPen(QColor(230, 233, 236, 210), 1.0))
    for name, pts in faces.items():
        lit = name == face
        painter.setBrush(QColor(255, 255, 255, 255) if lit
                         else QColor(150, 158, 168, 70))
        painter.drawPolygon(QPolygonF(pts))
    painter.end()
    return QIcon(pix)


def add_sketch_controls(win, bar):
    """Plane (Top / Front / Side), grid and snap on the 2D view's own
    bar (they used to sit on the main toolbar): the plane buttons are
    exclusive and follow the scene when it jumps plane by itself; the
    grid button switches the grid, its arrow picks the spacing."""
    from PyQt5.QtWidgets import QActionGroup, QInputDialog
    from . import icons
    from .view2d import PLANES
    names = {"Top (XY)": ("Top", "Top view (XY plane)"),
             "Front (XZ)": ("Front", "Front view (XZ plane)"),
             "Side (YZ)": ("Side", "Side view (YZ plane)")}
    key_of = {"Top (XY)": "plane_top", "Front (XZ)": "plane_front",
              "Side (YZ)": "plane_side"}
    win._plane_buttons = {}
    line = QFrame(bar)
    line.setFrameShape(QFrame.VLine)
    bar.layout().insertWidget(0, line)
    for plane in reversed(list(PLANES)):
        label, tip = names[plane]
        button = QToolButton(bar)
        button.setIcon(cube_icon({"Top": "top", "Front": "front",
                                  "Side": "side"}[label]))
        set_tip(button, key_of[plane])
        button.setCheckable(True)
        button.setAutoExclusive(True)
        button.setChecked(plane == win.scene.plane)
        button.clicked.connect(lambda _=False, p=plane: win._set_plane(p))
        bar.layout().insertWidget(0, button)
        win._plane_buttons[plane] = button
    menu = QMenu(bar)
    group = QActionGroup(menu)
    win._grid_step_acts = {}
    for step in GRID_STEPS:
        act = menu.addAction("%g mm" % step)
        act.setCheckable(True)
        group.addAction(act)
        act.triggered.connect(lambda _=False, v=step: win._set_grid_step(v))
        win._grid_step_acts[step] = act
    menu.addSeparator()

    def ask():
        v, ok = QInputDialog.getDouble(
            win, "Grid spacing", "Spacing (mm):", win.scene.grid_size,
            0.01, 1000.0, 2)
        if ok:
            win._set_grid_step(v)
    menu.addAction("Custom…").triggered.connect(ask)
    layout = bar.layout()
    layout.addWidget(_vline(bar))
    grid = MenuButton(bar, menu)
    art = icons.icon("mdi.grid", "#e6e9ec")
    if art.isNull():
        grid.setText("#")
    else:
        grid.setIcon(art)
    set_tip(grid, "grid_bar")
    grid.setChecked(win.scene.show_grid)
    grid.clicked.connect(win._grid_act.setChecked)
    win._grid_act.toggled.connect(grid.setChecked)
    layout.addWidget(grid)
    snap = QToolButton(bar)
    art = icons.icon("mdi.magnet", "#e6e9ec")
    if art.isNull():
        snap.setText("⌗")
    else:
        snap.setIcon(art)
    snap.setCheckable(True)
    snap.setChecked(win.scene.snap_enabled)
    set_tip(snap, "snap_bar")
    snap.clicked.connect(win._snap_act.setChecked)
    win._snap_act.toggled.connect(snap.setChecked)
    layout.addWidget(snap)
    bar.buttons["grid"], bar.buttons["snap"] = grid, snap
    win._sync_grid_step()
    bar.place()


def _vline(parent):
    line = QFrame(parent)
    line.setFrameShape(QFrame.VLine)
    return line


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
    view.distance = max(view.MIN_DISTANCE,
                        min(view.MAX_DISTANCE, view.distance / factor))
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
         "nav3d_orbit_left",
         lambda: orbit_3d(view, -ORBIT_STEP), True),
        ("orbit_right", "mdi.rotate-right", "↻", "nav3d_orbit_right",
         lambda: orbit_3d(view, ORBIT_STEP), True),
        None,
        ("left", "mdi.chevron-left", "◀",
         "nav3d_left", lambda: pan_3d(view, -1, 0), True),
        ("up", "mdi.chevron-up", "▲", "nav3d_up",
         lambda: pan_3d(view, 0, 1), True),
        ("down", "mdi.chevron-down", "▼", "nav3d_down",
         lambda: pan_3d(view, 0, -1), True),
        ("right", "mdi.chevron-right", "▶", "nav3d_right",
         lambda: pan_3d(view, 1, 0), True),
        None,
        ("zoom_in", "mdi.magnify-plus-outline", "+",
         "nav3d_zoom_in",
         lambda: zoom_3d(view, ZOOM_STEP), True),
        ("zoom_out", "mdi.magnify-minus-outline", "−", "nav3d_zoom_out",
         lambda: zoom_3d(view, 1 / ZOOM_STEP), True),
        None,
        ("focus", "mdi.image-filter-center-focus", "◎",
         "nav3d_focus", lambda: focus_3d(view), False),
        ("fit", "mdi.arrow-expand-all", "⤢",
         "nav3d_fit",
         lambda: (view.fit(), view.update()), False),
        None,
        ("stage", "mdi.box-shadow", "◐",
         "nav3d_stage",
         lambda: view.set_stage(not view.stage), False),
    ])
    # the button shows the stage's state, whoever switched it
    stage = bar.buttons["stage"]
    stage.setCheckable(True)
    stage.setChecked(bool(getattr(view, "stage", False)))
    view.stage_toggled.connect(stage.setChecked)
    layout = bar.layout()
    layout.insertWidget(0, _vline(bar))
    for face, name, key in reversed((("top", "Top", "nav3d_top"),
                                     ("front", "Front", "nav3d_front"),
                                     ("side", "Right", "nav3d_side"))):
        button = QToolButton(bar)
        button.setIcon(cube_icon(face))
        set_tip(button, key)
        button.clicked.connect(lambda _=False, n=name: view.set_view(n))
        layout.insertWidget(0, button)
        bar.buttons["view_" + face] = button
    view.nav_bar = bar
    return bar
