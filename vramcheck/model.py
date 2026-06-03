import json
import os
import re
import urllib.request
import urllib.error
from typing import Optional

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "models.json")

OVERHEAD_BUFFER = 0.5  # GB reserved for OS / driver / KV cache base


def load_model_db() -> dict:
    with open(DATA_PATH) as f:
        return json.load(f)


def parse_model_name(model_str: str) -> tuple[str, Optional[float]]:
    """
    Parse a model string like 'llama3:8b', 'mistral:7b-instruct', or a raw param count.
    Returns (normalised_key, param_billions or None).
    """
    model_str = model_str.lower().strip()

    param_match = re.search(r"(\d+\.?\d*)\s*b\b", model_str)
    params = float(param_match.group(1)) if param_match else None

    key = re.sub(r"\s+", "", model_str)
    return key, params


def resolve_model(model_str: str) -> dict:
    """
    Resolve a model string to a {name, params_b, source} dict.
    Falls back to param extraction if not in the known list.
    """
    db = load_model_db()
    known = db["known_models"]

    key, params = parse_model_name(model_str)

    if key in known:
        entry = known[key]
        return {"name": key, "params_b": entry["params_b"], "hf_id": entry.get("hf_id"), "source": "db"}

    from difflib import get_close_matches
    matches = get_close_matches(key, known.keys(), n=1, cutoff=0.7)
    if matches:
        entry = known[matches[0]]
        return {"name": matches[0], "params_b": entry["params_b"], "hf_id": entry.get("hf_id"), "source": "fuzzy"}

    if params:
        return {"name": model_str, "params_b": params, "hf_id": None, "source": "parsed"}

    return {"name": model_str, "params_b": None, "hf_id": None, "source": "unknown"}


def estimate_vram_gb(params_b: float, quant_multiplier: float, context_overhead_mb: int = 512) -> float:
    """
    Estimate VRAM usage in GB.
    Formula: params * 2 bytes (fp16 baseline) * quant_ratio + overhead
    """
    base_gb = params_b * 2 * quant_multiplier
    overhead_gb = (context_overhead_mb / 1024) + OVERHEAD_BUFFER
    return round(base_gb + overhead_gb, 2)


def get_quant_recommendations(params_b: float, available_vram_gb: float, context_size: int = 4096) -> list[dict]:
    """
    Return all quants sorted by size, each tagged as fits / tight / won't fit.
    """
    db = load_model_db()
    quants = db["quant_multipliers"]
    context_mb = db["context_overhead_mb"].get(str(context_size), 512)

    results = []
    for quant_name, multiplier in quants.items():
        vram_needed = estimate_vram_gb(params_b, multiplier, context_mb)
        headroom = available_vram_gb - vram_needed

        if headroom >= 0.5:
            status = "fits"
        elif headroom >= 0:
            status = "tight"
        else:
            status = "no"

        results.append({
            "quant": quant_name,
            "vram_gb": vram_needed,
            "headroom_gb": round(headroom, 2),
            "status": status,
            "multiplier": multiplier,
        })

    results.sort(key=lambda x: x["vram_gb"])
    return results


PREFERRED_QUANT_ORDER = [
    "Q4_K_M", "Q5_K_M", "Q4_K_S", "Q5_K_S",
    "Q4_0", "Q3_K_M", "Q3_K_L", "Q6_K", "Q8_0"
]


def pick_best_quant(quants: list[dict]) -> Optional[dict]:
    """Pick best fitting quant from a list of recommendations."""
    fitting = [q for q in quants if q["status"] in ("fits", "tight")]
    if not fitting:
        return None
    for p in PREFERRED_QUANT_ORDER:
        for q in fitting:
            if q["quant"] == p:
                return q
    return max(fitting, key=lambda x: x["multiplier"])


def estimate_tokens_per_sec(params_b: float, bandwidth_gbps: float, quant_multiplier: float) -> int:
    """
    Rough tok/s estimate based on memory bandwidth.
    Each token needs to load all model weights once: bytes = params_b * 2B * quant_ratio
    tok/s = bandwidth / bytes_per_token
    """
    bytes_per_param = 2 * quant_multiplier
    model_bytes = params_b * 1e9 * bytes_per_param
    bandwidth_bytes = bandwidth_gbps * 1e9
    tps = bandwidth_bytes / model_bytes
    return max(1, round(tps))


def suggest_models(available_vram_gb: float, context_size: int = 4096, limit: int = 10) -> list[dict]:
    """
    Suggest the best models that fit in the given VRAM.
    Returns a list of models ranked by tier (S > A > B > C) and within each tier by params desc.
    Each entry includes the model info, best quant, estimated vram, headroom, and tok/s.
    """
    db = load_model_db()
    known = db["known_models"]
    tiers = db.get("model_tiers", {})

    # Build tier lookup: model_name -> tier_rank (S=0, A=1, B=2, C=3)
    tier_rank = {}
    tier_order = {"s": 0, "a": 1, "b": 2, "c": 3}
    for tier_name, models in tiers.items():
        rank = tier_order.get(tier_name, 3)
        for name in models:
            tier_rank[name] = rank

    candidates = []

    for name, info in known.items():
        params_b = info["params_b"]

        # Skip embedding models for general suggestion
        if params_b < 0.5:
            continue

        # Find the best quant that fits
        quants = get_quant_recommendations(params_b, available_vram_gb, context_size)
        best = pick_best_quant(quants)

        if best is None:
            continue

        # Use placeholder bandwidth for tok/s estimate (can be refined later with actual GPU bw)
        tps = estimate_tokens_per_sec(params_b, 336.1, best["multiplier"])
        rank = tier_rank.get(name, 3)

        candidates.append({
            "name": name,
            "params_b": params_b,
            "tier": ["S", "A", "B", "C"][rank],
            "tier_rank": rank,
            "best_quant": best["quant"],
            "vram_gb": best["vram_gb"],
            "headroom_gb": best["headroom_gb"],
        })

    # Sort by tier first (S highest), then by params desc within tier
    candidates.sort(key=lambda x: (x["tier_rank"], -x["params_b"]))

    return candidates[:limit]
