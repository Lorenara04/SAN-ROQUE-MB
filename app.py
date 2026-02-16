import os
import json
from datetime import timedelta
from flask import Flask, redirect, url_for, send_file
from flask_login import LoginManager, current_user
from flask_cors import CORS
from dotenv import load_dotenv
import io

# Importaciones locales
from database import db
from config import Config
from models import Usuario, Mesa  # IMPORTANTE: modelos importados aquí
from utils.time_utils import obtener_hora_colombia

# Intentar importar barcode (opcional)
try:
    import barcode
    from barcode.writer import ImageWriter
except ImportError:
    barcode = None

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # --------------------------------------------------
    # CONFIGURACIÓN DE BASE DE DATOS (Render / Local)
    # --------------------------------------------------
    database_url = os.getenv("DATABASE_URL")

    if database_url and "postgresql" in database_url:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///sanroque.db"

    # --------------------------------------------------
    # SEGURIDAD Y SESIONES
    # --------------------------------------------------
    app.config["SECRET_KEY"] = os.getenv(
        "SECRET_KEY", "san-roque-mb-secret-2026"
    )
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)

    # --------------------------------------------------
    # INICIALIZACIÓN DE EXTENSIONES
    # --------------------------------------------------
    CORS(app)
    db.init_app(app)

    # --------------------------------------------------
    # GESTIÓN DE LOGIN
    # --------------------------------------------------
    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return Usuario.query.get(int(user_id))

    # --------------------------------------------------
    # REGISTRO DE BLUEPRINTS (ANTES DE CREAR TABLAS)
    # --------------------------------------------------
    from routes.auth import auth_bp
    from routes.inventario import inventario_bp
    from routes.ventas import ventas_bp
    from routes.reportes import reportes_bp
    from routes.admin import admin_bp
    from routes.clientes import clientes_bp
    from routes.proveedores_gastos import proveedores_gastos_bp
    from routes.creditos import creditos_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(inventario_bp, url_prefix='/inventario')
    app.register_blueprint(ventas_bp, url_prefix='/ventas')
    app.register_blueprint(reportes_bp, url_prefix='/reportes')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(clientes_bp, url_prefix='/clientes')
    app.register_blueprint(proveedores_gastos_bp, url_prefix='/proveedores')
    app.register_blueprint(creditos_bp, url_prefix='/creditos')

    # --------------------------------------------------
    # CREACIÓN SEGURA DE TABLAS (DESPUÉS DE TODO CARGADO)
    # --------------------------------------------------
    with app.app_context():

        print("🚀 SINCRONIZANDO BASE DE DATOS...")

        db.create_all()   # 🔥 YA NO USAMOS drop_all()

        print("✅ TABLAS VERIFICADAS.")

        # Crear mesas si no existen
        if Mesa.query.count() == 0:
            for i in range(1, 13):
                nueva_mesa = Mesa(
                    id=i,
                    estado='libre',
                    total_cuenta=0
                )
                db.session.add(nueva_mesa)
            db.session.commit()
            print("🪑 MESAS: 12 mesas inicializadas correctamente.")

        # Crear admin si no existe
        if Usuario.query.filter_by(username="admin").first() is None:
            admin = Usuario(
                nombre="LORENA",
                apellido="RODRIGUEZ",
                username="admin",
                rol="Administrador",
                cedula="123"
            )
            admin.set_password("1234")

            db.session.add(admin)
            db.session.commit()

            print("👤 USUARIO ADMIN: Creado por defecto (admin / 1234)")

    # --------------------------------------------------
    # FILTRO JINJA
    # --------------------------------------------------
    @app.template_filter("format_number")
    def format_number(value):
        try:
            return f"{float(value):,.0f}".replace(",", ".")
        except:
            return "0"

    # --------------------------------------------------
    # RUTAS BASE
    # --------------------------------------------------
    @app.route("/")
    def index():
        return redirect(url_for("ventas.dashboard"))

    @app.route("/generar_codigo/<codigo>")
    def generar_codigo(codigo):
        if not barcode:
            return "Librería 'python-barcode' no instalada", 404

        CODE128 = barcode.get_barcode_class('code128')
        buffer = io.BytesIO()

        instancia = CODE128(str(codigo), writer=ImageWriter())
        instancia.write(buffer)

        buffer.seek(0)
        return send_file(buffer, mimetype='image/png')

    # --------------------------------------------------
    # CONTEXT PROCESSOR GLOBAL
    # --------------------------------------------------
    @app.context_processor
    def inject_utilities():
        es_admin = False

        if current_user.is_authenticated:
            rol = getattr(current_user, 'rol', '')
            if rol and rol.lower() == 'administrador':
                es_admin = True

        return {
            "ahora_col": obtener_hora_colombia(),
            "timedelta": timedelta,
            "hoy": obtener_hora_colombia().strftime('%Y-%m-%d'),
            "es_admin": es_admin
        }

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
