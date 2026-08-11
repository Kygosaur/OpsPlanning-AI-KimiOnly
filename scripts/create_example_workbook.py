from pathlib import Path

import pandas as pd


root = Path(__file__).resolve().parents[1]
output = root / "data" / "planning.xlsx"
output.parent.mkdir(parents=True, exist_ok=True)

workers = pd.DataFrame([
    {"Worker": "Aisha", "Skill": "welding", "Available": True},
    {"Worker": "Ben", "Skill": "welding", "Available": True},
    {"Worker": "Chen", "Skill": "machining", "Available": True},
])
machines = pd.DataFrame([
    {"Machine": "WELD-01", "Type": "welder", "Available": True},
    {"Machine": "CNC-01", "Type": "cnc", "Available": True},
    {"Machine": "CNC-02", "Type": "cnc", "Available": True},
])
vehicles = pd.DataFrame([
    {"Vehicle": "FORK-01", "Type": "forklift", "Available": True},
])
tasks = pd.DataFrame([
    {"Task": "Cut plate", "Duration_Hours": 3, "Priority": "high", "Deadline_Days": 1, "Required_Skill": "machining", "Workers_Needed": 1, "Machine_Type": "cnc", "Predecessors": "", "Vehicle_Type": ""},
    {"Task": "Weld frame", "Duration_Hours": 4, "Priority": "critical", "Deadline_Days": 1, "Required_Skill": "welding", "Workers_Needed": 2, "Machine_Type": "welder", "Predecessors": "Cut plate", "Vehicle_Type": ""},
    {"Task": "Move frame", "Duration_Hours": 1, "Priority": "medium", "Deadline_Days": 2, "Required_Skill": "welding", "Workers_Needed": 1, "Machine_Type": "welder", "Predecessors": "Weld frame", "Vehicle_Type": "forklift"},
])
with pd.ExcelWriter(output, engine="openpyxl") as writer:
    workers.to_excel(writer, sheet_name="Workers", index=False)
    tasks.to_excel(writer, sheet_name="Tasks", index=False)
    machines.to_excel(writer, sheet_name="Machines", index=False)
    vehicles.to_excel(writer, sheet_name="Vehicles", index=False)
print(f"Created {output}")

