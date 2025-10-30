# /usr/lib/enigma2/python/Plugins/Extensions/AzmanPanel/plugin.py

from Plugins.Plugin import PluginDescriptor
from .screens import AzmanPanelMainScreen

def main(session, **kwargs):
    session.open(AzmanPanelMainScreen)

def Plugins(**kwargs):
    return [PluginDescriptor(
        name="Azman Panel", 
        description="Panel narzędziowy od Azman.", 
        icon="icon.png",
        where=[PluginDescriptor.WHERE_PLUGINMENU], 
        fnc=main
    )]