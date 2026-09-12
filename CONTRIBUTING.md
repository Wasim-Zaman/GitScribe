# Contributing to GitScribe

Thank you for considering contributing to GitScribe!

## How to contribute

1. **Open an issue first** to discuss bug fixes or new features before investing a lot of time.
2. **Fork the repository** and create a feature branch.
3. **Make your changes** with clear, focused commits.
4. **Test your changes** locally by running the tool with a sample repository.
5. **Open a pull request** describing what changed and why.

## Development setup

```bash
git clone https://github.com/Wasim-Zaman/GitScribe.git
cd GitScribe
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env with your OPENAI_API_KEY and REPO_PATH
```

## Code style

- Keep changes minimal and focused.
- Add or update docstrings for new tools and functions.
- Do not commit secrets, API keys, or personal file paths.

## Reporting security issues

If you discover a security problem (for example, an accidentally committed secret), please do not open a public issue. Contact the maintainers privately so we can resolve it safely.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
