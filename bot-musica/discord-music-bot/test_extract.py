#!/usr/bin/env python3
import asyncio
import argparse
import sys
import copy

import yt_dlp

# Opciones similares a las usadas por el bot
YTDL_FORMAT_OPTIONS = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

async def extract_info_async(url, extract_flat=True, timeout=30):
    opts = copy.copy(YTDL_FORMAT_OPTIONS)
    opts['noplaylist'] = False
    if extract_flat:
        opts['extract_flat'] = True
    ydl = yt_dlp.YoutubeDL(opts)
    loop = asyncio.get_event_loop()
    return await asyncio.wait_for(loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False)), timeout=timeout)

async def main():
    parser = argparse.ArgumentParser(description='Probar extracción de playlists con yt_dlp')
    parser.add_argument('url', help='URL de playlist o vídeo')
    parser.add_argument('--no-flat', action='store_true', help='No usar extract_flat (extraer metadata completa)')
    parser.add_argument('--timeout', type=int, default=30, help='Timeout en segundos para la extracción')
    args = parser.parse_args()

    try:
        data = await extract_info_async(args.url, extract_flat=not args.no_flat, timeout=args.timeout)
    except asyncio.TimeoutError:
        print('ERROR: Timeout durante la extracción (esperado si el sitio responde lento).')
        sys.exit(2)
    except Exception as e:
        print('ERROR: Excepción durante la extracción:')
        print(e)
        sys.exit(1)

    print('--- Extracción completada ---')
    print(f"Tipo de objeto: {type(data)}")

    if isinstance(data, dict) and 'entries' in data:
        entries = [e for e in data['entries'] if e]
        print(f"Entries encontradas: {len(entries)}")
        for i, e in enumerate(entries[:20], start=1):
            print(f"{i}. id={e.get('id')} title={e.get('title')} webpage_url={e.get('webpage_url') or e.get('url')}")
    else:
        print('No se detectó campo `entries`. Información directa:')
        print(f"id={data.get('id')} title={data.get('title')} url={data.get('webpage_url') or data.get('url')}")

    # Intentar extraer metadata completa de la primera entrada si existe
    if isinstance(data, dict) and 'entries' in data and data['entries']:
        first = data['entries'][0]
        vid = first.get('id') or first.get('url')
        if vid:
            print('\n--- Probando extracción completa del primer item ---')
            try:
                opts2 = copy.copy(YTDL_FORMAT_OPTIONS)
                opts2['noplaylist'] = True
                ydl2 = yt_dlp.YoutubeDL(opts2)
                info = ydl2.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
                print('Extracción completa OK:')
                print(f"title={info.get('title')} duration={info.get('duration')}")
            except Exception as e:
                print('ERROR al extraer metadata completa del primer item:')
                print(e)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
