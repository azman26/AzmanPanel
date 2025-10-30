# /usr/lib/enigma2/python/Plugins/Extensions/AzmanPanel/utils.py

import os
import zipfile
import traceback
import datetime
import shutil  # <-- IMPORT PRZENIESIONY TUTAJ

LOG_FILE = "/tmp/azman_panel.log"

def log_error(exception, context_info="Unknown"):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"--- {timestamp} - Błąd w kontekście: {context_info} ---\n")
            f.write(f"Typ Błędu: {type(exception).__name__}\n")
            f.write(f"Wiadomość: {str(exception)}\n")
            f.write("Pełny Traceback:\n")
            traceback.print_exc(file=f)
            f.write("--- Koniec wpisu ---\n\n")
        print(f"[AzmanPanel] Zapisano szczegóły błędu do {LOG_FILE}")
    except Exception as log_e:
        print(f"[AzmanPanel] BŁĄD KRYTYCZNY: Nie można zapisać do pliku logu {LOG_FILE}. Błąd: {log_e}")

def safe_extract_zip_member(zip_ref, member, target_dir):
    target_path = os.path.join(target_dir, member.filename)
    if not os.path.realpath(target_path).startswith(os.path.realpath(target_dir)):
        raise zipfile.BadZipFile(f"Wykryto próbę ataku ścieżką (path traversal): {member.filename}")
    if not member.is_dir():
        parent_dir = os.path.dirname(target_path)
        os.makedirs(parent_dir, exist_ok=True)
        with zip_ref.open(member, 'r') as source, open(target_path, 'wb') as target:
            # import shutil  <-- USUNIĘTO STĄD
            shutil.copyfileobj(source, target)