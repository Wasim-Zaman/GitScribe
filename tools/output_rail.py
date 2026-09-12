from agents import function_tool
from typing import List, Optional
from pydantic import BaseModel, Field

import pandas as pd


class RefinedCommit(BaseModel):
    title: str = Field(..., description="Short, refined, professional English title of the change.")
    date: str = Field(..., description="Commit date or date range, e.g. '2026-09-07' or '2026-09-07 to YYYY-MM-DD'.")
    description: str = Field(..., description="Clear explanation of what changed, in good English. Can be multi-line.")
    category: str = Field(default="New Backend", description="Category label, e.g. 'New Backend'.")
    type: Optional[str] = Field(default=None, description="Either 'New Feature' or 'Enhancement'. Inferred if omitted.")


# Keywords that typically signal a brand-new capability rather than an improvement
_NEW_FEATURE_KEYWORDS = (
    "add", "added", "adding",
    "new", "introduce", "introduced",
    "implement", "implemented", "implementing",
    "create", "created", "creating",
    "feature", "feat:", "feat(",
    "support for", "initial",
)

# Keywords that typically signal improving/fixing something that already exists
_ENHANCEMENT_KEYWORDS = (
    "update", "updated", "updating",
    "improve", "improved", "improvement",
    "refactor", "refactored",
    "fix", "fixed", "bugfix", "hotfix",
    "optimize", "optimized", "optimization",
    "enhance", "enhanced", "enhancement",
    "change", "changed",
    "adjust", "adjusted",
    "remove", "removed",
    "cleanup", "clean up",
    "rename", "renamed",
    "perf:", "chore:", "fix:", "refactor:",
)


def _predict_type(text: str) -> str:
    """
    Predicts whether a commit represents a 'New Feature' or an 'Enhancement'
    based on keywords in its title/description.

    Heuristic, not ML-based — checks for conventional-commit prefixes and
    common verb patterns. Falls back to 'Enhancement' when ambiguous.
    """
    text = text.lower()

    if text.startswith("feat:") or text.startswith("feat("):
        return "New Feature"
    if any(text.startswith(p) for p in ("fix:", "fix(", "refactor:", "refactor(", "chore:", "chore(", "perf:", "perf(")):
        return "Enhancement"

    new_feature_hits = sum(1 for kw in _NEW_FEATURE_KEYWORDS if kw in text)
    enhancement_hits = sum(1 for kw in _ENHANCEMENT_KEYWORDS if kw in text)

    if new_feature_hits > enhancement_hits:
        return "New Feature"
    return "Enhancement"


@function_tool
def output_rail(
    commits: List[RefinedCommit],
    start_number: Optional[int] = 1,
    output_path: Optional[str] = "gitscribe_output.tsv",
) -> str:
    """
    Output rail for Google Sheets.

    Builds a tab-separated file from refined commit records using pandas and
    writes it to disk. Columns in the file:
        A: No #
        B: Title
        C: Date
        D: Description
        E: Category
        F: Type

    The rail guards the output by:
      - Predicting Type ('New Feature' or 'Enhancement') from title+description
        when not explicitly supplied (preserved from format_report.py).
      - Replacing any stray tab characters inside cell text with spaces so the
        TSV structure stays valid.
      - Defaulting the category to "New Backend" when omitted.

    Args:
        commits: List of refined commit records.
        start_number: Number to begin the "No #" column at (defaults to 1).
        output_path: Path for the generated TSV file (defaults to
            "gitscribe_output.tsv" in the working directory).

    Returns:
        A short confirmation message. The actual data is written to the TSV file.
    """
    rows = []
    for i, commit in enumerate(commits, start=start_number):
        text_for_type = f"{commit.title} {commit.description}"
        commit_type = commit.type or _predict_type(text_for_type)

        rows.append({
            "No #": i,
            "Title": commit.title.replace("\t", "    "),
            "Date": commit.date.replace("\t", "    "),
            "Description": commit.description.replace("\t", "    "),
            "Category": (commit.category or "New Backend").replace("\t", "    "),
            "Type": commit_type.replace("\t", "    "),
        })

    df = pd.DataFrame(rows, columns=["No #", "Title", "Date", "Description", "Category", "Type"])
    df.to_csv(output_path, sep="\t", index=False)

    return f"Saved {len(rows)} row(s) to {output_path}. Open/import the file into Google Sheets."
