from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import Usuario
from sqlalchemy.exc import OperationalError

# Definimos el Blueprint para autenticación
# Se llama 'auth', por lo tanto en url_for se usa 'auth.login'
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # 1. Si el usuario ya está logueado, lo mandamos al dashboard directamente
    if current_user.is_authenticated:
        return redirect(url_for('ventas.dashboard'))

    if request.method == 'POST':
        # strip() elimina espacios accidentales al inicio o final
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Por favor, ingresa todos los campos.', 'warning')
            return render_template('login.html')

        try:
            # Buscamos al usuario en la base de datos
            user = Usuario.query.filter_by(username=username).first()

            # Verificamos usuario y contraseña
            if user and user.check_password(password):
                login_user(user)
                flash(f'¡Bienvenido, {user.nombre}! 🍷', 'success')
                return redirect(url_for('ventas.dashboard'))
            else:
                flash('Usuario o contraseña incorrectos.', 'danger')

        except OperationalError as e:
            flash('Error de conexión con la base de datos. Intenta de nuevo.', 'danger')
            print(f"Error de DB: {e}")
        except Exception as e:
            flash(f'Ocurrió un error inesperado: {str(e)}', 'danger')

    # IMPORTANTE: Asegúrate de que el archivo en templates se llame 'login.html'
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada. ¡Vuelve pronto!', 'info')
    return redirect(url_for('auth.login'))