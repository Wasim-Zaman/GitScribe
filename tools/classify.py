"""Keyword heuristic fallback for classifying a change as 'New Feature' or 'Enhancement'.

Used only when the LLM leaves ``type`` empty. Consolidated here from the
previously duplicated copies in format_report.py / output_rail.py.
"""

import re

_NEW_FEATURE_KEYWORDS = (
    "add", "added", "adding",
    "new", "introduce", "introduced",
    "implement", "implemented", "implementing",
    "create", "created", "creating",
    "feature", "support for", "initial",
)

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
)

_ENHANCEMENT_PREFIXES = ("fix", "refactor", "chore", "perf", "docs", "style", "test", "build", "ci")


def predict_type(text: str) -> str:
    """Predict 'New Feature' vs 'Enhancement'; ambiguous text falls back to 'Enhancement'."""
    text = text.lower().strip()

    prefix = re.match(r"^(\w+)(\(.*?\))?!?:", text)
    if prefix:
        if prefix.group(1) == "feat":
            return "New Feature"
        if prefix.group(1) in _ENHANCEMENT_PREFIXES:
            return "Enhancement"

    words = set(re.findall(r"[a-z]+", text))
    new_hits = sum(1 for kw in _NEW_FEATURE_KEYWORDS if (kw in words if " " not in kw else kw in text))
    enh_hits = sum(1 for kw in _ENHANCEMENT_KEYWORDS if (kw in words if " " not in kw else kw in text))
    return "New Feature" if new_hits > enh_hits else "Enhancement"
