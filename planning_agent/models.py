from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Worker:
    name: str
    skill: str
    available: bool = True


@dataclass(frozen=True)
class Machine:
    name: str
    machine_type: str
    available: bool = True


@dataclass(frozen=True)
class Vehicle:
    name: str
    vehicle_type: str
    available: bool = True


@dataclass(frozen=True)
class Task:
    name: str
    duration_hours: float
    priority: str
    deadline_hours: float | None
    required_skill: str
    workers_needed: int
    machine_type: str
    predecessors: tuple[str, ...] = ()
    vehicle_type: str | None = None


@dataclass(frozen=True)
class PlanningRequest:
    blocked_machines: tuple[str, ...] = ()
    blocked_workers: tuple[str, ...] = ()
    blocked_vehicles: tuple[str, ...] = ()
    safety_question: str | None = None


@dataclass(frozen=True)
class ScheduledTask:
    task: str
    start_hour: float
    end_hour: float
    workers: tuple[str, ...]
    machine: str
    vehicle: str | None
    priority: str
    deadline_hour: float | None
    deadline_met: bool | None
    selection_reason: str


@dataclass(frozen=True)
class UnscheduledTask:
    task: str
    reason: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScheduleResult:
    scheduled: tuple[ScheduledTask, ...]
    unscheduled: tuple[UnscheduledTask, ...]
    makespan_hours: float
    unavailable_resources: dict[str, tuple[str, ...]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

