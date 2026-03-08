import sqlite3
import requests
import json
from datetime import datetime
import logging
import urllib.parse

def obtener_resumen_generativo(tickets_pendientes):
    """Pide a Llama 3.2 que analice el backlog pendiente"""
    if not tickets_pendientes:
        return "No hay incidencias pendientes sobre las que reportar."

    # t[1] es asunto, t[3] es razonamiento (basado en el SELECT de abajo)
    texto_fallos = "\n".join([f"- Asunto: {t[1]} | Problema: {t[3]}" for t in tickets_pendientes])
    
    prompt = f"""
    SISTEMA: Eres el Director de Soporte IT.
    TAREA: Redacta un Resumen Ejecutivo (máximo 3 líneas) sobre los tickets que se han quedado PENDIENTES hoy.
    INSTRUCCIONES:
    1. Identifica patrones si existen.
    2. Tono corporativo y directo.

    BACKLOG PENDIENTE:
    {texto_fallos}
    """
    
    try:
        url = "http://localhost:11434/api/generate"
        r = requests.post(url, json={"model": "llama3.2", "prompt": prompt, "stream": False}, timeout=30)
        return r.json().get('response', 'No se pudo generar el resumen.')
    except Exception as e:
        logging.error(f"Error en motor IA: {e}")
        return "Resumen IA no disponible en este momento."

def enviar_reporte_diario(webhook_url):
    db_path = "data/incidencias.db"
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. ESTADÍSTICAS DE HOY (Ajustado a columna 'score')
        cursor.execute('SELECT COUNT(*) FROM tickets WHERE fecha LIKE ?', (f"{fecha_hoy}%",))
        total_hoy = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM tickets WHERE fecha LIKE ? AND revisado = 0', (f"{fecha_hoy}%",))
        total_pendientes = cursor.fetchone()[0]

        # Aciertos (revisados donde el humano no cambió el score o no puso uno nuevo)
        cursor.execute('''
            SELECT COUNT(*) FROM tickets 
            WHERE fecha LIKE ? AND revisado = 1 
            AND (score_humano IS NULL OR score_humano = score)
        ''', (f"{fecha_hoy}%",))
        total_aciertos = cursor.fetchone()[0]

        # Corregidos (revisados donde el humano cambió el score)
        cursor.execute('''
            SELECT COUNT(*) FROM tickets 
            WHERE fecha LIKE ? AND revisado = 1 
            AND score_humano IS NOT NULL AND score_humano != score
        ''', (f"{fecha_hoy}%",))
        total_corregidos = cursor.fetchone()[0]
        
        # 2. OBTENER BACKLOG PENDIENTE (Usando nombres de columna estándar)
        cursor.execute('''
            SELECT remitente, asunto, score, razonamiento, id_mensaje 
            FROM tickets 
            WHERE revisado = 0
            ORDER BY score DESC
        ''')
        tickets_pendientes = cursor.fetchall()
        conn.close()

        # --- CONSTRUCCIÓN DE LA TARJETA ---
        cuerpo_tarjeta = [
            {
                "type": "TextBlock",
                "text": "📊 Reporte de Rendimiento y Backlog IT",
                "weight": "Bolder", "size": "ExtraLarge", "color": "Accent"
            },
            {
                "type": "FactSet",
                "facts": [
                    {"title": "📥 Total Hoy:", "value": str(total_hoy)},
                    {"title": "✅ IA Correcta:", "value": str(total_aciertos)},
                    {"title": "🛠️ IA Corregida:", "value": str(total_corregidos)},
                    {"title": "⏳ PENDIENTES:", "value": f"**{total_pendientes}**"}
                ]
            }
        ]

        if total_pendientes > 0:
            resumen_ia = obtener_resumen_generativo(tickets_pendientes)
            cuerpo_tarjeta.append({
                "type": "Container", "style": "emphasis", "padding": "10px",
                "items": [
                    {"type": "TextBlock", "text": "🧠 Análisis de Pendientes:", "weight": "Bolder"},
                    {"type": "TextBlock", "text": resumen_ia, "wrap": True, "fontType": "Monospace", "size": "Small"}
                ]
            })

            for t in tickets_pendientes:
                remitente, asunto, score, razonamiento, id_mensaje = t
                id_encoded = urllib.parse.quote(id_mensaje) if id_mensaje else ""
                url_outlook = f"https://outlook.live.com/mail/0/inbox/id/{id_encoded}"

                cuerpo_tarjeta.append({
                    "type": "Container", 
                    "style": "attention" if score >= 4 else "default",
                    "items": [
                        {"type": "TextBlock", "text": f"🔥 [Score {score}] {asunto}", "weight": "Bolder"},
                        {"type": "TextBlock", "text": f"👤 {remitente}", "isSubtle": True, "size": "Small"},
                        {
                            "type": "ActionSet",
                            "actions": [{"type": "Action.OpenUrl", "title": "📧 Ver Correo", "url": url_outlook}]
                        }
                    ]
                })
        else:
            cuerpo_tarjeta.append({"type": "TextBlock", "text": "✅ No hay tareas pendientes para mañana.", "color": "Good"})

        # --- ENVÍO ---
        payload = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {"type": "AdaptiveCard", "version": "1.4", "body": cuerpo_tarjeta}
            }]
        }
        
        response = requests.post(webhook_url, json=payload)
        if response.status_code == 200:
            logging.info("📈 Reporte enviado correctamente a Teams.")
        else:
            logging.error(f"❌ Error en Webhook: {response.status_code} - {response.text}")

    except Exception as e:
        logging.error(f"❌ Error crítico en reporte: {e}")