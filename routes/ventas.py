from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from database import db
from models import Producto, Venta, VentaDetalle, Cliente, Factura, Gasto, Abono, Usuario, Credito
from utils.time_utils import cerrar_turno_anterior_si_pendiente
from sqlalchemy import func
from datetime import datetime, date
import pytz
import json

# ==============================
# Blueprint
# ==============================
ventas_bp = Blueprint('ventas', __name__)

# ======================================================
# DASHBOARD
# ======================================================
@ventas_bp.route('/dashboard')
@login_required
def dashboard():
    es_admin = current_user.rol.lower() in ['administrador', 'administradora']

    if es_admin:
        v_hoy = db.session.query(func.sum(Venta.total)) \
            .filter(func.date(Venta.fecha) == date.today()).scalar() or 0
    else:
        v_hoy = db.session.query(func.sum(Venta.total)) \
            .filter(
                func.date(Venta.fecha) == date.today(),
                Venta.usuario_id == current_user.id
            ).scalar() or 0

    inv_total = db.session.query(func.sum(Producto.cantidad)).scalar() or 0

    if es_admin:
        v_interno = db.session.query(func.sum(Producto.cantidad * Producto.valor_interno)).scalar() or 0
        v_venta = db.session.query(func.sum(Producto.cantidad * Producto.valor_venta)).scalar() or 0
        
        total_facturas = db.session.query(func.sum(Factura.total)).scalar() or 0
        total_abonos_facturas = db.session.query(func.sum(Abono.monto)).filter(Abono.factura_id.isnot(None)).scalar() or 0
        saldos_proveedores = total_facturas - total_abonos_facturas

        total_gastos = db.session.query(func.sum(Gasto.total)).scalar() or 0
        total_abonos_gastos = db.session.query(func.sum(Abono.monto)).filter(Abono.gasto_id.isnot(None)).scalar() or 0
        saldos_gastos = total_gastos - total_abonos_gastos
    else:
        v_interno = v_venta = saldos_proveedores = saldos_gastos = None

    return render_template(
        'dashboard.html',
        ventas_hoy=v_hoy,
        total_inventario=inv_total,
        valor_interno_total=v_interno,
        valor_venta_total=v_venta,
        total_facturas_pendiente=saldos_proveedores,
        total_gastos_pendiente=saldos_gastos,
        es_admin=es_admin
    )

# ======================================================
# NUEVA VENTA
# ======================================================
@ventas_bp.route('/ventas/nueva', methods=['GET', 'POST'])
@login_required
def nueva_venta():
    cerrar_turno_anterior_si_pendiente(current_user.id)

    if request.method == 'GET':
        productos = Producto.query.filter(Producto.cantidad > 0).all()
        clientes = Cliente.query.order_by(Cliente.nombre.asc()).all()
        return render_template('nueva_venta.html', productos=productos, clientes=clientes)

    try:
        cliente_id = int(request.form.get('cliente_id') or 1)
        total_venta = float(request.form.get('total_venta', 0))
        productos_vendidos = json.loads(request.form.get('productos_vendidos_json', '[]'))

        if not productos_vendidos:
            flash('No hay productos seleccionados.', 'warning')
            return redirect(url_for('ventas.nueva_venta'))

        referencias = json.loads(request.form.get('referencias_pago_json', '{}'))
        detalle_pago = {
            'Efectivo': float(request.form.get('pago_efectivo', 0)),
            'Nequi': float(request.form.get('pago_nequi', 0)),
            'Daviplata': float(request.form.get('pago_daviplata', 0)),
            'Tarjeta/Bold': float(request.form.get('pago_tarjeta', 0)),
            'Transferencia': float(request.form.get('pago_transferencia', 0)),
            'Referencias': referencias
        }

        nueva_v = Venta(
            fecha=datetime.now(pytz.timezone('America/Bogota')),
            total=total_venta,
            usuario_id=current_user.id,
            cliente_id=cliente_id,
            detalle_pago=json.dumps(detalle_pago)
        )

        db.session.add(nueva_v)
        db.session.flush()

        for item in productos_vendidos:
            prod = Producto.query.get(item['id'])
            if prod.cantidad < int(item['cantidad']):
                raise Exception(f"Stock insuficiente: {prod.nombre}")

            detalle = VentaDetalle(
                venta_id=nueva_v.id,
                producto_id=prod.id,
                cantidad=int(item['cantidad']),
                precio_unitario=float(item['precio']),
                subtotal=float(item['subtotal'])
            )
            prod.cantidad -= int(item['cantidad'])
            db.session.add(detalle)

        db.session.commit()
        flash('Venta registrada exitosamente.', 'success')
        return redirect(url_for('ventas.encomprobante_final', venta_id=nueva_v.id))

    except Exception as e:
        db.session.rollback()
        flash(f'Error al procesar venta: {str(e)}', 'danger')
        return redirect(url_for('ventas.nueva_venta'))

# ======================================================
# GESTIÓN VENTAS & COMPROBANTES
# ======================================================
@ventas_bp.route('/gestion_ventas')
@login_required
def gestion_ventas():
    if current_user.rol.lower() not in ['administrador', 'administradora']:
        flash('Permiso denegado.', 'danger')
        return redirect(url_for('ventas.dashboard'))

    page = request.args.get('page', 1, type=int)
    ventas_paginadas = Venta.query.order_by(Venta.id.desc()).paginate(page=page, per_page=50, error_out=False)
    
    vendedores = Usuario.query.all()
    clientes = Cliente.query.all()

    return render_template(
        'gestion_ventas.html',
        ventas_paginadas=ventas_paginadas,
        vendedores_full=vendedores,
        clientes_full=clientes
    )

