# /usr/lib/enigma2/python/Plugins/Extensions/AzmanPanel/constants.py

# --- STAŁE ---

# Wersja pluginu
PLUGIN_VERSION = "1.5.0 (Refactored)"

# Bukiety azmanIPTV
GITHUB_BOUQUET_ZIP_URL = "https://github.com/azman26/azmanIPTVsettings/archive/refs/heads/main.zip"
GITHUB_BOUQUET_REPO_NAME = "azmanIPTVsettings-main"
BOUQUET_TARGET_DIR = "/etc/enigma2"
BOUQUET_FILE_EXTENSIONS = ('.tv', '.userbouquet', '.radio')

# Bukiety azmanFAST
GITHUB_FAST_BOUQUET_ZIP_URL = "https://github.com/azman26/azmanFASTsettings/archive/refs/heads/main.zip"
GITHUB_FAST_BOUQUET_REPO_NAME = "azmanFASTsettings-main"

# Źródła EPG
SOURCES_XML_URL = "https://raw.githubusercontent.com/azman26/EPGazman/main/polandAzman.sources.xml"
SOURCES_XML_TARGET_DIR = "/etc/epgimport"
SOURCES_XML_FILENAME = "polandAzman.sources.xml"

# Picony
PICONS_BASE_URL = "https://www.topolowa4.pl/Picony/"
DEFAULT_PICON_TARGET_DIR = "/media/hdd/picon"
PICON_RECOMMENDED_DIRS = [("/media/hdd/picon", "HDD (/media/hdd/picon)"), ("/media/usb/picon", "USB (/media/usb/picon)")]

# Dodatki E2Kodi
E2KODI_BASE_DIR = "/etc/E2Kodi"

# Skiny E2Kodi
GITHUB_E2K_SKINS_REPO_URL = "https://github.com/azman26/enigma2-E2K-skins/archive/refs/heads/main.zip"
E2K_SKINS_REPO_NAME = "enigma2-E2K-skins-main"
E2K_SKINS_TARGET_DIR = "/etc/E2Kodi/userSkins"
E2K_SKIN_FOLDERS_TO_INSTALL = ["azman-E2K-MetrixHD-skins", "jk36-E2K-skins-all"]

# Pluginy E2Kodi
GITHUB_E2K_PLUGINS_ZIP_URL = "https://github.com/azman26/enigma2-E2K-plugins/archive/refs/heads/main.zip"
E2K_PLUGINS_REPO_NAME = "enigma2-E2K-plugins-main"
E2K_PLUGINS_TARGET_DIR = "/usr/lib/enigma2/python/Plugins/Extensions/E2Kodi/site-packages/emukodi/Plugins"

# Bukiet iptv-org
IPTV_ORG_PL_M3U_URL = "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/pl.m3u"
IPTV_ORG_PL_BOUQUET_FILENAME = "userbouquet.iptvorg_pl.tv"
IPTV_ORG_PL_BOUQUET_NAME = "iptv.org m3u PL"