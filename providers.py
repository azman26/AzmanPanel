import os
import subprocess
import urllib.request
import urllib.parse
import zipfile
import tempfile
import shutil
import threading
import time
import re
import stat

from enigma import eDVBDB, eConsoleAppContainer, eListboxPythonMultiContent, gFont
from enigma import eTimer

from Plugins.Plugin import PluginDescriptor
from Components.ActionMap import ActionMap
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.Label import Label
from Components.Sources.StaticText import StaticText
from Components.config import config, getConfigListEntry, ConfigSelection, ConfigSubsection, NoSave, ConfigNothing
from Components.ConfigList import ConfigListScreen
from Tools.BoundFunction import boundFunction
from Components.ProgressBar import ProgressBar
from Components.MenuList import MenuList


# --- STAŁE ---
GITHUB_BOUQUET_ZIP_URL = "https://github.com/azman26/azmanIPTVsettings/archive/refs/heads/main.zip"
BOUQUET_TARGET_DIR = "/etc/enigma2"
GITHUB_BOUQUET_REPO_NAME = "azmanIPTVsettings-main"
BOUQUET_FILE_EXTENSIONS = ('.tv', '.userbouquet', '.radio')
GITHUB_FAST_BOUQUET_ZIP_URL = "https://github.com/azman26/azmanFASTsettings/archive/refs/heads/main.zip"
GITHUB_FAST_BOUQUET_REPO_NAME = "azmanFASTsettings-main"
SOURCES_XML_URL = "https://raw.githubusercontent.com/azman26/EPGazman/main/polandAzman.sources.xml"
SOURCES_XML_TARGET_DIR = "/etc/epgimport"
SOURCES_XML_FILENAME = "polandAzman.sources.xml"
PICONS_BASE_URL = "https://www.topolowa4.pl/Picony/"
DEFAULT_PICON_TARGET_DIR = "/media/hdd/picon"
PICON_RECOMMENDED_DIRS = [("/media/hdd/picon", "HDD (/media/hdd/picon)"), ("/media/usb/picon", "USB (/media/usb/picon)")]
GITHUB_E2K_SKINS_REPO_URL = "https://github.com/azman26/enigma2-E2K-skins/archive/refs/heads/main.zip"
E2K_SKINS_REPO_NAME = "enigma2-E2K-skins-main"
E2K_SKINS_TARGET_DIR = "/etc/E2Kodi/userSkins"
E2K_SKIN_FOLDERS_TO_INSTALL = ["azman-E2K-MetrixHD-skins", "jk36-E2K-skins-all"]
E2KODI_BASE_DIR = "/etc/E2Kodi"
GITHUB_E2K_PLUGINS_ZIP_URL = "https://github.com/azman26/enigma2-E2K-plugins/archive/refs/heads/main.zip"
E2K_PLUGINS_REPO_NAME = "enigma2-E2K-plugins-main"
E2K_PLUGINS_TARGET_DIR = "/usr/lib/enigma2/python/Plugins/Extensions/E2Kodi/site-packages/emukodi/Plugins"
IPTV_ORG_PL_M3U_URL = "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/pl.m3u"
IPTV_ORG_PL_BOUQUET_FILENAME = "userbouquet.iptvorg_pl.tv"
IPTV_ORG_PL_BOUQUET_NAME = "iptv.org m3u PL"

config.plugins.azmanIPTV = ConfigSubsection()

