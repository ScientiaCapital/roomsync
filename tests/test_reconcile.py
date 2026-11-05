import itertools
from datetime import UTC, datetime, timedelta

import pytest

from roomsync.models import Disagreement, DisagreementKind, Recorder, Room, ScheduledSession, Source
from roomsync.reconcile import NO_RECORDER, adhoc_checks, reconcile

AS_OF = datetime(2026, 1, 12, 8, 0, tzinfo=UTC)
START = datetime(2026, 1, 12, 14, 0, tzinfo=UTC)
HOUR = timedelta(hours=1)
MIN = timedelta(minutes=1)

REC_204 = "00000000-0000-0000-0000-0000000000aa"
REC_310 = "00000000-0000-0000-0000-0000000000bb"
DEV_204 = "TEST-DEVICE-0001"
DEV_310 = "TEST-DEVICE-0002"

ROOM_204 = Room(name="Room 204", platform_recorder_id=REC_204, edge_device_id=DEV_204)
ROOM_310 = Room(name="Room 310", platform_recorder_id=REC_310, edge_device_id=DEV_310)
ROOMS = [ROOM_204, ROOM_310]
RECORDERS = [Recorder(id=REC_204, name="Room 204 recorder"), Recorder(id=REC_310, name="Room 310 recorder")]

_ids = itertools.count(1)


def _next_id() -> int:
    return next(_ids)


def plat(start: datetime = START, minutes: int = 50, recorder_id: str | None = REC_204) -> ScheduledSession:
    return ScheduledSession(
        id=f"00000000-0000-0000-0000-{_next_id():012d}",
        name="Lecture",
        start=start,
        end=start + timedelta(minutes=minutes),
        recorder_id=recorder_id,
        source=Source.PLATFORM,
    )


def edge(start: datetime = START, minutes: int = 50, device_id: str = DEV_204) -> ScheduledSession:
    return ScheduledSession(
        id=f"event-{_next_id()}:{int(start.timestamp())}",
        name="Lecture",
        start=start,
        end=start + timedelta(minutes=minutes),
        recorder_id=device_id,
        source=Source.EDGE,
    )


def run(
    platform: list[ScheduledSession],
    edge_sessions: list[ScheduledSession],
    *,
    rooms: list[Room] = ROOMS,
    recorders: list[Recorder] = RECORDERS,
    as_of: datetime = AS_OF,
    horizon: timedelta = timedelta(days=7),
    tolerance: timedelta = 2 * MIN,
) -> list[Disagreement]:
    return reconcile(platform, edge_sessions, rooms, recorders, as_of=as_of, horizon=horizon, tolerance=tolerance)


def kinds(result: list[Disagreement]) -> list[DisagreementKind]:
    return [d.kind for d in result]


# reconcile


def test_exact_match_reports_nothing() -> None:
    assert run([plat()], [edge()]) == []


def test_within_tolerance_reports_nothing() -> None:
    assert run([plat()], [edge(start=START + MIN, minutes=49)]) == []


def test_tolerance_boundary_is_inclusive() -> None:
    assert run([plat()], [edge(start=START + 2 * MIN, minutes=48)]) == []


def test_overlapping_but_outside_tolerance_is_time_mismatch() -> None:
    p, e = plat(), edge(start=START + 10 * MIN)
    result = run([p], [e])
    assert kinds(result) == [DisagreementKind.TIME_MISMATCH]
    d = result[0]
    assert d.room == "Room 204"
    assert d.platform == p and d.edge == e
    assert d.verified is True
    assert "2026-01-12T14:00:00+00:00" in d.detail
    assert "2026-01-12T14:10:00+00:00" in d.detail


def test_end_outside_tolerance_is_time_mismatch() -> None:
    assert kinds(run([plat()], [edge(minutes=80)])) == [DisagreementKind.TIME_MISMATCH]


def test_missing_on_device() -> None:
    p = plat()
    result = run([p], [])
    assert kinds(result) == [DisagreementKind.MISSING_ON_DEVICE]
    assert result[0].platform == p and result[0].edge is None
    assert result[0].room == "Room 204"


def test_missing_on_platform() -> None:
    e = edge()
    result = run([], [e])
    assert kinds(result) == [DisagreementKind.MISSING_ON_PLATFORM]
    assert result[0].edge == e and result[0].platform is None


def test_non_overlapping_sessions_do_not_pair() -> None:
    result = run([plat()], [edge(start=START + 2 * HOUR)])
    assert sorted(kinds(result)) == sorted([DisagreementKind.MISSING_ON_DEVICE, DisagreementKind.MISSING_ON_PLATFORM])


def test_session_past_horizon_is_not_reported() -> None:
    far = AS_OF + timedelta(weeks=3)
    assert run([plat(start=far)], [], horizon=timedelta(days=7)) == []
    assert run([], [edge(start=far)], horizon=timedelta(days=7)) == []


def test_already_ended_session_is_ignored() -> None:
    past = AS_OF - 2 * HOUR
    assert run([plat(start=past)], []) == []
    assert run([], [edge(start=past)]) == []


def test_session_in_progress_at_as_of_is_considered() -> None:
    assert kinds(run([plat(start=AS_OF - 10 * MIN)], [])) == [DisagreementKind.MISSING_ON_DEVICE]


def test_greedy_pairing_takes_closest_start() -> None:
    p = plat(minutes=120)
    near, far = edge(start=START + 5 * MIN, minutes=120), edge(start=START + 30 * MIN, minutes=60)
    result = run([p], [far, near])
    assert kinds(result) == [DisagreementKind.TIME_MISMATCH, DisagreementKind.MISSING_ON_PLATFORM]
    assert result[0].edge == near
    assert result[1].edge == far


