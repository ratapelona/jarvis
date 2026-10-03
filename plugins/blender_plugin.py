"""
plugins/blender_plugin.py — Plugin de Automatización y Render 3D con Blender (bpy) — MULTIPLATAFORMA

Ejecuta scripts de modelado y renderizado 3D con Blender usando la API nativa `bpy`.
Soporta ejecución headless (--background) para no saturar ventanas ni la GPU innecesariamente.

Soporte: Windows + macOS (/Applications/Blender.app) + Linux (/usr/bin/blender)
"""
import os
import glob
import shutil
import subprocess
from typing import Dict, Any, List

from plugins.base_plugin import BasePlugin
from config import SANDBOX_DIR, ES_WINDOWS, ES_MAC
from data.sql_store import log_accion


def _buscar_blender_exe() -> str | None:
    """Busca el ejecutable de Blender en rutas estándar del sistema operativo o en el PATH."""
    # 1. Si 'blender' ya está en el PATH del sistema (funciona en Mac/Linux/Windows)
    which_blender = shutil.which("blender")
    if which_blender:
        return which_blender

    # 2. Rutas específicas por SO
    if ES_WINDOWS:
        rutas_comunes = [
            r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender\blender.exe",
        ]
        for r in rutas_comunes:
            if os.path.exists(r):
                return r

        # Búsqueda por glob en archivos de programa
        hallazgos = glob.glob(r"C:\Program Files\Blender Foundation\*\blender.exe")
        if hallazgos:
            return hallazgos[0]

    elif ES_MAC:
        rutas_mac = [
            "/Applications/Blender.app/Contents/MacOS/Blender",
            os.path.expanduser("~/Applications/Blender.app/Contents/MacOS/Blender"),
        ]
        for r in rutas_mac:
            if os.path.exists(r):
                return r

    else:
        rutas_linux = [
            "/usr/bin/blender",
            "/usr/local/bin/blender",
            "/snap/bin/blender",
        ]
        for r in rutas_linux:
            if os.path.exists(r):
                return r

    return None


