# KherveCAD — GPL-3.0-or-later. See LICENSE.
"""The Claude Code plugin and the Claude Desktop extension stay usable."""

import json
import os
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugins", "khervecad")
LAUNCHER = os.path.join(PLUGIN, "bin", "khervecad_mcp.py")


def _server_name(cmd, env):
    """Answer an MCP initialize (needs no running window)."""
    req = (b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":'
           b'{"protocolVersion":"2025-06-18","capabilities":{},'
           b'"clientInfo":{"name":"test","version":"1"}}}\n')
    out = subprocess.run(cmd, input=req, capture_output=True, env=env,
                         timeout=30).stdout
    return json.loads(out.splitlines()[0])["result"]["serverInfo"]["name"]


def test_manifests_point_at_the_plugin():
    market = json.load(open(os.path.join(ROOT, ".claude-plugin",
                                         "marketplace.json")))
    src = market["plugins"][0]["source"]
    assert os.path.normpath(os.path.join(ROOT, src)) == PLUGIN
    json.load(open(os.path.join(PLUGIN, ".claude-plugin", "plugin.json")))
    mcp = json.load(open(os.path.join(PLUGIN, ".mcp.json")))
    assert "bin/khervecad_mcp.py" in mcp["mcpServers"]["khervecad"]["args"][0]


def test_launcher_starts_the_server():
    env = dict(os.environ, KHERVECAD_SOURCE=ROOT)
    assert _server_name([sys.executable, LAUNCHER], env) == "khervecad"


def test_desktop_bundle_runs_on_its_own(tmp_path):
    sys.path.insert(0, os.path.join(ROOT, "packaging"))
    import build_mcpb
    out = build_mcpb.build(str(tmp_path / "k.mcpb"))
    with zipfile.ZipFile(out) as z:
        man = json.loads(z.read("manifest.json"))
        z.extractall(tmp_path / "x")
    assert man["server"]["entry_point"] in z.namelist()
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path)}
    launcher = str(tmp_path / "x" / man["server"]["entry_point"])
    assert _server_name([sys.executable, "-I", launcher], env) == "khervecad"
