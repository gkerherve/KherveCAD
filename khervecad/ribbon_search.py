"""The ribbon's command search (2026-10-20, the user: "after the last
ribbon, a search where you type what you're looking for, like
blueprint, and that shows you exactly where it is located").

A box after the last tab. Typing lists every ribbon command whose name
(or help text) holds the words, as "Blueprint — INSPECT ▸ Documents";
picking one brings its tab to the front and flashes its button (or the
panel's ▾ label when the command sits in the panel's list), and says
where it is in the status bar. Enter on a single match does the same.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import re

from PyQt5.QtCore import QStringListModel, Qt, QTimer
from PyQt5.QtWidgets import QCompleter, QLineEdit, QToolButton

from . import icons, language

#: how long a found button stays lit (ms)
FLASH_MS = 1800
FLASH_STYLE = ("QToolButton { background: #ffd27a; border: 2px solid "
               "#f08a24; border-radius: 3px; }")


def _plain(text):
    from .ribbon import short_name
    return short_name(text)


def entries(ribbon):
    """[(label, tab index, panel title, action)] for every command."""
    from . import ribbon as rb
    out, seen = [], set()
    for i, (_key, _f, _s, panels) in enumerate(getattr(ribbon, "order", rb.TABS)):
        tab = ribbon.tabs.tabText(i).replace("&", "")
        for panel in panels:
            title, acts = rb.panel_actions(ribbon.win, panel)
            for act in acts:
                name = _plain(act.text())
                if not name or (name, i) in seen:
                    continue
                seen.add((name, i))
                out.append((f"{name} — {tab} ▸ {title}", i, title, act))
    return out


def matches(items, text):
    """Items whose name, place or help holds every typed word."""
    words = [w for w in re.split(r"\s+", text.lower()) if w]
    found = []
    for item in items:
        label, _i, _t, act = item
        hay = (label + " " + re.sub("<[^>]+>", " ", act.toolTip() or "")
               ).lower()
        if all(w in hay for w in words):
            # names that START with the words first
            first = label.lower().startswith(words[0]) if words else False
            found.append((not first, label, item))
    return [f[2] for f in sorted(found, key=lambda f: (f[0], f[1]))]


class SearchBox(QLineEdit):
    def __init__(self, ribbon):
        super().__init__(ribbon)
        self.ribbon = ribbon
        self.setObjectName("ribbonSearch")
        self.setPlaceholderText(language.tr("Search commands"))
        self.setClearButtonEnabled(True)
        art = icons.icon("mdi.magnify", "#6e6e6e")
        if not art.isNull():
            self.addAction(art, QLineEdit.LeadingPosition)
        self.setFixedWidth(220)
        self.setToolTip(language.tr(
            "Type a command (blueprint, fillet, loft…) to see which tab "
            "and panel it is on; pick it to jump there."))
        self._items = None
        self._model = QStringListModel(self)
        self._completer = QCompleter(self._model, self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.setMaxVisibleItems(12)
        self._completer.activated[str].connect(self.locate_label)
        self.setCompleter(self._completer)
        self.textEdited.connect(self._refresh)
        self.returnPressed.connect(self._enter)

    def items(self):
        if self._items is None:
            self._items = entries(self.ribbon)
        return self._items

    def _refresh(self, text):
        # the list holds what matches by name OR by help text, so
        # "drawing" finds the Blueprint too
        found = matches(self.items(), text) if text.strip() else []
        self._model.setStringList([f[0] for f in found])
        self._completer.setCompletionPrefix("")
        self._completer.setFilterMode(Qt.MatchContains)
        if found:
            self._completer.complete()

    def _enter(self):
        found = matches(self.items(), self.text())
        if found:
            self.locate(found[0])

    def locate_label(self, label):
        for item in self.items():
            if item[0] == label:
                self.locate(item)
                return

    def locate(self, item):
        """Bring the command's tab forward and light its button."""
        label, index, panel, act = item
        rb = self.ribbon
        rb.tabs.setCurrentIndex(index)
        page = rb.stack.widget(index)
        target = None
        for b in page.findChildren(QToolButton):
            if b.defaultAction() is act:
                target = b
                break
        if target is None:                 # only in the panel's ▾ list
            for b in page.findChildren(QToolButton):
                if b.objectName() == "panelLabel" and b.menu() and \
                        act in b.menu().actions():
                    target = b
                    break
        if target is not None:
            flash(target)
        where = label.split(" — ", 1)[-1]
        name = label.split(" — ", 1)[0]
        msg = language.tr("{name} is on {where}").format(name=name,
                                                         where=where)
        rb.win.statusBar().showMessage(msg, 6000)
        self.setText(name)
        return target


def flash(button):
    old = button.styleSheet()
    button.setStyleSheet(FLASH_STYLE)
    QTimer.singleShot(FLASH_MS, lambda: button.setStyleSheet(old))
