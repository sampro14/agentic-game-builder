from datetime import datetime


def _ts():
    return datetime.now().strftime("%H:%M:%S")

def info(msg: str):    print(f"[{_ts()}] [INFO]    {msg}")
def step(msg: str):    print(f"\n{'='*60}\n[{_ts()}] [STEP]    {msg}\n{'='*60}")
def agent(msg: str):   print(f"[{_ts()}] [AGENT]   {msg}")
def success(msg: str): print(f"[{_ts()}] [SUCCESS] {msg}")
def warning(msg: str): print(f"[{_ts()}] [WARNING] {msg}")
def error(msg: str):   print(f"[{_ts()}] [ERROR]   {msg}")
