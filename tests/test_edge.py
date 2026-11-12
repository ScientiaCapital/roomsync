import asyncio
import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from roomsync.edge import (
    KNOWN_EVENT_STATUSES,
    EdgeEvent,
    format_events,
    load_json,
    parse_events,
    parse_recording_devices,
    to_sessions,
)
from roomsync.models import ScheduledSession, Source

FIXTURES = Path(__file__).parent / "fixtures" / "edge"
EVENT_ID = "test-event-0001:1767225600"


def fixture(name: str) -> object:
    return json.loads((FIXTURES / name).read_text())


def raw_event(**overrides: object) -> dict[str, object]:
    data = fixture("events_for_device.json")
    assert isinstance(data, dict)
    event: dict[str, object] = copy.deepcopy(data["events"][0])
    event.update(overrides)
    return event


def test_parses_events_for_device_shape() -> None:
    [event] = parse_events(fixture("events_for_device.json"))
    assert event.id == EVENT_ID
    assert event.title == "Room 204 lecture"
    assert event.cms == "epiphan"
    assert event.status == "scheduled"
    assert event.confirmed is True
    assert event.start == datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    assert event.finish == datetime(2026, 1, 1, 0, 50, tzinfo=UTC)
    assert event.device_ids == ("TEST-DEVICE-0001",)


def test_parses_current_or_next_shape() -> None:
    [event] = parse_events(fixture("current_or_next.json"))
    assert event.id == EVENT_ID
    assert event.device_ids == ("TEST-DEVICE-0001",)


def test_both_shapes_give_the_same_event() -> None:
    assert parse_events(fixture("events_for_device.json")) == parse_events(fixture("current_or_next.json"))


def test_empty_events() -> None:
    assert parse_events(fixture("events_empty.json")) == []


def test_current_or_next_entry_without_event_is_skipped() -> None:
    assert parse_events({"events": [{"device_id": "TEST-DEVICE-0001", "event": None}]}) == []


def test_dedupes_by_event_id() -> None:
    event = raw_event()
    assert len(parse_events({"events": [event, copy.deepcopy(event)]})) == 1


def test_dedupe_keeps_distinct_occurrences() -> None:
    later = raw_event(id="test-event-0001:1767312000", start="2026-01-02T00:00:00Z", finish="2026-01-02T00:50:00Z")
    assert [e.id for e in parse_events({"events": [raw_event(), later]})] == [EVENT_ID, "test-event-0001:1767312000"]


def test_synthetic_panopto_event_parses() -> None:
    [event] = parse_events({"events": [raw_event(cms="panopto")]})
    assert event.cms == "panopto"
    assert event.status_verified


def test_extra_fields_are_ignored() -> None:
    [event] = parse_events({"events": [raw_event(recurrence={"freq": "weekly"})]})
    assert event.id == EVENT_ID


def test_confirmed_may_be_missing() -> None:
    event = raw_event()
    del event["confirmed"]
    [parsed] = parse_events({"events": [event]})
    assert parsed.confirmed is None


def test_status_verified_only_for_known_statuses() -> None:
    assert KNOWN_EVENT_STATUSES == frozenset({"scheduled"})
    [event] = parse_events({"events": [raw_event(status="running")]})
    assert not event.status_verified


def test_naive_timestamp_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_events({"events": [raw_event(start="2026-01-01T00:00:00")]})


def test_bad_timestamp_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_events({"events": [raw_event(finish="not a time")]})


@pytest.mark.parametrize(
    "data",
    [
        [],
        "events",
        {"devices": []},
        {"events": "x"},
        {"events": [42]},
    ],
)
def test_unknown_shape_raises(data: object) -> None:
    with pytest.raises(ValueError, match="Edge"):
        parse_events(data)


def test_edge_event_is_frozen() -> None:
    [event] = parse_events(fixture("events_for_device.json"))
    with pytest.raises(ValidationError):
        event.title = "Changed"  # type: ignore[misc]


