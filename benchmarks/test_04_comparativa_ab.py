import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from sklearn.metrics import mean_absolute_error

# ==========================================
# CONFIGURACIÓN (RUTAS ROBUSTAS Y COLORES OFICIALES)
# ==========================================
DIRECTORIO_BASE = os.path.dirname(os.path.abspath(__file__))
PATH_CSV_BASE = os.path.join(DIRECTORIO_BASE, "data", "resultados_evaluacion.csv")
PATH_CSV_RAG = os.path.join(DIRECTORIO_BASE, "data", "resultados_evaluacion_rag.csv")
DIRECTORIO_SALIDA = os.path.join(DIRECTORIO_BASE, "data", "graficas_comparativas")

# Paleta EXTRAÍDA EXACTAMENTE de los cmaps "Blues" y "Oranges"
COLOR_QUEJA = '#4292c6'   # Tono medio-oscuro de matplotlib 'Blues'
COLOR_RETRASO = '#f16913' # Tono medio-oscuro de matplotlib 'Oranges'
PALETA_DIMENSIONES = [COLOR_QUEJA, COLOR_RETRASO]

sns.set_theme(style="whitegrid")
plt.rcParams.update({
    'font.size': 11,
    'axes.titlesize': 14,
    'axes.labelsize': 12,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight'
})

def crear_directorio_si_no_existe(ruta):
    if not os.path.exists(ruta):
        os.makedirs(ruta)

def calcular_metricas_locales(df, col_real, col_pred):
    mae = mean_absolute_error(df[col_real], df[col_pred])
    diff = np.abs(df[col_real] - df[col_pred])
    fallo_critico = np.mean(diff >= 3) * 100
    return mae, fallo_critico

# ==========================================
# FUNCIONES DE GRAFICADO
# ==========================================
def graficar_comparativa_por_dimension(metricas_base, metricas_rag, titulo, ylabel, filename):
    labels_modelos = ['Modelo Base\n(Sin Memoria)', 'Modelo + RAG\n(Con Memoria)']
    x = np.arange(len(labels_modelos))
    width = 0.35

    valores_queja = [metricas_base[0], metricas_rag[0]]
    valores_retraso = [metricas_base[1], metricas_rag[1]]

    fig, ax = plt.subplots(figsize=(8, 6))
    
    # Usamos los HEX exactos
    rects1 = ax.bar(x - width/2, valores_queja, width, label='Dimensión: Queja', color=COLOR_QUEJA, alpha=0.85, edgecolor='black')
    rects2 = ax.bar(x + width/2, valores_retraso, width, label='Dimensión: Retraso', color=COLOR_RETRASO, alpha=0.85, edgecolor='black')

    ax.set_ylabel(ylabel, fontweight='bold')
    ax.set_title(titulo, pad=20, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(labels_modelos, fontweight='bold')
    ax.legend()

    for rects in [rects1, rects2]:
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height:.2f}',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points",
                        ha='center', va='bottom', fontweight='bold')

    plt.savefig(os.path.join(DIRECTORIO_SALIDA, filename))
    plt.close()

# ==========================================
# FLUJO PRINCIPAL
# ==========================================
print("Iniciando Análisis Comparativo A/B con Paleta Cmap Exacta...")
crear_directorio_si_no_existe(DIRECTORIO_SALIDA)

try:
    df_base = pd.read_csv(PATH_CSV_BASE, delimiter=";")
    df_rag = pd.read_csv(PATH_CSV_RAG, delimiter=";")
    
    df_fusion = pd.merge(df_base, df_rag, on='ID_Ticket', suffixes=('_BASE', '_RAG'))
    print(f"[*] Dataset alineado: {len(df_fusion)} tickets comparables.")
except Exception as e:
    print(f"[*] Error al cargar datos: {e}")
    exit()

