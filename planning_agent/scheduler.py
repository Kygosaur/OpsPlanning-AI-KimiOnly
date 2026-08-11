from __future__ import annotations

from .models import Machine, PlanningRequest, ScheduledTask, ScheduleResult, Task, UnscheduledTask, Vehicle, Worker

PRIORITY_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def create_schedule(workers: list[Worker], tasks: list[Task], machines: list[Machine], vehicles: list[Vehicle] | None = None, request: PlanningRequest | None = None) -> ScheduleResult:
    vehicles = vehicles or []
    request = request or PlanningRequest()
    blocked_machines = {x.casefold() for x in request.blocked_machines}
    blocked_workers = {x.casefold() for x in request.blocked_workers}
    blocked_vehicles = {x.casefold() for x in request.blocked_vehicles}

    usable_workers = [w for w in workers if w.available and w.name.casefold() not in blocked_workers]
    usable_machines = [m for m in machines if m.available and m.name.casefold() not in blocked_machines]
    usable_vehicles = [v for v in vehicles if v.available and v.name.casefold() not in blocked_vehicles]
    worker_free = {w.name: 0.0 for w in usable_workers}
    machine_free = {m.name: 0.0 for m in usable_machines}
    vehicle_free = {v.name: 0.0 for v in usable_vehicles}
    finish: dict[str, float] = {}
    scheduled: list[ScheduledTask] = []
    unscheduled: list[UnscheduledTask] = []
    remaining = {task.name: task for task in tasks}

    while remaining:
        ready = [t for t in remaining.values() if all(p in finish for p in t.predecessors)]
        if not ready:
            for task in remaining.values():
                missing = [p for p in task.predecessors if p not in finish]
                unscheduled.append(UnscheduledTask(task.name, "Predecessor cycle or unscheduled predecessor", {"predecessors": missing}))
            break
        ready.sort(key=lambda t: (-PRIORITY_WEIGHT[t.priority], t.deadline_hours if t.deadline_hours is not None else float("inf"), t.name.casefold()))
        task = ready[0]
        del remaining[task.name]

        candidate_workers = [w for w in usable_workers if w.skill == task.required_skill]
        candidate_machines = [m for m in usable_machines if m.machine_type == task.machine_type]
        candidate_vehicles = [v for v in usable_vehicles if task.vehicle_type and v.vehicle_type == task.vehicle_type]
        if len(candidate_workers) < task.workers_needed:
            unscheduled.append(UnscheduledTask(task.name, "Insufficient available skilled workers", {"needed": task.workers_needed, "available": len(candidate_workers), "skill": task.required_skill}))
            continue
        if not candidate_machines:
            unscheduled.append(UnscheduledTask(task.name, "No available compatible machine", {"machine_type": task.machine_type}))
            continue
        if task.vehicle_type and not candidate_vehicles:
            unscheduled.append(UnscheduledTask(task.name, "No available compatible vehicle", {"vehicle_type": task.vehicle_type}))
            continue

        predecessor_finish = max((finish[p] for p in task.predecessors), default=0.0)
        chosen_workers = sorted(candidate_workers, key=lambda w: (worker_free[w.name], w.name))[:task.workers_needed]
        machine = min(candidate_machines, key=lambda m: (machine_free[m.name], m.name))
        vehicle = min(candidate_vehicles, key=lambda v: (vehicle_free[v.name], v.name)) if task.vehicle_type else None
        start = max(predecessor_finish, machine_free[machine.name], *(worker_free[w.name] for w in chosen_workers), vehicle_free[vehicle.name] if vehicle else 0.0)
        end = start + task.duration_hours
        for worker in chosen_workers:
            worker_free[worker.name] = end
        machine_free[machine.name] = end
        if vehicle:
            vehicle_free[vehicle.name] = end
        finish[task.name] = end
        deadline_met = None if task.deadline_hours is None else end <= task.deadline_hours
        scheduled.append(ScheduledTask(task.name, start, end, tuple(w.name for w in chosen_workers), machine.name, vehicle.name if vehicle else None, task.priority, task.deadline_hours, deadline_met, "Earliest-available compatible resources; ties resolved by identifier"))

    unavailable = {
        "workers": tuple(w.name for w in workers if not w.available or w.name.casefold() in blocked_workers),
        "machines": tuple(m.name for m in machines if not m.available or m.name.casefold() in blocked_machines),
        "vehicles": tuple(v.name for v in vehicles if not v.available or v.name.casefold() in blocked_vehicles),
    }
    return ScheduleResult(tuple(sorted(scheduled, key=lambda x: (x.start_hour, x.task))), tuple(unscheduled), max((x.end_hour for x in scheduled), default=0.0), unavailable)

