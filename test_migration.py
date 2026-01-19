"""
test_migration.py
 
Script de verificación para la migración a NoteEvent.
 
Ejecuta esto para confirmar que:
1. RhythmEngine carga correctamente
2. Los patrones tienen events (NoteEvent list)
3. Los tracks legacy siguen funcionando
4. El mapeo de instrumentos funciona
"""
 
import sys
from core.rhythm_core import RhythmEngine
from core.models import DrumInstrument
 
 
def main():
    print("=" * 60)
    print("VERIFICACIÓN DE MIGRACIÓN - Book of Drums")
    print("=" * 60)
    print()
 
    # 1. Cargar engine
    print("1️⃣ Cargando RhythmEngine...")
    engine = RhythmEngine()
 
    total_patterns = len(engine._patterns)
    print(f"   ✅ {total_patterns} patrones cargados")
    print()
 
    if total_patterns == 0:
        print("❌ No se cargaron patrones. Verifica database.xlsx")
        return
 
    # 2. Verificar primer patrón
    print("2️⃣ Analizando primer patrón...")
    first_pid = list(engine._patterns.keys())[0]
    pattern = engine.get_pattern(first_pid)
 
    print(f"   ID: {pattern.id_name}")
    print(f"   Nombre: {pattern.name_human}")
    print(f"   BPM: {pattern.bpm}")
    print(f"   Swing: {pattern.swing_feel:.2f}")
    print(f"   Duración: {pattern.duration_bars} compás(es)")
    print()
 
    # 3. Verificar tracks legacy
    print("3️⃣ Verificando tracks legacy (dict)...")
    print(f"   Instrumentos en tracks: {len(pattern.tracks)}")
    for track_name in list(pattern.tracks.keys())[:3]:
        steps = pattern.tracks[track_name]
        active = sum(1 for s in steps if s.intensity > 0)
        print(f"      - {track_name}: {active}/16 pasos activos")
    print()
 
    # 4. Verificar events (NUEVO)
    print("4️⃣ Verificando events (NoteEvent list)...")
    print(f"   Total eventos: {len(pattern.events)}")
 
    if len(pattern.events) == 0:
        print("   ⚠️ No hay eventos. Verifica convert_legacy_tracks_to_events()")
    else:
        print("   ✅ Eventos creados correctamente")
        print()
        print("   Primeros 5 eventos:")
        for i, event in enumerate(pattern.events[:5]):
            print(f"      [{i+1}] {event.instrument.name:20} | "
                  f"pos={event.position:5.2f} beats | "
                  f"vel={event.velocity:3} | "
                  f"offset={event.offset_ms:+6.2f}ms")
    print()
 
    # 5. Verificar mapeo de instrumentos
    print("5️⃣ Verificando mapeo DrumInstrument.from_string()...")
    test_names = ["kick", "snare_full", "hihat_closed", "rim", "crash"]
    for name in test_names:
        result = DrumInstrument.from_string(name)
        if result:
            print(f"   ✅ '{name}' -> {result.name} (MIDI {result.value})")
        else:
            print(f"   ❌ '{name}' -> No mapeado")
    print()
 
    # 6. Verificar múltiples patrones
    print("6️⃣ Estadísticas generales...")
    total_events = 0
    patterns_with_events = 0
 
    for pid, pat in engine._patterns.items():
        if pat.events:
            patterns_with_events += 1
            total_events += len(pat.events)
 
    print(f"   Patrones con eventos: {patterns_with_events}/{total_patterns}")
    print(f"   Total eventos en biblioteca: {total_events}")
 
    if patterns_with_events > 0:
        avg = total_events / patterns_with_events
        print(f"   Promedio eventos por patrón: {avg:.1f}")
    print()
 
    # 7. Verificar serialización
    print("7️⃣ Verificando serialización to_dict()...")
    try:
        data = pattern.to_dict()
        print(f"   ✅ Patrón serializado correctamente")
        print(f"      - Claves: {list(data.keys())}")
        print(f"      - Eventos serializados: {len(data['events'])}")
    except Exception as e:
        print(f"   ❌ Error en serialización: {e}")
    print()
 
    # Resumen final
    print("=" * 60)
    print("RESUMEN")
    print("=" * 60)
 
    if patterns_with_events == total_patterns and total_events > 0:
        print("✅ MIGRACIÓN EXITOSA")
        print("   - Todos los patrones tienen eventos")
        print("   - Tracks legacy funcionan")
        print("   - Listo para ArrangerWidget y MidiExporter")
    else:
        print("⚠️ MIGRACIÓN PARCIAL")
        print(f"   - Solo {patterns_with_events}/{total_patterns} patrones con eventos")
        print("   - Verifica REJILLAS en database.xlsx")
    print()
 
 
if __name__ == "__main__":
    main()