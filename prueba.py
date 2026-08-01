import flet as ft

def laboratorio_vidrio(page: ft.Page):
    # 1. PREPARACIÓN DEL LIENZO
    page.title = "Laboratorio Glassmorphism"
    page.padding = 0

    # 2. EL EMISOR DE LUZ (El Fondo)
    fondo_gradiente = ft.Container(
        expand=True,
        gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,      # <--- A mayúscula
            end=ft.Alignment.BOTTOM_RIGHT,    # <--- A mayúscula
            colors=[ft.Colors.BLUE_900, ft.Colors.PURPLE_900, ft.Colors.DEEP_ORANGE_900]
        )
    )

    # 3. EL MOLDE DE VIDRIO (La matemática centralizada)
    borde_luminoso = ft.Colors.with_opacity(0.2, ft.Colors.WHITE)
    estilo_vidrio = {
        "bgcolor": ft.Colors.with_opacity(0.1, ft.Colors.WHITE),
        "blur": ft.Blur(20, 20, ft.BlurTileMode.MIRROR), 
        "border": ft.Border(
            top=ft.BorderSide(1, borde_luminoso),
            right=ft.BorderSide(1, borde_luminoso),
            bottom=ft.BorderSide(1, borde_luminoso),
            left=ft.BorderSide(1, borde_luminoso)
        ),
        "border_radius": 20,
        "padding": 40
    }

    # 4. EL PANEL DE PRUEBA
    panel_prueba = ft.Container(
        **estilo_vidrio,
        width=400,
        height=300,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            run_alignment=ft.MainAxisAlignment.CENTER, 
            controls=[
                ft.Icon(ft.Icons.DIAMOND, size=50, color=ft.Colors.WHITE),
                ft.Text("Glassmorphism", size=30, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                ft.Text("Mueve la ventana para ver la refracción", color=ft.Colors.WHITE70)
            ]
        )
    )

    # 5. EL ENSAMBLAJE (EJE Z)
    escenario = ft.Stack(
        expand=True,
        controls=[
            fondo_gradiente, # Capa 0: La luz
            
            # Capa 1: El Vidrio. 
            ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER, # <--- A mayúscula
                content=panel_prueba
            )
        ]
    )

    page.add(escenario)

ft.run(laboratorio_vidrio)
# ARRANQUE LIMPIO (Actualizado al nuevo estándar de Flet)