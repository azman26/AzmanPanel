# /usr/lib/enigma2/python/Plugins/Extensions/AzmanPanel/screens.py

import os
import shutil
import tempfile
import stat

from enigma import eTimer
from Components.ActionMap import ActionMap
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.Label import Label
from Components.Sources.StaticText import StaticText
from Tools.BoundFunction import boundFunction
from Components.ProgressBar import ProgressBar
from Components.MenuList import MenuList
from Components.Pixmap import Pixmap
from Tools.LoadPixmap import LoadPixmap
from skin import loadSkin

# Definiujemy absolutną ścieżkę do katalogu pluginu
PLUGIN_PATH = os.path.dirname(os.path.realpath(__file__))

# Importy z lokalnych modułów
from . import constants, utils
from .workers import (PiconInstallationWorker, PiconZipListWorker, RepoItemListWorker,
                      E2KListDownloader, SourcesXmlDownloadWorker, IptvOrgPlDownloadWorker)

# --- GŁÓWNY EKRAN PLUGINU (WERSJA - STATYCZNA SIATKA) ---
loadSkin(f"{PLUGIN_PATH}/skin.xml")

class AzmanPanelMainScreen(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self.progress_screen = None
        self.temp_repo_dir = None
        
        self.changes_made_e2k = False
        self.temp_dir_e2k = None
        self.current_config_e2k = {}

        self.GRID_ROWS, self.GRID_COLS = 4, 6
        self.items_per_page = self.GRID_ROWS * self.GRID_COLS
        self.items = []
        self.markerPixmap = LoadPixmap(f"{PLUGIN_PATH}/icons/marker.png")
        self.current_page, self.selected_pos = 0, (0, 0)

        self["title"] = Label("Azman Panel")
        self["version_info"] = Label(constants.PLUGIN_VERSION)
        self["description"] = Label("")

        for r in range(self.GRID_ROWS):
            for c in range(self.GRID_COLS):
                self[f"logo_{r}x{c}"], self[f"marker_{r}x{c}"] = Pixmap(), Pixmap()

        self["actions"] = ActionMap(["OkCancelActions", "DirectionActions"], {
            "ok": self.run_selected_item,
            "cancel": self.close,
            "back": self.close,
            "up": lambda: self.move(-1, 0),
            "down": lambda: self.move(1, 0),
            "left": lambda: self.move(0, -1),
            "right": lambda: self.move(0, 1),
        }, -1)

        self.onLayoutFinish.append(self.prepare_menu)
        self.onClose.append(self.__onClose)

    def prepare_menu(self):
        menu_definitions = [
            ("Pluginy E2K", self.start_e2k_plugins_flow, "icon_e2k.png"),
            ("Skiny E2K", self.start_e2k_skins_flow, "icon_skins.png"),
            ("Bukiety IPTV", self.open_bouquet_source_selection, "icon_iptv.png"),
            ("Picony", self.open_picon_management_screen, "icon_picons.png"),
            ("EPG Sources", self.download_and_install_sources_xml, "icon_epg.png"),
            # ### NOWA OPCJA W MENU ###
            ("Zainstaluj Azman Feed", self.install_azman_feed, "icon_feed.png"),
        ]
        self.items = [{'text': t, 'func': f, 'pixmap': LoadPixmap(f"{PLUGIN_PATH}/icons/{i}")} for t, f, i in menu_definitions]
        self.draw_page()

    # --- Pozostałe metody AzmanPanelMainScreen (bez zmian) ---
    def draw_page(self):
        start_index = self.current_page * self.items_per_page
        for r in range(self.GRID_ROWS):
            for c in range(self.GRID_COLS):
                item_index = start_index + (r * self.GRID_COLS + c)
                logo_widget = self[f"logo_{r}x{c}"]
                if item_index < len(self.items):
                    logo_widget.instance.setPixmap(self.items[item_index]['pixmap'])
                    logo_widget.show()
                else:
                    logo_widget.hide()
        self.update_selection()

    def update_selection(self):
        for r in range(self.GRID_ROWS):
            for c in range(self.GRID_COLS):
                self[f"marker_{r}x{c}"].hide()
        sel_r, sel_c = self.selected_pos
        item_index = self.current_page * self.items_per_page + (sel_r * self.GRID_COLS + sel_c)
        if item_index < len(self.items):
            self[f"marker_{sel_r}x{sel_c}"].instance.setPixmap(self.markerPixmap)
            self[f"marker_{sel_r}x{sel_c}"].show()
            self["description"].setText(self.items[item_index]['text'])
        else:
            self["description"].setText("")

    def move(self, d_row, d_col):
        new_r, new_c = self.selected_pos[0] + d_row, self.selected_pos[1] + d_col
        if new_c >= self.GRID_COLS: new_c, new_r = 0, new_r + 1
        if new_c < 0: new_c, new_r = self.GRID_COLS - 1, new_r - 1
        if new_r >= self.GRID_ROWS: new_r = 0
        if new_r < 0: new_r = self.GRID_ROWS - 1
        if self.current_page * self.items_per_page + (new_r * self.GRID_COLS + new_c) < len(self.items):
            self.selected_pos = (new_r, new_c)
            self.update_selection()

    def run_selected_item(self):
        sel_r, sel_c = self.selected_pos
        item_index = self.current_page * self.items_per_page + (sel_r * self.GRID_COLS + sel_c)
        if item_index < len(self.items):
            self.items[item_index]['func']()

    def __onClose(self):
        if self.temp_repo_dir:
            shutil.rmtree(self.temp_repo_dir, ignore_errors=True)
        self.cleanup_e2k()

    def _update_progress_ui(self, current_bytes, total_bytes):
        if self.progress_screen:
            self.progress_screen.setProgress(current_bytes, total_bytes)

    # ### NOWA FUNKCJA-ZAŚLEPKA ###
    def install_azman_feed(self):
        self.session.open(MessageBox, "Instalacja Azman Feed\n\nTa funkcja jest w przygotowaniu.", type=MessageBox.TYPE_INFO, timeout=5)

    # --- Metody dla BUKETÓW, EPG, PICONÓW (bez większych zmian) ---

    def open_picon_management_screen(self):
        self.session.open(MessageBox, "Funkcja w przygotowaniu.", type=MessageBox.TYPE_INFO, timeout=5)

    def download_and_install_sources_xml(self):
        if not os.path.exists(constants.SOURCES_XML_TARGET_DIR):
            os.makedirs(constants.SOURCES_XML_TARGET_DIR, exist_ok=True)
        self.session.openWithCallback(self._confirm_and_proceed_download_sources_xml, MessageBox, f"Czy chcesz pobrać i nadpisać plik:\n'{constants.SOURCES_XML_FILENAME}'\n\nw lokalizacji:\n{constants.SOURCES_XML_TARGET_DIR}?", MessageBox.TYPE_YESNO, timeout=10, default=False)

    def _confirm_and_proceed_download_sources_xml(self, confirmed):
        if not confirmed:
            return
        target_path = os.path.join(constants.SOURCES_XML_TARGET_DIR, constants.SOURCES_XML_FILENAME)
        self.progress_screen = self.session.open(DownloadProgressScreen, title=f"Pobieranie {constants.SOURCES_XML_FILENAME}...")
        worker = SourcesXmlDownloadWorker(constants.SOURCES_XML_URL, target_path, self._update_progress_ui, self._on_generic_download_finished, parent_screen=self)
        worker.start()

    def _on_generic_download_finished(self, parent_screen, error_message, final_message, *args):
        if parent_screen.progress_screen and parent_screen.progress_screen.shown:
            parent_screen.progress_screen.close()
        parent_screen.progress_screen = None
        message = final_message or error_message
        msg_type = MessageBox.TYPE_ERROR if error_message else MessageBox.TYPE_INFO
        self.final_epg_message_timer = eTimer()
        self.final_epg_message_timer.callback += boundFunction(self.session.open, MessageBox, message, type=msg_type, timeout=10)
        self.final_epg_message_timer.start(1, True)

    def open_bouquet_source_selection(self, *args):
        self.session.openWithCallback(self._on_bouquet_source_selection, BouquetSourceSelectionScreen)

    def _on_bouquet_source_selection(self, result):
        if self.temp_repo_dir:
            shutil.rmtree(self.temp_repo_dir, ignore_errors=True)
            self.temp_repo_dir = None
        if not result:
            self.show()
            return
        source_map = {'standard': (constants.GITHUB_BOUQUET_ZIP_URL, constants.GITHUB_BOUQUET_REPO_NAME, "Pobieranie listy bukietów IPTV PL..."), 'fast': (constants.GITHUB_FAST_BOUQUET_ZIP_URL, constants.GITHUB_FAST_BOUQUET_REPO_NAME, "Pobieranie listy bukietów FAST...")}
        if result in source_map:
            self.hide()
            zip_url, repo_name, title = source_map[result]
            self.temp_repo_dir = tempfile.mkdtemp()
            self.progress_screen = self.session.open(DownloadProgressScreen, title=title)
            worker = RepoItemListWorker(zip_url=zip_url, repo_name=repo_name, temp_extraction_dir=self.temp_repo_dir, item_finder_func=self._find_bouquet_items, callback_progress=self._update_progress_ui, callback_finished=self._list_download_finished, parent_screen=self)
            worker.start()
        elif result == 'iptv_org_pl':
            self.hide()
            tmp_dir = tempfile.mkdtemp()
            m3u_path = os.path.join(tmp_dir, "pl.m3u")
            output_path = os.path.join(constants.BOUQUET_TARGET_DIR, constants.IPTV_ORG_PL_BOUQUET_FILENAME)
            self.progress_screen = self.session.open(DownloadProgressScreen, title=f"Pobieranie '{constants.IPTV_ORG_PL_BOUQUET_NAME}'...")
            worker = IptvOrgPlDownloadWorker(constants.IPTV_ORG_PL_M3U_URL, m3u_path, output_path, constants.IPTV_ORG_PL_BOUQUET_NAME, self._update_progress_ui, self._iptv_org_pl_download_finished, parent_screen=self)
            worker.start()

    def _find_bouquet_items(self, repo_path):
        found = []
        for root, _, files in os.walk(repo_path):
            for file_name in files:
                is_bouquet = file_name.lower().endswith(constants.BOUQUET_FILE_EXTENSIONS) or file_name.lower() in ('bouquets.tv', 'bouquets.radio')
                if is_bouquet:
                    found.append(os.path.join(root, file_name))
        return found

    def _list_download_finished(self, parent_screen, error_message, found_items, temp_extraction_dir):
        if self.progress_screen:
            self.progress_screen.close()
            self.progress_screen = None
        if error_message or not found_items:
            msg = error_message or "Nie znaleziono żadnych elementów."
            if temp_extraction_dir:
                shutil.rmtree(temp_extraction_dir, ignore_errors=True)
            self.session.openWithCallback(self.show, MessageBox, msg, MessageBox.TYPE_ERROR, timeout=7)
            return
        item_list = [(path, os.path.basename(path)) for path in found_items]
        self.temp_repo_dir = temp_extraction_dir
        self.open_selection_timer = eTimer()
        self.open_selection_timer.callback += boundFunction(self._open_multi_selection_screen, "bukiety", item_list, self._on_multi_bouquet_selected)
        self.open_selection_timer.start(1, True)

    def _open_multi_selection_screen(self, item_type_name, item_list, selection_callback):
        self.session.openWithCallback(selection_callback, AzmanSelectListScreen, f"Wybierz {item_type_name} do instalacji", item_list)

    def _on_multi_bouquet_selected(self, selected_paths):
        self.show()
        if not selected_paths:
            if self.temp_repo_dir:
                shutil.rmtree(self.temp_repo_dir, ignore_errors=True)
                self.temp_repo_dir = None
            return
        installed_count, failed_count = 0, 0
        for path in selected_paths:
            try:
                dest_filename = os.path.basename(path)
                dest_path = os.path.join(constants.BOUQUET_TARGET_DIR, dest_filename)
                shutil.copy2(path, dest_path)
                os.chmod(dest_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
                bouquets_tv_path = os.path.join(constants.BOUQUET_TARGET_DIR, "bouquets.tv")
                new_entry = f'#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "{dest_filename}" ORDER BY bouquet\n'
                if not os.path.exists(bouquets_tv_path) or new_entry not in open(bouquets_tv_path, 'r', encoding='utf-8').read():
                    with open(bouquets_tv_path, 'a', encoding='utf-8') as f:
                        f.write(new_entry)
                installed_count += 1
            except Exception as e:
                print(f"[AzmanPanel] Failed to install bouquet {path}: {e}")
                failed_count += 1
        if self.temp_repo_dir:
            shutil.rmtree(self.temp_repo_dir, ignore_errors=True)
            self.temp_repo_dir = None
        utils.reload_dvb_services()
        message = f"Zainstalowano {installed_count} z {len(selected_paths)} wybranych bukietów."
        if failed_count > 0:
            message += f"\n{failed_count} instalacji nie powiodło się."
        self.session.open(MessageBox, message, type=MessageBox.TYPE_INFO, timeout=10)

    def _iptv_org_pl_download_finished(self, parent_screen, error_message, final_message):
        if parent_screen.progress_screen and parent_screen.progress_screen.shown:
            parent_screen.progress_screen.close()
        parent_screen.progress_screen = None
        message = final_message or error_message
        msg_type = MessageBox.TYPE_ERROR if error_message else MessageBox.TYPE_INFO
        if not error_message:
            utils.reload_dvb_services()
            message += "\n\nPrzeładowano listę kanałów."
        self.final_bouquet_message_timer = eTimer()
        self.final_bouquet_message_timer.callback += boundFunction(self.session.openWithCallback, self.open_bouquet_source_selection, MessageBox, message, type=msg_type, timeout=10)
        self.final_bouquet_message_timer.start(1, True)

    # --- Metody dla E2K ---
    
    def cleanup_e2k(self):
        if self.temp_dir_e2k:
            shutil.rmtree(self.temp_dir_e2k, ignore_errors=True)
            self.temp_dir_e2k = None

    def _ask_for_restart_e2k(self, *args):
        if self.changes_made_e2k:
            self.session.openWithCallback(
                self._do_restart_gui, MessageBox, 
                "Zainstalowano nowe dodatki E2K.\nZalecany jest restart GUI.\nCzy chcesz zrestartować GUI teraz?", 
                MessageBox.TYPE_YESNO, timeout=15, default=True
            )
        self.changes_made_e2k = False

    def _do_restart_gui(self, confirmed):
        if confirmed:
            from Screens.Standby import TryQuitMainloop
            self.session.open(TryQuitMainloop, 3)

    def _find_skin_items(self, repo_path):
        return [os.path.join(repo_path, f) for f in constants.E2K_SKIN_FOLDERS_TO_INSTALL if os.path.isdir(os.path.join(repo_path, f))]

    def _find_plugin_items(self, repo_path):
        return [os.path.join(repo_path, i) for i in os.listdir(repo_path) if not i.startswith('.') and os.path.isdir(os.path.join(repo_path, i))]

    def start_e2k_download(self, config):
        self.cleanup_e2k()
        self.current_config_e2k = config
        
        if not os.path.exists(constants.E2KODI_BASE_DIR):
            self.session.open(MessageBox, f"Katalog E2Kodi ({constants.E2KODI_BASE_DIR}) nie znaleziony.", MessageBox.TYPE_ERROR, timeout=10)
            return
        
        self.progress_screen = self.session.open(DownloadProgressScreen, title=f"Pobieranie listy {config['type']}...")
        worker = E2KListDownloader(config=config, callback_progress=self._update_progress_ui, callback_finished=self.on_e2k_list_downloaded)
        worker.start()

    def start_e2k_skins_flow(self):
        self.start_e2k_download({
            "type": "skinów", 
            "url": constants.GITHUB_E2K_SKINS_REPO_URL, 
            "repo_name": constants.E2K_SKINS_REPO_NAME, 
            "target_dir": constants.E2K_SKINS_TARGET_DIR, 
            "finder": self._find_skin_items
        })

    def start_e2k_plugins_flow(self):
        self.start_e2k_download({
            "type": "pluginów", 
            "url": constants.GITHUB_E2K_PLUGINS_ZIP_URL, 
            "repo_name": constants.E2K_PLUGINS_REPO_NAME, 
            "target_dir": constants.E2K_PLUGINS_TARGET_DIR, 
            "finder": self._find_plugin_items
        })

    def on_e2k_list_downloaded(self, error_message, found_items, temp_dir):
        if self.progress_screen:
            self.progress_screen.close()
            self.progress_screen = None
        
        self.temp_dir_e2k = temp_dir

        if error_message or not found_items:
            msg = error_message or f"Nie znaleziono żadnych {self.current_config_e2k['type']}."
            self.session.open(MessageBox, msg, MessageBox.TYPE_ERROR)
            self.cleanup_e2k()
            return
        
        item_list = [(item['path'], item['name']) for item in found_items]
        self.open_selection_timer_e2k = eTimer()
        self.open_selection_timer_e2k.callback += boundFunction(self.show_e2k_selection_screen, item_list)
        self.open_selection_timer_e2k.start(1, True)
    
    def show_e2k_selection_screen(self, item_list):
        self.session.openWithCallback(
            self.on_e2k_items_selected,
            AzmanSelectListScreen,
            f"Wybierz {self.current_config_e2k['type']} do instalacji",
            item_list
        )

    def on_e2k_items_selected(self, selected_paths):
        if not selected_paths:
            self.cleanup_e2k()
            return

        target_dir = self.current_config_e2k['target_dir']
        
        if not os.path.isdir(target_dir):
            try:
                os.makedirs(target_dir)
            except OSError as e:
                self.session.open(MessageBox, f"Błąd tworzenia katalogu docelowego:\n{target_dir}\n{e}", MessageBox.TYPE_ERROR)
                self.cleanup_e2k()
                return

        installed_count, failed_count, installed_names = 0, 0, []
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
        
        self.cleanup_e2k()
        
        if installed_count > 0:
            self.changes_made_e2k = True
        
        message = f"Zainstalowano: {installed_count}\nBłędy: {failed_count}"
        if installed_names:
            message += "\n\nZainstalowane pozycje:\n" + "\n".join(f"- {name}" for name in installed_names)
            
        self.session.openWithCallback(self._ask_for_restart_e2k, MessageBox, message, type=MessageBox.TYPE_INFO, timeout=10)


# --- POZOSTAŁE KLASY EKRANÓW (bez zmian) ---

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
        self.session, self.item_list, self.selected_items = session, item_list, []
        self["title"] = StaticText(title)
        self["key_red"] = StaticText("Anuluj")
        self["key_green"] = StaticText("Zainstaluj zaznaczone")
        self["key_yellow"] = StaticText("Zaznacz/Odznacz wszystko")
        self["list"] = MenuList([])
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions"], {
            "ok": self.toggle_selection, "cancel": self.cancel, "red": self.cancel, "back": self.cancel,
            "green": self.save, "yellow": self.toggle_all,
            "up": self["list"].up, "down": self["list"].down
        }, -1)
        self.onLayoutFinish.append(self.build_list)

    def build_list(self):
        self["list"].setList([(f"[{'x' if item[0] in self.selected_items else ' '}] {item[1]}", item[0]) for item in self.item_list])

    def toggle_selection(self):
        current = self["list"].getCurrent()
        if not current:
            return
        path_value = current[1]
        if path_value in self.selected_items:
            self.selected_items.remove(path_value)
        else:
            self.selected_items.append(path_value)
        self.build_list()

    def toggle_all(self):
        all_paths = [i[0] for i in self.item_list]
        if len(self.selected_items) == len(all_paths):
            self.selected_items = []
        else:
            self.selected_items = all_paths
        self.build_list()

    def save(self):
        if not self.selected_items:
            self.session.open(MessageBox, "Nie zaznaczono żadnych elementów.", type=MessageBox.TYPE_INFO, timeout=5)
            return
        self.close(self.selected_items)

    def cancel(self):
        self.close([])

