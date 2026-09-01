#!/usr/bin/env python3
import os
import sys
import time

from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudFailedLoginException

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
)
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.rule import Rule

console = Console()

# Parole chiave che indicano un errore NON recuperabile con un retry
# (credenziali/permessi): riprovare all'infinito non serve a nulla e
# bloccherebbe lo script per sempre.
FATAL_ERROR_KEYWORDS = (
    "401",
    "403",
    "unauthorized",
    "authentication",
    "invalid_grant",
    "access denied",
    "forbidden",
)
MAX_RETRIES_ON_FATAL_LIKE = 3


def print_banner():
    banner = (
        "[bold white]📸  iCloud Photo Backup & Cleaner  ☁️[/bold white]\n"
        "[dim]Backup sicuro in locale, poi pulizia di iCloud su tua conferma[/dim]"
    )
    console.print(Panel.fit(banner, border_style="cyan", padding=(1, 4)))


def get_credentials():
    console.print(Rule("[bold cyan]Accesso[/bold cyan]", style="cyan"))
    email = os.environ.get("ICLOUD_EMAIL") or Prompt.ask("📧 [bold]Apple ID[/bold]")
    password = os.environ.get("ICLOUD_PASSWORD") or Prompt.ask(
        "🔑 [bold]Password[/bold]", password=True
    )
    destination = os.environ.get("ICLOUD_BACKUP_PATH") or Prompt.ask(
        "📁 [bold]Cartella di destinazione[/bold]", default="./Backup_iCloud"
    )
    return email, password, destination


def authenticate(email, password):
    try:
        with console.status("[bold green]Autenticazione in corso...", spinner="dots"):
            api = PyiCloudService(email, password)
    except PyiCloudFailedLoginException:
        console.print("[bold red]✗ Credenziali errate. Controlla email e password.[/bold red]")
        sys.exit(1)

    if api.requires_2fa:
        console.print("[yellow]⚠ Autenticazione a due fattori richiesta.[/yellow]")
        code = Prompt.ask("🔐 [bold]Codice ricevuto sul dispositivo[/bold]")
        if not api.validate_2fa_code(code):
            console.print("[bold red]✗ Codice non valido.[/bold red]")
            sys.exit(1)
        if not api.is_trusted_session:
            with console.status("[bold green]Autorizzo la sessione...", spinner="dots"):
                api.trust_session()

    console.print("[bold green]✓ Accesso effettuato con successo.[/bold green]\n")
    return api


def is_fatal_error(error_msg: str) -> bool:
    lowered = error_msg.lower()
    return any(keyword in lowered for keyword in FATAL_ERROR_KEYWORDS)


def wait_after_error(error_msg: str) -> int:
    if "503" in error_msg or "Service Unavailable" in error_msg:
        return 30
    if "Connection" in error_msg or "socket" in error_msg:
        return 10
    return 5


def safe_filename(photo) -> str:
    try:
        return photo.filename
    except Exception:
        return "<file sconosciuto>"


def download_photos(all_photos, base_path):
    console.print(Rule("[bold cyan]FASE 1 · Download[/bold cyan]", style="cyan"))
    console.print(f"[dim]Destinazione:[/dim] {base_path}")
    console.print(
        "[dim]I file già presenti vengono saltati. Gli errori di rete vengono ritentati "
        "automaticamente; gli errori di permesso/autenticazione no.[/dim]\n"
    )

    downloaded_count = 0
    skipped_count = 0
    failed_files = []

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    )

    with progress:
        task = progress.add_task("Download", total=len(all_photos))

        for photo in all_photos:
            fatal_retries = 0

            while True:
                try:
                    created = photo.created
                    year = str(created.year)
                    month = f"{created.month:02d}"
                    filename = photo.filename
                    media_type = (
                        "Video"
                        if filename.lower().endswith((".mp4", ".mov", ".avi", ".m4v"))
                        else "Foto"
                    )

                    folder_path = os.path.join(base_path, year, month, media_type)
                    os.makedirs(folder_path, exist_ok=True)
                    file_path = os.path.join(folder_path, filename)

                    if os.path.exists(file_path):
                        if os.path.getsize(file_path) > 0:
                            skipped_count += 1
                            break
                        else:
                            progress.console.print(
                                f"[yellow]⚠ File vuoto/corrotto {filename}, lo riscarico.[/yellow]"
                            )
                            os.remove(file_path)

                    download_data = photo.download()

                    with open(file_path, "wb") as f:
                        if hasattr(download_data, "iter_content"):
                            for chunk in download_data.iter_content(chunk_size=1024 * 1024):
                                if chunk:
                                    f.write(chunk)
                        else:
                            f.write(download_data)

                    downloaded_count += 1
                    time.sleep(0.2)
                    break

                except OSError as e:
                    # Errori del filesystem locale (disco pieno, permessi negati, ecc.):
                    # ritentare non risolve nulla, meglio fermarsi subito.
                    progress.console.print(
                        f"[bold red]✗ Errore filesystem locale: {e}. "
                        "Interrompo lo script (disco pieno o permessi negati?).[/bold red]"
                    )
                    sys.exit(1)

                except Exception as e:
                    error_msg = str(e)
                    name = safe_filename(photo)

                    if is_fatal_error(error_msg):
                        fatal_retries += 1
                        if fatal_retries >= MAX_RETRIES_ON_FATAL_LIKE:
                            progress.console.print(
                                f"[bold red]✗ {name}: errore non recuperabile "
                                f"({error_msg}). Salto il file.[/bold red]"
                            )
                            failed_files.append(name)
                            break
                        progress.console.print(
                            f"[red]Errore di autenticazione/permessi per {name}. "
                            f"Tentativo {fatal_retries}/{MAX_RETRIES_ON_FATAL_LIKE}...[/red]"
                        )
                        time.sleep(5)
                        continue

                    wait_time = wait_after_error(error_msg)
                    progress.console.print(
                        f"[yellow]⚠ Errore per {name}: {error_msg}. "
                        f"Riprovo tra {wait_time}s...[/yellow]"
                    )
                    time.sleep(wait_time)

            progress.advance(task)

    total_count = len(all_photos)
    table = Table(title="Riepilogo Download", box=None, show_header=False)
    table.add_row("✅ Scaricati", str(downloaded_count))
    table.add_row("⏭️  Già presenti (saltati)", str(skipped_count))
    table.add_row("❌ Falliti", str(len(failed_files)))
    table.add_row("📦 Totale", str(total_count))
    console.print()
    console.print(table)

    if failed_files:
        console.print(
            f"\n[yellow]⚠ {len(failed_files)} file non sono stati scaricati e "
            "NON verranno eliminati da iCloud.[/yellow]"
        )

    console.print("\n[bold green]Tutti gli altri file sono al sicuro sul tuo PC.[/bold green]\n")
    return failed_files


