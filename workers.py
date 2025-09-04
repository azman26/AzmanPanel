# /usr/lib/enigma2/python/Plugins/Extensions/AzmanPanel/main/workers.py

import os
import re
import shutil
import stat
import threading
import time
import urllib.request
import zipfile
import subprocess # <- NOWY IMPORT

from Tools.BoundFunction import boundFunction
from enigma import eTimer

# Importy z lokalnych modułów
from . import constants

class BaseDownloadWorker(threading.Thread):
    def __init__(self, callback_progress, callback_finished):
        threading.Thread.__init__(self)
        self.callback_progress = callback_progress
        self.callback_finished = callback_finished
        self._last_update_time = 0
        self._update_interval_ms = 200
        self.timer = eTimer()
        self.timer_connected = False
        self._callback_to_execute = None

    def _safe_call_main_thread(self, func, *args, **kwargs):
        if self.timer_connected:
            try: self.timer.callback.remove(self._timer_callback)
            except (ValueError, TypeError): pass
            self.timer_connected = False
        self._callback_to_execute = boundFunction(func, *args, **kwargs)
        self.timer.callback.append(self._timer_callback)
        self.timer_connected = True
        self.timer.start(0, True)

    def _timer_callback(self):
        if self._callback_to_execute: self._callback_to_execute()
        if self.timer_connected:
            try: self.timer.callback.remove(self._timer_callback)
            except (ValueError, TypeError): pass
            self.timer_connected = False
        self._callback_to_execute = None

    def _internal_reporthook(self, count, block_size, total_size):
        current_time = time.time() * 1000
        if (current_time - self._last_update_time) >= self._update_interval_ms:
            self._safe_call_main_thread(self.callback_progress, count * block_size, total_size)
            self._last_update_time = current_time

