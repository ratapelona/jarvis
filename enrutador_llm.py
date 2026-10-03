import requests
import json
import re

# Modelos disponibles (Diccionario provisto)
MODELOS_DISPONIBLES = {
    "qwen2.5-coder:7b": "El experto en programación y JSON.",
    "qwen3:8b": "El experto en escritura y resúmenes.",
    "nomic-embed-text": "Un micro-modelo experto en buscar documentos locales."
}

def decidir_modelo_para_tarea(prompt_usuario, url_api="http://localhost:11434/v1/chat/completions"):
    """
    Usa un modelo router para decidir a qué especialista enviar la tarea
    según el prompt del usuario. Retorna el nombre del modelo exacto.
    """
    instrucciones = (
        "Eres un enrutador (router) inteligente. Tu único trabajo es analizar el mensaje del usuario "
        "y decidir cuál de los siguientes modelos es el más adecuado para procesar su solicitud:\n\n"
    )
    for nombre, desc in MODELOS_DISPONIBLES.items():
        instrucciones += f"- '{nombre}': {desc}\n"
    
    instrucciones += (
        "\nDebes responder ÚNICAMENTE con el nombre exacto del modelo. "
        "No des explicaciones, ni uses bloques de código, ni comillas."
    )
    
    paquete = {
        "model": "qwen3:8b", # Modelo base para tomar la decisión
        "messages": [
            {"role": "system", "content": instrucciones},
            {"role": "user", "content": prompt_usuario}
        ],
        "temperature": 0.1,
        "stream": False
    }
    
    try:
        res = requests.post(url_api, json=paquete, timeout=30)
        if res.status_code == 200:
            respuesta = res.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            # Limpiar posible <think> de razonamiento del modelo
            respuesta = re.sub(r"<think>[\s\S]*?</think>", "", respuesta).strip()
            
            # Buscar que el nombre del modelo esté en la respuesta
            for modelo in MODELOS_DISPONIBLES.keys():
                if modelo.lower() in respuesta.lower():
                    return modelo
            
            return "qwen3:8b" # Default fallback
    except Exception as e:
        print(f"Error en el enrutador: {e}")
        return "qwen3:8b" # Default fallback

if __name__ == "__main__":
    # Tests locales
    print("--- Prueba del Enrutador LoRA ---")
    prompts_prueba = [
        "Escribe un script en python para hacer web scraping con beautifulsoup.",
        "Redacta un resumen formal y ejecutivo del último reporte de finanzas.",
        "Busca el archivo de políticas en mi directorio local para ver qué dice sobre vacaciones."
    ]
    for p in prompts_prueba:
        print(f"\nUsuario: '{p}'")
        modelo = decidir_modelo_para_tarea(p)
        print(f"Despertando a -> {modelo}")
