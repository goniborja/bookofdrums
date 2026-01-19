# 🚀 Quick Start - ArrangerWidget & MidiExporter
 
## Installation
 
### 1. Install Required Library
 
```bash
pip install mido
```
 
### 2. Copy New Files to Your Project
 
Copy these files to your `D:\BookOfDrums\BookOfDrums\` directory:
 
```
BookOfDrums/
├── export/
│   ├── __init__.py          ← NEW
│   └── midi_exporter.py     ← NEW
├── ui/
│   ├── __init__.py          ← NEW
│   └── arranger_widget.py   ← NEW
└── test_arranger_and_midi.py  ← NEW (demo app)
```
 
---
 
## Test the New Features
 
### Option 1: Run Demo Application
 
```bash
cd D:\BookOfDrums\BookOfDrums
python test_arranger_and_midi.py
```
 
**What you'll see:**
- Pattern library on left (loaded from `database.xlsx`)
- Timeline arranger on right
- Double-click pattern → adds to timeline
- "Export MIDI" button → saves arrangement to MIDI file
 
---
 
### Option 2: Quick MIDI Export Test
 
Create a test script (`test_quick_export.py`):
 
```python
from core.rhythm_core import RhythmEngine
from export.midi_exporter import export_pattern_to_midi
 
# Load patterns
engine = RhythmEngine()
pattern = engine.get_pattern("one_drop_basic")  # Use any pattern ID
 
# Export to MIDI
if pattern:
    success = export_pattern_to_midi(
        pattern=pattern,
        output_path="test_output.mid",
        ppq=480,
        apply_humanization=True
    )
 
    if success:
        print("✅ MIDI exported to test_output.mid")
    else:
        print("❌ Export failed")
else:
    print("❌ Pattern not found")
```
 
Run it:
```bash
python test_quick_export.py
```
 
Check the output file (`test_output.mid`) in your DAW or MIDI player.
 
---
 
## Integrate with Main Application
 
### Add Arranger Tab to main.py
 
1. **Import ArrangerWidget:**
 
```python
# At top of main.py
from ui.arranger_widget import ArrangerWidget
```
 
2. **Add tab in UI setup:**
 
```python
class BookOfDrumsApp(QMainWindow):
    def __init__(self):
        super().__init__()
        # ... existing code ...
 
        # After creating other tabs, add:
        self.arranger = ArrangerWidget()
        self.tab_widget.addTab(self.arranger, "🎼 Arranger")
```
 
3. **Connect pattern library to arranger:**
 
```python
def on_library_pattern_double_click(self, item):
    """When user double-clicks pattern in library."""
    pattern_id = item.data(0, Qt.ItemDataRole.UserRole)
    pattern = self.engine.get_pattern(pattern_id)
 
    if pattern:
        # Add to arranger
        self.arranger.add_pattern(pattern)
```
 
---
 
## Verify Everything Works
 
### Checklist
 
- [ ] `pip install mido` successful
- [ ] All files copied to project directory
- [ ] `python test_arranger_and_midi.py` runs without errors
- [ ] Patterns load from `database.xlsx`
- [ ] Can add patterns to timeline by double-clicking
- [ ] Can drag pattern blocks on timeline
- [ ] Can export to MIDI (opens save dialog)
- [ ] Exported MIDI file opens in DAW
- [ ] Drums play on correct notes (verify with metronome)
 
---
 
## Common Issues
 
### "ModuleNotFoundError: No module named 'mido'"
 
**Solution:**
```bash
pip install mido
```
 
---
 
### "No patterns loaded from database.xlsx"
 
**Solution:** Make sure `database.xlsx` exists in:
```
D:\BookOfDrums\BookOfDrums\assets\database\database.xlsx
```
 
Run this to check:
```python
import os
db_path = r"D:\BookOfDrums\BookOfDrums\assets\database\database.xlsx"
print(f"Database exists: {os.path.exists(db_path)}")
```
 
---
 
### MIDI file has no sound in DAW
 
**Check:**
1. Track 10 (MIDI channel 10) is set to drums/percussion
2. Pattern has events: `len(pattern.events) > 0`
3. Velocities are not zero: `event.velocity > 0`
 
**Debug script:**
```python
pattern = engine.get_pattern("one_drop_basic")
print(f"Pattern: {pattern.name_human}")
print(f"Total events: {len(pattern.events)}")
 
for i, event in enumerate(pattern.events[:5]):
    print(f"  [{i+1}] {event.instrument.name} | "
          f"pos={event.position:.2f} | "
          f"vel={event.velocity}")
```
 
---
 
## Next Steps
 
1. **Test MIDI export** with different patterns
2. **Create arrangements** with multiple patterns
3. **Verify timing** in your DAW
4. **Add humanization** (future: offset_ms column in Excel)
 
See `ARRANGER_AND_MIDI_GUIDE.md` for full documentation.
 
---
 
**Ready to create professional drum arrangements with MIDI export!** 🥁🎵