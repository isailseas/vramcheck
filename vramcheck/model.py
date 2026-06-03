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


def fetch_hf_info(hf_id: str) -> Optional[dict]:
    """
    Try to fetch basic model info from Hugging Face API.
    Returns dict with downloads, likes etc or None on failure.
    """
    url = f"https://huggingface.co/api/models/{hf_id}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "vramcheck/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return {
                "downloads": data.get("downloads", 0),
                "likes": data.get("likes", 0),
                "pipeline_tag": data.get("pipeline_tag", "unknown"),
                "tags": data.get("tags", []),
            }
    except Exception:
        return None
