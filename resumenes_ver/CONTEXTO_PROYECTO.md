# 🧠 Reaxy$ (Jarvis Project) — Contexto Completo del Proyecto

> **Última actualización:** 2026-10-10  
> **Versión actual:** 2.1 alpha (alpha 2.1)  
> **Nombre código:** `jarvis_proyect`  
> **Nombre público:** Reaxy$ - Agentic OS

---

## 📌 ¿Qué es este proyecto?

**Reaxy$** es un asistente de escritorio con inteligencia artificial que funciona como un **sistema operativo agéntico personal**. Combina:

- **Interacción por voz** (wake word "Hey Jarvis" + transcripción con Whisper en CPU + TTS neural)
- **Interacción por texto** (chat tipo ChatGPT con streaming token a token)
- **Ejecución autónoma de tareas** (agente que controla mouse, teclado, Windows UIA y pantalla con OCR)
- **Sistema Extensible de Plugins & MCP** (Marketplace visual `/plugins`, PowerPoint, Blender 3D, DaVinci Resolve, AutoCAD)
- **Cola Serializada de Inferencia & VRAM Guard (ESC-09)** (Gestión atómica de modelo residente `qwen3.5:9b` y modo pesado `gpt-oss:20b`)
- **Memoria a largo plazo** (base de datos vectorial con ChromaDB y embeddings ONNX locales en CPU)
- **Historial de conversaciones** (base de datos relacional SQLite con WAL mode)
- **Sistema de autenticación y seguridad Zero-Trust** con roles (Admin vs Invitado, bcrypt, sandboxing, anti prompt-injection)
- **Interfaz gráfica moderna** con estética Neo-brutalista reactiva (Flet)

En esencia: **es un asistente de IA local-first que no solo habla, sino que ACTÚA** — puede abrir apps, navegar la web con Playwright CDP, crear presentaciones PPTX, renderizar escenas en Blender, automatizar DaVinci Resolve, generar planos en AutoCAD, mover el mouse, escribir y razonar con modelos locales (`qwen3.5:9b` y `gpt-oss:20b`).

---

## 🏗️ Arquitectura del Sistema

### Tipo de Arquitectura: **Monolito Modular con Capas & Sistema de Plugins**

El proyecto evolucionó de un monolito de 875 líneas (`cerebro.py`) a una arquitectura modular con separación estricta de responsabilidades, protección de recursos de hardware y conectores extensibles:

```
jarvis_proyect/
│
├── main.py                     # Punto de entrada de la aplicación UI
├── config.py                   # Centro de configuración centralizado, constantes y whitelists
├── ARQUITECTURA.md             # Especificación técnica formal Zero-Trust y diagramas
├── Reaxy.spec                  # Configuración de compilación con PyInstaller
├── plugins_config.json         # Estado persistente de plugins activos y configs de usuario
│
├── plugins/                    # 🧩 BIBLIOTECA DE PLUGINS Y CONECTORES MCP
│   ├── catalog.json            #   Catálogo maestro (24 conectores predeterminados)
│   ├── base_plugin.py          #   Interfaz abstracta para plugins locales y remotos
│   ├── pptx_plugin.py          #   Generador y lector de presentaciones PowerPoint (.pptx)
│   ├── blender_plugin.py       #   Automatización y scripts bpy para Blender 3D Suite
│   ├── davinci_plugin.py       #   Control, atajos y timeline plan para DaVinci Resolve Free
│   └── autocad_plugin.py       #   Trazado COM ActiveX y scripts .scr para AutoCAD
│
├── core/                       # 🧠 CAPA DE LÓGICA (Núcleo)
│   ├── ia_engine.py            #   Motor IA: streaming, function calling e inyección de plugins
│   ├── agente.py               #   Agente autónomo background multi-paso (ReAct)
│   ├── plugin_manager.py       #   Gestor central de plugins y conectores MCP dinámicos
│   ├── cola_mensajes.py        #   Cola FIFO serializada para protección de GPU/VRAM (ESC-09)
│   ├── tool_executor.py        #   Ejecución segura de herramientas e interfaz con el SO
│   ├── sanitizador.py          #   Sanitización de inputs (anti prompt injection en 3 capas)
│   └── voice_engine.py         #   Motor de voz: wake word + Whisper + grabación
│
├── security/                   # 🔒 CAPA DE SEGURIDAD
│   └── auth.py                 #   Autenticación bcrypt + rate limiting + historial SQL
│
├── data/                       # 💾 CAPA DE DATOS
│   ├── sql_store.py            #   Wrapper SQL WAL (preparado para migrar a PostgreSQL)
│   └── vector_store.py         #   Memoria semántica con ChromaDB + poda automática
│
├── ui/                         # 🎨 CAPA DE PRESENTACIÓN
│   └── app.py                  #   Interfaz Flet (neo-brutalismo, streaming, /plugins marketplace)
│
├── assets/                     # Fuentes y recursos visuales
├── output/                     # Sandbox restringido de archivos generados por la IA
│
├── ─── ARCHIVOS LEGADO ───
├── cerebro.py                  # Monolito original (875 líneas, versión alpha 0.1)
├── cerebro_jarvis_prototipo.py # Prototipo previo
├── seguridad.py                # Módulo de seguridad legacy (SHA-256)
├── dattabase.py                # Base de datos vectorial legacy
├── escchar.py                  # Script de prueba de audio
└── prueba.py                   # Laboratorio de glassmorphism Flet
```

