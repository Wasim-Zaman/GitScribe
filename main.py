"""GitScribe — turn raw git history into polished, Google-Sheets-ready reports.

Usage:
    python main.py                                  # interactive session
    python main.py "commits from 2026-10-05 till today, start from 418"
    python main.py --repo ~/code/api --model gpt-5 "this week's commits"
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from agents import Agent, MaxTurnsExceeded, RunContextWrapper, Runner

from tools import ScribeContext, fetch_commits, output_rail

console = Console()

TOOL_LABELS = {
    "fetch_commits": "🔎 Scanning git history across all branches…",
    "output_rail": "📝 Validating records & writing TSV…",
}


def build_instructions(ctx: RunContextWrapper[ScribeContext], agent: Agent) -> str:
    sc = ctx.context
    now = sc.now()
    return f"""You are GitScribe, an expert technical writer and git history analyst. You turn raw commit
history into polished, release-note quality records for a Google Sheets work log.

## Session facts (authoritative — never guess these)
- Today: {now:%Y-%m-%d} ({now:%A}), local time {now:%H:%M}, timezone {now.tzname()}.
- Default repository: {sc.default_repo or "NOT CONFIGURED — ask the user for a path"}.
- Next counter value if the user says "continue": {sc.next_number}.

## Understanding the request
- Resolve every relative date against Today: "today", "yesterday", "this week" (Monday→today),
  "last week" (previous Mon→Sun), "this month", "last 3 days", "since Monday", etc.
- "from X till today" → date_from=X, date_to=Today. A single date → both ends equal.
- No date mentioned → Today only.
- Counter: "start counter/number/range from 418" → start_number=418. Default 1.
- "my commits" → author="me". Otherwise author=null (all authors).
- sync_remote=true and include_merges=false unless the user says otherwise.

## Workflow
1. Call `fetch_commits` exactly once per repository/date range requested.
2. If it returns an error, explain it plainly and suggest a fix. Do not call output_rail.
3. If total is 0: do NOT call output_rail. Tell the user no commits exist in that range,
   mention `latest_commit_in_repo` and any warnings (e.g. a failed git fetch), and suggest
   a range that does contain work.
4. Otherwise write one RefinedCommit per meaningful change:
   - Usually one record per commit. Merge near-duplicate commits about the SAME change
     (e.g. "fix typo", "wip", "address review", a follow-up fix of a commit from the same day)
     into one record by listing all their hashes in source_hashes.
   - title: imperative, specific, ≤ 80 chars, no conventional-commit prefix
     (e.g. "Add failed-rows download for bulk product imports").
   - description: 1–3 crisp sentences of professional English explaining WHAT changed and
     WHY/impact. Use the subject, body, branch name and changed file paths for context.
     Never invent details that aren't supported by the data.
   - category: domain label such as 'New Backend', 'Frontend', 'Database', 'API', 'DevOps',
     'Security', 'Documentation', 'Testing'. Default 'New Backend' for generic backend work.
   - type: 'New Feature' for genuinely new capabilities/endpoints/modules; 'Enhancement' for
     fixes, refactors, optimisations, docs, chores and improvements to existing things.
   - source_hashes: the hashes exactly as returned by fetch_commits.
5. Call `output_rail` with ALL records and start_number. Every fetched commit must be cited
   exactly once. If it reports VALIDATION FAILED, fix the issues and call it again.
6. Final answer: a short markdown summary (2–5 lines): rows written, the No # range,
   the file path, clipboard status, and any merged/notable items or warnings.
   Do not repeat the full table — the CLI renders it.

