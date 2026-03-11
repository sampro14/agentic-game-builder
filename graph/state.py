from typing import TypedDict, Optional, List, Dict


class GameState(TypedDict, total=False):

    # User input
    user_input: str

    # Clarification phase
    clarifying_questions: Optional[List[str]]
    question_index: Optional[int]
    answers: Optional[List[str]]
    clarified_requirements: Optional[Dict]

    # Planning phase
    game_plan: Optional[Dict]

    # Builder output
    generated_code: Optional[str]
    generated_files: Optional[Dict[str, str]]

    # Validation phase
    validation_result: Optional[str]
    validation_issues: Optional[List[str]]

    # Repair loop
    iteration: Optional[int]

    # Debug / trace
    logs: Optional[List[str]]