def test_to_sessions_one_per_device() -> None:
    devices = [
        {"device_id": "TEST-DEVICE-0001", "channels": []},
        {"device_id": "TEST-DEVICE-0002", "channels": []},
    ]
    [event] = parse_events({"events": [raw_event(devices=devices)]})
    sessions = to_sessions(event)
    assert [s.recorder_id for s in sessions] == ["TEST-DEVICE-0001", "TEST-DEVICE-0002"]
    for s in sessions:
        assert isinstance(s, ScheduledSession)
        assert s.id == EVENT_ID
        assert s.name == "Room 204 lecture"
        assert s.source is Source.EDGE
        assert s.start == event.start
        assert s.end == event.finish


def test_to_sessions_no_devices() -> None:
    event = EdgeEvent.model_validate(raw_event(devices=[]))
    assert to_sessions(event) == []


def test_recording_devices_all_stopped() -> None:
    assert parse_recording_devices(fixture("devices.json")) == (frozenset(), True)


def test_recording_devices_unconfirmed_state() -> None:
    data = fixture("devices.json")
    assert isinstance(data, dict)
    data["devices"][1]["Channels"][1]["recording_status"]["state"] = "started"
    assert parse_recording_devices(data) == (frozenset({"TEST-DEVICE-0002"}), False)


def test_recording_devices_ignores_missing_status() -> None:
    data = {"devices": [{"Id": "TEST-DEVICE-0001", "Channels": [{"channel_id": "1"}]}]}
    assert parse_recording_devices(data) == (frozenset(), True)


def test_recording_devices_unknown_shape() -> None:
    with pytest.raises(ValueError, match="Edge"):
        parse_recording_devices({"events": []})


def test_load_json_reads_file(tmp_path: Path) -> None:
    path = tmp_path / "events.json"
    path.write_text(json.dumps({"events": []}))
    assert asyncio.run(load_json(path)) == {"events": []}


def test_load_json_malformed(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not json")
    with pytest.raises(ValueError, match="broken.json"):
        asyncio.run(load_json(path))


def test_format_events_table() -> None:
    out = format_events(parse_events(fixture("events_for_device.json")))
    lines = out.splitlines()
    assert lines[0].split() == ["start", "UTC", "finish", "UTC", "device", "cms", "status", "title"]
    row = lines[-1]
    for part in (
        "2026-01-01 00:00",
        "2026-01-01 00:50",
        "TEST-DEVICE-0001",
        "epiphan",
        "scheduled",
        "Room 204 lecture",
    ):
        assert part in row
    assert "UNVERIFIED" not in out


def test_format_events_marks_unverified_status() -> None:
    out = format_events(parse_events({"events": [raw_event(status="running")]}))
    assert "UNVERIFIED status" in out.splitlines()[-1]


def test_format_events_converts_to_utc() -> None:
    out = format_events(parse_events({"events": [raw_event(start="2026-01-01T05:00:00+05:00")]}))
    assert "2026-01-01 00:00" in out.splitlines()[-1]


def test_format_events_empty() -> None:
    assert format_events([]) == "No Edge events in this file."


@pytest.mark.parametrize("bad", ["\x1b[2J", "\x1b]52;c;cm0gLXJmIH4=\x07", "\x07", "\x9b2J"])
def test_format_events_escapes_control_characters(bad: str) -> None:
    event = raw_event(title=f"Room 204 {bad}lecture")
    out = format_events(parse_events({"events": [event]}))
    assert bad not in out
    assert "\x1b" not in out and "\x07" not in out and "\x9b" not in out
    assert "Room 204 " in out and "lecture" in out


def test_format_events_escapes_device_ids_and_status() -> None:
    event = raw_event(status="running\x1b[2J", devices=[{"device_id": "TEST-DEVICE-0001\x07"}])
    out = format_events(parse_events({"events": [event]}))
    assert "\x1b" not in out and "\x07" not in out
    assert "TEST-DEVICE-0001\\x07" in out
