import os
import re
import email
from email import policy
import json
import time
import pandas as pd
import ollama

# =================================================================
# 1. CONFIGURACIÓN Y RUTAS
# =================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

# Carpeta donde guardaste los correos simulados
PATH_INPUT_DIR = os.path.join(ROOT_DIR, "data", "raw", "eml_simulados")
# Archivo de resultados con el Scoring
PATH_OUTPUT = os.path.join(ROOT_DIR, "data", "processed", "evaluacion_scoring_compleja.csv")

os.makedirs(os.path.dirname(PATH_OUTPUT), exist_ok=True)

# =================================================================
# 2. EL EXTRACTOR Y SEPARADOR ESTRUCTURAL (NLP Data Prep)
# =================================================================
def limpiar_y_separar_correo(texto_bruto):
    """
    Decodifica el texto y lo corta estratégicamente en dos bloques
    para darle "pesos" distintos a la IA.
    """
    texto = texto_bruto.replace('\r\n', '\n')
    
    # Patrones que indican el inicio de un correo reenviado o respondido
    patrones_corte = [
        r"----- Mensaje Original -----",
        r"-----Original Message-----",
        r"De: .*\nPara: .*\nAsunto:",
        r"From: .*\nTo: .*\nSubject:",
        r"_{10,}" # Líneas de guiones bajos largas
    ]
    
    patron_combinado = "(?i)(" + "|".join(patrones_corte) + ")"
    match = re.search(patron_combinado, texto)
    
    if match:
        # 1. Lo principal (El mensaje de hoy)
        mensaje_actual = texto[:match.start()].strip()
        # 2. El contexto (Correos de días anteriores)
        historial = texto[match.start():].strip()
    else:
        mensaje_actual = texto.strip()
        historial = "No hay correos previos en este hilo."
        
    return mensaje_actual, historial

def parsear_archivo_eml(ruta_eml):
    """Abre el .eml, destruye los adjuntos binarios y extrae el texto puro"""
    with open(ruta_eml, 'rb') as f:
        msg = email.message_from_binary_file(f, policy=policy.default)
    
    asunto = msg.get('Subject', 'Sin Asunto')
    remitente = msg.get('From', 'Desconocido')
    cuerpo_texto = ""
    
    # Navegar por el MIME Multipart
    if msg.is_multipart():
        for part in msg.walk():
            # Ignoramos la basura binaria (PDFs, imágenes, base64)
            if part.get_content_disposition() == 'attachment':
                continue
            
            if part.get_content_type() == 'text/plain':
                cuerpo_texto = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore')
                break
    else:
        cuerpo_texto = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', errors='ignore')

    # Separamos estructuralmente
    msg_actual, historial = limpiar_y_separar_correo(cuerpo_texto)

    return {
        "asunto": asunto,
        "remitente": remitente,
        "mensaje_actual": msg_actual,
        "historial": historial
    }

# =================================================================
# 3. EL CEREBRO EVALUADOR (Llama 3.2 con Pesos Semánticos)
# =================================================================
def evaluar_scoring_ticket(asunto, mensaje_actual, historial):
    system_prompt = """
    Eres un analista Senior de IT Service Desk. Tu trabajo es leer correos y asignar un SCORE de criticidad/enfado del 1 al 5.
    
    ESCALA DE SCORE:
    1: Contento, duda resuelta, agradecimiento.
    2: Duda técnica normal, proceso rutinario.
    3: Molestia ligera, interrupción menor.
    4: Frustración evidente, queja formal, retraso inaceptable.
    5: Furia total, bloqueo crítico (sistema caído), lenguaje de urgencia extrema.
    
    ⚠️ REGLA DE ORO PARA EL ANÁLISIS (PESOS DE ATENCIÓN):
    - Debes basar el 90% de tu decisión en la caja [MENSAJE ACTUAL DEL USUARIO]. Esa es la emoción real de hoy.
    - La caja [HISTORIAL DE CONTEXTO] tiene un peso menor. Úsala SOLO para entender de qué sistema técnico están hablando (ej. VPN, ERP). NO uses las emociones de los correos antiguos para calcular el Score.
    
    RESPONDE ÚNICAMENTE EN JSON:
    {
      "score_ia": <número del 1 al 5>,
      "sistema_afectado": "<Nombre del sistema o 'Desconocido'>",
      "razonamiento": "<Breve explicación de por qué este score, diferenciando el mensaje de hoy del historial>"
    }
    """
    
    prompt_usuario = f"""
    ASUNTO: {asunto}
    
    ==================================
    [MENSAJE ACTUAL DEL USUARIO] (Evalúa la emoción aquí)
    {mensaje_actual}
    ==================================
    [HISTORIAL DE CONTEXTO] (Solo para contexto técnico)
    {historial}
    ==================================
    """
    
    try:
        response = ollama.generate(
            model='llama3.2',
            prompt=f"{system_prompt}\n\n{prompt_usuario}",
            format='json',
            options={'temperature': 0.0} # Temp 0 para máxima precisión analítica
        )
        return json.loads(response['response'])
    except Exception as e:
        print(f"[*] Error en LLM: {e}")
        return None

