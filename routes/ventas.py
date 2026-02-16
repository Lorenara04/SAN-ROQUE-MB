from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from database import db
from models import Producto, Venta, VentaDetalle, Mesa, Cliente
from datetime import datetime
import json

ventas_bp = Blueprint('ventas', __name__)

# =========================================================
# DASHBOARD: ESTADO DE MESAS Y VENTAS ACTIVAS
# =========================================================
@ventas_bp.route('/')
@ventas_bp.route('/dashboard')
@login_required
def dashboard():
    mesas = Mesa.query.order_by(Mesa.id.asc()).all()
    ventas_abiertas = Venta.query.filter_by(estado='abierta').all()
    return render_template('dashboard.html', mesas=mesas, ventas_abiertas=ventas_abiertas)

# =========================================================
# GESTIÓN DE PESTAÑAS (ABRIR Y ELIMINAR)
# =========================================================

@ventas_bp.route('/abrir_pestana')
@login_required
def abrir_pestana():
    """Crea una orden genérica en la primera mesa libre disponible."""
    ventas_abiertas = Venta.query.filter_by(estado='abierta').all()
    ids_ocupados = [v.mesa_id for v in ventas_abiertas]
    
    mesa_libre = Mesa.query.filter(~Mesa.id.in_(ids_ocupados)).first()
    
    if not mesa_libre:
        return jsonify({'success': False, 'message': 'No hay mesas disponibles'}), 400

    return redirect(url_for('ventas.ver_mesa', mesa_id=mesa_libre.id))

@ventas_bp.route('/eliminar_venta/<int:venta_id>', methods=['POST'])
@login_required
def eliminar_venta(venta_id):
    """Borra la venta actual, sus detalles y libera la mesa."""
    venta = Venta.query.get_or_404(venta_id)
    try:
        if venta.mesa_id:
            mesa = Mesa.query.get(venta.mesa_id)
            if mesa: mesa.estado = 'libre'
        
        VentaDetalle.query.filter_by(venta_id=venta.id).delete()
        db.session.delete(venta)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# =========================================================
# TERMINAL DE VENTA (UI Y LÓGICA DE CLIENTE)
# =========================================================

@ventas_bp.route('/mesa/<int:mesa_id>')
@login_required
def ver_mesa(mesa_id):
    mesa = Mesa.query.get_or_404(mesa_id)
    nombre_cliente = request.args.get('nombre')
    venta = Venta.query.filter_by(mesa_id=mesa_id, estado='abierta').first()

    if not venta:
        # Nombre por defecto si no se especifica uno
        alias = nombre_cliente if nombre_cliente else f"ORDEN {mesa_id}"
        venta = Venta(
            fecha=datetime.now(),
            total=0,
            usuario_id=current_user.id,
            estado='abierta',
            mesa_id=mesa_id,
            nombre_cliente=alias
        )
        db.session.add(venta)
        mesa.estado = 'ocupada'
        db.session.commit()
    
    elif nombre_cliente:
        venta.nombre_cliente = nombre_cliente
        db.session.commit()

    return render_template(
        'nueva_venta.html',
        mesa=mesa,
        venta=venta,
        productos=Producto.query.filter(Producto.cantidad > 0).all(),
        detalles=VentaDetalle.query.filter_by(venta_id=venta.id).all(),
        pestañas_activas=Venta.query.filter_by(estado='abierta').all(),
        clientes=Cliente.query.all()
    )

@ventas_bp.route('/asignar_cliente', methods=['POST'])
@login_required
def asignar_cliente():
    data = request.get_json()
    venta = Venta.query.get_or_404(data.get('venta_id'))
    cliente = Cliente.query.get(data.get('cliente_id'))

    if not cliente:
        return jsonify({'success': False, 'message': 'Cliente no encontrado'}), 400

    venta.cliente_id = cliente.id
    venta.nombre_cliente = cliente.nombre 
    db.session.commit()

    return jsonify({'success': True})

# =========================================================
# OPERACIONES DE PRODUCTOS (CARRITO)
# =========================================================

@ventas_bp.route('/buscar_producto/<codigo>')
@login_required
def buscar_producto(codigo):
    producto = Producto.query.filter_by(codigo=codigo).first()
    if producto:
        return jsonify({
            'success': True,
            'producto_id': producto.id,
            'nombre': producto.nombre,
            'precio': producto.valor_venta
        })
    return jsonify({'success': False, 'message': 'Producto no encontrado'})

