# 📋 Registro de Cambios, Reglas y Decisiones

> **Propósito:** Documentar TODOS los cambios realizados, las reglas recurrentes que se aplican, y las decisiones de diseño tomadas durante el desarrollo.

---

## 🔄 Historial de Cambios (Changelog)

### 🏷️ alpha 2.0 (version 2.0 alpha) — Arquitectura Modular de Plugins, Conectores MCP, Cola FIFO de Inferencia y Soporte Multiplataforma

**Hitos Principales de la Versión 2.0 Alpha:**
- **Sistema Extensible de Plugins (`plugins/`, `core/plugin_manager.py`):**
  - Implementación de la arquitectura `BasePlugin` (`plugins/base_plugin.py`) con interfaz abstracta para function calling (`get_tools`, `execute`, `is_available`).
  - Integración nativa de 4 plugins de alta productividad:
    - `pptx_plugin.py`: Generador y lector de presentaciones PowerPoint (`.pptx`) con soporte multi-diapositiva y formato estructurado.
    - `blender_plugin.py`: Automatización de escenas 3D, ejecución headless de scripts `bpy`, renderizado y manipulación de geometría.
    - `davinci_plugin.py`: Automatización para DaVinci Resolve Free mediante atajos de teclado, planes de edición y macros de timeline.
    - `autocad_plugin.py`: Generación de scripts `.scr` y control ActiveX/COM para dibujo y diseño asistido por computadora.
  - Catálogo maestro (`plugins/catalog.json`) con 24 conectores predefinidos y archivo de estado persistente (`plugins_config.json`).
  - Carga y descarga en caliente: activación/desactivación sin necesidad de reiniciar la aplicación ni el motor IA.
  - Inyección dinámica de herramientas en `core/ia_engine.py` y `core/agente.py`: solo se inyectan las herramientas de los plugins activos, evitando sobrecarga y degradación en la ventana de contexto del LLM.
- **Marketplace Visual de Plugins (`/plugins` en UI):**
  - Nuevo comando y modal interactivo en Flet (`ui/app.py`) para explorar el catálogo, ver estado (instalado/activo), activar plugins y configurar parámetros (rutas de ejecutables, flags).
  - Soporte para registrar servidores MCP y plugins personalizados directamente desde la interfaz.
- **Cola Serializada FIFO para Protección de VRAM (Regla ESC-09 en `core/cola_mensajes.py`):**
  - Cola centralizada (`queue.Queue`) con worker en hilo desacoplado (`_loop_worker`) que serializa todas las inferencias hacia el LLM.
  - Previene caídas o agotamiento de VRAM en Ollama (`qwen3:8b`) ante ráfagas concurrentes de peticiones del chat y del motor de voz.
  - Notificaciones reactivas en tiempo real hacia la UI mediante PubSub (`cola_estado`, `pendientes`) informando la carga del sistema.
- **Soporte Multiplataforma Nativo (`config.py`):**
  - Detección dinámica del sistema operativo: Windows, macOS y Linux.
  - Whitelist de aplicaciones y rutas de ejecutables segregadas por plataforma (`open -a` en Mac, `xdg-open` en Linux).
  - Blacklists de aplicaciones (`APPS_BLOQUEADAS`) y combinaciones de teclas prohibidas (`TECLAS_BLOQUEADAS`) adaptadas a cada SO (protección contra comandos como `command+q`, `kill`, etc.).
  - Detección y localización dinámica del binario de Tesseract OCR por plataforma.
- **Compilación y Empaquetado Desktop (`Reaxy.spec`):**
  - Especificación de PyInstaller configurada para compilar el ejecutable autónomo con soporte de assets, fuentes, catálogo y dependencias.
- **Documento Maestro de Arquitectura (`ARQUITECTURA.md`):**
  - Especificación técnica exhaustiva con diagramas de flujo Mermaid, desglose de capas y principios Zero-Trust.

---

### 🏷️ alpha 0.5.1 — Reestructuración de Prompts (Modo Ejecución/Mentor) y Logs de Herramientas

