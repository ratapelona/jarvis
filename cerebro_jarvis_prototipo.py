from bs4 import BeautifulSoup
import faster_whisper
import sounddevice
from scipy.io import wavfile
import numpy
import requests 
import subprocess
import time
import pygame
import os
import glob
from ddgs import DDGS
from dotenv import load_dotenv
import openwakeword
from openwakeword.model import Model
from fpdf import FPDF
import flet as ft
import threading
import json
import random

# IMPORTACIONES DE ARQUITECTURA AISLADA
import seguridad 
import dattabase

seguridad.inicializar_seguridad()

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

load_dotenv()

navegador_web = None

def obtener_navegador():
    global navegador_web
    if navegador_web is None:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--window-size=1920x1080")
        navegador_web = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    return navegador_web

hz = 16000
matriz_len = hz * 5

carga_modelo = None
guardiano = None
mic_guardian = None

url_api = "https://api.groq.com/openai/v1/chat/completions"
api_key = os.getenv("GROQ_API_KEY", "")
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}
id_peticion_global = 0

# --- GAFETES DE ESTADO GLOBAL ---
usuario_activo = None
rol_activo = None
conversacion_activa_id = None 

mis_apps = {
    "spotify": "start spotify",
    "edge": "start msedge",
    "calculadora": "start calc",
    "archivos": "explorer",
    "obs": 'start "" "C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe"',
    "docker": 'start "" "C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe"',
    "packet tracer": 'start "" "C:\\Program Files\\Cisco Packet Tracer 9.0.0\\bin\\PacketTracer.exe"',
    "ollama": 'start "" "C:\\Users\\alexa\\AppData\\Local\\Programs\\Ollama\\ollama app.exe"',
    "microsoft store": "start ms-windows-store:",
    "chrome": 'start "" "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"',
    "discord": 'start "" "C:\\Users\\alexa\\AppData\\Local\\Discord\\Update.exe" --processStart Discord.exe',
    "steam": 'start "" "C:\\Program Files (x86)\\Steam\\steam.exe"',
    "vscode": 'start "" "C:\\Users\\alexa\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe"',
    "league of legends": 'start "" "C:\\Riot Games\\Riot Client\\RiotClientServices.exe"',
    "git bash": 'start "" "C:\\Program Files\\Git\\git-bash.exe"',
    "notepad": "notepad.exe",
    "paint": "mspaint.exe",
    "task manager": "taskmgr.exe",
    "roblox": 'start "" "C:\\Users\\alexa\\AppData\\Local\\Roblox\\Versions\\version-c5aecda2245e4fae\\RobloxPlayerBeta.exe"',
    "antigravity": 'start "" "C:\\Users\\alexa\\AppData\\Local\\Programs\\antigravity\\Antigravity.exe"',
    "antigravity ide": 'start "" "C:\\Users\\alexa\\AppData\\Local\\Programs\\Antigravity IDE\\Antigravity IDE.exe"'
}
nombres_apps = ", ".join(mis_apps.keys())

def inicializar_sistemas_audio(page):
    global carga_modelo, guardiano, mic_guardian
    pygame.mixer.init()
    try:
        openwakeword.utils.download_models()
        guardiano = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
        carga_modelo = faster_whisper.WhisperModel("base", device="cpu", compute_type="int8")
        mic_guardian = sounddevice.InputStream(samplerate=16000, channels=1, dtype='int16')
        mic_guardian.start()
        page.pubsub.send_all({"tipo": "audio_listo"})
    except Exception as e:
        print(f"Error fatal de audio: {e}")

# --- EL CEREBRO DE ENRUTAMIENTO Y EJECUCIÓN ---
def recolector_basura_asincrono(conversacion_id):
    """Verifica si la conversación supera los 20 mensajes y comprime los más antiguos."""
    try:
        mensajes = seguridad.obtener_mensajes_de_conversacion(conversacion_id)
        if len(mensajes) > 20:
            num_a_comprimir = 10 if len(mensajes) >= 10 else len(mensajes)
            mensajes_a_comprimir = mensajes[:num_a_comprimir]
            texto_historial = "\n".join([f"{msg[0]}: {msg[1]}" for msg in mensajes_a_comprimir])
            
            prompt_resumen = f"Resume brevemente estos mensajes manteniendo el contexto clave. Sé conciso:\n{texto_historial}"
            paquete = {
                "model": "qwen3:8b", 
                "messages": [{"role": "user", "content": prompt_resumen}],
                "stream": False
            }
            
            res = requests.post(url_api, headers=headers, json=paquete, timeout=30)
            if res.status_code == 200:
                resumen = res.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                resumen = re.sub(r"<think>[\s\S]*?</think>", "", resumen).strip()
                if resumen:
                    seguridad.comprimir_historial_sql(conversacion_id, num_a_comprimir, resumen)
                    print(f"🗑️ Recolector de basura actuó. {num_a_comprimir} mensajes comprimidos en la BD.")
    except Exception as e:
        print(f"Error en recolector de basura asincrono: {e}")