class BlenderPlugin(BasePlugin):
    def __init__(self, custom_path: str = ""):
        self.custom_path = custom_path

    @property
    def plugin_id(self) -> str:
        return "blender_3d"

    @property
    def name(self) -> str:
        return "Blender 3D Suite"

    @property
    def description(self) -> str:
        return "Modelado, generación procedural y renderizado 3D con Blender y la API nativa bpy."

    def _get_exe(self) -> str:
        if self.custom_path and os.path.exists(self.custom_path):
            return self.custom_path
        autodetect = _buscar_blender_exe()
        return autodetect if autodetect else "blender"

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "ejecutar_script_blender",
                    "description": "Ejecuta un script Python para Blender (con la API 'bpy') para modelar, animar o renderizar una escena 3D.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "codigo_python_bpy": {
                                "type": "string",
                                "description": "Código completo de Python que importa bpy y construye la escena."
                            },
                            "nombre_archivo_script": {
                                "type": "string",
                                "description": "Nombre del script a guardar en el sandbox (ej: 'escena_cubo.py')."
                            },
                            "headless": {
                                "type": "boolean",
                                "default": True,
                                "description": "Si es True, ejecuta en segundo plano sin abrir ventana gráfica (-b)."
                            }
                        },
                        "required": ["codigo_python_bpy", "nombre_archivo_script"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "crear_escena_3d_demo",
                    "description": "Crea una escena 3D demo (geometría, luz de estudio, cámara y render) y la guarda como script listo para ejecutar.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tipo_objeto": {
                                "type": "string",
                                "enum": ["cubo", "esfera", "cilindro", "dona_torus"],
                                "default": "esfera"
                            },
                            "color_hex": {
                                "type": "string",
                                "default": "#3B82F6",
                                "description": "Color principal del material en formato hexadecimal."
                            }
                        },
                        "required": ["tipo_objeto"]
                    }
                }
            }
        ]

    def execute(self, tool_name: str, arguments: Dict[str, Any], user: str = "") -> str:
        if tool_name == "ejecutar_script_blender":
            return self._ejecutar_script(arguments, user)
        elif tool_name == "crear_escena_3d_demo":
            return self._crear_demo(arguments, user)
        return f"Herramienta '{tool_name}' no soportada por BlenderPlugin."

    def _ejecutar_script(self, args: Dict[str, Any], user: str) -> str:
        codigo = args.get("codigo_python_bpy", "")
        nombre_script = args.get("nombre_archivo_script", "script_blender.py")
        headless = args.get("headless", True)

        os.makedirs(SANDBOX_DIR, exist_ok=True)
        ruta_script = os.path.realpath(os.path.join(SANDBOX_DIR, nombre_script))
        if not ruta_script.startswith(os.path.realpath(SANDBOX_DIR)):
            return "⛔ BLOQUEADO: Path traversal detectado."

        # Guardar el script en el sandbox
        try:
            with open(ruta_script, "w", encoding="utf-8") as f:
                f.write(codigo)
        except Exception as e:
            return f"❌ Error guardando script: {e}"

        exe = self._get_exe()

        cmd = [exe]
        if headless:
            cmd.append("-b")
        cmd.extend(["-P", ruta_script])

        log_accion(user, "ejecutar_script_blender", nombre_script, f"cmd: {' '.join(cmd)}")

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, shell=False)
            if proc.returncode == 0:
                log_accion(user, "ejecutar_script_blender", nombre_script, "OK")
                return f"✅ Script de Blender ejecutado exitosamente con código 0.\nSalida: {proc.stdout[-400:] if proc.stdout else 'Render/Escena lista'}"
            else:
                return f"⚠️ Blender finalizó con advertencias (code {proc.returncode}):\n{proc.stderr[-400:] or proc.stdout[-400:]}"
        except FileNotFoundError:
            return (
                f"ℹ️ El script fue guardado con éxito en '{ruta_script}', pero el ejecutable de Blender "
                f"no se encontró automáticamente en tu sistema. Puedes configurar la ruta en la Biblioteca de Plugins o ejecutarlo manualmente con: blender -b -P {ruta_script}"
            )
        except Exception as e:
            return f"❌ Error al ejecutar Blender: {e}"

    def _crear_demo(self, args: Dict[str, Any], user: str) -> str:
        tipo = args.get("tipo_objeto", "esfera")
        color = args.get("color_hex", "#3B82F6")

        ruta_render = os.path.join(SANDBOX_DIR, f"render_{tipo}.png").replace("\\", "/")

        codigo = f'''import bpy

# Limpiar escena
bpy.ops.wm.read_factory_settings(use_empty=True)

# Crear cámara
bpy.ops.object.camera_add(location=(0, -4, 2), rotation=(1.1, 0, 0))
bpy.context.scene.camera = bpy.context.object

# Crear luz de estudio
bpy.ops.object.light_add(type='POINT', location=(3, -3, 4))
bpy.context.object.data.energy = 500

# Crear objeto principal: {tipo}
if "{tipo}" == "cubo":
    bpy.ops.mesh.primitive_cube_add(size=1.5, location=(0, 0, 0))
elif "{tipo}" == "cilindro":
    bpy.ops.mesh.primitive_cylinder_add(radius=0.8, depth=1.5, location=(0, 0, 0))
elif "{tipo}" == "dona_torus":
    bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.35, location=(0, 0, 0))
else:
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(0, 0, 0))

obj = bpy.context.object

# Asignar material con color
mat = bpy.data.materials.new(name="MaterialAuto")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
if bsdf:
    bsdf.inputs['Base Color'].default_value = (0.23, 0.51, 0.96, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.3
obj.data.materials.append(mat)

# Configurar motor de render (EEVEE o Cycles)
bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in bpy.types.RenderEngine.bl_rna.properties['engine'].enum_items else 'BLENDER_EEVEE'
bpy.context.scene.render.filepath = "{ruta_render}"
bpy.ops.render.render(write_still=True)
print("Render completado exitosamente.")
'''
        return self._ejecutar_script({
            "codigo_python_bpy": codigo,
            "nombre_archivo_script": f"demo_{tipo}.py",
            "headless": True
        }, user)
