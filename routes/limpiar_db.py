from app import app 
from database import db
from sqlalchemy import text

with app.app_context():
    # Lista de comandos para actualizar la tabla producto
    comandos = [
        "ALTER TABLE producto ADD COLUMN codigo_barra VARCHAR(100)",
        "ALTER TABLE producto ADD COLUMN precio_unit FLOAT",
        "ALTER TABLE producto ADD COLUMN precio_costo FLOAT"
    ]
    
    for sql in comandos:
        try:
            db.session.execute(text(sql))
            db.session.commit()
            print(f"✅ Ejecutado: {sql}")
        except Exception as e:
            print(f"ℹ️ Saltado (ya existe o error): {e}")
    print("🚀 Base de datos sincronizada.")