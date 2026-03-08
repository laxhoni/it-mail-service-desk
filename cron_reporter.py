import os
import logging
from dotenv import load_dotenv

# Importamos la función de reporte que actualizamos
from src.reporter import enviar_reporte_diario

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [CRON JOB] - %(levelname)s - %(message)s')

def ejecutar_reporte_diario():
    logging.info("⏱️ Iniciando tarea programada: Reporte de Rendimiento y Backlog.")
    
    load_dotenv()
    WEBHOOK = os.getenv("WEBHOOK_TEAMS")
    
    if not WEBHOOK:
        logging.error("❌ ERROR CRÍTICO: No se encontró el WEBHOOK_TEAMS en el .env")
        return

    try:
        logging.info("📊 Recopilando métricas de IA y tickets pendientes...")
        
        # Llama a la función que conecta a la DB y construye la tarjeta de Teams
        enviar_reporte_diario(WEBHOOK)
        
        logging.info("✅ Reporte de backlog enviado a Teams con éxito. Finalizando proceso.")
    except Exception as e:
        logging.error(f"❌ Fallo al enviar el reporte diario: {e}")

if __name__ == "__main__":
    ejecutar_reporte_diario()