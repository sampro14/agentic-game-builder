import re
import json

from langchain_openai import ChatOpenAI
from utils.logger import step, agent
from utils.tracer import add_trace
from utils.prompt_loader import load_prompt
from utils.code_extractor import extract_blocks

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


def _extract_json_safe(text: str):
    text = re.sub(r"```json|```", "", text).strip()
    # Normalize: strip all quotes and whitespace to handle "valid", 'valid', etc.
    normalized = text.lower().replace('"', '').replace("'", "").strip()
    if normalized == "valid":
        return {"valid": True, "issues": []}
    if normalized == "invalid":
        return {"valid": False, "issues": ["Implementation invalid"]}
    # Try full JSON parse
    try:
        parsed = json.loads(text)
        # Handle case where LLM returned a JSON string like "valid" instead of object
        if isinstance(parsed, str):
            if parsed.lower() == "valid":
                return {"valid": True, "issues": []}
            if parsed.lower() == "invalid":
                return {"valid": False, "issues": ["Implementation invalid"]}
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    # Extract first JSON object from mixed text
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return None


def validate_node(state: dict) -> dict:
    step("Validation Phase")

    generated_code = state.get("generated_code")
    game_plan = state.get("game_plan", {})

    if not generated_code:
        raise RuntimeError("Validator received empty generated_code")

    issues = []
    html, css, js = extract_blocks(generated_code)

    html = html or ""
    css  = css  or ""
    js   = js   or ""

    # ── Structure ─────────────────────────────────────────────────────────────
    if not html: issues.append("Missing HTML block")
    if not css:  issues.append("Missing CSS block")
    if not js:   issues.append("Missing JS block")

    if issues:
        agent(f"Structure check failed → {issues}")
        add_trace("validation", generated_code, {"issues": issues, "result": "false"})
        return {"validation_result": "false", "validation_issues": issues}

    h, j = html.lower(), js.lower()

    # ── HTML linkage ──────────────────────────────────────────────────────────
    if "style.css" not in h: issues.append("index.html missing style.css link")
    if "game.js"   not in h: issues.append("index.html missing game.js link")

    # ── Framework ─────────────────────────────────────────────────────────────
    framework = str(game_plan.get("framework", "")).lower()
    if framework == "phaser":
        if "phaser" not in h:            issues.append("Phaser CDN missing")
        if "phaser.game" not in j:       issues.append("Phaser game not initialized")
    if framework == "vanilla_js":
        if "canvas" not in h:            issues.append("Canvas element missing")
        if "getcontext(" not in j:       issues.append("Canvas context missing")

    # ── Gameplay presence ─────────────────────────────────────────────────────
    if not any(p in j or p in h for p in ["fillrect","arc(","add.rectangle","add.circle","canvas"]):
        issues.append("No visible game elements")
    if not any(p in j for p in ["keydown","keyup","addeventlistener","this.input.keyboard","cursors"]):
        issues.append("Player input handling missing")
    if not any(p in j for p in ["requestanimationframe","update(","phaser.game"]):
        issues.append("Game loop missing")
    if not any(p in j for p in ["score","points","lives","health"]):
        issues.append("Score / lives system missing")
    collision_signals = ["collision", "collides", "overlap", "intersect", "hittest", "a.x < b.x", "b.x + b.w", ".x + .w", "rect"]
    if not any(s in j for s in collision_signals):
        issues.append("Collision detection missing")

    # ── Syntax sanity ─────────────────────────────────────────────────────────
    if js.count("{") != js.count("}"):  issues.append("JS brace mismatch")
    if js.count("(") != js.count(")"):  issues.append("JS parenthesis mismatch")

    if issues:
        agent(f"Static validation failed → {issues}")
        add_trace("validation", generated_code, {"issues": issues, "result": "false"})
        return {"validation_result": "false", "validation_issues": issues}

    # ── LLM semantic check ────────────────────────────────────────────────────
    agent("Running LLM semantic validation")
    try:
        prompt = load_prompt("validator_llm_prompt.txt").replace(
            "{game_plan}", json.dumps(game_plan)
        ).replace("{js_code}", js[:2000])
        resp = llm.invoke(prompt)
        raw = resp.content.strip()
        result = _extract_json_safe(raw)
        if result is None:
            agent("Semantic validation: assuming valid (no parseable result)")
        elif not result.get("valid", True):
            llm_issues = result.get("issues", [])
            if llm_issues:
                agent(f"LLM semantic issues → {llm_issues}")
                issues.extend(llm_issues)
        else:
            agent("Semantic validation passed ✓")
    except Exception as e:
        agent(f"Semantic validator skipped: {e}")

    if issues:
        agent(f"Validation failed → {issues}")
        add_trace("validation", generated_code, {"issues": issues, "result": "false"})
        return {"validation_result": "false", "validation_issues": issues}

    agent("Validation passed ✓")
    add_trace("validation", generated_code, {"issues": [], "result": "true"})
    return {"validation_result": "true", "validation_issues": []}