@ventas_bp.route('/ventas/eliminar/<int:venta_id>')
@login_required
def eliminar_venta(venta_id):
    if current_user.rol.lower() not in ['administrador', 'administradora']:
        flash('Solo administradores pueden anular ventas.', 'danger')
        return redirect(url_for('ventas.gestion_ventas'))

    venta = Venta.query.get_or_404(venta_id)
    for d in venta.detalles:
        prod = Producto.query.get(d.producto_id)
        if prod: prod.cantidad += d.cantidad

    VentaDetalle.query.filter_by(venta_id=venta.id).delete()
    db.session.delete(venta)
    db.session.commit()
    flash('Venta anulada y stock devuelto.', 'success')
    return redirect(url_for('ventas.gestion_ventas'))

@ventas_bp.route('/ventas/comprobante/<int:venta_id>')
@login_required
def encomprobante_final(venta_id):
    # 1. Obtener la venta
    venta = Venta.query.get_or_404(venta_id)
    
    # 2. Obtener detalles incluyendo el objeto producto para marca/descripción
    detalles = VentaDetalle.query.filter_by(venta_id=venta_id).all()
    
    # 3. Obtener los datos del cliente de forma independiente
    cliente_obj = Cliente.query.get(venta.cliente_id)
    
    # 4. Aseguramos que la fecha sea local antes de enviar
    return render_template('comprobante.html', 
                           venta=venta, 
                           detalles=detalles, 
                           cliente=cliente_obj)

# ======================================================
# API PARA EDICIÓN Y GESTIÓN DE CRÉDITOS
# ======================================================
@ventas_bp.route('/api/venta/<int:venta_id>')
@login_required
def obtener_venta_api(venta_id):
    try:
        venta = Venta.query.get_or_404(venta_id)
        items = [{
            'id': d.producto_id,
            'nombre': d.producto.nombre if d.producto else "Eliminado",
            'cantidad': d.cantidad,
            'precio': d.precio_unitario,
            'subtotal': d.subtotal
        } for d in venta.detalles]
        
        pagos = json.loads(venta.detalle_pago) if venta.detalle_pago else {}
        return jsonify({
            'id': venta.id,
            'vendedor_id': venta.usuario_id,
            'cliente_id': venta.cliente_id,
            'items': items,
            'pagos': pagos,
            'total': venta.total
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ventas_bp.route('/api/venta/editar_info/<int:venta_id>', methods=['POST'])
@login_required
def editar_info_venta(venta_id):
    try:
        data = request.json
        venta = Venta.query.get_or_404(venta_id)
        
        venta.usuario_id = data.get('vendedor_id')
        venta.cliente_id = data.get('cliente_id')
        cliente_nuevo = Cliente.query.get(venta.cliente_id)
        
        pagos = data.get('pagos')
        tipo_cuenta = data.get('tipo_cuenta', 'contado') 
        
        if tipo_cuenta in ['corto', 'largo'] and cliente_nuevo:
            cred = Credito.query.filter(Credito.producto.like(f"Venta #{venta.id}%")).first()
            if not cred:
                cred = Credito(
                    cliente=cliente_nuevo.nombre,
                    producto=f"Venta #{venta.id}",
                    cantidad=1,
                    total_consumido=venta.total,
                    abonado=0,
                    estado="ABIERTO",
                    fecha=venta.fecha
                )
                db.session.add(cred)
            else:
                cred.cliente = cliente_nuevo.nombre
                cred.total_consumido = venta.total

        venta.detalle_pago = json.dumps(pagos)
        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'msg': str(e)})

@ventas_bp.route('/api/venta/editar_items/<int:venta_id>', methods=['POST'])
@login_required
def editar_items_venta(venta_id):
    try:
        data = request.json
        venta = Venta.query.get_or_404(venta_id)
        
        # Devolver stock anterior
        for d in venta.detalles:
            prod = Producto.query.get(d.producto_id)
            if prod: prod.cantidad += d.cantidad
        
        VentaDetalle.query.filter_by(venta_id=venta.id).delete()
        
        nuevo_total = 0
        for item in data.get('items'):
            prod = Producto.query.get(item['id'])
            if not prod: continue
            
            nuevo_d = VentaDetalle(
                venta_id=venta.id, 
                producto_id=prod.id,
                cantidad=int(item['cantidad']), 
                precio_unitario=float(item['precio']),
                subtotal=float(item['subtotal'])
            )
            prod.cantidad -= int(item['cantidad'])
            nuevo_total += nuevo_d.subtotal
            db.session.add(nuevo_d)
            
        venta.total = nuevo_total
        
        cred = Credito.query.filter(Credito.producto.like(f"Venta #{venta.id}%")).first()
        if cred:
            cred.total_consumido = nuevo_total

        db.session.commit()
        return jsonify({'ok': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'msg': str(e)})

@ventas_bp.route('/api/productos/buscar')
@login_required
def buscar_productos_api():
    q = request.args.get('q', '').lower()
    productos = Producto.query.filter(Producto.nombre.ilike(f'%{q}%')).limit(10).all()
    return jsonify([{'id': p.id, 'nombre': p.nombre, 'precio': p.valor_venta} for p in productos])