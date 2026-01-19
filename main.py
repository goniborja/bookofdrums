"""
UBICACIÓN: BookOfDrums/main.py
Versión: 27.1 (MIGRACIÓN FASE 3: INTEGRACIÓN DE MOTOR DE AUDIO)
"""
import sys
import os
import traceback
import json

# --- MIGRACIÓN: Importamos la Fábrica del Nuevo Motor ---
from audio.factory import create_audio_engine

# --- CONFIGURACIÓN DE LIBRERÍAS ---
print(">>> [SISTEMA] Cargando librerías...")

# 1. Pydub
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

# 2. PyQt6 y Core
try:
    from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                                 QHBoxLayout, QTreeWidget, QTreeWidgetItem, QLabel, 
                                 QPushButton, QComboBox, QGridLayout, QGroupBox, 
                                 QTableWidget, QTableWidgetItem, QHeaderView, 
                                 QAbstractItemView, QListWidget, QListWidgetItem,
                                 QSlider, QMessageBox, QDoubleSpinBox, QMenu, QFileDialog, QProgressDialog)
    from PyQt6.QtCore import Qt, QMimeData, QSize
    from PyQt6.QtGui import QColor, QDrag, QAction
    
    from core.rhythm_core import RhythmEngine, DrumStep, RhythmBlock
    # Nota: Mantenemos DrumSampler por ahora para la gestión de kits, 
    # pero el motor de audio real será el 'audio_backend'
    from core.audio_engine import DrumSampler, SequencePlayer
    print("   [OK] Core y Gráficos cargados.")

except Exception as e:
    print(f"\n!!! ERROR CRÍTICO AL IMPORTAR CORE: {e}")
    sys.exit(1)

# --- NUEVOS MÓDULOS (IMPORT SEGURO / NO ROMPE ARRANQUE) ---
ARRANGER_AVAILABLE = False
MIDI_EXPORT_AVAILABLE = False
DB_MANAGER_AVAILABLE = False

try:
    from core.database_manager import DatabaseManager
    DB_MANAGER_AVAILABLE = True
except Exception as e:
    print(f"   [WARN] DatabaseManager desactivado: {e}")

try:
    from ui.arranger_widget import ArrangerWidget
    ARRANGER_AVAILABLE = True
except Exception as e:
    print(f"   [WARN] ArrangerWidget desactivado: {e}")

try:
    from export.midi_exporter import MidiExporter
    MIDI_EXPORT_AVAILABLE = True
except Exception as e:
    print(f"   [WARN] MidiExporter desactivado: {e}")


# 3. Tempo Sync
TEMPO_SYNC_ERROR = None
SyncManagerClass = None
try:
    from core.tempo_sync import TempoSyncManager
    SyncManagerClass = TempoSyncManager
    print("   [OK] Módulo IA (TempoSync) cargado.")
except Exception as e:
    TEMPO_SYNC_ERROR = str(e)
    print(f"   [FALLO] No se cargó TempoSync: {e}")


# --- CLASES VISUALES ---
class DraggableTree(QTreeWidget):
    def __init__(self):
        super().__init__()
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setHeaderLabel("Estilo / Ritmo")
        self.setStyleSheet("background-color: #252015; color: #e8e0d0; border: 1px solid #4a3f30;")
    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item or not item.data(0, Qt.ItemDataRole.UserRole): return
        mime = QMimeData(); mime.setText(item.data(0, Qt.ItemDataRole.UserRole))
        drag = QDrag(self); drag.setMimeData(mime); drag.exec(supportedActions)

class TimelineWidget(QListWidget):
    def __init__(self, parent_app):
        super().__init__()
        self.parent_app = parent_app
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(False)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setSpacing(4)
        self.setFixedHeight(110)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True); self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setStyleSheet("""
            QListWidget { background-color: #050505; border: 1px solid #333; border-left: 4px solid #c9a227; }
            QListWidget::item { border-radius: 2px; color: #fff; font-weight: bold; border: 1px solid rgba(255,255,255,0.1); }
            QListWidget::item:selected { border: 2px solid #fff; background-color: rgba(255,255,255,0.2); }
        """)
    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item: return
        mime = QMimeData(); mime.setText(item.data(Qt.ItemDataRole.UserRole))
        drag = QDrag(self); drag.setMimeData(mime); drag.exec(supportedActions)
    def dragEnterEvent(self, e): e.accept() if e.mimeData().hasText() else e.ignore()
    def dragMoveEvent(self, e): 
        if e.mimeData().hasText():
            e.setDropAction(Qt.DropAction.MoveAction if e.source() == self else Qt.DropAction.CopyAction)
            e.accept()
        else: e.ignore()
    def dropEvent(self, e):
        if e.source() == self:
            e.ignore(); curr = self.currentItem(); 
            if not curr: return
            old = self.row(curr)
            try: pos = e.position().toPoint()
            except: pos = e.pos()
            tgt = self.itemAt(pos); new_r = self.row(tgt) if tgt else self.count() - 1
            self.takeItem(old); self.insertItem(new_r, curr); self.setCurrentItem(curr)
            self.parent_app.rebuild_song_from_ui()
        elif e.mimeData().hasText():
            e.setDropAction(Qt.DropAction.CopyAction)
            self.add_block(e.mimeData().text()); e.accept()
            self.parent_app.rebuild_song_from_ui()
    def add_block(self, pid):
        b = self.parent_app.engine.get_pattern(pid)
        if not b: return
        n = b.name_human
        name_lower = n.lower()
        if "intro" in name_lower: c = QColor("#2d4a25")
        elif "outro" in name_lower: c = QColor("#252d4a")
        elif "fill" in name_lower: c = QColor("#662222")
        elif "chorus" in name_lower: c = QColor("#c9a227")
        else: c = QColor("#2a2318")
        it = QListWidgetItem(f"{n}\n{b.bpm} BPM")
        it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        it.setData(Qt.ItemDataRole.UserRole, pid); it.setBackground(c)
        it.setForeground(QColor("#000") if c == QColor("#c9a227") else QColor("#e0e0e0"))
        it.setSizeHint(QSize(110, 80)); self.addItem(it); self.scrollToBottom()
    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Delete:
            for i in self.selectedItems(): self.takeItem(self.row(i))
            self.parent_app.rebuild_song_from_ui()
        else: super().keyPressEvent(e)

