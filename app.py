import os
import re
import json
import time
import asyncio
from collections import defaultdict
from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

from agents.clarifier import clarify_node
from graph.workflow import graph
from utils.save_output import save_agent_output
from utils.tracer import save_trace

OUTPUT_DIR  = os.path.join(os.getcwd(), "output")
FRONTEND_DIR = os.path.join(os.getcwd(), "frontend")
os.makedirs(OUTPUT_DIR,   exist_ok=True)
os.makedirs(FRONTEND_DIR, exist_ok=True)

app = FastAPI(title="Agentic Game Builder AI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate Limiter ──────────────────────────────────────────────────────────────
# Tracks: { ip: [timestamp, timestamp, ...] }
_request_log: dict[str, list[float]] = defaultdict(list)

RATE_LIMIT_REQUESTS = 3    # max requests
RATE_LIMIT_WINDOW   = 60   # per 60 seconds
IDEA_MAX_LENGTH     = 500  # max chars for game idea input

def check_rate_limit(ip: str):
    """Raise 429 if the IP has exceeded the rate limit."""
    now   = time.time()
    cutoff = now - RATE_LIMIT_WINDOW

    # Keep only timestamps within the current window
    _request_log[ip] = [t for t in _request_log[ip] if t > cutoff]

    if len(_request_log[ip]) >= RATE_LIMIT_REQUESTS:
        oldest   = _request_log[ip][0]
        retry_in = int(RATE_LIMIT_WINDOW - (now - oldest)) + 1
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {retry_in} seconds."
        )

    _request_log[ip].append(now)


