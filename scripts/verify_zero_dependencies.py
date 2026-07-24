"""Reproducibly verify that pyveil's core has zero runtime dependencies.

pyveil advertises a standard-library-only core. Optional provider extras
(``openai``, ``anthropic``, ``ollama``, ``azure-openai``, ``dev``, ``test``)
add third-party packages, but installing ``pyveil`` alone must pull in nothing.

This reads the installed package metadata and confirms every declared
requirement is guarded by an ``extra`` marker, so none is an unconditional
core dependency. It uses only the standard library.

Usage::

    python scripts/verify_zero_dependencies.py
"""

from __future__ import annotations

import importlib.metadata as metadata
import sys


def core_requirements(requirements: list[str]) -> list[str]:
    """Return declared requirements that are NOT gated behind an extra.

    A requirement string may carry an environment marker after ``;`` such as
    ``python_version >= "3.9" and extra == "openai"``. Anything without an
    ``extra`` marker would install unconditionally with the core package.
    """

    core: list[str] = []
    for requirement in requirements:
        marker = requirement.split(";", 1)[1] if ";" in requirement else ""
        if "extra" not in marker:
            core.append(requirement.strip())
    return core


def main() -> int:
    try:
        declared = metadata.requires("pyveil") or []
    except metadata.PackageNotFoundError:
        print("pyveil is not installed; run 'python -m pip install -e .' first")
        return 2

    core = core_requirements(declared)
    if core:
        print("zero-dependency check failed: unconditional core requirements found:")
        for requirement in core:
            print(f"  - {requirement}")
        return 1

    extras = len(declared)
    print(
        f"zero-dependency core verified: 0 runtime dependencies "
        f"({extras} optional requirement(s) all gated behind extras)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
