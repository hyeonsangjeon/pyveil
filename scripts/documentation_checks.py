"""Check the public quickstart and local HTML navigation without network access."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent


class DocumentationHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.links: list[str] = []
        self.quickstarts: list[str] = []
        self._quickstart: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.add(str(attributes["id"]))
        for attribute in ("href", "src"):
            if attributes.get(attribute):
                self.links.append(str(attributes[attribute]))
        if tag == "code" and "data-quickstart" in attributes:
            self._quickstart = []

    def handle_data(self, data: str) -> None:
        if self._quickstart is not None:
            self._quickstart.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "code" and self._quickstart is not None:
            self.quickstarts.append("".join(self._quickstart).strip())
            self._quickstart = None


def quickstart_code(root: Path = ROOT) -> str:
    text = (root / "README.md").read_text(encoding="utf-8")
    matches: list[str] = re.findall(
        r"<!-- quickstart:python -->\s*```python\n(.*?)\n```\s*<!-- /quickstart:python -->",
        text,
        re.DOTALL,
    )
    if len(matches) != 1:
        raise ValueError("README must contain exactly one marked Python quickstart")
    return matches[0].strip()


def check_documentation(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    snippet = quickstart_code(root)
    for filename in ("index.html", "manual.html"):
        page = DocumentationHTML()
        page.feed((root / "docs" / filename).read_text(encoding="utf-8"))
        if page.quickstarts != [snippet]:
            errors.append(f"docs/{filename}: quickstart differs from README")

    for source in (root / "docs").rglob("*.html"):
        page = DocumentationHTML()
        page.feed(source.read_text(encoding="utf-8"))
        for link in page.links:
            url = urlsplit(link)
            if url.netloc == "hyeonsangjeon.github.io" and url.path.startswith("/pyveil/"):
                target = root / "docs" / unquote(url.path[len("/pyveil/") :])
            elif url.scheme or url.netloc:
                continue
            else:
                target = source.parent / unquote(url.path) if url.path else source
            if target.is_dir():
                target = target / "index.html"
            if not target.is_file():
                errors.append(f"{source.relative_to(root)}: missing target {link}")
            elif url.fragment and target.suffix == ".html":
                destination = DocumentationHTML()
                destination.feed(target.read_text(encoding="utf-8"))
                if unquote(url.fragment) not in destination.ids:
                    errors.append(f"{source.relative_to(root)}: missing anchor {link}")

    # README uses inline Markdown links. Relative file links fail on PyPI.
    readme = (root / "README.md").read_text(encoding="utf-8")
    for link in re.findall(r"\]\(([^\s)]+)\)", readme):
        url = urlsplit(link)
        if not url.scheme and not link.startswith("#"):
            errors.append(f"README: use a PyPI-safe absolute link for {link}")
        prefix = "https://github.com/hyeonsangjeon/pyveil/blob/main/"
        if link.startswith(prefix):
            path = unquote(urlsplit(link[len(prefix) :]).path)
            if not (root / path).is_file():
                errors.append(f"README: missing repository target {path}")
    return errors


if __name__ == "__main__":
    problems = check_documentation()
    for problem in problems:
        print(problem)
    if not problems:
        print("Documentation: matching quickstarts, valid local HTML links and README targets")
    raise SystemExit(bool(problems))
