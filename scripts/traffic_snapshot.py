"""Capture maintainer-only adoption signals; never infer users from downloads.

Requires an authenticated `gh` CLI with repository traffic access. Run manually:
    python scripts/traffic_snapshot.py
Snapshots stay under the git-ignored local.data/metrics directory. No telemetry
is added to pyveil or its examples.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import urllib.request
from pathlib import Path
from typing import Any, Callable

REPO = "hyeonsangjeon/pyveil"
ROOT = Path(__file__).resolve().parent.parent


def github(path: str) -> Any:
    response = subprocess.run(
        ["gh", "api", "repos/" + REPO + path],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if response.returncode:
        raise RuntimeError("GitHub endpoint unavailable; check gh auth and traffic access")
    return json.loads(response.stdout)


def pypi_recent() -> Any:
    request = urllib.request.Request(
        "https://pypistats.org/api/packages/pyveil/recent",
        headers={"User-Agent": "pyveil-maintainer-traffic-snapshot"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def capture(
    get_github: Callable[[str], Any] = github,
    get_downloads: Callable[[], Any] = pypi_recent,
) -> dict[str, Any]:
    sources: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for name, path in (
        ("repository", ""),
        ("views", "/traffic/views"),
        ("clones", "/traffic/clones"),
        ("paths", "/traffic/popular/paths"),
        ("referrers", "/traffic/popular/referrers"),
    ):
        try:
            value = get_github(path)
            if name == "repository":
                value = {
                    key: value[key]
                    for key in ("stargazers_count", "forks_count", "pushed_at", "html_url")
                }
            sources[name] = value
        except Exception as exc:
            # Store only the failure class, never credentials or raw response text.
            errors[name] = type(exc).__name__
    try:
        sources["pypi_recent"] = get_downloads()
    except Exception as exc:
        errors["pypi_recent"] = type(exc).__name__
    return {
        "schema_version": 1,
        "collected_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "repository": REPO,
        "status": "partial" if errors else "complete",
        "sources": sources,
        "errors": errors,
    }


def render(snapshot: dict[str, Any]) -> str:
    sources = snapshot["sources"]
    lines = [
        "# pyveil Traffic Snapshot",
        "",
        "Collected (UTC): " + snapshot["collected_at_utc"],
        "",
        "| Signal | Returned window (UTC) | Count | Unique |",
        "| --- | --- | ---: | ---: |",
    ]
    for name in ("views", "clones"):
        data = sources.get(name)
        if data is None:
            lines.append(f"| GitHub {name} | unavailable | n/a | n/a |")
            continue
        dates = sorted(row["timestamp"][:10] for row in data.get(name, []))
        window = f"{dates[0]} through {dates[-1]}" if dates else "no daily rows returned"
        lines.append(f"| GitHub {name} | {window} | {data['count']} | {data['uniques']} |")
    recent = sources.get("pypi_recent", {}).get("data", {})
    for bucket in ("last_day", "last_week", "last_month"):
        lines.append(
            f"| PyPI {bucket} | upstream rolling bucket | {recent.get(bucket, 'n/a')} | n/a |"
        )
    stars = sources.get("repository", {}).get("stargazers_count", "n/a")
    lines.extend(
        [
            "",
            f"GitHub stars (cumulative at collection): {stars}",
            "",
            "## Interpretation",
            "",
            "- Downloads and clones include repeat/automated activity; neither measures active users.",
            "- Use the returned dates, not an assumed window ending today. Current days may be partial.",
            "- Use API aggregate uniques; summing daily uniques double-counts repeat visitors.",
            "- PyPI recent buckets may lag collection; they cannot be aligned to GitHub dates here.",
            "- Stars are cumulative, not conversions from these views or clones.",
            "- Compare non-overlapping equal windows and record releases/outreach as confounders.",
            "- Missing sources are unavailable, not zero. Empty referrers do not prove no referrals.",
            "- Example runs, activation, retention, and Pages visits are not measured by these APIs.",
        ]
    )
    if snapshot["errors"]:
        lines.extend(["", "Unavailable sources: " + ", ".join(sorted(snapshot["errors"]))])
    return "\n".join(lines) + "\n"


def save(snapshot: dict[str, Any], directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    json_path = directory / (stamp + ".json")
    markdown_path = directory / (stamp + ".md")
    for path, content in (
        (json_path, json.dumps(snapshot, indent=2, sort_keys=True) + "\n"),
        (markdown_path, render(snapshot)),
    ):
        with path.open("x", encoding="utf-8") as output:
            path.chmod(0o600)
            output.write(content)
    return json_path, markdown_path


def main() -> int:
    snapshot = capture()
    paths = save(snapshot, ROOT / "local.data" / "metrics")
    print(render(snapshot))
    for path in paths:
        print(path.relative_to(ROOT))
    return 1 if snapshot["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
