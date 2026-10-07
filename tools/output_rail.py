"""Output rail: validates the LLM's refined records and writes a Google-Sheets-ready TSV.

Guard rails:
* Every refined record must cite the commit hashes it summarises.
* Unknown (hallucinated) hashes are rejected.
* Every fetched commit must be covered exactly once, so nothing gets dropped.
* Dates are derived from the real commit timestamps, not trusted from the LLM.
* Rows are always sorted chronologically and numbered from ``start_number``.
* The rows (without a header) are copied to the clipboard for a direct paste.
"""

from __future__ import annotations

import csv
import io
import platform
import shutil
import subprocess
from datetime import datetime
from typing import Dict, List, Literal, Optional

from agents import RunContextWrapper, function_tool
from pydantic import BaseModel, Field

from tools.classify import predict_type
from tools.context import CommitRecord, Report, ReportRow, ScribeContext

COLUMNS = ["No #", "Title", "Date", "Description", "Category", "Type"]


class RefinedCommit(BaseModel):
    title: str = Field(..., description="Short, professional, imperative-mood title.")
    description: str = Field(..., description="Clear explanation of what changed and why.")
    category: str = Field(..., description="Category label, e.g. 'New Backend'.")
    type: Optional[Literal["New Feature", "Enhancement"]] = Field(
        ..., description="'New Feature' or 'Enhancement'. Null to infer automatically."
    )
    source_hashes: List[str] = Field(
        ..., description="Hashes (from fetch_commits) of every commit this record summarises."
    )


def _clean(text: str) -> str:
    return text.replace("\t", " ").replace("\r", "").strip()


def _resolve(h: str, fetched: Dict[str, CommitRecord]) -> Optional[str]:
    h = h.strip().lower()
    if len(h) < 6:
        return None
    matches = [full for full in fetched if full.startswith(h)]
    return matches[0] if len(matches) == 1 else None


def _copy_to_clipboard(text: str) -> bool:
    system = platform.system()
    candidates = {
        "Darwin": [["pbcopy"]],
        "Windows": [["clip"]],
    }.get(system, [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "-ib"]])
    for cmd in candidates:
        if shutil.which(cmd[0]):
            try:
                subprocess.run(cmd, input=text, text=True, check=True, timeout=5)
                return True
            except (subprocess.SubprocessError, OSError):
                continue
    return False


def _to_tsv(rows: List[List[str]]) -> str:
    buf = io.StringIO()
    csv.writer(buf, delimiter="\t", lineterminator="\n").writerows(rows)
    return buf.getvalue()


@function_tool
def output_rail(
    ctx: RunContextWrapper[ScribeContext],
    commits: List[RefinedCommit],
    start_number: int,
) -> str:
    """Validate refined commit records and write them to a TSV for Google Sheets.

    Columns: No # | Title | Date | Description | Category | Type. Dates are derived
    automatically from the cited commits. If validation fails, fix the listed problems
    and call this tool again.

    Args:
        commits: Refined records. Together they must cite every fetched commit exactly once.
        start_number: Number for the first row's "No #" column (1 unless the user asked otherwise).
    """
    sc = ctx.context
    problems: List[str] = []
    used: Dict[str, int] = {}
    resolved_records: List[tuple[RefinedCommit, List[CommitRecord]]] = []

    for idx, rc in enumerate(commits):
        sources: List[CommitRecord] = []
        if not rc.source_hashes:
            problems.append(f"Record {idx} ('{rc.title}') cites no source_hashes.")
        for h in rc.source_hashes:
            full = _resolve(h, sc.fetched)
            if not full:
                problems.append(f"Record {idx} cites unknown hash '{h}'. Use hashes from fetch_commits only.")
                continue
            if full in used and used[full] != idx:
                problems.append(f"Commit {full[:8]} is cited by records {used[full]} and {idx}; cite it once.")
            used[full] = idx
            sources.append(sc.fetched[full])
        if sources:
            resolved_records.append((rc, sources))

    missing = [h for h in sc.pending if h not in used]
    if missing:
        listing = "; ".join(f"{h[:8]} '{sc.fetched[h].subject}'" for h in missing[:40])
        problems.append(
            f"{len(missing)} fetched commit(s) are not covered by any record: {listing}. "
            "Add them to an existing record's source_hashes or create new records."
        )

    if problems:
        return "VALIDATION FAILED — nothing written. Fix and call output_rail again:\n- " + "\n- ".join(problems)

    if not resolved_records:
        sc.last_report = None
        return "No commits to write — the TSV file was not created."

    def first_dt(item):
        return min(datetime.fromisoformat(c.date) for c in item[1])

    resolved_records.sort(key=first_dt)
    start = start_number if start_number and start_number > 0 else 1

    rows: List[ReportRow] = []
    for number, (rc, sources) in enumerate(resolved_records, start=start):
        days = sorted({datetime.fromisoformat(c.date).date().isoformat() for c in sources})
        date_str = days[0] if len(days) == 1 else f"{days[0]} to {days[-1]}"
        commit_type = rc.type or predict_type(
            " ".join([rc.title, rc.description] + [c.subject for c in sources])
        )
        rows.append(
            ReportRow(
                number=number,
                title=_clean(rc.title),
                date=date_str,
                description=_clean(rc.description),
                category=_clean(rc.category) or "New Backend",
                type=commit_type,
                source_hashes=[c.short_hash for c in sources],
            )
        )

    table = [[str(r.number), r.title, r.date, r.description, r.category, r.type] for r in rows]

    sc.output_dir.mkdir(parents=True, exist_ok=True)
    d_from, d_to = sc.last_range or (rows[0].date[:10], rows[-1].date[-10:])
    name = f"gitscribe_{d_from}.tsv" if d_from == d_to else f"gitscribe_{d_from}_to_{d_to}.tsv"
    path = (sc.output_dir / name).resolve()
    path.write_text(_to_tsv([COLUMNS] + table), encoding="utf-8")

    copied = sc.use_clipboard and _copy_to_clipboard(_to_tsv(table))

    sc.last_report = Report(path=str(path), rows=rows, copied_to_clipboard=copied)
    sc.pending.clear()
    sc.next_number = rows[-1].number + 1

    return (
        f"SUCCESS: wrote {len(rows)} row(s) (No # {rows[0].number}–{rows[-1].number}) "
        f"covering {len(used)} commit(s) to {path}."
        + (" Rows copied to clipboard (paste directly into Google Sheets)." if copied else "")
    )
