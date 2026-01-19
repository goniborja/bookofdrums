"""core/database_manager.py

DatabaseManager for Book of Drums.

Uses database.xlsx to build a hierarchy for the Sidebar:
  Estilo -> Variacion (FUENTE) -> Patron

Playback stays in RhythmEngine; this module is only for UI organization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import os

import pandas as pd

from PyQt6.QtCore import QObject, pyqtSignal


@dataclass(frozen=True, slots=True)
class StyleInfo:
    id: str
    name: str
    bpm_min: int
    bpm_max: int
    bpm_typical: int
    feel: str
    swing: float
    description: str


@dataclass(frozen=True, slots=True)
class PatternInfo:
    id: str
    style_id: str
    name: str
    bpm: int
    description: str
    source: str
    tipo: str  # intro, break, groove, fills, outro


class DatabaseManager(QObject):
    """Read-only view over database.xlsx for UI needs."""

    dataLoaded = pyqtSignal()
    loadError = pyqtSignal(str)

    def __init__(self, db_path: str):
        super().__init__()
        self.db_path = db_path

        self.styles: Dict[str, StyleInfo] = {}
        self.patterns: Dict[str, PatternInfo] = {}

        # style_id -> source -> [pattern_ids]
        self.sidebar_index: Dict[str, Dict[str, List[str]]] = {}

        self.load()

    def load(self) -> None:
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Database not found: {self.db_path}")

        try:
            self._load_styles()
            self._load_patterns()
            self._build_sidebar_index()
            self.dataLoaded.emit()
        except Exception as e:
            try:
                self.loadError.emit(str(e))
            except Exception:
                pass
            raise

    def _load_styles(self) -> None:
        df = pd.read_excel(self.db_path, sheet_name="ESTILOS")
        required = {"ID", "NOMBRE", "BPM_MIN", "BPM_MAX", "BPM_TIPICO", "FEEL", "SWING", "DESCRIPCION"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"ESTILOS missing columns: {sorted(missing)}")

        self.styles.clear()
        for _, r in df.iterrows():
            sid = str(r["ID"]).strip()
            if not sid:
                continue
            swing = 0.0
            try:
                swing = float(r.get("SWING", 0.0)) / 100.0
            except Exception:
                swing = 0.0

            self.styles[sid] = StyleInfo(
                id=sid,
                name=str(r.get("NOMBRE", sid)).strip() or sid,
                bpm_min=int(r.get("BPM_MIN", 0) or 0),
                bpm_max=int(r.get("BPM_MAX", 0) or 0),
                bpm_typical=int(r.get("BPM_TIPICO", 120) or 120),
                feel=str(r.get("FEEL", "")).strip(),
                swing=swing,
                description=str(r.get("DESCRIPCION", "")).strip(),
            )

    def _load_patterns(self) -> None:
        df = pd.read_excel(self.db_path, sheet_name="PATRONES")
        required = {"ID_PATRON", "ESTILO", "NOMBRE", "BPM", "DESCRIPCION", "FUENTE"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"PATRONES missing columns: {sorted(missing)}")

        self.patterns.clear()
        for _, r in df.iterrows():
            pid = str(r["ID_PATRON"]).strip()
            if not pid:
                continue

            style_id = str(r["ESTILO"]).strip()
            name = str(r.get("NOMBRE", pid)).strip() or pid

            bpm = 120
            if pd.notna(r.get("BPM")):
                try:
                    bpm = int(r.get("BPM"))
                except Exception:
                    bpm = 120

            desc = str(r.get("DESCRIPCION", "")).strip()
            src = str(r.get("FUENTE", "")).strip() or "(Sin fuente)"

            # Detectar TIPO (de columna si existe, o por keywords)
            tipo = str(r.get("TIPO", "")).strip().lower() if "TIPO" in r.index else ""
            if not tipo:
                tipo = self._detect_tipo(name)

            self.patterns[pid] = PatternInfo(
                id=pid,
                style_id=style_id,
                name=name,
                bpm=bpm,
                description=desc,
                source=src,
                tipo=tipo,
            )

    def _detect_tipo(self, pattern_name: str) -> str:
        """Detecta el tipo de patrón por palabras clave."""
        name_lower = pattern_name.lower()
        if any(k in name_lower for k in ['intro', 'apertura', 'opening', 'count']):
            return 'intro'
        elif any(k in name_lower for k in ['break', 'corte', 'cut', 'stop']):
            return 'break'
        elif any(k in name_lower for k in ['fill', 'redoble', 'roll']):
            return 'fills'
        elif any(k in name_lower for k in ['outro', 'final', 'ending', 'end', 'coda']):
            return 'outro'
        return 'groove'

    def _build_sidebar_index(self) -> None:
        """Construye índice: TIPO -> ESTILO -> [pattern_ids]"""
        idx: Dict[str, Dict[str, List[str]]] = {}

        for pid, p in self.patterns.items():
            tipo = p.tipo or 'groove'
            idx.setdefault(tipo, {})
            idx[tipo].setdefault(p.style_id, [])
            idx[tipo][p.style_id].append(pid)

        # Ordenar patrones dentro de cada estilo
        for tipo, by_style in idx.items():
            for style, pids in by_style.items():
                pids.sort(key=lambda x: self.patterns[x].name.lower())
            idx[tipo] = dict(sorted(by_style.items(), key=lambda kv: kv[0].lower()))

        # Orden fijo de tipos
        tipo_order = ['intro', 'groove', 'break', 'fills', 'outro']
        self.sidebar_index = {t: idx.get(t, {}) for t in tipo_order if t in idx}

    # -------- UI helpers --------

    def style_label(self, style_id: str) -> str:
        st = self.styles.get(style_id)
        if not st:
            return style_id.upper()
        # example: "SKA  —  Ska"
        return f"{st.id.upper()}  —  {st.name}"

    def get_pattern_name(self, pattern_id: str) -> str:
        p = self.patterns.get(pattern_id)
        return p.name if p else pattern_id

    def get_pattern_source(self, pattern_id: str) -> str:
        p = self.patterns.get(pattern_id)
        return p.source if p else "(Sin fuente)"

    def get_style_ids(self) -> List[str]:
        return list(self.sidebar_index.keys())

    def get_sources(self, style_id: str) -> List[str]:
        return list(self.sidebar_index.get(style_id, {}).keys())

    def get_patterns_for(self, style_id: str, source: str) -> List[str]:
        return list(self.sidebar_index.get(style_id, {}).get(source, []))

    # -------- NEW: TIPO -> ESTILO -> PATRON helpers --------

    def get_tipos(self) -> List[str]:
        """Devuelve lista de tipos disponibles."""
        return list(self.sidebar_index.keys())

    def get_styles_for_tipo(self, tipo: str) -> List[str]:
        """Devuelve estilos que tienen patrones de ese tipo."""
        return list(self.sidebar_index.get(tipo, {}).keys())

    def get_patterns_for_tipo_style(self, tipo: str, style_id: str) -> List[str]:
        """Devuelve patrones de un tipo y estilo específicos."""
        return list(self.sidebar_index.get(tipo, {}).get(style_id, []))
