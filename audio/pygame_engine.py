"""
UBICACIÓN: BookOfDrums/audio/pygame_engine.py
DESCRIPCIÓN: Implementación del motor usando Pygame (Legacy).
MIGRACIÓN: Paso 1.2
"""
import pygame
import os
from .interface import AudioEngine

class PygameAudioEngine(AudioEngine):
    """
    Envoltorio (Wrapper) para el sistema de audio actual basado en Pygame.
    Permite que el código existente funcione bajo la nueva arquitectura.
    """

    def __init__(self):
        self._sounds = {} # Diccionario para guardar objetos pygame.mixer.Sound
        self._is_initialized = False

    def initialize(self):
        if self._is_initialized:
            return
        
        try:
            # Configuración idéntica a tu core/audio_engine.py actual
            pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(32)
            self._is_initialized = True
            print("   [AUDIO] Motor Pygame inicializado (Legacy Wrapper).")
        except Exception as e:
            print(f"!!! Error inicializando Pygame: {e}")

    def load_sample(self, name: str, filepath: str):
        if not self._is_initialized:
            return
            
        if not os.path.exists(filepath):
            print(f"   [AVISO] Archivo no encontrado: {filepath}")
            return

        try:
            sound = pygame.mixer.Sound(filepath)
            self._sounds[name] = sound
        except Exception as e:
            print(f"!!! Error cargando sample {name}: {e}")

    def play_sample(self, name: str, velocity: float = 1.0):
        if name in self._sounds:
            try:
                sound = self._sounds[name]
                # Pygame volumen es 0.0 a 1.0
                sound.set_volume(max(0.0, min(1.0, velocity)))
                sound.play()
            except Exception:
                pass

    def stop_all(self):
        if self._is_initialized:
            pygame.mixer.stop()

    def shutdown(self):
        if self._is_initialized:
            pygame.mixer.quit()
            self._is_initialized = False
            self._sounds.clear()