"""Automatic updates from the GitHub releases.

Help > Check for Updates... asks GitHub for the newest release built for
this platform, and if it is newer than the running build shows what
changed and offers to install it:

* **Windows** -- releases tagged ``v0.1.N`` carrying the Inno Setup
  installer ``KherveCAD-Setup-0.1.N.exe``. It is downloaded, the app
  closes, and the installer runs silently; the ``[Run]`` entry that
  ``packaging/khervecad.iss`` keeps for silent mode starts the new build
  when it is done.
* **macOS** -- releases tagged ``macos-v0.1.N`` carrying the arm64 DMG.
  The DMG is mounted, and a detached shell script waits for this process
  to exit, swaps the ``.app`` bundle for the one in the image and opens
  it again. A bundle that cannot be replaced in place (a read-only
  folder, App Translocation, run from the DMG) gets the DMG opened in
  Finder instead.
* **Anything else**, a portable Windows copy, and a source checkout only
  report the new version and offer the release page.

The version number *is* the commit count (``_version.py``), so releases
compare on the ``N`` in ``0.1.N`` and "what changed" is two lists: the
notes of every release newer than the running one, and the commit
subjects between the running sha and the release tag (GitHub's compare
API), grouped by their ``feat:`` / ``fix:`` ... prefix.

An installed build checks by itself a few seconds after startup, at most
once a day; a failed automatic check says nothing. Running from source
never checks by itself -- a developer's checkout is ahead of every
release anyway.

The pure functions (version parsing, release selection, changelog
grouping, the installer command line, the macOS script) carry no Qt and
no network, so the tests exercise them directly.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shlex
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from PyQt5.QtCore import QObject, QSettings, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (QApplication, QDialog, QDialogButtonBox,
                             QLabel, QMessageBox, QProgressDialog,
                             QTextBrowser, QVBoxLayout)

from . import APP_NAME, __version__

REPO = "gkerherve/KherveCAD"
API = f"https://api.github.com/repos/{REPO}"
RELEASES_API = f"{API}/releases?per_page=50"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
TIMEOUT = 10                       # seconds, per request
USER_AGENT = f"{APP_NAME}/{__version__} (+https://github.com/{REPO})"

SETTINGS = ("Kherve", "KherveCAD")
KEY_LAST = "update_last_check"     # epoch seconds of the last good check
KEY_AUTO = "update_auto"           # check by itself (default on)
KEY_SKIP = "update_skip_version"   # "0.1.N" the user said to skip
CHECK_INTERVAL_S = 24 * 3600
STARTUP_DELAY_MS = 5000

#: tag prefix and asset names per platform family, most specific first
FAMILIES = {
    "windows": {
        "prefix": "v",
        "assets": (r"KherveCAD-Setup-\d+\.\d+\.\d+\.exe",
                   r"KherveCAD-Setup\.exe"),
    },
    "macos": {
        "prefix": "macos-v",
        "assets": (r"KherveCAD-\d+\.\d+\.\d+-macOS-arm64\.dmg",
                   r"KherveCAD-macOS-arm64\.dmg"),
    },
}
#: the family whose release notes carry the changelog prose
MAIN_FAMILY = "windows"

#: commit prefix -> changelog heading; ``None`` drops the commit
COMMIT_GROUPS = {"feat": "New", "fix": "Fixed", "perf": "Improved",
                 "style": "Improved", "refactor": "Improved",
                 "docs": None, "test": None}
GROUP_ORDER = ("New", "Fixed", "Improved", "Other")

#: Inno Setup switches: progress window only, default answer to every
#: message box, never reboot, close whatever holds the files.
INNO_SILENT_FLAGS = ("/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                     "/CLOSEAPPLICATIONS")
_DETACHED_PROCESS = 0x00000008
_CREATE_NEW_PROCESS_GROUP = 0x00000200


class UpdateError(Exception):
    """A check or a download that could not complete (message is for
    the user)."""


class DownloadCancelled(UpdateError):
    pass


# ------------------------------------------------------------- versions

_VERSION_RE = re.compile(r"v?(\d+)\.(\d+)\.(\d+)(?:\+([0-9A-Za-z.]+))?")


def parse_version(text) -> tuple[tuple[int, int, int], str] | None:
    """``'0.1.191+abc1234'`` -> ``((0, 1, 191), 'abc1234')``.

    The sha is ``''`` when absent (a release tag, an old VERSION file);
    anything unparseable gives None.
    """
    m = _VERSION_RE.fullmatch(str(text or "").strip())
    if not m:
        return None
    return (int(m[1]), int(m[2]), int(m[3])), m[4] or ""


def running_version(text: str = __version__):
    """The running build's (version tuple, sha); the ``0.1.0`` fallback
    for a string nobody can read, so every release looks newer."""
    return parse_version(text) or ((0, 1, 0), "")


def label(version) -> str:
    return ".".join(str(v) for v in version)


def is_newer(candidate, current) -> bool:
    return tuple(candidate) > tuple(current)


def platform_key(sys_platform: str | None = None,
                 machine: str | None = None) -> str | None:
    """The release family this machine can install, or None."""
    sys_platform = sys.platform if sys_platform is None else sys_platform
    machine = platform.machine() if machine is None else machine
    if sys_platform.startswith("win"):
        return "windows"
    if sys_platform == "darwin" and machine.lower() in ("arm64", "aarch64"):
        return "macos"                  # the DMG is Apple Silicon only
    return None


# ------------------------------------------------------------- releases

@dataclass
class Release:
    tag: str
    version: tuple
    name: str = ""
    body: str = ""
    url: str = RELEASES_PAGE
    asset: dict | None = None          # {"name", "url", "size"}

    @property
    def label(self) -> str:
        return label(self.version)


def tag_version(tag: str, family: str):
    prefix = FAMILIES[family]["prefix"]
    m = re.fullmatch(re.escape(prefix) + r"(\d+)\.(\d+)\.(\d+)", tag or "")
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def pick_asset(assets, family: str) -> dict | None:
    for pattern in FAMILIES[family]["assets"]:
        for a in assets or ():
            if re.fullmatch(pattern, a.get("name", "")):
                return {"name": a["name"],
                        "url": a.get("browser_download_url", ""),
                        "size": int(a.get("size") or 0)}
    return None


def releases_for(data, family: str | None) -> list[Release]:
    """Published releases of *family*, newest first.

    Drafts and prereleases are skipped, and so is a release that lacks
    this platform's installer (still uploading, or a failed build).
    ``family=None`` -- a platform with no build -- reads the main line
    for reporting only, assets ignored.
    """
    out = []
    for r in data if isinstance(data, list) else ():
        if not isinstance(r, dict) or r.get("draft") or r.get("prerelease"):
            continue
        version = tag_version(r.get("tag_name", ""), family or MAIN_FAMILY)
        if version is None:
            continue
        asset = None
        if family is not None:
            asset = pick_asset(r.get("assets"), family)
            if asset is None or not asset["url"]:
                continue
        out.append(Release(
            tag=r["tag_name"], version=version,
            name=r.get("name") or "",
            body=(r.get("body") or "").replace("\r\n", "\n").strip(),
            url=r.get("html_url") or RELEASES_PAGE, asset=asset))
    out.sort(key=lambda rel: rel.version, reverse=True)
    return out


def newest_release(data, family: str | None) -> Release | None:
    found = releases_for(data, family)
    return found[0] if found else None


def notes_between(data, family: str | None, current, target) -> list[Release]:
    """Releases in (current, target], newest first, whose notes to show.

    The platform's own releases plus the main line's: the macOS release
    bodies are install instructions, the changelog prose lives on the
    ``v`` releases. Identical bodies show once.
    """
    families = {family or MAIN_FAMILY, MAIN_FAMILY}
    picked, seen = [], set()
    for fam in families:
        for rel in releases_for(data, fam if fam == family else None):
            if is_newer(rel.version, current) and \
                    not is_newer(rel.version, target):
                picked.append(rel)
    picked.sort(key=lambda rel: (rel.version, rel.tag), reverse=True)
    out = []
    for rel in picked:
        if rel.body and rel.body not in seen:
            seen.add(rel.body)
            out.append(rel)
    return out


def notes_markdown(releases) -> str:
    parts = []
    for rel in releases:
        title = rel.name or f"{APP_NAME} {rel.label}"
        parts.append(f"## {title}\n\n{rel.body}")
    return "\n\n".join(parts)


_PREFIX_RE = re.compile(r"(\w+)(?:\([^)]*\))?!?:\s*(.+)")


def group_commits(compare) -> dict[str, list[str]]:
    """Commit subjects from a compare reply, by changelog heading.

    ``feat: x`` -> New, ``fix:`` -> Fixed, ``perf/style/refactor:`` ->
    Improved, ``docs:``/``test:`` dropped, anything else -> Other; the
    prefix is stripped, merges skipped, newest first.
    """
    groups: dict[str, list[str]] = {}
    commits = compare.get("commits") if isinstance(compare, dict) else None
    for c in reversed(commits or []):
        message = ((c or {}).get("commit") or {}).get("message") or ""
        subject = message.strip().splitlines()[0].strip() if message.strip() \
            else ""
        if not subject or subject.startswith("Merge "):
            continue
        m = _PREFIX_RE.fullmatch(subject)
        heading = "Other"
        if m and m[1].lower() in COMMIT_GROUPS:
            heading = COMMIT_GROUPS[m[1].lower()]
            subject = m[2].strip()
            if heading is None:
                continue
        first = subject.split(" ", 1)[0]
        if first.islower():            # "macOS ..." keeps its spelling
            subject = subject[:1].upper() + subject[1:]
        bucket = groups.setdefault(heading, [])
        if subject not in bucket:
            bucket.append(subject)
    return {h: groups[h] for h in GROUP_ORDER if groups.get(h)}


def changelog_markdown(groups) -> str:
    return "\n\n".join(
        f"### {heading}\n\n" + "\n".join(f"- {s}" for s in items)
        for heading, items in groups.items())


def compare_url(sha: str, tag: str) -> str:
    return f"{API}/compare/{sha}...{tag}"


# -------------------------------------------------------------- network

def _ssl_context():
    import ssl
    ctx = ssl.create_default_context()
    try:           # a frozen build may not find the system CA bundle
        import certifi
        ctx.load_verify_locations(certifi.where())
    except Exception:
        pass
    return ctx


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })


def _describe(exc) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code in (403, 429) and \
                (exc.headers or {}).get("X-RateLimit-Remaining") == "0":
            return ("GitHub's hourly limit for anonymous requests is used "
                    "up — try again later.")
        return f"GitHub answered {exc.code} {exc.reason}."
    reason = getattr(exc, "reason", None) or exc
    return f"Could not reach GitHub ({reason})."


def fetch_json(url: str, timeout: float = TIMEOUT):
    """GET *url* as JSON; every failure becomes an UpdateError."""
    try:
        with urllib.request.urlopen(_request(url), timeout=timeout,
                                    context=_ssl_context()) as reply:
            return json.loads(reply.read().decode("utf-8"))
    except (urllib.error.URLError, OSError) as exc:
        raise UpdateError(_describe(exc)) from exc
    except ValueError as exc:
        raise UpdateError("GitHub sent a reply that is not JSON.") from exc


@dataclass
class UpdateInfo:
    current: tuple
    sha: str
    family: str | None
    release: Release | None = None     # newest release for this platform
    notes: str = ""                    # release notes (Markdown)
    changes: str = ""                  # grouped commit subjects (Markdown)

    @property
    def available(self) -> bool:
        return self.release is not None and \
            is_newer(self.release.version, self.current)

    def markdown(self) -> str:
        parts = []
        if self.notes:
            parts.append(self.notes)
        if self.changes:
            parts.append(f"## Every change since {label(self.current)}"
                         f"\n\n{self.changes}")
        return "\n\n".join(parts)


def check_for_update(version_text: str = __version__,
                     family: str | None = "auto") -> UpdateInfo:
    """Ask GitHub; raise UpdateError when it cannot be asked.

    Release notes and the commit list are fetched only when there is
    something newer; a failed compare (a local sha GitHub never saw)
    just leaves the commit list out.
    """
    if family == "auto":
        family = platform_key()
    current, sha = running_version(version_text)
    data = fetch_json(RELEASES_API)
    if not isinstance(data, list):
        raise UpdateError("GitHub sent an unexpected reply.")
    info = UpdateInfo(current=current, sha=sha, family=family,
                      release=newest_release(data, family))
    if not info.available:
        return info
    info.notes = notes_markdown(
        notes_between(data, family, current, info.release.version))
    if sha:
        try:
            info.changes = changelog_markdown(group_commits(
                fetch_json(compare_url(sha, info.release.tag))))
        except UpdateError:
            pass
    return info


def download(url: str, dest: Path, expected_size: int = 0,
             progress=None, cancelled=None, opener=None,
             chunk: int = 1 << 16) -> Path:
    """Stream *url* to *dest* (via ``dest.part``), checking the size.

    ``progress(done, total)`` is called per chunk, ``cancelled()`` polled
    per chunk; ``opener`` stands in for ``urlopen`` in tests.
    """
    dest = Path(dest)
    part = dest.with_name(dest.name + ".part")
    opener = opener or (lambda req: urllib.request.urlopen(
        req, timeout=TIMEOUT, context=_ssl_context()))
    done = 0
    try:
        with opener(_request(url)) as reply, open(part, "wb") as out:
            total = expected_size or int(
                (getattr(reply, "headers", None) or {}).get(
                    "Content-Length") or 0)
            while True:
                if cancelled is not None and cancelled():
                    raise DownloadCancelled("cancelled")
                block = reply.read(chunk)
                if not block:
                    break
                out.write(block)
                done += len(block)
                if progress is not None:
                    progress(done, total)
    except DownloadCancelled:
        part.unlink(missing_ok=True)
        raise
    except (urllib.error.URLError, OSError) as exc:
        part.unlink(missing_ok=True)
        raise UpdateError(_describe(exc)) from exc
    if expected_size and done != expected_size:
        part.unlink(missing_ok=True)
        raise UpdateError(f"The download is incomplete ({done:,} of "
                          f"{expected_size:,} bytes).")
    os.replace(part, dest)
    return dest


# ------------------------------------------------------------- settings

def _as_bool(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def auto_enabled(settings) -> bool:
    return _as_bool(settings.value(KEY_AUTO, True), True)


def should_auto_check(settings, now: float | None = None,
                      frozen: bool | None = None) -> bool:
    """Installed build, automatic checks on, and a day since the last."""
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if not frozen or not auto_enabled(settings):
        return False
    now = time.time() if now is None else now
    try:
        last = float(settings.value(KEY_LAST, 0) or 0)
    except (TypeError, ValueError):
        last = 0.0
    # a clock that went backwards must not silence the check for good
    return last > now or now - last >= CHECK_INTERVAL_S


def record_check(settings, now: float | None = None) -> None:
    settings.setValue(KEY_LAST, float(time.time() if now is None else now))


def skip_version(settings, release: Release) -> None:
    settings.setValue(KEY_SKIP, release.label)


def is_skipped(settings, release: Release) -> bool:
    return str(settings.value(KEY_SKIP, "") or "") == release.label


# -------------------------------------------------------------- install

def install_mode(family: str | None, frozen: bool | None = None,
                 executable: str | None = None) -> str:
    """How this copy can take an update.

    ``windows`` (run the installer), ``mac-replace`` (swap the bundle),
    ``mac-open`` (hand the DMG to Finder) or ``page`` (open the release
    page: a source checkout, a portable copy, another platform).
    """
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    executable = executable or sys.executable
    if not frozen:
        return "page"
    if family == "windows":
        return "windows" if windows_installed(executable) else "page"
    if family == "macos":
        bundle = mac_app_bundle(executable)
        if bundle is None:
            return "page"
        return "mac-replace" if mac_can_replace(bundle) else "mac-open"
    return "page"


def windows_installed(executable: str) -> bool:
    """True for an Inno Setup install (its uninstaller sits beside the
    exe); a portable copy would be left stale by the installer."""
    return any(Path(executable).parent.glob("unins*.exe"))


def windows_install_command(installer, log: str | None = None) -> list[str]:
    cmd = [str(installer), *INNO_SILENT_FLAGS]
    if log:
        cmd.append(f"/LOG={log}")
    return cmd


def windows_popen_kwargs() -> dict:
    """Detach the installer: it must outlive this process."""
    return {"creationflags": _DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP,
            "close_fds": True, "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}


def mac_app_bundle(executable: str | None = None) -> Path | None:
    """``/Applications/KherveCAD.app`` from its ``Contents/MacOS/...``."""
    exe = Path(executable or sys.executable)
    for parent in exe.parents:
        if parent.suffix == ".app" and exe.parent == \
                parent / "Contents" / "MacOS":
            return parent
    return None


def mac_can_replace(bundle: Path) -> bool:
    text = str(bundle)
    if "/AppTranslocation/" in text or text.startswith("/Volumes/"):
        return False                   # a read-only randomised / DMG copy
    return os.access(bundle.parent, os.W_OK) and os.access(bundle, os.W_OK)


def mac_attach_command(dmg, mountpoint) -> list[str]:
    return ["hdiutil", "attach", "-nobrowse", "-quiet",
            "-mountpoint", str(mountpoint), str(dmg)]


def mac_install_script(pid: int, source_app, target_app, mountpoint,
                       log) -> str:
    """The detached script that swaps the bundle once *pid* has exited.

    The new bundle is copied beside the old one first and the two are
    swapped by rename, so a failed copy or a full disk leaves the old
    app intact -- and it is reopened either way.
    """
    q = shlex.quote
    return f"""#!/bin/sh
