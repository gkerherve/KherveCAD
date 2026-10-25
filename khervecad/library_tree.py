"""The Part Library window's tree, organised EXACTLY like the Library
menu (2026-10-25, the user: "reorganise the part library by sections and
menus, just like in the menu"): it is read from that menu, so the two
never disagree — section headers (ENGINEERING, BUILDINGS & PLACES ...)
are top-level rows, each submenu a folder, each part a leaf. Builders
and examples are left out (the window inserts parts). Without a window
menu (tests, a bare dialog) it falls back to one folder per category in
the menu's order.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QTreeWidgetItem

PART = Qt.UserRole


def _clean(text):
    return text.replace("&&", "\0").replace("&", "").replace("\0", "&") \
        .split("\t")[0].strip()


def _walk(menu, parent, parts):
    """Add *menu*'s parts and submenus under *parent*; True when any
    part landed."""
    got = False
    section = parent
    for act in menu.actions():
        if act.isSeparator():
            continue
        sub = act.menu()
        data = act.data()
        if sub is not None:
            item = QTreeWidgetItem([_clean(act.text())])
            if _walk(sub, item, parts):
                section.addChild(item) if hasattr(section, "addChild") \
                    else section.addTopLevelItem(item)
                got = True
        elif isinstance(data, str) and data.startswith("part:"):
            pid = data[5:]
            if pid in parts:
                item = QTreeWidgetItem([parts[pid]["label"]])
                item.setData(0, PART, pid)
                section.addChild(item) if hasattr(section, "addChild") \
                    else section.addTopLevelItem(item)
                got = True
        elif not act.isEnabled() and act.text().strip() and \
                not hasattr(parent, "addChild"):
            # a section header of the top menu: a bold top-level row
            item = QTreeWidgetItem([_clean(act.text())])
            font = QFont(item.font(0))
            font.setBold(True)
            item.setFont(0, font)
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            parent.addTopLevelItem(item)
            section = item
    return got


def _prune(tree):
    """Drop section rows left without parts."""
    for i in reversed(range(tree.topLevelItemCount())):
        item = tree.topLevelItem(i)
        if item.childCount() == 0 and item.data(0, PART) is None:
            tree.takeTopLevelItem(i)


def fill(tree, window, parts):
    """Fill *tree* from the window's Library menu, or by category."""
    tree.clear()
    menu = getattr(window, "_library_menu", None)
    if menu is not None:
        _walk(menu, tree, parts)
        _prune(tree)
    if tree.topLevelItemCount() == 0:
        from .library_groups import category_order
        by_cat = {}
        for pid, spec in parts.items():
            by_cat.setdefault(spec.get("category", "Other"), []).append(pid)
        for cat in category_order(list(by_cat)):
            folder = QTreeWidgetItem([cat])
            for pid in by_cat[cat]:
                leaf = QTreeWidgetItem([parts[pid]["label"]])
                leaf.setData(0, PART, pid)
                folder.addChild(leaf)
            tree.addTopLevelItem(folder)


def leaves(tree):
    out = []

    def walk(item):
        if item.data(0, PART):
            out.append(item)
        for i in range(item.childCount()):
            walk(item.child(i))
    for i in range(tree.topLevelItemCount()):
        walk(tree.topLevelItem(i))
    return out


def filter_tree(tree, text):
    """Show the parts whose label holds every word of *text*, with their
    folders opened; an empty text shows all, folded."""
    words = text.lower().split()

    def walk(item):
        pid = item.data(0, PART)
        if pid:
            show = all(w in item.text(0).lower() for w in words)
        else:
            show = False
            for i in range(item.childCount()):
                show = walk(item.child(i)) or show
            if words and show:
                item.setExpanded(True)
        item.setHidden(bool(words) and not show)
        return show
    for i in range(tree.topLevelItemCount()):
        top = tree.topLevelItem(i)
        walk(top)
        if not words:
            top.setHidden(False)
