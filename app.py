import os
import json
from datetime import timedelta
from flask import Flask, redirect, url_for
from flask_login import LoginManager
from flask_cors import CORS
from dotenv import load_dotenv

from database import db
from config import Config
from models import Usuario
from utils.time_utils import obtener_hora_colombia

# Cargar variables de entorno del archivo .env
load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)


    with app.app_context():
    db.create_all()
    # TRUCO: Crear administrador automático si la base está vacía
    from models import Usuario
    if Usuario.query.count() == 0:
        admin = Usuario(
            nombre="LORENA", 
            username="admin", 
            rol="Administrador", 
            cedula="123"
        )
        admin.set_password("1234")
        db.session.add(admin)
        db.session.commit()
        print("✅ Base de datos vacía: Usuario 'admin' creado automáticamente.")

    # --------------------------------------------------
    # 🗄️ CONFIGURACIÓN DE BASE DE DATOS (POSTGRESQL / RENDER)
    # --------------------------------------------------
    # Prioridad: 1. Variable de entorno 'DATABASE_URL' | 2. Tu link directo | 3. SQLite local
    link_directo_render = "postgresql://sanroque_db_user:Lnr7p7UWphk9sTGUoBAk9pDkm87uMWA8@dpg-d5ugvjnfte5s73eb9at0-a.virginia-postgres.render.com/sanroque_db"
    
    database_url = os.getenv('DATABASE_URL', link_directo_render)

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # --------------------------------------------------
    # 🔐 CONFIGURACIÓN DE SEGURIDAD
    # --------------------------------------------------
    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = os.getenv(
            'SECRET_KEY',
            'licorera-san-roque-mb-2026'
        )

    # --------------------------------------------------
    # 📧 VARIABLES DE CORREO
    # --------------------------------------------------
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 465))
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'false').lower() == 'true'
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['CORREO_INFORMES'] = os.getenv('CORREO_INFORMES')

    # --------------------------------------------------
    # EXTENSIONES
    # --------------------------------------------------
    CORS(app)
    db.init_app(app)

    # --------------------------------------------------
    # LOGIN MANAGER
    # --------------------------------------------------
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "Por favor inicia sesión para acceder."
    login_manager.login_message_category = "info"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return Usuario.query.get(int(user_id))

    # --------------------------------------------------
    # FILTROS JINJA
    # --------------------------------------------------
    @app.template_filter('from_json')
    def from_json_filter(value):
        try:
            if value:
                return json.loads(value)
            return {}
        except Exception:
            return {}

    @app.template_filter('format_number')
    def format_number(value):
        try:
            if value is None or value == "":
                return "$ 0"
            return f"$ {float(value):,.0f}".replace(",", ".")
        except Exception:
            return "$ 0"

    @app.template_filter('fecha_co')
    def fecha_co(value):
        if not value:
            return ""
        try:
            return value.strftime('%d/%m/%Y')
        except Exception:
            return str(value)

    # --------------------------------------------------
    # BLUEPRINTS
    # --------------------------------------------------
    from routes.auth import auth_bp
    from routes.inventario import inventario_bp
    from routes.ventas import ventas_bp
    from routes.reportes import reportes_bp
    from routes.admin import admin_bp
    from routes.clientes import clientes_bp
    from routes.proveedores_gastos import proveedores_gastos_bp
    from routes.creditos import creditos_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(inventario_bp)
    app.register_blueprint(ventas_bp)
    app.register_blueprint(reportes_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(clientes_bp)
    app.register_blueprint(proveedores_gastos_bp)
    app.register_blueprint(creditos_bp)

    # --------------------------------------------------
    # RUTA PRINCIPAL
    # --------------------------------------------------
    @app.route('/')
    def index():
        return redirect(url_for('ventas.dashboard'))

    # --------------------------------------------------
    # CONTEXT PROCESSOR GLOBAL
    # --------------------------------------------------
    @app.context_processor
    def inject_utilities():
        return {
            'ahora_col': obtener_hora_colombia(),
            'timedelta': timedelta
        }

    return app

# --------------------------------------------------
# INSTANCIA Y CREACIÓN DE TABLAS
# --------------------------------------------------
app = create_app()

if __name__ == '__main__':
    with app.app_context():
        # Esto crea las tablas en Postgres si no existen
        db.create_all()
        print("✅ Base de Datos PostgreSQL conectada")
        print("✅ Sistema San Roque M.B. iniciado correctamente")

    app.run(debug=True, port=5000)