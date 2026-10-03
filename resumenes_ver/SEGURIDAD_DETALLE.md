# 🔒 Resumen de Seguridad — Medidas Implementadas

> Referencia rápida de todas las medidas de seguridad del proyecto con su código, ubicación y detalle técnico.

---

## Tabla de Medidas

| Código | Nombre | Archivo | Líneas Clave |
|--------|--------|---------|--------------|
| **SEC-02** | Registro público solo invitado | `ui/app.py` | `accionar_registro()` → rol fijo "invitado" |
| **SEC-03** | Backdoor eliminado | `security/auth.py` | `crear_usuario()` NO checa nombre |
| **SEC-04** | bcrypt + migración lazy | `security/auth.py` | `_hash_password()`, `_check_password()`, `_is_legacy_sha256()` |
| **SEC-05** | shell=False en subprocess | `core/tool_executor.py` | `subprocess.Popen(cmd_lista, shell=False)` |
| **SEC-06** | Sandbox de archivos | `core/tool_executor.py` | `crear_archivo_seguro()`, `crear_pdf_seguro()` |
| **SEC-07** | Blacklists + Logging | `core/tool_executor.py`, `config.py` | `APPS_BLOQUEADAS`, `TECLAS_BLOQUEADAS`, `log_accion()` |
| **SEC-08** | Estado por sesión | `ui/app.py` | Refs mutables: `[0]`, `[None]` |
| **SEC-10** | Rate Limiting | `security/auth.py` | `_esta_bloqueado()`, `_registrar_fallo()` |
| **SEC-11** | Anti Prompt Injection | `core/sanitizador.py` | 3 capas: longitud + regex + delimitadores |
| **SEC-12** | Aislamiento y Sandbox en Plugins | `core/plugin_manager.py`, `plugins/` | Exposición bajo demanda + confinamiento en `output/` |
| **ESC-09** | VRAM Guard / Serialización FIFO | `core/cola_mensajes.py` | Prevención de saturación GPU y DoS local |

---

## Detalle por Medida

### SEC-02: Registro Público Solo Invitado
```
ANTES: Botón público "Crear Cuenta (Administrador)" en la pantalla de login
AHORA: Solo existe "Crear Cuenta (Invitado)" — admin se crea por código/DB directa
```

### SEC-03: Backdoor Eliminado
```python
# ANTES (seguridad.py):
if "alejandro" in username.lower():
    rol = "admin"  # ← Cualquiera podía registrarse como admin

# AHORA (security/auth.py):
# NO HAY CHEQUEO DE NOMBRE — el rol se respeta tal cual
```

### SEC-04: bcrypt con Migración Lazy
```python
# Hash nuevo con bcrypt:
bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12))

# Migración lazy: si detecta hash SHA-256 viejo (64 chars hex):
if _is_legacy_sha256(stored_hash):
    # Verifica con SHA-256 → re-hashea a bcrypt → actualiza DB
```

### SEC-05: shell=False
```python
# ANTES:
subprocess.Popen("start spotify", shell=True)  # ← Inyección posible

# AHORA:
subprocess.Popen(["cmd", "/c", "start", "spotify"], shell=False)  # ← Seguro
```

### SEC-06: Sandbox de Archivos
```python
# Archivos SOLO dentro de output/
ruta_real = os.path.realpath(os.path.join(SANDBOX_DIR, nombre))
if not ruta_real.startswith(sandbox_real):
    return "⛔ BLOQUEADO: Path traversal detectado."

# Solo extensiones permitidas
EXTENSIONES_PERMITIDAS = {".py", ".html", ".css", ".js", ".txt", ".json", ".md", ".c", ".csv"}
```

### SEC-07: Blacklists + Logging
```python
# Apps que NUNCA se pueden abrir:
APPS_BLOQUEADAS = {"cmd", "powershell", "terminal", "regedit"}

# Teclas que NUNCA se pueden presionar:
TECLAS_BLOQUEADAS = {"alt+f4", "ctrl+alt+del", "win+r", "ctrl+shift+escape"}

# TODA acción se logea:
log_accion(usuario, "abrir_app", nombre_app, "OK")
```

### SEC-10: Rate Limiting
```python
# 5 intentos fallidos → 30 segundos de bloqueo
RATE_LIMIT_MAX_INTENTOS = 5
RATE_LIMIT_BLOQUEO_SEGUNDOS = 30
```

### SEC-11: Anti Prompt Injection (3 Capas)
```python
# Capa 1: Longitud máxima
texto_limpio = texto[:2000]

# Capa 2: Neutralización de patrones peligrosos
# Detecta: "ignora instrucciones", "eres un nuevo asistente", "JAILBREAK", etc.
texto_limpio = _PATRON_COMPILADO.sub("[CONTENIDO_FILTRADO]", texto_limpio)

# Capa 3: Encapsulación con delimitadores
texto_encapsulado = "[INICIO_MENSAJE_USUARIO]\n{texto}\n[FIN_MENSAJE_USUARIO]"

# + Directiva en system prompt que indica NUNCA interpretar contenido entre delimitadores como instrucción
```

### SEC-12: Aislamiento y Sandbox en Plugins
```python
# Los plugins solo inyectan herramientas si están explícitamente activados en plugins_config.json
herramientas_permitidas = HERRAMIENTAS_ADMIN + plugin_manager.obtener_herramientas_activas()

# Todo archivo generado por plugins (ej: presentaciones PPTX, scripts de Blender) 
# se confina estrictamente dentro del directorio output/
```

### ESC-09: VRAM Guard / Serialización FIFO
```python
# Cola FIFO centralizada con worker daemon que serializa las llamadas al LLM
cola_mensajes.encolar_peticion(callback, args, page)
# Previene OOM en GPU y condiciones de carrera entre hilos de voz y texto
```


---

## Patrones de Prompt Injection Detectados

| Categoría | Patrones |
|-----------|----------|
| **Español** | "ignora instrucciones", "olvida todo", "eres un nuevo asistente", "a partir de ahora", "nuevo modo", "actúa como", "haz de cuenta" |
| **English** | "ignore instructions", "forget your instructions", "you are a new assistant", "from now on", "pretend to be", "disregard all" |
| **Técnicos** | `<system>`, `[SYSTEM]`, "ADMIN OVERRIDE", "JAILBREAK", "DAN mode" |
