"""Smoke tests for the planned subsystems (registry).

These modules are intentionally unimplemented, but they are part of the public
package surface and their interfaces must import cleanly and fail loudly. Testing
that contract now keeps the seams honest and counts them in coverage. (The
resolver is now implemented; its tests live in ``test_resolver.py``.)
"""

from __future__ import annotations

import pytest

from hdl_ip_packager import registry

pytestmark = pytest.mark.unit


def test_registry_is_abstract() -> None:
    # The abstract base cannot be instantiated until a concrete backend exists.
    with pytest.raises(TypeError):
        registry.Registry()  # type: ignore[abstract]
