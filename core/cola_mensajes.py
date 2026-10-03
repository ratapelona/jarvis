"""
core/cola_mensajes.py — Sistema de Cola de Mensajes (ESC-09)

Serializa TODAS las peticiones IA para proteger la VRAM:
- Una sola llamada al LLM a la vez (FIFO)
- La UI no se bloquea (encolar es instantáneo)
- Feedback visual al usuario sobre el estado de la cola
"""
import queue
import threading

from config import COLA_IA_MAXSIZE


# =============================================================================
# Cola centralizada + worker
# =============================================================================
_cola: queue.Queue = queue.Queue(maxsize=COLA_IA_MAXSIZE)
_worker_activo = False


def encolar_peticion(callback, args: tuple, page=None):
    """
    Encola una petición IA para procesamiento secuencial.

    Args:
        callback: función a ejecutar (ej: _procesar_ia_wrapper)
        args: tupla de argumentos para el callback
        page: referencia a la página Flet para feedback visual (opcional)
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
