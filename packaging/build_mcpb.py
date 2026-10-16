"""Build the Claude Desktop extension: dist/KherveCAD.mcpb.

A .mcpb is a zip with a manifest.json; Claude Desktop installs it with a
double-click and starts the server it names. The bundle carries the
shared launcher (plugins/khervecad/bin/khervecad_mcp.py), which runs the
installed KherveCAD app with --mcp-server, plus a copy of the stdlib-only
khervecad/mcp_server.py as a fallback — copied at build time, so it never
drifts from the app.

    python packaging/build_mcpb.py

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def manifest(version):
    return {
        "manifest_version": "0.2",
        "name": "khervecad",
        "display_name": "KherveCAD",
        "version": version,
        "description": "Drive a live KherveCAD window: parametric CAD on "
                       "the OpenSCAD engine.",
        "long_description": (
            "Build models as a real object tree that compiles to OpenSCAD, "
            "insert library parts, render the 3D view, check prints and "
            "export STL, STEP and drawings. KherveCAD must be running with "
            "AI > Connect to Claude switched on."),
        "author": {"name": "Gwilherm Kerherve",
                   "url": "https://khervetools.com"},
        "homepage": "https://khervetools.com",
        "repository": {"type": "git",
                       "url": "https://github.com/gkerherve/KherveCAD"},
        "license": "GPL-3.0",
        "icon": "icon.png",
        "keywords": ["cad", "openscad", "3d", "3d-printing"],
        "server": {
            "type": "python",
            "entry_point": "server/khervecad_mcp.py",
            "mcp_config": {
                "command": "python3",
                "args": ["${__dirname}/server/khervecad_mcp.py"],
                "env": {"KHERVECAD_EXE": "${user_config.executable}"},
            },
        },
        "user_config": {
            "executable": {
                "type": "file",
                "title": "KherveCAD executable",
                "description": "Only needed when KherveCAD is not in the "
                               "usual install folder.",
                "required": False,
                "default": "",
            },
        },
        "compatibility": {
            "platforms": ["darwin", "win32", "linux"],
            "runtimes": {"python": ">=3.8"},
        },
    }


def build(out=None):
    from khervecad._version import get_version
    version = get_version().split("+")[0]
    out = out or os.path.join(ROOT, "dist", "KherveCAD.mcpb")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest(version), indent=2))
        z.write(os.path.join(ROOT, "plugins", "khervecad", "bin",
                             "khervecad_mcp.py"), "server/khervecad_mcp.py")
        z.writestr("server/khervecad/__init__.py", "")
        z.write(os.path.join(ROOT, "khervecad", "mcp_server.py"),
                "server/khervecad/mcp_server.py")
        z.write(os.path.join(ROOT, "packaging", "khervecad.png"), "icon.png")
    return out


if __name__ == "__main__":
    print(build())
