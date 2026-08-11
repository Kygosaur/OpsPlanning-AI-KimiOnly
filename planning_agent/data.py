from __future__ import annotations

from pathlib import Path

import pandas as pd

from .models import Machine, Task, Vehicle, Worker


PRIORITIES = {"critical", "high", "medium", "low"}


def _required_columns(frame: pd.DataFrame, sheet: str, columns: set[str]) -> None:
    missing = columns - set(frame.columns)
    if missing:
        raise ValueError(f"Sheet {sheet!r} is missing columns: {sorted(missing)}")


def _text(value: object, field: str) -> str:
    if pd.isna(value) or not str(value).strip():
        raise ValueError(f"{field} must not be empty")
    return str(value).strip()


def _boolean(value: object, field: str) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"{field} must be a boolean, got {value!r}")


def load_workbook(path: str | Path) -> tuple[list[Worker], list[Task], list[Machine], list[Vehicle]]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Planning workbook not found: {path}")

    book = pd.ExcelFile(path)
    for sheet in ("Workers", "Tasks", "Machines"):
        if sheet not in book.sheet_names:
            raise ValueError(f"Workbook is missing required sheet {sheet!r}")

    workers_df = pd.read_excel(book, "Workers")
    tasks_df = pd.read_excel(book, "Tasks")
    machines_df = pd.read_excel(book, "Machines")
    vehicles_df = pd.read_excel(book, "Vehicles") if "Vehicles" in book.sheet_names else pd.DataFrame()

    _required_columns(workers_df, "Workers", {"Worker", "Skill", "Available"})
    _required_columns(machines_df, "Machines", {"Machine", "Type", "Available"})
    _required_columns(tasks_df, "Tasks", {"Task", "Duration_Hours", "Priority", "Deadline_Days", "Required_Skill", "Workers_Needed", "Machine_Type"})

    workers = [Worker(_text(r.Worker, "Worker"), _text(r.Skill, "Skill").casefold(), _boolean(r.Available, "Worker.Available")) for r in workers_df.itertuples(index=False)]
    machines = [Machine(_text(r.Machine, "Machine"), _text(r.Type, "Machine.Type").casefold(), _boolean(r.Available, "Machine.Available")) for r in machines_df.itertuples(index=False)]

    vehicles: list[Vehicle] = []
    if not vehicles_df.empty:
        _required_columns(vehicles_df, "Vehicles", {"Vehicle", "Type", "Available"})
        vehicles = [Vehicle(_text(r.Vehicle, "Vehicle"), _text(r.Type, "Vehicle.Type").casefold(), _boolean(r.Available, "Vehicle.Available")) for r in vehicles_df.itertuples(index=False)]

    tasks: list[Task] = []
    for row in tasks_df.to_dict("records"):
        priority = _text(row["Priority"], "Task.Priority").casefold()
        if priority not in PRIORITIES:
            raise ValueError(f"Unknown priority {priority!r}; expected one of {sorted(PRIORITIES)}")
        duration = float(row["Duration_Hours"])
        workers_needed_float = float(row["Workers_Needed"])
        if duration <= 0 or not workers_needed_float.is_integer() or workers_needed_float < 1:
            raise ValueError(f"Invalid duration or worker count for task {row['Task']!r}")
        deadline = None if pd.isna(row["Deadline_Days"]) else float(row["Deadline_Days"]) * 24
        predecessor_value = row.get("Predecessors", "")
        predecessors = () if pd.isna(predecessor_value) else tuple(x.strip() for x in str(predecessor_value).split(",") if x.strip())
        vehicle_value = row.get("Vehicle_Type")
        vehicle_type = None if vehicle_value is None or pd.isna(vehicle_value) or not str(vehicle_value).strip() else str(vehicle_value).strip().casefold()
        tasks.append(Task(
            name=_text(row["Task"], "Task"), duration_hours=duration,
            priority=priority, deadline_hours=deadline,
            required_skill=_text(row["Required_Skill"], "Required_Skill").casefold(),
            workers_needed=int(workers_needed_float), machine_type=_text(row["Machine_Type"], "Machine_Type").casefold(),
            predecessors=predecessors, vehicle_type=vehicle_type,
        ))

    _validate_unique([w.name for w in workers], "worker")
    _validate_unique([m.name for m in machines], "machine")
    _validate_unique([v.name for v in vehicles], "vehicle")
    _validate_unique([t.name for t in tasks], "task")
    known_tasks = {t.name for t in tasks}
    for task in tasks:
        unknown = set(task.predecessors) - known_tasks
        if unknown:
            raise ValueError(f"Task {task.name!r} has unknown predecessors: {sorted(unknown)}")
    return workers, tasks, machines, vehicles


def _validate_unique(names: list[str], kind: str) -> None:
    folded = [name.casefold() for name in names]
    duplicates = sorted({names[i] for i, value in enumerate(folded) if folded.count(value) > 1})
    if duplicates:
        raise ValueError(f"Duplicate {kind} identifiers: {duplicates}")

