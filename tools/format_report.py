from agents import function_tool
from typing import List
from tools.git_commits import CommitRecord


@function_tool
def format_report(commits: List[CommitRecord]) -> str:
    """
    Takes raw commits and prints a console table with:
    Title | Description | Date | Category | Type
    (Refinement/classification into New Backend/Enhancement/New Feature
    happens via the agent's LLM reasoning before calling this tool.)
    """
    lines = []
    header = f"{'Title':<40} {'Date':<12} {'Category':<15} {'Type':<15}"
    lines.append(header)
    lines.append("-" * len(header))

    for c in commits:
        title = c.message.split("\n")[0][:38]
        date = c.date.split("T")[0]
        lines.append(f"{title:<40} {date:<12} {'New Backend':<15} {'':<15}")

    return "\n".join(lines)