**Mejoras en Prompts y Depuración:**
- **Prompts Estrictos (Modo Ejecución / Modo Mentor):** Se reescribieron las instrucciones base en `core/ia_engine.py` y `cerebro_jarvis_prototipo.py` para obligar al LLM a usar exclusivamente function calling en tareas de acción (MODO EJECUCIÓN) y aplicar el "Método de Enseñanza Profunda" para consultas conceptuales (MODO MENTOR).
- **Feedback de Herramientas en Terminal:** Se añadió una impresión en tiempo real (`print("[*] Herramienta usada: ...", flush=True)`) en el bucle de ejecución de `core/ia_engine.py` para visibilizar qué herramienta está usando Jarvis mientras procesa.

---

### 🏷️ alpha 0.5 — Mejoras de Estabilidad, Limpieza de DOM, GC Asíncrono y Enrutador LoRA

**Nuevas características y refactorización:**
- **Limpieza de DOM (BeautifulSoup):** Se integró `beautifulsoup4` para extraer el `page_source` limpio sin etiquetas invasivas (`div`, `span`, etc.).
- **Recolector de Basura Asíncrono:** Se añadió un GC mediante `threading` que llama a `comprimir_historial_sql` cuando los mensajes superan el umbral para resumir el historial y liberar memoria de contexto sin perder el hilo semántico.
- **Enrutador Inteligente (LoRA Router):** Creación de `enrutador_llm.py`, un selector que decide qué modelo instanciar (`qwen2.5-coder:7b`, `Qwen3:8b`, `nomic-embed-text`) basándose en el análisis del prompt.
- **Correcciones del Agente Autónomo (`core/agente.py`):**
  - El agente background ahora expone y maneja correctamente `buscar_internet` y `crear_archivo` en `_HERRAMIENTAS_BG`.
  - Se corrigió el error donde el agente intentaba usar `ir_a_url_web` y `leer_pantalla_web`; ahora invoca correctamente la herramienta unificada `navegar_y_leer_pantalla`.
- **Actualización de Dependencias:** Sustitución de `duckduckgo_search` por `ddgs` en `core/tool_executor.py`.

---

### 🏷️ alpha 0.4 — Streaming UI, Migración a Ollama (Qwen) y Regla de Actualidad

**Mejoras en UI y Motor IA (`core/ia_engine.py`, `ui/app.py`, `config.py`):**
- **Migración a Ollama Local:** Se eliminó la dependencia de Groq API. El motor ahora apunta a `http://localhost:11434/v1/chat/completions` usando el modelo `qwen3:8b`.
- **Streaming de Texto en Tiempo Real:** Se modificó `_hacer_peticion_stream` en el motor IA para procesar Server-Sent Events (SSE) y enviar chunks de texto a Flet. Esto soluciona la congelación de UI ("Procesando...") en sistemas sin aceleración de GPU, imitando el comportamiento de Claude/Gemini.
- **Regla Crítica de Actualidad:** Se añadió una regla estricta al system prompt que prohíbe el uso de memoria interna para datos en tiempo real (noticias, versiones), obligando al agente a usar la herramienta `navegar_y_leer_pantalla`.
- **Limpieza Flet PubSub:** Se añadieron nuevos eventos (`respuesta_ia_stream_start`, `respuesta_ia_stream_chunk`, `respuesta_ia_stream_end`) y se removió la redundancia del envío de texto final.

---

### 🏷️ alpha 0.3 — Navegación Web Autónoma CDP (Playwright)

**Implementación de navegación web autónoma y extracción de DOM en `cerebro.py`:**
- Se eliminó la herramienta antigua `abrir_sitio_web` (basada en `webbrowser`).
- Se introdujo Playwright con CDP (`connect_over_cdp("http://localhost:9222")`) para inyectarse en un navegador Edge ya abierto.
- Nuevas herramientas añadidas:
  - `navegar_en_edge_abierto`: Navega a una URL exacta.
  - `leer_pantalla_web`: Extrae un JSON ligero del DOM (solo textos visibles, `<a>`, `<button>`, `<input>`, `<h1>`, `<h2>`, `<p>`).
