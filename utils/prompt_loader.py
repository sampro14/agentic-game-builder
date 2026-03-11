import os


def load_prompt(filename: str) -> str:
    base_dir = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(base_dir, "prompts", filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
