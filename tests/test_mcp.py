"""The MCP transports, access levels and host configuration.

`test_mcp_tools.py` covers what the tools do to a model; this covers
getting a request to them — the stdio handshake, the loopback bridge,
the HTTP door, the access gate and the host config writer.

Run with: python -m pytest tests/  (offscreen Qt).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import base64
import json
import os
import socket
import sys
import threading
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import mcp_hosts, mcp_schema, mcp_server
from khervecad.mcp_bridge import (ACCESS_LEVELS, DEFAULT_ACCESS,
                                    _names_a_path, tool_allowed)

_FAKE_TOOLS = [
    {"name": "list_tree", "description": "List the object tree.",
     "input_schema": {"type": "object", "properties": {}}},
]


# ── A stand-in for the in-app bridge, on a real socket ─────────────

class FakeBridge:
    def __init__(self):
        self.token = "s3cret-token"
        self.calls = []
        self._srv = socket.socket()
        self._srv.bind(("127.0.0.1", 0))
        self._srv.listen(4)
        self.port = self._srv.getsockname()[1]
        self._stop = False
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while not self._stop:
            try:
                conn, _ = self._srv.accept()
            except OSError:
                return
            threading.Thread(target=self._session, args=(conn,),
                             daemon=True).start()

    def _session(self, conn):
        buf = b""
        with conn:
            while not self._stop:
                try:
                    chunk = conn.recv(65536)
                except OSError:
                    return
                if not chunk:
                    return
                buf += chunk
                while b"\n" in buf:
                    line, _, buf = buf.partition(b"\n")
                    reply = self._handle(json.loads(line))
                    conn.sendall((json.dumps(reply) + "\n").encode())

    def _handle(self, req):
        if req.get("token") != self.token:
            return {"id": req.get("id"), "error": "Invalid bridge token."}
        method = req.get("method")
        if method == "get_status":
            return {"id": req["id"],
                    "result": {"version": "0.1.99+abc", "nodes": 0}}
        if method == "list_tools":
            return {"id": req["id"], "result": _FAKE_TOOLS}
        if method == "call_tool":
            self.calls.append(req["params"])
            if req["params"]["name"] == "boom":
                return {"id": req["id"],
                        "result": {"error": "no such node"}}
            if req["params"]["name"] == "render_view":
                png = base64.b64encode(
                    b"\x89PNG\r\n\x1a\n" + b"\0" * 8).decode()
                return {"id": req["id"],
                        "result": {mcp_server.IMAGE_KEY: png, "scale": 1.0}}
            return {"id": req["id"], "result": {"count": 0}}
        return {"id": req.get("id"), "error": f"unknown {method}"}

    def close(self):
        self._stop = True
        self._srv.close()


@pytest.fixture
def endpoint(tmp_path):
    fake = FakeBridge()
    path = tmp_path / "mcp-bridge.json"
    path.write_text(json.dumps({"host": "127.0.0.1", "port": fake.port,
                                "token": fake.token, "pid": 1,
                                "version": "0.1.99+abc"}))
    yield fake, str(path)
    fake.close()


@pytest.fixture
def server(endpoint):
    _fake, path = endpoint
    return mcp_server.McpServer(mcp_server.BridgeClient(path))


def _rpc(server, method, params=None, msg_id=1):
    return server.handle({"jsonrpc": "2.0", "id": msg_id,
                          "method": method, "params": params or {}})


# ── Handshake ──────────────────────────────────────────────────────

def test_initialize_echoes_a_protocol_the_client_asked_for(server):
    reply = _rpc(server, "initialize", {"protocolVersion": "2024-11-05"})
    assert reply["result"]["protocolVersion"] == "2024-11-05"


def test_initialize_falls_back_to_our_newest_protocol(server):
    reply = _rpc(server, "initialize", {"protocolVersion": "1999-01-01"})
    assert reply["result"]["protocolVersion"] == mcp_server.LATEST_PROTOCOL


def test_initialize_carries_the_briefing_the_host_will_not_write(server):
    text = _rpc(server, "initialize", {})["result"]["instructions"]
    assert "get_document_info" in text and "render_view" in text


def test_initialize_reports_the_running_app_version(server):
    info = _rpc(server, "initialize", {})["result"]["serverInfo"]
    assert info["name"] == "khervecad"
    assert info["version"] == "0.1.99+abc"


def test_initialize_still_answers_when_the_app_is_not_running(tmp_path):
    lonely = mcp_server.McpServer(
        mcp_server.BridgeClient(str(tmp_path / "absent.json")))
    reply = _rpc(lonely, "initialize", {})
    assert reply["result"]["serverInfo"]["version"] == "unknown"


def test_notifications_get_no_reply(server):
    assert server.handle({"method": "notifications/initialized"}) is None


def test_an_unknown_method_is_a_jsonrpc_error(server):
    reply = _rpc(server, "tools/explode")
    assert reply["error"]["code"] == -32601


def test_capability_probes_answer_empty_rather_than_failing(server):
    assert _rpc(server, "resources/list")["result"] == {"resources": []}
    assert _rpc(server, "prompts/list")["result"] == {"prompts": []}


# ── Tools over stdio ───────────────────────────────────────────────

def test_tools_list_comes_from_the_running_app(server):
    tools = _rpc(server, "tools/list")["result"]["tools"]
    assert [t["name"] for t in tools] == ["list_tree"]
    assert tools[0]["inputSchema"]["type"] == "object"


def test_a_tool_call_reaches_the_bridge(server, endpoint):
    fake, _path = endpoint
    reply = _rpc(server, "tools/call",
                 {"name": "list_tree", "arguments": {"depth": 1}})
    assert fake.calls == [{"name": "list_tree", "input": {"depth": 1}}]
    assert reply["result"]["isError"] is False


def test_a_tool_error_is_flagged_not_hidden(server):
    reply = _rpc(server, "tools/call", {"name": "boom", "arguments": {}})
    assert reply["result"]["isError"] is True
    assert "no such node" in reply["result"]["content"][0]["text"]


def test_a_render_comes_back_as_an_image_block(server):
    reply = _rpc(server, "tools/call",
                 {"name": "render_view", "arguments": {}})
    blocks = reply["result"]["content"]
    assert blocks[0]["type"] == "image"
    assert blocks[0]["mimeType"] == "image/png"
    # The rest of the result still travels, as text.
    assert "scale" in blocks[1]["text"]
    assert mcp_server.IMAGE_KEY not in blocks[1]["text"]


def test_a_dead_app_is_reported_in_plain_words(tmp_path):
    lonely = mcp_server.McpServer(
        mcp_server.BridgeClient(str(tmp_path / "absent.json")))
    reply = _rpc(lonely, "tools/call", {"name": "list_tree"})
    assert "Tools" in reply["error"]["message"]


def test_valid_png_b64_rejects_something_that_is_not_a_png():
    assert not mcp_server.valid_png_b64(base64.b64encode(b"nope").decode())
    assert mcp_server.valid_png_b64(
        base64.b64encode(b"\x89PNG\r\n\x1a\n").decode())


# ── The access gate ────────────────────────────────────────────────

def test_read_only_allows_looking_and_refuses_building():
    assert tool_allowed("list_tree", "read")
    assert tool_allowed("get_code", "read")
    assert tool_allowed("render_view", "read")
    assert not tool_allowed("add_node", "read")
    assert not tool_allowed("apply_code", "read")


def test_the_default_level_can_build():
    assert DEFAULT_ACCESS == "edit"
    for name in ("add_node", "wrap_nodes", "apply_code", "insert_part",
                 "new_document"):
        assert tool_allowed(name, "edit"), name


def test_every_tool_is_reachable_at_full():
    for tool in mcp_schema.TOOLS:
        assert tool_allowed(tool["name"], "full")


def test_a_client_chosen_path_is_what_needs_the_full_level():
    assert _names_a_path("save_document", {"path": "/tmp/x.kcad"})
    assert _names_a_path("export_document", {"path": "/tmp/x.stl"})
    # Saving over the file the user already has open is Ctrl+S, not a
    # reach into the filesystem.
    assert not _names_a_path("save_document", {})
    assert not _names_a_path("add_node", {"type": "cube"})


def test_access_levels_are_ordered_weakest_first():
    assert ACCESS_LEVELS == ("read", "edit", "full")


# ── The in-app bridge, end to end ──────────────────────────────────

@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def live(app, tmp_path, monkeypatch):
    """A real McpBridge on a real port, with its endpoint file in tmp."""
    from khervecad import mcp_bridge
    from khervecad.mainwindow import MainWindow
    path = tmp_path / "mcp-bridge.json"
    monkeypatch.setattr(mcp_bridge, "endpoint_path", lambda: str(path))
    monkeypatch.setattr(mcp_bridge, "state_dir", lambda: str(tmp_path))
    win = MainWindow()
    bridge = mcp_bridge.McpBridge(win)
    assert bridge.start()
    yield win, bridge, path
    bridge.stop()


def _ask(bridge, method, params=None, token=None):
    """One request over the bridge's real socket, pumping Qt meanwhile."""
    sock = socket.create_connection(("127.0.0.1", bridge.port()), timeout=5)
    payload = {"id": 1, "token": bridge.token() if token is None else token,
               "method": method, "params": params or {}}
    sock.sendall((json.dumps(payload) + "\n").encode())
    buf = b""
    while b"\n" not in buf:
        QApplication.processEvents()
        sock.settimeout(0.05)
        try:
            chunk = sock.recv(65536)
        except socket.timeout:
            continue
        if not chunk:
            break
        buf += chunk
    sock.close()
    return json.loads(buf.split(b"\n")[0])


