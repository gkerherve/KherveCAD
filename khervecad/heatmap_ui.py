"""Analyse ▸ Heat Map — the heat map switch on the main window.

The window keeps ``_heatmap`` = {kind, min_wall, overhang} (kind "off"
= none) and its last ``_heat_stats``; `apply` is called from
`MainWindow._refresh_preview` with the preview's triangles and replaces
their colours. MCP `set_render_options heatmap` sets the same state, so
render_view pictures show it.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtWidgets import QAction, QActionGroup

from . import heatmap, icons, language


def state(window) -> dict:
    st = getattr(window, "_heatmap", None)
    if st is None:
        st = window._heatmap = dict(kind="off", min_wall=0.8,
                                    overhang=45.0)
    return st


def set_heatmap(window, kind=None, min_wall=None, overhang=None):
    st = state(window)
    if kind is not None:
        if kind not in heatmap.KINDS:
            raise ValueError("heatmap must be one of "
                             + ", ".join(heatmap.KINDS))
        st["kind"] = kind
    if min_wall is not None:
        st["min_wall"] = max(float(min_wall), 1e-6)
    if overhang is not None:
        st["overhang"] = min(max(float(overhang), 1.0), 89.0)
    for act in getattr(window, "_heat_actions", {}).values():
        act.setChecked(act.data() == st["kind"])
    window._refresh_preview()
    return getattr(window, "_heat_stats", {})


def apply(window, tris, colors, label):
    """(colours, label) with the heat map painted, or unchanged."""
    st = state(window)
    if st["kind"] == "off" or not tris:
        window._heat_stats = {}
        return colors, label
    from . import units
    wall = st["min_wall"]
    cols, stats = heatmap.colours(tris, st["kind"], wall, st["overhang"])
    window._heat_stats = stats
    if cols is None:
        return colors, label
    sym = units.symbol(window.model.unit)
    if st["kind"] == "thickness":
        thin = stats.get("thinnest")
        suffix = language.tr(
            "— heat map: wall thickness, red < {wall:g} {unit}").format(
                wall=wall, unit=sym)
        if thin is not None:
            suffix += ", " + language.tr(
                "thinnest {thin:.2f}").format(thin=thin)
        label += " " + suffix
    else:
        label += " " + language.tr(
            "— heat map: overhang, red past {angle:g}° "
            "({fraction:.0f} %)").format(
                angle=st['overhang'],
                fraction=stats['overhang_fraction'] * 100)
    return cols, label


def add_menu(window, menu):
    sub = menu.addMenu(icons.icon("mdi.thermometer"),
                       language.tr("&Heat Map"))
    group = QActionGroup(window)
    window._heat_actions = {}
    for kind, text in (("off", language.tr("&Off")),
                       ("thickness", language.tr("&Wall thickness")),
                       ("overhang", language.tr("Over&hangs"))):
        act = QAction(text, window, checkable=True)
        act.setData(kind)
        act.setChecked(state(window)["kind"] == kind)
        act.triggered.connect(lambda _c, k=kind: set_heatmap(window, k))
        group.addAction(act)
        sub.addAction(act)
        window._heat_actions[kind] = act
    return sub
