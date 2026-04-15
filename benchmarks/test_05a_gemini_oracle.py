import os
import sys
import json
import csv
import time
import numpy as np
import google.generativeai as genai
from tqdm import tqdm
from sklearn.metrics import mean_absolute_error, mean_squared_error, cohen_kappa_score
from datetime import datetime

# ==========================================
# 1. IMPORTAMOS MOTOR RAG Y CONFIGURAMOS RUTAS
# ==========================================
ruta_raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ruta_raiz not in sys.path:
    sys.path.insert(0, ruta_raiz)

from src.rag_engine import buscar_tickets_similares

DIRECTORIO_BASE = os.path.dirname(os.path.abspath(__file__))
# Usamos los mismos datos que el Test 04
PATH_CSV_ENTRADA = os.path.join(DIRECTORIO_BASE, "data", "dataset_test_rag.csv") 
DB_PATH_BENCHMARK = os.path.join(DIRECTORIO_BASE, "data", "incidencias_test.db") 

# Salidas específicas para el Oráculo
PATH_CSV_SALIDA = os.path.join(DIRECTORIO_BASE, "data", "resultados_gemini_oracle.csv")
PATH_JSON_METRICAS = os.path.join(DIRECTORIO_BASE, "data", "metricas_globales_test05_gemini.json")

# ==========================================
# 2. CONFIGURACIÓN DE GEMINI Y CONTEXTO
# ==========================================
GEMINI_API_KEY = "TuAPIKeyDeGoogleAI"  # Reemplaza con tu API Key de Google AI
genai.configure(api_key=GEMINI_API_KEY)
modelo_gemini = genai.GenerativeModel('gemini-2.5-flash-lite')

config = {
    "contexto": "El objetivo es priorizar la atención técnica. Ignora firmas de correo y ruido corporativo. Céntrate en el impacto operativo y la urgencia temporal descrita."
}

def construir_contexto_rag(asunto, cuerpo):
    similares, _ = buscar_tickets_similares(asunto, cuerpo, top_k=3, db_path=DB_PATH_BENCHMARK)
    if not similares:
        return ""
    
    contexto = "TICKETS HISTÓRICOS SIMILARES RESUELTOS:\n"
    for i, res in enumerate(similares, 1):
        q = res['nivel_queja_humano'] if res['nivel_queja_humano'] else res['nivel_queja']
        r = res['nivel_retraso_humano'] if res['nivel_retraso_humano'] else res['nivel_retraso']
        razon = res['razonamiento_humano'] if res['razonamiento_humano'] else res['razonamiento']
        
        contexto += f"[Ejemplo {i}] - Similitud: {res['similitud']:.2f}\n"
        contexto += f"Asunto original: {res['asunto']}\n"
        contexto += f"Evaluación Oficial -> Queja: {q} | Retraso: {r}\n"
        contexto += f"Justificación: {razon}\n\n"
    return contexto

