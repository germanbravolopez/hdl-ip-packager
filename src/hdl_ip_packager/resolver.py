"""Dependency resolution.

The resolver turns a root :class:`~hdl_ip_packager.manifest.Manifest` plus the set
of available core versions into a concrete, reproducible solution: one chosen
:class:`~hdl_ip_packager.vlnv.Vlnv` per package that satisfies every constraint.
The solution is what gets written to the lockfile (``ip.lock``).

Design (see ``docs/architecture.md`` and ``docs/research/state_of_the_art.md``):

* **Single version per package**, fail-on-conflict -- HDL elaboration cannot host
  two versions of the same module, unlike npm's nesting.
* **Newest-compatible** selection: among the versions satisfying every accumulated
  constraint, prefer the highest. Pre-releases are excluded unless a constraint's
  operand is itself a pre-release of the same ``MAJOR.MINOR.PATCH`` (the rule
  already enforced by :meth:`VersionConstraint.matches`).
* **Backtracking search** over the candidate sets: choosing the newest version can
  make a transitive constraint unsatisfiable, so the search falls back to older
  versions before giving up. The graphs are small today; this can be lowered to a
  SAT/CDCL solver later without changing the public contract.
* **Pure**: the available versions are passed in (the registry/cache layer fetches
  them), so the solve does no I/O and is deterministic.

``available`` maps each package to the *manifests* of its known versions -- not
just the version numbers -- because a candidate's own ``[dependencies]`` drive the
transitive solve.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .exceptions import ResolutionError
from .manifest import Manifest
from .version import VersionConstraint
from .vlnv import PackageRef, Vlnv

__all__ = ["Resolution", "resolve"]


@dataclass(frozen=True)
class Resolution:
    """The result of a successful resolve: one concrete version per package."""

    selected: Mapping[PackageRef, Vlnv]

    @property
    def vlnvs(self) -> tuple[Vlnv, ...]:
        """The selected VLNVs in a deterministic (sorted) order."""
        return tuple(sorted(self.selected.values(), key=str))


def resolve(
    root: Manifest,
    available: Mapping[PackageRef, Sequence[Manifest]],
) -> Resolution:
    """Resolve *root*'s dependency graph against the *available* versions.

    Args:
        root: the top-level manifest whose dependencies drive the solve.
        available: for each package, the manifests of the versions a registry/cache
            offers. Each candidate's own dependencies are followed transitively.

    Returns:
        A :class:`Resolution` mapping every required package to one chosen VLNV.

    Raises:
        ResolutionError: if no assignment satisfies all constraints.
    """
    index: dict[PackageRef, list[Manifest]] = {
        ref: sorted(manifests, key=lambda m: m.vlnv.version, reverse=True)
        for ref, manifests in available.items()
    }
    initial: dict[PackageRef, list[VersionConstraint]] = {}
    for dep in root.dependencies:
        initial.setdefault(dep.ref, []).append(dep.constraint)

    failures: list[str] = []
    solution = _solve(initial, {}, index, failures)
    if solution is None:
        detail = failures[-1] if failures else "the constraints cannot be satisfied"
        raise ResolutionError(f"Could not resolve dependencies: {detail}.")
    return Resolution(selected={ref: manifest.vlnv for ref, manifest in solution.items()})


def _solve(
    constraints: dict[PackageRef, list[VersionConstraint]],
    assignment: dict[PackageRef, Manifest],
    index: dict[PackageRef, list[Manifest]],
    failures: list[str],
) -> dict[PackageRef, Manifest] | None:
    """Backtracking core. Return a complete assignment, or None on failure."""
    pending = sorted((ref for ref in constraints if ref not in assignment), key=str)
    if not pending:
        return dict(assignment)

    pkg = pending[0]
    pkg_constraints = constraints[pkg]
    candidates = index.get(pkg)
    if not candidates:
        failures.append(f"no versions of {pkg} are available")
        return None

    viable = [m for m in candidates if all(c.matches(m.vlnv.version) for c in pkg_constraints)]
    if not viable:
        wanted = ", ".join(str(c) for c in pkg_constraints)
        have = ", ".join(str(m.vlnv.version) for m in candidates)
        failures.append(f"no version of {pkg} satisfies {wanted} (available: {have})")
        return None

    for manifest in viable:  # candidates are pre-sorted newest-first
        next_assignment = {**assignment, pkg: manifest}
        next_constraints, conflict = _extend(constraints, manifest, next_assignment)
        if conflict is not None:
            failures.append(conflict)
            continue
        result = _solve(next_constraints, next_assignment, index, failures)
        if result is not None:
            return result
    return None


def _extend(
    constraints: dict[PackageRef, list[VersionConstraint]],
    manifest: Manifest,
    assignment: dict[PackageRef, Manifest],
) -> tuple[dict[PackageRef, list[VersionConstraint]], str | None]:
    """Add *manifest*'s dependencies as constraints; report a conflict with an
    already-chosen version if one is introduced."""
    extended = {ref: list(clauses) for ref, clauses in constraints.items()}
    for dep in manifest.dependencies:
        extended.setdefault(dep.ref, []).append(dep.constraint)
        chosen = assignment.get(dep.ref)
        if chosen is not None and not dep.constraint.matches(chosen.vlnv.version):
            conflict = (
                f"{manifest.vlnv} requires {dep.ref} {dep.constraint}, "
                f"but {chosen.vlnv.version} is already selected"
            )
            return extended, conflict
    return extended, None
