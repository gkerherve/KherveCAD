"""Help ▸ User Guide: the full manual, with screenshots.

A chapter list on the left, the manual on the right, a search box on
top. The chapters (userguide_content.py) are one HTML document, so
search finds a word anywhere and the list just scrolls to an anchor.
Screenshots live in ``khervecad/help/`` — regenerate them with
``packaging/make_help_screenshots.py`` after a UI change — and the
Tool reference chapter is built from the very table the toolbar
tooltips use (tooltips.py), with each tool's real icon, so the manual
and the tooltips cannot drift apart.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from pathlib import Path

from PyQt5.QtCore import QSize, Qt, QUrl
from PyQt5.QtGui import QKeySequence, QTextDocument
from PyQt5.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout,
                             QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QShortcut, QSplitter,
                             QTextBrowser, QVBoxLayout)

from . import APP_NAME, __version__

#: screenshots shipped with the package (PyInstaller datas: see the spec)
HELP_DIR = Path(__file__).resolve().parent / "help"

#: the widest a screenshot is shown, in pixels
IMAGE_WIDTH = 760

_CSS = """
h1 { color: #3776ab; }
h2 { color: #3776ab; margin-top: 18px; }
h3 { color: #b35f22; margin-top: 12px; }
p, li { line-height: 135%; }
td { padding: 3px 6px; vertical-align: top; }
.cap { color: #777777; font-size: small; }
.key { background: #eeeeee; font-family: monospace; }
.tip { color: #555555; }
"""


def figure(name, caption="", width=IMAGE_WIDTH):
    """A screenshot with a caption. A missing image is left out rather
    than drawn as a broken box (a source checkout that never ran the
    screenshot script)."""
    path = HELP_DIR / f"{name}.png"
    if not path.is_file():
        return ""
    from PyQt5.QtGui import QImageReader
    size = QImageReader(str(path)).size()
    w = min(width, size.width()) if size.isValid() else width
    cap = f"<br><span class='cap'>{caption}</span>" if caption else ""
    return (f"<p align='center'><img src='{name}.png' width='{w}'>"
            f"{cap}</p>")


def kbd(keys):
    return f"<span class='key'>&nbsp;{keys}&nbsp;</span>"


def _tool_reference():
    """The Tool reference chapter: every toolbar tool, its icon, what it
    does, how to use it — straight from tooltips.TIPS."""
    from . import tooltips, toolbars
    from .model import NODE_TYPES
    sections = [
        ("Drawing tools (left toolbar, top)",
         [(t[0], t[1], t[3]) for t in toolbars.TOOLS
          + toolbars.MEASURE_TOOLS]),
        ("3D solids (left toolbar, bottom)",
         [(p, NODE_TYPES[p]["icon"], "") for p in toolbars.PRIMITIVES]),
    ]
    for key, ops in toolbars.OPERATION_GROUPS:
        title, blurb = tooltips.GROUPS[key]
        sections.append((f"{title} — {blurb} (main toolbar)",
                         [(op, NODE_TYPES[op]["icon"],
                           "Ctrl+G" if op == "union" else "")
                          for op in ops]))
    sections.append(("The rest of the main toolbar", [
        ("new", "mdi.file-outline", "Ctrl+N"),
        ("open", "mdi.folder-open-outline", "Ctrl+O"),
        ("save", "mdi.content-save-outline", "Ctrl+S"),
        ("undo", "mdi.undo", "Ctrl+Z"), ("redo", "mdi.redo", "Ctrl+Y"),
        ("snap_objects", "mdi.magnet-on", "J"),
        ("grid", "mdi.grid", "Ctrl+'"),
        ("grid_snap", "mdi.magnet", "Ctrl+Shift+'"),
        ("grid_size", None, ""), ("plane", None, ""),
        ("fit_sketch", "mdi.fit-to-page-outline", "Ctrl+Shift+F"),
        ("render", "mdi.play-outline", "F5"),
        ("fit_3d", "mdi.arrow-expand-all", "Ctrl+F"),
        ("vibe_model", "mdi.creation", "Ctrl+Shift+M")]))
    out, icons_used = [], []
    for heading, items in sections:
        out.append(f"<h3>{heading}</h3><table width='100%'>")
        for key, glyph, keys in items:
            title, what, steps, tip = tooltips.entry(key)
            icon = f"<img src='icon:{glyph}' width='24'>" if glyph else ""
            if glyph:
                icons_used.append(glyph)
            body = [f"<b>{title}</b>" + (f" &nbsp;{kbd(keys)}" if keys
                                         else ""), f"<br>{what}"]
            if steps:
                body.append("<ol style='margin-top:2px'>" + "".join(
                    f"<li>{s}</li>" for s in steps) + "</ol>")
            if tip:
                body.append(f"<span class='tip'><i>Tip:</i> {tip}</span>")
            out.append(f"<tr><td width='34'>{icon}</td>"
                       f"<td>{''.join(body)}</td></tr>")
        out.append("</table>")
    return "".join(out), icons_used


def build_html():
    """(title, anchor) chapters and the whole manual as one HTML page,
    plus the icon names the page references."""
    from .userguide_content import chapters
    reference, icons_used = _tool_reference()
    parts = [f"<h1><span style='color:#3776ab'>Kherve</span><span "
             f"style='color:#e07b39'>CAD</span> User Guide</h1>"
             f"<p class='cap'>Version {__version__}</p>"]
    toc = []
    for n, (anchor, title, html) in enumerate(chapters(), 1):
        if html == "@reference":
            html = reference
        toc.append((f"{n}. {title}", anchor))
        parts.append(f"<a name='{anchor}'></a><h2>{n}. {title}</h2>"
                     f"{html}")
    parts.append("<hr><p class='cap'>KherveCAD by Gwilherm Kerherve "
                 "&mdash; part of the Kherve family of native scientific "
                 "apps. GPL-3.0.</p>")
    return toc, "".join(parts), icons_used


class UserGuideDialog(QDialog):
    """The manual: chapters, search, screenshots."""

    def __init__(self, parent=None, chapter=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} — User Guide")
        self.resize(1120, 800)
        toc, html, icons_used = build_html()

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search the guide (Enter = next "
                                       "match)")
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(self.find_next)
        self.search.textChanged.connect(lambda _t: self.find_next(True))
        self.status = QLabel("")

        self.chapters = QListWidget()
        self.chapters.setMinimumWidth(290)
        for title, anchor in toc:
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, anchor)
            self.chapters.addItem(item)
        self.chapters.currentItemChanged.connect(
            lambda item, _old: item and self.browser.scrollToAnchor(
                item.data(Qt.UserRole)))

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setSearchPaths([str(HELP_DIR)])
        doc = self.browser.document()
        doc.setDefaultStyleSheet(_CSS)
        from . import icons
        for glyph in set(icons_used):
            pix = icons.icon(glyph).pixmap(QSize(48, 48))
            doc.addResource(QTextDocument.ImageResource,
                            QUrl(f"icon:{glyph}"), pix)
        self.browser.setHtml(html)

        top = QHBoxLayout()
        top.addWidget(self.search, 1)
        top.addWidget(self.status)
        split = QSplitter(Qt.Horizontal)
        split.addWidget(self.chapters)
        split.addWidget(self.browser)
        split.setStretchFactor(1, 1)
        split.setSizes([300, 820])
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(split, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        QShortcut(QKeySequence.Find, self, self.search.setFocus)
        QShortcut(QKeySequence.FindNext, self, self.find_next)
        if chapter:
            self.show_chapter(chapter)

    def show_chapter(self, anchor):
        for row in range(self.chapters.count()):
            if self.chapters.item(row).data(Qt.UserRole) == anchor:
                self.chapters.setCurrentRow(row)
                return

    def find_next(self, restart=False):
        """Jump to the next match of the search text, wrapping round."""
        text = self.search.text().strip()
        if not text:
            self.status.setText("")
            return
        if restart:
            cursor = self.browser.textCursor()
            cursor.movePosition(cursor.Start)
            self.browser.setTextCursor(cursor)
        if not self.browser.find(text):
            cursor = self.browser.textCursor()
            cursor.movePosition(cursor.Start)
            self.browser.setTextCursor(cursor)
            if not self.browser.find(text):
                self.status.setText("not found")
                return
        self.status.setText("")


def show_user_guide(parent=None, chapter=None):
    """Non-modal, so the guide can stay open beside the model."""
    dlg = UserGuideDialog(parent, chapter)
    dlg.setAttribute(Qt.WA_DeleteOnClose)
    dlg.show()
    return dlg
