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
- **Importa:** `os`, `sys`, `dotenv`
- **Usado por:** Todos los módulos de `core/`, `security/`, `data/`, `ui/`
- **Contiene:**
  - URLs de Ollama (`/api/chat`, `/api/tags`, `/api/ps`)
  - Modelos: `MODELO_RAPIDO = "qwen3.5:9b"`, `MODELO_PESADO = "gpt-oss:20b"`
  - Configuración fija de inferencia: `NUM_CTX = 8192`, `KEEP_ALIVE_RESIDENTE = -1`, `OLLAMA_OPTIONS`
  - Parámetros de audio y Whisper en CPU (`device="cpu"`, `compute_type="int8"`)
  - Paths de DB y ChromaDB
  - Parámetros de seguridad (bcrypt cost, rate limiting)
  - Sandbox + whitelists y blacklists por plataforma
  - Dimensiones de UI

---

### `enrutador_llm.py`
- **Qué hace:** Enrutador determinista sin llamadas a LLM ni modelos especialistas.
- **Importa:** `config` (`MODELO_RAPIDO`, `MODELO_PESADO`)
- **Usado por:** Módulos de orquestación de inferencia.
- **Función clave:** `decidir_modelo_para_tarea()` (Rápido por defecto, Pesado solo para delegar tarea larga).

---

### `core/ia_engine.py`
- **Qué hace:** Motor interactivo de IA — construye prompts, canaliza el streaming hacia la UI, delega inferencias en `cola_mensajes.solicitar_inferencia_ollama()` (`qwen3.5:9b`), inyecta tools de plugins y despacha tareas largas hacia la cola serializada.
- **Importa:** `config`, `core.sanitizador`, `core.tool_executor`, `core.plugin_manager`, `core.cola_mensajes`, `data.sql_store`
- **Usado por:** `ui/app.py` (via `cola_mensajes.encolar_peticion`)
- **Función clave:** `procesar_peticion_ia()`

### `core/cola_mensajes.py` *(Actualizado v2.1)*
- **Qué hace:** Orquestador central de inferencia y VRAM Guard (Regla ESC-09). Gestiona la cola FIFO, el precalentamiento del modelo residente, las transiciones atómicas al Modo Pesado (`gpt-oss:20b`), avisos TTS de entrada/salida y ofrece el cliente unificado `solicitar_inferencia_ollama()`.
- **Importa:** `config`, `queue`, `threading`, `requests`, `pygame`, `core.tool_executor`
- **Usado por:** `ui/app.py`, `core/voice_engine.py`, `core/ia_engine.py`, `core/agente.py`
- **Funciones clave:** `encolar_peticion()`, `encolar_tarea_pesada()`, `solicitar_inferencia_ollama()`, `precalentar_modelo_residente()`, `esta_en_modo_pesado()`, `cancelar_tarea_pesada()`

### `core/plugin_manager.py` *(Novedad v2.0 alpha)*
- **Qué hace:** Gestor central de plugins y conectores MCP. Carga dinámica, sincronización de catálogo, inyección de tools y ejecución.
- **Importa:** `plugins.base_plugin`, plugins locales (`PptxPlugin`, `BlenderPlugin`, etc.), `json`, `os`
- **Usado por:** `core/ia_engine.py`, `core/agente.py`, `ui/app.py`
- **Funciones clave:** `toggle_plugin()`, `obtener_herramientas_activas()`, `ejecutar_herramienta_plugin()`

### `core/agente.py` *(Actualizado v2.1)*
- **Qué hace:** Agente autónomo para Modo Pesado (`gpt-oss:20b`, reasoning "low"). Ejecuta ciclos ReAct con guardarraíles, sin llamar a Ollama directamente (canaliza por `cola_mensajes.solicitar_inferencia_ollama()`) y con soporte para cancelación externa.
- **Importa:** `config`, `core.tool_executor`, `core.plugin_manager`, `core.cola_mensajes`, `data.sql_store`
- **Usado por:** `core/cola_mensajes.py` (via `_operacion_serializada_modo_pesado`)
- **Función clave:** `agente_autonomo_background()`

### `core/tool_executor.py`
- **Qué hace:** Ejecuta herramientas de forma segura (sandbox, whitelists, logging, Playwright CDP, Windows UIA, TTS con shell=False)
- **Importa:** `config`, `data.sql_store`, `pyautogui`, `pywinauto`, `pytesseract`, `PIL`, `fpdf2`, `ddgs`, `playwright`
- **Usado por:** `core/ia_engine.py`, `core/agente.py`, `core/cola_mensajes.py`
- **Funciones clave:** `abrir_app()`, `crear_archivo_seguro()`, `sintetizar_voz()`, `escanear_pantalla_ocr()`, `mover_y_click()`, etc.

### `core/sanitizador.py`
- **Qué hace:** Sanitiza inputs del usuario en 3 capas (longitud + regex + delimitadores anti prompt injection)
- **Importa:** `config`, `re`
- **Usado por:** `core/ia_engine.py`
- **Funciones clave:** `sanitizar_input()`, `obtener_directiva_sistema_sanitizacion()`

### `core/voice_engine.py` *(Actualizado v2.1)*
- **Qué hace:** Wake word ("Hey Jarvis"), grabación con umbrales de silencio, transcripción con Whisper en CPU int8, y manejo inteligente de interrupciones de voz durante Modo Pesado (cancelar o encolar).
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
- **Qué hace:** Memoria semántica con ChromaDB + poda automática. Usa embeddings locales ONNX en CPU (`all-MiniLM-L6-v2`), nunca Ollama.
- **Importa:** `config`, `chromadb`, `chromadb.utils.embedding_functions`
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
