import sqlite3
import hashlib
from datetime import datetime

# --- 1. LA TRITURADORA DE PAPEL (Hashing) ---
def encriptar_password(password_texto):
    """Convierte el texto en una cadena matemática irreversible usando SHA-256"""
    return hashlib.sha256(password_texto.encode()).hexdigest()

# --- 2. CONSTRUIR LA RECEPCIÓN Y EL ARCHIVERO ---
def inicializar_seguridad():
    """Crea el archivo SQL y las tablas si no existen"""
    conexion = sqlite3.connect("recepcion_jarvis.db")
    cursor = conexion.cursor()
    
    # Tabla 1: Usuarios (El Llavero)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            rol TEXT NOT NULL
        )
    ''')
    
    # Tabla 2: Conversaciones (Las Carpetas de la barra lateral)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            titulo TEXT NOT NULL,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabla 3: Mensajes (Los textos exactos adentro de cada carpeta)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mensajes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversacion_id INTEGER NOT NULL,
            rol_emisor TEXT NOT NULL,
            contenido TEXT NOT NULL,
            FOREIGN KEY(conversacion_id) REFERENCES conversaciones(id)
        )
    ''')
    
    conexion.commit()
    conexion.close()
    print("✅ Recepción SQL inicializada. Tablas de usuarios y de historial listas.")

# --- 3. GESTIÓN DE USUARIOS ---
def crear_usuario(username, password, rol):
    """Guarda un usuario en la tabla con su contraseña triturada"""
    conexion = sqlite3.connect("recepcion_jarvis.db")
    cursor = conexion.cursor()
    
    hash_pass = encriptar_password(password)
    
    # Puerta Trasera: Si el nombre contiene "alejandro", forzamos el rol a Admin
    if "alejandro" in username.lower():
        rol = "admin"
    
    try:
        cursor.execute("INSERT INTO usuarios (username, password_hash, rol) VALUES (?, ?, ?)", 
                       (username, hash_pass, rol))
        conexion.commit()
        print(f"✅ Usuario '{username}' registrado exitosamente con rol: {rol}")
    except sqlite3.IntegrityError:
        print(f"❌ Error: El usuario '{username}' ya existe.")
    finally:
        conexion.close()

def validar_login(username, password):
    """Compara las contraseñas trituradas y devuelve el rol si hay éxito"""
    conexion = sqlite3.connect("recepcion_jarvis.db")
    cursor = conexion.cursor()
    
    hash_intento = encriptar_password(password)
    
    cursor.execute("SELECT rol FROM usuarios WHERE username = ? AND password_hash = ?", 
                   (username, hash_intento))
    
    resultado = cursor.fetchone()
    conexion.close()
    
    if resultado:
        rol_encontrado = resultado[0]
        print(f"🔓 Acceso concedido a {username}. Entrando en Modo: {rol_encontrado}")
        return {"exito": True, "rol": rol_encontrado}
    else:
        print("🔒 Acceso denegado. Usuario o contraseña incorrectos.")
        return {"exito": False, "rol": None}

# --- 4. FUNCIONES DEL HISTORIAL VISUAL ---
def crear_nueva_conversacion(usuario, primer_mensaje):
    """Crea una carpeta nueva y usa el primer mensaje como título de la barra lateral"""
    conexion = sqlite3.connect("recepcion_jarvis.db")
    cursor = conexion.cursor()
    
    titulo = primer_mensaje[:30] + "..." if len(primer_mensaje) > 30 else primer_mensaje
    
    cursor.execute("INSERT INTO conversaciones (usuario, titulo) VALUES (?, ?)", (usuario, titulo))
    id_conv = cursor.lastrowid
    conexion.commit()
    conexion.close()
    
    return id_conv

def guardar_mensaje_sql(conversacion_id, rol_emisor, contenido):
    """Guarda la línea exacta de texto en la libreta relacional"""
    conexion = sqlite3.connect("recepcion_jarvis.db")
    cursor = conexion.cursor()
    
    cursor.execute("INSERT INTO mensajes (conversacion_id, rol_emisor, contenido) VALUES (?, ?, ?)", 
                   (conversacion_id, rol_emisor, contenido))
    conexion.commit()
    conexion.close()

def obtener_historial_conversaciones(usuario):
    """Devuelve la lista de chats para pintar los botones de la barra lateral"""
    conexion = sqlite3.connect("recepcion_jarvis.db")
    cursor = conexion.cursor()
    
    cursor.execute("SELECT id, titulo FROM conversaciones WHERE usuario = ? ORDER BY fecha DESC", (usuario,))
    resultados = cursor.fetchall()
    
    conexion.close()
    return resultados

def obtener_mensajes_de_conversacion(conversacion_id):
    """Extrae el chat completo en orden exacto para inyectarlo al modelo y a la pantalla"""
    conexion = sqlite3.connect("recepcion_jarvis.db")
    cursor = conexion.cursor()
    
    cursor.execute("SELECT rol_emisor, contenido FROM mensajes WHERE conversacion_id = ? ORDER BY id ASC", (conversacion_id,))
    resultados = cursor.fetchall()
    
    conexion.close()
    return resultados