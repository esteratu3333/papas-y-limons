# 🚀 Guía Rápida de Inicio

Esta guía te ayudará a poner en marcha tu bot de música de Discord en **5 minutos**.

## ✅ Checklist Rápido

- [ ] Python 3.8+ instalado
- [ ] FFmpeg instalado
- [ ] Bot creado en Discord Developer Portal
- [ ] Token del bot obtenido
- [ ] Bot invitado a tu servidor

## 📝 Pasos Rápidos

### 1️⃣ Crear el Bot en Discord (2 minutos)

1. Ve a https://discord.com/developers/applications
2. Click en **"New Application"** → Dale un nombre
3. Ve a **"Bot"** → Click en **"Add Bot"**
4. Activa estos **Intents**:
   - ✅ MESSAGE CONTENT INTENT
   - ✅ SERVER MEMBERS INTENT
5. Copia el **TOKEN** (botón "Reset Token")

### 2️⃣ Invitar el Bot a tu Servidor (1 minuto)

1. Ve a **"OAuth2"** → **"URL Generator"**
2. Selecciona: `bot`
3. Permisos: `Send Messages`, `Connect`, `Speak`, `Use Voice Activity`
4. Copia la URL generada y ábrela en tu navegador
5. Selecciona tu servidor e invita el bot

### 3️⃣ Configurar el Proyecto (2 minutos)

```bash
# Navegar a la carpeta del bot
cd discord-music-bot

# Crear entorno virtual
python3 -m venv venv

# Activar entorno virtual
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate     # Windows

# Instalar dependencias
pip install -r requirements.txt

# Configurar el token
export DISCORD_BOT_TOKEN='TU_TOKEN_AQUI'
```

### 4️⃣ Ejecutar el Bot

```bash
python bot.py
```

Deberías ver:
```
Bot conectado como TuBot#1234 (ID: ...)
------
```

## 🎮 Primeros Comandos

En Discord, escribe:

```
!join          # El bot se une a tu canal de voz
!play despacito  # Reproduce una canción
!queue         # Ver la cola
!comandos      # Ver todos los comandos
```

## ⚠️ Problemas Comunes

### "FFmpeg no encontrado"
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg
```

### "Bot no responde"
- Verifica que MESSAGE CONTENT INTENT esté activado
- Asegúrate de que el bot tenga permisos en el servidor

### "No se puede conectar"
- Verifica que el token sea correcto
- Asegúrate de estar en un canal de voz

## 📚 Más Información

Para documentación completa, consulta el archivo `README.md`.

---

**¡Listo! Tu bot está funcionando. 🎉**
