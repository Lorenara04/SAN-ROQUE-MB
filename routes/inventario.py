from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
import barcode
from barcode.writer import ImageWriter
import io
import pandas as pd
from datetime import datetime

from database import db
from models import Producto, MovimientoStock 

inventario_bp = Blueprint('inventario', __name__)

# =========================================================
# EXPORTAR A EXCEL (SEGURIDAD: SOLO ADMIN)
# =========================================================
@inventario_bp.route('/inventario/exportar')
@login_required
def exportar_excel():
    if current_user.rol.lower() != 'administrador':
        flash('No tienes permisos para descargar reportes.', 'danger')
        return redirect(url_for('inventario.inventario'))

    try:
        productos = Producto.query.all()
        data = []
        for p in productos:
            utilidad_unid = (p.valor_venta - p.valor_interno)
            data.append({
                'Código': p.codigo,
                'Nombre': p.nombre,
                'Detalle/Marca': p.marca,
                'Existencias': p.cantidad,
                'Costo Compra': p.valor_interno,
                'Precio Venta': p.valor_venta,
                'Utilidad x Unidad': utilidad_unid,
                'Inversión Total': p.cantidad * p.valor_interno,
                'Utilidad Potencial Total': utilidad_unid * p.cantidad
            })
        
        df = pd.DataFrame(data)
        output = io.BytesIO()
        # Se requiere tener instalado XlsxWriter: pip install xlsxwriter
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Inventario')
        output.seek(0)
        
        fecha = datetime.now().strftime("%Y-%m-%d")
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
                         as_attachment=True, download_name=f'Inventario_MB_{fecha}.xlsx')
    except Exception as e:
        flash(f'❌ Error al generar Excel: {e}', 'danger')
        return redirect(url_for('inventario.inventario'))

# =========================================================
# LISTADO CON PAGINACIÓN E HISTORIAL DETALLADO
# =========================================================
@inventario_bp.route('/inventario')
@login_required
def inventario():
    # Implementación de Paginación
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()
    
    query = Producto.query.order_by(Producto.id.desc())
    
    if search_query:
        query = query.filter(
            (Producto.nombre.ilike(f'%{search_query}%')) | 
            (Producto.codigo.ilike(f'%{search_query}%')) |
            (Producto.marca.ilike(f'%{search_query}%'))
        )
    
    # 15 productos por página para mantener velocidad
    productos_paginados = query.paginate(page=page, per_page=15, error_out=False)
    
    # Historial detallado para la tabla inferior (últimos 15 movimientos)
    historial = MovimientoStock.query.order_by(MovimientoStock.fecha.desc()).limit(15).all()
    
    return render_template('productos.html', 
                           productos_paginados=productos_paginados, 
                           historial=historial, 
                           search_query=search_query)

# =========================================================
# CREAR PRODUCTO (SEGURIDAD: SOLO ADMIN)
# =========================================================
@inventario_bp.route('/inventario/crear_producto', methods=['POST'])
@login_required
def crear_producto():
    if current_user.rol.lower() != 'administrador':
        flash('Acceso denegado. Solo administradores pueden crear productos.', 'danger')
        return redirect(url_for('inventario.inventario'))

    try:
        codigo = request.form.get('codigo', '').strip() or None
        
        if codigo and Producto.query.filter_by(codigo=codigo).first():
            flash('❌ Ya existe un producto con ese código.', 'danger')
            return redirect(url_for('inventario.inventario'))

        producto = Producto(
            codigo=codigo,
            nombre=request.form.get('nombre'),
            marca=request.form.get('marca'),
            cantidad=int(request.form.get('cantidad', 0)),
            valor_venta=float(request.form.get('valor_venta', 0)),
            valor_interno=float(request.form.get('valor_interno', 0))
        )
        db.session.add(producto)
        db.session.flush()

        if not producto.codigo:
            producto.codigo = str(producto.id).zfill(8)

        # Registro detallado en historial
        mov = MovimientoStock(
            producto_id=producto.id, 
            cantidad=producto.cantidad, 
            tipo='CREACIÓN', 
            usuario=current_user.username
        )
        db.session.add(mov)
        db.session.commit()
        flash(f'✅ Producto "{producto.nombre}" registrado exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al crear producto: {e}', 'danger')
    return redirect(url_for('inventario.inventario'))

