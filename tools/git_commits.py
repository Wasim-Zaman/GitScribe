"""Git commit fetching tool.

Uses the git CLI directly (fast, and it can see remote branches) instead of
iterating local branches only. Improvements over the previous version:

* Scans **all local and remote-tracking branches**, not just local ones.
* Optionally runs ``git fetch --all`` first so freshly pushed work is visible.
* Filters by **author date in local time** (rebases/merges don't shift dates).
* Skips merge commits by default (PR merges are noise in a changelog).
* De-duplicates cherry-picks/rebased copies across branches.
* Returns file + line stats so the LLM can write much better descriptions.
* Returns diagnostics (latest commit in repo, warnings) when nothing is found.
"""

from __future__ import annotations

import json
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from agents import RunContextWrapper, function_tool

from tools.context import CommitRecord, ScribeContext

_REC = "\x1e"
_SEP = "\x1f"
_FORMAT = _SEP.join(["%H", "%an", "%ae", "%aI", "%S", "%P", "%s", "%b"])
_MAX_BODY = 1500
_MAX_FILES = 15


class GitError(RuntimeError):
    pass


def _git(repo: str, *args: str, timeout: int = 60) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", repo, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise GitError("git executable not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError(f"git {' '.join(args[:2])} timed out after {timeout}s") from exc
    if proc.returncode != 0:
        raise GitError(proc.stderr.strip() or f"git {args[0]} failed")
    return proc.stdout


def resolve_repo(repo_path: Optional[str], default: Optional[str]) -> str:
    raw = (repo_path or default or "").strip().strip('"').strip("'")
    if not raw:
        raise GitError("No repository path given and REPO_PATH is not configured.")
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        raise GitError(f"Repository path does not exist: {path}")
    return _git(str(path), "rev-parse", "--show-toplevel").strip()


def _parse_day(value: Optional[str], field_name: str) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise GitError(f"{field_name} must be YYYY-MM-DD, got {value!r}") from exc


def _clean_ref(ref: str) -> str:
    for prefix in ("refs/heads/", "refs/remotes/", "refs/tags/"):
        if ref.startswith(prefix):
            return ref[len(prefix):]
    return ref


def _parse_log(output: str) -> List[CommitRecord]:
    records: List[CommitRecord] = []
    for chunk in output.split(_REC):
        if not chunk.strip():
            continue
        parts = chunk.split(_SEP)
        if len(parts) < 8:
            continue
        sha, author, email, adate, source, _parents, subject = parts[:7]
        # Body is followed by the --numstat block, separated by a blank line.
        tail = _SEP.join(parts[7:])
        body, files, ins, dels = tail, [], 0, 0
        lines = tail.rstrip("\n").split("\n")
        stat_lines: List[str] = []
        while lines and _is_numstat(lines[-1]):
            stat_lines.insert(0, lines.pop())
        body = "\n".join(lines).strip()
        for line in stat_lines:
            a, d, name = line.split("\t", 2)
            ins += int(a) if a.isdigit() else 0
            dels += int(d) if d.isdigit() else 0
            files.append(name)

        local_dt = datetime.fromisoformat(adate).astimezone()
        records.append(
            CommitRecord(
                hash=sha,
                short_hash=sha[:8],
                author=author,
                email=email,
                date=local_dt.isoformat(timespec="seconds"),
                branch=_clean_ref(source),
                subject=subject.strip(),
                body=body[:_MAX_BODY] + ("…" if len(body) > _MAX_BODY else ""),
                files_changed=len(files),
                insertions=ins,
                deletions=dels,
                files=files[:_MAX_FILES],
            )
        )
    return records


def _is_numstat(line: str) -> bool:
    parts = line.split("\t")
    return len(parts) == 3 and all(p.isdigit() or p == "-" for p in parts[:2])


