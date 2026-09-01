#!/usr/bin/env python3
"""Interfaccia web locale per iCloud Photo Backup & Cleaner.

Avvia un piccolo server sul proprio computer (non raggiungibile da
internet) che mostra le miniature della libreria iCloud e permette di
selezionare gli elementi con il mouse per scaricarli, eliminarli o
caricarne di nuovi.

Non va eseguito direttamente: si avvia con

    python photodeleter.py --web
"""
import io
import os
import secrets
import threading
import time
import webbrowser
from datetime import datetime

from flask import Flask, abort, jsonify, request, send_file, send_from_directory

from photodeleter import (
    console,
    filter_photos,
    is_video,
    parse_date,
    safe_filename,
    wait_after_error,
    is_fatal_error,
    MAX_RETRIES_ON_FATAL_LIKE,
)

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
THUMB_DIR_NAME = ".miniature"

app = Flask(__name__, static_folder=None)
stato = None  # istanza di StatoApp, valorizzata da avvia_webui()


# --------------------------------------------------------------------------
# Stato dell'applicazione
# --------------------------------------------------------------------------
class StatoApp:
    def __init__(self, api, foto, base_path):
        self.api = api
        self.foto = foto
        self.base_path = base_path
        self.token = secrets.token_urlsafe(24)
        self.lock = threading.Lock()
        self.operazioni = {}
        self.thumb_dir = os.path.join(base_path, THUMB_DIR_NAME)
        os.makedirs(self.thumb_dir, exist_ok=True)
        self.meta = self._calcola_metadati()

    def _calcola_metadati(self):
        """Legge una volta sola i metadati di ogni elemento."""
        meta = []
        for i, foto in enumerate(self.foto):
            try:
                nome = foto.filename
            except Exception:
                nome = None
            try:
                creata = foto.created
            except Exception:
                creata = None
            try:
                dimensione = foto.size
            except Exception:
                dimensione = None

            meta.append(
                {
                    "id": i,
                    "nome": nome or "(nome non disponibile)",
                    "data": creata.isoformat() if creata else None,
                    "data_breve": creata.strftime("%d/%m/%Y") if creata else "—",
                    "tipo": "video" if (nome and is_video(nome)) else "foto",
                    "dimensione": dimensione,
                    "leggibile": nome is not None and creata is not None,
                }
            )
        return meta

    def elimina_dai_dati(self, ids):
        """Toglie dalla lista in memoria gli elementi eliminati da iCloud."""
        rimossi = set(ids)
        with self.lock:
            self.foto = [f for i, f in enumerate(self.foto) if i not in rimossi]
            self.meta = self._calcola_metadati()


# --------------------------------------------------------------------------
# Sicurezza: solo localhost e solo con il token generato all'avvio
# --------------------------------------------------------------------------
@app.before_request
def controlla_accesso():
    if request.remote_addr not in ("127.0.0.1", "::1"):
        abort(403)

    # Blocca le richieste inviate da una pagina web esterna (CSRF)
    origine = request.headers.get("Origin")
    if origine and not origine.startswith(("http://127.0.0.1", "http://localhost")):
        abort(403)

    if request.path.startswith("/api/"):
        token = request.headers.get("X-Token") or request.args.get("t")
        if not token or not secrets.compare_digest(token, stato.token):
            abort(401)


# --------------------------------------------------------------------------
# Pagine statiche
# --------------------------------------------------------------------------
@app.route("/")
def home():
    return send_from_directory(WEB_DIR, "index.html")


@app.route("/static/<path:nome>")
def statici(nome):
    return send_from_directory(WEB_DIR, nome)


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
@app.route("/api/stato")
def api_stato():
    return jsonify(
        {
            "totale": len(stato.meta),
            "destinazione": os.path.abspath(stato.base_path),
        }
    )


@app.route("/api/elementi")
def api_elementi():
    """Elenco filtrato per data e tipo."""
    data_da = parse_date(request.args.get("da", ""))
    data_a = parse_date(request.args.get("a", ""))
    tipo = request.args.get("tipo", "tutti")
    if tipo not in ("tutti", "foto", "video"):
        tipo = "tutti"

    risultato = []
    for m in stato.meta:
        if tipo != "tutti" and m["tipo"] != tipo:
            continue
        if data_da or data_a:
            if not m["data"]:
                continue
            giorno = datetime.fromisoformat(m["data"]).date()
            if data_da and giorno < data_da:
                continue
            if data_a and giorno > data_a:
                continue
        risultato.append(m)

    return jsonify({"elementi": risultato, "totale": len(risultato)})


@app.route("/api/miniatura/<int:id_foto>")
def api_miniatura(id_foto):
    """Miniatura di un elemento, con cache su disco."""
    if id_foto < 0 or id_foto >= len(stato.foto):
        abort(404)

    percorso_cache = os.path.join(stato.thumb_dir, f"{id_foto}.jpg")
    if os.path.exists(percorso_cache) and os.path.getsize(percorso_cache) > 0:
        return send_file(percorso_cache, mimetype="image/jpeg")

    foto = stato.foto[id_foto]
    dati = None
    for versione in ("thumb", "medium"):
        try:
            dati = foto.download(versione)
            if dati:
                break
        except Exception:
            continue

    if not dati:
        abort(404)

    if hasattr(dati, "read"):
        dati = dati.read()

    try:
        with open(percorso_cache, "wb") as f:
            f.write(dati)
    except OSError:
        pass  # cache non essenziale

    return send_file(io.BytesIO(dati), mimetype="image/jpeg")


