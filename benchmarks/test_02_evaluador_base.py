import json
import csv
import time
import requests
import numpy as np
from tqdm import tqdm
from sklearn.metrics import mean_absolute_error, mean_squared_error, cohen_kappa_score
from datetime import datetime

# ==========================================
# CONFIGURACIÓN DEL EXPERIMENTO
# ==========================================
OLLAMA_URL = "http://localhost:11434/api/generate"
MODELO = "llama3.2"
PATH_CSV_ENTRADA = "data/auditoria_HITL.csv" 
PATH_CSV_SALIDA = "data/resultados_evaluacion.csv"
PATH_JSON_METRICAS = "data/metricas_globales_test02.json"

def obtener_prediccion_llama(asunto, cuerpo):
    """
    Invoca a Llama 3.2 usando el prompt ultra-robusto con CoT (Chain of Thought).
    """
    prompt_produccion = f"""
    <rol>
    Eres un Analista Experto de Nivel 3 en el Service Desk IT de una corporación multinacional. Tu tarea es analizar correos electrónicos entrantes y clasificarlos con precisión matemática basándote ESTRICTAMENTE en dos rúbricas predefinidas.
    </rol>

    <instrucciones_contexto>
    El objetivo es priorizar la atención técnica. Ignora firmas de correo y ruido corporativo. Céntrate en el impacto operativo y la urgencia temporal descrita.
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
    9 - Pánico o Amenaza de Negocio: Amenazas de escalar a RRHH/Dirección, o mención explícita de pérdida de dinero/ventas.
    10 - Catástrofe: Insultos directos graves, histeria total, o confirmación de caída de sistemas Core (producción parada, ciberataque).

    DIMENSIÓN 2: NIVEL DE RETRASO / SLA (URGENCIA TEMPORAL)
    1 - Planificación futura: Semanas o meses vista. Ninguna prisa.
    2 - Tarea sin plazo: "Cuando podáis", "No corre prisa". Baja prioridad.
    3 - Tiempo de resolución estándar (SLA normal): Primer aviso de una incidencia común sin indicar urgencia temporal.
    4 - Urgencia moderada: Petición para resolver "hoy" o "lo antes posible". Ligera presión.
    5 - Retraso con impacto: Seguimiento de un ticket anterior no resuelto. El retraso empieza a afectar la planificación.
    6 - Reiteración urgente: 2º o 3º aviso consecutivo ("lo necesito para esta tarde sin falta").
    7 - Bloqueo inminente: El usuario no puede avanzar en su trabajo principal y está parado esperando a IT.
    8 - Atención inmediata ("minutos"): Reuniones ejecutivas bloqueadas, directivos esperando en sala, fallo crítico reportado en tiempo real.
    9 - Paralización de negocio: Caída que afecta a clientes externos en vivo o detiene completamente un departamento.
    10 - Emergencia vital/absoluta: Servidores caídos, riesgo físico (incendio, aire acondicionado de CPD roto), ransomware masivo.
    </rubricas_evaluacion>

    <correo_a_evaluar>
    Asunto: {asunto}
    Cuerpo: {cuerpo}
    </correo_a_evaluar>

    <formato_salida_obligatorio>
    Genera ÚNICAMENTE un objeto JSON válido. NO incluyas texto introductorio.
    ESTRUCTURA EXACTA:
    {{
      "razonamiento": "<Analiza paso a paso: 1) Palabras clave. 2) Justificación Queja. 3) Justificación Retraso.>",
      "nivel_queja": <int>,
      "nivel_retraso": <int>
    }}
    </formato_salida_obligatorio>
    """
    
    try:
        start_time = time.time()
        res = requests.post(OLLAMA_URL, json={"model": MODELO, "prompt": prompt_produccion, "stream": False, "format": "json"})
        latencia = (time.time() - start_time) * 1000 # ms
        
        raw_response = res.json()["response"]
        data = json.loads(raw_response)
        
        q = int(data.get("nivel_queja", 0))
        r = int(data.get("nivel_retraso", 0))
        razon = data.get("razonamiento", "Sin razonamiento proporcionado.")
        
        return q, r, razon, latencia
    except Exception as e:
        return None, None, f"Error de parseo/inferencia: {e}", 0

# ==========================================
# PROCESAMIENTO DE DATOS Y EXPORTACIÓN
# ==========================================

print("🚀 Iniciando Evaluación Test 02...")

tickets_a_procesar = []
y_true_q = []
y_true_r = []

with open(PATH_CSV_ENTRADA, mode="r", encoding="utf-8") as f:
    reader = csv.DictReader(f, delimiter=";")
    for row in reader:
        # Prioriza la nota del humano, si no, usa el Target
        q_real = row.get("Queja_Real_Humano") or row.get("Queja_Target")
        r_real = row.get("Retraso_Real_Humano") or row.get("Retraso_Target")
        
        if q_real and r_real:
            y_true_q.append(int(q_real))
            y_true_r.append(int(r_real))
            tickets_a_procesar.append(row)

