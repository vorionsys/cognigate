# Contributing to Cognigate

Thank you for your interest in contributing to Cognigate, the open governance gateway for AI agents.

## Development Setup

```bash
git clone https://github.com/vorionsys/cognigate.git
cd cognigate
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
pytest
```

## Pull Request Process

1. Fork the repository and create a feature branch.
2. Use Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
3. Include or update tests for behavior changes.
4. Ensure all tests pass before requesting review.

## Developer Certificate of Origin (DCO)

By contributing to this project, you certify that your contribution was created in whole or in part by you and you have the right to submit it under the Apache-2.0 license. All commits must include a `Signed-off-by` line:

```
Signed-off-by: Your Name <your.email@example.com>
```

Use `git commit -s` to add this automatically.

## Reporting Issues

Use GitHub Issues with clear reproduction steps, expected behavior, and relevant logs.

## Code of Conduct

By participating, you agree to follow the [Code of Conduct](.github/CODE_OF_CONDUCT.md) in this repository.
