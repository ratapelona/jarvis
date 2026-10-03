"""
plugins/base_plugin.py — Interfaz Base de Plugins para Reaxy$

Todo plugin implementa:
- get_tools(): retorna lista de herramientas en formato OpenAI Function Calling
- execute(tool_name, arguments, user): ejecuta la herramienta de forma segura
- is_available(): verifica si las dependencias o ejecutables están listos
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List


class BasePlugin(ABC):
    @property
    @abstractmethod
    def plugin_id(self) -> str:
        """Identificador único del plugin (ej: 'pptx_generator')."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre legible del plugin."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Descripción corta de lo que hace."""
        pass

    @abstractmethod
    def get_tools(self) -> List[Dict[str, Any]]:
        """Retorna las especificaciones de herramientas para el LLM."""
        pass

    @abstractmethod
    def execute(self, tool_name: str, arguments: Dict[str, Any], user: str = "") -> str:
        """Ejecuta una herramienta del plugin."""
        pass

    def is_available(self) -> bool:
        """Verifica si el plugin está en condiciones de operar."""
        return True
