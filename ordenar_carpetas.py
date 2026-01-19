import os
import shutil

print("--- INICIANDO ORGANIZACIÓN AUTOMÁTICA ---")

current_dir = os.path.dirname(os.path.abspath(__file__))
assets_dir = os.path.join(current_dir, "assets")
hidden_folder = os.path.join(assets_dir, "kits")

if os.path.exists(hidden_folder):
    print(f"Detectada carpeta contenedora: {hidden_folder}")
    
    # Listar qué hay dentro de 'kits'
    items = os.listdir(hidden_folder)
    
    for item in items:
        src = os.path.join(hidden_folder, item)
        dst = os.path.join(assets_dir, item)
        
        print(f"MOVIENDO: {item} -> assets/{item}")
        try:
            shutil.move(src, dst)
        except Exception as e:
            print(f"Error moviendo {item}: {e}")
            
    # Intentar borrar la carpeta 'kits' si ha quedado vacía
    try:
        os.rmdir(hidden_folder)
        print("Carpeta 'kits' vacía eliminada.")
    except:
        print("Nota: La carpeta 'kits' no se pudo borrar (quizás tiene archivos basura), pero lo importante ya se movió.")

    print("\n✅ ¡LISTO! Ahora tus baterías están donde deben estar.")
else:
    print("\n❌ No encuentro la carpeta 'assets/kits'. ¿Quizás ya lo has arreglado?")

input("Presiona ENTER para cerrar...")