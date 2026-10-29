"""Tools ▸ Options as SolidWorks lays it out (2026-10-29, the user: theme
and interface style moved here, and what SolidWorks' Options have).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os

from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest

from khervecad import interface_menus, options_dialog
from test_lever_by_mouse import win  # noqa

SHOTS = os.environ.get("KHERVECAD_SHOTS")


def test_theme_and_style_left_the_view_menu(win):
    view = next(a.menu() for a in win.menuBar().actions()
                if a.text().replace("&", "") == "View")
    texts = [a.text().replace("&", "") for a in view.actions()]
    assert "Theme" not in texts and "Interface Style" not in texts
    assert not interface_menus.missing(win)


def test_every_page_opens_and_a_switch_is_the_menus_own(win):
    dlg = options_dialog.OptionsDialog(win)
    assert dlg.PAGES[:2] == ("General", "Display")
    for row, name in enumerate(dlg.PAGES):
        dlg.setCurrentRow(row)
        assert dlg.stack.currentIndex() == row
        if SHOTS:
            dlg.show()
            QTest.qWait(50)
            dlg.grab().save(os.path.join(
                SHOTS, "options-%d-%s.png" % (row, name.lower().replace(
                    " ", "-"))))
    paths = interface_menus.index(win)
    edges = paths["view/3d edge lines"]
    was = edges.isChecked()
    box = next(b for b, a in dlg._checks if a is edges)
    dlg.setCurrentRow(dlg.PAGES.index("Display"))
    dlg.show()
    QTest.qWait(30)
    box.click()                        # as a click on it
    assert box.isChecked() is (not was)
    dlg.apply()
    assert edges.isChecked() is (not was)
    # a drop-down of the menu's choices: the projection
    combo = next(c for c, acts in dlg._choices
                 if any("projection" in p for p in acts))
    combo.setCurrentIndex(combo.findData("view/3d projection/orthographic"))
    dlg.apply()
    assert win.view3d.projection == "Orthographic"
    # Document Properties: open_dialog(win, 1) opens its first page
    assert options_dialog.OptionsDialog.DOCUMENT == dlg.PAGES.index("Units")
    dlg.close()


def test_material_and_grid_apply(win):
    dlg = options_dialog.OptionsDialog(win)
    dlg.material.setCurrentIndex(dlg.material.findData("Aluminium")
                                 if dlg.material.findData("Aluminium") >= 0
                                 else 1)
    chosen = dlg.material.currentData()
    dlg.grid.setText("2.5")
    dlg.apply()
    from khervecad import massbar
    assert massbar.material_of(win.model) == chosen
    assert win.scene.grid_size == 2.5
