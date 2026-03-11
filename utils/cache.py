import json
import os
import hashlib

CACHE_DIR = ".cache"
CACHE_FILE = os.path.join(CACHE_DIR, "llm_cache.json")


def _ensure_cache():
    os.makedirs(CACHE_DIR, exist_ok=True)
    if not os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "w") as f:
            json.dump({}, f)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def get_cached_response(prompt: str):
    _ensure_cache()
    with open(CACHE_FILE, "r") as f:
        cache = json.load(f)
    return cache.get(_hash(prompt))


def save_cached_response(prompt: str, response: str):
    _ensure_cache()
    with open(CACHE_FILE, "r") as f:
        cache = json.load(f)
    cache[_hash(prompt)] = response
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)
