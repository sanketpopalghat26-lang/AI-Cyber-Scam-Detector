# Contributing to AI Cyber Scam Detector

Thank you for considering contributing to **AI Cyber Scam Detector**! We welcome
contributions from the community. This document outlines the process for
contributing to the project.

## Code of Conduct

By participating in this project, you agree to abide by our
[Code of Conduct](CODE_OF_CONDUCT.md).

## How to Contribute

### 1. Reporting Bugs

- Check the [open issues](https://github.com/organization/ai-cyber-scam-detector/issues) to see if the issue has already been reported.
- If not, create a new issue with a clear title and description.
- Include steps to reproduce, expected behavior, and actual behavior.
- Include the version and environment details.

### 2. Suggesting Enhancements

- Create an issue describing the enhancement and why it's valuable.
- Provide examples of usage and expected behavior.

### 3. Submitting Code Changes

1. **Fork** the repository and create a feature branch:
   ```bash
   git checkout -b feature/your-feature
   ```
2. **Make your changes** following the project's coding standards.
3. **Write tests** for your changes.
4. **Run the full validation suite** (see below).
5. **Commit** with a clear, descriptive message.
6. **Push** and open a **pull request** against `main`.

## Development Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
pip install ruff mypy black isort pytest pytest-cov
```

### Frontend

```bash
cd frontend
npm install
```

## Code Standards

- **Python**: Follow PEP 8. Use `ruff` and `black` for linting/formatting.
- **Type hints**: Add type hints to all function signatures.
- **Tests**: Every new feature must include tests.
- **Documentation**: Update relevant docs when changing behavior.

## Running Validation

```bash
# Lint
ruff check backend/ enterprise_pipeline/
black --check backend/ enterprise_pipeline/
isort --check-only --diff backend/ enterprise_pipeline/

# Type check
mypy backend/ enterprise_pipeline/

# Tests
pytest -v --cov=backend --cov=enterprise_pipeline --cov-fail-under=80

# Security
bandit -r backend/ enterprise_pipeline/
pip-audit -r backend/requirements.txt
safety check -r backend/requirements.txt
```

## Commit Message Guidelines

Use conventional commits:

- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation changes
- `style:` formatting, no code change
- `refactor:` code change that doesn't fix a bug or add a feature
- `test:` adding or updating tests
- `chore:` maintenance tasks

## Pull Request Checklist

- [ ] Tests pass and coverage is ≥ 80%
- [ ] Lint (ruff, black, isort) passes
- [ ] Type check (mypy) passes
- [ ] Security scans pass
- [ ] Documentation updated
- [ ] No secrets committed

## License

By contributing, you agree that your contributions will be licensed under the
project's [Proprietary Enterprise License](LICENSE).
