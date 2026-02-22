import sqlite3
import requests
import json
from datetime import datetime
import logging

def obtener_resumen_generativo(tickets_criticos):
    """Pide a Llama 3.2 que lea los fallos y redacte una conclusión directiva"""
    if not tickets_criticos:
        return "No hay incidencias críticas sobre las que reportar."

    # Preparamos un texto con los asuntos y la IA razonamientos
    # (t[1] es asunto, t[3] es razonamiento)
    texto_fallos = "\n".join([f"- Asunto: {t[1]} | Problema: {t[3]}" for t in tickets_criticos])
    
    prompt = f"""
    SISTEMA: Eres el Director de Soporte IT (CIO).
    TAREA: Redacta un Resumen Ejecutivo muy breve (máximo 3 líneas) sobre las incidencias críticas de hoy.
    INSTRUCCIONES:
    1. Menciona si hay algún patrón (ej: "Múltiples fallos en la red Wi-Fi").
    2. Sugiere una acción preventiva rápida.
    3. Tono profesional y corporativo.

    INCIDENCIAS DE HOY:
    {texto_fallos}
    """
    
    try:
        url = "http://localhost:11434/api/generate"
        r = requests.post(url, json={"model": "llama3.2", "prompt": prompt, "stream": False}, timeout=30)
        return r.json().get('response', 'No se pudo generar el resumen.')
    except Exception as e:
        logging.error(f"Error generando resumen IA: {e}")
        return "Error de conexión con el motor IA de resúmenes."

def enviar_reporte_diario(webhook_url):
    db_path = "data/incidencias.db"
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. Obtenemos TODOS los tickets de hoy (para la estadística general)
        cursor.execute('SELECT score FROM tickets WHERE fecha LIKE ?', (f"{fecha_hoy}%",))
        todos_hoy = cursor.fetchall()
        total_tickets = len(todos_hoy)
        
        # 2. Obtenemos SOLO los críticos (Score 4 y 5), AHORA INCLUYENDO link_correo
        cursor.execute('''
            SELECT remitente, asunto, score, razonamiento, link_correo 
            FROM tickets 
            WHERE fecha LIKE ? AND score >= 4
        ''', (f"{fecha_hoy}%",))
        tickets_criticos = cursor.fetchall()
        total_criticos = len(tickets_criticos)
        
        conn.close()

        # Calculamos porcentaje
        porcentaje_criticos = round((total_criticos / total_tickets * 100), 1) if total_tickets > 0 else 0

        # --- CONSTRUCCIÓN DE LA TARJETA TEAMS ---
        cuerpo_tarjeta = [
            {
                "type": "TextBlock",
                "text": "📊 Reporte Ejecutivo de Soporte IT",
                "weight": "Bolder",
                "size": "ExtraLarge",
                "color": "Accent",
                "wrap": True
            },
            {
                "type": "FactSet",
                "facts": [
                    {"title": "📅 Fecha:", "value": datetime.now().strftime('%d/%m/%Y')},
                    {"title": "📥 Total Tickets Hoy:", "value": str(total_tickets)},
                    {"title": "🔥 Tickets Críticos:", "value": f"{total_criticos} ({porcentaje_criticos}%)"}
                ]
            }
        ]

        if total_criticos == 0:
            cuerpo_tarjeta.append({
                "type": "Container", "style": "good", "padding": "10px",
                "items": [{"type": "TextBlock", "text": "🎉 ¡Excelente jornada! Cero incidencias críticas registradas hoy.", "weight": "Bolder", "wrap": True}]
            })
        else:
            # Pedimos el resumen ejecutivo a la IA
            resumen_ia = obtener_resumen_generativo(tickets_criticos)
            
            # Bloque del Resumen de la IA
            cuerpo_tarjeta.append({
                "type": "Container", "style": "emphasis", "padding": "10px", "spacing": "Medium",
                "items": [
                    {"type": "TextBlock", "text": "🧠 Análisis Ejecutivo (Llama 3.2):", "weight": "Bolder"},
                    {"type": "TextBlock", "text": resumen_ia, "wrap": True, "isSubtle": True, "fontType": "Monospace"}
                ]
            })
            
            cuerpo_tarjeta.append({"type": "TextBlock", "text": "Detalle de Incidencias Críticas:", "weight": "Bolder", "spacing": "Medium"})
            
            # Lista de tickets críticos
            for ticket in tickets_criticos:
                # Ahora desempaquetamos también el link_correo (5 variables)
                remitente, asunto, score, razonamiento, link_correo = ticket
                color = "attention" if score == 5 else "warning"
                
                # Elementos básicos de la incidencia
                ticket_items = [
                    {"type": "TextBlock", "text": f"🔥 [Score: {score}/5] {asunto}", "weight": "Bolder", "wrap": True},
                    {"type": "TextBlock", "text": f"👤 {remitente} | 🤖 {razonamiento}", "wrap": True, "size": "Small"}
                ]
                
                # Si existe el link, añadimos el botón a este bloque
                if link_correo:
                    ticket_items.append({
                        "type": "ActionSet",
                        "actions": [
                            {
                                "type": "Action.OpenUrl",
                                "title": "📧 Abrir en Outlook",
                                "url": link_correo
                            }
                        ]
                    })
                
                # Añadimos el bloque completo a la tarjeta
                cuerpo_tarjeta.append({
                    "type": "Container", "style": color, "spacing": "Small", "padding": "10px",
                    "items": ticket_items
                })

        payload = {
            "type": "message",
            "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": {"type": "AdaptiveCard", "version": "1.4", "body": cuerpo_tarjeta}}]
        }

        requests.post(webhook_url, json=payload)
        logging.info("📈 Reporte diario avanzado enviado a Teams con éxito.")

    except Exception as e:
        logging.error(f"❌ Error al generar el reporte diario: {e}")