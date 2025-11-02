import threading
import urllib.request
import urllib.parse
import subprocess
import gzip
import re
import os
import tempfile
import zipfile
from Tools.BoundFunction import boundFunction
from enigma import eTimer
from . import constants, utils

class BaseWorker(threading.Thread):
    def __init__(self, callback_finished):
        threading.Thread.__init__(self)
        self._is_cancelled = False
        self.callback_finished = callback_finished
        self.timer = eTimer()
        self.timer.callback.append(self._safe_callback)
        self._callback_args = ()

    def cancel(self):
        self._is_cancelled = True

    def _safe_call_main_thread(self, *args):
        self._callback_args = args
        self.timer.start(0, True)

    def _safe_callback(self):
        self.timer.stop()
        if not self._is_cancelled and self.callback_finished:
            self.callback_finished(*self._callback_args)

    def _internal_reporthook(self, count, block_size, total_size):
        if self._is_cancelled:
            raise InterruptedError("Download cancelled by user")

# --- Workery dla Azman OPKG Feed ---
# ... (bez zmian) ...
class PackageListWorker(BaseWorker):
    def __init__(self, callback_finished):
        super(PackageListWorker, self).__init__(callback_finished)
        self.error_message = None
        self.packages = []
    def _parse_packages_file(self, content):
        packages = []
        current_package = {}
        for line in content.split('\n'):
            if not line:
                if 'Package' in current_package: packages.append(current_package)
                current_package = {}
                continue
            if ': ' in line:
                key, value = line.split(': ', 1)
                current_package[key] = value
        if 'Package' in current_package: packages.append(current_package)
        return packages
    def _get_installed_packages(self):
        installed = {}
        try:
            process = subprocess.Popen(["opkg", "list-installed"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate(timeout=60)
            if process.returncode == 0:
                for line in stdout.decode('utf-8', errors='ignore').split('\n'):
                    if ' - ' in line:
                        name, version = line.split(' - ', 1)
                        installed[name.strip()] = version.strip()
            else:
                raise Exception(stderr.decode('utf-8', errors='ignore'))
        except Exception as e:
            utils.log_error(e, "opkg list-installed")
            self.error_message = "Błąd sprawdzania zainstalowanych pakietów."
        return installed
    def run(self):
        try:
            packages_gz_url = f"{constants.FEED_PACKAGES_BASE_URL}/all/Packages.gz"
            with urllib.request.urlopen(packages_gz_url, timeout=20) as response:
                packages_content = gzip.decompress(response.read()).decode('utf-8')
            available_packages = self._parse_packages_file(packages_content)
            installed_packages = self._get_installed_packages()
            if self.error_message: raise Exception(self.error_message)
            for pkg in available_packages:
                pkg_name = pkg.get('Package')
                if not pkg_name: continue
                self.packages.append({'name': pkg_name, 'version': pkg.get('Version', 'N/A'), 'description': pkg.get('Description', 'Brak opisu.'), 'status': 'Zainstalowany' if pkg_name in installed_packages else 'Dostępny'})
        except Exception as e:
            utils.log_error(e, self.__class__.__name__)
            self.error_message = "Nie można pobrać listy pakietów. Sprawdź połączenie z internetem."
        finally:
            self._safe_call_main_thread(self.error_message, self.packages)

# --- Workery dla Picon ---
# ... (bez zmian) ...
class PiconZipListWorker(BaseWorker):
    def __init__(self, callback_finished):
        super(PiconZipListWorker, self).__init__(callback_finished)
        self.error_message = None
        self.picon_zip_filenames = []
    def run(self):
        try:
            with urllib.request.urlopen(constants.PICONS_BASE_URL, timeout=10) as response:
                html = response.read().decode('utf-8')
            self.picon_zip_filenames = sorted(re.findall(r'href="([^"]+\.zip)"', html), key=lambda x: x.lower())
            if not self.picon_zip_filenames:
                self.error_message = "Nie znaleziono plików *.zip w katalogu picon."
        except Exception as e:
            utils.log_error(e, self.__class__.__name__)
            self.error_message = "Błąd pobierania listy picon."
        finally:
            self._safe_call_main_thread(self.error_message, self.picon_zip_filenames)
class PiconInstallationWorker(BaseWorker):
    def __init__(self, selected_zips, target_dir, callback_progress, callback_finished):
        super(PiconInstallationWorker, self).__init__(callback_finished)
        self.selected_zips = selected_zips
        self.target_dir = target_dir
        self.callback_progress = callback_progress
        self.progress_timer = eTimer()
        self.progress_timer.callback.append(self._safe_progress_callback)
        self._progress_args = ()
    def _safe_call_progress(self, *args):
        self._progress_args = args
        self.progress_timer.start(0, True)
    def _safe_progress_callback(self):
        self.progress_timer.stop()
        if not self._is_cancelled and self.callback_progress:
            self.callback_progress(*self._progress_args)
    def run(self):
        final_message = ""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                if not os.path.exists(self.target_dir):
                    os.makedirs(self.target_dir)
                total_zips = len(self.selected_zips)
                for i, zip_filename in enumerate(self.selected_zips):
                    if self._is_cancelled: break
                    display_filename = urllib.parse.unquote(zip_filename)
                    self._safe_call_progress(i, total_zips, f"Pobieranie: {display_filename}")
                    temp_zip_path = os.path.join(temp_dir, zip_filename)
                    picon_zip_url = urllib.parse.urljoin(constants.PICONS_BASE_URL, zip_filename)
                    urllib.request.urlretrieve(picon_zip_url, temp_zip_path, reporthook=self._internal_reporthook)
                    self._safe_call_progress(i, total_zips, f"Rozpakowywanie: {display_filename}")
                    with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                        for member in zip_ref.infolist():
                            if self._is_cancelled: break
                            utils.safe_extract_zip_member(zip_ref, member, self.target_dir)
                final_message = f"Zainstalowano pomyślnie {len(self.selected_zips)} paczek." if not self._is_cancelled else "Instalacja anulowana."
        except InterruptedError:
            final_message = "Instalacja anulowana przez użytkownika."
        except Exception as e:
            utils.log_error(e, self.__class__.__name__)
            final_message = f"Wystąpił błąd podczas instalacji:\n{e}"
        finally:
            self._safe_call_main_thread(final_message)
            
# --- Workery dla Bukietów ---
# POPRAWKA: Zmodyfikowano, aby przyjmować URL jako argument
class IptvBouquetListWorker(BaseWorker):
    def __init__(self, list_url, callback_finished):
        super(IptvBouquetListWorker, self).__init__(callback_finished)
        self.list_url = list_url
        self.error_message = None
        self.bouquet_filenames = []
        
    def run(self):
        try:
            with urllib.request.urlopen(self.list_url, timeout=10) as response:
                html = response.read().decode('utf-8')
            found_files = re.findall(r'href="[^"]*?(userbouquet\.[^"]+\.tv)"', html)
            self.bouquet_filenames = sorted(list(set(found_files)), key=lambda x: x.lower())
            if not self.bouquet_filenames:
                self.error_message = "Nie znaleziono żadnych plików bukietów w repozytorium."
        except Exception as e:
            utils.log_error(e, self.__class__.__name__)
            self.error_message = "Błąd pobierania listy bukietów."
        finally:
            self._safe_call_main_thread(self.error_message, self.bouquet_filenames)

# POPRAWKA: Zmodyfikowano, aby przyjmować BASE_URL jako argument
class IptvBouquetInstallWorker(BaseWorker):
    def __init__(self, selected_bouquets, base_url, callback_progress, callback_finished):
        super(IptvBouquetInstallWorker, self).__init__(callback_finished)
        self.selected_bouquets = selected_bouquets
        self.base_url = base_url
        self.callback_progress = callback_progress
        self.progress_timer = eTimer()
        self.progress_timer.callback.append(self._safe_progress_callback)
        self._progress_args = ()

    def _safe_call_progress(self, *args):
        self._progress_args = args
        self.progress_timer.start(0, True)
    
    def _safe_progress_callback(self):
        self.progress_timer.stop()
        if not self._is_cancelled and self.callback_progress:
            self.callback_progress(*self._progress_args)
            
    def run(self):
        final_message = ""
        target_dir = "/etc/enigma2"
        bouquets_tv_path = os.path.join(target_dir, "bouquets.tv")
        
        try:
            total_bouquets = len(self.selected_bouquets)
            for i, filename in enumerate(self.selected_bouquets):
                if self._is_cancelled: raise InterruptedError("Installation cancelled")
                self._safe_call_progress(i, total_bouquets, f"Pobieranie: {filename}")
                
                download_url = self.base_url + filename
                target_path = os.path.join(target_dir, filename)
                urllib.request.urlretrieve(download_url, target_path, reporthook=self._internal_reporthook)

            self._safe_call_progress(total_bouquets, total_bouquets, "Aktualizowanie bouquets.tv...")
            
            existing_lines = []
            if os.path.exists(bouquets_tv_path):
                with open(bouquets_tv_path, "r") as f:
                    existing_lines = [line.strip() for line in f.readlines()]
            
            existing_bouquets_set = set(existing_lines)
            
            for filename in self.selected_bouquets:
                bouquet_line = f'1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "{filename}" ORDER BY bouquet'
                if bouquet_line not in existing_bouquets_set:
                    existing_lines.append(bouquet_line)
            
            with open(bouquets_tv_path, "w") as f:
                f.write("\n".join(existing_lines) + "\n")
            
            self._safe_call_progress(total_bouquets, total_bouquets, "Przeładowywanie listy kanałów...")
            try:
                urllib.request.urlopen("http://127.0.0.1/api/servicelistreload?mode=2", timeout=15).read()
                final_message = f"Zainstalowano pomyślnie {total_bouquets} bukiet(ów).\nLista kanałów została przeładowana."
            except Exception as reload_e:
                utils.log_error(reload_e, "ServicelistReload")
                final_message = f"Zainstalowano {total_bouquets} bukiet(ów), ale wystąpił błąd podczas przeładowywania listy kanałów. Zrestartuj GUI ręcznie."
                
        except InterruptedError:
            final_message = "Instalacja anulowana przez użytkownika."
        except Exception as e:
            utils.log_error(e, self.__class__.__name__)
            final_message = f"Wystąpił błąd podczas instalacji:\n{e}"
        finally:
            self._safe_call_main_thread(final_message)


# --- Pozostałe workery bez zmian ---
class SourcesXmlDownloadWorker(BaseWorker):
    def __init__(self, callback_finished):
        super(SourcesXmlDownloadWorker, self).__init__(callback_finished)
        self.error_message = None
        self.final_message = None

    def run(self):
        target_path = os.path.join(constants.SOURCES_XML_TARGET_DIR, constants.SOURCES_XML_FILENAME)
        filename = constants.SOURCES_XML_FILENAME
        try:
            if self._is_cancelled: return
            
            if not os.path.exists(constants.SOURCES_XML_TARGET_DIR):
                os.makedirs(constants.SOURCES_XML_TARGET_DIR, exist_ok=True)
            
            urllib.request.urlretrieve(constants.SOURCES_XML_URL, target_path, reporthook=self._internal_reporthook)
            
            self.final_message = f"Plik '{filename}' pomyślnie zainstalowany."
        except InterruptedError:
            self.error_message = "Pobieranie anulowane przez użytkownika."
        except Exception as e:
            utils.log_error(e, self.__class__.__name__)
            self.error_message = f"Błąd pobierania pliku {filename}."
        finally:
            if not self._is_cancelled:
                self._safe_call_main_thread(self.error_message, self.final_message)