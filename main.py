import asyncio

from dotenv import load_dotenv
load_dotenv()

from agents import Agent, Runner

from tools import fetch_commits

PATH = "/Users/wasimzaman/Wasim/coding/--Node/GS1KSA/gs1ksa_administrators_api"

commit_polish_agent = Agent(
    name="GitScribe",
    handoff_description="Specialist for fetching and refining git commit history.",
    instructions=(
        "You fetch git commit history for a given repo path and date range, "
        "then rewrite each commit message in clear, professional English "
        "without changing its meaning."
        f"If you do not find the path you have to use {PATH}"
    ),
    tools=[fetch_commits],
)


async def main() -> None:
    result = await Runner.run(
        commit_polish_agent,
        # f"Fetch commits from {PATH} for 2026-09-09 and refine the messages.",
        input("Enter your query: "),
    )
    print(result.final_output)
    print(result.last_agent.name)


if __name__ == "__main__":
    asyncio.run(main())