@app.route("/api/operazione", methods=["POST"])
def api_operazione():
    """Avvia scaricamento o eliminazione in background."""
    corpo = request.get_json(silent=True) or {}
    azione = corpo.get("azione")
    ids = corpo.get("ids") or []

    if azione not in ("scarica", "elimina"):
        return jsonify({"errore": "azione non valida"}), 400
    if not ids:
        return jsonify({"errore": "nessun elemento selezionato"}), 400
    if azione == "elimina" and corpo.get("conferma") is not True:
        return jsonify({"errore": "conferma mancante"}), 400

    ids = [i for i in ids if isinstance(i, int) and 0 <= i < len(stato.foto)]

    id_op = secrets.token_urlsafe(8)
    stato.operazioni[id_op] = {
        "azione": azione,
        "totale": len(ids),
        "fatti": 0,
        "riusciti": 0,
        "falliti": 0,
        "saltati": 0,
        "messaggi": [],
        "finita": False,
        "corrente": "",
    }

    thread = threading.Thread(target=_esegui_operazione, args=(id_op, azione, ids), daemon=True)
    thread.start()
    return jsonify({"id": id_op})


@app.route("/api/operazione/<id_op>")
def api_stato_operazione(id_op):
    op = stato.operazioni.get(id_op)
    if not op:
        abort(404)
    return jsonify(op)


@app.route("/api/carica", methods=["POST"])
def api_carica():
    """Carica su iCloud i file scelti dall'utente."""
    file_ricevuti = request.files.getlist("file")
    if not file_ricevuti:
        return jsonify({"errore": "nessun file ricevuto"}), 400

    cartella_tmp = os.path.join(stato.base_path, ".upload_tmp")
    os.makedirs(cartella_tmp, exist_ok=True)

    caricati, falliti = [], []
    for f in file_ricevuti:
        nome = os.path.basename(f.filename or "")
        if not nome:
            continue
        percorso = os.path.join(cartella_tmp, nome)
        try:
            f.save(percorso)
            stato.api.photos.upload(percorso)
            caricati.append(nome)
        except Exception as e:
            falliti.append({"nome": nome, "errore": str(e)})
        finally:
            try:
                os.remove(percorso)
            except OSError:
                pass

    return jsonify({"caricati": caricati, "falliti": falliti})


# --------------------------------------------------------------------------
# Esecuzione delle operazioni lunghe
# --------------------------------------------------------------------------
def _esegui_operazione(id_op, azione, ids):
    op = stato.operazioni[id_op]

    for id_foto in ids:
        foto = stato.foto[id_foto]
        nome = safe_filename(foto)
        op["corrente"] = nome

        if azione == "scarica":
            esito = _scarica_uno(foto, nome, op)
        else:
            esito = _elimina_uno(foto, nome, op)

        op[esito] = op.get(esito, 0) + 1
        op["fatti"] += 1

    if azione == "elimina" and op["riusciti"]:
        eliminati = [i for i in ids]
        stato.elimina_dai_dati(eliminati)

    op["corrente"] = ""
    op["finita"] = True


def _scarica_uno(foto, nome, op):
    tentativi_fatali = 0
    while True:
        try:
            creata = foto.created
            cartella = os.path.join(
                stato.base_path,
                str(creata.year),
                f"{creata.month:02d}",
                "Video" if is_video(nome) else "Foto",
            )
            os.makedirs(cartella, exist_ok=True)
            percorso = os.path.join(cartella, nome)

            if os.path.exists(percorso) and os.path.getsize(percorso) > 0:
                return "saltati"

            dati = foto.download()
            with open(percorso, "wb") as f:
                if hasattr(dati, "iter_content"):
                    for pezzo in dati.iter_content(chunk_size=1024 * 1024):
                        if pezzo:
                            f.write(pezzo)
                else:
                    f.write(dati)
            return "riusciti"

        except OSError as e:
            op["messaggi"].append(f"Errore disco su {nome}: {e}")
            return "falliti"

        except Exception as e:
            messaggio = str(e)
            if is_fatal_error(messaggio):
                tentativi_fatali += 1
                if tentativi_fatali >= MAX_RETRIES_ON_FATAL_LIKE:
                    op["messaggi"].append(f"{nome}: errore non recuperabile ({messaggio})")
                    return "falliti"
                time.sleep(5)
                continue
            attesa = wait_after_error(messaggio)
            op["messaggi"].append(f"{nome}: {messaggio}. Riprovo tra {attesa}s")
            time.sleep(attesa)


def _elimina_uno(foto, nome, op):
    tentativi = 0
    while True:
        try:
            foto.delete()
            return "riusciti"
        except Exception as e:
            if "503" in str(e) and tentativi < 3:
                tentativi += 1
                time.sleep(10)
                continue
            op["messaggi"].append(f"Impossibile eliminare {nome}: {e}")
            return "falliti"


# --------------------------------------------------------------------------
# Avvio
# --------------------------------------------------------------------------
def avvia_webui(api, foto, base_path, porta=8765, apri_browser=True):
    global stato
    stato = StatoApp(api, foto, base_path)

    indirizzo = f"http://127.0.0.1:{porta}/?t={stato.token}"

    console.print()
    console.print("[bold green]✓ Interfaccia web avviata.[/bold green]")
    console.print(f"[bold]Apri questo indirizzo nel browser:[/bold]\n[cyan]{indirizzo}[/cyan]")
    console.print(
        "\n[dim]Il server è accessibile solo da questo computer. "
        "Premi Ctrl+C in questa finestra per chiuderlo.[/dim]\n"
    )

    if apri_browser:
        threading.Timer(1.0, lambda: webbrowser.open(indirizzo)).start()

    app.run(host="127.0.0.1", port=porta, threaded=True, debug=False)
