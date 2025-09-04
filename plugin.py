# /usr/lib/enigma2/python/Plugins/Extensions/AzmanPanel/plugin.py

from Plugins.Plugin import PluginDescriptor

# Importujemy główny ekran z naszego modułu 'screens'
from .screens import AzmanPanelMainScreen

def main(session, **kwargs):
    """Główna funkcja wywoływana przy starcie pluginu."""
    session.open(AzmanPanelMainScreen)

def Plugins(**kwargs):
    """Rejestruje plugin w systemie Enigma2."""
    return [PluginDescriptor(
        name="Azman Panel", 
        description="Pobieranie bukietów IPTV, Picon, dodatków E2K oraz EPG sources.", 
        icon="icon.png", # Upewnij się, że ten plik istnieje w katalogu pluginu
        where=[PluginDescriptor.WHERE_PLUGINMENU], 
        fnc=main
    )]