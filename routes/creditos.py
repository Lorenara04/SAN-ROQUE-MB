from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from database import db
from models import Credito, CreditoItem, AbonoCredito, Producto, Cliente, Venta, VentaDetalle
from datetime import datetime, date

creditos_bp = Blueprint('creditos', __name__, url_prefix='/creditos')

# --------------------------------------------------
# BUSCAR PRODUCTO
# --------------------------------------------------
@creditos_bp.route('/buscar_producto/<codigo>')
@login_required
def buscar_producto(codigo):
    producto = Producto.query.filter(
        (Producto.codigo_barra == codigo) |
        (Producto.codigo == codigo)
    ).first()

    if producto:
        return jsonify({
            "nombre": producto.nombre,
            "precio": producto.valor_venta,
            "costo": producto.valor_interno
        })

    return jsonify({"error": "Producto no encontrado"}), 404


# --------------------------------------------------
# CREDITOS CORTOS
# --------------------------------------------------
@creditos_bp.route('/corto', methods=['GET', 'POST'])
@login_required
def creditos_corto():

    if request.method == "POST":

        nombre_cliente = request.form.get('cliente', '').strip().upper()
        codigo = request.form.get('producto')
        cantidad = int(request.form.get('cantidad', 1))
        fecha_str = request.form.get('fecha')

        # ------------------------
        # VALIDAR CLIENTE
        # ------------------------
        if not nombre_cliente:
            flash("Debe ingresar el nombre del cliente", "danger")
            return redirect(url_for('creditos.creditos_corto'))

        # ------------------------
        # CREAR CLIENTE SI NO EXISTE
        # ------------------------
        cliente_db = Cliente.query.filter_by(nombre=nombre_cliente).first()
        if not cliente_db:
            cliente_db = Cliente(nombre=nombre_cliente)
            db.session.add(cliente_db)
            db.session.flush()

        # ------------------------
        # BUSCAR PRODUCTO
        # ------------------------
        producto_db = Producto.query.filter(
            (Producto.codigo_barra == codigo) |
            (Producto.codigo == codigo)
        ).first()

        if not producto_db:
            flash("Producto no encontrado", "danger")
            return redirect(url_for('creditos.creditos_corto'))

        # ------------------------
        # FECHA
        # ------------------------
        fecha_item = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else date.today()

        # ------------------------
        # BUSCAR CRÉDITO ABIERTO
        # ------------------------
        credito = Credito.query.filter_by(
            cliente=cliente_db.nombre,
            tipo='corto',
            estado='abierto'
        ).first()

        if not credito:
            credito = Credito(
                cliente=cliente_db.nombre,
                tipo='corto',
                estado='abierto',
                fecha_inicio=fecha_item,
                total_consumido=0,
                abonado=0
            )
            db.session.add(credito)
            db.session.flush()

        # ------------------------
        # ITEM
        # ------------------------
        nuevo_item = CreditoItem(
            credito_id=credito.id,
            producto=producto_db.nombre.upper(),
            cantidad=cantidad,
            precio_unit=producto_db.valor_venta,
            total_linea=producto_db.valor_venta * cantidad,
            fecha=fecha_item
        )

        credito.total_consumido += nuevo_item.total_linea

        db.session.add(nuevo_item)
        db.session.commit()

        flash(f"Se agregó {producto_db.nombre} a la cuenta de {cliente_db.nombre}", "success")
        return redirect(url_for('creditos.creditos_corto'))

    # ------------------------
    # GET
    # ------------------------
    creditos = Credito.query.filter_by(
        tipo='corto',
        estado='abierto'
    ).order_by(Credito.fecha_inicio.desc()).all()

    inventario = Producto.query.all()

    return render_template(
        "creditos_corto.html",
        creditos=creditos,
        inventario=inventario,
        hoy=date.today().strftime('%Y-%m-%d')
    )