def get_client_ip(request: Request) -> str:
    """Get real IP, respecting X-Forwarded-For for reverse proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host


# ── Models ────────────────────────────────────────────────────────────────────
class IdeaRequest(BaseModel):
    idea: str

class BuildRequest(BaseModel):
    idea: str
    answers: list[str]


# ── Helpers ───────────────────────────────────────────────────────────────────
def extract_and_save_files(code_output: str) -> dict:
    html = re.search(r"```(?:html|HTML)[^\n]*\n(.*?)```", code_output, re.S)
    css  = re.search(r"```(?:css|CSS)[^\n]*\n(.*?)```",  code_output, re.S)
    js   = re.search(r"```(?:javascript|js|JS)[^\n]*\n(.*?)```", code_output, re.S)
    if not (html and css and js):
        raise RuntimeError("Generated code missing HTML/CSS/JS blocks")
    files = {
        "index.html": html.group(1).strip(),
        "style.css":  css.group(1).strip(),
        "game.js":    js.group(1).strip(),
    }
    for fname, content in files.items():
        with open(os.path.join(OUTPUT_DIR, fname), "w", encoding="utf-8") as f:
            f.write(content)
    return files


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "running"}


@app.post("/clarify")
def clarify(req: IdeaRequest, request: Request):
    # Validate input length
    if len(req.idea.strip()) == 0:
        raise HTTPException(status_code=400, detail="Game idea cannot be empty.")
    if len(req.idea) > IDEA_MAX_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Game idea too long. Max {IDEA_MAX_LENGTH} characters."
        )
    try:
        state = {
            "user_input": req.idea,
            "clarifying_questions": None,
            "clarified_requirements": None,
            "answers": [],
            "question_index": 0,
            "iteration": 0,
        }
        result = clarify_node(state)
        questions   = result.get("clarifying_questions") or []
        already_clear = bool(result.get("clarified_requirements"))
        return {"questions": questions, "already_clear": already_clear}
    except HTTPException:
        raise
    except Exception as exc:
        return {"error": str(exc)}


@app.post("/build/stream")
async def build_stream(req: BuildRequest, request: Request):
    # ── Rate limit check ──────────────────────────────────────────────────────
    ip = get_client_ip(request)
    check_rate_limit(ip)

    # ── Input validation ──────────────────────────────────────────────────────
    if len(req.idea.strip()) == 0:
        raise HTTPException(status_code=400, detail="Game idea cannot be empty.")
    if len(req.idea) > IDEA_MAX_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Game idea too long. Max {IDEA_MAX_LENGTH} characters."
        )
    if len(req.answers) > 10:
        raise HTTPException(status_code=400, detail="Too many answers.")

    async def generate():
        loop = asyncio.get_event_loop()

        yield sse("progress", {"phase": "clarify", "message": "✦ Analysing requirements…"})
        await asyncio.sleep(0)

        state = {
            "user_input":              req.idea,
            "clarifying_questions":    None,
            "clarified_requirements":  None,
            "answers":                 req.answers,
            "question_index":          0,
            "game_plan":               None,
            "generated_code":          None,
            "validation_result":       None,
            "validation_issues":       None,
            "iteration":               0,
        }

        try:
            yield sse("progress", {"phase": "plan", "message": "📋 Planning game architecture…"})
            await asyncio.sleep(0)

            result = await loop.run_in_executor(None, graph.invoke, state)

            # ── Plan output ───────────────────────────────────────────────────
            game_plan = result.get("game_plan") or {}
            if game_plan:
                yield sse("plan_output", {
                    "game_type": game_plan.get("game_type", ""),
                    "framework": game_plan.get("framework", ""),
                    "controls":  game_plan.get("player_controls", {}).get("description", ""),
                    "mechanics": game_plan.get("core_mechanics", []),
                    "game_loop": game_plan.get("game_loop_description", ""),
                })
                await asyncio.sleep(0)

            yield sse("progress", {"phase": "build", "message": "⚙️  Generating game code…"})
            await asyncio.sleep(0)

            # ── Validation output ─────────────────────────────────────────────
            val_result = result.get("validation_result", "")
            val_issues = result.get("validation_issues", [])
            iterations = result.get("iteration", 0)
            passed     = "true" in str(val_result).lower()

            yield sse("validation_output", {
                "passed":     passed,
                "issues":     val_issues,
                "iterations": iterations,
            })
            await asyncio.sleep(0)

            yield sse("progress", {
                "phase":   "validate",
                "message": f"{'✓ Validation passed' if passed else f'🔧 Repair applied ({iterations} pass)'}"
            })
            await asyncio.sleep(0)

            # ── Files ─────────────────────────────────────────────────────────
            code = result.get("generated_code")
            if not code:
                yield sse("error", {"message": "No code generated"})
                return

            files = extract_and_save_files(code)
            save_agent_output("builder", code)
            save_trace()

            yield sse("done", {
                "files":             files,
                "validation_result": val_result,
                "validation_issues": val_issues,
                "iterations":        iterations,
            })

        except Exception as exc:
            yield sse("error", {"message": str(exc)})

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/build")
def build_game(req: BuildRequest, request: Request):
    ip = get_client_ip(request)
    check_rate_limit(ip)

    try:
        state = {
            "user_input":             req.idea,
            "clarifying_questions":   None,
            "clarified_requirements": None,
            "answers":                req.answers,
            "question_index":         0,
            "game_plan":              None,
            "generated_code":         None,
            "validation_result":      None,
            "validation_issues":      None,
            "iteration":              0,
        }
        result = graph.invoke(state)
        code = result.get("generated_code")
        if not code:
            return {"error": "Game generation failed"}
        files = extract_and_save_files(code)
        save_agent_output("builder", code)
        save_trace()
        return {
            "files":             files,
            "validation_result": result.get("validation_result"),
            "validation_issues": result.get("validation_issues", []),
            "iterations":        result.get("iteration", 0),
        }
    except HTTPException:
        raise
    except Exception as exc:
        return {"error": str(exc)}


# ── Static files ──────────────────────────────────────────────────────────────
app.mount("/output", StaticFiles(directory=OUTPUT_DIR),              name="output")
app.mount("/",       StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")