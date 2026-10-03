"""
core/tool_executor.py — Ejecución Segura de Herramientas (MULTIPLATAFORMA)

SEC-05: shell=False + listas de argumentos (anti-inyección OS)
SEC-06: Sandbox + whitelist para creación de archivos
SEC-07: Blacklist de apps/teclas + logging de acciones

Soporte: Windows (pywinauto/Win32) + macOS (AppleScript/osascript)
"""
import os
import json
import subprocess
import tempfile
import time
import sys

import pyautogui
from PIL import ImageGrab
from fpdf import FPDF
from ddgs import DDGS
from playwright.sync_api import sync_playwright

from config import (
    ES_WINDOWS,
    ES_MAC,
    MIS_APPS,
    APPS_BLOQUEADAS,
    TECLAS_PERMITIDAS,
    TECLAS_BLOQUEADAS,
    SANDBOX_DIR,
    EXTENSIONES_PERMITIDAS,
    TESSERACT_CMD,
    TTS_VOICE,
)
from data.sql_store import log_accion

# --- Imports condicionales por plataforma ---
if ES_WINDOWS:
    import pywinauto
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
else:
    # En macOS/Linux, pytesseract se importa condicionalmente
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    except ImportError:
        pytesseract = None


# =============================================================================
# SEC-06: Sandbox — Creación segura de archivos
# =============================================================================
def crear_archivo_seguro(nombre: str, contenido: str, usuario: str = "") -> str:
    """
    Crea un archivo SOLO dentro del directorio sandbox.
    Valida path traversal y extensión.
    """
    # Asegurar que el sandbox existe
    os.makedirs(SANDBOX_DIR, exist_ok=True)

    # Resolver ruta real para prevenir path traversal (../../etc)
    ruta_real = os.path.realpath(os.path.join(SANDBOX_DIR, nombre))
    sandbox_real = os.path.realpath(SANDBOX_DIR)

    if not ruta_real.startswith(sandbox_real):
        log_accion(usuario, "crear_archivo", nombre, "BLOQUEADO: path traversal")
        return "⛔ BLOQUEADO: Path traversal detectado. Solo puedes crear archivos dentro del sandbox."

    ext = os.path.splitext(nombre)[1].lower()
    if ext not in EXTENSIONES_PERMITIDAS:
        log_accion(usuario, "crear_archivo", nombre, f"BLOQUEADO: extensión {ext}")
        return f"⛔ BLOQUEADO: Extensión '{ext}' no permitida. Permitidas: {', '.join(sorted(EXTENSIONES_PERMITIDAS))}"

    try:
        # Crear subdirectorios si el nombre incluye carpetas
        os.makedirs(os.path.dirname(ruta_real), exist_ok=True)
        with open(ruta_real, "w", encoding="utf-8") as f:
            f.write(contenido)
        log_accion(usuario, "crear_archivo", nombre, f"OK: {ruta_real}")
        return f"✅ Archivo '{nombre}' creado en el sandbox: {ruta_real}"
    except Exception as e:
        log_accion(usuario, "crear_archivo", nombre, f"ERROR: {e}")
        return f"❌ Error al crear archivo: {e}"


# =============================================================================
# SEC-06: Sandbox — Creación segura de PDFs
# =============================================================================
def crear_pdf_seguro(nombre: str, contenido: str, usuario: str = "") -> str:
    """Crea un PDF dentro del sandbox."""
    os.makedirs(SANDBOX_DIR, exist_ok=True)

    # Forzar extensión .pdf
    if not nombre.lower().endswith(".pdf"):
        nombre += ".pdf"

    ruta_real = os.path.realpath(os.path.join(SANDBOX_DIR, nombre))
    sandbox_real = os.path.realpath(SANDBOX_DIR)

    if not ruta_real.startswith(sandbox_real):
        log_accion(usuario, "crear_pdf", nombre, "BLOQUEADO: path traversal")
        return "⛔ BLOQUEADO: Path traversal detectado."

    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Helvetica", size=12)
        for linea in contenido.split("\n"):
            pdf.cell(0, 10, linea, new_x="LMARGIN", new_y="NEXT")
        pdf.output(ruta_real)
        log_accion(usuario, "crear_pdf", nombre, f"OK: {ruta_real}")
        return f"✅ PDF '{nombre}' creado en: {ruta_real}"
    except Exception as e:
        log_accion(usuario, "crear_pdf", nombre, f"ERROR: {e}")
        return f"❌ Error al crear PDF: {e}"


