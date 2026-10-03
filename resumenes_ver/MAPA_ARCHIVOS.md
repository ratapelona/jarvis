# 🗺️ Mapa de Archivos — Guía Rápida

> Referencia rápida de cada archivo del proyecto: qué hace, de dónde importa, y quién lo usa.

---

## 📂 Archivos Activos (Punto de entrada: `main.py`)

### `main.py`
- **Qué hace:** Arranca la app Flet
- **Importa:** `flet`, `ui.app.interfaz_principal`
- **Usado por:** Nadie (es el entry point)
- **Ejecutar:** `python main.py`

---

### `config.py`
- **Qué hace:** Centraliza TODA la configuración del proyecto
- **Importa:** `os`, `dotenv`
- **Usado por:** Todos los módulos de `core/`, `security/`, `data/`, `ui/`
- **Contiene:**
  - URLs y API keys
  - Parámetros de audio
  - Paths de DB
  - Parámetros de seguridad (bcrypt cost, rate limiting)
  - Sandbox + whitelists
  - Dimensiones de UI

---

### `enrutador_llm.py`
- **Qué hace:** Enruta inteligentemente los prompts al modelo especialista adecuado (programación, redacción, embeddings).
- **Importa:** `requests`, `json`, `config`
- **Usado por:** `cerebro.py`, `cerebro_jarvis_prototipo.py`, y componentes de IA.
- **Función clave:** `decidir_modelo_para_tarea()`

---

### `core/ia_engine.py`
- **Qué hace:** Motor principal de IA — construye prompts, streaming de tokens, llama a la API Ollama, inyecta tools de plugins y ejecuta tools nativas
- **Importa:** `config`, `core.sanitizador`, `core.tool_executor`, `core.plugin_manager`, `data.sql_store`, `data.vector_store`
- **Usado por:** `ui/app.py` (via `cola_mensajes.encolar_peticion`)
- **Función clave:** `procesar_peticion_ia()`

### `core/cola_mensajes.py` *(Novedad v2.0 alpha)*
- **Qué hace:** Cola FIFO serializada para proteger la VRAM de la GPU (Regla ESC-09). Despacha inferencias una a una con feedback visual.
- **Importa:** `config`, `queue`, `threading`
- **Usado por:** `ui/app.py`, `core/voice_engine.py`
- **Funciones clave:** `encolar_peticion()`, `iniciar_worker()`, `obtener_tamano_cola()`

### `core/plugin_manager.py` *(Novedad v2.0 alpha)*
- **Qué hace:** Gestor central de plugins y conectores MCP. Carga dinámica, sincronización de catálogo, inyección de tools y ejecución.
- **Importa:** `plugins.base_plugin`, plugins locales (`PptxPlugin`, `BlenderPlugin`, etc.), `json`, `os`
- **Usado por:** `core/ia_engine.py`, `core/agente.py`, `ui/app.py`
- **Funciones clave:** `toggle_plugin()`, `obtener_herramientas_activas()`, `ejecutar_herramienta_plugin()`

### `core/agente.py`
- **Qué hace:** Agente autónomo que controla la pantalla en background con ciclo ReAct
- **Importa:** `config`, `core.tool_executor`, `core.plugin_manager`, `data.sql_store`
- **Usado por:** `core/ia_engine.py` (via `delegar_tarea_larga`)
- **Función clave:** `agente_autonomo_background()`

### `core/tool_executor.py`
- **Qué hace:** Ejecuta herramientas de forma segura (sandbox, whitelists, logging, Playwright CDP, Windows UIA)
- **Importa:** `config`, `data.sql_store`, `pyautogui`, `pywinauto`, `pytesseract`, `PIL`, `fpdf2`, `ddgs`, `playwright`
- **Usado por:** `core/ia_engine.py`, `core/agente.py`
- **Funciones clave:** `abrir_app()`, `crear_archivo_seguro()`, `escanear_pantalla_ocr()`, `mover_y_click()`, etc.

### `core/sanitizador.py`
- **Qué hace:** Sanitiza inputs del usuario en 3 capas (longitud + regex + delimitadores anti prompt injection)
- **Importa:** `config`, `re`
- **Usado por:** `core/ia_engine.py`
- **Funciones clave:** `sanitizar_input()`, `obtener_directiva_sistema_sanitizacion()`

### `core/voice_engine.py`
- **Qué hace:** Wake word, grabación de audio, transcripción con Whisper, TTS con Edge-TTS
- **Importa:** `config`, `core.cola_mensajes`, `openwakeword`, `faster_whisper`, `sounddevice`, `numpy`, `scipy`
- **Usado por:** `ui/app.py`
- **Funciones clave:** `inicializar_sistemas_audio()`, `motor_jarvis()`

---

## 🧩 Biblioteca de Plugins (`plugins/`) *(Novedad v2.0 alpha)*

