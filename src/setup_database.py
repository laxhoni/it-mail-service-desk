import sqlite3
import os
import json
from datetime import datetime
import logging

DB_PATH = os.path.join("data", "incidencias.db")

def inicializar_db():
    """Crea la base de datos y añade columnas de feedback si faltan."""
    if not os.path.exists("data"):
        os.makedirs("data")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Crear tabla con el esquema completo (AÑADIDAS COLUMNAS DE DOBLE VALIDACIÓN)
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
            id_mensaje TEXT UNIQUE,
            embedding_vector TEXT,
            score_humano INTEGER,
            razonamiento_humano TEXT,
            revisado INTEGER DEFAULT 0,
            nivel_queja INTEGER,
            nivel_retraso INTEGER,
            nivel_queja_humano INTEGER,
            nivel_retraso_humano INTEGER
        )
    ''')

    # Migración: Añadir columnas por si la DB ya existía (AÑADIDOS NUEVOS CAMPOS AQUÍ)
    columnas = [
        ("score_humano", "INTEGER"),
        ("razonamiento_humano", "TEXT"),
        ("revisado", "INTEGER DEFAULT 0"),
        ("embedding_vector", "TEXT"),
        ("nivel_queja", "INTEGER"),
        ("nivel_retraso", "INTEGER"),
        ("nivel_queja_humano", "INTEGER"),
        ("nivel_retraso_humano", "INTEGER")
    ]
    for col, tipo in columnas:
        try:
            cursor.execute(f"ALTER TABLE tickets ADD COLUMN {col} {tipo}")
        except sqlite3.OperationalError:
            pass 

    conn.commit()
    conn.close()
    logging.info("🗄️ Base de datos inicializada y esquema verificado con doble validación.")

def guardar_ticket(datos, res_ia, archivo, vector_embedding):
    """Guarda el análisis de la IA en la base de datos."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        vector_str = json.dumps(vector_embedding) if vector_embedding else "[]"
        
        # AÑADIDOS nivel_queja y nivel_retraso en el INSERT
        cursor.execute('''
            INSERT OR IGNORE INTO tickets (
                fecha, remitente, destinatario, asunto, cuerpo, importancia, 
                prediccion, score, razonamiento, archivo, link_correo, id_mensaje, embedding_vector,
                nivel_queja, nivel_retraso
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            datos.get('id_mensaje', 'SIN_ID'),
            vector_str,
            res_ia.get('nivel_queja', 1),     # NUEVO: Guarda predicción IA
            res_ia.get('nivel_retraso', 1)    # NUEVO: Guarda predicción IA
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"❌ Error al guardar en DB: {e}")