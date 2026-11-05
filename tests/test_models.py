from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from roomsync.models import Disagreement, DisagreementKind, Recorder, Room, ScheduledSession, Source

START = datetime(2026, 1, 12, 14, 0, tzinfo=UTC)


def session(**overrides: object) -> ScheduledSession:
    fields: dict[str, object] = {
        "id": "00000000-0000-0000-0000-000000000001",
        "name": "Lecture",
        "start": START,
        "end": START + timedelta(minutes=50),
        "recorder_id": "00000000-0000-0000-0000-0000000000aa",
        "source": Source.PLATFORM,
    }
    fields.update(overrides)
    return ScheduledSession(**fields)


def test_session_requires_timezone_aware_times() -> None:
    with pytest.raises(ValidationError):
        session(start=datetime(2026, 1, 12, 14, 0))


def test_session_end_must_follow_start() -> None:
    with pytest.raises(ValidationError):
        session(end=START)


def test_session_recorder_is_optional() -> None:
    assert session(recorder_id=None).recorder_id is None


def test_models_are_frozen() -> None:
    s = session()
    with pytest.raises(ValidationError):
        s.name = "Changed"  # type: ignore[misc]


def test_source_accepts_plain_strings() -> None:
    assert session(source="edge").source is Source.EDGE


def test_room_links_platform_recorder_to_edge_device() -> None:
    room = Room(name="Room 204", platform_recorder_id="rec-1", edge_device_id="TEST-SERIAL-0001")
    assert room.edge_device_id == "TEST-SERIAL-0001"


def test_recorder_state_is_optional() -> None:
    assert Recorder(id="rec-1", name="Room 204 recorder").state is None


def test_disagreement_defaults_to_verified() -> None:
    d = Disagreement(kind=DisagreementKind.MISSING_ON_DEVICE, room="Room 204", platform=session(), detail="x")
    assert d.verified is True
    assert d.edge is None


def test_disagreement_label_marks_unverified() -> None:
    d = Disagreement(kind=DisagreementKind.TIME_MISMATCH, room="Room 204", detail="x", verified=False)
    assert d.label == "UNVERIFIED time_mismatch"
    assert Disagreement(kind=DisagreementKind.TIME_MISMATCH, room="Room 204", detail="x").label == "time_mismatch"