def procesar_peticion_ia(page, texto_usuario, usar_voz=True, id_peticion=0):
    global id_peticion_global, rol_activo, usuario_activo, conversacion_activa_id
    
    # 1. GESTIÓN DEL DIARIO EXACTO (SQL)
    if conversacion_activa_id is None:
        conversacion_activa_id = seguridad.crear_nueva_conversacion(usuario_activo, texto_usuario)
        page.pubsub.send_all({"tipo": "actualizar_sidebar"})
        
    seguridad.guardar_mensaje_sql(conversacion_activa_id, "user", texto_usuario)

    # 2. GESTIÓN DEL SUBCONSCIENTE (VECTORIAL)
    recuerdo_recuperado = dattabase.recordar(texto_usuario, usuario_activo)
    contexto_memoria = f"Recuerdos previos del usuario: {recuerdo_recuperado}" if recuerdo_recuperado else "No hay recuerdos a largo plazo."

    # 3. INGENIERÍA DE PROMPTS AVANZADA (CÓDIGO ALPHA)
    if rol_activo == "admin":
        import datetime
        fecha_hoy = datetime.datetime.now().strftime("%d de %B de %Y")
        instrucciones = (
            f"Eres Jarvis, el núcleo agéntico y mentor de {usuario_activo}. Hoy es {fecha_hoy}.\n\n"
            
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
            f"- {contexto_memoria}\n"
            "- Usa los recuerdos SOLO si tienen relación lógica directa con la pregunta actual.\n\n"
            
            "4. EJECUCIÓN SILENCIOSA DE HERRAMIENTAS:\n"
            f"- Tienes acceso a estas apps: {nombres_apps} y herramientas de sistema.\n"
            "- Las herramientas deben ejecutarse en completo SILENCIO usando el canal del sistema (Function Calling)."
        )
        herramientas_permitidas = [
            { "type": "function", "function": { "name": "abrir_app", "description": "Abre aplicacion.", "parameters": { "type": "object", "properties": {"nombre_app": {"type": "string"}}, "required": ["nombre_app"] } } },
            { "type": "function", "function": { "name": "buscar_internet", "description": "Busca en web.", "parameters": { "type": "object", "properties": {"tema_a_buscar": {"type": "string"}}, "required": ["tema_a_buscar"] } } },
            { "type": "function", "function": { "name": "crear_pdf", "description": "Crea documento PDF.", "parameters": { "type": "object", "properties": {"nombre_archivo": {"type": "string"}, "contenido_texto": {"type": "string"}}, "required": ["nombre_archivo", "contenido_texto"] } } },
            { "type": "function", "function": { "name": "crear_archivo", "description": "Escribe codigo fuente. (Siempre se guardara en W:\\prcts\\jarvis_proyect\\output)", "parameters": { "type": "object", "properties": {"nombre_archivo": {"type": "string"}, "contenido": {"type": "string"}}, "required": ["nombre_archivo", "contenido"] } } },
            { "type": "function", "function": { "name": "escanear_pantalla_web", "description": "Escanea la pantalla web actual o navega a una URL dada.", "parameters": { "type": "object", "properties": {"url": {"type": "string", "description": "URL opcional a visitar"}}, "required": [] } } },
            { "type": "function", "function": { "name": "ejecutar_click", "description": "Hace clic en un elemento web.", "parameters": { "type": "object", "properties": {"selector": {"type": "string", "description": "Texto, clase, ID o selector CSS del elemento"}}, "required": ["selector"] } } },
            { "type": "function", "function": { "name": "inyectar_texto", "description": "Escribe texto en un elemento web.", "parameters": { "type": "object", "properties": {"selector": {"type": "string"}, "texto": {"type": "string"}}, "required": ["selector", "texto"] } } }
        ]
    else:
        instrucciones = (
            f"Eres Jarvis, un asistente analítico y mentor personal platicando con {usuario_activo}.\n\n"
            "1. ANÁLISIS DE INTENCIÓN (ABSTRACCIÓN):\n"
            "- Abstrae la intención real del usuario. Entiende el contexto completo. Si usa lenguaje informal, sé amigable y conversacional.\n\n"
            "2. MÉTODO DE APRENDIZAJE (CAUSA Y EFECTO):\n"
            "- Tu objetivo es que el usuario aprenda. Explica el 'porqué' usando abstracción, analogías y lógica.\n\n"
            "3. AISLAMIENTO DE MEMORIA (CRÍTICO):\n"
            f"- {contexto_memoria}\n"
            "- REGLA DE ORO: Usa los recuerdos SOLO como contexto silencioso. IGNÓRALOS por completo si no tienen relación lógica con el prompt actual.\n\n"
            "4. LÍMITES DE SISTEMA:\n"
            "- NO tienes acceso al sistema operativo. Si te piden abrir aplicaciones, indícalo amablemente."
        )
        herramientas_permitidas = [] 

    # 4. CONSTRUCCIÓN DE LA MEMORIA A CORTO PLAZO
    mensajes_historial = seguridad.obtener_mensajes_de_conversacion(conversacion_activa_id)
    lista_mensajes = [{"role": "system", "content": instrucciones}]
    
    for msg in mensajes_historial:
        lista_mensajes.append({"role": msg[0], "content": msg[1]})

    paquete = {
        "model": "llama-3.3-70b-versatile", 
        "messages": lista_mensajes, 
        "stream": False
    }
    
    if herramientas_permitidas:
        paquete["tools"] = herramientas_permitidas
            
    try:
        page.pubsub.send_all({"tipo": "pensando", "estado": True, "id": id_peticion})
        respuesta = requests.post(url_api, headers=headers, json=paquete)                                            
        
        if id_peticion != id_peticion_global:
            page.pubsub.send_all({"tipo": "pensando", "estado": False, "id": id_peticion})
            return 

        if respuesta.status_code == 200:
            mensaje_ia = respuesta.json().get("choices", [{}])[0].get("message", {})
            texto_para_voz = ""

            # 5. EJECUCIÓN FÍSICA DE HERRAMIENTAS
            if "tool_calls" in mensaje_ia and rol_activo == "admin":
                for tool in mensaje_ia["tool_calls"]:
                    nombre_funcion = tool["function"]["name"]
                    argumentos = tool["function"]["arguments"]
                    
                    if isinstance(argumentos, str):
                        try: argumentos = json.loads(argumentos)
                        except: argumentos = {}
                    
                    if nombre_funcion == "abrir_app":
                        app_solicitada = argumentos.get("nombre_app", "").lower().strip()
                        if app_solicitada in mis_apps:
                            subprocess.Popen(mis_apps[app_solicitada], shell=True)
                            time.sleep(2)
                            texto_para_voz = f"Iniciando {app_solicitada}, señor."
                        else: texto_para_voz = f"No encuentro la aplicacion {app_solicitada}."
                            
                    elif nombre_funcion == "buscar_internet":
                        tema = argumentos.get("tema_a_buscar", "")
                        try:
                            resultados = DDGS().text(tema, max_results=3)
                            if resultados:
                                texto_crudo = "".join([f"{c['title']}: {c['body']}\n" for c in resultados])
                                # 1. Clonamos la lista de mensajes exacta para que TENGA EL HISTORIAL COMPLETO
                                mensajes_busqueda = lista_mensajes.copy() 

                                instruccion_busqueda = (
                                    f"[SISTEMA INTERNO - RESULTADOS DE RED]:\n{texto_crudo}\n\n"
                                    "REGLA OBLIGATORIA DE PROCESAMIENTO:\n"
                                    "- Analiza la información de red, PERO responde basándote ESTRICTAMENTE en las premisas y datos (como los componentes de PC) que el usuario proporcionó en la conversación.\n"
                                    "- Puedes sugerir mejores alternativas o hardware EXCLUSIVAMENTE si primero ya resolviste y respondiste correctamente a la duda principal del usuario.\n"
                                    "no puedes responder al usuario con el formato de  \n"
                                    "- Responde exactamente a lo que se preguntó usando tu método de aprendizaje (lógica y causa-efecto).\n"
                                    "- IMPORTANTE: La información de red fue obtenida por ti, el usuario NO te proporcionó ningún enlace ni video."
                                    
                                )
                                
                                # Añadimos esta inyección final al paquete
                                mensajes_busqueda.append({"role": "user", "content": instruccion_busqueda})
                                
                                res = requests.post(url_api, headers=headers, json={"model": "llama-3.3-70b-versatile", "messages": mensajes_busqueda, "stream": False})
                                texto_para_voz = res.json().get("choices", [{}])[0].get("message", {}).get("content", "Fallo síntesis.") if res.status_code == 200 else "Fallo síntesis."
                            else: 
                                texto_para_voz = "Sin resultados de red."
                        except: 
                            texto_para_voz = "Satélites desconectados."
                    elif nombre_funcion == "crear_pdf":
                        n_arch = argumentos.get("nombre_archivo", "doc.pdf")
                        c_codigo = argumentos.get("contenido_texto", "")
                        try:
                            pdf = FPDF()
                            pdf.add_page()
                            pdf.set_font("Arial", size=12)
                            pdf.multi_cell(0, 10, txt=c_codigo.encode('latin-1', 'replace').decode('latin-1'))
                            pdf.output(n_arch)
                            texto_para_voz = f"Documento {n_arch} compilado exitosamente."
                            subprocess.Popen(f'start "" "{n_arch}"', shell=True)
                        except: texto_para_voz = "Error interno al generar PDF."

                    elif nombre_funcion == "escanear_pantalla_web":
                        url = argumentos.get("url", "")
                        try:
                            driver = obtener_navegador()
                            if url:
                                driver.get(url)
                                time.sleep(2)
                            
                            html_crudo = driver.page_source
                            texto_crudo = BeautifulSoup(html_crudo, "html.parser").get_text(separator=' ', strip=True)
                            
                            if len(texto_crudo) > 4000: texto_crudo = texto_crudo[:4000] + "... (texto truncado)"
                            elif not texto_crudo: texto_crudo = "La página parece estar vacía."
                            
                            mensajes_analisis = lista_mensajes.copy()
                            instruccion_analisis = f"[SISTEMA INTERNO - ESCÁNER WEB]:\n{texto_crudo}\n\nREGLA OBLIGATORIA: Analiza esta información visual extraída de la web y responde a lo que pidió el usuario."
                            mensajes_analisis.append({"role": "user", "content": instruccion_analisis})
                            
                            res = requests.post(url_api, headers=headers, json={"model": "llama-3.3-70b-versatile", "messages": mensajes_analisis, "stream": False})
                            texto_para_voz = res.json().get("choices", [{}])[0].get("message", {}).get("content", "Fallo análisis web.") if res.status_code == 200 else "Fallo análisis web."
                        except Exception as e:
                            texto_para_voz = f"Error al escanear la pantalla: {str(e)}"
                            
                    elif nombre_funcion == "ejecutar_click":
                        selector = argumentos.get("selector", "")
                        try:
                            driver = obtener_navegador()
                            try: elemento = driver.find_element(By.LINK_TEXT, selector)
                            except:
                                try: elemento = driver.find_element(By.PARTIAL_LINK_TEXT, selector)
                                except: elemento = driver.find_element(By.CSS_SELECTOR, selector)
                            elemento.click()
                            time.sleep(1)
                            texto_para_voz = f"He hecho clic en el elemento: {selector} exitosamente, señor."
                        except Exception as e:
                            texto_para_voz = f"No pude hacer clic en {selector}. Error: {str(e)}"
                            
                    elif nombre_funcion == "inyectar_texto":
                        selector = argumentos.get("selector", "")
                        texto = argumentos.get("texto", "")
                        try:
                            driver = obtener_navegador()
                            elemento = driver.find_element(By.CSS_SELECTOR, selector)
                            elemento.clear()
                            elemento.send_keys(texto)
                            texto_para_voz = f"He escrito el texto '{texto}' exitosamente, señor."
                        except Exception as e:
                            texto_para_voz = f"No pude escribir el texto. Error: {str(e)}"

                    elif nombre_funcion == "crear_archivo":
                        n_arch = argumentos.get("nombre_archivo", "codigo.txt")
                        c_codigo = argumentos.get("contenido", "")
                        try:
                            with open(n_arch, "w", encoding="utf-8") as f: f.write(c_codigo)
                            texto_para_voz = f"Archivo {n_arch} creado."
                            if n_arch.endswith((".py", ".c", ".html", ".css", ".js")): subprocess.Popen(f"code {n_arch}", shell=True)
                        except Exception as err: 
                            texto_para_voz = "Permisos denegados."
                            
            else:
                texto_para_voz = mensaje_ia.get("content", "")
                if texto_para_voz is None or texto_para_voz.strip() == "":
                    texto_para_voz = "Recibí un vacío matemático."

            # 6. ESCRITURA EN MEMORIAS Y PUBLICACIÓN
            page.pubsub.send_all({"tipo": "pensando", "estado": False, "id": id_peticion})
            if texto_para_voz.strip() != "":
                # Escribimos el efecto en el Diario SQL
                seguridad.guardar_mensaje_sql(conversacion_activa_id, "assistant", texto_para_voz)
                # Ejecutar Garbage Collector en 2do plano
                threading.Thread(target=recolector_basura_asincrono, args=(conversacion_activa_id,), daemon=True).start()
                dattabase.guardar_recuerdo(f"msg_{int(time.time())}", f"Humano: {texto_usuario} | IA: {texto_para_voz}", usuario_activo)
                page.pubsub.send_all({"tipo": "respuesta_ia", "texto": texto_para_voz})

            if texto_para_voz.strip() != "" and usar_voz == True:
                page.pubsub.send_all({"tipo": "onda_hablando", "estado": True})
                nombre_audio = f"respuesta_{int(time.time())}.mp3"
                txt_limpio = texto_para_voz.replace('"', '').replace("'", "").replace('\n', ' ').replace('`', '')
                cmd_tts = f'edge-tts --voice "es-MX-JorgeNeural" --text "{txt_limpio}" --write-media "{nombre_audio}"'
                subprocess.run(cmd_tts, shell=True, capture_output=True)
                if os.path.exists(nombre_audio):
                    pygame.mixer.music.load(nombre_audio)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy(): pygame.time.Clock().tick(10)
                    pygame.mixer.music.unload()
                    try: os.remove(nombre_audio)
                    except: pass
                page.pubsub.send_all({"tipo": "onda_hablando", "estado": False})

        else: 
            page.pubsub.send_all({"tipo": "pensando", "estado": False, "id": id_peticion})
            page.pubsub.send_all({"tipo": "respuesta_ia", "texto": f"⚠️ [Alarma de Sistema]: El motor colapsó (Error {respuesta.status_code})."})
    except Exception as e: 
        page.pubsub.send_all({"tipo": "pensando", "estado": False, "id": id_peticion})
        page.pubsub.send_all({"tipo": "respuesta_ia", "texto": f"⚠️ [Falla Crítica]: {e}"})

