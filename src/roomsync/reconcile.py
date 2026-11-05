"""Compare platform and Edge schedules. Pure functions: no network, no I/O, no writes.

Ids never match across sides (Edge occurrence ids look like "<event>:<unix start>", Panopto ids are GUIDs), so
sessions are paired by Room mapping and time, never by id.
"""

from collections.abc import Collection, Sequence
from datetime import UTC, datetime, timedelta

from roomsync.models import Disagreement, DisagreementKind, Recorder, Room, ScheduledSession, Source

NO_RECORDER = "(no recorder)"
"""Room label for a platform session that names no recorder."""

_Keyed = tuple[tuple[str, datetime, str, str, str], Disagreement]


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat()


def _require_aware(as_of: datetime) -> None:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone aware")


def _keyed(d: Disagreement, anchor: datetime) -> _Keyed:
    p_id = d.platform.id if d.platform else ""
    e_id = d.edge.id if d.edge else ""
    return (d.room, anchor, d.kind.value, p_id, e_id), d


def _span(s: ScheduledSession) -> str:
    return f"{_iso(s.start)} to {_iso(s.end)}"


def _overlaps(a: ScheduledSession, b: ScheduledSession) -> bool:
    return a.start < b.end and b.start < a.end


def _pair(
    platform: list[ScheduledSession], edge: list[ScheduledSession]
) -> tuple[list[tuple[ScheduledSession, ScheduledSession]], list[ScheduledSession], list[ScheduledSession]]:
    """Greedy pairing: among overlapping (platform, edge) pairs, take the closest start first; each session pairs once.

    Ties break by platform start, then platform id, then edge id, so the result never depends on input order.
    """
    candidates = sorted(
        ((p, e) for p in platform for e in edge if _overlaps(p, e)),
        key=lambda pe: (abs(pe[0].start - pe[1].start), pe[0].start, pe[0].id, pe[1].id),
    )
    pairs: list[tuple[ScheduledSession, ScheduledSession]] = []
    used_p: set[str] = set()
    used_e: set[str] = set()
    for p, e in candidates:
        if p.id in used_p or e.id in used_e:
            continue
        pairs.append((p, e))
        used_p.add(p.id)
        used_e.add(e.id)
    return pairs, [p for p in platform if p.id not in used_p], [e for e in edge if e.id not in used_e]


def reconcile(
    platform: Sequence[ScheduledSession],
    edge: Sequence[ScheduledSession],
    rooms: Sequence[Room],
    recorders: Sequence[Recorder],
    *,
    as_of: datetime,
    horizon: timedelta,
    tolerance: timedelta,
) -> list[Disagreement]:
    """Report where the platform schedule and the device schedule disagree, room by room.

    Only sessions with end > as_of and start < as_of + horizon count, on both sides. The kb page
    cms/view-scheduled-cms-events-and-history says the device can "see up to 90 days depending on the CMS platform,
    shortest being Panopto (1 week) of upcoming scheduled events", so a platform session past the device's horizon is
    not missing. The same page says "The Events page updates to show new events at least every hour."

    Within a room, platform and edge sessions pair when their times overlap (see `_pair`). A pair whose start and
    end both differ by at most `tolerance` agrees; otherwise it is TIME_MISMATCH. Unpaired sessions are
    MISSING_ON_DEVICE or MISSING_ON_PLATFORM. A platform session naming no known room recorder is RECORDER_UNKNOWN.
    Recorder `state` is never judged, since Panopto's state vocabulary is unverified; RECORDER_OFFLINE (unverified)
    only means the platform did not list the room's recorder while the room has sessions in the window.
    Edge sessions on devices that belong to no room are ignored. Output is sorted by room, start time, then kind.
    """
    _require_aware(as_of)
    if horizon < timedelta(0):
        raise ValueError("horizon must not be negative")
    if tolerance < timedelta(0):
        raise ValueError("tolerance must not be negative")

    window_end = as_of + horizon
    platform = [s for s in platform if s.end > as_of and s.start < window_end]
    edge = [s for s in edge if s.end > as_of and s.start < window_end]
    known = {r.id for r in recorders}
    out: list[_Keyed] = []

    room_recorders = {room.platform_recorder_id for room in rooms}
    for s in platform:
        if s.recorder_id is None:
            detail = f"The platform named no recorder for the session at {_span(s)}."
            d = Disagreement(kind=DisagreementKind.RECORDER_UNKNOWN, room=NO_RECORDER, platform=s, detail=detail)
            out.append(_keyed(d, s.start))
        elif s.recorder_id not in room_recorders:
            detail = f"Recorder {s.recorder_id} matches no room, for the session at {_span(s)}."
            d = Disagreement(kind=DisagreementKind.RECORDER_UNKNOWN, room=s.recorder_id, platform=s, detail=detail)
            out.append(_keyed(d, s.start))

    for room in rooms:
        p_room = [s for s in platform if s.recorder_id == room.platform_recorder_id]
        e_room = [s for s in edge if s.recorder_id == room.edge_device_id]
        if (p_room or e_room) and room.platform_recorder_id not in known:
            first = min(s.start for s in p_room + e_room)
            detail = (
                f"The platform did not list recorder {room.platform_recorder_id}, "
                f"and the room has sessions from {_iso(first)}."
            )
            d = Disagreement(kind=DisagreementKind.RECORDER_OFFLINE, room=room.name, detail=detail, verified=False)
            out.append(_keyed(d, first))

        pairs, lone_p, lone_e = _pair(p_room, e_room)
        for p, e in pairs:
            if abs(p.start - e.start) <= tolerance and abs(p.end - e.end) <= tolerance:
                continue
            detail = f"The platform has {_span(p)} and the device has {_span(e)}."
            d = Disagreement(kind=DisagreementKind.TIME_MISMATCH, room=room.name, platform=p, edge=e, detail=detail)
            out.append(_keyed(d, p.start))
        for p in lone_p:
            detail = f"The platform has a session at {_span(p)} that the device does not list."
            d = Disagreement(kind=DisagreementKind.MISSING_ON_DEVICE, room=room.name, platform=p, detail=detail)
            out.append(_keyed(d, p.start))
        for e in lone_e:
            detail = f"The device has a session at {_span(e)} that the platform does not list."
            d = Disagreement(kind=DisagreementKind.MISSING_ON_PLATFORM, room=room.name, edge=e, detail=detail)
            out.append(_keyed(d, e.start))

    return [d for _, d in sorted(out, key=lambda kd: kd[0])]


