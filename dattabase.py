import chromadb
import requests

# --- 1. CONEXIÓN A LA BÓVEDA ---
boveda = chromadb.PersistentClient(path="./cerebro_jarvis")
memoria_largo_plazo = boveda.get_or_create_collection(name="database_vectorial")

# --- 2. EL TRADUCTOR MATEMÁTICO ---
def convertir_a_coordenadas(texto):
    """Convierte el texto en un vector usando Ollama local"""
    url = "http://127.0.0.1:11434/api/embeddings"
    paquete = {
        "model": "nomic-embed-text",
        "prompt": texto
    }
    try:
        respuesta = requests.post(url, json=paquete)
        if respuesta.status_code == 200:
            return respuesta.json()["embedding"]
    except:
        pass
    print("❌ Error de conexión con el traductor matemático.")
    return None

# --- 3. GUARDAR CON ETIQUETA MULTI-INQUILINO ---
def guardar_recuerdo(id_recuerdo, texto, usuario_activo):
    """Guarda el recuerdo ENGRAPANDO el nombre del dueño"""
    vector = convertir_a_coordenadas(texto)
    if vector:
        memoria_largo_plazo.add(
            ids=[f"{usuario_activo}_{id_recuerdo}"], # Hacemos el ID único por usuario
            embeddings=[vector],
            documents=[texto],
            metadatas=[{"dueño": usuario_activo}]    # <--- LA ETIQUETA INVISIBLE
        )
        print(f"✅ Recuerdo guardado en la bóveda de: {usuario_activo}")

# --- 4. RECORDAR CON FILTRO DE SEGURIDAD ---
def recordar(pregunta, usuario_activo):
    """Busca en el mapa matemático SOLO dentro de los vectores del dueño"""
    vector_pregunta = convertir_a_coordenadas(pregunta)
    if vector_pregunta:
        resultados = memoria_largo_plazo.query(
            query_embeddings=[vector_pregunta],
            n_results=1,
            where={"dueño": usuario_activo}          # <--- LA BARRERA MATEMÁTICA
        )
        
        if resultados['documents'] and resultados['documents'][0]:
            return resultados['documents'][0][0]
        else:
            return "No tengo recuerdos sobre eso en tu perfil, señor."

# ==========================================
# ZONA DE PRUEBAS
# ==========================================
if __name__ == "__main__":
    print("--- INICIANDO PRUEBAS MULTI-INQUILINO ---\n")
    
    # 1. Tu hermana guarda su recuerdo
    guardar_recuerdo("pony_dia1", "Hoy vi un episodio increíble de Rainbow Dash.", "hermana")
    
    # 2. Tú guardas tu recuerdo
    guardar_recuerdo("jarvis_dia1", "Hoy construí un sistema agéntico con Python y Flet.", "diego")
    
    print("\n--- PRUEBA DE AISLAMIENTO ---")
    pregunta = "¿Qué hice hoy?"
    
    # Tú preguntas qué hiciste hoy
    print(f"Pregunta alejandro: {recordar(pregunta, 'diego')}")
    
    # Tu hermana pregunta qué hizo hoy
    print(f"Pregunta Hermana: {recordar(pregunta, 'hermana')}")