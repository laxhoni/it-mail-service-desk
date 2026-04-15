import os
import sys
import json
import csv
import sys
import time
import requests
import numpy as np
from tqdm import tqdm
from sklearn.metrics import mean_absolute_error, mean_squared_error, cohen_kappa_score
from datetime import datetime

# Ruta de la raíz (donde están 'src' y 'benchmarks')
ruta_raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Añadimos la raíz al sistema
if ruta_raiz not in sys.path:
    sys.path.insert(0, ruta_raiz)

# IMPORTAMOS MOTOR RAG
from src.rag_engine import buscar_tickets_similares

# ==========================================
# CONFIGURACIÓN DEL EXPERIMENTO (RUTAS ABSOLUTAS)
# ==========================================
OLLAMA_URL = "http://localhost:11434/api/generate"
MODELO = "llama3.2"

# 1. Obtenemos la ruta absoluta de la carpeta donde está ESTE script ('benchmarks')
DIRECTORIO_BASE = os.path.dirname(os.path.abspath(__file__))

# 2. Construimos las rutas dinámicas para los CSV
PATH_CSV_ENTRADA = os.path.join(DIRECTORIO_BASE, "data", "dataset_test_rag.csv") 
PATH_CSV_SALIDA = os.path.join(DIRECTORIO_BASE, "data", "resultados_evaluacion_rag.csv")
PATH_JSON_METRICAS = os.path.join(DIRECTORIO_BASE, "data", "metricas_globales_test04_rag.json")

# 3. RUTA ESPECÍFICA A LA NUEVA BBDD DE PRUEBAS
DB_PATH_BENCHMARK = os.path.join(DIRECTORIO_BASE, "data", "incidencias_test.db") 

# Configuración centralizada para el contexto del prompt
config = {
    "contexto": "El objetivo es priorizar la atención técnica. Ignora firmas de correo y ruido corporativo. Céntrate en el impacto operativo y la urgencia temporal descrita."
}

def construir_contexto_rag(asunto, cuerpo):
    """
    Busca en SQLite y construye el texto para inyectar en el prompt.
    """
    # IMPORTANTE: Pasamos la ruta de la nueva BBDD de pruebas al motor RAG
    similares, _ = buscar_tickets_similares(asunto, cuerpo, top_k=3, db_path=DB_PATH_BENCHMARK)
    
    if not similares:
        return "" # Devolvemos vacío para que el prompt maneje el caso "Sin memoria"
    
    contexto = "TICKETS HISTÓRICOS SIMILARES RESUELTOS:\n"
    for i, res in enumerate(similares, 1):
        # Priorizamos la nota humana si existe, si no, la de la IA
        q = res['nivel_queja_humano'] if res['nivel_queja_humano'] else res['nivel_queja']
        r = res['nivel_retraso_humano'] if res['nivel_retraso_humano'] else res['nivel_retraso']
        razon = res['razonamiento_humano'] if res['razonamiento_humano'] else res['razonamiento']
        
        contexto += f"[Ejemplo {i}] - Similitud: {res['similitud']:.2f}\n"
        contexto += f"Asunto original: {res['asunto']}\n"
        contexto += f"Evaluación Oficial -> Queja: {q} | Retraso: {r}\n"
        contexto += f"Justificación: {razon}\n\n"
        
    return contexto