def obtener_prediccion_gemini_con_rag(asunto, cuerpo):
    bloque_ejemplos = construir_contexto_rag(asunto, cuerpo)
    prompt_rag = f"""
    <rol>
    Eres un Analista Experto de Nivel 3 en el Service Desk IT de una corporación multinacional. Tu tarea es analizar correos electrónicos entrantes y clasificarlos con precisión matemática basándote ESTRICTAMENTE en dos rúbricas predefinidas.
    </rol>

    <instrucciones_contexto>
    {config['contexto']}
    </instrucciones_contexto>

    <rubricas_evaluacion>
    Evalúa el ticket en las siguientes dos dimensiones. Asigna un valor numérico entero (1 al 10). NO inventes niveles intermedios ni te desvíes de estas definiciones. Si el correo es SPAM ininteligible o vacío, asigna 1 a ambas dimensiones.

    DIMENSIÓN 1: NIVEL DE QUEJA / IMPACTO EMOCIONAL Y OPERATIVO
    1 - Tono puramente positivo: Agradecimiento por un ticket resuelto o confirmación de éxito. (Nota: ignorar "gracias de antemano" si hay una queja).
    2 - Tono neutro/informativo: Consulta general, duda de uso, sin fricción alguna.
    3 - Petición estándar: Solicitud de accesos, software o hardware para el futuro. Tono profesional y calmado.
    4 - Fricción leve: Falla menor, error recurrente pero salvable (workaround disponible). El usuario informa sin enfado explícito.
    5 - Frustración evidente: Lenguaje que denota molestia ("es la tercera vez", "es muy molesto"). Bloqueo de una tarea individual.
    6 - Exigencia de solución: Tono asertivo o queja formal leve. Afectación de un grupo pequeño o bloqueo total de un usuario base.
    7 - Tono cortante/Imperativo: Fuerte malestar. Usuario VIP bloqueado o afectación severa que paraliza un departamento entero.
    8 - Lenguaje agresivo: Uso de MAYÚSCULAS para gritar, múltiples exclamaciones (!!!), quejas directas sobre la incompetencia de IT.
    9 - Pánico o Amenaza de Negocio: Amenazas de escalar a RRHH/Dirección, o mención explícita de pérdida de dinero/ventas (ej. "estamos perdiendo miles de euros").
    10 - Catástrofe: Insultos directos graves, histeria total, o confirmación de caída de sistemas Core (producción parada a nivel global, ciberataque).

    DIMENSIÓN 2: NIVEL DE RETRASO / SLA (URGENCIA TEMPORAL)
    1 - Planificación futura: Semanas o meses vista. Ninguna prisa.
    2 - Tarea sin plazo: "Cuando podáis", "No corre prisa". Baja prioridad.
    3 - Tiempo de resolución estándar (SLA normal): Primer aviso de una incidencia común sin indicar urgencia temporal.
    4 - Urgencia moderada: Petición para resolver "hoy" o "lo antes posible". Ligera presión.
    5 - Retraso con impacto: Seguimiento de un ticket anterior no resuelto. El retraso empieza a afectar la planificación del usuario.
    6 - Reiteración urgente: 2º o 3º aviso consecutivo ("lo necesito para esta tarde sin falta").
    7 - Bloqueo inminente: El usuario no puede avanzar en su trabajo principal y está parado esperando a IT.
    8 - Atención inmediata ("minutos"): Reuniones ejecutivas bloqueadas, directivos esperando en sala, fallo crítico reportado en tiempo real.
    9 - Paralización de negocio: Caída que afecta a clientes externos en vivo o detiene completamente un departamento operativo.
    10 - Emergencia vital/absoluta: Servidores caídos, riesgo físico (incendio, aire acondicionado de CPD roto), ransomware masivo. Intervención en "segundos".
    </rubricas_evaluacion>

    <memoria_rag>
    Utiliza el siguiente historial de casos (Ground Truth) para calibrar tu respuesta y evitar errores pasados:
    {bloque_ejemplos if bloque_ejemplos else "Sin memoria relevante para este caso. Aplica las rúbricas de forma independiente."}
    </memoria_rag>

    <correo_a_evaluar>
    Asunto: {asunto}
    Cuerpo: {cuerpo}
    </correo_a_evaluar>

    <formato_salida_obligatorio>
    Genera ÚNICAMENTE un objeto JSON válido. NO incluyas texto introductorio ni etiquetas markdown (```json). Empieza directamente con la llave '{{'.
    
    ESTRUCTURA EXACTA:
    {{
      "razonamiento": "<Analiza paso a paso>",
      "nivel_queja": <int>,
      "nivel_retraso": <int>
    }}
    </formato_salida_obligatorio>
    """
    
    try:
        start_time = time.time()
        res = modelo_gemini.generate_content(
            prompt_rag,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1
            ),
            # ¡CORRECCIÓN 1! APAGAMOS LOS FILTROS DE SEGURIDAD PARA EVITAR BLOQUEOS POR LENGUAJE IT
            safety_settings={
                genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: genai.types.HarmBlockThreshold.BLOCK_NONE,
                genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
            }
        )
        latencia = (time.time() - start_time) * 1000 
        data = json.loads(res.text)
        
        q_raw = int(data.get("nivel_queja", 1))
        r_raw = int(data.get("nivel_retraso", 1))
        
        q = max(1, min(10, q_raw))
        r = max(1, min(10, r_raw))
        razon = data.get("razonamiento", "Sin razonamiento.")
        
        return q, r, razon, latencia
    except Exception as e:
        error_msg = str(e).lower()
        if "429" in error_msg or "quota" in error_msg or "exhausted" in error_msg:
            return None, None, "CUOTA_EXCEDIDA", 0
        return None, None, f"Error Gemini: {e}", 0

# ==========================================
# 3. PROCESAMIENTO RESILIENTE (CHECKPOINTING)
# ==========================================
print(f"Iniciando Test 05 (Oráculo Resiliente): Evaluación Gemini 2.5 Flash Lite + RAG...")

# 3.1 Cargar progreso anterior
tickets_procesados = set()
y_true_q, y_pred_q = [], []
y_true_r, y_pred_r = [], []
latencias = []

archivo_existe = os.path.exists(PATH_CSV_SALIDA)