def adhoc_checks(
    edge: Sequence[ScheduledSession],
    platform: Sequence[ScheduledSession],
    rooms: Sequence[Room],
    recording_device_ids: Collection[str],
    *,
    as_of: datetime,
    lookahead: timedelta,
) -> list[Disagreement]:
    """Flag rooms whose device records at `as_of` with no scheduled session covering that moment.

    Snapshot check at `as_of` only. For each such room this emits UNSCHEDULED_RECORDING, and, when the room's next
    scheduled session (either side) starts after `as_of` and before `as_of + lookahead`, ADHOC_PREEMPTED. The kb page
    cms/create-ad-hoc-events-using-the-touch-screen (Pearl-2, Pearl Mini) says: "Scheduled events have priority over
    ad hoc events. If an ad hoc event is still in progress when it's time to start a scheduled event, the Pearl
    device gracefully stops the ad hoc event and automatically starts the scheduled event." It also says "You cannot
    start an ad hoc event if it's within five minutes of a scheduled event's start time." It gives 600 minutes as the
    longest event from the touch screen, a sensible `lookahead`.

    Every result has verified=False: the Edge recording-state value that marks a channel as recording has not been
    observed yet, so `recording_device_ids` and the detection built on it are unconfirmed.
    """
    _require_aware(as_of)
    if lookahead < timedelta(0):
        raise ValueError("lookahead must not be negative")
    out: list[_Keyed] = []
    for room in rooms:
        if room.edge_device_id not in recording_device_ids:
            continue
        sessions = [s for s in platform if s.recorder_id == room.platform_recorder_id]
        sessions += [s for s in edge if s.recorder_id == room.edge_device_id]
        if any(s.start <= as_of < s.end for s in sessions):
            continue
        detail = f"The device is recording at {_iso(as_of)} with no scheduled session covering that time."
        d = Disagreement(kind=DisagreementKind.UNSCHEDULED_RECORDING, room=room.name, detail=detail, verified=False)
        out.append(_keyed(d, as_of))

        upcoming = [s for s in sessions if as_of < s.start < as_of + lookahead]
        if not upcoming:
            continue
        nxt = min(upcoming, key=lambda s: (s.start, s.source.value, s.id))
        detail = (
            f"A scheduled session starts at {_iso(nxt.start)}; the device stops the ad hoc event "
            "when a scheduled event starts."
        )
        on_platform = nxt.source is Source.PLATFORM
        d = Disagreement(
            kind=DisagreementKind.ADHOC_PREEMPTED,
            room=room.name,
            platform=nxt if on_platform else None,
            edge=None if on_platform else nxt,
            detail=detail,
            verified=False,
        )
        out.append(_keyed(d, nxt.start))
    return [d for _, d in sorted(out, key=lambda kd: kd[0])]
