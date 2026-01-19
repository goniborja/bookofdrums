import os

print("="*60)
print("   DIAGNÓSTICO DE RUTAS - BOOK OF DRUMS")
print("="*60)

# 1. ¿Dónde está este archivo script?
ubicacion_script = os.path.dirname(os.path.abspath(__file__))
print(f"[1] Ubicación del script:  {ubicacion_script}")

# 2. ¿Dónde debería estar la carpeta assets?
ruta_assets = os.path.join(ubicacion_script, "assets")
existe_assets = os.path.exists(ruta_assets)
estado_assets = "✅ ENCONTRADA" if existe_assets else "❌ NO EXISTE AQUÍ"
print(f"[2] Buscando carpeta 'assets': {ruta_assets}")
print(f"    -> {estado_assets}")

# 3. ¿Dónde debería estar el Excel?
ruta_excel = os.path.join(ruta_assets, "database", "database.xlsx")
existe_excel = os.path.exists(ruta_excel)
estado_excel = "✅ ENCONTRADO" if existe_excel else "❌ NO EXISTE O TIENE OTRO NOMBRE"
print(f"[3] Buscando Excel: {ruta_excel}")
print(f"    -> {estado_excel}")

# 4. Chequeo de librerías
print("-" * 60)
try:
    import pandas
    print("[4] Librería 'pandas':     ✅ Instalada")
except ImportError:
    print("[4] Librería 'pandas':     ❌ FALTA (Ejecuta: pip install pandas)")

try:
    import openpyxl
    print("[5] Librería 'openpyxl':   ✅ Instalada")
except ImportError:
    print("[5] Librería 'openpyxl':   ❌ FALTA (Ejecuta: pip install openpyxl)")

print("="*60)
input("Presiona ENTER para salir...")