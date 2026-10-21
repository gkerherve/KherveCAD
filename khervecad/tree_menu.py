"""The tree's right-click menu, made compact (2026-10-21, the user: "a
more compact way ... menus, submenus, shorter sentences").

`compact(menu)` runs on the finished menu: the everyday commands stay on
top (Edit in Object tab, Hide, Colour, Rename, Duplicate, Group), the
rest go into a few submenus by what they do, long labels are shortened,
and Suppress / Delete stay last. Items are matched by their English
text through `language.tr`, so a translated menu regroups too; anything
unknown stays at the top level, in its place.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import language

#: (submenu title, mdi glyph, label prefixes that go in it)
GROUPS = [
    ("Clipboard", "mdi.content-paste",
     ["Cut", "Copy", "Paste", "Linked copy"]),
    ("Position", "mdi.anchor",
     ["Anchors", "Snap by clicking faces", "Snap by faces", "Attach", "Detach",
      "Drop", "Reach", "Set origin"]),
    ("Modify", "mdi.auto-fix",
     ["Apply", "Edit Vertices", "Edit vertices", "Sculpt", "Paint", "Split for print",
      "Debug modifier", "Imported mesh", "Make Sizes Equal", "Pick edges",
      "Unfold", "Export flat pattern", "Convert"]),
    ("Organise", "mdi.file-tree",
     ["Ungroup", "Make Object", "Insert Object", "Move to Collection",
      "Roll back to here", "Roll forward"]),
]

#: kept on top, in this order, before the submenus
TOP = ["Edit in Object tab", "Hide", "Show", "Color", "Colour", "Rename",
       "Duplicate", "Group"]
#: kept last, in this order
LAST = ["Suppress", "Unsuppress", "Delete, keep contents", "Delete all",
        "Delete"]

#: long labels -> short ones
SHORT = {
    "Linked copy (updates with the original)": "Linked copy",
    "Edit Vertices (Edit Mode)": "Edit vertices",
    "Snap by clicking faces": "Snap by faces",
    "Attach / snap to…": "Attach to…",
    "Attach / snap to...": "Attach to…",
    "Debug modifier (OpenSCAD)": "Debug modifier",
    "Split for printing…": "Split for print…",
    "Split for printing...": "Split for print…",
    "Edit in Object tab": "Edit in Object tab",
}


def _plain(text):
    return text.split("\t")[0].replace("&", "").strip()


def _starts(text, prefixes):
    for p in prefixes:
        if text.startswith(language.tr(p)) or text.startswith(p):
            return True
    return False


def _shorten(act):
    text = act.text()
    head, tab, keys = text.partition("\t")
    for long, short in SHORT.items():
        if head.strip() in (long, language.tr(long)):
            act.setText(language.tr(short) + (tab + keys if tab else ""))
            return


def compact(menu):
    """Regroup *menu* in place."""
    from PyQt5.QtWidgets import QMenu
    from . import icons
    acts = [a for a in menu.actions() if not a.isSeparator()]
    for a in acts:
        menu.removeAction(a)
    for a in list(menu.actions()):              # the separators
        menu.removeAction(a)
    top, last, rest = [], [], []
    groups = {g[0]: [] for g in GROUPS}
    for a in acts:
        _shorten(a)
        t = _plain(a.text())
        if a.menu() is None and _starts(t, LAST) and \
                not t.startswith(language.tr("Delete constraint")):
            last.append(a)
        elif _starts(t, TOP) and not _starts(t, ["Group part"]) and \
                not any(_starts(t, g[2]) for g in GROUPS
                        if g[0] == "Organise"):
            top.append(a)
        else:
            for title, _glyph, prefixes in GROUPS:
                if _starts(t, prefixes):
                    groups[title].append(a)
                    break
            else:
                rest.append(a)
    order = {p: i for i, p in enumerate(TOP)}
    top.sort(key=lambda a: next((order[p] for p in TOP
                                 if _starts(_plain(a.text()), [p])), 99))
    for a in top:
        menu.addAction(a)
    menu.addSeparator()
    for title, glyph, _p in GROUPS:
        items = groups[title]
        if not items:
            continue
        if len(items) == 1 and items[0].menu() is None:
            menu.addAction(items[0])          # one item needs no submenu
            continue
        sub = QMenu(language.tr(title), menu)
        sub.setIcon(icons.icon(glyph))
        for a in items:
            sub.addAction(a)
        menu.addMenu(sub)
    if rest:
        menu.addSeparator()
        for a in rest:
            menu.addAction(a)
    if last:
        menu.addSeparator()
        last.sort(key=lambda a: next((i for i, p in enumerate(LAST)
                                      if _starts(_plain(a.text()), [p])), 99))
        for a in last:
            menu.addAction(a)
    return menu
