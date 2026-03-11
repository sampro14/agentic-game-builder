import os
import sys
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from utils.logger import step, agent
from utils.tracer import add_trace
from utils.prompt_loader import load_prompt
from utils.code_extractor import extract_blocks, require_blocks

MODEL_NAME = "gpt-4o-mini"
llm = ChatOpenAI(model=MODEL_NAME, temperature=0)


def repair_node(state: dict) -> dict:
    step("Repair Phase")

    generated_code = state.get("generated_code")
    issues = state.get("validation_issues", [])
    game_plan = state.get("game_plan", {})

    if not generated_code:
        raise RuntimeError("Repair agent received empty generated_code")

    if not issues:
        agent("No issues → skipping repair")
        return {"generated_code": generated_code}

    agent(f"Fixing {len(issues)} issue(s): {issues}")

    prompt_template = load_prompt("repair_prompt.txt")
    base_prompt = prompt_template.format(
        issues=json.dumps(issues, indent=2),
        code=generated_code,
        game_plan=json.dumps(game_plan),
    )

    repaired_code = None
    for attempt in range(1, 3):
        agent(f"Repair LLM call (attempt {attempt})")
        suffix = (
            f"\n\nRepair attempt {attempt}. Fix ALL listed issues. "
            "Return exactly three code blocks: html, css, javascript. No explanations."
        )
        response = llm.invoke(base_prompt + suffix)
        candidate = response.content.strip()
        html, css, js = extract_blocks(candidate)
        if html and css and js:
            repaired_code = candidate
            agent(f"Repair succeeded on attempt {attempt}")
            break
        agent("Malformed repair output → retrying")

    if not repaired_code:
        agent("Repair failed — returning original code for final delivery")
        return {"generated_code": generated_code}

    require_blocks(repaired_code)
    add_trace("repair", {"issues": issues, "framework": game_plan.get("framework")}, repaired_code)

    return {"generated_code": repaired_code}
