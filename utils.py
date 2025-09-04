# /usr/lib/enigma2/python/Plugins/Extensions/AzmanPanel/main/utils.py

import os
import zipfile
from enigma import eDVBDB
from Components.Console import Console

class CommandRunner:
    """
    Klasa pomocnicza do asynchronicznego uruchamiania poleceń w konsoli
    i otrzymywania powiadomienia o ich zakończeniu.
    """
    def __init__(self):
        self.console = Console()
        self.callback = None
        self.output = []

    def run(self, command, callback=None):
        self.callback = callback
        self.output = []
        self.console.eUIData.add(self.on_console_output)
        self.console.eConnectCallback.add(self.on_command_finished)
        self.console.execute(command)

    def on_console_output(self, data):
        if data:
            self.output.append(data.strip())
            print("[CommandRunner] >>", data.strip())

    def on_command_finished(self, result=None):
        self.console.eUIData.remove(self.on_console_output)
        self.console.eConnectCallback.remove(self.on_command_finished)
        if self.callback:
            self.callback(result, self.output)

def run_command(command, callback=None):
    """
    Uproszczona funkcja do wywoływania CommandRunner.
    """
    runner = CommandRunner()
    runner.run(command, callback)

def safe_extract_zip_member(zip_ref, member, target_dir):
    """
    Bezpiecznie wypakowuje pojedynczy element z archiwum ZIP,
    chroniąc przed atakami Path Traversal.
    """
    member = member.lstrip(os.sep).lstrip('/')
    if not member: return
    member_path_parts = [part for part in member.split(os.sep) if part not in ('', '.', '..')]
    normalized_member = os.path.join(*member_path_parts)
    if not normalized_member: return
    member_abs_path = os.path.abspath(os.path.join(target_dir, normalized_member))
    abs_target_dir = os.path.abspath(target_dir)
    if not member_abs_path.startswith(abs_target_dir + os.sep) and member_abs_path != abs_target_dir:
        raise zipfile.BadZipFile(f"Wykryto próbę ataku ścieżką (path traversal) lub nieprawidłową ścieżkę: {member} -> {member_abs_path}")
    os.makedirs(os.path.dirname(member_abs_path), exist_ok=True)
    zip_ref.extract(member, path=target_dir)

def reload_dvb_services():
    """
    Przeładowuje listę kanałów i bukietów w Enigma2.
    """
    print("[AzmanPanel] Reloading DVB services and bouquets.")
    try:
        eDVBDB.getInstance().reloadServicelist()
        eDVBDB.getInstance().reloadBouquets()
    except Exception as e:
        print(f"[AzmanPanel utils] Failed to reload DVB services: {e}")