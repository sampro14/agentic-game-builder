import json
import os
from datetime import datetime

_trace_data = []


def add_trace(step: str, input_data, output_data):
    _trace_data.append({
        "timestamp": datetime.now().isoformat(),
        "step": step,
        "input": str(input_data)[:500],
        "output": str(output_data)[:500],
    })


def save_trace():
    os.makedirs("debug", exist_ok=True)
    with open("debug/trace.json", "w", encoding="utf-8") as f:
        json.dump(_trace_data, f, indent=2)


def clear_trace():
    global _trace_data
    _trace_data = []
