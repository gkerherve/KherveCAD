"""Deleting a node that holds others (2026-10-21, the user: deleting a
Difference took the extrude and polygon inside it with it — "I want a
choice to remove all under difference or to keep the rest").

`delete_nodes` asks once when any of the nodes is a container with
something inside: **Keep what's inside** (the node goes, its children
take its place — `DocumentModel.ungroup`), **Delete everything**, or
Cancel. Leaves are deleted without a question, as before. Used by the
tree's right-click Delete, the Delete key and Edit ▸ Delete.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

KEEP, ALL, CANCEL = "keep", "all", "cancel"

#: tests (and an MCP-free caller) may answer instead of the dialog
ask_hook = None


def _holders(nodes):
    return [n for n in nodes if n.is_container() and n.children
            and n.type not in ("root",)]


def ask(parent, nodes):
    """KEEP, ALL or CANCEL for deleting *nodes* that hold others."""
    if ask_hook is not None:
        return ask_hook(nodes)
    from PyQt5.QtWidgets import QMessageBox
    from . import language
    holders = _holders(nodes)
    if len(holders) == 1:
        h = holders[0]
        inside = ", ".join(c.name for c in h.children[:3]) + (
            "…" if len(h.children) > 3 else "")
        text = language.tr("“{name}” holds {inside}.").format(
            name=h.name, inside=inside)
    else:
        text = language.tr("{n} of the selected objects hold others.") \
            .format(n=len(holders))
    box = QMessageBox(parent)
    box.setWindowTitle(language.tr("Delete"))
    box.setIcon(QMessageBox.Question)
    box.setText(text)
    box.setInformativeText(language.tr(
        "Delete only the operation and keep what is inside it, or "
        "delete everything?"))
    keep = box.addButton(language.tr("Keep what's inside"),
                         QMessageBox.AcceptRole)
    every = box.addButton(language.tr("Delete everything"),
                          QMessageBox.DestructiveRole)
    box.addButton(QMessageBox.Cancel)
    box.setDefaultButton(keep)
    box.exec_()
    clicked = box.clickedButton()
    return KEEP if clicked is keep else ALL if clicked is every \
        else CANCEL


def delete_nodes(parent, model, nodes):
    """Delete *nodes*, asking first when one holds others. Returns the
    choice made (KEEP / ALL / CANCEL, or ALL for plain leaves)."""
    nodes = [n for n in nodes if n is not None and n.parent is not None]
    if not nodes:
        return CANCEL
    choice = ask(parent, nodes) if _holders(nodes) else ALL
    if choice == CANCEL:
        return choice
    for node in nodes:
        if choice == KEEP and node.is_container() and node.children:
            model.ungroup(node)
        else:
            model.remove_node(node)
    return choice
