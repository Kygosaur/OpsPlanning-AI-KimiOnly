# PlanningAI (Kimi)

PlanningAI is a private industrial planning assistant that runs on one computer.
It combines a deterministic Python scheduler with a locally hosted Kimi model,
a FastAPI backend, and a responsive React chat interface.

The application can:

- schedule tasks using workers, machines, vehicles, priorities, deadlines, and
  task dependencies;
- answer questions about approved local PDFs, Word documents, spreadsheets,
  CSV, JSON, Markdown, text, YAML, and Python files;
- retrieve relevant passages locally and cite the source file and location; and
- understand natural-language planning requests and explain Python-generated
  schedules.

Kimi understands requests and explains results; it does not invent the final
allocation. OR-Tools CP-SAT creates the schedule subject to resource, calendar,
maintenance, certification, deadline, and dependency constraints. The result is
saved as a draft for human approval.

## How the local system works

```text
Browser at 127.0.0.1:8000
          |
          v
React
  |
FastAPI
  |
Planning Agent
  |-- Kimi -------- Ollama (local GPU)
  |-- RAG --------- Documents / Excel
  `-- Optimizer --- OR-Tools CP-SAT
           \          /
            SQLite database
```

The intent router returns non-exclusive flags. A request can use RAG and
planning together:

```json
{"general": false, "rag": true, "planning": true}
```

Each completed request uses one response contract containing `answer`,
`sources`, `warnings`, `intents`, optional `schedule`, and per-stage `timing`.
Schedule metadata includes solver status, makespan, and approval status. This
lets the React interface render reliable structured results without extracting
facts from Kimi's prose.

`Ollama` is the local model runtime. It loads Kimi onto the GPU and provides an
API at `127.0.0.1:11434`. This is a process on the same PC, not a remote server.
FastAPI sends the user's question and only the most relevant local excerpts to
that process. The application rejects non-loopback model addresses.

No cloud LLM, remote embedding API, telemetry, web search, CDN, or external
frontend asset is used. Model weights must be downloaded once during setup;
afterward, normal planning and document chat do not require internet access.

## Requirements

- Windows with Python 3.11 or newer
- Node.js and npm to rebuild the React interface
- Ollama
- An NVIDIA GPU with sufficient VRAM

The verified configuration uses an RTX 5060 Ti with 16 GB VRAM and Kimi-VL A3B
Thinking Q5. The model is approximately 12 GB. The included profile limits its
context to 8K tokens to leave GPU memory for the context cache and application.

## 1. Install the application

```powershell
git clone https://github.com/Kygosaur/PlanningAI-Kimi.git
cd PlanningAI-Kimi

python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Prepare the fully local embedding and reranking models once (internet is needed
only for this download):

```powershell
.venv\Scripts\python.exe scripts\prepare_retrieval_models.py
```

Normal use is then offline. Retrieval combines BM25 lexical matching and local
embedding similarity, fuses candidates, and reranks them with a local cross
encoder. Set `RETRIEVAL_ENABLE_SEMANTIC=false` for lexical-only operation.

Build the React interface:

```powershell
cd web
npm install
npm run build
cd ..
```

The compiled interface is already included, but rebuilding it ensures it matches
the installed source.

## 2. Install and prepare Kimi with Ollama

