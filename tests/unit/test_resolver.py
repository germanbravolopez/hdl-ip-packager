"""Unit tests for the dependency resolver.

The resolver is pure, so these tests build small in-memory dependency graphs (a
root manifest plus the manifests a registry would offer) and assert the chosen
versions. Coverage spans the happy paths (newest-compatible, transitive, diamond),
the failure modes (conflict, missing package, pre-release exclusion), and the
backtracking that makes newest-first selection complete.
"""

from __future__ import annotations

import pytest

from hdl_ip_packager.exceptions import ResolutionError
from hdl_ip_packager.manifest import Dependency, Manifest
from hdl_ip_packager.resolver import Resolution, resolve
from hdl_ip_packager.version import VersionConstraint
from hdl_ip_packager.vlnv import PackageRef, Vlnv

pytestmark = pytest.mark.unit


def core(vlnv: str, deps: dict[str, str] | None = None) -> Manifest:
    """Build a manifest for *vlnv* with ``{ref: constraint}`` dependencies."""
    dependencies = tuple(
        Dependency(PackageRef.parse(ref), VersionConstraint.parse(spec))
        for ref, spec in (deps or {}).items()
    )
    return Manifest(vlnv=Vlnv.parse(vlnv), dependencies=dependencies)


def available(*manifests: Manifest) -> dict[PackageRef, list[Manifest]]:
    """Group candidate manifests by package, as a registry would expose them."""
    index: dict[PackageRef, list[Manifest]] = {}
    for manifest in manifests:
        index.setdefault(manifest.ref, []).append(manifest)
    return index


def chosen(resolution: Resolution, ref: str) -> str:
    return str(resolution.selected[PackageRef.parse(ref)])


def test_no_dependencies_resolves_to_empty() -> None:
    resolution = resolve(core("acme:lib:top:1.0.0"), {})
    assert dict(resolution.selected) == {}
    assert resolution.vlnvs == ()


def test_picks_newest_compatible() -> None:
    root = core("acme:lib:top:1.0.0", {"acme:lib:a": "^1.0.0"})
    index = available(
        core("acme:lib:a:1.0.0"),
        core("acme:lib:a:1.1.0"),
        core("acme:lib:a:2.0.0"),  # excluded by caret upper bound
    )
    resolution = resolve(root, index)
    assert chosen(resolution, "acme:lib:a") == "acme:lib:a:1.1.0"


def test_transitive_dependency_is_followed() -> None:
    root = core("acme:lib:top:1.0.0", {"acme:lib:a": "^1.0.0"})
    index = available(
        core("acme:lib:a:1.0.0", {"acme:lib:b": "^2.0.0"}),
        core("acme:lib:b:2.3.0"),
        core("acme:lib:b:2.4.0"),
    )
    resolution = resolve(root, index)
    assert chosen(resolution, "acme:lib:a") == "acme:lib:a:1.0.0"
    assert chosen(resolution, "acme:lib:b") == "acme:lib:b:2.4.0"


def test_diamond_intersects_constraints() -> None:
    root = core("acme:lib:top:1.0.0", {"acme:lib:a": "^1.0.0", "acme:lib:b": "^1.0.0"})
    index = available(
        core("acme:lib:a:1.0.0", {"acme:lib:c": "^1.0.0"}),
        core("acme:lib:b:1.0.0", {"acme:lib:c": "^1.2.0"}),
        core("acme:lib:c:1.0.0"),
        core("acme:lib:c:1.2.0"),
        core("acme:lib:c:1.3.0"),  # satisfies >=1.2.0 and <2.0.0 -> newest pick
        core("acme:lib:c:2.0.0"),
    )
    resolution = resolve(root, index)
    assert chosen(resolution, "acme:lib:c") == "acme:lib:c:1.3.0"


def test_conflicting_constraints_raise() -> None:
    root = core("acme:lib:top:1.0.0", {"acme:lib:a": "^1.0.0", "acme:lib:b": "^1.0.0"})
    index = available(
        core("acme:lib:a:1.0.0", {"acme:lib:c": "^1.0.0"}),
        core("acme:lib:b:1.0.0", {"acme:lib:c": "^2.0.0"}),
        core("acme:lib:c:1.5.0"),
        core("acme:lib:c:2.0.0"),
    )
    with pytest.raises(ResolutionError, match="acme:lib:c"):
        resolve(root, index)


def test_missing_package_raises() -> None:
    root = core("acme:lib:top:1.0.0", {"acme:lib:a": "^1.0.0"})
    with pytest.raises(ResolutionError, match="no versions of acme:lib:a"):
        resolve(root, {})


def test_prerelease_excluded_by_default() -> None:
    root = core("acme:lib:top:1.0.0", {"acme:lib:a": "^1.0.0"})
    index = available(core("acme:lib:a:1.0.0-rc.1"))
    with pytest.raises(ResolutionError, match="no version of acme:lib:a"):
        resolve(root, index)


def test_prerelease_allowed_when_targeted() -> None:
    root = core("acme:lib:top:1.0.0", {"acme:lib:a": ">=1.0.0-rc.1,<2.0.0"})
    index = available(core("acme:lib:a:1.0.0-rc.1"))
    resolution = resolve(root, index)
    assert chosen(resolution, "acme:lib:a") == "acme:lib:a:1.0.0-rc.1"


def test_backtracks_to_older_version_when_newest_is_unsatisfiable() -> None:
    # a:1.1.0 needs b ^2 (unavailable); the resolver must fall back to a:1.0.0.
    root = core("acme:lib:top:1.0.0", {"acme:lib:a": "^1.0.0"})
    index = available(
        core("acme:lib:a:1.0.0", {"acme:lib:b": "^1.0.0"}),
        core("acme:lib:a:1.1.0", {"acme:lib:b": "^2.0.0"}),
        core("acme:lib:b:1.0.0"),
    )
    resolution = resolve(root, index)
    assert chosen(resolution, "acme:lib:a") == "acme:lib:a:1.0.0"
    assert chosen(resolution, "acme:lib:b") == "acme:lib:b:1.0.0"


def test_vlnvs_property_is_sorted() -> None:
    root = core("acme:lib:top:1.0.0", {"acme:lib:b": "^1.0.0", "acme:lib:a": "^1.0.0"})
    index = available(core("acme:lib:a:1.0.0"), core("acme:lib:b:1.0.0"))
    resolution = resolve(root, index)
    assert [str(v) for v in resolution.vlnvs] == ["acme:lib:a:1.0.0", "acme:lib:b:1.0.0"]
