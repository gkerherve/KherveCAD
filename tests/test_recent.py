"""Tests for the Open Recent files list and menu.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    # Isolate the recent-files list from the real user registry so the
    # test neither reads nor clobbers a developer's actual recents.
    QSettings("Kherve", "KherveCAD").setValue("recent_files", [])
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    yield w
    QSettings("Kherve", "KherveCAD").setValue("recent_files", [])


def test_add_moves_to_front_without_duplicates(window):
    window._add_recent(r"C:\tmp\alpha.kcad")
    window._add_recent(r"C:\tmp\beta.kcad")
    window._add_recent(r"C:\tmp\alpha.kcad")   # re-open jumps to front
    files = window._recent_files()
    assert len(files) == 2
    assert files[0].endswith("alpha.kcad")
    assert files[1].endswith("beta.kcad")


def test_list_is_capped(window):
    for i in range(window._MAX_RECENT + 5):
        window._add_recent(rf"C:\tmp\file{i}.kcad")
    assert len(window._recent_files()) == window._MAX_RECENT
    # The most recently added is first.
    newest = window._MAX_RECENT + 4
    assert window._recent_files()[0].endswith(f"file{newest}.kcad")


def test_empty_string_is_ignored(window):
    window._add_recent("")
    window._add_recent(None)
    assert window._recent_files() == []


def test_forget_and_clear(window):
    window._add_recent(r"C:\tmp\a.kcad")
    window._add_recent(r"C:\tmp\b.kcad")
    window._forget_recent(r"C:\tmp\a.kcad")
    assert [Path(f).name for f in window._recent_files()] == ["b.kcad"]
    window._clear_recent()
    assert window._recent_files() == []


def test_menu_reflects_the_list(window):
    window._add_recent(r"C:\tmp\alpha.kcad")
    window._add_recent(r"C:\tmp\beta.kcad")
    window._rebuild_recent_menu()
    texts = [a.text() for a in window.recent_menu.actions() if a.text()]
    # Newest first: beta was added last, so it heads the list.
    assert "beta.kcad" in texts[0]
    assert "alpha.kcad" in texts[1]
    assert any("Clear Recent Files" in t for t in texts)


def test_empty_menu_shows_placeholder(window):
    window._rebuild_recent_menu()
    acts = window.recent_menu.actions()
    assert len(acts) == 1
    assert not acts[0].isEnabled()
    assert "no recent" in acts[0].text().lower()
