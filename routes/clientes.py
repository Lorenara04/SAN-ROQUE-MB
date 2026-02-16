from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from database import db
from models import Cliente
from sqlalchemy.exc import IntegrityError

clientes_bp = Blueprint('clientes', __name__)


# ===============================
# LISTAR CLIENTES
# ===============================
@clientes_bp.route('/clientes')
@login_required
def clientes():
    clientes_list = Cliente.query.order_by(Cliente.nombre.asc()).all()
    return render_template('clientes.html', clientes=clientes_list)


# ===============================
# AGREGAR CLIENTE
# ===============================
@clientes_bp.route('/clientes/agregar', methods=['POST'])
@login_required
def agregar_cliente():
    nombre = (request.form.get('nombre') or '').strip().upper()
    tipo = (request.form.get('tipo') or 'estandar').lower()

    if not nombre:
        flash('❌ El nombre del cliente es obligatorio.', 'warning')
        return redirect(url_for('clientes.clientes'))

    if tipo not in ['estandar', 'premium']:
        tipo = 'estandar'

    try:
        nuevo = Cliente(
            nombre=nombre,
            tipo=tipo,
            telefono=request.form.get('telefono'),
            direccion=request.form.get('direccion'),
            email=request.form.get('email')
        )

        db.session.add(nuevo)
        db.session.commit()

        flash(f'✅ Cliente {nombre} registrado como {tipo.upper()}.', 'success')

    except IntegrityError:
        db.session.rollback()
        flash('❌ Ya existe un cliente con ese nombre.', 'danger')

    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al registrar: {str(e)}', 'danger')

    return redirect(url_for('clientes.clientes'))


# ===============================
# EDITAR CLIENTE
# ===============================
@clientes_bp.route('/clientes/editar/<int:id>', methods=['POST'])
@login_required
def editar_cliente(id):
    cliente = Cliente.query.get_or_404(id)

    nombre = (request.form.get('nombre') or '').strip().upper()
    tipo = (request.form.get('tipo') or 'estandar').lower()

    if not nombre:
        flash('❌ El nombre no puede estar vacío.', 'warning')
        return redirect(url_for('clientes.clientes'))

    if tipo not in ['estandar', 'premium']:
        tipo = 'estandar'

    try:
        cliente.nombre = nombre
        cliente.tipo = tipo
        cliente.telefono = request.form.get('telefono')
        cliente.direccion = request.form.get('direccion')
        cliente.email = request.form.get('email')

        db.session.commit()

        flash(f'✅ Cliente actualizado a {tipo.upper()}.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al actualizar: {str(e)}', 'danger')

    return redirect(url_for('clientes.clientes'))


# ===============================
# ELIMINAR CLIENTE
# ===============================
@clientes_bp.route('/clientes/eliminar/<int:id>', methods=['POST'])
@login_required
def eliminar_cliente(id):
    cliente = Cliente.query.get_or_404(id)

    try:
        db.session.delete(cliente)
        db.session.commit()
        flash('🗑️ Cliente eliminado correctamente.', 'success')

    except Exception:
        db.session.rollback()
        flash('❌ No se pudo eliminar (puede tener ventas asociadas).', 'danger')

    return redirect(url_for('clientes.clientes'))
