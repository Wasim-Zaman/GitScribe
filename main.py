import asyncio

from dotenv import load_dotenv

load_dotenv()

from agents import Agent, Runner

from tools.git_commits import fetch_commits

commit_polish_agent = Agent(
    name="CommitPolish",
    handoff_description="Specialist for fetching and refining git commit history.",
    instructions=(
        "You fetch git commit history for a given repo path and date range, "
        "then rewrite each commit message in clear, professional English "
        "without changing its meaning."
    ),
    tools=[fetch_commits],
)


async def main() -> None:
    result = await Runner.run(
        commit_polish_agent,
        "Who was the first president of the United States?",
    )
    print(result.final_output)
    print(result.last_agent.name)


if __name__ == "__main__":
    asyncio.run(main())