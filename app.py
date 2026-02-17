import os
import io
from datetime import timedelta

from flask import Flask, redirect, url_for, send_file
from flask_login import LoginManager, current_user
from flask_cors import CORS
from flask_migrate import Migrate
from dotenv import load_dotenv

# --------------------------------------------------
# CARGAR VARIABLES DE ENTORNO
# --------------------------------------------------
load_dotenv()

# --------------------------------------------------
# IMPORTACIONES LOCALES
# --------------------------------------------------
from database import db
from models import Usuario, Mesa
from utils.time_utils import obtener_hora_colombia

# Barcode opcional
try:
    import barcode
    from barcode.writer import ImageWriter
except ImportError:
    barcode = None


# --------------------------------------------------
# CREATE APP
# --------------------------------------------------
def create_app():

    app = Flask(__name__)

    # --------------------------------------------------
    # CONFIG BASE DE DATOS (Render Postgres / Local SQLite)
    # --------------------------------------------------
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace(
                "postgres://", "postgresql://", 1
            )
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///licorera.db"

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "sanroque-secret")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)

    # --------------------------------------------------
    # EXTENSIONES
    # --------------------------------------------------
    CORS(app)
    db.init_app(app)

    # ✅ MIGRACIONES ACTIVAS
    Migrate(app, db)

    # --------------------------------------------------
    # FILTRO JINJA (FIX ERROR format_number)
    # --------------------------------------------------
    @app.template_filter("format_number")
    def format_number(value):
        try:
            return f"{float(value):,.0f}".replace(",", ".")
        except:
            return "0"

    # --------------------------------------------------
    # LOGIN MANAGER
    # --------------------------------------------------
    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return Usuario.query.get(int(user_id))

    # --------------------------------------------------
    # BLUEPRINTS (REGISTRAR TODOS)
    # --------------------------------------------------
    from routes.auth import auth_bp
    from routes.inventario import inventario_bp
    from routes.ventas import ventas_bp
    from routes.reportes import reportes_bp
    from routes.admin import admin_bp
    from routes.clientes import clientes_bp
    from routes.proveedores_gastos import proveedores_gastos_bp
    from routes.creditos import creditos_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(inventario_bp, url_prefix="/inventario")
    app.register_blueprint(ventas_bp, url_prefix="/ventas")
    app.register_blueprint(reportes_bp, url_prefix="/reportes")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(clientes_bp, url_prefix="/clientes")
    app.register_blueprint(proveedores_gastos_bp, url_prefix="/proveedores")
    app.register_blueprint(creditos_bp, url_prefix="/creditos")

    # --------------------------------------------------
    # RUTA PRINCIPAL
    # --------------------------------------------------
    @app.route("/")
    def index():
        return redirect(url_for("ventas.dashboard"))

    # --------------------------------------------------
    # GENERAR CODIGO DE BARRAS
    # --------------------------------------------------
    @app.route("/generar_codigo/<codigo>")
    def generar_codigo(codigo):

        if not barcode:
            return "Barcode no instalado", 404

        CODE128 = barcode.get_barcode_class("code128")
        buffer = io.BytesIO()

        instancia = CODE128(str(codigo), writer=ImageWriter())
        instancia.write(buffer)
        buffer.seek(0)

        return send_file(buffer, mimetype="image/png")

    # --------------------------------------------------
    # CONTEXT PROCESSOR GLOBAL
    # --------------------------------------------------
    @app.context_processor
    def inject_utilities():

        es_admin = False
        if current_user.is_authenticated:
            rol = getattr(current_user, "rol", "")
            if rol and rol.lower() == "administrador":
                es_admin = True

        return {
            "ahora_col": obtener_hora_colombia(),
            "timedelta": timedelta,
            "hoy": obtener_hora_colombia().strftime("%Y-%m-%d"),
            "es_admin": es_admin
        }

    return app


# --------------------------------------------------
# APP PARA GUNICORN / RENDER
# --------------------------------------------------
app = create_app()
