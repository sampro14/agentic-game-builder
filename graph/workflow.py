from langgraph.graph import StateGraph, END

from graph.state import GameState
from agents.clarifier import clarify_node
from agents.planner import planning_node
from agents.builder import build_node
from agents.validator import validate_node
from agents.repair import repair_node
from utils.logger import info


# --------------------------------
# Clarification Router
# --------------------------------
def clarification_router(state):
    if state.get("clarified_requirements"):
        info("Requirements clarified → moving to planning")
        return "plan"
    info("More clarification needed")
    return "clarify"


# --------------------------------
# Validation Router
# --------------------------------
def validation_router(state):
    result = str(state.get("validation_result", "")).lower()
    iteration = state.get("iteration", 0)

    if any(x in result for x in ["true", "valid", "pass"]):
        info("Validation passed ✓")
        return "end"

    if iteration >= 2:
        info("Max repair attempts reached → delivering best output")
        return "end"

    info(f"Validation failed → repair attempt {iteration + 1}")
    return "repair"


# --------------------------------
# Repair wrapper — tracks iteration
# --------------------------------
def repair_with_iteration(state):
    iteration = state.get("iteration", 0) + 1
    info(f"Repair attempt #{iteration}")
    repaired = repair_node(state)
    return {**repaired, "iteration": iteration}


# --------------------------------
# Build Graph
# --------------------------------
builder = StateGraph(GameState)

builder.add_node("clarify", clarify_node)
builder.add_node("plan", planning_node)
builder.add_node("build", build_node)
builder.add_node("validate", validate_node)
builder.add_node("repair", repair_with_iteration)

builder.set_entry_point("clarify")

builder.add_conditional_edges(
    "clarify",
    clarification_router,
    {"clarify": "clarify", "plan": "plan"}
)

builder.add_edge("plan", "build")
builder.add_edge("build", "validate")

builder.add_conditional_edges(
    "validate",
    validation_router,
    {"repair": "repair", "end": END}
)

builder.add_edge("repair", "validate")

graph = builder.compile()
