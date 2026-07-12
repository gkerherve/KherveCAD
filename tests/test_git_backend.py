"""Tests for the per-document Git backend.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from khervecad import git_backend

pytestmark = pytest.mark.skipif(
    not git_backend.is_available(), reason="pygit2 not installed")


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "Model1.kcad").write_text('{"format":"kcad"}',
                                          encoding="utf-8")
    return tmp_path


def test_commit_creates_a_commit_on_dev(repo):
    oid = git_backend.commit_all(repo, "first", file_stem="Model1")
    assert oid is not None
    assert git_backend.current_branch(repo) == "dev"
    hist = git_backend.history(repo)
    assert len(hist) == 1
    assert hist[0][2] == "first"


def test_no_change_commit_returns_none(repo):
    git_backend.commit_all(repo, "first", file_stem="Model1")
    assert git_backend.commit_all(repo, "again", file_stem="Model1") is None


def test_second_commit_after_edit(repo):
    git_backend.commit_all(repo, "first", file_stem="Model1")
    (repo / "Model1.kcad").write_text('{"format":"kcad","v":2}',
                                      encoding="utf-8")
    oid = git_backend.commit_all(repo, "second", file_stem="Model1")
    assert oid is not None
    assert len(git_backend.history(repo)) == 2


def test_set_and_get_remote(repo):
    assert git_backend.set_remote(repo, "origin",
                                  "https://example.com/r.git")
    assert git_backend.get_remotes(repo) == [
        ("origin", "https://example.com/r.git")]


def test_stem_only_stages_matching_files(repo):
    (repo / "Other.kcad").write_text("x", encoding="utf-8")
    git_backend.commit_all(repo, "just model1", file_stem="Model1")
    # Other.kcad wasn't staged, so a fresh commit for it still has content
    oid = git_backend.commit_all(repo, "now other", file_stem="Other")
    assert oid is not None
