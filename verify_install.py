# verify_install.py - Ejecutar después de instalar
def verify():
    results = {}
    print("--- VERIFICANDO LIBRERÍAS ---")
    try:
        import cffi; results['cffi'] = cffi.__version__
    except: results['cffi'] = 'FALLO'
    try:
        import numpy as np; results['numpy'] = np.__version__
    except: results['numpy'] = 'FALLO'
    try:
        import sounddevice as sd
        results['sounddevice'] = sd.__version__
        # Intentamos ver la versión de PortAudio
        results['portaudio'] = sd.get_portaudio_version()[1]
    except Exception as e: results['sounddevice'] = f'FALLO: {e}'
    try:
        import soundfile as sf; results['soundfile'] = sf.__version__
    except: results['soundfile'] = 'FALLO'
    try:
        import rtmixer; results['rtmixer'] = 'OK'
    except: results['rtmixer'] = 'FALLO'
    
    for k, v in results.items():
        status = '✓' if 'FALLO' not in str(v) else '✗'
        print(f"{status} {k}: {v}")
    
    print("\n--- DISPOSITIVOS DE AUDIO DETECTADOS ---")
    import sounddevice as sd
    print(sd.query_devices())

if __name__ == "__main__":
    verify()