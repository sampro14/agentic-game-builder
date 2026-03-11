import json
import os
from datetime import datetime

RUN_DIR = "runs"


def save_agent_output(agent_name: str, data) -> str:
    os.makedirs(RUN_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"{RUN_DIR}/{ts}_{agent_name}.json"
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(data, dict):
            json.dump(data, f, indent=2)
        else:
            f.write(str(data))
    return path
