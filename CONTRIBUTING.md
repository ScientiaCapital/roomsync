# Contributing

roomsync is a small Epiphan project. Contributions that keep it honest (documented facts only), safe (every change
to a video platform or a device approved by a person) and small are the most welcome.

## What helps most

1. Facts about the video platform's API, quoted from its published description, with the page or file cited.
2. A read-only command that lists recorders and scheduled sessions.
3. Checks that compare the platform's schedule with a device's real state.
4. Anything else: open an issue first for anything large.

## Set up

```bash
uv sync --group dev
uv run pytest -q
bash tests/hook-test.sh
uvx pre-commit install      # runs gitleaks, ruff, shellcheck, actionlint and zizmor on every commit
```

Most of the code can be worked on without a device or a platform account. Tests mock `httpx` and make no network
calls. For real work, copy `.env.example` to `.env` and use a test or demo site, never a school's live one.

## Rules

1. Documented facts only. Platform and Epiphan behavior comes from the platform's published API description and
   kb.epiphan.com, cited beside the code. If the docs don't cover it, it's a bench test or an open question.
2. Changes need a person. Creating or changing anything on a video platform or an Epiphan device needs approval
   that names the room, the time and the effect. Dry run is the default. Don't weaken the Edge write guard, the
   redaction hook or the permissions in `.claude/settings.json`. They come from the Epiphan Edge Claude Kit, so
   change them there first.
3. No real data. No school, instructor, room or course names, device serials, IPs, recordings, internal messages,
   customer data or CRM figures in code, fixtures, issues or PRs. Use placeholders.
4. Secrets in `.env` only, read through one `Settings` class. gitleaks runs in pre-commit and CI.
5. Code style: Python 3.12+, async for all I/O, type hints on every function, `ruff` clean, no OpenAI.
6. Prose: sentence-case headings, no em dashes, no bold for emphasis. Run the Epiphan Brand check on READMEs and docs.

## Commits and pull requests

- Use [Conventional Commits](https://www.conventionalcommits.org/) with a scope: `feat(platform): ...`,
  `docs(readme): ...`, `ci: ...`, `test(hooks): ...`.
- One concern per PR, from a branch. Fill in the Evidence section of the PR template with commands you ran and
  what they printed. CI must be green: lint, tests on Linux and macOS, the hook tests, and the secrets scan.
- Main needs a second reviewer.

## Using an AI assistant

Fine and welcome. Point it at [AGENTS.md](AGENTS.md). You are responsible for every line you submit.

## Security issues

See [SECURITY.md](SECURITY.md). Contributions are made as Epiphan work, belong to Epiphan Systems Inc., and are
licensed under the Apache License 2.0 (see [LICENSE](LICENSE)).
