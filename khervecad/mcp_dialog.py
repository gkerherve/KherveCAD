"""Control panel for the assistant connection.

Shows whether the connection is open and wires Claude Desktop, Claude
Code and their relatives up to it.

Nothing here says "MCP" unless the user has to type it somewhere: the
protocol is our problem, not theirs.  What a person needs to know is
which application to connect, that it must be restarted afterwards, and
that they then say "KherveCAD" in the chat -- that last step is
invisible, and skipping it makes a correctly connected assistant look
broken.

Editing ``claude_desktop_config.json`` by hand is the step that stops
people connecting at all, so the dialog detects the applications on
this machine and writes the entry itself (see ``mcp_hosts``).  The
snippet and its Copy button stay for the ones we refuse to rewrite and
for anyone configuring a machine by hand.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import json
import sys

from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QGroupBox, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton,
    QVBoxLayout,
)

from . import language
from .mcp_bridge import ACCESS_LEVELS
from .mcp_hosts import HOSTS, Host, cli_command, host_config
from .mcp_server import endpoint_path

SETTINGS = ("Kherve", "KherveCAD")

#: A literal double quote cannot appear inside an f-string before
#: Python 3.12, and the messages below quote what to type in the chat.
DQ = '"'

#: Access level → (label, what it means).  Order matches ACCESS_LEVELS.
def _access_labels():
    return [
        (language.tr("Read only"),
         language.tr(
             "Inspect the model, read its OpenSCAD and look at the "
             "3D view; no changes.")),
        (language.tr("Edit"),
         language.tr(
             "Build and edit objects, assemble parts, run code — "
             "and save over the open file, but not open or export "
             "another one.")),
        (language.tr("Full (recommended)"),
         language.tr(
             "Everything, including opening, saving and exporting "
             "files it names itself, so 'open my bracket and add a "
             "hole' works in one go.")),
    ]


class McpServerDialog(QDialog):
    """Enable/disable the bridge and copy the host configuration."""

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self._bridge = bridge
        self.setWindowTitle(language.tr("Connect to Claude"))
        self.setMinimumWidth(620)
        self._build_ui()
        self._refresh()
        # Bound methods, not lambdas: PyQt drops the connection when
        # this dialog is destroyed (it is WA_DeleteOnClose), whereas a
        # lambda would outlive it and fire on a deleted widget.
        bridge.started.connect(self._on_bridge_started)
        bridge.stopped.connect(self._refresh)
        bridge.tool_invoked.connect(self._on_tool_invoked)

    # ── UI ───────────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)

        blurb = QLabel(language.tr(
            "Let Claude build in this document directly — no API "
            "key, it uses the login you already have. Works with "
            "<b>Claude Desktop</b> and <b>Claude Code</b>, and with "
            "Cursor, Cline, VS Code and LM Studio.<br><br>Claude "
            "gets the whole app rather than a chat reply: the object "
            "tree, OpenSCAD in and out, the part library, assemblies "
            "and mates, and a look at the 3D view to check its own "
            "work. Everything it does is undoable with Ctrl+Z."))
        blurb.setWordWrap(True)
        lay.addWidget(blurb)

        self._enable = QCheckBox(
            language.tr("Let assistants connect to this document"))
        self._enable.toggled.connect(self._on_toggled)
        lay.addWidget(self._enable)

        self._status = QLabel()
        self._status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self._status)

        acc_row = QHBoxLayout()
        acc_row.addWidget(QLabel(language.tr("The assistant may:")))
        self._access = QComboBox()
        for label, tip in _access_labels():
            self._access.addItem(label)
            self._access.setItemData(self._access.count() - 1, tip,
                                     Qt.ToolTipRole)
        self._access.currentIndexChanged.connect(self._on_access_changed)
        acc_row.addWidget(self._access, 1)
        lay.addLayout(acc_row)

        self._access_hint = QLabel()
        self._access_hint.setWordWrap(True)
        lay.addWidget(self._access_hint)

        host_box = QGroupBox(language.tr("Connect an application"))
        host_lay = QVBoxLayout(host_box)
        host_lay.addWidget(QLabel(language.tr(
            "Pick yours and press Connect — KherveCAD writes itself "
            "into that application's own settings, so there is no "
            "config file to edit by hand.")))
        self._hosts = QListWidget()
        self._hosts.setMaximumHeight(120)
        self._hosts.currentRowChanged.connect(self._refresh_host_buttons)
        host_lay.addWidget(self._hosts)
        hrow = QHBoxLayout()
        self._connect_btn = QPushButton(language.tr("Connect"))
        self._connect_btn.clicked.connect(self._on_connect)
        self._disconnect_btn = QPushButton(language.tr("Disconnect"))
        self._disconnect_btn.clicked.connect(self._on_disconnect)
        hrow.addWidget(self._connect_btn)
        hrow.addWidget(self._disconnect_btn)
        other = QPushButton(language.tr("Other application…"))
        other.setToolTip(language.tr(
            "Point at another assistant's JSON config file and add "
            "KherveCAD to it."))
        other.clicked.connect(self._on_other_host)
        hrow.addWidget(other)
        hrow.addStretch(1)
        host_lay.addLayout(hrow)
        self._host_hint = QLabel()
        self._host_hint.setWordWrap(True)
        self._host_hint.setTextInteractionFlags(Qt.TextSelectableByMouse)
        host_lay.addWidget(self._host_hint)
        lay.addWidget(host_box)

        row = QHBoxLayout()
        row.addWidget(QLabel(language.tr("Or set it up by hand:")))
        self._flavour = QComboBox()
        self._flavour.addItems([
            language.tr("Claude Desktop / Cursor / Zed (JSON)"),
            language.tr("Claude Code (command line)"),
            language.tr("URL only (clients that take an HTTP endpoint)"),
        ])
        self._flavour.currentIndexChanged.connect(self._refresh_snippet)
        row.addWidget(self._flavour, 1)
        lay.addLayout(row)

        self._snippet = QPlainTextEdit()
        self._snippet.setReadOnly(True)
        mono = QFont("Consolas" if sys.platform.startswith("win")
                     else "Monospace")
        mono.setStyleHint(QFont.TypeWriter)
        mono.setPointSize(9)
        self._snippet.setFont(mono)
        self._snippet.setMinimumHeight(150)
        lay.addWidget(self._snippet)

        hint = QLabel(language.tr(
            "<b>Then say &quot;KherveCAD&quot; in the chat.</b> "
            "Claude only reaches for this document when you point it "
            "here &mdash; <i>&quot;in KherveCAD, build a "
            "40&nbsp;mm bracket with two M6 holes&quot;</i>. After "
            "that it carries on in the open document.<br><br>Restart "
            "the application after connecting &mdash; it reads its "
            "tool list once at startup &mdash; and leave KherveCAD "
            "running with the box above ticked."))
        hint.setWordWrap(True)
        lay.addWidget(hint)

        act_box = QGroupBox(language.tr("Recent activity"))
        act_lay = QVBoxLayout(act_box)
        self._activity = QListWidget()
        self._activity.setMaximumHeight(110)
        act_lay.addWidget(self._activity)
        lay.addWidget(act_box)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        copy = QPushButton(language.tr("Copy"))
        copy.clicked.connect(self._copy)
        btns.addButton(copy, QDialogButtonBox.ActionRole)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    # ── Behaviour ────────────────────────────────────────────────────

    def _on_bridge_started(self, _port: int):
        self._refresh()

    def _on_tool_invoked(self, name: str, outcome: str):
        self._activity.insertItem(0, f"{name} — {outcome}")
        while self._activity.count() > 50:
            self._activity.takeItem(self._activity.count() - 1)

    def _on_access_changed(self, index: int):
        level = ACCESS_LEVELS[index]
        self._bridge.set_access(level)
        QSettings(*SETTINGS).setValue("mcp/access", level)
        self._refresh_access_hint()

    def _on_toggled(self, on: bool):
        if on:
            if not self._bridge.start():
                self._enable.setChecked(False)
                self._status.setText(language.tr(
                    "<b>Could not open a local port.</b> Another "
                    "process may be holding it."))
                return
        else:
            self._bridge.stop()
        QSettings(*SETTINGS).setValue("mcp/enabled", bool(on))
        self._refresh()

    def _refresh_access_hint(self):
        idx = self._access.currentIndex()
        text = _access_labels()[idx][1]
        if ACCESS_LEVELS[idx] == "full":
            text += " " + language.tr(
                "It can read and overwrite files anywhere you can, "
                "so connect only applications you trust.")
        self._access_hint.setText(text)

    def _refresh(self):
        running = self._bridge.is_running()
        self._enable.blockSignals(True)
        self._enable.setChecked(running)
        self._enable.blockSignals(False)
        self._access.blockSignals(True)
        self._access.setCurrentIndex(
            ACCESS_LEVELS.index(self._bridge.access()))
        self._access.blockSignals(False)
        self._refresh_access_hint()
        self._activity.clear()
        for entry in reversed(self._bridge.log):
            self._activity.addItem(
                f"{entry['time']}  {entry['tool']} — {entry['outcome']}")
        if running:
            http = self._bridge.http_url()
            extra = (" &nbsp; " + language.tr("HTTP: {url}").format(
                url=http)) if http else ""
            self._status.setText(language.tr(
                "<b style='color:#2e7d32'>Listening</b> on "
                "127.0.0.1:{port}{extra}<br>endpoint file: "
                "{path}").format(port=self._bridge.port(), extra=extra,
                                 path=endpoint_path()))
        else:
            self._status.setText(language.tr(
                "<b style='color:#b71c1c'>Stopped</b> — no assistant "
                "can reach this document."))
        self._refresh_snippet()
        self._refresh_hosts()

    # ── Host wiring ──────────────────────────────────────────────────

    def _selected_host(self):
        row = self._hosts.currentRow()
        return HOSTS[row] if 0 <= row < len(HOSTS) else None

    def _refresh_hosts(self):
        """Rebuild the host list, keeping the current selection."""
        row = max(self._hosts.currentRow(), 0)
        self._hosts.blockSignals(True)
        self._hosts.clear()
        for host in HOSTS:
            status = host.status()
            item = QListWidgetItem(
                f"{host.label} — {language.tr(status)}")
            if status.startswith("connected"):
                item.setForeground(Qt.darkGreen)
            elif status == "not installed":
                item.setForeground(Qt.gray)
            self._hosts.addItem(item)
        self._hosts.setCurrentRow(min(row, len(HOSTS) - 1))
        self._hosts.blockSignals(False)
        self._refresh_host_buttons()

    def _refresh_host_buttons(self):
        host = self._selected_host()
        if host is None:
            self._connect_btn.setEnabled(False)
            self._disconnect_btn.setEnabled(False)
            self._host_hint.clear()
            return
        connected = host.connected()
        self._connect_btn.setEnabled(not host.manual)
        self._connect_btn.setText(
            language.tr("Update entry")
            if connected and not host.up_to_date()
            else language.tr("Connect"))
        self._disconnect_btn.setEnabled(connected and not host.manual)
        bits = []
        if host.manual:
            bits.append(language.tr("Cannot be edited automatically."))
        bits.append(host.note)
        path = host.path()
        if path:
            bits.append(f"<i>{path}</i>")
        self._host_hint.setText("  ".join(b for b in bits if b))

    def _report(self, result: dict):
        """Show what a connect/disconnect actually did."""
        title = language.tr("Connect to Claude")
        host = result.get("host", "host")
        if not result.get("ok"):
            QMessageBox.warning(self, title, result.get(
                "error", language.tr(
                    "Could not configure {host}.").format(host=host)))
            self._refresh_hosts()
            return
        action = language.tr(result.get('action', 'updated'))
        lines = [language.tr("{host}: KherveCAD {action}.").format(
                     host=host, action=action),
                 language.tr("File: {path}").format(
                     path=result.get('path', ''))]
        if result.get("backup"):
            lines.append(language.tr(
                "Previous version saved as {backup}").format(
                    backup=result['backup']))
        if result.get("restart"):
            lines.append("\n" + language.tr(
                "Restart {host} for it to take effect.").format(host=host))
        if result.get("action") != "removed":
            # The step with no visible cue: a correctly connected
            # assistant sits there doing nothing until a chat names
            # this application.
            lines.append("\n" + language.tr(
                "Then mention KherveCAD in your chat with {host} — "
                "say {dq}in KherveCAD, build a 40 mm bracket{dq} — "
                "and it will work in this document.").format(
                    host=host, dq=DQ))
        QMessageBox.information(self, title, "\n".join(lines))
        self._refresh_hosts()

    def _require_running(self) -> bool:
        if self._bridge.is_running():
            return True
        QMessageBox.information(
            self, language.tr("Connect to Claude"), language.tr(
                "Tick 'Let assistants connect to this document' "
                "first — the entry is only useful while KherveCAD is "
                "listening."))
        return False

    def _on_connect(self):
        host = self._selected_host()
        if host is None or not self._require_running():
            return
        self._report(host.connect())

    def _on_other_host(self):
        """Add KherveCAD to a config file the user points us at.

        The named entries cannot cover every MCP client, and guessing a
        path wrongly is worse than asking.
        """
        if not self._require_running():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, language.tr("Choose the client's MCP config file"), "",
            "JSON config (*.json);;All files (*)")
        if not path:
            return
        # Match the file's own convention rather than imposing ours:
        # most clients copied Claude Desktop's "mcpServers", VS Code
        # and its relatives use "servers".
        shape = "mcpServers"
        try:
            with open(path, "r", encoding="utf-8") as fh:
                doc = json.load(fh)
            if isinstance(doc, dict) and "servers" in doc \
                    and "mcpServers" not in doc:
                shape = "servers"
        except Exception:
            pass          # empty or unreadable: connect() reports it
        host = Host.for_file(path, shape=shape)
        if shape == "servers":
            host.entry_extra = {"type": "stdio"}
        self._report(host.connect())

    def _on_disconnect(self):
        host = self._selected_host()
        if host is None:
            return
        if QMessageBox.question(
                self, language.tr("Connect to Claude"), language.tr(
                    "Remove KherveCAD from {host}'s configuration?\n"
                    "Other servers are left untouched.").format(
                        host=host.label),
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._report(host.disconnect())

    def _refresh_snippet(self):
        idx = self._flavour.currentIndex()
        if idx == 0:
            self._snippet.setPlainText(host_config())
        elif idx == 1:
            self._snippet.setPlainText(cli_command())
        else:
            self._snippet.setPlainText(self._http_snippet())

    def _http_snippet(self) -> str:
        """Endpoint and token for a client that only takes a URL."""
        url = self._bridge.http_url()
        if not url:
            return language.tr(
                "The HTTP endpoint is not listening.\nTick the box "
                "above.")
        return language.tr(
            "URL      {url}\n"
            "Transport  Streamable HTTP (POST JSON-RPC)\n"
            "Header   Authorization: Bearer {token}\n"
            "\n"
            "For clients that take an endpoint rather than a "
            "command —\nOpen WebUI, n8n, and some IDE setups. The "
            "token changes\nevery time the server is switched on, so "
            "re-copy it after\nrestarting KherveCAD.\n"
            "\n"
            "127.0.0.1 only: this is not reachable from another "
            "machine,\nand cloud assistants (ChatGPT, Le Chat, Grok) "
            "cannot use it.").format(url=url, token=self._bridge.token())

    def _copy(self):
        QApplication.clipboard().setText(self._snippet.toPlainText())
