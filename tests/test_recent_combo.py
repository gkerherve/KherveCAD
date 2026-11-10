"""The status bar's Recent files combo box."""

from PyQt5.QtWidgets import QApplication


def test_recent_combo_lists_and_opens(tmp_path, monkeypatch):
    from khervecad.mainwindow import MainWindow
    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    try:
        win._set_recent_files([])
        f = tmp_path / "part.kcad"
        f.write_text("{}")
        win._add_recent(str(f))
        combo = win._recent_combo
        assert combo.count() == 2 and combo.itemText(1) == "part.kcad"
        opened = []
        monkeypatch.setattr(win, "_open_path", opened.append)
        combo.activated.emit(1)
        app.processEvents()
        assert opened == [str(f)] and combo.currentIndex() == 0
    finally:
        win._set_recent_files([])
        win._dirty = False
        win.close()
