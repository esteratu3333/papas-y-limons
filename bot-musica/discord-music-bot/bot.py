import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os
from dotenv import load_dotenv

# Configuración del bot
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='-', intents=intents)

# Cargar variables de entorno desde el archivo .env (si existe)
load_dotenv()

# Configuración de yt-dlp
ytdl_format_options = {
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

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -hide_banner -loglevel warning'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)


async def enqueue_playlist(ctx, url, limit: int = None, progress: bool = False):
    """Extrae las entradas de una playlist (incluye YouTube Music) y las añade a la cola.

    Args:
        ctx: contexto del comando.
        url: URL de la playlist.
        limit: máximo de canciones a encolar (None = sin límite salvo límite seguro interno).
        progress: si True, muestra y actualiza un mensaje con el progreso.

    Devuelve el número de canciones añadidas.
    """
    queue = get_queue(ctx.guild.id)
    loop = asyncio.get_event_loop()

    # Normalizar enlaces de YouTube Music a YouTube estándar para mejor extracción
    if 'music.youtube.com' in (url or '').lower():
        url = url.replace('music.youtube.com', 'www.youtube.com')

    def extract():
        opts = ytdl_format_options.copy()
        opts['noplaylist'] = False
        # Usar extracción 'flat' para obtener rápidamente los ids de vídeo
        # y así no bloquear mucho tiempo al encolar playlists grandes.
        opts['extract_flat'] = True
        ydl_local = yt_dlp.YoutubeDL(opts)
        return ydl_local.extract_info(url, download=False)

    try:
        # Evitar bloqueo indefinido: tiempo máximo para extraer la playlist
        data = await asyncio.wait_for(loop.run_in_executor(None, extract), timeout=30)
    except asyncio.TimeoutError:
        await ctx.send("❌ Timeout al extraer la playlist (tardó demasiado). Intenta de nuevo más tarde.")
        return 0
    except Exception as e:
        await ctx.send(f"❌ Error al extraer la playlist: {e}")
        return 0

    entries = []
    if 'entries' in data and data['entries']:
        entries = [e for e in data['entries'] if e]
    elif data.get('url'):
        entries = [data]

    # Límite seguro por defecto para evitar colas inmensas
    SAFE_LIMIT = 200
    if limit is None:
        limit = SAFE_LIMIT
    else:
        limit = min(limit, SAFE_LIMIT)

    added = 0
    progress_msg = None
    if progress:
        progress_msg = await ctx.send(f"🔎 Procesando playlist... (0)")

    # Encolar entries rápidamente (con 'extract_flat' normalmente sólo tenemos 'id' o 'url' rápido)
    for entry in entries:
        if added >= limit:
            break

        # Construir URL reproducible a partir del id cuando usemos extract_flat
        vid_id = entry.get('id')
        webpage = entry.get('webpage_url') or entry.get('url') or (f"https://www.youtube.com/watch?v={vid_id}" if vid_id else None)
        title = entry.get('title')
        if webpage:
            queue.add({'query': webpage, 'title': title})
            added += 1

            if progress and added % 10 == 0:
                try:
                    await progress_msg.edit(content=f"✅ Añadidas {added} canciones...")
                except Exception:
                    pass

    if progress and progress_msg:
        try:
            await progress_msg.edit(content=f"✅ Añadidas {added} canciones de la playlist a la cola.")
        except Exception:
            pass

    return added


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        try:
            data = await asyncio.wait_for(loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream)), timeout=30)
        except asyncio.TimeoutError:
            raise RuntimeError("Timeout al obtener información del stream")

        if 'entries' in data:
            # Tomar el primer resultado si es una búsqueda
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


# Cola de reproducción
class MusicQueue:
    def __init__(self):
        self.queue = []
        self.current = None

    def add(self, song):
        self.queue.append(song)

    def get_next(self):
        if self.queue:
            return self.queue.pop(0)
        return None

    def clear(self):
        self.queue = []
        self.current = None

    def is_empty(self):
        return len(self.queue) == 0


# Diccionario para almacenar colas por servidor
music_queues = {}


def get_queue(guild_id):
    if guild_id not in music_queues:
        music_queues[guild_id] = MusicQueue()
    return music_queues[guild_id]


@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user.name} (ID: {bot.user.id})')
    print('------')


