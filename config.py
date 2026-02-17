import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:

    # 🔐 Clave secreta Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", "licorera-pro-secret")

    # --------------------------------------------------
    # BASE DE DATOS (Postgres Render / SQLite Local)
    # --------------------------------------------------
    database_url = os.environ.get("DATABASE_URL")

    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://", "postgresql://", 1
        )

    SQLALCHEMY_DATABASE_URI = database_url or (
        "sqlite:///" + os.path.join(basedir, "licorera.db")
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