# 1. Extraer métricas
mae_q_b, fc_q_b = calcular_metricas_locales(df_fusion, 'Queja_Real_BASE', 'Queja_Pred_BASE')
mae_q_r, fc_q_r = calcular_metricas_locales(df_fusion, 'Queja_Real_RAG', 'Queja_Pred_RAG')

mae_r_b, fc_r_b = calcular_metricas_locales(df_fusion, 'Retraso_Real_BASE', 'Retraso_Pred_BASE')
mae_r_r, fc_r_r = calcular_metricas_locales(df_fusion, 'Retraso_Real_RAG', 'Retraso_Pred_RAG')

# 2. Gráficas de Barras (MAE y Fallos Críticos)
print("[*] Generando gráficos de barras...")
graficar_comparativa_por_dimension(
    [mae_q_b, mae_r_b], [mae_q_r, mae_r_r],
    "Impacto del RAG: Reducción del Error Absoluto Medio (MAE)",
    "MAE (Menor es mejor)",
    "01_comparativa_mae.png"
)

graficar_comparativa_por_dimension(
    [fc_q_b, fc_r_b], [fc_q_r, fc_r_r],
    "Impacto del RAG: Tasa de Fallos Críticos (Error ≥ 3)",
    "Porcentaje de tickets con fallo grave (%)",
    "02_comparativa_fallos_criticos.png"
)

# 3. Boxplot de Estabilidad (El gráfico más determinante)
print("[*] Generando análisis de estabilidad (Boxplot)...")
plt.figure(figsize=(10, 6))

errores_data = {
    'Modelo': (['1. Modelo Base']*len(df_fusion)*2) + (['2. Modelo RAG']*len(df_fusion)*2),
    'Dimensión': (['Queja']*len(df_fusion) + ['Retraso']*len(df_fusion)) * 2,
    'Error_Absoluto': np.concatenate([
        np.abs(df_fusion['Queja_Pred_BASE'] - df_fusion['Queja_Real_BASE']),
        np.abs(df_fusion['Retraso_Pred_BASE'] - df_fusion['Retraso_Real_BASE']),
        np.abs(df_fusion['Queja_Pred_RAG'] - df_fusion['Queja_Real_RAG']),
        np.abs(df_fusion['Retraso_Pred_RAG'] - df_fusion['Retraso_Real_RAG'])
    ])
}
df_err = pd.DataFrame(errores_data)

sns.boxplot(x='Modelo', y='Error_Absoluto', hue='Dimensión', data=df_err, palette=PALETA_DIMENSIONES, showmeans=True, meanprops={"marker":"o", "markerfacecolor":"white", "markeredgecolor":"black"})

plt.title("Estabilidad del Sistema: Dispersión del Error por Modelo", fontweight='bold', pad=20)
plt.ylabel("Magnitud del Error Absoluto", fontweight='bold')
plt.xlabel("")
plt.legend(title="Dimensión Evaluada")
plt.savefig(os.path.join(DIRECTORIO_SALIDA, "03_boxplot_estabilidad.png"))
plt.close()

# 4. Gráfica de Rendimiento (Latencia) - Mantenemos los grises para no confundir
print("[*] Generando análisis de rendimiento...")
lat_b = df_fusion['Latencia_ms_BASE'].mean()
lat_r = df_fusion['Latencia_ms_RAG'].mean()

plt.figure(figsize=(6, 5))
barras = plt.bar(['Modelo Base', 'Modelo + RAG'], [lat_b, lat_r], color=['#95a5a6', '#34495e'], edgecolor='black', alpha=0.9)
plt.title("Trade-off de Rendimiento: Tiempo Medio de Inferencia", pad=20, fontweight='bold')
plt.ylabel("Milisegundos (ms) por Ticket", fontweight='bold')

for bar in barras:
    yval = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2, yval + (yval*0.02), f"{int(yval)} ms", ha='center', va='bottom', fontweight='bold')

plt.savefig(os.path.join(DIRECTORIO_SALIDA, "04_comparativa_latencia.png"))
plt.close()

print(f"\nVisualizaciones terminadas.")