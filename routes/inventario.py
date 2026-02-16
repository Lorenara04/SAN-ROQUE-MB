from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
import barcode
from barcode.writer import ImageWriter
import io
import pandas as pd
from datetime import datetime

from database import db
from models import Producto, MovimientoStock, Mesa, MesaItem

inventario_bp = Blueprint('inventario', __name__)

# =========================================================
# API DE BÚSQUEDA GLOBAL
# =========================================================
@inventario_bp.route('/api/productos/buscar')
@login_required
def api_buscar_productos():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    
    # Búsqueda optimizada por nombre, código o marca
    productos = Producto.query.filter(
        (Producto.nombre.ilike(f'%{query}%')) | 
        (Producto.codigo.ilike(f'%{query}%')) |
        (Producto.marca.ilike(f'%{query}%'))
    ).limit(20).all() # Limitamos resultados para mejorar velocidad
    
    return jsonify([{
        'id': p.id,
        'codigo': p.codigo,
        'nombre': (p.nombre or "SIN NOMBRE").upper(),
        'stock': p.cantidad,
        'precio': p.valor_venta,
        'marca': (p.marca or "S.M").upper(),
        'valor_interno': p.valor_interno
    } for p in productos])

# =========================================================
# API PARA ESTADO DE MESAS
# =========================================================
@inventario_bp.route('/api/mesas/estado')
@login_required
def api_estado_mesas():
    mesas_ocupadas = Mesa.query.filter_by(estado='ocupada').all()
    return jsonify([{
        'id': m.id,
        'total': m.total_cuenta or 0,
        'items': len(m.items) if m.items else 0
    } for m in mesas_ocupadas])

# =========================================================
# LISTADO PRINCIPAL CON PAGINACIÓN
# =========================================================
@inventario_bp.route('/inventario')
@login_required
def inventario():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()
    
    query = Producto.query.order_by(Producto.id.desc())
    
    if search_query:
        query = query.filter(
            (Producto.nombre.ilike(f'%{search_query}%')) | 
            (Producto.codigo.ilike(f'%{search_query}%')) |
            (Producto.marca.ilike(f'%{search_query}%'))
        )
    
    productos_paginados = query.paginate(page=page, per_page=15, error_out=False) 
    historial = MovimientoStock.query.order_by(MovimientoStock.fecha.desc()).limit(15).all()
    
    return render_template('productos.html', 
                           productos_paginados=productos_paginados, 
                           historial=historial, 
                           search_query=search_query)

# =========================================================
# GESTIÓN DE PRODUCTOS
# =========================================================
@inventario_bp.route('/inventario/crear_producto', methods=['POST'])
@login_required
def crear_producto():
    if current_user.rol.lower() != 'administrador':
        flash('❌ Acceso denegado. Se requieren permisos de administrador.', 'danger')
        return redirect(url_for('inventario.inventario'))

    try:
        codigo = request.form.get('codigo', '').strip() or None
        
        if codigo and Producto.query.filter_by(codigo=codigo).first():
            flash(f'❌ El código "{codigo}" ya está registrado.', 'danger')
            return redirect(url_for('inventario.inventario'))

        producto = Producto(
            codigo=codigo,
            nombre=(request.form.get('nombre') or '').strip().upper(),
            marca=(request.form.get('marca') or 'S.M').strip().upper(),
            cantidad=int(request.form.get('cantidad') or 0),
            valor_venta=float(request.form.get('valor_venta') or 0),
            valor_interno=float(request.form.get('valor_interno') or 0)
        )
        db.session.add(producto)
        db.session.flush()

        # Autogenerar código si no se provee
        if not producto.codigo:
            producto.codigo = str(producto.id).zfill(8)

        mov = MovimientoStock(
            producto_id=producto.id, 
            cantidad=producto.cantidad, 
            tipo='CREACIÓN', 
            usuario=current_user.username
        )
        db.session.add(mov)
        db.session.commit()
        flash(f'✅ "{producto.nombre}" registrado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al crear producto: {str(e)}', 'danger')
    return redirect(url_for('inventario.inventario'))

