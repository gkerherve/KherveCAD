"""The TOOL GUIDE: help you can see while you use the menus.

On macOS the menu bar is the system's own, and it never shows tooltips,
so the how-to text every tool has (`tooltips.TIPS`) stayed invisible,
and an operation chosen with nothing selected only flashed a status-bar
line — "nothing happens". The guide is a card floating in the bottom
right of the main window, in three moods:

* hover — while a menu is open, the item under the mouse: what it does
  and how to use it (Help ▸ Show Help While Hovering Menus turns it off);
* needs a selection — an operation chosen with nothing selected says so
  plainly, with an Apply button that lights up as soon as something is
  selected (in the tree or the 2D view);
* applied — after an operation wraps the selection: what was made and
  where its settings are (Properties).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtCore import QEvent, QObject, QSettings, Qt, QTimer
from PyQt5.QtWidgets import (QFrame, QHBoxLayout, QLabel, QMenu,
                             QPushButton, QToolButton, QVBoxLayout)

from . import language, tooltips

SETTING = "help/hover_menus"
WIDTH = 380
#: how long an "applied" note stays (ms); a hover card goes with the menu
APPLIED_MS = 12000


def hover_enabled():
    value = QSettings("Kherve", "KherveCAD").value(SETTING, True)
    return value not in (False, "false", "0", 0)


class ToolGuide(QFrame):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.setObjectName("tool_guide")
        self.setFrameShape(QFrame.StyledPanel)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "#tool_guide { background: palette(base); border: 1px solid "
            "palette(mid); border-radius: 8px; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        top = QHBoxLayout()
        self.head = QLabel()
        self.head.setStyleSheet("font-weight: 600; color: #e07b39;")
        top.addWidget(self.head, 1)
        close = QToolButton()
        close.setText("✕")
        close.setAutoRaise(True)
        close.clicked.connect(self.dismiss)
        top.addWidget(close)
        lay.addLayout(top)
        self.body = QLabel()
        self.body.setWordWrap(True)
        self.body.setTextFormat(Qt.RichText)
        self.body.setFixedWidth(WIDTH - 24)
        lay.addWidget(self.body)
        row = QHBoxLayout()
        row.addStretch(1)
        self.apply_btn = QPushButton()
        self.apply_btn.clicked.connect(self._apply)
        row.addWidget(self.apply_btn)
        lay.addLayout(row)
        self.setFixedWidth(WIDTH)
        self.mode = None
        self.op = None
        self._poll = QTimer(self)
        self._poll.setInterval(300)
        self._poll.timeout.connect(self._check_selection)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.dismiss)
        main.installEventFilter(self)
        from PyQt5.QtWidgets import QApplication
        QApplication.instance().installEventFilter(self)
        self.hide()

    # -- placement
    def eventFilter(self, obj, event):
        # never raise here: an exception out of a Qt callback aborts
        try:
            kind = event.type()
            if kind == QEvent.Resize and obj is self.main and \
                    self.isVisible():
                self._place()
            elif self.mode == "hover" and self.isVisible() and kind in (
                    QEvent.MouseMove, QEvent.MouseButtonPress,
                    QEvent.KeyPress, QEvent.WindowDeactivate):
                # a menu's help goes the moment the pointer is anywhere
                # but in a menu — native menus (macOS) give no close signal
                from PyQt5.QtWidgets import QMenuBar
                if kind != QEvent.MouseMove or not isinstance(
                        obj, (QMenu, QMenuBar)):
                    self.menu_closed()
        except Exception:                          # noqa: BLE001
            pass
        return False

    def _place(self):
        self.adjustSize()
        m = self.main
        bar = m.statusBar().height() if m.statusBar() else 0
        self.move(m.width() - self.width() - 16,
                  m.height() - self.height() - bar - 16)
        self.raise_()

    def _show(self, head, html, button=None):
        self.head.setText(head)
        self.body.setText(html)
        self.apply_btn.setVisible(button is not None)
        if button:
            self.apply_btn.setText(button)
        self._place()
        self.show()
        self.raise_()
        self._place()

    # -- the three moods
    def hover(self, key=None, text=""):
        if not hover_enabled() or self.mode == "need":
            return
        self._hide_timer.stop()
        self.mode = "hover"
        if key:
            self._show(language.tr("Help"), tooltips.rich(key))
        elif text:
            self._show(language.tr("Help"), text)
        else:
            self.hide()

    def menu_closed(self):
        if self.mode == "hover":
            self.mode = None
            self.hide()

    def need_selection(self, op):
        """*op* chosen with nothing selected: say what to do, and offer
        to apply it as soon as something is."""
        self.mode = "need"
        self.op = op
        self._hide_timer.stop()
        title = tooltips.entry(op)[0]
        lead = language.tr(
            "<p><b>Select what {title} works on first</b> — click a part "
            "in the tree (left) or in the 2D view. Then press "
            "<b>Apply</b> below, or choose {title} again.</p>").format(
            title=title)
        self._show(language.tr("Nothing selected"),
                   lead + tooltips.rich(op), language.tr("Apply"))
        self.apply_btn.setEnabled(False)
        self._poll.start()
        self._check_selection()

    def applied(self, op, node, wrapped=()):
        """What *op* just made round *wrapped*, and where to change it."""
        from .model import NODE_TYPES
        self._poll.stop()
        self.mode = "applied"
        spec = NODE_TYPES.get(op, {})
        labels = [label for _k, label, *_r in spec.get("schema", [])][:5]
        if op == "linear_extrude":
            # its Properties speak like the Extrude window (extrude_props)
            labels = ["Direction", "End condition", "Distance",
                      "Reverse direction", "Twist", "Scale"]
        settings = ", ".join(labels)
        what = tooltips.entry(op)[1]
        html = language.tr(
            "<p><b>{title}</b> now wraps <b>{name}</b> — the new "
            "<b>{node}</b> is selected in the tree.</p><p>{what}</p>").format(
            title=tooltips.entry(op)[0], node=node.name, what=what,
            name=", ".join(n.name for n in wrapped[:3]) +
            ("…" if len(wrapped) > 3 else "") if wrapped else "it")
        if settings:
            html += language.tr(
                "<p>Change it in <b>Properties</b> (bottom left): "
                "{settings}.</p>").format(settings=settings)
        html += language.tr("<p style='color:#8a8a8a'>Ctrl+Z takes it "
                            "off again.</p>")
        self._show(language.tr("Done"), html)
        self._hide_timer.start(APPLIED_MS)

    def dismiss(self):
        self._poll.stop()
        self._hide_timer.stop()
        self.mode = None
        self.op = None
        self.hide()

    # -- the Apply button
    def _selected(self):
        try:
            return self.main.builder.active_tree().selected_nodes()
        except Exception:                          # noqa: BLE001
            return []

    def _check_selection(self):
        if self.mode != "need":
            self._poll.stop()
            return
        has = bool(self._selected())
        self.apply_btn.setEnabled(has)
        self.apply_btn.setText(language.tr("Apply to the selection") if has
                               else language.tr("Apply"))

    def _apply(self):
        op = self.op
        self.dismiss()
        if op:
            self.main._apply_operation(op)


def _bar_keys():
    """The tools of the vertical bar: their hover tooltip is enough."""
    from . import toolbars
    keys = {t[0] for t in toolbars.TOOLS}
    keys |= {t[0] for t in toolbars.MEASURE_TOOLS}
    return keys | set(toolbars.BAR_PRIMITIVES)


class _MenuHover(QObject):
    """Feeds the guide from every menu: hovered actions and closing."""

    def __init__(self, guide):
        super().__init__(guide)
        self.guide = guide
        self._hooked = set()

    def hook(self, menu):
        if id(menu) in self._hooked:
            return
        self._hooked.add(id(menu))
        menu.hovered.connect(self._hovered)
        menu.aboutToHide.connect(self._closed)
        menu.aboutToShow.connect(lambda m=menu: self._sub(m))
        self._sub(menu)

    def _sub(self, menu):
        for act in menu.actions():
            if act.menu() is not None:
                self.hook(act.menu())

    def _hovered(self, action):
        try:
            self._show_for(action)
        except Exception:                          # noqa: BLE001
            pass                    # help must never take the app down

    def _show_for(self, action):
        if action is None or action.isSeparator():
            return
        key = action.data()
        if isinstance(key, str) and key in _bar_keys():
            self.guide.hover(text=None)   # the toolbar has its own tooltip
            return
        if isinstance(key, str) and key in tooltips.TIPS:
            self.guide.hover(key)
            return
        if action.menu() is not None:
            return                      # a submenu: its items say more
        from . import menu_help
        card = menu_help.resolve(action)
        if card:
            self.guide.hover(text=card)
            return
        text = action.toolTip() or ""
        plain = action.text().replace("&", "").split("\t")[0]
        if text and text.replace("&", "") != plain:
            self.guide.hover(text=text)
        elif action.statusTip():
            self.guide.hover(text=f"<b>{plain}</b><p>"
                             f"{action.statusTip()}</p>")
        else:
            self.guide.hover(text=None)

    def _closed(self):
        QTimer.singleShot(150, self._maybe_close)

    def _maybe_close(self):
        from PyQt5.QtWidgets import QApplication
        if not isinstance(QApplication.activePopupWidget(), QMenu):
            self.guide.menu_closed()


def install(main):
    """The guide on *main*: every menu of its menu bar feeds it, and
    Help gets the switch for the hover help."""
    guide = ToolGuide(main)
    main.tool_guide = guide
    hover = _MenuHover(guide)
    main._menu_hover = hover        # menus built later (Interface Style)
    for act in main.menuBar().actions():
        if act.menu() is not None:
            hover.hook(act.menu())
            if act.text().replace("&", "") == language.tr("Help"):
                help_menu = act.menu()
                toggle = help_menu.addAction(language.tr(
                    "Show Help While Hovering Menus"))
                toggle.setCheckable(True)
                toggle.setChecked(hover_enabled())
                toggle.toggled.connect(lambda on: QSettings(
                    "Kherve", "KherveCAD").setValue(SETTING, bool(on)))
    return guide
