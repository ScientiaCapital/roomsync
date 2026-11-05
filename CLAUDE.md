# roomsync

@AGENTS.md

AGENTS.md (imported above) has the commands, hard rules, style and map for any assistant. This file adds what
Claude Code needs. If `.claude/context.local.md` exists, read it at session start, but never copy names, device IDs
or dates from it into a tracked file.

## Epiphan tools

- Fleet: the `epiphan` MCP server in `.mcp.json` (tools `mcp__epiphan__*`) or the claude.ai Epiphan connector under
  another name. Read tools are allowed. Every write asks first and names device and channel.
- The sign-in picks one Edge team. Confirm it is your sandbox with `get_devices_in_my_team` before any write. Never
  write to a team other people use without the maintainer's say-so. Don't write its device, room or group names
  into this repo.
- Product facts: the Epiphan Knowledge connector or `kb_search` and `kb_fetch`. If a page doesn't cover it, say so.
- Prose: the Epiphan Brand connector (`get_writing_style`, `check_my_copy`). Product names are Pearl-2,
  Pearl Mini, Pearl Nexus, Pearl Nano, EC20, Epiphan Edge.

## Data model

Team, then Devices (`Id`), then Channels (`channel_id`), then recording status and publishers. A batch channel
address is `<device_id>-<channel_id>`. Third-party video-platform events are read only through the Epiphan MCP
tools. A device follows one video platform at a time (`get_cms_names_for_devices`). `create_cms_event` works only
for devices on Epiphan Edge's own CMS, so it is not the way roomsync schedules for a Panopto room.

## Now

Early. `roomsync recorders` and `roomsync edge-events` exist. Both are read only and tested only with mocks.
Nothing has talked to a real Panopto site. Waiting on Panopto demo credentials. A check the documentation doesn't
settle is reported as `UNVERIFIED`.
