import time
import json
import os
import shutil
import requests
from dotenv import load_dotenv

# ==========================================
# 0. CARGAR SEGURIDAD
# ==========================================
load_dotenv()

# ==========================================
# 1. CONFIGURACIÓN
# ==========================================
CARPETA_ONEDRIVE = r"C:\Users\barco\OneDrive\Documentos\GitHub\it-mail-service-desk\docs" 
WEBHOOK_TEAMS = os.getenv("WEBHOOK_TEAMS")

if not WEBHOOK_TEAMS:
    print("[*] ERROR: No se encontró WEBHOOK_TEAMS en el .env")
    exit()

CARPETA_PROCESADOS = os.path.join(CARPETA_ONEDRIVE, "Procesados")
if not os.path.exists(CARPETA_PROCESADOS):
    os.makedirs(CARPETA_PROCESADOS)

# ==========================================
# 2. EL CEREBRO CLASIFICADOR (Llama 3.2)
# ==========================================
def analizar_con_ia(asunto, cuerpo):
    print("🦙 Llama 3.2 analizando severidad...")
    url_ollama = "http://localhost:11434/api/generate"
    
    prompt_ia = f"""
    Eres un analista de soporte técnico. Analiza este mensaje.
    REGLAS:
    1. Predicción: NEGATIVE (queja/fallo) o NO_QUEJA.
    2. Score: Del 1 al 5 (5 es urgencia máxima, 1 es duda leve).

    Mensaje:
    Asunto: {asunto}
    Cuerpo: {cuerpo}

    RESPONDE ÚNICAMENTE EN JSON:
    {{
      "prediccion": "NEGATIVE o NO_QUEJA",
      "score": 1-5,
      "razonamiento": "Breve explicación"
    }}
    """
    
    try:
        respuesta = requests.post(url_ollama, json={
            "model": "llama3.2", 
            "prompt": prompt_ia,
            "stream": False,
            "format": "json"
        })
        if respuesta.status_code == 200:
            return json.loads(respuesta.json().get("response", "{}"))
        return {"prediccion": "ERROR", "score": 1, "razonamiento": "Error de comunicación con IA."}
    except Exception as e:
        return {"prediccion": "ERROR", "score": 1, "razonamiento": str(e)}

# ==========================================
# 3. NOTIFICACIÓN ESTILO PREMIUM
# ==========================================
def enviar_alerta_teams(remitente, asunto, razonamiento, score, archivo):
    print(f"📢 Escalando alerta crítica a Teams (Score: {score})...")
    
    # Construcción de la Adaptive Card según el estilo solicitado
    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
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
                            "text": f"**Prioridad Detectada:** Nivel {score}/5",
                            "isSubtle": True,
                            "wrap": True
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                { "title": "Archivo:", "value": archivo },
                                { "title": "Remitente:", "value": remitente },
                                { "title": "Asunto:", "value": asunto }
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
                            "text": razonamiento,
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
    
    try:
        headers = {'Content-Type': 'application/json'}
        respuesta = requests.post(WEBHOOK_TEAMS, data=json.dumps(payload), headers=headers)
        if respuesta.status_code in [200, 202]:
             print("[*] Tarjeta enviada con éxito.")
        else:
             print(f"[*] Error en Teams: {respuesta.status_code}")
    except Exception as e:
        print(f"[*] Error de red: {e}")

# ==========================================
# 👀 4. EL VIGILANTE
# ==========================================
def vigilar_carpeta_activamente():
    print("==================================================")
    print("AGENTE IA INICIADO - ESTILO PREMIUM TEAMS")
    print("==================================================")
    
    while True:
        try:
            archivos = [f for f in os.listdir(CARPETA_ONEDRIVE) if f.endswith('.json')]
            
            for archivo in archivos:
                ruta = os.path.join(CARPETA_ONEDRIVE, archivo)
                if os.path.isfile(ruta):
                    try:
                        with open(ruta, 'r', encoding='utf-8') as f:
                            # strict=False para tolerar los saltos de línea del JSON de Power Automate
                            datos = json.loads(f.read(), strict=False)
                        
                        print(f"\nPROCESANDO: {archivo}")
                        remitente = datos.get("remitente", "Desconocido")
                        asunto = datos.get("asunto", "Sin asunto")
                        cuerpo = datos.get("cuerpo", "Sin cuerpo")

                        # 1. IA Analiza
                        res = analizar_con_ia(asunto, cuerpo)
                        pred = res.get("prediccion", "").upper()
                        score = res.get("score", 1)
                        razon = res.get("razonamiento", "Sin detalles.")

                        # 2. Filtro de Decisión (Solo alertas si es NEGATIVE o Score alto)
                        es_queja = "NEGATIVE" in pred or score >= 4

                        if es_queja:
                            print(f"🔥 VEREDICTO: Queja (Score {score}). Enviando Card...")
                            enviar_alerta_teams(remitente, asunto, razon, score, archivo)
                        else:
                            print(f"🟢 VEREDICTO: {pred} (Score {score}). No requiere alerta.")

                        # 3. Mover a Procesados
                        shutil.move(ruta, os.path.join(CARPETA_PROCESADOS, archivo))
                        print("[*] Ciclo completado.")

                    except (json.JSONDecodeError, PermissionError):
                        continue 
        except Exception as e:
            print(f"[*] Error general: {e}")
            
        time.sleep(5)

if __name__ == "__main__":
    vigilar_carpeta_activamente()