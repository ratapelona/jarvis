"""
core/agente.py — Agente Autónomo Background (SEC-07)

Guardarraíles:
- Blacklist de apps peligrosas (via tool_executor)
- Blacklist de teclas peligrosas (via tool_executor)
- Log de CADA acción del agente
- Límite de pasos configurable
"""
import json
import time

import requests

from config import (
    OLLAMA_API_URL,
    API_HEADERS,
    MODELO_AGENTE,
    AGENTE_MAX_PASOS,
    AGENTE_DELAY_INICIO_SECS,
    TEMPERATURA,
)
from core import tool_executor
from core.plugin_manager import plugin_manager
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
# Helper: ejecutar una herramienta por nombre (reutilizable desde tool_calls y fallback JSON)
# Retorna el resultado como string, o "__FINALIZAR__" si es finalizar_tarea.
# =============================================================================
def _ejecutar_herramienta_bg(func: str, args: dict, page, usuario: str, registro: list) -> str:
    if func == "finalizar_tarea":
        return "__FINALIZAR__"

    ejecutores = {
        "mover_y_click_mouse": lambda: tool_executor.mover_y_click(
            args.get("x", 0), args.get("y", 0), args.get("boton", "left"), usuario),
        "escribir_teclado":    lambda: tool_executor.escribir_teclado(args.get("texto", ""), usuario),
        "presionar_tecla":     lambda: tool_executor.presionar_tecla(args.get("tecla", ""), usuario),
        "escanear_pantalla_ocr": lambda: tool_executor.escanear_pantalla_ocr(usuario),
        "navegar_y_leer_pantalla": lambda: tool_executor.navegar_y_leer_pantalla(args.get("url", ""), usuario),
        "buscar_internet":     lambda: tool_executor.buscar_internet(args.get("tema_a_buscar", ""), usuario),
        "crear_archivo":       lambda: tool_executor.crear_archivo_seguro(
            args.get("nombre_archivo", ""), args.get("contenido", ""), usuario),
        "escribir_en_elemento": lambda: tool_executor.escribir_en_elemento(
            args.get("selector", ""), args.get("texto", ""), usuario),
        "click_en_elemento":   lambda: tool_executor.click_en_elemento(args.get("selector", ""), usuario),
        "escanear_entorno_uia": lambda: tool_executor.escanear_entorno_uia(usuario),
        "click_uia":           lambda: tool_executor.click_uia(
            args.get("titulo_ventana", ""), args.get("nombre_control", ""),
            args.get("tipo_control", "Button"), usuario),
        "escribir_uia":        lambda: tool_executor.escribir_uia(
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
def agente_autonomo_background(page, objetivo: str, usuario: str = "", delay_inicio: int = None):
    """
    Ejecuta un agente autónomo en segundo plano con:
    - Delay de inicio configurable (None = usar AGENTE_DELAY_INICIO_SECS)
    - Modo silencioso: no reporta en tiempo real, solo al final
    - Reporte final en formato de lista con estado de cada subtarea
    - Logging de cada acción
    """
    espera = delay_inicio if delay_inicio is not None else AGENTE_DELAY_INICIO_SECS

    page.pubsub.send_all({
        "tipo": "respuesta_ia",
        "texto": f"[AGENTE PREPARÁNDOSE]: Tienes {espera} segundos para preparar la ventana...",
    })
    time.sleep(espera)

    page.pubsub.send_all({
        "tipo": "respuesta_ia",
        "texto": f"[AGENTE INICIADO]: Trabajando en modo silencioso para: {objetivo}",
    })

    log_accion(usuario, "agente_iniciado", objetivo, "")

    # Lista interna de tareas ejecutadas (solo se muestra en el reporte final)
    _registro_tareas = []

    mensajes = [{
        "role": "system",
        "content": (
            f"Eres un agente de automatización de Windows. Tu único objetivo es: {objetivo}\n"
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
            "- NO puedes ejecutar más de 15 herramientas en total. Si llegas al límite, llama a finalizar_tarea.\n"
        ),
    }]

    for iteracion in range(AGENTE_MAX_PASOS):
        paquete = {
            "model": MODELO_AGENTE,
            "messages": mensajes,
            "tools": _HERRAMIENTAS_BG + plugin_manager.obtener_herramientas_activas(),
            "stream": False,
            "temperature": TEMPERATURA,
        }

        try:
            print(f"[AGENTE] Iteración {iteracion + 1}/{AGENTE_MAX_PASOS} — enviando petición...", flush=True)
            resp_raw = requests.post(OLLAMA_API_URL, headers=API_HEADERS, json=paquete)
            resp = resp_raw.json()

            # Diagnóstico: ver qué devuelve el modelo
            finish_reason = resp.get("choices", [{}])[0].get("finish_reason", "N/A")
            msg_ia = resp.get("choices", [{}])[0].get("message", {})
            tiene_tools = "tool_calls" in msg_ia
            tiene_content = bool(msg_ia.get("content", "").strip())
            print(f"[AGENTE] finish_reason={finish_reason} | tool_calls={tiene_tools} | content={tiene_content}", flush=True)
            if tiene_content and not tiene_tools:
                # Mostrar los primeros 200 chars del content para diagnóstico
                print(f"[AGENTE] content[:200]: {str(msg_ia.get('content', ''))[:200]}", flush=True)

            if not isinstance(msg_ia, dict):
                print("[AGENTE] Error: msg_ia no es dict, rompiendo loop", flush=True)
                break
            mensajes.append(msg_ia)

            if "tool_calls" in msg_ia:
                terminado = False
                for tool in msg_ia["tool_calls"]:
                    func = tool["function"]["name"]
                    args = tool["function"]["arguments"]
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except (json.JSONDecodeError, ValueError):
                            args = {}

                    tool_id = tool.get("id")

                    if func == "finalizar_tarea":
                        reporte = args.get("reporte", "")
                        # Inyectar el registro interno al reporte
                        if _registro_tareas:
                            resumen = "\n".join(_registro_tareas)
                            reporte_completo = f"{reporte}\n\n📋 Registro detallado:\n{resumen}"
                        else:
                            reporte_completo = reporte
                        page.pubsub.send_all({
                            "tipo": "respuesta_ia",
                            "texto": f"[AGENTE COMPLETADO]:\n{reporte_completo}",
                        })
                        log_accion(usuario, "agente_completado", objetivo, reporte_completo)
                        terminado = True
                        break

                    elif func == "mover_y_click_mouse":
                        try:
                            resultado = tool_executor.mover_y_click(
                                args.get("x", 0), args.get("y", 0),
                                args.get("boton", "left"), usuario,
                            )
                            _registro_tareas.append(f"  - mover_y_click ({args.get('x')},{args.get('y')}): ✅ Éxito")
                        except Exception as ex:
                            resultado = f"Error: {ex}"
                            _registro_tareas.append(f"  - mover_y_click ({args.get('x')},{args.get('y')}): ❌ Fallida")
                        mensajes.append({"role": "tool", "tool_call_id": tool_id, "content": resultado})

                    elif func == "escribir_teclado":
                        try:
                            resultado = tool_executor.escribir_teclado(args.get("texto", ""), usuario)
                            _registro_tareas.append(f"  - escribir_teclado: ✅ Éxito")
                        except Exception as ex:
                            resultado = f"Error: {ex}"
                            _registro_tareas.append(f"  - escribir_teclado: ❌ Fallida")
                        mensajes.append({"role": "tool", "tool_call_id": tool_id, "content": resultado})

                    elif func == "presionar_tecla":
                        try:
                            resultado = tool_executor.presionar_tecla(args.get("tecla", ""), usuario)
                            _registro_tareas.append(f"  - presionar_tecla ({args.get('tecla')}): ✅ Éxito")
                        except Exception as ex:
                            resultado = f"Error: {ex}"
                            _registro_tareas.append(f"  - presionar_tecla: ❌ Fallida")
                        mensajes.append({"role": "tool", "tool_call_id": tool_id, "content": resultado})

                    elif func == "escanear_pantalla_ocr":
                        try:
                            resultado = tool_executor.escanear_pantalla_ocr(usuario)
                            _registro_tareas.append(f"  - escanear_pantalla_ocr: ✅ Éxito")
                        except Exception as ex:
                            resultado = f"Error: {ex}"
                            _registro_tareas.append(f"  - escanear_pantalla_ocr: ❌ Fallida")
                        mensajes.append({"role": "tool", "tool_call_id": tool_id, "content": resultado})

                    elif func == "navegar_y_leer_pantalla":
                        try:
                            resultado = tool_executor.navegar_y_leer_pantalla(args.get("url", ""), usuario)
                            _registro_tareas.append(f"  - navegar ({args.get('url', '')[:40]}): ✅ Éxito")
                        except Exception as ex:
                            resultado = f"Error: {ex}"
                            _registro_tareas.append(f"  - navegar ({args.get('url', '')[:40]}): ❌ Fallida")
                        mensajes.append({"role": "tool", "tool_call_id": tool_id, "content": resultado})

                    elif func == "buscar_internet":
                        try:
                            resultado = tool_executor.buscar_internet(args.get("tema_a_buscar", ""), usuario)
                            _registro_tareas.append(f"  - buscar_internet ('{args.get('tema_a_buscar', '')[:30]}'): ✅ Éxito")
                        except Exception as ex:
                            resultado = f"Error: {ex}"
                            _registro_tareas.append(f"  - buscar_internet: ❌ Fallida")
                        mensajes.append({"role": "tool", "tool_call_id": tool_id, "content": resultado})

                    elif func == "crear_archivo":
                        try:
                            resultado = tool_executor.crear_archivo_seguro(args.get("nombre_archivo", ""), args.get("contenido", ""), usuario)
                            _registro_tareas.append(f"  - crear_archivo ('{args.get('nombre_archivo', '')}'): ✅ Éxito")
                        except Exception as ex:
                            resultado = f"Error: {ex}"
                            _registro_tareas.append(f"  - crear_archivo: ❌ Fallida")
                        mensajes.append({"role": "tool", "tool_call_id": tool_id, "content": resultado})

                    elif func == "escribir_en_elemento":
                        try:
                            resultado = tool_executor.escribir_en_elemento(args.get("selector", ""), args.get("texto", ""), usuario)
                            _registro_tareas.append(f"  - escribir_en_elemento ('{args.get('selector', '')[:30]}'): ✅ Éxito")
                        except Exception as ex:
                            resultado = f"Error: {ex}"
                            _registro_tareas.append(f"  - escribir_en_elemento: ❌ Fallida")
                        mensajes.append({"role": "tool", "tool_call_id": tool_id, "content": resultado})

                    elif func == "click_en_elemento":
                        try:
                            resultado = tool_executor.click_en_elemento(args.get("selector", ""), usuario)
                            _registro_tareas.append(f"  - click_en_elemento ('{args.get('selector', '')[:30]}'): ✅ Éxito")
                        except Exception as ex:
                            resultado = f"Error: {ex}"
                            _registro_tareas.append(f"  - click_en_elemento: ❌ Fallida")
                        mensajes.append({"role": "tool", "tool_call_id": tool_id, "content": resultado})

                    elif func == "escanear_entorno_uia":
                        try:
                            resultado = tool_executor.escanear_entorno_uia(usuario)
                            _registro_tareas.append(f"  - escanear_entorno_uia: ✅ Éxito")
                        except Exception as ex:
                            resultado = f"Error: {ex}"
                            _registro_tareas.append(f"  - escanear_entorno_uia: ❌ Fallida")
                        mensajes.append({"role": "tool", "tool_call_id": tool_id, "content": resultado})

                    elif func == "click_uia":
                        try:
                            resultado = tool_executor.click_uia(args.get("titulo_ventana", ""), args.get("nombre_control", ""), args.get("tipo_control", "Button"), usuario)
                            _registro_tareas.append(f"  - click_uia ('{args.get('nombre_control', '')}'): ✅ Éxito")
                        except Exception as ex:
                            resultado = f"Error: {ex}"
                            _registro_tareas.append(f"  - click_uia: ❌ Fallida")
                        mensajes.append({"role": "tool", "tool_call_id": tool_id, "content": resultado})

                    elif func == "escribir_uia":
                        try:
                            resultado = tool_executor.escribir_uia(args.get("titulo_ventana", ""), args.get("nombre_control", ""), args.get("texto", ""), usuario)
                            _registro_tareas.append(f"  - escribir_uia ('{args.get('nombre_control', '')}'): ✅ Éxito")
                        except Exception as ex:
                            resultado = f"Error: {ex}"
                            _registro_tareas.append(f"  - escribir_uia: ❌ Fallida")
                        mensajes.append({"role": "tool", "tool_call_id": tool_id, "content": resultado})

                    elif plugin_manager.puede_ejecutar(func):
                        try:
                            resultado = plugin_manager.ejecutar_herramienta_plugin(func, args, usuario)
                            _registro_tareas.append(f"  - {func}: ✅ Éxito (Plugin)")
                        except Exception as ex:
                            resultado = f"Error: {ex}"
                            _registro_tareas.append(f"  - {func}: ❌ Fallida ({ex})")
                        mensajes.append({"role": "tool", "tool_call_id": tool_id, "content": resultado})

                    else:
                        mensajes.append({
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "content": f"Herramienta '{func}' no disponible para el agente.",
                        })
                        _registro_tareas.append(f"  - {func}: ❌ Herramienta no disponible")

                if terminado:
                    break
            else:
                # El modelo respondió con texto en vez de tool_calls
                content_text = msg_ia.get("content", "").strip()
                print(f"[AGENTE] Modelo respondió con texto. Intentando parsear como tool call JSON. Iter {iteracion+1}", flush=True)

                # Intentar parsear el content como tool call JSON (qwen3 a veces hace esto)
                tool_call_ejecutado = False
                try:
                    # Limpiar posibles bloques de código markdown: ```json ... ```
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
                        print(f"[AGENTE] Tool call detectado en texto: {func}({args})", flush=True)
                        # Ejecutar como si fuera un tool call real
                        resultado_tc = _ejecutar_herramienta_bg(func, args, page, usuario, _registro_tareas)
                        if resultado_tc == "__FINALIZAR__":
                            break
                        mensajes.append({"role": "tool", "tool_call_id": "text_fallback", "content": resultado_tc})
                        tool_call_ejecutado = True
                except (json.JSONDecodeError, Exception):
                    pass

                if not tool_call_ejecutado:
                    # No era JSON válido — re-inyectar instrucción de usar herramientas
                    print(f"[AGENTE] No se pudo parsear como tool call. Re-inyectando instrucción.", flush=True)
                    mensajes.append({
                        "role": "user",
                        "content": (
                            "INSTRUCCIÓN DEL SISTEMA: Debes responder EXCLUSIVAMENTE con una llamada a herramienta (tool call). "
                            "NO generes texto. Elige la herramienta más apropiada para el siguiente paso del objetivo y ejecútala ahora."
                        )
                    })

        except Exception as e:
            _registro_tareas.append(f"  - iteración {iteracion + 1}: ❌ Error interno ({e})")
            log_accion(usuario, "agente_error", objetivo, str(e))
            # No romper el loop — continuar con la siguiente iteración
            continue
