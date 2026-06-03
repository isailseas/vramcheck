from typing import Optional

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
    from rich import box
    RICH = True
except ImportError:
    RICH = False


console = Console() if RICH else None


def _status_icon(status: str) -> str:
    return {"fits": "✓", "tight": "~", "no": "✗"}.get(status, "?")


def _status_color(status: str) -> str:
    return {"fits": "green", "tight": "yellow", "no": "red"}.get(status, "white")


def print_header(model_name: str, params_b: float, gpu_name: str, vram_gb: float, source: str = ""):
    if RICH:
        console.print()
        console.print(f"[bold cyan]vramcheck[/bold cyan]  [dim]v1.0[/dim]")
        console.print(f"[bold]Model :[/bold] {model_name}", end="")
        if source == "fuzzy":
            console.print(f"  [dim](fuzzy matched)[/dim]", end="")
        elif source == "parsed":
            console.print(f"  [dim](parsed)[/dim]", end="")
        console.print()
        console.print(f"[bold]Params :[/bold] {params_b}B")
        console.print(f"[bold]GPU    :[/bold] {gpu_name.title()}  ({vram_gb}GB VRAM)")
        console.print()
    else:
        print(f"\nvramcheck v1.0")
        print(f"Model  : {model_name}")
        print(f"Params : {params_b}B")
        print(f"GPU    : {gpu_name.title()}  ({vram_gb}GB VRAM)\n")


def print_quant_table(quants: list[dict], bandwidth_gbps: float, params_b: float, highlight_quant: Optional[str] = None):
    from vramcheck.model import estimate_tokens_per_sec

    if RICH:
        table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold dim")
        table.add_column("Quant", style="bold", width=12)
        table.add_column("VRAM needed", justify="right", width=13)
        table.add_column("Headroom", justify="right", width=10)
        table.add_column("Tok/s (est)", justify="right", width=11)
        table.add_column("", width=3)

        for q in quants:
            tps = estimate_tokens_per_sec(params_b, bandwidth_gbps, q["multiplier"])
            icon = _status_icon(q["status"])
            color = _status_color(q["status"])

            headroom_str = f"+{q['headroom_gb']}GB" if q["headroom_gb"] >= 0 else f"{q['headroom_gb']}GB"

            is_highlight = q["quant"] == highlight_quant
            row_style = "bold" if is_highlight else ""

            table.add_row(
                Text(q["quant"] + (" ◀" if is_highlight else ""), style=row_style),
                Text(f"{q['vram_gb']}GB", style=row_style),
                Text(headroom_str, style=f"{color} {row_style}".strip()),
                Text(f"~{tps}", style=row_style),
                Text(icon, style=color),
            )

        console.print(table)
    else:
        print(f"{'Quant':<14} {'VRAM needed':>12} {'Headroom':>10} {'Tok/s':>8}  ")
        print("-" * 52)
        for q in quants:
            tps = estimate_tokens_per_sec(params_b, bandwidth_gbps, q["multiplier"])
            icon = _status_icon(q["status"])
            headroom_str = f"+{q['headroom_gb']}GB" if q["headroom_gb"] >= 0 else f"{q['headroom_gb']}GB"
            marker = " <" if q["quant"] == highlight_quant else ""
            print(f"{q['quant']:<14} {q['vram_gb']:>10.1f}GB {headroom_str:>10} {tps:>6}  {icon}{marker}")


def print_recommendation(best: Optional[dict], ollama_cmd: str, params_b: float, vram_gb: float):
    if best is None:
        from vramcheck.model import load_model_db, OVERHEAD_BUFFER
        db = load_model_db()
        q2_mult = db["quant_multipliers"]["Q2_K"]
        ctx_overhead = 512 / 1024  # default 4096 context
        min_vram = round(params_b * 2 * q2_mult + ctx_overhead + OVERHEAD_BUFFER, 1)
        if RICH:
            console.print(f"[red bold]✗ This model won't fit in your VRAM at any quantisation.[/red bold]")
            console.print(f"[dim]You need at least {min_vram}GB for Q2_K.[/dim]\n")
        else:
            print(f"\n✗ This model won't fit in your VRAM at any quantisation.")
            print(f"  You need at least {min_vram}GB for Q2_K.\n")
        return

    if RICH:
        console.print(f"[green bold]Recommended quant:[/green bold] [cyan]{best['quant']}[/cyan]")
        console.print(f"[bold]Run it:[/bold]")
        console.print(f"  [on grey15] {ollama_cmd} [/on grey15]\n")
    else:
        print(f"\nRecommended quant : {best['quant']}")
        print(f"Run it            : {ollama_cmd}\n")


def print_warning(msg: str):
    if RICH:
        console.print(f"[yellow]⚠  {msg}[/yellow]")
    else:
        print(f"⚠  {msg}")


def print_error(msg: str):
    if RICH:
        console.print(f"[red]✗  {msg}[/red]")
    else:
        print(f"✗  {msg}")


def print_gpu_list(gpus: list[str]):
    if RICH:
        console.print("\n[bold]Supported GPUs:[/bold]\n")
        for g in gpus:
            console.print(f"  [dim]{g}[/dim]")
        console.print()
    else:
        print("\nSupported GPUs:\n")
        for g in gpus:
            print(f"  {g}")
        print()
