"""
security/auth.py — Autenticación con bcrypt + Rate Limiting

SEC-04: SHA-256 → bcrypt (salt automático, cost factor configurable)
SEC-03: Backdoor por nombre eliminado
SEC-10: Rate limiting (5 intentos, 30 seg de bloqueo)
Migración lazy: detecta hashes SHA-256 viejos y los rehashea al login exitoso.
"""
import sqlite3
import bcrypt
import hashlib
import threading
from datetime import datetime, timedelta

from config import (
    DB_PATH,
    BCRYPT_COST,
    RATE_LIMIT_MAX_INTENTOS,
    RATE_LIMIT_BLOQUEO_SEGUNDOS,
)

# =============================================================================
# Connection pooling básico con thread-local storage
# =============================================================================
_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """Obtiene una conexión SQLite con WAL mode, reutilizando por thread."""
    if not hasattr(_local, "conn") or _local.conn is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        _local.conn = conn
    return _local.conn


# =============================================================================
# 1. Hashing con bcrypt
# =============================================================================
def _hash_password(password: str) -> str:
    """Genera un hash bcrypt con salt automático."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_COST)).decode("utf-8")


def _check_password(password: str, hashed: str) -> bool:
    """Verifica una contraseña contra su hash bcrypt."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def _is_legacy_sha256(hashed: str) -> bool:
    """Detecta si un hash es SHA-256 (hex, 64 chars) en vez de bcrypt ($2b$...)."""
    return len(hashed) == 64 and not hashed.startswith("$2")


def _check_legacy_sha256(password: str, hashed: str) -> bool:
    """Verifica contra un hash SHA-256 viejo."""
    return hashlib.sha256(password.encode()).hexdigest() == hashed


