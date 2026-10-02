import json
from pathlib import Path
from typing import Any

from scripts.traffic_snapshot import capture, render, save


def source(path: str) -> Any:
    if not path:
        return {
            "stargazers_count": 3,
            "forks_count": 0,
            "pushed_at": "2026-09-10",
            "html_url": "https://github.com/hyeonsangjeon/pyveil",
            "ignored": "unused",
        }
    if path.endswith(("paths", "referrers")):
        return []
    name = path.rsplit("/", 1)[1]
    return {
        "count": 8,
        "uniques": 2,
        name: [
            {"timestamp": "2026-09-01T00:00:00Z", "count": 4, "uniques": 2},
            {"timestamp": "2026-09-02T00:00:00Z", "count": 4, "uniques": 2},
        ],
    }


def downloads() -> Any:
    return {"data": {"last_day": 1, "last_week": 4, "last_month": 10}}


def test_snapshot_preserves_aggregate_uniques_and_actual_dates() -> None:
    snapshot = capture(source, downloads)
    assert snapshot["status"] == "complete"
    assert snapshot["sources"]["clones"]["uniques"] == 2
    assert "ignored" not in snapshot["sources"]["repository"]
    report = render(snapshot)
    assert "2026-09-01 through 2026-09-02 | 8 | 2" in report
    assert "upstream rolling bucket | 10 | n/a" in report
    assert "neither measures active users" in report


def test_failures_are_unavailable_not_zero_and_do_not_leak_errors() -> None:
    def failure(*args: Any) -> Any:
        raise RuntimeError("synthetic-private-auth-detail")

    snapshot = capture(failure, failure)
    assert snapshot["status"] == "partial"
    assert len(snapshot["errors"]) == 6
    assert "synthetic-private-auth-detail" not in json.dumps(snapshot)
    report = render(snapshot)
    assert "unavailable | n/a | n/a" in report
    assert "upstream rolling bucket | n/a | n/a" in report


def test_partial_results_preserve_available_sources() -> None:
    def partial(path: str) -> Any:
        if path.endswith("views"):
            raise TimeoutError()
        return source(path)

    snapshot = capture(partial, downloads)
    assert snapshot["errors"] == {"views": "TimeoutError"}
    assert "GitHub clones | 2026-09-01 through 2026-09-02 | 8 | 2" in render(snapshot)


def test_snapshots_do_not_overwrite_previous_observations(tmp_path: Path) -> None:
    snapshot = capture(source, downloads)
    first = save(snapshot, tmp_path)
    second = save(snapshot, tmp_path)
    assert first != second
    assert json.loads(first[0].read_text(encoding="utf-8")) == snapshot
    assert first[1].read_text(encoding="utf-8") == render(snapshot)