class PiconInstallationWorker(BaseDownloadWorker):
    # ... (zawartość tej klasy bez zmian) ...
    def __init__(self, selected_zips, target_dir, base_url, callback_progress, callback_finished):
        BaseDownloadWorker.__init__(self, callback_progress, callback_finished)
        self.selected_zips = selected_zips
        self.target_dir = target_dir
        self.base_url = base_url
        self.temp_dir = None
        self.installed_items = []
        self.failed_items = []
        self.final_message = ""

    def run(self):
        try:
            self.temp_dir = tempfile.mkdtemp()
            if not os.path.exists(self.target_dir):
                os.makedirs(self.target_dir)
            total_zips = len(self.selected_zips)
            for i, zip_filename in enumerate(self.selected_zips):
                display_filename = zip_filename.replace('%20', ' ')
                self._safe_call_main_thread(self.callback_progress, -1, total_zips, f"Instalacja ({i+1}/{total_zips}): {display_filename}")
                temp_zip_path = os.path.join(self.temp_dir, zip_filename)
                picon_zip_url = urllib.parse.urljoin(self.base_url, zip_filename)
                try:
                    urllib.request.urlretrieve(picon_zip_url, temp_zip_path, reporthook=self._internal_reporthook)
                    self._safe_call_main_thread(self.callback_progress, os.path.getsize(temp_zip_path), os.path.getsize(temp_zip_path))
                    self._safe_call_main_thread(self.callback_progress, 0, 0)
                    num_extracted = 0
                    with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                        for member in zip_ref.namelist():
                            if member.endswith('/') or member.endswith('\\'): continue
                            base_filename = os.path.basename(member)
                            if base_filename.startswith('.') or base_filename.lower() in ('__macosx', '.ds_store'): continue
                            temp_file_path = os.path.join(self.temp_dir, base_filename)
                            with zip_ref.open(member) as source, open(temp_file_path, 'wb') as target:
                                shutil.copyfileobj(source, target)
                            final_picon_path = os.path.join(self.target_dir, base_filename)
                            shutil.move(temp_file_path, final_picon_path)
                            os.chmod(final_picon_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
                            num_extracted += 1
                    self.installed_items.append(f"{display_filename} ({num_extracted} picon)")
                    os.remove(temp_zip_path)
                except Exception as e:
                    print(f"[PiconInstallationWorker] Błąd podczas instalacji paczki {display_filename}: {e}")
                    self.failed_items.append(display_filename)
            summary = []
            if self.installed_items:
                summary.append(f"Pomyślnie zainstalowano ({len(self.installed_items)}):\n" + "\n".join(f"- {item}" for item in self.installed_items))
            if self.failed_items:
                summary.append(f"\nBłędy instalacji ({len(self.failed_items)}):\n" + "\n".join(f"- {item}" for item in self.failed_items))
            self.final_message = "\n\n".join(summary)
            if not self.final_message:
                self.final_message = "Nie wykonano żadnych operacji."
        except Exception as e:
            self.final_message = f"Wystąpił krytyczny błąd: {e}"
        finally:
            if self.temp_dir:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            self._safe_call_main_thread(self.callback_finished, self.final_message)


class PiconZipListWorker(BaseDownloadWorker):
    # ... (zawartość tej klasy bez zmian) ...
    def __init__(self, picons_base_url, callback_finished, parent_screen):
        BaseDownloadWorker.__init__(self, None, callback_finished)
        self.picons_base_url, self.picon_zip_filenames, self.parent_screen = picons_base_url, [], parent_screen
        self.error_message = None
        
    def run(self):
        try:
            with urllib.request.urlopen(self.picons_base_url, timeout=10) as response: html = response.read().decode('utf-8')
            self.picon_zip_filenames = sorted(re.findall(r'href="([^"]+\.zip)"', html), key=lambda x: x.lower())
            if not self.picon_zip_filenames: self.error_message = "Nie znaleziono plików *.zip w katalogu picon."
        except Exception as e: self.error_message = f"Błąd pobierania listy picon z '{self.picons_base_url}': {str(e)}"
        finally:
            self._safe_call_main_thread(self.callback_finished, self.parent_screen, self.error_message, self.picon_zip_filenames)


class RepoItemListWorker(BaseDownloadWorker):
    # ... (zawartość tej klasy bez zmian) ...
    def __init__(self, zip_url, repo_name, temp_extraction_dir, item_finder_func, 
                 callback_progress, callback_finished, parent_screen):
        BaseDownloadWorker.__init__(self, callback_progress, callback_finished)
        self.zip_url, self.repo_name, self.temp_extraction_dir = zip_url, repo_name, temp_extraction_dir
        self.item_finder_func, self.parent_screen = item_finder_func, parent_screen
        self.temp_zip_path = os.path.join(self.temp_extraction_dir, "repo.zip")
        self.found_items = []
        self.error_message = None

    def run(self):
        try:
            urllib.request.urlretrieve(self.zip_url, self.temp_zip_path, reporthook=self._internal_reporthook)
            self._safe_call_main_thread(self.callback_progress, os.path.getsize(self.temp_zip_path), os.path.getsize(self.temp_zip_path))
            self._safe_call_main_thread(self.callback_progress, 0, 0)
            with zipfile.ZipFile(self.temp_zip_path, 'r') as zip_ref:
                for member in zip_ref.namelist():
                    try:
                        from . import utils
                        utils.safe_extract_zip_member(zip_ref, member, self.temp_extraction_dir)
                    except zipfile.BadZipFile as e:
                        self.error_message = f"Problem bezpieczeństwa: {member}. Operacja przerwana."
                        break
            if self.error_message:
                raise Exception(self.error_message)
            repo_base_path = os.path.join(self.temp_extraction_dir, self.repo_name)
            if not os.path.isdir(repo_base_path):
                raise FileNotFoundError(f"Katalog repozytorium '{self.repo_name}' nie został znaleziony.")
            source_paths = self.item_finder_func(repo_base_path)
            for path in source_paths:
                item_name = os.path.basename(path)
                self.found_items.append((item_name, path))
            if not self.found_items:
                self.error_message = "Nie znaleziono żadnych elementów do instalacji w repozytorium."
            else:
                self.found_items.sort(key=lambda x: x[0].lower())
        except Exception as e:
            self.error_message = f"Wystąpił błąd: {str(e)}"
        finally:
            self._safe_call_main_thread(self.callback_finished, self.parent_screen, self.error_message, self.found_items, self.temp_extraction_dir)
            if os.path.exists(self.temp_zip_path):
                os.remove(self.temp_zip_path)


class E2KListDownloader(BaseDownloadWorker):
    # ... (zawartość tej klasy bez zmian) ...
    def __init__(self, config, callback_progress, callback_finished):
        BaseDownloadWorker.__init__(self, callback_progress, callback_finished)
        self.config = config
        self.error_message = None
        self.found_items = []
        self.temp_dir = None

    def run(self):
        try:
            self.temp_dir = tempfile.mkdtemp()
            zip_path = os.path.join(self.temp_dir, "repo.zip")
            urllib.request.urlretrieve(self.config['url'], zip_path, reporthook=self._internal_reporthook)
            self._safe_call_main_thread(self.callback_progress, os.path.getsize(zip_path), os.path.getsize(zip_path))
            self._safe_call_main_thread(self.callback_progress, 0, 0)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for member in zip_ref.namelist():
                    from . import utils
                    utils.safe_extract_zip_member(zip_ref, member, self.temp_dir)
            os.remove(zip_path)
            repo_base_path = os.path.join(self.temp_dir, self.config['repo_name'])
            if not os.path.isdir(repo_base_path):
                raise FileNotFoundError(f"Katalog repozytorium '{self.config['repo_name']}' nie został znaleziony w archiwum.")
            source_paths = self.config['finder'](repo_base_path)
            for path in source_paths:
                item_name = os.path.basename(path)
                self.found_items.append({'name': item_name, 'path': path})
            if not self.found_items:
                self.error_message = f"Nie znaleziono żadnych {self.config['type']} w repozytorium."
        except Exception as e:
            self.error_message = str(e)
            if self.temp_dir:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.temp_dir = None
        finally:
            self._safe_call_main_thread(self.callback_finished, self.error_message, self.found_items, self.temp_dir)


class SourcesXmlDownloadWorker(BaseDownloadWorker):
    # ... (zawartość tej klasy bez zmian) ...
    def __init__(self, url, target_path, callback_progress, callback_finished, parent_screen):
        BaseDownloadWorker.__init__(self, callback_progress, callback_finished)
        self.url, self.target_path, self.parent_screen = url, target_path, parent_screen
        self.filename = os.path.basename(target_path)
        self.error_message = None
        self.final_message = None

    def run(self):
        try:
            urllib.request.urlretrieve(self.url, self.target_path, reporthook=self._internal_reporthook)
            self._safe_call_main_thread(self.callback_progress, os.path.getsize(self.target_path), os.path.getsize(self.target_path))
            self.final_message = f"Plik '{self.filename}' pomyślnie zainstalowany w {os.path.dirname(self.target_path)}."
        except Exception as e: self.error_message = f"Błąd pobierania pliku {self.filename}: {str(e)}"
        finally:
            self._safe_call_main_thread(self.callback_finished, self.parent_screen, self.error_message, self.final_message)


class IptvOrgPlDownloadWorker(BaseDownloadWorker):
    # ... (zawartość tej klasy bez zmian) ...
    def __init__(self, m3u_url, temp_m3u_path, output_bouquet_path, bouquet_name, callback_progress, callback_finished, parent_screen):
        BaseDownloadWorker.__init__(self, callback_progress, callback_finished)
        self.m3u_url, self.temp_m3u_path = m3u_url, temp_m3u_path
        self.output_bouquet_path, self.bouquet_name, self.parent_screen = output_bouquet_path, bouquet_name, parent_screen
        self.temp_dir_for_cleanup = os.path.dirname(temp_m3u_path)
        self.error_message = None
        self.final_message = None

    def run(self):
        try:
            urllib.request.urlretrieve(self.m3u_url, self.temp_m3u_path, reporthook=self._internal_reporthook)
            self._safe_call_main_thread(self.callback_progress, os.path.getsize(self.temp_m3u_path), os.path.getsize(self.temp_m3u_path))
            self._safe_call_main_thread(self.callback_progress, 0, 0)
            with open(self.temp_m3u_path, 'r', encoding='utf-8') as f_m3u: lines = f_m3u.readlines()
            bouquet_lines = [f'#NAME {self.bouquet_name}\n']
            channel_name = None
            for line in lines:
                line = line.strip()
                if line.startswith('#EXTINF:'):
                    match = re.search(r'tvg-name="([^"]*)"', line) or re.search(r'group-title="([^"]*)"', line) or re.search(r'\,(.*?)$', line)
                    channel_name = match.group(1).strip() if match else "Nieznany kanał"
                elif line.startswith('http'):
                    if channel_name:
                        encoded_url = urllib.parse.quote_plus(line).replace('+', '%20') 
                        bouquet_lines.append(f'#SERVICE 4097:0:1:0:0:0:0:0:0:0:{encoded_url}:{channel_name}\n')
                        channel_name = None
            with open(self.output_bouquet_path, 'w', encoding='utf-8') as f_bouquet: f_bouquet.writelines(bouquet_lines)
            os.chmod(self.output_bouquet_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
            self.final_message = f"Bukiet '{self.bouquet_name}' pomyślnie skonwertowany."
            bouquets_tv_path = os.path.join(constants.BOUQUET_TARGET_DIR, "bouquets.tv")
            new_entry = f'#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "{os.path.basename(self.output_bouquet_path)}" ORDER BY bouquet\n'
            if not os.path.exists(bouquets_tv_path) or os.path.basename(self.output_bouquet_path) not in open(bouquets_tv_path, 'r', encoding='utf-8').read():
                with open(bouquets_tv_path, 'a', encoding='utf-8') as f: f.write(new_entry)
                self.final_message += "\nDodano wpis do głównej listy bukietów."
            else: self.final_message += "\nWpis już istniał."
        except Exception as e: self.error_message = f"Błąd konwersji '{self.bouquet_name}': {str(e)}"
        finally:
            if self.temp_dir_for_cleanup: shutil.rmtree(self.temp_dir_for_cleanup, ignore_errors=True)
            self._safe_call_main_thread(self.callback_finished, self.parent_screen, self.error_message, self.final_message)


# ### NOWA KLASA WORKERA ###
class FeedInstallerWorker(threading.Thread):
    def __init__(self, parent_screen, callback_finished):
        threading.Thread.__init__(self)
        self.parent_screen = parent_screen
        self.callback_finished = callback_finished
        self.error_message = None

    def run(self):
        try:
            # 1. Pobieranie pliku
            print(f"[FeedInstallerWorker] Pobieranie feeda z: {constants.FEED_CONF_URL}")
            urllib.request.urlretrieve(constants.FEED_CONF_URL, constants.FEED_CONF_TARGET_PATH)
            print(f"[FeedInstallerWorker] Zapisano feed w: {constants.FEED_CONF_TARGET_PATH}")
            
            # 2. Uruchomienie opkg update
            print("[FeedInstallerWorker] Uruchamianie 'opkg update'")
            # Używamy subprocess, bo to prostsze w wątku niż Console
            # Timeout na 120 sekund, aby uniknąć wiecznego zawieszenia
            process = subprocess.Popen("opkg update", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate(timeout=120)
            
            if process.returncode != 0:
                # Jeśli komenda się nie powiedzie, zapisz błąd
                self.error_message = stderr.decode('utf-8', errors='ignore')
                print(f"[FeedInstallerWorker] Błąd opkg update: {self.error_message}")

        except Exception as e:
            self.error_message = str(e)
            print(f"[FeedInstallerWorker] Błąd: {self.error_message}")
        
        finally:
            # Wywołaj funkcję zwrotną w głównym wątku
            # Używamy session.nav.event.send, aby bezpiecznie przejść z wątku do głównej pętli Enigmy
            self.parent_screen.session.nav.event.send(boundFunction(self.callback_finished, self.error_message))