# =============================================================================
# 2. Inicialización de tablas
# =============================================================================
def inicializar_seguridad():
    """Crea las tablas si no existen. Incluye la tabla de rate limiting."""
    conn = _get_conn()
    cursor = conn.cursor()

    # Tabla: Usuarios
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            rol TEXT NOT NULL
        )
    """)

    # Tabla: Conversaciones (carpetas del sidebar)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            titulo TEXT NOT NULL,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tabla: Mensajes (textos dentro de cada conversación)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mensajes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversacion_id INTEGER NOT NULL,
            rol_emisor TEXT NOT NULL,
            contenido TEXT NOT NULL,
            FOREIGN KEY(conversacion_id) REFERENCES conversaciones(id)
        )
    """)

    # Tabla: Intentos de login (SEC-10: Rate Limiting)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS intentos_login (
            username TEXT PRIMARY KEY,
            intentos INTEGER DEFAULT 0,
            bloqueado_hasta DATETIME
        )
    """)

    # Tabla: Log de acciones del agente (SEC-07: Auditoría)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS log_acciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            accion TEXT NOT NULL,
            argumentos TEXT,
            resultado TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    print("✅ Recepción SQL inicializada (WAL mode, bcrypt, rate limiting).")


# =============================================================================
# 3. Rate Limiting
# =============================================================================
def _esta_bloqueado(username: str) -> bool:
    """Verifica si el usuario está bloqueado por intentos fallidos."""
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT intentos, bloqueado_hasta FROM intentos_login WHERE username = ?",
        (username,),
    )
    row = cursor.fetchone()
    if row is None:
        return False

    intentos, bloqueado_hasta_str = row
    if bloqueado_hasta_str:
        bloqueado_hasta = datetime.fromisoformat(bloqueado_hasta_str)
        if datetime.now() < bloqueado_hasta:
            return True
        # Si ya pasó el bloqueo, reseteamos
        cursor.execute(
            "UPDATE intentos_login SET intentos = 0, bloqueado_hasta = NULL WHERE username = ?",
            (username,),
        )
        conn.commit()
    return False


def _registrar_fallo(username: str):
    """Registra un intento fallido. Bloquea si se excede el límite."""
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT intentos FROM intentos_login WHERE username = ?", (username,)
    )
    row = cursor.fetchone()

    if row is None:
        cursor.execute(
            "INSERT INTO intentos_login (username, intentos) VALUES (?, 1)",
            (username,),
        )
    else:
        nuevos_intentos = row[0] + 1
        if nuevos_intentos >= RATE_LIMIT_MAX_INTENTOS:
            bloqueado_hasta = datetime.now() + timedelta(seconds=RATE_LIMIT_BLOQUEO_SEGUNDOS)
            cursor.execute(
                "UPDATE intentos_login SET intentos = ?, bloqueado_hasta = ? WHERE username = ?",
                (nuevos_intentos, bloqueado_hasta.isoformat(), username),
            )
        else:
            cursor.execute(
                "UPDATE intentos_login SET intentos = ? WHERE username = ?",
                (nuevos_intentos, username),
            )
    conn.commit()


def _resetear_intentos(username: str):
    """Resetea el contador de intentos al hacer login exitoso."""
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM intentos_login WHERE username = ?", (username,)
    )
    conn.commit()


# =============================================================================
# 4. Gestión de Usuarios
# =============================================================================
def crear_usuario(username: str, password: str, rol: str = "invitado"):
    """
    Registra un usuario con hash bcrypt. 
    SEC-03: NO hay backdoor por nombre. El rol se respeta tal cual.
    """
    conn = _get_conn()
    cursor = conn.cursor()

    password_hash = _hash_password(password)

    try:
        cursor.execute(
            "INSERT INTO usuarios (username, password_hash, rol) VALUES (?, ?, ?)",
            (username, password_hash, rol),
        )
        conn.commit()
        print(f"✅ Usuario '{username}' registrado con rol: {rol}")
    except sqlite3.IntegrityError:
        print(f"❌ Error: El usuario '{username}' ya existe.")


def validar_login(username: str, password: str) -> dict:
    """
    Valida credenciales con bcrypt + rate limiting.
    Migración lazy: si detecta hash SHA-256 viejo, lo rehashea a bcrypt.
    """
    # Rate limiting check
    if _esta_bloqueado(username):
        print(f" Usuario '{username}' bloqueado por exceso de intentos.")
        return {
            "exito": False,
            "rol": None,
            "mensaje": f"Cuenta bloqueada. Intenta en {RATE_LIMIT_BLOQUEO_SEGUNDOS} segundos.",
        }

    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT password_hash, rol FROM usuarios WHERE username = ?", (username,)
    )
    row = cursor.fetchone()

    if row is None:
        _registrar_fallo(username)
        print(" Acceso denegado. Usuario no encontrado.")
        return {"exito": False, "rol": None, "mensaje": "Credenciales inválidas."}

    stored_hash, rol = row

    # Migración lazy: detectar SHA-256 y rehashear
    if _is_legacy_sha256(stored_hash):
        if _check_legacy_sha256(password, stored_hash):
            # Rehashear a bcrypt
            new_hash = _hash_password(password)
            cursor.execute(
                "UPDATE usuarios SET password_hash = ? WHERE username = ?",
                (new_hash, username),
            )
            conn.commit()
            print(f" Hash migrado de SHA-256 a bcrypt para '{username}'.")
            _resetear_intentos(username)
            return {"exito": True, "rol": rol, "mensaje": "Login exitoso (hash migrado)."}
        else:
            _registrar_fallo(username)
            print(" Acceso denegado. Contraseña incorrecta.")
            return {"exito": False, "rol": None, "mensaje": "Credenciales inválidas."}

    # Verificación bcrypt normal
    if _check_password(password, stored_hash):
        _resetear_intentos(username)
        print(f" Acceso concedido a {username}. Modo: {rol}")
        return {"exito": True, "rol": rol, "mensaje": "Login exitoso."}
    else:
        _registrar_fallo(username)
        print(" Acceso denegado. Contraseña incorrecta.")
        return {"exito": False, "rol": None, "mensaje": "Credenciales inválidas."}


# =============================================================================
# 5. Historial de Conversaciones (misma API que seguridad.py original)
# =============================================================================
def crear_nueva_conversacion(usuario: str, primer_mensaje: str) -> int:
    """Crea una nueva conversación y devuelve su ID."""
    conn = _get_conn()
    cursor = conn.cursor()
    titulo = primer_mensaje[:30] + "..." if len(primer_mensaje) > 30 else primer_mensaje
    cursor.execute(
        "INSERT INTO conversaciones (usuario, titulo) VALUES (?, ?)",
        (usuario, titulo),
    )
    id_conv = cursor.lastrowid
    conn.commit()
    return id_conv


def guardar_mensaje_sql(conversacion_id: int, rol_emisor: str, contenido: str):
    """Guarda un mensaje en el historial exacto."""
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO mensajes (conversacion_id, rol_emisor, contenido) VALUES (?, ?, ?)",
        (conversacion_id, rol_emisor, contenido),
    )
    conn.commit()


def obtener_historial_conversaciones(usuario: str) -> list:
    """Devuelve la lista de conversaciones para pintar el sidebar."""
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, titulo FROM conversaciones WHERE usuario = ? ORDER BY fecha DESC",
        (usuario,),
    )
    return cursor.fetchall()


def obtener_mensajes_de_conversacion(conversacion_id: int) -> list:
    """Extrae mensajes en orden para inyectar al modelo y a la UI."""
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT rol_emisor, contenido FROM mensajes WHERE conversacion_id = ? ORDER BY id ASC",
        (conversacion_id,),
    )
    return cursor.fetchall()


# =============================================================================
# 6. Log de acciones del agente (SEC-07: Auditoría)
# =============================================================================
def log_accion(usuario: str, accion: str, argumentos: str = "", resultado: str = ""):
    """Registra una acción del agente para auditoría."""
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO log_acciones (usuario, accion, argumentos, resultado) VALUES (?, ?, ?, ?)",
        (usuario, accion, argumentos, resultado),
    )
    conn.commit()
