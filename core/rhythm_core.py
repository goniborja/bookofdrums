"""
UBICACIÓN: BookOfDrums/core/rhythm_core.py
Versión: 10.0 - Migrado a NoteEvent con soporte de micro-timing
 
Cambios principales:
- Usa RhythmBlock y NoteEvent de core/models.py
- Convierte rejillas de 16 pasos a lista de eventos
- Mantiene compatibilidad con código legacy (tracks dict)
- Prepara infraestructura para offset_ms futuro
"""
import os
import pandas as pd
from dataclasses import dataclass
from typing import Dict, Optional
 
# Importar nuevos modelos con NoteEvent
from core.models import (
    DrumInstrument,
    NoteEvent,
    RhythmBlock,
    convert_legacy_tracks_to_events
)
 
 
# ============================================================
# LEGACY CLASS - Mantener para compatibilidad con main.py
# ============================================================
 
@dataclass
class DrumStep:
    """
    Legacy format for 16-step grid.
    Kept for backward compatibility with existing UI code.
 
    IMPORTANTE: Esta clase debe permanecer aquí para que
    main.py pueda importarla:
    from core.rhythm_core import RhythmEngine, DrumStep, RhythmBlock
    """
    intensity: int = 0
    velocity_base: int = 100
    timing_ticks: int = 0       # Offset en ticks (puede ser negativo)
    duration_ticks: int = 120   # Duración de la nota

    @property
    def velocity_float(self) -> float:
        if self.intensity == 0:
            return 0.0
        return min(1.0, (self.velocity_base / 127.0))
 
 
# ============================================================
# RHYTHM ENGINE - Carga patrones desde database.xlsx
# ============================================================
 
