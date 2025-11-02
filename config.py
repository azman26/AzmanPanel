# /usr/lib/enigma2/python/Plugins/Extensions/AzmanPanel/config.py

from Components.config import config, ConfigSubsection, ConfigText, configfile
from . import constants

# Inicjalizacja sekcji konfiguracyjnej dla pluginu
config.plugins.AzmanPanel = ConfigSubsection()

# Definicja opcji - przechowuje ostatnio wybraną ścieżkę do picon
config.plugins.AzmanPanel.picon_path = ConfigText(default=constants.DEFAULT_PICON_TARGET_DIR)

def save_config():
    """Funkcja pomocnicza do zapisu konfiguracji"""
    configfile.save()