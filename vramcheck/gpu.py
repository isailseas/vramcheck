import json
import os
from difflib import get_close_matches
from typing import Optional

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gpus.json")


def load_gpu_db() -> dict:
    with open(DATA_PATH) as f:
        return json.load(f)


def find_gpu(name: str) -> Optional[dict]:
    """
    Look up a GPU by name. Case-insensitive, fuzzy-matched.
    Returns dict with vram_gb, bandwidth_gbps, and name keys, or None.
    """
    db = load_gpu_db()
    query = name.lower().strip()

    all_gpus = {}
    for vendor, gpus in db.items():
        for gpu_name, specs in gpus.items():
            all_gpus[gpu_name] = {**specs, "name": gpu_name, "vendor": vendor}

    if query in all_gpus:
        return all_gpus[query]

    matches = get_close_matches(query, all_gpus.keys(), n=1, cutoff=0.6)
    if matches:
        return all_gpus[matches[0]]

    for gpu_name in all_gpus:
        if query in gpu_name or gpu_name in query:
            return all_gpus[gpu_name]

    return None


def list_gpus() -> list[str]:
    db = load_gpu_db()
    names = []
    for vendor, gpus in db.items():
        for name in gpus:
            names.append(f"{vendor.upper()}: {name}")
    return sorted(names)
