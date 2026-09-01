#!/usr/bin/env python3
"""Punto di ingresso storico: permette di eseguire "python3 photodeleter.py"
senza dover installare il pacchetto (vedi il README, Parte 3).

Il codice vero e proprio vive in src/icloud_photo_backup/. Se invece hai
installato il progetto con pip/pipx, usa direttamente il comando
"icloud-photo-backup" al posto di questo file.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from icloud_photo_backup.cli import main

if __name__ == "__main__":
    main()
