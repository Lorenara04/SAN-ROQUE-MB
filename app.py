import os
import json
from datetime import timedelta
from flask import Flask, redirect, url_for
from flask_login import LoginManager
from flask_cors import CORS

from database import db
from config import Config
from models import Usuario
from utils.time_utils import obtener_hora_colombia

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # 🔐 Clave secreta (Garantiza que las sesiones funcionen)
    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = 'licorera-san-roque-mb-2026'

    # Inicializar extensiones
    CORS(app)
    db.init_app(app)

    # -------------------------
    # Login Manager
    # -------------------------
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "Por favor inicia sesión para acceder."
    login_manager.login_message_category = "info"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return Usuario.query.get(int(user_id))

    # -------------------------
    # Filtros personalizados para Jinja2
    # -------------------------
    
    @app.template_filter('from_json')
    def from_json_filter(value):
        """Convierte una cadena JSON de la DB en un diccionario de Python"""
        try:
            if value:
                return json.loads(value)
            return {}
        except (ValueError, TypeError):
            return {}

    @app.template_filter('format_number')
    def format_number(value):
        """Formato de moneda profesional: $ 1.250"""
        try:
            if value is None or value == "":
                return "$ 0"
            return f"$ {float(value):,.0f}".replace(",", ".")
        except (ValueError, TypeError):
            return "$ 0"

    @app.template_filter('fecha_co')
    def fecha_co(value):
        """Formatea objetos de fecha al estándar colombiano"""
        if not value:
            return ""
        try:
            return value.strftime('%d/%m/%Y')
        except AttributeError:
            return str(value)

    # -----------------------------------------------------------
    # Registro de Blueprints
    # -----------------------------------------------------------
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

    # -------------------------
    # Rutas globales y Context Processors
    # -------------------------
    @app.route('/')
    def index():
        return redirect(url_for('ventas.dashboard'))

    @app.context_processor
    def inject_utilities():
        """Inyecta variables y funciones útiles en todas las plantillas"""
        return {
            'ahora_col': obtener_hora_colombia(),
            'timedelta': timedelta  # Permite cálculos de fechas directamente en el HTML
        }

    return app

if __name__ == '__main__':
    app = create_app()

    with app.app_context():
        # Crea las tablas si no existen basándose en los modelos corregidos
        db.create_all()
        print("✅ Base de datos de San Roque M.B. verificada correctamente.")

    # Ejecución del servidor
    app.run(debug=True, port=5000)