### `plugins/base_plugin.py`
- **Qué hace:** Interfaz abstracta `BasePlugin` que define el contrato (`plugin_id`, `name`, `get_tools`, `execute`, `is_available`).

### `plugins/catalog.json`
- **Qué hace:** Catálogo maestro con 24 conectores predeterminados (productividad, CAD, 3D, desarrollo, multimedia).

### `plugins/pptx_plugin.py`
- **Qué hace:** Generador y lector de presentaciones PowerPoint (`.pptx`) usando `python-pptx` dentro del sandbox.

### `plugins/blender_plugin.py`
- **Qué hace:** Automatización de Blender 3D mediante scripts `bpy` en modo headless, creación de objetos y renderizado.

### `plugins/davinci_plugin.py`
- **Qué hace:** Automatización de DaVinci Resolve Free mediante atajos de teclado del SO, planes de edición y macros de timeline.

### `plugins/autocad_plugin.py`
- **Qué hace:** Trazado de geometrías, ejecución de scripts `.scr` y automatización ActiveX COM para AutoCAD.

---

### `security/auth.py`
- **Qué hace:** Autenticación (bcrypt), rate limiting, CRUD de usuarios, historial SQL
- **Importa:** `config`, `sqlite3`, `bcrypt`, `hashlib`
- **Usado por:** `data/sql_store.py`, `ui/app.py`
- **Funciones clave:** `validar_login()`, `crear_usuario()`, `inicializar_seguridad()`, `crear_nueva_conversacion()`, etc.

---

### `data/sql_store.py`
- **Qué hace:** Wrapper/re-export de funciones SQL de `security/auth.py`
- **Importa:** `security.auth`
- **Usado por:** `core/ia_engine.py`, `core/agente.py`, `ui/app.py`
- **Razón de existir:** Capa de abstracción para migrar a PostgreSQL sin tocar importadores

### `data/vector_store.py`
- **Qué hace:** Memoria semántica con ChromaDB + poda automática
- **Importa:** `config`, `chromadb`
- **Usado por:** `core/ia_engine.py`
- **Funciones clave:** `guardar_recuerdo()`, `recordar()`

---

### `ui/app.py`
- **Qué hace:** Interfaz Flet completa (login + dashboard + chat streaming + marketplace de plugins con `/plugins`)
- **Importa:** `config`, `security.auth`, `core.ia_engine`, `core.voice_engine`, `core.cola_mensajes`, `core.plugin_manager`, `data.sql_store`
- **Usado por:** `main.py`
- **Función clave:** `interfaz_principal()`

---

## 📂 Archivos Legado (NO usados por `main.py`)

| Archivo | Qué hacía | Reemplazado por |
|---------|-----------|-----------------|
| `cerebro.py` | TODO el sistema en 875 líneas | `core/*` + `plugins/*` + `ui/app.py` |
| `seguridad.py` | Auth con SHA-256 + backdoor | `security/auth.py` |
| `dattabase.py` | ChromaDB sin poda | `data/vector_store.py` |
| `cerebro_jarvis_prototipo.py` | Prototipo anterior | N/A |
| `escchar.py` | Script de prueba de audio | N/A |
| `prueba.py` | Lab de glassmorphism | N/A |

---

## 📂 Otros Archivos del Sistema

| Archivo | Propósito |
|---------|-----------|
| `ARQUITECTURA.md` | Especificación técnica formal Zero-Trust, flujos de secuencia y capas |
| `Reaxy.spec` | Configuración de empaquetado binario PyInstaller para Windows |
| `plugins_config.json` | Almacenamiento persistente de plugins activos y ajustes del usuario |
| `requirements.txt` | Lista de dependencias del proyecto con especificadores multiplataforma |
| `.env` | Variables de entorno opcionales |
| `.gitignore` | Excluye: .env, __pycache__, DBs, audio, output/, build/, dist/, session_store.json |
| `recepcion_jarvis.db` | Base de datos SQLite WAL (generada automáticamente) |

---

## 📊 Grafo de Dependencias entre Módulos (v2.0 alpha)

```
main.py
  └── ui/app.py
        ├── config.py
        ├── security/auth.py ─────── config.py
        ├── core/cola_mensajes.py ── config.py
        ├── core/plugin_manager.py ─ plugins/* ─ config.py
        ├── core/ia_engine.py
        │     ├── config.py
        │     ├── core/sanitizador.py ── config.py
        │     ├── core/plugin_manager.py
        │     ├── core/tool_executor.py
        │     │     ├── config.py
        │     │     └── data/sql_store.py
        │     ├── data/sql_store.py ──── security/auth.py
        │     └── data/vector_store.py ── config.py
        ├── core/voice_engine.py
        │     ├── config.py
        │     └── core/cola_mensajes.py
        └── data/sql_store.py

core/agente.py (llamado dinámicamente desde ia_engine)
  ├── config.py
  ├── core/plugin_manager.py
  ├── core/tool_executor.py
  └── data/sql_store.py
```
