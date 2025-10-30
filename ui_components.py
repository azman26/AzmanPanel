import os
# Usunięto 'import urllib.request', bo nie jest już potrzebny
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Components.Sources.StaticText import StaticText
from Components.ProgressBar import ProgressBar
from Components.ScrollLabel import ScrollLabel
from enigma import eConsoleAppContainer, eTimer, eDVBDB # <-- DODANO eDVBDB
from . import constants
from .workers import PackageListWorker

# --- Ekrany dla Azman OPKG Feed ---

class OpkgCommandScreen(Screen):
    def __init__(self, session, command, title="", callback=None):
        Screen.__init__(self, session)
        self.command = command
        self.callback = callback
        self.setTitle(title)
        self["console"] = Label()
        self["actions"] = ActionMap(["OkCancelActions"], {"ok": self.close, "cancel": self.close}, -1)
        self.console_app = eConsoleAppContainer()
        self.console_app.dataAvail.append(self.on_console_data)
        self.console_app.appClosed.append(self.on_command_finished)
        self.onShown.append(self.run_command)

    def run_command(self):
        self["console"].setText(f"> {self.command}\n\n")
        self.console_app.execute(self.command)

    def on_console_data(self, data):
        if data: self["console"].setText(self["console"].getText() + data.decode("utf-8", "ignore"))

    def on_command_finished(self, result):
        self["console"].setText(self["console"].getText() + "\n\nPolecenie zakończone. Zamykanie okna...")
        self.timer = eTimer()
        try:
            self.timer_conn = self.timer.timeout.connect(self.finish_and_close)
        except:
            self.timer.callback.append(self.finish_and_close)
        self.timer.start(2000, True)

    def finish_and_close(self):
        self.timer.stop()
        if self.callback:
            self.callback()
        self.close()

class AzmanFeedScreen(Screen):
    def __init__(self, session, title="Azman Feed - Menedżer pakietów", filter_keywords=None):
        Screen.__init__(self, session)
        self.filter_keywords = filter_keywords
        self.setTitle(title)
        self.packages = []
        self.worker = None
        self["title"] = StaticText(title)
        self["description"] = Label("Wczytywanie listy pakietów...")
        self["key_green"] = StaticText("Zainstaluj")
        self["key_red"] = StaticText("Odinstaluj")
        self["key_yellow"] = StaticText("Odśwież")
        self["list"] = MenuList([])
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {"ok": self.handle_action, "cancel": self.close, "green": self.install_package, "red": self.remove_package, "yellow": self.refresh_list}, -1)
        self["list"].onSelectionChanged.append(self.on_selection_changed)
        self.onLayoutFinish.append(self.refresh_list)
        self.onClose.append(self.__onClose)

    def __onClose(self):
        if self.worker and self.worker.is_alive(): self.worker.cancel()

    def refresh_list(self):
        self["description"].setText("Aktualizowanie listy pakietów...")
        self["list"].setList([])
        self.worker = PackageListWorker(callback_finished=self._on_package_list_ready)
        self.worker.start()

    def _on_package_list_ready(self, error_message, packages):
        self.worker = None
        if error_message:
            self.session.open(MessageBox, error_message, type=MessageBox.TYPE_ERROR)
            self["description"].setText(error_message)
            return
        if self.filter_keywords:
            filtered_packages = []
            for pkg in packages:
                pkg_name_lower = pkg.get('name', '').lower()
                if any(keyword.lower() in pkg_name_lower for keyword in self.filter_keywords):
                    filtered_packages.append(pkg)
            self.packages = sorted(filtered_packages, key=lambda p: p['name'])
        else:
            self.packages = sorted(packages, key=lambda p: p['name'])
        if not self.packages:
            msg = "Nie znaleziono żadnych pasujących pakietów." if self.filter_keywords else "Brak dostępnych pakietów."
            self["description"].setText(msg)
            self["list"].setList([])
        else:
            menu_list = [(f"{p['name']} ({p['version']}) - [{p['status']}]", p) for p in self.packages]
            self["list"].setList(menu_list)
        self.on_selection_changed()

    def on_selection_changed(self):
        current = self["list"].getCurrent()
        if current:
            self["description"].setText(current[1].get('description', 'Brak opisu.'))
        else:
            msg = "Nie znaleziono żadnych pasujących pakietów." if self.filter_keywords else "Brak dostępnych pakietów."
            self["description"].setText(msg)

    def handle_action(self):
        current = self["list"].getCurrent()
        if not current: return
        self.install_package() if current[1]['status'] != 'Zainstalowany' else self.remove_package()

    def install_package(self): self._run_opkg_command("install")
    def remove_package(self): self._run_opkg_command("remove")

    def _run_opkg_command(self, action):
        current = self["list"].getCurrent()
        if not current: return
        pkg = current[1]
        if action == "install" and pkg['status'] == 'Zainstalowany':
            self.session.open(MessageBox, "Ten pakiet jest już zainstalowany.", type=MessageBox.TYPE_INFO)
            return
        if action == "remove" and pkg['status'] != 'Zainstalowany':
            self.session.open(MessageBox, "Ten pakiet nie jest zainstalowany.", type=MessageBox.TYPE_INFO)
            return
        command = f"opkg {action} {pkg['name']}"
        title = f"{'Instalowanie' if action == 'install' else 'Odinstalowywanie'}: {pkg['name']}"
        self.session.openWithCallback(self.refresh_list, OpkgCommandScreen, command=command, title=title)

