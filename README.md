# iCloud Photo Backup & Cleaner 📸 ☁️

Script Python da terminale per **scaricare l'intera libreria iCloud Photos** sul proprio computer, organizzarla in cartelle ordinate e — solo dopo che il backup è riuscito — **liberare spazio su iCloud** eliminando le foto dal cloud.

<p align="center">
  <img src="docs/01-avvio.svg" alt="Schermata di avvio e accesso" width="100%">
</p>

---

## ✨ Funzionalità

| | |
|---|---|
| 📅 **Organizzazione automatica** | I file vengono ordinati in `Anno / Mese / Foto o Video`, non ammassati in un'unica cartella |
| ⏸️ **Riprendibile** | I file già scaricati vengono saltati: se il backup si interrompe, basta rilanciarlo |
| 📊 **Barre di progresso** | Contatore file, tempo trascorso e **tempo rimanente stimato**, sia in download che in eliminazione |
| 💾 **Ricorda le impostazioni** | Email e cartella di destinazione vengono riproposte al prossimo avvio |
| 🔐 **Password mai salvata** | Input nascosto a runtime, nessuna credenziale scritta nel codice o su disco |
| 🔁 **Retry intelligente** | Ritenta automaticamente sugli errori di rete, si ferma su quelli irrecuperabili |
| 🛡️ **Eliminazione sicura** | Avviene solo dopo il download completo, con conferma esplicita, e **salta i file non scaricati** |
| 🎞️ **Video pesanti** | Download a blocchi (chunk) per non saturare la memoria con i 4K |

---

## 🚀 Requisiti e installazione

Serve **Python 3.8+**. Clona il repository e installa le dipendenze:

```bash
git clone https://github.com/emanuelediluzio/downloadanddeleteallphotosicloud.git
cd downloadanddeleteallphotosicloud
pip install -r requirements.txt
```

Dipendenze installate: [`pyicloud`](https://github.com/picklepete/pyicloud) (API iCloud) e [`rich`](https://github.com/Textualize/rich) (interfaccia terminale).

---

## 🛠️ Come si usa (passo per passo)

### Passo 1 — Avvia lo script

```bash
python photodeleter.py
```

### Passo 2 — Inserisci le credenziali

Lo script chiede **Apple ID**, **password** (input nascosto) e **cartella di destinazione**.
Se hai già eseguito lo script in passato, i valori salvati vengono riproposti tra parentesi: premi **Invio** per confermarli.

### Passo 3 — Codice 2FA

Se il tuo account ha l'autenticazione a due fattori, inserisci il codice a 6 cifre che compare sui tuoi dispositivi Apple. La sessione viene poi marcata come *fidata* (vedi la schermata a inizio pagina).

### Passo 4 — Attendi il download (Fase 1)

Lo script scarica tutti i file organizzandoli per anno/mese/tipo. La barra mostra a che punto è, da quanto sta lavorando e **quanto manca alla fine**.

> 💡 Puoi interrompere in qualsiasi momento con `Ctrl+C` e riprendere più tardi: i file già scaricati non verranno riscaricati.

![Fase di download](docs/02-download.svg)

### Passo 5 — Controlla il riepilogo e conferma

A fine download vedi la tabella con scaricati / saltati / falliti. Solo a questo punto ti viene chiesto se vuoi eliminare le foto da iCloud: rispondi `y` per procedere o `n` (predefinito) per uscire lasciando iCloud intatto.

![Riepilogo e conferma](docs/03-riepilogo.svg)

### Passo 6 — Eliminazione da iCloud (Fase 2)

Se hai confermato, le foto vengono rimosse da iCloud con una seconda barra di progresso. **Le copie sul tuo computer non vengono toccate.**

![Fase di eliminazione](docs/04-eliminazione.svg)

---

## ⚙️ Configurazione

### Impostazioni ricordate

Dopo il primo avvio, **email** e **cartella di destinazione** vengono salvate in:

```text
~/.icloud_photodeleter_config.json
```

e riproposte come valore predefinito. La **password non viene mai salvata su disco**.

### Variabili d'ambiente (per automazioni)

Per eseguire lo script senza prompt interattivi:

```bash
export ICLOUD_EMAIL="tuo_id@icloud.com"
export ICLOUD_PASSWORD="tua_password"
export ICLOUD_BACKUP_PATH="./Backup_iCloud"
python photodeleter.py
```

| Variabile | Descrizione |
|---|---|
| `ICLOUD_EMAIL` | Apple ID |
| `ICLOUD_PASSWORD` | Password (o password specifica per app) |
| `ICLOUD_BACKUP_PATH` | Cartella locale di destinazione |

> ⚠️ Se usi le variabili d'ambiente, evita di lasciare la password nella cronologia della shell.

---

## 📁 Struttura della cartella di output

```text
Backup_iCloud/
├── 2023/
│   ├── 01/
│   │   ├── Foto/
│   │   │   └── IMG_001.JPG
│   │   └── Video/
│   │       └── VIDEO_002.MOV
│   └── 05/
│       └── Foto/
│           └── IMG_042.HEIC
└── 2024/
    └── 12/
        └── Foto/
            └── IMG_999.PNG
```

---

## 🔁 Gestione degli errori

Lo script distingue tre tipi di problema, per non restare mai bloccato all'infinito:

| Tipo di errore | Comportamento |
|---|---|
| **Rete / server occupato** (503, connessione persa) | Ritenta automaticamente con attesa progressiva (5s → 10s → 30s), senza perdere nessun file |
| **Autenticazione / permessi** (401, 403) | Ritenta 3 volte, poi salta il file e lo segnala: viene **escluso dall'eliminazione** su iCloud |
| **Disco locale** (spazio esaurito, permessi negati) | Interrompe subito lo script con un messaggio chiaro, invece di ritentare a vuoto |

I file da 0 byte (download corrotti) vengono rilevati e riscaricati automaticamente.

---

## ⚠️ Avvertenze

* **Spazio su disco**: verifica di avere spazio locale sufficiente prima di iniziare.
* **L'eliminazione è definitiva**: una volta confermata, i file passano nel cestino di iCloud o vengono rimossi in modo permanente a seconda delle impostazioni del tuo account.
* **Fai un controllo prima di cancellare**: apri la cartella di backup e verifica che i file ci siano davvero prima di rispondere `y` alla Fase 2.
* **Password specifica per app**: se il login viene rifiutato, prova a generare una password per app dalla sezione sicurezza del tuo account Apple su `appleid.apple.com`.

---

## 🔮 Roadmap / To-Do

* **☁️ Supporto Multi-Cloud**: caricamento diretto su Google Drive, OneDrive e Dropbox.
* **🔄 Streaming Transfer**: trasferimento "pipe" da iCloud al cloud di destinazione senza salvare i file in locale.
* **🔐 Crittografia (opzionale)**: cifratura dei file prima dell'upload sul cloud di destinazione.

---

## 🖼️ Rigenerare gli screenshot

Se modifichi l'interfaccia, aggiorna le immagini del README con:

```bash
python docs/generate_screenshots.py
```
