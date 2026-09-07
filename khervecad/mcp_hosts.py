"""Write KherveCAD's entry into an MCP host's own config file.

Hand-editing ``claude_desktop_config.json`` is the step that stops
people using the bridge at all, and the installed application already
knows the one thing a hand-edit gets wrong — the path to its own
executable.  So it writes the entry itself.

Deliberately Qt-free: the dialog is a thin layer over this, and the
merge logic is the part worth testing without a window.

Every write here touches a file another application owns, so the rules
are strict: never clobber a file we could not parse, always back up
first, always write atomically, and never touch a key that is not ours.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from typing import List, Optional

from .mcp_server import SERVER_NAME


# ── The entry itself ───────────────────────────────────────────────

def launch_command() -> list:
    """Argv an MCP host should run to reach this installation.

    A frozen build re-executes itself with ``--mcp-server``; a source
    checkout runs the module under the same interpreter.
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, "--mcp-server"]
    return [sys.executable, "-m", "khervecad.mcp_server"]


def checkout_root() -> str:
    """Directory containing the ``khervecad`` package."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def server_entry() -> dict:
    """The ``mcpServers`` value describing this installation."""
    argv = launch_command()
    entry = {"command": argv[0], "args": argv[1:]}
    if not getattr(sys, "frozen", False):
        # `-m khervecad.mcp_server` only resolves if the checkout is
        # importable, and the host picks the working directory.  A
        # "cwd" key does not travel — Claude Code drops it — so the
        # server died with ModuleNotFoundError before it could answer
        # initialize, which the host reports as "Server disconnected".
        # PYTHONPATH is passed through by every host, so use that.
        entry["env"] = {"PYTHONPATH": checkout_root()}
    return entry


def host_config(indent: int = 2) -> str:
    """JSON snippet for a host whose config file we cannot safely edit."""
    return json.dumps({"mcpServers": {SERVER_NAME: server_entry()}},
                      indent=indent)


def cli_command() -> str:
    """One-liner for `claude mcp add`."""
    argv = launch_command()
    quoted = " ".join(f'"{a}"' if " " in a else a for a in argv)
    env = ""
    if not getattr(sys, "frozen", False):
        env = f'-e PYTHONPATH="{checkout_root()}" '
    return f"claude mcp add {SERVER_NAME} {env}-- {quoted}"


# ── Known hosts ────────────────────────────────────────────────────

class Host:
    """One MCP host we know how to configure.

    *path_by_platform* maps ``sys.platform`` prefixes to the config
    file.  *manual* marks a host whose file we refuse to rewrite — Zed
    keeps comments in its settings, and json.dump would silently eat
    them — so the user gets the snippet instead.
    """

    def __init__(self, key, label, paths, note="", manual=False,
                 cli=None, shape="mcpServers", entry_extra=None):
        self.key = key
        self.label = label
        self._paths = paths
        self.note = note
        self.manual = manual
        self.cli = cli            # argv prefix, for CLI-managed hosts
        #: Top-level key holding the server table.  Most clients copied
        #: Claude Desktop's "mcpServers"; VS Code uses "servers".
        self.shape = shape
        #: Extra keys this client wants inside the entry itself.
        self.entry_extra = entry_extra or {}
        self._override_path = None

    @classmethod
    def for_file(cls, path: str, shape: str = "mcpServers"):
        """A one-off host for a config file the user picked themselves.

        The named entries below cannot cover every MCP client, and
        guessing a path wrongly is worse than asking, so the dialog
        offers this for anything not listed.
        """
        h = cls("custom", os.path.basename(path) or "config", {},
                note="Restart the application to pick up the change.",
                shape=shape)
        h._override_path = os.path.abspath(os.path.expanduser(path))
        return h

    def entry(self) -> dict:
        e = dict(server_entry())
        e.update(self.entry_extra)
        return e

    def path(self) -> Optional[str]:
        if self._override_path:
            return self._override_path
        for prefix, tail in self._paths.items():
            if sys.platform.startswith(prefix):
                return os.path.expandvars(os.path.expanduser(tail))
        return None

    # ── State ───────────────────────────────────────────────────
    def exists(self) -> bool:
        """Is this host installed?  Its config dir is the tell."""
        p = self.path()
        if not p:
            return False
        return os.path.exists(p) or os.path.isdir(os.path.dirname(p))

    def connected(self) -> bool:
        """Is KherveCAD already in this host's config?"""
        doc = self._read()
        if doc is None:
            return False
        return SERVER_NAME in (doc.get(self.shape) or {})

    def up_to_date(self) -> bool:
        """Is the entry present *and* pointing at this installation?"""
        doc = self._read()
        if doc is None:
            return False
        return (doc.get(self.shape) or {}).get(SERVER_NAME) == \
            self.entry()

    def status(self) -> str:
        if not self.exists():
            return "not installed"
        if not self.connected():
            return "not connected"
        if not self.up_to_date():
            return "connected (points elsewhere)"
        return "connected"

    # ── File access ─────────────────────────────────────────────
    def _read(self) -> Optional[dict]:
        """Parsed config, or None when absent/unreadable/not an object."""
        p = self.path()
        if not p or not os.path.isfile(p):
            return None
        try:
            with open(p, "r", encoding="utf-8") as fh:
                text = fh.read().strip()
        except OSError:
            return None
        if not text:
            return {}
        try:
            doc = json.loads(text)
        except ValueError:
            return None
        return doc if isinstance(doc, dict) else None

    def _write(self, doc: dict) -> str:
        """Back up, then replace the config atomically.  Returns path."""
        p = self.path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        backup = ""
        if os.path.isfile(p):
            backup = f"{p}.khervecad-{time.strftime('%Y%m%d-%H%M%S')}.bak"
            shutil.copy2(p, backup)
        tmp = f"{p}.khervecad-tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, p)         # atomic: never a half-written config
        return backup

    # ── Mutation ────────────────────────────────────────────────
    def connect(self) -> dict:
        """Add or refresh KherveCAD's entry.  Returns a report."""
        if self.manual:
            return {"ok": False, "manual": True, "host": self.label,
                    "error": (f"{self.label} keeps comments in its "
                              "settings file, which rewriting would "
                              "discard. Copy the snippet in instead.")}
        if self.cli:
            return self._connect_via_cli()
        p = self.path()
        if not p:
            return {"ok": False, "host": self.label,
                    "error": f"{self.label} is not supported on "
                             f"{sys.platform}."}
        doc = self._read()
        if doc is None and os.path.isfile(p):
            return {"ok": False, "host": self.label, "path": p,
                    "error": (f"{p} is not valid JSON. Fix or remove it "
                              "first — overwriting it would throw away "
                              "your other servers.")}
        doc = doc if doc is not None else {}
        servers = doc.setdefault(self.shape, {})
        if not isinstance(servers, dict):
            return {"ok": False, "host": self.label, "path": p,
                    "error": f"'{self.shape}' in {p} is not an object."}
        existed = SERVER_NAME in servers
        servers[SERVER_NAME] = self.entry()
        try:
            backup = self._write(doc)
        except OSError as exc:
            return {"ok": False, "host": self.label, "path": p,
                    "error": f"Could not write {p}: {exc}"}
        return {"ok": True, "host": self.label, "path": p,
                "backup": backup, "action": "updated" if existed
                else "added", "restart": True}

    def disconnect(self) -> dict:
        """Remove KherveCAD's entry, leaving every other one alone."""
        if self.cli:
            return self._disconnect_via_cli()
        p = self.path()
        doc = self._read()
        if doc is None:
            return {"ok": False, "host": self.label,
                    "error": f"Could not read {p}."}
        servers = doc.get(self.shape)
        if not isinstance(servers, dict) or SERVER_NAME not in servers:
            return {"ok": True, "host": self.label, "path": p,
                    "action": "already absent"}
        servers.pop(SERVER_NAME)
        try:
            backup = self._write(doc)
        except OSError as exc:
            return {"ok": False, "host": self.label, "path": p,
                    "error": f"Could not write {p}: {exc}"}
        return {"ok": True, "host": self.label, "path": p,
                "backup": backup, "action": "removed", "restart": True}

    # ── CLI-managed hosts ───────────────────────────────────────
    #
    # Claude Code keeps its servers in ~/.claude.json alongside a great
    # deal of unrelated session state.  Its own CLI owns that file's
    # shape, so drive that rather than reaching into it.
    def _run_cli(self, args: List[str]) -> dict:
        exe = shutil.which(self.cli[0])
        if not exe:
            return {"ok": False, "host": self.label,
                    "error": (f"The '{self.cli[0]}' command is not on "
                              "PATH, so its config cannot be edited "
                              "safely. Run the command shown below in a "
                              "terminal instead.")}
        try:
            proc = subprocess.run([exe] + args, capture_output=True,
                                  text=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as exc:
            return {"ok": False, "host": self.label,
                    "error": f"Could not run {self.cli[0]}: {exc}"}
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            return {"ok": False, "host": self.label,
                    "error": f"{self.cli[0]} failed: {detail}"}
        return {"ok": True, "host": self.label,
                "output": (proc.stdout or "").strip()}

    def _connect_via_cli(self) -> dict:
        # Remove first so a stale entry is replaced rather than
        # rejected: `claude mcp add` refuses a name that already exists.
        self._run_cli(["mcp", "remove", SERVER_NAME])
        argv = launch_command()
        args = ["mcp", "add", SERVER_NAME]
        if not getattr(sys, "frozen", False):
            args += ["-e", f"PYTHONPATH={checkout_root()}"]
        args += ["--"] + argv
        out = self._run_cli(args)
        if out.get("ok"):
            out.update(action="added", path="managed by the claude CLI",
                       restart=False)
        return out

    def _disconnect_via_cli(self) -> dict:
        out = self._run_cli(["mcp", "remove", SERVER_NAME])
        if out.get("ok"):
            out.update(action="removed", path="managed by the claude CLI",
                       restart=False)
        return out


#: Hosts we can configure, in the order the dialog lists them.
HOSTS = [
    Host("claude-desktop", "Claude Desktop", {
        "darwin": "~/Library/Application Support/Claude/"
                  "claude_desktop_config.json",
        "win": "%APPDATA%/Claude/claude_desktop_config.json",
        "linux": "~/.config/Claude/claude_desktop_config.json",
    }, note="Restart Claude Desktop to pick up the change."),
    Host("claude-code", "Claude Code", {
        "darwin": "~/.claude.json",
        "win": "~/.claude.json",
        "linux": "~/.claude.json",
    }, note="Applied through the claude CLI. Reconnect the session to "
            "see the tools.",
       cli=["claude"]),
    Host("cursor", "Cursor", {
        "darwin": "~/.cursor/mcp.json",
        "win": "~/.cursor/mcp.json",
        "linux": "~/.cursor/mcp.json",
    }, note="Restart Cursor to pick up the change."),
    Host("windsurf", "Windsurf", {
        "darwin": "~/.codeium/windsurf/mcp_config.json",
        "win": "~/.codeium/windsurf/mcp_config.json",
        "linux": "~/.codeium/windsurf/mcp_config.json",
    }, note="Restart Windsurf to pick up the change."),
    Host("vscode", "VS Code (Copilot)", {
        "darwin": "~/Library/Application Support/Code/User/mcp.json",
        "win": "%APPDATA%/Code/User/mcp.json",
        "linux": "~/.config/Code/User/mcp.json",
    }, note="Restart VS Code, or run 'MCP: List Servers' to start it.",
       shape="servers", entry_extra={"type": "stdio"}),
    Host("cline", "Cline (VS Code)", {
        "darwin": "~/Library/Application Support/Code/User/globalStorage/"
                  "saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
        "win": "%APPDATA%/Code/User/globalStorage/"
               "saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
        "linux": "~/.config/Code/User/globalStorage/"
                 "saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
    }, note="Cline reloads its servers on its own."),
    Host("lmstudio", "LM Studio", {
        "darwin": "~/.lmstudio/mcp.json",
        "win": "~/.lmstudio/mcp.json",
        "linux": "~/.lmstudio/mcp.json",
    }, note="Restart LM Studio to pick up the change."),
    Host("zed", "Zed", {
        "darwin": "~/.config/zed/settings.json",
        "win": "%APPDATA%/Zed/settings.json",
        "linux": "~/.config/zed/settings.json",
    }, note="Zed's settings file allows comments, so KherveCAD will "
            "not rewrite it. Copy the snippet in by hand.",
       manual=True),
]


def host_by_key(key: str) -> Optional[Host]:
    for h in HOSTS:
        if h.key == key:
            return h
    return None


def detected() -> List[Host]:
    """Hosts that appear to be installed on this machine."""
    return [h for h in HOSTS if h.exists()]
