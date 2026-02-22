import requests
import json

def enviar_alerta_teams(webhook_url, datos, res_ia, archivo):
    # Cogemos el enlace, o ponemos un texto vacío si no existe
    link = datos.get('link_correo', '')

    cuerpo_tarjeta = [
        {"type": "TextBlock", "text": "🚨 ALERTA CRÍTICA ESCALADA", "weight": "Bolder", "size": "Large", "color": "Attention"},
        {"type": "TextBlock", "text": f"Prioridad detectada: Nivel {res_ia['score']}/5", "isSubtle": True},
        {"type": "FactSet", "facts": [
            {"title": "👤 De:", "value": datos.get('remitente')},
            {"title": "🎯 Para:", "value": datos.get('destinatario')},
            {"title": "📌 Asunto:", "value": datos.get('asunto')},
            {"title": "⚠️ Importancia:", "value": datos.get('importancia')}
        ]},
        {"type": "TextBlock", "text": "**Análisis IA:**", "weight": "Bolder", "spacing": "Medium"},
        {"type": "TextBlock", "text": res_ia['razonamiento'], "wrap": True, "fontType": "Monospace", "color": "Warning"}
    ]

    # Si tenemos el link del correo, añadimos el botón al final de la tarjeta
    if link:
        cuerpo_tarjeta.append({
            "type": "ActionSet",
            "actions": [
                {
                    "type": "Action.OpenUrl",
                    "title": "📧 Responder en Outlook",
                    "url": link
                }
            ]
        })

    payload = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "type": "AdaptiveCard", 
                "version": "1.4",
                "body": cuerpo_tarjeta
            }
        }]
    }
    
    requests.post(webhook_url, json=payload)