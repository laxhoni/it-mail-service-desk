import sqlite3
import requests
import json
from datetime import datetime
import logging
import urllib.parse
import os

# Configuración de logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [REPORTER] - %(levelname)s - %(message)s')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(ROOT_DIR, "data", "incidencias.db")

OLLAMA_URL = "http://localhost:11434/api/generate"

def obtener_resumen_generativo(tickets_pendientes, fecha_texto):
    """Pide a Llama 3.2 que analice el backlog pendiente y detecte patrones."""
    if not tickets_pendientes:
        return "No hay incidencias críticas pendientes."

    # Preparamos los datos para la IA (limitamos a los 10 peores para no saturar el prompt)
    texto_fallos = "\n".join([f"- Prioridad {t[2]}/5: {t[1]} (Por: {t[0]})" for t in tickets_pendientes[:10]])
    
    prompt = f"""
    SISTEMA: Eres el Director de Operaciones (COO) analizando un reporte de incidencias.
    
    TAREA: Redacta un Resumen Ejecutivo (máximo 4 líneas) sobre los tickets que han quedado PENDIENTES en el periodo: {fecha_texto}.
    
    INSTRUCCIONES:
    1. Identifica el cuello de botella principal o el patrón de los problemas (ej. problemas de hardware, quejas de clientes específicos, etc.).
    2. Usa un tono corporativo, analítico y directo.
    3. Si hay tickets con prioridad 4 o 5, destácalos como riesgo operativo.

    BACKLOG PENDIENTE (Top 10):
    {texto_fallos}
    """
    
    try:
        logging.info("🧠 Solicitando análisis de backlog a Llama 3.2...")
        r = requests.post(OLLAMA_URL, json={"model": "llama3.2", "prompt": prompt, "stream": False}, timeout=45)
        return r.json().get('response', 'Análisis no disponible temporalmente.')
    except Exception as e:
        logging.error(f"❌ Error conectando con motor IA local: {e}")
        return "El motor de análisis generativo no está disponible."

