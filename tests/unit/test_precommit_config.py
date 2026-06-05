"""Integrity test for ``.pre-commit-config.yaml``.

The pre-commit config is dev infrastructure, not shipped code, but a typo there
silently disables the local gates. This test parses it and asserts the hooks that
mirror CI (ruff lint, ruff-format, mypy) are present, so an accidental removal or
malformed YAML fails fast -- the same guard the docs-site test gives ``mkdocs.yml``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

CONFIG_PATH = Path(__file__).resolve().parents[2] / ".pre-commit-config.yaml"


def _hook_ids() -> set[str]:
    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    return {hook["id"] for repo in data["repos"] for hook in repo["hooks"]}


def test_config_exists_and_parses() -> None:
    assert CONFIG_PATH.is_file(), f"{CONFIG_PATH} is missing"


def test_ci_mirroring_hooks_are_present() -> None:
    ids = _hook_ids()
    for required in ("ruff", "ruff-format", "mypy"):
        assert required in ids, f"pre-commit config is missing the '{required}' hook"
