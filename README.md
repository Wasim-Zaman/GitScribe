# GitScribe

GitScribe is a small command-line tool that uses an OpenAI agent to fetch git commit history from a local repository and produce a polished, human-readable TSV report ready for Google Sheets.

## Features

- Ask for commit summaries in plain English (e.g. "Summarize today's commits").
- Fetches commits across all branches for a given date range.
- Refines commit messages into professional titles, descriptions, categories, and types.
- Exports the results as a tab-separated file that imports cleanly into Google Sheets.

## Prerequisites

- Python 3.10 or newer
- Git
- An [OpenAI API key](https://platform.openai.com/api-keys)

## Installation

```bash
git clone https://github.com/Wasim-Zaman/GitScribe.git
cd GitScribe
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
OPENAI_API_KEY=sk-...
REPO_PATH=/path/to/your/git/repo
```

`REPO_PATH` is optional; you can also tell GitScribe which repo to use in your request.

## Usage

```bash
python main.py                                   # interactive session (remembers context)
python main.py "commits from 2026-10-05 till today, start counter from 418"
python main.py --repo ~/code/api "my commits this week"
```

Flags: `--repo`, `--model` (or `GITSCRIBE_MODEL`), `--output-dir`, `--offline` (skip `git fetch`), `--no-clipboard`.

GitScribe will:

1. Run `git fetch --all` and scan **every local and remote branch** (merge commits skipped, cherry-picks de-duplicated).
2. Refine commits into professional records, grouping near-duplicate follow-ups.
3. Validate the result: no invented commits, none dropped, and dates taken from the real commit timestamps.
4. Write `output/gitscribe_<from>_to_<to>.tsv` and copy the rows to your clipboard, ready to paste into Google Sheets.

## Output

The generated TSV contains these columns:

1. No #
2. Title
3. Date
4. Description
5. Category
6. Type (`New Feature` or `Enhancement`)

## Contributing

Contributions are welcome. Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).

## License

GitScribe is released under the [MIT License](LICENSE).
