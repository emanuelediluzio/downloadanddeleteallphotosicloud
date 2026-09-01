# AGENTS.md

Guida operativa per agenti AI (Claude Code, Copilot, Cursor, ecc.) che lavorano su questo repository. Il README.md è per gli utenti finali (in italiano, guida passo per passo); questo file è per chi deve **modificare il codice**.

## Cos'è questo progetto

Uno script Python che scarica l'intera libreria iCloud Photos in locale e, dopo conferma, la elimina dal cloud. Ha due interfacce che condividono la stessa logica:

* **Terminale** (`photodeleter.py`) — usa [`rich`](https://github.com/Textualize/rich) per barre di progresso, pannelli e prompt.
* **Web** (`photodeleter.py --web` avvia `webui.py`) — server Flask locale (`127.0.0.1` soltanto) con frontend statico in `web/`, per selezionare le foto col mouse.

Tutto il testo rivolto all'utente (messaggi, README, commenti nel codice quando servono) è **in italiano**. Mantieni questa convenzione in ogni modifica.

## Struttura del repository

```
photodeleter.py      Entry point CLI: auth, download, eliminazione, filtri per data/tipo, argparse
webui.py              Server Flask per l'interfaccia web (importa funzioni da photodeleter.py)
web/index.html        Markup della pagina web
web/style.css         Stile (tema scuro, mobile-unfriendly per design: uso desktop)
web/app.js            Logica client: selezione col mouse, filtri, polling delle operazioni, player video
docs/                 Screenshot per il README + generate_screenshots.py per rigenerare quelli del terminale
requirements.txt      pyicloud, rich, flask
.gitignore            Esclude Backup_iCloud/, .miniature/, .upload_tmp/, __pycache__/, .venv/
```

`webui.py` importa direttamente da `photodeleter.py` (stessa cartella, nessun package): `filter_photos`, `is_video`, `parse_date`, `safe_filename`, `wait_after_error`, `is_fatal_error`, `MAX_RETRIES_ON_FATAL_LIKE`, `console`. Se rinomini o sposti una di queste funzioni, aggiorna anche `webui.py`.

## Setup ambiente

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 -m py_compile photodeleter.py webui.py   # verifica minima dopo ogni modifica
```

Non esiste una suite di test automatizzata nel repo (nessuna cartella `tests/`). La verifica si fa con script ad-hoc — vedi sotto.

## Come testare SENZA credenziali iCloud reali

Non avrai mai credenziali Apple vere in questo ambiente, e non devono mai essere richieste all'utente per un test. Testa invece con **oggetti finti che replicano l'interfaccia di `pyicloud.services.photos.PhotoAsset`**:

```python
class FotoFinta:
    def __init__(self, filename, created):
        self.filename = filename   # es. "IMG_001.JPG" / "VID_002.MOV"
        self.created = created     # datetime
        self.size = 1234

    def download(self, version="original"):
        ...  # vedi sotto: il comportamento dipende da `version`
    def delete(self):
        ...
```

### Dettaglio critico: le versioni di `download()`

`PhotoAsset.download(version)` in pyicloud NON restituisce sempre un'immagine. Le versioni disponibili sono (vedi `pyicloud.services.photos.PhotoAsset.PHOTO_VERSION_LOOKUP` / `VIDEO_VERSION_LOOKUP`):

| version | Per una FOTO | Per un VIDEO |
|---|---|---|
| `thumb` | JPEG piccola | **file video piccolo** (resVidSmall) — NON un'immagine |
| `medium` | JPEG media | **file video medio** (resVidMed) — NON un'immagine |
| `thumb_image` | JPEG piccola | JPEG piccola (fotogramma) |
| `medium_image` | JPEG media | JPEG media (fotogramma) |
| `medium_video` | n/d | file video comprimibile per streaming |
| `original` | file originale | file originale |

Questo ha già causato un bug reale (miniature dei video rotte, corretto in `webui.py::api_miniatura` — vedi il commit "Corregge le miniature dei video"). **Se tocchi il codice delle miniature o del player video, un finto oggetto che restituisce sempre la stessa cosa per ogni `version` non basta**: deve differenziare il comportamento come nella tabella sopra, altrimenti il test passa ma il codice reale si rompe.

`webui.py` valida comunque i byte ricevuti con `_sembra_immagine()` (controllo magic number JPEG/PNG/WEBP) prima di servirli o metterli in cache, come rete di sicurezza.

### Test del cuore della logica (download/retry/eliminazione)

Pattern collaudato: creare `FotoFinta` con `fail_times` (quante volte simulare un errore 503 prima di riuscire) e `fatal` (errore 401/403 permanente), chiamare direttamente `download_photos()` / `filter_photos()` / `delete_photos()` da `photodeleter.py`, e verificare:
* la struttura di cartelle generata (`Anno/Mese/Foto|Video/`)
* il numero di tentativi (`MAX_RETRIES_ON_FATAL_LIKE = 3` per errori fatali, retry illimitato per errori transitori)
* che un file fallito nel download resti **escluso** dalla successiva eliminazione (invariante di sicurezza: non si cancella da iCloud nulla che non sia stato scaricato)

### Test dell'interfaccia web (Flask)

Due livelli:

1. **API con `Flask test_client` o `curl`**: istanzia `webui.StatoApp(api_finta, lista_foto_finte, cartella_tmp)`, assegnala a `webui.stato`, poi chiama gli endpoint. Ogni chiamata `/api/*` richiede l'header `X-Token` (o `?t=`) uguale a `webui.stato.token`.
2. **Browser reale con Playwright**: l'ambiente ha Chromium preinstallato in `/opt/pw-browsers/chromium-1194/chrome-linux/chrome` (usa questo path esplicito con `executable_path=`, **non** lanciare `playwright install`, la versione del pacchetto pip può disallinearsi dai browser preinstallati). Serve per verificare cose che un test HTTP non cattura: se un elemento nascosto con `hidden` blocca comunque i click (successo proprio con `.modale[hidden] { display: none }` — un bug reale trovato così), se il rettangolo di selezione via mouse funziona, se un video viene *davvero* decodificato (`video.readyState`, `video.currentTime` che avanza) e non solo richiesto via HTTP.

Per generare un video di prova riproducibile **senza ffmpeg** (non disponibile in questo ambiente, solo il binario ridotto di Playwright per le registrazioni schermo): usa `MediaRecorder` dentro una pagina Playwright (`canvas.captureStream()` + `MediaRecorder` con `video/webm;codecs=vp8`), esporta in base64 via `page.evaluate`, scrivi su disco. Funziona, produce un file `.webm` valido che Chromium riproduce.

Avvio di un server demo per test manuali/visivi: crea uno script che istanzia `webui.avvia_webui(api_finta, foto_finte, cartella, apri_browser=False)` in un processo separato (`setsid nohup ... &`), leggi il token dall'URL stampato in log. Per riavviarlo, libera prima la porta con `fuser -k 8765/tcp` (l'ambiente non ha `ss`).

Tutti questi script di test sono **usa e getta**: vivono nella scratchpad directory della sessione, mai nel repository.

## Convenzioni di sicurezza da NON violare

* **Nessuna credenziale hardcoded.** Email/password sempre da prompt (`rich.Prompt.ask(password=True)`) o variabili d'ambiente (`ICLOUD_EMAIL`, `ICLOUD_PASSWORD`, `ICLOUD_BACKUP_PATH`).
* **La password non va mai salvata su disco.** `~/.icloud_photodeleter_config.json` salva solo email e cartella di destinazione (vedi `load_saved_config`/`save_config` in `photodeleter.py`).
* **Il server web ascolta solo su `127.0.0.1`** e rifiuta richieste con header `Origin` esterno (protezione CSRF minimale, vedi `controlla_accesso()` in `webui.py`). Non estendere l'ascolto a `0.0.0.0` senza aggiungere autenticazione vera.
* **Il token di accesso web** (`stato.token`, generato con `secrets.token_urlsafe`) va confrontato con `secrets.compare_digest`, mai con `==`.
* **L'eliminazione da iCloud è irreversibile.** Qualunque modifica al flusso di eliminazione deve preservare: (a) conferma esplicita dell'utente, (b) esclusione automatica dei file che non sono stati scaricati con successo, (c) messaggio chiaro prima dell'azione.

## Convenzioni di errore

`is_fatal_error()` distingue errori permanenti (401/403/auth) — ritentati poche volte poi il file viene saltato — da errori transitori (503/connessione) — ritentati a oltranza con attesa crescente (`wait_after_error()`). Se aggiungi nuovi tipi di errore da gestire, decidi esplicitamente in quale categoria cadono: un errore permanente trattato come transitorio blocca lo script all'infinito (bug già corretto una volta, vedi storia commit); un errore transitorio trattato come permanente fa perdere file scaricabili.

Gli errori del filesystem locale (`OSError`: disco pieno, permessi) vanno gestiti a parte e **devono interrompere subito**, mai essere ritentati: non si risolvono aspettando.

## Dopo ogni modifica visibile all'utente

1. Se cambi l'interfaccia terminale: rigenera gli screenshot con `python docs/generate_screenshots.py`.
2. Se cambi l'interfaccia web: rifai gli screenshot con Playwright (vedi sopra) e sostituisci i file in `docs/web-*.png`.
3. Aggiorna il README.md corrispondente (ha due percorsi paralleli: "PARTE 2 — Interfaccia grafica" e "PARTE 3 — Solo terminale"; tienili sincronizzati se cambi un comportamento comune a entrambi, es. i filtri o la gestione errori).
4. Verifica che ogni immagine referenziata nel README esista davvero: `grep -oE 'docs/[0-9a-z-]+\.(svg|png)' README.md | sort -u | xargs -I{} test -f {}`.

## Comandi rapidi

```bash
# Verifica sintattica
python3 -m py_compile photodeleter.py webui.py

# Help della CLI
python3 photodeleter.py --help

# Avvio interfaccia web (richiede credenziali reali)
python3 photodeleter.py --web

# Rigenera gli screenshot del terminale
python docs/generate_screenshots.py
```

## Cosa NON fare

* Non aggiungere dipendenze pesanti senza necessità reale (il progetto è volutamente minimale: 3 dipendenze in `requirements.txt`).
* Non introdurre codice che invia dati a servizi esterni oltre ad Apple (iCloud) senza che sia esplicitamente richiesto — è uno strumento di backup personale, la fiducia dell'utente sui suoi dati è il punto centrale del progetto.
* Non rimuovere le conferme di sicurezza (doppia conferma web con checkbox, prompt `[y/n]` da terminale) per "velocizzare" il flusso.
* Non committare cartelle di backup, cache miniature, o screenshot di test generati con dati finti dentro `docs/` se rappresentano dati reali di un utente — solo dati sintetici o mockup sono accettabili nel repository pubblico.