# =========================================================
# RECEPCIÓN RÁPIDA (ESCÁNER)
# =========================================================
@inventario_bp.route('/inventario/agregar_producto', methods=['POST'])
@login_required
def agregar_producto():
    codigo = request.form.get('codigo_scanner', '').strip()
    cantidad = int(request.form.get('cantidad_scanner', 1))
    
    if not codigo:
        flash('❌ Debe escanear o ingresar un código.', 'warning')
        return redirect(url_for('inventario.inventario'))

    producto = Producto.query.filter_by(codigo=codigo).first()

    if not producto:
        flash('❌ Producto no encontrado.', 'danger')
        return redirect(url_for('inventario.inventario'))

    producto.cantidad += cantidad
    
    mov = MovimientoStock(
        producto_id=producto.id, 
        cantidad=cantidad, 
        tipo='ESCÁNER', 
        usuario=current_user.username
    )
    db.session.add(mov)
    db.session.commit()
    
    flash(f'📦 Stock actualizado: {producto.nombre} (+{cantidad})', 'success')
    return redirect(url_for('inventario.inventario'))

# =========================================================
# AJUSTAR STOCK (MODAL MANUAL)
# =========================================================
@inventario_bp.route('/inventario/ajustar_stock/<int:producto_id>', methods=['POST'])
@login_required
def ajustar_stock(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    try:
        cantidad_a_sumar = int(request.form.get('cantidad_sumar', 0))
        producto.cantidad += cantidad_a_sumar
        
        mov = MovimientoStock(
            producto_id=producto.id, 
            cantidad=cantidad_a_sumar, 
            tipo='AJUSTE MANUAL', 
            usuario=current_user.username
        )
        db.session.add(mov)
        db.session.commit()
        
        if cantidad_a_sumar >= 0:
            flash(f'✅ Se agregaron {cantidad_a_sumar} unidades a {producto.nombre}.', 'success')
        else:
            flash(f'📉 Se restaron {abs(cantidad_a_sumar)} unidades a {producto.nombre}.', 'warning')
            
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al ajustar stock: {e}', 'danger')
    return redirect(url_for('inventario.inventario'))

# =========================================================
# EDITAR Y ELIMINAR (SEGURIDAD: SOLO ADMIN)
# =========================================================
@inventario_bp.route('/inventario/editar/<int:producto_id>', methods=['POST'])
@login_required
def editar_producto(producto_id):
    if current_user.rol.lower() != 'administrador':
        flash('No tienes permisos para editar.', 'danger')
        return redirect(url_for('inventario.inventario'))
        
    producto = Producto.query.get_or_404(producto_id)
    try:
        producto.nombre = request.form.get('nombre')
        producto.marca = request.form.get('marca')
        producto.codigo = request.form.get('codigo', '').strip()
        producto.valor_interno = float(request.form.get('valor_interno', 0))
        producto.valor_venta = float(request.form.get('valor_venta', 0))
        producto.cantidad = int(request.form.get('cantidad', 0))
        
        db.session.commit()
        flash(f'✅ Producto actualizado exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al editar: {e}', 'danger')
    return redirect(url_for('inventario.inventario'))

@inventario_bp.route('/inventario/eliminar/<int:producto_id>')
@login_required
def eliminar_producto(producto_id):
    if current_user.rol.lower() != 'administrador':
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('inventario.inventario'))
        
    producto = Producto.query.get_or_404(producto_id)
    try:
        db.session.delete(producto)
        db.session.commit()
        flash(f'🗑️ Producto eliminado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al eliminar: {e}', 'danger')
    return redirect(url_for('inventario.inventario'))

# =========================================================
# GENERACIÓN DE CÓDIGO DE BARRAS
# =========================================================
@inventario_bp.route('/generar_codigo/<codigo>')
@login_required
def generar_codigo(codigo):
    try:
        CODIGO_B = barcode.get_barcode_class('code128')
        buffer = io.BytesIO()
        instancia = CODIGO_B(str(codigo), writer=ImageWriter())
        instancia.write(buffer, options={'module_height': 18.0, 'font_size': 10, 'text_distance': 4.0})
        buffer.seek(0)
        return send_file(buffer, mimetype='image/png')
    except Exception as e:
        return f"Error: {str(e)}", 500