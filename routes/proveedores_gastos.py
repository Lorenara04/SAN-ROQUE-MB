from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import date, datetime
import pandas as pd
from io import BytesIO
import os
from werkzeug.utils import secure_filename

from database import db
from models import Factura, Abono, Gasto

# ======================================================
# Blueprint: Proveedores y Gastos
# ======================================================
proveedores_gastos_bp = Blueprint(
    'proveedores_gastos',
    __name__,
    url_prefix='/proveedores'
)

# Configuración de subida de archivos
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def guardar_soporte(file, folder_name):
    """Función auxiliar para guardar la imagen físicamente"""
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
        upload_path = os.path.join(current_app.root_path, 'static/uploads', folder_name)
        
        if not os.path.exists(upload_path):
            os.makedirs(upload_path)
            
        file.save(os.path.join(upload_path, filename))
        return filename
    return None

# ======================================================
# GESTIÓN DE FACTURAS DE PROVEEDORES
# ======================================================
@proveedores_gastos_bp.route('/', methods=['GET', 'POST'])
@login_required
def enlista_proveedores():
    if current_user.rol.lower() != "administrador":
        flash("Permiso denegado.", "danger")
        return redirect(url_for('ventas.dashboard'))

    if request.method == "POST":
        try:
            fecha_str = request.form.get("fecha")
            fecha_final = datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else date.today()

            # Procesar la imagen de la factura
            file = request.files.get('soporte_foto')
            nombre_archivo = guardar_soporte(file, 'facturas_proveedores')

            nueva_f = Factura(
                numero=request.form.get("numero"),
                proveedor=request.form.get("proveedor").upper(),
                total=float(request.form.get("total", 0)),
                fecha=fecha_final,
                soporte_foto=nombre_archivo # Guardamos el nombre en la DB
            )
            db.session.add(nueva_f)
            db.session.commit()
            flash("✅ Factura de proveedor registrada con éxito.", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error al registrar factura: {e}", "danger")

        return redirect(url_for('proveedores_gastos.enlista_proveedores'))

    facturas_db = Factura.query.order_by(Factura.fecha.desc()).all()
    todos_los_abonos = Abono.query.filter(Abono.factura_id.isnot(None)).order_by(Abono.fecha.asc()).all()
    
    for f in facturas_db:
        f.abonado = db.session.query(func.sum(Abono.monto)).filter(Abono.factura_id == f.id).scalar() or 0
        f.saldo = f.total - f.abonado
        f.fecha_factura = f.fecha.strftime('%Y-%m-%d') if f.fecha else ""
        f.lista_abonos = [a for a in todos_los_abonos if a.factura_id == f.id]

    return render_template("proveedores.html", 
                           facturas=facturas_db, 
                           abonos=todos_los_abonos, 
                           productos_paginados=[], 
                           hoy=date.today().strftime('%Y-%m-%d'))

# ======================================================
# EDITAR FACTURA (MODAL)
# ======================================================
@proveedores_gastos_bp.route('/factura/editar/<int:factura_id>', methods=['POST'])
@login_required
def editar_factura(factura_id):
    if current_user.rol.lower() != "administrador":
        flash("No tienes permisos para editar.", "danger")
        return redirect(url_for('proveedores_gastos.enlista_proveedores'))

    factura = Factura.query.get_or_404(factura_id)
    try:
        factura.numero = request.form.get("numero")
        factura.proveedor = request.form.get("proveedor").upper()
        factura.total = float(request.form.get("total", 0))
        
        # Si suben una nueva foto al editar, reemplazar la anterior
        file = request.files.get('soporte_foto')
        if file and file.filename != '':
            nuevo_nombre = guardar_soporte(file, 'facturas_proveedores')
            factura.soporte_foto = nuevo_nombre

        fecha_str = request.form.get("fecha")
        if fecha_str:
            factura.fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()

        db.session.commit()
        flash("✅ Factura actualizada correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al actualizar factura: {e}", "danger")

    return redirect(url_for('proveedores_gastos.enlista_proveedores'))

# ======================================================
# ELIMINAR FACTURA
# ======================================================
@proveedores_gastos_bp.route('/eliminar_factura/<int:factura_id>', methods=['POST', 'GET'])
@login_required
def eliminar_factura(factura_id):
    if current_user.rol.lower() != "administrador":
        flash("No tienes permiso para eliminar.", "danger")
        return redirect(url_for('proveedores_gastos.enlista_proveedores'))

    factura = Factura.query.get_or_404(factura_id)
    try:
        # Opcional: Eliminar el archivo físico del servidor
        if factura.soporte_foto:
            ruta_archivo = os.path.join(current_app.root_path, 'static/uploads/facturas_proveedores', factura.soporte_foto)
            if os.path.exists(ruta_archivo):
                os.remove(ruta_archivo)

        Abono.query.filter_by(factura_id=factura_id).delete()
        db.session.delete(factura)
        db.session.commit()
        flash("🗑️ Factura eliminada.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al eliminar: {e}", "danger")

    return redirect(url_for('proveedores_gastos.enlista_proveedores'))

# ======================================================
# GESTIÓN DE GASTOS OPERATIVOS
# ======================================================
@proveedores_gastos_bp.route('/gastos', methods=['GET', 'POST'])
@login_required
def gastos():
    if request.method == "POST":
        try:
            fecha_str = request.form.get("fecha")
            fecha_final = datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else date.today()
            
            # Procesar imagen para gastos generales
            file = request.files.get('soporte_foto')
            nombre_archivo = guardar_soporte(file, 'gastos_operativos')

            nuevo_g = Gasto(
                categoria=request.form.get("categoria"),
                concepto=request.form.get("concepto"),
                total=float(request.form.get("total", 0)),
                fecha=fecha_final,
                soporte_foto=nombre_archivo
            )
            db.session.add(nuevo_g)
            db.session.commit()
            flash("✅ Gasto registrado.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error: {e}", "danger")
        return redirect(url_for('proveedores_gastos.gastos'))

    gastos_list = Gasto.query.order_by(Gasto.fecha.desc()).all()
    abonos_gastos_db = Abono.query.filter(Abono.gasto_id.isnot(None)).order_by(Abono.fecha.asc()).all()

    for g in gastos_list:
        g.abonado = db.session.query(func.sum(Abono.monto)).filter(Abono.gasto_id == g.id).scalar() or 0
        g.saldo = g.total - g.abonado
        g.lista_abonos = [a for a in abonos_gastos_db if a.gasto_id == g.id]
        
    return render_template("modulo_gastos.html", 
                           gastos=gastos_list, 
                           abonos=abonos_gastos_db,
                           hoy=date.today().strftime('%Y-%m-%d'))

# ======================================================
# EDITAR GASTO
# ======================================================
@proveedores_gastos_bp.route('/gasto/editar/<int:gasto_id>', methods=['POST'])
@login_required
def editar_gasto(gasto_id):
    gasto = Gasto.query.get_or_404(gasto_id)
    try:
        gasto.categoria = request.form.get("categoria")
        gasto.concepto = request.form.get("concepto")
        gasto.total = float(request.form.get("total", 0))
        
        file = request.files.get('soporte_foto')
        if file and file.filename != '':
            gasto.soporte_foto = guardar_soporte(file, 'gastos_operativos')

        fecha_str = request.form.get("fecha")
        if fecha_str:
            gasto.fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()

        db.session.commit()
        flash("✅ Gasto actualizado correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al editar: {e}", "danger")
    return redirect(url_for('proveedores_gastos.gastos'))

# ======================================================
# ELIMINAR GASTO
# ======================================================
@proveedores_gastos_bp.route('/eliminar_gasto/<int:gasto_id>', methods=['POST', 'GET'])
@login_required
def eliminar_gasto(gasto_id):
    gasto = Gasto.query.get_or_404(gasto_id)
    try:
        if gasto.soporte_foto:
            ruta_archivo = os.path.join(current_app.root_path, 'static/uploads/gastos_operativos', gasto.soporte_foto)
            if os.path.exists(ruta_archivo):
                os.remove(ruta_archivo)

        Abono.query.filter_by(gasto_id=gasto_id).delete()
        db.session.delete(gasto)
        db.session.commit()
        flash("🗑️ Gasto eliminado.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error: {e}", "danger")
    return redirect(url_for('proveedores_gastos.gastos'))

# ======================================================
# FUNCIÓN UNIFICADA DE ABONAR (Facturas y Gastos)
# ======================================================
@proveedores_gastos_bp.route('/abonar', methods=['POST'])
@login_required
def abonar():
    try:
        monto = float(request.form.get("monto", 0))
        medio = request.form.get("medio", "Efectivo")
        factura_id = request.form.get("factura_id")
        gasto_id = request.form.get("gasto_id")
        fecha_abono_str = request.form.get("fecha_abono")

        if monto <= 0:
            flash("⚠️ El monto debe ser mayor a cero.", "warning")
            return redirect(request.referrer)

        fecha_final = datetime.strptime(fecha_abono_str, "%Y-%m-%d").date() if fecha_abono_str else date.today()

        f_id = int(factura_id) if factura_id and str(factura_id).isdigit() else None
        g_id = int(gasto_id) if gasto_id and str(gasto_id).isdigit() else None

        nuevo_abono = Abono(
            monto=monto,
            medio_pago=medio,
            fecha=fecha_final,
            factura_id=f_id,
            gasto_id=g_id
        )

        db.session.add(nuevo_abono)
        db.session.commit()
        flash(f"✅ Abono de ${monto:,.0f} registrado.", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al procesar el abono: {e}", "danger")

    return redirect(request.referrer)

# ... [Resto de funciones de abonos y exportación se mantienen igual] ...

@proveedores_gastos_bp.route('/abono/eliminar/<int:abono_id>')
@login_required
def eliminar_abono_proveedor(abono_id):
    abono = Abono.query.get_or_404(abono_id)
    try:
        db.session.delete(abono)
        db.session.commit()
        flash("🗑️ Abono eliminado correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al eliminar abono: {e}", "danger")
    return redirect(request.referrer)

@proveedores_gastos_bp.route('/abono/editar/<int:abono_id>', methods=['POST'])
@login_required
def editar_abono_proveedor(abono_id):
    abono = Abono.query.get_or_404(abono_id)
    try:
        abono.monto = float(request.form.get("monto", 0))
        nueva_fecha = request.form.get("fecha_abono")
        nuevo_medio = request.form.get("medio")
        
        if nuevo_medio:
            abono.medio_pago = nuevo_medio
        if nueva_fecha:
            abono.fecha = datetime.strptime(nueva_fecha, "%Y-%m-%d").date()
            
        db.session.commit()
        flash("✅ Abono actualizado con éxito.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al actualizar abono: {e}", "danger")
        
    return redirect(request.referrer)

@proveedores_gastos_bp.route('/exportar_proveedores')
@login_required
def exportar_proveedores():
    facturas = Factura.query.all()
    data = []
    for f in facturas:
        abonado = db.session.query(func.sum(Abono.monto)).filter(Abono.factura_id == f.id).scalar() or 0
        data.append({
            "Fecha": f.fecha,
            "Factura": f.numero,
            "Proveedor": f.proveedor,
            "Total": f.total,
            "Abonado": abonado,
            "Saldo": f.total - abonado
        })

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Proveedores')
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=f"reporte_proveedores_{date.today()}.xlsx",
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )