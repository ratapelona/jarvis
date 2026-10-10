"""
config.py — Centro de Configuración de Reaxy$
Todas las constantes, whitelist, y configuración centralizada.

Soporte multiplataforma: Windows + macOS
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# DETECCIÓN DE PLATAFORMA
# =============================================================================
ES_WINDOWS = sys.platform == "win32"
ES_MAC = sys.platform == "darwin"
ES_LINUX = sys.platform.startswith("linux")

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
VERSION = "2.0-alpha"

# =============================================================================
# API & MODELOS (OLLAMA RESIDENTE + MODO PESADO)
# =============================================================================
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL}/api/chat"
OLLAMA_API_URL = OLLAMA_CHAT_URL
OLLAMA_TAGS_URL = f"{OLLAMA_BASE_URL}/api/tags"
OLLAMA_PS_URL = f"{OLLAMA_BASE_URL}/api/ps"
OLLAMA_API_KEY = "ollama"  # Ollama no requiere una API key real por defecto
API_HEADERS = {
    "Authorization": f"Bearer {OLLAMA_API_KEY}",
    "Content-Type": "application/json"
}

# Modelo residente (siempre cargado en memoria) y modo pesado (solo tareas largas)
MODELO_RAPIDO = "qwen3.5:9b"
MODELO_PESADO = "gpt-oss:20b"
MODELO_PRINCIPAL = MODELO_RAPIDO
MODELO_AGENTE = MODELO_PESADO
TEMPERATURA = 0.1
NUM_CTX = 8192
KEEP_ALIVE_RESIDENTE = -1
OLLAMA_OPTIONS = {
    "num_ctx": NUM_CTX,
    "temperature": TEMPERATURA
}

# =============================================================================
# AUDIO
# =============================================================================
SAMPLE_RATE = 16000
WAKEWORD_THRESHOLD = 0.5
SILENCE_THRESHOLD = 0.015
SILENCE_TIMEOUT_SECS = 2.0
MAX_RECORDING_SECS = 15.0
NO_SPEECH_TIMEOUT_SECS = 1.0
TTS_VOICE = "es-MX-JorgeNeural"
WHISPER_MODEL = "base"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"

# =============================================================================
# BASE DE DATOS
# =============================================================================
DB_PATH = os.path.join(_PROJECT_ROOT, "recepcion_jarvis.db")
CHROMA_PATH = os.path.join(_PROJECT_ROOT, "cerebro_jarvis")
CHROMA_COLLECTION = "database_vectorial_v2"
MAX_RECUERDOS_POR_USUARIO = 500

# =============================================================================
# SEGURIDAD — Autenticación
# =============================================================================
BCRYPT_COST = 12
RATE_LIMIT_MAX_INTENTOS = 5
RATE_LIMIT_BLOQUEO_SEGUNDOS = 30

# =============================================================================
# SEGURIDAD — Sandbox para creación de archivos (MULTIPLATAFORMA)
# =============================================================================
SANDBOX_DIR = os.path.join(_PROJECT_ROOT, "output")
EXTENSIONES_PERMITIDAS = {".py", ".html", ".css", ".js", ".txt", ".json", ".md", ".c", ".csv"}

# =============================================================================
# SEGURIDAD — Whitelist de aplicaciones (POR PLATAFORMA)
# =============================================================================
if ES_WINDOWS:
    MIS_APPS = {
        "spotify": ["cmd", "/c", "start", "spotify"],
        "edge": [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", "--remote-debugging-port=9222"],
        "calculadora": ["cmd", "/c", "start", "calc"],
        "archivos": ["explorer.exe"],
        "obs": [r"C:\Program Files\obs-studio\bin\64bit\obs64.exe"],
        "docker": [r"C:\Program Files\Docker\Docker\Docker Desktop.exe"],
        "packet tracer": [r"C:\Program Files\Cisco Packet Tracer 9.0.0\bin\PacketTracer.exe"],
        "ollama": [r"C:\Users\alexa\AppData\Local\Programs\Ollama\ollama app.exe"],
        "microsoft store": ["cmd", "/c", "start", "ms-windows-store:"],
        "chrome": [r"C:\Program Files\Google\Chrome\Application\chrome.exe"],
        "discord": [r"C:\Users\alexa\AppData\Local\Discord\Update.exe", "--processStart", "Discord.exe"],
        "steam": [r"C:\Program Files (x86)\Steam\steam.exe"],
        "vscode": [r"C:\Users\alexa\AppData\Local\Programs\Microsoft VS Code\Code.exe"],
        "league of legends": [r"C:\Riot Games\Riot Client\RiotClientServices.exe"],
        "git bash": [r"C:\Program Files\Git\git-bash.exe"],
        "notepad": ["notepad.exe"],
        "paint": ["mspaint.exe"],
        "task manager": ["taskmgr.exe"],
        "roblox": [r"C:\Users\alexa\AppData\Local\Roblox\Versions\version-c5aecda2245e4fae\RobloxPlayerBeta.exe"],
        "antigravity": [r"C:\Users\alexa\AppData\Local\Programs\antigravity\Antigravity.exe"],
        "antigravity ide": [r"C:\Users\alexa\AppData\Local\Programs\Antigravity IDE\Antigravity IDE.exe"],
    }
elif ES_MAC:
    MIS_APPS = {
        "spotify": ["open", "-a", "Spotify"],
        "safari": ["open", "-a", "Safari"],
        "chrome": ["open", "-a", "Google Chrome", "--args", "--remote-debugging-port=9222"],
        "edge": ["open", "-a", "Microsoft Edge", "--args", "--remote-debugging-port=9222"],
        "calculadora": ["open", "-a", "Calculator"],
        "archivos": ["open", "-a", "Finder"],
        "obs": ["open", "-a", "OBS"],
        "docker": ["open", "-a", "Docker"],
        "ollama": ["open", "-a", "Ollama"],
        "discord": ["open", "-a", "Discord"],
        "steam": ["open", "-a", "Steam"],
        "vscode": ["open", "-a", "Visual Studio Code"],
        "notas": ["open", "-a", "Notes"],
        "terminal": ["open", "-a", "Terminal"],
        "textedit": ["open", "-a", "TextEdit"],
        "monitor de actividad": ["open", "-a", "Activity Monitor"],
        "preview": ["open", "-a", "Preview"],
        "xcode": ["open", "-a", "Xcode"],
        "blender": ["open", "-a", "Blender"],
    }
else:
    # Linux / Otros
    MIS_APPS = {
        "archivos": ["xdg-open", os.path.expanduser("~")],
        "chrome": ["google-chrome"],
        "firefox": ["firefox"],
        "calculadora": ["gnome-calculator"],
        "vscode": ["code"],
        "terminal": ["gnome-terminal"],
    }

NOMBRES_APPS = ", ".join(MIS_APPS.keys())

# =============================================================================
# SEGURIDAD — Blacklist de aplicaciones peligrosas (Agente)
# =============================================================================
if ES_WINDOWS:
    APPS_BLOQUEADAS = {"cmd", "powershell", "terminal", "regedit", "cmd.exe", "powershell.exe"}
elif ES_MAC:
    APPS_BLOQUEADAS = {"terminal", "iterm", "iterm2", "system preferences", "disk utility"}
else:
    APPS_BLOQUEADAS = {"bash", "sh", "zsh", "gnome-terminal", "konsole"}

# =============================================================================
# SEGURIDAD — Whitelist de teclas permitidas (Agente)
# =============================================================================
TECLAS_PERMITIDAS = {
    "enter", "tab", "space", "backspace", "delete", "escape",
    "up", "down", "left", "right",
    "home", "end", "pageup", "pagedown",
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
    "shift", "ctrl", "alt",
    "volumeup", "volumedown", "volumemute",
}

# Combinaciones de teclas PROHIBIDAS (pueden dañar el sistema)
if ES_WINDOWS:
    TECLAS_BLOQUEADAS = {
        "alt+f4", "ctrl+alt+del", "ctrl+alt+delete",
        "win+r", "ctrl+shift+escape", "ctrl+shift+esc",
    }
elif ES_MAC:
    TECLAS_BLOQUEADAS = {
        "command+q", "command+option+escape",
        "command+shift+q", "ctrl+command+q",
    }
else:
    TECLAS_BLOQUEADAS = {
        "ctrl+alt+del", "alt+f4",
    }

# =============================================================================
# AGENTE AUTÓNOMO
# =============================================================================
AGENTE_MAX_PASOS = 15
AGENTE_DELAY_INICIO_SECS = 4

# =============================================================================
# ESCALABILIDAD
# =============================================================================
VENTANA_HISTORIAL = 20  # Últimos N mensajes enviados a la API
MAX_WORKERS_IA = 3      # ThreadPoolExecutor para peticiones IA
COLA_AUDIO_MAXSIZE = 10
COLA_IA_MAXSIZE = 10         # Cola de peticiones IA (protección VRAM)
SANITIZACION_MAX_CHARS = 2000

# =============================================================================
# OCR / Tesseract (MULTIPLATAFORMA)
# =============================================================================
if ES_WINDOWS:
    TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
elif ES_MAC:
    # Homebrew instala Tesseract en /opt/homebrew/bin o /usr/local/bin
    TESSERACT_CMD = "/opt/homebrew/bin/tesseract" if os.path.exists("/opt/homebrew/bin/tesseract") else "/usr/local/bin/tesseract"
else:
    TESSERACT_CMD = "tesseract"  # Linux: se asume que está en el PATH

# =============================================================================
# Flet UI
# =============================================================================
WINDOW_WIDTH = 940
WINDOW_HEIGHT = 940
FONT_TITULO = "assets/fonts/Akira Expanded Demo.otf"
FONT_FIRMA = "assets/fonts/Gohan.ttf"
