"""
export/midi_exporter.py
 
Professional MIDI exporter for Book of Drums patterns.
Exports RhythmBlock patterns with full humanization support.
 
Features:
- Multi-track export (one track per instrument)
- Micro-timing humanization (offset_ms)
- Swing feel application
- MIDI GM standard compatibility
- Configurable PPQ (pulses per quarter note)
"""
 
from __future__ import annotations
 
from pathlib import Path
from typing import List, Optional, Dict
from dataclasses import dataclass
 
try:
    from mido import MidiFile, MidiTrack, Message, MetaMessage
    MIDO_AVAILABLE = True
except ImportError:
    MIDO_AVAILABLE = False
    print("⚠️ mido library not installed. Run: pip install mido")
 
from core.models import RhythmBlock, NoteEvent, DrumInstrument
 
 
@dataclass
class MidiExportConfig:
    """Configuration for MIDI export."""
    ppq: int = 480  # Pulses (ticks) per quarter note
    default_velocity: int = 100
    default_duration_ticks: int = 120  # Duration of each note (in ticks)
    tempo_bpm: Optional[int] = None  # If None, use pattern's BPM
    apply_swing: bool = True  # Apply pattern's swing_feel
    apply_humanization: bool = True  # Apply offset_ms from events
 
    # Duration mapping by instrument (in ticks)
    duration_map: Dict[DrumInstrument, int] = None
 
    def __post_init__(self):
        """Set default duration map if not provided."""
        if self.duration_map is None:
            self.duration_map = {
                DrumInstrument.KICK: 180,
                DrumInstrument.KICK_ACOUSTIC: 180,
                DrumInstrument.SNARE: 240,
                DrumInstrument.SNARE_FULL: 240,
                DrumInstrument.SNARE_CROSSSTICK: 120,
                DrumInstrument.HIHAT_CLOSED: 80,
                DrumInstrument.HIHAT_OPEN: 240,
                DrumInstrument.HIHAT_PEDAL: 100,
                DrumInstrument.CRASH: 480,
                DrumInstrument.CRASH_2: 480,
                DrumInstrument.RIDE: 240,
                DrumInstrument.RIDE_BELL: 180,
                DrumInstrument.TOM_LOW: 200,
                DrumInstrument.TOM_MID: 200,
                DrumInstrument.TOM_HIGH: 200,
                DrumInstrument.COWBELL: 150,
                DrumInstrument.TAMBOURINE: 240,
                DrumInstrument.CLAP: 100,
            }
 
 
