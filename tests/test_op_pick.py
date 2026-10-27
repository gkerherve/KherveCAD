# Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later
"""Every solid tool picks its part in 3D when nothing is selected, like
Fillet; Combine takes the body and then the others; the Options gear
is on the top bar."""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import op_pick, options_dialog
from khervecad.mcp_tools import McpToolExecutor


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    ex = McpToolExecutor(win)
    ex.execute("apply_code", {"code": "cube(10);\n"
                                      "translate([20, 0, 0]) sphere(5);"})
    win.builder.active_tree().select_nodes([])
    yield win
    win._dirty = False
    win.close()


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _run(window, op, monkeypatch):
    calls = []
    monkeypatch.setattr(window.view3d, "start_pick",
                        lambda cb, groups=None, **k: calls.append((cb, groups)))
    window._apply_operation(op)
    picks = 0
    while calls:
        cb, groups = calls.pop(0)
        if groups and picks < op_pick.MULTI.get(op, 1):
            picks += 1
            cb({"kind": "face"}, groups[0][0])
        else:
            cb(None, None)                   # Done / Esc
    return [n for n in _walk(window.model.root) if n.type == op]


@pytest.mark.parametrize("op", ["hull", "translate", "subdivide",
                                "difference", "union"])
def test_a_click_in_3d_applies_the_tool(window, op, monkeypatch):
    made = _run(window, op, monkeypatch)
    assert made
    if op in op_pick.MULTI:
        assert len(made[0].children) == 2    # the body and the other


def test_combine_waits_for_a_second_body(window, monkeypatch):
    calls = []
    monkeypatch.setattr(window.view3d, "start_pick",
                        lambda cb, groups=None, **k: calls.append((cb, groups)))
    window._apply_operation("difference")
    cb, groups = calls.pop()
    cb({"kind": "face"}, groups[0][0])
    cb2, _groups = calls.pop()
    cb2(None, None)                          # Done with one body: nothing
    assert not [n for n in _walk(window.model.root)
                if n.type == "difference"]


def test_the_options_gear_is_on_the_top_bar(window):
    act = options_dialog.action(window)
    assert act in window._options_bar.actions()
