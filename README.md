# Private Local Industrial Planning Agent

This project combines a deterministic resource-constrained scheduler with a
locally hosted Kimi-compatible model. Planning files and document excerpts stay
on the machine: the application contains no cloud LLM client, web search, remote
embedding call, telemetry, or automatic model download.

The model provides a natural-language interface and explains results. Python
creates the actual schedule, validates inputs, prevents resource overlap, and
reports infeasible tasks.

## Privacy boundary

- The LLM URL must use an explicit loopback IP (`127.0.0.0/8` or `::1`).
- Hostnames and non-loopback addresses are rejected, preventing accidental cloud
  configuration and DNS rebinding.
- Retrieval is local lexical search; no document is sent to an embedding API.
- Workspace chat is read-only and cannot execute commands or edit files.
- `.env`, `.git`, `.venv`, `credentials`, `secrets`, symlinks, unsupported files,
  and files larger than 5 MB are not indexed.
- Only the most relevant local excerpts are sent to the model process running on
  the same computer.

Network isolation for the whole machine remains an operating-system concern. For
the strongest assurance, block the model server and Python executable from
outbound network access with the host firewall after installing the required
software and model weights.

## Components

- Excel scheduler for workers, tasks, machines, vehicles, precedence, priorities,
  and deadlines
- PSPLIB single-mode parser and serial RCPSP scheduler
- Local readers for PDF, Word, Excel, CSV, JSON, Markdown, text, YAML, and Python
- Local TF-IDF-style document retrieval without embeddings
- OpenAI-compatible loopback client for Ollama, vLLM, or another local server
- Interactive read-only workspace chat
- Responsive React interface served locally by FastAPI
- Streaming progress states and elapsed-time reporting for requests over 10 seconds

## Installation

```powershell
cd C:\Users\USER\OneDrive\Desktop\projects\industrial_planning_agent
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

The verified configuration uses Ollama with Kimi-VL A3B Thinking Q5. Install
Ollama, pull the model, and create the VRAM-safe local profile:

```powershell
ollama pull richardyoung/kimi-vl-a3b-thinking:Q5_K_M
ollama create planning-kimi --file models/Kimi.Modelfile
```

This is a community GGUF quantization of Moonshot AI's open Kimi-VL model. It is
approximately 12 GB. The included profile caps context at 8K tokens so it runs
reliably on a 16 GB GPU while retaining enough room for retrieved document
excerpts and recent conversation history.

Ollama exposes its OpenAI-compatible API only on the expected loopback endpoint:

```text
http://127.0.0.1:11434/v1
```

The model weights are stored by Ollama outside this repository and are never
committed to GitHub.

## Create a schedule

Create an example workbook:

```powershell
python scripts/create_example_workbook.py
```

Use the local model to understand and explain a request:

```powershell
python -m planning_agent.cli `
  --llm-url http://127.0.0.1:11434/v1 `
  --model kimi `
  schedule `
  --workbook data/planning.xlsx `
  --workspace documents `
  --request "Plan all work. CNC-02 is unavailable. What does the local SOP say about welding PPE?"
```

Run the deterministic scheduler without any model server:

```powershell
python -m planning_agent.cli schedule `
  --workbook data/planning.xlsx `
  --blocked-machine CNC-02 `
  --no-llm
```

## Private workspace chat

### Local web application

Build the interface once and start the loopback-only server:

```powershell
cd web
npm install
npm run build
cd ..
.venv\Scripts\python.exe scripts\run_web.py
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000). FastAPI serves the
compiled React interface and the local API from the same origin. It never binds
to the LAN. The interface provides:

- responsive desktop and mobile layouts;
- interactive chat history held only in browser memory;
- fast in-memory indexed lookup;
- cited local file sources;
- a workspace refresh control;
- staged loading feedback; and
- a live elapsed-time indicator after 10 seconds, with final duration reporting.

Close the terminal or press `Ctrl+C` to stop the application. The browser UI has
no external fonts, analytics, scripts, images, or CDN dependencies.

### Terminal interface

Start an interactive session over an explicitly selected directory:

```powershell
python -m planning_agent.cli `
  --model kimi `
  chat `
  --workspace C:\path\to\approved\work-files
```

Or ask one question:

```powershell
python -m planning_agent.cli --model kimi chat `
  --workspace documents `
  --question "What PPE requirements are stated for welding?"
```

Answers cite the local filename and page, sheet, or document location. If retrieval
does not find adequate evidence, the model is instructed to say so.

## PSPLIB

```powershell
python -m planning_agent.cli psplib --instance data/j30.sm
```

PSPLIB capacities are handled separately from named industrial workers and
machines.

## Excel schema

Required sheets and columns:

- `Workers`: `Worker`, `Skill`, `Available`
- `Machines`: `Machine`, `Type`, `Available`
- `Tasks`: `Task`, `Duration_Hours`, `Priority`, `Deadline_Days`,
  `Required_Skill`, `Workers_Needed`, `Machine_Type`

Optional task columns are `Predecessors` and `Vehicle_Type`. When vehicles are
required, add a `Vehicles` sheet containing `Vehicle`, `Type`, and `Available`.

## Docker

Docker remains optional. The supplied Compose service is network-isolated and
runs only the `--no-llm` scheduler. Run the local Kimi workflow directly on the
host so its loopback-only endpoint remains enforceable.

## Tests

```powershell
python -m unittest discover -s tests -v
```

This remains an auditable baseline, not a certified industrial control system.
Production use still needs real shifts, maintenance windows, setup/travel time,
permissions, approvals, and organization-specific safety validation.