class DownloadProgressScreen(Screen):
    def __init__(self, session, title="", parent_worker=None):
        Screen.__init__(self, session)
        self.parent_worker = parent_worker
        self["title"] = StaticText(title)
        self["progress"] = ProgressBar()
        self["progresstext"] = Label("0%")
        self["actions"] = ActionMap(["OkCancelActions"], {"cancel": self.keyCancel}, -1)
    def keyCancel(self):
        if self.parent_worker and self.parent_worker.is_alive(): self.parent_worker.cancel()
        self.close()
    def setProgress(self, current, total, custom_title=""):
        if custom_title: self["title"].setText(custom_title)
        if total > 0:
            percent = int(current * 100 / total)
            self["progress"].setValue(percent)
            self["progresstext"].setText(f"{percent}%")

class PiconPathSelectionScreen(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        self.setTitle("Wybierz ścieżkę instalacji picon")
        self["title"] = StaticText("Wybierz ścieżkę instalacji picon")
        self["key_green"] = StaticText("Wybierz")
        self["list"] = MenuList([])
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {"cancel": self.keyCancel, "ok": self.keyGreen, "green": self.keyGreen}, -1)
        self.onLayoutFinish.append(self.build_target_list)
    def build_target_list(self):
        choices = []
        for path, display_name in constants.PICON_RECOMMENDED_DIRS:
            parent_dir = os.path.dirname(path)
            if os.path.exists(parent_dir) and os.access(parent_dir, os.W_OK):
                status = " (zalecane)"
                if not os.path.exists(path): status += " - zostanie utworzony"
                choices.append((f"{display_name}{status}", path))
        if not choices:
            self.session.openWithCallback(self.keyCancel, MessageBox, "Nie znaleziono żadnej zapisywalnej lokalizacji (HDD/USB).", MessageBox.TYPE_ERROR)
        else:
            self["list"].setList(choices)
    def keyGreen(self):
        selection = self["list"].getCurrent()
        if selection: self.close(selection[1])
    def keyCancel(self): self.close(None)

class AzmanSelectListScreen(Screen):
    def __init__(self, session, title, item_list, on_save_callback=None):
        Screen.__init__(self, session)
        self.setTitle(title)
        self.item_list = item_list
        self.selected_items = []
        self.on_save_callback = on_save_callback
        self["title"] = StaticText(title)
        self["key_green"] = StaticText("Zainstaluj zaznaczone")
        self["key_yellow"] = StaticText("Zaznacz/Odznacz wszystko")
        self["list"] = MenuList([])
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {"cancel": self.keyCancel, "ok": self.toggle_selection, "green": self.save, "yellow": self.toggle_all}, -1)
        self.onLayoutFinish.append(self.build_list)
    def build_list(self):
        self["list"].setList([(f"[{'x' if item[0] in self.selected_items else ' '}] {item[1]}", item[0]) for item in self.item_list])
    def toggle_selection(self):
        current = self["list"].getCurrent()
        if not current: return
        path_value = current[1]
        if path_value in self.selected_items: self.selected_items.remove(path_value)
        else: self.selected_items.append(path_value)
        self.build_list()
    def toggle_all(self):
        all_paths = [i[0] for i in self.item_list]
        self.selected_items = [] if len(self.selected_items) == len(all_paths) else all_paths
        self.build_list()
    def save(self):
        if self.on_save_callback:
            self.on_save_callback(self.selected_items)
            self.close() 
        else:
            self.close(self.selected_items)
    def keyCancel(self):
        self.close([])

