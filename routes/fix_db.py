from app import app  # Asegúrate de que 'app' sea tu archivo principal
from database import db
from sqlalchemy import text

def fix():
    with app.app_context():
        # He ajustado los nombres de las columnas para que coincidan con 
        # lo que tus otros archivos (admin.py, creditos.py) esperan.
        columnas = [
            ('codigo', 'VARCHAR(100)'),
            ('valor_venta', 'FLOAT'),
            ('valor_interno', 'FLOAT'),
            ('categoria', 'VARCHAR(50)')  # Útil para el modelo de Cliente/Producto
        ]
        
        print("🚀 Iniciando actualización de base de datos...")
        
        for nombre_col, tipo in columnas:
            try:
                # Usamos text() para SQL puro
                db.session.execute(text(f'ALTER TABLE producto ADD COLUMN {nombre_col} {tipo}'))
                db.session.commit()
                print(f"✅ Columna '{nombre_col}' agregada con éxito.")
            except Exception as e:
                db.session.rollback()  # Limpiamos la sesión tras el error
                # El error suele ser porque la columna ya existe
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    print(f"ℹ️ La columna '{nombre_col}' ya existe, saltando...")
                else:
                    print(f"❌ Error inesperado en '{nombre_col}': {e}")

        print("🏁 Proceso finalizado.")

if __name__ == "__main__":
    fix()