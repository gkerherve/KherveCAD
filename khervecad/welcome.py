"""The Welcome window — a replica of SolidWorks' (2026-11-16, the user:
"it shows new part or assembly or drawing ... we need this at the
beginning too").

Tabs Home / Recent / Learn / Alerts. Home: New (Part, Assembly, Drawing,
Advanced...) and Open, Recent Documents as cards with the picture kept
when the file was saved, Recent Folders and Resources. A tip bar closes
it. It opens when the program starts and from File > New (both the menu
and the toolbar button), is NON-modal, and "Show at start-up" turns the
start-up showing off (QSettings `welcome/show_at_start`).

A kcad Part is an Object opened in the Object tab, an Assembly the Main
tab, a Drawing the Blueprint window — the same split the rest of the
program uses.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from pathlib import Path

from PyQt5.QtCore import QRectF, QSettings, QSize, Qt, QTimer, QUrl
from PyQt5.QtGui import (QColor, QDesktopServices, QIcon, QImage, QPainter,
                         QPen, QPixmap)
from PyQt5.QtWidgets import (QAbstractButton, QCheckBox, QComboBox, QDialog,
                             QFileDialog, QFrame, QGridLayout, QHBoxLayout,
                             QLabel, QListWidget, QListWidgetItem,
                             QPushButton, QScrollArea, QStackedWidget,
                             QToolButton, QVBoxLayout, QWidget)

from . import icons, icons_welcome, language, welcome_thumb

SETTINGS = ("Kherve", "KherveCAD")
SITE = "https://khervetools.com"
REPO = "https://github.com/gkerherve/KherveCAD"

TABS = ("Home", "Recent", "Learn", "Alerts")

#: the tip bar's lines, one at a time (left / right arrows)
TIPS = (
    "Arrow keys in the 3D view turn the model; Ctrl + arrows pan it.",
    "Press Ctrl+N at any time to come back to this window.",
    "Everything you draw becomes a node: the Code tab shows the OpenSCAD "
    "program it writes, and editing the code edits the model.",
    "Right-click a face in the 3D view to round, chamfer or sketch on it.",
    "Press Esc to leave any tool and get back to Select.",
    "The status bar's Recent files list opens your last documents.",
)

#: what the Home tab's resources open (label, address)
RESOURCES = (
    ("What's New", "whats_new"),
    ("User Guide", "guide"),
    ("Website", SITE),
    ("Source on GitHub", REPO),
    ("Check for Updates", "updates"),
    ("Get Support", REPO + "/issues"),
)

STYLE = """
QDialog#Welcome { background: #f4f4f4; }
QLabel#Title { font-size: 20px; color: #333; }
QLabel#Section { font-size: 17px; font-weight: bold; color: #222; }
QLabel#Muted { color: #666; }
QFrame#Band { background: #ffffff; border: none; }
QFrame#Line { color: #d6d6d6; }
QPushButton#TabBtn { border: none; background: transparent; color: #666;
  font-size: 19px; padding: 8px 6px; margin: 0 14px; }
QPushButton#TabBtn:checked { color: #2a73b7; font-weight: bold;
  border-bottom: 3px solid #2a73b7; }
QToolButton#NewBtn { border: 1px solid transparent; background: transparent;
  font-size: 17px; color: #333; padding: 6px 10px; }
QToolButton#NewBtn:hover { background: #eaf2fa; border-color: #b9d2ea; }
QPushButton#Advanced { font-size: 17px; padding: 8px 28px;
  background: #ececec; border: 1px solid #8f8f8f; color: #222; }
QPushButton#Advanced:hover { background: #e2eefa; border-color: #2a73b7; }
QToolButton#Card { border: 1px solid #c8c8c8; background: #f1f1f1;
  color: #333; font-size: 13px; padding: 2px; }
QToolButton#Card:hover { border-color: #2a73b7; background: #eaf2fa; }
QPushButton#Link, QToolButton#Link { border: none; background: transparent;
  color: #2a73b7; font-size: 15px; text-align: left; }
QPushButton#Link:hover, QToolButton#Link:hover { text-decoration: underline; }
QToolButton#Item { border: none; background: transparent; color: #222;
  font-size: 15px; text-align: left; padding: 4px; }