# --- EKRAN WIELOKROTNEGO WYBORU ---
class AzmanSelectListScreen(Screen):
    skin = """
        <screen name="AzmanSelectListScreen" title="Wybierz" position="center,center" size="1012,632">
            <widget source="title" render="Label" position="center,13" size="987,51" font="Regular;31" halign="center" />
            <widget name="list" position="13,76" size="987,442" scrollbarMode="showOnDemand" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/AzmanPanel/red.png" position="25,557" size="37,51" alphatest="blend" />
            <widget source="key_red" render="Label" position="70,557" size="180,51" zPosition="3" font="Regular; 28" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/AzmanPanel/green.png" position="265,557" size="37,51" alphatest="blend" />
            <widget source="key_green" render="Label" position="310,557" size="290,51" zPosition="3" font="Regular; 28" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/AzmanPanel/yellow.png" position="615,557" size="37,51" alphatest="blend" />
            <widget source="key_yellow" render="Label" position="660,557" size="330,51" zPosition="3" font="Regular; 28" transparent="1" />
        </screen>
    """
    
    def __init__(self, session, title, item_list):
        Screen.__init__(self, session)
        self.session = session
        self.item_list = item_list 
        self.selected_items = []

        self["title"] = StaticText(title)
        self["key_red"] = StaticText("Anuluj")
        self["key_green"] = StaticText("Zainstaluj zaznaczone")
        self["key_yellow"] = StaticText("Zaznacz/Odznacz wszystko")
        
        self["list"] = MenuList([])
        
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions"], {
            "ok": self.toggle_selection,
            "cancel": self.cancel,
            "red": self.cancel,
            "green": self.save,
            "yellow": self.toggle_all,
            "up": self["list"].up,
            "down": self["list"].down
        }, -1)
        
        self.onLayoutFinish.append(self.build_list)

    def build_list(self):
        menu_list = []
        for value, display_name in self.item_list:
            prefix = "[x]" if value in self.selected_items else "[ ]"
            menu_list.append( (f"{prefix} {display_name}", value) )
        self["list"].setList(menu_list)

    def toggle_selection(self):
        current = self["list"].getCurrent()
        if not current: return
        
        value_to_toggle = current[1]
        
        if value_to_toggle in self.selected_items:
            self.selected_items.remove(value_to_toggle)
        else:
            self.selected_items.append(value_to_toggle)
        
        self.build_list()
        
    def toggle_all(self):
        all_values = [item[0] for item in self.item_list]
        if len(self.selected_items) == len(all_values):
            self.selected_items = []
        else:
            self.selected_items = all_values
        self.build_list()

    def save(self):
        if not self.selected_items:
            self.session.open(MessageBox, "Nie zaznaczono żadnych elementów.", type=MessageBox.TYPE_INFO, timeout=5)
            return
        self.close(self.selected_items)

    def cancel(self):
        self.close([])

# --- FUNKCJE I KLASY POMOCNICZE ---
def safe_extract_zip_member(zip_ref, member, target_dir):
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

class DownloadProgressScreen(Screen):
    skin = """
        <screen name="DownloadProgressScreen" title="Pobieranie..." position="center,center" size="600,200">
            <widget name="status_label" position="10,10" size="580,40" font="Regular;24" halign="center" valign="center" />
            <widget name="progress_bar" position="50,80" size="500,30" borderWidth="2" borderColor="#ffffff" />
            <widget name="info_label" position="10,120" size="580,40" font="Regular;20" halign="center" valign="center" />
        </screen>
    """
    def __init__(self, session, title="Pobieranie pliku"):
        Screen.__init__(self, session)
        self.setTitle(title)
        self.close_timer = eTimer()
        self.close_timer.callback.append(self.close)
        
        self["status_label"] = Label("Inicjowanie pobierania...")
        self["progress_bar"] = ProgressBar()
        self["progress_bar"].setValue(0)
        self["info_label"] = Label("")
        self["actions"] = ActionMap(["OkCancelActions"], {"cancel": self.close}, -1)

    def setProgress(self, current_bytes, total_bytes, custom_title=None):
        if custom_title:
             self["status_label"].setText(custom_title)

        if current_bytes == -1:
            return
            
        if total_bytes > 0:
            percentage = int((current_bytes / total_bytes) * 100)
            self["progress_bar"].setValue(percentage)
            if not custom_title:
                self["status_label"].setText(f"Pobieranie ({percentage}%)")
                
            if total_bytes >= 1024 * 1024:
                self["info_label"].setText(f"{current_bytes / (1024*1024):.2f} MB / {total_bytes / (1024*1024):.2f} MB")
            elif total_bytes >= 1024:
                self["info_label"].setText(f"{current_bytes / 1024:.2f} KB / {total_bytes / 1024:.2f} KB")
            else:
                self["info_label"].setText(f"{current_bytes} B / {total_bytes} B")
        else:
            if not custom_title:
                 self["status_label"].setText("Analizowanie...")
            self["progress_bar"].setValue(0)
            self["info_label"].setText("Trwa operacja plikowa...")

    def showFinished(self, message, is_error=False, timeout=5):
        self["status_label"].setText("Zakończono!")
        self["progress_bar"].setValue(100)
        self["info_label"].setText(message)
        self.close_timer.start(timeout * 1000, True)

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

# --- KLASY ROBOCZE (WORKERS) ---

