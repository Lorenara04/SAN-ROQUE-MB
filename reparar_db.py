import sqlite3
import os

def encontrar_y_reparar():
    # Lista de posibles nombres y rutas de tu base de datos
    posibles_rutas = [
        os.path.join(os.getcwd(), 'instance', 'database.db'),
        os.path.join(os.getcwd(), 'database.db'),
        os.path.join(os.getcwd(), 'instance', 'licorera.db'),
        os.path.join(os.getcwd(), 'licorera.db')
    ]
    
    db_encontrada = None
    for ruta in posibles_rutas:
        if os.path.exists(ruta):
            db_encontrada = ruta
            break
            
    if not db_encontrada:
        print("❌ No se encontró ningún archivo .db. Verifica el nombre de tu base de datos.")
        return

    print(f"🔍 Base de datos encontrada en: {db_encontrada}")
    
    try:
        conn = sqlite3.connect(db_encontrada)
        cursor = conn.cursor()
        
        # Columnas faltantes detectadas en los errores
        columnas = [
            'ALTER TABLE producto ADD COLUMN codigo_barra VARCHAR(100)',
            'ALTER TABLE producto ADD COLUMN precio_unit FLOAT',
            'ALTER TABLE producto ADD COLUMN precio_costo FLOAT'
        ]
        
        for sql in columnas:
            try:
                cursor.execute(sql)
                print(f"✅ Columna agregada.")
            except sqlite3.OperationalError:
                print(f"ℹ️ La columna ya existía, saltando...")
        
        conn.commit()
        conn.close()
        print("🚀 ¡LISTO! Ya puedes volver a ejecutar app.py y editar tus ventas.")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    encontrar_y_reparar()