- Se actualizó `buscar_internet` (DuckDuckGo) para devolver un JSON limpio e ignorar explícitamente a Wikipedia.
- Se añadió una regla estricta (`# REGLA ESTRICTA DE NAVEGACIÓN WEB AUTÓNOMA`) en el prompt del sistema y se bloqueó explícitamente el uso de texto crudo (`<tool_call>`) para forzar el mechanism nativo de function calling.

---

### 🏷️ alpha 0.1 — Commit Inicial (`95b1f84`)

**Creación del monolito `cerebro.py`** — 875 líneas con todo el sistema en un solo archivo:
- Motor de voz (wake word + Whisper + TTS)
- Motor de IA con function calling (API Groq)
- Ejecución de herramientas (inline en un solo método gigante)
- Interfaz Flet completa (login + dashboard)
- Base de datos vectorial (`dattabase.py`) con ChromaDB
- Seguridad básica (`seguridad.py`) con SHA-256
- Archivos de prueba (`escchar.py`, `prueba.py`)

**Problemas del monolito:**
- Todo en `cerebro.py`: voz, IA, herramientas, UI, config, agente
- Seguridad débil: SHA-256, backdoor por nombre ("alejandro" → admin)
- `shell=True` en subprocess (inyección de comandos posible)
- Sin sanitización de inputs del usuario
- Sin rate limiting
- Sin sandbox para archivos
- Globals para estado de sesión
- Sin poda de memoria vectorial
- Sin ventana deslizante de historial

---

### 🏷️ alpha 0.2 — Refactorización Mayor (`8bdc748`)

**Refactorización completa del monolito en arquitectura modular:**

#### Archivos Creados (Nuevos)
| Archivo | Propósito |
|---------|-----------|
| `main.py` | Punto de entrada limpio (3 líneas) |
| `config.py` | Configuración centralizada de todo el proyecto |
| `core/__init__.py` | Paquete de lógica central |
| `core/ia_engine.py` | Motor IA refactorizado con sanitización |
| `core/agente.py` | Agente autónomo con guardarraíles |
| `core/tool_executor.py` | Ejecución segura de herramientas |
| `core/sanitizador.py` | Anti prompt injection (3 capas) |
| `core/voice_engine.py` | Motor de voz con cola de audio |
| `security/__init__.py` | Paquete de seguridad |
| `security/auth.py` | Autenticación bcrypt + rate limiting |
| `data/__init__.py` | Paquete de datos |
| `data/sql_store.py` | Capa SQL (wrapper para migración futura) |
| `data/vector_store.py` | Memoria vectorial con poda automática |
| `ui/__init__.py` | Paquete de UI |
| `ui/app.py` | Interfaz refactorizada con estado por sesión |

#### Cambios de Seguridad Aplicados
| Código | Cambio | De → A |
|--------|--------|--------|
| SEC-02 | Registro público | Botón "Crear Admin" público → Solo registro invitado |
| SEC-03 | Backdoor | `if "alejandro" in username → admin` → Eliminado |
| SEC-04 | Hashing | SHA-256 → bcrypt (cost 12) + migración lazy |
| SEC-05 | Subprocess | `shell=True` + strings → `shell=False` + listas |
| SEC-06 | Archivos | Escritura libre en cualquier ruta → Sandbox + whitelist extensiones |
| SEC-07 | Agente | Sin restricciones → Blacklist apps + blacklist teclas + logging |
| SEC-08 | Estado | Variables globales → Refs mutables por sesión |
| SEC-10 | Login | Sin límite de intentos → 5 intentos, 30s bloqueo |
| SEC-11 | Inputs | Sin filtro → 3 capas: longitud + regex + delimitadores |

#### Cambios de Escalabilidad
| Código | Cambio |
|--------|--------|
| ESC-02 | Wrapper SQL preparado para migración a PostgreSQL |
| ESC-03 | Poda automática de ChromaDB (max 500 recuerdos/usuario) |
| ESC-05 | Ventana deslizante de historial (últimos 20 mensajes a la API) |
| ESC-06 | Cola de audio con `queue.Queue` |
| ESC-07 | `ThreadPoolExecutor` para peticiones IA (max 3 workers) |
| ESC-08 | Archivos temporales con `tempfile` |