# =============================================================================
# SEC-05: Abrir apps con shell=False + whitelist (MULTIPLATAFORMA)
# =============================================================================
def abrir_app(nombre_app: str, usuario: str = "") -> str:
    """Abre una app del whitelist con shell=False."""
    nombre_key = nombre_app.lower().strip()

    if nombre_key in APPS_BLOQUEADAS:
        log_accion(usuario, "abrir_app", nombre_app, "BLOQUEADO: app peligrosa")
        return f"⛔ BLOQUEADO: '{nombre_app}' está en la lista de aplicaciones prohibidas."

    if nombre_key not in MIS_APPS:
        log_accion(usuario, "abrir_app", nombre_app, "NO ENCONTRADA")
        return f"❌ App '{nombre_app}' no registrada. Disponibles: {', '.join(MIS_APPS.keys())}"

    try:
        cmd_lista = MIS_APPS[nombre_key]
        subprocess.Popen(cmd_lista, shell=False)
        time.sleep(2)
        log_accion(usuario, "abrir_app", nombre_app, "OK")
        return f"✅ App '{nombre_app}' abierta exitosamente."
    except Exception as e:
        log_accion(usuario, "abrir_app", nombre_app, f"ERROR: {e}")
        return f"❌ Error al abrir '{nombre_app}': {e}"


# =============================================================================
# Búsqueda web
# =============================================================================
def buscar_internet(tema: str, usuario: str = "") -> str:
    """Busca en la web usando DuckDuckGo."""
    try:
        resultados = DDGS().text(tema, max_results=3)
        if resultados:
            texto = "".join([f"{c['title']}: {c['body']}\n" for c in resultados])
        else:
            texto = "La búsqueda no arrojó resultados."
        log_accion(usuario, "buscar_internet", tema, "OK")
        return texto
    except Exception as e:
        log_accion(usuario, "buscar_internet", tema, f"ERROR: {e}")
        return "Error de red. Satélites desconectados."


# =============================================================================
# Control físico con guardarraíles (SEC-07) — MULTIPLATAFORMA
# =============================================================================
def mover_y_click(x: int, y: int, boton: str = "left", usuario: str = "") -> str:
    """Mueve el mouse y hace click en las coordenadas."""
    try:
        pyautogui.moveTo(x, y, duration=0.5)
        pyautogui.click(button=boton)
        log_accion(usuario, "mover_y_click", f"({x},{y}) {boton}", "OK")
        return f"Click '{boton}' exitoso en ({x}, {y})."
    except Exception as e:
        log_accion(usuario, "mover_y_click", f"({x},{y})", f"ERROR: {e}")
        return f"Error al hacer click: {e}"


def escribir_teclado(texto: str, usuario: str = "") -> str:
    """Escribe texto con el teclado físico."""
    try:
        import pyperclip
        pyperclip.copy(texto)
        time.sleep(0.1)
        # En macOS se usa Command+V en vez de Ctrl+V
        if ES_MAC:
            pyautogui.hotkey('command', 'v')
        else:
            pyautogui.hotkey('ctrl', 'v')
        log_accion(usuario, "escribir_teclado", texto[:50], "OK")
        return f"Texto escrito en el teclado físico (vía portapapeles para soportar tildes)."
    except Exception as e:
        log_accion(usuario, "escribir_teclado", texto[:50], f"ERROR: {e}")
        return f"Error al escribir: {e}"


def presionar_tecla(tecla: str, usuario: str = "") -> str:
    """
    Presiona una tecla especial CON validación de whitelist.
    SEC-07: Bloquea combinaciones peligrosas.
    """
    tecla_lower = tecla.lower().strip()

    # Verificar combinaciones bloqueadas
    for combo_bloqueado in TECLAS_BLOQUEADAS:
        if tecla_lower == combo_bloqueado:
            log_accion(usuario, "presionar_tecla", tecla, "BLOQUEADO")
            return f"⛔ BLOQUEADO: Combinación '{tecla}' no permitida por seguridad."

    # Verificar whitelist (para teclas simples)
    tecla_base = tecla_lower.split("+")[-1] if "+" in tecla_lower else tecla_lower
    if tecla_base not in TECLAS_PERMITIDAS:
        log_accion(usuario, "presionar_tecla", tecla, "BLOQUEADO: no en whitelist")
        return f"⛔ BLOQUEADO: Tecla '{tecla}' no está en la lista de teclas permitidas."

    try:
        pyautogui.press(tecla)
        log_accion(usuario, "presionar_tecla", tecla, "OK")
        return f"Tecla '{tecla}' presionada."
    except Exception as e:
        log_accion(usuario, "presionar_tecla", tecla, f"ERROR: {e}")
        return f"Error al presionar tecla: {e}"


