import requests
import json

def enviar_alerta_teams(webhook_url, datos, res_ia, archivo):
    card = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "type": "AdaptiveCard", "version": "1.4",
                "body": [
                    {"type": "TextBlock", "text": "🚨 ALERTA ESCALADA POR IA", "weight": "Bolder", "size": "Large", "color": "Attention"},
                    {"type": "FactSet", "facts": [
                        {"title": "De:", "value": datos['remitente']},
                        {"title": "Asunto:", "value": datos['asunto']},
                        {"title": "Score:", "value": str(res_ia['score'])}
                    ]},
                    {"type": "TextBlock", "text": res_ia['razonamiento'], "wrap": True, "fontType": "Monospace", "color": "Warning"}
                ]
            }
        }]
    }
    requests.post(webhook_url, json=card)