class PiconInstallationWorker(BaseDownloadWorker):
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
                        safe_extract_zip_member(zip_ref, member, self.temp_extraction_dir)
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
                    safe_extract_zip_member(zip_ref, member, self.temp_dir)
            
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
            bouquets_tv_path = os.path.join(BOUQUET_TARGET_DIR, "bouquets.tv")
            new_entry = f'#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "{os.path.basename(self.output_bouquet_path)}" ORDER BY bouquet\n'
            
            if not os.path.exists(bouquets_tv_path) or os.path.basename(self.output_bouquet_path) not in open(bouquets_tv_path, 'r', encoding='utf-8').read():
                with open(bouquets_tv_path, 'a', encoding='utf-8') as f: f.write(new_entry)
                self.final_message += "\nDodano wpis do głównej listy bukietów."
            else: self.final_message += "\nWpis już istniał."
        except Exception as e: self.error_message = f"Błąd konwersji '{self.bouquet_name}': {str(e)}"
        finally:
            if self.temp_dir_for_cleanup: shutil.rmtree(self.temp_dir_for_cleanup, ignore_errors=True)
            self._safe_call_main_thread(self.callback_finished, self.parent_screen, self.error_message, self.final_message)

# --- GŁÓWNE EKRANY PLUGINU ---

