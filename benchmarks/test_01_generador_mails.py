import json
import random
import requests
import csv
from tqdm import tqdm  

# ==========================================
# 1. REPRODUCIBILIDAD
# ==========================================
SEMILLA_EXPERIMENTO = 42
random.seed(SEMILLA_EXPERIMENTO)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODELO = "llama3.2"

# ==========================================
# 2. MATRIZ DE ARQUETIPOS ITSM (RECALIBRADA A RÚBRICA ESTRICTA)
# ==========================================
arquetipos = [
    # --- CATEGORÍA 1: PETICIONES DE SERVICIO ---
    {"rol": "Usuario agradecido", "contexto": "Responde solo para dar las gracias porque todo funciona.", "q": 1, "r": 2, "hilo": True},
    {"rol": "Usuario nuevo", "contexto": "Pregunta cómo configurar la firma del correo.", "q": 2, "r": 3, "hilo": False},
    {"rol": "Becario", "contexto": "No sabe programar una reunión en Teams.", "q": 2, "r": 3, "hilo": False},
    {"rol": "Empleado estándar", "contexto": "Pide instalar Visio para un proyecto el mes que viene.", "q": 3, "r": 1, "hilo": True},
    {"rol": "Administrativo", "contexto": "Pide cambiar el ratón por uno ergonómico.", "q": 3, "r": 2, "hilo": False},

    # --- CATEGORÍA 2: INCIDENCIAS MENORES ---
    {"rol": "RRHH", "contexto": "Error de permisos en la carpeta 'Nominas_2024'.", "q": 4, "r": 4, "hilo": True},
    {"rol": "Marketing", "contexto": "No sincroniza OneDrive (cruz roja).", "q": 4, "r": 4, "hilo": True},
    {"rol": "Jefe equipo", "contexto": "Impresora planta 2 atasca papel.", "q": 5, "r": 4, "hilo": False},
    {"rol": "Analista", "contexto": "Excel se queda colgado con macros pesadas.", "q": 5, "r": 5, "hilo": True},
    
    # --- CATEGORÍA 3: DEGRADACIÓN Y EXIGENCIA ---
    {"rol": "Reincidente", "contexto": "Tercera vez que se bloquea el Active Directory.", "q": 5, "r": 6, "hilo": True},
    {"rol": "Logística", "contexto": "Pistolas PDA del almacén pierden conexión intermitente.", "q": 6, "r": 6, "hilo": False},
    {"rol": "Director planta", "contexto": "WiFi en el ala oeste muy lento, afecta al departamento.", "q": 7, "r": 7, "hilo": True},
    {"rol": "Contabilidad", "contexto": "El ERP SAP va muy lento, bloquea la facturación de hoy.", "q": 6, "r": 7, "hilo": False},

    # --- CATEGORÍA 4: RUIDO Y AGRESIVIDAD (Falso crítico) ---
    {"rol": "Usuario enfadado", "contexto": "Se queja de la nueva actualización de Outlook.", "q": 8, "r": 2, "hilo": False},
    {"rol": "Comercial estresado", "contexto": "Escribe furioso porque no sabe poner fondo en Zoom.", "q": 8, "r": 4, "hilo": True},
    {"rol": "Manager caprichoso", "contexto": "Exige Premiere Pro urgente para vídeo de cumpleaños.", "q": 7, "r": 4, "hilo": False},

    # --- CATEGORÍA 5: EL PELIGRO SILENCIOSO (Poca queja, mucha urgencia) ---
    {"rol": "Sistema (Alerta)", "contexto": "Espacio disco servidor principal al 98%.", "q": 2, "r": 9, "hilo": False},
    {"rol": "Sistemas", "contexto": "Error en Batch de backups. No hay copia hoy.", "q": 2, "r": 8, "hilo": False},
    {"rol": "Admin web", "contexto": "Certificado SSL del dominio caduca en 24h.", "q": 3, "r": 7, "hilo": True},
    {"rol": "Técnico CPD", "contexto": "Aire acondicionado CPD falló. Racks a 35 grados.", "q": 2, "r": 10, "hilo": False},

    # --- CATEGORÍA 6: CIBERSEGURIDAD Y CAÍDAS NÚCLEO ---
    {"rol": "CEO", "contexto": "Reunión ejecutiva bloqueada. Pantalla interactiva rota.", "q": 7, "r": 8, "hilo": False},
    {"rol": "Usuario alarmado", "contexto": "Compañero hizo click en Phishing masivo.", "q": 8, "r": 9, "hilo": True},
    {"rol": "Gerente E-commerce", "contexto": "Pasarela web da Error 500. Pérdida económica masiva.", "q": 9, "r": 9, "hilo": True},
    {"rol": "Seguridad", "contexto": "Detectado Ransomware .lock en sede central.", "q": 9, "r": 10, "hilo": False}
]

