"""Runtime-derived version string.

The version is the commit count, `git rev-list --count HEAD` — "1025",
shown as kCAD v1025 (2026-11-13, the user: no more "0.1." and no more
letters after it). It bumps on every commit without anyone editing a
constant. The commit's short sha is kept apart (:func:`get_commit`) for
the updater's "what changed" list; it is never shown.

A frozen build ships no `.git`, so `packaging/build_installer.py` writes
the resolved number (and, on a second line, the sha) into a `VERSION` file next to this module just
before PyInstaller runs and that file is read first. A copy with
neither a bundled VERSION nor a `.git` folder falls back to
``_FALLBACK``.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import re
import subprocess
from functools import lru_cache
from pathlib import Path

_FALLBACK = "0"


def _git(*args):
    root = Path(__file__).resolve().parent.parent
    if not (root / ".git").exists():
        return ""
    try:
        return subprocess.check_output(
            ["git", *args], cwd=root, stderr=subprocess.DEVNULL,
        ).strip().decode()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return ""


def _bundled():
    """The lines of a frozen build's VERSION file ([] when none)."""
    bundled = Path(__file__).resolve().parent / "VERSION"
    if bundled.is_file():
        return [ln.strip() for ln in
                bundled.read_text(encoding="utf-8").splitlines()]
    return []


@lru_cache(maxsize=1)
def get_version() -> str:
    lines = _bundled()
    if lines and lines[0]:
        # (an older VERSION file wrote "0.1.N+sha": its N is the version)
        m = re.fullmatch(r"(?:\d+\.\d+\.)?(\d+)(?:\+\w+)?", lines[0])
        return m.group(1) if m else lines[0]
    count = _git("rev-list", "--count", "HEAD")
    return count if count.isdigit() else _FALLBACK


@lru_cache(maxsize=1)
def get_commit() -> str:
    """The short sha this build was made from ('' when unknown)."""
    lines = _bundled()
    if lines:
        if len(lines) > 1 and lines[1]:
            return lines[1]
        m = re.fullmatch(r".*\+(\w+)", lines[0])
        return m.group(1) if m else ""
    return _git("rev-parse", "--short", "HEAD")
