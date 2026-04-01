# Contributing to Jagabot

Thank you for your interest in contributing to **jagabot** — a financial risk management AI assistant for Malaysian retail investors.

## Getting Started

1. **Fork** the repository
2. **Clone** your fork: `git clone https://github.com/<you>/jagabot.git`
3. **Install** in development mode:
   ```bash
   cd jagabot
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```
4. **Run tests**: `python -m pytest tests/ -q`

## Development Workflow

1. Create a feature branch: `git checkout -b feat/my-feature`
2. Make your changes
3. Run the full test suite: `python -m pytest tests/ -q`
4. Commit with a descriptive message
5. Open a Pull Request

## Adding a New Tool

All tools follow the `Tool` ABC pattern in `jagabot/agent/tools/base.py`:

1. Create `jagabot/agent/tools/my_tool.py` implementing `Tool`
2. Define `name`, `description`, `parameters` (JSON Schema)
3. Implement `async execute(**kwargs) -> str`
4. Register in **3 places**:
   - `jagabot/agent/loop.py` → `_register_default_tools()`
   - `jagabot/agent/tools/__init__.py` → imports + `__all__`
   - `jagabot/guardian/tools/__init__.py` → `ALL_TOOLS` list
5. Write tests in `tests/test_jagabot/`
6. Update `jagabot/skills/financial/SKILL.md` if relevant

## Code Style

- Python 3.11+
- Type hints on all public functions
- Docstrings on classes and public methods
- Keep tools stateless — pure functions where possible

## Testing

- Use `pytest` + `pytest-asyncio` for async tool tests
- Target: every tool method has at least 2 test cases
- Run: `python -m pytest tests/ -q`

## Locale Support

Jagabot supports `en`, `ms` (Malay), and `id` (Indonesian). When adding user-facing strings, include translations for all three locales.

## Reporting Issues

- Use GitHub Issues
- Include: Python version, OS, steps to reproduce, expected vs actual behavior
- For security issues, see [SECURITY.md](SECURITY.md)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
