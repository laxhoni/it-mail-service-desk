import pandas as pd
import os
import time
import ollama
import json

# =================================================================
# 1. CONFIGURACIÓN DE RUTAS Y ENTORNO
# =================================================================
DIRECTORIO_SCRIPT = os.path.dirname(os.path.abspath(__file__))
DIRECTORIO_RAIZ = os.path.dirname(DIRECTORIO_SCRIPT)

PATH_DATASET = os.path.join(DIRECTORIO_RAIZ, "data", "processed", "dataset_validacion_tfg.csv")
PATH_CHECKPOINT = os.path.join(DIRECTORIO_RAIZ, "data", "processed", "progreso_llama_local.csv")

def cargar_datos():
    try:
        df = pd.read_csv(PATH_DATASET)
        print(f"[*] Dataset cargado: {len(df)} registros.")
        return df
    except FileNotFoundError:
        raise SystemExit(f"[*] ERROR: Dataset no encontrado en {PATH_DATASET}")

# =================================================================
# 2. LÓGICA DE CLASIFICACIÓN (MARCO DE CONTINUIDAD DE NEGOCIO)
# =================================================================
def clasificar_ticket_local(texto):
    """
    Utiliza un marco agnóstico de ITIL para evaluar el impacto en la continuidad
    del negocio, detectando incidentes técnicos y transiciones de servicio.
    """
    
    system_prompt = (
        "Actúa como un Gestor de Operaciones Digitales experto en ITIL v4. "
        "Tu misión es clasificar la urgencia (1 o 0) evaluando el impacto en la 'Continuidad de Servicio'.\n\n"
        
        "### MARCO DE EVALUACIÓN (3 PILARES DE URGENCIA 1):\n"
        "1. ESTADO DE OPERACIÓN: ¿Hay un fallo, error o degradación activa en un entorno real/producción? (Incidente).\n"
        "2. TRANSICIÓN DE SERVICIO: ¿El ticket menciona un despliegue, salida a producción ('Go-Live'), lanzamiento "
        "o cambio inminente? Las transiciones son hitos críticos de negocio.\n"
        "3. EXPANSIÓN DE INFRAESTRUCTURA: ¿Se trata de añadir nuevas sedes, bancos, sucursales o nodos al sistema principal?\n\n"
        
        "### LÓGICA DE EXCLUSIÓN (URGENCIA 0):\n"
        "- Consultas de información ('how to', 'query'), peticiones de archivos, dudas sobre configuraciones "
        "o errores en entornos de prueba (UAT/Test) sin impacto en el servicio real.\n\n"
        
        "IMPORTANTE: Responde siempre en español. No importa el idioma del ticket.\n"
        "RESPONDE ÚNICAMENTE EN ESTE FORMATO JSON:\n"
        "{\n"
        "  \"tipo_servicio\": \"Incidente / Transición / Petición\",\n"
        "  \"analisis_continuidad\": \"Analiza si afecta al flujo de valor o es un hito de negocio.\",\n"
        "  \"urgency_level\": 1 o 0\n"
        "}"
    )
    
    user_prompt = f"Ticket a evaluar:\n'''\n{texto}\n'''"
    
    try:
        response = ollama.generate(
            model='llama3.2', 
            prompt=f"{system_prompt}\n\n{user_prompt}", 
            format='json',
            options={
                'temperature': 0.1, 
                'num_predict': 400
            } 
        )
        
        res_raw = response['response'].strip()
        
        # Localizamos el bloque JSON para evitar texto extra del modelo
        start_idx = res_raw.find('{')
        end_idx = res_raw.rfind('}') + 1
        res_json = res_raw[start_idx:end_idx]
        
        # Forzamos interpretación correcta de caracteres (útil para tickets en árabe o con símbolos)
        datos_json = json.loads(res_json)
        
        # Construcción del razonamiento unificado
        tipo = datos_json.get('tipo_servicio', 'N/A')
        analisis = datos_json.get('analisis_continuidad', 'Sin análisis detallado')
        razonamiento = f"TIPO: {tipo} | ANÁLISIS: {analisis}"
        
        # Extracción segura de urgencia
        val_urg = datos_json.get('urgency_level')
        urgencia = 1 if str(val_urg) == '1' else 0
            
        return razonamiento, urgencia
        
    except Exception as e:
        return f"Error en inferencia/parseo: {str(e)}", None

# =================================================================
# 3. MOTOR DE EJECUCIÓN CON CHECKPOINTING
# =================================================================
df_master = cargar_datos()
# Tomamos una muestra para el experimento
df_experimento = df_master.sample(100, random_state=42).copy()

# Gestión del progreso para no repetir tickets
if os.path.exists(PATH_CHECKPOINT):
    df_progreso = pd.read_csv(PATH_CHECKPOINT)
    procesados_ids = df_progreso['id_original'].tolist()
    print(f"Reanudando desde checkpoint: {len(procesados_ids)} tickets ya procesados.")
else:
    df_progreso = pd.DataFrame(columns=['id_original', 'texto_limpio', 'es_urgente_real', 'prediccion_ia', 'razonamiento_ia'])
    df_progreso.to_csv(PATH_CHECKPOINT, index=False)
    procesados_ids = []

df_pendientes = df_experimento[~df_experimento.index.isin(procesados_ids)]
total_pendientes = len(df_pendientes)

print(f"Procesando {total_pendientes} tickets con Marco de Continuidad...\n" + "-"*50)

for i, (index, row) in enumerate(df_pendientes.iterrows()):
    inicio = time.time()
    
    # Ejecución de la IA
    razonamiento, prediccion = clasificar_ticket_local(str(row['texto_limpio']))
    
    tiempo = time.time() - inicio
    
    if prediccion is not None:
        # Guardado en el checkpoint (modo append para seguridad)
        nueva_fila = {
            'id_original': index,
            'texto_limpio': row['texto_limpio'],
            'es_urgente_real': row['es_urgente_real'],
            'prediccion_ia': prediccion,
            'razonamiento_ia': razonamiento
        }
        pd.DataFrame([nueva_fila]).to_csv(PATH_CHECKPOINT, mode='a', header=False, index=False)
        
        # Feedback visual en consola
        match = "✅" if prediccion == row['es_urgente_real'] else "❌"
        print(f"[{i+1}/{total_pendientes}] ID: {index} | Pred: {prediccion} vs Real: {row['es_urgente_real']} {match} ({tiempo:.1f}s)")
        print(f"    [*] {razonamiento[:120]}...")
    else:
        print(f"[*] Error en ticket ID {index}, saltando...")

print("-" * 50 + "\nProceso completado con éxito.")