class MidiExporter:
    """
    MIDI exporter for Book of Drums patterns.
 
    Exports RhythmBlock patterns to standard MIDI files with:
    - Multi-track support (one track per instrument)
    - Humanization via offset_ms
    - Swing feel application
    - MIDI GM drum mapping
 
    Example:
        exporter = MidiExporter()
        exporter.export_pattern(
            pattern=my_pattern,
            output_path="output.mid",
            config=MidiExportConfig(ppq=480)
        )
    """
 
    def __init__(self):
        """Initialize MIDI exporter."""
        if not MIDO_AVAILABLE:
            raise ImportError(
                "mido library is required for MIDI export. "
                "Install with: pip install mido"
            )
 
    def export_pattern(
        self,
        pattern: RhythmBlock,
        output_path: str | Path,
        config: Optional[MidiExportConfig] = None
    ) -> bool:
        """
        Export a single pattern to MIDI file.
 
        Args:
            pattern: RhythmBlock to export
            output_path: Path to save MIDI file
            config: Export configuration (uses defaults if None)
 
        Returns:
            True if export successful, False otherwise
        """
        if config is None:
            config = MidiExportConfig()
 
        try:
            # Create MIDI file
            mid = MidiFile(ticks_per_beat=config.ppq)
 
            # Determine tempo
            tempo_bpm = config.tempo_bpm if config.tempo_bpm else pattern.bpm
            tempo_microseconds = int(60_000_000 / tempo_bpm)
 
            # Create tempo track
            tempo_track = MidiTrack()
            mid.tracks.append(tempo_track)
            tempo_track.append(MetaMessage('set_tempo', tempo=tempo_microseconds, time=0))
            tempo_track.append(MetaMessage('time_signature', numerator=4, denominator=4, time=0))
 
            # Group events by instrument
            events_by_instrument = self._group_events_by_instrument(pattern.events)
 
            # Create one track per instrument
            for instrument, events in events_by_instrument.items():
                track = self._create_track_for_instrument(
                    instrument=instrument,
                    events=events,
                    pattern=pattern,
                    config=config
                )
                mid.tracks.append(track)
 
            # Save MIDI file
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            mid.save(str(output_path))
 
            print(f"✅ MIDI exported: {output_path}")
            print(f"   - Tracks: {len(mid.tracks) - 1} instruments")
            print(f"   - Total events: {len(pattern.events)}")
            print(f"   - Tempo: {tempo_bpm} BPM")
            print(f"   - PPQ: {config.ppq}")
 
            return True
 
        except Exception as e:
            print(f"❌ Error exporting MIDI: {e}")
            import traceback
            traceback.print_exc()
            return False
 
    def export_arrangement(
        self,
        arrangement: List[tuple[RhythmBlock, float]],  # (pattern, start_time_beats)
        output_path: str | Path,
        config: Optional[MidiExportConfig] = None
    ) -> bool:
        """
        Export an arrangement (multiple patterns on timeline) to MIDI.
 
        Args:
            arrangement: List of (pattern, start_time_beats) tuples
            output_path: Path to save MIDI file
            config: Export configuration
 
        Returns:
            True if export successful, False otherwise
        """
        if config is None:
            config = MidiExportConfig()
 
        try:
            # Create MIDI file
            mid = MidiFile(ticks_per_beat=config.ppq)
 
            # Determine tempo (use first pattern's BPM or config)
            if arrangement:
                first_pattern = arrangement[0][0]
                tempo_bpm = config.tempo_bpm if config.tempo_bpm else first_pattern.bpm
            else:
                tempo_bpm = config.tempo_bpm if config.tempo_bpm else 120
 
            tempo_microseconds = int(60_000_000 / tempo_bpm)
 
            # Create tempo track
            tempo_track = MidiTrack()
            mid.tracks.append(tempo_track)
            tempo_track.append(MetaMessage('set_tempo', tempo=tempo_microseconds, time=0))
            tempo_track.append(MetaMessage('time_signature', numerator=4, denominator=4, time=0))
 
            # Collect all events from all patterns
            all_events = []
            for pattern, start_beats in arrangement:
                for event in pattern.events:
                    # Create a new event with adjusted position
                    adjusted_event = NoteEvent(
                        instrument=event.instrument,
                        position=event.position + start_beats,
                        velocity=event.velocity,
                        offset_ms=event.offset_ms
                    )
                    all_events.append((adjusted_event, pattern))
 
            # Group by instrument
            events_by_instrument = {}
            for event, pattern in all_events:
                if event.instrument not in events_by_instrument:
                    events_by_instrument[event.instrument] = []
                events_by_instrument[event.instrument].append((event, pattern))
 
            # Create tracks
            for instrument, event_pattern_pairs in events_by_instrument.items():
                # Extract just events for track creation
                events = [e for e, p in event_pattern_pairs]
                # Use first pattern for swing reference (can be improved)
                reference_pattern = event_pattern_pairs[0][1] if event_pattern_pairs else None
 
                track = self._create_track_for_instrument(
                    instrument=instrument,
                    events=events,
                    pattern=reference_pattern,
                    config=config
                )
                mid.tracks.append(track)
 
            # Save
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            mid.save(str(output_path))
 
            print(f"✅ Arrangement exported: {output_path}")
            print(f"   - Patterns: {len(arrangement)}")
            print(f"   - Total events: {len(all_events)}")
            print(f"   - Tempo: {tempo_bpm} BPM")
 
            return True
 
        except Exception as e:
            print(f"❌ Error exporting arrangement: {e}")
            import traceback
            traceback.print_exc()
            return False
 
    def _group_events_by_instrument(
        self,
        events: List[NoteEvent]
    ) -> Dict[DrumInstrument, List[NoteEvent]]:
        """Group events by instrument."""
        grouped = {}
        for event in events:
            if event.instrument not in grouped:
                grouped[event.instrument] = []
            grouped[event.instrument].append(event)
        return grouped
 
    def _create_track_for_instrument(
        self,
        instrument: DrumInstrument,
        events: List[NoteEvent],
        pattern: Optional[RhythmBlock],
        config: MidiExportConfig
    ) -> MidiTrack:
        """
        Create a MIDI track for a single instrument.
 
        Args:
            instrument: Which drum instrument
            events: All events for this instrument
            pattern: Reference pattern (for swing feel)
            config: Export configuration
 
        Returns:
            MidiTrack with all note events
        """
        track = MidiTrack()
 
        # Track name
        track.append(MetaMessage('track_name', name=instrument.name, time=0))
 
        # Set channel 10 (MIDI drums)
        track.append(Message('program_change', channel=9, program=0, time=0))
 
        # Sort events by position
        sorted_events = sorted(events, key=lambda e: e.position)
 
        # Convert events to MIDI messages
        midi_messages = []
        for event in sorted_events:
            # Calculate absolute time in ticks
            base_ticks = self._beats_to_ticks(event.position, config.ppq)
 
            # Apply swing if enabled
            if config.apply_swing and pattern and pattern.swing_feel != 0.5:
                swing_offset = self._calculate_swing_offset(
                    event.position,
                    pattern.swing_feel,
                    config.ppq
                )
                base_ticks += swing_offset
 
            # Apply humanization (offset_ms)
            if config.apply_humanization and event.offset_ms != 0.0:
                # Convert offset_ms to ticks
                # At 120 BPM: 1 beat = 500ms, so 1 tick (ppq=480) = 500/480 = 1.042ms
                # offset_ticks = offset_ms / (ms_per_beat / ppq)
                # ms_per_beat = 60000 / bpm
                bpm = pattern.bpm if pattern else 120
                ms_per_beat = 60000.0 / bpm
                ms_per_tick = ms_per_beat / config.ppq
                offset_ticks = int(round(event.offset_ms / ms_per_tick))
                base_ticks += offset_ticks
 
            # Ensure non-negative
            base_ticks = max(0, base_ticks)
 
            # Get MIDI note number
            midi_note = instrument.to_midi_note()
 
            # Get duration
            duration_ticks = config.duration_map.get(
                instrument,
                config.default_duration_ticks
            )
 
            # Create note_on and note_off messages
            midi_messages.append({
                'type': 'note_on',
                'time': base_ticks,
                'note': midi_note,
                'velocity': event.velocity,
                'channel': 9  # Channel 10 (0-indexed = 9)
            })
 
            midi_messages.append({
                'type': 'note_off',
                'time': base_ticks + duration_ticks,
                'note': midi_note,
                'velocity': 0,
                'channel': 9
            })
 
        # Sort all messages by time
        midi_messages.sort(key=lambda m: m['time'])
 
        # Convert absolute times to delta times
        current_time = 0
        for msg_data in midi_messages:
            absolute_time = msg_data['time']
            delta_time = absolute_time - current_time
 
            if msg_data['type'] == 'note_on':
                track.append(Message(
                    'note_on',
                    note=msg_data['note'],
                    velocity=msg_data['velocity'],
                    channel=msg_data['channel'],
                    time=delta_time
                ))
            elif msg_data['type'] == 'note_off':
                track.append(Message(
                    'note_off',
                    note=msg_data['note'],
                    velocity=msg_data['velocity'],
                    channel=msg_data['channel'],
                    time=delta_time
                ))
 
            current_time = absolute_time
 
        # End of track
        track.append(MetaMessage('end_of_track', time=0))
 
        return track
 
    def _beats_to_ticks(self, beats: float, ppq: int) -> int:
        """Convert beats (quarter notes) to MIDI ticks."""
        return int(round(beats * ppq))
 
    def _calculate_swing_offset(
        self,
        position: float,
        swing_feel: float,
        ppq: int
    ) -> int:
        """
        Calculate swing offset for a note position.
 
        Swing affects every other 16th note (off-beats).
        swing_feel = 0.5 means straight (no swing)
        swing_feel = 0.66 means triplet swing
        swing_feel = 0.75 means heavy swing
 
        Args:
            position: Note position in beats
            swing_feel: Swing amount (0.5 = straight, 0.66 = triplet)
            ppq: Pulses per quarter note
 
        Returns:
            Offset in ticks (can be positive or negative)
        """
        # Only apply swing to 16th notes on off-beats
        # Position in 16th notes
        position_16th = position * 4
 
        # Check if this is an off-beat 16th (1, 3, 5, 7, 9, 11, 13, 15)
        is_offbeat = (int(position_16th * 2) % 2) == 1
 
        if not is_offbeat:
            return 0
 
        # Calculate swing offset
        # At swing_feel=0.5 (straight), offset = 0
        # At swing_feel=0.66 (triplet), offset pushes note later
        straight_ticks = ppq / 4  # 16th note duration
        swing_offset = (swing_feel - 0.5) * straight_ticks
 
        return int(round(swing_offset))
 
 
# Convenience function
def export_pattern_to_midi(
    pattern: RhythmBlock,
    output_path: str | Path,
    ppq: int = 480,
    apply_humanization: bool = True
) -> bool:
    """
    Quick export function for a single pattern.
 
    Args:
        pattern: Pattern to export
        output_path: Where to save MIDI file
        ppq: Pulses per quarter note (default 480)
        apply_humanization: Apply offset_ms values
 
    Returns:
        True if successful
    """
    exporter = MidiExporter()
    config = MidiExportConfig(
        ppq=ppq,
        apply_humanization=apply_humanization
    )
    return exporter.export_pattern(pattern, output_path, config)