# AGENTS.md

Instructions for AI coding assistants (Claude Code, Codex, Cursor and others) working in this repo. Humans:
[README.md](README.md) and the same rules apply.

## What this is

roomsync keeps a school's video-platform schedule (Panopto first), the state of each room's Epiphan device, and the
device's backup recording in agreement. It reads both sides, reports where they disagree, and only creates
platform sessions after a person approves a dry run. Python 3.12, uv, ruff, pytest. Package in `src/roomsync/`.
Epiphan-owned, Apache 2.0, not an officially supported Epiphan product. Status: early. Two read-only commands exist
and nothing writes to a platform.

## Commands

```bash
uv sync --group dev
uv run pytest -q                       # unit tests, no network
bash tests/hook-test.sh                # Edge write guard, redaction, secrets hook, permission rules
uv run ruff check . && uv run ruff format --check .
```

## Hard rules

1. **Read before write, dry run by default.** Every command is read only until a person approves a plan that names
   the room, the time and the effect. `ROOMSYNC_DRY_RUN=1` is the default; creating or changing anything on the
   video platform needs the maintainer's approval in that session. Platform writes are built last.
2. **Platform API: only documented calls and fields.** Use what the platform's published API description and
   Epiphan's kb pages say. Never invent endpoints, fields or behavior; cite the page beside a new call. Epiphan
   product facts come from `kb_search` and `kb_fetch` or the Epiphan Knowledge connector, never from memory.
3. **Epiphan Edge writes need a person.** Never call an Edge write tool without the maintainer's approval in that
   session, naming device, channel and effect. Never weaken `.claude/hooks/epiphan-write-guard.sh`,
   `.claude/hooks/epiphan-redact.sh` or the `permissions` in `.claude/settings.json`. Those hooks are copied from
   the Edge Claude Kit and are fixed there first. Run `get_devices_in_my_team` and confirm the team is your sandbox
   before any write. The Edge team you're signed in to may be one other people use.
4. **Secrets stay in `.env`**, read through one `Settings` class, never `os.environ`. Passwords and client
   secrets are `SecretStr`. No secret, stream key or credentialed URL in code, fixtures, logs or output.
5. **No real data in the repo.** No school, customer, instructor, room or course names, device serials, IPs,
   device IDs, recordings, frames, internal messages, CRM figures or documents in code, fixtures, docs, issues,
   PRs or commit messages. Use placeholders like `TEST-SERIAL-0001` and "Room 204". Real schedules and reports are
   gitignored and stay on the machine they were made on.
6. **Python cannot call MCP tools.** Edge data reaches roomsync as saved JSON. A Claude session reads the Edge
   tools, writes the JSON to the scratchpad (never the repo), runs the roomsync command on it, and deletes the
   file. The commands that take it are read only and say `UNVERIFIED` when the kb does not settle a check.
7. **Async for every network and blocking disk call; type hints on every function.** No network in tests: mock
   `httpx` with a transport.
8. **No OpenAI.** If a model is ever needed: Anthropic direct, or DeepSeek, Qwen or Groq via OpenRouter.
9. **Unannounced hardware is not a spec.** Nothing in code or docs states or depends on specs Product hasn't
   published. Camera and channel counts are data.
10. **Ownership.** Copyright Epiphan Systems Inc. (NOTICE). Keep the trademark line and "not an officially supported
    Epiphan product" wherever licensing is described.
11. **Prose goes through the Epiphan Brand connector.** Call `get_writing_style` before writing README or docs
    prose, and run `check_my_copy` and fix every flag before committing it. Sentence-case headings, no em dashes,
    no bold for emphasis.

## Style

- Conventional Commits with scopes (`feat(platform):`, `docs(readme):`). One concern per PR.
- Work on a branch and open a PR; CI must be green. The PR's Evidence section shows commands you actually ran.
- Plain words in docs. Say what is documented, what is a bench test and what is unknown.
- Main needs a second reviewer. Never merge your own PR without a review, and never push to main.

## Map

| Path | What it does |
|---|---|
| `src/roomsync/` | The package: the settings, the Panopto client, the Edge reader, the comparison, and the command line |
| `.claude/hooks/` | Edge write guard and redaction (from the Edge Claude Kit), secrets hook |
| `.claude/settings.json` | Permissions: reads allowed, writes ask, bypass mode off |
| `tests/hook-test.sh`, `tests/redaction-cases.json` | Hook and permission tests; redaction cases shared with Fleetwatch |
| `.claude/context.local.md` | Local only: your sandbox details. Gitignored |
