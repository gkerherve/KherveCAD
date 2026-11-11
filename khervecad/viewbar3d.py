"""The 3D view's toolbar, the way SolidWorks lays out its Heads-Up View
toolbar (2026-11-10, the user: "put it at the bottom centre ... mimic a
bit what SolidWorks has ... is there some that we can add in a submenu,
like focus and fit all? ... the exploded view, can we remove that ...
and the cut, that should be inside the ribbon ... the wireframe should
be on the left side").

It had grown to nineteen buttons in the top-right corner. Now six, along
the foot of the view, centred:

    Wireframe | View orientation ▾ | Zoom to fit ▾ | Pan | Hide / show ▾
    | View settings ▾

- **Wireframe** first, on the left.
- **View orientation** — SolidWorks' cube: a click is Isometric (again:
  the next quarter turn), the arrow lists Isometric, Front, Back, Left,
  Right, Top, Bottom and the two small turns.
- **Zoom to fit** — a click frames everything; the arrow has Zoom to
  selection (the old Focus), Zoom in and Zoom out.
- **Pan** — the hand.
- **Hide / show** — Smart Dimensions, the main planes, the origin axes,
  the scale bar (SolidWorks' Hide/Show Items).
- **View settings** — platform & shadow, the lighting panel, cavity
  shading, edge lines, smooth shading, the reference overlay, hardware
  rendering (SolidWorks' View Settings).

Exploded View and Cut Through left the bar: they are on the ribbon
(Features ▸ Assemble, Evaluate) and in the View menu.

`attach(view)` builds what needs only the view; `add_window_controls`
adds what belongs to the main window. Every menu entry is kept in
``bar.actions`` by key (tests and the assistant trigger them), the
visible buttons in ``bar.buttons``.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtWidgets import QAction, QMenu, QToolButton

from . import viewnav

#: (key, the view's name, label)
ORIENTATIONS = [("view_iso", "Isometric", "Isometric"),
                ("view_front", "Front", "Front"),
                ("view_back", "Back", "Back"),
                ("view_left", "Left", "Left"),
                ("view_side", "Right", "Right"),
                ("view_top", "Top", "Top"),
                ("view_bottom", "Bottom", "Bottom")]


def _icon(button, glyph, fallback):
    from . import icons
    art = icons.icon(glyph, "#e6e9ec")
    if art.isNull():                           # qtawesome missing
        button.setText(fallback)
    else:
        button.setIcon(art)


def _split(bar, key, menu, tip, on_click):
    """A button whose click does the usual thing and whose arrow opens
    *menu*."""
    button = viewnav.MenuButton(bar, menu)
    button.setCheckable(False)
    viewnav.set_tip(button, tip)
    button.clicked.connect(lambda _=False: on_click())
    bar.layout().addWidget(button)
    bar.buttons[key] = button
    return button


def _drop(bar, key, glyph, fallback, tip, menu):
    """A button that only opens *menu*."""
    button = QToolButton(bar)
    button.setMenu(menu)
    button.setPopupMode(QToolButton.InstantPopup)
    _icon(button, glyph, fallback)
    viewnav.set_tip(button, tip)
    bar.layout().addWidget(button)
    bar.buttons[key] = button
    return button


def _act(bar, menu, key, text, slot, checkable=False):
    act = QAction(text, bar)
    act.setCheckable(checkable)
    act.triggered.connect(slot)
    menu.addAction(act)
    bar.actions[key] = act
    return act


def attach(view):
    from .language import tr
    view.hand_pan = viewnav.HandPan3D(view)
    bar = viewnav.NavBar(view, [])
    bar.anchor = "bottom-centre"
    bar.actions = {}

    # ---- view orientation: SolidWorks' cube
    menu = QMenu(bar)
    for key, name, label in ORIENTATIONS:
        _act(bar, menu, key, tr(label),
             lambda _=False, n=name: viewnav.view_click(view, n))
    menu.addSeparator()
    _act(bar, menu, "orbit_left", tr("Turn left"),
         lambda _=False: viewnav.orbit_3d(view, -viewnav.ORBIT_STEP))
    _act(bar, menu, "orbit_right", tr("Turn right"),
         lambda _=False: viewnav.orbit_3d(view, viewnav.ORBIT_STEP))
    cube = _split(bar, "orientation", menu, "nav3d_orientation",
                  lambda: viewnav.view_click(view, "Isometric"))
    cube.setIcon(viewnav.cube_icon("iso"))

    # ---- zoom to fit, the rest of the zooms under its arrow
    menu = QMenu(bar)
    _act(bar, menu, "fit", tr("Zoom to fit"),
         lambda _=False: (view.fit(), view.update()))
    _act(bar, menu, "focus", tr("Zoom to selection"),
         lambda _=False: viewnav.focus_3d(view))
    menu.addSeparator()
    _act(bar, menu, "zoom_in", tr("Zoom in"),
         lambda _=False: viewnav.zoom_3d(view, viewnav.ZOOM_STEP))
    _act(bar, menu, "zoom_out", tr("Zoom out"),
         lambda _=False: viewnav.zoom_3d(view, 1 / viewnav.ZOOM_STEP))
    fit = _split(bar, "fit", menu, "nav3d_fit",
                 lambda: (view.fit(), view.update()))
    _icon(fit, "mdi.arrow-expand-all", "⤢")

    # ---- pan
    hand = QToolButton(bar)
    _icon(hand, "mdi6.hand-back-right-outline", "✋")
    hand.setCheckable(True)
    viewnav.set_tip(hand, "nav3d_hand")
    hand.clicked.connect(lambda on: view.hand_pan.set_on(bool(on)))
    bar.layout().addWidget(hand)
    bar.buttons["hand"] = hand

    # ---- view settings (the window adds its own actions before these)
    menu = QMenu(bar)
    stage = _act(bar, menu, "stage", tr("Platform && shadow"),
                 lambda on: view.set_stage(bool(on)), checkable=True)
    stage.setChecked(bool(getattr(view, "stage", False)))
    view.stage_toggled.connect(stage.setChecked)
    light = _act(bar, menu, "lighting", tr("Lighting panel"),
                 lambda on: view.set_lighting_bar(bool(on)), checkable=True)
    light.setChecked(bool(getattr(view, "lighting_wanted", True)))
    bar.layout().addWidget(viewnav._vline(bar))
    _drop(bar, "display", "mdi.tune-variant", "☰",
          "nav3d_display", menu)
    view.nav_bar = bar
    bar.place()
    return bar


def add_window_controls(win):
    """What needs the main window: Wireframe on the left, Hide / show,
    and the View menu's own looks in View settings."""
    from .language import tr
    bar = getattr(win.view3d, "nav_bar", None)
    if bar is None or not hasattr(bar, "actions"):
        return
    layout = bar.layout()
    from . import wireframe            # edges + every sketch's lines
    wire = viewnav._toggle(bar, "mdi.cube-outline", "▢", "wireframe_bar",
                           wireframe.action(win))
    layout.insertWidget(0, wire)
    layout.insertWidget(1, viewnav._vline(bar))
    bar.buttons["wireframe"] = wire

    # ---- hide / show: before View settings (its separator + button)
    menu = QMenu(bar)
    shown = [("smart_dims", getattr(win, "_smart_dims_act", None)),
             ("relations", getattr(win, "_relations_act", None)),
             ("planes", getattr(win, "_ref_planes_act", None)),
             ("axes", getattr(win, "_axes_act", None)),
             ("scale_bar", getattr(win, "_scale_bar_act", None))]
    from . import view_cube
    win._view_cube_act = view_cube.action(win)
    shown.append(("view_cube", win._view_cube_act))
    for key, act in shown:
        if act is not None:
            menu.addAction(act)
            bar.actions[key] = act
    # SolidWorks' Hide/Show Items: the glasses, a grid of toggles
    # (2026-11-11, the user) — the same one as the 2D sketch's bar
    from . import hide_show
    show = hide_show.button(win, bar)
    layout.insertWidget(layout.count() - 1, show)
    bar.buttons["show"] = show

    # ---- view settings: the window's stage action IS the stage switch
    display = bar.buttons["display"].menu()
    own = [bar.actions.pop("stage", None)]
    for act in own:
        if act is not None:
            display.removeAction(act)
    first = display.actions()[0] if display.actions() else None
    display.insertAction(first, win._stage_act)
    bar.actions["stage"] = win._stage_act
    for act in (win._cavity_act, win._edges_act, win._smooth_act,
                win._overlay_act, win._gl_act):
        display.addAction(act)
    bar.place()
