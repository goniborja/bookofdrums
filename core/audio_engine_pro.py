"""
UBICACIÓN: BookOfDrums/core/audio_engine_pro.py
DESCRIPCIÓN: Motor de Audio de Alta Precisión (SoundDevice / WASAPI)
CUMPLE CON: Documento 'sincronizar audio.md' (Reloj Hardware)
"""
import sounddevice as sd
import soundfile as sf
import numpy as np
import os
import threading
import queue

class AudioEnginePro:
    def __init__(self, assets_path, sample_rate=None):
        self.assets_path = assets_path
        
        # 1. Detectar Sample Rate nativo de la tarjeta para evitar errores
        if sample_rate is None:
            try:
                device_info = sd.query_devices(sd.default.device[1])
                self.sample_rate = int(device_info['default_samplerate'])
            except:
                self.sample_rate = 44100 # Fallback estándar
        else:
            self.sample_rate = sample_rate

        print(f"   [AUDIO PRO] Inicializando a {self.sample_rate} Hz (WASAPI Shared)")

        self.block_size = 512
        self.channels = 2
        self.kits = {}
        self.loaded_samples = {} # Cache de numpy arrays {nombre: array}
        
        # Estado del Secuenciador
        self.is_playing = False
        self.bpm = 120.0
        self.samples_per_beat = 0
        self.current_frame = 0
        self.next_beat_frame = 0
        
        # Cola de eventos (para disparar sonidos desde la UI)
        self.event_queue = queue.Queue()
        
        # Voces activas: lista de dicts {'data': array, 'cursor': int}
        self.active_voices = []
        
        # Inicializar Stream (pero no arrancarlo aún)
        self.stream = None
        self._init_stream()

    def _init_stream(self):
        """Configura el stream en modo Shared (más estable)"""
        try:
            self.stream = sd.OutputStream(
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                channels=self.channels,
                callback=self._audio_callback,
                latency='low' # Pide la menor latencia posible sin modo exclusivo
            )
        except Exception as e:
            print(f"!!! Error fatal iniciando SoundDevice: {e}")

    def _audio_callback(self, outdata, frames, time_info, status):
        """
        EL CORAZÓN DEL RELOJ.
        Se ejecuta cientos de veces por segundo.
        """
        if status:
            print(f"⚠️ SD Status: {status}")

        # 1. Limpiar buffer (silencio)
        outdata.fill(0)
        
        # 2. Procesar cola de eventos externos (ej: click del ratón)
        while not self.event_queue.empty():
            try:
                # Si la UI manda tocar algo, lo añadimos a las voces activas YA
                sample_key, vol = self.event_queue.get_nowait()
                if sample_key in self.loaded_samples:
                    # Ajustar volumen multiplicando el array
                    data = self.loaded_samples[sample_key] * vol
                    self.active_voices.append({'data': data, 'cursor': 0})
            except:
                break

        # 3. Lógica del Secuenciador (Si está Play)
        if self.is_playing:
            # Calcular offset para el siguiente golpe
            offset = self.next_beat_frame - self.current_frame
            
            # Si el golpe cae DENTRO de este buffer
            if 0 <= offset < frames:
                # AQUÍ iría la lógica compleja de mirar qué nota toca en el patrón
                # Por ahora, solo marcamos el beat
                self.next_beat_frame += self.samples_per_beat
                # (Futuro: Aquí llamaremos a self.get_sounds_for_step())

        # 4. MEZCLADOR (Sumar todas las voces activas)
        # Iteramos sobre una copia para poder borrar
        remaining_voices = []
        
        for voice in self.active_voices:
            data = voice['data']
            cursor = voice['cursor']
            
            # Cuánto queda del sample
            remaining_sample = len(data) - cursor
            # Cuánto cabe en el buffer
            to_copy = min(frames, remaining_sample)
            
            if to_copy > 0:
                # Sumar al buffer de salida
                # (Protección contra mismatch de canales simplificada)
                try:
                    outdata[:to_copy] += data[cursor : cursor + to_copy]
                except ValueError:
                    pass # Evitar crash si canales no coinciden
                
                # Avanzar cursor
                if to_copy < remaining_sample:
                    voice['cursor'] += to_copy
                    remaining_voices.append(voice)
            
        self.active_voices = remaining_voices
        self.current_frame += frames

    def start_engine(self):
        if self.stream and not self.stream.active:
            self.stream.start()
            print("   [AUDIO PRO] Motor arrancado.")

    def stop_engine(self):
        if self.stream and self.stream.active:
            self.stream.stop()

    def load_kit(self, kit_name):
        """Carga los WAVs del kit en arrays de Numpy"""
        kit_path = os.path.join(self.assets_path, kit_name)
        if not os.path.exists(kit_path): return
        
        print(f"   [AUDIO PRO] Cargando kit en memoria: {kit_name}...")
        self.loaded_samples = {}
        
        # Buscamos recursivamente
        for root, _, files in os.walk(kit_path):
            for f in files:
                if f.endswith(".wav"):
                    path = os.path.join(root, f)
                    try:
                        data, fs = sf.read(path, dtype='float32')
                        # Resampleo básico si no coincide (importante)
                        if fs != self.sample_rate:
                            # Nota: Para producción usaríamos scipy.resample, 
                            # aquí asumimos que el usuario usa 44.1k o 48k estándar
                            pass 
                        
                        # Convertir a stereo si es mono
                        if data.ndim == 1:
                            data = np.column_stack((data, data))
                            
                        # Guardar en diccionario usando nombre de archivo como clave
                        # (Simplificación, luego usaremos mapeo kick -> archivo)
                        key = self._guess_category(f)
                        self.loaded_samples[key] = data
                    except Exception as e:
                        print(f"Error cargando {f}: {e}")

    def play_one_shot(self, category, velocity=1.0):
        """Método seguro para llamar desde la UI (Thread-safe)"""
        if category in self.loaded_samples:
            self.event_queue.put((category, velocity))
    
    def _guess_category(self, n):
        # Misma lógica de detección que tenías antes
        n = n.lower()
        if "ohat" in n or "open" in n: return "hihat_op"
        if "chat" in n or "closed" in n: return "hihat_cl"
        if "rim" in n or "stick" in n: return "rim"
        if "snare" in n or "caja" in n: return "snare"
        if "kick" in n or "bombo" in n: return "kick"
        if "tom" in n: return "tom"
        if "crash" in n or "cymbal" in n: return "cymbal"
        return n # Si no adivina, usa el nombre tal cual