import os
import time
import json
import shutil
import logging
from dotenv import load_dotenv

from src.setup_database import inicializar_db, guardar_ticket
from src.prompt_complaints import analizar_con_ia

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [WORKER] - %(levelname)s - %(message)s')

def ejecutar_agente():
    load_dotenv()
    WEBHOOK = os.getenv("WEBHOOK_TEAMS")
    INPUT_DIR = os.getenv("CARPETA_DOCS", "docs")
    
    # 1. Definir y crear la carpeta de salida para Power Automate
    ALERTS_OUT_DIR = os.path.join(INPUT_DIR, "Alertas_Teams")
    
    if not os.path.exists(ALERTS_OUT_DIR): os.makedirs(ALERTS_OUT_DIR)
    
    inicializar_db()
    
    logging.info(f"🚀 WORKER INICIADO - Vigilando {INPUT_DIR}")

    while True:
        archivos = [f for f in os.listdir(INPUT_DIR) if f.endswith('.json') and os.path.isfile(os.path.join(INPUT_DIR, f))]
        
        for nombre_archivo in archivos:
            ruta_completa = os.path.join(INPUT_DIR, nombre_archivo)
            try:
                with open(ruta_completa, 'r', encoding='utf-8') as f:
                    datos = json.loads(f.read(), strict=False)
                
                # 1. Analizar con IA
                resultado, vector_correo = analizar_con_ia(datos.get('asunto'), datos.get('cuerpo'))
                
                # 2. Persistencia en SQLite
                guardar_ticket(datos, resultado, nombre_archivo, vector_correo)
                
                # 3. Filtro de Escalación
                if resultado.get('score', 0) >= 4:
                    logging.warning(f"🔥 Score {resultado['score']} detectado. Generando alerta para Teams...")
                    
                    # --- NUEVO: PAYLOAD CON DOBLE VALIDACIÓN PARA LA TARJETA ---
                    payload_teams = {
                        "id_mensaje": datos.get('id_mensaje', nombre_archivo),
                        "asunto": datos.get('asunto', 'Sin Asunto'),
                        "remitente": datos.get('remitente', 'Desconocido'),
                        "score_ia": resultado.get('score'),
                        "nivel_queja_ia": resultado.get('nivel_queja', 1),     # Nuevo
                        "nivel_retraso_ia": resultado.get('nivel_retraso', 1), # Nuevo
                        "razonamiento_ia": resultado.get('razonamiento', 'Sin detalles')
                    }
                    
                    ruta_alerta_json = os.path.join(ALERTS_OUT_DIR, f"alerta_{nombre_archivo}")
                    with open(ruta_alerta_json, 'w', encoding='utf-8') as f_out:
                        json.dump(payload_teams, f_out, indent=4, ensure_ascii=False)
                    
                    logging.info(f"📂 Archivo de alerta creado en: {ALERTS_OUT_DIR}")
                    
                else:
                    logging.info(f"✅ Ticket filtrado (Score {resultado.get('score', 1)}).")

                # 4. Eliminar el archivo original para evitar reprocesos (ya está guardado en DB)
                os.remove(ruta_completa) 
                logging.info(f"🗑️ Archivo original {nombre_archivo} eliminado de 'docs' (Guardado en DB).")                
            except Exception as e:
                logging.error(f"❌ Error procesando {nombre_archivo}: {e}")
        
        time.sleep(5)

if __name__ == "__main__":
    ejecutar_agente()