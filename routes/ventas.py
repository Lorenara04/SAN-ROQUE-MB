from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from database import db
from models import Producto, Venta, VentaDetalle, Cliente, Factura, Gasto, Abono, Usuario, Credito
from utils.time_utils import cerrar_turno_anterior_si_pendiente
from sqlalchemy import func, or_
from datetime import datetime, time
import pytz
import json
import urllib.parse

# ==============================
# Blueprint
# ==============================
ventas_bp = Blueprint('ventas', __name__)

# ======================================================
# DASHBOARD (RESISTENTE A ERRORES Y MULTI-ZONA)
# ======================================================
@ventas_bp.route('/dashboard')
@login_required
def dashboard():
    es_admin = current_user.rol.lower() in ['administrador', 'administradora']
    
    # Configuración de tiempo (Bogotá)
    bogota_tz = pytz.timezone('America/Bogota')
    ahora = datetime.now(bogota_tz)
    inicio_dia = datetime.combine(ahora.date(), time.min)
    fin_dia = datetime.combine(ahora.date(), time.max)

    # 1. Ventas del día
    query_ventas = Venta.query.filter(Venta.fecha >= inicio_dia, Venta.fecha <= fin_dia)
    if not es_admin:
        query_ventas = query_ventas.filter(Venta.usuario_id == current_user.id)
    
    ventas_hoy_lista = query_ventas.all()

    # 2. Desglose de Dinero
    v_hoy = 0
    t_efectivo = 0
    t_nequi = 0
    t_daviplata = 0
    t_tarjeta = 0
    t_transferencia = 0

    for v in ventas_hoy_lista:
        v_hoy += v.total
        if v.detalle_pago:
            try:
                # Cargamos el JSON de pagos
                p = json.loads(v.detalle_pago) if isinstance(v.detalle_pago, str) else v.detalle_pago
                t_efectivo += float(p.get('Efectivo', 0))
                t_nequi += float(p.get('Nequi', 0))
                t_daviplata += float(p.get('Daviplata', 0))
                # Unificamos nombres de tarjeta
                t_tarjeta += float(p.get('Tarjeta/Bold', 0) or p.get('Tarjeta', 0))
                t_transferencia += float(p.get('Transferencia', 0))
            except:
                pass

    # 3. Egresos y Cartera
    egresos_hoy = db.session.query(func.sum(Abono.monto))\
        .filter(Abono.fecha >= inicio_dia.date(), Abono.fecha <= fin_dia.date(), Abono.gasto_id.isnot(None)).scalar() or 0

    inv_total = db.session.query(func.sum(Producto.cantidad)).scalar() or 0
    total_deuda_clientes = db.session.query(func.sum(Credito.total_consumido - Credito.abonado))\
        .filter(func.lower(Credito.estado) == "abierto").scalar() or 0

    if es_admin:
        v_interno = db.session.query(func.sum(Producto.cantidad * Producto.valor_interno)).scalar() or 0
        v_venta = db.session.query(func.sum(Producto.cantidad * Producto.valor_venta)).scalar() or 0
        
        s_prov = (db.session.query(func.sum(Factura.total)).scalar() or 0) - \
                 (db.session.query(func.sum(Abono.monto)).filter(Abono.factura_id.isnot(None)).scalar() or 0)
        s_gast = (db.session.query(func.sum(Gasto.total)).scalar() or 0) - \
                 (db.session.query(func.sum(Abono.monto)).filter(Abono.gasto_id.isnot(None)).scalar() or 0)
        total_por_pagar = s_prov + s_gast
    else:
        v_interno = v_venta = total_por_pagar = None

    return render_template(
        'dashboard.html',
        ventas_hoy=v_hoy,
        pago_efectivo=t_efectivo,
        pago_nequi=t_nequi,
        pago_daviplata=t_daviplata,
        pago_tarjeta=t_tarjeta,
        pago_electronico=(t_nequi + t_daviplata + t_tarjeta + t_transferencia),
        egresos_hoy=egresos_hoy,
        total_inventario=inv_total,
        valor_interno_total=v_interno,
        valor_venta_total=v_venta,
        total_facturas_pendiente=total_por_pagar,
        cartera_clientes=total_deuda_clientes,
        es_admin=es_admin
    )

