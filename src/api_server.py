from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import logging

# Configuración de logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [API] - %(levelname)s - %(message)s')

app = FastAPI(title="Webhook Teams -> RAG")
DB_PATH = "data/incidencias.db"

# Definimos el formato exacto que esperamos recibir de Power Automate
class FeedbackTeams(BaseModel):
    id_mensaje: str
    nuevo_score: int
    razonamiento_humano: str

@app.post("/webhook/feedback")
async def recibir_feedback(datos: FeedbackTeams):
    """Recibe la corrección desde Teams y actualiza la Base de Datos RAG"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Actualizamos la memoria del RAG
        cursor.execute("""
            UPDATE tickets 
            SET score_humano = ?, razonamiento_humano = ?, revisado = 1 
            WHERE id_mensaje = ?
        """, (datos.nuevo_score, datos.razonamiento_humano, datos.id_mensaje))
        
        if cursor.rowcount == 0:
            conn.close()
            logging.warning(f"⚠️ Ticket {datos.id_mensaje} no encontrado en BD.")
            raise HTTPException(status_code=404, detail="Ticket no encontrado")

        conn.commit()
        conn.close()
        
        logging.info(f"✅ ¡RAG Actualizado! Ticket {datos.id_mensaje} ahora es Score {datos.nuevo_score}")
        return {"status": "success", "message": "Feedback procesado e inyectado en RAG"}
        
    except Exception as e:
        logging.error(f"❌ Error en BD: {e}")
        raise HTTPException(status_code=500, detail=str(e))