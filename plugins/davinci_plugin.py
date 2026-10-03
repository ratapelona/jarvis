"""
plugins/davinci_plugin.py — Plugin de DaVinci Resolve (Free Edition) — MULTIPLATAFORMA

Especializado en la versión gratuita de DaVinci Resolve.
Combina la API de scripting interna si está habilitada, con automatización de macros,
atajos de teclado de edición (Blade, Ripple Delete, In/Out) e inspección de UIAutomation.

Soporte: Windows (pywinauto) + macOS (AppleScript/osascript)
"""
import os
import sys
import time
import subprocess
from typing import Dict, Any, List

from plugins.base_plugin import BasePlugin
from config import SANDBOX_DIR, ES_WINDOWS, ES_MAC
from data.sql_store import log_accion


def _buscar_resolve_exe() -> str:
    if ES_WINDOWS:
        rutas = [
            r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe",
            r"D:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe",
        ]
        for r in rutas:
            if os.path.exists(r):
                return r
        return r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe"
    elif ES_MAC:
        ruta_mac = "/Applications/DaVinci Resolve/DaVinci Resolve.app"
        if os.path.exists(ruta_mac):
            return ruta_mac
        return ruta_mac
    else:
        # Linux: DaVinci Resolve se instala en /opt
        ruta_linux = "/opt/resolve/bin/resolve"
        return ruta_linux


