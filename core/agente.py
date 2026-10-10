"""
core/agente.py — Agente Autónomo Background (SEC-07, Modo Pesado gpt-oss:20b)

Guardarraíles:
- Blacklist de apps peligrosas (via tool_executor)
- Blacklist de teclas peligrosas (via tool_executor)
- Log de CADA acción del agente
- Límite de pasos configurable (AGENTE_MAX_PASOS)
- Sandbox en output/ para creación de archivos
- CERO llamadas directas a Ollama: toda inferencia pasa por core.cola_mensajes
- Soporte para cancelación externa mediante cancel_flag
"""
import json
import time
import threading

from config import (
    MODELO_AGENTE,
    AGENTE_MAX_PASOS,
    AGENTE_DELAY_INICIO_SECS,
    TEMPERATURA,
)
from core import tool_executor
from core.plugin_manager import plugin_manager
from core.cola_mensajes import solicitar_inferencia_ollama
from data.sql_store import log_accion


# =============================================================================
# Definición de herramientas del agente background
# =============================================================================
_HERRAMIENTAS_BG = [
    {"type": "function", "function": {"name": "navegar_y_leer_pantalla", "description": "Navega a una URL y lee todo el texto de la pantalla. ÚSALA SIEMPRE para buscar datos actuales. ADVERTENCIA: Solo debes enviar el parámetro 'url'.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "buscar_internet", "description": "Busca en web.", "parameters": {"type": "object", "properties": {"tema_a_buscar": {"type": "string"}}, "required": ["tema_a_buscar"]}}},
    {"type": "function", "function": {"name": "crear_archivo", "description": "Escribe codigo fuente o texto en un archivo fisico (Siempre se guardara en el sandbox del proyecto en la carpeta output/).", "parameters": {"type": "object", "properties": {"nombre_archivo": {"type": "string"}, "contenido": {"type": "string"}}, "required": ["nombre_archivo", "contenido"]}}},
    {"type": "function", "function": {"name": "escribir_en_elemento", "description": "Escribe en DOM.", "parameters": {"type": "object", "properties": {"selector": {"type": "string"}, "texto": {"type": "string"}}, "required": ["selector", "texto"]}}},
    {"type": "function", "function": {"name": "click_en_elemento", "description": "Click en DOM.", "parameters": {"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]}}},
    {"type": "function", "function": {"name": "escanear_entorno_uia", "description": "Extrae ventanas UIA.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "click_uia", "description": "Click UIA.", "parameters": {"type": "object", "properties": {"titulo_ventana": {"type": "string"}, "nombre_control": {"type": "string"}, "tipo_control": {"type": "string", "default": "Button"}}, "required": ["titulo_ventana", "nombre_control"]}}},
    {"type": "function", "function": {"name": "escribir_uia", "description": "Escribir UIA.", "parameters": {"type": "object", "properties": {"titulo_ventana": {"type": "string"}, "nombre_control": {"type": "string"}, "texto": {"type": "string"}}, "required": ["titulo_ventana", "nombre_control", "texto"]}}},
    {"type": "function", "function": {"name": "mover_y_click_mouse", "description": "Mueve y hace click fisico (SOLO COMO RESPALDO).", "parameters": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "boton": {"type": "string"}}, "required": ["x", "y", "boton"]}}},
    {"type": "function", "function": {"name": "escribir_teclado", "description": "Escribe texto fisico (SOLO COMO RESPALDO).", "parameters": {"type": "object", "properties": {"texto": {"type": "string"}}, "required": ["texto"]}}},
    {"type": "function", "function": {"name": "presionar_tecla", "description": "Presiona tecla especial (SOLO COMO RESPALDO).", "parameters": {"type": "object", "properties": {"tecla": {"type": "string"}}, "required": ["tecla"]}}},
    {"type": "function", "function": {"name": "escanear_pantalla_ocr", "description": "Captura pantalla OCR (SOLO COMO RESPALDO).", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "finalizar_tarea", "description": "Termina la ejecucion autonoma.", "parameters": {"type": "object", "properties": {"reporte": {"type": "string"}}, "required": ["reporte"]}}},
]


# =============================================================================
# Helper: ejecutar una herramienta por nombre (reutilizable y seguro)
# =============================================================================
def _ejecutar_herramienta_bg(func: str, args: dict, page, usuario: str, registro: list) -> str:
    if func == "finalizar_tarea":
        return "__FINALIZAR__"

    ejecutores = {
        "mover_y_click_mouse": lambda: tool_executor.mover_y_click(
            args.get("x", 0), args.get("y", 0), args.get("boton", "left"), usuario),
        "escribir_teclado": lambda: tool_executor.escribir_teclado(args.get("texto", ""), usuario),
        "presionar_tecla": lambda: tool_executor.presionar_tecla(args.get("tecla", ""), usuario),
        "escanear_pantalla_ocr": lambda: tool_executor.escanear_pantalla_ocr(usuario),
        "navegar_y_leer_pantalla": lambda: tool_executor.navegar_y_leer_pantalla(args.get("url", ""), usuario),
        "buscar_internet": lambda: tool_executor.buscar_internet(args.get("tema_a_buscar", ""), usuario),
        "crear_archivo": lambda: tool_executor.crear_archivo_seguro(
            args.get("nombre_archivo", ""), args.get("contenido", ""), usuario),
        "escribir_en_elemento": lambda: tool_executor.escribir_en_elemento(
            args.get("selector", ""), args.get("texto", ""), usuario),
        "click_en_elemento": lambda: tool_executor.click_en_elemento(args.get("selector", ""), usuario),
        "escanear_entorno_uia": lambda: tool_executor.escanear_entorno_uia(usuario),
        "click_uia": lambda: tool_executor.click_uia(
            args.get("titulo_ventana", ""), args.get("nombre_control", ""),
            args.get("tipo_control", "Button"), usuario),
        "escribir_uia": lambda: tool_executor.escribir_uia(
            args.get("titulo_ventana", ""), args.get("nombre_control", ""),
            args.get("texto", ""), usuario),
    }

    ejecutor = ejecutores.get(func)
    if not ejecutor:
        if plugin_manager.puede_ejecutar(func):
            try:
                resultado = plugin_manager.ejecutar_herramienta_plugin(func, args, usuario)
                print(f"[AGENTE] ✅ {func} (Plugin) ejecutado.", flush=True)
                registro.append(f"  - {func}: ✅ Éxito (Plugin)")
                return resultado
            except Exception as ex:
                print(f"[AGENTE] ❌ {func} falló: {ex}", flush=True)
                registro.append(f"  - {func}: ❌ Fallida ({ex})")
                return f"Error: {ex}"
        registro.append(f"  - {func}: ❌ Herramienta no disponible")
        return f"Herramienta '{func}' no disponible."

    try:
        resultado = ejecutor()
        print(f"[AGENTE] ✅ {func} ejecutado.", flush=True)
        registro.append(f"  - {func}: ✅ Éxito")
        return resultado
    except Exception as ex:
        print(f"[AGENTE] ❌ {func} falló: {ex}", flush=True)
        registro.append(f"  - {func}: ❌ Fallida ({ex})")
        return f"Error: {ex}"


# =============================================================================
# Agente autónomo con guardarraíles
# =============================================================================
def agente_autonomo_background(
    page,
    objetivo: str,
    usuario: str = "",
    delay_inicio: int = None,
    cancel_flag: threading.Event = None,
):
    """
    Ejecuta un agente autónomo en segundo plano.
    - CERO llamadas directas a Ollama: usa core.cola_mensajes.solicitar_inferencia_ollama.
    - Delay de inicio configurable.
    - Streaming de razonamiento y respuesta.
    - Reporte final detallado con registro de cada acción.
    - Soporte de cancelación graciosa.
    """
    espera = delay_inicio if delay_inicio is not None else AGENTE_DELAY_INICIO_SECS

    if page:
        page.pubsub.send_all({
            "tipo": "respuesta_ia",
            "texto": f"[AGENTE PREPARÁNDOSE]: Tienes {espera} segundos para preparar la ventana...",
        })
    time.sleep(espera)

    if cancel_flag and cancel_flag.is_set():
        print("[AGENTE] Tarea cancelada antes de iniciar.", flush=True)
        return

    if page:
        page.pubsub.send_all({
            "tipo": "respuesta_ia",
            "texto": f"[AGENTE INICIADO]: Trabajando con `{MODELO_AGENTE}` para: {objetivo}",
        })

    stream_id = f"agent-{time.time_ns()}"
    if page:
        page.pubsub.send_all({"tipo": "respuesta_ia_stream_start", "id": stream_id})
        page.pubsub.send_all({"tipo": "pensando", "estado": True, "id": stream_id, "agente": True})

    log_accion(usuario, "agente_iniciado", objetivo, f"Modelo: {MODELO_AGENTE}")

    _registro_tareas = []

    mensajes = [{
        "role": "system",
        "content": (
            f"Eres un agente de automatización de Windows con alta capacidad analítica. Tu único objetivo es: {objetivo}\n"
            "REGLAS ABSOLUTAS:\n"
            "- Tu ÚNICA forma de actuar es mediante function calling (herramientas). NUNCA generes texto conversacional.\n"
            "- Ejecuta una herramienta, espera su resultado, luego decide la siguiente acción.\n"
            "- Para tareas web usa: buscar_internet → navegar_y_leer_pantalla → escribir_en_elemento / click_en_elemento.\n"
            "- Para tareas de Windows usa: escanear_entorno_uia → click_uia / escribir_uia.\n"
            "- Para guardar resultados usa: crear_archivo.\n"
            "- Si una herramienta falla, intenta un enfoque alternativo o pasa a la siguiente subtarea.\n"
            "- Cuando TODAS las subtareas estén terminadas (con éxito o fallo), DEBES llamar a 'finalizar_tarea'.\n"
            "- El reporte de finalizar_tarea debe listar cada subtarea así:\n"
            "  'Reporte:\n- [subtarea]: Éxito\n- [subtarea]: Fallida (razón)'\n"
            f"- NO puedes ejecutar más de {AGENTE_MAX_PASOS} herramientas en total. Si llegas al límite, llama a finalizar_tarea.\n"
        ),
    }]

    def _on_chunk(c: str):
        if page and c:
            page.pubsub.send_all({"tipo": "respuesta_ia_stream_chunk", "id": stream_id, "chunk": c})

    def _on_think_chunk(c: str):
        if page and c:
            page.pubsub.send_all({"tipo": "respuesta_ia_stream_think_chunk", "id": stream_id, "chunk": c})

    for iteracion in range(AGENTE_MAX_PASOS):
        # Verificar señal de cancelación
        if cancel_flag and cancel_flag.is_set():
            print(f"[AGENTE] 🛑 Señal de cancelación detectada en iteración {iteracion + 1}.", flush=True)
            if page:
                page.pubsub.send_all({
                    "tipo": "respuesta_ia",
                    "texto": f"🛑 [AGENTE CANCELADO]: Tarea '{objetivo}' detenida por el usuario.",
                })
            log_accion(usuario, "agente_cancelado", objetivo, f"Cancelado en paso {iteracion + 1}")
            break

        paquete = {
            "model": MODELO_AGENTE,
            "messages": mensajes,
            "tools": _HERRAMIENTAS_BG + plugin_manager.obtener_herramientas_activas(),
            "stream": True,
            "temperature": TEMPERATURA,
        }

        try:
            print(f"[AGENTE] Iteración {iteracion + 1}/{AGENTE_MAX_PASOS} — solicitando a cola_mensajes ({MODELO_AGENTE})...", flush=True)
            status_code, msg_ia = solicitar_inferencia_ollama(
                paquete=paquete,
                on_chunk=_on_chunk,
                on_think_chunk=_on_think_chunk,
                cancel_flag=cancel_flag,
                stream=True,
            )

            if cancel_flag and cancel_flag.is_set():
                break

            if status_code != 200:
                raise RuntimeError(f"Error en inferencia: código {status_code}")

            if not isinstance(msg_ia, dict):
                print("[AGENTE] msg_ia no es dict, saliendo del loop.", flush=True)
                break

            mensajes.append(msg_ia)
            tiene_tools = "tool_calls" in msg_ia and bool(msg_ia["tool_calls"])

            if tiene_tools:
                terminado = False
                for tool in msg_ia["tool_calls"]:
                    func = tool["function"]["name"]
                    args = tool["function"]["arguments"]

                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except (json.JSONDecodeError, ValueError):
                            args = {}
                    if not isinstance(args, dict):
                        args = {}

                    tool_id = tool.get("id", f"call_{time.time_ns()}")

                    if func == "finalizar_tarea":
                        reporte = args.get("reporte", "Tarea finalizada.")
                        if _registro_tareas:
                            resumen = "\n".join(_registro_tareas)
                            reporte_completo = f"{reporte}\n\n📋 Registro detallado:\n{resumen}"
                        else:
                            reporte_completo = reporte

                        if page:
                            page.pubsub.send_all({
                                "tipo": "respuesta_ia",
                                "texto": f"[AGENTE COMPLETADO]:\n{reporte_completo}",
                            })
                        log_accion(usuario, "agente_completado", objetivo, reporte_completo)
                        terminado = True
                        break

                    # Ejecutar herramienta con guardarraíles
                    resultado = _ejecutar_herramienta_bg(func, args, page, usuario, _registro_tareas)
                    mensajes.append({"role": "tool", "tool_call_id": tool_id, "content": resultado})

                if terminado:
                    break

            else:
                # El modelo respondió con texto en vez de tool_calls nativo: intentar fallback JSON
                content_text = msg_ia.get("content", "").strip()
                tool_call_ejecutado = False

                if content_text:
                    try:
                        texto_limpio = content_text
                        if "```" in texto_limpio:
                            import re
                            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", texto_limpio, re.DOTALL)
                            if match:
                                texto_limpio = match.group(1)

                        parsed = json.loads(texto_limpio)
                        func = parsed.get("name") or parsed.get("function") or parsed.get("tool")
                        args = parsed.get("arguments") or parsed.get("parameters") or parsed.get("args") or {}
                        if isinstance(args, str):
                            args = json.loads(args)

                        if func:
                            print(f"[AGENTE] Tool call detectado en texto fallback: {func}", flush=True)
                            resultado_tc = _ejecutar_herramienta_bg(func, args, page, usuario, _registro_tareas)
                            if resultado_tc == "__FINALIZAR__":
                                break
                            mensajes.append({"role": "tool", "tool_call_id": "text_fallback", "content": resultado_tc})
                            tool_call_ejecutado = True
                    except Exception:
                        pass

                if not tool_call_ejecutado:
                    mensajes.append({
                        "role": "user",
                        "content": (
                            "INSTRUCCIÓN DEL SISTEMA: Debes responder EXCLUSIVAMENTE con una llamada a herramienta (tool call). "
                            "NO generes texto libre. Elige la herramienta apropiada y ejecútala."
                        )
                    })

        except Exception as e:
            _registro_tareas.append(f"  - iteración {iteracion + 1}: ❌ Error interno ({e})")
            log_accion(usuario, "agente_error", objetivo, str(e))
            continue

    if page:
        page.pubsub.send_all({"tipo": "pensando", "estado": False, "id": stream_id, "agente": True})
        page.pubsub.send_all({"tipo": "respuesta_ia_stream_end", "id": stream_id})
