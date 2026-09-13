"""Application entry: QApplication setup, crash log, Fusion style.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import datetime
import faulthandler
import sys
import tempfile
import time
import traceback
from pathlib import Path

from PyQt5.QtWidgets import QApplication

CRASH_LOG = Path(tempfile.gettempdir()) / "khervecad_crash.log"
#: the log keeps earlier sessions (a crash is usually reported after a
#: restart, which used to wipe it) but not without end
CRASH_LOG_LIMIT = 512 * 1024


def _open_crash_log():
    """Append to the crash log, starting afresh once it grows too big,
    with a header per session."""
    try:
        if CRASH_LOG.exists() and CRASH_LOG.stat().st_size > CRASH_LOG_LIMIT:
            CRASH_LOG.replace(CRASH_LOG.with_suffix(".old.log"))
    except OSError:
        pass
    handle = open(CRASH_LOG, "a", encoding="utf-8")
    handle.write(f"\n=== KherveCAD session "
                 f"{datetime.datetime.now().isoformat(timespec='seconds')}"
                 f" ===\n")
    handle.flush()
    return handle


def install_excepthook(log=CRASH_LOG, notify=True):
    """Keep the app alive through a Python error.

    PyQt turns an exception escaping a Qt callback — a paint, a click,
    a menu action — into qFatal: the whole application aborted and took
    the unsaved document with it. Now the traceback goes to the crash
    log and stderr, the user is told once (not in the middle of a paint:
    the message waits for the event loop), and KherveCAD carries on so
    the work can be saved."""
    state = {"last": 0.0}

    def hook(kind, value, tb):
        text = "".join(traceback.format_exception(kind, value, tb))
        sys.stderr.write(text)
        try:
            with open(log, "a", encoding="utf-8") as fh:
                fh.write(f"--- "
                         f"{datetime.datetime.now().isoformat(timespec='seconds')}"
                         f" Python error\n{text}")
        except OSError:
            pass
        if issubclass(kind, KeyboardInterrupt) or not notify:
            return
        now = time.monotonic()
        if now - state["last"] < 5.0:
            return                      # one message for a burst of errors
        state["last"] = now
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(0, lambda: _tell(value, log))

    sys.excepthook = hook
    return hook


def _tell(value, log):
    from PyQt5.QtWidgets import QMessageBox
    QMessageBox.warning(
        QApplication.activeWindow(), "KherveCAD",
        f"Something went wrong: {value}\n\nKherveCAD kept running and "
        f"your document is still open — save it. The details were "
        f"written to:\n{log}")


def main():
    # An MCP host launches us as a plain stdio subprocess it owns.  That
    # half must not build a QApplication (or a window), so it forks off
    # before anything Qt happens.
    if "--mcp-server" in sys.argv[1:]:
        from .mcp_server import main as mcp_main
        sys.exit(mcp_main([a for a in sys.argv[1:] if a != "--mcp-server"]))

    crash_file = _open_crash_log()
    faulthandler.enable(file=crash_file)
    install_excepthook()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("KherveCAD")

    from .style import apply_style
    apply_style(app)

    from .mainwindow import MainWindow
    win = MainWindow()
    win.show()
    win.start_mcp_if_enabled()
    sys.exit(app.exec_())