class DavinciPlugin(BasePlugin):
    def __init__(self, custom_path: str = ""):
        self.custom_path = custom_path

    @property
    def plugin_id(self) -> str:
        return "davinci_resolve_free"

    @property
    def name(self) -> str:
        return "DaVinci Resolve (Free Edition)"

    @property
    def description(self) -> str:
        return "Automatización de montaje, cortes en línea de tiempo y exportación para DaVinci Resolve Free."

    def _get_exe(self) -> str:
        if self.custom_path and os.path.exists(self.custom_path):
            return self.custom_path
        return _buscar_resolve_exe()

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "abrir_davinci_resolve",
                    "description": "Inicia la aplicación DaVinci Resolve de forma segura.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "aplicar_accion_edicion_davinci",
                    "description": "Ejecuta acciones de edición en la línea de tiempo activa de DaVinci Resolve mediante comandos y atajos de teclado.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "accion": {
                                "type": "string",
                                "enum": [
                                    "cortar_clip_cuchilla",
                                    "eliminar_espacio_ripple",
                                    "marcar_punto_in",
                                    "marcar_punto_out",
                                    "reproducir_pausar",
                                    "ir_pagina_edicion",
                                    "ir_pagina_color",
                                    "ir_pagina_entrega",
                                    "ajustar_zoom_timeline"
                                ],
                                "description": "Comando de edición a ejecutar en DaVinci."
                            }
                        },
                        "required": ["accion"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generar_guion_montaje_davinci",
                    "description": "Genera una lista de decisiones de edición (EDL/Timeline plan) en formato texto/json guardada en el sandbox para importar o guiar la edición.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "nombre_proyecto": {"type": "string"},
                            "clips_con_tiempos": {
                                "type": "string",
                                "description": "Descripción o JSON con lista de clips y rangos de tiempo (ej: [{'clip': 'video.mp4', 'in': '00:01', 'out': '00:15'}])"
                            }
                        },
                        "required": ["nombre_proyecto", "clips_con_tiempos"]
                    }
                }
            }
        ]

    def execute(self, tool_name: str, arguments: Dict[str, Any], user: str = "") -> str:
        if tool_name == "abrir_davinci_resolve":
            return self._abrir_resolve(user)
        elif tool_name == "aplicar_accion_edicion_davinci":
            return self._accion_edicion(arguments, user)
        elif tool_name == "generar_guion_montaje_davinci":
            return self._generar_guion(arguments, user)
        return f"Herramienta '{tool_name}' no soportada por DavinciPlugin."

    def _abrir_resolve(self, user: str) -> str:
        exe = self._get_exe()

        if ES_MAC:
            # En macOS abrimos la .app con 'open'
            try:
                subprocess.Popen(["open", "-a", "DaVinci Resolve"], shell=False)
                log_accion(user, "abrir_davinci_resolve", "macOS", "OK")
                return "✅ DaVinci Resolve (Free) iniciado exitosamente en macOS."
            except Exception as e:
                return f"❌ Error al iniciar DaVinci en macOS: {e}"
        else:
            # Windows / Linux: ejecutar el binario directamente
            if not os.path.exists(exe):
                return f"❌ DaVinci Resolve no fue hallado en '{exe}'. Por favor verifica la ruta de instalación en la configuración del plugin."
            try:
                subprocess.Popen([exe], shell=False)
                log_accion(user, "abrir_davinci_resolve", exe, "OK")
                return "✅ DaVinci Resolve (Free) iniciado exitosamente."
            except Exception as e:
                return f"❌ Error al iniciar DaVinci: {e}"

    def _accion_edicion(self, args: Dict[str, Any], user: str) -> str:
        import pyautogui

        accion = args.get("accion", "")

        # Enfocar ventana de DaVinci si está abierta (MULTIPLATAFORMA)
        if ES_WINDOWS:
            try:
                import pywinauto
                desktop = pywinauto.Desktop(backend="win32")
                ventanas = [w for w in desktop.windows() if "davinci resolve" in w.window_text().lower()]
                if ventanas:
                    ventanas[0].set_focus()
                    time.sleep(0.3)
            except Exception:
                pass
        elif ES_MAC:
            try:
                subprocess.run(
                    ["osascript", "-e", 'tell application "DaVinci Resolve" to activate'],
                    capture_output=True, timeout=5
                )
                time.sleep(0.5)
            except Exception:
                pass

        # Mapeo de atajos (en macOS, Ctrl → Command)
        if ES_MAC:
            mapeo_atajos = {
                "cortar_clip_cuchilla": lambda: pyautogui.hotkey('command', '\\'),
                "eliminar_espacio_ripple": lambda: pyautogui.hotkey('shift', 'delete'),
                "marcar_punto_in": lambda: pyautogui.press('i'),
                "marcar_punto_out": lambda: pyautogui.press('o'),
                "reproducir_pausar": lambda: pyautogui.press('space'),
                "ir_pagina_edicion": lambda: pyautogui.hotkey('shift', '4'),
                "ir_pagina_color": lambda: pyautogui.hotkey('shift', '6'),
                "ir_pagina_entrega": lambda: pyautogui.hotkey('shift', '8'),
                "ajustar_zoom_timeline": lambda: pyautogui.hotkey('shift', 'z'),
            }
        else:
            mapeo_atajos = {
                "cortar_clip_cuchilla": lambda: pyautogui.hotkey('ctrl', '\\'),
                "eliminar_espacio_ripple": lambda: pyautogui.hotkey('shift', 'delete'),
                "marcar_punto_in": lambda: pyautogui.press('i'),
                "marcar_punto_out": lambda: pyautogui.press('o'),
                "reproducir_pausar": lambda: pyautogui.press('space'),
                "ir_pagina_edicion": lambda: pyautogui.hotkey('shift', '4'),
                "ir_pagina_color": lambda: pyautogui.hotkey('shift', '6'),
                "ir_pagina_entrega": lambda: pyautogui.hotkey('shift', '8'),
                "ajustar_zoom_timeline": lambda: pyautogui.hotkey('shift', 'z'),
            }

        fn = mapeo_atajos.get(accion)
        if not fn:
            return f"Acción '{accion}' no mapeada."

        try:
            fn()
            log_accion(user, "accion_edicion_davinci", accion, "OK")
            return f"✅ Acción de edición '{accion}' ejecutada en DaVinci Resolve."
        except Exception as e:
            return f"❌ Error ejecutando atajo de DaVinci: {e}"

    def _generar_guion(self, args: Dict[str, Any], user: str) -> str:
        nombre = args.get("nombre_proyecto", "proyecto_edicion")
        clips = args.get("clips_con_tiempos", "")
        ruta_archivo = os.path.join(SANDBOX_DIR, f"{nombre}_timeline_plan.txt")

        contenido = f"""# PLAN DE MONTAJE — DAVINCI RESOLVE FREE
Proyecto: {nombre}
Generado por: Reaxy$ Agentic OS

ESTRUCTURA DE CORTES:
{clips}

NOTAS DE FLUJO EN LA VERSIÓN FREE:
1. Asegúrate de estar en la página 'Edit' (Shift+4).
2. Usa 'Shift+Z' para ajustar la vista del timeline.
3. Posiciona el cabezal de reproducción y usa cortar ({"Cmd+\\\\" if ES_MAC else "Ctrl+\\\\"}) para dividir los clips.
"""
        try:
            os.makedirs(SANDBOX_DIR, exist_ok=True)
            with open(ruta_archivo, "w", encoding="utf-8") as f:
                f.write(contenido)
            log_accion(user, "generar_guion_montaje_davinci", nombre, "OK")
            return f"✅ Plan de montaje generado exitosamente en {ruta_archivo}"
        except Exception as e:
            return f"❌ Error generando guion: {e}"
