import json
import sys
import os
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from utils.cache import get_cached_response, save_cached_response
from utils.logger import step, agent
from utils.tracer import add_trace
from utils.prompt_loader import load_prompt
from utils.pretty_print import show_agent_output
from utils.save_output import save_agent_output

MODEL_NAME = "gpt-4o-mini"
llm = ChatOpenAI(model=MODEL_NAME, temperature=0)

REQUIRED_FIELDS = [
    "game_type", "framework", "player_controls",
    "core_mechanics", "game_loop_description", "file_structure"
]


def _extract_json(text: str) -> dict:
    text = re.sub(r"```json|```", "", text).strip()
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("Planner response contains no JSON object")
    return json.loads(match.group())


def planning_node(state: dict) -> dict:
    step("Planning Phase")

    requirements = state.get("clarified_requirements")
    if not requirements:
        raise RuntimeError("Planner received empty clarified_requirements")

    requirements_json = json.dumps(requirements, indent=2)
    prompt_template = load_prompt("planner_prompt.txt")
    prompt = prompt_template.replace("{requirements}", requirements_json)
    cache_key = f"{MODEL_NAME}:{prompt}"

    cached = get_cached_response(cache_key)
    if cached:
        raw_plan = cached
        agent("Planner cache hit")
    else:
        response = llm.invoke(prompt)
        raw_plan = response.content.strip()
        save_cached_response(cache_key, raw_plan)
        agent("Planner LLM call executed and cached")

    try:
        game_plan = _extract_json(raw_plan)

        if not isinstance(game_plan, dict):
            raise ValueError("Planner JSON must be an object")

        missing = [f for f in REQUIRED_FIELDS if f not in game_plan]
        if missing:
            raise ValueError(f"Planner JSON missing fields: {missing}")

        # Normalise framework — always vanilla_js for reliability
        fw = str(game_plan.get("framework", "")).lower()
        if fw not in ["phaser", "vanilla_js"]:
            agent(f"Unknown framework '{fw}' → forcing vanilla_js")
            fw = "vanilla_js"
        game_plan["framework"] = fw

    except Exception as exc:
        raise RuntimeError(
            f"Planner output parsing failed.\nRaw:\n{raw_plan}\nError: {exc}"
        )

    show_agent_output("planner", game_plan)
    save_agent_output("planner", game_plan)
    agent("Game architecture plan generated")
    add_trace("planning", requirements, game_plan)

    return {"game_plan": game_plan}