"""
UBICACIÓN: BookOfDrums/audio/factory.py
DESCRIPCIÓN: Patrón Factory para instanciar el motor de audio.
MIGRACIÓN: Paso 3.1 (Activación)
"""
import sys
import os

# Ajustar path para importar config desde raíz
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import AUDIO_ENGINE
from .interface import AudioEngine

def create_audio_engine() -> AudioEngine:
    """
    Crea y devuelve una instancia del motor de audio configurado en config.py.
    """
    
    if AUDIO_ENGINE == "sounddevice":
        try:
            # Importamos dinámicamente el motor nuevo
            from .sounddevice_engine import SounddeviceAudioEngine
            return SounddeviceAudioEngine()
        except Exception as e:
            print(f"   [ERROR CRÍTICO] Falló carga de SoundDevice: {e}")
            print("   -> Haciendo fallback automático a Pygame...")

    # Fallback por defecto: Pygame (Legacy)
    from .pygame_engine import PygameAudioEngine
    return PygameAudioEngine()