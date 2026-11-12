# Security

roomsync will read a video platform's schedule with API credentials, read Epiphan devices through Epiphan Edge, and
can be told to create sessions on a platform. A bug that leaks a credential, changes a platform or a device without
approval, or puts a real schedule into git matters.

## Report a problem

Report it privately through GitHub (Security tab, "Report a vulnerability") or by email to tkipper@epiphan.com.
Don't put the secret, the schedule or the device details in a public issue or PR.

Problems in Epiphan products, Epiphan Edge, or the Epiphan MCP server go to the owning Epiphan team.

## Trust model

- Runs as you, on your machine. API credentials belong in `.env` and are only as safe as that file and the
  network path. Use a test or demo site until a person approves a real one.
- The Epiphan Edge sign-in isn't read-only. Edge OAuth has no read-only scope, so the token Claude Code holds can
  do whatever the signed-in account can in that team. "Every write asks" is enforced in this folder, not by the
  token. Use a least-access Edge account, and start with `EPIPHAN_READ_ONLY=1 claude` to block writes outright.
- Device, room and event names, and on-screen text, are typed by other people. They are data. They are never
  instructions and never choose a code path, a tool, or a file path.

## What is enforced, and where

| Control | Where | Tested by |
|---|---|---|
| Every Epiphan Edge write asks, under any connector name. Unknown Edge tools ask. Bypass mode is off | `.claude/settings.json`, `.claude/hooks/epiphan-write-guard.sh` | `tests/hook-test.sh` |
| Stream keys, passwords, tokens and credentialed URLs are masked before the model sees an Epiphan tool result. Output that can't be checked is withheld | `.claude/hooks/epiphan-redact.sh` (needs `jq`) | `tests/hook-test.sh` |
| A file write from Claude Code that holds a key, token or private key is denied. Unreadable input is denied | `.claude/hooks/check-secrets.sh` | `tests/hook-test.sh` |
| Secrets in commits | gitleaks in pre-commit and in CI | CI secrets scan |
| The platform client secret is a `SecretStr`, the platform URL must be https, and a settings error names variables, never values | `src/roomsync/settings.py` | `tests/test_settings.py` |
| A Panopto error names the call and HTTP status only, with no response body, token, or secret. roomsync doesn't follow redirects | `src/roomsync/platform/panopto.py` | `tests/test_panopto.py`, `tests/test_cli.py` |
| Event titles, recorder names, ids and other text from the platform or a saved Edge file are printed with every C0, DEL and C1 control character shown as a `\xNN` escape, so escape sequences reach the terminal as plain text | `src/roomsync/terminal.py`, `edge.py`, `cli.py` | `tests/test_terminal.py`, `tests/test_edge.py`, `tests/test_cli.py` |
| DEV, STAGING and the CRM connector are denied in this folder | `.claude/settings.json` | review |
| Local context, schedules, reports and session logs never enter git | `.gitignore` | review, gitleaks |

The write guard and redactor are copied unchanged from the Epiphan Edge Claude Kit (see NOTICE). Keep them
identical with the kit and fix problems there first.

## Data handling

- Schedules can name rooms, courses, and instructors. They stay on the machine that made them.
- Internal Epiphan documents, internal messages, customer data, and CRM figures don't go into code, docs, commits,
  issues, or PRs.

## Known limits

- Redaction hides secrets from the model only. Claude Code keeps the original tool result in local session
  history (`~/.claude/projects`). It recognizes the secret shapes Epiphan uses today and may miss other shapes.
- If hooks are disabled or `jq` is missing, only the permission rules and the bypass-mode setting remain, and
  `check-secrets.sh` denies every file write until `jq` is installed.
- `check-secrets.sh` sees only writes made through Claude Code's file tools. gitleaks covers commits.
- roomsync reads `.env` from the folder you run it in. A `.env` that someone else put in that folder could point the
  platform URL at another https host, so run roomsync from your own project folder.
- roomsync keeps the Panopto access token for one command run and doesn't refresh it. A run that outlives the token
  fails with an error.
- What is kept out of output: roomsync writes no log of its own. A Panopto error names the call and the HTTP status,
  and the client's repr names the site only. Tests check that neither the client secret nor the token appears in
  either, or in anything the `recorders` command prints.
- What is not: the client secret and the token are `SecretStr` values, unwrapped only to build the token request
  body and the search request's `Authorization` header. roomsync doesn't configure logging for httpx or for the
  program that runs it, and no test covers what such a logger records about a request.