### Diagrama de Flujo de la Arquitectura (v2.0 alpha)

```
┌────────────────────────────────────────────────────────────────────────┐
│                          USUARIO / ENTORNO                             │
│                  (Interacción por Voz o por Texto)                     │
└──────────────────┬──────────────────────────────────┬──────────────────┘
                   │                                  │
          ┌────────▼────────┐                ┌────────▼─────────┐
          │  voice_engine   │                │     ui/app.py    │
          │ (Wake Word +    │                │  (Campo de chat  │
          │  Whisper STT)   │                │  /plugins modal) │
          └────────┬────────┘                └────────┬─────────┘
                   │                                  │
                   └─────────────────┬────────────────┘
                                     │
                            ┌────────▼────────┐
                            │  sanitizador.py │  ← Anti prompt injection (3 capas)
                            └────────┬────────┘
                                     │
                            ┌────────▼────────┐
                            │ cola_mensajes.py│  ← Cola FIFO + VRAM Guard (Orquestador de Modelos)
                            └────────┬────────┘
                                     │
                            ┌────────▼────────┐
                            │   ia_engine.py  │  ← Orquestador Ollama (qwen3.5:9b residente)
                            │                 │  ← Inyección de tools de plugins
                            └────┬───────┬────┘
                                 │       │
                      ┌──────────┘       └──────────┐
                      │                             │
             ┌────────▼────────┐         ┌──────────▼──────────┐
             │  tool_executor  │         │      agente.py      │
             │ (Tools nativas: │         │  (Agente autónomo   │
             │  apps, files)   │         │   multi-paso ReAct) │
             └────────┬────────┘         └──────────┬──────────┘
                      │                             │
                      └──────────────┬──────────────┘
                                     │
                     ┌───────────────┴───────────────┐
                     ▼                               ▼
       ┌───────────────────────────┐   ┌───────────────────────────┐
       │     plugin_manager.py     │   │        MUNDO REAL         │
       │ - PPTX Generator          │   │ - Playwright CDP (Edge)   │
       │ - Blender 3D (bpy)        │   │ - Windows UIA (pywinauto) │
       │ - DaVinci Resolve Free    │   │ - Mouse/Teclado / OCR     │
       │ - AutoCAD (.scr/COM)      │   │ - Sandbox output/         │
       │ - Servidores MCP externos │   │ - TTS (edge-tts)          │
       └───────────────────────────┘   └───────────────────────────┘
```

---

## ⚡ Features (Funcionalidades)

### 🎤 Motor de Voz
| Feature | Tecnología | Detalle |
|---------|-----------|---------|
| Wake Word | `openwakeword` | Activa con "Hey Jarvis" (threshold 0.5) |
| Transcripción | `faster_whisper` (base, int8) | Modelo local, idioma español |
| Detección de silencio | `sounddevice` + `numpy` | 2s de silencio = fin de grabación, max 15s |
| Text-to-Speech | `edge-tts` | Voz "es-MX-JorgeNeural" (Microsoft) |

