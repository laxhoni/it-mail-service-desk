import requests
import json
import logging

def analizar_con_ia(asunto, cuerpo):
    url = "http://localhost:11434/api/generate"
    
    # PROMPT UNIFICADO: Escala + Restricciones de Salida
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
        }, timeout=60)
        
        # Parseo de la respuesta
        respuesta_json = json.loads(r.json().get('response', '{}'))
        
        # Limpieza de seguridad: Forzamos mayúsculas en la predicción por si acaso
        return {
            "prediccion": str(respuesta_json.get("prediccion", "NO_QUEJA")).upper(),
            "score": int(respuesta_json.get("score", 1)),
            "razonamiento": respuesta_json.get("razonamiento", "Sin detalles adicionales.")
        }

    except Exception as e:
        logging.error(f"❌ Error en motor IA: {e}")
        return {"prediccion": "ERROR", "score": 1, "razonamiento": "Fallo de conexión o formato."}