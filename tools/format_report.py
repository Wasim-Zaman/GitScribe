from agents import function_tool
from typing import List, Optional
from tools.git_commits import CommitRecord


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


def _predict_type(message: str) -> str:
    """
    Predicts whether a commit represents a 'New Feature' or an 'Enhancement'
    based on keywords in its message/description.

    Heuristic, not ML-based — checks for conventional-commit prefixes and
    common verb patterns. Falls back to 'Enhancement' when ambiguous, since
    most day-to-day commits are incremental changes rather than net-new
    capabilities.
    """
    text = message.lower()

    # Conventional commit prefixes take priority when present
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
def format_report(commits: List[CommitRecord], start: Optional[int] = 1) -> str:
    """
    Takes raw commits and prints a console table with:
    No # | Title | Date | Category | Type

    Category is set via the agent's LLM reasoning before calling this tool
    (expected as `c.category` on each CommitRecord). Type ("Enhancement" or
    "New Feature") is predicted here from the commit message/description
    using keyword heuristics.

    Args:
        commits: List of commit records.
        start: Number to begin the "No #" column at (defaults to 1).
    """
    lines = []
    header = f"{'No #':<6}{'Title':<40}{'Date':<12}{'Category':<15}{'Type':<15}"
    lines.append(header)
    lines.append("-" * len(header))

    for i, c in enumerate(commits, start=start):
        full_message = c.message
        title = full_message.split("\n")[0][:38]
        date = c.date.split("T")[0]
        category = getattr(c, "category", "New Backend")

        # Use full message (title + body) for better prediction context
        description = full_message.split("\n", 1)[1] if "\n" in full_message else ""
        predicted_type = _predict_type(full_message.split("\n")[0] + " " + description)

        lines.append(f"{i:<6}{title:<40}{date:<12}{category:<15}{predicted_type:<15}")

    return "\n".join(lines)