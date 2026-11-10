"""Which ribbon tabs show (2026-11-10, the user: "is there not too many
tabs in too many ribbons? Is it something that SolidWorks has or not?
Because that seems to be way too many").

SolidWorks' CommandManager shows about six tabs for a part — Features,
Sketch, Markup, Evaluate, MBD Dimensions, Add-Ins — and keeps the others
(Surfaces, Sheet Metal, Weldments, Mold Tools, Direct Editing…) off
until they are ticked in the menu a right-click on any tab opens (Tabs
▸). KherveCAD showed all eleven of its own.

The same here: the everyday tabs show, the rest are one tick away —
right-click a tab, or the ⋯ button after the last one. Nothing is lost:
every command of a hidden tab stays in the menus and in the ribbon's
search box, and running a command of a hidden tab from the search shows
its tab for that session.

Remembered in QSettings ``ribbon/hidden_tabs``: tab keys, comma
separated; "none" = every tab shown (the tests' setting); absent = the
defaults below.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtWidgets import QMenu, QToolButton

SETTING = "ribbon/hidden_tabs"
_SETTINGS = ("Kherve", "KherveCAD")
#: off until ticked: what SolidWorks has no everyday tab for
DEFAULT_HIDDEN = ("form", "character", "utilities", "build")
#: never hidden: a ribbon needs somewhere to stand
ALWAYS = ("features", "sketch")


def hidden():
    """The set of tab keys not shown."""
    value = QSettings(*_SETTINGS).value(SETTING)
    if value is None:
        return set(DEFAULT_HIDDEN)
    return {k for k in str(value).split(",")
            if k and k != "none" and k not in ALWAYS}


def _save(keys):
    QSettings(*_SETTINGS).setValue(SETTING, ",".join(sorted(keys)) or "none")


def _index(ribbon, key):
    return next((i for i, t in enumerate(ribbon.order) if t[0] == key), -1)


def apply(ribbon):
    """Show / hide *ribbon*'s tabs as remembered. The current tab, if it
    is hidden now, gives way to the first one shown."""
    keys = hidden() - getattr(ribbon, "_shown_once", set())
    for i, tab in enumerate(ribbon.order):
        ribbon.tabs.setTabVisible(i, tab[0] not in keys)
    current = ribbon.tabs.currentIndex()
    if 0 <= current < len(ribbon.order) and ribbon.order[current][0] in keys:
        first = next((i for i, t in enumerate(ribbon.order)
                      if t[0] not in keys), 0)
        ribbon.tabs.setCurrentIndex(first)


def set_shown(ribbon, key, on=True, current=False):
    """Tick or untick tab *key*, remembered."""
    if key in ALWAYS and not on:
        return
    keys = hidden()
    keys.discard(key) if on else keys.add(key)
    _save(keys)
    if not on:
        getattr(ribbon, "_shown_once", set()).discard(key)
    apply(ribbon)
    if on and current:
        ribbon.show_tab(key)


def reveal(ribbon, index):
    """Tab *index* is being opened by a command (the search box): shown
    for this session even if it is unticked."""
    if 0 <= index < len(ribbon.order) and \
            not ribbon.tabs.isTabVisible(index):
        if not hasattr(ribbon, "_shown_once"):
            ribbon._shown_once = set()
        ribbon._shown_once.add(ribbon.order[index][0])
        ribbon.tabs.setTabVisible(index, True)


def menu(ribbon, parent=None):
    """The Tabs menu: one tick a tab."""
    from . import language
    m = QMenu(parent or ribbon)
    m.addSection(language.tr("Tabs"))
    keys = hidden()
    for key, fusion_title, sw_title, _panels in ribbon.order:
        title = language.tr(fusion_title if ribbon.fusion else sw_title)
        act = m.addAction(title.title() if ribbon.fusion else title)
        act.setCheckable(True)
        act.setChecked(key not in keys)
        act.setEnabled(key not in ALWAYS)
        act.toggled.connect(
            lambda on, k=key: set_shown(ribbon, k, on, current=on))
    m.addSeparator()
    m.addAction(language.tr("Show every tab"),
                lambda: (_save(set()), apply(ribbon)))
    m.addAction(language.tr("Show the usual tabs"),
                lambda: (QSettings(*_SETTINGS).remove(SETTING),
                         apply(ribbon)))
    return m


def install(ribbon):
    """Right-click on the tabs opens the Tabs menu; returns the ⋯ button
    to stand after the last tab."""
    from . import language
    bar = ribbon.tabs
    bar.setContextMenuPolicy(Qt.CustomContextMenu)
    bar.customContextMenuRequested.connect(
        lambda pos: menu(ribbon).exec_(bar.mapToGlobal(pos)))
    more = QToolButton(ribbon)
    more.setObjectName("ribbonMoreTabs")
    more.setText("⋯")
    more.setAutoRaise(True)
    more.setToolTip(language.tr(
        "Show or hide tabs (also: right-click any tab)"))
    more.clicked.connect(lambda: menu(ribbon).exec_(
        more.mapToGlobal(more.rect().bottomLeft())))
    ribbon.more_tabs = more
    apply(ribbon)
    return more