QToolButton#Item:hover { background: #eaf2fa; }
QScrollBar:horizontal { height: 14px; background: #ececec; margin: 0; }
QScrollBar::handle:horizontal { background: #c4c4c4; min-width: 40px;
  border-radius: 4px; margin: 2px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal
  { width: 0; height: 0; }
QFrame#Tip { background: #e6eefa; }
QToolButton#TipArrow { border: none; font-size: 18px; color: #555; }
QListWidget { background: #fff; border: none; font-size: 15px; }
QListWidget::item { padding: 6px 10px; }
QListWidget::item:hover { background: #eaf2fa; color: #222; }
QListWidget::item:selected { background: #d5e6f7; color: #222; }
"""


# ── settings ──────────────────────────────────────────────────────────
def show_at_start() -> bool:
    val = QSettings(*SETTINGS).value("welcome/show_at_start", True)
    return str(val).lower() not in ("false", "0", "")


def set_show_at_start(on: bool):
    QSettings(*SETTINGS).setValue("welcome/show_at_start", bool(on))


# ── pictures of documents (welcome_thumb.py) ────────────────────────
def card_pixmap(doc_path):
    """The kept 3D picture of *doc_path*, else None (a stand-in is
    painted by the card until `welcome_thumb.render_file` makes one)."""
    png = welcome_thumb.current(doc_path)
    if png:
        img = QImage(png)
        if not img.isNull():
            return QPixmap.fromImage(img)
    return None


class Card(QAbstractButton):
    """A Recent Documents card: the file name over a framed 3D picture,
    a Part / Assembly badge in its corner — SolidWorks' tile."""

    W, H = 250, 236

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.W, self.H)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(path)
        self.setProperty("path", path)
        self._path = path
        self._pix = None
        self._hover = False
        self._badge = icons_welcome.get(
            "welcome_" + icons_welcome.kind_of(path))
        self.setEnabled(Path(path).exists())

    def set_picture(self, pix):
        self._pix = pix
        self.update()

    def has_picture(self):
        return self._pix is not None

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        edge = QColor("#2a73b7" if self._hover else "#bcbcbc")
        p.setPen(QPen(edge, 1))
        p.setBrush(QColor("#eaf2fa" if self._hover else "#f4f4f4"))
        p.drawRect(0, 0, self.W - 1, self.H - 1)
        p.setPen(QColor("#222") if self.isEnabled() else QColor("#999"))
        font = p.font()
        font.setPixelSize(14)
        p.setFont(font)
        name = p.fontMetrics().elidedText(
            Path(self._path).name, Qt.ElideRight, self.W - 16)
        p.drawText(8, 4, self.W - 16, 24, Qt.AlignVCenter | Qt.AlignLeft,
                   name)
        frame = QRectF(10, 32, self.W - 20, self.H - 44)
        p.setPen(QPen(QColor("#c4c4c4"), 1))
        p.setBrush(QColor("#ffffff"))
        p.drawRect(frame)
        if self._pix is not None:
            pm = self._pix.scaled(
                int(frame.width() - 4), int(frame.height() - 4),
                Qt.KeepAspectRatio, Qt.SmoothTransformation)
            p.drawPixmap(
                int(frame.x() + (frame.width() - pm.width()) / 2),
                int(frame.y() + (frame.height() - pm.height()) / 2), pm)
        else:
            ph = icons_welcome.get("welcome_part")
            p.setOpacity(0.35)
            ph.paint(p, frame.adjusted(60, 30, -60, -30).toRect())
            p.setOpacity(1.0)
        if not self._badge.isNull():
            self._badge.paint(p, int(frame.right() - 34),
                              int(frame.bottom() - 34), 30, 30)
        p.end()


# ── what the buttons do ───────────────────────────────────────────────
KINDS = ("part", "assembly", "drawing")


def new_document(win, kind="part", unit=None) -> bool:
    """A new document of *kind*: a Part (an empty Object open in the
    Object tab), an Assembly (the Main tab) or a Drawing (the Blueprint
    window). False when the user kept the unsaved one."""
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}; use one of {KINDS}")
    if not win._confirm_discard():
        return False
    win._dirty = False                    # new_document must not ask twice
    win.new_document()
    if unit:
        try:
            win.model.set_unit(unit)
            win.model.undo_stack.clear()
            win._dirty = False
        except Exception:
            pass
    if kind == "part":
        win.builder.open_component(
            win.model.new_component("Part1", visible=False))
    elif kind == "assembly":
        win.builder.setCurrentWidget(win.builder._main_page)
    else:
        win.open_blueprint()
    win._update_title()
    return True


def recent_files(win) -> list:
    return [p for p in win._recent_files()]


def recent_folders(win) -> list:
    """The folders of the recent files, newest first, each once."""
    seen, out = set(), []
    for f in recent_files(win):
        d = str(Path(f).parent)
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def learn_examples() -> list:
    """(label, builder) of the numbered Learn tutorials."""
    from .examples import EXAMPLES
    return [(label, build) for label, cat, build in EXAMPLES
            if cat == "Learn"]


def short_folder(path, limit=46) -> str:
    text = path.replace("\\", "/")
    home = str(Path.home()).replace("\\", "/")
    if text.startswith(home):
        text = "~" + text[len(home):]
    if len(text) > limit:
        text = text[:20] + "…" + text[-(limit - 21):]
    return text


# ── pieces ────────────────────────────────────────────────────────────
def _icon(name, colour=None):
    """A painted SolidWorks-style icon (icons_welcome) for the `welcome_`
    keys, else the Material glyph in *colour*."""
    if name.startswith("welcome_"):
        return icons_welcome.get(name)
    return icons.icon(name, colour)


def _line():
    ln = QFrame()
    ln.setObjectName("Line")
    ln.setFrameShape(QFrame.HLine)
    return ln


def _section(text):
    lab = QLabel(language.tr(text))
    lab.setObjectName("Section")
    return lab


class AdvancedDialog(QDialog):
    """New ▸ Advanced... : the kind and the unit in one place."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(language.tr("New KherveCAD Document"))
        self.setStyleSheet(STYLE)
        self.kind = None
        lay = QVBoxLayout(self)
        lay.addWidget(_section("Template"))
        self.list = QListWidget()
        for kind, text, ico in (
                ("part", "Part — one Object, edited in the Object tab",
                 "welcome_part"),
                ("assembly", "Assembly — parts placed and mated in Main",
                 "welcome_assembly"),
                ("drawing", "Drawing — the Blueprint sheet",
                 "welcome_drawing")):
            it = QListWidgetItem(_icon(ico), language.tr(text))
            it.setData(Qt.UserRole, kind)
            self.list.addItem(it)
        self.list.setCurrentRow(0)
        self.list.setIconSize(QSize(32, 32))
        self.list.itemDoubleClicked.connect(lambda _i: self.accept())
        lay.addWidget(self.list)
        row = QHBoxLayout()
        row.addWidget(QLabel(language.tr("Units")))
        self.unit = QComboBox()
        from . import units
        for u in units.UNITS:
            self.unit.addItem(u)
        self.unit.setCurrentText(parent.model.unit
                                 if parent is not None else "mm")
        row.addWidget(self.unit)
        row.addStretch(1)
        lay.addLayout(row)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        ok = QPushButton(language.tr("OK"))
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        cancel = QPushButton(language.tr("Cancel"))
        cancel.clicked.connect(self.reject)
        buttons.addWidget(ok)
        buttons.addWidget(cancel)
        lay.addLayout(buttons)
        self.resize(480, 320)

    def choice(self):
        it = self.list.currentItem()
        return (it.data(Qt.UserRole) if it else "part",
                self.unit.currentText())


class WelcomeDialog(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setObjectName("Welcome")
        self.setStyleSheet(STYLE)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        from . import SHORT_NAME, __version__
        self.setWindowTitle(
            f"{language.tr('Welcome')} - {SHORT_NAME} v{__version__}")
        self.resize(1000, 830)
        self.setMinimumSize(780, 780)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # tab row
        tabs = QHBoxLayout()
        tabs.setContentsMargins(20, 18, 20, 0)
        self._tabs = []
        for i, name in enumerate(TABS):
            b = QPushButton(language.tr(name))
            b.setObjectName("TabBtn")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=i: self.show_tab(k))
            tabs.addWidget(b)
            self._tabs.append(b)
        tabs.addStretch(1)
        outer.addLayout(tabs)
        outer.addWidget(_line())

        self.pages = QStackedWidget()
        self.pages.addWidget(self._home_page())
        self.pages.addWidget(self._recent_page())
        self.pages.addWidget(self._learn_page())
        self.pages.addWidget(self._alerts_page())
        outer.addWidget(self.pages, 1)

        outer.addWidget(self._tip_bar())
        self.show_tab(0)

    # ------------------------------------------------------------ tabs
    def show_tab(self, index):
        self.pages.setCurrentIndex(index)
        for i, b in enumerate(self._tabs):
            b.setChecked(i == index)

    def refresh(self):
        """Rebuild what lists the recent documents (called on show)."""
        self._fill_cards()
        self._fill_folders()
        self._fill_recent_list()
        self._alerts_label.setText(self._alerts_text())

    # ------------------------------------------------------------ home
    def _home_page(self):
        page = QWidget()
        page.setStyleSheet("background:#ffffff;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(36, 18, 36, 0)
        lay.setSpacing(10)

        lay.addWidget(_section("New"))
        row = QHBoxLayout()
        row.setSpacing(18)
        for kind, text, ico in (
                ("part", "Part", "welcome_part"),
                ("assembly", "Assembly", "welcome_assembly"),
                ("drawing", "Drawing", "welcome_drawing")):
            btn = self._big_button(text, ico)
            btn.setObjectName("NewBtn")
            btn.setProperty("kind", kind)
            btn.clicked.connect(lambda _=False, k=kind: self._new(k))
            row.addWidget(btn)
            setattr(self, f"btn_{kind}", btn)
        adv = QPushButton(language.tr("Advanced..."))
        adv.setObjectName("Advanced")
        adv.setCursor(Qt.PointingHandCursor)
        adv.clicked.connect(self._advanced)
        self.btn_advanced = adv
        row.addSpacing(10)
        row.addWidget(adv)
        row.addSpacing(10)
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setObjectName("Line")
        row.addWidget(sep)
        op = self._big_button("Open", "welcome_open")
        op.setObjectName("NewBtn")
        op.clicked.connect(self._open)
        self.btn_open = op
        row.addWidget(op)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(_line())

        head = QHBoxLayout()
        head.addWidget(_section("Recent Documents"))
        head.addStretch(1)
        va = QPushButton(language.tr("View all"))
        va.setObjectName("Link")
        va.setCursor(Qt.PointingHandCursor)
        va.clicked.connect(lambda: self.show_tab(1))
        head.addWidget(va)
        lay.addLayout(head)

        self._cards_host = QWidget()
        self._cards_row = QHBoxLayout(self._cards_host)
        self._cards_row.setContentsMargins(0, 0, 0, 0)
        self._cards_row.setSpacing(16)
        scroll = QScrollArea()
        scroll.setWidget(self._cards_host)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedHeight(268)
        self._cards_scroll = scroll
        lay.addWidget(scroll)

        low = QHBoxLayout()
        low.setSpacing(30)
        left = QVBoxLayout()
        lh = QHBoxLayout()
        lh.addWidget(_section("Recent Folders"))
        lh.addStretch(1)
        left.addLayout(lh)
        self._folders = QVBoxLayout()
        self._folders.setSpacing(2)
        left.addLayout(self._folders)
        left.addStretch(1)
        low.addLayout(left, 1)

        right = QVBoxLayout()
        right.addWidget(_section("Resources"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(30)
        self.resource_buttons = {}
        for i, (label, target) in enumerate(RESOURCES):
            b = QToolButton()
            b.setObjectName("Item")
            b.setText("  " + language.tr(label))
            b.setIcon(_icon(icons_welcome.RESOURCE_KEYS.get(label, "mdi.link"),
                            "#4a7fb5"))
            b.setIconSize(QSize(28, 28))
            b.setMinimumHeight(40)
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, t=target: self._resource(t))
            grid.addWidget(b, i // 2, i % 2)
            self.resource_buttons[label] = b
        right.addLayout(grid)
        right.addStretch(1)
        low.addLayout(right, 1)
        lay.addLayout(low, 1)
        return page

    def _big_button(self, text, ico):
        b = QToolButton()
        b.setText("  " + language.tr(text))
        b.setIcon(_icon(ico))
        b.setIconSize(QSize(56, 56))
        b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        b.setCursor(Qt.PointingHandCursor)
        return b

    def _fill_cards(self):
        lay = self._cards_row
        while lay.count():
            it = lay.takeAt(0)
            if it.widget() is not None:
                it.widget().deleteLater()
        files = recent_files(self.win)
        if not files:
            empty = QLabel(language.tr(
                "No recent documents yet — they will appear here."))
            empty.setObjectName("Muted")
            lay.addWidget(empty)
        self.cards = []
        self._pending = []
        for path in files:
            card = Card(path)
            pix = card_pixmap(path)
            if pix is not None:
                card.set_picture(pix)
            elif Path(path).exists() and not welcome_thumb.refused(path):
                self._pending.append(card)
            card.clicked.connect(lambda _=False, p=path: self._open_path(p))
            lay.addWidget(card)
            self.cards.append(card)
        self._start_pictures()
        lay.addStretch(1)

    # --------------------------------------------- pictures, one a turn
    def _start_pictures(self):
        """Documents with no picture yet are drawn one per event-loop
        turn, so the window opens at once and the cards fill in."""
        if getattr(self, "_pictures_running", False) or not self._pending:
            return
        self._pictures_running = True
        QTimer.singleShot(60, self._next_picture)

    def _next_picture(self):
        self._pictures_running = False
        if not self._pending or not self.isVisible():
            return
        card = self._pending.pop(0)
        try:
            alive = card.isVisible()
        except RuntimeError:                 # rebuilt meanwhile
            alive = False
        if alive:
            path = card.property("path")
            if welcome_thumb.render_file(path):
                pix = card_pixmap(path)
                if pix is not None:
                    card.set_picture(pix)
        self._start_pictures()

    def _fill_folders(self):
        lay = self._folders
        while lay.count():
            it = lay.takeAt(0)
            if it.widget() is not None:
                it.widget().deleteLater()
        self.folder_buttons = []
        for d in recent_folders(self.win)[:4]:
            b = QToolButton()
            b.setObjectName("Item")
            b.setIcon(_icon("welcome_folder"))
            b.setIconSize(QSize(40, 40))
            b.setText("  " + Path(d).name + "\n  " + short_folder(d))
            b.setToolTip(d)
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, p=d: self._open_in(p))
            lay.addWidget(b)
            self.folder_buttons.append(b)
        if not self.folder_buttons:
            lab = QLabel(language.tr("No recent folders."))
            lab.setObjectName("Muted")
            lay.addWidget(lab)

    # ---------------------------------------------------------- recent
    def _recent_page(self):
        page = QWidget()
        page.setStyleSheet("background:#ffffff;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(36, 18, 36, 12)
        lay.addWidget(_section("Recent Documents"))
        self.recent_list = QListWidget()
        self.recent_list.itemActivated.connect(
            lambda it: self._open_path(it.data(Qt.UserRole)))
        self.recent_list.itemClicked.connect(
            lambda it: self._open_path(it.data(Qt.UserRole)))
        lay.addWidget(self.recent_list, 1)
        return page

    def _fill_recent_list(self):
        self.recent_list.clear()
        for path in recent_files(self.win):
            it = QListWidgetItem(
                _icon("welcome_" + icons_welcome.kind_of(path)),
                f"{Path(path).name}\n{short_folder(path, 80)}")
            it.setData(Qt.UserRole, path)
            it.setToolTip(path)
            if not Path(path).exists():
                it.setFlags(Qt.NoItemFlags)
            self.recent_list.addItem(it)

    # ----------------------------------------------------------- learn
    def _learn_page(self):
        page = QWidget()
        page.setStyleSheet("background:#ffffff;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(36, 18, 36, 12)
        row = QHBoxLayout()
        row.addWidget(_section("Learn"))
        row.addStretch(1)
        guide = QPushButton(language.tr("Open the User Guide (F1)"))
        guide.setObjectName("Link")
        guide.setCursor(Qt.PointingHandCursor)
        guide.clicked.connect(self._guide)
        row.addWidget(guide)
        lay.addLayout(row)
        note = QLabel(language.tr(
            "Numbered tutorials, one technique each, from the simplest "
            "to the most advanced. A click replaces the open document."))
        note.setObjectName("Muted")
        note.setWordWrap(True)
        lay.addWidget(note)
        self.learn_list = QListWidget()
        try:
            self._learn = learn_examples()
        except Exception:
            self._learn = []
        for i, (label, _b) in enumerate(self._learn):
            it = QListWidgetItem(_icon("welcome_learn"),
                                 label)
            it.setData(Qt.UserRole, i)
            self.learn_list.addItem(it)
        self.learn_list.itemClicked.connect(self._learn_clicked)
        lay.addWidget(self.learn_list, 1)
        return page

    def _learn_clicked(self, item):
        build = self._learn[item.data(Qt.UserRole)][1]
        if self.win._confirm_discard():
            self.win._dirty = False
            self.win._load_example(build)
            self.close()

    # ---------------------------------------------------------- alerts
    def _alerts_page(self):
        page = QWidget()
        page.setStyleSheet("background:#ffffff;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(36, 18, 36, 12)
        lay.addWidget(_section("Alerts"))
        self._alerts_label = QLabel(self._alerts_text())
        self._alerts_label.setWordWrap(True)
        self._alerts_label.setObjectName("Muted")
        lay.addWidget(self._alerts_label)
        chk = QPushButton(language.tr("Check for Updates"))
        chk.setObjectName("Advanced")
        chk.setCursor(Qt.PointingHandCursor)
        chk.clicked.connect(lambda: self._resource("updates"))
        lay.addWidget(chk, 0, Qt.AlignLeft)
        lay.addStretch(1)
        return page

    def _alerts_text(self):
        from . import SHORT_NAME, __version__
        engine = getattr(self.win, "engine", None)
        found = bool(getattr(engine, "binary", None)) if engine else False
        lines = [language.tr("You are running {name} v{version}.")
                 .format(name=SHORT_NAME, version=__version__)]
        lines.append(language.tr(
            "OpenSCAD engine found: exact renders and STL export are on.")
            if found else language.tr(
            "OpenSCAD was not found: the built-in preview is used. "
            "Edit ▸ Locate OpenSCAD to point to it."))
        return "\n\n".join(lines)

    # --------------------------------------------------------- tip bar
    def _tip_bar(self):
        bar = QFrame()
        bar.setObjectName("Tip")
        bar.setFixedHeight(54)
        row = QHBoxLayout(bar)
        row.setContentsMargins(18, 0, 14, 0)
        bulb = QLabel()
        bulb.setPixmap(_icon("welcome_tip").pixmap(30, 30))
        row.addWidget(bulb)
        self._tip_index = 0
        self.tip_label = QLabel(language.tr(TIPS[0]))
        self.tip_label.setWordWrap(True)
        row.addWidget(self.tip_label, 1)
        self.show_check = QCheckBox(language.tr("Show at start-up"))
        self.show_check.setChecked(show_at_start())
        self.show_check.toggled.connect(set_show_at_start)
        row.addWidget(self.show_check)
        for text, step in (("‹", -1), ("›", 1)):
            b = QToolButton()
            b.setObjectName("TipArrow")
            b.setText(text)
            b.clicked.connect(lambda _=False, s=step: self.next_tip(s))
            row.addWidget(b)
        return bar

    def next_tip(self, step=1):
        self._tip_index = (self._tip_index + step) % len(TIPS)
        self.tip_label.setText(language.tr(TIPS[self._tip_index]))

    # --------------------------------------------------------- actions
    def _new(self, kind, unit=None):
        if new_document(self.win, kind, unit):
            self.close()

    def _advanced(self):
        dlg = AdvancedDialog(self.win)
        if dlg.exec_() == QDialog.Accepted:
            kind, unit = dlg.choice()
            self._new(kind, unit)

    def _open(self):
        self.close()
        self.win.open_file()

    def _open_in(self, folder):
        path, _ = QFileDialog.getOpenFileName(
            self, language.tr("Open"), folder,
            language.tr("KherveCAD document (*.kcad);;All files (*)"))
        if path:
            self.close()
            self.win.open_any(path)

    def _open_path(self, path):
        self.close()
        self.win._open_path(path)

    def _guide(self):
        self.win._user_guide()

    def _resource(self, target):
        if target == "guide":
            self._guide()
        elif target == "updates":
            try:
                self.win.updater.check_now()
            except Exception:
                QDesktopServices.openUrl(QUrl(REPO + "/releases"))
        elif target == "whats_new":
            QDesktopServices.openUrl(QUrl(REPO + "/releases"))
        else:
            QDesktopServices.openUrl(QUrl(target))


def show_welcome(win, tab=0):
    """Open (or raise) the Welcome window of *win*, centred over it."""
    dlg = getattr(win, "_welcome", None)
    if dlg is None:
        dlg = win._welcome = WelcomeDialog(win)
    dlg.refresh()
    dlg.show_tab(tab)
    if not dlg.isVisible():
        geo = win.frameGeometry()
        dlg.move(geo.center().x() - dlg.width() // 2,
                 geo.center().y() - dlg.height() // 2)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    return dlg


def show_at_startup(win):
    """Called once by main(): the Welcome window, unless switched off."""
    if show_at_start():
        return show_welcome(win)
    return None
