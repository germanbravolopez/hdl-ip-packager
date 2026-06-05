"""Unit tests for the starter-manifest scaffolder (``scaffold.py``).

The renderer is pure, so these tests call it directly and assert two things: the
rendered text round-trips through :class:`Manifest` (a scaffolded core is always
valid), and identity/version validation fails loudly on bad input.
"""

from __future__ import annotations

import pytest

from hdl_ip_packager.exceptions import InvalidVersionError, InvalidVlnvError
from hdl_ip_packager.manifest import Manifest
from hdl_ip_packager.scaffold import DEFAULT_VERSION, ScaffoldOptions, render_manifest
from hdl_ip_packager.version import Version

pytestmark = pytest.mark.unit


def test_rendered_manifest_round_trips() -> None:
    options = ScaffoldOptions.create("acme", "common", "fifo")
    manifest = Manifest.from_str(render_manifest(options))
    assert str(manifest.vlnv) == "acme:common:fifo:0.1.0"
    assert manifest.top == "fifo"
    assert "rtl" in manifest.filesets
    assert manifest.filesets["rtl"].files == ("rtl/fifo.sv",)
    assert manifest.targets["sim"].toolflow == "verilator"


def test_default_version_is_used() -> None:
    options = ScaffoldOptions.create("acme", "common", "fifo")
    assert options.version == Version.parse(DEFAULT_VERSION)


def test_top_defaults_to_name_but_is_overridable() -> None:
    assert ScaffoldOptions.create("a", "b", "core").effective_top == "core"
    assert ScaffoldOptions.create("a", "b", "core", top="core_top").effective_top == "core_top"
    options = ScaffoldOptions.create("a", "b", "core", top="wrap")
    manifest = Manifest.from_str(render_manifest(options))
    assert manifest.top == "wrap"
    assert manifest.targets["sim"].top == "wrap"


def test_metadata_is_rendered_and_escaped() -> None:
    options = ScaffoldOptions.create(
        "acme", "common", "fifo", description='a "fast" fifo', license="Apache-2.0"
    )
    manifest = Manifest.from_str(render_manifest(options))
    assert manifest.description == 'a "fast" fifo'
    assert manifest.license == "Apache-2.0"


def test_invalid_segment_raises() -> None:
    with pytest.raises(InvalidVlnvError):
        ScaffoldOptions.create("acme", "common", "bad name")


def test_invalid_version_raises() -> None:
    with pytest.raises(InvalidVersionError):
        ScaffoldOptions.create("acme", "common", "fifo", version="not-a-version")