# --- MOTOR DE ESCUCHA (WHISPER) ---
def motor_jarvis(page: ft.Page):
    global id_peticion_global
    while guardiano is None or carga_modelo is None: time.sleep(1)
    try:
        while True:
            for archivo_basura in glob.glob("respuesta_*.mp3"):
                try: os.remove(archivo_basura)
                except: pass
            while True:      
                chunk, _ = mic_guardian.read(1280)
                prediccion = guardiano.predict(chunk.flatten())
                if prediccion['hey_jarvis'] > 0.5:
                    page.pubsub.send_all({"tipo": "onda_escuchando", "estado": True})
                    break
            audio_grabado, silencio_acumulado, tiempo_total, ha_hablado = [], 0.0, 0.0, False
            with sounddevice.InputStream(samplerate=hz, channels=1, dtype='float32') as mic_stream:
                while True:
                    chunk, _ = mic_stream.read(int(hz * 0.1))
                    audio_grabado.append(chunk)
                    tiempo_total += 0.1
                    if numpy.sqrt(numpy.mean(chunk**2)) > 0.015:
                        ha_hablado = True
                        silencio_acumulado = 0.0 
                    else:
                        if ha_hablado: silencio_acumulado += 0.1 
                        elif tiempo_total > 1.0: break
                    if silencio_acumulado >= 2.0 or tiempo_total >= 15.0: break
            page.pubsub.send_all({"tipo": "onda_escuchando", "estado": False})
            if not ha_hablado: continue
            wavfile.write("audio_temporal.wav", hz, numpy.concatenate(audio_grabado, axis=0))
            segmentos, _ = carga_modelo.transcribe("audio_temporal.wav", language="es")
            transcripcion = "".join([s.text + " " for s in segmentos]).strip()
            if transcripcion == "": continue
            id_peticion_global += 1
            page.pubsub.send_all({"tipo": "mensaje_usuario_ui", "texto": transcripcion})
            threading.Thread(target=procesar_peticion_ia, args=(page, transcripcion, True, id_peticion_global), daemon=True).start()
    except KeyboardInterrupt: pass

