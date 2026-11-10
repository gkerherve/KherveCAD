"""The status bar's Recent files combo box (2026-11-10, the user): the
same list as File > Open Recent, at the bottom left; picking one opens it.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from pathlib import Path

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QComboBox, QSizePolicy


class RecentCombo(QComboBox):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setToolTip(self.tr("Recent files: pick one to open it"))
        self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(22)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.activated.connect(self._picked)
        self.refresh()

    def refresh(self):
        self.blockSignals(True)
        self.clear()
        self.addItem(self.tr("Recent files…"))
        for path in self.window._recent_files():
            self.addItem(Path(path).name, path)
            i = self.count() - 1
            self.setItemData(i, path, 3)          # Qt.ToolTipRole
            if not Path(path).exists():
                self.model().item(i).setEnabled(False)
        self.setCurrentIndex(0)
        self.blockSignals(False)

    def _picked(self, index):
        path = self.itemData(index)
        self.setCurrentIndex(0)
        if path:
            # next turn: opening rebuilds this combo while it emits
            QTimer.singleShot(0, lambda: self.window._open_path(path))


def install(window):
    window._recent_combo = RecentCombo(window)
    window.statusBar().addWidget(window._recent_combo)
