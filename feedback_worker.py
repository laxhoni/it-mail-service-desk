import os
import json
import sqlite3
import time
import logging

# --- CONFIGURACIÓN ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [FEEDBACK] - %(levelname)s - %(message)s')

BASE_DOCS = os.getenv("CARPETA_DOCS", "docs")
RUTA_FEEDBACK = os.path.join(BASE_DOCS, "Feedback_Queue")
DB_PATH = os.path.join("data", "incidencias.db") 

def procesar_archivo(ruta_archivo):
    try:
        # Intentamos leer el archivo
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        id_msg = data.get('id_mensaje')
        score = data.get('nuevo_score')
        razonamiento = data.get('razonamiento_humano', 'Sin comentarios')

        if not id_msg or score is None:
            logging.warning(f"⚠️ Archivo mal formado: {os.path.basename(ruta_archivo)}")
            return False

        # Actualizar Base de Datos
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tickets 
            SET score_humano = ?, razonamiento_humano = ?, revisado = 1 
            WHERE id_mensaje = ?
        """, (int(score), razonamiento, id_msg))
        
        filas_afectadas = cursor.rowcount
        conn.commit()
        conn.close()

        if filas_afectadas > 0:
            logging.info(f"✅ DB actualizada para ticket: {id_msg}")
            return True
        else:
            logging.error(f"❓ No se encontró el ID {id_msg} en la base de datos.")
            return True # Retornamos True para que borre el archivo aunque no lo encuentre (archivo huérfano)

    except Exception as e:
        logging.error(f"❌ Error procesando {os.path.basename(ruta_archivo)}: {e}")
        return False

def ejecutar_feedback_worker():
    if not os.path.exists(RUTA_FEEDBACK): os.makedirs(RUTA_FEEDBACK)
    
    logging.info("-" * 50)
    logging.info("🚀 WORKER 2 INICIADO - Escaneando Feedback 24/7...")
    logging.info(f"📂 Vigilando: {RUTA_FEEDBACK}")
    logging.info("-" * 50)

    while True:
        # Listar archivos JSON en la carpeta
        archivos = [f for f in os.listdir(RUTA_FEEDBACK) if f.endswith('.json')]
        
        for nombre_archivo in archivos:
            ruta_completa = os.path.join(RUTA_FEEDBACK, nombre_archivo)
            
            # Intentar procesar
            exito = procesar_archivo(ruta_completa)
            
            if exito:
                # Si se procesó bien, lo borramos igual que el worker normal mueve archivos
                try:
                    os.remove(ruta_completa)
                    logging.info(f"🗑️ Archivo eliminado: {nombre_archivo}")
                except Exception as e:
                    logging.error(f"No se pudo eliminar el archivo: {e}")
        
        # Esperar 5 segundos antes de la siguiente vuelta (igual que Worker 1)
        time.sleep(5)

if __name__ == "__main__":
    ejecutar_feedback_worker()