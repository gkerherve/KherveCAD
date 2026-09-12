"""In-app half of KherveCAD's MCP support.

``McpBridge`` listens on a loopback TCP port and answers newline-
delimited JSON requests by running the tools in `mcp_tools.py` against
the live document.  ``mcp_server.py`` (spawned by the MCP host) and
``mcp_http.py`` are the only intended clients.

Why a socket rather than serving MCP from inside the app: MCP hosts
launch their servers as stdio subprocesses they own and restart at
will, while CAD tools must run on the Qt GUI thread of an
already-running window.  The socket is the seam between the two.

Security posture: the listener binds to 127.0.0.1 only, and every
request must carry the random token from the endpoint file, which is
written user-readable only.  The bridge is off unless the user turns
it on in AI ▸ Connect to Claude (Simple).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import json
import os
import secrets
import time
from collections import deque
from typing import Dict, Optional

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtNetwork import QHostAddress, QTcpServer, QTcpSocket

from . import __version__
from .mcp_server import endpoint_path, state_dir

#: 0 lets the OS pick a free port; the endpoint file carries the choice.
DEFAULT_PORT = 0

#: Refuse absurd payloads rather than buffering without bound.  An
#: apply_code call carries a program; only a render comes back large.
_MAX_LINE = 8 * 1024 * 1024

#: Tools that only look at the document (``select_nodes`` highlights
#: nodes in the window but changes nothing in the model, and being able
#: to point at what it is describing is exactly what a read-only client
#: should be able to do).  Wrapping these in an undo macro would litter
#: the stack with empty "MCP: list_tree" entries.
_READ_ONLY_TOOLS = frozenset({
    "get_document_info", "list_node_types", "list_tree", "get_node",
    "get_code", "render_view", "list_parts", "list_examples",
    "list_anchors", "select_nodes", "get_node_bounds", "measure",
    "section", "check_code", "list_edges", "mass_properties",
    "check_printability", "check_interference",
})

#: Tools that never change the document, so there is no snapshot to
#: force at the end of them (``save_document`` writes a file and
#: ``export_document`` can drive OpenSCAD for a minute, but neither
#: leaves an edit behind).
_NO_SNAPSHOT_TOOLS = _READ_ONLY_TOOLS | {
    "save_document", "export_document", "export_drawing",
    "publish_to_printables",
}

#: Tools that can read or write a file the client names.  Everything
#: else stays inside the window, where the worst case is a model the
#: user undoes; these reach the filesystem, so they are the ones held
#: back until the user raises the access level.
_FILE_TOOLS = frozenset({
    "open_document", "save_document", "export_document",
    "export_drawing", "publish_to_printables", "set_reference_image",
})


def _names_a_path(name: str, tool_input: dict) -> bool:
    """True if this call would read or write a client-chosen path.

    ``save_document`` with no path saves over the file the user already
    has open, which is the same thing Ctrl+S does — that stays allowed
    at the ordinary level.  A path is a different act.

    ``publish_to_printables`` always writes a folder of exports, and
    picks one itself when the client names none, so it counts either
    way.
    """
    if name == "publish_to_printables":
        return True
    return name in _FILE_TOOLS and bool((tool_input or {}).get("path"))


#: What a connected client is allowed to do, weakest first.  "full" is
#: the default, because the levels below it break the workflow people
#: actually came for: an assistant that cannot open the file you are
#: talking about, or save the part it just built, sends you back to the
#: File menu between every step.  The connection is loopback-only,
#: token-authenticated and off until the user turns it on, so the trust
#: decision has already been made by the time a tool runs; "read" and
#: "edit" stay for anyone who wants a narrower grant.
ACCESS_LEVELS = ("read", "edit", "full")
DEFAULT_ACCESS = "full"

#: How many recent calls the dialog's activity log shows.
_LOG_LEN = 200


def tool_allowed(name: str, access: str) -> bool:
    """Is *name* callable at this access level?"""
    if access in ("full", "edit"):
        return True
    return name in _READ_ONLY_TOOLS


class McpBridge(QObject):
    """Loopback JSON server exposing the CAD tools to MCP clients."""

    started = pyqtSignal(int)              # port
    stopped = pyqtSignal()
    tool_invoked = pyqtSignal(str, str)    # tool name, summary

    def __init__(self, mainwindow):
        super().__init__(mainwindow)
        self._mw = mainwindow
        self._server: Optional[QTcpServer] = None
        self._http = None            # McpHttpServer, when listening
        self._buffers: Dict[QTcpSocket, bytes] = {}
        self._token = ""
        self._executor = None
        self._access = DEFAULT_ACCESS
        self._busy = False
        self.log: deque = deque(maxlen=_LOG_LEN)

    # ── Lifecycle ───────────────────────────────────────────────

    def is_running(self) -> bool:
        return self._server is not None and self._server.isListening()

    def port(self) -> int:
        return self._server.serverPort() if self.is_running() else 0

    def token(self) -> str:
        return self._token

    def access(self) -> str:
        return self._access

    def set_access(self, level: str):
        """Change what connected clients may do, effective immediately.

        Hosts cache ``tools/list`` from their startup, so tightening
        this mid-session shows up as a refusal rather than a shorter
        tool list until they reconnect.
        """
        if level not in ACCESS_LEVELS:
            raise ValueError(f"Unknown access level {level!r}")
        self._access = level

    def visible_tools(self) -> list:
        """The tool table as this access level sees it."""
        from .mcp_schema import TOOLS
        return [t for t in TOOLS if tool_allowed(t["name"], self._access)]

    def start(self, port: int = DEFAULT_PORT) -> bool:
        """Begin listening.  Returns False (with no side effects) if
        the port could not be bound."""
        if self.is_running():
            return True
        server = QTcpServer(self)
        if not server.listen(QHostAddress.LocalHost, port):
            server.deleteLater()
            return False
        server.newConnection.connect(self._on_new_connection)
        self._server = server
        self._token = secrets.token_urlsafe(32)
        # Second door for clients that only take a URL.  Same loopback
        # binding, same token, same access level — a different skin on
        # the same bridge, not a wider one.
        from .mcp_http import McpHttpServer
        self._http = McpHttpServer(self)
        if not self._http.start():
            self._http = None
        self._write_endpoint()
        self.started.emit(server.serverPort())
        return True

    def http_url(self) -> str:
        """The Streamable HTTP endpoint, or "" when it is not up."""
        return self._http.url() if self._http is not None else ""

    def stop(self):
        if self._http is not None:
            self._http.stop()
            self._http = None
        if self._server is not None:
            for sock in list(self._buffers):
                sock.disconnectFromHost()
            self._buffers.clear()
            self._server.close()
            self._server.deleteLater()
            self._server = None
        self._token = ""
        self._clear_endpoint()
        self.stopped.emit()

    # ── Endpoint file ───────────────────────────────────────────

    def _write_endpoint(self):
        """Publish host/port/token so the stdio server can find us."""
        try:
            os.makedirs(state_dir(), exist_ok=True)
            path = endpoint_path()
            payload = {
                "host": "127.0.0.1",
                "port": self.port(),
                "token": self._token,
                "pid": os.getpid(),
                "version": __version__,
                "http_url": self.http_url(),
            }
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            try:
                os.chmod(path, 0o600)   # best effort; a no-op on Windows
            except OSError:
                pass
        except Exception:
            pass

    def _clear_endpoint(self):
        try:
            os.remove(endpoint_path())
        except OSError:
            pass

    # ── Socket plumbing ─────────────────────────────────────────

    def _on_new_connection(self):
        while (self._server is not None
               and self._server.hasPendingConnections()):
            sock = self._server.nextPendingConnection()
            self._buffers[sock] = b""
            sock.readyRead.connect(lambda s=sock: self._on_ready_read(s))
            sock.disconnected.connect(lambda s=sock: self._on_closed(s))

    def _on_closed(self, sock: QTcpSocket):
        self._buffers.pop(sock, None)
        sock.deleteLater()

    def _on_ready_read(self, sock: QTcpSocket):
        buf = self._buffers.get(sock, b"") + bytes(sock.readAll())
        if len(buf) > _MAX_LINE:
            sock.disconnectFromHost()
            self._buffers.pop(sock, None)
            return
        while b"\n" in buf:
            line, _, buf = buf.partition(b"\n")
            if line.strip():
                self._handle_line(sock, line)
        self._buffers[sock] = buf

    def _handle_line(self, sock: QTcpSocket, line: bytes):
        try:
            req = json.loads(line.decode("utf-8"))
        except Exception:
            self._reply(sock, None, error="Malformed JSON request.")
            return
        req_id = req.get("id")
        if not secrets.compare_digest(str(req.get("token", "")),
                                      self._token):
            self._reply(sock, req_id, error="Invalid bridge token.")
            return
        method = req.get("method")
        params = req.get("params") or {}
        try:
            if method == "get_status":
                self._reply(sock, req_id, result=self._status())
            elif method == "list_tools":
                self._reply(sock, req_id, result=self.visible_tools())
            elif method == "call_tool":
                self._reply(sock, req_id, result=self._call_tool(params))
            else:
                self._reply(sock, req_id,
                            error=f"Unknown bridge method: {method!r}")
        except Exception as exc:
            self._reply(sock, req_id, error=str(exc))

    def _reply(self, sock: QTcpSocket, req_id, *, result=None, error=None):
        payload = {"id": req_id}
        if error is not None:
            payload["error"] = error
        else:
            payload["result"] = result
        try:
            data = json.dumps(payload, default=str) + "\n"
        except Exception as exc:
            data = json.dumps(
                {"id": req_id,
                 "error": f"Unserialisable result: {exc}"}) + "\n"
        sock.write(data.encode("utf-8"))
        sock.flush()

    # ── Tool execution (main/GUI thread) ────────────────────────

    def _status(self) -> dict:
        model = self._mw.model
        return {
            "app": "KherveCAD",
            "version": __version__,
            "pid": os.getpid(),
            "access": self._access,
            "nodes": sum(1 for _ in model.root.walk()) - 1,
            "objects": [c.name for c in model.components()],
            "openscad": bool(self._mw.engine.available),
            "path": self._mw._path,
        }

    @staticmethod
    def _flush_snapshot(model, isolate: bool = False):
        """Take the model's pending undo snapshot now.

        `DocumentModel` captures one snapshot per event-loop *cycle*, on
        a 0 ms timer, so a tool call returns before its undo step
        exists.  A QUndoStack macro around the call therefore wraps
        nothing — and, being empty, pushes a do-nothing step of its own,
        which is worse than no macro at all: the user presses Ctrl+Z and
        sees nothing happen.  Forcing the capture on the way in (so the
        "before" state is current) and on the way out gives exactly one
        real step per call.

        *isolate* stops that step folding into the one before it.
        Snapshots pushed within `UNDO_MERGE_S` normally merge, which is
        right for a drag or a spinbox scrub — one gesture, one Ctrl+Z.
        Two tool calls are two gestures the user did not make, and they
        can easily land inside that window, so merging them would take
        away the ability to reject just the last one.
        """
        merge = model.UNDO_MERGE_S
        if isolate:
            model.UNDO_MERGE_S = -1.0     # any elapsed time refuses
        try:
            model._capture_timer.stop()
            model._capture()
        finally:
            model.UNDO_MERGE_S = merge

    def _record(self, name: str, outcome: str):
        self.log.append({"time": time.strftime("%H:%M:%S"),
                         "tool": name, "outcome": outcome})
        self.tool_invoked.emit(name, outcome)

    def _refuse(self, name: str, reason: str) -> dict:
        self._record(str(name), "refused")
        return {"error": f"Refused: {reason} The user can change this in "
                         f"AI ▸ Connect to Claude (Simple)."}

    def _call_tool(self, params: dict) -> dict:
        name = params.get("name")
        if not name:
            return {"error": "Missing tool name."}
        tool_input = params.get("input") or {}
        if not tool_allowed(name, self._access):
            return self._refuse(
                name, f"{name} would change the model, and MCP access "
                      f"is set to 'Read only'.")
        if self._access != "full" and _names_a_path(name, tool_input):
            return self._refuse(
                name, f"{name} with a path of its own reads or writes a "
                      f"file outside the open document, which needs MCP "
                      f"access set to 'Full'.")
        # An STL export drives OpenSCAD and pumps the Qt event loop
        # while it runs, which can deliver a second request into this
        # same handler.  Two tool calls interleaving on one document
        # would corrupt both, so make the second wait its turn by
        # failing.
        if self._busy:
            self._record(str(name), "busy")
            return {"error": "KherveCAD is still running the previous "
                             "tool call. Retry when it finishes."}
        if self._executor is None:
            from .mcp_tools import McpToolExecutor
            self._executor = McpToolExecutor(self._mw)
        # One undo step per mutating call keeps the app's promise: a
        # single Ctrl+Z reverts whatever the remote assistant just
        # built.  See _flush_snapshot for why a QUndoStack macro is the
        # wrong tool for it here.
        model = self._mw.model
        snapshot = name not in _NO_SNAPSHOT_TOOLS
        if snapshot:
            self._flush_snapshot(model)
        self._busy = True
        try:
            result = self._executor.execute(name, tool_input)
        finally:
            self._busy = False
            if snapshot:
                self._flush_snapshot(model, isolate=True)
        summary = (result.get("error") if isinstance(result, dict)
                   and "error" in result else "ok")
        self._record(str(name), str(summary))
        return result
