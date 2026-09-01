#!/usr/bin/env python3
"""Genera gli screenshot SVG dell'interfaccia mostrati nel README.

Usa gli stessi componenti `rich` dello script principale, con dati di esempio.
Rigenerare dopo ogni modifica all'interfaccia:

    python docs/generate_screenshots.py
"""
import os

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    MofNCompleteColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    ProgressSample,
)
from rich.rule import Rule
from rich.table import Table

OUT = os.path.dirname(os.path.abspath(__file__))
WIDTH = 84


def new_console():
    return Console(record=True, width=WIDTH, force_terminal=True, color_system="truecolor")


def progress_snapshot(console, desc, color, total, elapsed, remaining):
    """Disegna una barra di progresso ferma a uno stato realistico."""
    progress = Progress(
        SpinnerColumn(),
        TextColumn(f"[bold {color}]{{task.description}}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    )
    task_id = progress.add_task(desc, total=total)
    done = int(total * 0.62)
    progress.update(task_id, completed=done)

    task = progress.tasks[0]
    task.start_time = progress.get_time() - elapsed
    task.stop_time = None
    # Campioni fittizi perché rich calcoli un ETA credibile
    speed = (total - done) / remaining
    task._progress.clear()
    task._progress.extend([ProgressSample(0.0, 0), ProgressSample(100.0, speed * 100)])

    console.print(progress.get_renderable())


def summary_table(title, rows):
    table = Table(title=title, box=None, show_header=False, min_width=34)
    for label, value in rows:
        table.add_row(label, value)
    return table


# ---------- 1. Avvio e accesso ----------
console = new_console()
console.print(
    Panel.fit(
        "[bold white]📸  iCloud Photo Backup & Cleaner  ☁️[/bold white]\n"
        "[dim]Backup sicuro in locale, poi pulizia di iCloud su tua conferma[/dim]",
        border_style="cyan",
        padding=(1, 4),
    )
)
console.print(Rule("[bold cyan]Accesso[/bold cyan]", style="cyan"))
console.print("📧 [bold]Apple ID[/bold] [cyan](mario@icloud.com)[/cyan]: mario@icloud.com")
console.print("🔑 [bold]Password[/bold]: [dim]••••••••••••[/dim]")
console.print("📁 [bold]Cartella di destinazione[/bold] [cyan](./Backup_iCloud)[/cyan]: ")
console.print("[yellow]⚠ Autenticazione a due fattori richiesta.[/yellow]")
console.print("🔐 [bold]Codice ricevuto sul dispositivo[/bold]: 481920")
console.print("[bold green]✓ Accesso effettuato con successo.[/bold green]\n")
console.print("[bold]Trovati 3847 elementi su iCloud.[/bold]")
console.save_svg(os.path.join(OUT, "01-avvio.svg"), title="iCloud Photo Backup & Cleaner")

# ---------- 2. Fase di download ----------
console = new_console()
console.print(Rule("[bold cyan]FASE 1 · Download[/bold cyan]", style="cyan"))
console.print("[dim]Destinazione:[/dim] ./Backup_iCloud")
console.print(
    "[dim]I file già presenti vengono saltati. Gli errori di rete vengono ritentati "
    "automaticamente; gli errori di permesso/autenticazione no.[/dim]\n"
)
console.print(
    "[yellow]⚠ Errore per IMG_2841.HEIC: 503 Service Unavailable. Riprovo tra 30s...[/yellow]"
)
console.print("[yellow]⚠ File vuoto/corrotto IMG_2903.JPG, lo riscarico.[/yellow]")
progress_snapshot(console, "Download", "blue", 3847, 512, 314)
console.save_svg(os.path.join(OUT, "02-download.svg"), title="Fase 1 · Download")

# ---------- 3. Riepilogo e conferma ----------
console = new_console()
console.print(
    summary_table(
        "Riepilogo Download",
        [
            ("✅ Scaricati", "3812"),
            ("⏭️  Già presenti (saltati)", "34"),
            ("❌ Falliti", "1"),
            ("📦 Totale", "3847"),
        ],
    )
)
console.print(
    "\n[yellow]⚠ 1 file non sono stati scaricati e NON verranno eliminati da iCloud.[/yellow]"
)
console.print("\n[bold green]Tutti gli altri file sono al sicuro sul tuo PC.[/bold green]\n")
console.print(Rule("[bold red]FASE 2 · Eliminazione da iCloud[/bold red]", style="red"))
console.print(
    Panel(
        "Stai per eliminare definitivamente [bold]3846[/bold] elementi da iCloud.\n"
        "Le copie locali sul tuo PC NON verranno toccate.\n"
        "[yellow]1 file non scaricati correttamente verranno preservati su iCloud.[/yellow]",
        title="⚠️  Attenzione",
        border_style="red",
    )
)
console.print(
    "[bold]Procedere con l'eliminazione da iCloud?[/bold] "
    "[cyan]\\[y/n][/cyan] [dim](n)[/dim]: y"
)
console.save_svg(os.path.join(OUT, "03-riepilogo.svg"), title="Riepilogo e conferma")

# ---------- 4. Fase di eliminazione ----------
console = new_console()
progress_snapshot(console, "Eliminazione", "red", 3846, 240, 148)
console.print()
console.print(summary_table("Riepilogo Eliminazione", [("🗑️  Eliminati", "3846"), ("❌ Falliti", "0")]))
console.print("\n[bold green]Pulizia iCloud completata.[/bold green]")
console.save_svg(os.path.join(OUT, "04-eliminazione.svg"), title="Fase 2 · Eliminazione")

print(f"Screenshot generati in {OUT}:")
for name in sorted(f for f in os.listdir(OUT) if f.endswith(".svg")):
    print(" -", name)