class AzmanPanelMainScreen(Screen):
    skin = """
        <screen name="AzmanPanelMainScreen" title="Azman Panel" position="center,center" size="1012,632">
            <widget name="title" position="center,5" size="987,70" font="Regular;31" halign="center" valign="top" />
            <widget name="info_label" position="13,76" size="987,442" font="Regular;28" halign="center" valign="center" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/AzmanPanel/red.png" position="25,557" size="37,51" alphatest="blend" />
            <widget source="key_red" render="Label" position="70,557" size="210,51" zPosition="3" font="Regular; 28" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/AzmanPanel/green.png" position="295,557" size="37,51" alphatest="blend" />
            <widget source="key_green" render="Label" position="340,557" size="180,51" zPosition="3" font="Regular; 28" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/AzmanPanel/yellow.png" position="540,557" size="37,51" alphatest="blend" />
            <widget source="key_yellow" render="Label" position="585,557" size="180,51" zPosition="3" font="Regular; 28" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/AzmanPanel/blue.png" position="770,557" size="37,51" alphatest="blend" />
            <widget source="key_blue" render="Label" position="815,557" size="180,51" zPosition="3" font="Regular; 28" transparent="1" />
        </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self.progress_screen = None
        self.temp_repo_dir = None
        
        PLUGIN_VERSION = "1.0.3"
        self["title"] = Label(f"Azman Panel\n{PLUGIN_VERSION}")
        self["info_label"] = Label(
            "Wybierz opcję, naciskając jeden z kolorowych przycisków na pilocie:\n"
            "   Czerwony: Pobierz Dodatki E2K\n"
            "   Zielony: Pobierz Bukiety IPTV\n"
            "   Żółty: Pobierz Picony\n" 
            "   Niebieski: Pobierz azman EPG Sources"
        )
        self["key_red"] = StaticText("E2K Dodatki")
        self["key_green"] = StaticText("IPTV Bouquets")
        self["key_yellow"] = StaticText("Picons") 
        self["key_blue"] = StaticText("EPG Sources")
        
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "cancel": self.close, 
            "red": self.open_e2k_addons_screen,
            "green": self.open_bouquet_source_selection, 
            "yellow": self.open_picon_management_screen,
            "blue": self.download_and_install_sources_xml, 
        }, -1)
        self.onClose.append(self.__onClose)

    def __onClose(self):
        if self.temp_repo_dir: shutil.rmtree(self.temp_repo_dir, ignore_errors=True)
        
    def _update_progress_ui(self, current_bytes, total_bytes):
        if self.progress_screen: self.progress_screen.setProgress(current_bytes, total_bytes)
        
    def open_e2k_addons_screen(self):
        self.session.open(E2KAddonsScreen)

    def open_picon_management_screen(self):
        self.session.open(PiconManagementScreen)

    def download_and_install_sources_xml(self):
        if not os.path.exists(SOURCES_XML_TARGET_DIR): os.makedirs(SOURCES_XML_TARGET_DIR, exist_ok=True)
        self.session.openWithCallback(
            self._confirm_and_proceed_download_sources_xml, MessageBox,
            f"Czy na pewno chcesz pobrać i nadpisać plik: '{SOURCES_XML_FILENAME}' w {SOURCES_XML_TARGET_DIR}?",
            MessageBox.TYPE_YESNO, timeout=10, default=False
        )

    def _confirm_and_proceed_download_sources_xml(self, confirmed):
        if not confirmed: return
        target_path = os.path.join(SOURCES_XML_TARGET_DIR, SOURCES_XML_FILENAME)
        self.progress_screen = self.session.open(DownloadProgressScreen, title=f"Pobieranie {SOURCES_XML_FILENAME}...")
        worker = SourcesXmlDownloadWorker(SOURCES_XML_URL, target_path, self._update_progress_ui, self._on_generic_download_finished, parent_screen=self)
        worker.start()

    def _on_generic_download_finished(self, parent_screen, error_message, final_message, *args):
        if parent_screen.progress_screen and parent_screen.progress_screen.shown:
            parent_screen.progress_screen.close()
        parent_screen.progress_screen = None

        message = final_message or error_message
        msg_type = MessageBox.TYPE_ERROR if error_message else MessageBox.TYPE_INFO

        self.final_epg_message_timer = eTimer()
        self.final_epg_message_timer.callback.append(
            boundFunction(self.session.open, MessageBox, message, type=msg_type, timeout=10)
        )
        self.final_epg_message_timer.start(1, True)
    
    def open_bouquet_source_selection(self, *args):
        self.session.openWithCallback(self._on_bouquet_source_selection, BouquetSourceSelectionScreen)
        
    def _on_bouquet_source_selection(self, result):
        if self.temp_repo_dir: shutil.rmtree(self.temp_repo_dir, ignore_errors=True); self.temp_repo_dir = None
        
        if not result:
            self.show()
            return

        source_map = {
            'standard': (GITHUB_BOUQUET_ZIP_URL, GITHUB_BOUQUET_REPO_NAME, "Pobieranie listy bukietów IPTV PL..."),
            'fast': (GITHUB_FAST_BOUQUET_ZIP_URL, GITHUB_FAST_BOUQUET_REPO_NAME, "Pobieranie listy bukietów FAST...")}
        
        if result in source_map:
            self.hide()
            zip_url, repo_name, title = source_map[result]
            self.temp_repo_dir = tempfile.mkdtemp()
            self.progress_screen = self.session.open(DownloadProgressScreen, title=title)
            
            worker = RepoItemListWorker(
                zip_url=zip_url,
                repo_name=repo_name,
                temp_extraction_dir=self.temp_repo_dir,
                item_finder_func=self._find_bouquet_items,
                callback_progress=self._update_progress_ui,
                callback_finished=self._list_download_finished,
                parent_screen=self)
            worker.start()
            
        elif result == 'iptv_org_pl':
            self.hide()
            tmp_dir = tempfile.mkdtemp()
            m3u_path = os.path.join(tmp_dir, "pl.m3u")
            output_path = os.path.join(BOUQUET_TARGET_DIR, IPTV_ORG_PL_BOUQUET_FILENAME)
            self.progress_screen = self.session.open(DownloadProgressScreen, title=f"Pobieranie '{IPTV_ORG_PL_BOUQUET_NAME}'...")
            worker = IptvOrgPlDownloadWorker(IPTV_ORG_PL_M3U_URL, m3u_path, output_path, IPTV_ORG_PL_BOUQUET_NAME, self._update_progress_ui, self._iptv_org_pl_download_finished, parent_screen=self)
            worker.start()

    def _find_bouquet_items(self, repo_path):
        found = []
        for root, _, files in os.walk(repo_path):
            for file_name in files:
                is_bouquet = file_name.lower().endswith(BOUQUET_FILE_EXTENSIONS) or file_name.lower() in ('bouquets.tv', 'bouquets.radio')
                if is_bouquet:
                    found.append(os.path.join(root, file_name))
        return found
        
    def _list_download_finished(self, parent_screen, error_message, found_items, temp_extraction_dir):
        if self.progress_screen: self.progress_screen.close(); self.progress_screen = None
        
        if error_message or not found_items:
            msg = error_message or "Nie znaleziono żadnych elementów."
            if temp_extraction_dir: shutil.rmtree(temp_extraction_dir, ignore_errors=True)
            self.session.openWithCallback(self.show, MessageBox, msg, MessageBox.TYPE_ERROR, timeout=7)
            return

        self.temp_repo_dir = temp_extraction_dir
        item_list = [(path, name) for name, path in found_items]
        
        self.open_selection_timer = eTimer()
        self.open_selection_timer.callback.append(boundFunction(self._open_multi_selection_screen, "bukiety", item_list, self._on_multi_bouquet_selected))
        self.open_selection_timer.start(1, True)
    
    def _open_multi_selection_screen(self, item_type_name, item_list, selection_callback):
        self.session.openWithCallback(selection_callback, AzmanSelectListScreen, f"Wybierz {item_type_name} do instalacji", item_list)

    def _reload_dvb_services(self):
        print("[AzmanPanel] Reloading DVB services and bouquets.")
        eDVBDB.getInstance().reloadServicelist()
        eDVBDB.getInstance().reloadBouquets()

    def _on_multi_bouquet_selected(self, selected_paths):
        self.show()
        if not selected_paths:
            if self.temp_repo_dir: shutil.rmtree(self.temp_repo_dir, ignore_errors=True); self.temp_repo_dir = None
            return
            
        installed_count, failed_count = 0, 0
        for path in selected_paths:
            try:
                dest_filename = os.path.basename(path)
                dest_path = os.path.join(BOUQUET_TARGET_DIR, dest_filename)
                shutil.copy2(path, dest_path)
                os.chmod(dest_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
                bouquets_tv_path = os.path.join(BOUQUET_TARGET_DIR, "bouquets.tv")
                new_entry = f'#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "{dest_filename}" ORDER BY bouquet\n'
                entry_exists = os.path.exists(bouquets_tv_path) and dest_filename in open(bouquets_tv_path, 'r', encoding='utf-8').read()
                if not entry_exists:
                    with open(bouquets_tv_path, 'a', encoding='utf-8') as f: f.write(new_entry)
                installed_count += 1
            except Exception as e: print(f"[AzmanPanel] Failed to install bouquet {path}: {e}"); failed_count += 1
        
        if self.temp_repo_dir: shutil.rmtree(self.temp_repo_dir, ignore_errors=True); self.temp_repo_dir = None
        
        self._reload_dvb_services()
        message = f"Zainstalowano {installed_count} z {len(selected_paths)} wybranych bukietów."
        if failed_count > 0: message += f"\n{failed_count} instalacji nie powiodło się."
        
        self.session.open(MessageBox, message, type=MessageBox.TYPE_INFO, timeout=10)
        
    def _iptv_org_pl_download_finished(self, parent_screen, error_message, final_message):
        if parent_screen.progress_screen and parent_screen.progress_screen.shown:
            parent_screen.progress_screen.close()
        parent_screen.progress_screen = None

        message = final_message or error_message
        msg_type = MessageBox.TYPE_ERROR if error_message else MessageBox.TYPE_INFO
        
        if not error_message:
            self._reload_dvb_services()
            message += "\n\nPrzeładowano listę kanałów."

        self.final_bouquet_message_timer = eTimer()
        self.final_bouquet_message_timer.callback.append(
            boundFunction(
                self.session.openWithCallback, 
                self.open_bouquet_source_selection, 
                MessageBox, 
                message, 
                type=msg_type, 
                timeout=10
            )
        )
        self.final_bouquet_message_timer.start(1, True)

class PiconManagementScreen(Screen):
    skin = """
        <screen name="PiconManagementScreen" title="Zarządzanie Piconami" position="center,center" size="1012,632">
            <widget source="title" render="Label" position="center,13" size="987,51" font="Regular;31" halign="center" />
            <widget name="list" position="13,76" size="987,442" scrollbarMode="showOnDemand" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/AzmanPanel/red.png" position="25,557" size="37,51" alphatest="blend" />
            <widget source="key_red" render="Label" position="70,557" size="180,51" zPosition="3" font="Regular; 28" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/AzmanPanel/green.png" position="265,557" size="37,51" alphatest="blend" />
            <widget source="key_green" render="Label" position="310,557" size="350,51" zPosition="3" font="Regular; 28" transparent="1" />
        </screen>
    """
    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self.progress_screen = None
        self.target_dir = None
        
        self["title"] = StaticText("Wybierz lokalizację i zainstaluj picony")
        self["key_red"] = StaticText("Anuluj")
        self["key_green"] = StaticText("Pobierz listę paczek")
        
        self["list"] = MenuList([])
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "cancel": self.close,
            "red": self.close,
            "green": self.start_list_download,
            "ok": self.start_list_download,
        }, -1)
        
        self.onLayoutFinish.append(self.build_target_list)

    def build_target_list(self):
        picon_dir_choices = []
        for path, display_name in PICON_RECOMMENDED_DIRS:
            parent_dir = os.path.dirname(path)
            if os.path.exists(parent_dir) and os.path.isdir(parent_dir) and os.access(parent_dir, os.W_OK):
                status = " (zalecane)"
                if not os.path.exists(path):
                    status += " - zostanie utworzony"
                picon_dir_choices.append((f"{display_name}{status}", path))
        
        if not picon_dir_choices:
            parent_default_dir = os.path.dirname(DEFAULT_PICON_TARGET_DIR)
            if os.path.exists(parent_default_dir) and os.access(parent_default_dir, os.W_OK):
                 picon_dir_choices.append((f"Domyślny ({DEFAULT_PICON_TARGET_DIR})", DEFAULT_PICON_TARGET_DIR))

        if not picon_dir_choices:
            self.session.openWithCallback(
                self.close, MessageBox, 
                "Nie znaleziono żadnej zapisywalnej lokalizacji dla picon (HDD/USB).", 
                MessageBox.TYPE_ERROR
            )
        else:
            self["list"].setList(picon_dir_choices)

    def start_list_download(self):
        selection = self["list"].getCurrent()
        if not selection:
            return
        
        self.target_dir = selection[1]
        
        self.progress_screen = self.session.open(DownloadProgressScreen, title="Skanowanie archiwów ZIP...")
        worker = PiconZipListWorker(PICONS_BASE_URL, self.on_picon_list_downloaded, parent_screen=self)
        worker.start()

    def on_picon_list_downloaded(self, parent_screen, error_message, picon_zip_filenames):
        if self.progress_screen:
            self.progress_screen.close()
            self.progress_screen = None

        if error_message or not picon_zip_filenames:
            msg = error_message or "Nie znaleziono plików *.zip na serwerze."
            self.session.open(MessageBox, msg, MessageBox.TYPE_ERROR)
            return

        item_list = [(filename, filename.replace('%20', ' ')) for filename in picon_zip_filenames]
        
        self.open_selection_timer = eTimer()
        self.open_selection_timer.callback.append(boundFunction(self.show_selection_screen, item_list))
        self.open_selection_timer.start(1, True)

    def show_selection_screen(self, item_list):
        self.session.openWithCallback(
            self.on_picons_selected,
            AzmanSelectListScreen,
            "Wybierz paczki picon do instalacji",
            item_list
        )
    
    def on_picons_selected(self, selected_zips):
        if not selected_zips:
            self.session.open(MessageBox, "Anulowano. Nie wybrano żadnych paczek.", MessageBox.TYPE_INFO, timeout=5)
            return

        self.progress_screen = self.session.open(DownloadProgressScreen, title="Przygotowanie do instalacji...")
        worker = PiconInstallationWorker(
            selected_zips=selected_zips,
            target_dir=self.target_dir,
            base_url=PICONS_BASE_URL,
            callback_progress=self._update_progress_ui,
            callback_finished=self.on_installation_finished
        )
        worker.start()

    def _update_progress_ui(self, current_bytes, total_bytes, custom_title=None):
        if self.progress_screen:
            self.progress_screen.setProgress(current_bytes, total_bytes, custom_title)

    def on_installation_finished(self, final_message):
        if self.progress_screen:
            self.progress_screen.close()
            self.progress_screen = None
        
        self.final_message_timer = eTimer()
        self.final_message_timer.callback.append(boundFunction(self.show_final_messagebox, final_message))
        self.final_message_timer.start(1, True)

    def show_final_messagebox(self, final_message):
         self.session.openWithCallback(
            self.close, 
            MessageBox, 
            f"Zakończono instalację picon.\n\n{final_message}", 
            type=MessageBox.TYPE_INFO, 
            timeout=10
        )


class E2KAddonsScreen(Screen):
    skin = """
        <screen name="E2KAddonsScreen" title="E2K Dodatki" position="center,center" size="1012,632">
            <widget name="title" position="center,5" size="987,70" font="Regular;31" halign="center" valign="top" />
            <widget name="info_label" position="13,76" size="987,442" font="Regular;28" halign="center" valign="center" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/AzmanPanel/green.png" position="295,557" size="37,51" alphatest="blend" />
            <widget source="key_green" render="Label" position="340,557" size="180,51" zPosition="3" font="Regular; 28" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/AzmanPanel/yellow.png" position="540,557" size="37,51" alphatest="blend" />
            <widget source="key_yellow" render="Label" position="585,557" size="180,51" zPosition="3" font="Regular; 28" transparent="1" />
        </screen>
    """
    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self.setTitle("E2K Dodatki")
        self.progress_screen = None
        self.changes_made = False
        self.temp_dir = None
        self.current_config = {}

        self["title"] = Label("E2K Dodatki")
        self["info_label"] = Label(
            "Wybierz opcję, aby zarządzać dodatkami E2Kodi:\n"
            "   Zielony: Pluginy E2K\n"
            "   Żółty: Skiny E2K\n\n"
            "Pobrana zostanie lista dostępnych dodatków,\nz której będzie można wybrać te do instalacji."
        )
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "cancel": self.ask_for_restart_on_exit,
            "green": self.start_plugin_download,
            "yellow": self.start_skin_download,
        }, -1)
        self["key_green"] = StaticText("Pluginy")
        self["key_yellow"] = StaticText("Skiny")
        self.onClose.append(self.cleanup)

    def cleanup(self):
        if self.temp_dir:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.temp_dir = None

    def ask_for_restart_on_exit(self):
        if self.changes_made:
            self.session.openWithCallback(
                self._prompt_gui_restart_callback_final, MessageBox,
                "Zainstalowano nowe dodatki E2K.\nZalecany jest restart GUI.\nCzy chcesz zrestartować GUI teraz?",
                MessageBox.TYPE_YESNO, timeout=15, default=True
            )
        else:
            self.close()

    def _prompt_gui_restart_callback_final(self, confirmed):
        if confirmed:
            self.session.openWithCallback(self.close, MessageBox, "Restartowanie GUI Enigmy2...", MessageBox.TYPE_INFO, timeout=3)
            eConsoleAppContainer().execute("init 4 && sleep 2 && init 3")
        else:
            self.close()

    def _update_progress_ui(self, current_bytes, total_bytes):
        if self.progress_screen:
            self.progress_screen.setProgress(current_bytes, total_bytes)

    def _find_skin_items(self, repo_path):
        return [os.path.join(repo_path, f) for f in E2K_SKIN_FOLDERS_TO_INSTALL if os.path.isdir(os.path.join(repo_path, f))]

    def _find_plugin_items(self, repo_path):
        return [os.path.join(repo_path, i) for i in os.listdir(repo_path) if not i.startswith('.') and os.path.isdir(os.path.join(repo_path, i))]

    def start_download(self, config):
        self.cleanup()
        self.current_config = config
        
        if not os.path.exists(E2KODI_BASE_DIR):
            self.session.open(MessageBox, f"Katalog E2Kodi ({E2KODI_BASE_DIR}) nie znaleziony.", MessageBox.TYPE_ERROR, timeout=10)
            return

        self.progress_screen = self.session.open(DownloadProgressScreen, title=f"Pobieranie listy {config['type']}...")
        worker = E2KListDownloader(
            config=config,
            callback_progress=self._update_progress_ui,
            callback_finished=self.on_list_downloaded
        )
        worker.start()

    def start_skin_download(self):
        self.start_download({
            # *** POPRAWKA GRAMATYCZNA ***
            "type": "skiny",
            "url": GITHUB_E2K_SKINS_REPO_URL,
            "repo_name": E2K_SKINS_REPO_NAME,
            "target_dir": E2K_SKINS_TARGET_DIR,
            "finder": self._find_skin_items
        })

    def start_plugin_download(self):
        self.start_download({
            # *** POPRAWKA GRAMATYCZNA ***
            "type": "pluginy",
            "url": GITHUB_E2K_PLUGINS_ZIP_URL,
            "repo_name": E2K_PLUGINS_REPO_NAME,
            "target_dir": E2K_PLUGINS_TARGET_DIR,
            "finder": self._find_plugin_items
        })

    def on_list_downloaded(self, error_message, found_items, temp_dir):
        if self.progress_screen:
            self.progress_screen.close()
            self.progress_screen = None
        
        self.temp_dir = temp_dir

        if error_message or not found_items:
            msg = error_message or f"Nie znaleziono żadnych {self.current_config['type']}."
            self.session.open(MessageBox, msg, MessageBox.TYPE_ERROR)
            self.cleanup()
            return
        
        item_list = [(item['path'], item['name']) for item in found_items]
        
        self.open_selection_timer = eTimer()
        self.open_selection_timer.callback.append(boundFunction(self.show_selection_screen, item_list))
        self.open_selection_timer.start(1, True)
    
    def show_selection_screen(self, item_list):
        self.session.openWithCallback(
            self.on_items_selected,
            AzmanSelectListScreen,
            f"Wybierz {self.current_config['type']} do instalacji",
            item_list
        )

    def on_items_selected(self, selected_paths):
        if not selected_paths:
            self.cleanup()
            return

        target_dir = self.current_config['target_dir']
        
        if not os.path.isdir(target_dir):
            try:
                os.makedirs(target_dir)
            except OSError as e:
                self.session.open(MessageBox, f"Błąd tworzenia katalogu docelowego:\n{target_dir}\n{e}", MessageBox.TYPE_ERROR)
                self.cleanup()
                return

        installed_count = 0
        failed_count = 0
        installed_names = []
        for source_path in selected_paths:
            try:
                item_name = os.path.basename(source_path)
                dest_path = os.path.join(target_dir, item_name)
                
                if os.path.exists(dest_path):
                    shutil.rmtree(dest_path)
                
                shutil.copytree(source_path, dest_path)
                installed_names.append(item_name)
                installed_count += 1
            except Exception as e:
                print(f"[AzmanPanel E2K] Błąd instalacji {item_name}: {e}")
                failed_count += 1
        
        self.cleanup()
        
        if installed_count > 0:
            self.changes_made = True
        
        message = f"Zainstalowano: {installed_count}\nBłędy: {failed_count}"
        if installed_names:
            message += "\n\nZainstalowane pozycje:\n" + "\n".join(f"- {name}" for name in installed_names)
            
        self.session.open(MessageBox, message, type=MessageBox.TYPE_INFO, timeout=10)

class BouquetSourceSelectionScreen(Screen):
    skin = """
        <screen name="BouquetSourceSelectionScreen" title="Wybierz źródło bukietów" position="center,center" size="1012,632">
            <widget name="title" position="center,5" size="987,70" font="Regular;31" halign="center" valign="top" />
            <widget name="info_label" position="13,76" size="987,442" font="Regular;28" halign="center" valign="center" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/AzmanPanel/green.png" position="25,557" size="37,51" alphatest="blend" />
            <widget source="key_green" render="Label" position="70,557" size="290,51" zPosition="3" font="Regular; 28" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/AzmanPanel/yellow.png" position="370,557" size="37,51" alphatest="blend" />
            <widget source="key_yellow" render="Label" position="415,557" size="290,51" zPosition="3" font="Regular; 28" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/AzmanPanel/blue.png" position="715,557" size="37,51" alphatest="blend" />
            <widget source="key_blue" render="Label" position="760,557" size="230,51" zPosition="3" font="Regular; 28" transparent="1" />
        </screen>
    """
    def __init__(self, session):
        Screen.__init__(self, session)
        self.setTitle("Wybierz źródło bukietów")
        self["title"] = Label("Wybierz rodzaj bukietów do pobrania")
        self["info_label"] = Label("Wybierz źródło, z którego chcesz pobrać bukiety kanałów IPTV.")
        self["key_green"] = StaticText("IPTV PL")
        self["key_yellow"] = StaticText("FAST Worldwide")
        self["key_blue"] = StaticText("iptv.org m3u PL")
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {"cancel": lambda: self.close(None), "green": lambda: self.close('standard'), "yellow": lambda: self.close('fast'), "blue": lambda: self.close('iptv_org_pl')}, -1)

# --- REJESTRACJA PLUGINU ---

def main(session, **kwargs):
    session.open(AzmanPanelMainScreen)

def Plugins(**kwargs):
    return [PluginDescriptor(
        name="Azman Panel", 
        description="Pobieranie bukietów IPTV, Picon, dodatków E2K oraz EPG sources.", 
        icon="icon.png", 
        where=[PluginDescriptor.WHERE_PLUGINMENU], 
        fnc=main
    )]