# --- APP ---
class BookOfDrumsApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Book of Drums — The Reggae Architect (V27.1)")
        self.resize(1400, 950)
        
        # STYLESHEET CORREGIDO: QMessageBox forzado a Blanco/Negro
        self.setStyleSheet("""
            QMainWindow { background-color: #1a1510; }
            QMenuBar { background-color: #0f0c08; color: #e8e0d0; }
            QMenuBar::item:selected { background-color: #c9a227; color: #000; }
            QMenu { background-color: #252015; color: #e8e0d0; border: 1px solid #4a3f30; }
            QMenu::item:selected { background-color: #c9a227; color: #000; }
            QLabel { color: #e8e0d0; font-family: 'Segoe UI'; }
            QGroupBox { color: #c9a227; font-weight: bold; border: 1px solid #4a3f30; margin-top: 10px; padding-top: 20px; }
            QPushButton { background-color: #2a2318; color: #e8e0d0; border: 1px solid #4a3f30; padding: 6px; }
            QDoubleSpinBox, QComboBox { background-color: #0a0908; color: #c9a227; border: 1px solid #4a3f30; }
            QTableWidget { background-color: #0a0908; gridline-color: #333; color: #fff; border: none; }
            
            /* FIX PARA MENSAJES EMERGENTES ILEGIBLES */
            QMessageBox { background-color: #f0f0f0; color: #000000; }
            QMessageBox QLabel { color: #000000; }
            QMessageBox QPushButton { background-color: #ddd; color: #000; border: 1px solid #aaa; }
        """)
        
        # --- MIGRACIÓN PASO 3.2: Inicialización del Audio Backend ---
        # Esto usará config.py para decidir si arranca Pygame o SoundDevice
        try:
            print(">>> [INIT] Inicializando Backend de Audio...")
            self.audio_backend = create_audio_engine()
            self.audio_backend.initialize()
        except Exception as e:
            print(f"!!! Error fatal iniciando backend de audio: {e}")

        # Core Engines
        self.engine = RhythmEngine()

        # DatabaseManager (Sidebar data-driven)
        self.dbm = None
        if DB_MANAGER_AVAILABLE:
            try:
                self.dbm = DatabaseManager(self.engine.db_path)
                print(">>> [DB] DatabaseManager activo (Sidebar data-driven).")
            except Exception as e:
                self.dbm = None
                print(f">>> [DB] DatabaseManager desactivado: {e}")
        assets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
        # Pasamos el backend (SoundDevice) al sampler
        self.sampler = DrumSampler(assets_path, audio_engine=self.audio_backend)
        self.current_player = None
        self.instrument_combos = {} 
        self.song_data_objects = []
        self.current_editing_id = None
        self.global_swing = 0.5 
        self.current_bpm = 78.0 
        
        self.sync_manager = None
        self.init_sync_manager()
        self.init_ui()

    def init_sync_manager(self):
        if TEMPO_SYNC_ERROR: return
        if SyncManagerClass:
            try:
                self.sync_manager = SyncManagerClass(genero='one_drop')
                print(">>> IA Audio: LISTA")
            except Exception as e:
                self.sync_init_error = str(e); self.sync_manager = None

    def init_ui(self):
        menubar = self.menuBar()
        fm = menubar.addMenu("Archivo")
        fm.addAction("📂 Abrir Proyecto...", self.load_project_dialog)
        fm.addAction("💾 Guardar Proyecto...", self.save_project_dialog)
        fm.addSeparator()
        
        if self.sync_manager:
            act_imp = QAction("⬇️ Inportatu audioa (Auto-BPM)...", self)
            act_imp.triggered.connect(self.import_audio_smart)
            fm.addAction(act_imp)
        else:
            act_imp = QAction("⚠️ Inportatu audioa (Error de carga)", self)
            act_imp.triggered.connect(self.show_sync_error)
            fm.addAction(act_imp)

        fm.addAction("⬆️ Exportar Canción a WAV...", self.export_wav_dialog)
        fm.addAction("⬆️ Exportar Canción a MIDI...", self.export_midi_dialog)
        
        main = QWidget(); self.setCentralWidget(main); layout = QHBoxLayout(main)
        
        left = QVBoxLayout()
        g_tempo = QGroupBox("⏱️ MASTER TEMPO")
        h_tempo = QHBoxLayout()
        h_tempo.addWidget(QLabel("BPM:"))
        self.spin_bpm = QDoubleSpinBox(); self.spin_bpm.setRange(40.0, 200.0); self.spin_bpm.setValue(self.current_bpm)
        self.spin_bpm.valueChanged.connect(self.update_bpm)
        h_tempo.addWidget(self.spin_bpm)
        g_tempo.setLayout(h_tempo)
        left.addWidget(g_tempo)
        
        self.lbl_backing = QLabel("🎸 Guitarra: Ninguna")
        self.lbl_backing.setStyleSheet("color: #666; font-style: italic;")
        left.addWidget(self.lbl_backing)
        
        self.btn_offset = QPushButton("🛠️ Ajustar Retardo")
        self.btn_offset.setEnabled(False)
        left.addWidget(self.btn_offset)

        left.addWidget(QLabel("📚 RITMOS"))
        self.tree = DraggableTree() 
        self.populate_tree()
        self.tree.itemClicked.connect(self.on_tree_click)
        left.addWidget(self.tree)
        
        h_trans = QHBoxLayout()
        self.btn_preview = QPushButton("▶ Preview Loop")
        self.btn_preview.setStyleSheet("background-color: #4a7c52; color: white;")
        self.btn_preview.clicked.connect(self.play_preview)
        btn_stop = QPushButton("⏹ Stop"); btn_stop.clicked.connect(self.stop_playback)
        h_trans.addWidget(self.btn_preview); h_trans.addWidget(btn_stop)
        left.addLayout(h_trans)
        layout.addLayout(left, 1)
        
        right = QVBoxLayout()
        g_sound = QGroupBox("🎛️ RACK & SWING")
        v_sound = QVBoxLayout()
        h_swing = QHBoxLayout()
        self.lbl_swing = QLabel("Swing: 50%")
        self.slider_swing = QSlider(Qt.Orientation.Horizontal); self.slider_swing.setRange(50, 75); self.slider_swing.setValue(50)
        self.slider_swing.valueChanged.connect(self.update_swing)
        h_swing.addWidget(self.lbl_swing); h_swing.addWidget(self.slider_swing)
        v_sound.addLayout(h_swing)
        
        h_kit = QHBoxLayout()
        self.cb_kit = QComboBox(); self.cb_kit.addItems(self.sampler.available_kits)
        self.cb_kit.currentTextChanged.connect(self.change_kit)
        h_kit.addWidget(QLabel("Kit:")); h_kit.addWidget(self.cb_kit, 1)
        v_sound.addLayout(h_kit)
        
        grid_inst = QGridLayout()
        self.inst_keys = ["kick", "snare", "rim", "hihat_cl", "hihat_op", "cymbal", "tom"]
        for i, k in enumerate(self.inst_keys):
            r = 0 if i < 4 else 2; c = i if i < 4 else i-4
            grid_inst.addWidget(QLabel(k.upper()), r, c)
            cb = QComboBox(); self.instrument_combos[k] = cb
            cb.activated.connect(lambda idx, key=k: self.change_sample(key))
            grid_inst.addWidget(cb, r+1, c)
        v_sound.addLayout(grid_inst)
        g_sound.setLayout(v_sound)
        right.addWidget(g_sound)
        
        g_edit = QGroupBox("🎹 EDITOR")
        v_edit = QVBoxLayout()
        self.grid = QTableWidget(7, 16)
        self.grid.setVerticalHeaderLabels(["Kick", "Snare", "Rim", "HH Cl", "HH Op", "Cymbal", "Tom"])
        self.grid.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.grid.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.grid.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.grid.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.grid.cellClicked.connect(self.on_grid_cell_click)
        v_edit.addWidget(self.grid)
        g_edit.setLayout(v_edit)
        right.addWidget(g_edit, 1)
        
        g_arr = QGroupBox("🎼 ARRANGER")
        v_arr = QVBoxLayout()

        # --- SNAP CONTROL (Step 9) ---
        self.cb_snap = None
        if ARRANGER_AVAILABLE:
            try:
                snap_row = QHBoxLayout()
                snap_row.addWidget(QLabel("Snap:"))
                self.cb_snap = QComboBox()
                self.cb_snap.addItems(["Bar", "1/2", "1/4", "1/8", "1/16"])
                self.cb_snap.setCurrentText("Bar")
                self.cb_snap.currentTextChanged.connect(self.on_snap_changed)
                snap_row.addWidget(self.cb_snap)
                snap_row.addStretch(1)
                v_arr.addLayout(snap_row)
            except Exception:
                self.cb_snap = None

        # --- NUEVO ARRANGER (QGraphicsView) con fallback al Timeline legacy ---
        if ARRANGER_AVAILABLE:
            self.timeline_widget = ArrangerWidget(parent_app=self, engine=self.engine)
            # Rebuild automático cuando cambie el arrangement
            if hasattr(self.timeline_widget, "arrangementChanged"):
                try:
                    self.timeline_widget.arrangementChanged.connect(self.rebuild_song_from_ui)
                except Exception:
                    pass
        else:
            self.timeline_widget = TimelineWidget(self)
        v_arr.addWidget(self.timeline_widget)
        h_arr = QHBoxLayout()
        btn_play_song = QPushButton("▶ REPRODUCIR CANCIÓN")
        btn_play_song.setStyleSheet("background-color: #4a7c52; color: white;")
        btn_play_song.clicked.connect(self.play_song)
        btn_clear = QPushButton("🗑️ Borrar"); btn_clear.clicked.connect(self.clear_timeline)
        h_arr.addWidget(btn_play_song); h_arr.addWidget(btn_clear)
        v_arr.addLayout(h_arr)
        g_arr.setLayout(v_arr)
        
        right.addWidget(g_arr)
        layout.addLayout(right, 3)
        self.refresh_instrument_combos()

    def show_sync_error(self):
        msg = "No se pudo activar la IA de Audio.\n\n"
        if TEMPO_SYNC_ERROR: msg += f"Razón: {TEMPO_SYNC_ERROR}\n"
        elif hasattr(self, 'sync_init_error'): msg += f"Razón: {self.sync_init_error}"
        else: msg += "Razón desconocida."
        QMessageBox.warning(self, "Error IA", msg)

    def import_audio_smart(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Inportatu Audioa", "", "Audio Files (*.wav)")
        if not fname: return
        
        progress = QProgressDialog("Analizando BPM...", "Cancelar", 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal); progress.show()
        QApplication.processEvents()
        
        try:
            bpm, confidence = self.sync_manager.cargar_referencia(fname)
            progress.setValue(100)
            if bpm:
                msg = f"Detectado: {bpm:.2f} BPM\nConfianza: {confidence*100:.0f}%\n\n¿Ajustar proyecto?"
                r = QMessageBox.question(self, "BPM Detectado", msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if r == QMessageBox.StandardButton.Yes: self.spin_bpm.setValue(bpm)
            
            # --- AQUÍ FALLABA ANTES: Ahora llamamos a load_backing_track que ya existe en audio_engine ---
            if self.sampler.load_backing_track(fname):
                self.lbl_backing.setText(f"🎸 {os.path.basename(fname)}")
                self.lbl_backing.setStyleSheet("color: #4a7c52; font-weight: bold;")
                self.btn_offset.setEnabled(True)
                
        except Exception as e:
            QMessageBox.critical(self, "Error Análisis", f"Falló el análisis:\n{e}")

    def export_wav_dialog(self):
        if not PYDUB_AVAILABLE: return QMessageBox.critical(self, "Error", "Instala 'pydub' para exportar.")
        self.rebuild_song_from_ui()
        if not self.song_data_objects: return QMessageBox.warning(self, "Aviso", "Timeline vacía.")
        f, _ = QFileDialog.getSaveFileName(self, "Exportar", "mix.wav", "WAV (*.wav)")
        if f: self.render_audio_to_file(f)
    def export_midi_dialog(self):
        """Step 9: Export MIDI from the rendered timeline.

        With sub-bar snapping (1/2, 1/4, 1/8, 1/16), exporting via
        (pattern_id, start_bar) would lose the sub-bar offset.

        We rebuild the song into 1-bar blocks (16 steps) that already include
        the offsets and export sequentially.
        """
        if not MIDI_EXPORT_AVAILABLE:
            return QMessageBox.critical(self, "Error", "MidiExporter no disponible (revisa export/midi_exporter.py).")

        self.rebuild_song_from_ui()
        if not self.song_data_objects:
            return QMessageBox.warning(self, "Aviso", "Timeline vacía.")

        f, _ = QFileDialog.getSaveFileName(self, "Exportar MIDI", "song.mid", "MIDI (*.mid)")
        if not f:
            return

        try:
            exporter = MidiExporter(ppq=960)
            exporter.export_patterns(
                f,
                self.song_data_objects,
                bpm=float(self.current_bpm),
                swing=float(self.global_swing),
                apply_human_feel=True,
            )
            QMessageBox.information(self, "Éxito", "¡Archivo MIDI exportado!")
        except Exception as e:
            QMessageBox.critical(self, "Error Exportando MIDI", str(e))

    def render_audio_to_file(self, filename):
        progress = QProgressDialog("Renderizando...", "Cancelar", 0, len(self.song_data_objects), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal); progress.show()
        bpm = self.current_bpm
        ms_step = (60000.0 / bpm) / 4.0
        master = AudioSegment.silent(duration=0)
        cache = {}
        km = { "kick":"kick", "bombo":"kick", "snare":"snare", "caja":"snare", "full":"snare", "rim":"rim", "stick":"rim", "hihat_closed":"hihat_cl", "chat":"hihat_cl", "closed":"hihat_cl", "hihat_open":"hihat_op", "ohat":"hihat_op", "open":"hihat_op", "cymbal":"cymbal", "crash":"cymbal", "tom":"tom", "perc":"tom" }
        for idx, pat in enumerate(self.song_data_objects):
            if progress.wasCanceled(): return
            progress.setValue(idx)
            blk_ms = ms_step * 16
            blk_aud = AudioSegment.silent(duration=blk_ms)
            sw_del = 0
            if self.global_swing > 0.5: sw_del = ms_step * ((self.global_swing-0.5)*1.5)
            for trk, steps in pat.tracks.items():
                ikey = None; tlow = trk.lower()
                for ks, kr in km.items():
                    if ks in tlow:
                        if kr == "snare" and ("rim" in tlow or "stick" in tlow): continue
                        ikey = kr; break
                if not ikey: continue
                sf = self.sampler.current_selection.get(ikey)
                if not sf: continue
                if sf not in cache:
                    fp = self.find_file_in_kit(sf)
                    if fp: 
                        try: cache[sf] = AudioSegment.from_wav(fp)
                        except: continue
                    else: continue
                sseg = cache[sf]
                for i in range(min(16, len(steps))):
                    st = steps[i]
                    if st.intensity > 0:
                        pos = i * ms_step
                        if (i%2!=0) and sw_del > 0: pos += sw_del
                        g_db = (st.velocity_base - 127) / 3.0
                        if g_db < -40: g_db = -100
                        blk_aud = blk_aud.overlay(sseg + g_db, position=pos)
            master += blk_aud
        peak = master.max_dBFS
        if peak > -1.0: master = master.apply_gain(-1.0 - peak)
        try:
            master.export(filename, format="wav")
            progress.setValue(len(self.song_data_objects))
            QMessageBox.information(self, "Éxito", "¡Archivo WAV exportado!")
        except Exception as e: QMessageBox.critical(self, "Error Exportando", str(e))

    def find_file_in_kit(self, f):
        kp = os.path.join(self.sampler.assets_path, self.sampler.current_kit_name)
        for r, _, fl in os.walk(kp):
            if f in fl: return os.path.join(r, f)
        return None
    def save_project_dialog(self):
        f, _ = QFileDialog.getSaveFileName(self, "Guardar", "", "BOD Files (*.bod)")
        if f: self.save_project(f)
    def load_project_dialog(self):
        f, _ = QFileDialog.getOpenFileName(self, "Abrir", "", "BOD Files (*.bod)")
        if f: self.load_project(f)
    def save_project(self, f):
        """Guarda proyecto.

        Step 5: si el timeline es el Arranger (QGraphicsView), guarda posiciones reales
        (pattern_id + start_bar + bars). Mantiene también un campo legacy 'timeline'
        con solo IDs para compatibilidad.
        """
        timeline_ids = []
        placements = []

        # Arranger nuevo (preferido)
        if hasattr(self.timeline_widget, "get_arrangement_placements"):
            try:
                pls = list(self.timeline_widget.get_arrangement_placements())
            except Exception:
                pls = []

            for pl in pls:
                try:
                    pid = getattr(pl, 'pattern_id', None)
                    start_bar = getattr(pl, 'start_bar', None)
                    bars = getattr(pl, 'bars', 1)

                    # tuple/list fallback
                    if pid is None and isinstance(pl, (list, tuple)) and len(pl) >= 2:
                        pid = pl[0]
                        start_bar = pl[1]
                        bars = pl[2] if len(pl) >= 3 else 1

                    if pid is None or start_bar is None:
                        continue

                    # Step 9: store start_step (1/16 bar) when available
                    start_step = getattr(pl, 'start_step', None)
                    if start_step is None and isinstance(pl, dict):
                        start_step = pl.get('start_step', None)
                    try:
                        if start_step is not None:
                            start_step_i = int(start_step)
                            start_bar_i = max(0, start_step_i // 16)
                        else:
                            start_bar_i = int(start_bar)
                            start_step_i = max(0, start_bar_i) * 16
                    except Exception:
                        start_bar_i = 0
                        start_step_i = 0

                    placements.append({
                        "pattern_id": str(pid),
                        "start_bar": int(start_bar_i),
                        "start_step": int(start_step_i),
                        "bars": int(bars),
                    })
                    timeline_ids.append(str(pid))
                except Exception:
                    continue

        # Fallback: Arranger legacy IDs
        elif hasattr(self.timeline_widget, "get_arrangement"):
            try:
                timeline_ids = list(self.timeline_widget.get_arrangement())
            except Exception:
                timeline_ids = []

        # Timeline QListWidget
        else:
            timeline_ids = [
                self.timeline_widget.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.timeline_widget.count())
            ]

        data = {
            "version": "1.1",
            "bpm": float(self.current_bpm),
            "swing": float(self.global_swing),
            "kit": self.cb_kit.currentText(),
            "timeline": timeline_ids,
            "timeline_placements": placements,
        }

        try:
            with open(f, 'w', encoding='utf-8') as fh:
                json.dump(data, fh, indent=4, ensure_ascii=False)
            QMessageBox.information(self, "Ok", "Guardado.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"{e}")

    def load_project(self, f):
        """Carga proyecto.

        Step 5: si hay 'timeline_placements' y el timeline es Arranger, restaura
        posiciones reales en compases.
        """
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                data = json.load(fh)

            if "bpm" in data:
                self.spin_bpm.setValue(float(data["bpm"]))
            if "swing" in data:
                try:
                    self.slider_swing.setValue(int(float(data["swing"]) * 100))
                except Exception:
                    pass
            if "kit" in data:
                self.cb_kit.setCurrentText(data["kit"])

            # Limpiar timeline compatible
            if hasattr(self.timeline_widget, "clear_all"):
                self.timeline_widget.clear_all()
            else:
                self.timeline_widget.clear()

            self.song_data_objects = []

            placements = data.get("timeline_placements", [])

            # Preferido: restaurar placements reales en Arranger
            if placements and hasattr(self.timeline_widget, "set_arrangement_placements"):
                try:
                    self.timeline_widget.set_arrangement_placements(placements)
                except Exception:
                    # fallback a inserción secuencial si algo falla
                    placements = []

            # Fallback: insertar en orden secuencial
            if not placements:
                for pid in data.get("timeline", []):
                    if not self.engine.get_pattern(pid):
                        continue
                    if hasattr(self.timeline_widget, "add_clip"):
                        self.timeline_widget.add_clip(pid)
                    else:
                        self.timeline_widget.add_block(pid)

            self.rebuild_song_from_ui()
            QMessageBox.information(self, "Ok", "Cargado.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"{e}")
    def populate_tree(self):
        """Rellena el árbol de ritmos.

        Prioridad: jerarquía real de database.xlsx vía DatabaseManager
        (Estilo -> Fuente/Variación -> Patrón).

        Fallback: grouping legacy basado en RhythmEngine.
        """
        self.tree.clear()

        # --- Sidebar data-driven (database.xlsx) ---
        if getattr(self, 'dbm', None):
            for style_id in self.dbm.get_style_ids():
                style_node = QTreeWidgetItem(self.tree)
                style_node.setText(0, self.dbm.style_label(style_id))
                style_node.setExpanded(True)

                for fuente in self.dbm.get_sources(style_id):
                    fuente_node = QTreeWidgetItem(style_node)
                    fuente_node.setText(0, fuente)
                    fuente_node.setExpanded(False)

                    for pid in self.dbm.get_patterns_for(style_id, fuente):
                        # Playback compatibility: only patterns known by RhythmEngine
                        if not self.engine.get_pattern(pid):
                            continue
                        item = QTreeWidgetItem(fuente_node)
                        item.setText(0, self.dbm.get_pattern_name(pid))
                        item.setData(0, Qt.ItemDataRole.UserRole, pid)
            return

        # --- Fallback legacy (por keywords) ---
        grouped = {}
        for pid, b in self.engine._patterns.items():
            est = b.estilo_id.upper()
            if est not in grouped: grouped[est] = []
            grouped[est].append(b)
        for est in sorted(grouped.keys()):
            style_node = QTreeWidgetItem(self.tree); style_node.setText(0, est); style_node.setExpanded(True)
            loops_node = QTreeWidgetItem(style_node); loops_node.setText(0, '🔄 Grooves'); loops_node.setExpanded(True)
            fills_node = QTreeWidgetItem(style_node); fills_node.setText(0, '🔥 Fills & Cortes'); fills_node.setExpanded(True)
            has_loops = False; has_fills = False
            for b in grouped[est]:
                kws = ['fill', 'intro', 'outro', 'break', 'roll', 'end']
                is_fill = any(k in b.name_human.lower() for k in kws)
                target = fills_node if is_fill else loops_node
                item = QTreeWidgetItem(target); item.setText(0, b.name_human); item.setData(0, Qt.ItemDataRole.UserRole, b.id_name)
                if is_fill: has_fills = True
                else: has_loops = True
            if not has_loops: style_node.removeChild(loops_node)
            if not has_fills: style_node.removeChild(fills_node)

    def rebuild_song_from_ui(self):
        """Reconstruye self.song_data_objects a partir del timeline.

        Step 8: respetaba huecos por compases (start_bar).
        Step 9: soporta offsets sub-compas via start_step (1 step = 1/16 compas).
        """
        self.song_data_objects = []

        # ---- Arranger (preferido): placements con start_step/start_bar ----
        if hasattr(self.timeline_widget, "get_arrangement_placements"):
            try:
                placements = list(self.timeline_widget.get_arrangement_placements())
            except Exception:
                placements = []

            norm = []
            for pl in placements:
                try:
                    pid = getattr(pl, 'pattern_id', None)
                    bars = getattr(pl, 'bars', 1)
                    start_step = getattr(pl, 'start_step', None)
                    start_bar = getattr(pl, 'start_bar', None)
                    if pid is None and isinstance(pl, (list, tuple)) and len(pl) >= 2:
                        pid = pl[0]
                        start_bar = pl[1]
                        bars = pl[2] if len(pl) >= 3 else 1
                    if pid is None:
                        continue
                    if start_step is None:
                        if start_bar is None:
                            start_bar = 0
                        start_step = int(start_bar) * 16
                    norm.append({
                        'pattern_id': str(pid),
                        'start_step': max(0, int(start_step)),
                        'bars': max(1, int(bars) if bars else 1),
                    })
                except Exception:
                    continue

            if not norm:
                return

            norm.sort(key=lambda d: (d['start_step'], d['pattern_id']))

            # Timeline length in 16th steps
            end_step = 0
            for d in norm:
                end_step = max(end_step, d['start_step'] + d['bars'] * 16)
            total_bars = (end_step + 15) // 16

            def _make_empty_bar(bar_index: int):
                return RhythmBlock(
                    id_name=f'__bar__{bar_index}',
                    name_human=f'Bar {bar_index+1}',
                    estilo_id='song',
                    bpm=int(self.current_bpm),
                    description='(arranger)',
                    tracks={},
                    swing_feel=0.5,
                )

            bars_out = [_make_empty_bar(i) for i in range(total_bars)]

            def _ensure_track(block: RhythmBlock, track_name: str):
                if track_name not in block.tracks:
                    block.tracks[track_name] = [DrumStep(0, 100) for _ in range(16)]
                if len(block.tracks[track_name]) < 16:
                    block.tracks[track_name] = (block.tracks[track_name] + [DrumStep(0, 100) for _ in range(16)])[:16]

            for d in norm:
                pid = d['pattern_id']
                start_step = d['start_step']
                rep_bars = d['bars']
                blk = self.engine.get_pattern(pid)
                if not blk:
                    continue

                for rep in range(rep_bars):
                    for s in range(16):
                        gstep = start_step + rep * 16 + s
                        bi = gstep // 16
                        si = gstep % 16
                        if bi < 0 or bi >= len(bars_out):
                            continue
                        target = bars_out[bi]
                        for tname, steps in (blk.tracks or {}).items():
                            if not steps or len(steps) <= s:
                                continue
                            src = steps[s]
                            if getattr(src, 'intensity', 0) <= 0:
                                continue
                            _ensure_track(target, tname)
                            dst = target.tracks[tname][si]
                            # Merge policy: keep strongest hit
                            if src.intensity > dst.intensity:
                                dst.intensity = int(src.intensity)
                                dst.velocity_base = int(getattr(src, 'velocity_base', 100))
                            elif src.intensity == dst.intensity:
                                dst.velocity_base = max(int(getattr(src, 'velocity_base', 100)), int(getattr(dst, 'velocity_base', 100)))

            # Trim trailing empty bars
            def _is_empty_bar(block: RhythmBlock) -> bool:
                for steps in (block.tracks or {}).values():
                    for st in steps:
                        if getattr(st, 'intensity', 0) > 0:
                            return False
                return True

            while bars_out and _is_empty_bar(bars_out[-1]):
                bars_out.pop()

            self.song_data_objects = bars_out
            return

        # ---- Arranger legacy: lista ordenada de IDs (sin huecos) ----
        if hasattr(self.timeline_widget, "get_arrangement"):
            try:
                ids = list(self.timeline_widget.get_arrangement())
            except Exception:
                ids = []
            for pid in ids:
                blk = self.engine.get_pattern(pid)
                if blk:
                    self.song_data_objects.append(blk)
            return

        # ---- Timeline legacy (QListWidget) ----
        for i in range(self.timeline_widget.count()):
            pid = self.timeline_widget.item(i).data(Qt.ItemDataRole.UserRole)
            blk = self.engine.get_pattern(pid)
            if blk:
                self.song_data_objects.append(blk)


    def play_song(self):
        self.stop_playback(); self.rebuild_song_from_ui()
        if not self.song_data_objects: return
        for b in self.song_data_objects: b.swing_feel = self.global_swing
        self.current_player = SequencePlayer(self.sampler, self.song_data_objects, self.current_bpm, False)
        self.current_player.start()
    def clear_timeline(self):
        # Compatible con Arranger nuevo y Timeline legacy
        if hasattr(self.timeline_widget, "clear_all"):
            self.timeline_widget.clear_all()
        else:
            self.timeline_widget.clear()
        self.song_data_objects = []
    def update_bpm(self, val):
        self.current_bpm = val
        if self.current_player: self.current_player.bpm = val
    def update_swing(self, val):
        self.global_swing = val / 100.0
        self.lbl_swing.setText(f"Swing: {val}%")
        if self.current_player and hasattr(self.current_player, 'pattern'):
            self.current_player.pattern.swing_feel = self.global_swing

    def on_snap_changed(self, txt: str):
        """Step 9: update Arranger snap grid."""
        if not hasattr(self, 'timeline_widget'):
            return
        mapping = {"Bar": 1, "1/2": 2, "1/4": 4, "1/8": 8, "1/16": 16}
        div = mapping.get(str(txt).strip(), 1)
        if hasattr(self.timeline_widget, 'set_snap_divisor'):
            try:
                self.timeline_widget.set_snap_divisor(div)
            except Exception:
                pass

    def on_grid_cell_click(self, r, c):
        if not self.current_editing_id: return
        pat = self.engine.get_pattern(self.current_editing_id)
        if not pat: return
        t_map = {0:"kick", 1:"snare_full", 2:"snare_crossstick", 3:"hihat_closed", 4:"hihat_open", 5:"crash", 6:"tom_high"}
        t = t_map.get(r, "perc")
        if t not in pat.tracks: pat.tracks[t] = [DrumStep(0, 100) for _ in range(16)]
        s = pat.tracks[t][c]
        v = s.velocity_base if s.intensity > 0 else 0
        if v == 0: nv = 60
        elif v <= 70: nv = 100
        elif v <= 110: nv = 127
        else: nv = 0
        s.intensity = 1 if nv > 0 else 0; s.velocity_base = nv
        self.update_single_cell(r, c, nv)
        if nv > 0 and r < len(self.inst_keys): self.sampler.play_one_shot(self.inst_keys[r], nv/127.0)
    def update_single_cell(self, r, c, v):
        it = self.grid.item(r, c)
        if not it: it = QTableWidgetItem(); self.grid.setItem(r, c, it)
        if v == 0: it.setBackground(QColor("#15120d")); it.setText("")
        elif v <= 70: it.setBackground(QColor("#4a3f30")); it.setText("•")
        elif v <= 110: it.setBackground(QColor("#c9a227")); it.setText("")
        else: it.setBackground(QColor("#ffcc00")); it.setText("★")
    def on_tree_click(self, item, col):
        pid = item.data(0, Qt.ItemDataRole.UserRole)
        if pid: self.current_editing_id = pid; self.update_visualizer(pid)
    def update_visualizer(self, pid):
        b = self.engine.get_pattern(pid); self.grid.clearContents()
        if not b: return
        rk = {0:["kick","bombo"], 1:["snare","caja","full"], 2:["rim","stick","cross"], 3:["hihat_closed","chat"], 4:["hihat_open","ohat"], 5:["cymbal","crash"], 6:["tom","perc"]}
        for r, ks in rk.items():
            mg=[0]*16; mv=[0]*16
            for tn, ss in b.tracks.items():
                if r==1 and ("rim" in tn or "stick" in tn): continue
                if any(k in tn.lower() for k in ks):
                    for i in range(min(16, len(ss))):
                        if ss[i].intensity > 0: mg[i]=1; mv[i]=max(mv[i],ss[i].velocity_base)
            for c in range(16): self.update_single_cell(r, c, mv[c] if mg[c] else 0)
    def change_kit(self, k): self.sampler.load_kit(k); self.refresh_instrument_combos()
    def refresh_instrument_combos(self):
        d = self.sampler.current_kit_data
        for k, cb in self.instrument_combos.items():
            cb.blockSignals(True); cb.clear(); cb.addItems(d.get(k, []))
            curr = self.sampler.current_selection.get(k)
            if curr in d.get(k, []): cb.setCurrentText(curr)
            cb.blockSignals(False)
    def change_sample(self, k):
        self.sampler.set_instrument_sample(self.cb_kit.currentText(), k, self.instrument_combos[k].currentText())
        self.sampler.play_one_shot(k, 0.9)
    def play_preview(self):
        self.stop_playback()
        if self.current_editing_id:
            b = self.engine.get_pattern(self.current_editing_id)
            b.swing_feel = self.global_swing
            self.current_player = SequencePlayer(self.sampler, [b], self.current_bpm, True)
            self.current_player.start()
    def stop_playback(self):
        if self.current_player: self.current_player.stop(); self.current_player = None
    
    # --- MIGRACIÓN: Cerramos el backend de audio correctamente ---
    def closeEvent(self, e): 
        print(">>> [CIERRE] Apagando Backend de Audio...")
        if hasattr(self, 'audio_backend'):
            self.audio_backend.shutdown()
        self.stop_playback() 
        e.accept()

if __name__ == "__main__":
    print(">>> [SISTEMA] EJECUTANDO...")
    app = QApplication(sys.argv)
    window = BookOfDrumsApp()
    window.show()
    sys.exit(app.exec())