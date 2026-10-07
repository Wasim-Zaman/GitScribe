"""Shared run context passed to every tool via RunContextWrapper.

The context is the agent's "ground truth": the commits that were actually
fetched from git live here, so the output rail can verify that the LLM neither
invented nor dropped any commit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel


class CommitRecord(BaseModel):
    hash: str
    short_hash: str
    author: str
    email: str
    date: str  # local ISO-8601 author datetime
    branch: str
    subject: str
    body: str
    files_changed: int
    insertions: int
    deletions: int
    files: List[str]


class ReportRow(BaseModel):
    number: int
    title: str
    date: str
    description: str
    category: str
    type: str
    source_hashes: List[str]


class Report(BaseModel):
    path: str
    rows: List[ReportRow]
    copied_to_clipboard: bool


@dataclass
class ScribeContext:
    default_repo: Optional[str] = None
    output_dir: Path = field(default_factory=lambda: Path("output"))
    allow_network: bool = True
    use_clipboard: bool = True

    # Every commit ever fetched in this session, keyed by full hash.
    fetched: Dict[str, CommitRecord] = field(default_factory=dict)
    # Hashes fetched since the last successful report; all must be covered.
    pending: List[str] = field(default_factory=list)
    # Date range of the most recent fetch (used for the output filename).
    last_range: Optional[tuple[str, str]] = None
    # Result of the latest output_rail call (rendered by the CLI).
    last_report: Optional[Report] = None
    # Counter continuity across requests in the same session.
    next_number: int = 1

    @staticmethod
    def now() -> datetime:
        return datetime.now().astimezone()
