#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
from datetime import datetime

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

# File dove vengono ricordati email e cartella di destinazione tra un
# avvio e l'altro (la password NON viene mai salvata su disco).
CONFIG_PATH = os.path.expanduser("~/.icloud_photodeleter_config.json")

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

# Estensioni considerate video (tutto il resto e' trattato come foto)
VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".m4v")

# Formati di data accettati nei prompt e negli argomenti da riga di comando
DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y")


def print_banner():
    banner = (
        "[bold white]📸  iCloud Photo Backup & Cleaner  ☁️[/bold white]\n"
        "[dim]Backup sicuro in locale, poi pulizia di iCloud su tua conferma[/dim]"
    )
    console.print(Panel.fit(banner, border_style="cyan", padding=(1, 4)))


def load_saved_config() -> dict:
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(email: str, destination: str) -> None:
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump({"email": email, "destination": destination}, f)
    except OSError:
        pass  # non bloccante: se non riesce a salvare, pazienza


def get_credentials():
    console.print(Rule("[bold cyan]Accesso[/bold cyan]", style="cyan"))
    saved = load_saved_config()

    email = os.environ.get("ICLOUD_EMAIL")
    if not email:
        email = Prompt.ask("📧 [bold]Apple ID[/bold]", default=saved.get("email"))

    password = os.environ.get("ICLOUD_PASSWORD") or Prompt.ask(
        "🔑 [bold]Password[/bold]", password=True
    )

    destination = os.environ.get("ICLOUD_BACKUP_PATH")
    if not destination:
        destination = Prompt.ask(
            "📁 [bold]Cartella di destinazione[/bold]",
            default=saved.get("destination", "./Backup_iCloud"),
        )

    save_config(email, destination)
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


def is_video(filename: str) -> bool:
    return filename.lower().endswith(VIDEO_EXTENSIONS)


def parse_date(text: str):
    """Converte una data scritta dall'utente. Restituisce None se non valida."""
    text = (text or "").strip()
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def ask_date(label: str):
    """Chiede una data finche' non e' valida. Invio vuoto = nessun limite."""
    while True:
        raw = Prompt.ask(f"{label} [dim](GG/MM/AAAA, Invio per nessun limite)[/dim]", default="")
        if not raw.strip():
            return None
        parsed = parse_date(raw)
        if parsed:
            return parsed
        console.print("[red]Data non valida. Esempio corretto: 31/12/2023[/red]")


def ask_filters():
    """Menu interattivo di selezione. Restituisce (data_da, data_a, tipo)."""
    console.print(Rule("[bold cyan]Selezione[/bold cyan]", style="cyan"))

    console.print("Quali elementi vuoi elaborare?")
    console.print("  [bold]1[/bold]) Tutta la libreria")
    console.print("  [bold]2[/bold]) Solo un intervallo di date")
    scelta = Prompt.ask("Scelta", choices=["1", "2"], default="1")

    data_da = data_a = None
    if scelta == "2":
        while True:
            data_da = ask_date("📆 [bold]Dalla data[/bold]")
            data_a = ask_date("📆 [bold]Alla data[/bold]")
            if data_da and data_a and data_da > data_a:
                console.print("[red]La data iniziale è successiva a quella finale. Riprova.[/red]")
                continue
            break

    console.print("\nQuale tipo di media?")
    console.print("  [bold]1[/bold]) Foto e video")
    console.print("  [bold]2[/bold]) Solo foto")
    console.print("  [bold]3[/bold]) Solo video")
    tipo = {"1": "tutti", "2": "foto", "3": "video"}[
        Prompt.ask("Scelta", choices=["1", "2", "3"], default="1")
    ]

    return data_da, data_a, tipo


def describe_filter(data_da, data_a, tipo) -> str:
    """Descrizione leggibile dei filtri attivi."""
    parti = []
    if data_da and data_a:
        parti.append(f"dal {data_da:%d/%m/%Y} al {data_a:%d/%m/%Y}")
    elif data_da:
        parti.append(f"dal {data_da:%d/%m/%Y} in poi")
    elif data_a:
        parti.append(f"fino al {data_a:%d/%m/%Y}")

    if tipo == "foto":
        parti.append("solo foto")
    elif tipo == "video":
        parti.append("solo video")

    return ", ".join(parti) if parti else "tutta la libreria"


def filter_photos(all_photos, data_da, data_a, tipo):
    """Applica i filtri di data e tipo. La selezione vale sia per il
    download che per l'eliminazione."""
    if not data_da and not data_a and tipo == "tutti":
        return all_photos

    selezionati = []
    illeggibili = 0

    for photo in all_photos:
        # --- filtro per tipo di media ---
        if tipo != "tutti":
            try:
                nome = photo.filename
            except Exception:
                illeggibili += 1
                continue  # nel dubbio si esclude: l'eliminazione e' irreversibile
            if is_video(nome) and tipo != "video":
                continue
            if not is_video(nome) and tipo != "foto":
                continue

        # --- filtro per data ---
        if data_da or data_a:
            try:
                creata = photo.created.date()
            except Exception:
                illeggibili += 1
                continue  # nel dubbio si esclude
            if data_da and creata < data_da:
                continue
            if data_a and creata > data_a:
                continue

        selezionati.append(photo)

    if illeggibili:
        console.print(
            f"[yellow]⚠ {illeggibili} elementi esclusi: data o nome file illeggibili.[/yellow]"
        )

    return selezionati


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
                    media_type = "Video" if is_video(filename) else "Foto"

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
    table = Table(title="Riepilogo Download", box=None, show_header=False, min_width=34)
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