def generar_ticket_limpio(indice):
    arq = random.choice(arquetipos)
    ticket_id = f"TICKET_{indice:03d}"
    
    instruccion_ruido = ""
    if arq['q'] >= 8:
        instruccion_ruido += "- Usa MAYÚSCULAS para enfatizar tu queja, usa múltiples exclamaciones (!!!) y muestra un tono agresivo o de pánico extremo.\n"
    elif arq['q'] == 1:
        instruccion_ruido += "- Usa un tono puramente positivo, de agradecimiento. Ninguna queja.\n"
    elif arq['q'] == 2:
        instruccion_ruido += "- Usa un tono completamente neutro e informativo, sin emociones ni fricción.\n"

    instruccion_hilo = ""
    if arq['hilo']:
        instruccion_hilo = "- Simula que esto es un correo reenviado. Añade una cabecera falsa (Ej: '--- Mensaje reenviado ---') al principio del CUERPO del mensaje (nunca en el asunto).\n"

    prompt = f"""
    Eres un empleado en una empresa escribiendo al soporte informático.
    Tu rol: {arq['rol']}. Tu problema: {arq['contexto']}.
    
    Reglas de escritura obligatorias:
    {instruccion_ruido}{instruccion_hilo}
    - No uses etiquetas como [ASUNTO] o [CUERPO] dentro del texto generado.
    
    RESPONDE ÚNICAMENTE CON UN JSON VÁLIDO. Este es el esquema exacto:
    {{
      "asunto": "escribe el asunto aquí",
      "cuerpo": "escribe el contenido del correo aquí"
    }}
    """

    try:
        res = requests.post(OLLAMA_URL, json={"model": MODELO, "prompt": prompt, "stream": False, "format": "json"})
        respuesta_json = json.loads(res.json()["response"])
        
        asunto = respuesta_json.get("asunto", "Incidencia General").strip()
        cuerpo = respuesta_json.get("cuerpo", "Sin detalle").strip()
        
        if asunto.upper().startswith("ASUNTO:"):
            asunto = asunto[7:].strip()
            
    except Exception as e:
        return None, None

    ticket_json = {
        "id": ticket_id,
        "asunto": asunto,
        "cuerpo": cuerpo,
        "gt_queja": arq['q'],
        "gt_retraso": arq['r']
    }

    fila_csv = [ticket_id, asunto, cuerpo, arq['q'], arq['r'], "", ""]
    return ticket_json, fila_csv

# ==========================================
# MOTOR DE EJECUCIÓN CON TQDM
# ==========================================
VOLUMEN_DESEADO = 100 

lista_json = []
lista_csv = [["ID_Ticket", "Asunto", "Cuerpo", "Queja_Target", "Retraso_Target", "Queja_Real_Humano", "Retraso_Real_Humano"]]

print(f"[*] Iniciando generación limpia en modo JSON nativo (Seed: {SEMILLA_EXPERIMENTO})...")

# Inicializamos la barra de progreso
barra_progreso = tqdm(range(1, VOLUMEN_DESEADO + 1), desc="Generando Tickets", unit="ticket", colour="green", ncols=100)

for i in barra_progreso:
    t_json, f_csv = generar_ticket_limpio(i)
    if t_json:
        lista_json.append(t_json)
        lista_csv.append(f_csv)
        # Actualiza el texto auxiliar de la barra con los datos del último ticket
        barra_progreso.set_postfix_str(f"✅ {t_json['id']} [Q:{t_json['gt_queja']} R:{t_json['gt_retraso']}]")

with open("data/dataset_gold_standard.json", "w", encoding="utf-8") as f:
    json.dump(lista_json, f, indent=4, ensure_ascii=False)

with open("data/auditoria_HITL.csv", mode="w", newline="", encoding="utf-8") as f:
    csv.writer(f, delimiter=";").writerows(lista_csv)

print("\n[*] Dataset Completado. Archivos generados:\n- data/dataset_gold_standard.json\n- data/auditoria_HITL.csv")