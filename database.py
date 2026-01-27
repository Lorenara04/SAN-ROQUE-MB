from flask_sqlalchemy import SQLAlchemy

# Creamos el objeto db sin pasarle la aplicación (Flask) todavía.
# Esto nos permite importar 'db' en models.py y en las rutas sin problemas.
db = SQLAlchemy()