## Off-topic requests
If the request is unrelated to git history / changelogs / work logs, politely say GitScribe
specialises in turning git commit history into reports.
"""


def build_agent(model: str | None) -> Agent[ScribeContext]:
    kwargs = {"model": model} if model else {}
    return Agent[ScribeContext](
        name="GitScribe",
        handoff_description="Specialist for fetching and refining git commit history.",
        instructions=build_instructions,
        tools=[fetch_commits, output_rail],
        **kwargs,
    )


def render_report(sc: ScribeContext) -> None:
    report = sc.last_report
    if not report:
        return
    table = Table(title="GitScribe Report", header_style="bold cyan", show_lines=True, expand=True)
    table.add_column("No #", justify="right", style="bold", no_wrap=True)
    table.add_column("Title", style="white", ratio=3)
    table.add_column("Date", style="green", no_wrap=True)
    table.add_column("Description", style="dim", ratio=5)
    table.add_column("Category", style="magenta", no_wrap=True)
    table.add_column("Type", no_wrap=True)
    for r in report.rows:
        type_style = "bold yellow" if r.type == "New Feature" else "cyan"
        table.add_row(str(r.number), r.title, r.date, r.description, r.category, f"[{type_style}]{r.type}[/]")
    console.print(table)
    clip = "[green]✔ copied to clipboard[/green]" if report.copied_to_clipboard else "[dim]clipboard unavailable[/dim]"
    console.print(f"[bold]File:[/bold] [link=file://{report.path}]{report.path}[/link]  {clip}")


async def run_once(agent: Agent, sc: ScribeContext, history: list, query: str) -> list:
    sc.last_report = None
    result = Runner.run_streamed(agent, history + [{"role": "user", "content": query}], context=sc, max_turns=25)

    with console.status("[bold cyan]GitScribe is thinking…[/bold cyan]", spinner="dots") as status:
        async for event in result.stream_events():
            if event.type != "run_item_stream_event":
                continue
            if event.name == "tool_called":
                name = getattr(event.item.raw_item, "name", "tool")
                status.update(f"[bold cyan]{TOOL_LABELS.get(name, f'Running {name}…')}[/bold cyan]")
            elif event.name == "tool_output":
                output = str(event.item.output)
                if output.startswith("VALIDATION FAILED"):
                    console.print("[yellow]↻ Output rail caught issues — agent is self-correcting…[/yellow]")
                status.update("[bold cyan]GitScribe is thinking…[/bold cyan]")

    render_report(sc)
    if result.final_output:
        console.print(Panel(Markdown(str(result.final_output)), title="[bold cyan]GitScribe[/bold cyan]", border_style="green"))
    return result.to_input_list()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="GitScribe — AI git commit history refiner")
    p.add_argument("request", nargs="*", help="One-shot request; omit for interactive mode.")
    p.add_argument("--repo", default=os.getenv("REPO_PATH"), help="Repository path (default: $REPO_PATH).")
    p.add_argument("--model", default=os.getenv("GITSCRIBE_MODEL"), help="Model name (default: $GITSCRIBE_MODEL or SDK default).")
    p.add_argument("--output-dir", default=os.getenv("GITSCRIBE_OUTPUT_DIR", "output"), help="Where TSV files are written.")
    p.add_argument("--offline", action="store_true", help="Never run `git fetch`.")
    p.add_argument("--no-clipboard", action="store_true", help="Don't copy rows to the clipboard.")
    return p.parse_args()


async def main() -> int:
    args = parse_args()
    if not os.getenv("OPENAI_API_KEY"):
        console.print("[bold red]OPENAI_API_KEY is not set.[/bold red] Add it to .env (see .env.example).")
        return 1

    sc = ScribeContext(
        default_repo=(args.repo or "").strip().strip('"') or None,
        output_dir=Path(args.output_dir),
        allow_network=not args.offline,
        use_clipboard=not args.no_clipboard,
    )
    agent = build_agent(args.model)

    console.print(Panel.fit(
        "[bold cyan]GitScribe[/bold cyan] — Git Commit History Refiner\n"
        f"[dim]repo:[/dim] {sc.default_repo or '[red]not set[/red]'}   "
        f"[dim]today:[/dim] {sc.now():%Y-%m-%d (%a)}",
        border_style="cyan",
    ))

    history: list = []
    one_shot = " ".join(args.request).strip()
    while True:
        query = one_shot or Prompt.ask("\n[bold green]Enter your request[/bold green] [dim](or 'exit')[/dim]").strip()
        if not query:
            continue
        if query.lower() in {"exit", "quit", "q", ":q"}:
            return 0
        try:
            history = await run_once(agent, sc, history, query)
        except MaxTurnsExceeded:
            console.print("[red]The agent hit its turn limit. Try a narrower request.[/red]")
        except Exception as exc:  # surface any SDK/API error without a traceback wall
            console.print(f"[bold red]Error:[/bold red] {type(exc).__name__}: {exc}")
        if one_shot:
            return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Bye![/dim]")