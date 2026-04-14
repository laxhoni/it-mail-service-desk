import os
import pandas as pd
import numpy as np
import re
import warnings

warnings.filterwarnings('ignore')

# =================================================================
# 1. CONFIGURACIÓN Y RUTAS (Dinámicas y Seguras)
# =================================================================
# Detecta dinámicamente dónde está este script y sube al directorio raíz
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..")) 

DATA_RAW = os.path.join(BASE_DIR, "data", "raw")
DATA_PROCESSED = os.path.join(BASE_DIR, "data", "processed")

# Crear carpetas si no existen
os.makedirs(DATA_RAW, exist_ok=True)
os.makedirs(DATA_PROCESSED, exist_ok=True)

# Definición de archivos
PATH_ISSUES = os.path.join(DATA_RAW, "issues.csv")
PATH_TEXTOS = os.path.join(DATA_RAW, "sample_utterances.csv")
PATH_EXCEL = os.path.join(DATA_RAW, "issues_snapshot_sample.xlsx")
PATH_OUTPUT = os.path.join(DATA_PROCESSED, "dataset_validacion_tfg.csv")

print(f"[*] Entorno listo.\n[*] Datos brutos en: {DATA_RAW}\n[*] Salida procesada en: {DATA_PROCESSED}")

# =================================================================
# 2. CARGA DE DATOS
# =================================================================
print("[*] Cargando datos...")

try:
    df_issues = pd.read_csv(PATH_ISSUES)
    df_textos = pd.read_csv(PATH_TEXTOS)
    # Nota: Para leer Excel local necesitas: pip install openpyxl
    df_sample = pd.read_excel(PATH_EXCEL)

    print(f"[*] Tickets (issues): {df_issues.shape[0]}")
    print(f"[*] Mensajes (textos): {df_textos.shape[0]}")
    print(f"[*] Evaluaciones Manager: {df_sample.shape[0]}")
except Exception as e:
    print(f"[*] Error al cargar archivos: {e}\n[*] Asegúrate de tener los archivos en la carpeta data/raw/")
    exit() # Detiene el script si no hay datos

# =================================================================
# 3. PREPROCESAMIENTO Y LIMPIEZA (NLP)
# =================================================================
# Filtrar mensajes del cliente (reporter)
df_clientes = df_textos[df_textos['author_role'] == 'reporter'].copy()

# Ordenar y limpiar
df_clientes = df_clientes.sort_values(by=['issueid', 'comment_seq', 'utr_seq'])
df_clientes = df_clientes.dropna(subset=['actionbody'])

# Quedarnos solo con el comment_seq == 0 (Apertura del ticket)
df_primer_contacto = df_clientes[df_clientes['comment_seq'] == 0]

# Agrupar mensajes fragmentados
df_textos_agrupados = df_primer_contacto.groupby('issueid')['actionbody'].apply(lambda x: ' \n '.join(x)).reset_index()
df_textos_agrupados.rename(columns={'actionbody': 'texto_cliente_completo'}, inplace=True)

print(f"[*] Tickets con correo de apertura reconstruido: {df_textos_agrupados.shape[0]}")

def limpiar_texto(texto):
    if not isinstance(texto, str): return ""
    
    texto = texto.lower()
    # Anonimización de placeholders
    texto = re.sub(r'ph_ip_address', '[IP]', texto)
    texto = re.sub(r'ph_user', '[USER]', texto)
    texto = re.sub(r'ph_technical', '[TECH_TERM]', texto)
    
    # Limpieza de espacios
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

df_textos_agrupados['texto_limpio'] = df_textos_agrupados['texto_cliente_completo'].apply(limpiar_texto)
print("[*] Texto normalizado para el LLM.")

# =================================================================
# 4. INTEGRACIÓN Y CREACIÓN DEL GROUND TRUTH (Verdad Absoluta)
# =================================================================
# Unir con información de prioridad y tiempos
df_master = pd.merge(df_textos_agrupados, 
                     df_issues[['id', 'issue_priority', 'issue_type', 'wf_total_time']], 
                     left_on='issueid', right_on='id', how='inner')

# Unir con notas del Manager para auditoría
if 'id' in df_sample.columns:
    df_master = pd.merge(df_master, df_sample[['id', 'Notes', 'Q1', 'Q2', 'Q3']], on='id', how='left')

df_master.drop(columns=['id'], inplace=True)
print(f"[*] Dataset integrado. Tamaño final: {df_master.shape}")

def asignar_urgencia_tfg(row):
    # Clase 1: Urgencia explícita
    if row['issue_priority'] in ['High', 'Highest', 'Blocker']:
        return 1
    
    # Clase Especial: Auditoría de Medium
    if row['issue_priority'] == 'Medium':
        # Si existe nota del manager, asumimos que requirió atención
        if pd.notnull(row['Notes']):
            return 1
            
    return 0

df_master['es_urgente_real'] = df_master.apply(asignar_urgencia_tfg, axis=1)

print("[*] Distribución de es_urgente_real:")
print(df_master['es_urgente_real'].value_counts(normalize=True) * 100)

# =================================================================
# 5. EXPORTACIÓN
# =================================================================
df_master.to_csv(PATH_OUTPUT, index=False, encoding='utf-8')
print(f"\nDataset guardado en: {PATH_OUTPUT}")
print("Todo listo para ejecutar el script de clasificación local.")