"""A public HTTPS link to the local MCP endpoint, for cloud assistants.

ChatGPT's connectors (Developer mode), Mistral's Le Chat custom
connectors and Grok's remote MCP all live in someone else's data
centre: they cannot spawn ``mcp_server`` and cannot reach 127.0.0.1.
They take a public HTTPS URL, and they cannot send a custom header
(the only choices are OAuth or "no authentication").

So this starts a tunnel — **cloudflared** (a free "quick tunnel", no
account) or **ngrok** — pointing at ``McpHttpServer``, and hands out
``https://<tunnel>/mcp/<token>``: the per-session token rides in the
PATH, which is the one thing such a client can carry.  Anyone holding
that URL drives the open document at the chosen access level, so the
link is off until the user presses Start, dies with the bridge, and a
new token (a new URL) comes with every session.

Neither program is bundled; ``find_tunnel`` looks on PATH and in the
usual install folders.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from typing import Optional, Tuple

from PyQt5.QtCore import QObject, QProcess, QTimer, pyqtSignal

#: Tunnel programs in the order they are tried.
KINDS = ("cloudflared", "ngrok")

#: Where installers put them when PATH does not know.
_EXTRA_DIRS = ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin",
               os.path.expanduser("~/bin"),
               os.path.expandvars(r"%ProgramFiles%\cloudflared"),
               os.path.expandvars(r"%ProgramFiles(x86)%\cloudflared"),
               os.path.expandvars(r"%LOCALAPPDATA%\ngrok"))

#: Seconds to wait for the tunnel to announce its public URL.
START_TIMEOUT_S = 40

_CLOUDFLARE_URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

#: Where to get each program, for the dialog's hint.
INSTALL_HINT = (
    "Install cloudflared (free, no account): "
    "https://developers.cloudflare.com/cloudflare-one/connections/"
    "connect-networks/downloads/ — on a Mac, `brew install "
    "cloudflared`; on Windows, `winget install Cloudflare.cloudflared`. "
    "ngrok works too once its authtoken is configured.")


def find_tunnel(kind: Optional[str] = None) -> Tuple[str, str]:
    """(kind, path) of the first tunnel program found, else ("", "")."""
    for k in ([kind] if kind else KINDS):
        exe = k + (".exe" if os.name == "nt" else "")
        path = shutil.which(k)
        if not path:
            for d in _EXTRA_DIRS:
                cand = os.path.join(d, exe)
                if os.path.isfile(cand) and os.access(cand, os.X_OK):
                    path = cand
                    break
        if path:
            return k, path
    return "", ""


def tunnel_args(kind: str, port: int) -> list:
    """Command-line arguments that expose 127.0.0.1:*port*."""
    target = f"http://127.0.0.1:{port}"
    if kind == "cloudflared":
        return ["tunnel", "--no-autoupdate", "--url", target]
    if kind == "ngrok":
        return ["http", target, "--log", "stdout", "--log-format", "json"]
    raise ValueError(f"Unknown tunnel {kind!r}")


def parse_public_url(kind: str, text: str) -> str:
    """The public https URL announced in a chunk of tunnel output."""
    if kind == "cloudflared":
        m = _CLOUDFLARE_URL.search(text)
        return m.group(0) if m else ""
    for line in text.splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        url = rec.get("url") if isinstance(rec, dict) else None
        if isinstance(url, str) and url.startswith("https://"):
            return url
    return ""


def public_mcp_url(base: str, token: str) -> str:
    """The URL a cloud assistant is given: the token in the path."""
    from .mcp_http import ENDPOINT_PATH
    return f"{base.rstrip('/')}{ENDPOINT_PATH}/{token}"


class Tunnel(QObject):
    """One tunnel process, owned by the bridge."""

    ready = pyqtSignal(str)      # the public MCP URL
    failed = pyqtSignal(str)     # why
    stopped = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc: Optional[QProcess] = None
        self._kind = ""
        self._base = ""
        self._token = ""
        self._output = ""
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._timed_out)

    def is_running(self) -> bool:
        return self._proc is not None

    def kind(self) -> str:
        return self._kind

    def url(self) -> str:
        """The public MCP URL, or "" until the tunnel is up."""
        return public_mcp_url(self._base, self._token) if self._base else ""

    def start(self, port: int, token: str,
              program: Optional[Tuple[str, str]] = None) -> bool:
        """Launch the tunnel.  False (and ``failed``) when impossible."""
        if self._proc is not None:
            return True
        kind, path = program or find_tunnel()
        if not path:
            self.failed.emit("No tunnel program found. " + INSTALL_HINT)
            return False
        self._kind, self._token = kind, token
        self._base, self._output = "", ""
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.MergedChannels)
        proc.readyReadStandardOutput.connect(self._on_output)
        proc.finished.connect(self._on_finished)
        proc.errorOccurred.connect(self._on_error)
        self._proc = proc
        proc.start(path, tunnel_args(kind, port))
        self._timer.start(START_TIMEOUT_S * 1000)
        return True

    def stop(self):
        proc, self._proc = self._proc, None
        self._timer.stop()
        self._base = ""
        if proc is not None:
            proc.finished.disconnect(self._on_finished)
            proc.kill()
            proc.waitForFinished(2000)
            proc.deleteLater()
            self.stopped.emit()

    # ── Process events ──────────────────────────────────────────
    def _on_output(self):
        if self._proc is None:
            return
        chunk = bytes(self._proc.readAllStandardOutput()).decode(
            "utf-8", "replace")
        self._output = (self._output + chunk)[-8000:]
        if not self._base:
            base = parse_public_url(self._kind, self._output)
            if base:
                self._base = base
                self._timer.stop()
                self.ready.emit(self.url())

    def _on_finished(self, *_):
        tail = self._output.strip().splitlines()[-3:]
        self._drop()
        self.failed.emit(f"{self._kind} stopped. " + " ".join(tail))

    def _on_error(self, _err):
        if self._proc is not None and \
                self._proc.state() == QProcess.NotRunning:
            self._drop()
            self.failed.emit(f"Could not run {self._kind}.")

    def _timed_out(self):
        self.stop()
        self.failed.emit(f"{self._kind} did not give a public address "
                         f"within {START_TIMEOUT_S} s.")

    def _drop(self):
        self._timer.stop()
        self._base = ""
        if self._proc is not None:
            self._proc.deleteLater()
            self._proc = None
