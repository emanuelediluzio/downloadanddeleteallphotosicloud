import os
import sys
from pyicloud import PyiCloudService
from tqdm import tqdm

def backup_and_clean_icloud(username, password, base_path):
    try:
        print(f"--- Inizio Script ---")
        api = PyiCloudService(username, password)

        # Gestione 2FA (Autenticazione a due fattori)
        if api.requires_2fa:
            print("Autenticazione a due fattori richiesta.")
            code = input("Inserisci il codice ricevuto sul tuo dispositivo: ")
            if not api.validate_2fa_code(code):
                print("Codice non valido. Uscita.")
                return
        
        # Caricamento libreria foto
        print("Accesso alla libreria foto in corso (attendere prego)...")
        all_photos = list(api.photos.all)
        total_count = len(all_photos)
        print(f"Trovati {total_count} elementi su iCloud.")

        if total_count == 0:
            print("Nessun file trovato. Fine.")
            return

        # --- FASE 1: DOWNLOAD ---
        print(f"\nFASE 1: Download in corso in: {base_path}")
        downloaded_count = 0
        skipped_count = 0
        
        # Barra di avanzamento
        for photo in tqdm(all_photos, desc="Avanzamento", unit="file"):
            try:
                # Recupera metadati per organizzazione (Anno/Mese)
                created = photo.created
                year = str(created.year)
                month = f"{created.month:02d}"
                
                # Distingue tra Foto e Video
                media_type = "Video" if photo.filename.lower().endswith(('.mp4', '.mov', '.avi', '.m4v')) else "Foto"
                
                # --- PUNTO 1: GESTIONE CARTELLE ---
                # Costruisce il percorso: Base/Anno/Mese/Tipo/
                folder_path = os.path.join(base_path, year, month, media_type)
                
                # exist_ok=True significa: "Se la cartella esiste già, usala senza errori e non sovrascriverla"
                os.makedirs(folder_path, exist_ok=True)

                file_path = os.path.join(folder_path, photo.filename)
                
                # --- PUNTO 2: GESTIONE FILE ESISTENTI ---
                # Se il file esiste già, NON lo scarica e passa al prossimo
                if os.path.exists(file_path):
                    skipped_count += 1
                    continue  # Salta al prossimo giro del ciclo for

                # Se siamo qui, il file non esiste, quindi procediamo al download
                download_data = photo.download()
                
                with open(file_path, 'wb') as f:
                    # Gestione corretta se il download arriva a pezzi (stream) o tutto intero (bytes)
                    if hasattr(download_data, 'iter_content'):
                        for chunk in download_data.iter_content(chunk_size=1024*1024):
                            if chunk:
                                f.write(chunk)
                    else:
                        f.write(download_data)
                        
                downloaded_count += 1
                
            except Exception as e:
                # tqdm.write permette di stampare l'errore senza rompere la barra di caricamento
                tqdm.write(f"Errore nel download di {photo.filename}: {e}")

        print(f"\n--- RIEPILOGO DOWNLOAD ---")
        print(f"Scaricati nuovi: {downloaded_count}")
        print(f"Già presenti (saltati): {skipped_count}")
        print(f"Totale esaminati: {total_count}")

        # --- FASE 2: ELIMINAZIONE ---
        # Chiede conferma prima di cancellare
        confirm = input(f"\nATTENZIONE: Vuoi eliminare definitivamente {total_count} foto da iCloud? (scrivi 'SI' per procedere): ")
        
        if confirm.upper() == "SI":
            print("FASE 2: Eliminazione in corso...")
            for photo in tqdm(all_photos, desc="Eliminazione", unit="file"):
                try:
                    photo.delete()
                except Exception as e:
                    tqdm.write(f"Errore eliminazione {photo.filename}: {e}")
            print("Pulizia iCloud completata.")
        else:
            print("Eliminazione annullata. I file sono al sicuro sul PC.")

    except Exception as e:
        print(f"Errore generale nello script: {e}")

# --- CONFIGURAZIONE ---
if __name__ == "__main__":
    # INSERISCI QUI I TUOI DATI
    EMAIL = 'tua_email@icloud.com'
    PASSWORD = 'tua_password'
    
    # Percorso di salvataggio
    DESTINAZIONE = './Backup_iCloud' 

    backup_and_clean_icloud(EMAIL, PASSWORD, DESTINAZIONE)
