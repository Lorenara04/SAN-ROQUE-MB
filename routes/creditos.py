from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from database import db
from models import Credito, CreditoItem, AbonoCredito, Producto, Cliente, Venta, VentaDetalle
from datetime import datetime, date

creditos_bp = Blueprint('creditos', __name__, url_prefix='/creditos')

# --------------------------------------------------
# BUSCAR PRODUCTO (PARA AGREGAR AL CRÉDITO)
# --------------------------------------------------
@creditos_bp.route('/buscar_producto/<codigo>')
@login_required
def buscar_producto(codigo):
    producto = Producto.query.filter_by(codigo=codigo).first()

    if producto:
        return jsonify({
            "nombre": producto.nombre,
            "precio": producto.valor_venta,
            "costo": producto.valor_interno,
            "stock": producto.cantidad
        })

    return jsonify({"error": "Producto no encontrado"}), 404


# --------------------------------------------------
# CRÉDITOS LARGOS (GESTIÓN)
# --------------------------------------------------
@creditos_bp.route('/largo', methods=['GET', 'POST'])
@login_required
def creditos_largo():
    if request.method == "POST":
        nombre_cliente = (request.form.get('cliente') or '').strip().upper()
        codigo = request.form.get('producto')
        cantidad = int(request.form.get('cantidad', 1))
        fecha_str = request.form.get('fecha')

        if not nombre_cliente:
            flash("Debe ingresar el nombre del cliente", "danger")
            return redirect(url_for('creditos.creditos_largo'))

        # Buscar producto
        producto_db = Producto.query.filter_by(codigo=codigo).first()
        if not producto_db:
            flash("Producto no encontrado", "danger")
            return redirect(url_for('creditos.creditos_largo'))

        # --- CORRECCIÓN: Validar Stock ---
        if producto_db.cantidad < cantidad:
            flash(f"Stock insuficiente para {producto_db.nombre}. Disponible: {producto_db.cantidad}", "warning")
            return redirect(url_for('creditos.creditos_largo'))

        # Buscar o crear cliente
        cliente_db = Cliente.query.filter_by(nombre=nombre_cliente).first()
        if not cliente_db:
            cliente_db = Cliente(nombre=nombre_cliente)
            db.session.add(cliente_db)
            db.session.flush()

        fecha_item = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else date.today()

        # Buscar crédito largo abierto
        credito = Credito.query.filter_by(
            cliente=cliente_db.nombre,
            tipo='largo',
            estado='abierto'
        ).first()

        if not credito:
            credito = Credito(
                cliente=cliente_db.nombre,
                tipo='largo',
                estado='abierto',
                fecha_inicio=fecha_item,
                total_consumido=0,
                abonado=0
            )
            db.session.add(credito)
            db.session.flush()

        # Crear item del crédito
        total_linea = producto_db.valor_venta * cantidad

        nuevo_item = CreditoItem(
            credito_id=credito.id,
            producto=producto_db.nombre.upper(),
            cantidad=cantidad,
            precio_unit=producto_db.valor_venta,
            total_linea=total_linea,
            fecha=fecha_item
        )

        # Actualizar totales y RESTAR del inventario
        credito.total_consumido += total_linea
        producto_db.cantidad -= cantidad 

        db.session.add(nuevo_item)
        db.session.commit()

        flash(f"✅ Cargado: {cantidad}x {producto_db.nombre} a {nombre_cliente}", "success")
        return redirect(url_for('creditos.creditos_largo'))

    # Listado créditos largos
    creditos = Credito.query.filter_by(tipo='largo').order_by(Credito.fecha_inicio.desc()).all()
    inventario = Producto.query.all()

    return render_template(
        "credito_largo.html",
        creditos=creditos,
        inventario=inventario,
        hoy=date.today().strftime('%Y-%m-%d')
    )