def enviar_reporte_diario(webhook_url, fecha_desde=None, fecha_hasta=None):
    """Genera y envía un informe analítico completo a Teams basado en un rango de fechas."""
    
    # 1. GESTIÓN DE FECHAS
    hoy = datetime.now().strftime("%Y-%m-%d")
    f_desde = fecha_desde if fecha_desde else hoy
    f_hasta = fecha_hasta if fecha_hasta else hoy
    
    # RED DE SEGURIDAD 
    # Si el usuario pone la fecha final antes que la inicial, las intercambiamos
    if f_desde > f_hasta:
        f_desde, f_hasta = f_hasta, f_desde
    
    # Rango temporal completo para la consulta SQL
    inicio_sql = f"{f_desde} 00:00:00"
    fin_sql = f"{f_hasta} 23:59:59"
    
    texto_fechas = f"{f_desde}" if f_desde == f_hasta else f"{f_desde} al {f_hasta}"
    logging.info(f"📊 Generando reporte para el periodo: {texto_fechas}")

    try:
        # 2. EXTRACCIÓN DE MÉTRICAS (Uso de 'with' asegura el cierre de la DB)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Métricas Generales
            cursor.execute('SELECT COUNT(*), AVG(score) FROM tickets WHERE fecha BETWEEN ? AND ?', (inicio_sql, fin_sql))
            res_general = cursor.fetchone()
            total_tickets = res_general[0] or 0
            score_promedio = round(res_general[1] or 0, 1)
            
            # Estado del Workflow
            cursor.execute('SELECT COUNT(*) FROM tickets WHERE fecha BETWEEN ? AND ? AND revisado = 0', (inicio_sql, fin_sql))
            total_pendientes = cursor.fetchone()[0]
            
            # --- RENDIMIENTO IA (Con Tolerancia de ±1 punto) ---
            cursor.execute('''
                SELECT score, score_humano 
                FROM tickets 
                WHERE fecha BETWEEN ? AND ? AND revisado = 1
            ''', (inicio_sql, fin_sql))
            tickets_revisados = cursor.fetchall()

            exactos = 0
            leves = 0
            criticos = 0

            for t in tickets_revisados:
                score_ia = t[0]
                score_h = t[1]

                # Si el humano no puso nota, asumimos que validó la de la IA
                if score_h is None:
                    exactos += 1
                else:
                    diferencia = abs(score_ia - score_h)
                    if diferencia == 0:
                        exactos += 1
                    elif diferencia == 1:
                        leves += 1
                    else:
                        criticos += 1

            total_revisados = len(tickets_revisados)
            precision_ia = 0
            if total_revisados > 0:
                # La precisión operativa suma los exactos y los leves
                precision_ia = round(((exactos + leves) / total_revisados) * 100, 1)

            # Analítica Avanzada: Top Remitente (El que más tickets genera)
            cursor.execute('''
                SELECT remitente, COUNT(*) as vol FROM tickets 
                WHERE fecha BETWEEN ? AND ? 
                GROUP BY remitente ORDER BY vol DESC LIMIT 1
            ''', (inicio_sql, fin_sql))
            top_remitente_row = cursor.fetchone()
            top_remitente = f"{top_remitente_row[0]} ({top_remitente_row[1]} tkts)" if top_remitente_row else "N/A"

            # Extracción del Backlog Pendiente (Ordenado por gravedad)
            cursor.execute('''
                SELECT remitente, asunto, score, razonamiento, id_mensaje 
                FROM tickets 
                WHERE fecha BETWEEN ? AND ? AND revisado = 0
                ORDER BY score DESC
            ''', (inicio_sql, fin_sql))
            tickets_pendientes_lista = cursor.fetchall()

        # 3. DISEÑO DE LA TARJETA ADAPTABLE (Dashboard Interactivo)
        cuerpo_tarjeta = [
            {
                "type": "TextBlock",
                "text": "📊 Informe Analítico de Service Desk",
                "weight": "Bolder", "size": "ExtraLarge", "color": "Accent"
            },
            {
                "type": "TextBlock",
                "text": f"📅 **Periodo analizado:** {texto_fechas}",
                "wrap": True, "spacing": "Small"
            },
            # --- SECCIÓN: KPIs PRINCIPALES ---
            {
                "type": "ColumnSet",
                "separator": True,
                "spacing": "Medium",
                "columns": [
                    {
                        "type": "Column", "width": "stretch",
                        "items": [
                            {"type": "TextBlock", "text": "Volumen Total", "size": "Small", "isSubtle": True},
                            {"type": "TextBlock", "text": str(total_tickets), "size": "ExtraLarge", "weight": "Bolder", "color": "Good"}
                        ]
                    },
                    {
                        "type": "Column", "width": "stretch",
                        "items": [
                            {"type": "TextBlock", "text": "Gravedad Media", "size": "Small", "isSubtle": True},
                            {"type": "TextBlock", "text": f"{score_promedio}/5", "size": "ExtraLarge", "weight": "Bolder", "color": "Warning"}
                        ]
                    },
                    {
                        "type": "Column", "width": "stretch",
                        "items": [
                            {"type": "TextBlock", "text": "Pendientes", "size": "Small", "isSubtle": True},
                            {"type": "TextBlock", "text": str(total_pendientes), "size": "ExtraLarge", "weight": "Bolder", "color": "Attention" if total_pendientes > 0 else "Good"}
                        ]
                    }
                ]
            },
            # --- SECCIÓN: RENDIMIENTO IA Y ANALÍTICA ---
            {
                "type": "FactSet",
                "separator": True,
                "facts": [
                    {"title": "🎯 Precisión Operativa:", "value": f"**{precision_ia}%** (Margen ±1)"},
                    {"title": "🟢 Aciertos Exactos:", "value": str(exactos)},
                    {"title": "🟡 Desviaciones Leves:", "value": str(leves)},
                    {"title": "🔴 Fallos Críticos:", "value": str(criticos)},
                    {"title": "📢 Top Solicitante:", "value": top_remitente}
                ]
            }
        ]

        # 4. AÑADIR ANÁLISIS GENERATIVO Y BACKLOG (Si aplica)
        if total_pendientes > 0:
            resumen_ia = obtener_resumen_generativo(tickets_pendientes_lista, texto_fechas)
            cuerpo_tarjeta.append({
                "type": "Container", "style": "emphasis", "padding": "10px", "spacing": "Medium",
                "items": [
                    {"type": "TextBlock", "text": "🧠 Resumen Ejecutivo (IA):", "weight": "Bolder", "color": "Accent"},
                    {"type": "TextBlock", "text": resumen_ia, "wrap": True, "fontType": "Monospace", "size": "Small"}
                ]
            })

            cuerpo_tarjeta.append({"type": "TextBlock", "text": "⚠️ Top Incidencias Pendientes:", "weight": "Bolder", "spacing": "Medium"})

            # Mostrar un máximo de 5 tickets en la tarjeta para no romper Teams
            for t in tickets_pendientes_lista[:5]:
                remitente, asunto, score, razonamiento, id_mensaje = t
                id_encoded = urllib.parse.quote(id_mensaje) if id_mensaje else ""
                url_outlook = f"https://outlook.live.com/mail/0/inbox/id/{id_encoded}"

                cuerpo_tarjeta.append({
                    "type": "Container", 
                    "style": "attention" if score >= 4 else "default",
                    "spacing": "Small",
                    "items": [
                        {"type": "TextBlock", "text": f"Nivel {score} | {asunto}", "weight": "Bolder"},
                        {"type": "TextBlock", "text": f"👤 {remitente}", "isSubtle": True, "size": "Small"},
                        {
                            "type": "ActionSet",
                            "actions": [{"type": "Action.OpenUrl", "title": "📧 Ver en Outlook", "url": url_outlook}]
                        }
                    ]
                })
            
            if total_pendientes > 5:
                cuerpo_tarjeta.append({"type": "TextBlock", "text": f"... y {total_pendientes - 5} tickets más.", "isSubtle": True, "size": "Small", "horizontalAlignment": "Center"})
        
        else:
            cuerpo_tarjeta.append({"type": "TextBlock", "text": "✅ Bandeja limpia. No hay tareas pendientes en este periodo.", "color": "Good", "spacing": "Medium"})

        # 5. ENVÍO DEL PAYLOAD A TEAMS
        payload = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {"type": "AdaptiveCard", "version": "1.4", "body": cuerpo_tarjeta}
            }]
        }
        
        response = requests.post(webhook_url, json=payload)
        # requests.response.ok incluye cualquier código de éxito (200, 201, 202...)
        if response.ok: 
            logging.info("📈 Reporte enviado y aceptado correctamente por Teams.")
        else:
            logging.error(f"❌ Error en Webhook Teams: {response.status_code} - {response.text}")
    except Exception as e:
        logging.error(f"❌ Error crítico generando reporte: {e}")