# Written by {APP_NAME}'s updater: wait for the app to quit, replace
# the bundle with the one from the mounted disk image, reopen it.
pid={int(pid)}
src={q(str(source_app))}
dest={q(str(target_app))}
mnt={q(str(mountpoint))}
exec >>{q(str(log))} 2>&1
echo "update started $(date)"
n=0
while kill -0 "$pid" 2>/dev/null; do
    n=$((n + 1))
    if [ "$n" -gt 600 ]; then
        echo "the app did not quit; update abandoned"
        hdiutil detach "$mnt" -quiet
        exit 1
    fi
    sleep 0.5
done
stage="$dest.update-new"
old="$dest.update-old"
rm -rf "$stage" "$old"
if ditto "$src" "$stage"; then
    if mv "$dest" "$old"; then
        if mv "$stage" "$dest"; then
            rm -rf "$old"
            echo "bundle replaced"
        else
            mv "$old" "$dest"
        fi
    fi
else
    echo "copy failed; keeping the installed app"
fi
rm -rf "$stage"
hdiutil detach "$mnt" -quiet || hdiutil detach "$mnt" -force -quiet
xattr -dr com.apple.quarantine "$dest" 2>/dev/null
open "$dest"
"""


def mac_mount(dmg: Path, workdir: Path) -> tuple[Path, Path]:
    """Attach *dmg* under *workdir*; return (mountpoint, the .app in it)."""
    mnt = Path(workdir) / "mnt"
    mnt.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(mac_attach_command(dmg, mnt), check=True,
                       capture_output=True, timeout=300)
    except (subprocess.SubprocessError, OSError) as exc:
        raise UpdateError(f"Could not open the disk image ({exc}).") from exc
    app = next(iter(sorted(mnt.glob("*.app"))), None)
    if app is None:
        subprocess.run(["hdiutil", "detach", str(mnt), "-quiet"],
                       capture_output=True)
        raise UpdateError("The disk image holds no application.")
    return mnt, app


# ------------------------------------------------------------- threads
#
# Workers have no Qt parent and are owned by C++: a check still waiting
# on the network when the window closes must neither be destroyed while
# running (Qt aborts) nor keep the window alive. _LIVE holds the Python
# side until the thread finishes; deleteLater frees the rest.

_LIVE: set = set()


def _launch(worker: QThread) -> QThread:
    try:
        from PyQt5 import sip
    except ImportError:                                  # pragma: no cover
        import sip
    sip.transferto(worker, None)
    _LIVE.add(worker)
    worker.finished.connect(lambda w=worker: _LIVE.discard(w))
    worker.finished.connect(worker.deleteLater)
    worker.start()
    return worker


class CheckWorker(QThread):
    checked = pyqtSignal(object, str)          # UpdateInfo | None, error

    def __init__(self, version_text: str = __version__,
                 family: str | None = "auto"):
        super().__init__()
        self._version = version_text
        self._family = family

    def run(self):
        try:
            self.checked.emit(check_for_update(self._version, self._family),
                              "")
        except UpdateError as exc:
            self.checked.emit(None, str(exc))
        except Exception as exc:                 # never take the app down
            self.checked.emit(None, f"Unexpected error: {exc}")


class DownloadWorker(QThread):
    progress = pyqtSignal(object, object)      # bytes done, total
    succeeded = pyqtSignal(object)             # prepare() result or path
    failed = pyqtSignal(str)                   # "" when cancelled

    def __init__(self, asset: dict, directory: Path, prepare=None):
        super().__init__()
        self._asset = asset
        self._dir = Path(directory)
        self._prepare = prepare

    def run(self):
        try:
            path = download(self._asset["url"], self._dir /
                            self._asset["name"], self._asset.get("size", 0),
                            progress=self.progress.emit,
                            cancelled=self.isInterruptionRequested)
            result = self._prepare(path) if self._prepare else path
        except DownloadCancelled:
            self.failed.emit("")
        except UpdateError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(f"Unexpected error: {exc}")
        else:
            self.succeeded.emit(result)


# -------------------------------------------------------------- dialog

class UpdateDialog(QDialog):
    INSTALL, LATER, SKIP = "install", "later", "skip"

    def __init__(self, info: UpdateInfo, action_text: str, parent=None):
        super().__init__(parent)
        self.choice = self.LATER
        self.setWindowTitle("Update available")
        self.resize(620, 520)
        lay = QVBoxLayout(self)
        head = QLabel(f"<b>{APP_NAME} {info.release.label} is available</b>"
                      f" (you have {label(info.current)}).")
        head.setWordWrap(True)
        lay.addWidget(head)
        lay.addWidget(QLabel("What changed:"))
        notes = QTextBrowser()
        notes.setOpenExternalLinks(True)
        text = info.markdown() or "_No release notes._"
        if hasattr(notes, "setMarkdown"):
            notes.setMarkdown(text)
        else:                                            # pragma: no cover
            notes.setPlainText(text)
        lay.addWidget(notes, 1)
        box = QDialogButtonBox()
        for text, role, choice in (
                (action_text, QDialogButtonBox.AcceptRole, self.INSTALL),
                ("Later", QDialogButtonBox.RejectRole, self.LATER),
                ("Skip this version", QDialogButtonBox.ActionRole,
                 self.SKIP)):
            button = box.addButton(text, role)
            button.clicked.connect(lambda _=False, c=choice: self._pick(c))
            if choice == self.INSTALL:
                button.setDefault(True)
        lay.addWidget(box)

    def _pick(self, choice):
        self.choice = choice
        self.accept() if choice == self.INSTALL else self.reject()


ACTION_TEXT = {"windows": "Download and install",
               "mac-replace": "Download and install",
               "mac-open": "Download",
               "page": "Open release page"}


# ---------------------------------------------------------- controller

class Updater(QObject):
    """The Help-menu front end, owned by a MainWindow."""

    def __init__(self, window):
        super().__init__(window)
        self._window = window
        self._manual = False
        self._info: UpdateInfo | None = None
        self._mode = "page"
        self._checking = False
        self._downloader: DownloadWorker | None = None
        self._progress: QProgressDialog | None = None
        self._workdir: Path | None = None
        self.auto_action = None

    # ---- settings / menu
    @staticmethod
    def settings():
        return QSettings(*SETTINGS)

    def add_menu_actions(self, menu):
        menu.addAction("Check for &Updates...", self.check_now)
        act = menu.addAction("Check for Updates &Automatically")
        act.setCheckable(True)
        act.setChecked(auto_enabled(self.settings()))
        act.setToolTip("An installed KherveCAD looks for a new release "
                       "once a day, a few seconds after it starts")
        act.toggled.connect(self.set_auto)
        self.auto_action = act

    def set_auto(self, on: bool):
        self.settings().setValue(KEY_AUTO, bool(on))

    def schedule_startup_check(self, delay_ms: int = STARTUP_DELAY_MS):
        if not should_auto_check(self.settings()):
            return
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._start_check(manual=False))
        timer.start(delay_ms)

    # ---- checking
    def check_now(self):
        self._start_check(manual=True)

    def _status(self, text, ms=6000):
        try:
            self._window.statusBar().showMessage(text, ms)
        except (AttributeError, RuntimeError):
            pass

    def _start_check(self, manual: bool):
        if self._checking:
            if manual:
                self._manual = True
                self._status("Already checking for updates...")
            return
        self._checking = True
        self._manual = manual
        if manual:
            self._status("Checking for updates...", 0)
        worker = CheckWorker()
        worker.checked.connect(self._checked)
        _launch(worker)

    def _checked(self, info, error: str):
        self._checking = False
        manual = self._manual
        if manual:
            self._status("")
        if info is None:
            if manual:
                QMessageBox.warning(self._window, "Check for Updates",
                                    f"Could not check for updates.\n\n"
                                    f"{error}")
            return
        settings = self.settings()
        record_check(settings)
        if not info.available:
            if manual:
                newest = (f" The newest release for this platform is "
                          f"{info.release.label}." if info.release else "")
                QMessageBox.information(
                    self._window, "Check for Updates",
                    f"{APP_NAME} {label(info.current)} is up to date."
                    f"{newest}")
            return
        if not manual and is_skipped(settings, info.release):
            return
        self._offer(info)

    def _offer(self, info: UpdateInfo):
        self._info = info
        self._mode = install_mode(info.family)
        dlg = UpdateDialog(info, ACTION_TEXT[self._mode], self._window)
        dlg.exec_()
        if dlg.choice == UpdateDialog.SKIP:
            skip_version(self.settings(), info.release)
            self._status(f"{APP_NAME} {info.release.label} skipped — you "
                         f"will be told about the next release.")
        elif dlg.choice == UpdateDialog.INSTALL:
            if self._mode == "page":
                from PyQt5.QtCore import QUrl
                from PyQt5.QtGui import QDesktopServices
                QDesktopServices.openUrl(QUrl(info.release.url))
            else:
                self._start_download()

    # ---- downloading
    def _start_download(self):
        if self._downloader is not None:
            return
        asset = self._info.release.asset
        self._workdir = Path(tempfile.mkdtemp(prefix="khervecad-update-"))
        prepare = None
        if self._mode == "mac-replace":
            workdir = self._workdir
            prepare = lambda path: (path, *mac_mount(path, workdir))  # noqa
        worker = DownloadWorker(asset, self._workdir, prepare)
        worker.progress.connect(self._on_progress)
        worker.succeeded.connect(self._downloaded)
        worker.failed.connect(self._download_failed)
        self._downloader = worker
        size = asset.get("size") or 0
        dlg = QProgressDialog(
            f"Downloading {asset['name']} ({size / 1e6:.0f} MB)...",
            "Cancel", 0, 1000, self._window)
        dlg.setWindowTitle("Updating " + APP_NAME)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.canceled.connect(worker.requestInterruption)
        dlg.show()
        self._progress = dlg
        _launch(worker)

    def _on_progress(self, done, total):
        if self._progress is None:
            return
        if total:
            self._progress.setValue(int(1000 * min(done, total) / total))
            self._progress.setLabelText(
                f"Downloading {APP_NAME} {self._info.release.label}: "
                f"{done / 1e6:.1f} of {total / 1e6:.1f} MB")
        if total and done >= total and self._mode == "mac-replace":
            self._progress.setLabelText("Opening the disk image...")

    def _end_download(self):
        self._downloader = None
        if self._progress is not None:
            try:                  # close() emits canceled; nothing to stop
                self._progress.canceled.disconnect()
            except TypeError:
                pass
            self._progress.close()
            self._progress.deleteLater()
            self._progress = None

    def _download_failed(self, message: str):
        self._end_download()
        if not message:
            self._status("Update download cancelled.")
            return
        QMessageBox.warning(self._window, "Update",
                            f"The update could not be downloaded.\n\n"
                            f"{message}")

    def _downloaded(self, result):
        self._end_download()
        if self._mode == "mac-open":
            subprocess.Popen(["open", str(result)])
            QMessageBox.information(
                self._window, "Update downloaded",
                f"The {APP_NAME} {self._info.release.label} disk image is "
                f"open in Finder. Quit {APP_NAME}, then drag the new "
                f"{APP_NAME} onto Applications to replace this one.")
            return
        self._install(result)

    # ---- installing
    def _close_windows(self) -> bool:
        """Close every window (each may ask to save); False if one
        refused."""
        windows = [self._window] + [
            w for w in getattr(type(self._window), "_windows", [])
            if w is not self._window]
        for w in windows:
            try:
                if w.isVisible() and not w.close():
                    return False
            except RuntimeError:
                continue
        return True

    def _install(self, result):
        app = QApplication.instance()
        app.setQuitOnLastWindowClosed(False)
        if not self._close_windows():
            app.setQuitOnLastWindowClosed(True)
            if self._mode == "mac-replace":
                subprocess.run(["hdiutil", "detach", str(result[1]),
                                "-quiet"], capture_output=True)
            self._status("Update postponed — the window was not closed.")
            return
        try:
            if self._mode == "windows":
                path = Path(result)
                subprocess.Popen(
                    windows_install_command(path,
                                            str(path.parent / "install.log")),
                    **windows_popen_kwargs())
            else:
                _dmg, mnt, source = result
                script = self._workdir / "install.sh"
                script.write_text(mac_install_script(
                    os.getpid(), source, mac_app_bundle(), mnt,
                    self._workdir / "install.log"), encoding="utf-8")
                subprocess.Popen(["/bin/sh", str(script)],
                                 start_new_session=True, close_fds=True,
                                 stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        except OSError as exc:
            QMessageBox.critical(None, "Update",
                                 f"The installer could not be started.\n\n"
                                 f"{exc}\n\nIt was saved in {self._workdir}.")
        app.quit()
