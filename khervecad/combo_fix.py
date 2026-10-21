"""Drop-down rows drawn in the theme's colours (2026-10-21).

Qt's default combo delegate ignores the stylesheet's ``::item`` rules, so
macOS drew the picked row BLACK (the user). Every QComboBox made after
`install` gets a QStyledItemDelegate in its constructor — set once, at
no cost per event (an app-wide event filter did it on Polish but ran
Python on every event of the program and slowed everything down).

`install` swaps PyQt5.QtWidgets.QComboBox for a subclass, so it must run
before the modules that import QComboBox: the package does it on import.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

_done = False


def install():
    global _done
    if _done:
        return
    _done = True
    try:
        import PyQt5.QtWidgets as W
    except ImportError:                       # pragma: no cover
        return
    base = W.QComboBox

    class QComboBox(base):                    # noqa: D401 - a drop-in
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            try:
                self.setItemDelegate(W.QStyledItemDelegate(self))
            except Exception:                 # pragma: no cover
                pass

    QComboBox.__module__ = base.__module__
    W.QComboBox = QComboBox
