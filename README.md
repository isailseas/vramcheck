# vramcheck

**Will it run?** A CLI tool that tells you exactly which quantisation of a local AI model fits in your GPU's VRAM, estimates tokens/sec, and gives you the Ollama command to run it.

No more tab-switching between GGUF metadata, GPU spec sheets, and Ollama docs.

```
$ vramcheck llama3:8b --gpu "rtx 3060"

vramcheck  v1.0
Model : llama3:8b
Params : 8B
GPU    : Rtx 3060  (12.0GB VRAM)

 Quant        VRAM needed   Headroom   Tok/s
─────────────────────────────────────────────
 Q2_K            4.20GB     +7.80GB   ~112  ✓
 Q3_K_S          4.36GB     +7.64GB   ~107  ✓
 Q4_K_M ◀        5.32GB     +6.68GB    ~83  ✓
 Q5_K_S          5.96GB     +6.04GB    ~73  ✓
 Q5_K_M          6.20GB     +5.80GB    ~69  ✓
 Q6_K            7.08GB     +4.92GB    ~59  ✓
 Q8_0            9.48GB     +2.52GB    ~42  ✓

Recommended quant : Q4_K_M
Run it            : ollama run llama3:Q4_K_M
```

Or launch the interactive TUI with no arguments:

```
$ vramcheck
```

## Install

From PyPI:

```bash
pip install vramcheck
```

From source:

```bash
git clone https://github.com/yourusername/vramcheck
cd vramcheck
pip install -e .
```

Requirements: Python 3.10+, `rich` (installed automatically).

## Usage

```bash
# Interactive TUI (no arguments)
vramcheck

# Basic check
vramcheck llama3:8b --gpu "gtx 1660 super"

# Specify GPU
vramcheck llama3:8b --gpu "rtx 4090"

# Different context window (affects overhead estimate)
vramcheck mistral:7b --gpu "rtx 3060" --context 8192

# Show all quants including ones that don't fit
vramcheck deepseek-r1:32b --gpu "rtx 4090" --all

# List all supported GPUs
vramcheck --list-gpus

# Show version
vramcheck --version
```

### TUI Commands

| Command | Description |
|---|---|
| `check <model>` | Check a model against the current GPU |
| `check <model> --ctx N` | Set context window (2048–32768) |
| `check <model> --all` | Show all quants including ones that won't fit |
| `gpu <name>` | Switch active GPU for this session |
| `ctx <size>` | Set context window for this session |
| `list models` | Show all built-in models |
| `list gpus` | Show all supported GPUs |
| `/help` | Show command reference |
| `/quit` | Exit |

## Supported models

Over 65+ common models pre-loaded including:

- **Llama**: Llama 3 / 3.1 / 3.2 / 3.3 (1B – 405B)
- **Mistral**: Mistral 7B, Mixtral 8x7B
- **Gemma**: Gemma 1/2/3 (1B – 27B), CodeGemma
- **Phi**: Phi 3 / 3.5 / 4
- **Qwen**: Qwen 2 / 2.5 / 3 (0.5B – 72B), Qwen2.5-Coder
- **DeepSeek**: R1 distills (1.5B – 70B), DeepSeek-V3
- **Code**: CodeLlama (7B/13B/34B), StarCoder2 (3B/7B/15B)
- **Cohere**: Command R (35B), Command R+ (104B)
- **Embedding**: nomic-embed-text, nomic-embed-v2, bge-large-en, bge-m3

Any model not in the list can be specified by param count directly:
```
vramcheck 13b --gpu "rtx 3080"
```

## Supported GPUs

59+ GPUs across Nvidia (GTX 10/16 series, RTX 20/30/40/50 series), AMD (RX 6000/7000/9000), and Intel Arc.

Run `vramcheck --list-gpus` for the full list.

Missing your GPU? Add it to `data/gpus.json` and open a PR.

## How VRAM is estimated

```
vram = (params_B × 2 bytes × quant_ratio) + context_overhead + 0.5GB buffer
```

Tokens/sec is estimated from GPU memory bandwidth:

```
tok/s ≈ bandwidth_GB/s ÷ (params_B × 2 × quant_ratio)
```

These are approximations — real performance varies by GPU generation, driver, and model architecture. Quantisation multipliers are calibrated against real-world GGUF model sizes from llama.cpp.

## Adding a GPU

Open `data/gpus.json` and add an entry under the right vendor:

```json
"rtx 9090": { "vram_gb": 48.0, "bandwidth_gbps": 2000.0, "cuda_cores": 32768 }
```

## Adding a Model

Open `data/models.json` and add an entry to `known_models`:

```json
"mymodel:7b": { "params_b": 7, "hf_id": "org/mymodel-7b" }
```

## Contributing

PRs welcome for:
- New GPU entries
- New model entries in `data/models.json`
- Better tok/s estimation per architecture
- Anything that makes it more useful

## License

MIT