### 🤖 Motor de IA (Arquitectura Dual Ollama)
| Feature | Detalle |
|---------|---------|
| **Modelo Residente (Rápido)** | `qwen3.5:9b` siempre en VRAM (`keep_alive: -1`, `think: False`, `num_ctx: 8192`, precalentado al inicio) |
| **Modo Pesado (Agente)** | `gpt-oss:20b` (`think: "low"`), cargado solo durante `delegar_tarea_larga` previa descarga del 9B |
| **Enrutador Determinista** | `enrutador_llm.py` sin llamadas a LLM: rápido por defecto, pesado solo en delegar tarea |
| **LLM Cloud (fallback)** | Groq API con `llama-3.3-70b-versatile` (opcional en código) |
| **Function Calling** | Nativo vía `/api/chat` Ollama con herramientas de plugins y nativas |
| **System Prompt** | Dinámico según rol (Admin = MODO EJECUCIÓN estricto para tools y MODO MENTOR, Invitado = chat casual) |
| **Método de Enseñanza** | Explica 2 veces: intuitiva (analogías) + técnica (bajo nivel) |

### 🛠️ Herramientas (Function Calling)
| Herramienta | Descripción |
|------------|-------------|
| `abrir_app` | Abre apps del whitelist (Spotify, Edge, OBS, Docker, etc.) |
| `navegar_en_edge_abierto` | Navega a URL usando Playwright (CDP puerto 9222) |
| `leer_pantalla_web` | Extrae resumen ligero del DOM en JSON usando CDP |
| `buscar_internet` | Busca en DuckDuckGo con `ddgs` (JSON, ignora Wikipedia) |
| `crear_pdf` | Genera PDFs dentro del sandbox con `fpdf` |
| `crear_archivo` | Crea archivos de código en el sandbox |
| `escanear_pantalla_ocr` | Captura pantalla + OCR con Tesseract |
| `mover_y_click_mouse` | Control físico del mouse con `pyautogui` |
| `escribir_teclado` | Escritura física de texto |
| `presionar_tecla` | Presiona teclas especiales (con whitelist) |
| `escanear_entorno_sistema` | Lista ventanas activas + resolución |
| `delegar_tarea_larga` | Lanza agente autónomo en background thread |

### 🧩 Sistema de Plugins y Conectores MCP (Novedad v2.0 alpha)
| Plugin | Archivo | Capacidades / Herramientas Clave |
|--------|---------|----------------------------------|
| **PowerPoint (.pptx)** | `plugins/pptx_plugin.py` | `crear_presentacion_powerpoint`, `leer_presentacion_powerpoint` (soporte multi-slide con python-pptx) |
| **Blender 3D Suite** | `plugins/blender_plugin.py` | `ejecutar_script_blender`, `renderizar_escena_blender`, `crear_objeto_3d_blender` (vía Python `bpy` headless) |
| **DaVinci Resolve Free** | `plugins/davinci_plugin.py` | `enviar_atajo_davinci`, `crear_plan_edicion`, `importar_medios_davinci` (control por atajos nativos y macros) |
| **AutoCAD** | `plugins/autocad_plugin.py` | `ejecutar_script_autocad`, `dibujar_geometria_autocad` (scripts `.scr` y automatización ActiveX COM) |
| **Conectores MCP / Custom**| `core/plugin_manager.py` | Integración dinámica vía `/plugins` con catálogo de 24 herramientas y soporte para servidores MCP |

### 🛡️ Capa de Resiliencia: Cola FIFO y Orquestación VRAM (ESC-09)
- **Serialización Total:** Toda petición al LLM (chat, voz o tarea de agente) pasa por `cola_mensajes.solicitar_inferencia_ollama()`.
- **Transición Atómica:** Al delegar tarea larga, la cola avisa por TTS, descarga el 9B, monta el 20B (`gpt-oss:20b`), corre la tarea y al terminar descarga el 20B y restablece el 9B, avisando nuevamente por TTS.
- **Manejo de Interrupciones de Voz:** Si llega voz durante el modo pesado: cancela el agente si el usuario lo ordena (*"cancela"*, *"detén"*), o encola la consulta para procesarla al recuperar el 9B.
- **Protección de VRAM:** `OLLAMA_MAX_LOADED_MODELS=1` garantiza que nunca coexistan dos modelos en GPU.
- **Feedback UI:** Publica estado de la cola y modo activo en tiempo real (`cola_estado`).

