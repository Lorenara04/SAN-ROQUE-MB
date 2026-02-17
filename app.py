import os
import io
from datetime import timedelta
from flask import Flask, redirect, url_for, send_file
from flask_login import LoginManager, current_user
from flask_cors import CORS
from flask_migrate import Migrate
from dotenv import load_dotenv

load_dotenv()

from database import db
from models import Usuario, Mesa
from utils.time_utils import obtener_hora_colombia

# Barcode opcional
try:
    import barcode
    from barcode.writer import ImageWriter
except ImportError:
    barcode = None


def create_app():

    app = Flask(__name__)

    # ✅ CONFIG DB
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)

        app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///licorera.db"

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "sanroque-secret")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)

    # ✅ INIT EXTENSIONS
    CORS(app)
    db.init_app(app)

    # 🔥 MIGRATE REGISTRADO CORRECTAMENTE
    Migrate(app, db)

    # ✅ LOGIN
    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return Usuario.query.get(int(user_id))

    # ✅ BLUEPRINTS
    from routes.inventario import inventario_bp
    from routes.ventas import ventas_bp
    from routes.auth import auth_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(inventario_bp)
    app.register_blueprint(ventas_bp)

    # ❌ NO create_all EN PRODUCCIÓN
    # db.create_all() QUITAR

    return app


app = create_app()
