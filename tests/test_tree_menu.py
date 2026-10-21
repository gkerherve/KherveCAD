"""The tree's right-click menu stays compact.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtWidgets import QApplication, QMenu


def test_the_menu_is_short_and_grouped(monkeypatch):
    app = QApplication.instance() or QApplication([])
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        m = win.model
        m.make_component(m.add_node("cube", {}))
        app.processEvents()
        tree = win.builder.active_tree()
        tree.select_nodes([m.root.children[-1]])
        app.processEvents()
        shown = []
        monkeypatch.setattr(QMenu, "exec_", lambda self, *a: shown.append(
            [a.text().split("\t")[0] for a in self.actions()
             if not a.isSeparator()]))
        tree._context_menu(tree.visualItemRect(tree.currentItem()).center())
        top = shown[0]
        assert len(top) <= 16, top
        for word in ("Clipboard", "Position", "Modify", "Organise"):
            assert word in top
        assert all(len(t) <= 24 for t in top), top
        assert top[-1] == "Delete all"
    finally:
        win._dirty = False
        win.close()
