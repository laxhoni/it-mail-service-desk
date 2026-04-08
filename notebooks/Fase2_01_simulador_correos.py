import os
import json
import time
import random
from datetime import datetime
from email.message import EmailMessage
import ollama

# =================================================================
# 1. CONFIGURACIÓN
# =================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
PATH_OUTPUT_DIR = os.path.join(ROOT_DIR, "data", "raw", "eml_simulados")

os.makedirs(PATH_OUTPUT_DIR, exist_ok=True)

# =================================================================
# 2. PROMPT AVANZADO (Casuísticas de Hilos y Firmas)
# =================================================================
def inventar_correo_complejo(es_queja):
    
    # Configuramos el tono según si queremos queja o no
    if es_queja:
        contexto = "un SCORE de 5/5. Estás MUY frustrado. Hay un bloqueo crítico (ej. VPN caída, ERP no funciona, cuenta bloqueada). Usa lenguaje de urgencia y queja formal."
        asunto_prefijo = random.choice(["RE: URGENTE:", "FW: INCIDENCIA CRÍTICA -", "RE: "])
    else:
        contexto = "un SCORE de 1/5 o 2/5. Estás tranquilo. Es una simple duda, un agradecimiento por resolver un ticket anterior, o pedir un acceso rutinario."
        asunto_prefijo = random.choice(["RE: Solucionado -", "Duda sobre", "FW: Acceso a "])

    system_prompt = f"""
    Eres un empleado de un banco escribiendo un correo al IT Service Desk en Español.
    Tienes {contexto}
    
    REQUISITOS OBLIGATORIOS DEL CUERPO DEL CORREO (CASUÍSTICAS):
    1. FIRMA CORPORATIVA: Al final de tu mensaje, incluye una firma corporativa larga (Nombre, Cargo, Departamento, Aviso de Confidencialidad largo).
    2. HILO ANIDADO: Debajo de tu firma, SIMULA que estás respondiendo a un hilo. Usa separadores como "----- Mensaje Original -----" o "De: ... Para: ... Fecha: ...", e inventa el mensaje anterior (ej. un compañero que te reenvió el error o un técnico de IT que te pidió datos).
    3. MENCIÓN DE ADJUNTO: Menciona en tu texto que adjuntas una captura o un documento.
    
    RESPONDE ÚNICAMENTE EN JSON:
    {{
        "remitente_nombre": "Nombre Apellido",
        "remitente_email": "usuario@banco.com",
        "asunto": "{asunto_prefijo} [Tema inventado]",
        "cuerpo": "Tu mensaje actual\\n\\nFirma Corporativa...\\n\\n----- Mensaje Original -----\\nDe: ...\\nAsunto: ...\\n[Mensaje antiguo]",
        "nombre_adjunto": "captura_pantalla_error.png"
    }}
    """
    
    try:
        response = ollama.generate(
            model='llama3.2',
            prompt=system_prompt,
            format='json',
            options={'temperature': 0.7}
        )
        return json.loads(response['response'])
    except Exception as e:
        print(f"⚠️ Error en LLM: {e}")
        return None

# =================================================================
# 3. EMPAQUETADOR MIME (Crea el .eml real con adjuntos)
# =================================================================
def crear_archivo_eml(datos_llm, id_ticket):
    msg = EmailMessage()
    
    # Cabeceras estándar
    msg['Subject'] = datos_llm.get('asunto', f'Ticket {id_ticket}')
    msg['From'] = f"{datos_llm.get('remitente_nombre', 'Usuario')} <{datos_llm.get('remitente_email', 'usuario@banco.com')}>"
    msg['To'] = "it-servicedesk@banco.com"
    msg['Date'] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0100")
    
    # Añadimos el cuerpo del texto (con hilos y firmas)
    msg.set_content(datos_llm.get('cuerpo', ''))
    
    # INYECTAMOS UN ADJUNTO FALSO REAL (Simulamos un archivo binario/texto)
    nombre_adj = datos_llm.get('nombre_adjunto', 'log_error.txt')
    contenido_falso = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xFF\xFF\x00\x00\xb8\x00\x00\x00" # Cabecera binaria falsa
    
    msg.add_attachment(
        contenido_falso, 
        maintype='application', 
        subtype='octet-stream', 
        filename=nombre_adj
    )
        
    # Guardar archivo .eml
    ruta_archivo = os.path.join(PATH_OUTPUT_DIR, f"{id_ticket}.eml")
    with open(ruta_archivo, 'wb') as f:
        f.write(msg.as_bytes())
        
    return ruta_archivo

# =================================================================
# 4. MOTOR PRINCIPAL (5 Quejas, 5 No-Quejas)
# =================================================================
def ejecutar_pipeline_simulacion():
    print("🚀 Fabricando 10 correos .EML complejos (Hilos anidados + Adjuntos)...\n" + "-"*50)
    
    # Definimos la lista exacta: 5 quejas (True) y 5 no-quejas (False)
    casuisticas = [True]*5 + [False]*5
    random.shuffle(casuisticas) # Los mezclamos para que no vayan en orden
    
    for i, es_queja in enumerate(casuisticas):
        tipo_str = "🤬 QUEJA" if es_queja else "😊 NO QUEJA"
        id_ticket = f"TKT-2026-C{1000 + i}"
        
        print(f"[{i+1}/10] Generando {tipo_str}...")
        datos = inventar_correo_complejo(es_queja)
        
        if datos:
            ruta = crear_archivo_eml(datos, id_ticket)
            print(f"   ✅ Guardado: {id_ticket}.eml 📎 (Asunto: {datos['asunto'][:30]}...)")
        else:
            print("   ❌ Fallo al generar este correo.")

    print("\n" + "="*50)
    print(f"💾 Archivos .eml listos en: {PATH_OUTPUT_DIR}")

if __name__ == "__main__":
    ejecutar_pipeline_simulacion()