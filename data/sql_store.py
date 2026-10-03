"""
data/sql_store.py — Capa de datos SQL (ESC-02)

Wrapper sobre security.auth para operaciones de datos SQL.
Preparado para migración a PostgreSQL (cambiar import y connection string).

WAL mode activado para concurrencia.
Connection pooling via thread-local storage (en security/auth.py).
"""
from security.auth import (
    crear_nueva_conversacion,
    guardar_mensaje_sql,
    obtener_historial_conversaciones,
    obtener_mensajes_de_conversacion,
    log_accion,
)

# Re-exportamos las funciones de datos para que el resto del proyecto
# importe desde data.sql_store en vez de security.auth directamente.
# Esto permite cambiar la implementación (ej: PostgreSQL) sin tocar los importadores.

__all__ = [
    "crear_nueva_conversacion",
    "guardar_mensaje_sql",
    "obtener_historial_conversaciones",
    "obtener_mensajes_de_conversacion",
    "log_accion",
]
