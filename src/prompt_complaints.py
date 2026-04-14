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
                logging.info(f"[*] Memoria de Negocio cargada: Peso Queja={datos.get('peso_queja')} | Peso Retraso={datos.get('peso_retraso')}")
                return {
                    "peso_queja": float(datos.get("peso_queja", 0.5)),
                    "peso_retraso": float(datos.get("peso_retraso", 0.5)),
                    "contexto": str(datos.get("contexto", config_default["contexto"]))
                }
        else:
            logging.warning(f"[*] Archivo no encontrado en {ruta_config}. Usando fallback por defecto.")
    except Exception as e:
        logging.error(f"[*] Error crítico leyendo config.json: {e}. Usando fallback.")
    
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
                    origen = "[*] EXPERTO HUMANO (VALIDADO - CUMPLIR OBLIGATORIAMENTE)"
                else:
                    queja_final = ej.get('nivel_queja', 1)
                    retraso_final = ej.get('nivel_retraso', 1)
                    score_final = ej.get('score', 1)
                    razonamiento_final = ej.get('razonamiento')
                    origen = "[*] PREDICCIÓN IA PREVIA"

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
        logging.info("[*] RAG: No se han encontrado casos similares previos (o están por debajo del 0.65).")
    else:
        # Esto te dirá cuántos casos le está enviando realmente a la IA
        num_casos = bloque_ejemplos.count("[CASO HISTÓRICO")
        logging.info(f"[*] RAG: Memoria activada. Inyectando {num_casos} casos similares al prompt.")
    # -----------------------------------------------------
    
    # --- 3. INYECCIÓN DEL META-PROMPT MULTIDIMENSIONAL ---
    prompt = f"""
    <rol>
    Eres un Analista Experto de Nivel 3 en el Service Desk IT de una corporación multinacional. Tu tarea es analizar correos electrónicos entrantes y clasificarlos con precisión matemática basándote ESTRICTAMENTE en dos rúbricas predefinidas.
    </rol>

    <instrucciones_contexto>
    {config['contexto']}
    </instrucciones_contexto>

    <rubricas_evaluacion>
    Evalúa el ticket en las siguientes dos dimensiones. Asigna un valor numérico entero (1 al 10). NO inventes niveles intermedios ni te desvíes de estas definiciones. Si el correo es SPAM ininteligible o vacío, asigna 1 a ambas dimensiones.

    DIMENSIÓN 1: NIVEL DE QUEJA / IMPACTO EMOCIONAL Y OPERATIVO
    1 - Tono puramente positivo: Agradecimiento por un ticket resuelto o confirmación de éxito. (Nota: ignorar "gracias de antemano" si hay una queja).
    2 - Tono neutro/informativo: Consulta general, duda de uso, sin fricción alguna.
    3 - Petición estándar: Solicitud de accesos, software o hardware para el futuro. Tono profesional y calmado.
    4 - Fricción leve: Falla menor, error recurrente pero salvable (workaround disponible). El usuario informa sin enfado explícito.
    5 - Frustración evidente: Lenguaje que denota molestia ("es la tercera vez", "es muy molesto"). Bloqueo de una tarea individual.
    6 - Exigencia de solución: Tono asertivo o queja formal leve. Afectación de un grupo pequeño o bloqueo total de un usuario base.
    7 - Tono cortante/Imperativo: Fuerte malestar. Usuario VIP bloqueado o afectación severa que paraliza un departamento entero.
    8 - Lenguaje agresivo: Uso de MAYÚSCULAS para gritar, múltiples exclamaciones (!!!), quejas directas sobre la incompetencia de IT.
    9 - Pánico o Amenaza de Negocio: Amenazas de escalar a RRHH/Dirección, o mención explícita de pérdida de dinero/ventas (ej. "estamos perdiendo miles de euros").
    10 - Catástrofe: Insultos directos graves, histeria total, o confirmación de caída de sistemas Core (producción parada a nivel global, ciberataque).

    DIMENSIÓN 2: NIVEL DE RETRASO / SLA (URGENCIA TEMPORAL)
    1 - Planificación futura: Semanas o meses vista. Ninguna prisa.
    2 - Tarea sin plazo: "Cuando podáis", "No corre prisa". Baja prioridad.
    3 - Tiempo de resolución estándar (SLA normal): Primer aviso de una incidencia común sin indicar urgencia temporal.
    4 - Urgencia moderada: Petición para resolver "hoy" o "lo antes posible". Ligera presión.
    5 - Retraso con impacto: Seguimiento de un ticket anterior no resuelto. El retraso empieza a afectar la planificación del usuario.
    6 - Reiteración urgente: 2º o 3º aviso consecutivo ("lo necesito para esta tarde sin falta").
    7 - Bloqueo inminente: El usuario no puede avanzar en su trabajo principal y está parado esperando a IT.
    8 - Atención inmediata ("minutos"): Reuniones ejecutivas bloqueadas, directivos esperando en sala, fallo crítico reportado en tiempo real.
    9 - Paralización de negocio: Caída que afecta a clientes externos en vivo o detiene completamente un departamento operativo.
    10 - Emergencia vital/absoluta: Servidores caídos, riesgo físico (incendio, aire acondicionado de CPD roto), ransomware masivo. Intervención en "segundos".
    </rubricas_evaluacion>

    <memoria_rag>
    Utiliza el siguiente historial de casos (Ground Truth) para calibrar tu respuesta y evitar errores pasados:
    {bloque_ejemplos if bloque_ejemplos else "Sin memoria relevante para este caso. Aplica las rúbricas de forma independiente."}
    </memoria_rag>

    <correo_a_evaluar>
    Asunto: {asunto}
    Cuerpo: {cuerpo}
    </correo_a_evaluar>

    <formato_salida_obligatorio>
    Genera ÚNICAMENTE un objeto JSON válido. NO incluyas texto introductorio (ej. "Aquí tienes la respuesta:") ni etiquetas markdown (```json). Empieza directamente con la llave '{{'.
    
    ESTRUCTURA EXACTA:
    {{
      "razonamiento": "<Analiza paso a paso: 1) Palabras clave del texto. 2) Justificación de la nota de Queja según la rúbrica. 3) Justificación de la nota de Retraso según la rúbrica.>",
      "nivel_queja": <int>,
      "nivel_retraso": <int>
    }}
    </formato_salida_obligatorio>
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
        logging.error(f"[*] Error en inferencia IA: {e}")
        return {"prediccion": "ERROR", "score": 1, "nivel_queja": 1, "nivel_retraso": 1, "razonamiento": "Error de procesamiento."}, []