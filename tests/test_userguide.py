"""The User Guide: chapters, screenshots and the tool reference.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import re

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import tooltips, toolbars, userguide
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
