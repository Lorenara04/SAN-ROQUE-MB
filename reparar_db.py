import sqlite3
import os

def reparacion_integral_sanroque():
    # 1. Identificar rutas de la base de datos sanroque.db
    base_dir = os.path.abspath(os.getcwd())
    rutas_a_reparar = [
        os.path.join(base_dir, 'sanroque.db'),
        os.path.join(base_dir, 'instance', 'sanroque.db')
    ]

    print(f"--- INICIANDO REPARACIÓN INTEGRAL: SAN ROQUE MB ---")
    
    for ruta in rutas_a_reparar:
        if os.path.exists(ruta):
            print(f"\n📂 Reparando base de datos en: {ruta}")
            try:
                conn = sqlite3.connect(ruta)
                cursor = conn.cursor()
                
                # --- SOLUCIÓN AL ERROR DE CLIENTE_ID ---
                try:
                    # Agregamos cliente_id a la tabla venta (nombre en minúsculas por SQLAlchemy)
                    cursor.execute("ALTER TABLE venta ADD COLUMN cliente_id INTEGER REFERENCES cliente(id)")
                    print("✅ Columna 'cliente_id' agregada a tabla 'venta'")
                except sqlite3.OperationalError as e:
                    print(f"ℹ️ Tabla 'venta' (cliente_id): {e}")

                # --- REPARACIONES DE SOPORTE FOTO ---
                # Intentar agregar a facturas (si la usas)
                try:
                    cursor.execute("ALTER TABLE facturas ADD COLUMN soporte_foto VARCHAR(255)")
                    print("✅ Columna 'soporte_foto' agregada a tabla 'facturas'")
                except sqlite3.OperationalError as e:
                    print(f"ℹ️ Tabla 'facturas': {e}")

                # Intentar agregar a gastos
                try:
                    cursor.execute("ALTER TABLE gastos ADD COLUMN soporte_foto VARCHAR(255)")
                    print("✅ Columna 'soporte_foto' agregada a tabla 'gastos'")
                except sqlite3.OperationalError as e:
                    print(f"ℹ️ Tabla 'gastos': {e}")
                
                conn.commit()
                conn.close()
                print(f"✨ Proceso finalizado con éxito en esta ruta.")
            except Exception as e:
                print(f"❌ Error crítico conectando a {ruta}: {e}")
        else:
            print(f"❓ No se encontró el archivo en: {ruta}")

    print("\n--- REPARACIÓN TERMINADA ---")
    print("Prueba entrar de nuevo al terminal POS. Si el error persiste, reinicia la aplicación.")

if __name__ == "__main__":
    reparacion_integral_sanroque()