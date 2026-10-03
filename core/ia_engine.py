"""
core/ia_engine.py — Motor de IA (Enrutamiento + Function Calling)

Refactorizado desde cerebro.py:
- SEC-11: Sanitización de inputs antes de la API
- ESC-05: Ventana deslizante de historial (últimos 20 mensajes)
- ESC-07: ThreadPoolExecutor para peticiones IA
- Separación limpia de herramientas via tool_executor
"""
import json
import time
import threading
import datetime
from concurrent.futures import ThreadPoolExecutor

import requests
import pygame

from config import (
    OLLAMA_API_URL,
    API_HEADERS,
    MODELO_PRINCIPAL,
    NOMBRES_APPS,
    VENTANA_HISTORIAL,
    MAX_WORKERS_IA,
    TEMPERATURA,
)
from core.sanitizador import sanitizar_input, obtener_directiva_sistema_sanitizacion
from core import tool_executor
from core.plugin_manager import plugin_manager
from data import sql_store

# =============================================================================
# Thread pool para peticiones IA (ESC-07)
# =============================================================================
_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS_IA)

# =============================================================================
# Definición de herramientas para function calling
# =============================================================================
HERRAMIENTAS_ADMIN = [
    {"type": "function", "function": {"name": "abrir_app", "description": "Abre aplicacion.", "parameters": {"type": "object", "properties": {"nombre_app": {"type": "string"}}, "required": ["nombre_app"]}}},
    {"type": "function", "function": {"name": "buscar_internet", "description": "Busca en web.", "parameters": {"type": "object", "properties": {"tema_a_buscar": {"type": "string"}}, "required": ["tema_a_buscar"]}}},
    {"type": "function", "function": {"name": "crear_pdf", "description": "Crea documento PDF.", "parameters": {"type": "object", "properties": {"nombre_archivo": {"type": "string"}, "contenido_texto": {"type": "string"}}, "required": ["nombre_archivo", "contenido_texto"]}}},
    {"type": "function", "function": {"name": "crear_archivo", "description": "Escribe codigo fuente o texto. Siempre se guardara en el sandbox del proyecto (carpeta output/).", "parameters": {"type": "object", "properties": {"nombre_archivo": {"type": "string"}, "contenido": {"type": "string"}}, "required": ["nombre_archivo", "contenido"]}}},
    {"type": "function", "function": {"name": "escanear_pantalla_ocr", "description": "Toma una captura de pantalla y usa OCR para encontrar texto. Retorna el texto encontrado y sus coordenadas X, Y.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "mover_y_click_mouse", "description": "Mueve y hace click en coordenadas fisicas de la pantalla.", "parameters": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "boton": {"type": "string", "description": "left o right"}}, "required": ["x", "y", "boton"]}}},
    {"type": "function", "function": {"name": "escribir_teclado", "description": "Escribe texto con el teclado fisico.", "parameters": {"type": "object", "properties": {"texto": {"type": "string"}}, "required": ["texto"]}}},
    {"type": "function", "function": {"name": "presionar_tecla", "description": "Presiona tecla especial (enter, tab, space, etc).", "parameters": {"type": "object", "properties": {"tecla": {"type": "string"}}, "required": ["tecla"]}}},
    {"type": "function", "function": {"name": "escanear_entorno_sistema", "description": "Obtiene la lista de ventanas activas y resolucion para saber donde clickear.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "delegar_tarea_larga", "description": "Inicia un agente en segundo plano para tareas complejas o largas sin bloquear la conversacion.", "parameters": {"type": "object", "properties": {"objetivo": {"type": "string"}}, "required": ["objetivo"]}}},
    {"type": "function", "function": {"name": "navegar_y_leer_pantalla", "description": "Navega a una URL y lee todo el texto de la pantalla. ÚSALA SIEMPRE para buscar datos actuales. ADVERTENCIA: Solo debes enviar el parámetro 'url'. Tienes PROHIBIDO inventar parámetros adicionales como 'selector', 'modo' o cualquier otro.", "parameters": {"type": "object", "properties": {"url": {"type": "string", "description": "La URL exacta a la que quieres navegar."}}, "required": ["url"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "escribir_en_elemento", "description": "Escribe texto en un elemento DOM (usar su selector).", "parameters": {"type": "object", "properties": {"selector": {"type": "string"}, "texto": {"type": "string"}}, "required": ["selector", "texto"]}}},
    {"type": "function", "function": {"name": "click_en_elemento", "description": "Haz click en un elemento DOM (usar su selector).", "parameters": {"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]}}},
    {"type": "function", "function": {"name": "escanear_entorno_uia", "description": "Obtiene los elementos de la interfaz grafica nativa Windows.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "click_uia", "description": "Hace click en elemento de ventana Windows nativa usando UIA.", "parameters": {"type": "object", "properties": {"titulo_ventana": {"type": "string"}, "nombre_control": {"type": "string"}, "tipo_control": {"type": "string", "default": "Button"}}, "required": ["titulo_ventana", "nombre_control"]}}},
    {"type": "function", "function": {"name": "escribir_uia", "description": "Escribe en elemento de ventana Windows nativa usando UIA.", "parameters": {"type": "object", "properties": {"titulo_ventana": {"type": "string"}, "nombre_control": {"type": "string"}, "texto": {"type": "string"}}, "required": ["titulo_ventana", "nombre_control", "texto"]}}},
]


# =============================================================================
# Ejecutor de herramientas — mapea nombre de función a tool_executor
# =============================================================================
def _ejecutar_herramienta(nombre_funcion: str, argumentos: dict, page, usuario: str) -> str:
    """Ejecuta una herramienta y retorna el resultado como string."""

    if nombre_funcion == "abrir_app":
        return tool_executor.abrir_app(argumentos.get("nombre_app", ""), usuario)

    elif nombre_funcion == "buscar_internet":
        return tool_executor.buscar_internet(argumentos.get("tema_a_buscar", ""), usuario)

    elif nombre_funcion == "crear_pdf":
        return tool_executor.crear_pdf_seguro(
            argumentos.get("nombre_archivo", ""),
            argumentos.get("contenido_texto", ""),
            usuario,
        )

    elif nombre_funcion == "crear_archivo":
        return tool_executor.crear_archivo_seguro(
            argumentos.get("nombre_archivo", ""),
            argumentos.get("contenido", ""),
            usuario,
        )

    elif nombre_funcion == "escanear_pantalla_ocr":
        return tool_executor.escanear_pantalla_ocr(usuario)

    elif nombre_funcion == "mover_y_click_mouse":
        return tool_executor.mover_y_click(
            argumentos.get("x", 0),
            argumentos.get("y", 0),
            argumentos.get("boton", "left"),
            usuario,
        )

    elif nombre_funcion == "escribir_teclado":
        return tool_executor.escribir_teclado(argumentos.get("texto", ""), usuario)

    elif nombre_funcion == "presionar_tecla":
        return tool_executor.presionar_tecla(argumentos.get("tecla", ""), usuario)

    elif nombre_funcion == "escanear_entorno_sistema":
        return tool_executor.escanear_entorno_sistema(usuario)

    elif nombre_funcion == "delegar_tarea_larga":
        from core.agente import agente_autonomo_background
        objetivo = argumentos.get("objetivo", "")
        threading.Thread(
            target=agente_autonomo_background,
            args=(page, objetivo, usuario),
            daemon=True,
        ).start()
        return f"Agente iniciado en segundo plano para: '{objetivo}'"

    elif nombre_funcion == "navegar_y_leer_pantalla":
        return tool_executor.navegar_y_leer_pantalla(argumentos.get("url", ""), usuario)
    elif nombre_funcion == "escribir_en_elemento":
        return tool_executor.escribir_en_elemento(argumentos.get("selector", ""), argumentos.get("texto", ""), usuario)
    elif nombre_funcion == "click_en_elemento":
        return tool_executor.click_en_elemento(argumentos.get("selector", ""), usuario)

    elif nombre_funcion == "escanear_entorno_uia":
        return tool_executor.escanear_entorno_uia(usuario)
    elif nombre_funcion == "click_uia":
        return tool_executor.click_uia(argumentos.get("titulo_ventana", ""), argumentos.get("nombre_control", ""), argumentos.get("tipo_control", "Button"), usuario)
    elif nombre_funcion == "escribir_uia":
        return tool_executor.escribir_uia(argumentos.get("titulo_ventana", ""), argumentos.get("nombre_control", ""), argumentos.get("texto", ""), usuario)

    if plugin_manager.puede_ejecutar(nombre_funcion):
        return plugin_manager.ejecutar_herramienta_plugin(nombre_funcion, argumentos, usuario)

    return f"Herramienta '{nombre_funcion}' no reconocida."


# =============================================================================
# Motor principal de procesamiento IA
# =============================================================================
def procesar_peticion_ia(
    page,
    texto_usuario: str,
    usar_voz: bool = True,
    id_peticion: int = 0,
    id_peticion_ref: list = None,
    usuario_activo: str = None,
    rol_activo: str = None,
    conversacion_activa_id_ref: list = None,
):
    """
    Procesa una petición del usuario: sanitiza, construye contexto, llama a la API,
    ejecuta herramientas si es necesario, y publica resultados en la UI.

    id_peticion_ref: lista [int] mutable para comparar contra la petición global
    conversacion_activa_id_ref: lista [int|None] mutable para la conversación activa
    """
    conversacion_activa_id = conversacion_activa_id_ref[0] if conversacion_activa_id_ref else None
    id_peticion_global = id_peticion_ref[0] if id_peticion_ref else id_peticion

    # --- 1. Gestión de conversación SQL ---
    if conversacion_activa_id is None:
        conversacion_activa_id = sql_store.crear_nueva_conversacion(usuario_activo, texto_usuario)
        if conversacion_activa_id_ref is not None:
            conversacion_activa_id_ref[0] = conversacion_activa_id
        page.pubsub.send_all({"tipo": "actualizar_sidebar"})

    sql_store.guardar_mensaje_sql(conversacion_activa_id, "user", texto_usuario)

    # --- 2. Memoria vectorial (subconsciente) ---
    # Desactivada por fase de pruebas. No se guardan ni leen recuerdos a largo plazo.
    contexto_memoria = "No hay recuerdos a largo plazo."

    # --- 3. Sanitización del input (SEC-11) ---
    texto_sanitizado = sanitizar_input(texto_usuario)
    directiva_sanitizacion = obtener_directiva_sistema_sanitizacion()

    # --- 4. Construcción del system prompt según rol ---
    if rol_activo == "admin":
        fecha_hoy = datetime.datetime.now().strftime("%d de %B de %Y")
        instrucciones = (
            f"Eres Jarvis, el núcleo agéntico y mentor de Alejandro. Hoy es {fecha_hoy}.\n\n"
            
            "DIRECTRICES DE COMPORTAMIENTO (Basado en la intención del usuario):\n"
            "1. MODO EJECUCIÓN (Si el usuario pide buscar, abrir, automatizar o usar herramientas):\n"
            "- TIENES ESTRICTAMENTE PROHIBIDO generar texto conversacional, explicaciones o pasos.\n"
            "- TU ÚNICA SALIDA VÁLIDA es invocar la herramienta correspondiente mediante Function Calling nativo.\n"
            "- Si necesitas hacer múltiples pasos (ej. buscar y luego leer), ejecuta SOLO LA PRIMERA HERRAMIENTA. Espera el resultado del sistema antes de ejecutar la siguiente.\n\n"
            
            "2. MODO MENTOR (Solo si el usuario pide aprender, teoría, o hace una pregunta conceptual):\n"
            "- Actúa con el Método de Enseñanza Profunda.\n"
            "- Explica las cosas dos veces: 1) Intuitivamente (analogías) y 2) Técnicamente (bajo nivel).\n"
            "- Desglosa los sistemas en 'Modelos Mentales' y explica el paso a paso físicamente.\n"
            "- Cero respuestas cortantes en este modo.\n\n"
            
            "3. AISLAMIENTO DE MEMORIA:\n"
            "- Solo toma en cuenta el historial reciente.\n\n"
            
            f"4. SANITIZACIÓN:\n- {directiva_sanitizacion}\n"
        )
        herramientas_permitidas = HERRAMIENTAS_ADMIN + plugin_manager.obtener_herramientas_activas()
    else:
        instrucciones = (
            f"Eres un asistente amigable platicando con {usuario_activo}.\n"
            "- NO eres Jarvis. No tienes acceso al sistema operativo.\n"
            "- Platica de manera casual y amigable.\n"
            "- Si te piden abrir aplicaciones o alterar el sistema, diles amablemente que no tienes permisos de Administrador.\n\n"
            f"{directiva_sanitizacion}"
        )
        herramientas_permitidas = []

    # --- 5. Ventana deslizante de historial (ESC-05) ---
    mensajes_historial = sql_store.obtener_mensajes_de_conversacion(conversacion_activa_id)
    lista_mensajes = [{"role": "system", "content": instrucciones}]

    # Solo enviamos los últimos N mensajes a la API
    mensajes_recortados = mensajes_historial[-VENTANA_HISTORIAL:]
    for msg in mensajes_recortados:
        lista_mensajes.append({"role": msg[0], "content": msg[1]})

    # Reemplazar el último mensaje del usuario con la versión sanitizada
    if lista_mensajes and lista_mensajes[-1]["role"] == "user":
        lista_mensajes[-1]["content"] = texto_sanitizado

    # --- 6. Primera llamada a la API ---
    paquete = {
        "model": MODELO_PRINCIPAL,
        "messages": lista_mensajes,
        "stream": False,
        "temperature": TEMPERATURA,
    }
    if herramientas_permitidas:
        paquete["tools"] = herramientas_permitidas

    try:
        page.pubsub.send_all({"tipo": "pensando", "estado": True, "id": id_peticion})
        
        def _hacer_peticion_stream(paquete_req):
            paquete_req["stream"] = True
            resp = requests.post(OLLAMA_API_URL, headers=API_HEADERS, json=paquete_req, stream=True)
            texto_completo = ""
            tool_calls = []
            if resp.status_code == 200:
                page.pubsub.send_all({"tipo": "respuesta_ia_stream_start", "id": id_peticion})
                for linea in resp.iter_lines():
                    if id_peticion_ref and id_peticion != id_peticion_ref[0]:
                        break
                    if linea:
                        decoded = linea.decode('utf-8')
                        if decoded.startswith('data: ') and decoded != 'data: [DONE]':
                            try:
                                chunk = json.loads(decoded[6:])
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                if "content" in delta and delta["content"]:
                                    c = delta["content"]
                                    texto_completo += c
                                    page.pubsub.send_all({"tipo": "respuesta_ia_stream_chunk", "id": id_peticion, "chunk": c})
                                if "tool_calls" in delta:
                                    for tc in delta["tool_calls"]:
                                        idx = tc["index"]
                                        while len(tool_calls) <= idx:
                                            tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                                        if "id" in tc and tc["id"]:
                                            tool_calls[idx]["id"] += tc["id"]
                                        if "function" in tc:
                                            if "name" in tc["function"] and tc["function"]["name"]:
                                                tool_calls[idx]["function"]["name"] += tc["function"]["name"]
                                            if "arguments" in tc["function"] and tc["function"]["arguments"]:
                                                tool_calls[idx]["function"]["arguments"] += tc["function"]["arguments"]
                            except json.JSONDecodeError:
                                pass
                page.pubsub.send_all({"tipo": "respuesta_ia_stream_end", "id": id_peticion})
                msg = {}
                if texto_completo:
                    msg["content"] = texto_completo
                if tool_calls:
                    msg["tool_calls"] = tool_calls
                return 200, msg
            return resp.status_code, None

        status_code, mensaje_ia = _hacer_peticion_stream(paquete)

        # Verificar si la petición sigue siendo vigente
        if id_peticion_ref and id_peticion != id_peticion_ref[0]:
            page.pubsub.send_all({"tipo": "pensando", "estado": False, "id": id_peticion})
            return

        if status_code == 200:
            if not isinstance(mensaje_ia, dict):
                mensaje_ia = {}
            texto_para_voz = ""

            # --- 7. Bucle de ejecución de herramientas (function calling) ---
            iteraciones_herramientas = 0
            while "tool_calls" in mensaje_ia and rol_activo == "admin" and iteraciones_herramientas < 20:
                iteraciones_herramientas += 1
                lista_mensajes.append(mensaje_ia)

                for tool in mensaje_ia["tool_calls"]:
                    nombre_funcion = tool["function"]["name"]
                    argumentos = tool["function"]["arguments"]
                    
                    print(f"[*] Herramienta usada: {nombre_funcion}", flush=True)

                    if isinstance(argumentos, str):
                        try:
                            argumentos = json.loads(argumentos)
                        except (json.JSONDecodeError, ValueError):
                            argumentos = {}
                    if not isinstance(argumentos, dict):
                        argumentos = {}

                    resultado = _ejecutar_herramienta(nombre_funcion, argumentos, page, usuario_activo)

                    # Inyectar contexto especial para búsqueda web
                    if nombre_funcion == "buscar_internet":
                        resultado = (
                            f"[SISTEMA - RESULTADOS DE BÚSQUEDA]:\n{resultado}\n\n"
                            "REGLA: Analiza estos datos y responde a la pregunta original del usuario con el Método de Enseñanza Profunda."
                        )
                    else:
                        resultado = f"[SISTEMA]:\n{resultado}"

                    lista_mensajes.append({
                        "role": "tool",
                        "tool_call_id": tool.get("id"),
                        "content": resultado,
                    })

                # Siguiente llamada: enviamos el resultado y vemos si quiere usar otra herramienta o responder texto
                paquete_siguiente = {
                    "model": MODELO_PRINCIPAL,
                    "messages": lista_mensajes,
                    "stream": False,
                    "temperature": TEMPERATURA,
                    "tools": herramientas_permitidas
                }
                seg_status, mensaje_ia = _hacer_peticion_stream(paquete_siguiente)

                if seg_status != 200:
                    mensaje_ia = {"content": "El motor colapsó procesando los datos de red."}
                    break
                if not isinstance(mensaje_ia, dict):
                    mensaje_ia = {}

            texto_para_voz = mensaje_ia.get("content", "") or ""
            if not texto_para_voz.strip() and iteraciones_herramientas == 0:
                texto_para_voz = "Recibí un vacío matemático."

            # --- 8. Escritura en memorias y publicación ---
            page.pubsub.send_all({"tipo": "pensando", "estado": False, "id": id_peticion})
            if texto_para_voz.strip():
                sql_store.guardar_mensaje_sql(conversacion_activa_id, "assistant", texto_para_voz)
                # La UI ya se actualizó mediante el stream


            # --- 9. Síntesis de voz (SEC-05: shell=False) ---
            if texto_para_voz.strip() and usar_voz:
                page.pubsub.send_all({"tipo": "onda_hablando", "estado": True})
                nombre_audio = tool_executor.sintetizar_voz(texto_para_voz)
                if nombre_audio:
                    import os
                    try:
                        pygame.mixer.music.load(nombre_audio)
                        pygame.mixer.music.play()
                        while pygame.mixer.music.get_busy():
                            pygame.time.Clock().tick(10)
                        pygame.mixer.music.unload()
                    finally:
                        try:
                            os.remove(nombre_audio)
                        except OSError:
                            pass
                page.pubsub.send_all({"tipo": "onda_hablando", "estado": False})

        else:
            page.pubsub.send_all({"tipo": "pensando", "estado": False, "id": id_peticion})
            page.pubsub.send_all({
                "tipo": "respuesta_ia",
                "texto": f"[Alarma de Sistema]: El motor colapsó (Error {status_code}).",
            })

    except Exception as e:
        page.pubsub.send_all({"tipo": "pensando", "estado": False, "id": id_peticion})
        page.pubsub.send_all({"tipo": "respuesta_ia", "texto": f"[Falla Crítica]: {e}"})
