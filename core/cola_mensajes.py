"""
core/cola_mensajes.py — Sistema de Cola de Mensajes y Orquestación Ollama (ESC-09)

Serializa TODAS las peticiones IA para proteger la VRAM:
- Un solo modelo residente: qwen3.5:9b (keep_alive: -1, think: false, num_ctx: 8192 fijo)
- Modo pesado: gpt-oss:20b (think: "low", solo para delegar_tarea_larga)
- Transición serializada: descargar 9B -> cargar 20B -> ejecutar tarea -> descargar 20B -> recargar 9B
- Avisos TTS al entrar y al salir del modo pesado
- agente.py no llama a Ollama directo; pasa por solicitar_inferencia_ollama()
- Manejo de concurrencia: una sola inferencia a la vez (FIFO)
"""
import queue
import threading
import time
import json
import os
import requests
import pygame

from config import (
    COLA_IA_MAXSIZE,
    OLLAMA_CHAT_URL,
    API_HEADERS,
    MODELO_RAPIDO,
    MODELO_PESADO,
    NUM_CTX,
    KEEP_ALIVE_RESIDENTE,
    OLLAMA_OPTIONS,
)
from core import tool_executor

# =============================================================================
# Cola centralizada + estado
# =============================================================================
_cola: queue.Queue = queue.Queue(maxsize=COLA_IA_MAXSIZE)
_worker_activo = False

# Estado del Modo Pesado
_modo_pesado_activo = False
_cancelar_tarea_pesada_flag = threading.Event()


def esta_en_modo_pesado() -> bool:
    """Indica si el sistema está ejecutando una tarea en modo pesado (gpt-oss:20b)."""
    return _modo_pesado_activo


def cancelar_tarea_pesada():
    """Señala la cancelación de la tarea pesada actualmente en ejecución."""
    global _cancelar_tarea_pesada_flag
    _cancelar_tarea_pesada_flag.set()
    print("[COLA] 🛑 Señal de cancelación enviada a la tarea pesada.", flush=True)


def reproducir_tts_sistema(texto: str, page=None):
    """Sintetiza y reproduce un mensaje de voz del sistema mediante TTS."""
    try:
        if page:
            page.pubsub.send_all({"tipo": "onda_hablando", "estado": True})

        nombre_audio = tool_executor.sintetizar_voz(texto)
        if nombre_audio and os.path.exists(nombre_audio):
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(nombre_audio)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            pygame.mixer.music.unload()
            try:
                os.remove(nombre_audio)
            except OSError:
                pass
    except Exception as ex:
        print(f"[COLA] Error al reproducir TTS del sistema: {ex}", flush=True)
    finally:
        if page:
            page.pubsub.send_all({"tipo": "onda_hablando", "estado": False})


# =============================================================================
# Gestión del Ciclo de Vida de Modelos en Ollama
# =============================================================================
def precalentar_modelo_residente():
    """
    Realiza una petición vacía para precargar qwen3.5:9b en VRAM al iniciar la app.
    OLLAMA_KEEP_ALIVE=-1 y opciones num_ctx fijas (8192).
    """
    print(f"[COLA] 🔥 Precalentando modelo residente: {MODELO_RAPIDO}...", flush=True)
    try:
        paquete = {
            "model": MODELO_RAPIDO,
            "messages": [],
            "keep_alive": KEEP_ALIVE_RESIDENTE,
            "think": False,
            "options": OLLAMA_OPTIONS,
        }
        resp = requests.post(OLLAMA_CHAT_URL, headers=API_HEADERS, json=paquete, timeout=120)
        if resp.status_code == 200:
            print(f"[COLA] ✅ Modelo residente {MODELO_RAPIDO} precalentado y anclado en VRAM.", flush=True)
        else:
            print(f"[COLA] ⚠️ Precalentamiento devolvió status {resp.status_code}: {resp.text}", flush=True)
    except Exception as e:
        print(f"[COLA] ⚠️ No se pudo precalentar el modelo residente: {e}", flush=True)


def descargar_modelo(modelo: str):
    """Descarga inmediatamente un modelo de VRAM usando keep_alive: 0."""
    print(f"[COLA] 🧹 Descargando modelo de VRAM: {modelo}...", flush=True)
    try:
        paquete = {
            "model": modelo,
            "keep_alive": 0,
        }
        resp = requests.post(OLLAMA_CHAT_URL, headers=API_HEADERS, json=paquete, timeout=30)
        if resp.status_code == 200:
            print(f"[COLA] ✅ Modelo {modelo} liberado de VRAM.", flush=True)
        else:
            print(f"[COLA] ⚠️ Descarga de {modelo} status {resp.status_code}", flush=True)
    except Exception as e:
        print(f"[COLA] ⚠️ Error al descargar {modelo}: {e}", flush=True)


