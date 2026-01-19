"""
UBICACIÓN: BookOfDrums/core/audio_engine.py
DESCRIPCIÓN: Lógica de instrumentos y secuenciador (Agnóstico del motor).
MIGRACIÓN: Fase 3 (Conectado a AudioInterface)
"""
import os
import time
import threading

# IMPORTANTE: Ya no usamos pygame aquí directamente.
# Usamos la fábrica para obtener el motor activo (sea cual sea).
from audio.factory import create_audio_engine


class DrumSampler:
    def __init__(self, assets_path, audio_engine=None):
        self.assets_path = assets_path

        # Inyección de dependencia:
        # Si nos pasan el motor desde main, lo usamos. Si no, pedimos uno a la fábrica.
        if audio_engine:
            self.engine = audio_engine
        else:
            print("   [SAMPLER] Alerta: Motor no inyectado, creando instancia propia.")
            self.engine = create_audio_engine()
            self.engine.initialize()

        # Kit por defecto (pero lo validaremos tras escanear)
        self.current_kit_name = "Reggae_Standard"
        self.current_kit_data = {}   # { 'kick': ['kick1.wav', 'kick2.wav'], ... }
        self.current_selection = {}  # { 'kick': 'kick1.wav', ... }
        self.available_kits = []

        self._scan_kits()

        # Si el kit por defecto no existe, elegimos el primero disponible
        if self.available_kits and self.current_kit_name not in self.available_kits:
            self.current_kit_name = self.available_kits[0]

        if self.available_kits:
            self.load_kit(self.current_kit_name)
        else:
            print("   [SAMPLER] No hay kits válidos (no se encontraron WAVs).")

    def _dir_has_wav(self, folder_path: str) -> bool:
        """Un kit válido debe contener al menos 1 .wav en cualquier subcarpeta."""
        for root, _, files in os.walk(folder_path):
            for f in files:
                if f.lower().endswith(".wav"):
                    return True
        return False

    def _scan_kits(self):
        if not os.path.exists(self.assets_path):
            os.makedirs(self.assets_path)

        kits = []
        for d in os.listdir(self.assets_path):
            full = os.path.join(self.assets_path, d)
            if not os.path.isdir(full):
                continue

            # Ignorar carpetas típicas NO-kits
            if d.lower() in ("database", "__pycache__", ".git"):
                continue

            # Solo considerar "kit" si tiene WAVs
            if self._dir_has_wav(full):
                kits.append(d)

        kits.sort(key=lambda s: s.lower())
        self.available_kits = kits if kits else ["Default"]

    def load_kit(self, kit_name):
        kit_path = os.path.join(self.assets_path, kit_name)
        if not os.path.exists(kit_path):
            print(f"   [SAMPLER] Kit '{kit_name}' no encontrado en: {kit_path}")
            return

        self.current_kit_name = kit_name
        self.current_kit_data = {}
        self.current_selection = {}

        # 1. Escanear archivos WAV
        for root, _, files in os.walk(kit_path):
            for f in files:
                if f.lower().endswith(".wav"):
                    cat = self._guess_category(f)
                    if cat not in self.current_kit_data:
                        self.current_kit_data[cat] = []
                    self.current_kit_data[cat].append(f)

        # 2. Seleccionar el primero de cada categoría por defecto
        for cat, file_list in self.current_kit_data.items():
            if file_list:
                self.current_selection[cat] = file_list[0]

                # 3. CARGAR EN EL MOTOR DE AUDIO
                full_path = os.path.join(kit_path, file_list[0])

                # Usamos el nombre del archivo como ID único para el motor
                self.engine.load_sample(file_list[0], full_path)

        print(f"   [SAMPLER] Kit '{kit_name}' cargado en el motor.")

    def set_instrument_sample(self, kit_name, instrument_key, filename):
        """Cambia el sample de un instrumento y lo carga en el motor al vuelo"""
        if instrument_key in self.current_kit_data:
            if filename in self.current_kit_data[instrument_key]:
                self.current_selection[instrument_key] = filename

                # Cargar en el motor (si no estaba ya)
                full_path = os.path.join(self.assets_path, kit_name, filename)
                self.engine.load_sample(filename, full_path)

    def play_one_shot(self, category, velocity=1.0):
        """Dispara un sonido usando el motor conectado"""
        if category in self.current_selection:
            file_id = self.current_selection[category]
            self.engine.play_sample(file_id, velocity)

    def load_backing_track(self, filepath):
        """Carga una pista de acompañamiento (Guitarra/Bajo)"""
        if os.path.exists(filepath):
            fname = os.path.basename(filepath)
            self.engine.load_sample("backing_track", filepath)
            self.current_selection["backing"] = "backing_track"
            return True
        return False

    def _guess_category(self, n):
        n = n.lower()
        if "ohat" in n or "open" in n:
            return "hihat_op"
        if "chat" in n or "closed" in n:
            return "hihat_cl"
        if "rim" in n or "stick" in n:
            return "rim"
        if "snare" in n or "caja" in n:
            return "snare"
        if "kick" in n or "bombo" in n:
            return "kick"
        if "tom" in n:
            return "tom"
        if "crash" in n or "cymbal" in n:
            return "cymbal"
        return "perc"


class SequencePlayer(threading.Thread):
    """
    Reproductor básico basado en Threads (Fase de transición).
    En el futuro, esto se moverá al callback de C para precisión perfecta.
    """
    def __init__(self, sampler, pattern_list, bpm, loop=False):
        super().__init__()
        self.sampler = sampler
        self.pattern_list = pattern_list if isinstance(pattern_list, list) else [pattern_list]
        self.bpm = bpm
        self.loop = loop
        self.is_playing = False
        self._stop_event = threading.Event()
        self.daemon = True

    def run(self):
        self.is_playing = True

        inst_map = {
            "kick": "kick", "bombo": "kick",
            "snare": "snare", "caja": "snare", "full": "snare",
            "rim": "rim", "stick": "rim",
            "hihat_closed": "hihat_cl", "chat": "hihat_cl",
            "hihat_open": "hihat_op", "ohat": "hihat_op",
            "cymbal": "cymbal", "crash": "cymbal",
            "tom": "tom"
        }

        while self.is_playing and not self._stop_event.is_set():
            for pattern in self.pattern_list:
                step_duration = (60.0 / self.bpm) / 4.0

                for step_idx in range(16):
                    if self._stop_event.is_set():
                        break

                    start_time = time.time()

                    for track_name, steps in pattern.tracks.items():
                        if step_idx < len(steps):
                            step = steps[step_idx]
                            if step.intensity > 0:
                                inst_key = None
                                t_low = track_name.lower()

                                for k, v in inst_map.items():
                                    if k in t_low:
                                        if v == "snare" and ("rim" in t_low or "stick" in t_low):
                                            continue
                                        inst_key = v
                                        break

                                if inst_key:
                                    vel = step.velocity_base / 127.0
                                    self.sampler.play_one_shot(inst_key, vel)

                    elapsed = time.time() - start_time
                    wait = max(0, step_duration - elapsed)
                    time.sleep(wait)

            if not self.loop:
                break

        self.is_playing = False

    def stop(self):
        self._stop_event.set()
        self.is_playing = False
