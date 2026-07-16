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
for v in 3.9 3.10 3.11 3.12 3.13 3.14; do
  UV_PROJECT_ENVIRONMENT="/tmp/pyveil-provider-$v" uv run --python "$v" \
    --extra openai --extra anthropic --extra test \
    pytest tests/test_provider_contracts.py -m provider_contract -q --no-cov
done
uv run --extra dev python -m build
uv run --extra dev python -m twine check dist/*
WHEEL="$(find dist -maxdepth 1 -name 'pyveil-*-py3-none-any.whl' -print -quit)"
test -n "$WHEEL"
uv run --isolated --with "$WHEEL" python -c "from pyveil import CustomRule, Veil; assert '[PERSON:' in Veil.high(secret=b'test', rules=[CustomRule.exact('PERSON', 'Alice Kim')]).redact_text('Alice Kim').text"
uv run --isolated --with "$WHEEL" pyveil demo
uv run --isolated --with "$WHEEL" python -m pyveil demo
PYVEIL_SECRET=release-smoke OPENAI_MODEL=gpt-5.6-luna uv run --isolated --with "${WHEEL}[openai]" python -m pyveil.integrations.openai --dry-run
PYVEIL_SECRET=release-smoke ANTHROPIC_MODEL=claude-haiku-4-5 uv run --isolated --with "${WHEEL}[anthropic]" python -m pyveil.integrations.anthropic --dry-run
PYVEIL_SECRET=release-smoke uv run --isolated --with "${WHEEL}[azure-openai]" python -m pyveil.integrations.azure_openai --dry-run
PYVEIL_SECRET=release-smoke uv run --isolated --with "${WHEEL}[ollama]" python -m pyveil.integrations.ollama --dry-run
PYVEIL_SECRET=release-smoke OPENAI_MODEL=gpt-5.6-luna uv run --python 3.8 --isolated --with "${WHEEL}[openai]" python -m pyveil.integrations.openai --dry-run
PYVEIL_SECRET=release-smoke ANTHROPIC_MODEL=claude-haiku-4-5 uv run --python 3.8 --isolated --with "${WHEEL}[anthropic]" python -m pyveil.integrations.anthropic --dry-run
```

## Metadata

- `pyproject.toml` has final project URLs.
- Author and maintainer email are correct.
- License metadata builds cleanly with the Python 3.8-compatible setuptools range.
- `README.md`, `AGENTS.md`, `llms.txt`, and `SECURITY.md` are included in the source distribution.
- `evaluation/` is included in the source distribution and its CI check passes.
- Provider contract tests serialize redacted prompts through the official OpenAI and Anthropic SDKs without network calls.
- Provider SDK metadata keeps Python 3.8 installable while requiring Python 3.9+ only for live OpenAI/Anthropic calls.
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
