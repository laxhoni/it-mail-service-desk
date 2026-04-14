import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix
import numpy as np

# ==========================================
# CONFIGURACIÓN DEL ENTORNO
# ==========================================
PATH_CSV_ENTRADA = "data/resultados_evaluacion.csv"
DIRECTORIO_SALIDA = "data/graficas/"

# Configuración visual global (Estilo profesional/académico)
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
    """Garantiza que el directorio de salida existe para evitar errores."""
    if not os.path.exists(ruta):
        os.makedirs(ruta)
        print(f"Directorio creado: {ruta}")

def graficar_matriz_confusion(df, col_real, col_pred, titulo, nombre_archivo, cmap):
    """
    Genera y guarda una Matriz de Confusión térmica de 10x10.
    Fuerza los ejes del 1 al 10 para evitar que desaparezcan categorías vacías.
    """
    plt.figure(figsize=(10, 8))
    
    # Aseguramos que la matriz sea siempre de 10x10 aunque falten números en la muestra
    etiquetas = list(range(1, 11))
    matriz = confusion_matrix(df[col_real], df[col_pred], labels=etiquetas)
    
    # Creamos el heatmap
    ax = sns.heatmap(
        matriz, 
        annot=True,        # Mostrar el número en cada celda
        fmt='d',           # Formato entero
        cmap=cmap,         # Paleta de colores
        cbar=True,         # Barra de leyenda
        xticklabels=etiquetas, 
        yticklabels=etiquetas,
        linewidths=.5,
        linecolor='gray'
    )
    
    plt.title(f"Matriz de Confusión: {titulo}", pad=20, fontweight='bold')
    plt.xlabel('Predicción de la IA (Llama 3.2)', fontweight='bold')
    plt.ylabel('Valor Real (Ground Truth)', fontweight='bold')
    
    # Guardamos la imagen
    ruta_guardado = os.path.join(DIRECTORIO_SALIDA, nombre_archivo)
    plt.savefig(ruta_guardado)
    plt.close()
    print(f"Gráfica guardada: {nombre_archivo}")

def graficar_distribucion_errores(df, col_error_q, col_error_r):
    """
    Genera un histograma superpuesto para ver el sesgo del modelo (Under/Over-estimation).
    """
    plt.figure(figsize=(12, 6))
    
    # Histograma para el Error de Queja
    sns.histplot(df[col_error_q], bins=range(-10, 11), color="blue", alpha=0.5, label="Error en Queja", kde=True)
    # Histograma para el Error de Retraso
    sns.histplot(df[col_error_r], bins=range(-10, 11), color="orange", alpha=0.5, label="Error en Retraso", kde=True)
    
    plt.axvline(0, color='red', linestyle='dashed', linewidth=2, label="Cero Error (Perfecto)")
    
    plt.title("Distribución de Errores de Predicción ($\Delta$ Real vs IA)", pad=20, fontweight='bold')
    plt.xlabel('Magnitud del Error (Predicción - Real)', fontweight='bold')
    plt.ylabel('Frecuencia (Nº de Tickets)', fontweight='bold')
    plt.legend()
    plt.xticks(range(-9, 10, 2))
    
    ruta_guardado = os.path.join(DIRECTORIO_SALIDA, "03_distribucion_errores.png")
    plt.savefig(ruta_guardado)
    plt.close()
    print(f"Gráfica guardada: 03_distribucion_errores.png")

# ==========================================
# FLUJO PRINCIPAL
# ==========================================
def main():
    print("Iniciando Visualizador Analítico de Métricas...")
    
    # 1. Preparación del entorno
    crear_directorio_si_no_existe(DIRECTORIO_SALIDA)
    
    # 2. Carga y validación de datos
    try:
        df = pd.read_csv(PATH_CSV_ENTRADA, delimiter=";")
        print(f"[*] Datos cargados con éxito: {len(df)} tickets.")
    except FileNotFoundError:
        print(f"[*] Error: No se encuentra el archivo {PATH_CSV_ENTRADA}. Ejecuta el evaluador primero.")
        return

    # Limpieza básica por si hay nulos (buenas prácticas)
    df = df.dropna(subset=['Queja_Real', 'Queja_Pred', 'Retraso_Real', 'Retraso_Pred'])
    
    # Convertimos a enteros para evitar errores gráficos
    df['Queja_Real'] = df['Queja_Real'].astype(int)
    df['Queja_Pred'] = df['Queja_Pred'].astype(int)
    df['Retraso_Real'] = df['Retraso_Real'].astype(int)
    df['Retraso_Pred'] = df['Retraso_Pred'].astype(int)

    # 3. Generación de las Gráficas
    print("\nGenerando representaciones visuales...")
    graficar_matriz_confusion(
        df, 'Queja_Real', 'Queja_Pred', 
        titulo="Dimensión 1 - Queja / Impacto", 
        nombre_archivo="01_matriz_confusion_queja.png", 
        cmap="Blues"
    )
    
    graficar_matriz_confusion(
        df, 'Retraso_Real', 'Retraso_Pred', 
        titulo="Dimensión 2 - Retraso / SLA", 
        nombre_archivo="02_matriz_confusion_retraso.png", 
        cmap="Oranges"
    )
    
    graficar_distribucion_errores(df, 'Error_Q', 'Error_R')
    
    print("\nProceso finalizado")

if __name__ == "__main__":
    main()