# --- TEATRO: INTERFAZ VISUAL FLET ---
def interfaz_principal(page: ft.Page):
    global id_peticion_global, usuario_activo, rol_activo, conversacion_activa_id
    page.title = "Reaxy$ - Agentic OS"
    page.padding = 0
    page.window.width = 940
    page.window.height = 940
    page.window.max_width = 940
    page.window.max_height = 940
    page.window.maximizable = False

    page.fonts = {
        "LetraTitulo": "assets/fonts/Akira Expanded Demo.otf",
        "LetraFirma": "assets/fonts/Gohan.ttf"
    }

    # -- ESTRUCTURA VISUAL --
    lista_chat = ft.ListView(expand=True, spacing=15, auto_scroll=True, padding=20)
    columna_sidebar = ft.Column(spacing=5, scroll=ft.ScrollMode.AUTO, expand=True) 
    
    indicador_pensando = ft.Row(visible=False, controls=[ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.BLUE_400), ft.Text("Procesando...", color=ft.Colors.GREY_500, italic=True)])
    anillo_carga = ft.Container(content=ft.ProgressRing(width=40, height=40, stroke_width=3, color=ft.Colors.BLUE_400), opacity=1.0, animate_opacity=500)
    lineas_onda = [ft.Container(width=4, height=10, bgcolor=ft.Colors.BLUE_400, border_radius=5, animate_size=150) for _ in range(15)]
    contenedor_lineas = ft.Container(content=ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=6, controls=lineas_onda), opacity=0.0, animate_opacity=500)
    texto_estado_voz = ft.Text("Cargando modelo acústico...", color=ft.Colors.BLUE_300, size=11, italic=True)
    
    contenedor_onda_voz = ft.Container(visible=True, height=80, alignment=ft.Alignment.CENTER, content=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER, controls=[ft.Stack(controls=[anillo_carga, contenedor_lineas], alignment=ft.Alignment.CENTER), texto_estado_voz]))
    
    campo_texto = ft.TextField(hint_text="Escribe tu comando...", border_color=ft.Colors.BLUE_900, color=ft.Colors.WHITE, expand=True)
    btn_enviar_texto = ft.IconButton(icon=ft.Icons.SEND, icon_color=ft.Colors.BLUE_400)
    contenedor_input_texto = ft.Row(visible=False, controls=[campo_texto, btn_enviar_texto])

    animando_escucha = False
    animando_habla = False

    # --- LÓGICA DE REPINTADO UI ---
    def repintar_sidebar():
        columna_sidebar.controls.clear()
        if usuario_activo:
            chats = seguridad.obtener_historial_conversaciones(usuario_activo)
            
            if not chats:
                columna_sidebar.controls.append(
                    ft.Container(
                        content=ft.Text("Pizarra en blanco. Escribe tu primer mensaje.", color=ft.Colors.GREY_500, size=11, italic=True),
                        padding=10
                    )
                )
            else:
                for chat in chats:
                    id_chat, titulo = chat[0], chat[1]
                    btn_chat = ft.Container(
                        content=ft.Text(titulo, color=ft.Colors.WHITE70, size=12, no_wrap=True),
                        padding=10, border_radius=5,
                        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.WHITE) if id_chat == conversacion_activa_id else ft.Colors.TRANSPARENT,
                        on_click=lambda e, cid=id_chat: disparar_carga_chat(cid)
                    )
                    columna_sidebar.controls.append(btn_chat)
        page.update()

    def disparar_carga_chat(cid):
        global conversacion_activa_id
        conversacion_activa_id = cid
        lista_chat.controls.clear()
        mensajes = seguridad.obtener_mensajes_de_conversacion(cid)
        for msg in mensajes:
            rol, texto = msg[0], msg[1]
            if rol == "user":
                lista_chat.controls.append(ft.Container(padding=12, border_radius=10, bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.WHITE), content=ft.Text(f"Tú: {texto}", color=ft.Colors.WHITE)))
            else:
                nombre_bot = " Jarvis" if rol_activo == "admin" else "Asistente"
                lista_chat.controls.append(ft.Container(padding=12, border_radius=10, bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.BLUE_900), content=ft.Text(f"{nombre_bot}: {texto}", color=ft.Colors.BLUE_100)))
        repintar_sidebar()
        page.update()

    def accionar_nuevo_chat(e):
        global conversacion_activa_id
        conversacion_activa_id = None
        lista_chat.controls.clear()
        repintar_sidebar()
        page.update()

    def loop_animacion_onda(tipo_modo):
        while (tipo_modo == "escucha" and animando_escucha) or (tipo_modo == "habla" and animando_habla):
            for linea in lineas_onda: linea.height = random.randint(15, 65) if tipo_modo == "habla" else random.randint(10, 35)
            try: page.update()
            except: break
            time.sleep(0.12)
        for linea in lineas_onda: linea.height = 10
        try: page.update()
        except: pass

    # -- ENRUTADOR VISUAL (PUBSUB) --
    def enrutador_mensajes(mensaje_dict):
        global animando_escucha, animando_habla
        
        if mensaje_dict.get("tipo") == "actualizar_sidebar":
            repintar_sidebar()
            
        elif mensaje_dict.get("tipo") == "mensaje_usuario_ui":
            texto_usr = mensaje_dict["texto"]
            burbuja = ft.Container(padding=12, border_radius=10, bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.WHITE), content=ft.Text(f"Tú: {texto_usr}", color=ft.Colors.WHITE))
            lista_chat.controls.append(burbuja)
            page.update()
            
        elif mensaje_dict.get("tipo") == "pensando":
            if mensaje_dict["id"] == id_peticion_global:
                indicador_pensando.visible = mensaje_dict["estado"]
                page.update()
                
        elif mensaje_dict.get("tipo") == "respuesta_ia":
            nombre_bot = " Jarvis" if rol_activo == "admin" else " Asistente"
            color_fondo = ft.Colors.RED_900 if "⚠️" in mensaje_dict['texto'] else ft.Colors.BLUE_900
            burbuja_ia = ft.Container(padding=12, border_radius=10, bgcolor=ft.Colors.with_opacity(0.1, color_fondo), content=ft.Text(f"{nombre_bot}: {mensaje_dict['texto']}", color=ft.Colors.BLUE_100, selectable=True))
            lista_chat.controls.append(burbuja_ia)
            page.update()
            
        elif mensaje_dict.get("tipo") == "onda_escuchando":
            animando_escucha = mensaje_dict["estado"]
            if animando_escucha: threading.Thread(target=loop_animacion_onda, args=("escucha",), daemon=True).start()
        elif mensaje_dict.get("tipo") == "onda_hablando":
            animando_habla = mensaje_dict["estado"]
            if animando_habla: threading.Thread(target=loop_animacion_onda, args=("habla",), daemon=True).start()
        elif mensaje_dict.get("tipo") == "audio_listo":
            anillo_carga.opacity = 0.0          
            contenedor_lineas.opacity = 1.0     
            texto_estado_voz.value = f"Voz Activa ({usuario_activo}) - Di 'Hey Jarvis'"
            page.update()

    page.pubsub.subscribe(enrutador_mensajes)

    def enviar_texto(e):
        global id_peticion_global
        texto_escrito = campo_texto.value.strip()
        if texto_escrito == "": return 
        campo_texto.value = ""
        campo_texto.update()
        id_peticion_global += 1
        page.pubsub.send_all({"tipo": "mensaje_usuario_ui", "texto": texto_escrito})
        threading.Thread(target=procesar_peticion_ia, args=(page, texto_escrito, False, id_peticion_global), daemon=True).start()

    campo_texto.on_submit = enviar_texto
    btn_enviar_texto.on_click = enviar_texto

    btn_texto = ft.Container(content=ft.Text("Texto", color=ft.Colors.GREY_400), padding=ft.Padding(left=25, top=8, right=25, bottom=8), bgcolor=ft.Colors.TRANSPARENT, border_radius=50, data="texto")
    btn_voz = ft.Container(content=ft.Text("Voz", color=ft.Colors.WHITE), padding=ft.Padding(left=25, top=8, right=25, bottom=8), bgcolor=ft.Colors.BLUE_900, border_radius=50, data="voz")

    def cambiar_modo(e):
        if e.control.data == "texto":
            btn_voz.bgcolor = ft.Colors.TRANSPARENT
            btn_voz.content.color = ft.Colors.GREY_400
            btn_texto.bgcolor = ft.Colors.BLUE_900
            btn_texto.content.color = ft.Colors.WHITE
            contenedor_input_texto.visible = True
            contenedor_onda_voz.visible = False
        else:
            btn_texto.bgcolor = ft.Colors.TRANSPARENT
            btn_texto.content.color = ft.Colors.GREY_400
            btn_voz.bgcolor = ft.Colors.BLUE_900
            btn_voz.content.color = ft.Colors.WHITE
            contenedor_input_texto.visible = False
            contenedor_onda_voz.visible = True
        page.update()

    btn_texto.on_click = cambiar_modo
    btn_voz.on_click = cambiar_modo
    boton_capsula = ft.Row(alignment=ft.MainAxisAlignment.CENTER, controls=[btn_texto, btn_voz])

    # --- PANTALLA LOGIN ---
    campo_usuario = ft.TextField(label="Usuario", border=ft.InputBorder.UNDERLINE, color=ft.Colors.BLACK)
    campo_password = ft.TextField(label="Contraseña", password=True, can_reveal_password=True, border=ft.InputBorder.UNDERLINE, color=ft.Colors.BLACK)

    def accionar_login(e):
        global usuario_activo, rol_activo, conversacion_activa_id
        resultado = seguridad.validar_login(campo_usuario.value, campo_password.value)
        if resultado["exito"]:
            usuario_activo = campo_usuario.value
            rol_activo = resultado["rol"]
            conversacion_activa_id = None 
            page.route = "/dashboard"
            cambiar_ruta(None)
            threading.Thread(target=inicializar_sistemas_audio, args=(page,), daemon=True).start()
            threading.Thread(target=motor_jarvis, args=(page,), daemon=True).start()
        else:
            alerta = ft.SnackBar(ft.Text("❌ Acceso denegado. Credenciales inválidas.", color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_800)
            page.overlay.append(alerta)
            alerta.open = True
            page.update()

    def accionar_registro(e):
        if campo_usuario.value and campo_password.value:
            seguridad.crear_usuario(campo_usuario.value, campo_password.value, "invitado")
            alerta = ft.SnackBar(ft.Text("✅ Usuario (invitado) creado. Ahora inicia sesión.", color=ft.Colors.WHITE), bgcolor=ft.Colors.GREEN_800)
            page.overlay.append(alerta)
            alerta.open = True
            page.update()
        else:
            alerta = ft.SnackBar(ft.Text("⚠️ Llena ambos campos.", color=ft.Colors.WHITE), bgcolor=ft.Colors.ORANGE_800)
            page.overlay.append(alerta)
            alerta.open = True
            page.update()

    def accionar_registro_admin(e):
        if campo_usuario.value and campo_password.value:
            seguridad.crear_usuario(campo_usuario.value, campo_password.value, "admin")
            alerta = ft.SnackBar(ft.Text("✅ Administrador creado. Ahora inicia sesión.", color=ft.Colors.WHITE), bgcolor=ft.Colors.GREEN_800)
            page.overlay.append(alerta)
            alerta.open = True
            page.update()
        else:
            alerta = ft.SnackBar(ft.Text("⚠️ Llena ambos campos.", color=ft.Colors.WHITE), bgcolor=ft.Colors.ORANGE_800)
            page.overlay.append(alerta)
            alerta.open = True
            page.update()

    def accionar_logout(e):
        global usuario_activo, rol_activo, conversacion_activa_id
        usuario_activo = None
        rol_activo = None
        conversacion_activa_id = None
        lista_chat.controls.clear() 
        columna_sidebar.controls.clear()
        page.route = "/"
        cambiar_ruta(None)

    def cambiar_ruta(e):
        page.views.clear()

        if page.route == "/":
            lado_izq = ft.Container(expand=True, content=ft.Stack(expand=True, controls=[ft.Image(src="assets/fonts/ddd157d3da927f59baefed4b96cf9c0c.jpg", fit=ft.BoxFit.COVER, expand=True, filter_quality=ft.FilterQuality.NONE), ft.Container(left=30, top=50, content=ft.Column([ft.Text("Reaxy$", size=60, color=ft.Colors.WHITE, font_family="LetraTitulo"), ft.Text("your agentic friend", size=25, color=ft.Colors.GREY_300, font_family="LetraFirma")])), ft.Container(left=50, bottom=50, content=ft.Image(src="assets/fonts/caballero.gif", width=150, height=150, filter_quality=ft.FilterQuality.NONE))]))
            lado_der = ft.Container(expand=True, bgcolor=ft.Colors.WHITE, padding=50, content=ft.Column(run_alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                ft.Text("Acceso al Sistema", size=30, color=ft.Colors.BLACK, weight=ft.FontWeight.BOLD), 
                ft.Divider(color="transparent", height=40), 
                campo_usuario, 
                campo_password, 
                ft.Divider(color="transparent", height=30), 
                
                ft.Container(
                    content=ft.Text("Iniciar Sesión", size=16, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                    width=300, height=50, bgcolor=ft.Colors.BLUE_900, border_radius=10,
                    alignment=ft.Alignment.CENTER,
                    on_click=accionar_login
                ),
                
                ft.Container(
                    content=ft.Text("Crear Cuenta (Invitado)", size=16, color=ft.Colors.BLUE_900),
                    width=300, height=50, bgcolor=ft.Colors.TRANSPARENT, border_radius=10,
                    alignment=ft.Alignment.CENTER,
                    on_click=accionar_registro
                ),
                
                ft.Container(
                    content=ft.Text("Crear Cuenta (Administrador)", size=16, color=ft.Colors.RED_400, weight=ft.FontWeight.BOLD),
                    width=300, height=50, bgcolor=ft.Colors.TRANSPARENT, border_radius=10,
                    alignment=ft.Alignment.CENTER,
                    on_click=accionar_registro_admin
                )
            ]))
            page.views.append(ft.View(route="/", controls=[ft.Row(expand=True, spacing=0, controls=[lado_izq, lado_der])], bgcolor=ft.Colors.WHITE, padding=0))

        elif page.route == "/dashboard":
            texto_perfil = f"Admin: {usuario_activo}" if rol_activo == "admin" else f"Invitado: {usuario_activo}"
            color_barra = ft.Colors.BLUE_900 if rol_activo == "admin" else ft.Colors.PURPLE_900
            
            barra_lateral = ft.Container(bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.WHITE), blur=ft.Blur(20, 20, ft.BlurTileMode.MIRROR), width=260, padding=20, content=ft.Column(controls=[
                ft.Text("Reaxy$", size=30, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE), 
                ft.Container(bgcolor=color_barra, padding=5, border_radius=5, content=ft.Text(texto_perfil, color=ft.Colors.WHITE, size=12)),
                ft.Divider(color=ft.Colors.WHITE24), 
                
                ft.Container(
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER, 
                        controls=[
                            ft.Icon(ft.Icons.ADD, color=ft.Colors.WHITE, size=18),
                            ft.Text("Nueva Conversación", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)
                        ]
                    ),
                    bgcolor=ft.Colors.BLUE_800, border_radius=8, padding=10, width=220,
                    on_click=accionar_nuevo_chat
                ),
                
                ft.Text("Recientes", color=ft.Colors.WHITE70, size=14, weight=ft.FontWeight.BOLD),
                columna_sidebar, 
                
                ft.IconButton(icon=ft.Icons.LOGOUT, icon_color=ft.Colors.RED_400, on_click=accionar_logout, tooltip="Cerrar Sesión")
            ]))
            
            repintar_sidebar() 
            
            zona_central = ft.Container(expand=True, padding=20, content=ft.Column(controls=[boton_capsula, lista_chat, indicador_pensando, contenedor_onda_voz, contenedor_input_texto]))
            escenario_dashboard = ft.Stack(expand=True, controls=[ft.Container(expand=True, gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT, colors=["#0a0e1a", "#05080f", "#0d1220"])), ft.Row(expand=True, spacing=0, controls=[barra_lateral, zona_central])])
            page.views.append(ft.View(route="/dashboard", controls=[escenario_dashboard], padding=0))

        page.update()

    page.on_route_change = cambiar_ruta
    page.route = "/"
    cambiar_ruta(None)

ft.run(interfaz_principal, assets_dir="assets")