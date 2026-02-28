# Contributing to Cognigate

Thank you for considering contributing! We welcome all feedback, bug reports, and pull requests.

## Development Setup

```bash
git clone https://github.com/vorionsys/cognigate.git
cd cognigate
pip install -e .
uvicorn app.main:app --reload
```

## How to Submit Changes

1. Fork the repo
2. Create a feature branch (`git checkout -b feat/amazing-feature`)
3. Commit with [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, etc.)
4. Push and open a Pull Request

All PRs must pass CI and include tests for new functionality.

## Reporting Bugs

Open a [bug report](https://github.com/vorionsys/cognigate/issues/new?template=bug_report.md) with:
- Steps to reproduce
- Expected vs actual behavior
- Python version and OS

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Questions?

Open a [discussion](https://github.com/vorionsys/cognigate/issues) or reach out at security@vorion.org.
