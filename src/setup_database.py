import sqlite3
import logging
from datetime import datetime

DB_PATH = "data/incidencias.db"

def inicializar_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            remitente TEXT,
            asunto TEXT,
            prediccion TEXT,
            score INTEGER,
            razonamiento TEXT,
            archivo TEXT
        )
    ''')
    conn.commit()
    conn.close()

def guardar_ticket(datos, res_ia, archivo):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Usamos .get() con valores por defecto para evitar que el script falle
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        remitente = datos.get('remitente', 'Desconocido')
        asunto = datos.get('asunto', 'Sin asunto')
        prediccion = res_ia.get('prediccion', 'ERROR')
        score = res_ia.get('score', 0)
        razonamiento = res_ia.get('razonamiento', 'Error en respuesta de IA')

        cursor.execute('''
            INSERT INTO tickets (fecha, remitente, asunto, prediccion, score, razonamiento, archivo)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (fecha, remitente, asunto, prediccion, score, razonamiento, archivo))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"❌ Error real en DB: {e}")