import sounddevice as sd
import sys

print("="*50)
print("🔎 INSPECTOR DE HARDWARE DE AUDIO (SOUNDDEVICE)")
print("="*50)

try:
    # 1. Listar dispositivos
    print(f"\n🎧 Librería PortAudio versión: {sd.get_portaudio_version()[1]}")
    print("\n📋 DISPOSITIVOS DETECTADOS:")
    devices = sd.query_devices()
    print(devices)

    # 2. Buscar el dispositivo por defecto
    default_out = sd.default.device[1] # [1] es output
    info = sd.query_devices(default_out)
    
    print("\n" + "-"*50)
    print(f"✅ DISPOSITIVO ACTIVO: {info['name']}")
    print(f"   - Sample Rate por defecto: {info['default_samplerate']} Hz")
    print(f"   - Canales de salida: {info['max_output_channels']}")
    print(f"   - Latencia sugerida (Low): {info['default_low_output_latency']*1000:.2f} ms")
    
    # 3. Prueba de compatibilidad con WASAPI (Modo Exclusivo de Windows)
    # Tu documento dice que esto es clave para el timing perfecto.
    print("\n🧪 PRUEBA DE COMPATIBILIDAD API:")
    apis = sd.query_hostapis()
    has_wasapi = False
    for api in apis:
        print(f"   - API disponible: {api['name']}")
        if "WASAPI" in api['name']:
            has_wasapi = True

    if has_wasapi:
        print("\n🎉 ¡EXCELENTE! Tu sistema soporta WASAPI.")
        print("   Podremos implementar el reloj maestro de alta precisión.")
    else:
        print("\n⚠️ AVISO: No veo WASAPI explícito. Usaremos DirectSound o MME (menos precisos).")

except Exception as e:
    print(f"\n❌ ERROR CRÍTICO: {e}")
    print("   Posiblemente falten drivers o permisos.")

print("\n" + "="*50)
input("Pulsa ENTER para salir...")