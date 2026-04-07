import sqlite3
import random
import uuid
from datetime import datetime, timedelta
import os

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT_DIR, "data", "incidencias.db")

# 1. DICCIONARIO DE CASUÍSTICAS CORRELACIONADAS
CASUISTICAS = [
    # CRÍTICOS (Score 5) - Solo personal médico
    {
        "remitentes": ["Dr. Mendoza (Cirugía)", "Dra. Silva (Urgencias)", "Jefe de Planta UCI"],
        "asuntos": ["🚨 CAÍDA TOTAL SISTEMA QUIRÓFANO", "Error 504 historiales clínicos - URGENTE"],
        "cuerpos": [
            "Llevamos 20 minutos sin poder acceder a las pruebas del paciente. Tengo el quirófano parado. Solución ya.",
            "El sistema arroja error de timeout al intentar abrir el historial. Es inaceptable, los pacientes están esperando.",
            "Si no solucionan esto en 10 minutos, escalaré la queja a la gerencia del hospital."
        ],
        "score_ia": 5, "importancia": "alta",
        "razonamiento": "IA: Impacto crítico en operaciones clínicas. Riesgo vital y posible queja formal a gerencia."
    },
    # GRAVES (Score 4) - Enfermería y Admisión
    {
        "remitentes": ["Enfermería Planta 3", "Admisión Principal", "Farmacia Hospitalaria"],
        "asuntos": ["Impresora de pulseras no funciona", "No carga el módulo de dispensación"],
        "cuerpos": [
            "No podemos imprimir las pulseras de ingreso para los nuevos pacientes.",
            "El lector de códigos de barras de la farmacia no reconoce los medicamentos, por favor revisarlo rápido.",
            "La pantalla se queda en blanco tras el login."
        ],
        "score_ia": 4, "importancia": "alta",
        "razonamiento": "IA: Bloqueo operativo en procesos de planta/admisión. Afecta al flujo de pacientes."
    },
    # MEDIOS (Score 3) - Todos
    {
        "remitentes": ["RRHH", "Contabilidad", "Dr. López (Cardiología)"],
        "asuntos": ["Problema con el correo de Outlook", "Lentitud en la red WiFi"],
        "cuerpos": [
            "Llevo toda la mañana notando que los correos tardan mucho en salir.",
            "La conexión WiFi en mi despacho se cae constantemente.",
            "No me sincroniza el calendario en el móvil."
        ],
        "score_ia": 3, "importancia": "normal",
        "razonamiento": "IA: Degradación de servicio sin parada total. Molestia operativa."
    },
    # LEVES/RUIDO (Score 1-2) - Administración
    {
        "remitentes": ["RRHH", "Contabilidad", "Administración General"],
        "asuntos": ["Duda nómina", "Solicitud de ratón", "Cambio de contraseña"],
        "cuerpos": [
            "Hola, necesito un ratón inalámbrico nuevo porque el mío hace doble clic.",
            "Me avisa que la contraseña caduca mañana, ¿cómo la cambio?",
            "No puedo abrir un PDF que me han enviado."
        ],
        "score_ia": random.choice([1, 2]), "importancia": "normal",
        "razonamiento": "IA: Petición rutinaria de soporte o duda de ofimática. Cero impacto en el negocio."
    }
]

def generar_fecha_realista(dias_atras, hoy):
    """Genera fechas simulando horarios de oficina y picos los lunes."""
    fecha_base = hoy - timedelta(days=dias_atras)
    
    # Reducir drásticamente los tickets en fin de semana (sábado=5, domingo=6)
    if fecha_base.weekday() >= 5 and random.random() < 0.8:
        # Si es finde y cae en el 80%, lo movemos al lunes o viernes
        fecha_base += timedelta(days=random.choice([-1, 1, 2]))
        
    # Campana de Gauss para las horas (Media a las 11:00 AM, desviación de 3 horas)
    hora = int(random.gauss(11, 3))
    
    # Limitar las horas al rango de 24h
    hora = max(0, min(23, hora))
    minuto = random.randint(0, 59)
    segundo = random.randint(0, 59)
    
    return fecha_base.replace(hour=hora, minute=minuto, second=segundo).strftime("%Y-%m-%d %H:%M:%S")

def generar_mock_data(cantidad=500):
    print(f"🔄 Generando {cantidad} tickets hiperrealistas...")
    hoy = datetime.now()
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # Opcional: Limpiar la tabla antes de inyectar para empezar de cero
        cursor.execute("DELETE FROM tickets") 
        
        for _ in range(cantidad):
            id_mensaje = str(uuid.uuid4())
            dias_atras = random.randint(0, 90)
            fecha = generar_fecha_realista(dias_atras, hoy)
            
            # Elegir una casuística (30% críticas/graves, 70% leves/medias)
            tipo_incidencia = random.choices(CASUISTICAS, weights=[15, 15, 30, 40], k=1)[0]
            
            remitente = random.choice(tipo_incidencia["remitentes"])
            destinatario = "soporte@medtech.es"
            asunto = random.choice(tipo_incidencia["asuntos"])
            cuerpo = random.choice(tipo_incidencia["cuerpos"])
            importancia = tipo_incidencia["importancia"]
            score_ia = tipo_incidencia["score_ia"] if isinstance(tipo_incidencia["score_ia"], int) else random.choice([1, 2])
            razonamiento = tipo_incidencia["razonamiento"]
            
            # Lógica HITL Realista: Los graves se revisan SIEMPRE (100%), los leves a veces (60%)
            prob_revision = 1.0 if score_ia >= 4 else 0.6
            revisado = 1 if random.random() < prob_revision else 0
            
            score_humano = None
            if revisado == 1:
                prob_acierto = random.random()
                if prob_acierto < 0.85:
                    score_humano = score_ia # 85% Acierto perfecto
                elif prob_acierto < 0.95:
                    score_humano = min(5, max(1, score_ia + random.choice([-1, 1]))) # 10% Desviación de ±1
                else:
                    score_humano = min(5, max(1, score_ia + random.choice([-2, 2]))) # 5% Falla total
            
            cursor.execute('''
                INSERT INTO tickets (id_mensaje, fecha, remitente, destinatario, asunto, cuerpo, importancia, score, razonamiento, revisado, score_humano)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (id_mensaje, fecha, remitente, destinatario, asunto, cuerpo, importancia, score_ia, razonamiento, revisado, score_humano))
            
        conn.commit()
    print("✅ ¡Inyección hiperrealista completada! Tu Power BI va a quedar de cine.")

if __name__ == "__main__":
    generar_mock_data(500)