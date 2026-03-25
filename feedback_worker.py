import os
import json
import sqlite3
import time
import logging
import math # Añadido para el cálculo matemático

# --- CONFIGURACIÓN ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [FEEDBACK] - %(levelname)s - %(message)s')

BASE_DOCS = os.getenv("CARPETA_DOCS", "docs")
RUTA_FEEDBACK = os.path.join(BASE_DOCS, "Feedback_Queue")
DB_PATH = os.path.join("data", "incidencias.db")
CONFIG_PATH = os.path.join("data", "config", "config.json") # Ruta de los pesos

def obtener_pesos():
    """Lee los pesos actuales para calcular el Score Final humano."""
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                datos = json.load(f)
                return float(datos.get("peso_queja", 0.5)), float(datos.get("peso_retraso", 0.5))
    except Exception:
        pass
    return 0.5, 0.5 # Fallback de seguridad

def procesar_archivo(ruta_archivo):
    try:
        # Intentamos leer el archivo que manda Teams
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        id_msg = data.get('id_mensaje')
        # AHORA LEEMOS LAS DOS DIMENSIONES EN LUGAR DE UNA
        queja_humana = data.get('nivel_queja_humano')
        retraso_humano = data.get('nivel_retraso_humano')
        razonamiento = data.get('razonamiento_humano', 'Sin comentarios')

        if not id_msg or queja_humana is None or retraso_humano is None:
            logging.warning(f"⚠️ Archivo mal formado (Faltan dimensiones): {os.path.basename(ruta_archivo)}")
            return False

        # --- MATEMÁTICA: Calculamos el Score 1-5 final del humano ---
        peso_q, peso_r = obtener_pesos()
        score_combinado = (int(queja_humana) * peso_q) + (int(retraso_humano) * peso_r)
        score_humano_final = max(1, min(5, math.ceil(score_combinado / 2.0)))

        # --- Actualizar Base de Datos (Múltiples columnas) ---
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tickets 
            SET nivel_queja_humano = ?, 
                nivel_retraso_humano = ?, 
                score_humano = ?, 
                razonamiento_humano = ?, 
                revisado = 1 
            WHERE id_mensaje = ?
        """, (int(queja_humana), int(retraso_humano), score_humano_final, razonamiento, id_msg))
        
        filas_afectadas = cursor.rowcount
        conn.commit()
        conn.close()

        if filas_afectadas > 0:
            logging.info(f"✅ DB actualizada con Doble Validación para ticket: {id_msg}. Score Final: {score_humano_final}")
            return True
        else:
            logging.error(f"❓ No se encontró el ID {id_msg} en la base de datos.")
            return True # Retornamos True para que borre el archivo huérfano

    except Exception as e:
        logging.error(f"❌ Error procesando {os.path.basename(ruta_archivo)}: {e}")
        return False

def ejecutar_feedback_worker():
    if not os.path.exists(RUTA_FEEDBACK): os.makedirs(RUTA_FEEDBACK)
    
    logging.info("-" * 50)
    logging.info("🚀 WORKER 2 INICIADO - Escaneando Feedback Multidimensional 24/7...")
    logging.info(f"📂 Vigilando: {RUTA_FEEDBACK}")
    logging.info("-" * 50)

    while True:
        archivos = [f for f in os.listdir(RUTA_FEEDBACK) if f.endswith('.json')]
        
        for nombre_archivo in archivos:
            ruta_completa = os.path.join(RUTA_FEEDBACK, nombre_archivo)
            
            exito = procesar_archivo(ruta_completa)
            
            if exito:
                try:
                    os.remove(ruta_completa)
                    logging.info(f"🗑️ Archivo de feedback eliminado: {nombre_archivo}")
                except Exception as e:
                    logging.error(f"No se pudo eliminar el archivo: {e}")
        
        time.sleep(5)

if __name__ == "__main__":
    ejecutar_feedback_worker()