import os
import sys
import json
import hashlib

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from utils.logger import step, agent
from utils.tracer import add_trace
from utils.cache import get_cached_response, save_cached_response
from utils.prompt_loader import load_prompt
from utils.pretty_print import show_agent_output
from utils.save_output import save_agent_output
from utils.code_extractor import extract_blocks, require_blocks

MODEL_NAME = "gpt-4o-mini"
llm = ChatOpenAI(model=MODEL_NAME, temperature=0.2)


def _is_valid_candidate(html: str, css: str, js: str, framework: str) -> tuple[bool, str]:
    """Run quick sanity checks; return (ok, reason)."""
    h, j = html.lower(), js.lower()

    if framework == "vanilla_js":
        if "canvas" not in h:
            return False, "Canvas element missing from HTML"
        if "getcontext" not in j:
            return False, "Canvas context (getContext) missing"

    if framework == "phaser":
        if "phaser" not in h:
            return False, "Phaser CDN missing from HTML"
        if "new phaser.game" not in j:
            return False, "Phaser.Game not instantiated"

    loop_signals = ["requestanimationframe", "update(", "scene.update", "phaser.game"]
    if not any(s in j for s in loop_signals):
        return False, "Game loop missing"

    input_signals = ["keydown", "keyup", "addeventlistener", "this.input.keyboard", "cursors"]
    if not any(s in j for s in input_signals):
        return False, "Player input missing"

    render_signals = ["fillrect", "arc(", "add.rectangle", "add.circle", "add.graphics", "filltext"]
    if not any(s in j or s in h for s in render_signals):
        return False, "No visible rendered objects"

    score_signals = ["score", "points", "lives", "health"]
    if not any(s in j for s in score_signals):
        return False, "Score / lives system missing"

    return True, "ok"


def build_node(state: dict) -> dict:
    step("Builder Phase")

    game_plan = state.get("game_plan")
    if not game_plan:
        raise RuntimeError("Builder received empty game_plan")

    compact_plan = {
        "type": game_plan.get("game_type"),
        "framework": game_plan.get("framework", "vanilla_js"),
        "controls": game_plan.get("player_controls"),
        "mechanics": game_plan.get("core_mechanics"),
    }
    if compact_plan["framework"] not in ["phaser", "vanilla_js"]:
        compact_plan["framework"] = "vanilla_js"
        agent("Unknown framework → forcing vanilla_js")

    plan_json = json.dumps(compact_plan, separators=(",", ":"))
    prompt_template = load_prompt("builder_prompt.txt")
    prompt = prompt_template.replace("{game_plan}", plan_json)
    cache_key = hashlib.sha256(prompt.encode()).hexdigest()

    cached = get_cached_response(cache_key)
    if cached:
        agent("Builder cache hit")
        generated_code = cached
    else:
        generated_code = None
        for attempt in range(1, 4):
            agent(f"Builder LLM call (attempt {attempt})")
            response = llm.invoke(prompt)
            candidate = response.content.strip()

            html, css, js = extract_blocks(candidate)
            if not (html and css and js):
                agent("Missing code blocks → retrying")
                continue

            ok, reason = _is_valid_candidate(
                html, css, js, compact_plan["framework"]
            )
            if not ok:
                agent(f"Validation check failed: {reason} → retrying")
                continue

            generated_code = candidate
            save_cached_response(cache_key, generated_code)
            agent(f"Builder succeeded on attempt {attempt}")
            break

        if not generated_code:
            raise RuntimeError(
                "Builder failed to produce valid HTML/CSS/JS after 3 attempts"
            )

    # Final safety check
    require_blocks(generated_code)

    show_agent_output("builder", generated_code)
    save_agent_output("builder", generated_code)
    add_trace("builder", compact_plan, generated_code)

    return {"generated_code": generated_code}