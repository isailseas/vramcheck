#!/usr/bin/env python3
"""
vramcheck TUI — compact interactive terminal UI
"""

import os, sys, shutil, re as _re

# ── Cross-platform raw terminal input ────────────────────────────────────────
if sys.platform == "win32":
    import msvcrt
    def _readchar_impl():
        ch = msvcrt.getwch()
        # msvcrt returns '' for special keys (arrows etc.) — read second byte
        if ch in ('\x00', '\xe0'):
            ch2 = msvcrt.getwch()
            # Map Windows arrow scan codes to ANSI sequences so the rest of
            # the code (which already handles ESC [ A/B) just works.
            _map = {'H': '\x1b[A', 'P': '\x1b[B', 'K': '\x1b[D', 'M': '\x1b[C'}
            return _map.get(ch2, '')
        return ch
else:
    import termios, tty
    def _readchar_impl():
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        return ch

from vramcheck import __version__


from vramcheck import __version__


# ── Palette ──────────────────────────────────────────────────────────────────
R = "\033[0m"
def fg(n):   return f"\033[38;5;{n}m"
def fg(n):   return f"\033[38;5;{n}m"
def fg(n):   return f"\033[38;5;{n}m"
def bold(s): return f"\033[1m{s}{R}"

TEAL   = fg(87)
TEAL2  = fg(73)
ORANGE = fg(208)
DIM    = fg(245)
DIMMER = fg(240)
WHITE  = fg(255)
GREEN  = fg(83)
YELLOW = fg(220)
RED    = fg(203)
BORDER = fg(59)
PURPLE = fg(141)

def t(col, s): return f"{col}{s}{R}"

# ── Terminal helpers ──────────────────────────────────────────────────────────
def W(): return shutil.get_terminal_size((80, 24)).columns
def H(): return shutil.get_terminal_size((80, 24)).lines

def vlen(s): return len(_re.sub(r'\033\[[0-9;]*m', '', s))

def rpad(s, w):
    p = w - vlen(s)
    return s + " " * max(0, p)


# ── Compact box drawing ──────────────────────────────────────────────────────
def box_top(w, title=""):
    if title:
        tl = _re.sub(r'\033\[[0-9;]*m', '', title)
        pad = max(0, w - 2 - len(tl) - 2)
        l = pad // 2; r = pad - l
        inner = "─" * l + f" {title} " + "─" * r
    else:
        inner = "─" * (w - 2)
    return t(BORDER, "╭" + inner + "╮")

def box_mid(w):
    return t(BORDER, "├" + "─" * (w - 2) + "┤")

def box_bot(w):
    return t(BORDER, "╰" + "─" * (w - 2) + "╯")

def box_row(s, w, edge=True):
    """Render a box content row with 1-space padding on each side."""
    fill = " " * max(0, w - 2 - vlen(s))
    if edge:
        return f"{t(BORDER,'│')} {s}{fill}{t(BORDER,'│')}"
    return f"{t(BORDER,'│')}{s}{fill}{t(BORDER,'│')}"


# ── Readchar / readline with autocomplete ─────────────────────────────────────
def readchar():
    return _readchar_impl()