@inventario_bp.route('/inventario/editar/<int:producto_id>', methods=['POST'])
@login_required
def editar_producto(producto_id):
    if current_user.rol.lower() != 'administrador':
        flash('❌ No tienes permisos para editar.', 'danger')
        return redirect(url_for('inventario.inventario'))
        
    producto = Producto.query.get_or_404(producto_id)
    try:
        producto.nombre = (request.form.get('nombre') or '').strip().upper()
        producto.marca = (request.form.get('marca') or 'S.M').strip().upper()
        producto.codigo = (request.form.get('codigo') or '').strip()
        producto.valor_interno = float(request.form.get('valor_interno') or 0)
        producto.valor_venta = float(request.form.get('valor_venta') or 0)
        producto.cantidad = int(request.form.get('cantidad') or 0)
        
        db.session.commit()
        flash(f'✅ Producto "{producto.nombre}" actualizado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al editar: {str(e)}', 'danger')
    return redirect(url_for('inventario.inventario'))

@inventario_bp.route('/inventario/eliminar/<int:producto_id>', methods=['POST', 'GET'])
@login_required
def eliminar_producto(producto_id):
    if current_user.rol.lower() != 'administrador':
        flash('❌ Acceso denegado.', 'danger')
        return redirect(url_for('inventario.inventario'))
        
    producto = Producto.query.get_or_404(producto_id)
    try:
        # Borrar historial y dependencias para evitar errores de clave foránea
        MovimientoStock.query.filter_by(producto_id=producto_id).delete()
        MesaItem.query.filter_by(producto_id=producto_id).delete()
        
        db.session.delete(producto)
        db.session.commit()
        flash(f'🗑️ Producto "{producto.nombre}" eliminado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al eliminar (el producto tiene ventas registradas): {str(e)}', 'danger')
    return redirect(url_for('inventario.inventario'))

# =========================================================
# AJUSTE DE STOCK Y EXPORTACIÓN
# =========================================================
@inventario_bp.route('/inventario/ajustar_stock/<int:producto_id>', methods=['POST'])
@login_required
def ajustar_stock(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    try:
        cantidad_a_sumar = int(request.form.get('cantidad_sumar') or 0)
        producto.cantidad += cantidad_a_sumar
        
        mov = MovimientoStock(
            producto_id=producto.id, 
            cantidad=cantidad_a_sumar, 
            tipo='AJUSTE', 
            usuario=current_user.username
        )
        db.session.add(mov)
        db.session.commit()
        flash(f'✅ Stock de {producto.nombre} actualizado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error en ajuste: {str(e)}', 'danger')
    return redirect(url_for('inventario.inventario'))

@inventario_bp.route('/inventario/exportar')
@login_required
def exportar_excel():
    if current_user.rol.lower() != 'administrador':
        flash('❌ No tienes permisos de administrador.', 'danger')
        return redirect(url_for('inventario.inventario'))

    try:
        productos = Producto.query.all()
        data = []
        for p in productos:
            costo = p.valor_interno or 0
            venta = p.valor_venta or 0
            data.append({
                'Código': p.codigo,
                'Nombre': p.nombre,
                'Marca': p.marca,
                'Stock': p.cantidad,
                'Costo': costo,
                'Venta': venta,
                'Utilidad x Unidad': venta - costo,
                'Inversión Total': p.cantidad * costo
            })
        
        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Inventario')
        output.seek(0)
        
        fecha = datetime.now().strftime("%Y-%m-%d")
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
                         as_attachment=True, download_name=f'Inventario_MB_{fecha}.xlsx')
    except Exception as e:
        flash(f'❌ Error al generar Excel: {str(e)}', 'danger')
        return redirect(url_for('inventario.inventario'))

# =========================================================
# GENERACIÓN DE CÓDIGO DE BARRAS
# =========================================================
@inventario_bp.route('/generar_codigo/<codigo>')
@login_required
def generar_codigo(codigo):
    try:
        if not codigo or str(codigo).lower() == 'none':
            return "Código no válido", 400
            
        CODIGO_B = barcode.get_barcode_class('code128')
        buffer = io.BytesIO()
        instancia = CODIGO_B(str(codigo), writer=ImageWriter())
        instancia.write(buffer, options={'module_height': 18.0, 'font_size': 10, 'text_distance': 4.0})
        buffer.seek(0)
        return send_file(buffer, mimetype='image/png')
    except Exception as e:
        return f"Error: {str(e)}", 500