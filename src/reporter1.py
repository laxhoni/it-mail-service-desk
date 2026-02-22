import sqlite3
import requests
from datetime import datetime
import logging

def enviar_reporte_diario(webhook_url):
    db_path = "data/incidencias.db"
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Buscamos solo los tickets de HOY con Score 4 o 5
        cursor.execute('''
            SELECT remitente, asunto, score, razonamiento 
            FROM tickets 
            WHERE fecha LIKE ? AND score >= 4
        ''', (f"{fecha_hoy}%",))
        
        tickets_criticos = cursor.fetchall()
        conn.close()

        # Construcción visual de la tarjeta (Adaptive Card Premium)
        cuerpo_tarjeta = [
            {
                "type": "TextBlock",
                "text": "📊 Resumen Diario de Incidencias Críticas",
                "weight": "Bolder",
                "size": "ExtraLarge",
                "color": "Accent",
                "wrap": True
            },
            {
                "type": "TextBlock",
                "text": f"Fecha: {datetime.now().strftime('%d/%m/%Y')}",
                "isSubtle": True,
                "spacing": "None"
            }
        ]

        if not tickets_criticos:
            # Diseño si no hay fuegos (Mensaje en verde)
            cuerpo_tarjeta.append({
                "type": "Container",
                "style": "good",
                "padding": "10px",
                "items": [{
                    "type": "TextBlock",
                    "text": "🎉 ¡Buen trabajo! Hoy no se han registrado incidencias críticas ni quejas formales.",
                    "weight": "Bolder",
                    "wrap": True
                }]
            })
        else:
            # Diseño si hay incidencias (Aviso y lista)
            cuerpo_tarjeta.append({
                "type": "TextBlock",
                "text": f"⚠️ Se han detectado **{len(tickets_criticos)}** incidencias de alta prioridad hoy:",
                "wrap": True,
                "spacing": "Medium"
            })
            
            # Iteramos sobre cada ticket para crear un bloque visual bonito
            for ticket in tickets_criticos:
                remitente, asunto, score, razonamiento = ticket
                color_alerta = "attention" if score == 5 else "warning" # Rojo para 5, Naranja para 4
                
                cuerpo_tarjeta.append({
                    "type": "Container",
                    "style": color_alerta,
                    "spacing": "Medium",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": f"🔥 [Score: {score}/5] {asunto}",
                            "weight": "Bolder",
                            "wrap": True
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "👤 De:", "value": remitente},
                                {"title": "🤖 IA:", "value": razonamiento}
                            ]
                        }
                    ]
                })

        # Ensamblamos el JSON final
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

        # Enviamos a Teams
        requests.post(webhook_url, json=payload)
        logging.info("📈 Reporte diario enviado a Teams con éxito.")

    except Exception as e:
        logging.error(f"❌ Error al generar el reporte diario: {e}")