if archivo_existe:
    print("[*] Detectado archivo anterior. Cargando progreso para reanudar...")
    with open(PATH_CSV_SALIDA, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            tickets_procesados.add(row["ID_Ticket"])
            y_true_q.append(int(float(row["Queja_Real"])))
            y_pred_q.append(int(float(row["Queja_Pred"])))
            y_true_r.append(int(float(row["Retraso_Real"])))
            y_pred_r.append(int(float(row["Retraso_Pred"])))
            latencias.append(float(row["Latencia_ms"]))
    print(f"[*] Ya se han procesado {len(tickets_procesados)} tickets. Saltando...")

# 3.2 Cargar el dataset a evaluar
tickets_a_procesar = []
try:
    with open(PATH_CSV_ENTRADA, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            id_t = row.get("ID_Ticket")
            if row.get("Queja_Real_Humano") and row.get("Retraso_Real_Humano") and id_t not in tickets_procesados:
                tickets_a_procesar.append(row)
except FileNotFoundError:
    print(f"[*] Error: No se encontró el dataset en:\n{PATH_CSV_ENTRADA}")
    exit()

if not tickets_a_procesar:
    print("[*] Todos los tickets ya estaban procesados. Generando métricas finales...")
else:
    # 3.3 Procesar los que faltan
    barra_progreso = tqdm(tickets_a_procesar, desc="Evaluando con Gemini", unit="ticket", colour="cyan", ncols=100)
    
    with open(PATH_CSV_SALIDA, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        
        if not archivo_existe:
            writer.writerow(["ID_Ticket", "Latencia_ms", "Queja_Real", "Queja_Pred", "Error_Q", "Retraso_Real", "Retraso_Pred", "Error_R", "Razonamiento_LLM"])

        for i, ticket in enumerate(barra_progreso):
            q_real = int(float(ticket.get("Queja_Real_Humano")))
            r_real = int(float(ticket.get("Retraso_Real_Humano")))
            id_ticket = ticket.get("ID_Ticket", f"TICKET_{i}")
            
            q_pred, r_pred, razon, lat = obtener_prediccion_gemini_con_rag(ticket["Asunto"], ticket["Cuerpo"])
            
            if razon == "CUOTA_EXCEDIDA":
                print("\n[*] ALERTA: Límite de Cuota de Google AI superado.")
                print("[*] Frenando ejecución de forma segura. Cambia la API_KEY y relanza el script para continuar donde lo dejaste.")
                break 
                
            if q_pred is not None and r_pred is not None:
                y_true_q.append(q_real)
                y_true_r.append(r_real)
                y_pred_q.append(q_pred)
                y_pred_r.append(r_pred)
                latencias.append(lat)
                
                error_q = q_pred - q_real
                error_r = r_pred - r_real
                
                writer.writerow([id_ticket, round(lat, 2), q_real, q_pred, error_q, r_real, r_pred, error_r, razon])
                f.flush() 
                
                barra_progreso.set_postfix_str(f"ID:{id_ticket} | Err_Q:{error_q} Err_R:{error_r}")
            
            # ¡CORRECCIÓN 2! CHIVATO DE ERRORES: Imprime en pantalla si algo falla.
            else:
                print(f"\n❌ Falla el ticket {id_ticket} | Motivo: {razon}")
                
            time.sleep(4.1)

# ==========================================
# 4. CÁLCULO Y GUARDADO DE MÉTRICAS (TOTALES)
# ==========================================
if not y_pred_q:
    print("[*] No hay datos suficientes para calcular métricas.")
    exit()

def calcular_metricas(true, pred):
    true, pred = np.array(true), np.array(pred)
    mae = mean_absolute_error(true, pred)
    rmse = np.sqrt(mean_squared_error(true, pred))
    diff = np.abs(true - pred)
    acc_tol = np.mean(diff <= 1) * 100
    fc = np.mean(diff >= 3) * 100
    kappa = cohen_kappa_score(true, pred, weights='quadratic', labels=list(range(1,11)))
    return mae, rmse, acc_tol, fc, kappa

mae_q, rmse_q, acc_q, fc_q, kappa_q = calcular_metricas(y_true_q, y_pred_q)
mae_r, rmse_r, acc_r, fc_r, kappa_r = calcular_metricas(y_true_r, y_pred_r)

print("\n" + "="*60)
print("RESULTADOS DEL ORÁCULO (GEMINI 2.5 + RAG)")
print("="*60)
print(f"Muestra total procesada: {len(y_pred_q)} tickets.")
print(f"Latencia Media: {np.mean(latencias):.2f} ms")
print("-" * 60)
print(f"DIMENSIÓN: QUEJA  | MAE: {mae_q:.2f} | Fallos Críticos: {fc_q:.1f}% | Acc(±1): {acc_q:.1f}%")
print(f"DIMENSIÓN: RETRASO| MAE: {mae_r:.2f} | Fallos Críticos: {fc_r:.1f}% | Acc(±1): {acc_r:.1f}%")
print("="*60)

informe_experimento = {
    "experimento": "Test 05: Validación de Oráculo (Gemini 2.5 Flash Lite + RAG)",
    "modelo": "gemini-2.5-flash-lite",
    "fecha_ejecucion": datetime.now().isoformat(),
    "volumen_muestra": len(y_pred_q),
    "latencia_media_ms": round(float(np.mean(latencias)), 2),
    "metricas_queja": {
        "MAE": round(mae_q, 2), "RMSE": round(rmse_q, 2), "Accuracy_tol_1": round(acc_q, 1), "Kappa_QWK": round(kappa_q, 3), "Tasa_Fallo_Critico": round(fc_q, 1)
    },
    "metricas_retraso": {
        "MAE": round(mae_r, 2), "RMSE": round(rmse_r, 2), "Accuracy_tol_1": round(acc_r, 1), "Kappa_QWK": round(kappa_r, 3), "Tasa_Fallo_Critico": round(fc_r, 1)
    }
}

with open(PATH_JSON_METRICAS, "w", encoding="utf-8") as f:
    json.dump(informe_experimento, f, indent=4, ensure_ascii=False)