def readline_with_autocomplete(prompt_str, completions):
    buf = []
    showing_ac = False
    ac_items = []
    ac_idx = 0
    ac_lines_shown = 0

    def render_prompt():
        sys.stdout.write(f"\r{prompt_str}{''.join(buf)} \r{prompt_str}{''.join(buf)}")
        sys.stdout.flush()

    def clear_ac(lines):
        for _ in range(lines):
            sys.stdout.write("\033[A\033[2K")
        sys.stdout.flush()

    def show_ac(items, selected):
        sys.stdout.write("\n")
        for i, item in enumerate(items):
            cmd  = t(TEAL, item["cmd"])
            desc = t(DIM, item["desc"])
            sel  = t(ORANGE, "❯ ") if i == selected else "  "
            sys.stdout.write(f"  {sel}{cmd}  {desc}\n")
        sys.stdout.flush()
        return len(items)

    render_prompt()

    while True:
        try:
            ch = readchar()
        except Exception:
            raise KeyboardInterrupt

        if ch in ('\x03', '\x04'):
            raise KeyboardInterrupt

        if ch in ('\r', '\n'):
            if showing_ac and ac_items:
                if ac_lines_shown:
                    clear_ac(ac_lines_shown + 1)
                    ac_lines_shown = 0
                sys.stdout.write("\n"); sys.stdout.flush()
                return ac_items[ac_idx]["cmd"]
            sys.stdout.write("\n"); sys.stdout.flush()
            return ''.join(buf)

        if ch in ('\x7f', '\x08'):
            if showing_ac and ac_lines_shown:
                clear_ac(ac_lines_shown + 1)
                ac_lines_shown = 0
                showing_ac = False
            if buf:
                buf.pop()
            render_prompt()
            continue

        if ch == '\x1b':
            # Unix: read the rest of the escape sequence
            if sys.platform != "win32":
                nxt = sys.stdin.read(1)
                if nxt == '[':
                    arrow = sys.stdin.read(1)
                    if showing_ac and ac_items:
                        if arrow in ('A', 'B'):
                            if ac_lines_shown: clear_ac(ac_lines_shown + 1)
                            ac_idx = (ac_idx + (-1 if arrow == 'A' else 1)) % len(ac_items)
                            ac_lines_shown = show_ac(ac_items, ac_idx)
            render_prompt()
            continue

        # Windows: shim returns full '\x1b[A' / '\x1b[B' for arrow keys
        if sys.platform == "win32" and isinstance(ch, str) and ch.startswith('\x1b['):
            arrow = ch[2] if len(ch) > 2 else ''
            if showing_ac and ac_items and arrow in ('A', 'B'):
                if ac_lines_shown: clear_ac(ac_lines_shown + 1)
                ac_idx = (ac_idx + (-1 if arrow == 'A' else 1)) % len(ac_items)
                ac_lines_shown = show_ac(ac_items, ac_idx)
            render_prompt()
            continue

        if ch == '\t':
            if showing_ac and ac_items:
                if ac_lines_shown: clear_ac(ac_lines_shown + 1)
                ac_idx = (ac_idx + 1) % len(ac_items)
                ac_lines_shown = show_ac(ac_items, ac_idx)
                render_prompt()
            continue

        buf.append(ch)

        if ch == '/' and len(buf) == 1:
            showing_ac = True; ac_idx = 0
            ac_items = completions
            render_prompt()
            ac_lines_shown = show_ac(ac_items, ac_idx)
            continue

        if showing_ac:
            if ac_lines_shown: clear_ac(ac_lines_shown + 1)
            query = ''.join(buf).lstrip('/').lower()
            ac_items = [c for c in completions if query in c["cmd"].lower() or query in c["desc"].lower()]
            if ac_items:
                ac_idx = min(ac_idx, len(ac_items) - 1)
                render_prompt()
                ac_lines_shown = show_ac(ac_items, ac_idx)
            else:
                showing_ac = False; ac_lines_shown = 0
                render_prompt()
            continue

        render_prompt()


VENDOR_CLR = {"nvidia": TEAL, "amd": fg(203), "intel": fg(39)}

from vramcheck import __version__

COMMANDS = [
    {"cmd": "/help",   "desc": "command reference"},
    {"cmd": "/gpus",   "desc": "list supported GPUs"},
    {"cmd": "/models", "desc": "list known models"},
    {"cmd": "suggest", "desc": "suggest best models for your GPU"},
    {"cmd": "/clear",  "desc": "clear screen"},
    {"cmd": "/quit",   "desc": "exit"},
]


