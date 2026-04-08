import csv
import json
import requests
import os
import logging

# Configuración básica de logs para trazabilidad (Best practice en MLOps)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def enviar_alerta_teams(webhook_url, ticket):
    """
    Envía una tarjeta adaptativa (Adaptive Card) a Microsoft Teams.
    """
    # Payload moderno (Adaptive Card) exigido por la nueva arquitectura de Teams
    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": "🚨 ALERTA CRÍTICA ESCALADA POR IA",
                            "weight": "Bolder",
                            "size": "Large",
                            "color": "Attention"
                        },
                        {
                            "type": "TextBlock",
                            "text": f"**Sistema Afectado:** {ticket['sistema_afectado']} | **Score:** {ticket['score_ia']}/5",
                            "isSubtle": True,
                            "wrap": True
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                { "title": "Archivo:", "value": ticket['archivo'] },
                                { "title": "Remitente:", "value": ticket['remitente'] },
                                { "title": "Asunto:", "value": ticket['asunto'] }
                            ]
                        },
                        {
                            "type": "TextBlock",
                            "text": "**Razonamiento del LLM:**",
                            "weight": "Bolder",
                            "wrap": True,
                            "spacing": "Medium"
                        },
                        {
                            "type": "TextBlock",
                            "text": ticket['razonamiento'],
                            "wrap": True,
                            "fontType": "Monospace",
                            "size": "Small",
                            "color": "Warning"
                        }
                    ]
                }
            }
        ]
    }

    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(webhook_url, data=json.dumps(payload), headers=headers)
        response.raise_for_status() # Lanza una excepción si el status HTTP es de error
        logging.info(f"✅ Alerta enviada con éxito para el ticket: {ticket['archivo']}")
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Error al enviar alerta a Teams: {e}")
        if e.response is not None:
            logging.error(f"Detalle del servidor: {e.response.text}")

def procesar_incidencias(archivo_csv, webhook_url):
    """
    Lee el CSV generado por el LLM, filtra y orquesta el envío de alertas.
    """
    logging.info(f"Iniciando procesamiento del archivo: {archivo_csv}")
    
    try:
        with open(archivo_csv, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                score = int(row['score_ia'])
                # Regla de Negocio: Solo alertar si el Score es >= 4
                if score >= 4:
                    logging.warning(f"Incidencia crítica detectada (Score {score}). Escalando a Teams...")
                    enviar_alerta_teams(webhook_url, row)
                else:
                    logging.info(f"Incidencia menor (Score {score}). Ignorando ticket: {row['archivo']}")
    except FileNotFoundError:
        logging.error(f"❌ No se encontró el archivo: {archivo_csv}. Asegúrate de que está en la misma carpeta.")
    except Exception as e:
        logging.error(f"❌ Error inesperado al procesar el archivo: {e}")

if __name__ == "__main__":
    # 1. Cargamos la URL desde la variable de entorno por seguridad (Enterprise Data Privacy)
    WEBHOOK_URL = os.environ.get("TEAMS_WEBHOOK_URL")
    
    # 2. Archivo CSV con los datos que me pasaste antes
    ARCHIVO_DATOS = "../data/processed/evaluacion_scoring_compleja.csv" 
    
    if not WEBHOOK_URL:
        logging.error("❌ No se encontró la variable TEAMS_WEBHOOK_URL. Debes exportarla antes de ejecutar el script.")
    else:
        procesar_incidencias(ARCHIVO_DATOS, WEBHOOK_URL)