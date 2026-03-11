import sys
import os
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from utils.logger import step, agent
from utils.tracer import add_trace
from utils.prompt_loader import load_prompt
from utils.pretty_print import show_agent_output
from utils.save_output import save_agent_output
from utils.cache import get_cached_response, save_cached_response

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


def _normalize_game_type(idea: str) -> str:
    for word in ["build", "create", "make", "game", "a", "an", "the"]:
        idea = re.sub(rf"\b{word}\b", "", idea, flags=re.IGNORECASE)
    return idea.strip()


def _build_requirements(idea: str, answers: list, questions: list = None) -> dict:
    # Pair questions with answers so the planner gets full context
    qa_context = ""
    if questions and answers:
        qa_context = " | ".join(
            f"{q.strip()}: {a.strip()}"
            for q, a in zip(questions, answers)
            if a.strip()
        )
    full_desc = f"{idea}. {qa_context}" if qa_context else idea
    return {
        "game_name": _normalize_game_type(idea),
        "original_idea": idea,
        "full_description": full_desc,
        "qa_context": qa_context,
        "framework": "vanilla_js",
        "platform": "browser",
        "controls":      answers[0] if len(answers) > 0 else "arrow keys",
        "objective":     answers[1] if len(answers) > 1 else "survive and score points",
        "obstacles":     answers[2] if len(answers) > 2 else "falling objects",
        "win_condition":  answers[1] if len(answers) > 1 else "score target reached",
        "lose_condition": "player collision or health zero",
        "entities": ["player", "enemy", "projectile"],
    }


def clarify_node(state: dict) -> dict:
    step("Clarification Phase")

    idea           = state["user_input"]
    questions      = state.get("clarifying_questions")
    answers        = list(state.get("answers") or [])
    question_index = state.get("question_index", 0)

    # API mode = answers already provided by the web UI (no terminal prompting)
    api_mode = len(answers) > 0

    # ── Step 1: Generate clarifying questions ─────────────────────────────────
    if not questions:
        prompt_template = load_prompt("clarifier_prompt.txt")
        prompt = prompt_template.format(idea=idea)

        cached = get_cached_response(prompt)
        if cached:
            questions_raw = cached
            agent("Cache hit → clarification reused")
        else:
            response = llm.invoke(prompt)
            questions_raw = response.content.strip()
            save_cached_response(prompt, questions_raw)
            agent("LLM call → clarification cached")

        # Idea fully specified — skip Q&A
        if "NO_CLARIFICATION_REQUIRED" in questions_raw:
            agent("Idea already clear → skipping clarification")
            reqs = _build_requirements(idea, answers)
            show_agent_output("clarifier", reqs)
            save_agent_output("clarifier", reqs)
            add_trace("clarification_skipped", idea, reqs)
            return {"clarified_requirements": reqs, "clarifying_questions": None}

        # Extract numbered questions
        question_list = re.findall(r"\d+\s*[\.\)]\s*(.*)", questions_raw)
        if not question_list:
            question_list = [q.strip() for q in questions_raw.split("\n") if q.strip()]
        if not question_list:
            raise RuntimeError("Clarifier failed to generate questions")

        question_list = question_list[:3]
        agent(f"{len(question_list)} clarification questions generated")
        add_trace("clarification_questions", idea, {"questions": question_list})

        # API mode: answers already supplied — build requirements immediately
        # NEVER call input() when running under the web server
        if api_mode:
            agent("API mode — using pre-supplied answers")
            reqs = _build_requirements(idea, answers)
            show_agent_output("clarifier", reqs)
            save_agent_output("clarifier", reqs)
            add_trace("clarification_complete", idea, reqs)
            return {"clarified_requirements": reqs, "clarifying_questions": None}

        # CLI mode: store questions, loop back for interactive input
        return {
            "clarifying_questions": question_list,
            "answers": [],
            "question_index": 0,
        }

    # ── Step 2: CLI only — ask one question at a time via terminal ────────────
    if question_index < len(questions):
        next_q = questions[question_index]
        agent(f"Asking question {question_index + 1}/{len(questions)}")
        print(f"\n  Q{question_index + 1}: {next_q}")
        user_answer = input("  > ").strip() or "not specified"
        answers.append(user_answer)
        return {
            "answers": answers,
            "question_index": question_index + 1,
            "clarifying_questions": questions,
        }

    # ── Step 3: All CLI answers collected — build requirements ────────────────
    reqs = _build_requirements(idea, answers)
    agent("Clarification complete → requirements structured")
    show_agent_output("clarifier", reqs)
    save_agent_output("clarifier", reqs)
    add_trace("clarification_complete", idea, reqs)
    return {"clarified_requirements": reqs, "clarifying_questions": None}