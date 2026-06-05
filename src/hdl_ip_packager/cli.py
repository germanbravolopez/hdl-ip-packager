"""Command-line interface for the HDL IP Packager (``hdlpkg``).

The CLI is intentionally thin: it parses arguments and delegates to library
functions, so every behaviour stays unit-testable without spawning a process.
Only the commands backed by implemented modules do real work today; the rest
print a clear "not yet implemented" notice and point at the roadmap. The full
intended command set is documented here and in ``docs/architecture.md`` so the
surface is stable as features land.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .exceptions import HdlPackagerError, ManifestError
from .manifest import MANIFEST_FILENAME, Manifest
from .scaffold import DEFAULT_VERSION, ScaffoldOptions, render_manifest

# Commands that have a real implementation today. Everything else is a planned
# stub (see docs/progress_tracker.md) and reports as much instead of pretending.
_PLANNED = {
    "add": "add a dependency to ip.toml",
    "resolve": "resolve dependencies and write the lockfile (ip.lock)",
    "install": "resolve + fetch dependencies into the local cache",
    "pack": "package this core into a distributable .ipkg artifact",
    "publish": "publish this core to a registry",
    "pull": "download a core from a registry by VLNV",
    "gen": "generate tool/back-end files (EDAM) for a target",
    "export-ipxact": "export an IP-XACT (IEEE 1685) description for tool interop",
}


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser (kept separate so tests can use it)."""
    parser = argparse.ArgumentParser(
        prog="hdlpkg",
        description="HDL IP Packager - package, version, and resolve HDL IP cores.",
    )
    parser.add_argument("--version", action="version", version=f"hdlpkg {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p_info = sub.add_parser("info", help="show metadata parsed from a manifest")
    p_info.add_argument(
        "path",
        nargs="?",
        default=MANIFEST_FILENAME,
        help=f"path to the manifest (default: ./{MANIFEST_FILENAME})",
    )
    p_info.set_defaults(func=_cmd_info)

    p_validate = sub.add_parser("validate", help="parse and validate a manifest")
    p_validate.add_argument("path", nargs="?", default=MANIFEST_FILENAME)
    p_validate.set_defaults(func=_cmd_validate)

    p_init = sub.add_parser("init", help=f"scaffold a starter {MANIFEST_FILENAME}")
    p_init.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="directory to create the manifest in (default: current directory)",
    )
    p_init.add_argument("--vendor", help="VLNV vendor segment")
    p_init.add_argument("--library", help="VLNV library segment")
    p_init.add_argument("--name", help="VLNV name segment")
    p_init.add_argument(
        "--version", default=DEFAULT_VERSION, help=f"SemVer (default: {DEFAULT_VERSION})"
    )
    p_init.add_argument("--description", default="", help="short core description")
    p_init.add_argument("--license", default="", help="SPDX license identifier")
    p_init.add_argument("--top", help="top-level unit (default: the core name)")
    p_init.add_argument(
        "--force", action="store_true", help=f"overwrite an existing {MANIFEST_FILENAME}"
    )
    p_init.set_defaults(func=_cmd_init)

    for name, help_text in _PLANNED.items():
        p = sub.add_parser(name, help=f"[planned] {help_text}")
        p.set_defaults(func=_cmd_planned, command_name=name)

    return parser


def _load(path: str) -> Manifest:
    return Manifest.from_path(Path(path))


def _cmd_info(args: argparse.Namespace) -> int:
    manifest = _load(args.path)
    print(f"VLNV       : {manifest.vlnv}")
    if manifest.description:
        print(f"Description: {manifest.description}")
    if manifest.license:
        print(f"License    : {manifest.license}")
    if manifest.dependencies:
        print("Dependencies:")
        for dep in manifest.dependencies:
            print(f"  - {dep}")
    if manifest.filesets:
        print(f"Filesets   : {', '.join(sorted(manifest.filesets))}")
    if manifest.targets:
        print(f"Targets    : {', '.join(sorted(manifest.targets))}")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    manifest = _load(args.path)
    print(f"OK: {manifest.vlnv} is a valid manifest.")
    return 0


def _require_field(value: str | None, label: str, interactive: bool) -> str:
    """Return *value*, prompting for it when interactive, else raise."""
    if value:
        return value
    if interactive:
        entered = input(f"{label}: ").strip()
        if entered:
            return entered
    raise ManifestError(f"Missing required field '{label}'; pass --{label} or run interactively.")


def _cmd_init(args: argparse.Namespace) -> int:
    target_dir = Path(args.directory)
    manifest_path = target_dir / MANIFEST_FILENAME
    if manifest_path.exists() and not args.force:
        print(
            f"error: {manifest_path} already exists; pass --force to overwrite.",
            file=sys.stderr,
        )
        return 1

    interactive = sys.stdin.isatty()
    options = ScaffoldOptions.create(
        vendor=_require_field(args.vendor, "vendor", interactive),
        library=_require_field(args.library, "library", interactive),
        name=_require_field(args.name, "name", interactive),
        version=args.version,
        description=args.description,
        license=args.license,
        top=args.top,
    )

    target_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(render_manifest(options), encoding="utf-8")
    vlnv = options.vlnv
    print(f"Created {manifest_path} for {vlnv}")
    return 0


def _cmd_planned(args: argparse.Namespace) -> int:
    name = args.command_name
    print(
        f"'hdlpkg {name}' is planned but not implemented yet: {_PLANNED[name]}.\n"
        f"See docs/progress_tracker.md for the roadmap.",
        file=sys.stderr,
    )
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns a process exit code (0 = success)."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    try:
        return int(args.func(args))
    except HdlPackagerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