def test_unknown_recorder() -> None:
    p = plat(recorder_id="00000000-0000-0000-0000-0000000000ff")
    result = run([p], [])
    assert kinds(result) == [DisagreementKind.RECORDER_UNKNOWN]
    assert result[0].room == "00000000-0000-0000-0000-0000000000ff"
    assert result[0].platform == p


def test_session_with_no_recorder() -> None:
    result = run([plat(recorder_id=None)], [])
    assert kinds(result) == [DisagreementKind.RECORDER_UNKNOWN]
    assert result[0].room == NO_RECORDER
    assert "named no recorder" in result[0].detail


def test_recorder_missing_from_platform_list() -> None:
    result = run([plat()], [edge()], recorders=[RECORDERS[1]])
    assert kinds(result) == [DisagreementKind.RECORDER_OFFLINE]
    assert result[0].room == "Room 204"
    assert result[0].verified is False
    assert "did not list" in result[0].detail


def test_recorder_missing_but_no_sessions_is_not_reported() -> None:
    assert run([], [], recorders=[]) == []


def test_recorder_state_is_not_judged() -> None:
    recorders = [Recorder(id=REC_204, name="Room 204 recorder", state="SomethingUnfamiliar")]
    assert run([plat()], [edge()], rooms=[ROOM_204], recorders=recorders) == []


def test_rooms_are_isolated() -> None:
    result = run([plat()], [edge(device_id=DEV_310)])
    assert [(d.room, d.kind) for d in result] == [
        ("Room 204", DisagreementKind.MISSING_ON_DEVICE),
        ("Room 310", DisagreementKind.MISSING_ON_PLATFORM),
    ]


def test_output_is_sorted_and_deterministic() -> None:
    platform = [plat(start=START + 3 * HOUR), plat(recorder_id=REC_310), plat()]
    edge_sessions = [edge(start=START + 5 * HOUR), edge(start=START + HOUR, device_id=DEV_310)]
    first = run(platform, edge_sessions)
    second = run(list(reversed(platform)), list(reversed(edge_sessions)))
    assert first == second
    keys = [(d.room, (d.platform or d.edge).start) for d in first]  # type: ignore[union-attr]
    assert keys == sorted(keys)


@pytest.mark.parametrize(
    ("as_of", "horizon", "tolerance"),
    [
        (datetime(2026, 1, 12, 8, 0), timedelta(days=7), MIN),
        (AS_OF, timedelta(days=-1), MIN),
        (AS_OF, timedelta(days=7), -MIN),
    ],
)
def test_bad_arguments_raise(as_of: datetime, horizon: timedelta, tolerance: timedelta) -> None:
    with pytest.raises(ValueError):
        run([], [], as_of=as_of, horizon=horizon, tolerance=tolerance)


# adhoc_checks

NOW = START + 10 * MIN


def test_adhoc_recording_with_covering_session_reports_nothing() -> None:
    assert adhoc_checks([edge()], [], ROOMS, {DEV_204}, as_of=NOW, lookahead=LOOKAHEAD) == []
    assert adhoc_checks([], [plat()], ROOMS, {DEV_204}, as_of=NOW, lookahead=LOOKAHEAD) == []


def test_adhoc_recording_with_no_session() -> None:
    result = adhoc_checks([], [], ROOMS, {DEV_204}, as_of=NOW, lookahead=LOOKAHEAD)
    assert kinds(result) == [DisagreementKind.UNSCHEDULED_RECORDING]
    assert result[0].room == "Room 204"


def test_adhoc_recording_with_upcoming_session() -> None:
    upcoming = plat(start=NOW + 30 * MIN)
    result = adhoc_checks([edge(start=NOW + 2 * HOUR)], [upcoming], ROOMS, {DEV_204}, as_of=NOW, lookahead=LOOKAHEAD)
    assert kinds(result) == [DisagreementKind.UNSCHEDULED_RECORDING, DisagreementKind.ADHOC_PREEMPTED]
    preempted = result[1]
    assert preempted.platform == upcoming
    assert "2026-01-12T14:40:00+00:00" in preempted.detail
    assert "stops the ad hoc event" in preempted.detail


def test_adhoc_device_not_recording_reports_nothing() -> None:
    assert adhoc_checks([], [plat(start=NOW + 30 * MIN)], ROOMS, set(), as_of=NOW, lookahead=LOOKAHEAD) == []


def test_adhoc_results_are_unverified() -> None:
    result = adhoc_checks([], [plat(start=NOW + 30 * MIN)], ROOMS, {DEV_204, DEV_310}, as_of=NOW, lookahead=LOOKAHEAD)
    assert len(result) == 3
    assert all(d.verified is False for d in result)


def test_adhoc_rejects_naive_as_of() -> None:
    with pytest.raises(ValueError):
        adhoc_checks([], [], ROOMS, {DEV_204}, as_of=datetime(2026, 1, 12, 14, 0), lookahead=LOOKAHEAD)


LOOKAHEAD = timedelta(minutes=600)


def test_adhoc_preemption_ignores_sessions_past_lookahead() -> None:
    result = adhoc_checks([], [plat(start=NOW + 3 * 24 * HOUR)], ROOMS, {DEV_204}, as_of=NOW, lookahead=LOOKAHEAD)
    assert [d.kind for d in result] == [DisagreementKind.UNSCHEDULED_RECORDING]


def test_adhoc_rejects_negative_lookahead() -> None:
    with pytest.raises(ValueError):
        adhoc_checks([], [], ROOMS, {DEV_204}, as_of=NOW, lookahead=-HOUR)
