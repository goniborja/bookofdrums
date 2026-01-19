"""
PRUEBA DE CONCEPTO V2: MOTOR DE AUDIO ROBUSTO
Objetivo: Intentar WASAPI Exclusive, y si falla, usar WASAPI Shared.
"""
import sounddevice as sd
import soundfile as sf
import numpy as np
import os
import sys

# --- CONFIGURACIÓN ---
BPM = 120
# IMPORTANTE: Dejamos que sounddevice detecte el samplerate de tu tarjeta
# para evitar el error -9984
DEVICE_INFO = sd.query_devices(sd.default.device[1])
SAMPLE_RATE = int(DEVICE_INFO['default_samplerate'])
BUFFER_SIZE = 512

print("="*60)
print(f"   MOTOR DE AUDIO PRO V2 (Rate detectado: {SAMPLE_RATE} Hz)")
print("="*60)

# 1. BUSCAR UN SAMPLE
def buscar_sample():
    print("🔎 Buscando sample...")
    assets_dir = os.path.join(os.path.dirname(__file__), "assets")
    for root, dirs, files in os.walk(assets_dir):
        for f in files:
            if "snare" in f.lower() and f.endswith(".wav"):
                return os.path.join(root, f)
    # Fallback
    for root, dirs, files in os.walk(assets_dir):
        for f in files:
            if f.endswith(".wav"): return os.path.join(root, f)
    return None

sample_path = buscar_sample()
if not sample_path:
    print("!!! ERROR: Sin samples en assets.")
    sys.exit(1)

# 2. CARGAR SAMPLE
data, file_fs = sf.read(sample_path, dtype='float32')

# RESAMPLEO CHAPUCERO (Solo para el test)
# Si el archivo es 44100 y la tarjeta 48000, sonará ardilla si no hacemos esto.
# En el motor final usaremos una librería de resampleo real.
if file_fs != SAMPLE_RATE:
    print(f"⚠️ Aviso: Sample es {file_fs}Hz, Tarjeta es {SAMPLE_RATE}Hz. (Pitch variará en este test)")

if data.ndim == 1:
    data = np.column_stack((data, data))
sample_data = data
sample_len = len(data)

# 3. VARIABLES
current_frame = 0
next_beat_frame = 0
samples_per_beat = int((60.0 / BPM) * SAMPLE_RATE)
active_voices = [] 

# 4. CALLBACK
def audio_callback(outdata, frames, time_info, status):
    global current_frame, next_beat_frame, active_voices
    if status: print(f"⚠️ {status}")
    outdata.fill(0)
    
    # Lógica de disparo
    offset = next_beat_frame - current_frame
    if 0 <= offset < frames:
        active_voices.append(0)
        next_beat_frame += samples_per_beat

    # Lógica de mezcla
    new_active_voices = []
    for play_cursor in active_voices:
        remaining = sample_len - play_cursor
        can_copy = min(frames, remaining)
        if can_copy > 0:
            try:
                outdata[:can_copy] += sample_data[play_cursor : play_cursor+can_copy]
            except: pass 
            if can_copy < remaining:
                new_active_voices.append(play_cursor + can_copy)
    active_voices = new_active_voices
    current_frame += frames

# 5. INTENTO DE ARRANQUE INTELIGENTE
def run_stream(exclusive_mode):
    mode_name = "WASAPI EXCLUSIVE" if exclusive_mode else "WASAPI SHARED"
    print(f"\n🎧 Intentando iniciar en modo: {mode_name}...")
    
    extra = None
    if exclusive_mode:
        try: extra = sd.WasapiSettings(exclusive=True)
        except: return False

    try:
        with sd.OutputStream(samplerate=SAMPLE_RATE,
                             channels=2,
                             callback=audio_callback,
                             blocksize=BUFFER_SIZE,
                             extra_settings=extra):
            print(f"✅ ¡ÉXITO! Motor corriendo en {mode_name}.")
            print("   Escucha el metrónomo... (Ctrl+C para parar)")
            while True:
                sd.sleep(1000)
    except Exception as e:
        print(f"❌ Falló {mode_name}: {e}")
        return False

# LÓGICA DE FALLBACK
if not run_stream(exclusive_mode=True):
    print("\n🔄 Cambiando a plan B...")
    run_stream(exclusive_mode=False)