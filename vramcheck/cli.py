#!/usr/bin/env python3
"""
vramcheck — VRAM advisor for local AI models
  vramcheck              → interactive TUI
  vramcheck <model>      → one-shot CLI
"""

import argparse
import re
import sys

from vramcheck import __version__
from vramcheck.model import pick_best_quant

DEFAULT_CONTEXT = 4096


def build_ollama_cmd(model_name: str, quant: str) -> str:
    # Ollama model tags include quant as part of the tag
    # e.g. "llama3:8b" -> "llama3:Q4_K_M" (quant replaces param count tag)
    n = model_name.split("/")[-1].lower()
    # Remove any existing -instruct, -gguf suffixes
    n = re.sub(r"-(gguf|instruct|chat)$", "", n)
    # If model name has a colon tag, strip it (param count like 8b, 70b etc)
    if ":" in n:
        base = n.rsplit(":", 1)[0]
    else:
        base = n
    qt = quant.upper()
    return f"ollama run {base}:{qt}"


def run_oneshot(args):
    from vramcheck.gpu import find_gpu, list_gpus
    from vramcheck.model import resolve_model, get_quant_recommendations, OVERHEAD_BUFFER, load_model_db
    from vramcheck.display import (
        print_header, print_quant_table, print_recommendation,
        print_warning, print_error, print_gpu_list,
    )

    if args.list_gpus:
        print_gpu_list(list_gpus())
        return 0

    if args.suggest:
        gpu = find_gpu(args.gpu) if args.gpu else find_gpu("auto")
        if gpu is None:
            print_error(f"GPU not found: '{args.gpu}'")
            return 1
        from vramcheck.model import suggest_models
        suggestions = suggest_models(gpu["vram_gb"], args.context or DEFAULT_CONTEXT)
        print(f"\nRecommended models for {gpu['name'].title()} ({gpu['vram_gb']}GB VRAM):\n")
        for m in suggestions:
            print(f"  [{m['tier']}] {m['name']} ({m['params_b']}B) → {m['best_quant']} → {m['vram_gb']}GB")
        if suggestions:
            top = suggestions[0]
            print(f"\nTop pick: ollama run {top['name']}:{top['best_quant']}\n")
        return 0

    gpu = find_gpu(args.gpu) if args.gpu else find_gpu("auto")
    if gpu is None:
        print_error(f"GPU not found: '{args.gpu}'")
        print_warning("Run `vramcheck --list-gpus` to see supported GPUs.")
        return 1

    if gpu["name"] != args.gpu.lower():
        print_warning(f"GPU matched as: {gpu['name'].title()}")

    model = resolve_model(args.model)
    if model["params_b"] is None:
        print_error(f"Couldn't determine parameter count for '{args.model}'.")
        print_warning("Try specifying like: llama3:8b  or  mistral:7b")
        return 1

    ctx = args.context or DEFAULT_CONTEXT
    quants = get_quant_recommendations(model["params_b"], gpu["vram_gb"], ctx)
    best = pick_best_quant(quants)

    # Build version string from model source
    source = model.get("source", "")
    print_header(model["name"], model["params_b"], gpu["name"], gpu["vram_gb"], source)

    if args.all:
        display_quants = quants
    else:
        display_quants = [q for q in quants if q["status"] != "no"]
        if not display_quants:
            display_quants = quants[:4]

    print_quant_table(display_quants, gpu["bandwidth_gbps"], model["params_b"],
                      best["quant"] if best else None)

    ollama_cmd = build_ollama_cmd(model["name"], best["quant"]) if best else ""
    print_recommendation(best, ollama_cmd, model["params_b"], gpu["vram_gb"])

    if ctx != DEFAULT_CONTEXT:
        print_warning(f"Context size {ctx} used for overhead estimate.")

    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="vramcheck",
        description="vramcheck — VRAM advisor for local AI models. Run with no args for interactive TUI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  vramcheck                                   → interactive TUI
  vramcheck llama3:8b                         → quick check (uses default GPU)
  vramcheck llama3:8b -g "rtx 3060"          → specify GPU
  vramcheck mistral:7b -g "rtx 3060" -c 8192
  vramcheck deepseek-r1:32b -g "rtx 4090" --all
  vramcheck --list-gpus
  vramcheck --version
        """,
    )
    parser.add_argument("model", nargs="?", help="Model name (e.g. llama3:8b). Omit for TUI.")
    parser.add_argument("--gpu", "-g", default=None, help="GPU name (default: auto-detected)")
    parser.add_argument("--context", "-c", type=int, choices=[2048, 4096, 8192, 16384, 32768])
    parser.add_argument("--all", "-a", action="store_true", help="Show all quants")
    parser.add_argument("--list-gpus", action="store_true", help="List supported GPUs")
    parser.add_argument("--suggest", action="store_true", help="Suggest best models for your GPU")
    parser.add_argument("--version", "-V", action="version", version=f"vramcheck {__version__}")

    args = parser.parse_args()

    # No model + no list-gpus → launch TUI
    if not args.model and not args.suggest:
        from vramcheck.tui import repl
        repl()
        sys.exit(0)

    sys.exit(run_oneshot(args))


if __name__ == "__main__":
    main()
