"""The User Guide: chapters, screenshots and the tool reference.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import re

import pytest
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication

from khervecad import language, tooltips, toolbars, userguide
from khervecad.userguide_content import chapters


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_chapters_have_unique_anchors_and_content(app):
    items = chapters()
    anchors = [a for a, _t, _h in items]
    assert len(anchors) == len(set(anchors)) >= 20
    for anchor, title, html in items:
        assert title and (html == "@reference" or len(html) > 300), anchor


def test_every_screenshot_the_guide_names_is_shipped(app):
    """figure() silently drops a missing image, so a renamed screenshot
    would vanish from the manual unnoticed — check the names here."""
    names = set()
    source = "".join(h for _a, _t, h in chapters())
    names.update(re.findall(r"img src='([\w\-]+\.png)'", source))
    import inspect
    from khervecad import userguide_content
    code = inspect.getsource(userguide_content)
    wanted = set(re.findall(r'figure\("([\w\-]+)"', code))
    assert len(wanted) >= 25
    missing = [n for n in sorted(wanted)
               if not (userguide.HELP_DIR / f"{n}.png").is_file()]
    assert not missing, f"run packaging/make_help_screenshots.py: {missing}"


def test_reference_covers_every_toolbar_tool(app):
    toc, html, icons_used = userguide.build_html()
    keys = ([t[0] for t in toolbars.TOOLS + toolbars.MEASURE_TOOLS]
            + toolbars.PRIMITIVES + toolbars.OPERATIONS)
    for key in keys:
        title = tooltips.entry(key)[0]
        assert f"<b>{title}</b>" in html, key
    assert "@reference" not in html
    assert len(icons_used) >= len(keys)
    assert [a for _t, a in toc][:2] == ["welcome", "first-part"]


def test_dialog_searches_and_jumps(app):
    dlg = userguide.UserGuideDialog(chapter="assemblies")
    assert dlg.chapters.currentItem().data(0x0100) == "assemblies"
    dlg.search.setText("Difference")
    assert dlg.browser.textCursor().hasSelection()
    dlg.search.setText("zzzz-not-in-the-guide")
    assert dlg.status.text() == "not found"
    # the tool icons are registered as document resources
    doc = dlg.browser.document()
    from PyQt5.QtCore import QUrl
    from PyQt5.QtGui import QTextDocument
    assert doc.resource(QTextDocument.ImageResource,
                        QUrl("icon:mdi.cube-outline")) is not None
    dlg.close()


@pytest.mark.parametrize("code", ["zh", "fr", "es", "ja"])
def test_translated_chapters_match_english_structure(app, code):
    """Each translated chapters() module must mirror the English one:
    same anchors in the same order, every chapter actually translated
    (not left as a stray copy of the English text), figure()/kbd()
    still wired so no screenshot or shortcut silently vanishes."""
    import importlib
    module = importlib.import_module(f"khervecad.userguide_content_{code}")
    en = chapters()
    translated = module.chapters()
    assert [a for a, _t, _h in translated] == [a for a, _t, _h in en]
    # most titles must actually change; a stray cognate (e.g. French
    # "Collections") is fine, a whole untouched module full of English
    # titles is not
    en_titles = [t for _a, t, _h in en]
    tr_titles = [t for _a, t, _h in translated]
    unchanged = sum(1 for a, b in zip(en_titles, tr_titles) if a == b)
    assert unchanged <= max(2, len(en_titles) // 10)
    for (anchor, title, html), (_a, _t, en_html) in zip(translated, en):
        if html == "@reference":
            assert en_html == "@reference"
            continue
        assert len(html) > 200, anchor
        # the figure() calls must survive translation (same image names,
        # same count) — only their caption text may differ
        assert (re.findall(r'figure\("([\w\-]+)"', html)
                == re.findall(r'figure\("([\w\-]+)"', en_html)), anchor


@pytest.mark.parametrize("code", ["zh", "fr", "es", "ja"])
def test_the_guide_opens_in_every_translated_language(app, code):
    """A language switch actually swaps which chapters() module the
    dialog builds from (userguide._chapters_module reads the same
    QSettings key language.set_language() writes, not the installed
    DictTranslator, so this must work even before install() runs)."""
    settings = QSettings("Kherve", "KherveCAD")
    saved = settings.value("language")
    try:
        settings.setValue("language", code)
        dlg = userguide.UserGuideDialog()
        assert dlg.chapters.count() >= 20
        dlg.close()
    finally:
        if saved is None:
            settings.remove("language")
        else:
            settings.setValue("language", saved)