class RhythmEngine:
    """
    Main pattern loader for Book of Drums.
 
    Loads from database.xlsx and creates RhythmBlock objects
    with both legacy tracks (dict) and modern events (list of NoteEvent).
    """
 
    def __init__(self):
        base_path = os.path.dirname(os.path.abspath(__file__))
        self.db_path = os.path.join(base_path, "..", "assets", "database", "database.xlsx")
        self._patterns: Dict[str, RhythmBlock] = {}
        self.load_database()
 
    def load_database(self):
        """
        Load patterns from database.xlsx.
 
        Sheets used:
        - ESTILOS: Style definitions with swing values
        - PATRONES: Pattern metadata
        - REJILLAS: 16-step grid data
 
        Creates both:
        - tracks (legacy dict format)
        - events (modern NoteEvent list with offset_ms=0.0)
        """
        if not os.path.exists(self.db_path):
            print(f"⚠️ Database no encontrada: {self.db_path}")
            return
 
        try:
            # ---- PASO 1: Cargar ESTILOS (para swing) ----
            estilos_swing = {}
            try:
                df_est = pd.read_excel(self.db_path, sheet_name='ESTILOS')
                for _, row in df_est.iterrows():
                    sid = str(row['ID']).strip()
                    try:
                        swing_val = float(row['SWING']) / 100.0
                        estilos_swing[sid] = swing_val
                    except Exception:
                        estilos_swing[sid] = 0.5  # default straight
            except Exception as e:
                print(f"⚠️ No se pudo cargar ESTILOS: {e}")
 
            # ---- PASO 2: Cargar PATRONES (metadata) ----
            df_pat = pd.read_excel(self.db_path, sheet_name='PATRONES')
            for _, row in df_pat.iterrows():
                pid = str(row['ID_PATRON']).strip()
                est = str(row['ESTILO']).strip()
 
                # Crear RhythmBlock con el nuevo modelo (de models.py)
                blk = RhythmBlock(
                    id_name=pid,
                    name_human=str(row['NOMBRE']),
                    estilo_id=est,
                    bpm=int(row['BPM']) if pd.notna(row['BPM']) else 120,
                    description=str(row['DESCRIPCION']) if pd.notna(row['DESCRIPCION']) else "",
                    swing_feel=estilos_swing.get(est, 0.5),
                    duration_bars=1,  # Por ahora todos son 1 compás
                    events=[],  # Se llenará después
                    tracks={},  # Legacy compatibility
                )
                self._patterns[pid] = blk
 
            # ---- PASO 3: Cargar REJILLAS (16 pasos) ----
            df_grid = pd.read_excel(self.db_path, sheet_name='REJILLAS')
            df_grid.columns = df_grid.columns.astype(str).str.strip()
 
            for _, row in df_grid.iterrows():
                pid = str(row['ID_PATRON']).strip()
                inst_name = str(row['INSTRUMENTO']).strip()
 
                if pid not in self._patterns:
                    continue
 
                blk = self._patterns[pid]
 
                # Obtener velocidad base
                try:
                    vel = int(row['VEL_BASE'])
                except Exception:
                    vel = 100
 
                # Crear lista de DrumStep (legacy format)
                steps = []
                for i in range(1, 17):
                    col_name = str(i)
                    try:
                        val = int(row.get(col_name, 0))
                    except Exception:
                        val = 0
 
                    intensity = 1 if val > 0 else 0
                    steps.append(DrumStep(intensity=intensity, velocity_base=vel))
 
                # Guardar en tracks (legacy)
                blk.tracks[inst_name] = steps

            # ---- PASO 4: Cargar HUMANIZACION (velocities y timings reales) ----
            try:
                df_human = pd.read_excel(self.db_path, sheet_name='HUMANIZACION')

                for _, row in df_human.iterrows():
                    pid = str(row['ID_PATRON']).strip()
                    inst = str(row['INSTRUMENTO']).strip()

                    if pid not in self._patterns:
                        continue

                    blk = self._patterns[pid]

                    if inst not in blk.tracks:
                        continue

                    # Leer V1-V16 (velocities) y T1-T16 (timings)
                    for step_num in range(1, 17):
                        step_idx = step_num - 1

                        if step_idx >= len(blk.tracks[inst]):
                            continue

                        step_obj = blk.tracks[inst][step_idx]

                        # Velocity de la columna Vn
                        vel_col = f'V{step_num}'
                        if vel_col in row.index and pd.notna(row[vel_col]):
                            vel = int(row[vel_col])
                            if vel > 0:
                                step_obj.intensity = 1
                                step_obj.velocity_base = vel

                        # Timing de la columna Tn (en ticks)
                        timing_col = f'T{step_num}'
                        if timing_col in row.index and pd.notna(row[timing_col]):
                            step_obj.timing_ticks = int(row[timing_col])

                    # Duration opcional
                    if 'DURATION' in row.index and pd.notna(row['DURATION']):
                        for step_obj in blk.tracks[inst]:
                            step_obj.duration_ticks = int(row['DURATION'])

                print(f"✅ Humanización cargada: velocities (V1-V16) y timings (T1-T16)")

            except Exception as e:
                print(f"⚠️ No se pudo cargar HUMANIZACION: {e}")

            # ---- PASO 5: Convertir tracks a events (NUEVO) ----
            for pid, blk in self._patterns.items():
                if blk.tracks:
                    # Convertir el dict legacy a lista de NoteEvent
                    events = convert_legacy_tracks_to_events(
                        tracks=blk.tracks,
                        bars=blk.duration_bars
                    )
                    blk.events = events

                    # Debug: mostrar cuántos eventos se crearon (solo primeros 3)
                    if events and len(self._patterns) <= 3:
                        print(f"✅ {pid}: {len(events)} eventos creados")

        except Exception as e:
            print(f"❌ Error cargando database.xlsx: {e}")
            import traceback
            traceback.print_exc()
 
    def get_pattern(self, pid: str) -> Optional[RhythmBlock]:
        """
        Obtener un patrón por ID.
 
        Returns:
            RhythmBlock con:
            - events: Lista de NoteEvent (NUEVO, para MIDI export)
            - tracks: Dict legacy (para compatibilidad UI)
        """
        return self._patterns.get(pid)
 
    def get_all_pattern_ids(self) -> list:
        """Obtener lista de todos los IDs de patrones disponibles."""
        return list(self._patterns.keys())
 
    def get_patterns_by_style(self, style_id: str) -> list:
        """Obtener todos los patrones de un estilo específico."""
        return [
            blk for blk in self._patterns.values()
            if blk.estilo_id.upper() == style_id.upper()
        ]