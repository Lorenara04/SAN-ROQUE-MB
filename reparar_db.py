import sqlite3
import os

def reparacion_forzada():
    # 1. Identificar rutas
    base_dir = os.path.abspath(os.getcwd())
    rutas_a_reparar = [
        os.path.join(base_dir, 'licorera.db'),
        os.path.join(base_dir, 'instance', 'licorera.db')
    ]

    print(f"--- INICIANDO REPARACIÓN INTEGRAL ---")
    
    for ruta in rutas_a_reparar:
        if os.path.exists(ruta):
            print(f"\n📂 Reparando base de datos en: {ruta}")
            try:
                conn = sqlite3.connect(ruta)
                cursor = conn.cursor()
                
                # Intentar agregar la columna a facturas
                try:
                    cursor.execute("ALTER TABLE facturas ADD COLUMN soporte_foto VARCHAR(255)")
                    print("✅ Columna 'soporte_foto' agregada a tabla 'facturas'")
                except sqlite3.OperationalError as e:
                    print(f"ℹ️ Tabla 'facturas': {e}")

                # Intentar agregar la columna a gastos
                try:
                    cursor.execute("ALTER TABLE gastos ADD COLUMN soporte_foto VARCHAR(255)")
                    print("✅ Columna 'soporte_foto' agregada a tabla 'gastos'")
                except sqlite3.OperationalError as e:
                    print(f"ℹ️ Tabla 'gastos': {e}")
                
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"❌ Error conectando a {ruta}: {e}")
        else:
            print(f"❓ No existe archivo en: {ruta}")

    print("\n--- PROCESO TERMINADO ---")
    print("Si el error persiste, borra el archivo 'licorera.db' de la raíz y deja solo el de 'instance'.")

if __name__ == "__main__":
    reparacion_forzada()