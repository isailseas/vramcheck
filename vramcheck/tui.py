#!/usr/bin/env python3
"""
vramcheck TUI — compact interactive terminal UI
"""

import os, sys, shutil, termios, tty, re as _re

# ── Palette ──────────────────────────────────────────────────────────────────
R = "\033[0m"
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
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch


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

VERSION = "1.0.0"

COMMANDS = [
    {"cmd": "/help",   "desc": "command reference"},
    {"cmd": "/gpus",   "desc": "list supported GPUs"},
    {"cmd": "/models", "desc": "list known models"},
    {"cmd": "/clear",  "desc": "clear screen"},
    {"cmd": "/quit",   "desc": "exit"},
]


# ── Splash — truly compact, no blank rows ─────────────────────────────────────
def render_splash(gpu_name, vram_gb, gpu_count, model_count):
    w = W()

    # Header
    head_l = t(TEAL, " vramcheck") + t(DIM, f" v{VERSION}")
    head_r = t(DIM, f"{gpu_count} GPUs  {model_count} models")
    gap = w - vlen(head_l) - vlen(head_r) - 2
    print(t(BORDER, "╭") + head_l + t(DIMMER, "·" * max(2, gap)) + head_r + t(BORDER, "╮"))

    # Blank row between header and content
    print(box_row("", w))

    # Logo + tagline + gpu info
    # Tight "VRAM" ASCII art — each letter 3 wide, separated by single space gap
    logo1 = t(TEAL, "╦ ╦ ╦═╗ ╔═╗ ╔╦╗")
    logo2 = t(TEAL, "║ ║ ║   ╠═╣ ║║║")
    logo3 = t(TEAL, "╚═╝ ╩   ╝ ╩ ╩ ╩")

    tag  = t(DIM, "check if it runs")
    info = (t(DIMMER, "gpu ") + t(TEAL, gpu_name.title()) +
            t(DIMMER, "  ram ") + t(TEAL, f"{vram_gb} GB"))
    row1 = f"{logo1}  {tag}  {info}"
    print(box_row(row1, w))

    hint = (t(ORANGE, "check") + t(DIM, " <model>") +
            t(BORDER, " │ ") +
            t(ORANGE, "gpu") + t(DIM, " <name>") +
            t(BORDER, " │ ") +
            t(ORANGE, "ctx") + t(DIM, " <size>"))
    print(box_row(f"{logo2}  {hint}", w))

    print(box_row(logo3, w))

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


# ── Help ───────────────────────────────────────────────────────────────────────
def render_help():
    w = W()
    cmds = [
        ("check <model>",         "check model vs current GPU"),
        ("check <model> --ctx N", "context: 2048–32768"),
        ("check <model> --all",   "show all quants"),
        ("gpu <name>",            "switch GPU"),
        ("ctx <size>",            "set context window"),
        ("list  models | gpus",   "list known models or GPUs"),
        ("/help",                 "this screen"),
        ("/quit",                 "exit"),
    ]
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

    current_gpu = find_gpu("gtx 1660 super")
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
            os.system("clear")
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

        elif cmd == "list":
            sub = tokens[1].lower() if len(tokens) > 1 else ""
            if sub == "gpus":
                render_gpu_list()
            elif sub == "models":
                render_model_list()
            else:
                render_warn("list models  |  list gpus")

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