def delete_photos(all_photos, failed_files, filter_desc=None):
    console.print(Rule("[bold red]FASE 2 · Eliminazione da iCloud[/bold red]", style="red"))

    to_delete = [p for p in all_photos if safe_filename(p) not in failed_files]
    skipped_due_to_failure = len(all_photos) - len(to_delete)

    console.print(
        Panel(
            f"Stai per eliminare definitivamente [bold]{len(to_delete)}[/bold] elementi da iCloud.\n"
            "Le copie locali sul tuo PC NON verranno toccate."
            + (
                f"\n[cyan]Selezione attiva: {filter_desc}. "
                "Il resto della libreria non verrà toccato.[/cyan]"
                if filter_desc
                else ""
            )
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
        TimeRemainingColumn(),
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

    table = Table(title="Riepilogo Eliminazione", box=None, show_header=False, min_width=34)
    table.add_row("🗑️  Eliminati", str(deleted_count))
    table.add_row("❌ Falliti", str(len(delete_failed)))
    console.print()
    console.print(table)
    console.print("\n[bold green]Pulizia iCloud completata.[/bold green]\n")


def backup_and_clean_icloud(email, password, base_path, data_da=None, data_a=None, tipo=None):
    api = authenticate(email, password)

    with console.status("[bold green]Accesso alla libreria foto in corso...", spinner="dots"):
        all_photos = list(api.photos.all)
    total_count = len(all_photos)
    console.print(f"[bold]Trovati {total_count} elementi su iCloud.[/bold]\n")

    if total_count == 0:
        console.print("[yellow]Nessun file trovato. Fine.[/yellow]")
        return

    # Se non e' stato passato nessun filtro da riga di comando, lo si chiede
    if data_da is None and data_a is None and tipo is None:
        data_da, data_a, tipo = ask_filters()
    tipo = tipo or "tutti"

    selezionati = filter_photos(all_photos, data_da, data_a, tipo)
    filtro_attivo = len(selezionati) != total_count
    descrizione = describe_filter(data_da, data_a, tipo)

    if filtro_attivo:
        console.print(
            Panel.fit(
                f"Selezionati [bold]{len(selezionati)}[/bold] elementi su {total_count}\n"
                f"[dim]Criterio: {descrizione}[/dim]",
                border_style="cyan",
                title="🎯 Selezione",
            )
        )

    if not selezionati:
        console.print("\n[yellow]Nessun elemento corrisponde ai criteri scelti. Fine.[/yellow]")
        return

    console.print()
    failed_files = download_photos(selezionati, base_path)
    delete_photos(selezionati, failed_files, descrizione if filtro_attivo else None)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scarica la libreria iCloud Photos in locale e, su conferma, la elimina dal cloud.",
        epilog="Senza argomenti lo script chiede tutto in modo interattivo.",
    )
    parser.add_argument("--da", metavar="DATA", help="Elabora solo da questa data (GG/MM/AAAA)")
    parser.add_argument("--a", metavar="DATA", help="Elabora solo fino a questa data (GG/MM/AAAA)")
    parser.add_argument(
        "--tipo",
        choices=["tutti", "foto", "video"],
        help="Limita a sole foto o soli video (predefinito: tutti)",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Avvia l'interfaccia grafica nel browser invece di usare il terminale",
    )
    parser.add_argument(
        "--porta",
        type=int,
        default=8765,
        metavar="N",
        help="Porta dell'interfaccia web (predefinita: 8765)",
    )
    args = parser.parse_args()

    data_da = data_a = None
    if args.da:
        data_da = parse_date(args.da)
        if not data_da:
            parser.error(f"data non valida per --da: {args.da} (formato atteso: GG/MM/AAAA)")
    if args.a:
        data_a = parse_date(args.a)
        if not data_a:
            parser.error(f"data non valida per --a: {args.a} (formato atteso: GG/MM/AAAA)")
    if data_da and data_a and data_da > data_a:
        parser.error("la data di --da è successiva a quella di --a")

    return args, data_da, data_a, args.tipo


def avvia_interfaccia_web(email, password, base_path, porta):
    """Autentica nel terminale e poi apre l'interfaccia grafica nel browser."""
    try:
        from .webui import avvia_webui
    except ImportError:
        console.print(
            "\n[bold red]✗ Manca la libreria Flask, necessaria per l'interfaccia web.[/bold red]\n"
            "Installala con: [cyan]pip install -r requirements.txt[/cyan]"
        )
        sys.exit(1)

    api = authenticate(email, password)

    with console.status("[bold green]Accesso alla libreria foto in corso...", spinner="dots"):
        all_photos = list(api.photos.all)
    console.print(f"[bold]Trovati {len(all_photos)} elementi su iCloud.[/bold]")

    if not all_photos:
        console.print("[yellow]Nessun file trovato. Fine.[/yellow]")
        return

    os.makedirs(base_path, exist_ok=True)
    avvia_webui(api, all_photos, base_path, porta=porta)


def main():
    try:
        ARGS, DATA_DA, DATA_A, TIPO = parse_args()
        print_banner()
        EMAIL, PASSWORD, DESTINAZIONE = get_credentials()
        if ARGS.web:
            avvia_interfaccia_web(EMAIL, PASSWORD, DESTINAZIONE, ARGS.porta)
        else:
            backup_and_clean_icloud(EMAIL, PASSWORD, DESTINAZIONE, DATA_DA, DATA_A, TIPO)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Interrotto dall'utente.[/bold yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[bold red]ERRORE CRITICO DELLO SCRIPT:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
