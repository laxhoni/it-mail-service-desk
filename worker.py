import os
import time
import json
import shutil
import logging
from dotenv import load_dotenv

# Tus importaciones exactas
from src.setup_database import inicializar_db, guardar_ticket
from src.prompt_complaints import analizar_con_ia
from src.teams_bot import enviar_alerta_teams

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [WORKER] - %(levelname)s - %(message)s')

def ejecutar_agente():
    load_dotenv()
    WEBHOOK = os.getenv("WEBHOOK_TEAMS")
    INPUT_DIR = os.getenv("CARPETA_DOCS", "docs")
    PROC_DIR = "data/processed"
    
    if not os.path.exists(PROC_DIR): os.makedirs(PROC_DIR)
    inicializar_db()
    
    logging.info("🚀 WORKER INICIADO - Escaneando correos 24/7...")

    while True:
        archivos = [f for f in os.listdir(INPUT_DIR) if f.endswith('.json')]
        for nombre_archivo in archivos:
            ruta_completa = os.path.join(INPUT_DIR, nombre_archivo)
            try:
                with open(ruta_completa, 'r', encoding='utf-8') as f:
                    datos = json.loads(f.read(), strict=False)
                
                # 1. Analizar con Llama 3.2
                resultado = analizar_con_ia(datos.get('asunto'), datos.get('cuerpo'))
                
                # 2. Persistencia en SQLite
                guardar_ticket(datos, resultado, nombre_archivo)
                
                # 3. Filtro de Escalación (Solo Scores 4 y 5 van a Teams)
                # Usamos .get() por seguridad extra
                if resultado.get('score', 0) >= 4:
                    logging.warning(f"🔥 Score {resultado['score']} detectado. Notificando...")
                    enviar_alerta_teams(WEBHOOK, datos, resultado, nombre_archivo)
                else:
                    logging.info(f"✅ Ticket filtrado (Score {resultado.get('score', 'N/A')}). Registrado en DB.")

                # 4. Archivar
                shutil.move(ruta_completa, os.path.join(PROC_DIR, nombre_archivo))
                
            except Exception as e:
                logging.error(f"❌ Error procesando {nombre_archivo}: {e}")
        
        time.sleep(5)

if __name__ == "__main__":
    ejecutar_agente()