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

            self.patterns[pid] = PatternInfo(
                id=pid,
                style_id=style_id,
                name=name,
                bpm=bpm,
                description=desc,
                source=src,
            )

    def _build_sidebar_index(self) -> None:
        idx: Dict[str, Dict[str, List[str]]] = {}

        for pid, p in self.patterns.items():
            idx.setdefault(p.style_id, {})
            idx[p.style_id].setdefault(p.source, [])
            idx[p.style_id][p.source].append(pid)

        # stable ordering
        for st, by_src in idx.items():
            for src, pids in by_src.items():
                pids.sort(key=lambda x: self.patterns[x].name.lower())
            idx[st] = dict(sorted(by_src.items(), key=lambda kv: kv[0].lower()))

        self.sidebar_index = dict(sorted(idx.items(), key=lambda kv: kv[0].lower()))

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
