import requests
import sqlite3
import json
import numpy as np

def obtener_embedding(texto):
    """Llama a Ollama para convertir texto en un vector matemático."""
    url = "http://localhost:11434/api/embeddings"
    payload = {
        "model": "nomic-embed-text",
        "prompt": texto
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        return r.json().get("embedding", [])
    except Exception as e:
        print(f"Error generando embedding: {e}")
        return []

def similitud_coseno(v1, v2):
    """Calcula matemáticamente cuánto se parecen dos vectores (0.0 a 1.0)"""
    v1, v2 = np.array(v1), np.array(v2)
    if v1.size == 0 or v2.size == 0: return 0.0
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

def buscar_tickets_similares(asunto, cuerpo, top_k=2):
    """Busca en SQLite los tickets más parecidos semánticamente."""
    texto_buscar = f"{asunto} {cuerpo}"
    vector_nuevo = obtener_embedding(texto_buscar)
    
    if not vector_nuevo:
        return [], []

    try:
        conn = sqlite3.connect("data/incidencias.db")
        cursor = conn.cursor()
        
        # ACTULIZACIÓN: Extraemos las nuevas métricas multidimensionales y el feedback humano
        cursor.execute("""
            SELECT asunto, cuerpo, prediccion, score, razonamiento, embedding_vector,
                   revisado, score_humano, razonamiento_humano,
                   nivel_queja, nivel_retraso, nivel_queja_humano, nivel_retraso_humano
            FROM tickets 
            WHERE embedding_vector != '[]'
        """)
        filas = cursor.fetchall()
        conn.close()

        resultados = []
        for fila in filas:
            # Desempaquetado actualizado con las 13 columnas
            asunto_bd, cuerpo_bd, prediccion, score, razonamiento, emb_str, \
            revisado, score_humano, razonamiento_humano, \
            nivel_queja, nivel_retraso, nivel_queja_humano, nivel_retraso_humano = fila
            
            vector_bd = json.loads(emb_str)
            
            # Calculamos similitud
            similitud = similitud_coseno(vector_nuevo, vector_bd)
            
            # ACTULIZACIÓN: Añadimos todos los campos al diccionario de resultados
            resultados.append({
                "similitud": similitud,
                "asunto": asunto_bd,
                "cuerpo": cuerpo_bd,
                "prediccion": prediccion,
                "score": score,
                "razonamiento": razonamiento,
                "revisado": revisado,
                "score_humano": score_humano,
                "razonamiento_humano": razonamiento_humano,
                "nivel_queja": nivel_queja,
                "nivel_retraso": nivel_retraso,
                "nivel_queja_humano": nivel_queja_humano,
                "nivel_retraso_humano": nivel_retraso_humano
            })
        
        # Ordenamos de mayor a menor similitud y nos quedamos con los 2 mejores
        resultados_ordenados = sorted(resultados, key=lambda x: x["similitud"], reverse=True)[:top_k]
        
        return resultados_ordenados, vector_nuevo
        
    except Exception as e:
        print(f"Error en RAG: {e}")
        return [], vector_nuevo