# --------------------------------------------------
# REGISTRAR ABONO
# --------------------------------------------------
@creditos_bp.route('/registrar_abono', methods=['POST'])
@login_required
def registrar_abono():
    credito_id = request.form.get('credito_id')
    monto_raw = request.form.get('monto_abono', '0')
    monto = float(monto_raw) if monto_raw else 0.0
    medio = request.form.get('medio_pago', 'Efectivo')
    fecha_pago_str = request.form.get('fecha_pago')

    credito = Credito.query.get_or_404(credito_id)

    if monto <= 0:
        flash("Monto inválido", "danger")
        return redirect(url_for('creditos.creditos_largo'))

    fecha_pago = datetime.strptime(fecha_pago_str, '%Y-%m-%d').date() if fecha_pago_str else date.today()

    # Registrar abono
    nuevo_abono = AbonoCredito(
        credito_id=credito.id,
        monto=monto,
        medio_pago=medio,
        fecha=fecha_pago
    )
    db.session.add(nuevo_abono)

    credito.abonado += monto
    credito.fecha_ultimo_abono = fecha_pago

    # Registrar el abono como venta diaria
    venta = Venta(
        fecha=datetime.now(),
        total=monto,
        usuario_id=current_user.id,
        tipo_pago=medio,
        detalle_pago=f"ABONO CRÉDITO - CLIENTE: {credito.cliente}"
    )
    db.session.add(venta)
    db.session.flush()

    detalle = VentaDetalle(
        venta_id=venta.id,
        producto_id=None,
        cantidad=1,
        precio_unitario=monto,
        subtotal=monto
    )
    db.session.add(detalle)

    # Cerrar crédito si está saldado (o sobre-saldado)
    if (credito.total_consumido - credito.abonado) <= 0:
        credito.estado = 'cerrado'
        credito.fecha_cierre = date.today()
        flash(f"🎉 Cuenta de {credito.cliente} SALDADA.", "success")
    else:
        flash(f"💰 Abono de ${monto:,.0f} registrado.", "success")

    db.session.commit()
    return redirect(url_for('creditos.creditos_largo'))


# --------------------------------------------------
# ELIMINAR CRÉDITO
# --------------------------------------------------
@creditos_bp.route('/eliminar/<int:credito_id>', methods=['POST'])
@login_required
def eliminar_credito(credito_id):
    credito = Credito.query.get_or_404(credito_id)
    try:
        CreditoItem.query.filter_by(credito_id=credito.id).delete()
        AbonoCredito.query.filter_by(credito_id=credito.id).delete()
        db.session.delete(credito)
        db.session.commit()
        flash("Registro de crédito eliminado.", "info")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al eliminar: {str(e)}", "danger")
        
    return redirect(url_for('creditos.creditos_largo'))


# --------------------------------------------------
# EDITAR ITEM DEL CRÉDITO
# --------------------------------------------------
@creditos_bp.route('/editar_item/<int:item_id>', methods=['POST'])
@login_required
def editar_item_credito(item_id):
    item = CreditoItem.query.get_or_404(item_id)
    credito = Credito.query.get_or_404(item.credito_id)

    codigo = request.form.get("producto")
    cantidad = int(request.form.get("cantidad", 1))

    producto_db = Producto.query.filter_by(codigo=codigo).first()
    if not producto_db:
        flash("Producto no encontrado", "danger")
        return redirect(request.referrer)

    # Revertir stock y total antes de actualizar
    producto_anterior = Producto.query.filter_by(nombre=item.producto).first()
    if producto_anterior:
        producto_anterior.cantidad += item.cantidad

    credito.total_consumido -= item.total_linea

    # Aplicar nuevos valores
    item.producto = producto_db.nombre.upper()
    item.cantidad = cantidad
    item.precio_unit = producto_db.valor_venta
    item.total_linea = producto_db.valor_venta * cantidad

    # Descontar nuevo stock y sumar nuevo total
    producto_db.cantidad -= cantidad
    credito.total_consumido += item.total_linea

    db.session.commit()
    flash("Item y stock actualizados", "success")
    return redirect(request.referrer)