@ventas_bp.route('/agregar_producto', methods=['POST'])
@login_required
def agregar_producto():
    data = request.get_json()
    venta = Venta.query.get_or_404(data.get('venta_id'))
    producto = Producto.query.get_or_404(data.get('producto_id'))

    if producto.cantidad <= 0:
        return jsonify({'success': False, 'message': 'Sin stock disponible'}), 400

    try:
        cliente = Cliente.query.get(venta.cliente_id) if venta.cliente_id else None
        precio = producto.valor_interno if cliente and cliente.tipo == 'premium' else producto.valor_venta

        producto.cantidad -= 1
        detalle = VentaDetalle.query.filter_by(venta_id=venta.id, producto_id=producto.id).first()

        if detalle:
            detalle.cantidad += 1
            detalle.subtotal = detalle.cantidad * detalle.precio_unitario
        else:
            detalle = VentaDetalle(
                venta_id=venta.id,
                producto_id=producto.id,
                cantidad=1,
                precio_unitario=precio,
                subtotal=precio
            )
            db.session.add(detalle)

        db.session.commit()
        venta.total = sum(d.subtotal for d in VentaDetalle.query.filter_by(venta_id=venta.id).all())
        db.session.commit()

        return jsonify({'success': True, 'nuevo_total': venta.total})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@ventas_bp.route('/actualizar_cantidad', methods=['POST'])
@login_required
def actualizar_cantidad():
    data = request.get_json()
    detalle = VentaDetalle.query.get_or_404(data.get('detalle_id'))
    producto = Producto.query.get_or_404(detalle.producto_id)
    venta = Venta.query.get(detalle.venta_id)
    nueva_cantidad = int(data.get('cantidad', 1))
    diferencia = nueva_cantidad - detalle.cantidad

    if diferencia > 0 and producto.cantidad < diferencia:
        return jsonify({'success': False, 'message': 'Stock insuficiente'}), 400

    try:
        producto.cantidad -= diferencia
        detalle.cantidad = nueva_cantidad
        detalle.subtotal = nueva_cantidad * detalle.precio_unitario
        db.session.commit()
        venta.total = sum(d.subtotal for d in VentaDetalle.query.filter_by(venta_id=venta.id).all())
        db.session.commit()
        return jsonify({'success': True, 'nuevo_total': venta.total, 'nuevo_subtotal': detalle.subtotal})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@ventas_bp.route('/eliminar_producto', methods=['POST'])
@login_required
def eliminar_producto():
    """Ruta corregida para evitar el BuildError. Elimina un item específico del carrito."""
    data = request.get_json()
    detalle = VentaDetalle.query.get_or_404(data.get('detalle_id'))
    producto = Producto.query.get_or_404(detalle.producto_id)
    venta = Venta.query.get(detalle.venta_id)

    try:
        # Devolvemos el stock al producto
        producto.cantidad += detalle.cantidad
        db.session.delete(detalle)
        db.session.commit()

        # Recalculamos el total de la venta
        detalles_restantes = VentaDetalle.query.filter_by(venta_id=venta.id).all()
        venta.total = sum(d.subtotal for d in detalles_restantes)
        db.session.commit()

        return jsonify({'success': True, 'nuevo_total': venta.total})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# =========================================================
# CIERRE DE VENTA Y TICKETS
# =========================================================

@ventas_bp.route('/cerrar_venta', methods=['POST'])
@login_required
def cerrar_venta():
    data = request.get_json()
    venta = Venta.query.get_or_404(data.get('venta_id'))
    metodo = data.get('metodo_pago', 'EFECTIVO')
    efectivo = float(data.get('pago_efectivo', 0))

    try:
        venta.estado = 'cerrada'
        venta.tipo_pago = metodo
        venta.detalle_pago = json.dumps({
            "metodo": metodo, "recibido": efectivo,
            "cambio": efectivo - venta.total if efectivo > 0 else 0
        })

        if venta.mesa_id:
            mesa = Mesa.query.get(venta.mesa_id)
            if mesa: mesa.estado = 'libre'

        db.session.commit()
        return jsonify({'success': True, 'redirect_url': url_for('ventas.ver_ticket', venta_id=venta.id)})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@ventas_bp.route('/ticket/<int:venta_id>')
@login_required
def ver_ticket(venta_id):
    venta = Venta.query.get_or_404(venta_id)
    detalles = VentaDetalle.query.filter_by(venta_id=venta.id).all()
    pagos = json.loads(venta.detalle_pago) if venta.detalle_pago else {}
    return render_template('comprobante.html', venta=venta, detalles=detalles, pagos=pagos)