# ── Splash — truly compact, no blank rows ─────────────────────────────────────
def render_splash(gpu_name, vram_gb, gpu_count, model_count):
    w = W()

    # Header
    head_l = t(TEAL, " vramcheck") + t(DIM, f" v{__version__}")
    head_r = t(DIM, f"{gpu_count} GPUs {model_count} models")
    gap = w - vlen(head_l) - vlen(head_r) - 2
    print(t(BORDER, "╭") + head_l + t(DIMMER, "·" * max(2, gap)) + head_r + t(BORDER, "╮"))

    # Blank row between header and content
    print(box_row("", w))

    # Logo + tagline + gpu info
    LOGO_SPLASH_LINES = [
        "█████ █████ ████████   ██████   █████████████  ",
        "░░███ ░░███ ░░███░░███ ░░░░░███ ░░███░░███░░███ ",
        " ░███  ░███  ░███ ░░░   ███████  ░███ ░███ ░███ ",
        " ░░███ ███   ░███      ███░░███  ░███ ░███ ░███ ",
        "  ░░█████    █████    ░░████████ █████░███ █████",
        "   ░░░░░    ░░░░░      ░░░░░░░░ ░░░░░ ░░░ ░░░░░ ",
        "                                                ",
    ]

    # Print each line of the logo without gaps (edge=False)
    for line in LOGO_SPLASH_LINES:
        print(box_row(t(TEAL, line), w, edge=False))

    tag  = t(DIM, "check if it runs")
    info = (t(DIMMER, "gpu ") + t(TEAL, gpu_name.title()) +
            t(DIMMER, "  ram ") + t(TEAL, f"{vram_gb} GB"))
    print(box_row(f"{tag}  {info}", w))

    hint = (t(ORANGE, "check") + t(DIM, " <model>") +
            t(BORDER, " │ ") +
            t(ORANGE, "gpu") + t(DIM, " <name>") +
            t(BORDER, " │ ") +
            t(ORANGE, "ctx") + t(DIM, " <size>")
    )
    print(box_row(hint, w))

    print(box_bot(w))
    print()

# ── Result box — compact table, aligned columns ───────────────────────────────
def render_result(model_info, gpu_info, quants, best, ollama_cmd, ctx):
    from vramcheck.model import estimate_tokens_per_sec, OVERHEAD_BUFFER
    w = W()

    name   = model_info["name"]
    params = model_info["params_b"]
    gname  = gpu_info["name"]
    vram   = gpu_info["vram_gb"]
    bw     = gpu_info["bandwidth_gbps"]
    source = model_info.get("source", "")
    fuzzy  = source == "fuzzy"

    # Title
    title = t(TEAL, name)
    if fuzzy:
        title += t(YELLOW, " ~")
    elif source == "parsed":
        title += t(DIM, " *")

    # Subtitle: params | gpu bw | ctx
    sub = (t(DIMMER, f"{params}B") +
           t(BORDER, " │ ") + t(TEAL, gname.title()) +
           t(DIMMER, f"  {vram}GB {bw}GB/s") +
           t(BORDER, " │ ") + t(DIM, f"ctx {ctx}"))

    print(box_top(w, title))
    print(box_row(sub, w))
    print(box_mid(w))

    # Table header
    hdr = f"  {'quant':<12}{'vram':>9}{'headroom':>10}{'tok/s':>7}  "
    print(box_row(t(DIM, hdr), w))
    print(box_row(t(BORDER, "  " + "─" * 40), w))

    scol = {"fits": GREEN, "tight": YELLOW, "no": RED}
    sico = {"fits": "✓", "tight": "~", "no": "✗"}

    for q in quants:
        tps    = estimate_tokens_per_sec(params, bw, q["multiplier"])
        sc     = scol[q["status"]]
        si     = sico[q["status"]]
        hv     = q["headroom_gb"]
        hstr   = ("+" if hv >= 0 else "") + f"{hv}GB"
        isbest = best and q["quant"] == best["quant"]

        qn_plain = q["quant"].ljust(12)
        qn = t(ORANGE if isbest else WHITE, qn_plain)
        marker = t(ORANGE, "◀") if isbest else " "
        vs_plain = f"{q['vram_gb']}GB".rjust(8)
        vs = t(TEAL if isbest else DIM, vs_plain)
        hs = t(sc, f"{hstr:>9}")
        ts = t(DIMMER, f"~{tps:>5}")
        ic = t(sc, si)

        line = f"  {qn} {marker} {vs} {hs} {ts} {ic}"
        print(box_row(line, w))

    print(box_mid(w))

    if best is None:
        db = __import__("vramcheck.model", fromlist=["load_model_db"]).load_model_db()
        q2_mult = db["quant_multipliers"]["Q2_K"]
        min_vram = round(params * 2 * q2_mult + OVERHEAD_BUFFER + 0.5, 1)
        print(box_row(t(RED, f"  ✗  won't fit  (need ≥{min_vram}GB for Q2_K)"), w))
    else:
        print(box_row(t(GREEN, "  ✓  ") + t(ORANGE, best["quant"]) +
                       t(DIM, "  →  ") + t(TEAL, ollama_cmd), w))

    print(box_bot(w))
    print()