# ======================================================
# REGISTRAR NUEVA VENTA
# ======================================================
@ventas_bp.route('/ventas/nueva', methods=['GET', 'POST'])
@login_required
def nueva_venta():
    cerrar_turno_anterior_si_pendiente(current_user.id)

    if request.method == 'GET':
        # Cargamos productos y clientes para el formulario
        productos = Producto.query.filter(Producto.cantidad > 0).order_by(Producto.nombre.asc()).all()
        clientes = Cliente.query.order_by(Cliente.nombre.asc()).all()
        return render_template('nueva_venta.html', productos=productos, clientes=clientes)

    try:
        # 1. Captura de datos (Cliente General por defecto si no viene ID)
        cliente_id = int(request.form.get('cliente_id') or 1)
        total_venta = float(request.form.get('total_venta', 0))
        productos_vendidos = json.loads(request.form.get('productos_vendidos_json', '[]'))

        if not productos_vendidos:
            flash('El carrito está vacío.', 'warning')
            return redirect(url_for('ventas.nueva_venta'))

        # 2. Procesar detalle de pago (Sincronizado con HTML)
        referencias = json.loads(request.form.get('referencias_pago_json', '{}'))
        detalle_pago_dict = {
            'Efectivo': float(request.form.get('pago_efectivo', 0)),
            'Nequi': float(request.form.get('pago_nequi', 0)),
            'Daviplata': float(request.form.get('pago_daviplata', 0)),
            'Tarjeta/Bold': float(request.form.get('pago_tarjeta', 0)),
            'Transferencia': float(request.form.get('pago_transferencia', 0)),
            'Referencias': referencias
        }

        # 3. Crear Venta
        nueva_v = Venta(
            fecha=datetime.now(pytz.timezone('America/Bogota')).replace(tzinfo=None),
            total=total_venta,
            usuario_id=current_user.id,
            cliente_id=cliente_id,
            detalle_pago=json.dumps(detalle_pago_dict)
        )

        db.session.add(nueva_v)
        db.session.flush()

        # 4. Procesar Inventario y Detalles
        for item in productos_vendidos:
            prod = Producto.query.get(item['id'])
            cant_a_vender = int(item['cantidad'])

            if not prod or prod.cantidad < cant_a_vender:
                raise Exception(f"Stock insuficiente para: {prod.nombre if prod else 'Producto desconocido'}")

            detalle = VentaDetalle(
                venta_id=nueva_v.id,
                producto_id=prod.id,
                cantidad=cant_a_vender,
                precio_unitario=float(item['precio']),
                subtotal=float(item['subtotal'])
            )
            # Restamos del stock físico
            prod.cantidad -= cant_a_vender
            db.session.add(detalle)

        db.session.commit()
        flash('¡Venta registrada con éxito! 🍻', 'success')
        return redirect(url_for('ventas.encomprobante_final', venta_id=nueva_v.id))

    except Exception as e:
        db.session.rollback()
        flash(f'Error al procesar la venta: {str(e)}', 'danger')
        return redirect(url_for('ventas.nueva_venta'))

# ======================================================
# WHATSAPP Y RECIBO
# ======================================================
@ventas_bp.route('/ventas/comprobante/<int:venta_id>')
@login_required
def encomprobante_final(venta_id):
    venta = Venta.query.get_or_404(venta_id)
    detalles = VentaDetalle.query.filter_by(venta_id=venta_id).all()
    cliente_obj = Cliente.query.get(venta.cliente_id)

    # Construcción de mensaje para WhatsApp
    txt_productos = ""
    for d in detalles:
        txt_productos += f"• {d.cantidad}x {d.producto.nombre[:20]} - (${d.subtotal:,.0f})\n"

    mensaje = (
        f"✅ *TICKET DE VENTA #{venta.id:04d}*\n"
        f"📍 *LICORERA SAN ROQUE M.B.*\n"
        f"--------------------------\n"
        f"👤 Cliente: {cliente_obj.nombre.upper() if cliente_obj else 'GENERAL'}\n"
        f"📅 Fecha: {venta.fecha.strftime('%d/%m/%Y %I:%M %p')}\n"
        f"--------------------------\n"
        f"{txt_productos}"
        f"--------------------------\n"
        f"💰 *TOTAL: ${venta.total:,.0f}*\n\n"
        f"¡Salud! Gracias por tu compra. 🥂"
    )
    
    wa_link = f"https://wa.me/?text={urllib.parse.quote(mensaje)}"
    
    return render_template('comprobante.html', 
                            venta=venta, 
                            detalles=detalles, 
                            cliente=cliente_obj,
                            mensaje_wa=wa_link)

# ======================================================
# GESTIÓN Y ANULACIÓN
# ======================================================
@ventas_bp.route('/gestion_ventas')
@login_required
def gestion_ventas():
    if current_user.rol.lower() not in ['administrador', 'administradora']:
        flash('Acceso restringido.', 'danger')
        return redirect(url_for('ventas.dashboard'))

    page = request.args.get('page', 1, type=int)
    ventas_paginadas = Venta.query.order_by(Venta.id.desc()).paginate(page=page, per_page=30)
    
    return render_template('gestion_ventas.html', ventas_paginadas=ventas_paginadas)

@ventas_bp.route('/ventas/eliminar/<int:venta_id>')
@login_required
def eliminar_venta(venta_id):
    if current_user.rol.lower() not in ['administrador', 'administradora']:
        flash('No tienes permiso para borrar ventas.', 'danger')
        return redirect(url_for('ventas.gestion_ventas'))

    try:
        venta = Venta.query.get_or_404(venta_id)
        # Reversamos stock antes de borrar
        for d in venta.detalles:
            p = Producto.query.get(d.producto_id)
            if p: p.cantidad += d.cantidad

        db.session.delete(venta)
        db.session.commit()
        flash('Venta anulada. El stock ha sido devuelto al inventario.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar: {str(e)}', 'danger')
        
    return redirect(url_for('ventas.gestion_ventas'))

# ======================================================
# API DE BÚSQUEDA (Para Select2 o búsquedas manuales)
# ======================================================
@ventas_bp.route('/api/productos/buscar')
@login_required
def buscar_productos_api():
    q = request.args.get('q', '').lower()
    productos = Producto.query.filter(
        or_(
            Producto.nombre.ilike(f'%{q}%'),
            Producto.codigo.ilike(f'%{q}%')
        )
    ).limit(10).all()
    
    return jsonify([{
        'id': p.id, 
        'nombre': p.nombre.upper(),
        'precio': p.valor_venta,
        'stock': p.cantidad
    } for p in productos])