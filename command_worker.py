import os
import time
import logging
from dotenv import load_dotenv

# Importamos las funciones clave
from src.meta_prompter import generar_configuracion_dinamica
from src.reporter import enviar_reporte_diario

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [COMMANDS] - %(message)s')

def ejecutar_command_worker():
    load_dotenv()
    
    # 1. Definimos las rutas exactas que Power Automate va a usar
    RUTA_SETUP = os.path.join("data", "config", "initial_config.txt")
    DIR_REPORT = os.path.join("data", "report")
    RUTA_REPORT = os.path.join(DIR_REPORT, "report_request.txt")
    
    # Aseguramos que la carpeta de reportes exista
    if not os.path.exists(DIR_REPORT): os.makedirs(DIR_REPORT)
    
    logging.info("COMMAND WORKER INICIADO - Vigilando comandos ChatOps...")
    logging.info(f" ∟ Vigilando Setup en: {RUTA_SETUP}")
    logging.info(f" ∟ Vigilando Report en: {RUTA_REPORT}")

    while True:
        # --- CASO 1: COMANDO !SETUP ---
        if os.path.exists(RUTA_SETUP):
            logging.info("[*] Comando !setup detectado.")
            try:
                with open(RUTA_SETUP, 'r', encoding='utf-8') as f:
                    descripcion = f.read().strip()
                
                if descripcion:
                    generar_configuracion_dinamica(descripcion)
                
                os.remove(RUTA_SETUP)
                logging.info("[*] Archivo de setup procesado y eliminado.")
            except Exception as e:
                logging.error(f"[*] Error en setup: {e}")
                if os.path.exists(RUTA_SETUP): os.remove(RUTA_SETUP) # Borrar si falla para no buclear

        # --- CASO 2: COMANDO !REPORT ---
        if os.path.exists(RUTA_REPORT):
            logging.info("[*] Comando !report detectado.")
            try:
                webhook = os.getenv("WEBHOOK_TEAMS")
                enviar_reporte_diario(webhook)
                
                os.remove(RUTA_REPORT)
                logging.info("[*] Petición de reporte procesada y eliminada.")
            except Exception as e:
                logging.error(f"[*] Error en reporte: {e}")
                if os.path.exists(RUTA_REPORT): os.remove(RUTA_REPORT)

        time.sleep(3) # Pausa de 3 segundos para no saturar la CPU

if __name__ == "__main__":
    ejecutar_command_worker()