@bot.command(name='join', help='Une el bot al canal de voz', aliases=['j'])
async def join(ctx):
    if not ctx.author.voice:
        await ctx.send("❌ Debes estar en un canal de voz para usar este comando.")
        return

    channel = ctx.author.voice.channel
    if ctx.voice_client is not None:
        await ctx.voice_client.move_to(channel)
    else:
        await channel.connect()
    
    await ctx.send(f"✅ Conectado a {channel.name}")


@bot.command(name='leave', help='Desconecta el bot del canal de voz')
async def leave(ctx):
    if ctx.voice_client:
        queue = get_queue(ctx.guild.id)
        queue.clear()
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Desconectado del canal de voz")
    else:
        await ctx.send("❌ No estoy conectado a ningún canal de voz")


@bot.command(name='play', help='Reproduce una canción de YouTube (URL o búsqueda)', aliases=['p'])
async def play(ctx, *, query):
    # Verificar si el usuario está en un canal de voz
    if not ctx.author.voice:
        await ctx.send("❌ Debes estar en un canal de voz para usar este comando.")
        return

    # Conectar al canal si no está conectado
    if ctx.voice_client is None:
        channel = ctx.author.voice.channel
        await channel.connect()

    queue = get_queue(ctx.guild.id)

    # Si no es una URL, buscar en YouTube
    if not query.startswith('http'):
        query = f"ytsearch:{query}"
    # Detectar si la consulta es una playlist (YouTube / YouTube Music)
    is_playlist = False
    if query.startswith('http'):
        # Normalizar YouTube Music a YouTube para mejorar detección/extracción
        if 'music.youtube.com' in query.lower():
            query = query.replace('music.youtube.com', 'www.youtube.com')

        lowered = query.lower()
        if 'list=' in lowered or '/playlist' in lowered or 'music.youtube.com' in lowered:
            is_playlist = True

    if is_playlist:
        added = await enqueue_playlist(ctx, query, limit=None, progress=False)
        if added == 0:
            return
        await ctx.send(f"✅ Añadidas {added} canciones de la playlist a la cola.")
        # Si no está reproduciendo, iniciar la reproducción
        if not ctx.voice_client.is_playing():
            try:
                await play_next(ctx)
            except Exception as e:
                await ctx.send(f"❌ Error al iniciar la playlist: {e}")
        return

    # Encolar la consulta en vez de crear el stream ahora (evita expiración en colas largas)
    queue.add({'query': query})

    if ctx.voice_client.is_playing():
        await ctx.send(f"📝 Añadido a la cola: {query}")
    else:
        # Si no está reproduciendo, iniciar la reproducción (esto creará el stream justo antes de tocar)
        try:
            await play_next(ctx)
        except Exception as e:
            await ctx.send(f"❌ Error al reproducir: {str(e)}")


async def play_next(ctx):
    queue = get_queue(ctx.guild.id)
    
    if queue.is_empty():
        queue.current = None
        return
    song = queue.get_next()

    # Crear el stream justo antes de reproducir
    try:
        player = await YTDLSource.from_url(song['query'], loop=bot.loop, stream=True)
    except Exception as e:
        print(f'Error al crear el stream para {song.get("query")}: {e}')
        # Intentar con la siguiente canción
        # Estamos dentro del loop async: programar la siguiente reproducción sin bloquear
        try:
            asyncio.create_task(play_next(ctx))
        except Exception as e2:
            print(f'Error al programar siguiente canción después de fallo: {e2}')
        return

    full_song = {'player': player, 'title': player.title}
    queue.current = full_song

    def after_playing(error):
        if error:
            print(f'Error en reproducción: {error}')
        # Este callback se ejecuta en un hilo externo; programar la coroutine en el loop
        fut = asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
        # Añadir manejador para loguear excepciones cuando termine
        def _done(f):
            try:
                f.result()
            except Exception as exc:
                print(f'Error al reproducir siguiente canción (callback): {exc}')

        try:
            fut.add_done_callback(_done)
        except Exception as e:
            print(f'Error al programar siguiente canción desde callback: {e}')

    try:
        ctx.voice_client.play(full_song['player'], after=after_playing)
    except Exception as e:
        print(f'Error al iniciar reproducción: {e}')
        try:
            asyncio.create_task(play_next(ctx))
        except Exception as e2:
            print(f'Error al programar siguiente canción después de fallo: {e2}')
        return

    await ctx.send(f"🎵 Reproduciendo: **{full_song['title']}**")


@bot.command(name='pause', help='Pausa la reproducción actual')
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ Reproducción pausada")
    else:
        await ctx.send("❌ No hay nada reproduciéndose")


