"""Unit test: the MkDocs site config stays consistent with the docs tree.

The docs site (``mkdocs.yml`` -> GitHub Pages) builds from ``docs/``. This guards
the cheap-to-break invariant that every page wired into the ``nav`` actually
exists, so renaming or deleting a doc fails here instead of silently breaking the
published site. The full ``mkdocs build`` is exercised by the Docs workflow in CI.

``mkdocs.yml`` is kept free of ``!!python/name:`` tags precisely so ``safe_load``
can parse it here without importing MkDocs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
MKDOCS_YML = REPO_ROOT / "mkdocs.yml"


def _load_config() -> dict[str, object]:
    return yaml.safe_load(MKDOCS_YML.read_text(encoding="utf-8"))


def _nav_files(nav: object) -> list[str]:
    """Flatten an mkdocs ``nav`` tree into the list of referenced doc paths."""
    if isinstance(nav, str):
        return [nav]
    if isinstance(nav, list):
        return [ref for item in nav for ref in _nav_files(item)]
    if isinstance(nav, dict):
        return [ref for value in nav.values() for ref in _nav_files(value)]
    return []


def _docs_dir(config: dict[str, object]) -> Path:
    return REPO_ROOT / str(config.get("docs_dir", "docs"))


def test_mkdocs_config_exists() -> None:
    assert MKDOCS_YML.is_file(), "mkdocs.yml is missing from the repo root"


def test_docs_dir_exists() -> None:
    docs_dir = _docs_dir(_load_config())
    assert docs_dir.is_dir(), f"docs_dir does not exist: {docs_dir}"


def test_every_nav_page_exists() -> None:
    config = _load_config()
    docs_dir = _docs_dir(config)
    refs = _nav_files(config.get("nav", []))
    assert refs, "mkdocs.yml has no nav entries to validate"
    missing = [ref for ref in refs if not (docs_dir / ref).is_file()]
    assert not missing, f"nav references missing docs pages: {missing}"