# ── ASCII Logo ─────────────────────────────────────────────────────────────────
LOGO_LINES = [
    "█████ █████ ████████   ██████   █████████████  ",
    "░░███ ░░███ ░░███░░███ ░░░░░███ ░░███░░███░░███ ",
    " ░███  ░███  ░███ ░░░   ███████  ░███ ░███ ░███ ",
    " ░░███ ███   ░███      ███░░███  ░███ ░███ ░███ ",
    "  ░░█████    █████    ░░████████ █████░███ █████",
    "   ░░░░░    ░░░░░      ░░░░░░░░ ░░░░░ ░░░ ░░░░░ ",
]


# ── Help ───────────────────────────────────────────────────────────────────────
def render_help():
    w = W()
    cmds = [
        ("check <model>",         "check model vs current GPU"),
        ("check <model> --ctx N", "context: 2048-32768"),
        ("check <model> --all",   "show all quants"),
        ("suggest",               "suggest best models for current GPU"),
        ("gpu <name>",            "switch GPU"),
        ("ctx <size>",            "set context window"),
        ("list  models | gpus",   "list known models or GPUs"),
        ("/help",                 "this screen"),
        ("/quit",                 "exit"),
    ]
    # Logo at top of help
    for ln in LOGO_LINES:
        print(t(TEAL, ln))
    print()
    print(box_top(w, t(ORANGE, "commands")))
    for cmd, desc in cmds:
        row = t(TEAL, f"  {cmd:<26}") + t(DIM, desc)
        print(box_row(row, w))
    print(box_bot(w))
    print()


# ── Messages ──────────────────────────────────────────────────────────────────
def render_gpu_ok(g):
    vc = VENDOR_CLR.get(g.get("vendor", ""), WHITE)
    print(t(GREEN,"  ✓") + t(DIM," gpu → ") + t(TEAL, g["name"].title()) +
          t(DIMMER, f"  {g['vram_gb']}GB") +
          t(DIM, "  [") + t(vc, g.get("vendor","").upper()) + t(DIM, "]"))
    print()

def render_err(msg):
    print(t(RED, f"  ✗  {msg}"))
    print()

def render_warn(msg):
    print(t(YELLOW, f"  ~  {msg}"))
    print()


# ── Status bar ─────────────────────────────────────────────────────────────────
def render_status(gpu_name, vram, ctx):
    w = W()
    line = (t(BORDER, "─" * w) + "\n" +
            t(TEAL, " vramcheck") +
            t(BORDER, " │ ") + t(DIM, "gpu ") + t(TEAL2, gpu_name.title()) +
            t(BORDER, " │ ") + t(DIM, "vram ") + t(TEAL2, f"{vram}GB") +
            t(BORDER, " │ ") + t(DIM, f"ctx {ctx}"))
    print(line)

def prompt_str():
    return t(ORANGE, "❯ ")


