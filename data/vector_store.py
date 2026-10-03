"""
data/vector_store.py — Memoria Semántica con ChromaDB (ESC-03)

Reemplazo de dattabase.py con:
- Poda automática (máximo 500 recuerdos por usuario)
- Misma API multi-inquilino con filtros por dueño
"""
import chromadb

from config import CHROMA_PATH, CHROMA_COLLECTION, MAX_RECUERDOS_POR_USUARIO

# =============================================================================
# Conexión a la bóveda vectorial
# =============================================================================
_boveda = chromadb.PersistentClient(path=CHROMA_PATH)
_memoria = _boveda.get_or_create_collection(name=CHROMA_COLLECTION)


# =============================================================================
# Guardar con etiqueta multi-inquilino + poda
# =============================================================================
def guardar_recuerdo(id_recuerdo: str, texto: str, usuario_activo: str):
    """
    Guarda un recuerdo en ChromaDB con aislamiento por usuario.
    ESC-03: Poda automática si se excede el límite por usuario.
    """
    try:
        # Poda: verificar cantidad de recuerdos del usuario
        existentes = _memoria.get(
            where={"dueño": usuario_activo},
            include=[]  # Solo IDs, no documentos
        )
        
        if existentes and len(existentes["ids"]) >= MAX_RECUERDOS_POR_USUARIO:
            # Eliminar los más viejos (primeros en la lista = más antiguos)
            exceso = len(existentes["ids"]) - MAX_RECUERDOS_POR_USUARIO + 1
            ids_a_borrar = existentes["ids"][:exceso]
            _memoria.delete(ids=ids_a_borrar)
            print(f"🧹 Podados {exceso} recuerdos antiguos de {usuario_activo}")

        _memoria.add(
            ids=[f"{usuario_activo}_{id_recuerdo}"],
            documents=[texto],
            metadatas=[{"dueño": usuario_activo}],
        )
    except Exception as e:
        print(f"❌ Error al guardar recuerdo: {e}")


# =============================================================================
# Recordar con filtro de seguridad multi-inquilino
# =============================================================================
def recordar(pregunta: str, usuario_activo: str) -> str:
    """Busca recuerdos relevantes SOLO del usuario actual."""
    try:
        resultados = _memoria.query(
            query_texts=[pregunta],
            n_results=1,
            where={"dueño": usuario_activo},
        )

        if resultados["documents"] and len(resultados["documents"][0]) > 0:
            return resultados["documents"][0][0]
        else:
            return ""
    except Exception as e:
        print(f"❌ Error al buscar recuerdos: {e}")
        return ""