Install Ollama from [ollama.com](https://ollama.com), then open a new PowerShell
window and download the verified local model:

```powershell
ollama pull richardyoung/kimi-vl-a3b-thinking:Q5_K_M
```

Create the project-specific `planning-kimi` profile:

```powershell
ollama create planning-kimi --file models/Kimi.Modelfile
```

The profile references the downloaded weights without copying another 12 GB.
Ollama stores model weights outside the repository, so they are never committed
to GitHub.

Confirm that the model exists:

```powershell
ollama list
```

Test it directly:

```powershell
ollama run planning-kimi "Reply with: Kimi is ready"
```

Useful Ollama commands:

```powershell
ollama ps                       # Show models currently loaded in memory
ollama stop planning-kimi       # Unload Kimi from GPU memory
ollama list                     # Show downloaded models
```

Ollama normally starts its local background process automatically. The first
question after a restart is slower because the 12 GB model must be loaded onto
the GPU. Warm questions are considerably faster. Ollama unloads an inactive
model after its keep-alive period and reloads it when needed.

The `.env` file should contain:

```env
LOCAL_LLM_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_LLM_MODEL=planning-kimi
PLANNING_WORKSPACE=documents
PLANNING_WEB_PORT=8000
```

## 3. Add private work data

Place operational files in these folders:

```text
data/        Excel planning workbook and PSPLIB instances
documents/   Approved SOPs, manuals, and reference documents
outputs/     Generated schedule results
```

Their contents are ignored by Git except for placeholders and the sanitized
example SOP. Do not remove these ignore rules when using employee, operational,
or safety data.

Create a demonstration planning workbook if needed:

```powershell
.venv\Scripts\python.exe scripts\create_example_workbook.py
```

Supported planning workbook sheets and production fields:

- `Workers`: `Worker`, `Skill` or `Skills`, `Certifications`, `Available`,
  `Calendar`, `Shift`, `Location`, `Cost_Per_Hour`, `Current_Workload_Hours`.
- `Machines`: `Machine`, `Type`, `Capabilities`, `Available`, `Calendar`,
  `Location`, `Operating_Cost_Per_Hour`.
- Optional `Vehicles`: the same resource fields as machines.
- `Tasks`: `Task`, `Duration_Hours`, `Setup_Hours`, `Travel_Hours`, `Priority`,
  `Deadline_Days`, `Location`, `Required_Skill` or `Required_Skills`,
  `Required_Certifications`, `Workers_Needed`, `Machine_Type` or
  `Machine_Requirements`, optional `Vehicle_Type` or `Vehicle_Requirements`,
  `Predecessors`, and `Setup_Requirements`.

Comma-separated fields represent arrays. Names, skills, types, capabilities,
and certifications match case-insensitively. Total occupied time is task
duration + setup time + travel time.

Calendar examples:

```text
Worker A
Mon: 08:00-17:00
Tue: 08:00-17:00
Wed: leave

Machine A
Mon: 24h
Tue: maintenance 10:00-14:00

Worker B
Shift: 20:00-08:00
```

Use `scripts/create_example_workbook.py` as the canonical editable template.

Terminology aliases are intentionally source-controlled and easy to update in
`planning_agent/terminology.py`. Defaults include helmet/protective headgear,
automobile/vehicle, and PPE/personal protective equipment.

## 4. Start the web application

### One-click Windows shortcut

Run this once to create a **PlanningAI** shortcut on the current user's Desktop:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\create_desktop_shortcut.ps1
```

After that, double-click **PlanningAI**. The launcher checks Ollama and the
`planning-kimi` model, starts the private FastAPI service in the background,
waits until document indexing is ready, and opens the chat automatically. If
startup fails, it displays a readable error and records diagnostic logs under
`data\`.

The shortcut uses `assets\planning-ai.ico`. Re-run the shortcut creation script
after moving the repository to another folder or computer.

### PowerShell startup

From the repository folder:

```powershell
.venv\Scripts\python.exe scripts\run_web.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

The web application:

- indexes the approved workspace when it starts;
- searches the in-memory index before asking Kimi;
- shows the local sources used for an answer;
- displays search and thinking progress;
- shows a live timer after 10 seconds; and
- keeps conversation history only in browser memory.

Schedule runs and approval history are persisted locally in
`data/planning_agent.db`. New schedules begin as `draft`; a planner or admin can
approve or reject them through the API. Every change records an audit event.
Optional signed bearer-token authentication supports `viewer`, `planner`, and
`admin` roles. Enable it with `AUTH_ENABLED=true`, set a strong `AUTH_SECRET`,
and provide the bootstrap administrator variables documented in `.env.example`.

Key API routes are `/api/chat`, `/api/schedules`,
`/api/schedules/{id}/review`, `/api/auth/login`, and `/api/auth/me`. Send
`{"decision":"approved"}` or `{"decision":"rejected"}` to the review route.
FastAPI also exposes interactive local documentation at `/docs`.

Use the **Refresh** button after adding or changing workspace documents. Press
`Ctrl+C` in the server terminal to stop the web application.

## Planning from the terminal

Create and explain a schedule with local Kimi:

```powershell
.venv\Scripts\python.exe -m planning_agent.cli `
  --model planning-kimi `
  schedule `
  --workbook data/planning.xlsx `
  --workspace documents `
  --request "Plan all work. CNC-02 is unavailable. What does the welding SOP require?"
```

Run the deterministic scheduler without Kimi:

```powershell
.venv\Scripts\python.exe -m planning_agent.cli schedule `
  --workbook data/planning.xlsx `
  --blocked-machine CNC-02 `
  --no-llm
```

## Troubleshooting

**The application says model `planning-kimi` was not found**

```powershell
ollama create planning-kimi --file models/Kimi.Modelfile
ollama list
```

**The application cannot reach the local model**

Start Ollama from the Windows Start menu and test:

```powershell
ollama run planning-kimi "Hello"
```

**The first answer is slow**

This is expected while Ollama loads the model into GPU memory. Check `ollama ps`
to confirm that `planning-kimi` is loaded with GPU acceleration.

**Answers do not include a recently added file**

Select **Refresh** in the web interface. Files larger than 5 MB, symlinks,
`.env`, `.git`, `.venv`, credentials, secrets, and unsupported formats are
intentionally excluded.

## Validation

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

This software is an auditable planning baseline, not a certified industrial
control or safety system. Verify consequential schedules and safety information
against approved organizational procedures.

## Production scope

Implemented safeguards include worker/machine/vehicle conflict prevention,
multiple candidate resources and workers, blocked/unavailable resources,
shift and maintenance calendars, multi-skills and certifications, locations,
setup/travel time, precedence graphs and cycle detection, weighted priorities,
deadline tracking, operating costs, SQLite persistence, audit history, optional
role-based authentication, and human approval. The test suite covers these plus
invalid input, missing resources, unsupported documents, empty retrieval,
malformed LLM output, and an unreachable LLM.

For real deployment, place FastAPI behind an authenticated TLS reverse proxy,
rotate secrets, back up SQLite (or migrate the persistence adapter to a managed
database), restrict filesystem permissions, and validate organizational safety
and scheduling rules with domain owners.
