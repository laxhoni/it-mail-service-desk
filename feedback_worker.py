import os
import json
import sqlite3
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- CONFIGURACIÓN ---
# Asegúrate de que esta ruta es la de tu OneDrive sincronizado
RUTA_FEEDBACK = os.path.join(os.getenv("CARPETA_DOCS", "docs"), "Feedback_Queue")
# Al estar en la raíz, entramos a la carpeta 'data'
DB_PATH = os.path.join("data", "incidencias.db") 

class FeedbackHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".json"):
            print(f"📩 Feedback recibido: {os.path.basename(event.src_path)}")
            time.sleep(2) # Pausa de seguridad para sincronización
            self.actualizar_db(event.src_path)

    def actualizar_db(self, ruta_archivo):
        try:
            with open(ruta_archivo, 'r', encoding='utf-8') as f:
                d = json.load(f)
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE tickets 
                SET score_humano = ?, razonamiento_humano = ?, revisado = 1 
                WHERE id_mensaje = ?
            """, (int(d['nuevo_score']), d['razonamiento_humano'], d['id_mensaje']))
            
            conn.commit()
            conn.close()
            print(f"✅ DB actualizada para ticket: {d['id_mensaje']}")
            os.remove(ruta_archivo)
        except Exception as e:
            print(f"❌ Error procesando el archivo: {e}")

if __name__ == "__main__":
    if not os.path.exists(RUTA_FEEDBACK):
        os.makedirs(RUTA_FEEDBACK)
        
    observer = Observer()
    observer.schedule(FeedbackHandler(), RUTA_FEEDBACK, recursive=False)
    observer.start()
    
    print("-" * 30)
    print("🚀 WORKER 2: Sincronizador de Feedback")
    print(f"📂 Vigilando: {RUTA_FEEDBACK}")
    print(f"🗄️ Base de datos: {DB_PATH}")
    print("-" * 30)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()