# HDL IP Packager — Claude Code Instructions

**Before starting any task**, read [docs/ai_agent_instructions.md](docs/ai_agent_instructions.md)
in full. It is the project briefing: status, file map, coding + testability rules,
and your obligations as an agent.

Quick links:
- [docs/ai_agent_instructions.md](docs/ai_agent_instructions.md) — start here
- [docs/progress_tracker.md](docs/progress_tracker.md) — status + the ordered roadmap (read before working)
- [docs/architecture.md](docs/architecture.md) — module map, data model, subsystem designs
- [docs/research/state_of_the_art.md](docs/research/state_of_the_art.md) — why the design is what it is
- [docs/INDEX.md](docs/INDEX.md) — find any file, concept, or topic
- [.claude/commands/](.claude/commands/) — slash commands (`/coding-guidelines`, `/update-docs`, `/tackle-issue`, `/release`)

## After completing any task

1. Make the quality gates green: `pytest`, `ruff check .`, `ruff format --check .`, `mypy`.
2. Run `/update-docs` (or follow its checklist) to keep the docs current — at
   minimum `docs/progress_tracker.md`, plus `architecture.md`/`INDEX.md`/`README.md`
   when relevant.

## Coding rules (summary — full version in the docs)

- **Python 3.11+**, PEP 8 via `ruff format` (line length 100). English everywhere.
- **Types mandatory** on `src/` (mypy `--strict`). Model data as
  `@dataclass(frozen=True)` with `parse`/`from_*` classmethods.
- **Purity by default**: keep logic free of I/O; do filesystem/network only in the
  CLI and registry layers. This is the testability rule — see
  [.claude/commands/coding-guidelines.md](.claude/commands/coding-guidelines.md).
- **Every behaviour ships with tests** in the same change, covering error paths.
- **Errors** derive from `HdlPackagerError`; never `print` errors in library code.
- **No emojis** in docs/headings (the test-report icons in `scripts/` are the one
  intentional exception).

## Branch & merge workflow

`main` is governed by the repository ruleset named **"main"**: **never commit or
push directly to `main`** (no force-push, no deletion either). Branch off `main`
(`feature/`, `fix/`, `docs/`, or `release/X.Y.Z`), push, and open a PR. Every change
reaches `main` as a **merge commit** (squash/rebase disabled).

**The agent gates and merges its own PRs.** After CI is green, **review the PR with
`/code-review`**, resolve or file every finding (fix it on the branch, or record it
in `docs/progress_tracker.md` Open Non-Blocking Issues), then merge it with a merge
commit — `gh pr merge --merge --admin` (GitHub forbids self-approval, so `--admin`
satisfies the ruleset's required-review check and logs the bypass). Releases tag the
merged commit on `main`.

**Defer to a human gate only when the agent cannot safely decide on its own** — e.g.
the `1.0.0` stability sign-off, a security-sensitive or hard-to-reverse change beyond
a routine publish, or anything the user has explicitly reserved. In those cases,
prepare the branch + PR and stop. Full detail in
[docs/ai_agent_instructions.md](docs/ai_agent_instructions.md) and the `/release`
and `/tackle-issue` commands.

## Shell preference

Default to the **Bash** tool for `git`, file inspection, and general commands —
it handles UTF-8 cleanly on this machine. Use the **PowerShell** tool when a task
is Windows-specific (e.g. exercising `.ps1`, or reproducing a Windows-only path).

Note: `python` is the interpreter on PATH (Python 3.11). The `hdlpkg` script may
not be on PATH after `pip install -e` — use `python -m hdl_ip_packager …` if so.

## Things to watch on this machine

- `os.chdir` into a `%TEMP%` directory can fail with **WinError 5 (Access is
  denied)** due to Controlled Folder Access / AV. Tests that need a working
  directory skip gracefully; avoid relying on `chdir` into temp in new tests.
