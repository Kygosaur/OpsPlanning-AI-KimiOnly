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

Kimi does not decide the final resource allocation. Python creates and validates
the schedule, preventing overlapping assignments and reporting tasks that cannot
be scheduled.

## How the local system works

```text
Browser at 127.0.0.1:8000
          |
          v
React interface -> FastAPI -> local file index
                         \-> Ollama -> planning-kimi on the GPU
```

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

Supported planning workbook sheets:

- `Workers`: `Worker`, `Skill`, `Available`
- `Machines`: `Machine`, `Type`, `Available`
- `Tasks`: `Task`, `Duration_Hours`, `Priority`, `Deadline_Days`,
  `Required_Skill`, `Workers_Needed`, `Machine_Type`
- Optional `Vehicles`: `Vehicle`, `Type`, `Available`

Tasks may also contain `Predecessors` and `Vehicle_Type` columns.

## 4. Start the web application

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
