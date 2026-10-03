"""
plugins/autocad_plugin.py — Plugin de AutoCAD Design Suite — MULTIPLATAFORMA

Permite interactuar con Autodesk AutoCAD mediante:
1. Interfaz COM ActiveX nativa (win32com) si AutoCAD está en ejecución EN WINDOWS.
2. Generación de Scripts de Dibujo (.scr) y archivos de intercambio técnico en el sandbox (TODOS los OS).

En macOS/Linux: AutoCAD no tiene COM, pero se pueden generar .scr y .dxf
para importar en cualquier versión de AutoCAD o en alternativas como LibreCAD/FreeCAD.
"""
import os
import sys
from typing import Dict, Any, List

from plugins.base_plugin import BasePlugin
from config import SANDBOX_DIR, ES_WINDOWS
from data.sql_store import log_accion


class AutocadPlugin(BasePlugin):
    @property
    def plugin_id(self) -> str:
        return "autocad_suite"

    @property
    def name(self) -> str:
        return "AutoCAD Design Suite"

    @property
    def description(self) -> str:
        return "Automatización de dibujo técnico, trazo de geometrías y generación de planos para AutoCAD."

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "dibujar_geometria_autocad",
                    "description": "Dibuja entidades geométricas (líneas, círculos, textos) en la sesión activa de AutoCAD mediante la API COM de Windows. En macOS/Linux genera un script .scr equivalente.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entidad": {
                                "type": "string",
                                "enum": ["linea", "circulo", "texto", "rectangulo"],
                                "description": "Tipo de entidad a dibujar."
                            },
                            "parametros": {
                                "type": "string",
                                "description": "JSON con coordenadas: para linea {\"x1\":0, \"y1\":0, \"x2\":10, \"y2\":10}; para circulo {\"centro_x\":0, \"centro_y\":0, \"radio\":5}; para texto {\"x\":0, \"y\":0, \"texto\":\"Plano 1\"}"
                            }
                        },
                        "required": ["entidad", "parametros"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generar_script_autocad_scr",
                    "description": "Crea un archivo de script (.scr) de AutoCAD con secuencias de comandos de dibujo automáticas para ejecutar con el comando SCRIPT dentro de AutoCAD.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "nombre_archivo": {
                                "type": "string",
                                "description": "Nombre del archivo .scr (ej: 'plano_cimiento.scr')."
                            },
                            "comandos_autocad": {
                                "type": "string",
                                "description": "Comandos de AutoCAD línea por línea (ej: LINE 0,0 10,0 \\n CIRCLE 5,5 2 \\n ZOOM E \\n)"
                            }
                        },
                        "required": ["nombre_archivo", "comandos_autocad"]
                    }
                }
            }
        ]

    def execute(self, tool_name: str, arguments: Dict[str, Any], user: str = "") -> str:
        if tool_name == "dibujar_geometria_autocad":
            return self._dibujar(arguments, user)
        elif tool_name == "generar_script_autocad_scr":
            return self._generar_script_scr(arguments, user)
        return f"Herramienta '{tool_name}' no soportada por AutocadPlugin."

    def _dibujar(self, args: Dict[str, Any], user: str) -> str:
        import json
        entidad = args.get("entidad", "")
        params_raw = args.get("parametros", "{}")
        try:
            params = json.loads(params_raw) if isinstance(params_raw, str) else params_raw
        except Exception:
            params = {}

        if ES_WINDOWS:
            return self._dibujar_com_windows(entidad, params, user)
        else:
            # macOS/Linux: generar un script .scr como fallback inteligente
            return self._dibujar_fallback_scr(entidad, params, user)

    def _dibujar_com_windows(self, entidad: str, params: dict, user: str) -> str:
        """Dibujo directo via COM ActiveX (solo Windows)."""
        try:
            import win32com.client
            # Conectar a la instancia abierta de AutoCAD
            acad = win32com.client.GetActiveObject("AutoCAD.Application")
            doc = acad.ActiveDocument
            model = doc.ModelSpace

            if entidad == "linea":
                p1 = win32com.client.VARIANT(win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, [params.get("x1", 0.0), params.get("y1", 0.0), 0.0])
                p2 = win32com.client.VARIANT(win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, [params.get("x2", 10.0), params.get("y2", 10.0), 0.0])
                model.AddLine(p1, p2)
                log_accion(user, "autocad_dibujar", f"linea", "OK")
                return "✅ Línea dibujada exitosamente en el espacio modelo de AutoCAD."

            elif entidad == "circulo":
                centro = win32com.client.VARIANT(win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, [params.get("centro_x", 0.0), params.get("centro_y", 0.0), 0.0])
                radio = float(params.get("radio", 5.0))
                model.AddCircle(centro, radio)
                log_accion(user, "autocad_dibujar", f"circulo r={radio}", "OK")
                return f"✅ Círculo con radio {radio} dibujado exitosamente en AutoCAD."

            elif entidad == "texto":
                pos = win32com.client.VARIANT(win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, [params.get("x", 0.0), params.get("y", 0.0), 0.0])
                txt = params.get("texto", "Reaxy$ CAD")
                alt = float(params.get("altura", 2.5))
                model.AddText(txt, pos, alt)
                log_accion(user, "autocad_dibujar", f"texto '{txt}'", "OK")
                return f"✅ Texto '{txt}' insertado en AutoCAD."

            return f"Entidad '{entidad}' procesada."

        except Exception as e:
            # Fallback amigable si AutoCAD no está corriendo en COM
            return (
                f"ℹ️ No se detectó una sesión abierta de AutoCAD conectada a la API COM ({e}). "
                "Sugerencia: puedes usar la herramienta 'generar_script_autocad_scr' para generar un archivo .scr que puedes cargar instantáneamente en cualquier versión de AutoCAD."
            )

    def _dibujar_fallback_scr(self, entidad: str, params: dict, user: str) -> str:
        """Genera un .scr con los comandos equivalentes (macOS/Linux fallback)."""
        comandos = ""
        if entidad == "linea":
            x1, y1 = params.get("x1", 0), params.get("y1", 0)
            x2, y2 = params.get("x2", 10), params.get("y2", 10)
            comandos = f"LINE\n{x1},{y1}\n{x2},{y2}\n\n"
        elif entidad == "circulo":
            cx, cy = params.get("centro_x", 0), params.get("centro_y", 0)
            radio = params.get("radio", 5)
            comandos = f"CIRCLE\n{cx},{cy}\n{radio}\n"
        elif entidad == "texto":
            x, y = params.get("x", 0), params.get("y", 0)
            txt = params.get("texto", "Reaxy$ CAD")
            alt = params.get("altura", 2.5)
            comandos = f"TEXT\n{x},{y}\n{alt}\n0\n{txt}\n"
        elif entidad == "rectangulo":
            x1, y1 = params.get("x1", 0), params.get("y1", 0)
            x2, y2 = params.get("x2", 10), params.get("y2", 10)
            comandos = f"RECTANG\n{x1},{y1}\n{x2},{y2}\n"
        else:
            return f"Entidad '{entidad}' no soportada en modo script."

        # Guardar como .scr automáticamente
        nombre = f"auto_{entidad}.scr"
        return self._generar_script_scr({"nombre_archivo": nombre, "comandos_autocad": comandos}, user)

    def _generar_script_scr(self, args: Dict[str, Any], user: str) -> str:
        nombre = args.get("nombre_archivo", "plano.scr")
        if not nombre.lower().endswith(".scr"):
            nombre += ".scr"

        comandos = args.get("comandos_autocad", "")
        os.makedirs(SANDBOX_DIR, exist_ok=True)
        ruta_real = os.path.realpath(os.path.join(SANDBOX_DIR, nombre))
        if not ruta_real.startswith(os.path.realpath(SANDBOX_DIR)):
            return "⛔ BLOQUEADO: Path traversal detectado."

        try:
            with open(ruta_real, "w", encoding="utf-8") as f:
                f.write(comandos)
            log_accion(user, "generar_script_autocad_scr", nombre, "OK")
            return f"✅ Script de AutoCAD generado exitosamente en: {ruta_real}\nPara ejecutarlo en AutoCAD escribe en su barra de comandos: SCRIPT y selecciona este archivo."
        except Exception as e:
            return f"❌ Error generando script de AutoCAD: {e}"
