"""
UBICACIÓN: BookOfDrums/core/tempo_sync.py
VERSIÓN: 1.0
DESCRIPCIÓN: Sincronización de tempo y time-stretching para Book of Drums
AUTOR: Generado para Borja (Bilbomatiks)
FECHA: Enero 2025

INSTALACIÓN REQUERIDA:
    pip install pedalboard soundfile librosa

USO BÁSICO:
    from core.tempo_sync import TempoSyncManager
    
    manager = TempoSyncManager(genre='one_drop')
    bpm, confianza = manager.cargar_referencia("skank.wav")
    manager.sincronizar_sample("kick.wav", "kick_sync.wav", source_bpm=85)
"""

import os
import re
import numpy as np
from typing import Optional, Tuple, Dict, Callable, List
from dataclasses import dataclass
from enum import Enum

# ============================================================================
# VERIFICACIÓN DE DEPENDENCIAS
# ============================================================================

class DependencyStatus:
    """Estado de las dependencias de audio."""
    soundfile: bool = False
    librosa: bool = False
    pedalboard: bool = False
    pyrubberband: bool = False
    
    _sf_module = None
    _librosa_module = None
    _pb_stretch = None
    _pyrb_module = None

DEPS = DependencyStatus()

# Intentar importar soundfile
try:
    import soundfile as _sf
    DEPS.soundfile = True
    DEPS._sf_module = _sf
except ImportError:
    pass

# Intentar importar librosa
try:
    import librosa as _librosa
    DEPS.librosa = True
    DEPS._librosa_module = _librosa
except ImportError:
    pass

# Intentar importar pedalboard
try:
    from pedalboard import time_stretch as _pb_ts
    DEPS.pedalboard = True
    DEPS._pb_stretch = _pb_ts
except ImportError:
    pass

# Intentar importar pyrubberband
try:
    import pyrubberband as _pyrb
    DEPS.pyrubberband = True
    DEPS._pyrb_module = _pyrb
except ImportError:
    pass


def verificar_dependencias() -> Dict[str, bool]:
    """Retorna el estado de todas las dependencias."""
    return {
        'soundfile': DEPS.soundfile,
        'librosa': DEPS.librosa,
        'pedalboard': DEPS.pedalboard,
        'pyrubberband': DEPS.pyrubberband
    }


def imprimir_estado():
    """Imprime el estado de las dependencias en consola."""
    print("\n" + "="*50)
    print("📦 TEMPO SYNC - ESTADO DE DEPENDENCIAS")
    print("="*50)
    
    status = verificar_dependencias()
    for lib, disponible in status.items():
        icon = "✅" if disponible else "❌"
        print(f"   {icon} {lib}")
    
    # Motor de stretching
    if DEPS.pedalboard:
        print(f"\n🎛️ Motor de stretching: Pedalboard (Spotify)")
    elif DEPS.pyrubberband:
        print(f"\n🎛️ Motor de stretching: pyrubberband")
    else:
        print(f"\n⚠️ Sin motor de stretching disponible")
        print(f"   Instalar: pip install pedalboard")
    
    print("="*50 + "\n")


# ============================================================================
# ENUMS Y DATACLASSES
# ============================================================================

class GeneroMusical(Enum):
    """Géneros musicales con sus rangos de BPM típicos."""
    SKA = ('ska', 110, 180)
    ROCKSTEADY = ('rocksteady', 80, 110)
    EARLY_REGGAE = ('early_reggae', 90, 130)
    ONE_DROP = ('one_drop', 65, 95)
    ROCKERS = ('rockers', 70, 95)
    STEPPERS = ('steppers', 100, 140)
    NYABINGHI = ('nyabinghi', 55, 80)
    DEFAULT = ('default', 60, 160)
    
    def __init__(self, nombre: str, bpm_min: int, bpm_max: int):
        self._nombre = nombre
        self._bpm_min = bpm_min
        self._bpm_max = bpm_max
    
    @property
    def rango(self) -> Tuple[int, int]:
        return (self._bpm_min, self._bpm_max)


@dataclass
class AnalisisResult:
    """Resultado del análisis de tempo."""
    bpm_detectado: float
    bpm_raw: float
    confianza: float
    duracion_segundos: float
    sample_rate: int
    num_beats: int
    fue_corregido: bool
    mensaje: str = ""


@dataclass
class StretchResult:
    """Resultado del time-stretching."""
    exito: bool
    ruta_salida: Optional[str]
    factor_aplicado: float
    duracion_original: float
    duracion_nueva: float
    mensaje: str = ""


# ============================================================================
# CLASE PRINCIPAL: TempoAnalyzer
# ============================================================================

