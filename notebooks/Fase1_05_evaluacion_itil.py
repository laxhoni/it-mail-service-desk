import pandas as pd
import os

# =================================================================
# 1. RUTAS DINÁMICAS (Igual que en el script de generación)
# =================================================================
DIRECTORIO_SCRIPT = os.path.dirname(os.path.abspath(__file__))
DIRECTORIO_RAIZ = os.path.dirname(DIRECTORIO_SCRIPT)

# Archivo que acaba de generar Llama 3.2
ARCHIVO_RESULTADOS = os.path.join(DIRECTORIO_RAIZ, "data", "processed", "progreso_llama_local.csv")
# Si el archivo anterior te falló y lo guardaste en la raíz, descomenta esta línea:
# ARCHIVO_RESULTADOS = os.path.join(DIRECTORIO_RAIZ, "progreso_llama_local.csv")

# Archivo final limpio que guardaremos para tu TFG
ARCHIVO_FINAL = os.path.join(DIRECTORIO_RAIZ, "data", "processed", "evaluacion_llama_final.csv")

print("Evaluando el rendimiento de Llama 3.2 (Sentimiento/Quejas)...\n")

try:
    # Leemos los resultados
    # Asumimos columnas: id_original, texto_limpio, es_urgente_real, prediccion_ia
    df = pd.read_csv(ARCHIVO_RESULTADOS)
    
    # Aseguramos que las columnas clave son números
    df['es_urgente_real'] = pd.to_numeric(df['es_urgente_real'], errors='coerce')
    df['prediccion_ia'] = pd.to_numeric(df['prediccion_ia'], errors='coerce')
    df = df.dropna(subset=['es_urgente_real', 'prediccion_ia'])
    
    # =================================================================
    # 2. CÁLCULO DE MÉTRICAS
    # =================================================================
    total = len(df)
    aciertos = (df['es_urgente_real'] == df['prediccion_ia']).sum()
    accuracy = (aciertos / total) * 100
    
    # Falso Positivo: La IA dice que hay queja (1), pero era un ticket neutral (0)
    falsos_positivos = ((df['es_urgente_real'] == 0) & (df['prediccion_ia'] == 1)).sum()
    
    # Falso Negativo: La IA dice que es neutral (0), pero el cliente estaba enfadado (1)
    falsos_negativos = ((df['es_urgente_real'] == 1) & (df['prediccion_ia'] == 0)).sum()
    
    print(f"Se han evaluado {total} tickets procesados en local.")
    print("-" * 50)
    print(f"ACCURACY ZERO-SHOT (LLAMA 3.2): {accuracy:.2f}% ({aciertos}/{total})")
    print("-" * 50)
    print(f"Falsas Quejas (IA ve enfado donde no lo hay): {falsos_positivos}")
    print(f"Quejas Ignoradas (IA no detecta la frustración): {falsos_negativos}")
    print("-" * 50)

    # Exportamos el archivo limpio para anexar al TFG
    df.to_csv(ARCHIVO_FINAL, index=False, encoding='utf-8')
    print(f"Archivo final guardado en:\n{ARCHIVO_FINAL}")

except FileNotFoundError:
    print(f"[*] ERROR: No encuentro el archivo '{ARCHIVO_RESULTADOS}'.")
except Exception as e:
    print(f"[*] Error inesperado al calcular: {e}")