@bot.command(name='resume', help='Reanuda la reproducción pausada')
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ Reproducción reanudada")
    else:
        await ctx.send("❌ La reproducción no está pausada")


@bot.command(name='skip', help='Salta a la siguiente canción', aliases=['s'])
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭️ Canción saltada")
    else:
        await ctx.send("❌ No hay nada reproduciéndose")


@bot.command(name='queue', help='Muestra la cola de reproducción')
async def show_queue(ctx):
    queue = get_queue(ctx.guild.id)
    
    if queue.current is None and queue.is_empty():
        await ctx.send("📋 La cola está vacía")
        return

    message = "📋 **Cola de reproducción:**\n\n"
    
    if queue.current:
        message += f"🎵 **Reproduciendo ahora:** {queue.current['title']}\n\n"
    
    if not queue.is_empty():
        message += "**Próximas canciones:**\n"
        for i, song in enumerate(queue.queue, 1):
            # Mostrar título si está disponible, sino la consulta
            message += f"{i}. {song.get('title', song.get('query'))}\n"
    
    await ctx.send(message)


@bot.command(name='clear', help='Limpia la cola de reproducción')
async def clear_queue(ctx):
    queue = get_queue(ctx.guild.id)
    queue.clear()
    
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
    
    await ctx.send("🗑️ Cola limpiada")


@bot.command(name='stop', help='Detiene la reproducción y limpia la cola')
async def stop(ctx):
    queue = get_queue(ctx.guild.id)
    queue.clear()
    
    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.send("⏹️ Reproducción detenida")
    else:
        await ctx.send("❌ No hay nada reproduciéndose")


@bot.command(name='volume', help='Ajusta el volumen (0-100)')
async def volume(ctx, vol: int):
    if ctx.voice_client is None:
        await ctx.send("❌ No estoy conectado a un canal de voz")
        return

    if not 0 <= vol <= 100:
        await ctx.send("❌ El volumen debe estar entre 0 y 100")
        return

    ctx.voice_client.source.volume = vol / 100
    await ctx.send(f"🔊 Volumen ajustado a {vol}%")


@bot.command(name='comandos', help='Muestra todos los comandos disponibles')
async def comandos(ctx):
    help_text = """
**🎵 Comandos del Bot de Música 🎵**

`!join` (o `!j`) - Une el bot a tu canal de voz
`!leave` - Desconecta el bot del canal de voz
`!play <canción>` (o `!p`) - Reproduce una canción (URL o búsqueda)
`!pause` - Pausa la reproducción actual
`!resume` - Reanuda la reproducción
`!skip` (o `!s`) - Salta a la siguiente canción
`!stop` - Detiene la reproducción y limpia la cola
`!queue` - Muestra la cola de reproducción
`!clear` - Limpia la cola de reproducción
`!volume <0-100>` - Ajusta el volumen
`!comandos` - Muestra este mensaje

**Ejemplos:**
`!play https://www.youtube.com/watch?v=...`
`!play despacito`
`!play https://music.youtube.com/playlist?list=...`  (añade todas las canciones de la playlist)
`!volume 50`
    """
    await ctx.send(help_text)


@bot.command(name='enqueue', help='Encola los títulos de una playlist y muestra progreso', aliases=['enq'])
async def enqueue(ctx, url: str, limit: int = None):
    """Encola una playlist mostrando progreso y aplicando un límite seguro.

    Uso: `-enqueue <url> [limit]`
    """
    # Verificar si el usuario está en un canal de voz
    if not ctx.author.voice:
        await ctx.send("❌ Debes estar en un canal de voz para usar este comando.")
        return

    # Conectar al canal si no está conectado
    if ctx.voice_client is None:
        channel = ctx.author.voice.channel
        await channel.connect()

    added = await enqueue_playlist(ctx, url, limit=limit, progress=True)
    if added == 0:
        await ctx.send("❌ No se agregaron canciones de la playlist.")
        return

    # Iniciar reproducción si es necesario
    if not ctx.voice_client.is_playing():
        try:
            await play_next(ctx)
        except Exception as e:
            await ctx.send(f"❌ Error al iniciar la reproducción: {e}")


# Iniciar el bot
if __name__ == '__main__':
    TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    
    if not TOKEN:
        print("❌ Error: No se encontró el token del bot.")
        print("Por favor, configura la variable de entorno DISCORD_BOT_TOKEN")
        print("Ejemplo: export DISCORD_BOT_TOKEN='tu_token_aqui'")
    else:
        bot.run(TOKEN)