### 🤖 Agente Autónomo
- **Loop de hasta 15 pasos** con herramientas reducidas (OCR + mouse + teclado + plugins activos)
- **Delay de 4 segundos** al inicio para que el usuario posicione la ventana
- Ejecuta en `daemon thread` separado, sin bloquear la conversación
- Soporta Function Calling nativo y fallback parser de JSON
- Concluye obligatoriamente con `finalizar_tarea` y reporte estructurado (✅/❌)

### 🧠 Sistema de Memoria Dual
| Capa | Tipo | Tecnología | Propósito |
|------|------|-----------|-----------|
| **Corto Plazo** | Relacional (SQL) | SQLite + WAL mode | Historial exacto de conversaciones |
| **Largo Plazo** | Vectorial | ChromaDB | Recuerdos semánticos, búsqueda por similitud |

- Multi-inquilino: cada usuario tiene sus propios recuerdos aislados
- Poda automática: máximo 500 recuerdos por usuario
- Ventana deslizante: solo los últimos 20 mensajes van a la API

### 🔐 Sistema de Seguridad
| Código | Medida | Detalle |
|--------|--------|---------|
| SEC-02 | Registro público solo invitado | No hay botón de "crear admin" en la UI |
| SEC-03 | Backdoor eliminado | Ya no se fuerza admin por nombre |
| SEC-04 | bcrypt | Migración de SHA-256 a bcrypt con lazy rehash |
| SEC-05 | `shell=False` | Todos los `subprocess` usan listas de argumentos |
| SEC-06 | Sandbox de archivos | Creación restringida a `output/`, extensiones en whitelist |
| SEC-07 | Blacklists + Logging | Apps bloqueadas (cmd, powershell), teclas bloqueadas (alt+f4, ctrl+alt+del) |
| SEC-08 | Estado por sesión | Refs mutables en vez de globals |
| SEC-10 | Rate Limiting | 5 intentos fallidos → 30 seg de bloqueo |
| SEC-11 | Anti Prompt Injection | 3 capas: longitud max + patrones regex + delimitadores |
| ESC-09 | VRAM Guard / FIFO Queue | Serialización de inferencias para evitar saturación de hardware |

### 🎨 Interfaz (UI)
- **Framework:** Flet (Flutter para Python)
- **Diseño:** Neo-brutalismo con gradientes y temas dinámicos según hora
- **Rutas:** Login (`/`) → Dashboard (`/dashboard`) con protección de sesión persistente
- **Streaming:** Respuestas de IA renderizadas token-a-token en tiempo real sin congelar la UI
- **Marketplace de Plugins:** Modal accesible con comando `/plugins` para toggles y configuración en caliente
- **Animaciones:** Ondas de audio reactivas para escucha y habla
- **Tipografías custom:** "Akira Expanded Demo" y "Gohan"

---

## 🔄 Cómo Opera (Flujo Completo)

### Flujo de una Petición por Voz:
```
1. voice_engine detecta "Hey Jarvis" (openwakeword)
2. UI muestra animación de "escuchando" (ondas de voz)
3. sounddevice graba audio hasta 2s de silencio o 15s max
4. Whisper transcribe el WAV a texto en español
5. Texto se publica al chat (pubsub → UI)
6. Se encola la petición en cola_mensajes (FIFO worker procesa secuencialmente)
```

### Flujo de una Petición por Texto:
```
1. Usuario escribe en el TextField y presiona Enter/Send
2. Texto se publica al chat (pubsub → UI)
3. Se encola la petición en cola_mensajes (FIFO worker procesa secuencialmente)
```

### Flujo del Motor IA (procesar_peticion_ia):
```
1. GESTIÓN SQL
   - Si no hay conversación activa → crear una nueva (título = primeros 30 chars)
   - Guardar mensaje del usuario en la DB SQL

2. MEMORIA VECTORIAL
   - Consultar ChromaDB por recuerdos relevantes del usuario actual

3. SANITIZACIÓN
   - Truncar a 2000 chars
   - Filtrar patrones de prompt injection
   - Encapsular con delimitadores [INICIO/FIN_MENSAJE_USUARIO]

4. CONSTRUCCIÓN DEL PROMPT & INYECCIÓN DE PLUGINS
   - Admin → System prompt de Jarvis (MODO EJECUCIÓN estricto para tools o MODO MENTOR)
   - Invitado → System prompt casual (sin herramientas)
   - Inyectar herramientas nativas + herramientas de plugins activos (plugin_manager)
   - Inyectar ventana deslizante de los últimos 20 mensajes

5. CICLO DE INFERENCIA Y FUNCTION CALLING (Ollama local qwen3:8b)
   - Streaming de respuesta token a token hacia la UI
   - Si hay tool_calls → ejecutar herramienta nativa o derivar a plugin_manager
   - Inyectar resultado como rol 'tool' y solicitar veredicto final

6. PUBLICACIÓN
   - Guardar respuesta en SQL + ChromaDB
   - Publicar texto final y cerrar stream
   - Si modo voz → generar audio con edge-tts y reproducir con pygame
```