if not tickets_a_procesar:
    print("❌ Error: No se encontraron datos válidos en el CSV.")
    exit()

y_pred_q = []
y_pred_r = []
latencias = []
registro_detallado = []

cabeceras_salida = [
    "ID_Ticket", "Latencia_ms", 
    "Queja_Real", "Queja_Pred", "Error_Q",
    "Retraso_Real", "Retraso_Pred", "Error_R",
    "Razonamiento_LLM"
]
registro_detallado.append(cabeceras_salida)

print(f"📊 Evaluando {len(tickets_a_procesar)} tickets con Llama 3.2...")
barra_progreso = tqdm(tickets_a_procesar, desc="Progreso", unit="ticket", colour="blue", ncols=100)

for i, ticket in enumerate(barra_progreso):
    q_real = y_true_q[i]
    r_real = y_true_r[i]
    id_ticket = ticket.get("ID_Ticket", f"TICKET_{i}")
    
    q_pred, r_pred, razon, lat = obtener_prediccion_llama(ticket["Asunto"], ticket["Cuerpo"])
    
    if q_pred is not None and r_pred is not None:
        y_pred_q.append(q_pred)
        y_pred_r.append(r_pred)
        latencias.append(lat)
        
        error_q = q_pred - q_real
        error_r = r_pred - r_real
        
        registro_detallado.append([
            id_ticket, round(lat, 2),
            q_real, q_pred, error_q,
            r_real, r_pred, error_r,
            razon
        ])
        
        barra_progreso.set_postfix_str(f"ID:{id_ticket} | Err_Q:{error_q} Err_R:{error_r}")

with open(PATH_CSV_SALIDA, mode="w", newline="", encoding="utf-8") as f:
    csv.writer(f, delimiter=";").writerows(registro_detallado)

# ==========================================
# CÁLCULO DE MÉTRICAS AVANZADAS
# ==========================================

def calcular_metricas(true, pred):
    true = np.array(true)
    pred = np.array(pred)
    
    mae = mean_absolute_error(true, pred)
    rmse = np.sqrt(mean_squared_error(true, pred))
    diff = np.abs(true - pred)
    acc_tol = np.mean(diff <= 1) * 100
    fallo_critico = np.mean(diff >= 3) * 100
    kappa = cohen_kappa_score(true, pred, weights='quadratic', labels=list(range(1,11)))
    
    return mae, rmse, acc_tol, fallo_critico, kappa

mae_q, rmse_q, acc_q, fc_q, kappa_q = calcular_metricas(y_true_q, y_pred_q)
mae_r, rmse_r, acc_r, fc_r, kappa_r = calcular_metricas(y_true_r, y_pred_r)

# ==========================================
# INFORME FINAL Y GUARDADO DE EXPERIMENTO
# ==========================================

print("\n" + "="*60)
print("🏆 RESULTADOS DEL TEST 02 (EVALUADOR BASE)")
print("="*60)
print(f"Modelo Evaluado: {MODELO}")
print(f"Muestra: {len(y_pred_q)} tickets procesados.")
print(f"Latencia Media: {np.mean(latencias):.2f} ms / ticket")

print("\n📈 DIMENSIÓN: NIVEL DE QUEJA")
print(f" - MAE: {mae_q:.2f} | RMSE: {rmse_q:.2f} | Acc(±1): {acc_q:.1f}% | QWK: {kappa_q:.3f} | Fallos Críticos: {fc_q:.1f}%")

print("\n📉 DIMENSIÓN: NIVEL DE RETRASO")
print(f" - MAE: {mae_r:.2f} | RMSE: {rmse_r:.2f} | Acc(±1): {acc_r:.1f}% | QWK: {kappa_r:.3f} | Fallos Críticos: {fc_r:.1f}%")
print("="*60)

# Guardar las métricas en JSON
informe_experimento = {
    "experimento": "Test 02: Evaluacion Base con Rúbrica",
    "fecha_ejecucion": datetime.now().isoformat(),
    "modelo": MODELO,
    "volumen_muestra": len(y_pred_q),
    "latencia_media_ms": round(float(np.mean(latencias)), 2),
    "metricas_queja": {
        "MAE": round(mae_q, 3),
        "RMSE": round(rmse_q, 3),
        "Accuracy_tol_1": round(acc_q, 2),
        "Kappa_QWK": round(kappa_q, 3),
        "Tasa_Fallo_Critico": round(fc_q, 2)
    },
    "metricas_retraso": {
        "MAE": round(mae_r, 3),
        "RMSE": round(rmse_r, 3),
        "Accuracy_tol_1": round(acc_r, 2),
        "Kappa_QWK": round(kappa_r, 3),
        "Tasa_Fallo_Critico": round(fc_r, 2)
    }
}

with open(PATH_JSON_METRICAS, "w", encoding="utf-8") as f:
    json.dump(informe_experimento, f, indent=4, ensure_ascii=False)

print(f"💾 Resultados detallados guardados en: {PATH_CSV_SALIDA}")
print(f"💾 Métricas globales guardadas en: {PATH_JSON_METRICAS}")