"""Verify pyveil's zero-dependency core claim from installed metadata."""

import importlib.metadata as metadata

import pytest

from scripts.verify_zero_dependencies import core_requirements


def test_core_requirements_ignores_extra_gated_requirements():
    declared = [
        "openai>=2.45.0,<3.0.0; python_version >= '3.9' and extra == 'openai'",
        'PyYAML>=6.0.0; extra == "test"',
    ]
    assert core_requirements(declared) == []


def test_core_requirements_flags_unconditional_dependency():
    declared = ["requests>=2.0.0", 'openai>=2.0.0; extra == "openai"']
    assert core_requirements(declared) == ["requests>=2.0.0"]


def test_installed_pyveil_has_zero_core_dependencies():
    try:
        declared = metadata.requires("pyveil") or []
    except metadata.PackageNotFoundError:
        pytest.skip("pyveil is not installed in this environment")
    assert core_requirements(declared) == []
