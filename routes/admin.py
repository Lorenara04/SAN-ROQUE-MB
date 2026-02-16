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
    # Evita bucles de redirección si la ruta de destino está dentro del mismo blueprint
    if request.endpoint and 'admin.' not in request.endpoint:
        return
        
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
    
    if not username:
        flash('El nombre de usuario es obligatorio.', 'warning')
        return redirect(url_for('admin.usuarios'))

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
        usuario.nombre = (request.form.get('nombre') or '').strip()
        usuario.apellido = (request.form.get('apellido') or '').strip()
        usuario.cedula = (request.form.get('cedula') or '').strip()
        usuario.rol = (request.form.get('rol') or 'Vendedor').strip()
        
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

@admin_bp.route('/usuarios/eliminar/<int:usuario_id>', methods=['POST'])
def eliminar_usuario(usuario_id):
    """Elimina un usuario de la base de datos (Solo POST por seguridad)."""
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
        flash('❌ No se pudo eliminar (el usuario tiene registros vinculados o error de DB).', 'danger')
        
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
    if file.filename == '':
        flash('No seleccionaste ningún archivo.', 'warning')
        return redirect(url_for('admin.vista_importar'))

    try:
        excel_data = BytesIO(file.read())
        df_productos = pd.read_excel(excel_data, sheet_name='Producto')
        
        for _, row in df_productos.iterrows():
            row_l = {str(k).lower().strip(): v for k, v in row.items()}
            
            # Validación de datos nulos para evitar errores de conversión
            nuevo = Producto(
                codigo=str(row_l.get('codigo')) if pd.notna(row_l.get('codigo')) else None,
                nombre=str(row_l.get('nombre')) if pd.notna(row_l.get('nombre')) else "Sin Nombre",
                cantidad=int(row_l.get('cantidad')) if pd.notna(row_l.get('cantidad')) else 0,
                valor_venta=float(row_l.get('valor_venta')) if pd.notna(row_l.get('valor_venta')) else 0.0,
                valor_interno=float(row_l.get('valor_interno')) if pd.notna(row_l.get('valor_interno')) else 0.0
            )
            db.session.add(nuevo)
            
        db.session.commit()
        flash('✅ Productos importados correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error durante la importación: {str(e)}', 'danger')
        
    return redirect(url_for('inventario.inventario'))

@admin_bp.route('/exportar_productos_excel')
def exportar_productos():
    try:
        productos = Producto.query.all()
        data = [
            {
                "ID": p.id, 
                "Código": p.codigo, 
                "Nombre": p.nombre, 
                "Stock": p.cantidad, 
                "Precio": p.valor_venta
            } for p in productos
        ]
        
        if not data:
            flash('No hay productos para exportar.', 'info')
            return redirect(url_for('inventario.inventario'))

        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Productos')
        
        output.seek(0)
        
        nombre_archivo = f"inventario_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        
        return send_file(
            output, 
            as_attachment=True, 
            download_name=nombre_archivo, 
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        flash(f'❌ Error al exportar: {str(e)}', 'danger')
        return redirect(url_for('inventario.inventario'))