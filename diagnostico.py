import sys
import traceback

print("\n" + "="*40)
print("   INICIANDO DIAGNÓSTICO PROFUNDO")
print("="*40)

def probar_import(nombre_libreria):
    print(f"\n[TEST] Intentando importar '{nombre_libreria}'...", end=" ")
    try:
        modulo = __import__(nombre_libreria)
        if hasattr(modulo, '__version__'):
            print(f"✅ OK (v{modulo.__version__})")
        else:
            print("✅ OK")
        return True
    except ImportError as e:
        print("❌ FALLÓ (ImportError)")
        print(f"   DETALLE: {e}")
        return False
    except Exception as e:
        print("🔥 ERROR CRÍTICO AL IMPORTAR")
        print(f"   DETALLE: {e}")
        # A veces el error tiene más info oculta
        traceback.print_exc()
        return False

# 1. PRUEBAS BÁSICAS
print("\n--- NIVEL 1: BÁSICOS ---")
probar_import("os")
probar_import("json")
probar_import("sys")

# 2. PRUEBAS GRÁFICAS
print("\n--- NIVEL 2: INTERFAZ (PyQt6) ---")
qt_ok = probar_import("PyQt6.QtWidgets")

# 3. PRUEBAS DE AUDIO (CORE)
print("\n--- NIVEL 3: MOTOR DE AUDIO ---")
probar_import("pygame")
probar_import("pydub")

# 4. PRUEBAS CIENTÍFICAS (AQUÍ ESTÁ EL PROBLEMA SEGURO)
print("\n--- NIVEL 4: CIENTÍFICO (ZONA PELIGROSA) ---")
numpy_ok = probar_import("numpy")
probar_import("soundfile")

print("\n[TEST] Intentando importar 'pedalboard'...", end=" ")
try:
    import pedalboard
    print("✅ OK")
except Exception as e:
    print("❌ FALLÓ")
    print(f"   ERROR: {e}")

print("\n[TEST] Intentando importar 'librosa'...", end=" ")
try:
    import librosa
    print("✅ OK")
except Exception as e:
    print("❌ FALLÓ")
    print(f"   ERROR: {e}")

print("\n" + "="*40)
print("DIAGNÓSTICO TERMINADO.")
input("Presiona ENTER para cerrar...")