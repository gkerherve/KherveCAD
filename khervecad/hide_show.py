"""**Hide/Show Items** — SolidWorks' glasses button (2026-11-11, the
user, with SolidWorks' heads-up toolbar: "the one with glasses … in 3D
view and 2D view, so we could hide them").

One button on the 3D view's bar and on the 2D sketch's bar opens a grid
of toggles — each the window's OWN action (the View menu's), so the
menus, the two bars and Options never disagree: Smart Dimensions,
automatic sizes, sketch relations, construction geometry (centerlines,
points, origins), the main planes, the origin axes, the sketch grid,
the scale bar and the view cube.

Construction geometry is new here (QSettings `sketch/show_construction`,
default shown): off, the 2D sketch draws no `%` shape, so a busy sketch
reads like the finished outline.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

SETTING = "sketch/show_construction"

#: (key, the window's action attribute, icon, short label)
ITEMS = [
    ("smart_dims", "_smart_dims_act", "mdi.ruler", "Smart Dimensions"),
    ("auto_dims", "_dims_act", "mdi.ruler-square", "Automatic sizes"),
    ("relations", "_relations_act", "mdi.link-variant", "Sketch relations"),
    ("construction", "_show_construction_act", "mdi.vector-line",
     "Construction geometry"),
    ("planes", "_ref_planes_act", "mdi.layers-outline", "Main planes"),
    ("axes", "_axes_act", "mdi.axis-arrow", "Origin axes"),
    ("grid", "_grid_act", "mdi.grid", "Sketch grid"),
    ("scale_bar", "_scale_bar_act", "mdi.ruler", "Scale bar"),
    ("view_cube", "_view_cube_act", "mdi.cube-outline", "View cube"),
]


def shows_construction() -> bool:
    try:
        from PyQt5.QtCore import QSettings
        v = QSettings("Kherve", "KherveCAD").value(SETTING, True)
    except Exception:
        return True
    return v not in (False, "false", "0", 0)


def construction_action(win):
    """View ▸ Construction Geometry, made once per window."""
    act = getattr(win, "_show_construction_act", None)
    if act is not None:
        return act
    from PyQt5.QtCore import QSettings
    from PyQt5.QtWidgets import QAction
    from . import icons, language
    act = QAction(icons.icon("mdi.vector-line"),
                  language.tr("Construction Geometry"), win)
    act.setCheckable(True)
    act.setChecked(shows_construction())
    act.setStatusTip(language.tr(
        "Centerlines, sketch points and origins: shown or hidden in the "
        "sketch (they still hold their relations)."))

    def toggled(on):
        QSettings("Kherve", "KherveCAD").setValue(SETTING, bool(on))
        try:
            win.view2d.scene().rebuild()
        except Exception:
            pass
        win.view3d.update()
    act.toggled.connect(toggled)
    win._show_construction_act = act
    return act


def actions(win):
    """[(key, action, icon, label)] of what this window has."""
    construction_action(win)
    out = []
    for key, attr, glyph, label in ITEMS:
        act = getattr(win, attr, None)
        if act is not None:
            out.append((key, act, glyph, label))
    return out


def _fill(win, menu):
    """The grid of toggles, made afresh each time the menu opens (some
    switches are made after the bars)."""
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import (QGridLayout, QLabel, QToolButton, QWidget,
                                 QWidgetAction)
    from . import icons, language
    menu.clear()
    holder = QWidget(menu)
    holder.setObjectName("hideShow")
    from .style import tokens
    t = tokens()
    # its own clear look (the bar's light text made the unticked ones and
    # the title vanish on the menu): off = framed, on = filled blue
    holder.setStyleSheet(
        "#hideShow { background: %(card)s; }"
        "#hideShow QLabel { color: %(text)s; }"
        "#hideShow QToolButton { color: %(text)s; background: %(card)s;"
        " border: 1px solid %(border)s; border-radius: 4px;"
        " padding: 3px 8px; text-align: left; }"
        "#hideShow QToolButton:hover { background: %(hover)s; }"
        "#hideShow QToolButton:checked { background: #2f7bd8;"
        " color: white; border-color: #2f7bd8; }" % t)
    grid = QGridLayout(holder)
    grid.setContentsMargins(8, 6, 8, 8)
    grid.setHorizontalSpacing(4)
    grid.setVerticalSpacing(2)
    title = QLabel("<b>%s</b>" % language.tr("Hide / Show Items"), holder)
    grid.addWidget(title, 0, 0, 1, 2)
    buttons = {}
    for i, (key, act, glyph, label) in enumerate(actions(win)):
        b = QToolButton(holder)
        b.setDefaultAction(act)            # follows the action both ways
        b.setIcon(icons.icon(glyph))
        b.setText(language.tr(label))
        b.setToolTip(act.statusTip() or act.text())
        b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        b.setAutoRaise(True)
        b.setMinimumWidth(170)
        grid.addWidget(b, 1 + i // 2, i % 2)
        buttons[key] = b
    wa = QWidgetAction(menu)
    wa.setDefaultWidget(holder)
    menu.addAction(wa)
    menu._items = buttons
    return buttons


def button(win, parent, ink="#e6e9ec"):
    """The glasses button: a popup grid of the toggles, two columns,
    each an icon and its name (SolidWorks shows icons alone; the names
    say what each does)."""
    from PyQt5.QtWidgets import QMenu, QToolButton
    from . import icons, language
    menu = QMenu(parent)
    menu.aboutToShow.connect(lambda: _fill(win, menu))
    _fill(win, menu)
    show = QToolButton(parent)
    show.setMenu(menu)
    show.setPopupMode(QToolButton.InstantPopup)
    art = icons.icon("mdi.glasses", ink)
    if art.isNull():
        show.setText("👓")
    else:
        show.setIcon(art)
    from . import viewnav
    viewnav.set_tip(show, "nav3d_show")    # the rich help card
    return show
