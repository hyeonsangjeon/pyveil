# Release Checklist

Use this checklist before tagging a release.

## Required Gates

```bash
uv run --extra dev ruff check .
uv run --extra dev mypy pyveil tests
uv run --extra test pytest
uv run --extra test python evaluation/evaluate.py --check
for v in 3.8 3.9 3.10 3.11 3.12 3.13 3.14; do
  UV_PROJECT_ENVIRONMENT="/tmp/pyveil-venv-$v" uv run --python "$v" --extra test pytest -q --disable-warnings --no-cov
done
uv run --extra dev python -m build
uv run --extra dev python -m twine check dist/*
uv run --isolated --with ./dist/pyveil-0.2.2-py3-none-any.whl python -c "from pyveil import CustomRule, Veil; assert '[PERSON:' in Veil.high(secret=b'test', rules=[CustomRule.exact('PERSON', 'Alice Kim')]).redact_text('Alice Kim').text"
uv run --isolated --with ./dist/pyveil-0.2.2-py3-none-any.whl pyveil demo
uv run --isolated --with ./dist/pyveil-0.2.2-py3-none-any.whl python -m pyveil demo
PYVEIL_SECRET=release-smoke uv run --isolated --with './dist/pyveil-0.2.2-py3-none-any.whl[azure-openai]' python -m pyveil.integrations.azure_openai --dry-run
```

## Metadata

- `pyproject.toml` has final project URLs.
- Author and maintainer email are correct.
- License metadata builds cleanly with the Python 3.8-compatible setuptools range.
- `README.md`, `AGENTS.md`, `llms.txt`, and `SECURITY.md` are included in the source distribution.
- `evaluation/` is included in the source distribution and its CI check passes.
- Version in `pyproject.toml` matches the changelog.

## Publishing

- GitHub Actions test matrix is green.
- Build artifacts pass `twine check`.
- PyPI trusted publishing is configured for `.github/workflows/release.yml`.
- GitHub release notes are prepared.

## Security

- No raw secrets or PII in tests, docs, fixtures, exceptions, or logs.
- Detector provenance is documented.
- No proprietary legacy rules are copied into the package.
