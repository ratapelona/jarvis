"""
enrutador_llm.py — Enrutador Determinista de Modelos (Sin llamadas a LLM)

Arquitectura Reaxy:
- Un solo modelo residente: qwen3.5:9b (rápido, siempre en VRAM)
- Modo pesado: gpt-oss:20b (exclusivo para delegar_tarea_larga)
- Regla fija determinista: sin llamadas al LLM para decidir el modelo.
"""
from config import MODELO_RAPIDO, MODELO_PESADO


def decidir_modelo_para_tarea(prompt_usuario: str = "", es_tarea_larga: bool = False, origen: str = "") -> str:
    """
    Retorna el nombre del modelo según regla fija determinista:
    - Rápido por defecto: 'qwen3.5:9b'
    - Pesado solo si es_tarea_larga=True o origen == 'delegar_tarea_larga': 'gpt-oss:20b'

    CERO llamadas a LLM para decidir.
    """
    if es_tarea_larga or origen == "delegar_tarea_larga":
        return MODELO_PESADO

    return MODELO_RAPIDO


if __name__ == "__main__":
    print("--- Prueba del Enrutador Determinista ---")
    print(f"Petición normal: {decidir_modelo_para_tarea('Hola, qué tal')} (esperado: {MODELO_RAPIDO})")
    print(f"Tarea delegada: {decidir_modelo_para_tarea('Investiga el mercado', origen='delegar_tarea_larga')} (esperado: {MODELO_PESADO})")
    print(f"Flag tarea larga: {decidir_modelo_para_tarea('Proceso largo', es_tarea_larga=True)} (esperado: {MODELO_PESADO})")