#### Cambio de Motor IA
| Aspecto | alpha 0.1 | alpha 0.2 |
|---------|-----------|-----------|
| API principal | Groq Cloud | Ollama Local (`localhost:11434`) |
| Modelo principal | `llama-3.3-70b-versatile` | `qwen3:8b` |
| Modelo agente | `llama-3.1-8b-instant` | `qwen3:8b` |
| Fallback | N/A | Groq (comentado en código) |

> **Nota:** `cerebro.py` tiene el cambio a Ollama local. `core/ia_engine.py` y `config.py` aún apuntan a Groq. Hay una desincronización entre el monolito y los módulos refactorizados.

---

## 📐 Reglas Recurrentes de Diseño

Estas son las reglas y patrones que se aplican consistentemente en el proyecto:

### 1. Seguridad como Prioridad
- **Todo subprocess debe usar `shell=False`** con listas de argumentos
- **Todo archivo creado por la IA va al sandbox** (`output/`)
- **Todo input del usuario se sanitiza** antes de ir a la API
- **Toda acción del agente se logea** en `log_acciones` SQL
- **Nunca exponer credenciales** → `.env` + `.gitignore`

### 2. Aislamiento Multi-Inquilino
- Los recuerdos vectoriales están etiquetados con `{"dueño": usuario}`
- Las conversaciones SQL están filtradas por `WHERE usuario = ?`
- El agente no puede cruzar datos entre usuarios

### 3. Estado Mutable por Sesión
- **No usar globals para estado** → usar listas mutables `[valor]`
- `id_peticion_ref = [0]`, `usuario_ref = [None]`, `rol_ref = [None]`, `conversacion_ref = [None]`
- Esto permite que los daemon threads compartan estado sin race conditions

### 4. Patrón PubSub para UI
- **Toda comunicación thread → UI va por `page.pubsub.send_all()`**
- Mensajes son dicts con `{"tipo": "nombre_evento", ...datos}`
- El `enrutador_mensajes()` despacha según `tipo`

### 5. Doble Golpe de API
- Si la IA usa herramientas → se ejecutan → se hace una SEGUNDA llamada con los resultados
- Esto permite que la IA sintetice la información antes de responder

### 6. Limpieza de Respuestas Qwen
- Qwen3 genera tags `<think>...</think>` que se limpian con regex
- `re.sub(r"<think>[\s\S]*?</think>", "", texto).strip()`

### 7. Convención de Nombres
- Módulos en español: `sanitizador`, `seguridad`, `dattabase`
- Variables en español: `texto_para_voz`, `lista_mensajes`, `herramientas_permitidas`
- Constantes en UPPER_SNAKE: `MODELO_PRINCIPAL`, `SANDBOX_DIR`
- Funciones con prefijo de acción: `accionar_login`, `disparar_carga_chat`, `repintar_sidebar`

### 8. Configuración Centralizada
- **TODO parámetro configurable va en `config.py`**
- Thresholds, paths, API keys, límites, whitelists, dimensiones de UI
- Los módulos importan de config, nunca hardcodean valores

### 9. Inyección Dinámica de Plugins (Zero Context Bloat)
- Las herramientas de plugins **NUNCA** se inyectan todas a la vez en el prompt o function calling.
- Solo los plugins marcados como `activo: true` en `plugins_config.json` exponen sus esquemas de herramientas mediante `plugin_manager.obtener_herramientas_activas()`.
- Esto protege la ventana de contexto del LLM y reduce las alucinaciones al invocar herramientas.

### 10. Serialización de Inferencia y VRAM Guard (ESC-09)
- Toda llamada de inferencia al LLM (desde voz o chat) entra a la cola FIFO `cola_mensajes.encolar_peticion`.
- Ningún hilo secundario debe disparar peticiones HTTP directas a Ollama concurrentemente para evitar congelamiento de la GPU o VRAM OOM.

### 11. Abstracción y Seguridad Multiplataforma
- Toda llamada al sistema operativo debe consultar las banderas de plataforma (`ES_WINDOWS`, `ES_MAC`, `ES_LINUX`).
- Las blacklists de comandos y teclas (`APPS_BLOQUEADAS`, `TECLAS_BLOQUEADAS`) y las rutas de OCR (`TESSERACT_CMD`) deben adaptarse a cada sistema operativo anfitrión.