# =================================================================
# 4. MOTOR DE EJECUCIÓN (Pipeline)
# =================================================================
def ejecutar_pipeline_evaluacion():
    archivos_eml = [f for f in os.listdir(PATH_INPUT_DIR) if f.endswith('.eml')]
    total = len(archivos_eml)
    
    if total == 0:
        print(f"[*] No hay archivos .eml en {PATH_INPUT_DIR}. Ejecuta primero el simulador.")
        return

    print(f"Iniciando Pipeline de Scoring (Lectura + Separación + Llama 3.2) con {total} tickets...\n" + "-"*60)

    # Checkpoint logic
    if os.path.exists(PATH_OUTPUT):
        df_existente = pd.read_csv(PATH_OUTPUT)
        procesados = df_existente['archivo'].tolist()
        print(f"[*] Checkpoint: {len(procesados)} tickets ya evaluados.")
    else:
        columnas = ['archivo', 'remitente', 'asunto', 'score_ia', 'sistema_afectado', 'razonamiento']
        pd.DataFrame(columns=columnas).to_csv(PATH_OUTPUT, index=False)
        procesados = []

    for i, archivo in enumerate(archivos_eml):
        if archivo in procesados:
            continue
            
        inicio = time.time()
        ruta_completa = os.path.join(PATH_INPUT_DIR, archivo)
        
        # 1. Parsear y Separar
        datos_correo = parsear_archivo_eml(ruta_completa)
        
        # 2. Inferencia LLM
        evaluacion = evaluar_scoring_ticket(
            datos_correo['asunto'], 
            datos_correo['mensaje_actual'], 
            datos_correo['historial']
        )
        
        if evaluacion:
            tiempo = time.time() - inicio
            score = evaluacion.get('score_ia', 0)
            
            # Formato visual en consola
            alert = "🔥 CRÍTICO" if score == 5 else "🚨 URGENTE" if score == 4 else "⚠️ AVISO" if score == 3 else "✅ NORMAL"
            
            nueva_fila = {
                'archivo': archivo,
                'remitente': datos_correo['remitente'],
                'asunto': datos_correo['asunto'],
                'score_ia': score,
                'sistema_afectado': evaluacion.get('sistema_afectado', ''),
                'razonamiento': evaluacion.get('razonamiento', '')
            }
            
            pd.DataFrame([nueva_fila]).to_csv(PATH_OUTPUT, mode='a', header=False, index=False)
            
            print(f"[{i+1}/{total}] {archivo} | SCORE: {score}/5 {alert} ({tiempo:.1f}s)")
            print(f"[*] Sistema: {nueva_fila['sistema_afectado']}")
            print(f"[*] Razón: {nueva_fila['razonamiento']}")
            print("-" * 60)

    print(f"\n💾 Pipeline completado. Reporte maestro guardado en:\n{PATH_OUTPUT}")

if __name__ == "__main__":
    ejecutar_pipeline_evaluacion()