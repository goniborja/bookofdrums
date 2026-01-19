"""
UBICACIÓN: BookOfDrums/audio/sounddevice_engine.py
DESCRIPCIÓN: Motor de audio de Alta Precisión (SoundDevice + Rtmixer).
MIGRACIÓN: Paso 2.2
"""
import sounddevice as sd
import soundfile as sf
import rtmixer
import numpy as np
import os
from .interface import AudioEngine

class SounddeviceAudioEngine(AudioEngine):
    """
    Implementación profesional del motor de audio.
    Usa Rtmixer (callbacks en C) para evitar latencia y Jitter.
    """

    def __init__(self):
        self.mixer = None
        self._samples = {} # Cache de arrays Numpy
        self._is_initialized = False

    def initialize(self):
        if self._is_initialized:
            return
        
        try:
            print("   [AUDIO PRO] Iniciando SoundDevice + Rtmixer...")
            # Configuración de baja latencia (~5.8ms a 256 samples)
            self.mixer = rtmixer.Mixer(
                samplerate=44100,
                blocksize=256,
                channels=2,
                latency='low' 
            )
            self.mixer.start()
            self._is_initialized = True
            print(f"   [AUDIO PRO] Motor activo. Dispositivo: {sd.query_devices(kind='output')['name']}")
            
        except Exception as e:
            print(f"!!! Error fatal iniciando SoundDevice: {e}")
            self._is_initialized = False

    def load_sample(self, name: str, filepath: str):
        if not self._is_initialized: return
        if not os.path.exists(filepath): return
        
        try:
            # 1. Cargar audio como float32 (formato nativo de la tarjeta)
            data, sr = sf.read(filepath, dtype='float32')
            
            # 2. Asegurar que sea Estéreo (si es mono, duplicar canal)
            if data.ndim == 1:
                data = np.column_stack([data, data])
            
            # 3. CRÍTICO: Convertir a array contiguo en memoria (requisito de Rtmixer)
            data = np.ascontiguousarray(data, dtype=np.float32)
            
            self._samples[name] = data
            
        except Exception as e:
            print(f"!!! Error cargando sample PRO {name}: {e}")

    def play_sample(self, name: str, velocity: float = 1.0):
        if not self._is_initialized or name not in self._samples:
            return
        
        try:
            sample_data = self._samples[name]
            
            # Aplicar volumen (velocity) multiplicando la matriz
            # (En el futuro esto se optimizará, pero para one-shots funciona bien)
            if velocity != 1.0:
                vol_data = sample_data * velocity
            else:
                vol_data = sample_data
                
            # Disparar al mezclador en tiempo real
            self.mixer.play_buffer(vol_data, channels=2)
            
        except Exception as e:
            # Evitamos saturar la consola si algo falla muy rápido
            pass

    def stop_all(self):
        if self.mixer:
            # Rtmixer no tiene "stop all" simple, abortamos y reiniciamos
            try:
                self.mixer.abort()
                self.mixer.start()
            except:
                pass

    def shutdown(self):
        if self.mixer:
            self.mixer.stop()
            self.mixer.close()
        self._is_initialized = False
        self._samples.clear()