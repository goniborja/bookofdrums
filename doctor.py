import sys
import os
import time
import traceback

print("==========================================")
print("   DOCTOR BOOK OF DRUMS - DIAGNÓSTICO")
print("==========================================\n")

def check_files():
    print("1. VERIFICANDO ARCHIVOS...")
    required = ["main.py", "core/rhythm_core.py", "core/audio_engine.py"]
    all_ok = True
    for f in required:
        if os.path.exists(f):
            print(f"   [OK] Encontrado: {f}")
        else:
            print(f"   [ERROR] NO EXISTE: {f}")
            all_ok = False
    return all_ok

def check_syntax():
    print("\n2. ANALIZANDO CÓDIGO DE main.py...")
    try:
        with open("main.py", "r", encoding='utf-8') as f:
            content = f.read()
        
        # Esto intenta 'leer' el código sin ejecutarlo
        compile(content, "main.py", "exec")
        print("   [OK] La estructura del código es válida.")
        return True
    except SyntaxError as e:
        print(f"   [FATAL] ERROR DE ESCRITURA EN main.py")
        print(f"   ------------------------------------------------")
        print(f"   Línea: {e.lineno}")
        print(f"   Texto: {e.text}")
        print(f"   Error: {e.msg}")
        print(f"   ------------------------------------------------")
        return False
    except Exception as e:
        print(f"   [ERROR] No se pudo leer el archivo: {e}")
        return False

def try_import():
    print("\n3. INTENTANDO IMPORTAR LIBRERÍAS...")
    try:
        import PyQt6
        print("   [OK] PyQt6 instalado.")
        import pygame
        print("   [OK] Pygame instalado.")
        import pandas
        print("   [OK] Pandas instalado.")
    except ImportError as e:
        print(f"   [ERROR] Falta una librería: {e}")

# --- EJECUCIÓN ---
if check_files():
    if check_syntax():
        try_import()
        print("\n4. INTENTANDO ARRANCAR EL PROGRAMA...")
        print("   (Si se cierra después de esto, el fallo es interno)")
        print("   Iniciando...")
        time.sleep(1)
        os.system("python main.py")
    else:
        print("\n>>> NO SE PUEDE ARRANCAR PORQUE EL CÓDIGO ESTÁ ROTO. <<<")
else:
    print("\n>>> FALTAN ARCHIVOS ESENCIALES. <<<")

print("\n==========================================")
input("Pulsa ENTER para cerrar este diagnóstico...")