---

## 📦 Dependencias Principales

| Paquete | Uso |
|---------|-----|
| `flet` | Framework UI (Flutter para Python) |
| `faster_whisper` | Transcripción de voz (Whisper local) |
| `openwakeword` | Detección de wake word |
| `sounddevice` | Captura de micrófono |
| `scipy` | Escritura de WAV |
| `numpy` | Procesamiento de audio |
| `pygame-ce` | Reproducción de audio |
| `requests` | Comunicación con API local Ollama |
| `chromadb` | Base de datos vectorial |
| `bcrypt` | Hashing de contraseñas |
| `pyautogui` | Control físico de mouse y teclado |
| `pywinauto` | Automatización nativa Windows UIA |
| `pywin32` | Integración COM ActiveX (AutoCAD y APIs Windows) |
| `python-pptx` | Manipulación y generación de presentaciones PowerPoint |
| `pytesseract` | OCR (requiere Tesseract instalado) |
| `Pillow` | Captura de pantalla |
| `fpdf2` | Generación de PDFs en sandbox |
| `duckduckgo-search` (`ddgs`) | Búsqueda web segura |
| `edge-tts` | Text-to-Speech neural (Microsoft) |
| `python-dotenv` | Variables de entorno (.env) |
| `playwright` | Navegación web automatizada y extracción DOM por CDP |

---

## 🗂️ Archivos Legado vs Refactorizados

| Archivo Legado | Reemplazo Modular (v2.0 alpha) | Estado |
|----------------|--------------------------------|--------|
| `cerebro.py` (875 líneas) | `core/ia_engine.py` + `core/agente.py` + `core/tool_executor.py` + `core/voice_engine.py` + `core/cola_mensajes.py` + `core/plugin_manager.py` + `ui/app.py` | ⚠️ Legado aún presente |
| `seguridad.py` (SHA-256 + backdoor) | `security/auth.py` (bcrypt + rate limiting) | ⚠️ Legado aún presente |
| `dattabase.py` (sin poda) | `data/vector_store.py` (con poda automática) | ⚠️ Legado aún presente |
| N/A | `core/sanitizador.py` | ✅ Activo |
| N/A | `config.py` | ✅ Activo |
| N/A | `core/cola_mensajes.py` | ✅ Activo (v2.0 alpha) |
| N/A | `core/plugin_manager.py` + `plugins/*` | ✅ Activo (v2.0 alpha) |

---

## 🎯 Estado Actual y Roadmap Implícito

### ✅ Completado en v2.0 alpha
- Motor de voz funcional (wake word + STT + TTS)
- Streaming token a token en tiempo real
- Motor IA con function calling completo y Ollama local (`qwen3:8b`)
- Cola de serialización FIFO para protección de VRAM (ESC-09)
- Sistema extensible de plugins con marketplace interactivo (`/plugins`)
- Plugins especializados: PowerPoint, Blender 3D, DaVinci Resolve, AutoCAD
- Agente autónomo con OCR y Windows UIAutomation
- Sistema de seguridad Zero-Trust (bcrypt, rate limiting, sandbox, sanitizador de 3 capas)
- UI Neo-brutalista con tema dinámico y retención de sesión
- Soporte multiplataforma (Windows/macOS/Linux) en configuración
- Especificación técnica formal (`ARQUITECTURA.md`) y empaquetado (`Reaxy.spec`)

### 🔮 Áreas de Mejora Potencial (v2.1+)
- Desincorporación definitiva de archivos legados (`cerebro.py`, `seguridad.py`, `dattabase.py`)
- Suite de pruebas automatizadas y tests unitarios
- Conexión cliente stdio/SSE para servidores MCP remotos en vivo
- Panel web/móvil complementario
- Migración opcional de SQLite a PostgreSQL para entornos multi-usuario en red

