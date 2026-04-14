import pandas as pd
import os
import time
import ollama
import json
import re
import html

# =================================================================
# 1. CONFIGURACIÓN DEL LABORATORIO
# =================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

PATH_RAW = os.path.join(ROOT_DIR, "data", "raw", "Tweets.csv")
PATH_OUTPUT = os.path.join(ROOT_DIR, "data", "processed", "lab_prompts_airlines.csv")

def limpiar_tweet(texto):
    texto = html.unescape(texto)
    texto = re.sub(r'^@\w+\s*', '', texto)
    texto = re.sub(r'http\S+', '', texto)
    return texto.strip()

def preparar_datos_equilibrados():
    if not os.path.exists(PATH_RAW):
        raise FileNotFoundError(f"[*] No encuentro el archivo en {PATH_RAW}")
    
    print("[*] Cargando dataset Gold Standard (Airline Sentiment)...")
    df = pd.read_csv(PATH_RAW)
    
    # Mantenemos el tweet_id para saber cuáles hemos procesado
    df = df[['tweet_id', 'text', 'airline_sentiment']].dropna().copy()
    
    quejas = df[df['airline_sentiment'] == 'negative'].sample(50, random_state=42)
    no_quejas = df[df['airline_sentiment'].isin(['positive', 'neutral'])].sample(50, random_state=42)
    
    df_equilibrado = pd.concat([quejas, no_quejas]).sample(frac=1, random_state=42).reset_index(drop=True)
    return df_equilibrado

# =================================================================
# 2. ZONA DE PRUEBAS DE PROMPT
# =================================================================
def probar_prompt(texto):
    system_prompt = (
        "Eres un analista de soporte técnico. Tu única misión es detectar QUEJAS reales.\n"
        "REGLAS:\n"
        "1. Es una QUEJA (NEGATIVE) si el cliente exige soluciones, reporta un problema, "
        "retraso, mal servicio, o expresa sarcasmo y frustración.\n"
        "2. Es NO_QUEJA (POSITIVE o NEUTRAL) si es una simple duda, "
        "un agradecimiento, o un comentario sin problemas activos.\n\n"
        "RESPONDE ÚNICAMENTE EN JSON:\n"
        "{\n"
        "  \"prediccion\": \"NEGATIVE/NO_QUEJA\",\n"
        "  \"razonamiento\": \"Breve justificación de tu decisión\"\n"
        "}"
    )

    try:
        response = ollama.generate(
            model='llama3.2',
            prompt=f"{system_prompt}\n\nMensaje del cliente: {texto}",
            format='json',
            options={'temperature': 0.0}
        )
        return json.loads(response['response'])
    except Exception as e:
        print(f"[*] Error: {e}")
        return None

# =================================================================
# 3. MOTOR DE EJECUCIÓN CON CHECKPOINT (GUARDADO EN VIVO)
# =================================================================
def ejecutar_laboratorio():
    df_eval = preparar_datos_equilibrados()
    
    # --- LÓGICA DE CHECKPOINT ---
    if os.path.exists(PATH_OUTPUT):
        df_existente = pd.read_csv(PATH_OUTPUT)
        # Obtenemos la lista de IDs que ya están guardados
        procesados = df_existente['tweet_id'].tolist()
        print(f"[*] Checkpoint: {len(procesados)} tickets ya evaluados. Reanudando...")
    else:
        # Si no existe, creamos el archivo con las cabeceras
        columnas = ['tweet_id', 'texto', 'es_queja_real', 'es_queja_ia', 'match', 'razonamiento']
        pd.DataFrame(columns=columnas).to_csv(PATH_OUTPUT, index=False)
        procesados = []

    # Filtramos para quedarnos solo con los que no hemos procesado
    df_pendientes = df_eval[~df_eval['tweet_id'].isin(procesados)]
    total = len(df_pendientes)
    
    if total == 0:
        print("[*] Todos los tickets de la muestra ya han sido procesados. Borra el archivo CSV si quieres volver a empezar.")
        return

    print(f"[*] Procesando {total} tickets restantes...\n" + "-"*50)

    for i, row in df_pendientes.iterrows():
        inicio = time.time()
        
        texto_original = str(row['text'])
        texto_limpio = limpiar_tweet(texto_original)
        etiqueta_real = str(row['airline_sentiment']).upper()
        
        pred = probar_prompt(texto_limpio)
        
        if pred:
            tiempo = time.time() - inicio
            prediccion_ia = str(pred.get('prediccion', '')).upper()
            
            es_queja_ia = 'NEG' in prediccion_ia
            es_queja_real = (etiqueta_real == 'NEGATIVE')
            match = (es_queja_real == es_queja_ia)
            
            # Preparamos la fila a guardar
            nueva_fila = {
                'tweet_id': row['tweet_id'],
                'texto': texto_limpio[:150] + "..." if len(texto_limpio) > 150 else texto_limpio,
                'es_queja_real': es_queja_real,
                'es_queja_ia': es_queja_ia,
                'match': match,
                'razonamiento': pred.get('razonamiento', '')
            }
            
            # GUARDADO INSTANTÁNEO EN EL CSV (Modo 'a' = append)
            pd.DataFrame([nueva_fila]).to_csv(PATH_OUTPUT, mode='a', header=False, index=False)
            
            estado = "✅" if match else "❌"
            real_str = "QUEJA" if es_queja_real else "NO_QUEJA"
            ia_str = "QUEJA" if es_queja_ia else "NO_QUEJA"
            
            print(f"[{i+1}/{total}] IA: {ia_str[:8]:8} | Real: {real_str[:8]:8} {estado} ({tiempo:.1f}s)")

    # --- CÁLCULO DE MÉTRICAS FINALES ---
    # Leemos el archivo completo recién actualizado para calcular el total
    df_final = pd.read_csv(PATH_OUTPUT)
    accuracy = (df_final['match'].sum() / len(df_final)) * 100
    falsos_positivos = len(df_final[(df_final['es_queja_real'] == False) & (df_final['es_queja_ia'] == True)])
    falsos_negativos = len(df_final[(df_final['es_queja_real'] == True) & (df_final['es_queja_ia'] == False)])

    print("\n" + "="*50)
    print(f"[*] ACCURACY GLOBAL: {accuracy:.2f}% (sobre {len(df_final)} evaluados)")
    print(f"[*] Falsas Quejas (IA se asustó): {falsos_positivos}")
    print(f"[*] Quejas Ignoradas (IA no lo vio): {falsos_negativos}")
    print("=" * 50)

if __name__ == "__main__":
    ejecutar_laboratorio()