import os
import sys
from pyicloud import PyiCloudService
from tqdm import tqdm

def backup_and_clean_icloud(username, password, base_path):
    try:
        print(f"--- Inizio Script ---")
        api = PyiCloudService(username, password)

        # Gestione 2FA
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
        
        for photo in tqdm(all_photos, desc="Download/Verifica", unit="file"):
            try:
                # Metadati per cartelle
                created = photo.created
                year = str(created.year)
                month = f"{created.month:02d}"
                media_type = "Video" if photo.filename.lower().endswith(('.mp4', '.mov', '.avi', '.m4v')) else "Foto"
                
                # Crea cartelle (senza sovrascrivere se esistono)
                folder_path = os.path.join(base_path, year, month, media_type)
                os.makedirs(folder_path, exist_ok=True)

                file_path = os.path.join(folder_path, photo.filename)
                
                # Controllo esistenza file
                if os.path.exists(file_path):
                    skipped_count += 1
                    continue # Salta al prossimo se esiste

                # Download
                download_data = photo.download()
                
                with open(file_path, 'wb') as f:
                    if hasattr(download_data, 'iter_content'):
                        for chunk in download_data.iter_content(chunk_size=1024*1024):
                            if chunk:
                                f.write(chunk)
                    else:
                        f.write(download_data)
                        
                downloaded_count += 1
                
            except Exception as e:
                tqdm.write(f"Errore nel download di {photo.filename}: {e}")

        print(f"\n--- RIEPILOGO ---")
        print(f"Scaricati: {downloaded_count}")
        print(f"Saltati (già presenti): {skipped_count}")

        # --- FASE 2: ELIMINAZIONE AUTOMATICA ---
        print("\nFASE 2: Eliminazione automatica da iCloud avviata...")
        
        for photo in tqdm(all_photos, desc="Eliminazione", unit="file"):
            try:
                photo.delete()
            except Exception as e:
                tqdm.write(f"Errore eliminazione {photo.filename}: {e}")
                
        print("Pulizia iCloud completata.")

    except Exception as e:
        print(f"Errore generale nello script: {e}")

# --- CONFIGURAZIONE ---
if __name__ == "__main__":
    EMAIL = 'tua_email@icloud.com'
    PASSWORD = 'tua_password'
    DESTINAZIONE = './Backup_iCloud' 

    backup_and_clean_icloud(EMAIL, PASSWORD, DESTINAZIONE)
