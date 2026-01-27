from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from database import db
from models import Cliente
from sqlalchemy.exc import IntegrityError

# Definimos el Blueprint correctamente
clientes_bp = Blueprint('clientes', __name__)

@clientes_bp.route('/clientes')
@login_required
def clientes():
    # Esta línea ahora funcionará porque la tabla se creará con 'categoria'
    clientes_list = Cliente.query.order_by(Cliente.nombre.asc()).all()
    return render_template('clientes.html', clientes=clientes_list)

@clientes_bp.route('/clientes/agregar', methods=['POST'])
@login_required
def agregar_cliente():
    try:
        nuevo = Cliente(
            nombre=request.form.get('nombre').strip().upper(),
            categoria=request.form.get('categoria', 'estandar'),
            telefono=request.form.get('telefono'),
            direccion=request.form.get('direccion'),
            email=request.form.get('email')
        )
        db.session.add(nuevo)
        db.session.commit()
        flash('✅ Cliente registrado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error: {str(e)}', 'danger')
    return redirect(url_for('clientes.clientes'))

@clientes_bp.route('/clientes/editar/<int:id>', methods=['POST'])
@login_required
def editar_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    try:
        cliente.nombre = request.form.get('nombre').strip().upper()
        cliente.categoria = request.form.get('categoria', 'estandar')
        cliente.telefono = request.form.get('telefono')
        cliente.direccion = request.form.get('direccion')
        cliente.email = request.form.get('email')
        db.session.commit()
        flash('✅ Actualizado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error: {str(e)}', 'danger')
    return redirect(url_for('clientes.clientes'))

@clientes_bp.route('/clientes/eliminar/<int:id>')
@login_required
def eliminar_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    try:
        db.session.delete(cliente)
        db.session.commit()
    except:
        db.session.rollback()
    return redirect(url_for('clientes.clientes'))