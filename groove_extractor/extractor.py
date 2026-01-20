"""
groove_extractor/extractor.py

Extractor principal de groove/humanización.
Analiza audio y genera datos para REJILLAS y HUMANIZACION.
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field

import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils.dataframe import dataframe_to_rows

# Intentar importar librosa (opcional pero recomendado)
try:
    import librosa
    import numpy as np
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False
    print("⚠️ librosa no instalado. Instalar: pip install librosa")


@dataclass
class OnsetInfo:
    """Información de un onset (golpe) detectado."""
    time_ms: float          # Tiempo en milisegundos
    velocity: int           # Velocidad estimada (0-127)
    step: int              # Paso más cercano (1-16)
    deviation_ticks: int    # Desviación en ticks respecto al paso teórico


@dataclass
class PatternAnalysis:
    """Resultado del análisis de un patrón."""
    pattern_id: str
    bpm: float
    instrument: str
    onsets: List[OnsetInfo] = field(default_factory=list)

    # Datos para REJILLAS (16 pasos, 0 o 1)
    rejilla: List[int] = field(default_factory=lambda: [0] * 16)
    vel_base: int = 100

    # Datos para HUMANIZACION (V1-V16, T1-T16)
    velocities: List[int] = field(default_factory=lambda: [0] * 16)
    timings: List[int] = field(default_factory=lambda: [0] * 16)


class GrooveExtractor:
    """
    Extrae groove/humanización de grabaciones de audio.

    Uso:
        extractor = GrooveExtractor("database.xlsx")
        extractor.analyze_audio("drums.wav", pattern_id="ska_groove", bpm=90)
        extractor.save()
    """

    # Parámetros de onset detection por instrumento
    ONSET_PARAMS = {
        'kick': {'pre_max': 3, 'post_max': 3, 'delta': 0.05, 'wait': 15},
        'snare': {'pre_max': 3, 'post_max': 3, 'delta': 0.06, 'wait': 10},
        'hihat': {'pre_max': 2, 'post_max': 2, 'delta': 0.04, 'wait': 5},
        'default': {'pre_max': 3, 'post_max': 3, 'delta': 0.07, 'wait': 10},
    }

    # PPQ estándar (pulses per quarter note)
    PPQ = 480

    def __init__(self, db_path: str):
        """
        Args:
            db_path: Ruta a database.xlsx
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database no encontrada: {db_path}")

        self.analyses: List[PatternAnalysis] = []

    def detect_bpm(self, audio_path: str) -> float:
        """Detecta el BPM de un archivo de audio."""
        if not HAS_LIBROSA:
            raise ImportError("librosa necesario para detección de BPM")

        y, sr = librosa.load(audio_path, sr=None, mono=True)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)

        # librosa puede devolver array
        if hasattr(tempo, '__len__'):
            tempo = float(tempo[0]) if len(tempo) > 0 else 120.0

        return float(tempo)

    def analyze_audio(
        self,
        audio_path: str,
        pattern_id: str,
        instrument: str = "drums",
        bpm: Optional[float] = None,
        bar_count: int = 1
    ) -> PatternAnalysis:
        """
        Analiza un archivo de audio y extrae datos de humanización.

        Args:
            audio_path: Ruta al archivo de audio
            pattern_id: ID del patrón para guardar en database
            instrument: Nombre del instrumento (kick, snare, hihat, etc.)
            bpm: BPM del audio (si None, se detecta automáticamente)
            bar_count: Número de compases a analizar

        Returns:
            PatternAnalysis con datos de rejilla y humanización
        """
        if not HAS_LIBROSA:
            raise ImportError("librosa necesario para análisis de audio")

        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio no encontrado: {audio_path}")

        print(f"📊 Analizando: {audio_path.name}")

        # Detectar BPM si no se proporciona
        if bpm is None:
            bpm = self.detect_bpm(str(audio_path))
            print(f"   BPM detectado: {bpm:.1f}")

        # Cargar audio
        y, sr = librosa.load(str(audio_path), sr=44100, mono=True)
        duration_ms = len(y) / sr * 1000

        # Detectar onsets
        params = self.ONSET_PARAMS.get(instrument.lower(), self.ONSET_PARAMS['default'])
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        onset_frames = librosa.onset.onset_detect(
            y=y, sr=sr, onset_envelope=onset_env,
            backtrack=True, **params
        )
        onset_times = librosa.frames_to_time(onset_frames, sr=sr)

        print(f"   Onsets detectados: {len(onset_times)}")

        # Calcular duración de un paso en ms
        # 16 pasos = 1 compás = 4 beats
        ms_per_beat = 60000.0 / bpm
        ms_per_step = ms_per_beat / 4  # 16th note
        ticks_per_step = self.PPQ / 4  # 120 ticks por step

        # Crear análisis
        analysis = PatternAnalysis(
            pattern_id=pattern_id,
            bpm=bpm,
            instrument=instrument
        )

        # Procesar cada onset
        for onset_time in onset_times:
            onset_ms = onset_time * 1000

            # Solo procesar onsets dentro del rango de compases
            max_ms = bar_count * 4 * ms_per_beat
            if onset_ms > max_ms:
                continue

            # Calcular step más cercano (0-15)
            step_float = onset_ms / ms_per_step
            step_idx = int(round(step_float))
            step_idx = max(0, min(15, step_idx))  # Clamp a 0-15

            # Calcular desviación en ticks
            theoretical_ms = step_idx * ms_per_step
            deviation_ms = onset_ms - theoretical_ms
            deviation_ticks = int(round(deviation_ms / ms_per_step * ticks_per_step))

            # Estimar velocity basado en amplitud del onset
            if onset_frames.size > 0:
                frame_idx = int(onset_time * sr / 512)  # hop_length típico
                if frame_idx < len(onset_env):
                    amplitude = onset_env[frame_idx]
                    # Normalizar a 0-127
                    velocity = int(np.clip(amplitude * 100, 60, 127))
                else:
                    velocity = 100
            else:
                velocity = 100

            onset_info = OnsetInfo(
                time_ms=onset_ms,
                velocity=velocity,
                step=step_idx + 1,  # 1-indexed para Excel
                deviation_ticks=deviation_ticks
            )
            analysis.onsets.append(onset_info)

            # Actualizar rejilla y humanización (mantener el más fuerte si hay conflicto)
            if analysis.velocities[step_idx] < velocity:
                analysis.rejilla[step_idx] = 1
                analysis.velocities[step_idx] = velocity
                analysis.timings[step_idx] = deviation_ticks

        # Calcular vel_base como promedio de velocities activos
        active_vels = [v for v in analysis.velocities if v > 0]
        if active_vels:
            analysis.vel_base = int(sum(active_vels) / len(active_vels))

        self.analyses.append(analysis)

        print(f"   Pasos activos: {sum(analysis.rejilla)}")
        print(f"   Velocidad base: {analysis.vel_base}")

        return analysis

    def save(self) -> Tuple[int, int]:
        """
        Guarda todos los análisis en database.xlsx.

        Returns:
            Tuple (filas_rejillas, filas_humanizacion) añadidas
        """
        if not self.analyses:
            print("⚠️ No hay análisis para guardar")
            return (0, 0)

        wb = load_workbook(self.db_path)

        # ========== GUARDAR EN REJILLAS ==========
        rejillas_added = 0
        if 'REJILLAS' in wb.sheetnames:
            ws_rej = wb['REJILLAS']
        else:
            ws_rej = wb.create_sheet('REJILLAS')
            # Headers
            headers = ['ID_PATRON', 'INSTRUMENTO'] + [str(i) for i in range(1, 17)] + ['VEL_BASE']
            for col, h in enumerate(headers, 1):
                ws_rej.cell(row=1, column=col, value=h)

        last_row_rej = ws_rej.max_row

        for analysis in self.analyses:
            last_row_rej += 1
            ws_rej.cell(row=last_row_rej, column=1, value=analysis.pattern_id)
            ws_rej.cell(row=last_row_rej, column=2, value=analysis.instrument)
            for i, val in enumerate(analysis.rejilla):
                ws_rej.cell(row=last_row_rej, column=3 + i, value=val)
            ws_rej.cell(row=last_row_rej, column=19, value=analysis.vel_base)
            rejillas_added += 1

        # ========== GUARDAR EN HUMANIZACION ==========
        humanizacion_added = 0
        if 'HUMANIZACION' in wb.sheetnames:
            ws_hum = wb['HUMANIZACION']
        else:
            ws_hum = wb.create_sheet('HUMANIZACION')
            # Headers: ID_PATRON, INSTRUMENTO, V1-V16, T1-T16, DURATION
            headers = ['ID_PATRON', 'INSTRUMENTO']
            headers += [f'V{i}' for i in range(1, 17)]
            headers += [f'T{i}' for i in range(1, 17)]
            headers += ['DURATION']
            for col, h in enumerate(headers, 1):
                ws_hum.cell(row=1, column=col, value=h)

        last_row_hum = ws_hum.max_row

        for analysis in self.analyses:
            last_row_hum += 1
            ws_hum.cell(row=last_row_hum, column=1, value=analysis.pattern_id)
            ws_hum.cell(row=last_row_hum, column=2, value=analysis.instrument)

            # V1-V16 (columnas 3-18)
            for i, vel in enumerate(analysis.velocities):
                ws_hum.cell(row=last_row_hum, column=3 + i, value=vel)

            # T1-T16 (columnas 19-34)
            for i, timing in enumerate(analysis.timings):
                ws_hum.cell(row=last_row_hum, column=19 + i, value=timing)

            # DURATION (columna 35)
            ws_hum.cell(row=last_row_hum, column=35, value=120)  # Default
            humanizacion_added += 1

        wb.save(self.db_path)
        print(f"✅ Guardado: {rejillas_added} filas en REJILLAS, {humanizacion_added} en HUMANIZACION")

        return (rejillas_added, humanizacion_added)

    def clear_analyses(self):
        """Limpia los análisis pendientes."""
        self.analyses.clear()


def main():
    """CLI básico para Groove Extractor."""
    import argparse

    parser = argparse.ArgumentParser(description='Groove Extractor - Extrae humanización de audio')
    parser.add_argument('audio', help='Archivo de audio a analizar')
    parser.add_argument('--pattern', '-p', required=True, help='ID del patrón')
    parser.add_argument('--instrument', '-i', default='drums', help='Instrumento (kick, snare, hihat, drums)')
    parser.add_argument('--bpm', type=float, help='BPM (si no se especifica, se detecta)')
    parser.add_argument('--db', default='assets/database/database.xlsx', help='Ruta a database.xlsx')
    parser.add_argument('--bars', type=int, default=1, help='Número de compases a analizar')

    args = parser.parse_args()

    try:
        extractor = GrooveExtractor(args.db)
        extractor.analyze_audio(
            args.audio,
            pattern_id=args.pattern,
            instrument=args.instrument,
            bpm=args.bpm,
            bar_count=args.bars
        )
        extractor.save()
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
