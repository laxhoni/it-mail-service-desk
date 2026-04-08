import pandas as pd
import os

# =================================================================
# 1. RUTAS DINÁMICAS
# =================================================================
DIRECTORIO_SCRIPT = os.path.dirname(os.path.abspath(__file__))
DIRECTORIO_RAIZ = os.path.dirname(DIRECTORIO_SCRIPT)

# Apuntamos al archivo que generó tu script de pruebas
ARCHIVO_RESULTADOS = os.path.join(DIRECTORIO_RAIZ, "data", "processed", "lab_prompts_airlines.csv")

# Archivo final limpio que guardaremos como anexo para tu TFG
ARCHIVO_FINAL = os.path.join(DIRECTORIO_RAIZ, "data", "processed", "evaluacion_quejas_final.csv")

print("📊 Evaluando el rendimiento de Llama 3.2 (Detección de Quejas)...\n")

try:
    # Leemos los resultados
    df = pd.read_csv(ARCHIVO_RESULTADOS)
    
    # Aseguramos que las columnas sean booleanas (True/False) para evitar errores lógicos
    df['es_queja_real'] = df['es_queja_real'].astype(bool)
    df['es_queja_ia'] = df['es_queja_ia'].astype(bool)
    
    # =================================================================
    # 2. CÁLCULO DE MÉTRICAS BASE (Matriz de Confusión)
    # =================================================================
    total = len(df)
    
    # Verdaderos Positivos (TP): Era queja y la IA dijo queja
    tp = ((df['es_queja_real'] == True) & (df['es_queja_ia'] == True)).sum()
    
    # Verdaderos Negativos (TN): NO era queja y la IA dijo NO_QUEJA
    tn = ((df['es_queja_real'] == False) & (df['es_queja_ia'] == False)).sum()
    
    # Falsos Positivos (FP): IA ve enfado donde no lo hay
    fp = ((df['es_queja_real'] == False) & (df['es_queja_ia'] == True)).sum()
    
    # Falsos Negativos (FN): IA ignora la frustración real
    fn = ((df['es_queja_real'] == True) & (df['es_queja_ia'] == False)).sum()
    
    # =================================================================
    # 3. MÉTRICAS ACADÉMICAS AVANZADAS (Para el Tribunal del TFG)
    # =================================================================
    accuracy = ((tp + tn) / total) * 100
    
    # Precision: De todas las que la IA dijo "Es Queja", ¿cuántas lo eran realmente?
    precision = (tp / (tp + fp)) * 100 if (tp + fp) > 0 else 0
    
    # Recall (Sensibilidad): De todas las quejas reales que había, ¿cuántas cazó la IA?
    recall = (tp / (tp + fn)) * 100 if (tp + fn) > 0 else 0
    
    # F1-Score: La media armónica entre Precision y Recall (La métrica rey)
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    # =================================================================
    # 4. REPORTE FINAL
    # =================================================================
    print(f"✅ Se han evaluado {total} tickets procesados en local.")
    print("=" * 50)
    print(f"🎯 ACCURACY GLOBAL: {accuracy:.2f}% ({tp+tn}/{total} aciertos)")
    print("-" * 50)
    print("MATRIZ DE CONFUSIÓN:")
    print(f" ✔️ Verdaderos Positivos (Quejas cazadas) : {tp}")
    print(f" ✔️ Verdaderos Negativos (Dudas filtradas): {tn}")
    print(f" 🚨 Falsos Positivos (IA se asustó)       : {fp}")
    print(f" 💤 Falsos Negativos (IA no lo vio)       : {fn}")
    print("-" * 50)
    print("MÉTRICAS ACADÉMICAS (Menciónalas en la memoria):")
    print(f" 🔹 Precisión (Precision) : {precision:.2f}%")
    print(f" 🔹 Sensibilidad (Recall) : {recall:.2f}%")
    print(f" 🏆 F1-Score              : {f1_score:.2f}%")
    print("=" * 50)

    # Exportamos el archivo limpio para anexar al TFG
    df.to_csv(ARCHIVO_FINAL, index=False, encoding='utf-8')
    print(f"💾 Archivo de evaluación guardado para anexos en:\n{ARCHIVO_FINAL}")

except FileNotFoundError:
    print(f"❌ ERROR: No encuentro el archivo '{ARCHIVO_RESULTADOS}'. Revisa dónde se guardó.")
except Exception as e:
    print(f"⚠️ Error inesperado al calcular: {e}")
    