def cargar_modelo(modelo: str, keep_alive=KEEP_ALIVE_RESIDENTE, options=None, think=None):
    """Carga y precalienta un modelo en VRAM con sus parámetros específicos."""
    print(f"[COLA] 🚀 Cargando modelo en VRAM: {modelo}...", flush=True)
    opts = options or OLLAMA_OPTIONS
    paquete = {
        "model": modelo,
        "messages": [],
        "keep_alive": keep_alive,
        "options": opts,
    }
    if think is not None:
        paquete["think"] = think
    try:
        resp = requests.post(OLLAMA_CHAT_URL, headers=API_HEADERS, json=paquete, timeout=180)
        if resp.status_code == 200:
            print(f"[COLA] ✅ Modelo {modelo} cargado correctamente.", flush=True)
        else:
            print(f"[COLA] ⚠️ Carga de {modelo} status {resp.status_code}", flush=True)
    except Exception as e:
        print(f"[COLA] ⚠️ Error al cargar {modelo}: {e}", flush=True)


# =============================================================================
# Cliente Centralizado de Inferencia Ollama (/api/chat)
# =============================================================================
def solicitar_inferencia_ollama(
    paquete: dict,
    on_chunk=None,
    on_think_chunk=None,
    cancel_flag: threading.Event = None,
    stream: bool = True,
) -> tuple[int, dict]:
    """
    Único punto de acceso a inferencias Ollama en la aplicación.
    Aplica las reglas estrictas de arquitectura:
    - qwen3.5:9b: think: False, keep_alive: -1, num_ctx: 8192
    - gpt-oss:20b: think: "low", keep_alive: -1, num_ctx: 8192
    """
    modelo = paquete.get("model", MODELO_RAPIDO)
    paquete_req = dict(paquete)

    # Forzar opciones idénticas y parámetros por modelo
    paquete_req["options"] = dict(OLLAMA_OPTIONS)
    paquete_req["keep_alive"] = KEEP_ALIVE_RESIDENTE

    if modelo == MODELO_RAPIDO:
        paquete_req["think"] = False
    elif modelo == MODELO_PESADO:
        paquete_req["think"] = "low"

    paquete_req["stream"] = stream

    try:
        resp = requests.post(
            OLLAMA_CHAT_URL,
            headers=API_HEADERS,
            json=paquete_req,
            stream=stream,
            timeout=180,
        )
        if resp.status_code != 200:
            return resp.status_code, {}

        if not stream:
            data = resp.json()
            return 200, data.get("message", {})

        texto_completo = ""
        tool_calls = []

        for linea in resp.iter_lines():
            if cancel_flag and cancel_flag.is_set():
                print("[COLA] Inferencia cancelada a mitad de stream.", flush=True)
                break

            if not linea:
                continue

            try:
                chunk = json.loads(linea.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            msg = chunk.get("message", {})

            # 1. Chunk de razonamiento
            thinking = msg.get("thinking", "")
            if thinking and on_think_chunk:
                on_think_chunk(thinking)

            # 2. Chunk de texto normal
            content = msg.get("content", "")
            if content:
                texto_completo += content
                if on_chunk:
                    on_chunk(content)

            # 3. Tool calls en /api/chat
            if "tool_calls" in msg and msg["tool_calls"]:
                for tc in msg["tool_calls"]:
                    tool_calls.append(tc)

            if chunk.get("done", False):
                break

        resultado_msg = {}
        if texto_completo:
            resultado_msg["content"] = texto_completo
        if tool_calls:
            resultado_msg["tool_calls"] = tool_calls

        return 200, resultado_msg

    except Exception as e:
        print(f"[COLA] Error en inferencia Ollama: {e}", flush=True)
        return 500, {"error": str(e)}


# =============================================================================
# Encolamiento y Despacho Serializado
# =============================================================================
def encolar_peticion(callback, args: tuple, page=None):
    """
    Encola una petición IA normal para procesamiento secuencial.
    """
    try:
        _cola.put_nowait((callback, args, page))
        _notificar_cola(page)
    except queue.Full:
        if page:
            page.pubsub.send_all({
                "tipo": "respuesta_ia",
                "texto": "[Sistema]: Cola llena. Espera a que se procesen los mensajes anteriores.",
            })


def encolar_tarea_pesada(objetivo: str, page, usuario: str, delay_inicio: int = None):
    """
    Encola una tarea pesada (delegar_tarea_larga) como una sola operación serializada:
    Descargar 9B -> Cargar 20B -> Ejecutar tarea -> Descargar 20B -> Cargar 9B.
    """
    encolar_peticion(
        _operacion_serializada_modo_pesado,
        (objetivo, page, usuario, delay_inicio),
        page,
    )


def _operacion_serializada_modo_pesado(objetivo: str, page, usuario: str, delay_inicio: int = None):
    """
    Operación serializada completa para el Modo Pesado.
    Ejecutada exclusivamente dentro del hilo de _loop_worker (protección absoluta de VRAM).
    """
    global _modo_pesado_activo
    _modo_pesado_activo = True
    _cancelar_tarea_pesada_flag.clear()

    print(f"\n[MODO PESADO] 🔄 Iniciando transición para: '{objetivo}'", flush=True)

    try:
        # --- 1. Feedback UI (sin voz: la voz es exclusiva de la sección de voz) ---
        if page:
            page.pubsub.send_all({
                "tipo": "respuesta_ia",
                "texto": f"⚙️ [Modo Pesado / OS]: Activando `{MODELO_PESADO}` con razonamiento para la tarea delegada...",
            })

        # --- 2. Descargar modelo 9B residente ---
        descargar_modelo(MODELO_RAPIDO)

        # --- 3. Cargar modelo 20B pesado ---
        cargar_modelo(MODELO_PESADO, keep_alive=KEEP_ALIVE_RESIDENTE, options=OLLAMA_OPTIONS, think="low")

        # --- 4. Ejecutar el agente autónomo (usa solicitar_inferencia_ollama) ---
        from core.agente import agente_autonomo_background
        agente_autonomo_background(
            page=page,
            objetivo=objetivo,
            usuario=usuario,
            delay_inicio=delay_inicio,
            cancel_flag=_cancelar_tarea_pesada_flag,
        )

    except Exception as e:
        print(f"[MODO PESADO] ❌ Error en ejecución de tarea: {e}", flush=True)
        if page:
            page.pubsub.send_all({
                "tipo": "respuesta_ia",
                "texto": f"❌ [Modo Pesado Falló]: {e}",
            })
    finally:
        # --- 5. Descargar 20B y restaurar 9B residente ---
        print("[MODO PESADO] 🔄 Restaurando modelo residente...", flush=True)
        descargar_modelo(MODELO_PESADO)
        cargar_modelo(MODELO_RAPIDO, keep_alive=KEEP_ALIVE_RESIDENTE, options=OLLAMA_OPTIONS, think=False)

        # --- 6. Feedback UI al salir (sin TTS: la voz es exclusiva de la sección de voz) ---
        if _cancelar_tarea_pesada_flag.is_set():
            texto_ui = f"🛑 [Modo Pesado / OS]: Cancelado. `{MODELO_RAPIDO}` restablecido en memoria."
        else:
            texto_ui = f"✅ [Modo Pesado / OS]: Completado. `{MODELO_RAPIDO}` activo y listo."

        if page:
            page.pubsub.send_all({"tipo": "respuesta_ia", "texto": texto_ui})

        _modo_pesado_activo = False
        _cancelar_tarea_pesada_flag.clear()
        print("[MODO PESADO] ✅ Transición completada con éxito.", flush=True)


def obtener_tamano_cola() -> int:
    """Retorna la cantidad de mensajes pendientes en la cola."""
    return _cola.qsize()


def iniciar_worker():
    """Inicia el worker thread (llamar una sola vez al arrancar la app)."""
    global _worker_activo
    if _worker_activo:
        return
    _worker_activo = True
    hilo = threading.Thread(target=_loop_worker, daemon=True)
    hilo.start()


# =============================================================================
# Worker interno — procesa peticiones una a una
# =============================================================================
def _loop_worker():
    """Loop infinito que extrae y procesa peticiones de la cola FIFO."""
    while True:
        callback, args, page = _cola.get()  # Bloquea hasta que haya algo
        try:
            _notificar_cola(page)
            callback(*args)
        except Exception as e:
            if page:
                page.pubsub.send_all({
                    "tipo": "respuesta_ia",
                    "texto": f"[Error Cola]: {e}",
                })
        finally:
            _cola.task_done()
            _notificar_cola(page)


def _notificar_cola(page):
    """Envía el estado actual de la cola a la UI."""
    if page:
        pendientes = _cola.qsize()
        page.pubsub.send_all({
            "tipo": "cola_estado",
            "pendientes": pendientes,
        })
