"""Application entry: QApplication setup, crash log, Fusion style.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import faulthandler
import sys
import tempfile
from pathlib import Path

from PyQt5.QtWidgets import QApplication

CRASH_LOG = Path(tempfile.gettempdir()) / "khervecad_crash.log"


def main():
    # An MCP host launches us as a plain stdio subprocess it owns.  That
    # half must not build a QApplication (or a window), so it forks off
    # before anything Qt happens.
    if "--mcp-server" in sys.argv[1:]:
        from .mcp_server import main as mcp_main
        sys.exit(mcp_main([a for a in sys.argv[1:] if a != "--mcp-server"]))

    crash_file = open(CRASH_LOG, "w")
    faulthandler.enable(file=crash_file)

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
