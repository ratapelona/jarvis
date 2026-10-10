"""
ui/app.py — Interfaz Principal Flet

SEC-02: Botón público de registro admin eliminado
SEC-05: Protección de ruta del dashboard
SEC-08: Estado por sesión
"""
import time
import random
import threading

import flet as ft

from config import WINDOW_WIDTH, WINDOW_HEIGHT, FONT_TITULO, FONT_FIRMA, RATE_LIMIT_BLOQUEO_SEGUNDOS
from security.auth import validar_login, crear_usuario, inicializar_seguridad
from core.ia_engine import procesar_peticion_ia
from core.voice_engine import inicializar_sistemas_audio, motor_jarvis, iniciar_dictado, detener_dictado
from data import sql_store
from core.cola_mensajes import (
    encolar_peticion,
    iniciar_worker,
    precalentar_modelo_residente,
    encolar_tarea_pesada,
)
from core.plugin_manager import plugin_manager


def interfaz_principal(page: ft.Page):
    """Punto de entrada de la UI Flet — login + dashboard."""

    # --- Inicializar seguridad (crea tablas si no existen) ---
    inicializar_seguridad()

    # --- Precalentar modelo residente (qwen3.5:9b) en background ---
    threading.Thread(target=precalentar_modelo_residente, daemon=True).start()

    # --- Estado de sesión (mutable refs para compartir entre threads) ---
    id_peticion_ref = [0]             # ESC-07: contador de peticiones
    usuario_ref = [None]              # Usuario activo
    rol_ref = [None]                  # Rol activo
    conversacion_ref = [None]         # Conversación activa

    page.title = "Reaxy$ - Agentic OS"
    page.padding = 0
    page.window.maximized = True

    # Tema Claro (Día) - Azul y Blanco
    page.theme = ft.Theme(
        color_scheme_seed=ft.Colors.BLUE,
        use_material3=True
    )
    
    # Tema Oscuro (Noche) - Negro y Verde
    page.dark_theme = ft.Theme(
        color_scheme_seed=ft.Colors.GREEN,
        use_material3=True
    )

    # Estado global adicional
    modo_oscuro_ref = [False]
    modo_oscuro_auto_ref = [True]
    sidebar_expandido_ref = [True]
    modo_activo_ref = ["texto"]  # "texto" | "voz" | "trabajo"

    def get_text_color(): return ft.Colors.WHITE if modo_oscuro_ref[0] else ft.Colors.BLACK
    def get_border_color(): return ft.Colors.WHITE if modo_oscuro_ref[0] else ft.Colors.BLACK
    def get_neo_border(): return ft.Border.all(3, get_border_color())
    def get_neo_shadow(): return ft.BoxShadow(spread_radius=0, blur_radius=0, offset=ft.Offset(6, 6), color=get_border_color())
    def get_btn_style(): return ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=0))

    # Evaluamos auto-theme al inicio
    import datetime
    es_noche = datetime.datetime.now().hour >= 19 or datetime.datetime.now().hour <= 6
    if modo_oscuro_auto_ref[0]:
        modo_oscuro_ref[0] = es_noche
    page.theme_mode = ft.ThemeMode.DARK if modo_oscuro_ref[0] else ft.ThemeMode.LIGHT

    # ==========================================================================
    # Estructura Visual
    # ==========================================================================
    lista_chat = ft.ListView(expand=True, spacing=15, auto_scroll=True, padding=20)
    columna_sidebar = ft.Column(spacing=5, scroll=ft.ScrollMode.AUTO, expand=True)

    indicador_pensando = ft.Row(
        visible=False,
        controls=[
            ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.BLUE_400),
            ft.Text("Procesando...", color=ft.Colors.GREY_500, italic=True),
        ],
    )
    anillo_carga = ft.Container(
        content=ft.ProgressRing(width=40, height=40, stroke_width=3, color=ft.Colors.BLUE_400),
        opacity=1.0,
        animate_opacity=500,
    )
    lineas_onda = [
        ft.Container(width=4, height=10, bgcolor=ft.Colors.BLUE_400, border_radius=5, animate_size=150)
        for _ in range(15)
    ]
    contenedor_lineas = ft.Container(
        content=ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=6, controls=lineas_onda),
        opacity=0.0,
        animate_opacity=500,
    )
    texto_estado_voz = ft.Text(
        "Cargando modelo acústico...", color=ft.Colors.BLUE_300, size=11, italic=True
    )
    contenedor_onda_voz = ft.Container(
        visible=True,
        height=80,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.Stack(controls=[anillo_carga, contenedor_lineas], alignment=ft.Alignment.CENTER),
                texto_estado_voz,
            ],
        ),
    )

    campo_texto = ft.TextField(
        hint_text="Escribe tu comando...",
        border_color=ft.Colors.TRANSPARENT,
        focused_border_color=ft.Colors.TRANSPARENT,
        bgcolor=ft.Colors.WHITE,
        color=ft.Colors.BLACK,
        hint_style=ft.TextStyle(color=ft.Colors.GREY_500),
        cursor_color=ft.Colors.BLACK,
        filled=True,
        fill_color=ft.Colors.WHITE,
        expand=True,
        min_lines=1,
        max_lines=6,
        shift_enter=True,
    )
    dictando_ref = [False]  # Estado del dictado en tiempo real

    btn_dictado = ft.IconButton(
        icon=ft.Icons.MIC,
        icon_color=ft.Colors.GREY_600,
        tooltip="Dictar (habla y se escribe)",
    )
    btn_enviar_texto = ft.IconButton(icon=ft.Icons.SEND, icon_color=ft.Colors.ON_SURFACE)
    contenedor_input_texto = ft.Container(
        visible=False,
        border_radius=0, border=ft.Border.all(3, ft.Colors.BLACK),
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=0, offset=ft.Offset(6, 6), color=ft.Colors.BLACK),
        padding=5, margin=10,
        bgcolor=ft.Colors.WHITE,
        content=ft.Row(
            controls=[btn_dictado, campo_texto, btn_enviar_texto],
            vertical_alignment=ft.CrossAxisAlignment.END,
        )
    )

    animando_escucha = [False]
    animando_habla = [False]

    # ==========================================================================
    # Lógica del sidebar
    # ==========================================================================
    def repintar_sidebar():
        columna_sidebar.controls.clear()
        if usuario_ref[0]:
            chats = sql_store.obtener_historial_conversaciones(usuario_ref[0])
            if not chats:
                columna_sidebar.controls.append(
                    ft.Container(
                        content=ft.Text(
                            "Pizarra en blanco. Escribe tu primer mensaje.",
                            color=ft.Colors.GREY_500, size=11, italic=True,
                        ),
                        padding=10,
                    )
                )
            else:
                for chat in chats:
                    id_chat, titulo = chat[0], chat[1]
                    btn_chat = ft.Container(
                        content=ft.Text(titulo, color=get_text_color(), size=12, no_wrap=True, weight=ft.FontWeight.W_800),
                        padding=10,
                        border_radius=0,
                        border=get_neo_border() if id_chat == conversacion_ref[0] else None,
                        shadow=get_neo_shadow() if id_chat == conversacion_ref[0] else None,
                        bgcolor=(
                            (ft.Colors.BLUE_400 if not modo_oscuro_ref[0] else ft.Colors.BLUE_900)
                            if id_chat == conversacion_ref[0]
                            else ft.Colors.TRANSPARENT
                        ),
                        on_click=lambda e, cid=id_chat: disparar_carga_chat(cid),
                    )
                    columna_sidebar.controls.append(btn_chat)
        page.update()

    def disparar_carga_chat(cid):
        conversacion_ref[0] = cid
        lista_chat.controls.clear()
        mensajes = sql_store.obtener_mensajes_de_conversacion(cid)
        for msg in mensajes:
            rol_msg, texto = msg[0], msg[1]
            if rol_msg == "user":
                lista_chat.controls.append(
                    ft.Container(
                        padding=15, border_radius=0,
                        border=get_neo_border(), shadow=get_neo_shadow(),
                        bgcolor=ft.Colors.YELLOW_300 if not modo_oscuro_ref[0] else ft.Colors.BROWN_800,
                        content=ft.Text(f"Tú: {texto}", color=get_text_color(), weight=ft.FontWeight.W_600),
                    )
                )
            else:
                nombre_bot = "Jarvis" if rol_ref[0] == "admin" else "Asistente"
                lista_chat.controls.append(
                    ft.Container(
                        padding=15, border_radius=0,
                        border=get_neo_border(), shadow=get_neo_shadow(),
                        bgcolor=ft.Colors.CYAN_300 if not modo_oscuro_ref[0] else ft.Colors.BLUE_900,
                        content=ft.Text(f"{nombre_bot}: {texto}", color=get_text_color(), weight=ft.FontWeight.W_600),
                    )
                )
        repintar_sidebar()
        page.update()

    def accionar_nuevo_chat(e):
        conversacion_ref[0] = None
        lista_chat.controls.clear()
        repintar_sidebar()
        page.update()

    def loop_animacion_onda(tipo_modo):
        while (tipo_modo == "escucha" and animando_escucha[0]) or (tipo_modo == "habla" and animando_habla[0]):
            for linea in lineas_onda:
                linea.height = random.randint(15, 65) if tipo_modo == "habla" else random.randint(10, 35)
            try:
                page.update()
            except Exception:
                break
            time.sleep(0.12)
        for linea in lineas_onda:
            linea.height = 10
        try:
            page.update()
        except Exception:
            pass

    streaming_bubbles = {}

    # ==========================================================================
    # Enrutador de mensajes PubSub
    # ==========================================================================
    def enrutador_mensajes(mensaje_dict):
        if mensaje_dict.get("tipo") == "actualizar_sidebar":
            repintar_sidebar()

        elif mensaje_dict.get("tipo") == "mensaje_usuario_ui":
            texto_usr = mensaje_dict["texto"]
            burbuja = ft.Container(
                padding=15, border_radius=0,
                border=get_neo_border(), shadow=get_neo_shadow(),
                bgcolor=ft.Colors.YELLOW_300 if not modo_oscuro_ref[0] else ft.Colors.BROWN_800,
                content=ft.Text(f"Tú: {texto_usr}", color=get_text_color(), weight=ft.FontWeight.W_600),
            )
            lista_chat.controls.append(burbuja)
            page.update()

        elif mensaje_dict.get("tipo") == "pensando":
            if mensaje_dict.get("agente") or mensaje_dict["id"] == id_peticion_ref[0]:
                indicador_pensando.visible = mensaje_dict["estado"]
                page.update()

        elif mensaje_dict.get("tipo") == "respuesta_ia":
            nombre_bot = "Jarvis" if rol_ref[0] == "admin" else "Asistente"
            texto_resp = mensaje_dict["texto"]
            es_error = "[Alarma de Sistema]" in texto_resp or "[Falla Crítica]" in texto_resp
            if not modo_oscuro_ref[0]:
                color_fondo = ft.Colors.RED_300 if es_error else ft.Colors.CYAN_300
            else:
                color_fondo = ft.Colors.RED_900 if es_error else ft.Colors.BLUE_900
            burbuja_ia = ft.Container(
                padding=15, border_radius=0,
                border=get_neo_border(), shadow=get_neo_shadow(),
                bgcolor=color_fondo,
                content=ft.Text(f"{nombre_bot}: {texto_resp}", color=get_text_color(), selectable=True, weight=ft.FontWeight.W_600),
            )
            lista_chat.controls.append(burbuja_ia)
            page.update()

        elif mensaje_dict.get("tipo") == "respuesta_ia_stream_start":
            id_pet = mensaje_dict["id"]
            nombre_bot = "Jarvis" if rol_ref[0] == "admin" else "Asistente"
            
            # 1. Crear el contenedor colapsable (Acordeón) para el pensamiento
            texto_think = ft.Text("", color=ft.Colors.GREY_500, italic=True, size=12, selectable=True)
            acordeon_think = ft.ExpansionTile(
                title=ft.Text("Pensando...", color=ft.Colors.GREY_500, italic=True, size=13),
                leading=ft.Icon(ft.Icons.LIGHTBULB_OUTLINE, color=ft.Colors.YELLOW_600),
                controls=[ft.Container(content=texto_think, padding=10, bgcolor=ft.Colors.BLACK12, border_radius=5)],
                visible=False, # Se mantiene oculto hasta que reciba el tag <think>
            )
            
            # 2. Crear el texto para la respuesta principal
            texto_ui = ft.Text(f"{nombre_bot}: ", color=get_text_color(), selectable=True, weight=ft.FontWeight.W_600)
            
            # 3. Empaquetar todo en la burbuja
            columna_burbuja = ft.Column(controls=[acordeon_think, texto_ui], spacing=5)
            burbuja_ia = ft.Container(
                padding=15, border_radius=0,
                border=get_neo_border(), shadow=get_neo_shadow(),
                bgcolor=ft.Colors.CYAN_300 if not modo_oscuro_ref[0] else ft.Colors.BLUE_900,
                content=columna_burbuja,
            )
            lista_chat.controls.append(burbuja_ia)
            
            # Guardamos el diccionario con las referencias a ambos textos y al acordeón
            streaming_bubbles[id_pet] = {"normal": texto_ui, "think": texto_think, "acordeon": acordeon_think}
            page.update()

        # NUEVO EVENTO: Dibuja el pensamiento dentro del acordeón gris
        elif mensaje_dict.get("tipo") == "respuesta_ia_stream_think_chunk":
            id_pet = mensaje_dict["id"]
            chunk = mensaje_dict["chunk"]
            if id_pet in streaming_bubbles:
                refs = streaming_bubbles[id_pet]
                refs["think"].value += chunk
                
                # Hacer visible y expandir el acordeón en cuanto empieza a pensar
                if not refs["acordeon"].visible:
                    refs["acordeon"].visible = True
                    # Flet requiere un update de la página para que tome la visibilidad inicial
                    page.update()
                    refs["acordeon"].expanded = True
                    
                page.update()

        elif mensaje_dict.get("tipo") == "respuesta_ia_stream_chunk":
            id_pet = mensaje_dict["id"]
            chunk = mensaje_dict["chunk"]
            if id_pet in streaming_bubbles:
                streaming_bubbles[id_pet]["normal"].value += chunk
                page.update()

        elif mensaje_dict.get("tipo") == "respuesta_ia_stream_end":
            id_pet = mensaje_dict["id"]
            if id_pet in streaming_bubbles:
                # Cierra el acordeón de pensamiento automáticamente cuando empieza a hablar
                if streaming_bubbles[id_pet]["acordeon"].visible:
                    streaming_bubbles[id_pet]["acordeon"].expanded = False
                del streaming_bubbles[id_pet]
            page.update()

        elif mensaje_dict.get("tipo") == "dictado_chunk":
            # Inserta el texto transcrito en el campo de escritura
            campo_texto.value = (campo_texto.value or "") + mensaje_dict["texto"]
            try:
                campo_texto.update()
            except Exception:
                pass

        elif mensaje_dict.get("tipo") == "dictado_estado":
            activo = mensaje_dict.get("activo", False)
            dictando_ref[0] = activo
            btn_dictado.icon = ft.Icons.MIC if not activo else ft.Icons.MIC_OFF
            btn_dictado.icon_color = ft.Colors.GREY_600 if not activo else ft.Colors.RED_600
            try:
                btn_dictado.update()
            except Exception:
                pass

        elif mensaje_dict.get("tipo") == "onda_escuchando":
            animando_escucha[0] = mensaje_dict["estado"]
            if animando_escucha[0]:
                threading.Thread(target=loop_animacion_onda, args=("escucha",), daemon=True).start()

        elif mensaje_dict.get("tipo") == "onda_hablando":
            animando_habla[0] = mensaje_dict["estado"]
            if animando_habla[0]:
                threading.Thread(target=loop_animacion_onda, args=("habla",), daemon=True).start()

        elif mensaje_dict.get("tipo") == "audio_listo":
            anillo_carga.opacity = 0.0
            contenedor_lineas.opacity = 1.0
            texto_estado_voz.value = f"Voz Activa ({usuario_ref[0]}) - Di 'Hey Jarvis'"
            page.update()

        elif mensaje_dict.get("tipo") == "cola_estado":
            pendientes = mensaje_dict.get("pendientes", 0)
            if pendientes > 0:
                indicador_pensando.visible = True
                indicador_pensando.controls[1].value = f"En cola: {pendientes} mensaje(s) pendiente(s)..."
            else:
                indicador_pensando.controls[1].value = "Procesando..."
            try:
                page.update()
            except Exception:
                pass

    page.pubsub.subscribe(enrutador_mensajes)

    # ==========================================================================
    # Callback wrapper para el motor IA (inyecta estado de sesión)
    # ==========================================================================
    def _procesar_ia_wrapper(page_ref, texto, usar_voz, id_pet):
        procesar_peticion_ia(
            page=page_ref,
            texto_usuario=texto,
            usar_voz=usar_voz,
            id_peticion=id_pet,
            id_peticion_ref=id_peticion_ref,
            usuario_activo=usuario_ref[0],
            rol_activo=rol_ref[0],
            conversacion_activa_id_ref=conversacion_ref,
        )

    # ==========================================================================
    # Envío de texto por teclado
    # ==========================================================================
    def enviar_texto(e):
        texto_escrito = campo_texto.value.strip()
        if texto_escrito == "":
            return
        campo_texto.value = ""
        campo_texto.update()

        if modo_activo_ref[0] == "trabajo":
            # Modo Trabajo (OS): delegar a través de la cola serializada (Modo Pesado)
            page.pubsub.send_all({"tipo": "mensaje_usuario_ui", "texto": texto_escrito})
            encolar_tarea_pesada(texto_escrito, page, usuario_ref[0], delay_inicio=2)
        else:
            id_peticion_ref[0] += 1
            page.pubsub.send_all({"tipo": "mensaje_usuario_ui", "texto": texto_escrito})
            encolar_peticion(
                _procesar_ia_wrapper,
                (page, texto_escrito, False, id_peticion_ref[0]),
                page,
            )

    def toggle_dictado(e):
        if dictando_ref[0]:
            detener_dictado()
        else:
            threading.Thread(target=iniciar_dictado, args=(page,), daemon=True).start()

    btn_dictado.on_click = toggle_dictado
    campo_texto.on_submit = enviar_texto
    btn_enviar_texto.on_click = enviar_texto

    # ==========================================================================
    # Selector Voz/Texto
    # ==========================================================================
    btn_texto = ft.Container(
        content=ft.Text("Texto", color=ft.Colors.BLACK, weight=ft.FontWeight.W_900),
        padding=ft.Padding(left=25, top=8, right=25, bottom=8),
        bgcolor=ft.Colors.WHITE, border_radius=0, data="texto",
        border=ft.Border.all(3, ft.Colors.BLACK),
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=0, offset=ft.Offset(4, 4), color=ft.Colors.BLACK)
    )
    btn_voz = ft.Container(
        content=ft.Text("Voz", color=ft.Colors.BLACK, weight=ft.FontWeight.W_900),
        padding=ft.Padding(left=25, top=8, right=25, bottom=8),
        bgcolor=ft.Colors.GREEN_400, border_radius=0, data="voz",
        border=ft.Border.all(3, ft.Colors.BLACK),
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=0, offset=ft.Offset(4, 4), color=ft.Colors.BLACK)
    )
    btn_trabajo = ft.Container(
        content=ft.Text("Trabajo (OS)", color=ft.Colors.BLACK, weight=ft.FontWeight.W_900),
        padding=ft.Padding(left=25, top=8, right=25, bottom=8),
        bgcolor=ft.Colors.ORANGE_300, border_radius=0, data="trabajo",
        border=ft.Border.all(3, ft.Colors.BLACK),
        shadow=ft.BoxShadow(spread_radius=0, blur_radius=0, offset=ft.Offset(4, 4), color=ft.Colors.BLACK)
    )

    def cambiar_modo(e):
        modo = e.control.data
        modo_activo_ref[0] = modo
        # Reset colores
        btn_texto.bgcolor = ft.Colors.WHITE
        btn_voz.bgcolor = ft.Colors.WHITE
        btn_trabajo.bgcolor = ft.Colors.WHITE

        if modo == "texto":
            btn_texto.bgcolor = ft.Colors.GREEN_400
            contenedor_input_texto.visible = True
            contenedor_onda_voz.visible = False
        elif modo == "voz":
            btn_voz.bgcolor = ft.Colors.GREEN_400
            contenedor_input_texto.visible = False
            contenedor_onda_voz.visible = True
        elif modo == "trabajo":
            btn_trabajo.bgcolor = ft.Colors.ORANGE_400
            # Trabajo usa el campo de texto (sin voz)
            contenedor_input_texto.visible = True
            contenedor_onda_voz.visible = False
            # Nueva conversación limpia al entrar en modo trabajo
            conversacion_ref[0] = None
            lista_chat.controls.clear()
            repintar_sidebar()
        page.update()

    btn_texto.on_click = cambiar_modo
    btn_voz.on_click = cambiar_modo
    btn_trabajo.on_click = cambiar_modo
    boton_capsula = ft.Row(alignment=ft.MainAxisAlignment.CENTER, controls=[btn_texto, btn_voz, btn_trabajo])

    # ==========================================================================
    # Pantalla Login
    # ==========================================================================
    campo_usuario = ft.TextField(label="Usuario", border_color=ft.Colors.ON_SURFACE, border_radius=0)
    campo_password = ft.TextField(
        label="Contraseña", password=True, can_reveal_password=True,
        border_color=ft.Colors.ON_SURFACE, border_radius=0,
    )

    def accionar_login(e):
        resultado = validar_login(campo_usuario.value, campo_password.value)
        if resultado["exito"]:
            usuario_ref[0] = campo_usuario.value
            rol_ref[0] = resultado["rol"]
            conversacion_ref[0] = None
            import json
            try:
                with open("session_store.json", "w") as f:
                    json.dump({"usuario": campo_usuario.value, "rol": resultado["rol"]}, f)
            except:
                pass
            page.route = "/dashboard"
            cambiar_ruta(None)
            iniciar_worker()  # ESC-09: Cola de mensajes IA
            threading.Thread(target=inicializar_sistemas_audio, args=(page,), daemon=True).start()
            threading.Thread(
                target=motor_jarvis,
                args=(page, id_peticion_ref, _procesar_ia_wrapper),
                daemon=True,
            ).start()
        else:
            mensaje_error = resultado.get("mensaje", "Acceso denegado. Credenciales inválidas.")
            alerta = ft.SnackBar(
                ft.Text(mensaje_error, color=ft.Colors.WHITE),
                bgcolor=ft.Colors.RED_800,
            )
            page.overlay.append(alerta)
            alerta.open = True
            page.update()

    # SEC-02: Solo registro como invitado — NO hay botón público de admin
    def accionar_registro(e):
        if campo_usuario.value and campo_password.value:
            crear_usuario(campo_usuario.value, campo_password.value, "invitado")
            alerta = ft.SnackBar(
                ft.Text("Usuario (invitado) creado. Ahora inicia sesión.", color=ft.Colors.WHITE),
                bgcolor=ft.Colors.GREEN_800,
            )
            page.overlay.append(alerta)
            alerta.open = True
            page.update()
        else:
            alerta = ft.SnackBar(
                ft.Text("Llena ambos campos.", color=ft.Colors.WHITE),
                bgcolor=ft.Colors.ORANGE_800,
            )
            page.overlay.append(alerta)
            alerta.open = True
            page.update()

    def accionar_logout(e):
        usuario_ref[0] = None
        rol_ref[0] = None
        conversacion_ref[0] = None
        import os
        try:
            if os.path.exists("session_store.json"):
                os.remove("session_store.json")
        except:
            pass
        lista_chat.controls.clear()
        columna_sidebar.controls.clear()
        page.route = "/"
        cambiar_ruta(None)

    # ==========================================================================
    # Router de vistas
    # ==========================================================================
    def cambiar_ruta(e):
        page.views.clear()

        if page.route == "/":
            import datetime
            es_noche = datetime.datetime.now().hour >= 19 or datetime.datetime.now().hour <= 6
            if modo_oscuro_auto_ref[0]:
                modo_oscuro_ref[0] = es_noche

            # Login Neobrutalista - Pantalla Completa
            fondo_login = ft.Colors.WHITE if not modo_oscuro_ref[0] else ft.Colors.DEEP_PURPLE_900

            campo_usuario.width = 400
            campo_password.width = 400
            campo_usuario.border_color = get_border_color()
            campo_password.border_color = get_border_color()
            campo_usuario.color = get_text_color()
            campo_password.color = get_text_color()
            
            # Aseguramos que el cursor (cursor_color) también contraste
            campo_usuario.cursor_color = get_text_color()
            campo_password.cursor_color = get_text_color()

            login_fullscreen = ft.Container(
                expand=True,
                bgcolor=fondo_login,
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text("Reaxy$", size=70, color=get_text_color(), weight=ft.FontWeight.W_900),
                        ft.Divider(color="transparent", height=40),
                        campo_usuario,
                        campo_password,
                        ft.Divider(color="transparent", height=40),
                        ft.ElevatedButton(
                            content=ft.Text("Iniciar Sesión", color=get_text_color(), weight=ft.FontWeight.BOLD),
                            width=400,
                            height=60,
                            bgcolor=ft.Colors.YELLOW_400 if not modo_oscuro_ref[0] else ft.Colors.YELLOW_900,
                            style=get_btn_style(),
                            on_click=accionar_login,
                        ),
                        ft.Container(height=10),
                        ft.ElevatedButton(
                            content=ft.Text("Crear Cuenta", color=get_text_color(), weight=ft.FontWeight.BOLD),
                            width=400,
                            height=60,
                            bgcolor=ft.Colors.CYAN_400 if not modo_oscuro_ref[0] else ft.Colors.CYAN_900,
                            style=get_btn_style(),
                            on_click=accionar_registro,
                        ),
                    ],
                ),
            )

            page.views.append(
                ft.View(
                    route="/",
                    controls=[login_fullscreen],
                    bgcolor=fondo_login,
                    padding=0,
                )
            )

        elif page.route == "/dashboard":
            # SEC-05: Protección de ruta — redirigir si no hay sesión
            if usuario_ref[0] is None or rol_ref[0] is None:
                page.route = "/"
                cambiar_ruta(None)
                return

            def toggle_sidebar(e):
                sidebar_expandido_ref[0] = not sidebar_expandido_ref[0]
                barra_lateral.visible = sidebar_expandido_ref[0]
                page.update()

            texto_perfil = f"Admin: {usuario_ref[0]}" if rol_ref[0] == "admin" else f"Invitado: {usuario_ref[0]}"
            color_barra = ft.Colors.PINK_400 if not modo_oscuro_ref[0] else ft.Colors.PINK_900

            barra_lateral = ft.Container(
                visible=sidebar_expandido_ref[0],
                bgcolor=ft.Colors.LIME_200 if not modo_oscuro_ref[0] else ft.Colors.ON_INVERSE_SURFACE,
                border=ft.Border.only(right=ft.BorderSide(3, get_border_color())),
                width=260, padding=20,
                content=ft.Column(controls=[
                    ft.Row([
                        ft.Text("Perfil", size=16, weight=ft.FontWeight.W_900, color=get_text_color()),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Container(
                        bgcolor=color_barra, padding=10, border_radius=0,
                        border=get_neo_border(), shadow=get_neo_shadow(),
                        content=ft.Text(texto_perfil, color=get_text_color(), size=12, weight=ft.FontWeight.BOLD),
                    ),
                    ft.Divider(color="transparent", height=10),
                    ft.Container(
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.ADD, color=get_text_color(), size=18),
                                ft.Text("Nueva Conversación", color=get_text_color(), weight=ft.FontWeight.BOLD),
                            ],
                        ),
                        bgcolor=ft.Colors.ORANGE_400 if not modo_oscuro_ref[0] else ft.Colors.ORANGE_900,
                        border_radius=0, padding=10, width=220,
                        border=get_neo_border(), shadow=get_neo_shadow(),
                        on_click=accionar_nuevo_chat,
                    ),
                    ft.Container(height=5),
                    ft.Container(
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.EXTENSION, color=get_text_color(), size=18),
                                ft.Text("Plugins & MCP", color=get_text_color(), weight=ft.FontWeight.BOLD),
                            ],
                        ),
                        bgcolor=ft.Colors.PURPLE_300 if not modo_oscuro_ref[0] else ft.Colors.PURPLE_900,
                        border_radius=0, padding=10, width=220,
                        border=get_neo_border(), shadow=get_neo_shadow(),
                        on_click=lambda e: (setattr(page, 'route', '/plugins'), cambiar_ruta(None)),
                    ),
                    ft.Text("Chats", size=14, color=ft.Colors.OUTLINE),
                    columna_sidebar,
                    ft.IconButton(
                        icon=ft.Icons.LOGOUT, icon_color=ft.Colors.ERROR,
                        on_click=accionar_logout, tooltip="Cerrar Sesión",
                    ),
                ]),
            )

            repintar_sidebar()

            # Input siempre en negro/blanco sin importar el modo
            campo_texto.color = ft.Colors.BLACK
            campo_texto.cursor_color = ft.Colors.BLACK
            campo_texto.bgcolor = ft.Colors.WHITE
            campo_texto.fill_color = ft.Colors.WHITE
            btn_enviar_texto.icon_color = ft.Colors.BLACK
            contenedor_input_texto.bgcolor = ft.Colors.WHITE
            contenedor_input_texto.border = ft.Border.all(3, ft.Colors.BLACK)
            contenedor_input_texto.shadow = ft.BoxShadow(spread_radius=0, blur_radius=0, offset=ft.Offset(6, 6), color=ft.Colors.BLACK)

            zona_central = ft.Container(
                expand=True, padding=20,
                bgcolor=ft.Colors.SURFACE,
                content=ft.Column(controls=[
                    ft.Row([
                        ft.IconButton(icon=ft.Icons.MENU, on_click=toggle_sidebar, tooltip="Expandir Sidebar"),
                        ft.Container(expand=True),
                        ft.IconButton(icon=ft.Icons.EXTENSION, on_click=lambda e: (setattr(page, 'route', '/plugins'), cambiar_ruta(None)), tooltip="Biblioteca de Plugins & Conectores IA (MCP)"),
                        ft.IconButton(icon=ft.Icons.SETTINGS, on_click=lambda e: (setattr(page, 'route', '/settings'), cambiar_ruta(None)), tooltip="Settings")
                    ]),
                    boton_capsula, lista_chat, indicador_pensando,
                    contenedor_onda_voz, contenedor_input_texto,
                ]),
            )

            import datetime
            es_noche = datetime.datetime.now().hour >= 19 or datetime.datetime.now().hour <= 6
            if modo_oscuro_auto_ref[0]:
                modo_oscuro_ref[0] = es_noche
            page.theme_mode = ft.ThemeMode.DARK if modo_oscuro_ref[0] else ft.ThemeMode.LIGHT

            escenario_dashboard = ft.Row(expand=True, spacing=0, controls=[barra_lateral, zona_central])
            page.views.append(
                ft.View(route="/dashboard", controls=[escenario_dashboard], padding=0)
            )

        elif page.route == "/settings":
            def toggle_modo(e):
                modo_oscuro_ref[0] = switch_modo.value
                modo_oscuro_auto_ref[0] = False
                page.theme_mode = ft.ThemeMode.DARK if modo_oscuro_ref[0] else ft.ThemeMode.LIGHT
                page.update()

            def toggle_auto(e):
                modo_oscuro_auto_ref[0] = switch_auto.value
                cambiar_ruta(None)

            switch_modo = ft.Switch(label="Modo Oscuro Manual", value=modo_oscuro_ref[0], on_change=toggle_modo)
            switch_auto = ft.Switch(label="Modo Auto (Noche)", value=modo_oscuro_auto_ref[0], on_change=toggle_auto)

            settings_content = ft.Container(
                expand=True, padding=40,
                bgcolor=ft.Colors.SURFACE,
                content=ft.Column([
                    ft.Row([
                        ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=lambda e: (setattr(page, 'route', '/dashboard'), cambiar_ruta(None))),
                        ft.Text("Configuración", size=30, weight=ft.FontWeight.BOLD),
                    ]),
                    ft.Divider(),
                    ft.Text("Apariencia", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                    switch_modo,
                    switch_auto,
                    ft.Divider(),
                    ft.Text("Habilidades (Skills)", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                    ft.Row([
                        ft.TextField(hint_text="URL Github del Skill...", expand=True),
                        ft.ElevatedButton("Añadir", color=ft.Colors.ON_PRIMARY, bgcolor=ft.Colors.PRIMARY)
                    ]),
                    ft.ListView(
                        controls=[
                            ft.ListTile(title=ft.Text("Skill Básico"), subtitle=ft.Text("Preinstalado"), leading=ft.Icon(ft.Icons.EXTENSION, color=ft.Colors.PRIMARY))
                        ]
                    )
                ])
            )

            import datetime
            es_noche = datetime.datetime.now().hour >= 19 or datetime.datetime.now().hour <= 6
            if modo_oscuro_auto_ref[0]:
                modo_oscuro_ref[0] = es_noche
            page.theme_mode = ft.ThemeMode.DARK if modo_oscuro_ref[0] else ft.ThemeMode.LIGHT

            page.views.append(
                ft.View(route="/settings", controls=[settings_content], padding=0)
            )

        elif page.route == "/plugins":
            if usuario_ref[0] is None or rol_ref[0] is None:
                page.route = "/"
                cambiar_ruta(None)
                return

            filtro_query = [""]
            filtro_categoria = ["todos"]

            columna_cards = ft.Column(spacing=15, scroll=ft.ScrollMode.AUTO, expand=True)

            def mostrar_dialogo_nuevo_plugin(e):
                campo_id = ft.TextField(label="ID del Plugin (slug único)", hint_text="ej: spotify_mcp", border_radius=0)
                campo_nombre = ft.TextField(label="Nombre del Plugin", hint_text="ej: Spotify Music Controller", border_radius=0)
                campo_cat = ft.Dropdown(
                    label="Categoría",
                    border_radius=0,
                    value="Productividad",
                    options=[
                        ft.dropdown.Option("Productividad"),
                        ft.dropdown.Option("Desarrollo de Software"),
                        ft.dropdown.Option("Diseño & Multimedia"),
                        ft.dropdown.Option("Comunicación & Equipos"),
                        ft.dropdown.Option("Datos & Analítica"),
                        ft.dropdown.Option("Personalizado"),
                    ]
                )
                campo_tipo = ft.Dropdown(
                    label="Tipo de Conector",
                    border_radius=0,
                    value="mcp_connector",
                    options=[
                        ft.dropdown.Option("mcp_connector", text="Conector MCP (Servidor Externo)"),
                        ft.dropdown.Option("local_python", text="Script Local (Python)"),
                    ]
                )
                campo_comando = ft.TextField(
                    label="Comando MCP o Endpoint",
                    hint_text="ej: npx -y @modelcontextprotocol/server-github o url",
                    border_radius=0
                )
                campo_uso = ft.TextField(
                    label="Descripción y Uso",
                    hint_text="Qué hace y cómo lo usa el LLM...",
                    multiline=True,
                    min_lines=2,
                    border_radius=0
                )

                def guardar_nuevo_plugin(ev):
                    if not campo_id.value or not campo_nombre.value:
                        alerta = ft.SnackBar(ft.Text("Por favor ingresa ID y Nombre."), bgcolor=ft.Colors.RED_800)
                        page.overlay.append(alerta)
                        alerta.open = True
                        page.update()
                        return
                    res = plugin_manager.agregar_plugin_personalizado({
                        "id": campo_id.value.strip(),
                        "nombre": campo_nombre.value.strip(),
                        "categoria": campo_cat.value,
                        "tipo": campo_tipo.value,
                        "plataformas": "Reaxy$ MCP",
                        "uso": campo_uso.value.strip(),
                        "ideal_para": "Herramienta personalizada agregada por el usuario",
                        "config": {"comando_mcp": campo_comando.value.strip()}
                    })
                    dialogo.open = False
                    repintar_catalogo()
                    alerta = ft.SnackBar(ft.Text(res, color=ft.Colors.WHITE), bgcolor=ft.Colors.GREEN_800)
                    page.overlay.append(alerta)
                    alerta.open = True
                    page.update()

                dialogo = ft.AlertDialog(
                    title=ft.Text("Añadir Nuevo Plugin / Conector MCP", weight=ft.FontWeight.BOLD),
                    content=ft.Container(
                        width=500,
                        content=ft.Column(
                            tight=True,
                            spacing=12,
                            controls=[campo_id, campo_nombre, campo_cat, campo_tipo, campo_comando, campo_uso]
                        )
                    ),
                    actions=[
                        ft.TextButton("Cancelar", on_click=lambda ev: (setattr(dialogo, 'open', False), page.update())),
                        ft.ElevatedButton(
                            "Guardar y Activar",
                            bgcolor=ft.Colors.GREEN_400 if not modo_oscuro_ref[0] else ft.Colors.GREEN_800,
                            color=get_text_color(),
                            style=get_btn_style(),
                            on_click=guardar_nuevo_plugin
                        ),
                    ],
                )
                page.overlay.append(dialogo)
                dialogo.open = True
                page.update()

            def mostrar_dialogo_config(plugin_meta):
                pid = plugin_meta["id"]
                nombre = plugin_meta["nombre"]
                conf_existente = plugin_meta.get("config", {})
                campos_ctrls = []
                fields = plugin_meta.get("config_fields", [
                    {"key": "param_general", "label": "Configuración / Parámetro", "default": ""}
                ])
                for fld in fields:
                    k = fld["key"]
                    val_actual = conf_existente.get(k, fld.get("default", ""))
                    tf = ft.TextField(label=fld["label"], value=val_actual, border_radius=0, data=k, expand=True)
                    campos_ctrls.append(tf)

                def guardar_conf(ev):
                    nuevos_valores = {}
                    for c in campos_ctrls:
                        nuevos_valores[c.data] = c.value.strip()
                    plugin_manager.guardar_config_plugin(pid, nuevos_valores)
                    dialog_conf.open = False
                    repintar_catalogo()
                    alerta = ft.SnackBar(ft.Text(f"Configuración de '{nombre}' guardada.", color=ft.Colors.WHITE), bgcolor=ft.Colors.GREEN_800)
                    page.overlay.append(alerta)
                    alerta.open = True
                    page.update()

                dialog_conf = ft.AlertDialog(
                    title=ft.Text(f"Configuración: {nombre}", weight=ft.FontWeight.BOLD),
                    content=ft.Container(
                        width=500,
                        content=ft.Column(tight=True, spacing=12, controls=campos_ctrls)
                    ),
                    actions=[
                        ft.TextButton("Cancelar", on_click=lambda ev: (setattr(dialog_conf, 'open', False), page.update())),
                        ft.ElevatedButton(
                            "Guardar Cambios",
                            bgcolor=ft.Colors.BLUE_400 if not modo_oscuro_ref[0] else ft.Colors.BLUE_800,
                            color=get_text_color(),
                            style=get_btn_style(),
                            on_click=guardar_conf
                        ),
                    ]
                )
                page.overlay.append(dialog_conf)
                dialog_conf.open = True
                page.update()

            def repintar_catalogo():
                columna_cards.controls.clear()
                plugins = plugin_manager.obtener_catalogo()
                query = filtro_query[0].lower().strip()
                cat_filtro = filtro_categoria[0]

                filtrados = []
                for p in plugins:
                    if query and (query not in p["nombre"].lower() and query not in p.get("categoria", "").lower() and query not in p.get("uso", "").lower()):
                        continue
                    if cat_filtro == "recomendados" and not p.get("recomendado", False):
                        continue
                    if cat_filtro == "locales" and p.get("tipo") != "local_python":
                        continue
                    if cat_filtro == "cloud" and p.get("tipo") == "local_python":
                        continue
                    filtrados.append(p)

                if not filtrados:
                    columna_cards.controls.append(
                        ft.Container(
                            padding=30,
                            alignment=ft.Alignment.CENTER,
                            content=ft.Text("No se encontraron plugins con ese criterio de búsqueda.", italic=True, color=ft.Colors.GREY_500)
                        )
                    )
                else:
                    for p in filtrados:
                        pid = p["id"]
                        es_activo = p.get("activo", False)
                        es_rec = p.get("recomendado", False)
                        tipo_label = "Local (Python)" if p.get("tipo") == "local_python" else "Conector MCP"
                        badge_tipo_color = ft.Colors.TEAL_400 if not modo_oscuro_ref[0] else ft.Colors.TEAL_900

                        def on_switch_cambio(ev, target_id=pid, target_name=p["nombre"]):
                            nuevo_estado = ev.control.value
                            plugin_manager.toggle_plugin(target_id, nuevo_estado)
                            alerta = ft.SnackBar(
                                ft.Text(f"Plugin '{target_name}': {'Activado ✅' if nuevo_estado else 'Desactivado ⏸️'}"),
                                bgcolor=ft.Colors.GREEN_700 if nuevo_estado else ft.Colors.GREY_800
                            )
                            page.overlay.append(alerta)
                            alerta.open = True
                            page.update()

                        switch_activo = ft.Switch(
                            value=es_activo,
                            active_color=ft.Colors.GREEN_500,
                            on_change=on_switch_cambio,
                            tooltip="Activar/Desactivar herramienta en el LLM"
                        )

                        badges = [
                            ft.Container(
                                content=ft.Text(p.get("categoria", "General"), size=11, weight=ft.FontWeight.BOLD, color=get_text_color()),
                                bgcolor=ft.Colors.AMBER_300 if not modo_oscuro_ref[0] else ft.Colors.AMBER_900,
                                padding=ft.Padding(left=8, top=2, right=8, bottom=2),
                                border=get_neo_border(),
                            ),
                            ft.Container(
                                content=ft.Text(tipo_label, size=11, weight=ft.FontWeight.BOLD, color=get_text_color()),
                                bgcolor=badge_tipo_color,
                                padding=ft.Padding(left=8, top=2, right=8, bottom=2),
                                border=get_neo_border(),
                            ),
                        ]
                        if es_rec:
                            badges.append(
                                ft.Container(
                                    content=ft.Text("⭐ Recomendado", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK),
                                    bgcolor=ft.Colors.YELLOW_300,
                                    padding=ft.Padding(left=8, top=2, right=8, bottom=2),
                                    border=get_neo_border(),
                                )
                            )

                        card = ft.Container(
                            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST if modo_oscuro_ref[0] else ft.Colors.WHITE,
                            padding=18,
                            border=get_neo_border(),
                            shadow=get_neo_shadow(),
                            content=ft.Column(
                                spacing=8,
                                controls=[
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            ft.Row(spacing=8, controls=badges),
                                            ft.Row(
                                                spacing=10,
                                                controls=[
                                                    ft.Text("Activo" if es_activo else "Inactivo", weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.GREEN_400 if es_activo else ft.Colors.GREY_500),
                                                    switch_activo,
                                                    ft.IconButton(
                                                        icon=ft.Icons.TUNE,
                                                        tooltip="Configurar parámetros",
                                                        icon_color=get_text_color(),
                                                        on_click=lambda ev, meta=p: mostrar_dialogo_config(meta)
                                                    )
                                                ]
                                            )
                                        ]
                                    ),
                                    ft.Text(p["nombre"], size=18, weight=ft.FontWeight.W_900, color=get_text_color()),
                                    ft.Text(p.get("uso", ""), size=13, color=get_text_color()),
                                    ft.Row([
                                        ft.Text("🎯 Ideal para: ", weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.BLUE_400),
                                        ft.Text(p.get("ideal_para", ""), size=12, color=get_text_color()),
                                    ]),
                                    ft.Row([
                                        ft.Text("🌐 Plataformas: ", weight=ft.FontWeight.BOLD, size=11, color=ft.Colors.GREY_500),
                                        ft.Text(p.get("plataformas", ""), size=11, italic=True, color=ft.Colors.GREY_500),
                                    ])
                                ]
                            )
                        )
                        columna_cards.append(card)
                page.update()

            def filtrar_por_texto(ev):
                filtro_query[0] = ev.control.value
                repintar_catalogo()

            def cambiar_filtro_cat(categoria):
                filtro_categoria[0] = categoria
                repintar_catalogo()

            campo_buscador = ft.TextField(
                hint_text="Buscar plugin o conector (ej: Blender, Google Drive, GitHub)...",
                prefix_icon=ft.Icons.SEARCH,
                expand=True,
                border_radius=0,
                border_color=get_border_color(),
                color=get_text_color(),
                on_change=filtrar_por_texto
            )

            btn_nuevo = ft.ElevatedButton(
                content=ft.Row([
                    ft.Icon(ft.Icons.ADD_BOX, color=get_text_color()),
                    ft.Text("+ Agregar Plugin / Conector MCP", color=get_text_color(), weight=ft.FontWeight.BOLD),
                ]),
                bgcolor=ft.Colors.GREEN_400 if not modo_oscuro_ref[0] else ft.Colors.GREEN_800,
                style=get_btn_style(),
                height=50,
                on_click=mostrar_dialogo_nuevo_plugin
            )

            barra_filtros = ft.Row(
                spacing=10,
                controls=[
                    ft.ElevatedButton("Todos (24)", style=get_btn_style(), bgcolor=ft.Colors.BLUE_200 if not modo_oscuro_ref[0] else ft.Colors.BLUE_900, on_click=lambda e: cambiar_filtro_cat("todos")),
                    ft.ElevatedButton("⭐ Recomendados", style=get_btn_style(), bgcolor=ft.Colors.YELLOW_200 if not modo_oscuro_ref[0] else ft.Colors.YELLOW_900, on_click=lambda e: cambiar_filtro_cat("recomendados")),
                    ft.ElevatedButton("💻 Locales (4)", style=get_btn_style(), bgcolor=ft.Colors.TEAL_200 if not modo_oscuro_ref[0] else ft.Colors.TEAL_900, on_click=lambda e: cambiar_filtro_cat("locales")),
                    ft.ElevatedButton("☁️ Cloud / MCP (20)", style=get_btn_style(), bgcolor=ft.Colors.PURPLE_200 if not modo_oscuro_ref[0] else ft.Colors.PURPLE_900, on_click=lambda e: cambiar_filtro_cat("cloud")),
                ]
            )

            plugins_content = ft.Container(
                expand=True, padding=30,
                bgcolor=ft.Colors.SURFACE,
                content=ft.Column(
                    spacing=15,
                    expand=True,
                    controls=[
                        ft.Row([
                            ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=lambda e: (setattr(page, 'route', '/dashboard'), cambiar_ruta(None))),
                            ft.Column([
                                ft.Text("Biblioteca de Plugins / Conectores de IA (MCP)", size=24, weight=ft.FontWeight.W_900, color=get_text_color()),
                                ft.Text("Gestiona, activa o conecta herramientas para tu agente sin reiniciar la aplicación.", size=12, color=ft.Colors.GREY_500),
                            ], spacing=2),
                            ft.Container(expand=True),
                            btn_nuevo,
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Divider(color=get_border_color(), height=2),
                        ft.Row([campo_buscador]),
                        barra_filtros,
                        ft.Divider(color="transparent", height=5),
                        columna_cards
                    ]
                )
            )

            repintar_catalogo()

            import datetime
            es_noche = datetime.datetime.now().hour >= 19 or datetime.datetime.now().hour <= 6
            if modo_oscuro_auto_ref[0]:
                modo_oscuro_ref[0] = es_noche
            page.theme_mode = ft.ThemeMode.DARK if modo_oscuro_ref[0] else ft.ThemeMode.LIGHT

            page.views.append(
                ft.View(route="/plugins", controls=[plugins_content], padding=0)
            )

        page.update()

    page.on_route_change = cambiar_ruta
    
    # Auto-Login dinamico sin hardcoding
    import json
    import os
    saved_session = None
    if os.path.exists("session_store.json"):
        try:
            with open("session_store.json", "r") as f:
                saved_session = json.load(f)
        except:
            pass
            
    if saved_session and saved_session.get("usuario"):
        usuario_ref[0] = saved_session["usuario"]
        rol_ref[0] = saved_session["rol"]
        page.route = "/dashboard"
        cambiar_ruta(None)
        iniciar_worker()
        threading.Thread(target=inicializar_sistemas_audio, args=(page,), daemon=True).start()
        threading.Thread(
            target=motor_jarvis,
            args=(page, id_peticion_ref, _procesar_ia_wrapper),
            daemon=True,
        ).start()
    else:
        page.route = "/"
        cambiar_ruta(None)
