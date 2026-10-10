import chromadb
from chromadb.utils import embedding_functions

# --- 1. CONEXIÓN A LA BÓVEDA (Embeddings locales en CPU, nunca Ollama) ---
_embedding_fn = embedding_functions.DefaultEmbeddingFunction()
boveda = chromadb.PersistentClient(path="./cerebro_jarvis")
memoria_largo_plazo = boveda.get_or_create_collection(
    name="database_vectorial_v2",
    embedding_function=_embedding_fn,
)

# --- 2. GUARDAR CON ETIQUETA MULTI-INQUILINO ---
def guardar_recuerdo(id_recuerdo, texto, usuario_activo):
    """Guarda el recuerdo ENGRAPANDO el nombre del dueño"""
    try:
        memoria_largo_plazo.add(
            ids=[f"{usuario_activo}_{id_recuerdo}"], # Hacemos el ID único por usuario
            documents=[texto],
            metadatas=[{"dueño": usuario_activo}]    # <--- LA ETIQUETA INVISIBLE
        )
        print(f"✅ Recuerdo guardado en la bóveda de: {usuario_activo}")
    except Exception as e:
        print(f"❌ Error al guardar el recuerdo: {e}")

# --- 3. RECORDAR CON FILTRO DE SEGURIDAD ---
def recordar(pregunta, usuario_activo):
    """Busca en el mapa matemático SOLO dentro de los vectores del dueño"""
    try:
        resultados = memoria_largo_plazo.query(
            query_texts=[pregunta],
            n_results=1,
            where={"dueño": usuario_activo}          # <--- LA BARRERA MATEMÁTICA
        )
        
        if resultados['documents'] and len(resultados['documents'][0]) > 0:
            return resultados['documents'][0][0]
        else:
            return "No tengo recuerdos sobre eso en tu perfil, señor."
    except Exception as e:
        print(f"❌ Error al buscar recuerdos: {e}")
        return "Hubo un problema al buscar en mis recuerdos."

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