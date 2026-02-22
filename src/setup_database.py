import sqlite3
import logging
from datetime import datetime
import os

DB_PATH = "data/incidencias.db"

def inicializar_db():
    if not os.path.exists("data"): os.makedirs("data")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Añadimos todas las columnas nuevas que vienen en tu JSON
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            remitente TEXT,
            destinatario TEXT,
            asunto TEXT,
            cuerpo TEXT,
            importancia TEXT,
            prediccion TEXT,
            score INTEGER,
            razonamiento TEXT,
            archivo TEXT,
            link_correo TEXT,
            id_mensaje TEXT
        )
    ''')
    conn.commit()
    conn.close()

def guardar_ticket(datos, res_ia, archivo):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO tickets (
                fecha, remitente, destinatario, asunto, cuerpo, importancia, 
                prediccion, score, razonamiento, archivo, link_correo, id_mensaje
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            datos.get('remitente', 'Desconocido'),
            datos.get('destinatario', 'Desconocido'),
            datos.get('asunto', 'Sin Asunto'),
            datos.get('cuerpo', ''),
            datos.get('importancia', 'Normal'),
            res_ia.get('prediccion', 'NO_QUEJA'),
            res_ia.get('score', 1),
            res_ia.get('razonamiento', 'Sin detalles'),
            archivo,
            datos.get('link_correo', ''),
            datos.get('id_mensaje', 'SIN_ID')
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"❌ Error DB: {e}")