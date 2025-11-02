import os
import urllib.parse
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.Sources.StaticText import StaticText
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.Standby import TryQuitMainloop
from Tools.LoadPixmap import LoadPixmap
from skin import loadSkin
from enigma import eTimer

from . import constants, utils
from .workers import PiconZipListWorker, PiconInstallationWorker, SourcesXmlDownloadWorker, IptvBouquetListWorker, IptvBouquetInstallWorker
from .ui_components import AzmanFeedScreen, PiconPathSelectionScreen, DownloadProgressScreen, AzmanSelectListScreen, OpkgCommandScreen, YtRunnerScreen
from .config import config, save_config

PLUGIN_PATH = os.path.dirname(os.path.realpath(__file__))
loadSkin(f"{PLUGIN_PATH}/skin.xml")

class AzmanPanelMainScreen(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self.current_worker = None
        self.GRID_ROWS, self.GRID_COLS = 3, 5
        self.menu_items = []
        self.markerPixmap = LoadPixmap(f"{PLUGIN_PATH}/icons/marker.png")
        self.selected_pos = (0, 0)
        self.params_for_screen_after_install = None
        self["title"] = Label("Azman Panel")
        self["version_info"] = Label(constants.PLUGIN_VERSION)
        self["description"] = Label("")
        self["selected_title"] = StaticText("")
        for r in range(self.GRID_ROWS):
            for c in range(self.GRID_COLS):
                self[f"logo_{r}x{c}"], self[f"marker_{r}x{c}"] = Pixmap(), Pixmap()
        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions"],
            {"ok": self.run_selected_item, "cancel": self.close, "up": lambda: self.move(-1, 0), "down": lambda: self.move(1, 0), "left": lambda: self.move(0, -1), "right": lambda: self.move(0, 1),}, -1)
        self.onLayoutFinish.append(self.prepare_menu)
        self.onClose.append(self.__onClose)

    def __onClose(self):
        if self.current_worker and self.current_worker.is_alive(): self.current_worker.cancel()

    def _load_icon(self, icon_name):
        path = f"{PLUGIN_PATH}/icons/{icon_name}"
        return LoadPixmap(path) if os.path.exists(path) else LoadPixmap(f"{PLUGIN_PATH}/icons/icon_placeholder.png")

    def prepare_menu(self):
        menu_definitions = [
            ("Azman OPKG Feed", self.open_azman_feed_manager, "icon_feed.png", "Menedżer pakietów IPK."),
            ("Bukiety IPTV PL", self.open_iptv_bouquet_manager, "icon_iptv_pl.png", "Pobierz bukiety polskich kanałów IPTV."),
            ("Bukiety FAST", self.open_fast_bouquet_manager, "icon_fast.png", "Pobierz bukiety kanałów FAST."),
            ("YT to m3u8", self.open_yttom3u8, "icon_yttom3u8.png", "Generuje i aktualizuje bukiet YT Channels m3u8."),
            ("Token Refrescher", self.start_token_refresh, "icon_token.png", "Uruchamia skrypt odświeżający tokeny."),
            ("Dodatki do E2K", self.open_e2k_addons_manager, "icon_e2k.png", "Pobierz dodatki dla E2Kodi."),
            ("Shelly Control", self.start_shelly_install, "icon_shelly.png", "Zainstaluj plugin Shelly Control Center."),
            ("Polskie źródła EPG", self.start_epg_download, "icon_epg.png", "Pobierz plik sources dla EPG-Import."),
            ("Picons", self.open_picon_manager, "icon_picons.png", "Pobierz picony 220x132 transparent."),
            ("Archiv CZSK", self.start_archivczsk_install, "icon_archivczsk.png", "Zainstaluj plugin ArchivCZSK."),
            ("AjPanel", self.open_ajpanel, "icon_ajpanel.png", "Zainstaluj plugin AjPanel. Ta funkcja jest w budowie."),
            ("M3UIPTV", self.open_m3uiptv, "icon_m3uiptv.png", "Pobieranie i konwertowanie list m3u do bukietu E2. Ta funkcja jest w budowie. "),
        ]
        self.menu_items = [{"text": t, "func": f, "pixmap": self._load_icon(i), "desc": d} for t, f, i, d in menu_definitions]
        self.GRID_ROWS = (len(self.menu_items) + self.GRID_COLS - 1) // self.GRID_COLS
        self.draw_page()

    def draw_page(self):
        for r in range(self.GRID_ROWS):
            for c in range(self.GRID_COLS):
                item_index = r * self.GRID_COLS + c
                logo_widget = self[f"logo_{r}x{c}"]
                if item_index < len(self.menu_items):
                    logo_widget.instance.setPixmap(self.menu_items[item_index]["pixmap"])
                    logo_widget.show()
                else:
                    logo_widget.hide()
        self.update_selection()

    def update_selection(self):
        for r in range(self.GRID_ROWS):
            for c in range(self.GRID_COLS):
                self[f"marker_{r}x{c}"].hide()
        sel_r, sel_c = self.selected_pos
        item_index = sel_r * self.GRID_COLS + sel_c
        if item_index < len(self.menu_items):
            marker_widget = self[f"marker_{sel_r}x{sel_c}"]
            marker_widget.instance.setPixmap(self.markerPixmap)
            marker_widget.show()
            selected_item = self.menu_items[item_index]
            self["selected_title"].setText(f" -  {selected_item['text']}")
            self["description"].setText(selected_item['desc'])
        else:
            self["selected_title"].setText("")
            self["description"].setText("")

    def move(self, d_row, d_col):
        new_r, new_c = self.selected_pos[0] + d_row, self.selected_pos[1] + d_col
        if new_c >= self.GRID_COLS: new_c = 0
        if new_c < 0: new_c = self.GRID_COLS - 1
        if new_r >= self.GRID_ROWS: new_r = 0
        if new_r < 0: new_r = self.GRID_ROWS - 1
        self.selected_pos = (new_r, new_c)
        self.update_selection()

    def run_selected_item(self):
        item_index = self.selected_pos[0] * self.GRID_COLS + self.selected_pos[1]
        if item_index < len(self.menu_items):
            try:
                self.menu_items[item_index]["func"]()
            except Exception as e:
                utils.log_error(e, f"run_selected_item: {self.menu_items[item_index]['text']}")
                self.session.open(MessageBox, f"Wystąpił błąd:\n{e}", type=MessageBox.TYPE_ERROR)

    def open_placeholder_screen(self):
        self.session.open(MessageBox, "Ta funkcja jest w budowie.", type=MessageBox.TYPE_INFO)

    def open_yttom3u8(self):
        self.session.open(YtRunnerScreen)

    def open_m3uiptv(self):
        self.session.open(MessageBox, "Pobieranie i konwertowanie list m3u do bukietu E2. Ta funkcja jest w budowie.", type=MessageBox.TYPE_INFO)

    def open_ajpanel(self):
        self.session.open(MessageBox, "Zainstaluj plugin AjPanel. Ta funkcja jest w budowie.", type=MessageBox.TYPE_INFO)

    # --- LOGIKA DLA AZMAN FEED ---
    def _open_package_manager(self, title, filter_keywords=None):
        if os.path.exists(constants.FEED_CONF_TARGET_PATH):
            self.session.open(AzmanFeedScreen, title=title, filter_keywords=filter_keywords)
        else:
            self.params_for_screen_after_install = {'title': title, 'filter_keywords': filter_keywords}
            message = "Repozytorium Azman Feed nie jest zainstalowane.\n\nCzy chcesz zainstalować je teraz?"
            self.session.openWithCallback(self._proceed_with_feed_install, MessageBox, message, MessageBox.TYPE_YESNO, default=True)

    def open_azman_feed_manager(self):
        self._open_package_manager(title="Azman Feed - Menedżer pakietów")

    def open_e2k_addons_manager(self):
        self._open_package_manager(title="Azman Feed - Dodatki do E2K", filter_keywords=["e2k", "e2kodi"])

    def _proceed_with_feed_install(self, confirmed):
        if not confirmed:
            self.session.open(MessageBox, "Instalacja anulowana.", type=MessageBox.TYPE_INFO)
            return
        command = (f"curl -s --insecure -o {constants.FEED_CONF_TARGET_PATH} {constants.FEED_CONF_URL} && opkg update")
        title = "Instalowanie Azman Feed"
        self.session.openWithCallback(self.on_feed_install_finished, OpkgCommandScreen, title=title, command=command)

    def on_feed_install_finished(self, *args):
        if os.path.exists(constants.FEED_CONF_TARGET_PATH):
            def open_target_screen(confirmed):
                if self.params_for_screen_after_install:
                    self.session.open(AzmanFeedScreen, **self.params_for_screen_after_install)
                    self.params_for_screen_after_install = None
            message = "Repozytorium Azman Feed zostało dodane!\n\nZostaniesz teraz przeniesiony do menedżera pakietów."
            self.session.openWithCallback(open_target_screen, MessageBox, message, type=MessageBox.TYPE_INFO, timeout=5)
        else:
            message = "Wystąpił błąd podczas instalacji feeda.\n\nSprawdź połączenie z internetem i spróbuj ponownie."
            self.session.open(MessageBox, message, type=MessageBox.TYPE_ERROR)
            
    # --- LOGIKA DLA PICON ---
    def open_picon_manager(self):
        saved_path = config.plugins.AzmanPanel.picon_path.value
        parent_dir = os.path.dirname(saved_path)
        if os.path.exists(parent_dir) and os.access(parent_dir, os.W_OK):
            self.on_picon_path_selected(saved_path)
        else:
            self.session.openWithCallback(self.on_picon_path_selected, PiconPathSelectionScreen)
            
    def on_picon_path_selected(self, target_dir):
        if not target_dir: return
        config.plugins.AzmanPanel.picon_path.value = target_dir
        save_config()
        self.picon_target_dir = target_dir
        self._open_picon_selection_screen()
        
    def _open_picon_selection_screen(self, *args):
        self.current_worker = PiconZipListWorker(callback_finished=self.on_picon_list_downloaded)
        self.current_worker.start()
        
    def on_picon_list_downloaded(self, error_message, picon_zip_filenames):
        self.current_worker = None
        if error_message or not picon_zip_filenames:
            msg = error_message or "Nie znaleziono plików *.zip na serwerze."
            self.session.open(MessageBox, msg, MessageBox.TYPE_ERROR)
            return
        item_list = [(filename, urllib.parse.unquote(filename)) for filename in picon_zip_filenames]
        def open_select_list_screen():
            self.session.open(AzmanSelectListScreen, "Wybierz paczki picon", item_list, on_save_callback=self.on_picons_selected)
        # Użycie eTimer tutaj jest poprawne, bo nie ma konfliktu z zamykaniem okien
        self.open_timer = eTimer()
        try:
            self.open_timer_conn = self.open_timer.timeout.connect(open_select_list_screen)
        except:
            self.open_timer.callback.append(open_select_list_screen)
        self.open_timer.start(1, True)

    def on_picons_selected(self, selected_zips):
        if not selected_zips: return
        self.progress_screen = self.session.open(DownloadProgressScreen, title="Instalowanie picon...")
        self.current_worker = PiconInstallationWorker(selected_zips=selected_zips, target_dir=self.picon_target_dir, callback_progress=self.progress_screen.setProgress, callback_finished=self.on_picon_installation_finished)
        self.progress_screen.parent_worker = self.current_worker
        self.current_worker.start()
        
    def on_picon_installation_finished(self, final_message):
        self.current_worker = None
        
        def after_messagebox_callback(result):
            if hasattr(self, 'progress_screen') and self.progress_screen:
                self.progress_screen.close()
            self._open_picon_selection_screen()

        self.session.openWithCallback(
            after_messagebox_callback,
            MessageBox, 
            f"Zakończono instalację picon.\n\n{final_message}", 
            type=MessageBox.TYPE_INFO
        )
    
    # --- LOGIKA DLA BUKIETÓW IPTV PL ---
    def open_iptv_bouquet_manager(self, *args):
        self.current_worker = IptvBouquetListWorker(constants.IPTV_SETTINGS_LIST_URL, callback_finished=self.on_iptv_bouquet_list_downloaded)
        self.current_worker.start()

    def on_iptv_bouquet_list_downloaded(self, error_message, bouquet_filenames):
        self.current_worker = None
        if error_message or not bouquet_filenames:
            msg = error_message or "Nie znaleziono bukietów na serwerze."
            self.session.open(MessageBox, msg, MessageBox.TYPE_ERROR)
            return
        item_list = []
        for filename in bouquet_filenames:
            display_name = filename.replace("userbouquet.", "").replace(".tv", "").replace("_", " ").title()
            item_list.append((filename, display_name))
        def open_select_list_screen():
            self.session.open(
                AzmanSelectListScreen, 
                "Wybierz bukiety IPTV PL do instalacji", 
                item_list,
                on_save_callback=self.on_iptv_bouquets_selected
            )
        self.open_timer = eTimer()
        try:
            self.open_timer_conn = self.open_timer.timeout.connect(open_select_list_screen)
        except:
            self.open_timer.callback.append(open_select_list_screen)
        self.open_timer.start(1, True)
    
    def on_iptv_bouquets_selected(self, selected_bouquets):
        if not selected_bouquets: return
        self.progress_screen = self.session.open(DownloadProgressScreen, title="Instalowanie bukietów...")
        self.current_worker = IptvBouquetInstallWorker(
            selected_bouquets=selected_bouquets,
            base_url=constants.IPTV_SETTINGS_BASE_URL,
            callback_progress=self.progress_screen.setProgress,
            callback_finished=self.on_iptv_bouquet_installation_finished
        )
        self.progress_screen.parent_worker = self.current_worker
        self.current_worker.start()

    def on_iptv_bouquet_installation_finished(self, final_message):
        self.current_worker = None
        
        def after_messagebox_callback(result):
            if hasattr(self, 'progress_screen') and self.progress_screen:
                self.progress_screen.close()
            self.open_iptv_bouquet_manager()
        
        self.session.openWithCallback(
            after_messagebox_callback,
            MessageBox, 
            final_message, 
            type=MessageBox.TYPE_INFO
        )

    # --- LOGIKA DLA BUKIETÓW FAST ---
    def open_fast_bouquet_manager(self, *args):
        self.current_worker = IptvBouquetListWorker(constants.FAST_SETTINGS_LIST_URL, callback_finished=self.on_fast_bouquet_list_downloaded)
        self.current_worker.start()
        
    def on_fast_bouquet_list_downloaded(self, error_message, bouquet_filenames):
        self.current_worker = None
        if error_message or not bouquet_filenames:
            msg = error_message or "Nie znaleziono bukietów FAST na serwerze."
            self.session.open(MessageBox, msg, MessageBox.TYPE_ERROR)
            return
        item_list = []
        for filename in bouquet_filenames:
            display_name = filename.replace("userbouquet.", "").replace(".tv", "").replace("_", " ").title()
            item_list.append((filename, display_name))
        def open_select_list_screen():
            self.session.open(
                AzmanSelectListScreen, 
                "Wybierz bukiety FAST do instalacji", 
                item_list,
                on_save_callback=self.on_fast_bouquets_selected
            )
        self.open_timer = eTimer()
        try:
            self.open_timer_conn = self.open_timer.timeout.connect(open_select_list_screen)
        except:
            self.open_timer.callback.append(open_select_list_screen)
        self.open_timer.start(1, True)
        
    def on_fast_bouquets_selected(self, selected_bouquets):
        if not selected_bouquets: return
        self.progress_screen = self.session.open(DownloadProgressScreen, title="Instalowanie bukietów FAST...")
        self.current_worker = IptvBouquetInstallWorker(
            selected_bouquets=selected_bouquets,
            base_url=constants.FAST_SETTINGS_BASE_URL,
            callback_progress=self.progress_screen.setProgress,
            callback_finished=self.on_fast_bouquet_installation_finished
        )
        self.progress_screen.parent_worker = self.current_worker
        self.current_worker.start()
        
    def on_fast_bouquet_installation_finished(self, final_message):
        self.current_worker = None
            
        def after_messagebox_callback(result):
            if hasattr(self, 'progress_screen') and self.progress_screen:
                self.progress_screen.close()
            self.open_fast_bouquet_manager()

        self.session.openWithCallback(
            after_messagebox_callback,
            MessageBox, 
            final_message, 
            type=MessageBox.TYPE_INFO
        )

    # --- LOGIKA DLA EPG SOURCES ---
    def start_epg_download(self):
        message = f"Czy chcesz pobrać i nadpisać plik:\n'{constants.SOURCES_XML_FILENAME}'\n\nw lokalizacji:\n'{constants.SOURCES_XML_TARGET_DIR}'?"
        self.session.openWithCallback(self._confirm_epg_download, MessageBox, message, MessageBox.TYPE_YESNO, default=True)
        
    def _confirm_epg_download(self, confirmed):
        if not confirmed:
            self.session.open(MessageBox, "Operacja anulowana.", type=MessageBox.TYPE_INFO)
            return
        self.current_worker = SourcesXmlDownloadWorker(callback_finished=self._on_epg_download_finished)
        self.current_worker.start()
        
    def _on_epg_download_finished(self, error_message, final_message):
        self.current_worker = None
        message = final_message or error_message
        msg_type = MessageBox.TYPE_ERROR if error_message else MessageBox.TYPE_INFO
        self.session.open(MessageBox, message, type=msg_type)
        
    # --- LOGIKA DLA ARCHIVCZSK ---
    def start_archivczsk_install(self):
        message = ("Czy na pewno chcesz pobrać i zainstalować plugin ArchivCZSK?\n\n"
                   "Zostanie wykonana zewnętrzna komenda, która pobierze i uruchomi skrypt instalacyjny.\n\n"
                   "UWAGA: Po zakończeniu instalacji nastąpi automatyczny restart GUI!")
        self.session.openWithCallback(self._confirm_archivczsk_install, MessageBox, message, MessageBox.TYPE_YESNO, default=False)
    def _confirm_archivczsk_install(self, confirmed):
        if not confirmed:
            self.session.open(MessageBox, "Instalacja anulowana.", type=MessageBox.TYPE_INFO)
            return
        title = "Instalowanie ArchivCZSK"
        command = constants.ARCHIVCZSK_INSTALL_CMD
        self.session.openWithCallback(self.on_archivczsk_install_finished, OpkgCommandScreen, title=title, command=command)
    def on_archivczsk_install_finished(self):
        restart_callback = lambda confirmed: self.session.open(TryQuitMainloop, 3)
        self.session.openWithCallback(restart_callback, MessageBox, "Instalacja ArchivCZSK została zakończona.\n\nNastąpi teraz restart interfejsu graficznego (GUI).", type=MessageBox.TYPE_INFO, title="Instalacja zakończona")

    # --- LOGIKA DLA Shelly Control Center ---
    def start_shelly_install(self):
        message = ("Czy na pewno chcesz pobrać i zainstalować plugin Shelly Control Center?\n\n"
                   "Zostanie wykonana zewnętrzna komenda, która pobierze i uruchomi skrypt instalacyjny.\n\n"
                   "UWAGA: Po zakończeniu instalacji nastąpi automatyczny restart GUI!")
        self.session.openWithCallback(self._confirm_shelly_install, MessageBox, message, MessageBox.TYPE_YESNO, default=False)

    def _confirm_shelly_install(self, confirmed):
        if not confirmed:
            self.session.open(MessageBox, "Instalacja anulowana.", type=MessageBox.TYPE_INFO)
            return
        title = "Instalowanie Shelly Control Center"
        command = constants.SHELLY_INSTALL_CMD
        self.session.openWithCallback(self.on_shelly_install_finished, OpkgCommandScreen, title=title, command=command)

    def on_shelly_install_finished(self):
        restart_callback = lambda confirmed: self.session.open(TryQuitMainloop, 3)
        self.session.openWithCallback(restart_callback, MessageBox, "Instalacja Shelly Control Center została zakończona.\n\nNastąpi teraz restart interfejsu graficznego (GUI).", type=MessageBox.TYPE_INFO, title="Instalacja zakończona")

    # --- LOGIKA DLA Token Refrescher ---
    def start_token_refresh(self):
        message = ("Czy chcesz uruchomić zewnętrzny skrypt odświeżający tokeny?\n\n"
                   "Zalecany jest restart GUI po zakończeniu operacji.")
        self.session.openWithCallback(self._confirm_token_refresh, MessageBox, message, MessageBox.TYPE_YESNO, default=False)

    def _confirm_token_refresh(self, confirmed):
        if not confirmed:
            self.session.open(MessageBox, "Operacja anulowana.", type=MessageBox.TYPE_INFO)
            return
        title = "Odświeżanie tokenów"
        command = constants.TOKEN_REFRESH_CMD
        self.session.openWithCallback(self.on_token_refresh_finished, OpkgCommandScreen, title=title, command=command)

    def on_token_refresh_finished(self):
        message = "Skrypt odświeżający tokeny zakończył pracę.\n\nZalecany jest restart interfejsu graficznego (GUI)."
        self.session.open(MessageBox, message, type=MessageBox.TYPE_INFO, title="Zakończono")