def collect_commits(
    repo: str,
    day_from: date,
    day_to: date,
    author: Optional[str] = None,
    include_merges: bool = False,
    branch: Optional[str] = None,
) -> List[CommitRecord]:
    """Pure helper (no LLM), reusable from tests and the CLI."""
    args = [
        "log",
        "--source",
        f"--format={_REC}{_FORMAT}",
        "--numstat",
        # Committer date >= author date, so this is a safe superset filter.
        f"--since={day_from.isoformat()} 00:00:00",
    ]
    args += [branch] if branch else ["--branches", "--remotes"]
    if not include_merges:
        args.append("--no-merges")
    if author:
        args += [f"--author={author}", "--regexp-ignore-case"]

    commits = _parse_log(_git(repo, *args))

    seen_keys = set()
    result: List[CommitRecord] = []
    for c in commits:
        day = datetime.fromisoformat(c.date).date()
        if not (day_from <= day <= day_to):
            continue
        key = (c.email.lower(), c.date, c.subject)  # cherry-picks / rebased copies
        if c.hash in seen_keys or key in seen_keys:
            continue
        seen_keys.update({c.hash, key})
        result.append(c)

    result.sort(key=lambda c: datetime.fromisoformat(c.date))
    return result


def _latest_commit_date(repo: str) -> Optional[str]:
    try:
        out = _git(repo, "log", "--branches", "--remotes", "-1", "--format=%aI|%s")
    except GitError:
        return None
    if not out.strip():
        return None
    when, _, subject = out.strip().partition("|")
    return f"{datetime.fromisoformat(when).astimezone():%Y-%m-%d %H:%M} — {subject}"


@function_tool
def fetch_commits(
    ctx: RunContextWrapper[ScribeContext],
    repo_path: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    author: Optional[str],
    include_merges: bool,
    sync_remote: bool,
) -> str:
    """Fetch commits from every local and remote branch for an inclusive date range.

    Args:
        repo_path: Repository path. Pass null to use the configured default repository.
        date_from: Inclusive start day, YYYY-MM-DD. Null means same as date_to (or today).
        date_to: Inclusive end day, YYYY-MM-DD. Null means today.
        author: Optional author name/email filter (case-insensitive substring). Use "me"
            for the repository's configured git user. Null for all authors.
        include_merges: Include merge commits. Usually false (merge/PR commits are noise).
        sync_remote: Run `git fetch --all` first so recently pushed commits are visible.
            Usually true.

    Returns:
        JSON with the commits (oldest first), their file/line stats, and diagnostics.
    """
    sc = ctx.context
    warnings: List[str] = []
    try:
        repo = resolve_repo(repo_path, sc.default_repo)
        today = sc.now().date()
        d_to = _parse_day(date_to, "date_to") or today
        d_from = _parse_day(date_from, "date_from") or d_to
        if d_from > d_to:
            d_from, d_to = d_to, d_from
        if d_to > today:
            warnings.append(f"date_to {d_to} is in the future; clamped to today {today}.")
            d_to = max(today, d_from)

        if author and author.strip().lower() in {"me", "myself", "mine", "i"}:
            author = _git(repo, "config", "user.email").strip() or None

        if sync_remote and sc.allow_network:
            try:
                _git(repo, "fetch", "--all", "--prune", "--quiet", timeout=45)
            except GitError as exc:
                warnings.append(f"git fetch failed (using local data only): {exc}")

        commits = collect_commits(repo, d_from, d_to, author=author, include_merges=include_merges)
    except GitError as exc:
        return json.dumps({"error": str(exc)})

    for c in commits:
        sc.fetched[c.hash] = c
        if c.hash not in sc.pending:
            sc.pending.append(c.hash)
    sc.last_range = (d_from.isoformat(), d_to.isoformat())

    payload = {
        "repo": repo,
        "date_from": d_from.isoformat(),
        "date_to": d_to.isoformat(),
        "author_filter": author,
        "total": len(commits),
        "warnings": warnings,
        "commits": [c.model_dump(exclude={"hash"}) | {"hash": c.short_hash} for c in commits],
    }
    if not commits:
        payload["latest_commit_in_repo"] = _latest_commit_date(repo)
    return json.dumps(payload, ensure_ascii=False)