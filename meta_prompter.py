import requests
import json
import logging
import os
import shutil

# Configuración básica de logs si se ejecuta de forma independiente
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [META-PROMPTER] - %(levelname)s - %(message)s')

def generar_configuracion_dinamica(descripcion_empresa):
    """
    Usa Llama 3.2 para traducir el lenguaje natural del cliente en 
    pesos matemáticos y un System Prompt estricto.
    """
    url = "http://localhost:11434/api/generate"
    
    meta_prompt = f"""
    SISTEMA: Eres un Arquitecto de IA (Prompt Engineer) especializado en Service Desk IT.
    
    TAREA: El Director de IT te ha descrito las necesidades de su negocio.
    Genera el archivo de configuración ideal para el motor de triaje.

    DESCRIPCIÓN DEL DIRECTOR IT:
    "{descripcion_empresa}"

    DEBES DETERMINAR:
    1. 'peso_queja' (0.1 a 0.9): Si el usuario enfatiza la frustración de clientes, VIPs, o daño de imagen, dale más peso (ej: 0.7 o 0.8).
    2. 'peso_retraso' (0.1 a 0.9): Si enfatiza SLAs estrictos, caídas de producción o tiempos límite, dale más peso (ej: 0.7 o 0.8).
       (⚠️ REGLA MATEMÁTICA: peso_queja + peso_retraso DEBEN sumar exactamente 1.0).
    3. 'contexto': Redacta un System Prompt robusto y directo (máximo 4 líneas) que instruya al motor de clasificación sobre qué debe priorizar y qué ignorar basándote estrictamente en lo que pidió el Director.

    RESPONDE SOLO EN JSON:
    {{
      "peso_queja": <float>,
      "peso_retraso": <float>,
      "contexto": "<System prompt generado>"
    }}
    """
    
    try:
        logging.info("⚙️ Solicitando rediseño de arquitectura a Llama 3.2...")
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
            logging.warning("⚠️ Los pesos generados no suman 1.0. Forzando normalización al 50/50.")
            nueva_config["peso_queja"] = 0.5
            nueva_config["peso_retraso"] = 0.5

        # Guardar en el archivo final
        ruta_directorio = os.path.join("data", "config")
        os.makedirs(ruta_directorio, exist_ok=True)
        ruta_archivo = os.path.join(ruta_directorio, "config.json")
        
        with open(ruta_archivo, 'w', encoding='utf-8') as f:
            json.dump(nueva_config, f, indent=4, ensure_ascii=False)
            
        logging.info(f"✅ Auto-configuración completada. Nuevo contexto inyectado en {ruta_archivo}")
        return True

    except Exception as e:
        logging.error(f"❌ Error en Meta-Prompting: {e}")
        return False

def procesar_cola_onboarding():
    """
    Busca si hay un nuevo comando de configuración desde Teams (Power Automate).
    """
    ruta_input = os.path.join("data", "config", "initial_config.txt")
    
    if os.path.exists(ruta_input):
        logging.info("📥 Nuevo input de configuración detectado desde Teams.")
        
        with open(ruta_input, 'r', encoding='utf-8') as f:
            descripcion = f.read().strip()
            
        if descripcion:
            exito = generar_configuracion_dinamica(descripcion)
            
            if exito:
                # Borramos el archivo de input para no procesarlo en bucle
                os.remove(ruta_input)
                logging.info("🗑️ Archivo de input procesado y eliminado.")
        else:
            logging.warning("El archivo de input estaba vacío. Eliminando...")
            os.remove(ruta_input)
    else:
        pass # No hay configuraciones pendientes

if __name__ == "__main__":
    # Si ejecutas python src/meta_prompter.py a mano, revisará si hay inputs pendientes.
    procesar_cola_onboarding()