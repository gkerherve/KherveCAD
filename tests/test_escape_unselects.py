"""Esc with no tool running unselects everything (2026-11-01, the user).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtTest import QTest

from test_lever_by_mouse import win  # noqa: F401


def test_escape_clears_the_selection(win):
    from khervecad import stop_tool
    cube = win.model.add_node("cube", dict(width=10, depth=10, height=10))
    tree = win.builder.active_tree()
    tree.select_nodes([cube])
    QTest.qWait(30)
    assert tree.selected_nodes()
    stop_tool.escape(win)
    QTest.qWait(30)
    assert not tree.selected_nodes()
    assert not win.view2d.scene().selectedItems()


def test_user_interface_left_the_view_menu():
    from khervecad import interface_menus
    text = repr(interface_menus.SOLIDWORKS)
    assert "User Interface" not in text
