"""A second way in for MCP clients that only speak HTTP.

The stdio server suits clients that spawn a subprocess.  Others — Open
WebUI, n8n, some IDE setups — only take a URL, so this answers MCP
directly over HTTP at ``http://127.0.0.1:<port>/mcp``.

It binds to loopback only, exactly like the stdio bridge, and is not a
step towards exposing the model to the internet: the tools rebuild
someone's open document and the auth is a per-session bearer token,
both of which are right for a local client and wrong for a public
one.  Two things follow from that and are enforced below:

* ``Origin`` is validated on every request.  A page in the user's
  browser can POST to 127.0.0.1 without any CORS preflight, so a
  hostile site could otherwise drive the model — the DNS-rebinding
  hole the MCP spec warns local servers about.
* The bearer token is required on every request, as on the stdio side.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import json
from typing import Optional
from urllib.parse import urlparse

from PyQt5.QtCore import QObject
from PyQt5.QtNetwork import QHostAddress, QTcpServer

from .mcp_server import (
    LATEST_PROTOCOL, SERVER_NAME, SUPPORTED_PROTOCOLS, _INSTRUCTIONS,
    tool_content,
)

#: Path the MCP endpoint answers on.
ENDPOINT_PATH = "/mcp"

#: Cap on a request body.  Generous for a tool call, small enough that
#: a runaway client cannot exhaust memory.
_MAX_BODY = 8 * 1024 * 1024

#: Origins a browser page could present that we accept.  Anything else
#: is refused: a local server with no CORS preflight is reachable from
#: any web page the user happens to have open.
_ALLOWED_ORIGIN_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}


def _origin_ok(origin: str) -> bool:
    """True when *origin* is absent or points back at this machine."""
    if not origin:
        return True          # non-browser client: no Origin header
    if origin == "null":
        return False
    try:
        host = urlparse(origin).hostname or ""
    except ValueError:
        return False
    return host.lower() in _ALLOWED_ORIGIN_HOSTS


class _Request:
    """A parsed HTTP request, or None-ish while still arriving."""

    __slots__ = ("method", "path", "headers", "body")

    def __init__(self, method, path, headers, body):
        self.method = method
        self.path = path
        self.headers = headers
        self.body = body

    @classmethod
    def parse(cls, raw: bytes) -> Optional["_Request"]:
        """Parse *raw*, or return None when the message is incomplete."""
        if b"\r\n\r\n" not in raw:
            return None
        head, _, rest = raw.partition(b"\r\n\r\n")
        try:
            lines = head.decode("latin-1").split("\r\n")
            method, path, _ = lines[0].split(" ", 2)
        except (UnicodeDecodeError, ValueError):
            raise ValueError("malformed request line")
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        try:
            length = int(headers.get("content-length", "0"))
        except ValueError:
            raise ValueError("bad Content-Length")
        if length > _MAX_BODY:
            raise ValueError("request body too large")
        if len(rest) < length:
            return None                      # keep reading
        return cls(method, path, headers, rest[:length])


_STATUS = {
    200: "OK", 202: "Accepted", 400: "Bad Request",
    401: "Unauthorized", 403: "Forbidden", 404: "Not Found",
    405: "Method Not Allowed", 413: "Payload Too Large",
    500: "Internal Server Error",
}


class McpHttpServer(QObject):
    """Answers MCP over HTTP on 127.0.0.1, backed by ``McpBridge``.

    The bridge owns the tool table, the access level and the undo
    macros; this class is only the protocol skin, so both transports
    behave identically and the activity log stays in one place.
    """

    def __init__(self, bridge, parent=None):
        super().__init__(parent or bridge)
        self._bridge = bridge
        self._server: Optional[QTcpServer] = None

    # ── Lifecycle ───────────────────────────────────────────────
    def start(self, port: int = 0) -> bool:
        if self._server is not None:
            return True
        server = QTcpServer(self)
        if not server.listen(QHostAddress.LocalHost, port):
            return False
        server.newConnection.connect(self._on_connection)
        self._server = server
        return True

    def stop(self):
        if self._server is not None:
            self._server.close()
            self._server.deleteLater()
            self._server = None

    def is_running(self) -> bool:
        return self._server is not None and self._server.isListening()

    def port(self) -> int:
        return self._server.serverPort() if self.is_running() else 0

    def url(self) -> str:
        return (f"http://127.0.0.1:{self.port()}{ENDPOINT_PATH}"
                if self.is_running() else "")

    # ── Connection handling ─────────────────────────────────────
    def _on_connection(self):
        while self._server and self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            sock.setProperty("buf", b"")
            sock.readyRead.connect(lambda s=sock: self._on_ready(s))
            sock.disconnected.connect(sock.deleteLater)

    def _on_ready(self, sock):
        buf = bytes(sock.property("buf") or b"") + bytes(sock.readAll())
        if len(buf) > _MAX_BODY + 65536:
            self._send(sock, 413, {"error": "request too large"})
            return
        try:
            req = _Request.parse(buf)
        except ValueError as exc:
            self._send(sock, 400, {"error": str(exc)})
            return
        if req is None:
            sock.setProperty("buf", buf)     # incomplete; wait
            return
        sock.setProperty("buf", b"")
        try:
            self._dispatch(sock, req)
        except Exception as exc:             # never drop the listener
            self._send(sock, 500, {"error": str(exc)})

    def _dispatch(self, sock, req: _Request):
        if not _origin_ok(req.headers.get("origin", "")):
            # A web page trying to reach the model through the
            # user's own browser.  Refuse before authenticating.
            self._send(sock, 403,
                       {"error": "Origin not allowed for this local "
                                 "server."})
            return
        path = req.path.split("?", 1)[0].rstrip("/") or "/"
        if path != ENDPOINT_PATH:
            self._send(sock, 404, {"error": f"Try {ENDPOINT_PATH}."})
            return
        if req.method == "GET":
            # Streamable HTTP allows a GET for a server-initiated SSE
            # stream.  Nothing here pushes, so decline politely rather
            # than hold a socket open forever.
            self._send(sock, 405,
                       {"error": "This server does not stream; POST "
                                 "JSON-RPC to this URL."})
            return
        if req.method == "DELETE":
            self._send(sock, 200, {"ok": True})   # session teardown
            return
        if req.method != "POST":
            self._send(sock, 405, {"error": "Use POST."})
            return
        if not self._authorised(req):
            self._send(sock, 401,
                       {"error": "Missing or invalid bearer token. It "
                                 "is in KherveCAD's endpoint file."})
            return
        try:
            msg = json.loads(req.body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            self._send(sock, 400, _rpc_error(
                None, -32700, "Parse error: body is not JSON."))
            return
        if isinstance(msg, list):
            replies = [r for r in (self._handle(m) for m in msg)
                       if r is not None]
            self._send(sock, 200 if replies else 202, replies or None)
            return
        reply = self._handle(msg)
        self._send(sock, 200 if reply is not None else 202, reply)

    def _authorised(self, req: _Request) -> bool:
        want = self._bridge.token()
        got = req.headers.get("authorization", "")
        if got.lower().startswith("bearer "):
            got = got[7:].strip()
        else:
            got = req.headers.get("x-khervecad-token", "").strip()
        import secrets
        return bool(want) and secrets.compare_digest(got, want)

    # ── MCP methods ─────────────────────────────────────────────
    def _handle(self, msg) -> Optional[dict]:
        """Answer one JSON-RPC message.  None means 'notification'."""
        if not isinstance(msg, dict):
            return _rpc_error(None, -32600, "Invalid request.")
        method = msg.get("method")
        msg_id = msg.get("id")
        if method is None:
            return None                       # a response: ignore
        try:
            if method == "initialize":
                result = self._initialize(msg.get("params") or {})
            elif method in ("notifications/initialized", "initialized",
                            "notifications/cancelled"):
                return None
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": self._tools()}
            elif method == "tools/call":
                result = self._call(msg.get("params") or {})
            elif method in ("resources/list",
                            "resources/templates/list"):
                key = ("resourceTemplates"
                       if method.endswith("templates/list")
                       else "resources")
                result = {key: []}
            elif method == "prompts/list":
                result = {"prompts": []}
            else:
                if msg_id is None:
                    return None
                return _rpc_error(msg_id, -32601,
                                  f"Unknown method: {method}")
        except Exception as exc:
            if msg_id is None:
                return None
            return _rpc_error(msg_id, -32603, f"Internal error: {exc}")
        if msg_id is None:
            return None
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def _initialize(self, params: dict) -> dict:
        asked = params.get("protocolVersion")
        version = (asked if asked in SUPPORTED_PROTOCOLS
                   else LATEST_PROTOCOL)
        from . import __version__
        return {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False},
                             "resources": {}, "prompts": {}},
            "serverInfo": {"name": SERVER_NAME, "title": "KherveCAD",
                           "version": __version__},
            "instructions": _INSTRUCTIONS,
        }

    def _tools(self) -> list:
        # visible_tools() already filters by the user's access level.
        return [
            {"name": t["name"],
             "description": t.get("description", ""),
             "inputSchema": t.get("input_schema",
                                  {"type": "object", "properties": {}})}
            for t in self._bridge.visible_tools()
        ]

    def _call(self, params: dict) -> dict:
        name = params.get("name")
        if not name:
            raise ValueError("tools/call requires a tool name.")
        result = self._bridge._call_tool(
            {"name": name, "input": params.get("arguments") or {}})
        is_error = isinstance(result, dict) and "error" in result
        # Same shaping as the stdio server: a rendered view travels as
        # a real image block, not a wall of base64 in a text block.
        return {"content": tool_content(result), "isError": bool(is_error)}

    # ── Response writing ────────────────────────────────────────
    def _send(self, sock, status: int, payload):
        body = b"" if payload is None else json.dumps(
            payload, default=str).encode("utf-8")
        head = (
            f"HTTP/1.1 {status} {_STATUS.get(status, 'OK')}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            # No CORS grant: a browser page must not be able to read
            # replies from this server even if it manages to POST.
            f"Cache-Control: no-store\r\n"
            f"Connection: close\r\n\r\n"
        ).encode("latin-1")
        sock.write(head + body)
        sock.flush()
        sock.disconnectFromHost()


def _rpc_error(msg_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id,
            "error": {"code": code, "message": message}}