def delete_photos(all_photos, failed_files):
    console.print(Rule("[bold red]FASE 2 · Eliminazione da iCloud[/bold red]", style="red"))

    to_delete = [p for p in all_photos if safe_filename(p) not in failed_files]
    skipped_due_to_failure = len(all_photos) - len(to_delete)

    console.print(
        Panel(
            f"Stai per eliminare definitivamente [bold]{len(to_delete)}[/bold] elementi da iCloud.\n"
            "Le copie locali sul tuo PC NON verranno toccate."
            + (
                f"\n[yellow]{skipped_due_to_failure} file non scaricati correttamente "
                "verranno preservati su iCloud.[/yellow]"
                if skipped_due_to_failure
                else ""
            ),
            title="⚠️  Attenzione",
            border_style="red",
        )
    )

    if not Confirm.ask("[bold]Procedere con l'eliminazione da iCloud?[/bold]", default=False):
        console.print(
            "\n[bold green]Operazione conclusa.[/bold green] "
            "I file sono sul tuo PC, nessuna foto è stata cancellata da iCloud."
        )
        return

    deleted_count = 0
    delete_failed = []

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold red]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    )

    with progress:
        task = progress.add_task("Eliminazione", total=len(to_delete))
        for photo in to_delete:
            name = safe_filename(photo)
            while True:
                try:
                    photo.delete()
                    deleted_count += 1
                    break
                except Exception as e:
                    if "503" in str(e):
                        progress.console.print(
                            "[yellow]⚠ Server occupato durante eliminazione. Attendo...[/yellow]"
                        )
                        time.sleep(10)
                    else:
                        progress.console.print(
                            f"[red]✗ Impossibile eliminare {name}: {e}. Salto.[/red]"
                        )
                        delete_failed.append(name)
                        break
            progress.advance(task)

    table = Table(title="Riepilogo Eliminazione", box=None, show_header=False)
    table.add_row("🗑️  Eliminati", str(deleted_count))
    table.add_row("❌ Falliti", str(len(delete_failed)))
    console.print()
    console.print(table)
    console.print("\n[bold green]Pulizia iCloud completata.[/bold green]\n")


def backup_and_clean_icloud(email, password, base_path):
    api = authenticate(email, password)

    with console.status("[bold green]Accesso alla libreria foto in corso...", spinner="dots"):
        all_photos = list(api.photos.all)
    total_count = len(all_photos)
    console.print(f"[bold]Trovati {total_count} elementi su iCloud.[/bold]\n")

    if total_count == 0:
        console.print("[yellow]Nessun file trovato. Fine.[/yellow]")
        return

    failed_files = download_photos(all_photos, base_path)
    delete_photos(all_photos, failed_files)


if __name__ == "__main__":
    try:
        print_banner()
        EMAIL, PASSWORD, DESTINAZIONE = get_credentials()
        backup_and_clean_icloud(EMAIL, PASSWORD, DESTINAZIONE)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Interrotto dall'utente.[/bold yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[bold red]ERRORE CRITICO DELLO SCRIPT:[/bold red] {e}")
        sys.exit(1)
