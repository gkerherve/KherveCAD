"""Per-document Git repo with auto-commit on save.

Each ``.kcad`` lives in a directory that is also its own git repo. The
committed artifact is the human-readable notebook file itself (``.kcad``
is JSON), so ``git diff`` between snapshots is meaningful.

Falls back gracefully if pygit2 is unavailable: every function becomes a
no-op and returns False/None, so the editor still works.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    import pygit2
    _PYGIT2_OK = True
except Exception:  # pragma: no cover — environment without pygit2
    pygit2 = None  # type: ignore
    _PYGIT2_OK = False


def is_available() -> bool:
    return _PYGIT2_OK


def _find_enclosing_repo(repo_dir: Path) -> Path | None:
    """Walk up the directory tree; if any ancestor has a .git, return that
    ancestor. Used to detect when a save would create a nested repo inside
    an existing one (which was the source of the rogue "master"-branch
    auto-commit history)."""
    cur = repo_dir.resolve()
    while cur != cur.parent:
        if (cur / ".git").exists():
            return cur
        cur = cur.parent
    return None


def init_repo(repo_dir: Path) -> bool:
    """Initialise a git repo in `repo_dir` if one doesn't already exist.

    - If `repo_dir` is already a repo, return True (no-op).
    - If `repo_dir` is INSIDE another git repo, use that parent repo
      instead of nesting — saves there should commit to the enclosing
      repo's current branch, not a new "master" branch under a hidden
      `.git` directory.
    - Otherwise initialise a fresh repo with HEAD pointing to
      `refs/heads/dev`, matching the project's branching convention.
    """
    if not _PYGIT2_OK:
        return False
    repo_dir.mkdir(parents=True, exist_ok=True)
    if (repo_dir / ".git").exists():
        return True
    if _find_enclosing_repo(repo_dir) is not None:
        # Don't create a nested repo. Caller's commit_all will still work
        # because it walks up from repo_dir to find the enclosing .git.
        return True
    pygit2.init_repository(str(repo_dir), bare=False)
    # libgit2 defaults the unborn HEAD to refs/heads/master; rewrite it
    # so the very first commit lands on `dev` instead.
    head_file = repo_dir / ".git" / "HEAD"
    head_file.write_text("ref: refs/heads/dev\n", encoding="utf-8")
    return True


def _repo_for(repo_dir: Path) -> "pygit2.Repository | None":
    """Return the pygit2.Repository governing `repo_dir`, walking up to
    find an enclosing one if `repo_dir` itself isn't a repo root.

    Returns None on transient errors (e.g. OneDrive holding a file lock
    on .git/index) so the caller degrades gracefully instead of crashing.
    """
    try:
        if (repo_dir / ".git").exists():
            return pygit2.Repository(str(repo_dir))
        enclosing = _find_enclosing_repo(repo_dir)
        return pygit2.Repository(str(enclosing)) if enclosing else None
    except Exception:
        return None


def _signature(repo: "pygit2.Repository | None" = None) -> "pygit2.Signature":
    """Build a commit signature, preferring the user's real git identity.

    Order:
      1. repo.default_signature — reads user.name/user.email from .git/config,
         the user's global config, or the system config (the same chain plain
         `git commit` uses, so auto-commits look identical to CLI commits).
      2. Hard-coded fallback only if no git identity is configured anywhere.
    """
    if repo is not None:
        try:
            return repo.default_signature
        except (KeyError, pygit2.GitError):
            pass
    return pygit2.Signature(
        "KherveCAD", "khervecad@local", int(datetime.now().timestamp()), 0)


def commit_all(repo_dir: Path, message: str | None = None,
               file_stem: str | None = None) -> str | None:
    """Stage files in *repo_dir* and create a commit.

    When *file_stem* is given only files whose name starts with that
    stem are staged (e.g. ``"Model1"`` stages ``Model1.kcad``).  Otherwise
    every tracked + new file is staged.

    Returns the new commit's hex OID, or None if nothing changed / git unavailable.
    """
    if not _PYGIT2_OK:
        return None
    init_repo(repo_dir)

    repo = _repo_for(repo_dir)
    if repo is None:
        return None
    index = repo.index
    if file_stem:
        repo_root = Path(repo.workdir)
        for p in repo_root.iterdir():
            if p.name.startswith(file_stem) and p.is_file():
                # Path relative to repo root for index.add.
                rel = str(p.relative_to(repo_root)).replace("\\", "/")
                index.add(rel)
    else:
        index.add_all()
    index.write()

    # Detect "no changes" by comparing the new tree against HEAD's tree.
    new_tree_oid = index.write_tree()
    parents: list[str] = []
    if not repo.head_is_unborn:
        head_commit = repo.head.peel(pygit2.Commit)
        if head_commit.tree_id == new_tree_oid:
            return None
        parents = [head_commit.id]

    sig = _signature(repo)
    msg = message or f"Edit at {datetime.now().isoformat(timespec='seconds')}"
    commit_oid = repo.create_commit(
        "HEAD" if repo.head_is_unborn else repo.head.name,
        sig, sig, msg, new_tree_oid, parents,
    )
    return str(commit_oid)


def _credentials_callbacks() -> "pygit2.RemoteCallbacks":
    """Best-effort callbacks for SSH/HTTPS auth. We try the SSH agent
    first; libgit2 also resolves Windows/macOS credential helpers
    transparently when no callbacks are supplied, so callers should
    retry without callbacks if these fail."""
    try:
        return pygit2.RemoteCallbacks(
            credentials=pygit2.KeypairFromAgent("git"))
    except Exception:
        return pygit2.RemoteCallbacks()


def get_remotes(repo_dir: Path) -> list[tuple[str, str]]:
    """Return [(name, url), ...] for every remote configured in the
    repo. Empty list if there is no repo or pygit2 isn't available —
    callers can use that to detect "remote needs configuring"."""
    if not _PYGIT2_OK:
        return []
    repo = _repo_for(repo_dir)
    if repo is None:
        return []
    return [(r.name, r.url) for r in repo.remotes]


def set_remote(repo_dir: Path, name: str, url: str) -> bool:
    """Add a remote or update its URL if it already exists. Returns
    True on success. The repo is created on demand so a fresh
    document can be wired up to a github URL before its first save."""
    if not _PYGIT2_OK or not name or not url:
        return False
    init_repo(repo_dir)
    repo = _repo_for(repo_dir)
    if repo is None:
        return False
    try:
        existing = {r.name for r in repo.remotes}
        if name in existing:
            repo.remotes.set_url(name, url)
        else:
            repo.remotes.create(name, url)
        return True
    except Exception:
        return False


def remove_remote(repo_dir: Path, name: str) -> bool:
    if not _PYGIT2_OK:
        return False
    repo = _repo_for(repo_dir)
    if repo is None:
        return False
    try:
        repo.remotes.delete(name)
        return True
    except Exception:
        return False


def current_branch(repo_dir: Path) -> str | None:
    """Short name of the current branch (e.g. 'dev'), or None if the
    repo is detached / unborn / missing."""
    if not _PYGIT2_OK:
        return None
    try:
        repo = _repo_for(repo_dir)
        if repo is None or repo.head_is_unborn or repo.head_is_detached:
            return None
        name = repo.head.name  # 'refs/heads/dev'
        if name.startswith("refs/heads/"):
            return name[len("refs/heads/"):]
        return name
    except Exception:
        return None


def pull(repo_dir: Path, remote_name: str = "origin") -> tuple[bool, str]:
    """Fetch from `remote_name` and fast-forward the current branch to
    match its upstream. Returns (success, message). Message is a short
    human-readable line for the status bar / dialog — "Already up to
    date", "Pulled 3 commits", "Cannot fast-forward, please merge
    manually" etc.

    We deliberately only do fast-forward merges; if a real merge is
    needed the user should drop to the command line. The KherveCAD
    auto-commit on save means three-way merges from inside the GUI
    would be too easy to misuse and lose work."""
    if not _PYGIT2_OK:
        return False, "pygit2 is not installed."
    repo = _repo_for(repo_dir)
    if repo is None:
        return False, "Not a git repository."
    if remote_name not in [r.name for r in repo.remotes]:
        return False, f"No remote named {remote_name!r} is configured."
    remote = repo.remotes[remote_name]

    # ---- fetch ------------------------------------------------------
    def _fetch() -> tuple[bool, str]:
        for cb in (_credentials_callbacks(), None):
            try:
                remote.fetch(callbacks=cb) if cb else remote.fetch()
                return True, ""
            except Exception as exc:
                last = str(exc)
        return False, last  # noqa: F821 — `last` always bound (loop runs ≥ once)

    ok, err = _fetch()
    if not ok:
        return False, f"Fetch failed: {err}"

    # ---- locate upstream ref ----------------------------------------
    branch = current_branch(repo_dir)
    if branch is None:
        return False, "Repository has no current branch."
    upstream_ref = f"refs/remotes/{remote_name}/{branch}"
    try:
        upstream_oid = repo.lookup_reference(upstream_ref).target
    except Exception:
        return False, (
            f"Remote {remote_name!r} has no branch {branch!r} to pull from."
        )

    # ---- fast-forward ----------------------------------------------
    head_oid = repo.head.target
    if head_oid == upstream_oid:
        return True, "Already up to date."
    merge_analysis, _ = repo.merge_analysis(upstream_oid)
    if merge_analysis & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE:
        return True, "Already up to date."
    if not (merge_analysis & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD):
        return False, (
            "Local branch has diverged from the remote — KherveCAD only "
            "fast-forwards. Resolve the merge from a terminal."
        )
    # Count incoming commits for a nicer status message. `.hide()`
    # tells the walker to stop at head_oid AND skip its ancestors, so
    # the count is exactly "how many new commits this pull brings in"
    # rather than "every commit reachable from upstream_oid".
    walker = repo.walk(upstream_oid, pygit2.GIT_SORT_NONE)
    walker.hide(head_oid)
    incoming = sum(1 for _ in walker)
    try:
        repo.checkout_tree(repo.get(upstream_oid))
        repo.references.get(repo.head.name).set_target(upstream_oid)
        repo.set_head(repo.head.name)
    except Exception as exc:
        return False, f"Fast-forward failed: {exc}"
    plural = "" if incoming == 1 else "s"
    return True, f"Pulled {incoming} commit{plural} from {remote_name}/{branch}."


def _system_git_available() -> bool:
    """True if the user has the system `git` CLI on PATH. We delegate
    HTTPS push to it when libgit2 can't authenticate, because system
    git knows how to talk to Windows Credential Manager / macOS
    Keychain / git credential helpers transparently."""
    return shutil.which("git") is not None


def _git_cli_push(repo_dir: Path, remote_name: str,
                  ref: str) -> tuple[bool, str]:
    """Run `git push <remote> <ref>` via subprocess. Captures stdout
    and stderr so we can surface a useful error message — most
    GitHub HTTPS failures end with a single-line "remote: ..." or
    "fatal: Authentication failed for ..." string that the user
    actually needs to read."""
    try:
        kw: dict = dict(cwd=str(repo_dir), capture_output=True,
                        text=True, timeout=60)
        if sys.platform == "win32":
            kw["creationflags"] = subprocess.CREATE_NO_WINDOW
        proc = subprocess.run(
            ["git", "push", remote_name, ref],
            **kw,
        )
    except subprocess.TimeoutExpired:
        return False, "git push timed out after 60s."
    except FileNotFoundError:
        return False, "System git is not on PATH."
    if proc.returncode == 0:
        return True, f"Pushed to {remote_name}."
    # Distil the most useful line from stderr.
    err = (proc.stderr or proc.stdout or "").strip()
    for line in reversed(err.splitlines()):
        line = line.strip()
        if line.startswith(("fatal:", "error:", "remote:")):
            return False, line
    return False, err.splitlines()[-1] if err else \
        f"git push exited with code {proc.returncode}."


def push(repo_dir: Path, remote_name: str = "origin",
         branch: str = "main") -> tuple[bool, str]:
    """Push the current branch to `remote_name`. Returns (ok, message).

    Strategy:
      1. Try libgit2 with SSH-agent credentials (works for git@ URLs).
      2. Try libgit2 with no callbacks (works for some HTTPS setups).
      3. If both libgit2 attempts fail AND the system `git` CLI is
         available, delegate to `git push`. This is what saves
         GitHub-over-HTTPS users on Windows — pygit2 doesn't talk to
         Windows Credential Manager, but the system git does, so a
         Personal Access Token stored there will just work.

    The message is intended for the user — it's the actual error from
    git (e.g. "fatal: Authentication failed for https://github.com/…")
    when one is available, not a generic "upload failed".
    """
    if not _PYGIT2_OK:
        return False, "pygit2 is not installed."
    if not (repo_dir / ".git").exists():
        return False, "Not a git repository."

    libgit2_err = ""
    head_ref = None
    remote_url = ""
    try:
        repo = pygit2.Repository(str(repo_dir))
        if remote_name not in [r.name for r in repo.remotes]:
            return False, f"No remote named {remote_name!r} is configured."
        remote = repo.remotes[remote_name]
        remote_url = remote.url
        if repo.head_is_unborn:
            return False, "Repository has no commits yet — save first."
        head_ref = repo.head.name  # e.g. "refs/heads/dev"
        refspec = f"{head_ref}:{head_ref}"

        # Attempt 1: SSH agent
        try:
            cb = pygit2.RemoteCallbacks(
                credentials=pygit2.KeypairFromAgent("git"))
            remote.push([refspec], callbacks=cb)
            return True, f"Pushed to {remote_name}."
        except Exception as exc:
            libgit2_err = str(exc)
        # Attempt 2: no callbacks
        try:
            remote.push([refspec])
            return True, f"Pushed to {remote_name}."
        except Exception as exc:
            libgit2_err = str(exc)
    except Exception as exc:
        libgit2_err = str(exc)

    # Attempt 3: system git CLI. Most useful for HTTPS URLs on
    # Windows, where libgit2 has no Credential Manager hookup.
    if head_ref and _system_git_available():
        ok, msg = _git_cli_push(repo_dir, remote_name, head_ref)
        if ok:
            return True, msg
        return False, msg  # surface the CLI's error, more actionable.

    # No git CLI available — best we can do is hand back libgit2's
    # complaint with a hint about credentials.
    hint = ""
    if remote_url.startswith("http"):
        hint = (" Tip: GitHub no longer accepts passwords over HTTPS — "
                "install Git for Windows so the system credential "
                "manager handles your Personal Access Token, or switch "
                "the remote URL to SSH (git@github.com:…).")
    return False, f"Push failed: {libgit2_err}.{hint}"


def restore_to_commit(repo_dir: Path, oid: str,
                      paths: list[str] | None = None) -> tuple[bool, str]:
    """Reset the working tree files to their state at `oid`. Does NOT
    move HEAD — the commit history stays intact; this is a "load this
    older version into the editor" operation, not a rebase. The user
    can then edit and save, which auto-commits the restored contents
    as a new commit on top.

    When `paths` is given, only those files are restored. When None,
    every tracked file at `oid` is restored.

    Returns (ok, message)."""
    if not _PYGIT2_OK:
        return False, "pygit2 is not installed."
    repo = _repo_for(repo_dir)
    if repo is None:
        return False, "Not a git repository."
    try:
        commit = repo.get(oid)
        if commit is None:
            return False, f"Commit {oid[:8]!r} not found."
        commit = commit.peel(pygit2.Commit)
        tree = commit.tree
    except Exception as exc:
        return False, f"Could not read commit: {exc}"
    try:
        if paths:
            # Restore only the listed paths from the commit's tree.
            for p in paths:
                try:
                    entry = tree[p]
                except KeyError:
                    continue  # path didn't exist at that commit
                blob = repo.get(entry.id)
                if blob is None:
                    continue
                target = repo_dir / p
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(blob.data)
        else:
            # Whole-tree checkout, but DON'T move HEAD — pygit2's
            # checkout_tree with strategy SAFE | RECREATE_MISSING
            # rewrites the working tree to match.
            repo.checkout_tree(
                tree,
                strategy=(pygit2.GIT_CHECKOUT_FORCE
                          | pygit2.GIT_CHECKOUT_RECREATE_MISSING),
            )
    except Exception as exc:
        return False, f"Restore failed: {exc}"
    return True, f"Restored files to {oid[:8]}."


def history(repo_dir: Path, limit: int = 50) -> list[tuple[str, str, str]]:
    """Return [(short_oid, iso_time, message_first_line), ...] newest first."""
    if not _PYGIT2_OK or not (repo_dir / ".git").exists():
        return []
    repo = _repo_for(repo_dir)
    if repo is None or repo.head_is_unborn:
        return []
    out: list[tuple[str, str, str]] = []
    for commit in repo.walk(repo.head.target, pygit2.GIT_SORT_TIME):
        out.append((
            str(commit.id)[:8],
            datetime.fromtimestamp(commit.commit_time).isoformat(timespec="seconds"),
            commit.message.splitlines()[0] if commit.message else "",
        ))
        if len(out) >= limit:
            break
    return out


def history_detailed(repo_dir: Path,
                     limit: int = 200,
                     file_stem: str | None = None) -> list[dict]:
    """Richer version of `history` for the GUI commit-browser.

    Each entry is a dict with the keys the history dialog needs:
      - oid:        full hex OID (str)
      - short_oid:  first 8 chars
      - timestamp:  ISO-8601 local time (str)
      - epoch:      Unix epoch (int) — for sorting if a caller needs it
      - author:     "Name <email>"
      - subject:    first line of the commit message
      - body:       lines 2+ of the commit message (may be empty)

    When *file_stem* is given (e.g. ``"Model1"``), only commits that
    touch a file whose name starts with that stem are returned.

    Empty list if pygit2 is missing or the repo has no commits."""
    if not _PYGIT2_OK or not (repo_dir / ".git").exists():
        return []
    repo = _repo_for(repo_dir)
    if repo is None or repo.head_is_unborn:
        return []
    out: list[dict] = []
    for commit in repo.walk(repo.head.target, pygit2.GIT_SORT_TIME):
        if file_stem and not _commit_touches_stem(commit, file_stem):
            continue
        msg = (commit.message or "").rstrip()
        lines = msg.splitlines()
        subject = lines[0] if lines else ""
        body = "\n".join(lines[1:]).strip("\n") if len(lines) > 1 else ""
        author = commit.author
        out.append({
            "oid": str(commit.id),
            "short_oid": str(commit.id)[:8],
            "timestamp": datetime.fromtimestamp(commit.commit_time).isoformat(
                timespec="seconds"),
            "epoch": int(commit.commit_time),
            "author": f"{author.name} <{author.email}>",
            "subject": subject,
            "body": body,
        })
        if len(out) >= limit:
            break
    return out


def _commit_touches_stem(commit, stem: str) -> bool:
    """Return True if *commit* changed any file whose name starts with *stem*."""
    parents = list(commit.parents)
    if not parents:
        # Root commit — check the tree for matching filenames.
        for entry in commit.tree:
            if entry.name.startswith(stem):
                return True
        return False
    parent = parents[0]
    try:
        diff = parent.tree.diff_to_tree(commit.tree)
    except Exception:
        return False
    for delta in diff.deltas:
        old = delta.old_file.path.split("/")[-1]
        new = delta.new_file.path.split("/")[-1]
        if old.startswith(stem) or new.startswith(stem):
            return True
    return False


def list_branches(repo_dir: Path) -> list[dict]:
    """Return info about every local and remote-tracking branch.

    Each entry is a dict:
      - name:    short name (e.g. 'dev', 'main')
      - ref:     full ref (e.g. 'refs/heads/dev')
      - oid:     hex OID the branch points to
      - current: True if this is HEAD
      - remote:  None for local branches, or the remote name ('origin')
    """
    if not _PYGIT2_OK:
        return []
    repo = _repo_for(repo_dir)
    if repo is None:
        return []
    cur = current_branch(repo_dir)
    out: list[dict] = []
    for ref_name in repo.references:
        if ref_name.startswith("refs/heads/"):
            short = ref_name[len("refs/heads/"):]
            try:
                oid = str(repo.references[ref_name].peel(pygit2.Commit).id)
            except Exception:
                continue
            out.append({"name": short, "ref": ref_name, "oid": oid,
                        "current": short == cur, "remote": None})
        elif ref_name.startswith("refs/remotes/"):
            parts = ref_name[len("refs/remotes/"):].split("/", 1)
            if len(parts) == 2 and parts[1] != "HEAD":
                try:
                    oid = str(repo.references[ref_name].peel(pygit2.Commit).id)
                except Exception:
                    continue
                out.append({"name": parts[1], "ref": ref_name, "oid": oid,
                            "current": False, "remote": parts[0]})
    return out


def create_branch(repo_dir: Path, name: str,
                  start_oid: str | None = None) -> tuple[bool, str]:
    """Create a new local branch pointing at *start_oid* (default HEAD).

    Does NOT switch to it — call switch_branch() afterwards if desired.
    Returns (ok, message)."""
    if not _PYGIT2_OK:
        return False, "pygit2 is not installed."
    repo = _repo_for(repo_dir)
    if repo is None:
        return False, "Not a git repository."
    if repo.head_is_unborn:
        return False, "Repository has no commits yet — save first."
    try:
        if start_oid:
            target = repo.get(start_oid).peel(pygit2.Commit)
        else:
            target = repo.head.peel(pygit2.Commit)
        repo.branches.local.create(name, target)
        return True, f"Branch '{name}' created."
    except Exception as exc:
        return False, str(exc)


def switch_branch(repo_dir: Path, name: str) -> tuple[bool, str]:
    """Switch HEAD to an existing local branch. Working-tree files are
    updated to match. Returns (ok, message)."""
    if not _PYGIT2_OK:
        return False, "pygit2 is not installed."
    repo = _repo_for(repo_dir)
    if repo is None:
        return False, "Not a git repository."
    ref = f"refs/heads/{name}"
    try:
        branch_ref = repo.references[ref]
    except KeyError:
        return False, f"Branch '{name}' does not exist."
    try:
        commit = branch_ref.peel(pygit2.Commit)
        repo.checkout_tree(commit, strategy=pygit2.GIT_CHECKOUT_SAFE)
        repo.set_head(ref)
        return True, f"Switched to branch '{name}'."
    except Exception as exc:
        return False, str(exc)


def delete_branch(repo_dir: Path, name: str) -> tuple[bool, str]:
    """Delete a local branch. Cannot delete the current branch.
    Returns (ok, message)."""
    if not _PYGIT2_OK:
        return False, "pygit2 is not installed."
    repo = _repo_for(repo_dir)
    if repo is None:
        return False, "Not a git repository."
    cur = current_branch(repo_dir)
    if name == cur:
        return False, "Cannot delete the branch you are currently on."
    try:
        branch = repo.branches.local[name]
        branch.delete()
        return True, f"Branch '{name}' deleted."
    except KeyError:
        return False, f"Branch '{name}' does not exist."
    except Exception as exc:
        return False, str(exc)


def history_graph(repo_dir: Path, limit: int = 300) -> list[dict]:
    """Build a commit list with graph-rail info for DAG visualisation.

    Returns commits in topological order (newest first). Each entry
    extends history_detailed's dict with:
      - parents:       list of full OIDs of parent commits
      - rail:          int — which column (0-based) this commit draws in
      - rails_before:  list of (from_rail, to_rail) active BEFORE this row
      - rails_after:   list of (from_rail, to_rail) active AFTER this row
      - branches:      list of branch-name strings that point at this OID
      - is_merge:      True if >1 parent
    """
    if not _PYGIT2_OK:
        return []
    repo = _repo_for(repo_dir)
    if repo is None or repo.head_is_unborn:
        return []

    # Collect branch tips so we can label commits.
    branch_map: dict[str, list[str]] = {}  # oid → [branch names]
    for ref_name in repo.references:
        if ref_name.startswith("refs/heads/"):
            short = ref_name[len("refs/heads/"):]
            try:
                oid = str(repo.references[ref_name].peel(pygit2.Commit).id)
            except Exception:
                continue
            branch_map.setdefault(oid, []).append(short)
        elif ref_name.startswith("refs/remotes/"):
            parts = ref_name[len("refs/remotes/"):].split("/", 1)
            if len(parts) == 2 and parts[1] != "HEAD":
                try:
                    oid = str(repo.references[ref_name].peel(pygit2.Commit).id)
                except Exception:
                    continue
                branch_map.setdefault(oid, []).append(f"{parts[0]}/{parts[1]}")

    # Walk ALL refs so we see every branch, not just HEAD.
    seen: set[str] = set()
    raw_commits: list = []
    for ref_name in repo.references:
        try:
            tip = repo.references[ref_name].peel(pygit2.Commit)
        except Exception:
            continue
        for commit in repo.walk(tip.id, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_TIME):
            oid = str(commit.id)
            if oid in seen:
                continue
            seen.add(oid)
            raw_commits.append(commit)
            if len(raw_commits) >= limit:
                break
        if len(raw_commits) >= limit:
            break

    # Re-sort by topo+time (walk order from multiple refs may interleave).
    raw_commits.sort(key=lambda c: -c.commit_time)

    # Assign rails: each "active line" occupies a column. When a commit
    # is encountered its OID is on one of the active rails; when it has
    # parents those parents continue (or fork) the rails.
    active: list[str | None] = []  # active[rail] = oid we expect next

    rows: list[dict] = []
    for commit in raw_commits:
        oid = str(commit.id)
        parent_oids = [str(p.id) for p in commit.parents]
        msg = (commit.message or "").rstrip()
        lines = msg.splitlines()
        subject = lines[0] if lines else ""
        body = "\n".join(lines[1:]).strip("\n") if len(lines) > 1 else ""
        author = commit.author

        # Find which rail this commit sits on.
        if oid in active:
            rail = active.index(oid)
        else:
            # New branch head — allocate a fresh rail.
            if None in active:
                rail = active.index(None)
                active[rail] = oid
            else:
                rail = len(active)
                active.append(oid)

        # Snapshot rails BEFORE this commit (for drawing incoming lines).
        rails_before = []
        for i, a in enumerate(active):
            if a is not None:
                rails_before.append((i, i))

        # Update active rails for this commit's parents.
        if not parent_oids:
            active[rail] = None
        elif len(parent_oids) == 1:
            active[rail] = parent_oids[0]
        else:
            # Merge commit: first parent stays on this rail,
            # additional parents get their own rails.
            active[rail] = parent_oids[0]
            for extra_parent in parent_oids[1:]:
                if extra_parent not in active:
                    if None in active:
                        slot = active.index(None)
                        active[slot] = extra_parent
                    else:
                        active.append(extra_parent)

        # Collapse trailing Nones to keep the graph compact.
        while active and active[-1] is None:
            active.pop()

        # Snapshot rails AFTER this commit.
        rails_after = []
        for i, a in enumerate(active):
            if a is not None:
                rails_after.append((i, i))

        rows.append({
            "oid": oid,
            "short_oid": oid[:8],
            "timestamp": datetime.fromtimestamp(commit.commit_time).isoformat(
                timespec="seconds"),
            "epoch": int(commit.commit_time),
            "author": f"{author.name} <{author.email}>",
            "subject": subject,
            "body": body,
            "parents": parent_oids,
            "rail": rail,
            "rails_before": rails_before,
            "rails_after": rails_after,
            "branches": branch_map.get(oid, []),
            "is_merge": len(parent_oids) > 1,
        })

    return rows


def diff_for_commit(repo_dir: Path, oid: str) -> str:
    """Return the unified diff produced by the given commit, as a single
    str. For a root commit (no parents) the diff is against an empty
    tree, so the whole initial state shows up as additions. Empty
    string if pygit2 is missing or the oid can't be resolved."""
    if not _PYGIT2_OK or not (repo_dir / ".git").exists():
        return ""
    repo = _repo_for(repo_dir)
    if repo is None:
        return ""
    try:
        commit = repo.get(oid)
        if commit is None:
            return ""
        # Resolve through tags / annotated tags etc. to the actual commit.
        commit = commit.peel(pygit2.Commit)
    except Exception:
        return ""
    parents = list(commit.parents)
    try:
        if parents:
            # Compare against the first parent — same as `git show` does
            # for non-merge commits. Merges show diff vs first parent
            # which is the conventional "what landed" view.
            diff = repo.diff(parents[0], commit, context_lines=3)
        else:
            # Root commit: diff against an empty tree so the initial
            # file contents appear as additions instead of an empty diff.
            diff = commit.tree.diff_to_tree(swap=True, context_lines=3)
    except Exception:
        return ""
    return diff.patch or ""
