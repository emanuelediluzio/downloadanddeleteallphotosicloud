# iCloud Photo Backup & Cleaner 📸 ☁️

Questo script Python permette di automatizzare il backup completo della libreria **iCloud Photos** sul proprio computer locale, organizzando i file in modo meticoloso e procedendo all'eliminazione sicura dal cloud solo dopo la conferma del successo dell'operazione.

## ✨ Funzionalità

* **Organizzazione Automatica**: I file non vengono "buttati" in una cartella, ma ordinati per:
* 📅 **Anno** (es. 2023)
* 📂 **Mese** (es. 05)
* 🎞️ **Tipo di Media** (Sottocartelle separate per `Foto` e `Video`).


* **Download Multi-chunk**: Gestisce file pesanti (video 4K) scaricandoli a pezzi per evitare crash della memoria.
* **Interfaccia da terminale curata**: barre di progresso, pannelli e tabelle di riepilogo tramite [`rich`](https://github.com/Textualize/rich).
* **Sicurezza Integrata**:
* Nessuna credenziale hardcoded: email e password vengono richieste a runtime (con input nascosto) oppure lette da variabili d'ambiente.
* Supporta l'autenticazione a due fattori (2FA), incluso il "trust" della sessione.
* L'eliminazione avviene **solo** dopo che tutti i download sono stati completati, e richiede conferma esplicita.
* Gli errori di rete/server vengono ritentati automaticamente; gli errori di autenticazione/permessi vengono invece rilevati e il file viene saltato (ed **escluso** dall'eliminazione su iCloud) dopo pochi tentativi, per evitare che lo script resti bloccato all'infinito.



## 📁 Struttura della Cartella di Output

Dopo l'esecuzione, il tuo percorso di destinazione apparirà così:

```text
Destinazione/
├── 2023/
│   ├── 01/
│   │   ├── Foto/
│   │   │   └── IMG_001.JPG
│   │   └── Video/
│   │       └── VIDEO_002.MOV
├── 2024/
│   └── 12/
│       └── Foto/
│           └── IMG_999.PNG

```

## 🚀 Requisiti

Assicurati di avere installato le librerie necessarie:

```bash
pip install -r requirements.txt

```

## 🛠️ Configurazione e Utilizzo

Le credenziali **non** sono più scritte nel codice. Puoi fornirle in due modi:

**A) Interattivo (consigliato)**: esegui lo script e inserisci email, password (nascosta) e cartella di destinazione quando richiesto.

```bash
python photodeleter.py

```

**B) Variabili d'ambiente** (utile per automazioni):

```bash
export ICLOUD_EMAIL="tuo_id@icloud.com"
export ICLOUD_PASSWORD="tua_password"
export ICLOUD_BACKUP_PATH="./Backup_iCloud"
python photodeleter.py

```

Segui poi le istruzioni a schermo:
* Inserisci il codice **2FA** se richiesto.
* Attendi il completamento della **Fase 1 (Download)**.
* Conferma quando richiesto per avviare la **Fase 2 (Eliminazione)** se vuoi liberare spazio su iCloud (i file non scaricati correttamente vengono automaticamente esclusi dall'eliminazione).



## ⚠️ Avvertenze

* **Verifica Spazio**: Assicurati di avere abbastanza spazio sul disco rigido locale prima di iniziare.
* **Connessione**: Una connessione instabile potrebbe interrompere il download. Lo script è progettato per saltare i file già esistenti, rendendo possibile una ripresa del processo.
* **Responsabilità**: L'uso della funzione di eliminazione è definitivo. Una volta confermato con `SI`, i file verranno spostati nel cestino di iCloud o eliminati permanentemente a seconda delle impostazioni del tuo account.

## 🔮 Roadmap / To-Do

Sto lavorando per espandere le capacità di backup oltre il disco locale. Le prossime funzionalità includeranno:

* **☁️ Supporto Multi-Cloud**: Integrazione diretta per spostare i file su servizi di terze parti:
    * **Google Drive**
    * **Microsoft OneDrive**
    * **Dropbox**
* **🔄 Streaming Transfer**: Implementazione di un sistema "pipe" per trasferire i dati da iCloud al Cloud di destinazione senza dover salvare permanentemente i file sul disco locale (riducendo l'uso dello spazio temporaneo).
* **🔐 Crittografia (Opzionale)**: Possibilità di criptare i file prima dell'upload sul cloud di destinazione.
