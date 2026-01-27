from app import app  # Asegúrate que 'app' sea el nombre de tu archivo principal
from database import db

def fix():
    with app.app_context():
        # Lista de columnas a agregar a la tabla 'producto'
        columnas = [
            ('codigo_barra', 'VARCHAR(100)'),
            ('precio_unit', 'FLOAT'),
            ('precio_costo', 'FLOAT')
        ]
        
        for nombre_col, tipo in columnas:
            try:
                db.session.execute(db.text(f'ALTER TABLE producto ADD COLUMN {nombre_col} {tipo}'))
                db.session.commit()
                print(f"✅ Columna '{nombre_col}' agregada.")
            except Exception as e:
                print(f"ℹ️ Columna '{nombre_col}' ya existía o no se pudo agregar.")

if __name__ == "__main__":
    fix()