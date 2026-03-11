# 🎮 Agentic Game Builder AI

An agentic AI system that accepts a natural-language game idea and autonomously produces a fully playable browser game (HTML + CSS + JS) through a multi-phase pipeline: **Clarify → Plan → Build → Validate → Repair**.

---

## Table of Contents

1. [How to Run the Agent](#how-to-run-the-agent)
2. [Docker Build & Run Instructions](#docker-build--run-instructions)
3. [Agent Architecture](#agent-architecture)
4. [Trade-offs Made](#trade-offs-made)
5. [Improvements With More Time](#improvements-with-more-time)

---

## How to Run the Agent

### Prerequisites

- Docker (recommended) **or** Python 3.12+
- An OpenAI API key (`gpt-4o-mini`)

### Option A — Docker (recommended)

See [Docker Build & Run Instructions](#docker-build--run-instructions) below.

### Option B — Local Python

```bash
# 1. Clone the repo
git clone <repo-url>
cd agentic-game-builder

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your API key
cp .env.example .env
# Edit .env and add: OPENAI_API_KEY=sk-...

# 5a. Run the web UI (recommended)
uvicorn app:app --reload
# Open http://localhost:8000

# 5b. Or run the CLI mode
python main.py
```

### Using the Web UI

1. Open `http://localhost:8000`
2. Enter a game idea (e.g. *"A space shooter where I fly a rocket and shoot asteroids"*)
3. Click **Analyse Idea** — the agent asks up to 3 clarifying questions
4. Answer the questions, then click **Build Game**
5. Watch the pipeline run live in the **Agent Log** tab
6. View the generated plan in **🗺 Game Plan**, validation results in **✅ Validation**
7. Play the game in **🎮 Preview** or download the files

---

## Docker Build & Run Instructions

### Build the image

```bash
docker build -t game-builder-agent .
```

### Run with Docker (web UI mode)

```bash
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=sk-your-key-here \
  -v $(pwd)/output:/app/output \
  game-builder-agent
```

Then open **http://localhost:8000** in your browser.

> **Windows PowerShell:** replace `$(pwd)` with `${PWD}`

### Run with Docker Compose

```bash
# Set your key in the environment or a .env file
export OPENAI_API_KEY=sk-your-key-here

docker compose up --build
```

Output files (index.html, style.css, game.js) are saved to `./output/` on your host machine via the volume mount.

### Run in CLI mode (no browser needed)

```bash
docker run -it \
  -e OPENAI_API_KEY=sk-your-key-here \
  -v $(pwd)/output:/app/output \
  game-builder-agent \
  python main.py
```

The CLI will prompt you for a game idea, ask clarifying questions interactively, then write the game files to `/app/output/`.

---

## Agent Architecture

The system is built with **LangGraph** — a stateful graph orchestration framework — on top of **LangChain + OpenAI**. The backend is **FastAPI** with Server-Sent Events (SSE) for real-time streaming to the browser UI.

### Pipeline Overview

```
User Input (natural language)
        │
        ▼
┌───────────────┐
│   CLARIFIER   │  ← Generates up to 3 targeted questions
│               │    Loops until requirements are clear
└──────┬────────┘
       │  clarified_requirements
       ▼
┌───────────────┐
│    PLANNER    │  ← Produces structured JSON game plan:
│               │    mechanics, controls, entities, loop
└──────┬────────┘
       │  game_plan
       ▼
┌───────────────┐
│    BUILDER    │  ← Generates index.html + style.css + game.js
│               │    3 retry attempts if output is malformed
└──────┬────────┘
       │  generated_code
       ▼
┌───────────────┐
│   VALIDATOR   │  ← Static checks (canvas, game loop, input,
│               │    collision, score, HUD) + LLM semantic check
└──────┬────────┘
       │  validation_result
    pass│      │fail (max 2 repairs)
       │       ▼
       │  ┌──────────┐
       │  │  REPAIR  │  ← Targeted fix using issues list
       │  └────┬─────┘
       │       │
       └───────┘
        │
        ▼
   Generated Game Files
   (index.html, style.css, game.js)
```

### Components

| Component | File | Responsibility |
|---|---|---|
| **State** | `graph/state.py` | Typed shared state (`GameState` TypedDict) passed between all nodes |
| **Workflow** | `graph/workflow.py` | LangGraph `StateGraph` — defines nodes, edges, conditional routing |
| **Clarifier** | `agents/clarifier.py` | Generates questions from idea; detects when requirements are complete; API-safe (no `input()` in web mode) |
| **Planner** | `agents/planner.py` | Converts requirements into structured JSON game plan with concrete sizes, speeds, spawn rates |
| **Builder** | `agents/builder.py` | Generates three code blocks (HTML/CSS/JS) from plan; validates structure; retries up to 3× |
| **Validator** | `agents/validator.py` | 10-point static check + optional LLM semantic check; returns issues list |
| **Repair** | `agents/repair.py` | Receives issues list; surgically fixes only the broken parts; max 2 iterations |
| **Server** | `app.py` | FastAPI: `/clarify` and `/build/stream` (SSE) endpoints |
| **Frontend** | `frontend/index.html` | Single-file UI: 5-tab panel (Log · Plan · Validation · Preview · Source) |
| **Cache** | `utils/cache.py` | SHA-256 prompt cache — avoids re-calling the LLM for identical inputs during development |
| **Tracer** | `utils/tracer.py` | Saves per-run JSON traces to `debug/trace.json` for debugging |

### Key Design Decisions

**LangGraph for orchestration** — the clarification loop and repair loop are naturally expressed as graph edges with conditional routing. The `clarification_router` sends state back to the clarify node until `clarified_requirements` is populated. The `validation_router` sends to repair up to 2 times before forcing `END`.

**Prompt-based code generation** — the builder prompt includes a fully-implemented working game as a structural template. This dramatically reduces hallucination of placeholder comments vs. real code.

**API mode detection in clarifier** — when answers are pre-supplied by the web UI, the clarifier detects `len(answers) > 0` and skips all `input()` calls, building requirements immediately from the Q&A pairs. This makes the same agent work in both CLI and web contexts.

**SSE streaming** — the `/build/stream` endpoint runs the LangGraph pipeline in a thread pool (`run_in_executor`) and yields SSE events at each phase. The frontend receives `plan_output` and `validation_output` events separately, populating different tabs in real time.

---

## Trade-offs Made

**Speed vs. quality — `gpt-4o-mini` over `gpt-4o`**
The full pipeline (clarify → plan → build → validate) takes ~30-60 seconds with `gpt-4o-mini`. Switching to `gpt-4o` would improve code quality and reduce repair cycles, but at ~10× the cost per run. For a dev/demo tool, `gpt-4o-mini` is the right default.

**Static validation over execution sandbox**
The validator checks for the presence of required patterns (canvas, game loop, collision, HUD) rather than actually running the JavaScript. A proper sandbox (headless Chromium, Playwright) would catch runtime errors that static analysis misses. The trade-off was implementation time vs. robustness — static checks catch ~80% of issues in practice.

**Prompt template vs. fine-tuning**
All agent behaviour is driven by prompt instructions rather than a fine-tuned model. This means prompt changes directly affect output quality and requires careful iteration. Fine-tuning on game examples would produce more consistent outputs but requires labelled data and retraining infrastructure.

**Single-file frontend**
The entire UI is one HTML file with inline CSS and JS. This makes deployment trivially simple (just serve the file) but sacrifices maintainability. A React/Vue frontend would be cleaner at scale.

**LLM response caching**
Identical prompts return cached responses during development. This is invaluable for iteration speed but must be cleared between serious test runs. In production this cache would be disabled or scoped per session.

**Max 2 repair iterations**
The repair loop is capped at 2 to avoid runaway API costs. In some cases a third repair pass would fix remaining issues. The cap is a cost/reliability trade-off.

---

## Improvements With More Time

**1. JavaScript execution sandbox**
Run the generated game.js in a headless browser (Playwright/Puppeteer) and check for: runtime exceptions, canvas draws occurring, input events responding. This would catch bugs that static analysis can't — like a syntax error in a function that only runs on collision.

**2. Richer game variety**
The current planner always selects `vanilla_js`. With more time I'd add: proper Phaser 3 support with scene management, a game-type classifier that selects the best framework per genre, and genre-specific builder prompts (platformer, puzzle, RPG).

**3. Streaming per-agent logs to the UI**
Currently the LangGraph graph runs in a thread pool and only SSE events at phase boundaries. With more time I'd pipe each agent's `logger` output directly to the SSE stream so the UI shows live token-by-token generation and per-agent output cards in real time.

**4. Multi-turn repair with user feedback**
After delivery, allow the user to type "the shooting doesn't work" and route back into the repair agent with their natural-language feedback, creating a true iterative co-development loop.

**5. Asset generation**
Integrate DALL-E or SVG generation to produce actual sprite images rather than coloured rectangles. This would dramatically improve the visual quality of generated games.

**6. Persistent session storage**
Save each build (idea, plan, code, validation result) to a database. Let users browse and replay previous builds, fork them with modifications, or share links.

**7. Automated test suite for the agent**
A regression suite of 20–30 game ideas with expected validation outcomes, run on every prompt change. This would prevent the repeated "validator breaking on valid code" issues encountered during development.
