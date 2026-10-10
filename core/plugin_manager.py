"""
core/plugin_manager.py — Gestor Central de Plugins y Conectores MCP

Responsabilidades:
1. Carga y sincronización de catálogo de plugins (plugins/catalog.json + plugins_config.json).
2. Activación / Desactivación dinámica desde la UI (sin reiniciar la app).
3. Registro de nuevos plugins / servidores MCP personalizados desde la UI.
4. Inyección dinámica de herramientas al LLM (evitando saturación de contexto).
5. Despacho y ejecución segura de herramientas.
"""
import os
import json
from typing import Dict, Any, List, Optional

from plugins.base_plugin import BasePlugin
from plugins.pptx_plugin import PptxPlugin
from plugins.blender_plugin import BlenderPlugin
from plugins.davinci_plugin import DavinciPlugin
from plugins.autocad_plugin import AutocadPlugin
from plugins.mcp_stdio_plugin import McpStdioPlugin

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins_config.json")
CATALOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins", "catalog.json")


class PluginManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PluginManager, cls).__new__(cls)
            cls._instance._inicializado = False
        return cls._instance

    def __init__(self):
        if self._inicializado:
            return
        self._inicializado = True
        self.plugins_locales: Dict[str, BasePlugin] = {}
        self.config_estado: Dict[str, Any] = {}
        self._cargar_configuracion()
        self._registrar_plugins_locales()

    def _cargar_configuracion(self):
        """Carga la configuración persistente o inicializa desde el catálogo base."""
        # 1. Leer catálogo maestro
        catalogo_base = []
        if os.path.exists(CATALOG_PATH):
            try:
                with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                    catalogo_base = json.load(f)
            except Exception as e:
                print(f"[PluginManager] Error leyendo catálogo: {e}")

        # 2. Leer plugins_config.json existente o crear nuevo
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    self.config_estado = json.load(f)
            except Exception:
                self.config_estado = {}
        else:
            self.config_estado = {}

        if "plugins" not in self.config_estado:
            self.config_estado["plugins"] = {}

        # Sincronizar con catálogo maestro
        for item in catalogo_base:
            pid = item["id"]
            if pid not in self.config_estado["plugins"]:
                self.config_estado["plugins"][pid] = {
                    "id": pid,
                    "nombre": item["nombre"],
                    "categoria": item.get("categoria", "General"),
                    "tipo": item.get("tipo", "mcp_connector"),
                    "plataformas": item.get("plataformas", ""),
                    "uso": item.get("uso", ""),
                    "ideal_para": item.get("ideal_para", ""),
                    "recomendado": item.get("recomendado", False),
                    "instalado": item.get("instalado", False),
                    "activo": item.get("activo", False),
                    "config": {}
                }

        self._guardar_config()

    def _guardar_config(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config_estado, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[PluginManager] Error guardando config: {e}")

    def _registrar_plugins_locales(self):
        """Instancia los plugins de Python locales instalados."""
        conf_davinci = self.config_estado["plugins"].get("davinci_resolve_free", {}).get("config", {})
        conf_blender = self.config_estado["plugins"].get("blender_3d", {}).get("config", {})

        self.plugins_locales["pptx_generator"] = PptxPlugin()
        self.plugins_locales["davinci_resolve_free"] = DavinciPlugin(custom_path=conf_davinci.get("exe_path", ""))
        self.plugins_locales["blender_3d"] = BlenderPlugin(custom_path=conf_blender.get("exe_path", ""))
        self.plugins_locales["autocad_suite"] = AutocadPlugin()

        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for pid, meta in self.config_estado.get("plugins", {}).items():
            if meta.get("tipo") == "mcp_stdio":
                self.plugins_locales[pid] = McpStdioPlugin(
                    plugin_id=pid,
                    name=meta.get("nombre", pid),
                    description=meta.get("uso", "Servidor MCP por stdio."),
                    config=meta.get("config", {}),
                    project_root=project_root,
                )

    # =========================================================================
    # Métodos Públicos para la UI y el Motor IA
    # =========================================================================
    def obtener_catalogo(self) -> List[Dict[str, Any]]:
        """Retorna lista de todos los plugins y su estado actual para pintar en la UI."""
        return list(self.config_estado.get("plugins", {}).values())

    def toggle_plugin(self, plugin_id: str, activo: bool):
        """Activa o desactiva un plugin en caliente."""
        if plugin_id in self.config_estado.get("plugins", {}):
            self.config_estado["plugins"][plugin_id]["activo"] = activo
            self.config_estado["plugins"][plugin_id]["instalado"] = True
            self._guardar_config()
            print(f"[PluginManager] Plugin '{plugin_id}' ahora activo={activo}")

    def guardar_config_plugin(self, plugin_id: str, config: Dict[str, Any]):
        """Actualiza parámetros de configuración (ej: rutas, tokens)."""
        if plugin_id in self.config_estado.get("plugins", {}):
            self.config_estado["plugins"][plugin_id]["config"].update(config)
            self._guardar_config()
            self._registrar_plugins_locales()

    def agregar_plugin_personalizado(self, datos: Dict[str, Any]) -> str:
        """
        Permite al usuario registrar un nuevo plugin o conector MCP desde la UI.
        datos debe incluir: id, nombre, categoria, uso, tipo, comando_mcp (opcional)
        """
        pid = datos.get("id", "").strip().lower().replace(" ", "_")
        if not pid:
            return "ID de plugin inválido."

        self.config_estado["plugins"][pid] = {
            "id": pid,
            "nombre": datos.get("nombre", pid),
            "categoria": datos.get("categoria", "Personalizado"),
            "tipo": datos.get("tipo", "mcp_custom"),
            "plataformas": datos.get("plataformas", "Reaxy$ MCP"),
            "uso": datos.get("uso", "Plugin personalizado"),
            "ideal_para": datos.get("ideal_para", "Extensión de usuario"),
            "recomendado": False,
            "instalado": True,
            "activo": True,
            "config": datos.get("config", {})
        }
        self._guardar_config()
        return f"✅ Plugin '{datos.get('nombre')}' agregado y activado con éxito."

    def obtener_herramientas_activas(self) -> List[Dict[str, Any]]:
        """
        Retorna la lista unificada de herramientas para el LLM
        SOLO de los plugins que el usuario tiene ACTIVADOS.
        """
        herramientas = []
        for pid, meta in self.config_estado.get("plugins", {}).items():
            if meta.get("activo", False):
                # Si es un plugin local implementado en Python
                if pid in self.plugins_locales:
                    plugin_inst = self.plugins_locales[pid]
                    try:
                        herramientas.extend(plugin_inst.get_tools())
                    except Exception as e:
                        print(f"[PluginManager] Error cargando tools de {pid}: {e}")
                # Si es un conector MCP en desarrollo/configurado
                elif meta.get("tipo") in ["mcp_connector", "mcp_custom"]:
                    # Añadir herramienta representativa de consulta al conector
                    herramientas.append({
                        "type": "function",
                        "function": {
                            "name": f"conector_{pid}",
                            "description": f"Envía una consulta u orden al conector de {meta.get('nombre')}: {meta.get('uso')}",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "accion": {"type": "string", "description": "Acción a realizar en el servicio."},
                                    "parametros": {"type": "string", "description": "Detalles o consulta específica."}
                                },
                                "required": ["accion"]
                            }
                        }
                    })
        return herramientas

    def puede_ejecutar(self, tool_name: str) -> bool:
        """Verifica si la herramienta corresponde a algún plugin activo."""
        for pid, meta in self.config_estado.get("plugins", {}).items():
            if meta.get("activo", False):
                if pid in self.plugins_locales:
                    tools = self.plugins_locales[pid].get_tools()
                    for t in tools:
                        if t.get("function", {}).get("name") == tool_name:
                            return True
                elif tool_name == f"conector_{pid}":
                    return True
        return False

    def ejecutar_herramienta_plugin(self, tool_name: str, arguments: Dict[str, Any], user: str = "") -> str:
        """Enruta y ejecuta la herramienta en el plugin correspondiente."""
        # 1. Buscar en plugins locales
        for pid, meta in self.config_estado.get("plugins", {}).items():
            if meta.get("activo", False) and pid in self.plugins_locales:
                plugin = self.plugins_locales[pid]
                for t in plugin.get_tools():
                    if t.get("function", {}).get("name") == tool_name:
                        return plugin.execute(tool_name, arguments, user)

        # 2. Manejar conectores MCP
        for pid, meta in self.config_estado.get("plugins", {}).items():
            if meta.get("activo", False) and tool_name == f"conector_{pid}":
                accion = arguments.get("accion", "")
                params = arguments.get("parametros", "")
                # Retorno de estado del conector
                return (
                    f"🔌 [Conector {meta.get('nombre')}]: Recibida orden '{accion}'. "
                    f"El conector está activo en Reaxy$. Configuración actual: {json.dumps(meta.get('config', {}))}. "
                    f"Detalle procesado: '{params}'."
                )

        return f"Herramienta de plugin '{tool_name}' no encontrada o inactiva."


# Instancia singleton accesible globalmente
plugin_manager = PluginManager()
