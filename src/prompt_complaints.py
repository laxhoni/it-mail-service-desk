import requests
import json
import logging
import os
import math

from src.rag_engine import buscar_tickets_similares

def cargar_configuracion():
    """
    Lee el archivo de configuración dinámico (Contexto y Pesos).
    Ruta estricta: data/config/config.json
    """
    ruta_config = os.path.join("data", "config", "config.json")
    
    config_default = {
        "peso_queja": 0.5,
        "peso_retraso": 0.5,
        "contexto": "Actúa como un técnico de Service Desk estándar de nivel 1."
    }
    
    try:
        if os.path.exists(ruta_config):
            with open(ruta_config, 'r', encoding='utf-8') as f:
                datos = json.load(f)
                logging.info(f"🧠 Memoria de Negocio cargada: Peso Queja={datos.get('peso_queja')} | Peso Retraso={datos.get('peso_retraso')}")
                return {
                    "peso_queja": float(datos.get("peso_queja", 0.5)),
                    "peso_retraso": float(datos.get("peso_retraso", 0.5)),
                    "contexto": str(datos.get("contexto", config_default["contexto"]))
                }
        else:
            logging.warning(f"⚠️ Archivo no encontrado en {ruta_config}. Usando fallback por defecto.")
    except Exception as e:
        logging.error(f"❌ Error crítico leyendo config.json: {e}. Usando fallback.")
    
    return config_default