---

## ⚠️ Problemas Conocidos / Deuda Técnica

| # | Problema | Impacto | Estado en v2.0 alpha |
|---|----------|---------|----------------------|
| 1 | Archivos legado siguen presentes | Confusión sobre cuál es el código activo | En proceso: `ARQUITECTURA.md` y `MAPA_ARCHIVOS.md` delimitan claramente `main.py` como punto único |
| 2 | Desincronización Ollama vs Groq | `cerebro.py` usa Ollama, `core/` usa Groq | **Resuelto:** Unificado en `config.py` hacia Ollama local (`qwen3:8b`) con headers compatibles |
| 3 | `cerebro.py` sigue teniendo `ft.run()` al final | Se puede ejecutar accidentalmente el monolito viejo | Mitigado: Documentado en mapa de archivos como legado |
| 4 | No hay tests | No se puede verificar que los cambios no rompan nada | Pendiente para v2.1 |
| 5 | `prueba.py` y `escchar.py` son scripts sueltos | No están integrados ni documentados | Documentados como pruebas aisladas legadas |
| 6 | `conexion.json` sin uso aparente | Archivo huérfano | Documentado |
| 7 | `Zero_Trust.pdf` sin contexto | Archivo huérfano | Referencia teórica documentada en `ARQUITECTURA.md` |
| 8 | Las fuentes están en `assets/fonts/` junto con imágenes | Mezcla de tipos de assets | Mantenido por retrocompatibilidad con PyInstaller |

---

## 🏗️ Decisiones de Diseño Importantes

### ¿Por qué Flet y no Electron/Web?
- Flet permite crear UIs desktop con Python puro
- No requiere HTML/CSS/JS ni servidor web
- Flutter rendering = rendimiento nativo
- Integración directa con el ecosistema Python (Whisper, ChromaDB, pyautogui)

### ¿Por qué SQLite + ChromaDB y no solo una DB?
- **SQLite** = historial exacto, ordenado, relacional (qué se dijo exactamente)
- **ChromaDB** = memoria semántica, búsqueda por similitud (de qué se habló)
- Son complementarias: SQL es el "diario", ChromaDB es el "subconsciente"

### ¿Por qué OCR y no Selenium/Playwright?
- OCR con Tesseract funciona en CUALQUIER aplicación, no solo el navegador
- El agente es "ciego" y ve la pantalla completa, puede interactuar con cualquier software
- No depende de APIs de navegador ni selectores CSS
- En v2.0 alpha se complementa con Playwright CDP para inspección profunda web cuando se requiere precisión DOM

### ¿Por qué daemon threads en vez de asyncio?
- Flet tiene su propio event loop
- Los daemon threads permiten ejecutar IA y agente sin bloquear la UI
- `pubsub` es el puente seguro entre threads y la UI

### ¿Por qué Ollama local en vez de Groq cloud?
- Privacidad: los datos no salen de la máquina
- Costo: sin límites de API ni pagos
- Latencia: red local es más rápida que HTTP a la nube
- Disponibilidad: funciona sin internet

### ¿Por qué un Sistema de Plugins Dinámico en v2.0 alpha?
- Permite extender las capacidades de Jarvis (PowerPoint, Blender 3D, DaVinci Resolve, AutoCAD, servidores MCP) sin tocar el código central ni aumentar la fragilidad del monolito.
- Evita la saturación del contexto del LLM al inyectar únicamente las herramientas de los plugins activos.
- Permite a los usuarios crear conectores estándar o conectar servidores remotos mediante `/plugins`.

### ¿Por qué una Cola FIFO (ESC-09) para Inferencia?
- Ollama ejecuta modelos locales de 8B parámetros que consumen recursos sustanciales de VRAM. Si un usuario envía un mensaje de texto mientras el motor de voz transcribe y consulta la IA, la ejecución paralela provocaría bloqueos de GPU, timeouts o degradación masiva de tokens/segundo.
- La cola garantiza ejecución secuencial atómica con feedback visual en la UI.

