"""Integration test for ``hdlpkg resolve`` end to end on the bundled examples.

The UART example depends on the FIFO example (`acme:common:fifo` ^1.0.0). Resolving
it against the `examples/` tree must discover the FIFO core, write a deterministic
`ip.lock`, and that lockfile must parse back and verify against the manifest digests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hdl_ip_packager import cli
from hdl_ip_packager.lockfile import Lockfile, sha256_digest

pytestmark = pytest.mark.integration

_REPO = Path(__file__).resolve().parents[2]
_EXAMPLES = _REPO / "examples"
_UART = _EXAMPLES / "uart" / "ip.toml"
_FIFO = _EXAMPLES / "fifo" / "ip.toml"


def test_resolve_writes_lockfile_for_examples(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "ip.lock"
    rc = cli.main(["resolve", str(_UART), "--search", str(_EXAMPLES), "--output", str(output)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "acme:common:fifo:1.0.0" in out

    lock = Lockfile.from_path(output)
    locked = {str(p.vlnv): p for p in lock.packages}
    assert "acme:common:fifo:1.0.0" in locked

    fifo = locked["acme:common:fifo:1.0.0"]
    assert fifo.source == "path:examples/fifo"
    # The recorded checksum is the manifest digest, and it verifies.
    assert fifo.checksum == sha256_digest(_FIFO.read_bytes())
    lock.verify({p.vlnv: p.checksum for p in lock.packages})


def test_resolve_is_deterministic() -> None:
    # Running twice yields byte-identical lockfile text.
    from hdl_ip_packager.manifest import Manifest
    from hdl_ip_packager.resolver import resolve

    root = Manifest.from_path(_UART)
    cli_index, sources, checksums = cli._discover_cores([str(_EXAMPLES)], _UART.resolve())
    first = Lockfile.from_resolution(resolve(root, cli_index), sources, checksums).to_toml()
    second = Lockfile.from_resolution(resolve(root, cli_index), sources, checksums).to_toml()
    assert first == second