def test_starting_publishes_an_endpoint_file_and_stopping_removes_it(live):
    _win, bridge, path = live
    info = json.loads(path.read_text())
    assert info["port"] == bridge.port()
    assert info["token"] == bridge.token()
    assert info["http_url"].startswith("http://127.0.0.1:")
    bridge.stop()
    assert not path.exists()


def test_a_wrong_token_gets_nothing(live):
    _win, bridge, _path = live
    assert "Invalid bridge token" in _ask(bridge, "get_status",
                                          token="guess")["error"]


def test_the_bridge_lists_and_runs_a_tool(live):
    _win, bridge, _path = live
    names = [t["name"] for t in _ask(bridge, "list_tools")["result"]]
    assert set(names) == set(mcp_schema.BY_NAME)
    reply = _ask(bridge, "call_tool",
                 {"name": "add_node", "input": {"type": "cube"}})
    assert reply["result"]["created"]


def test_read_only_shortens_the_tool_list_and_refuses_the_rest(live):
    _win, bridge, _path = live
    bridge.set_access("read")
    names = [t["name"] for t in _ask(bridge, "list_tools")["result"]]
    assert "add_node" not in names and "list_tree" in names
    reply = _ask(bridge, "call_tool", {"name": "add_node",
                                       "input": {"type": "cube"}})
    assert "Read only" in reply["result"]["error"]


