import os
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
        print("Accesso alla libreria foto in corso (potrebbe richiedere tempo)...")
        all_photos = list(api.photos.all)
        total_count = len(all_photos)
        print(f"Trovati {total_count} elementi.")

        if total_count == 0:
            print("Nessun file trovato. Fine.")
            return

        # --- FASE 1: DOWNLOAD ---
        print(f"\nFASE 1: Download in corso in: {base_path}")
        downloaded_count = 0
        
        for photo in tqdm(all_photos, desc="Download file", unit="file"):
            try:
                # Recupera metadati per organizzazione
                created = photo.created # Oggetto datetime
                year = str(created.year)
                month = f"{created.month:02d}"
                # Determina cartella media (Video o Foto)
                # Nota: PyiCloud usa spesso nomi file o estensioni per distinguere
                media_type = "Video" if photo.filename.lower().endswith(('.mp4', '.mov')) else "Foto"
                
                # Creazione percorso cartelle: Base/Anno/Mese/Tipo/
                folder_path = os.path.join(base_path, year, month, media_type)
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path)

                file_path = os.path.join(folder_path, photo.filename)
                
                # Download effettivo se il file non esiste già
                if not os.path.exists(file_path):
                    with open(file_path, 'wb') as f:
                        for chunk in photo.download().iter_content(chunk_size=1024*1024):
                            if chunk:
                                f.write(chunk)
                downloaded_count += 1
            except Exception as e:
                print(f"Errore nel download di {photo.filename}: {e}")

        print(f"Download completato: {downloaded_count} file salvati.")

        # --- FASE 2: ELIMINAZIONE ---
        confirm = input(f"\nATTENZIONE: Vuoi eliminare definitivamente {total_count} foto da iCloud? (scrivi 'SI' per procedere): ")
        
        if confirm.upper() == "SI":
            print("FASE 2: Eliminazione in corso...")
            # Procediamo a blocchi per stabilità
            for photo in tqdm(all_photos, desc="Eliminazione", unit="file"):
                try:
                    photo.delete()
                except Exception as e:
                    print(f"Errore eliminazione {photo.filename}: {e}")
            print("Pulizia iCloud completata.")
        else:
            print("Eliminazione annullata dall'utente. I file sono al sicuro sul PC.")

    except Exception as e:
        print(f"Errore generale: {e}")

# --- CONFIGURAZIONE ---
if __name__ == "__main__":
    EMAIL = 'tua_email@icloud.com'
    PASSWORD = 'tua_password'
    # Inserisci qui il percorso dove vuoi salvare le foto (es: 'C:/Backup_iCloud' o '/Users/nome/Desktop/Foto')
    DESTINAZIONE = './Backup_iCloud' 

    backup_and_clean_icloud(EMAIL, PASSWORD, DESTINAZIONE)