# =============================================================================
# OCR — Escaneo de pantalla (MULTIPLATAFORMA)
# =============================================================================
def escanear_pantalla_ocr(usuario: str = "") -> str:
    """Captura la pantalla y extrae texto con coordenadas via OCR."""
    if pytesseract is None:
        return "❌ OCR no disponible: pytesseract no está instalado en este sistema."
    try:
        img = ImageGrab.grab()
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        resultados = []
        for i in range(len(data["text"])):
            texto_encontrado = data["text"][i].strip()
            if len(texto_encontrado) > 2:
                x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
                cx, cy = x + w // 2, y + h // 2
                resultados.append(f"'{texto_encontrado}' (X:{cx}, Y:{cy})")
        txt = "Resultados OCR (Coordenadas X, Y del centro):\n" + "\n".join(resultados[-150:])
        log_accion(usuario, "escanear_pantalla_ocr", "", f"OK: {len(resultados)} elementos")
        return txt[:2500]
    except Exception as e:
        log_accion(usuario, "escanear_pantalla_ocr", "", f"ERROR: {e}")
        return f"Error OCR: {e}"


def escanear_entorno_sistema(usuario: str = "") -> str:
    """Obtiene resolución y lista de ventanas activas (MULTIPLATAFORMA)."""
    try:
        sw, sh = pyautogui.size()
        txt = f"Resolución de pantalla: {sw}x{sh}\nVentanas activas:\n"

        if ES_WINDOWS:
            windows = pywinauto.Desktop(backend="win32").windows()
            for w in windows:
                if w.is_visible() and w.window_text():
                    r = w.rectangle()
                    txt += f"- '{w.window_text()}' en (L:{r.left}, T:{r.top}, R:{r.right}, B:{r.bottom})\n"
        elif ES_MAC:
            # En macOS usamos AppleScript para listar ventanas activas
            result = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get the name of every process whose visible is true'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                apps = result.stdout.strip().split(", ")
                for app_name in apps:
                    txt += f"- '{app_name}'\n"
            else:
                txt += "No se pudieron obtener las ventanas activas.\n"
        else:
            # Linux fallback
            txt += "Listado de ventanas no disponible en este sistema.\n"

        log_accion(usuario, "escanear_entorno_sistema", "", "OK")
        return txt
    except Exception as e:
        log_accion(usuario, "escanear_entorno_sistema", "", f"ERROR: {e}")
        return f"Error al escanear entorno: {e}"


# =============================================================================
# TTS — Text-to-Speech con shell=False (SEC-05) — MULTIPLATAFORMA
# =============================================================================
def sintetizar_voz(texto: str) -> str | None:
    """
    Genera audio MP3 con edge-tts usando shell=False.
    Retorna la ruta del archivo o None si falla.
    """
    # Limpiar texto para TTS (sin metacaracteres peligrosos ya)
    txt_limpio = texto.replace('"', '').replace("'", "").replace('\n', ' ').replace('`', '')

    # Usar tempfile para archivos temporales (ESC-08)
    nombre_audio = os.path.join(
        tempfile.gettempdir(),
        f"reaxy_tts_{int(time.time())}.mp3"
    )

    try:
        # SEC-05: shell=False + lista de argumentos
        subprocess.run(
            ["edge-tts", "--voice", TTS_VOICE, "--text", txt_limpio, "--write-media", nombre_audio],
            shell=False,
            capture_output=True,
            timeout=30,
        )
        if os.path.exists(nombre_audio):
            return nombre_audio
        return None
    except Exception:
        return None


# =============================================================================
# HERRAMIENTAS WEB (Playwright sobre CDP) — MULTIPLATAFORMA
# =============================================================================
def _conectar_navegador():
    playwright = sync_playwright().start()
    try:
        # Intenta conectar a una sesión existente con debugging remoto (puerto 9222)
        browser = playwright.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()
    except Exception:
        # Si no hay sesión activa, lanza un navegador nuevo visible
        if ES_MAC:
            # En macOS, buscar Chrome o Edge
            browser = playwright.chromium.launch(channel="chrome", headless=False)
        else:
            browser = playwright.chromium.launch(channel="msedge", headless=False)
        context = browser.new_context()
        page = context.new_page()

    return playwright, browser, page

def navegar_y_leer_pantalla(url: str, usuario: str = "sistema"):
    log_accion(usuario, "navegar_y_leer_pantalla", url, "OK")
    try:
        p, b, page = _conectar_navegador()
        page.goto(url)
        js = """
        () => {
            let elements = [];
            document.querySelectorAll('a, button, input, textarea').forEach(el => {
                let rect = el.getBoundingClientRect();
                if(rect.width > 0 && rect.height > 0 && el.offsetParent !== null) {
                    let text = el.innerText || el.value || el.placeholder || el.name || '';
                    elements.push({tag: el.tagName, text: text.trim().substring(0,50)});
                }
            });
            return {
                title: document.title,
                url: document.location.href,
                text: document.body.innerText.substring(0, 1000),
                interactables: elements
            };
        }
        """
        data = page.evaluate(js)
        return json.dumps(data, ensure_ascii=False)
    except Exception as e:
        return f"Error al navegar y leer DOM: {e}"
    finally:
        if 'b' in locals(): b.close()
        if 'p' in locals(): p.stop()

