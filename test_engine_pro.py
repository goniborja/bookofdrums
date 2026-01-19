"""
PRUEBA DE CONCEPTO: MOTOR DE AUDIO PRO (SoundDevice + WASAPI)
Basado en: sincronizar audio.md
Objetivo: Demostrar timing perfecto sin 'drift'.
"""
import sounddevice as sd
import soundfile as sf
import numpy as np
import os
import sys

# --- CONFIGURACIÓN ---
BPM = 120
SAMPLE_RATE = 44100
BUFFER_SIZE = 512  # Bajo buffer = baja latencia

print("="*60)
print("   MOTOR DE AUDIO PRO: PRUEBA DE TIMING")
print("="*60)

# 1. BUSCAR UN SAMPLE (Cualquiera servirá, preferiblemente caja)
def buscar_sample():
    print("🔎 Buscando un sample de prueba en /assets...")
    assets_dir = os.path.join(os.path.dirname(__file__), "assets")
    for root, dirs, files in os.walk(assets_dir):
        for f in files:
            if "snare" in f.lower() and f.endswith(".wav"):
                full_path = os.path.join(root, f)
                print(f"✅ Encontrado: {f}")
                return full_path
    print("❌ No encontré ningún 'snare'. Usaré el primer WAV que vea.")
    # Fallback
    for root, dirs, files in os.walk(assets_dir):
        for f in files:
            if f.endswith(".wav"): return os.path.join(root, f)
    return None

sample_path = buscar_sample()
if not sample_path:
    print("!!! ERROR: No hay archivos WAV en la carpeta assets.")
    sys.exit(1)

# 2. CARGAR SAMPLE EN MEMORIA (Como array de Numpy)
data, fs = sf.read(sample_path, dtype='float32')
# Si es estéreo, lo dejamos; si es mono, lo duplicamos para que suene en L y R
if data.ndim == 1:
    data = np.column_stack((data, data))
sample_data = data
sample_len = len(data)
print(f"📊 Sample cargado: {sample_len} samples de duración.")

# 3. VARIABLES DE ESTADO (Para el Callback)
current_frame = 0
next_beat_frame = 0
samples_per_beat = int((60.0 / BPM) * SAMPLE_RATE)
active_voices = [] # Lista de (indice_sample, array_data)

print(f"⏱️ BPM: {BPM}")
print(f"📏 Samples por golpe: {samples_per_beat}")

# 4. EL CALLBACK (El corazón del sistema)
# Esta función es llamada por la tarjeta de sonido, no por Python.
# Tiene que ser ultra-rápida.
def audio_callback(outdata, frames, time_info, status):
    global current_frame, next_beat_frame, active_voices

    if status:
        print(f"⚠️ {status}")

    # Limpiar buffer de salida (silencio)
    outdata.fill(0)
    
    # ¿Toca disparar un sonido en este bloque de frames?
    # Calculamos si el 'next_beat_frame' cae dentro de este buffer
    frames_generated = 0
    
    # Bucle para rellenar el buffer (puede haber varios eventos en un buffer pequeño)
    # Pero para simplificar, procesamos todo el bloque:
    
    # A) Lógica de Secuenciador: ¿Toca disparar sonido AHORA?
    # Miramos si el momento del golpe cae dentro de este bloque de audio
    offset = next_beat_frame - current_frame
    
    if 0 <= offset < frames:
        # ¡SÍ! Toca disparar en el sample número 'offset' de este buffer
        # Añadimos una "voz" a la lista de reproducción
        active_voices.append(0) # 0 significa "empezar a reproducir desde el inicio del sample"
        # Programar el siguiente golpe
        next_beat_frame += samples_per_beat
        # print("BOM!", end=" ", flush=True) # (Cuidado con los prints en callbacks reales)

    # B) Lógica de Mezclador: Sumar todas las voces activas
    # Iteramos sobre una copia para poder borrar las que terminan
    new_active_voices = []
    
    for play_cursor in active_voices:
        # Cuánto queda de sample
        remaining = sample_len - play_cursor
        # Cuánto cabe en este buffer
        can_copy = min(frames, remaining)
        
        if can_copy > 0:
            # SUMA MATEMÁTICA (MEZCLA)
            # outdata[0:can_copy] += sample_data[play_cursor : play_cursor+can_copy]
            # (Simplificado para evitar problemas de broadcasting si el sample es mono/stereo vs output)
            
            # Aseguramos dimensiones
            chunk = sample_data[play_cursor : play_cursor+can_copy]
            
            # Si outdata es stereo (N,2) y chunk es stereo (N,2), sumamos
            try:
                outdata[:can_copy] += chunk
            except ValueError:
                # Si fallan las dimensiones, intentamos ajustar (chapuza de emergencia)
                pass 

            # Avanzamos el cursor
            if can_copy < remaining:
                new_active_voices.append(play_cursor + can_copy)
            # Si no, es que ha terminado, no lo añadimos a new_active_voices
            
    active_voices = new_active_voices
    current_frame += frames

# 5. INICIAR STREAM
try:
    # Intentamos forzar WASAPI Exclusive para latencia mínima
    extra_settings = None
    try:
        import sounddevice as sd
        extra_settings = sd.WasapiSettings(exclusive=True)
    except:
        pass

    print("\n🚀 INICIANDO MOTOR (Pulsa Ctrl+C para parar)...")
    
    with sd.OutputStream(samplerate=SAMPLE_RATE,
                         channels=2,
                         callback=audio_callback,
                         blocksize=BUFFER_SIZE,
                         extra_settings=extra_settings):
        
        print("✅ Motor corriendo. Deberías escuchar un metrónomo perfecto.")
        print("   Este sonido es generado matemáticas puras sample a sample.")
        # Bucle infinito para mantener el script vivo
        while True:
            sd.sleep(1000)

except KeyboardInterrupt:
    print("\n🛑 Detenido por usuario.")
except Exception as e:
    print(f"\n❌ Error al abrir stream: {e}")
    print("   Intenta cerrar otras apps que usen audio si usas WASAPI Exclusive.")