def obtener_prediccion_llama_con_rag(asunto, cuerpo):
    """
    Invoca a Llama 3.2 inyectando el contexto RAG dinámico en el prompt maestro.
    """
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
    Genera ÚNICAMENTE un objeto JSON válido. NO incluyas texto introductorio (ej. "Aquí tienes la respuesta:") ni etiquetas markdown (```json). Empieza directamente con la llave '{{'.
    
    ESTRUCTURA EXACTA:
    {{
      "razonamiento": "<Analiza paso a paso: 1) Palabras clave del texto. 2) Justificación de la nota de Queja según la rúbrica. 3) Justificación de la nota de Retraso según la rúbrica.>",
      "nivel_queja": <int>,
      "nivel_retraso": <int>
    }}
    </formato_salida_obligatorio>
    """
    
    try:
        start_time = time.time()
        res = requests.post(OLLAMA_URL, json={"model": MODELO, "prompt": prompt_rag, "stream": False, "format": "json"})
        latencia = (time.time() - start_time) * 1000 
        
        raw_response = res.json()["response"]
        data = json.loads(raw_response)
        
        q = int(data.get("nivel_queja", 0))
        r = int(data.get("nivel_retraso", 0))
        razon = data.get("razonamiento", "Sin razonamiento.")
        
        return q, r, razon, latencia
    except Exception as e:
        return None, None, f"Error: {e}", 0

# ==========================================
# PROCESAMIENTO Y BENCHMARKING
# ==========================================

print(f"Iniciando Test 04: Evaluación RAG apuntando a '{os.path.basename(DB_PATH_BENCHMARK)}'...")

tickets_a_procesar = []
y_true_q = []
y_true_r = []

# Carga segura con verificación de archivos
try:
    with open(PATH_CSV_ENTRADA, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            q_real = row.get("Queja_Real_Humano") 
            r_real = row.get("Retraso_Real_Humano") 
            
            if q_real and r_real:
                y_true_q.append(int(float(q_real)))
                y_true_r.append(int(float(r_real)))
                tickets_a_procesar.append(row)
except FileNotFoundError:
    print(f"[*] Error: No se encontró el dataset de prueba en:\n{PATH_CSV_ENTRADA}")
    print("[*] Asegúrate de ejecutar primero el script 'test_04a_preparar_bbdd.py'")
    exit()

y_pred_q, y_pred_r, latencias, registro_detallado = [], [], [], []
registro_detallado.append([
    "ID_Ticket", "Latencia_ms", "Queja_Real", "Queja_Pred", "Error_Q", "Retraso_Real", "Retraso_Pred", "Error_R", "Razonamiento_LLM"
])

barra_progreso = tqdm(tickets_a_procesar, desc="Evaluando con RAG", unit="ticket", colour="magenta", ncols=100)

for i, ticket in enumerate(barra_progreso):
    q_real = y_true_q[i]
    r_real = y_true_r[i]
    id_ticket = ticket.get("ID_Ticket", f"TICKET_{i}")
    
    q_pred, r_pred, razon, lat = obtener_prediccion_llama_con_rag(ticket["Asunto"], ticket["Cuerpo"])
    
    if q_pred is not None and r_pred is not None:
        y_pred_q.append(q_pred)
        y_pred_r.append(r_pred)
        latencias.append(lat)
        
        error_q = q_pred - q_real
        error_r = r_pred - r_real
        
        registro_detallado.append([id_ticket, round(lat, 2), q_real, q_pred, error_q, r_real, r_pred, error_r, razon])
        barra_progreso.set_postfix_str(f"ID:{id_ticket} | Err_Q:{error_q} Err_R:{error_r}")

with open(PATH_CSV_SALIDA, mode="w", newline="", encoding="utf-8") as f:
    csv.writer(f, delimiter=";").writerows(registro_detallado)

# ==========================================
# CÁLCULO Y GUARDADO DE MÉTRICAS
# ==========================================
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
print("RESULTADOS DEL TEST 04 (CON RAG)")
print("="*60)
print(f"Muestra evaluada: {len(y_pred_q)} tickets.")
print("\nDIMENSIÓN: QUEJA  | MAE: {:.2f} | Fallos Críticos: {:.1f}%".format(mae_q, fc_q))
print("DIMENSIÓN: RETRASO| MAE: {:.2f} | Fallos Críticos: {:.1f}%".format(mae_r, fc_r))
print("="*60)

informe_experimento = {
    "experimento": "Test 04: Evaluación con RAG (SQLite + Nomic)",
    "fecha": datetime.now().isoformat(),
    "latencia_media_ms": round(float(np.mean(latencias)), 2),
    "metricas_queja": {"MAE": round(mae_q, 3), "RMSE": round(rmse_q, 3), "Acc_tol_1": round(acc_q, 2), "QWK": round(kappa_q, 3), "Tasa_FC": round(fc_q, 2)},
    "metricas_retraso": {"MAE": round(mae_r, 3), "RMSE": round(rmse_r, 3), "Acc_tol_1": round(acc_r, 2), "QWK": round(kappa_r, 3), "Tasa_FC": round(fc_r, 2)}
}

with open(PATH_JSON_METRICAS, "w", encoding="utf-8") as f:
    json.dump(informe_experimento, f, indent=4, ensure_ascii=False)