#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import yt_dlp
import json
import requests
from urllib.parse import quote
import os
import sys

# Przekierowujemy stderr do dev/null, aby ukryć błędy yt-dlp w konsoli
sys.stderr = open(os.devnull, 'w')

def get_m3u8_for_video(video_url: str) -> str or None:
    print("    -> Pozyskuję link M3U8...", end='', flush=True)
    ydl_opts = {'quiet': True, 'no_warnings': True, 'get_url': True, 'format': 'best[protocol=m3u8_native]'}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            m3u8 = info.get('url')
            if m3u8:
                print(" [OK]")
                return m3u8
            else:
                print(" [BŁĄD]")
                return None
    except Exception:
        print(" [BŁĄD]")
        return None

# --- PRZYWRÓCONA FUNKCJA REKURSYWNA ---
def _recursive_find_live_videos(data_structure):
    live_videos = []
    if isinstance(data_structure, dict):
        if data_structure.get('is_live') and data_structure.get('webpage_url'):
            live_videos.append(data_structure)
        for value in data_structure.values():
            live_videos.extend(_recursive_find_live_videos(value))
    elif isinstance(data_structure, list):
        for item in data_structure:
            live_videos.extend(_recursive_find_live_videos(item))
    return live_videos

def find_active_streams_on_channel(channel_url: str) -> list:
    live_section_url = channel_url.rstrip('/') + '/live'
    print(f"  -> Skanuję...", end='', flush=True)
    ydl_opts = {'quiet': True, 'no_warnings': True}
    active_streams = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            live_info = ydl.extract_info(live_section_url, download=False)
            
            # --- ZMIANA: UŻYWAMY SKUTECZNIEJSZEJ METODY REKURSYWNEJ ---
            found_videos = _recursive_find_live_videos(live_info)
            unique_videos = list({video.get('webpage_url'): video for video in found_videos}.values())

            if not unique_videos:
                print(" [BRAK LIVE]")
                return []
            
            print("") # Nowa linia dla czytelności
            for video_entry in unique_videos:
                video_title = video_entry.get('title', 'Brak tytułu')
                video_url = video_entry.get('webpage_url')
                print(f"  -> Znaleziono transmisję: '{video_title}'")
                m3u8_link = get_m3u8_for_video(video_url)
                if m3u8_link:
                    active_streams.append({'title': video_title, 'm3u8_url': m3u8_link})
    except yt_dlp.utils.DownloadError:
        print(" [BRAK LIVE]")
    except Exception:
        print(" [BŁĄD KRYTYCZNY]")
    return active_streams

def get_channels_from_github(url: str):
    print(f"Pobieram plik konfiguracyjny...", end='', flush=True)
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = json.loads(response.text)
        print(" [OK]")
        return data
    except (requests.exceptions.RequestException, json.JSONDecodeError):
        print(" [BŁĄD]")
        return None

def create_bouquet_from_channels(config_data: dict, output_filepath: str):
    print("\nRozpoczynam tworzenie bukietu...")
    if not config_data:
        print("Brak danych konfiguracyjnych. Zamykam skrypt.")
        return 0
        
    channels_to_process = []
    for category in config_data.values():
        for channel in category:
            if 'name' in channel and 'url' in channel:
                channels_to_process.append((channel['name'], channel['url']))

    successful_channels_count = 0
    with open(output_filepath, 'w', encoding='utf-8') as f_out:
        f_out.write('#NAME Youtub Channels (YTtoM3U8 azman)\n')
        
        for name_prefix, url in channels_to_process:
            print(f"\n--- Przetwarzanie kanału: {name_prefix} ---")
            found_streams = find_active_streams_on_channel(url)
            
            for stream in found_streams:
                full_name = f"{name_prefix} - {stream['title']}"
                cleaned_name = full_name.replace(':', ' -')
                m3u8_link = stream['m3u8_url']
                encoded_m3u8 = quote(m3u8_link, safe='/')
                
                service_line = f"#SERVICE 4097:0:1:0:0:0:0:0:0:0:{encoded_m3u8}:{cleaned_name}\n"
                description_line = f"#DESCRIPTION {cleaned_name}\n"
                
                f_out.write(service_line)
                f_out.write(description_line)
                successful_channels_count += 1
                print("    -> Dodano do bukietu.")
    return successful_channels_count

if __name__ == "__main__":
    github_config_url = 'https://raw.githubusercontent.com/azman26/azmanIPTVsettings/main/YTchannels.json'
    output_bouquet_file = os.path.join('/etc/enigma2', 'userbouquet.iptv-yt-channels-azman.tv')

    config_data = get_channels_from_github(github_config_url)
    
    if config_data:
        count = create_bouquet_from_channels(config_data, output_bouquet_file)
        print("\n--- PODSUMOWANIE ---")
        print(f"Zakończono. Dodano {count} transmisji.")
        print(f"Bukiet zapisano w: {output_bouquet_file}")
    
    # Przywracamy stderr przed zakończeniem
    sys.stderr.close()
    sys.stderr = sys.__stderr__