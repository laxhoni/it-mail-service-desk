import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix
import numpy as np

# ==========================================
# CONFIGURACIÓN DEL ENTORNO (RUTAS ROBUSTAS)
# ==========================================
DIRECTORIO_BASE = os.path.dirname(os.path.abspath(__file__))
PATH_CSV_ENTRADA = os.path.join(DIRECTORIO_BASE, "data", "resultados_evaluacion_rag.csv")
DIRECTORIO_SALIDA = os.path.join(DIRECTORIO_BASE, "data", "graficas_rag")

# Configuración visual global (IDÉNTICA AL TEST 03)
sns.set_theme(style="whitegrid")
plt.rcParams.update({
    'font.size': 12,
    'axes.titlesize': 16,
    'axes.labelsize': 14,
    'figure.dpi': 300, 
    'savefig.dpi': 300,
    'savefig.bbox': 'tight'
})

def crear_directorio_si_no_existe(ruta):
    if not os.path.exists(ruta):
        os.makedirs(ruta)
        print(f"[*] Directorio de gráficas RAG creado en: {ruta}")

def graficar_matriz_confusion(df, col_real, col_pred, titulo, nombre_archivo, cmap):
    """Genera la matriz de confusión con el formato exacto del Test 03."""
    plt.figure(figsize=(10, 8))
    
    etiquetas = list(range(1, 11))
    matriz = confusion_matrix(df[col_real], df[col_pred], labels=etiquetas)
    
    ax = sns.heatmap(
        matriz, 
        annot=True,        
        fmt='d',           
        cmap=cmap,         
        cbar=True,         
        xticklabels=etiquetas, 
        yticklabels=etiquetas,
        linewidths=.5,
        linecolor='gray'
    )
    
    plt.title(f"Matriz de Confusión RAG: {titulo}", pad=20, fontweight='bold')
    plt.xlabel('Predicción de la IA (Llama 3.2 + RAG)', fontweight='bold')
    plt.ylabel('Valor Real (Ground Truth)', fontweight='bold')
    
    ruta_guardado = os.path.join(DIRECTORIO_SALIDA, nombre_archivo)
    plt.savefig(ruta_guardado)
    plt.close()
    print(f"[*] Gráfica guardada: {nombre_archivo}")

def graficar_distribucion_errores(df, col_error_q, col_error_r):
    """
    Genera el histograma superpuesto usando los colores ORIGINALES (Azul y Naranja).
    """
    plt.figure(figsize=(12, 6))
    
    # Azul para Queja (Mismo que Test 03)
    sns.histplot(df[col_error_q], bins=range(-10, 11), color="blue", alpha=0.5, label="Error en Queja (RAG)", kde=True)
    # Naranja para Retraso (Mismo que Test 03)
    sns.histplot(df[col_error_r], bins=range(-10, 11), color="orange", alpha=0.5, label="Error en Retraso (RAG)", kde=True)
    
    plt.axvline(0, color='red', linestyle='dashed', linewidth=2, label="Cero Error (Perfecto)")
    
    plt.title("Distribución de Errores con RAG ($\Delta$ Real vs IA)", pad=20, fontweight='bold')
    plt.xlabel('Magnitud del Error (Predicción - Real)', fontweight='bold')
    plt.ylabel('Frecuencia (Nº de Tickets)', fontweight='bold')
    plt.legend()
    plt.xticks(range(-9, 10, 2))
    
    ruta_guardado = os.path.join(DIRECTORIO_SALIDA, "03_distribucion_errores_rag.png")
    plt.savefig(ruta_guardado)
    plt.close()
    print(f"✅ Gráfica guardada: 03_distribucion_errores_rag.png")

# ==========================================
# FLUJO PRINCIPAL
# ==========================================
def main():
    print("Iniciando Visualizador Analítico RAG (Esquema de Colores Consistente)...")
    
    crear_directorio_si_no_existe(DIRECTORIO_SALIDA)
    
    try:
        df = pd.read_csv(PATH_CSV_ENTRADA, delimiter=";")
        print(f"[*] Datos RAG cargados: {len(df)} tickets.")
    except FileNotFoundError:
        print(f"[*] Error: No se encuentra el archivo {PATH_CSV_ENTRADA}.")
        return

    # Limpieza y conversión
    df = df.dropna(subset=['Queja_Real', 'Queja_Pred', 'Retraso_Real', 'Retraso_Pred'])
    for col in ['Queja_Real', 'Queja_Pred', 'Retraso_Real', 'Retraso_Pred']:
        df[col] = df[col].astype(int)

    # Generación de las Gráficas
    graficar_matriz_confusion(
        df, 'Queja_Real', 'Queja_Pred', 
        titulo="Dimensión 1 - Queja / Impacto", 
        nombre_archivo="01_matriz_confusion_queja_rag.png", 
        cmap="Blues" # Mismo azul térmico
    )
    
    graficar_matriz_confusion(
        df, 'Retraso_Real', 'Retraso_Pred', 
        titulo="Dimensión 2 - Retraso / SLA", 
        nombre_archivo="02_matriz_confusion_retraso_rag.png", 
        cmap="Oranges" # Mismo naranja térmico
    )
    
    graficar_distribucion_errores(df, 'Error_Q', 'Error_R')
    
    print(f"\nVisualización RAG finalizada.")

if __name__ == "__main__":
    main()