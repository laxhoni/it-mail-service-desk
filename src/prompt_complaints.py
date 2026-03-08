import requests
import json
import logging

# IMPORTANTE: Importamos tu nuevo motor de búsqueda semántica
from src.rag_engine import buscar_tickets_similares

def analizar_con_ia(asunto, cuerpo):
    url = "http://localhost:11434/api/generate"
    
    # --- 1. EJECUTAMOS EL RAG ANTES DE CREAR EL PROMPT ---
    ejemplos_rag, vector_correo_actual = buscar_tickets_similares(asunto, cuerpo)

    if ejemplos_rag:
        for ej in ejemplos_rag:
            if ej['similitud'] > 0.5:
                logging.info(f"🧠 [RAG ACTIVO] He recordado un correo! Similitud: {ej['similitud']:.2f} | Asunto: {ej['asunto']}")
    else:
        logging.info("🧠 [RAG VACÍO] No he encontrado correos parecidos en mi memoria.")

    # --- 2. CONSTRUIMOS LOS EJEMPLOS DINÁMICOS ---
    bloque_ejemplos = ""
    for i, ej in enumerate(ejemplos_rag):
        # Solo usamos el ejemplo si la IA está segura de que se parecen (más del 50%)
        if ej['similitud'] > 0.5:
            bloque_ejemplos += f"""
            EJEMPLO HISTÓRICO {i+1} (Relevancia Semántica: {ej['similitud']:.2f}):
            Asunto: {ej['asunto']}
            Cuerpo: {ej['cuerpo']}
            => Score Asignado en el pasado: {ej['score']} | Predicción: {ej['prediccion']}
            => Razonamiento: {ej['razonamiento']}
            -------------------------
            """

    # --- 3. PROMPT UNIFICADO: Escala + Restricciones + Memoria RAG ---
    prompt = f"""
    SISTEMA: Eres un clasificador de tickets de soporte. 
    TU OBJETIVO: Evaluar la urgencia REAL basada SOLO en el contenido del mensaje.

    ESCALA DE SCORE (1-5):
    1: POSITIVO. Agradecimientos o saludos cordiales. (Ej: "hola", "buenos días", "gracias").
    2: DUDA LEVE. Preguntas generales sin urgencia.
    3: SEGUIMIENTO. Consultas sobre estado de trámites.
    4: QUEJA. Frustración, mal servicio, fallos técnicos.
    5: CRÍTICO. Amenazas legales, insultos o reclamaciones oficiales.

    REGLAS DE ORO:
    - Si el mensaje es muy corto (ej: "hola", "test", "buenos días") sin más texto, el score DEBE SER 1 o 2.
    - NO asumas urgencia si no hay palabras de queja explícitas.
    - La prediccion debe ser "NO_QUEJA" para scores 1, 2 y 3.
    - La prediccion debe ser "NEGATIVE" para scores 4 y 5.

    --- CASOS PREVIOS SIMILARES (MEMORIA RAG) ---
    Aprende de cómo se puntuaron estos tickets en el pasado para mantener la coherencia en tu decisión:
    {bloque_ejemplos if bloque_ejemplos else "No hay casos similares recientes. Usa tu propio criterio basándote estrictamente en las reglas."}
    --- FIN DE LA MEMORIA ---

    TICKET A ANALIZAR:
    Asunto: {asunto}
    Cuerpo: {cuerpo}

    RESPONDE SOLO EN JSON:
    {{
      "prediccion": "NEGATIVE" / "NO_QUEJA",
      "score": 1-5,
      "razonamiento": "Justificación breve"
    }}
    """
    
    try:
        r = requests.post(url, json={
            "model": "llama3.2", 
            "prompt": prompt, 
            "format": "json", 
            "stream": False
        }, timeout=120) # Timeout subido a 120s para dar tiempo a Llama y al RAG
        
        # Parseo de la respuesta
        respuesta_json = json.loads(r.json().get('response', '{}'))
        
        # Limpieza de seguridad: Forzamos mayúsculas en la predicción
        res_ia = {
            "prediccion": str(respuesta_json.get("prediccion", "NO_QUEJA")).upper(),
            "score": int(respuesta_json.get("score", 1)),
            "razonamiento": respuesta_json.get("razonamiento", "Sin detalles adicionales.")
        }

        # ⚠️ RETORNAMOS LA RESPUESTA LIMPIA Y EL VECTOR MATEMÁTICO
        return res_ia, vector_correo_actual

    except Exception as e:
        logging.error(f"❌ Error en motor IA: {e}")
        # Si falla, devolvemos error y una lista vacía como vector
        return {"prediccion": "ERROR", "score": 1, "razonamiento": "Fallo de conexión o formato."}, []