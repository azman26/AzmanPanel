from Components.config import config, ConfigSubsection, ConfigText, configfile

PLUGIN_VERSION = "1.5.5"

# --- Azman OPKG Feed ---
FEED_CONF_URL = "https://raw.githubusercontent.com/azman26/azman-enigma2-repo/main/azman-feed.conf"
FEED_CONF_TARGET_PATH = "/etc/opkg/azman-feed.conf"
FEED_PACKAGES_BASE_URL = "https://azman26.github.io/azman-enigma2-repo"

# --- Picons ---
PICONS_BASE_URL = "https://www.topolowa4.pl/ENIGMA2/PICONY/"
DEFAULT_PICON_TARGET_DIR = "/media/hdd/picon"
PICON_RECOMMENDED_DIRS = [
    ("/media/hdd/picon", "Dysk twardy HDD (/media/hdd/picon)"),
    ("/media/usb/picon", "Pamięć USB (/media/usb/picon)")
]

# --- EPG sources ---
SOURCES_XML_URL = "https://raw.githubusercontent.com/azman26/EPGazman/main/polandAzman.sources.xml"
SOURCES_XML_TARGET_DIR = "/etc/epgimport"
SOURCES_XML_FILENAME = "polandAzman.sources.xml"

# --- ArchivCZSK ---
ARCHIVCZSK_INSTALL_CMD = "curl -s --insecure https://raw.githubusercontent.com/archivczsk/archivczsk/main/build/archivczsk_installer.sh | sh"

# --- Bukiety IPTV PL ---
IPTV_SETTINGS_LIST_URL = "https://github.com/azman26/azmanIPTVsettings"
IPTV_SETTINGS_BASE_URL = "https://raw.githubusercontent.com/azman26/azmanIPTVsettings/main/"

# --- Bukiety FAST ---
FAST_SETTINGS_LIST_URL = "https://github.com/azman26/azmanFASTsettings"
FAST_SETTINGS_BASE_URL = "https://raw.githubusercontent.com/azman26/azmanFASTsettings/main/"