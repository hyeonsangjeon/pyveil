import copy
import re
from pathlib import Path
from typing import Any

import pytest

from scripts.documentation_checks import DocumentationHTML, check_documentation, quickstart_code


def test_documentation_links_and_quickstarts() -> None:
    assert check_documentation() == []


def test_readme_quickstart_runs_and_preserves_input(capsys: Any) -> None:
    namespace: dict[str, Any] = {}
    exec(compile(quickstart_code(), "README.md quickstart", "exec"), namespace)
    output = capsys.readouterr().out
    assert re.fullmatch(r"Email \[EMAIL:[0-9a-f]{12}\] about ticket 42\.\n", output)
    original = copy.deepcopy(namespace["messages"])
    assert original == [{"role": "user", "content": "Email alice@example.com about ticket 42."}]
    safe = namespace["safe"]
    assert safe.data[0]["role"] == "user"
    assert "alice@example.com" not in repr(safe.findings)
    assert (
        safe.data
        == namespace["veil"].redact_data(original, channel=namespace["Channel"].PROMPT_INPUT).data
    )


def test_quickstart_missing_markers_fails(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("```python\nprint('not marked')\n```", encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one"):
        quickstart_code(tmp_path)


def test_html_code_decodes_entities_and_retains_anchors() -> None:
    page = DocumentationHTML()
    page.feed(
        '<section id="quickstart"><code data-quickstart>x &lt; 3</code>'
        '<a href="manual.html#quickstart">Read</a></section>'
    )
    assert page.quickstarts == ["x < 3"]
    assert page.ids == {"quickstart"}
    assert page.links == ["manual.html#quickstart"]


def test_documentation_check_rejects_drift_and_broken_navigation(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text(
        "<!-- quickstart:python -->\n```python\nprint(1)\n```\n<!-- /quickstart:python -->\n"
        "[bad relative](docs/missing.md)\n"
        "[bad absolute](https://github.com/hyeonsangjeon/pyveil/blob/main/missing.md)",
        encoding="utf-8",
    )
    for name in ("index.html", "manual.html"):
        (tmp_path / "docs" / name).write_text(
            '<code data-quickstart>print(2)</code><a href="index.html#missing">Bad</a>'
            '<img src="missing.png">',
            encoding="utf-8",
        )
    errors = check_documentation(tmp_path)
    assert any("quickstart differs" in error for error in errors)
    assert any("missing anchor" in error for error in errors)
    assert any("missing target" in error for error in errors)
    assert any("PyPI-safe" in error for error in errors)
    assert any("missing repository target" in error for error in errors)
