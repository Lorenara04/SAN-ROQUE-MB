import os

# Esto obtiene la ruta real de tu carpeta LICORERA
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'licorera-pro-secret-key-2026'
    # Esto asegura que la DB siempre esté en la raíz de tu proyecto
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'licorera.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False