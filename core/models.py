"""
core/models.py

Modern data models for Book of Drums.
Introduces NoteEvent with micro-timing support (offset_ms).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional


class DrumInstrument(Enum):
    """
    Drum instruments mapped to General MIDI standard.

    Each enum value is the MIDI note number for that instrument.
    This ensures compatibility with MIDI exporters and sequencers.
    """
    # Bass drums
    KICK = 36                    # Acoustic Bass Drum (GM)
    KICK_ACOUSTIC = 35           # Alternative kick

    # Snares
    SNARE = 38                   # Acoustic Snare (GM)
    SNARE_FULL = 38              # Alias for full snare hit
    SNARE_CROSSSTICK = 37        # Side Stick / Rim
    SNARE_RIM = 37               # Alias

    # Hi-hats
    HIHAT_CLOSED = 42            # Closed Hi-Hat (GM)
    HIHAT_OPEN = 46              # Open Hi-Hat (GM)
    HIHAT_PEDAL = 44             # Pedal Hi-Hat

    # Cymbals
    CRASH = 49                   # Crash Cymbal 1 (GM)
    CRASH_2 = 57                 # Crash Cymbal 2
    RIDE = 51                    # Ride Cymbal 1
    RIDE_BELL = 53               # Ride Bell
    CYMBAL = 49                  # Generic crash (alias)

    # Toms
    TOM_LOW = 45                 # Low Tom (GM)
    TOM_MID = 47                 # Mid Tom
    TOM_HIGH = 50                # High Tom
    TOM = 47                     # Generic tom (alias)

    # Percussion
    COWBELL = 56                 # Cowbell
    TAMBOURINE = 54              # Tambourine
    CLAP = 39                    # Hand Clap

    @classmethod
    def from_string(cls, name: str) -> Optional['DrumInstrument']:
        """
        Convert string name to DrumInstrument enum.

        Handles various naming conventions:
        - "kick", "bombo" -> KICK
        - "snare", "caja", "snare_full" -> SNARE_FULL
        - "rim", "stick", "crossstick" -> SNARE_CROSSSTICK
        - "hihat_closed", "chat", "hihat_cl" -> HIHAT_CLOSED
        - etc.

        Args:
            name: Instrument name (case-insensitive)

        Returns:
            DrumInstrument enum or None if not found
        """
        name_lower = name.lower().strip()

        # Mapping from legacy/common names to enum
        mappings = {
            # Kick
            "kick": cls.KICK,
            "bombo": cls.KICK,
            "bass_drum": cls.KICK,

            # Snare
            "snare": cls.SNARE_FULL,
            "caja": cls.SNARE_FULL,
            "snare_full": cls.SNARE_FULL,

            # Rim/Crossstick
            "rim": cls.SNARE_CROSSSTICK,
            "stick": cls.SNARE_CROSSSTICK,
            "crossstick": cls.SNARE_CROSSSTICK,
            "snare_crossstick": cls.SNARE_CROSSSTICK,

            # Hi-hats
            "hihat_closed": cls.HIHAT_CLOSED,
            "hihat_cl": cls.HIHAT_CLOSED,
            "chat": cls.HIHAT_CLOSED,
            "closed": cls.HIHAT_CLOSED,
            "hh_closed": cls.HIHAT_CLOSED,

            "hihat_open": cls.HIHAT_OPEN,
            "hihat_op": cls.HIHAT_OPEN,
            "ohat": cls.HIHAT_OPEN,
            "open": cls.HIHAT_OPEN,
            "hh_open": cls.HIHAT_OPEN,

            "hihat_pedal": cls.HIHAT_PEDAL,
            "pedal": cls.HIHAT_PEDAL,

            # Cymbals
            "crash": cls.CRASH,
            "cymbal": cls.CYMBAL,
            "ride": cls.RIDE,
            "ride_bell": cls.RIDE_BELL,

            # Toms
            "tom": cls.TOM,
            "tom_low": cls.TOM_LOW,
            "tom_mid": cls.TOM_MID,
            "tom_high": cls.TOM_HIGH,

            # Percussion
            "cowbell": cls.COWBELL,
            "tambourine": cls.TAMBOURINE,
            "clap": cls.CLAP,
            "perc": cls.TOM,  # Generic percussion -> tom
        }

        # Direct lookup
        result = mappings.get(name_lower)
        if result:
            return result

        # Fuzzy matching for partial names
        for key, instr in mappings.items():
            if key in name_lower or name_lower in key:
                return instr

        return None

    def to_midi_note(self) -> int:
        """Get MIDI note number (same as enum value)."""
        return self.value


@dataclass
class NoteEvent:
    """
    A single drum hit event with humanization support.

    Attributes:
        instrument: Which drum was hit
        position: Position in beats (0.0 = start of bar, 1.0 = 2nd beat, etc.)
        velocity: MIDI velocity (0-127)
        offset_ms: Micro-timing deviation in milliseconds
                   Positive = laid-back (behind the beat)
                   Negative = rushing (ahead of the beat)
                   0.0 = perfectly on grid
    """
    instrument: DrumInstrument
    position: float  # in beats (quarters)
    velocity: int = 100
    offset_ms: float = 0.0

    def __post_init__(self):
        """Validate velocity range."""
        if not (0 <= self.velocity <= 127):
            raise ValueError(f"Velocity must be 0-127, got {self.velocity}")

    def to_dict(self) -> dict:
        """Serialize to dict for JSON export."""
        return {
            "instrument": self.instrument.name,
            "position": float(self.position),
            "velocity": int(self.velocity),
            "offset_ms": float(self.offset_ms),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'NoteEvent':
        """Deserialize from dict."""
        return cls(
            instrument=DrumInstrument[data["instrument"]],
            position=float(data["position"]),
            velocity=int(data.get("velocity", 100)),
            offset_ms=float(data.get("offset_ms", 0.0)),
        )


@dataclass
class RhythmBlock:
    """
    A drum pattern (1 or more bars).

    Modern version using NoteEvent list instead of track dict.
    This enables better humanization and MIDI export.

    Attributes:
        id_name: Unique identifier (e.g. "one_drop_basic")
        name_human: Display name (e.g. "One Drop - Basic")
        estilo_id: Style ID (e.g. "REGGAE", "SKA")
        bpm: Typical tempo
        description: Optional description
        events: List of all drum hits in the pattern
        swing_feel: Global swing amount (0.5 = straight, 0.66 = triplet swing)
        duration_bars: Length in bars (typically 1 or 2)
    """
    id_name: str
    name_human: str
    estilo_id: str
    bpm: int
    events: List[NoteEvent] = field(default_factory=list)
    description: str = ""
    swing_feel: float = 0.5
    duration_bars: int = 1

    # Legacy compatibility: keep tracks dict for gradual migration
    tracks: Dict[str, List] = field(default_factory=dict)

    def add_event(self, event: NoteEvent) -> None:
        """Add a drum hit event."""
        self.events.append(event)

    def get_events_for_instrument(self, instrument: DrumInstrument) -> List[NoteEvent]:
        """Get all events for a specific instrument."""
        return [e for e in self.events if e.instrument == instrument]

    def total_duration_beats(self) -> float:
        """Total duration in quarter notes (4/4 time)."""
        return float(self.duration_bars * 4)

    def to_dict(self) -> dict:
        """Serialize to dict for saving."""
        return {
            "id_name": self.id_name,
            "name_human": self.name_human,
            "estilo_id": self.estilo_id,
            "bpm": self.bpm,
            "description": self.description,
            "swing_feel": self.swing_feel,
            "duration_bars": self.duration_bars,
            "events": [e.to_dict() for e in self.events],
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'RhythmBlock':
        """Deserialize from dict."""
        events = [NoteEvent.from_dict(e) for e in data.get("events", [])]
        return cls(
            id_name=data["id_name"],
            name_human=data["name_human"],
            estilo_id=data["estilo_id"],
            bpm=int(data["bpm"]),
            events=events,
            description=data.get("description", ""),
            swing_feel=float(data.get("swing_feel", 0.5)),
            duration_bars=int(data.get("duration_bars", 1)),
        )


# Helper function for legacy code migration
def convert_legacy_tracks_to_events(
    tracks: Dict[str, List],
    bars: int = 1
) -> List[NoteEvent]:
    """
    Convert legacy track dict (16-step grid) to NoteEvent list.

    Args:
        tracks: Dict mapping instrument name to 16-step list
        bars: Number of bars (default 1)

    Returns:
        List of NoteEvent objects with humanization (offset_ms from timing_ticks)
    """
    events = []
    steps_per_bar = 16
    beats_per_step = 4.0 / steps_per_bar  # 0.25 beats = 16th note

    for track_name, steps in tracks.items():
        # Map track name to instrument enum
        instrument = DrumInstrument.from_string(track_name)
        if not instrument:
            continue  # Skip unknown instruments

        for step_idx, step in enumerate(steps):
            # Check if step has intensity > 0 (legacy format)
            intensity = getattr(step, 'intensity', 0)
            if intensity <= 0:
                continue

            # Get velocity (legacy format)
            velocity = getattr(step, 'velocity_base', 100)

            # Calculate position in beats
            position = step_idx * beats_per_step

            # Timing humanizado: ticks -> ms aproximado
            # A 120 BPM, 480 PPQ: 1 tick = 1.04 ms
            timing_ticks = getattr(step, 'timing_ticks', 0)
            offset_ms = timing_ticks * 1.04

            # Create event with humanization from timing_ticks
            event = NoteEvent(
                instrument=instrument,
                position=position,
                velocity=int(velocity),
                offset_ms=offset_ms,
            )
            events.append(event)

    return events
