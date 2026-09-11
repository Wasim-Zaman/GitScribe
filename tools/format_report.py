from agents import function_tool
from typing import List, Optional
from tools.git_commits import CommitRecord


@function_tool
def format_report(commits: List[CommitRecord], start_number: Optional[int] = None) -> str:
    """
    Takes raw commits and prints a console table with:
    Title | Description | Date | Category | Type
    (Refinement/classification into New Backend/Enhancement/New Feature
    happens via the agent's LLM reasoning before calling this tool.)

    start_number: number to start counting from (e.g. 231). If not
    provided, counting starts at 1.

    The output has two sections:
    1. A pretty console table for reading.
    2. A tab-separated section labeled 'EXCEL COPY' — copy that section
       and paste into Excel; each field lands in its own column.
    """
    start = start_number if start_number is not None else 1

    lines = []
    header = f"{'NO':<5} {'Title':<40} {'Date':<12} {'Category':<15} {'Type':<15}"
    lines.append(header)
    lines.append("-" * len(header))

    tsv_lines = ["NO\tTitle\tDate\tCategory\tType"]

    for i, c in enumerate(commits, start=start):
        title = c.message.split("\n")[0][:38]
        date = c.date.split("T")[0]
        lines.append(f"{i:<5} {title:<40} {date:<12} {'New Backend':<15} {'':<15}")
        tsv_lines.append(f"{i}\t{title}\t{date}\tNew Backend\t")

    lines.append("")
    lines.append("=== EXCEL COPY (tab-separated, paste into Excel) ===")
    lines.extend(tsv_lines)

    return "\n".join(lines)