class TempoAnalyzer:
    """
    Analiza archivos de audio para detectar su BPM.
    Incluye correcciones específicas para música con off-beat (reggae/ska).
    """
    
    def __init__(self, genero: GeneroMusical = GeneroMusical.ONE_DROP):
        """
        Args:
            genero: Género musical para ajustar el rango de BPM esperado
        """
        if not DEPS.librosa:
            raise ImportError(
                "librosa es necesario para análisis de tempo.\n"
                "Instalar: pip install librosa"
            )
        
        self.genero = genero
        self.bpm_min, self.bpm_max = genero.rango
        self._librosa = DEPS._librosa_module
    
    def analizar(self, audio_path: str, 
                 corregir_offbeat: bool = True) -> AnalisisResult:
        """
        Analiza un archivo de audio y detecta su BPM.
        
        Args:
            audio_path: Ruta al archivo de audio
            corregir_offbeat: Si True, corrige detecciones de doble/mitad tempo
        
        Returns:
            AnalisisResult con toda la información del análisis
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Archivo no encontrado: {audio_path}")
        
        # Cargar audio (mono para análisis)
        try:
            y, sr = self._librosa.load(audio_path, sr=None, mono=True)
        except Exception as e:
            raise RuntimeError(f"Error cargando audio: {e}")
        
        duracion = len(y) / sr
        
        # Calcular onset envelope para detección más precisa
        onset_env = self._librosa.onset.onset_strength(y=y, sr=sr)
        
        # Detección de tempo principal
        tempo_result = self._librosa.beat.beat_track(
            y=y, sr=sr, onset_envelope=onset_env
        )
        
        # Manejar diferentes formatos de retorno de librosa
        if isinstance(tempo_result, tuple):
            tempo_raw, beats = tempo_result
        else:
            tempo_raw = tempo_result
            beats = []
        
        # Convertir a float si es array
        if hasattr(tempo_raw, '__len__'):
            tempo_raw = float(tempo_raw[0])
        else:
            tempo_raw = float(tempo_raw)
        
        # Calcular confianza basada en la consistencia de los beats
        if len(beats) > 1:
            beat_times = self._librosa.frames_to_time(beats, sr=sr)
            intervals = np.diff(beat_times)
            if len(intervals) > 0:
                std_intervals = np.std(intervals)
                mean_interval = np.mean(intervals)
                # Coeficiente de variación (menor = más consistente)
                cv = std_intervals / mean_interval if mean_interval > 0 else 1
                confianza = max(0.1, min(1.0, 1.0 - cv * 2))
            else:
                confianza = 0.5
        else:
            confianza = 0.3
        
        # Corrección para off-beat (reggae)
        bpm_final = tempo_raw
        fue_corregido = False
        mensaje = ""
        
        if corregir_offbeat:
            # Si detectó más del 30% por encima del máximo esperado
            if tempo_raw > self.bpm_max * 1.3:
                bpm_final = tempo_raw / 2
                fue_corregido = True
                confianza *= 0.85
                mensaje = f"Tempo dividido por 2 (off-beat detectado): {tempo_raw:.1f} → {bpm_final:.1f}"
            
            # Si detectó menos del 70% del mínimo esperado
            elif tempo_raw < self.bpm_min * 0.7:
                bpm_final = tempo_raw * 2
                fue_corregido = True
                confianza *= 0.85
                mensaje = f"Tempo multiplicado por 2: {tempo_raw:.1f} → {bpm_final:.1f}"
        
        return AnalisisResult(
            bpm_detectado=bpm_final,
            bpm_raw=tempo_raw,
            confianza=confianza,
            duracion_segundos=duracion,
            sample_rate=sr,
            num_beats=len(beats),
            fue_corregido=fue_corregido,
            mensaje=mensaje
        )
    
    def analizar_multiple(self, audio_paths: List[str]) -> Dict[str, AnalisisResult]:
        """Analiza múltiples archivos."""
        resultados = {}
        for path in audio_paths:
            try:
                resultados[path] = self.analizar(path)
            except Exception as e:
                resultados[path] = AnalisisResult(
                    bpm_detectado=0, bpm_raw=0, confianza=0,
                    duracion_segundos=0, sample_rate=0, num_beats=0,
                    fue_corregido=False, mensaje=f"Error: {e}"
                )
        return resultados


# ============================================================================
# CLASE: AudioStretcher
# ============================================================================

class AudioStretcher:
    """
    Realiza time-stretching de audio manteniendo el pitch.
    Usa Pedalboard (preferido) o pyrubberband como motor.
    """
    
    def __init__(self):
        """Inicializa el stretcher con el mejor motor disponible."""
        self.engine = None
        
        if DEPS.pedalboard:
            self.engine = 'pedalboard'
        elif DEPS.pyrubberband:
            self.engine = 'pyrubberband'
        else:
            raise ImportError(
                "Se necesita un motor de time-stretching.\n"
                "Instalar: pip install pedalboard"
            )
    
    def stretch(self, audio_data: np.ndarray, sample_rate: int,
                factor: float) -> np.ndarray:
        """
        Aplica time-stretch a datos de audio.
        
        Args:
            audio_data: Array numpy con los samples
            sample_rate: Frecuencia de muestreo
            factor: Factor de stretching (>1 = más rápido, <1 = más lento)
        
        Returns:
            Array numpy con el audio procesado
        """
        # Validar factor
        if factor <= 0:
            raise ValueError(f"Factor debe ser positivo, recibido: {factor}")
        
        if factor < 0.25 or factor > 4.0:
            print(f"⚠️ Factor extremo ({factor:.2f}). Posibles artefactos.")
            factor = np.clip(factor, 0.25, 4.0)
        
        # Asegurar float32 (requerido por Pedalboard)
        if audio_data.dtype != np.float32:
            audio_data = self._normalizar_audio(audio_data)
        
        # Aplicar stretching
        if self.engine == 'pedalboard':
            return DEPS._pb_stretch(audio_data, sample_rate, stretch_factor=factor)
        elif self.engine == 'pyrubberband':
            return DEPS._pyrb_module.time_stretch(audio_data, sample_rate, factor)
        
        raise RuntimeError("Motor de stretching no disponible")
    
    def stretch_bpm(self, audio_data: np.ndarray, sample_rate: int,
                    source_bpm: float, target_bpm: float) -> np.ndarray:
        """
        Aplica time-stretch basado en BPM.
        
        Args:
            audio_data: Array numpy con los samples
            sample_rate: Frecuencia de muestreo
            source_bpm: BPM original del audio
            target_bpm: BPM objetivo
        
        Returns:
            Array numpy con el audio procesado
        """
        factor = target_bpm / source_bpm
        return self.stretch(audio_data, sample_rate, factor)
    
    def procesar_archivo(self, input_path: str, output_path: str,
                         source_bpm: float, target_bpm: float) -> StretchResult:
        """
        Procesa un archivo de audio completo.
        
        Args:
            input_path: Ruta del archivo original
            output_path: Ruta donde guardar el resultado
            source_bpm: BPM original
            target_bpm: BPM objetivo
        
        Returns:
            StretchResult con información del proceso
        """
        if not DEPS.soundfile:
            raise ImportError("soundfile necesario. pip install soundfile")
        
        sf = DEPS._sf_module
        
        try:
            # Leer archivo
            data, sr = sf.read(input_path)
            duracion_original = len(data) / sr
            
            # Calcular factor
            factor = target_bpm / source_bpm
            
            # Normalizar a float32
            data = self._normalizar_audio(data)
            
            # Aplicar stretch
            stretched = self.stretch(data, sr, factor)
            duracion_nueva = len(stretched) / sr
            
            # Crear directorio de salida si no existe
            os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
            
            # Guardar resultado
            sf.write(output_path, stretched, sr)
            
            return StretchResult(
                exito=True,
                ruta_salida=output_path,
                factor_aplicado=factor,
                duracion_original=duracion_original,
                duracion_nueva=duracion_nueva,
                mensaje=f"OK: {source_bpm:.0f} → {target_bpm:.0f} BPM"
            )
            
        except Exception as e:
            return StretchResult(
                exito=False,
                ruta_salida=None,
                factor_aplicado=0,
                duracion_original=0,
                duracion_nueva=0,
                mensaje=f"Error: {e}"
            )
    
    def _normalizar_audio(self, data: np.ndarray) -> np.ndarray:
        """Convierte audio a float32 normalizado."""
        if data.dtype == np.float32:
            return data
        elif data.dtype == np.float64:
            return data.astype(np.float32)
        elif np.issubdtype(data.dtype, np.integer):
            # Obtener el valor máximo para el tipo
            info = np.iinfo(data.dtype)
            return data.astype(np.float32) / info.max
        else:
            # Normalización genérica
            max_val = np.abs(data).max()
            if max_val > 0:
                return data.astype(np.float32) / max_val
            return data.astype(np.float32)


# ============================================================================
# CLASE PRINCIPAL: TempoSyncManager
# ============================================================================

class TempoSyncManager:
    """
    Gestor principal de sincronización de tempo.
    Coordina detección de BPM y time-stretching de samples.
    
    Uso típico:
        manager = TempoSyncManager(genero='one_drop')
        bpm, confianza = manager.cargar_referencia("skank.wav")
        manager.sincronizar_sample("kick.wav", "kick_sync.wav")
    """
    
    def __init__(self, genero: str = 'one_drop'):
        """
        Args:
            genero: Nombre del género ('ska', 'rocksteady', 'one_drop', etc.)
        """
        # Convertir string a enum
        genero_upper = genero.upper()
        try:
            self.genero = GeneroMusical[genero_upper]
        except KeyError:
            self.genero = GeneroMusical.DEFAULT
        
        # Inicializar componentes
        self.analyzer = None
        self.stretcher = None
        
        # Estado
        self.reference_path: Optional[str] = None
        self.reference_bpm: Optional[float] = None
        self.reference_confianza: float = 0.0
        
        # Intentar inicializar analyzer
        if DEPS.librosa:
            try:
                self.analyzer = TempoAnalyzer(self.genero)
            except Exception as e:
                print(f"⚠️ Analyzer no disponible: {e}")
        
        # Intentar inicializar stretcher
        if DEPS.pedalboard or DEPS.pyrubberband:
            try:
                self.stretcher = AudioStretcher()
            except Exception as e:
                print(f"⚠️ Stretcher no disponible: {e}")
    
    @property
    def puede_analizar(self) -> bool:
        """Indica si puede analizar BPM."""
        return self.analyzer is not None
    
    @property
    def puede_estirar(self) -> bool:
        """Indica si puede hacer time-stretching."""
        return self.stretcher is not None
    
    @property
    def tiene_referencia(self) -> bool:
        """Indica si hay una referencia cargada."""
        return self.reference_bpm is not None
    
    def cargar_referencia(self, audio_path: str) -> Tuple[float, float]:
        """
        Carga un archivo de referencia y detecta su BPM.
        
        Args:
            audio_path: Ruta al archivo de audio de referencia
        
        Returns:
            tuple: (bpm_detectado, confianza)
        
        Raises:
            RuntimeError: Si no hay analyzer disponible
            FileNotFoundError: Si el archivo no existe
        """
        if not self.puede_analizar:
            raise RuntimeError(
                "Analyzer no disponible. Instalar: pip install librosa"
            )
        
        resultado = self.analyzer.analizar(audio_path)
        
        self.reference_path = audio_path
        self.reference_bpm = resultado.bpm_detectado
        self.reference_confianza = resultado.confianza
        
        # Log
        print(f"\n🎵 REFERENCIA CARGADA")
        print(f"   Archivo: {os.path.basename(audio_path)}")
        print(f"   BPM: {resultado.bpm_detectado:.1f}")
        print(f"   Confianza: {resultado.confianza*100:.0f}%")
        print(f"   Duración: {resultado.duracion_segundos:.2f}s")
        if resultado.fue_corregido:
            print(f"   ⚠️ {resultado.mensaje}")
        
        return resultado.bpm_detectado, resultado.confianza
    
    def sincronizar_sample(self, input_path: str, output_path: str,
                           source_bpm: Optional[float] = None) -> StretchResult:
        """
        Sincroniza un sample al BPM de la referencia.
        
        Args:
            input_path: Ruta del sample original
            output_path: Ruta donde guardar el resultado
            source_bpm: BPM original del sample (opcional)
        
        Returns:
            StretchResult con información del proceso
        """
        if not self.tiene_referencia:
            raise RuntimeError(
                "No hay referencia cargada. Usa cargar_referencia() primero."
            )
        
        if not self.puede_estirar:
            raise RuntimeError(
                "Stretcher no disponible. Instalar: pip install pedalboard"
            )
        
        # Determinar BPM origen
        if source_bpm is None:
            # Intentar extraer del nombre del archivo
            source_bpm = extraer_bpm_nombre(input_path)
            
            if source_bpm is None:
                # Asumir que está al BPM de la referencia (one-shots típicos)
                source_bpm = self.reference_bpm
                print(f"📌 Asumiendo BPM = {source_bpm:.0f} (igual que referencia)")
            else:
                print(f"📌 BPM extraído del nombre: {source_bpm:.0f}")
        
        return self.stretcher.procesar_archivo(
            input_path, output_path, source_bpm, self.reference_bpm
        )
    
    def sincronizar_batch(self, samples: Dict[str, Optional[float]],
                          output_dir: str,
                          callback: Optional[Callable[[int, int, str], None]] = None
                          ) -> Dict[str, StretchResult]:
        """
        Sincroniza múltiples samples en batch.
        
        Args:
            samples: Dict de {ruta_sample: bpm_original} (bpm puede ser None)
            output_dir: Carpeta donde guardar los resultados
            callback: Función para reportar progreso (idx, total, nombre)
        
        Returns:
            Dict de {ruta_sample: StretchResult}
        """
        if not self.tiene_referencia:
            raise RuntimeError("No hay referencia cargada.")
        
        os.makedirs(output_dir, exist_ok=True)
        resultados = {}
        total = len(samples)
        
        for idx, (input_path, source_bpm) in enumerate(samples.items()):
            nombre = os.path.basename(input_path)
            
            if callback:
                callback(idx, total, nombre)
            
            # Generar nombre de salida
            base, ext = os.path.splitext(nombre)
            output_name = f"{base}_{int(self.reference_bpm)}bpm{ext}"
            output_path = os.path.join(output_dir, output_name)
            
            try:
                result = self.sincronizar_sample(input_path, output_path, source_bpm)
                resultados[input_path] = result
            except Exception as e:
                resultados[input_path] = StretchResult(
                    exito=False, ruta_salida=None, factor_aplicado=0,
                    duracion_original=0, duracion_nueva=0,
                    mensaje=f"Error: {e}"
                )
        
        return resultados


# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================

def extraer_bpm_nombre(filepath: str) -> Optional[float]:
    """
    Intenta extraer el BPM del nombre de un archivo.
    
    Patrones soportados:
        - "loop_120.wav"
        - "beat_85bpm.wav"
        - "SKANK_1_100.wav"
        - "kick_at_90_bpm.wav"
    
    Returns:
        BPM como float, o None si no se encuentra
    """
    filename = os.path.basename(filepath).lower()
    
    patterns = [
        r'_(\d{2,3})\.wav$',           # _120.wav
        r'_(\d{2,3})bpm',              # _120bpm
        r'(\d{2,3})bpm',               # 120bpm
        r'bpm[_\s]*(\d{2,3})',         # bpm_120 o bpm 120
        r'at[_\s]*(\d{2,3})',          # at_120 o at 120
        r'[\-_](\d{2,3})[\-_\.]',      # -120- o _120_ o _120.
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            bpm = int(match.group(1))
            if 40 <= bpm <= 220:  # Rango válido
                return float(bpm)
    
    return None


def leer_audio(filepath: str) -> Tuple[np.ndarray, int]:
    """
    Lee un archivo de audio y lo retorna como array float32.
    
    Returns:
        tuple: (data como float32, sample_rate)
    """
    if not DEPS.soundfile:
        raise ImportError("soundfile necesario. pip install soundfile")
    
    data, sr = DEPS._sf_module.read(filepath)
    
    # Normalizar a float32
    if data.dtype != np.float32:
        if np.issubdtype(data.dtype, np.integer):
            info = np.iinfo(data.dtype)
            data = data.astype(np.float32) / info.max
        else:
            data = data.astype(np.float32)
    
    return data, sr


def guardar_audio(filepath: str, data: np.ndarray, sample_rate: int,
                  subtype: str = 'PCM_24'):
    """
    Guarda audio a archivo.
    
    Args:
        filepath: Ruta de salida
        data: Array de audio
        sample_rate: Frecuencia de muestreo
        subtype: Formato de submuestreo ('PCM_16', 'PCM_24', 'FLOAT')
    """
    if not DEPS.soundfile:
        raise ImportError("soundfile necesario. pip install soundfile")
    
    DEPS._sf_module.write(filepath, data, sample_rate, subtype=subtype)


# ============================================================================
# MAIN / TEST
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("   TEMPO SYNC MODULE - TEST")
    print("="*60)
    
    imprimir_estado()
    
    # Test de extracción de BPM del nombre
    test_names = [
        "SKANK_1_100.wav",
        "kick_85bpm.wav",
        "loop_at_120_bpm.wav",
        "random_file.wav"
    ]
    
    print("\n📝 Test de extracción de BPM de nombres:")
    for name in test_names:
        bpm = extraer_bpm_nombre(name)
        print(f"   '{name}' → {bpm}")
    
    # Si hay una referencia de prueba, analizarla
    test_file = "SKANK_1_100.wav"
    if os.path.exists(test_file) and DEPS.librosa:
        print(f"\n📊 Analizando archivo de prueba: {test_file}")
        try:
            manager = TempoSyncManager(genero='one_drop')
            bpm, conf = manager.cargar_referencia(test_file)
            print(f"\n✅ Test exitoso!")
        except Exception as e:
            print(f"\n❌ Error: {e}")
    
    print("\n" + "="*60)
