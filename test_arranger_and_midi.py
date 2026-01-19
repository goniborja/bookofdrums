"""
test_arranger_and_midi.py
 
Demo application for ArrangerWidget and MidiExporter.
 
This standalone application demonstrates:
1. Loading patterns from database.xlsx via RhythmEngine
2. Displaying ArrangerWidget with timeline
3. Adding pattern blocks to timeline
4. Exporting arrangement to MIDI
 
Usage:
    python test_arranger_and_midi.py
"""
 
import sys
from pathlib import Path
 
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QPushButton, QListWidget, QListWidgetItem, QLabel,
    QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt
 
from core.rhythm_core import RhythmEngine
from core.models import RhythmBlock
from ui.arranger_widget import ArrangerWidget
from export.midi_exporter import export_pattern_to_midi
 
 
class ArrangerDemo(QMainWindow):
    """
    Demo application showing ArrangerWidget and MidiExporter.
 
    Layout:
    - Left: Pattern library (loaded from database.xlsx)
    - Right: ArrangerWidget timeline
    """
 
    def __init__(self):
        super().__init__()
        self.engine: Optional[RhythmEngine] = None
        self.arranger: Optional[ArrangerWidget] = None
        self.pattern_list: Optional[QListWidget] = None
 
        self.init_ui()
        self.load_patterns()
 
    def init_ui(self):
        """Create UI layout."""
        self.setWindowTitle("Book of Drums - Arranger & MIDI Export Demo")
        self.setGeometry(100, 100, 1400, 800)
 
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
 
        # Create splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
 
        # Left panel: Pattern library
        left_panel = self.create_pattern_library_panel()
        splitter.addWidget(left_panel)
 
        # Right panel: Arranger
        self.arranger = ArrangerWidget()
        splitter.addWidget(self.arranger)
 
        # Set splitter sizes (30% library, 70% arranger)
        splitter.setSizes([400, 1000])
 
        # Status bar
        self.statusBar().showMessage("Ready. Load patterns from library.")
 
    def create_pattern_library_panel(self) -> QWidget:
        """Create left panel with pattern library."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
 
        # Header
        header = QLabel("📚 Pattern Library")
        header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        layout.addWidget(header)
 
        # Pattern list
        self.pattern_list = QListWidget()
        self.pattern_list.itemDoubleClicked.connect(self.on_pattern_double_clicked)
        layout.addWidget(self.pattern_list)
 
        # Instructions
        instructions = QLabel(
            "Double-click a pattern to add it to the timeline.\n\n"
            "Patterns will be added at the end of the timeline."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("padding: 10px; background-color: #f0f0f0;")
        layout.addWidget(instructions)
 
        # Quick export button
        export_group = QGroupBox("Single Pattern Export")
        export_layout = QVBoxLayout(export_group)
 
        self.export_single_btn = QPushButton("💾 Export Selected to MIDI")
        self.export_single_btn.clicked.connect(self.export_single_pattern)
        self.export_single_btn.setEnabled(False)
        export_layout.addWidget(self.export_single_btn)
 
        layout.addWidget(export_group)
 
        return panel
 
    def load_patterns(self):
        """Load patterns from database.xlsx via RhythmEngine."""
        try:
            self.statusBar().showMessage("Loading patterns from database.xlsx...")
 
            self.engine = RhythmEngine()
 
            # Get all pattern IDs
            pattern_ids = self.engine.get_all_pattern_ids()
 
            if not pattern_ids:
                QMessageBox.warning(
                    self,
                    "No Patterns",
                    "No patterns found in database.xlsx.\n\n"
                    "Make sure database.xlsx exists in assets/database/"
                )
                self.statusBar().showMessage("No patterns loaded.")
                return
 
            # Populate list
            for pid in pattern_ids:
                pattern = self.engine.get_pattern(pid)
                if pattern:
                    item = QListWidgetItem(f"{pattern.name_human} ({pattern.bpm} BPM)")
                    item.setData(Qt.ItemDataRole.UserRole, pid)  # Store pattern ID
                    self.pattern_list.addItem(item)
 
            self.statusBar().showMessage(f"✅ {len(pattern_ids)} patterns loaded from database.xlsx")
 
            # Enable export button when selection changes
            self.pattern_list.itemSelectionChanged.connect(
                lambda: self.export_single_btn.setEnabled(
                    len(self.pattern_list.selectedItems()) > 0
                )
            )
 
        except Exception as e:
            QMessageBox.critical(
                self,
                "Load Error",
                f"Failed to load patterns:\n{str(e)}\n\n"
                f"Make sure database.xlsx exists in assets/database/"
            )
            self.statusBar().showMessage("❌ Failed to load patterns")
            import traceback
            traceback.print_exc()
 
    def on_pattern_double_clicked(self, item: QListWidgetItem):
        """Handle double-click on pattern - add to timeline."""
        pattern_id = item.data(Qt.ItemDataRole.UserRole)
        pattern = self.engine.get_pattern(pattern_id)
 
        if not pattern:
            return
 
        # Determine start position (end of last block or 0)
        if self.arranger.scene.pattern_blocks:
            last_block = max(
                self.arranger.scene.pattern_blocks,
                key=lambda b: b.end_position
            )
            start_pos = last_block.end_position
        else:
            start_pos = 0.0
 
        # Auto-select track based on pattern's first instrument
        track_id = self.auto_detect_track(pattern)
 
        # Add to timeline
        self.arranger.add_pattern(pattern, track_id, start_pos)
 
        self.statusBar().showMessage(
            f"Added '{pattern.name_human}' at beat {start_pos:.1f} on track '{track_id}'"
        )
 
    def auto_detect_track(self, pattern: RhythmBlock) -> str:
        """
        Auto-detect which track to place pattern on.
 
        Looks at pattern's events and finds the most prominent instrument.
        """
        if not pattern.events:
            return "kick"  # Default fallback
 
        # Count events per instrument
        instrument_counts = {}
        for event in pattern.events:
            inst_name = event.instrument.name.lower()
            instrument_counts[inst_name] = instrument_counts.get(inst_name, 0) + 1
 
        # Find most common
        most_common = max(instrument_counts.items(), key=lambda x: x[1])
        return most_common[0]
 
    def export_single_pattern(self):
        """Export selected pattern to MIDI (single pattern, not arrangement)."""
        selected = self.pattern_list.selectedItems()
        if not selected:
            return
 
        item = selected[0]
        pattern_id = item.data(Qt.ItemDataRole.UserRole)
        pattern = self.engine.get_pattern(pattern_id)
 
        if not pattern:
            return
 
        # Ask for file path
        from PyQt6.QtWidgets import QFileDialog
 
        default_name = f"{pattern.id_name}.mid"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Single Pattern to MIDI",
            default_name,
            "MIDI Files (*.mid *.midi);;All Files (*)"
        )
 
        if not file_path:
            return  # User cancelled
 
        # Export
        try:
            success = export_pattern_to_midi(
                pattern=pattern,
                output_path=file_path,
                ppq=480,
                apply_humanization=True
            )
 
            if success:
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Pattern exported to:\n{file_path}"
                )
                self.statusBar().showMessage(f"✅ Exported: {file_path}")
            else:
                QMessageBox.critical(
                    self,
                    "Export Failed",
                    "Failed to export pattern. Check console for errors."
                )
 
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Error exporting pattern:\n{str(e)}"
            )
            import traceback
            traceback.print_exc()
 
 
def main():
    """Run demo application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Book of Drums - Arranger Demo")
    app.setOrganizationName("Book of Drums")
 
    # Check for mido library
    try:
        import mido
    except ImportError:
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Missing Library")
        msg.setText(
            "The 'mido' library is required for MIDI export.\n\n"
            "Install it with:\n"
            "pip install mido\n\n"
            "The application will run, but MIDI export will not work."
        )
        msg.exec()
 
    window = ArrangerDemo()
    window.show()
 
    sys.exit(app.exec())
 
 
if __name__ == "__main__":
    main()