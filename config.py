import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:

    # 🔐 Clave secreta Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", "licorera-pro-secret")

    # ✅ BASE DE DATOS (Postgres en Render / SQLite en Local)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(basedir, "licorera.db")
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
