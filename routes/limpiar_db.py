from app import app 
from database import db
from sqlalchemy import text

def sincronizar_columnas():
    with app.app_context():
        # Lista de comandos para actualizar la tabla producto con los nombres
        # que usan tus Blueprints (admin, inventario, creditos)
        comandos = [
            "ALTER TABLE producto ADD COLUMN codigo VARCHAR(100)",
            "ALTER TABLE producto ADD COLUMN valor_venta FLOAT",
            "ALTER TABLE producto ADD COLUMN valor_interno FLOAT",
            "ALTER TABLE producto ADD COLUMN marca VARCHAR(100)"
        ]
        
        print("🔍 Iniciando sincronización de esquema...")
        
        for sql in comandos:
            try:
                db.session.execute(text(sql))
                db.session.commit()
                print(f"✅ Ejecutado: {sql}")
            except Exception as e:
                db.session.rollback() # Limpia la transacción fallida
                # Ignoramos si el error es porque la columna ya existe
                if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                    print(f"ℹ️ Saltado: La columna ya existe.")
                else:
                    print(f"❌ Error en comando [{sql}]: {e}")
                    
        print("🚀 Base de datos sincronizada con los modelos actuales.")

if __name__ == "__main__":
    sincronizar_columnas()