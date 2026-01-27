from app import create_app
from database import db
from models import Usuario

app = create_app()

def generar_administrador():
    with app.app_context():
        # 1. Limpiamos por si quedó algún rastro
        Usuario.query.filter_by(username='admin').delete()
        
        # 2. Creamos con TODOS los campos de tu clase Usuario en models.py
        nuevo_usuario = Usuario(
            username='admin',
            nombre='Administradora',
            apellido='Lorena',
            cedula='12345678', # Campo único en tu modelo
            rol='Administrador'
        )
        nuevo_usuario.set_password('1234')
        
        db.session.add(nuevo_usuario)
        db.session.commit()
        print("✅ Usuario 'admin' (Clave: 1234) creado con éxito en la base de datos única.")

if __name__ == '__main__':
    generar_administrador()