def test_a_path_is_refused_below_the_full_level(live, tmp_path):
    _win, bridge, _path = live
    _ask(bridge, "call_tool", {"name": "add_node",
                               "input": {"type": "cube"}})
    reply = _ask(bridge, "call_tool",
                 {"name": "export_document",
                  "input": {"path": str(tmp_path / "x.scad")}})
    assert "Full" in reply["result"]["error"]
    bridge.set_access("full")
    reply = _ask(bridge, "call_tool",
                 {"name": "export_document",
                  "input": {"path": str(tmp_path / "x.scad")}})
    assert reply["result"].get("exported")


def test_one_tool_call_is_one_ctrl_z(live, app):
    """A program applied in one call comes back with a single Ctrl+Z,
    even though it created a dozen nodes and the model captures a
    snapshot per event-loop cycle."""
    window, bridge, _path = live
    app.processEvents()                       # settle the first snapshot
    stack = window.model.undo_stack
    depth = stack.count()
    _ask(bridge, "call_tool", {"name": "apply_code", "input": {"code": """
        difference() {
            cube([30, 20, 10]);
            translate([2, 2, -1]) cube([26, 16, 12]);
        }
        translate([0, 0, 20]) sphere(r = 5);
    """}})
    assert len(window.model.root.children) == 2
    assert stack.count() == depth + 1
    stack.undo()
    assert window.model.root.children == []


def test_two_calls_are_two_undo_steps(live, app):
    """Snapshots pushed close together normally merge — right for a
    drag, wrong for two edits the user did not make and may want to
    reject one at a time."""
    window, bridge, _path = live
    app.processEvents()
    stack = window.model.undo_stack
    depth = stack.count()
    for _ in range(2):
        _ask(bridge, "call_tool", {"name": "add_node",
                                   "input": {"type": "cube"}})
    assert len(window.model.root.children) == 2
    assert stack.count() == depth + 2
    stack.undo()
    assert len(window.model.root.children) == 1


def test_a_read_only_call_leaves_no_undo_step(live, app):
    window, bridge, _path = live
    _ask(bridge, "call_tool", {"name": "add_node",
                               "input": {"type": "cube"}})
    depth = window.model.undo_stack.count()
    for tool in ("list_tree", "get_code", "get_document_info"):
        _ask(bridge, "call_tool", {"name": tool, "input": {}})
    app.processEvents()
    assert window.model.undo_stack.count() == depth


def test_the_activity_log_records_what_was_run(live):
    _win, bridge, _path = live
    _ask(bridge, "call_tool", {"name": "get_document_info", "input": {}})
    assert bridge.log[-1]["tool"] == "get_document_info"
    assert bridge.log[-1]["outcome"] == "ok"