# Ścieżka do skryptu, który będziemy uruchamiać
YT_RUNNER_SCRIPT_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "scripts", "yt_aktualizator.py")
CRON_FILE = "/etc/cron/crontabs/root"

class YtRunnerScreen(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self.setTitle("YT to m3u8 Generator")
        
        self["console"] = ScrollLabel("Witaj!\n\nNaciśnij ZIELONY, aby uruchomić skrypt i wygenerować bukiet.\nNaciśnij ŻÓŁTY, aby dodać/usunąć automatyczne odświeżanie.")
        self["key_green"] = StaticText("Uruchom")
        self["key_yellow"] = StaticText("Dodaj/Usuń z CRON")
        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions", "DirectionActions"],
            {
                "cancel": self.close,
                "green": self.run_script,
                "yellow": self.toggle_cron_job,
                "up": self["console"].pageUp,
                "down": self["console"].pageDown
            }, -1
        )
        self.console_app = eConsoleAppContainer()
        self.console_app.dataAvail.append(self.on_console_data)
        self.console_app.appClosed.append(self.on_command_finished)

    def run_script(self):
        if not (os.path.exists(YT_RUNNER_SCRIPT_PATH) and os.access(YT_RUNNER_SCRIPT_PATH, os.X_OK)):
            try:
                os.chmod(YT_RUNNER_SCRIPT_PATH, 0o755)
            except OSError as e:
                self.session.open(MessageBox, f"Błąd uprawnień do skryptu:\n{e}\n\nNadaj mu ręcznie uprawnienia 755.", type=MessageBox.TYPE_ERROR)
                return

        command = f"python3 {YT_RUNNER_SCRIPT_PATH}"
        self["console"].setText(f"> Uruchamiam: {command}\n\n")
        self.console_app.execute(command)

    def on_console_data(self, data):
        if data:
            current_text = self["console"].getText()
            new_text = current_text + data.decode("utf-8", "ignore")
            self["console"].setText(new_text)

    def on_command_finished(self, result):
        self.appendText("\n--- SKRYPT ZAKOŃCZYŁ PRACĘ ---\n")
        try:
            # --- NOWA, LEPSZA METODA PRZEŁADOWANIA ---
            self.appendText("-> Przeładowuję listę kanałów i bukietów...\n")
            eDVBDB.getInstance().reloadBouquets()
            eDVBDB.getInstance().reloadServicelist()
            self.appendText("-> Przeładowano pomyślnie.\n\nMożesz teraz zamknąć to okno.")
            message = "Skrypt zakończył pracę, a lista kanałów została odświeżona."
        except Exception as e:
            # Ta sekcja błędu teraz praktycznie nie powinna wystąpić
            error_reason = str(e)
            self.appendText(f"-> Błąd krytyczny podczas przeładowania: {error_reason}\n")
            message = f"Skrypt zakończył pracę, ale wystąpił błąd podczas odświeżania listy kanałów.\n\nPowód: {error_reason}\n\nZrestartuj GUI ręcznie, aby zobaczyć zmiany."
            
        self.session.open(MessageBox, message, type=MessageBox.TYPE_INFO)

    def appendText(self, text):
        current_text = self["console"].getText()
        self["console"].setText(current_text + text)
        
    def get_cron_command(self):
        return f"30 4 * * * {YT_RUNNER_SCRIPT_PATH}"

    def toggle_cron_job(self):
        cron_command = self.get_cron_command()
        if not os.path.exists(CRON_FILE):
            with open(CRON_FILE, 'w') as f:
                f.write('')
        with open(CRON_FILE, 'r') as f:
            lines = f.readlines()
        job_exists = any(cron_command in line for line in lines)
        if job_exists:
            new_lines = [line for line in lines if cron_command not in line]
            message = "Zadanie CRON zostało pomyślnie usunięte."
        else:
            new_lines = lines
            new_lines.append(f"{cron_command}\n")
            message = "Zadanie CRON zostało dodane.\n\nBukiet będzie automatycznie odświeżany codziennie o 04:30."
        try:
            with open(CRON_FILE, 'w') as f:
                f.writelines(new_lines)
            os.system("/etc/init.d/crond.sh restart")
            self.session.open(MessageBox, message, type=MessageBox.TYPE_INFO)
        except Exception as e:
            self.session.open(MessageBox, f"Wystąpił błąd podczas modyfikacji pliku CRON:\n{e}", type=MessageBox.TYPE_ERROR)