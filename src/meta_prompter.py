import requests
import json
import logging
import os

# Configuración básica de logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [META-PROMPTER] - %(levelname)s - %(message)s')

def generar_configuracion_dinamica(descripcion_empresa):
    """
    Usa Llama 3.2 para traducir el lenguaje natural del cliente en 
    pesos matemáticos y un System Prompt estricto, adaptable a CUALQUIER sector.
    """
    url = "http://localhost:11434/api/generate"
    
    meta_prompt = f"""
    SISTEMA: Eres un Arquitecto de IA Experto en Triaje Operativo y Atención al Cliente.
    
    TAREA: Un directivo te ha descrito las necesidades y el modelo de negocio de su empresa.
    Tu objetivo es configurar el "Cerebro" de un motor de clasificación automático de tickets/correos para adaptarlo perfectamente a su sector.

    DESCRIPCIÓN DEL NEGOCIO Y PRIORIDADES:
    "{descripcion_empresa}"

    DEBES EXTRAER Y CALCULAR 3 PARÁMETROS:

    1. 'peso_queja' (Decimal entre 0.1 y 0.9): 
       Representa la sensibilidad al IMPACTO HUMANO Y REPUTACIONAL. 
       - Sube el peso (0.6 - 0.9) si el negocio prioriza: quejas de clientes, VIPs, imagen pública, enfados, reseñas negativas o impacto social.
       - Bájalo si los procesos mecánicos son más importantes que las emociones.

    2. 'peso_retraso' (Decimal entre 0.1 y 0.9): 
       Representa la sensibilidad al IMPACTO TÉCNICO Y OPERATIVO.
       - Sube el peso (0.6 - 0.9) si el negocio prioriza: tiempos límite (SLAs), producción detenida, logística, pérdidas financieras directas por tiempo, o fallos de maquinaria/software.
       
       [*] REGLA MATEMÁTICA ESTRICTA: 'peso_queja' + 'peso_retraso' DEBEN sumar exactamente 1.0.

    3. 'contexto': 
       Redacta las instrucciones (System Prompt) que usará el motor de IA para leer los correos cada día. 
       - Debe indicar claramente de qué sector es la empresa.
       - Debe decirle a la IA qué tipo de problemas son críticos para ellos y cuáles son triviales.
       - Tono directo e imperativo. Máximo 4 líneas.

    RESPONDE ÚNICAMENTE CON UN JSON VÁLIDO CON ESTE FORMATO EXACTO (sin texto adicional ni explicaciones):
    {{
      "peso_queja": <float>,
      "peso_retraso": <float>,
      "contexto": "<Instrucciones generadas>"
    }}
    """
    
    try:
        logging.info("[*] Solicitando arquitectura de triaje adaptativa a Llama 3.2...")
        r = requests.post(url, json={
            "model": "llama3.2", 
            "prompt": meta_prompt, 
            "format": "json", 
            "stream": False
        }, timeout=60)
        
        nueva_config = json.loads(r.json().get('response', '{}'))
        
        # Validación de seguridad: Asegurar que los pesos sumen 1.0
        pq = float(nueva_config.get("peso_queja", 0.5))
        pr = float(nueva_config.get("peso_retraso", 0.5))
        
        if abs((pq + pr) - 1.0) > 0.01:
            logging.warning("[*] Los pesos generados no suman 1.0. Forzando normalización proporcional...")
            total = pq + pr
            # Normalización segura en caso de que la IA se equivoque en la suma
            nueva_config["peso_queja"] = round(pq / total, 2)
            nueva_config["peso_retraso"] = round(pr / total, 2)

        # Guardar en el archivo final
        ruta_directorio = os.path.join("data", "config")
        os.makedirs(ruta_directorio, exist_ok=True)
        ruta_archivo = os.path.join(ruta_directorio, "config.json")
        
        with open(ruta_archivo, 'w', encoding='utf-8') as f:
            json.dump(nueva_config, f, indent=4, ensure_ascii=False)
            
        logging.info(f"[*] Auto-configuración completada. Nuevo contexto inyectado en {ruta_archivo}")
        return True

    except Exception as e:
        logging.error(f"[*] Error en Meta-Prompting: {e}")
        return False