from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
import barcode
from barcode.writer import ImageWriter
import io

from database import db
from models import Producto

inventario_bp = Blueprint('inventario', __name__)

# =========================================================
# GENERACIÓN DE CÓDIGO DE BARRAS (PARA DESCARGA E IMAGEN)
# =========================================================
@inventario_bp.route('/generar_codigo/<codigo>')
@login_required
def generar_codigo(codigo):
    """Genera una imagen PNG manteniendo ceros a la izquierda."""
    try:
        # Forzamos el código a string para no perder ceros
        codigo_texto = str(codigo).strip()
        CODIGO_B = barcode.get_barcode_class('code128')
        
        writer_options = {
            'module_height': 18.0,
            'font_size': 10,
            'text_distance': 4.0,
            'quiet_zone': 2.0
        }
        
        buffer = io.BytesIO()
        instancia = CODIGO_B(codigo_texto, writer=ImageWriter())
        instancia.write(buffer, options=writer_options)
        buffer.seek(0)
        
        return send_file(buffer, mimetype='image/png')
    except Exception as e:
        return f"Error al generar código: {str(e)}", 500

# =========================================================
# LISTADO DE INVENTARIO
# =========================================================
@inventario_bp.route('/inventario')
@login_required
def inventario():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    search_query = request.args.get('search', '').strip()

    query = Producto.query.order_by(Producto.id.desc())

    if search_query:
        query = query.filter(
            (Producto.nombre.ilike(f'%{search_query}%')) |
            (Producto.codigo.ilike(f'%{search_query}%')) |
            (Producto.marca.ilike(f'%{search_query}%'))
        )

    productos_paginados = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    return render_template(
        'productos.html',
        productos_paginados=productos_paginados,
        search_query=search_query
    )


# =========================================================
# CREAR PRODUCTO (MODAL "NUEVO PRODUCTO")
# =========================================================
@inventario_bp.route('/inventario/crear', methods=['POST'])
@login_required
def crear_producto():
    if current_user.rol.lower() != 'administrador':
        flash('Solo administradores pueden crear productos.', 'danger')
        return redirect(url_for('inventario.inventario'))

    try:
        # Tratamos el código siempre como String
        codigo = request.form.get('codigo', '').strip() or None

        if codigo:
            existe = Producto.query.filter_by(codigo=codigo).first()
            if existe:
                flash('❌ Ya existe un producto con ese código.', 'danger')
                return redirect(url_for('inventario.inventario'))

        cantidad_inicial = int(request.form.get('cantidad', 0))
        valor_interno = float(request.form.get('valor_interno', 0))
        valor_venta_input = request.form.get('valor_venta', '').strip()

        # Lógica automática de ganancia 35%
        if not valor_venta_input or float(valor_venta_input) == 0:
            valor_venta = round(valor_interno * 1.35)
        else:
            valor_venta = float(valor_venta_input)

        producto = Producto(
            codigo=codigo,
            nombre=request.form.get('nombre'),
            marca=request.form.get('marca'),
            descripcion=request.form.get('descripcion'),
            cantidad=cantidad_inicial,
            valor_venta=valor_venta,
            valor_interno=valor_interno,
            stock_minimo=5
        )

        db.session.add(producto)
        db.session.flush()

        # Si no se puso código, generamos uno con ceros basado en el ID
        if not producto.codigo:
            producto.codigo = str(producto.id).zfill(8)

        db.session.commit()
        flash(f'✅ Producto "{producto.nombre}" creado exitosamente.', 'success')

    except IntegrityError:
        db.session.rollback()
        flash('❌ Error de integridad: El código ya existe.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al crear producto: {e}', 'danger')

    return redirect(url_for('inventario.inventario'))


# =========================================================
# SUMAR STOCK RÁPIDO (ESCÁNER / BUSCADOR)
# =========================================================
@inventario_bp.route('/inventario/agregar', methods=['POST'])
@login_required
def agregar_producto():
    codigo = request.form.get('codigo_scanner', '').strip()
    cantidad = int(request.form.get('cantidad_scanner', 1))

    if not codigo:
        flash('❌ Código inválido.', 'danger')
        return redirect(url_for('inventario.inventario'))

    producto = Producto.query.filter(Producto.codigo == codigo).first()

    if not producto:
        flash('❌ Producto no encontrado.', 'danger')
        return redirect(url_for('inventario.inventario'))

    producto.cantidad += cantidad
    db.session.commit()

    flash(f'✅ Stock actualizado: {producto.nombre} (+{cantidad}).', 'success')
    return redirect(url_for('inventario.inventario'))


# =========================================================
# EDITAR PRODUCTO (MODAL)
# =========================================================
@inventario_bp.route('/inventario/editar/<int:producto_id>', methods=['POST'])
@login_required
def editar_producto(producto_id):
    if current_user.rol.lower() != 'administrador':
        flash('No tienes permisos para editar.', 'danger')
        return redirect(url_for('inventario.inventario'))

    producto = Producto.query.get_or_404(producto_id)

    try:
        nuevo_codigo = request.form.get('codigo', '').strip() or None

        if nuevo_codigo and nuevo_codigo != producto.codigo:
            existe = Producto.query.filter_by(codigo=nuevo_codigo).first()
            if existe:
                flash('❌ Ya existe otro producto con ese código.', 'danger')
                return redirect(url_for('inventario.inventario'))

        producto.nombre = request.form.get('nombre')
        producto.marca = request.form.get('marca')
        producto.codigo = nuevo_codigo
        producto.descripcion = request.form.get('descripcion')
        
        v_interno = float(request.form.get('valor_interno', 0))
        v_venta_input = request.form.get('valor_venta', '').strip()

        if not v_venta_input or float(v_venta_input) == 0:
            v_venta = round(v_interno * 1.35)
        else:
            v_venta = float(v_venta_input)

        producto.valor_interno = v_interno
        producto.valor_venta = v_venta
        producto.cantidad = int(request.form.get('cantidad', 0))

        db.session.commit()
        flash(f'✅ Producto "{producto.nombre}" actualizado correctamente.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al editar: {e}', 'danger')

    return redirect(url_for('inventario.inventario'))


# =========================================================
# ELIMINAR PRODUCTO
# =========================================================
@inventario_bp.route('/inventario/eliminar/<int:producto_id>')
@login_required
def eliminar_producto(producto_id):
    if current_user.rol.lower() != 'administrador':
        flash('No tienes permisos para eliminar.', 'danger')
        return redirect(url_for('inventario.inventario'))

    producto = Producto.query.get_or_404(producto_id)
    nombre_eliminado = producto.nombre
    db.session.delete(producto)
    db.session.commit()

    flash(f'🗑️ Producto "{nombre_eliminado}" eliminado.', 'success')
    return redirect(url_for('inventario.inventario'))


# =========================================================
# API BÚSQUEDA (VENTAS)
# =========================================================
@inventario_bp.route('/api/productos/buscar')
@login_required
def buscar_productos_api():
    query = request.args.get('q', '').strip()

    if not query:
        return jsonify([])

    productos = Producto.query.filter(
        (Producto.nombre.ilike(f'%{query}%')) |
        (Producto.codigo.ilike(f'{query}%'))
    ).limit(10).all()

    return jsonify([
        {
            'id': p.id,
            'nombre': p.nombre,
            'precio': p.valor_venta,
            'stock': p.cantidad
        }
        for p in productos
    ])