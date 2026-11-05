"""Shared data model. Platform adapters and the Edge reader produce these; the reconciler compares them."""

from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator


class Source(StrEnum):
    PLATFORM = "platform"
    EDGE = "edge"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Recorder(_Frozen):
    """A remote recorder as the video platform lists it."""

    id: str
    name: str
    state: str | None = None


class Room(_Frozen):
    """Links one platform recorder to the Epiphan device that runs it. Supplied by the operator, never guessed."""

    name: str
    platform_recorder_id: str
    edge_device_id: str


class ScheduledSession(_Frozen):
    """One scheduled recording, from either side. `recorder_id` is a platform recorder id or an Edge device id."""

    id: str
    name: str
    start: AwareDatetime
    end: AwareDatetime
    recorder_id: str | None
    source: Source

    @model_validator(mode="after")
    def _end_after_start(self) -> Self:
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class DisagreementKind(StrEnum):
    MISSING_ON_DEVICE = "missing_on_device"
    MISSING_ON_PLATFORM = "missing_on_platform"
    TIME_MISMATCH = "time_mismatch"
    RECORDER_OFFLINE = "recorder_offline"
    RECORDER_UNKNOWN = "recorder_unknown"
    UNSCHEDULED_RECORDING = "unscheduled_recording"
    ADHOC_PREEMPTED = "adhoc_preempted"


class Disagreement(_Frozen):
    """Where the platform and the device disagree. `verified` is False when the kb doesn't settle the check."""

    kind: DisagreementKind
    room: str
    platform: ScheduledSession | None = None
    edge: ScheduledSession | None = None
    detail: str
    verified: bool = True

    @property
    def label(self) -> str:
        return self.kind.value if self.verified else f"UNVERIFIED {self.kind.value}"
