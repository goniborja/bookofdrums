"""
UBICACIÓN: BookOfDrums/audio/interface.py
DESCRIPCIÓN: Contrato abstracto para el motor de audio.
MIGRACIÓN: Paso 1.1
"""
from abc import ABC, abstractmethod

class AudioEngine(ABC):
    """
    Clase base abstracta que define la interfaz obligatoria
    para cualquier motor de audio (Pygame o SoundDevice).
    """

    @abstractmethod
    def initialize(self):
        """Inicializa el sistema de audio y recursos."""
        pass

    @abstractmethod
    def load_sample(self, name: str, filepath: str):
        """
        Carga un archivo de audio en memoria.
        Args:
            name: Identificador único del sample (ej: 'kick').
            filepath: Ruta absoluta al archivo WAV.
        """
        pass

    @abstractmethod
    def play_sample(self, name: str, velocity: float = 1.0):
        """
        Reproduce un sample cargado.
        Args:
            name: Identificador del sample.
            velocity: Volumen/intensidad (0.0 a 1.0).
        """
        pass

    @abstractmethod
    def stop_all(self):
        """Detiene toda la reproducción de audio inmediatamente."""
        pass

    @abstractmethod
    def shutdown(self):
        """Libera recursos y cierra el sistema de audio."""
        pass