from agents import Agent, function_tool
from git import Repo
from datetime import datetime, timedelta

@function_tool
def fetch_commits(repo_path: str, date_from: str = None, date_to: str = None) -> list[dict]:
    """
    Fetch commits from all branches for a given date range.
    Dates in 'YYYY-MM-DD' format. If not provided, defaults to current day.
    """
    repo = Repo(repo_path)
    assert not repo.bare, "Invalid git repo"

    if not date_from and not date_to:
        today = datetime.now().strftime("%Y-%m-%d")
        date_from = date_to = today

    since = date_from
    until = (datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d") if date_to else None

    commits_seen = set()
    results = []

    for branch in repo.branches:
        for commit in repo.iter_commits(branch.name, since=since, until=until):
            if commit.hexsha in commits_seen:
                continue
            commits_seen.add(commit.hexsha)
            results.append({
                "hash": commit.hexsha,
                "author": commit.author.name,
                "date": commit.committed_datetime.isoformat(),
                "branch": branch.name,
                "message": commit.message.strip(),
            })
    return results