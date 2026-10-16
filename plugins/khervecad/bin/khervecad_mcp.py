"""Start KherveCAD's MCP stdio server for an MCP host.

Shared by the Claude Code plugin and the Claude Desktop extension. The
real server lives in the KherveCAD app (``--mcp-server``) or package
(``khervecad.mcp_server``); this script only finds one and hands over
stdin/stdout, so the tools never drift from the installed app.

Search order: $KHERVECAD_EXE, the usual install folders, a source
checkout ($KHERVECAD_SOURCE, or the repository this file sits in), and
last a copy of mcp_server.py bundled beside this script.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def app_candidates():
    env = os.environ.get("KHERVECAD_EXE")
    if env:
        yield env
    if sys.platform == "darwin":
        for root in ("/Applications", os.path.expanduser("~/Applications")):
            yield os.path.join(root, "KherveCAD.app", "Contents", "MacOS",
                               "KherveCAD")
    elif os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "")
        yield os.path.join(local, "Programs", "KherveCAD", "KherveCAD.exe")
        for var in ("ProgramFiles", "ProgramFiles(x86)"):
            yield os.path.join(os.environ.get(var, ""), "KherveCAD",
                               "KherveCAD.exe")


def source_candidates():
    env = os.environ.get("KHERVECAD_SOURCE")
    if env:
        yield env
    # plugins/khervecad/bin -> repository root
    yield os.path.normpath(os.path.join(HERE, "..", "..", ".."))
    yield HERE  # the Desktop bundle ships khervecad/mcp_server.py here


def main():
    args = sys.argv[1:]
    for exe in app_candidates():
        if exe and os.path.isfile(exe):
            return subprocess.call([exe, "--mcp-server"] + args)
    for root in source_candidates():
        if os.path.isfile(os.path.join(root, "khervecad", "mcp_server.py")):
            sys.path.insert(0, root)
            from khervecad.mcp_server import main as serve
            return serve(args)
    sys.stderr.write(
        "KherveCAD not found. Install it from khervetools.com, or set "
        "KHERVECAD_EXE to the KherveCAD executable.\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
