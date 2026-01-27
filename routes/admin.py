from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from database import db
from models import Usuario, Producto, Venta, VentaDetalle, CierreCaja, AcumuladoMensual
from sqlalchemy.exc import IntegrityError, OperationalError
import pandas as pd
from io import BytesIO
from datetime import datetime

# Definimos el Blueprint con el nombre 'admin'
admin_bp = Blueprint('admin', __name__)

# --- DECORADOR DE SEGURIDAD PARA BLUEPRINT ---
@admin_bp.before_request
@login_required
def verificar_admin():
    """Restringe todas las rutas de este blueprint solo a administradores"""
    if current_user.rol.lower() != 'administrador':
        flash('Acceso denegado. Se requieren permisos de administrador.', 'danger')
        return redirect(url_for('ventas.dashboard'))

# -------------------- GESTIÓN DE USUARIOS --------------------

@admin_bp.route('/usuarios')
def usuarios():
    """Lista todos los usuarios registrados."""
    usuarios_list = Usuario.query.all()
    return render_template('usuarios.html', usuarios=usuarios_list)

@admin_bp.route('/usuarios/agregar', methods=['POST'])
def agregar_usuario():
    """Procesa el formulario para crear un nuevo usuario."""
    username = (request.form.get('username') or '').strip()
    
    if Usuario.query.filter_by(username=username).first():
        flash(f'Error: El usuario "{username}" ya existe.', 'danger')
        return redirect(url_for('admin.usuarios'))

    try:
        nuevo_usuario = Usuario(
            username=username,
            nombre=(request.form.get('nombre') or '').strip(),
            apellido=(request.form.get('apellido') or '').strip(),
            cedula=(request.form.get('cedula') or '').strip(),
            rol=(request.form.get('rol') or 'Vendedor').strip()
        )
        nuevo_usuario.set_password(request.form.get('password') or '1234')
        
        db.session.add(nuevo_usuario)
        db.session.commit()
        flash(f'✅ Usuario {username} creado con éxito.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al crear el usuario: {str(e)}', 'danger')
        
    return redirect(url_for('admin.usuarios'))

@admin_bp.route('/usuarios/editar/<int:usuario_id>', methods=['POST'])
def editar_usuario(usuario_id):
    """Actualiza los datos de un usuario existente."""
    usuario = Usuario.query.get_or_404(usuario_id)
    
    try:
        usuario.nombre = request.form.get('nombre').strip()
        usuario.apellido = request.form.get('apellido').strip()
        usuario.cedula = request.form.get('cedula').strip()
        usuario.rol = request.form.get('rol').strip()
        
        # Si se ingresa una contraseña nueva, se actualiza
        password = request.form.get('password')
        if password and password.strip() != "":
            usuario.set_password(password.strip())
            
        db.session.commit()
        flash(f'✅ Usuario {usuario.username} actualizado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error al actualizar: {str(e)}', 'danger')
        
    return redirect(url_for('admin.usuarios'))

@admin_bp.route('/usuarios/eliminar/<int:usuario_id>', methods=['POST', 'GET'])
def eliminar_usuario(usuario_id):
    """Elimina un usuario de la base de datos."""
    if usuario_id == current_user.id:
        flash('⚠️ No puedes eliminar tu propia cuenta de administrador.', 'warning')
        return redirect(url_for('admin.usuarios'))
    
    usuario = Usuario.query.get_or_404(usuario_id)
    try:
        db.session.delete(usuario)
        db.session.commit()
        flash(f'🗑️ Usuario {usuario.username} eliminado definitivamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('❌ No se pudo eliminar (el usuario tiene registros vinculados).', 'danger')
        
    return redirect(url_for('admin.usuarios'))

# -------------------- IMPORTACIÓN / EXPORTACIÓN --------------------

@admin_bp.route('/importar')
def vista_importar():
    return render_template('importar_datos.html')

@admin_bp.route('/importar_productos', methods=['POST'])
def importar_productos_excel():
    if 'excel_file' not in request.files:
        flash('No se encontró el archivo.', 'danger')
        return redirect(url_for('admin.vista_importar'))

    file = request.files['excel_file']
    try:
        excel_data = BytesIO(file.read())
        df_productos = pd.read_excel(excel_data, sheet_name='Producto')
        for _, row in df_productos.iterrows():
            row_l = {str(k).lower(): v for k, v in row.items()}
            nuevo = Producto(
                codigo=str(row_l.get('codigo')) if pd.notna(row_l.get('codigo')) else None,
                nombre=str(row_l.get('nombre')),
                cantidad=int(row_l.get('cantidad', 0)),
                valor_venta=float(row_l.get('valor_venta', 0)),
                valor_interno=float(row_l.get('valor_interno', 0))
            )
            db.session.add(nuevo)
        db.session.commit()
        flash('✅ Productos importados.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error: {e}', 'danger')
    return redirect(url_for('inventario.inventario'))

@admin_bp.route('/exportar_productos_excel')
def exportar_productos():
    try:
        productos = Producto.query.all()
        data = [{"ID": p.id, "Código": p.codigo, "Nombre": p.nombre, "Stock": p.cantidad, "Precio": p.valor_venta} for p in productos]
        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Productos')
        output.seek(0)
        return send_file(output, as_attachment=True, download_name=f"inventario_{datetime.now().strftime('%Y%m%d')}.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        flash(f'❌ Error: {e}', 'danger')
        return redirect(url_for('inventario.inventario'))