# --------------------------------------------------
# CREDITOS LARGOS
# --------------------------------------------------
@creditos_bp.route('/largo', methods=['GET', 'POST'])
@login_required
def creditos_largo():

    if request.method == "POST":

        nombre_cliente = request.form.get('cliente', '').strip().upper()
        codigo = request.form.get('producto')
        cantidad = int(request.form.get('cantidad', 1))
        fecha_str = request.form.get('fecha')

        if not nombre_cliente:
            flash("Debe ingresar el nombre del cliente", "danger")
            return redirect(url_for('creditos.creditos_largo'))

        cliente_db = Cliente.query.filter_by(nombre=nombre_cliente).first()
        if not cliente_db:
            cliente_db = Cliente(nombre=nombre_cliente)
            db.session.add(cliente_db)
            db.session.flush()

        producto_db = Producto.query.filter(
            (Producto.codigo_barra == codigo) |
            (Producto.codigo == codigo)
        ).first()

        if not producto_db:
            flash("Producto no encontrado", "danger")
            return redirect(url_for('creditos.creditos_largo'))

        fecha_item = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else date.today()

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

        nuevo_item = CreditoItem(
            credito_id=credito.id,
            producto=producto_db.nombre.upper(),
            cantidad=cantidad,
            precio_unit=producto_db.valor_venta,
            total_linea=producto_db.valor_venta * cantidad,
            fecha=fecha_item
        )

        credito.total_consumido += nuevo_item.total_linea

        db.session.add(nuevo_item)
        db.session.commit()

        return redirect(url_for('creditos.creditos_largo'))

    creditos = Credito.query.filter_by(tipo='largo') \
        .order_by(Credito.fecha_inicio.desc()).all()

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
@creditos_bp.route('/registrar_abono', methods=['POST'], endpoint='registrar_abono')
@login_required
def abonar_credito():

    credito_id = request.form.get('credito_id')
    monto = float(request.form.get('monto_abono', 0))
    medio = request.form.get('medio_pago', 'Efectivo')
    fecha_pago_str = request.form.get('fecha_pago')

    credito = Credito.query.get_or_404(credito_id)
    redir = 'largo' if credito.tipo == 'largo' else 'corto'

    if monto > 0:

        fecha_pago = datetime.strptime(fecha_pago_str, '%Y-%m-%d').date() if fecha_pago_str else date.today()

        nuevo_abono = AbonoCredito(
            credito_id=credito.id,
            monto=monto,
            medio_pago=medio,
            fecha=fecha_pago
        )

        db.session.add(nuevo_abono)

        credito.abonado += monto
        credito.fecha_ultimo_abono = fecha_pago

        nueva_venta = Venta(
            fecha=datetime.now(),
            total=monto,
            usuario_id=current_user.id,
            tipo_pago=medio,
            detalle_pago=f"ABONO CRÉDITO - CLIENTE: {credito.cliente}"
        )

        db.session.add(nueva_venta)
        db.session.flush()

        detalle = VentaDetalle(
            venta_id=nueva_venta.id,
            producto_id=None,
            cantidad=1,
            precio_unitario=monto,
            subtotal=monto
        )

        db.session.add(detalle)

        if (credito.total_consumido - credito.abonado) <= 0:
            credito.estado = 'cerrado'
            credito.fecha_cierre = date.today()
            flash(f"Cuenta de {credito.cliente} SALDADA.", "success")
        else:
            flash(f"Abono de ${monto:,.0f} registrado.", "success")

        db.session.commit()

    return redirect(url_for(f'creditos.creditos_{redir}'))


# --------------------------------------------------
# ELIMINAR
# --------------------------------------------------
@creditos_bp.route('/eliminar/<int:credito_id>', methods=['POST'])
@login_required
def eliminar_credito(credito_id):

    credito = Credito.query.get_or_404(credito_id)
    tipo = credito.tipo

    CreditoItem.query.filter_by(credito_id=credito.id).delete()
    AbonoCredito.query.filter_by(credito_id=credito.id).delete()

    db.session.delete(credito)
    db.session.commit()

    flash("Registro eliminado.", "danger")

    return redirect(
        url_for('creditos.creditos_largo'
                if tipo == 'largo'
                else 'creditos.creditos_corto')
    )


# --------------------------------------------------
# EDITAR
# --------------------------------------------------
@creditos_bp.route('/editar/<int:credito_id>', methods=['GET', 'POST'])
@login_required
def editar_credito(credito_id):

    credito = Credito.query.get_or_404(credito_id)

    if request.method == "POST":

        nuevo_nombre = request.form.get("cliente", "").strip().upper()

        if not nuevo_nombre:
            flash("Nombre inválido", "danger")
            return redirect(request.url)

        credito.cliente = nuevo_nombre
        db.session.commit()

        flash("Datos actualizados.", "success")

        return redirect(
            url_for('creditos.creditos_largo'
                    if credito.tipo == 'largo'
                    else 'creditos.creditos_corto')
        )

    return render_template("editar_credito.html", credito=credito)
# --------------------------------------------------
# EDITAR ITEM DE CREDITO
# --------------------------------------------------
@creditos_bp.route('/editar_item/<int:item_id>', methods=['POST'])
@login_required
def editar_item_credito(item_id):

    item = CreditoItem.query.get_or_404(item_id)
    credito = Credito.query.get(item.credito_id)

    codigo = request.form.get("producto")
    cantidad = int(request.form.get("cantidad", 1))

    producto_db = Producto.query.filter(
        (Producto.codigo_barra == codigo) |
        (Producto.codigo == codigo)
    ).first()

    if not producto_db:
        flash("Producto no encontrado", "danger")
        return redirect(request.referrer)

    # 🔁 Ajustar total crédito
    credito.total_consumido -= item.total_linea

    item.producto = producto_db.nombre.upper()
    item.cantidad = cantidad
    item.precio_unit = producto_db.valor_venta
    item.total_linea = cantidad * producto_db.valor_venta

    credito.total_consumido += item.total_linea

    db.session.commit()

    flash("Producto actualizado correctamente", "success")
    return redirect(request.referrer)

