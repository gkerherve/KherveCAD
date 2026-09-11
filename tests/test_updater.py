"""Tests for the GitHub-release updater (no network, nothing launched).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import io
import os
import shlex
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from khervecad import updater as up


def _asset(name, size=1000):
    return {"name": name, "size": size,
            "browser_download_url": f"https://example.invalid/{name}"}


def _win(n, body="", draft=False, pre=False, assets=True):
    return {"tag_name": f"v0.1.{n}", "name": f"KherveCAD v0.1.{n}",
            "body": body, "draft": draft, "prerelease": pre,
            "html_url": f"https://github.com/x/releases/tag/v0.1.{n}",
            "assets": [_asset(f"KherveCAD-0.1.{n}-portable.zip"),
                       _asset(f"KherveCAD-Setup-0.1.{n}.exe"),
                       _asset("KherveCAD-Setup.exe")] if assets else []}


def _mac(n, body="Open the DMG and drag it to Applications."):
    return {"tag_name": f"macos-v0.1.{n}", "name": f"KherveCAD v0.1.{n} mac",
            "body": body, "draft": False, "prerelease": False,
            "html_url": f"https://github.com/x/releases/tag/macos-v0.1.{n}",
            "assets": [_asset(f"KherveCAD-0.1.{n}-macOS-arm64.dmg", 89),
                       _asset("KherveCAD-macOS-arm64.dmg", 89)]}


RELEASES = [
    _win(200, "Draft notes", draft=True),
    _win(190, "Pre notes", pre=True),
    _win(180, "## Faster\r\nBSP painter"),
    _mac(178),
    _win(172, "## MCP\nConnect Claude"),
    _mac(165),
    _win(155, "First release"),
    {"tag_name": "nightly", "draft": False, "prerelease": False,
     "assets": []},
    _win(185, "no installer uploaded yet", assets=False),
]


class FakeSettings:
    def __init__(self, **values):
        self.values = dict(values)

    def value(self, key, default=None):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value


# ------------------------------------------------------------ versions

def test_parse_version_with_and_without_sha():
    assert up.parse_version("0.1.191+abc1234") == ((0, 1, 191), "abc1234")
    assert up.parse_version("0.1.172") == ((0, 1, 172), "")
    assert up.parse_version(" v0.1.9 \n") == ((0, 1, 9), "")
    assert up.parse_version("0.1.N") is None
    assert up.parse_version(None) is None


def test_running_version_falls_back_to_zero():
    assert up.running_version("garbage") == ((0, 1, 0), "")
    assert up.running_version("0.1.0") == ((0, 1, 0), "")


def test_is_newer_compares_the_commit_count():
    assert up.is_newer((0, 1, 172), (0, 1, 155))
    assert up.is_newer((0, 1, 1000), (0, 1, 999))      # numeric, not text
    assert not up.is_newer((0, 1, 172), (0, 1, 172))
    assert not up.is_newer((0, 1, 9), (0, 1, 10))


def test_platform_key():
    assert up.platform_key("win32", "AMD64") == "windows"
    assert up.platform_key("darwin", "arm64") == "macos"
    assert up.platform_key("darwin", "x86_64") is None     # DMG is arm64
    assert up.platform_key("linux", "x86_64") is None


# ------------------------------------------------------------ releases

def test_windows_release_selection_skips_drafts_prereleases_and_mac():
    rels = up.releases_for(RELEASES, "windows")
    assert [r.tag for r in rels] == ["v0.1.180", "v0.1.172", "v0.1.155"]
    newest = rels[0]
    assert newest.asset["name"] == "KherveCAD-Setup-0.1.180.exe"
    assert newest.body == "## Faster\nBSP painter"          # CRLF folded


def test_macos_release_selection_uses_macos_tags_and_dmg():
    newest = up.newest_release(RELEASES, "macos")
    assert newest.tag == "macos-v0.1.178"
    assert newest.label == "0.1.178"
    assert newest.asset["name"] == "KherveCAD-0.1.178-macOS-arm64.dmg"
    assert newest.asset["size"] == 89


def test_stable_asset_name_is_the_fallback():
    rel = _win(3)
    rel["assets"] = [_asset("KherveCAD-Setup.exe")]
    assert up.pick_asset(rel["assets"], "windows")["name"] == \
        "KherveCAD-Setup.exe"


def test_unsupported_platform_reports_the_main_line():
    newest = up.newest_release(RELEASES, None)
    assert newest.tag == "v0.1.185"          # no asset needed to report
    assert newest.asset is None


def test_notes_between_includes_main_line_for_mac():
    notes = up.notes_between(RELEASES, "macos", (0, 1, 160), (0, 1, 178))
    tags = [r.tag for r in notes]
    assert tags == ["macos-v0.1.178", "v0.1.172"]     # 165 has same body
    notes = up.notes_between(RELEASES, "windows", (0, 1, 160), (0, 1, 180))
    assert [r.tag for r in notes] == ["v0.1.180", "v0.1.172"]
    md = up.notes_markdown(notes)
    assert md.startswith("## KherveCAD v0.1.180\n\n## Faster")
    assert "Connect Claude" in md


# ----------------------------------------------------------- changelog

COMPARE = {"status": "ahead", "commits": [
    {"commit": {"message": "feat: automatic updates\n\nwhy it matters"}},
    {"commit": {"message": "fix: 3D view draws in exact order"}},
    {"commit": {"message": "docs: explain the updater"}},
    {"commit": {"message": "perf(mesh): cache the tessellation"}},
    {"commit": {"message": "style: toolbar spacing"}},
    {"commit": {"message": "refactor!: split mainwindow"}},
    {"commit": {"message": "Merge branch 'x'"}},
    {"commit": {"message": "tidy something"}},
    {"commit": {"message": "test: cover the transports"}},
    {"commit": {"message": "feat: macOS build"}},
    {"commit": {"message": "feat: automatic updates"}},
]}


def test_group_commits_by_prefix():
    groups = up.group_commits(COMPARE)
    assert list(groups) == ["New", "Fixed", "Improved", "Other"]
    # deduped, newest first, "macOS" not turned into "MacOS"
    assert groups["New"] == ["Automatic updates", "macOS build"]
    assert not any("transports" in s for g in groups.values() for s in g)
    assert groups["Fixed"] == ["3D view draws in exact order"]
    assert groups["Improved"] == ["Split mainwindow", "Toolbar spacing",
                                  "Cache the tessellation"]    # newest 1st
    assert groups["Other"] == ["Tidy something"]
    assert all("docs" not in s.lower() for g in groups.values() for s in g)


def test_changelog_markdown_and_empty_compare():
    md = up.changelog_markdown(up.group_commits(COMPARE))
    assert md.startswith("### New\n\n- Automatic updates")
    assert "### Fixed" in md
    assert up.group_commits({}) == {}
    assert up.group_commits(None) == {}
    assert up.changelog_markdown({}) == ""


def _fake_fetch(compare=COMPARE, fail_compare=False, calls=None):
    def fetch(url, timeout=up.TIMEOUT):
        if calls is not None:
            calls.append(url)
        if "/compare/" in url:
            if fail_compare:
                raise up.UpdateError("404")
            return compare
        return RELEASES
    return fetch


def test_check_for_update_finds_newer(monkeypatch):
    calls = []
    monkeypatch.setattr(up, "fetch_json", _fake_fetch(calls=calls))
    info = up.check_for_update("0.1.170+deadbee", "windows")
    assert info.available
    assert info.release.tag == "v0.1.180"
    assert calls[-1].endswith("/compare/deadbee...v0.1.180")
    assert "Faster" in info.notes and "Connect Claude" in info.notes
    assert "First release" not in info.notes              # not newer
    md = info.markdown()
    assert "### New" in md and "Every change since 0.1.170" in md


def test_check_for_update_survives_a_failed_compare(monkeypatch):
    monkeypatch.setattr(up, "fetch_json", _fake_fetch(fail_compare=True))
    info = up.check_for_update("0.1.170+0000000", "windows")
    assert info.available and info.changes == "" and info.notes


def test_check_without_sha_skips_compare(monkeypatch):
    calls = []
    monkeypatch.setattr(up, "fetch_json", _fake_fetch(calls=calls))
    info = up.check_for_update("0.1.170", "windows")
    assert info.available
    assert not any("/compare/" in c for c in calls)


def test_up_to_date_makes_one_request(monkeypatch):
    calls = []
    monkeypatch.setattr(up, "fetch_json", _fake_fetch(calls=calls))
    info = up.check_for_update("0.1.191+abc", "windows")
    assert not info.available and info.release.tag == "v0.1.180"
    assert len(calls) == 1


def test_network_failure_raises_update_error(monkeypatch):
    def boom(req, timeout=None, context=None):
        raise up.urllib.error.URLError("no route to host")
    monkeypatch.setattr(up.urllib.request, "urlopen", boom)
    with pytest.raises(up.UpdateError, match="Could not reach GitHub"):
        up.check_for_update("0.1.1+abc", "windows")


def test_rate_limit_message(monkeypatch):
    def limited(req, timeout=None, context=None):
        raise up.urllib.error.HTTPError(
            req.full_url, 403, "rate limit exceeded",
            {"X-RateLimit-Remaining": "0"}, None)
    monkeypatch.setattr(up.urllib.request, "urlopen", limited)
    with pytest.raises(up.UpdateError, match="hourly limit"):
        up.fetch_json(up.RELEASES_API)


def test_check_worker_reports_errors_instead_of_raising(monkeypatch, qapp):
    def fetch(url, timeout=up.TIMEOUT):
        raise up.UpdateError("offline")
    monkeypatch.setattr(up, "fetch_json", fetch)
    got = []
    worker = up.CheckWorker("0.1.1", "windows")
    worker.checked.connect(lambda info, err: got.append((info, err)))
    worker.run()                                   # synchronously
    assert got == [(None, "offline")]


@pytest.fixture
def qapp():
    from PyQt5.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# ------------------------------------------------------------ download

class FakeReply(io.BytesIO):
    headers = {}


def test_download_streams_and_checks_size(tmp_path):
    data = b"x" * 150_000
    seen = []
    path = up.download("https://e/a.exe", tmp_path / "a.exe", len(data),
                       progress=lambda d, t: seen.append((d, t)),
                       opener=lambda req: FakeReply(data))
    assert path.read_bytes() == data
    assert seen[-1] == (len(data), len(data)) and len(seen) == 3
    assert not (tmp_path / "a.exe.part").exists()


def test_download_rejects_a_short_file(tmp_path):
    with pytest.raises(up.UpdateError, match="incomplete"):
        up.download("https://e/a.exe", tmp_path / "a.exe", 999,
                    opener=lambda req: FakeReply(b"short"))
    assert not list(tmp_path.iterdir())


def test_download_can_be_cancelled(tmp_path):
    with pytest.raises(up.DownloadCancelled):
        up.download("https://e/a.exe", tmp_path / "a.exe", 10,
                    cancelled=lambda: True,
                    opener=lambda req: FakeReply(b"0123456789"))
    assert not list(tmp_path.iterdir())


# ------------------------------------------------------------- settings

def test_auto_check_only_when_frozen_and_once_a_day():
    s = FakeSettings()
    now = 1_000_000.0
    assert not up.should_auto_check(s, now, frozen=False)  # source checkout
    assert up.should_auto_check(s, now, frozen=True)       # never checked
    up.record_check(s, now)
    assert not up.should_auto_check(s, now + 3600, frozen=True)
    assert up.should_auto_check(s, now + up.CHECK_INTERVAL_S, frozen=True)
    assert up.should_auto_check(s, now - 10, frozen=True)  # clock went back


def test_auto_check_can_be_turned_off():
    for off in (False, "false", "0"):
        s = FakeSettings(**{up.KEY_AUTO: off})
        assert not up.auto_enabled(s)
        assert not up.should_auto_check(s, 1e6, frozen=True)
    assert up.auto_enabled(FakeSettings(**{up.KEY_AUTO: "true"}))
    assert up.auto_enabled(FakeSettings())                 # default on


def test_bad_last_check_value_is_ignored():
    s = FakeSettings(**{up.KEY_LAST: "not a number"})
    assert up.should_auto_check(s, 1e6, frozen=True)


def test_skip_version_skips_only_that_version():
    s = FakeSettings()
    r180 = up.newest_release(RELEASES, "windows")
    up.skip_version(s, r180)
    assert s.values[up.KEY_SKIP] == "0.1.180"
    assert up.is_skipped(s, r180)
    newer = up.Release(tag="v0.1.181", version=(0, 1, 181))
    assert not up.is_skipped(s, newer)


# ------------------------------------------------------------- install

def test_windows_install_command():
    cmd = up.windows_install_command(r"C:\Temp\u\KherveCAD-Setup-0.1.9.exe",
                                     log=r"C:\Temp\u\install.log")
    assert cmd == [r"C:\Temp\u\KherveCAD-Setup-0.1.9.exe", "/SILENT",
                   "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS",
                   r"/LOG=C:\Temp\u\install.log"]
    kw = up.windows_popen_kwargs()
    assert kw["creationflags"] & 0x8 and kw["creationflags"] & 0x200


def test_install_mode(tmp_path):
    assert up.install_mode("windows", frozen=False) == "page"
    exe = tmp_path / "KherveCAD" / "KherveCAD.exe"
    exe.parent.mkdir()
    exe.touch()
    assert up.install_mode("windows", True, str(exe)) == "page"  # portable
    (exe.parent / "unins000.exe").touch()
    assert up.install_mode("windows", True, str(exe)) == "windows"
    assert up.install_mode(None, True, str(exe)) == "page"
    app_exe = tmp_path / "KherveCAD.app" / "Contents" / "MacOS" / "KherveCAD"
    app_exe.parent.mkdir(parents=True)
    app_exe.touch()
    assert up.install_mode("macos", True, str(app_exe)) == "mac-replace"
    assert up.install_mode("macos", True, str(exe)) == "page"


def test_mac_app_bundle_and_replaceability(tmp_path):
    exe = "/Applications/KherveCAD.app/Contents/MacOS/KherveCAD"
    assert up.mac_app_bundle(exe) == Path("/Applications/KherveCAD.app")
    assert up.mac_app_bundle("/usr/bin/python3") is None
    assert up.mac_app_bundle(
        "/x/KherveCAD.app/Contents/Resources/python") is None
    assert not up.mac_can_replace(Path(
        "/private/var/folders/ab/AppTranslocation/1234/d/KherveCAD.app"))
    assert not up.mac_can_replace(Path("/Volumes/KherveCAD/KherveCAD.app"))
    bundle = tmp_path / "KherveCAD.app"
    bundle.mkdir()
    assert up.mac_can_replace(bundle)


def test_mac_attach_command():
    assert up.mac_attach_command("/t/k.dmg", "/t/mnt") == [
        "hdiutil", "attach", "-nobrowse", "-quiet", "-mountpoint", "/t/mnt",
        "/t/k.dmg"]


def test_mac_install_script_text():
    script = up.mac_install_script(
        4321, "/tmp/u/mnt/KherveCAD.app", "/Users/me/My Apps/KherveCAD.app",
        "/tmp/u/mnt", "/tmp/u/install.log")
    assert script.startswith("#!/bin/sh\n")
    assert "pid=4321\n" in script
    assert 'kill -0 "$pid"' in script                  # waits for us
    # paths with spaces survive the shell
    assert f"dest={shlex.quote('/Users/me/My Apps/KherveCAD.app')}\n" in \
        script
    assert 'ditto "$src" "$stage"' in script
    assert 'mv "$stage" "$dest"' in script
    assert 'hdiutil detach "$mnt"' in script
    assert 'xattr -dr com.apple.quarantine "$dest"' in script
    assert script.rstrip().endswith('open "$dest"')
    # the copy happens before the old bundle is moved aside
    assert script.index("ditto") < script.index('mv "$dest" "$old"')


@pytest.mark.skipif(not os.path.exists("/bin/sh"), reason="needs a shell")
def test_mac_install_script_is_valid_shell(tmp_path):
    script = tmp_path / "install.sh"
    script.write_text(up.mac_install_script(1, "/a b/S.app", "/c d/T.app",
                                            "/m", tmp_path / "l.log"))
    import subprocess
    assert subprocess.run(["/bin/sh", "-n", str(script)]).returncode == 0


# ------------------------------------------------------------- menu

def test_help_menu_has_update_actions(qapp):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        texts = [a.text() for m in win.menuBar().actions()
                 if m.menu() for a in m.menu().actions()]
        assert "Check for &Updates..." in texts
        assert win.updater.auto_action.isCheckable()
    finally:
        win.close()