# ── GPU list ──────────────────────────────────────────────────────────────────
def render_gpu_list():
    from vramcheck.gpu import load_gpu_db
    w = W()
    db = load_gpu_db()
    print(box_top(w, t(ORANGE, "GPUs")))
    for vendor, gpus in db.items():
        vc = VENDOR_CLR.get(vendor, WHITE)
        names = list(gpus.keys())
        col_w = 20
        cols = max(1, (w - 4) // col_w)
        print(box_row(t(vc, f"  {vendor.upper()}"), w))
        for i in range(0, len(names), cols):
            chunk = names[i:i+cols]
            line = "    " + t(DIM, "  ".join(n.ljust(col_w - 2) for n in chunk))
            print(box_row(line, w))
    print(box_bot(w))
    print()


# ── Model list ─────────────────────────────────────────────────────────────────
def render_model_list():
    from vramcheck.model import load_model_db
    w = W()
    db = load_model_db()
    items = list(db["known_models"].items())
    print(box_top(w, t(ORANGE, "models")))

    # Group models by family prefix
    from collections import OrderedDict
    families = OrderedDict()
    for name, info in items:
        # Extract family: everything before the last colon or number
        import re as _re
        m = _re.match(r'^([a-z]+)', name)
        fam = m.group(1) if m else "other"
        families.setdefault(fam, []).append((name, info))

    for fam, members in families.items():
        # Family header
        print(box_row(t(TEAL2, f"  {fam.upper()}"), w))
        # Members in columns
        col_w = 28
        cols = max(1, (w - 4) // col_w)
        for i in range(0, len(members), cols):
            chunk = members[i:i+cols]
            parts = []
            for name, info in chunk:
                parts.append(t(TEAL2, name.ljust(22)) + t(DIM, f"{info['params_b']}B"))
            line = "    " + t(DIM, "  ").join(parts)
            print(box_row(line, w))

    print(box_bot(w))
    print()


# ── REPL ──────────────────────────────────────────────────────────────────────
def repl():
    from vramcheck.gpu import find_gpu, load_gpu_db
    from vramcheck.model import resolve_model, get_quant_recommendations, load_model_db

    gdb  = load_gpu_db()
    mdb  = load_model_db()
    gpu_count   = sum(len(v) for v in gdb.values())
    model_count = len(mdb["known_models"])

    # Use auto-detection for default GPU
    current_gpu = find_gpu("auto")
    if current_gpu is None:
        current_gpu = find_gpu("gtx 1660 super")  # fallback
    current_ctx = 4096

    render_splash(current_gpu["name"], current_gpu["vram_gb"], gpu_count, model_count)

    while True:
        try:
            render_status(current_gpu["name"], current_gpu["vram_gb"], current_ctx)
            if sys.stdin.isatty():
                raw = readline_with_autocomplete(prompt_str(), COMMANDS)
            else:
                sys.stdout.write(prompt_str()); sys.stdout.flush()
                raw = input()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{t(DIM, 'bye.')}")
            break

        line = raw.strip()
        if not line:
            continue

        tokens = line.split()
        cmd = tokens[0].lower()

        if cmd in ("/quit", "/exit", "q", "quit", "exit"):
            print(t(DIM, "bye."))
            break

        elif cmd in ("/help", "help", "?"):
            render_help()

        elif cmd in ("/clear", "clear"):
            os.system("cls" if sys.platform == "win32" else "clear")
            render_splash(current_gpu["name"], current_gpu["vram_gb"], gpu_count, model_count)

        elif cmd == "/gpus":
            render_gpu_list()

        elif cmd == "/models":
            render_model_list()

        elif cmd == "ctx":
            if len(tokens) < 2:
                render_warn("ctx <size>   e.g.  ctx 8192")
                continue
            try:
                new_ctx = int(tokens[1])
                if new_ctx in (2048, 4096, 8192, 16384, 32768):
                    current_ctx = new_ctx
                    print(t(GREEN, "  ✓") + t(DIM, f" ctx {current_ctx}"))
                    print()
                else:
                    render_warn("must be 2048, 4096, 8192, 16384, or 32768")
            except ValueError:
                render_warn("ctx <size>   e.g.  ctx 8192")

        elif cmd == "gpu":
            if len(tokens) < 2:
                render_warn("gpu <name>   e.g.  gpu rtx 4090")
                continue
            name = " ".join(tokens[1:])
            g = find_gpu(name)
            if g is None:
                render_err(f"gpu not found: '{name}'")
            else:
                current_gpu = g
                render_gpu_ok(g)

        elif cmd == "suggest":
            from vramcheck.model import suggest_models
            suggestions = suggest_models(current_gpu["vram_gb"], current_ctx)

            if not suggestions:
                render_warn("No models fit in your GPU's VRAM")
                continue

            print(box_top(W(), t(ORANGE, "Suggested Models")))
            print(box_row(t(DIM, f"  {'Tier':<6}{'Model':<24}{'Params':<8}{'Quant':<8}{'VRAM':<8}{'Headroom':<10}"), W()))
            print(box_row(t(BORDER, "  " + "─" * (W() - 8)), W()))

            for m in suggestions:
                tier_clr = {"S": GREEN, "A": TEAL, "B": DIM, "C": DIMMER}.get(m["tier"], DIM)
                tier_str = f"  {m['tier']:<5}"
                params_str = f"{m['params_b']}B".ljust(8)
                vram_str = f"{m['vram_gb']}GB".ljust(8)
                headroom_str = f"{m['headroom_gb']}GB"
                row = (
                    f"{t(tier_clr, tier_str)}" +
                    f"{t(TEAL, m['name'].ljust(24))}" +
                    f"{t(DIM, params_str)}" +
                    f"{t(ORANGE, m['best_quant'].ljust(8))}" +
                    f"{t(DIM, vram_str)}" +
                    f"{t(GREEN if m['headroom_gb'] > 0.5 else YELLOW, headroom_str)}"
                )
                print(box_row(row, W()))

            print(box_bot(W()))
            print()

            # Recommend the top one
            top = suggestions[0]
            print(t(GREEN, "  ✓") + t(DIM, " Recommended: ") +
                  t(TEAL, top["name"]) + t(DIM, f" ({top['tier']} tier)"))
            print(t(DIM, "  ") + t(ORANGE, f"ollama run {top['name']}:{top['best_quant']}"))
            print()
        elif cmd == "check":
            if len(tokens) < 2:
                render_warn("check <model>   e.g.  check llama3:8b")
                continue

            model_toks = []
            ctx = current_ctx
            show_all = False
            i = 1
            while i < len(tokens):
                tok = tokens[i]
                if tok in ("--ctx", "--context", "-c") and i + 1 < len(tokens):
                    try: ctx = int(tokens[i + 1])
                    except: pass
                    i += 2
                elif tok in ("--all", "-a"):
                    show_all = True
                    i += 1
                else:
                    model_toks.append(tok)
                    i += 1

            model = resolve_model(" ".join(model_toks))
            if model["params_b"] is None:
                render_err(f"unknown model: '{' '.join(model_toks)}'")
                continue

            quants = get_quant_recommendations(model["params_b"], current_gpu["vram_gb"], ctx)
            fitting = [q for q in quants if q["status"] in ("fits", "tight")]
            best = None
            for p in ["Q4_K_M", "Q5_K_M", "Q4_K_S", "Q5_K_S", "Q4_0", "Q3_K_M", "Q3_K_L", "Q6_K", "Q8_0"]:
                for q in fitting:
                    if q["quant"] == p:
                        best = q
                        break
                if best:
                    break
            if not best and fitting:
                best = max(fitting, key=lambda x: x["multiplier"])

            if show_all:
                dq = quants
            else:
                dq = [q for q in quants if q["status"] != "no"]
                if not dq:
                    dq = quants[:5]

            # Build ollama command
            n_base = model["name"].split("/")[-1].lower().replace("-gguf", "").replace("-instruct", "")
            if ":" in n_base:
                n_base = n_base.rsplit(":", 1)[0]
            qt = best["quant"].upper() if best else ""
            cmd_str = f"ollama run {n_base}:{qt}" if best else ""

            render_result(model, current_gpu, dq, best, cmd_str, ctx)

        else:
            render_warn(f"unknown: '{cmd}'   type / for commands")