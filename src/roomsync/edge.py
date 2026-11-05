"""Reads saved Epiphan Edge MCP JSON into roomsync models.

Python cannot call MCP tools (AGENTS.md rule 6). A Claude session reads the Edge tools, saves the JSON to its
scratchpad, and roomsync parses that file here. Everything in this module is read only.

What is known and what is not, as of the first sandbox read:

- Only event `status: "scheduled"` has been observed. The kb does not define the status vocabulary or what
  `confirmed` means, so any other status is reported as unverified.
- Only channel `recording_status.state: "stopped"` has been observed. The value that means "recording" is unknown.
- Event ids are occurrence ids (`"<event>:<unix start>"`), not video-platform session ids.
- Edge reads third-party platform events but cannot change them.
"""

import asyncio
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator

from roomsync.models import ScheduledSession, Source

KNOWN_EVENT_STATUSES: frozenset[str] = frozenset({"scheduled"})
"""Event statuses seen on a device. The kb does not list the full set."""

STOPPED_STATE = "stopped"
"""The only `recording_status.state` seen on a device. The state that means "recording" is unknown."""


class EdgeEvent(BaseModel):
    """One CMS event occurrence as an Edge tool returns it.

    `id` is an occurrence id (`"<event>:<unix start>"`), not a platform session id. `confirmed` is passed through
    as read; the kb does not define it. Unknown fields are ignored because the Edge output may grow.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: str
    title: str
    cms: str
    status: str
    confirmed: bool | None = None
    start: AwareDatetime
    finish: AwareDatetime
    device_ids: tuple[str, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def _device_ids_from_devices(cls, data: Any) -> Any:
        if isinstance(data, dict) and "device_ids" not in data and isinstance(data.get("devices"), list):
            ids = tuple(d["device_id"] for d in data["devices"] if isinstance(d, dict) and "device_id" in d)
            data = {**data, "device_ids": ids}
        return data

    @property
    def status_verified(self) -> bool:
        """True only for statuses seen on a device. Anything else is reported as UNVERIFIED."""
        return self.status in KNOWN_EVENT_STATUSES


def to_sessions(event: EdgeEvent) -> list[ScheduledSession]:
    """One ScheduledSession per device the event runs on. The session id is the Edge occurrence id."""
    return [
        ScheduledSession(
            id=event.id,
            name=event.title,
            start=event.start,
            end=event.finish,
            recorder_id=device_id,
            source=Source.EDGE,
        )
        for device_id in event.device_ids
    ]


def _shape_error(data: object, expected: str) -> ValueError:
    """Unknown input is a bad value for roomsync, so this is a ValueError even when the cause is a wrong type."""
    found = sorted(data) if isinstance(data, dict) else type(data).__name__
    return ValueError(f"Not a known Edge {expected} shape (expected {{{expected!r}: [...]}}, found {found})")


def _entry_error(expected: str, problem: str) -> ValueError:
    return ValueError(f"Not a known Edge {expected} shape: {problem}")


def parse_events(data: object) -> list[EdgeEvent]:
    """Parse saved output of the Edge CMS event tools, deduped by occurrence id in first-seen order.

    Accepts `get_cms_events_for_device` (`{"cms": ..., "events": [event, ...]}`), `get_cms_events_for_devices`
    (`{"events": [event, ...]}`) and `get_current_or_next_cms_events_for_devices`
    (`{"events": [{"device_id": ..., "event": event | null}, ...]}`). Raises ValueError for any other shape and
    pydantic's ValidationError (a ValueError) for a bad event, including a timestamp without a time zone.
    """
    if not isinstance(data, dict) or not isinstance(data.get("events"), list):
        raise _shape_error(data, "events")
    events: dict[str, EdgeEvent] = {}
    for entry in data["events"]:
        if not isinstance(entry, dict):
            raise _entry_error("events", f"entry is {type(entry).__name__}, not an object")
        if "event" in entry and "id" not in entry:
            entry = entry["event"]
            if entry is None:
                continue
        event = EdgeEvent.model_validate(entry)
        events.setdefault(event.id, event)
    return list(events.values())


def parse_recording_devices(data: object) -> tuple[frozenset[str], bool]:
    """From saved `get_devices_in_my_team` output, the devices with any channel not in the "stopped" state.

    Returns `(device_ids, verified)`. `verified` is False whenever a state other than "stopped" was seen, because
    the value that means "recording" is unknown. Channels without `recording_status` are ignored.
    """
    if not isinstance(data, dict) or not isinstance(data.get("devices"), list):
        raise _shape_error(data, "devices")
    recording: set[str] = set()
    for device in data["devices"]:
        if not isinstance(device, dict) or not isinstance(device.get("Id"), str):
            raise _entry_error("devices", "device entry has no string 'Id'")
        for channel in device.get("Channels") or []:
            status = channel.get("recording_status") if isinstance(channel, dict) else None
            state = status.get("state") if isinstance(status, dict) else None
            if state is not None and state != STOPPED_STATE:
                recording.add(device["Id"])
    return frozenset(recording), not recording


async def load_json(path: Path) -> object:
    """Read a saved Edge tool result. Malformed JSON raises ValueError naming the file."""
    text = await asyncio.to_thread(path.read_text, encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M")


def format_events(events: Sequence[EdgeEvent]) -> str:
    """A plain table, one row per event and device, times in UTC. Unknown statuses are marked UNVERIFIED."""
    if not events:
        return "No Edge events in this file."
    header = ("start UTC", "finish UTC", "device", "cms", "status", "title")
    rows = [
        (
            _utc(e.start),
            _utc(e.finish),
            device_id,
            e.cms,
            e.status if e.status_verified else f"{e.status} (UNVERIFIED status)",
            e.title,
        )
        for e in events
        for device_id in (e.device_ids or ("-",))
    ]
    widths = [max(len(row[i]) for row in (header, *rows)) for i in range(len(header) - 1)]
    return "\n".join(
        "  ".join([*(cell.ljust(w) for cell, w in zip(row[:-1], widths, strict=True)), row[-1]])
        for row in (header, *rows)
    )
