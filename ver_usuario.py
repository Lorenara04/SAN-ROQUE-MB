from app import app, db, Usuario
import os

print(f"📂 DIRECTORIO OPERATIVO: {os.getcwd()}")

with app.app_context():
    # Verificación de la ruta de datos
    db_uri = app.config['SQLALCHEMY_DATABASE_URI']
    print(f"🗄️ CONEXIÓN DB: {db_uri}")
    
    try:
        usuarios = Usuario.query.all()
        print(f"\n📊 AUDITORÍA DE PERSONAL - TOTAL: {len(usuarios)}")
        print("=" * 50)
        
        for u in usuarios:
            nombre_u = getattr(u, 'username', 'N/A')
            rol = getattr(u, 'rol', 'Sin rol')
            # Detectar si se usa hash o texto plano para la clave
            clave_val = getattr(u, 'password', None) or getattr(u, 'password_hash', None)
            
            print(f"👤 USUARIO: {nombre_u.upper()}")
            print(f"   ID: {u.id} | Rol: {rol}")
            
            if clave_val:
                # Solo mostramos el inicio del hash por seguridad
                print(f"   🔑 ESTATUS CLAVE: Protegida (Hash: {clave_val[:12]}...)")
            else:
                print("   ⚠️ ESTATUS CLAVE: [CRÍTICO: SIN CONTRASEÑA]")
                
            print("-" * 50)

        if not usuarios:
            print("❌ ATENCIÓN: No hay usuarios registrados en Licorera Olimpo.")
            print("👉 Ejecute 'crear_admin.py' para habilitar el acceso.")

    except Exception as e:
        print(f"❌ ERROR DE ACCESO A BASE DE DATOS: {e}")
        print("💡 Sugerencia: Verifique que las tablas existan o reinicie la conexión.")