def escribir_en_elemento(selector: str, texto: str, usuario: str = "sistema"):
    log_accion(usuario, "escribir_en_elemento", f"{selector} -> {texto}", "OK")
    try:
        p, b, page = _conectar_navegador()
        page.fill(selector, texto)
        return f"Escrito en '{selector}'"
    except Exception as e:
        return f"Error al escribir: {e}"
    finally:
        if 'b' in locals(): b.close()
        if 'p' in locals(): p.stop()

def click_en_elemento(selector: str, usuario: str = "sistema"):
    log_accion(usuario, "click_en_elemento", selector, "OK")
    try:
        p, b, page = _conectar_navegador()
        page.click(selector)
        return f"Click en '{selector}' realizado."
    except Exception as e:
        return f"Error al clickear: {e}"
    finally:
        if 'b' in locals(): b.close()
        if 'p' in locals(): p.stop()


# =============================================================================
# HERRAMIENTAS WINDOWS (UIAutomation) + macOS (AppleScript)
# =============================================================================
def escanear_entorno_uia(usuario: str = "sistema"):
    log_accion(usuario, "escanear_entorno_uia", "uia", "OK")
    if ES_WINDOWS:
        try:
            desktop = pywinauto.Desktop(backend="uia")
            windows = desktop.windows()
            resultado = "Ventanas abiertas (UIA):\n"
            for w in windows:
                if w.window_text():
                    resultado += f"- {w.window_text()} (Clase: {w.class_name()})\n"
            return resultado
        except Exception as e:
            return f"Error escaneando UIA: {e}"
    elif ES_MAC:
        try:
            result = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get the name of every process whose visible is true'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                apps = result.stdout.strip().split(", ")
                resultado = "Aplicaciones visibles (macOS):\n"
                for app_name in apps:
                    resultado += f"- {app_name}\n"
                return resultado
            return "No se pudieron obtener las aplicaciones visibles."
        except Exception as e:
            return f"Error escaneando entorno macOS: {e}"
    else:
        return "Escaneo de entorno no disponible en este sistema operativo."

def click_uia(titulo_ventana: str, nombre_control: str, tipo_control: str = "Button", usuario: str = "sistema"):
    log_accion(usuario, "click_uia", f"{titulo_ventana} -> {nombre_control}", "OK")
    if ES_WINDOWS:
        try:
            app = pywinauto.Desktop(backend="uia").window(title_re=f".*{titulo_ventana}.*")
            ctrl = app.child_window(title=nombre_control, control_type=tipo_control)
            ctrl.click_input()
            return f"Click en '{nombre_control}' de '{titulo_ventana}'"
        except Exception as e:
            return f"Error click UIA: {e}"
    elif ES_MAC:
        try:
            script = (
                f'tell application "System Events"\n'
                f'  tell process "{titulo_ventana}"\n'
                f'    click button "{nombre_control}" of window 1\n'
                f'  end tell\n'
                f'end tell'
            )
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return f"Click en '{nombre_control}' de '{titulo_ventana}' (macOS)"
            return f"Error click macOS: {result.stderr}"
        except Exception as e:
            return f"Error click macOS: {e}"
    else:
        return "Click en controles nativos no disponible en este sistema."

def escribir_uia(titulo_ventana: str, nombre_control: str, texto: str, usuario: str = "sistema"):
    log_accion(usuario, "escribir_uia", f"{titulo_ventana} -> {nombre_control}", "OK")
    if ES_WINDOWS:
        try:
            app = pywinauto.Desktop(backend="uia").window(title_re=f".*{titulo_ventana}.*")
            ctrl = app.child_window(title=nombre_control, control_type="Edit")
            ctrl.type_keys(texto, with_spaces=True)
            return f"Escrito en '{nombre_control}' de '{titulo_ventana}'"
        except Exception as e:
            return f"Error escribir UIA: {e}"
    elif ES_MAC:
        try:
            script = (
                f'tell application "System Events"\n'
                f'  tell process "{titulo_ventana}"\n'
                f'    set value of text field "{nombre_control}" of window 1 to "{texto}"\n'
                f'  end tell\n'
                f'end tell'
            )
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return f"Escrito en '{nombre_control}' de '{titulo_ventana}' (macOS)"
            return f"Error escribir macOS: {result.stderr}"
        except Exception as e:
            return f"Error escribir macOS: {e}"
    else:
        return "Escritura en controles nativos no disponible en este sistema."
