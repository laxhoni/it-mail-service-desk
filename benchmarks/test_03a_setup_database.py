import os
import sqlite3
import json
import csv
import requests
from datetime import datetime
from tqdm import tqdm

# ==========================================
# CONFIGURACIÓN
# ==========================================
CSV_ENTRADA = "data/auditoria_HITL_evaluado.csv"
CSV_TEST_SALIDA = "data/dataset_test_rag.csv"
DB_PATH = "data/incidencias_test.db"
URL_EMBEDDINGS = "http://localhost:11434/api/embeddings"
MODELO_EMBEDDING = "nomic-embed-text"

def inicializar_db():
    """Crea la base de datos con el esquema exacto de tu proyecto."""
    if not os.path.exists("data"):
        os.makedirs("data")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT, remitente TEXT, destinatario TEXT, asunto TEXT, cuerpo TEXT, importancia TEXT,
            prediccion TEXT, score INTEGER, razonamiento TEXT, archivo TEXT, link_correo TEXT, id_mensaje TEXT UNIQUE,
            embedding_vector TEXT, score_humano INTEGER, razonamiento_humano TEXT, revisado INTEGER DEFAULT 0,
            nivel_queja INTEGER, nivel_retraso INTEGER, nivel_queja_humano INTEGER, nivel_retraso_humano INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def obtener_embedding(texto):
    """Genera el vector matemático usando Ollama."""
    try:
        res = requests.post(URL_EMBEDDINGS, json={"model": MODELO_EMBEDDING, "prompt": texto}, stream=False)
        return res.json().get("embedding", [])
    except Exception as e:
        print(f"Error generando embedding: {e}")
        return []

def insertar_ticket_en_db(ticket):
    """Inserta el ticket en SQLite como historial validado."""
    texto_buscar = f"{ticket['Asunto']} {ticket['Cuerpo']}"
    vector = obtener_embedding(texto_buscar)
    
    if not vector:
        return False
        
    vector_str = json.dumps(vector)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tickets (
            fecha, asunto, cuerpo, embedding_vector, revisado,
            nivel_queja, nivel_retraso, nivel_queja_humano, nivel_retraso_humano
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ticket['Asunto'],
        ticket['Cuerpo'],
        vector_str,
        1, # Marcado como revisado por el Oráculo
        int(ticket['Queja_Target']), # Lo que predijo originalmente
        int(ticket['Retraso_Target']),
        int(ticket['Queja_Real_Humano']), # La Verdad Base definitiva
        int(ticket['Retraso_Real_Humano'])
    ))
    conn.commit()
    conn.close()
    return True

# ==========================================
# FLUJO DE EJECUCIÓN (SPLIT 50/50)
# ==========================================
print("Iniciando preparación de la Knowledge Base (RAG)...")

# 1. Leemos todos los tickets validados
tickets_totales = []
with open(CSV_ENTRADA, mode="r", encoding="utf-8") as f:
    reader = csv.DictReader(f, delimiter=";")
    for row in reader:
        if row.get("Queja_Real_Humano"):
            tickets_totales.append(row)

# 2. Separación (Data Split)
MITAD = len(tickets_totales) // 2
tickets_db = tickets_totales[:MITAD]
tickets_test = tickets_totales[MITAD:]

print(f"[*] Total tickets: {len(tickets_totales)}")
print(f"[*] Entrando a Base de Datos (Memoria): {len(tickets_db)} tickets")
print(f"[*] Reservados para el Test 04 (Inferencia): {len(tickets_test)} tickets")

# 3. Inicializar y Poblar BBDD
inicializar_db()

barra_db = tqdm(tickets_db, desc="Generando Embeddings y poblando SQLite", unit="ticket", colour="green")
for t in barra_db:
    insertar_ticket_en_db(t)

# 4. Guardar los tickets de Test en un nuevo CSV
with open(CSV_TEST_SALIDA, mode="w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=tickets_totales[0].keys(), delimiter=";")
    writer.writeheader()
    writer.writerows(tickets_test)

print(f"\nBase de datos vectorial lista en {DB_PATH}")
print(f"Dataset de evaluación guardado en {CSV_TEST_SALIDA}")