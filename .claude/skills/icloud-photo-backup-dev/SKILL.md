---
name: icloud-photo-backup-dev
description: Testare e far girare questo progetto (iCloud Photo Backup & Cleaner) senza credenziali iCloud reali — foto/video finti, server demo della web UI, verifica con Playwright. Usarla quando si modifica src/icloud_photo_backup/, webui.py, web/, o prima di dichiarare "fatto" su una modifica a questo repository.
---

# iCloud Photo Backup & Cleaner — sviluppo e test

Guida operativa rapida per verificare modifiche a questo progetto. Per il contesto completo (struttura, convenzioni di sicurezza, invarianti da non rompere) leggi prima `AGENTS.md` nella root del repo — questa skill è il complemento pratico, pensato per essere eseguito passo passo.

## 0. Non richiedere mai credenziali Apple reali

Non ci sono e non ci devono essere credenziali iCloud vere in questo ambiente. Ogni verifica va fatta con oggetti finti che replicano l'interfaccia di `pyicloud.services.photos.PhotoAsset`.

## 1. Verifica minima dopo ogni modifica

```bash
cd <root del repo>
python3 -m py_compile src/icloud_photo_backup/*.py photodeleter.py
python3 photodeleter.py --help   # la CLI deve rispondere senza installare nulla
```

## 2. Il dettaglio che rompe le cose se lo ignori: `download(version)`

`PhotoAsset.download(version)` NON restituisce sempre un'immagine. Un oggetto finto che ignora `version` e restituisce sempre la stessa cosa fa passare i test ma nasconde bug reali (è già successo: miniature dei video rotte).

| version | FOTO | VIDEO |
|---|---|---|
| `thumb` / `medium` | JPEG | **file video** — non un'immagine |
| `thumb_image` / `medium_image` | JPEG | JPEG (fotogramma) |
| `medium_video` | n/d | video comprimibile per lo streaming |
| `original` | file originale | file originale |

Modello minimo di foto/video finto da usare nei test:

```python
class FotoFinta:
    def __init__(self, filename, created, size=1234):
        self.filename = filename  # "IMG_001.JPG" oppure "VID_002.MOV"
        self.created = created    # datetime
        self.size = size

    def download(self, version="original"):
        # differenzia il comportamento in base a version E all'estensione,
        # come nella tabella sopra — altrimenti il test non vale nulla
        ...

    def delete(self):
        ...
```

## 3. Test del cuore della logica (senza rete, senza browser)

Crea `FotoFinta` con `fail_times` (N errori 503 prima di riuscire) e `fatal` (errore 401/403 permanente), poi chiama direttamente le funzioni di `icloud_photo_backup.cli`:

```python
import sys, time
sys.path.insert(0, "<root del repo>/src")
time.sleep = lambda s: None  # azzera le attese nei test

from icloud_photo_backup import cli as pd

# pd.download_photos(lista_foto, cartella_tmp)
# pd.filter_photos(lista_foto, data_da, data_a, tipo)
# pd.delete_photos(lista_foto, falliti)
# pd.carica_su_icloud(email, password, percorso)   # patcha pd.authenticate per evitare rete
```

Verifica sempre questi tre invarianti dopo una modifica al flusso principale:
1. Struttura di cartelle `Anno/Mese/Foto|Video/` corretta.
2. Un file fallito nel download resta **escluso** dall'eliminazione (mai cancellare da iCloud qualcosa che non è stato scaricato).
3. Errore fatale → si ferma dopo `MAX_RETRIES_ON_FATAL_LIKE` tentativi, mai un ciclo infinito.

## 4. Server demo per test manuali/visivi della web UI

```python
# avvia_demo.py (usa e getta, nella scratchpad, mai nel repo)
import sys
sys.path.insert(0, "<root del repo>/src")
from icloud_photo_backup import webui

# webui.avvia_webui(api_finta, lista_foto_finte, cartella_tmp, porta=8765, apri_browser=False)
```

Avvio in background, lettura del token dal log:

```bash
setsid nohup python3 avvia_demo.py > demo.log 2>&1 < /dev/null &
sleep 5
grep -a -oP 'http://127\.0\.0\.1:8765/\?t=[\w_-]+' demo.log
```

Per riavviarlo, libera prima la porta — l'ambiente **non ha `ss`**:

```bash
fuser -k 8765/tcp 2>/dev/null; sleep 2
```

Se servono foto realistiche negli screenshot (non quadrati colorati generati al volo): scarica foto stock da Picsum, nessuna API key richiesta —

```bash
curl -sSL -o foto_1.jpg "https://picsum.photos/seed/qualcosa1/600/600"
```

Se serve un video vero riproducibile e non hai `ffmpeg` (non disponibile in questo ambiente): genera un `.webm` con `MediaRecorder` dentro una pagina Playwright (`canvas.captureStream()` + `MediaRecorder`), esporta in base64 via `page.evaluate`, scrivi su disco.

## 5. Browser reale con Playwright — quando un test HTTP non basta

Serve per cose che un `curl`/`test_client` non cattura: un elemento con `hidden` che blocca comunque i click (bug reale già trovato: `display: block` in CSS vince su `[hidden]` se non c'è la regola `.classe[hidden] { display: none }`), il rettangolo di selezione via mouse, se un video viene *davvero* decodificato.

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
    )
    # NON lanciare "playwright install": la versione pip puo' disallinearsi
    # dai browser preinstallati, usa questo path esplicito.
```

Verifiche utili su un `<video>`:

```python
pagina.wait_for_function("document.getElementById('player-video').readyState >= 2")
# poi controlla videoWidth/videoHeight/error, e che currentTime avanzi davvero
```

Per il drag & drop, simula un vero `DataTransfer` con `page.evaluate` e dispatcha `dragenter`/`dragover`/`drop` su `window` (non basta un click, serve un evento `DragEvent` vero con `dataTransfer` popolato).

## 6. Dopo ogni modifica visibile all'utente

1. Rigenera gli screenshot toccati: `python docs/generate_screenshots.py` (terminale) o rifai gli screenshot Playwright (web) e sostituisci i file in `docs/web-*.png`.
2. Verifica che ogni immagine nel README esista: `grep -oE 'docs/[0-9a-z-]+\.(svg|png)' README.md | sort -u | xargs -I{} test -f {} || echo "MANCA: {}"`.
3. Se hai toccato `pyproject.toml` o la struttura di `src/`, verifica anche l'installazione come pacchetto: `pip install -e .` in un venv pulito, poi `icloud-photo-backup --help`.
