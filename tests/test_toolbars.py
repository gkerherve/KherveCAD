"""The toolbars: grouped operation families and how-to tooltips.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication

from khervecad import tooltips, toolbars
from khervecad.model import NODE_TYPES


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    yield win
    win._dirty = False
    win.close()


def test_every_operation_is_in_exactly_one_family():
    ops = [op for _key, family in toolbars.OPERATION_GROUPS
           for op in family]
    assert len(ops) == len(set(ops)) >= 21     # no duplicates, nothing lost
    assert all(op in NODE_TYPES for op in ops)
    assert all(key in tooltips.GROUPS
               for key, _family in toolbars.OPERATION_GROUPS)


def test_every_tool_has_a_written_tip():
    keys = ([t[0] for t in toolbars.TOOLS + toolbars.MEASURE_TOOLS]
            + toolbars.PRIMITIVES + toolbars.OPERATIONS)
    missing = [k for k in keys if k not in tooltips.TIPS]
    assert not missing
    for key in keys:
        title, what, steps, _tip = tooltips.TIPS[key]
        assert title and len(what) > 30, key
        assert steps, f"{key} has no how-to steps"


def test_rich_tip_is_fixed_width_html_with_steps():
    tip = tooltips.rich("difference", "Ctrl+G")
    assert tip.startswith("<table width=")
    assert "<ol" in tip and "How to use" in tip and "Ctrl+G" in tip
    assert "<" not in tooltips.summary("while_loop").split("—")[0]


def test_unknown_key_falls_back_to_the_node_label():
    title, what, _steps, _tip = tooltips.entry("hull")
    assert title == NODE_TYPES["hull"]["label"]


def test_toolbar_icons_carry_rich_tooltips(window):
    from PyQt5.QtWidgets import QWidgetAction
    checked = 0
    for bar in (window._tools_bar, window._options_bar):
        for act in bar.actions():
            if act.isSeparator() or isinstance(act, QWidgetAction):
                continue                    # labels, spin box, groups
            assert act.toolTip().startswith("<table"), act.text()
            assert act.statusTip(), act.text()
            checked += 1
    assert checked >= 25
    for button in window._op_groups.values():
        assert button.toolTip().startswith("<table")


def test_group_button_runs_and_remembers_the_last_tool(window):
    QSettings("Kherve", "KherveCAD").remove("toolbar/transform")
    button = window._op_groups["transform"]
    assert button.defaultAction().data() == "translate"
    scale = next(a for a in button.family if a.data() == "scale")
    scale.trigger()                     # picked from the drop-down
    assert button.defaultAction() is scale
    assert "Scale" in button.toolTip() and "arrow lists" in button.toolTip()
    assert QSettings("Kherve", "KherveCAD").value(
        "toolbar/transform") == "scale"
    QSettings("Kherve", "KherveCAD").remove("toolbar/transform")


def test_group_action_wraps_the_selection(window):
    node = window.model.add_node("cube")
    tree = window.builder.active_tree()
    tree.select_nodes([node])
    window._op_groups["combine"].family[0].trigger()        # Group
    assert node.parent.type == "union"
    QSettings("Kherve", "KherveCAD").remove("toolbar/combine")
