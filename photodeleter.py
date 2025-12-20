import os
import sys
import time
from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudAPIResponseException
from tqdm import tqdm

def backup_and_clean_icloud(username, password, base_path):
    try:
        print(f"--- Inizio Script ---")
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

        # --- FASE 1: DOWNLOAD ---
        print(f"\nFASE 1: Download in corso in: {base_path}")
        downloaded_count = 0
        skipped_count = 0
        
        for photo in tqdm(all_photos, desc="Download/Verifica", unit="file"):
            # Logica di ritentativo (Retry Logic)
            max_retries = 5
            attempt = 0
            success = False

            while attempt < max_retries and not success:
                try:
                    # Preparazione percorsi
                    created = photo.created
                    year = str(created.year)
                    month = f"{created.month:02d}"
                    media_type = "Video" if photo.filename.lower().endswith(('.mp4', '.mov', '.avi', '.m4v')) else "Foto"
                    
                    folder_path = os.path.join(base_path, year, month, media_type)
                    os.makedirs(folder_path, exist_ok=True)
                    file_path = os.path.join(folder_path, photo.filename)
                    
                    # Controllo esistenza
                    if os.path.exists(file_path):
                        skipped_count += 1
                        success = True
                        continue

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
                    success = True
                    # Piccola pausa per non sovraccaricare il server
                    time.sleep(0.5)

                except PyiCloudAPIResponseException as e:
                    if "503" in str(e):
                        attempt += 1
                        wait_time = 30 * attempt # Aumenta l'attesa ogni volta (30s, 60s, 90s...)
                        tqdm.write(f"Server occupato (503). Attendo {wait_time} secondi e riprovo...")
                        time.sleep(wait_time)
                    else:
                        tqdm.write(f"Errore API non gestibile per {photo.filename}: {e}")
                        break # Esce dal while e passa alla prossima foto
                except Exception as e:
                    tqdm.write(f"Errore generico {photo.filename}: {e}")
                    break

        print(f"\n--- RIEPILOGO ---")
        print(f"Scaricati: {downloaded_count}")
        print(f"Saltati (già presenti): {skipped_count}")

        # --- FASE 2: ELIMINAZIONE AUTOMATICA ---
        print("\nFASE 2: Eliminazione automatica da iCloud avviata...")
        
        for photo in tqdm(all_photos, desc="Eliminazione", unit="file"):
            attempt = 0
            success = False
            while attempt < 3 and not success:
                try:
                    photo.delete()
                    success = True
                except PyiCloudAPIResponseException as e:
                    if "503" in str(e):
                        attempt += 1
                        tqdm.write(f"Server occupato durante eliminazione. Attendo 10s...")
                        time.sleep(10)
                    else:
                        break
                except Exception as e:
                    tqdm.write(f"Errore eliminazione {photo.filename}: {e}")
                    break
                
        print("Pulizia iCloud completata.")

    except Exception as e:
        print(f"Errore generale nello script: {e}")

# --- CONFIGURAZIONE ---
if __name__ == "__main__":
    EMAIL = 'tua_email@icloud.com'
    PASSWORD = 'tua_password'
    DESTINAZIONE = './Backup_iCloud' 

    backup_and_clean_icloud(EMAIL, PASSWORD, DESTINAZIONE)