def analizar_con_ia(asunto, cuerpo):
    # --- 1. CARGA DE METADATOS Y REGLAS DE NEGOCIO ---
    config = cargar_configuracion()
    url = "http://localhost:11434/api/generate"
    
    # --- 2. RECUPERACIÓN DE MEMORIA (RAG) - AHORA CON VALIDACIÓN DOBLE ---
    ejemplos_rag, vector_correo_actual = buscar_tickets_similares(asunto, cuerpo)
    bloque_ejemplos = ""

    if ejemplos_rag:
        for i, ej in enumerate(ejemplos_rag):
            if ej['similitud'] > 0.65:
                # Prioridad absoluta al Ground Truth Humano
                esta_revisado = ej.get('revisado', 0) == 1
                
                if esta_revisado:
                    # Recuperamos la validación doble del humano (si existe), sino usamos la de la IA original
                    queja_final = ej.get('nivel_queja_humano') if ej.get('nivel_queja_humano') is not None else ej.get('nivel_queja', 1)
                    retraso_final = ej.get('nivel_retraso_humano') if ej.get('nivel_retraso_humano') is not None else ej.get('nivel_retraso', 1)
                    score_final = ej.get('score_humano') if ej.get('score_humano') is not None else ej.get('score', 1)
                    
                    razonamiento_final = ej.get('razonamiento_humano') if ej.get('razonamiento_humano') else ej.get('razonamiento')
                    origen = "🗣️ EXPERTO HUMANO (VALIDADO - CUMPLIR OBLIGATORIAMENTE)"
                else:
                    queja_final = ej.get('nivel_queja', 1)
                    retraso_final = ej.get('nivel_retraso', 1)
                    score_final = ej.get('score', 1)
                    razonamiento_final = ej.get('razonamiento')
                    origen = "🤖 PREDICCIÓN IA PREVIA"

                # El prompt ahora enseña a la IA el desglose de 1 a 10 exacto que debe imitar
                bloque_ejemplos += f"""
                [CASO HISTÓRICO {i+1} | Similitud: {ej['similitud']:.2f}]
                Asunto: {ej['asunto']}
                Cuerpo: {ej['cuerpo']}
                Origen de Decisión: {origen}
                => Nivel de Queja (1-10): {queja_final}
                => Nivel de Retraso (1-10): {retraso_final}
                (Score General Ponderado resultante: {score_final}/5)
                Razonamiento: {razonamiento_final}
                -------------------------
                """
    # --- LOGGING EN CASO NO COINCIDENCIAS ---
    if not bloque_ejemplos:
        logging.info("ℹ️ RAG: No se han encontrado casos similares previos (o están por debajo del 0.65).")
    else:
        # Esto te dirá cuántos casos le está enviando realmente a la IA
        num_casos = bloque_ejemplos.count("[CASO HISTÓRICO")
        logging.info(f"🧠 RAG: Memoria activada. Inyectando {num_casos} casos similares al prompt.")
    # -----------------------------------------------------
    
    # --- 3. INYECCIÓN DEL META-PROMPT MULTIDIMENSIONAL ---
    prompt = f"""
    SISTEMA: Eres un modelo analítico avanzado de clasificación de Service Desk IT.
    
    [INSTRUCCIONES CORE DEL NEGOCIO (PRIORIDAD MÁXIMA)]
    {config['contexto']}

    TAREA: Evalúa el ticket actual en dos dimensiones matemáticas (escala 1-10).

    DIMENSIÓN 1: NIVEL DE QUEJA / IMPACTO (1-10)
    1-3: Consultas, solicitudes estándar, agradecimientos.
    4-7: Frustración moderada, degradación de servicio, bloqueos individuales.
    8-10: Lenguaje agresivo/urgente, impacto crítico, VIPs bloqueados, amenaza de negocio.

    DIMENSIÓN 2: NIVEL DE RETRASO / SLA (1-10)
    1-3: Sin prisa, sin tiempo de espera previo.
    4-7: Seguimiento de tickets antiguos, necesita respuesta en el día.
    8-10: Interrupción en tiempo real, caída de sistemas core, exige resolución inmediata.

    [MEMORIA HISTÓRICA (RAG)]
    Aprende de estos casos para no cometer errores pasados. Presta especial atención a los niveles de Queja y Retraso asignados por el EXPERTO HUMANO.
    {bloque_ejemplos if bloque_ejemplos else "Sin memoria relevante para este caso."}

    [TICKET ACTUAL]
    Asunto: {asunto}
    Cuerpo: {cuerpo}

    RESPONDE ESTRICTAMENTE EN ESTE FORMATO JSON:
    {{
      "nivel_queja": <int 1-10>,
      "nivel_retraso": <int 1-10>,
      "razonamiento": "<justificación analítica concisa>"
    }}
    """
    
    try:
        r = requests.post(
            url, 
            json={
                "model": "llama3.2", 
                "prompt": prompt, 
                "format": "json", 
                "stream": False,
                "options": {
                    "temperature": 0.0
                }
            }, 
            timeout=120
        )
        
        respuesta_json = json.loads(r.json().get('response', '{}'))
        
        # --- 4. EXTRACCIÓN Y CÁLCULO PONDERADO ---
        nivel_queja = int(respuesta_json.get("nivel_queja", 1))
        nivel_retraso = int(respuesta_json.get("nivel_retraso", 1))
        razonamiento = respuesta_json.get("razonamiento", "Análisis no detallado.")

        # Ecuación de valor de negocio
        score_combinado_10 = (nivel_queja * config['peso_queja']) + (nivel_retraso * config['peso_retraso'])
        
        # Reducción a escala de 1 a 5 (para compatibilidad de base de datos)
        score_final_5 = max(1, min(5, math.ceil(score_combinado_10 / 2.0)))

        # Actualizamos el diccionario con los nuevos datos
        return {
            "prediccion": "NEGATIVE" if score_final_5 >= 4 else "NO_QUEJA",
            "score": score_final_5,
            "nivel_queja": nivel_queja,
            "nivel_retraso": nivel_retraso,
            "razonamiento": razonamiento
        }, vector_correo_actual

    except Exception as e:
        logging.error(f"❌ Error en inferencia IA: {e}")
        return {"prediccion": "ERROR", "score": 1, "nivel_queja": 1, "nivel_retraso": 1, "razonamiento": "Error de procesamiento."}, []