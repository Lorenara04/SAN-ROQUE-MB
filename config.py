import os
from dotenv import load_dotenv

# Cargar variables del archivo .env (solo en local)
load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:

    # 🔐 Clave secreta Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", "licorera-pro-secret")

    # --------------------------------------------------
    # BASE DE DATOS
    # - Producción (Render): PostgreSQL usando DATABASE_URL
    # - Local (Tu PC): SQLite usando sanroque.db
    # --------------------------------------------------

    database_url = os.environ.get("DATABASE_URL")

    # Render a veces usa postgres:// pero SQLAlchemy necesita postgresql://
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    # ✅ Si existe DATABASE_URL → estamos en Render
    # ✅ Si NO existe → usamos SQLite local sanroque.db
    SQLALCHEMY_DATABASE_URI = database_url or (
        "sqlite:///" + os.path.join(basedir, "sanroque.db")
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