def test_an_unknown_bridge_method_is_an_error(live):
    _win, bridge, _path = live
    assert "Unknown bridge method" in _ask(bridge, "sing")["error"]


# ── Host configuration ─────────────────────────────────────────────

def test_the_snippet_names_this_installation():
    entry = json.loads(mcp_hosts.host_config())["mcpServers"]["khervecad"]
    assert entry["command"] == sys.executable
    assert entry["args"] == ["-m", "khervecad.mcp_server"]
    # `-m` only resolves if the checkout is importable, and the host
    # picks the working directory — PYTHONPATH is what travels.
    assert entry["env"]["PYTHONPATH"] == mcp_hosts.checkout_root()


def test_the_cli_command_is_runnable_as_shown():
    assert mcp_hosts.cli_command().startswith("claude mcp add khervecad")


def test_connecting_adds_our_entry_and_keeps_the_others(tmp_path):
    cfg = tmp_path / "claude_desktop_config.json"
    cfg.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))
    host = mcp_hosts.Host.for_file(str(cfg))
    assert host.connect()["ok"]
    doc = json.loads(cfg.read_text())
    assert set(doc["mcpServers"]) == {"other", "khervecad"}
    assert host.connected() and host.up_to_date()


def test_connecting_backs_the_old_config_up_first(tmp_path):
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"mcpServers": {}}))
    result = mcp_hosts.Host.for_file(str(cfg)).connect()
    assert Path(result["backup"]).exists()


def test_a_config_we_cannot_parse_is_never_overwritten(tmp_path):
    cfg = tmp_path / "cfg.json"
    cfg.write_text("{ not json at all")
    result = mcp_hosts.Host.for_file(str(cfg)).connect()
    assert not result["ok"]
    assert cfg.read_text() == "{ not json at all"


def test_disconnecting_removes_only_our_entry(tmp_path):
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))
    host = mcp_hosts.Host.for_file(str(cfg))
    host.connect()
    assert host.disconnect()["ok"]
    assert list(json.loads(cfg.read_text())["mcpServers"]) == ["other"]


def test_a_vscode_style_config_keeps_its_own_shape(tmp_path):
    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps({"servers": {}}))
    host = mcp_hosts.Host.for_file(str(cfg), shape="servers")
    host.entry_extra = {"type": "stdio"}
    host.connect()
    doc = json.loads(cfg.read_text())
    assert doc["servers"]["khervecad"]["type"] == "stdio"


def test_zed_is_left_alone_because_its_settings_hold_comments():
    zed = mcp_hosts.host_by_key("zed")
    assert zed.manual
    assert not zed.connect()["ok"]


# ── The HTTP door ──────────────────────────────────────────────────

def _http(bridge, body, headers=""):
    raw = json.dumps(body).encode()
    url = bridge.http_url()
    port = int(url.split(":")[2].split("/")[0])
    sock = socket.create_connection(("127.0.0.1", port), timeout=5)
    sock.sendall(
        f"POST /mcp HTTP/1.1\r\nHost: 127.0.0.1\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(raw)}\r\n{headers}\r\n".encode() + raw)
    buf = b""
    while b"\r\n\r\n" not in buf or not buf.split(b"\r\n\r\n", 1)[1]:
        QApplication.processEvents()
        sock.settimeout(0.05)
        try:
            chunk = sock.recv(65536)
        except socket.timeout:
            continue
        if not chunk:
            break
        buf += chunk
    sock.close()
    head, _, payload = buf.partition(b"\r\n\r\n")
    status = int(head.split(b" ")[1])
    return status, (json.loads(payload) if payload else None)


def test_http_needs_the_bearer_token(live):
    _win, bridge, _path = live
    status, _body = _http(bridge, {"jsonrpc": "2.0", "id": 1,
                                   "method": "ping"})
    assert status == 401


def test_http_answers_initialize_with_the_token(live):
    _win, bridge, _path = live
    status, body = _http(
        bridge, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {}},
        headers=f"Authorization: Bearer {bridge.token()}\r\n")
    assert status == 200
    assert body["result"]["serverInfo"]["name"] == "khervecad"


def test_http_refuses_a_web_page_origin(live):
    _win, bridge, _path = live
    status, body = _http(
        bridge, {"jsonrpc": "2.0", "id": 1, "method": "ping"},
        headers=(f"Authorization: Bearer {bridge.token()}\r\n"
                 "Origin: https://evil.example\r\n"))
    assert status == 403
    assert "Origin" in body["error"]
