import os
import sys
import time
from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudAPIResponseException
from tqdm import tqdm

def backup_and_clean_icloud(username, password, base_path):
    try:
        print(f"--- Inizio Script Sicuro ---")
        api = PyiCloudService(username, password)

        if api.requires_2fa:
            print("Autenticazione a due fattori richiesta.")
            code = input("Inserisci il codice ricevuto sul tuo dispositivo: ")
            if not api.validate_2fa_code(code):
                print("Codice non valido. Uscita.")
                return
        
        print("Accesso alla libreria foto in corso (attendere prego)...")
        all_photos = list(api.photos.all)
        total_count = len(all_photos)
        print(f"Trovati {total_count} elementi su iCloud.")

        if total_count == 0:
            print("Nessun file trovato. Fine.")
            return

        # --- FASE 1: DOWNLOAD SICURO ---
        print(f"\nFASE 1: Download in corso in: {base_path}")
        print("NOTA: Lo script NON salterà nessun file. In caso di errore riproverà all'infinito.")
        
        downloaded_count = 0
        skipped_count = 0
        
        for photo in tqdm(all_photos, desc="Avanzamento Globale", unit="file"):
            # Ciclo infinito per ogni singolo file: non esce finché non ha successo
            while True:
                try:
                    # 1. Preparazione percorsi
                    created = photo.created
                    year = str(created.year)
                    month = f"{created.month:02d}"
                    media_type = "Video" if photo.filename.lower().endswith(('.mp4', '.mov', '.avi', '.m4v')) else "Foto"
                    
                    folder_path = os.path.join(base_path, year, month, media_type)
                    os.makedirs(folder_path, exist_ok=True)
                    file_path = os.path.join(folder_path, photo.filename)
                    
                    # 2. Controllo se file esiste già (per non riscaricarlo)
                    if os.path.exists(file_path):
                        # Controllo opzionale: se il file è 0 byte (corrotto), lo riscarica
                        if os.path.getsize(file_path) > 0:
                            skipped_count += 1
                            break # ESCE DAL WHILE (passa al prossimo file)
                        else:
                            tqdm.write(f"Trovato file vuoto/corrotto {photo.filename}, lo riscarico.")
                            os.remove(file_path)

                    # 3. Tentativo di Download
                    download_data = photo.download()
                    
                    with open(file_path, 'wb') as f:
                        if hasattr(download_data, 'iter_content'):
                            for chunk in download_data.iter_content(chunk_size=1024*1024):
                                if chunk:
                                    f.write(chunk)
                        else:
                            f.write(download_data)
                    
                    # Se arriva qui, ha finito senza errori
                    downloaded_count += 1
                    time.sleep(0.2) # Piccolissima pausa di cortesia
                    break # ESCE DAL WHILE (Successo)

                except Exception as e:
                    # Se c'è un errore, NON usciamo dal while. Aspettiamo e riproviamo.
                    error_msg = str(e)
                    wait_time = 10 # Secondi di attesa base
                    
                    if "503" in error_msg or "Service Unavailable" in error_msg:
                        tqdm.write(f"Server Apple occupato (503) per {photo.filename}. Riprovo tra 30 secondi...")
                        time.sleep(30)
                    elif "Connection" in error_msg or "socket" in error_msg:
                        tqdm.write(f"Errore connessione per {photo.filename}. Riprovo tra 10 secondi...")
                        time.sleep(10)
                    else:
                        tqdm.write(f"Errore generico: {error_msg}. Riprovo tra 5 secondi...")
                        time.sleep(5)
                    # Il ciclo 'while True' ricomincia da capo per questa foto

        print(f"\n--- RIEPILOGO DOWNLOAD ---")
        print(f"Scaricati con successo: {downloaded_count}")
        print(f"Già presenti (saltati): {skipped_count}")
        print(f"Totale: {total_count}")
        print("Tutti i file sono stati scaricati e sono al sicuro sul tuo PC.")

        # --- FASE 2: ELIMINAZIONE MANUALE ---
        print("\n" + "="*50)
        confirm = input(f"ATTENZIONE: Vuoi eliminare definitivamente le {total_count} foto DA ICLOUD?\nLe copie sul tuo PC NON verranno toccate.\nScrivi 'SI' per procedere alla cancellazione, qualsiasi altro tasto per uscire: ")
        print("="*50 + "\n")
        
        if confirm.upper() == "SI":
            print("FASE 2: Eliminazione in corso...")
            for photo in tqdm(all_photos, desc="Eliminazione", unit="file"):
                # Anche qui mettiamo un retry per essere sicuri che cancelli
                while True:
                    try:
                        photo.delete()
                        break # Cancellato, passa al prossimo
                    except Exception as e:
                        if "503" in str(e):
                            tqdm.write("Server occupato durante eliminazione. Attendo...")
                            time.sleep(10)
                        else:
                            tqdm.write(f"Impossibile eliminare {photo.filename}: {e}. Salto.")
                            break # Se non riesce a cancellare, qui saltiamo per non bloccare tutto (opzionale)
            print("Pulizia iCloud completata.")
        else:
            print("Operazione conclusa. I file sono sul tuo PC, nessuna foto è stata cancellata da iCloud.")

    except Exception as e:
        print(f"\nERRORE CRITICO DELLO SCRIPT: {e}")

# --- CONFIGURAZIONE ---
if __name__ == "__main__":
    EMAIL = 'tua_email@icloud.com'
    PASSWORD = 'tua_password'
    DESTINAZIONE = './Backup_iCloud' 

    backup_and_clean_icloud(EMAIL, PASSWORD, DESTINAZIONE)