class BouquetSourceSelectionScreen(Screen):
    skin = """
        <screen name="BouquetSourceSelectionScreen" title="Wybierz źródło bukietów" position="center,center" size="1012,632">
            <widget name="title" position="center,5" size="987,70" font="Regular;31" halign="center" valign="top" />
            <widget name="info_label" position="13,76" size="987,442" font="Regular;28" halign="center" valign="center" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/AzmanPanel/red.png" position="25,557" size="37,51" alphatest="blend" />
            <widget source="key_red" render="Label" position="70,557" size="180,51" zPosition="3" font="Regular; 28" transparent="1" />
            <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/AzmanPanel/green.png" position="265,557" size="37,51" alphatest="blend" />
            <widget source="key_green" render="Label" position="310,557" size="290,51" zPosition="3" font="Regular; 28" transparent="1" />
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
        self["key_red"] = StaticText("Anuluj")
        self["key_green"] = StaticText("IPTV PL")
        self["key_yellow"] = StaticText("FAST Worldwide")
        self["key_blue"] = StaticText("iptv.org m3u PL")
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "cancel": lambda: self.close(None), "red": lambda: self.close(None), "back": lambda: self.close(None),
            "green": lambda: self.close('standard'), "yellow": lambda: self.close('fast'),
            "blue": lambda: self.close('iptv_org_pl')
        }, -1)

class DownloadProgressScreen(Screen):
    skin = """
        <screen position="center,center" size="800,150" title="Pobieranie...">
            <widget name="title" position="10,10" size="780,50" font="Regular;24" halign="center" />
            <widget name="progress" position="10,70" size="780,20" />
            <widget name="progresstext" position="10,100" size="780,40" font="Regular;20" halign="center" />
        </screen>
    """
    def __init__(self, session, title=""):
        Screen.__init__(self, session)
        self["title"] = Label(title)
        self["progress"] = ProgressBar()
        self["progresstext"] = Label("0%")

    def setProgress(self, current, total):
        if total > 0:
            percent = int(current * 100 / total)
            self["progress"].setValue(percent)
            self["progresstext"].setText(f"{percent}%")

class PiconManagementScreen(Screen):
     def __init__(self, session):
        Screen.__init__(self, session)
        self.session.open(MessageBox, "Zarządzanie piconami nie jest jeszcze zaimplementowane.", type=MessageBox.TYPE_INFO, timeout=5)
        self.close()