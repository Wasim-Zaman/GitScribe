import os
import asyncio

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown
from rich.spinner import Spinner
from rich.live import Live

from agents import Agent, Runner

from tools import fetch_commits, format_report

console = Console()

PATH = os.getenv("REPO_PATH")

commit_polish_agent = Agent(
    name="GitScribe",
    handoff_description="Specialist for fetching and refining git commit history.",
    instructions=(
"You fetch git commit history for a given repo path and date range. "
f"If no path is given, use {PATH}. "
"If no date range is given, use the current day. "
"For each commit, produce these columns: "
"Title (short, refined, professional English), "
"Description (clear explanation of what changed, in good English), "
"Date, "
"Category (e.g. 'New Backend'), "
"Type ('New Feature' or 'Enhancement'). "
"Steps: "
"1. Call fetch_commits to get raw data. "
"2. Reason over each commit to write Title/Description/Type. "
"3. Call format_report with the refined records. "
"If the user asks to start the count/numbering from a specific number "
"(e.g. 'start my count from 231'), pass that number as start_number "
"to format_report. Otherwise omit start_number. "
"4. Your final answer MUST be the exact full text returned by format_report — "
"do not summarize it, do not shorten it, return it in full, as-is."
"If the input query is not related to git commits, return with nice sorry"
"Without wasting any time, direct return with sorry message"
    ),
    tools=[fetch_commits, format_report],
)


async def main() -> None:
    console.print(
        Panel.fit(
            "[bold cyan]GitScribe[/bold cyan] — Git Commit History Refiner",
            border_style="cyan",
        )
    )

    query = Prompt.ask("[bold green]Enter your request[/bold green]")

    with console.status("[bold cyan]GitScribe is working...[/bold cyan]", spinner="dots"):
        result = await Runner.run(
            commit_polish_agent,
            query,
        )

    console.print(Panel(Markdown(result.final_output), title="[bold cyan]Report[/bold cyan]", border_style="green"))
    console.print(f"[dim]Agent:[/dim] [bold magenta]{result.last_agent.name}[/bold magenta]")


if __name__ == "__main__":
    asyncio.run(main())