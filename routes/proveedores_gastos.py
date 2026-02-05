from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app, abort
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
# BLUEPRINT
# ======================================================

proveedores_gastos_bp = Blueprint(
    'proveedores_gastos',
    __name__,
    url_prefix='/proveedores'
)

# ======================================================
# CONFIG SUBIDA ARCHIVOS
# ======================================================

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def guardar_soporte(file, carpeta):
    if file and file.filename != '' and allowed_file(file.filename):
        extension = file.filename.rsplit('.', 1)[1].lower()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = secure_filename(f"soporte_{timestamp}.{extension}")

        upload_path = os.path.join(
            current_app.root_path,
            'static',
            'uploads',
            carpeta
        )

        os.makedirs(upload_path, exist_ok=True)
        file.save(os.path.join(upload_path, filename))
        return filename

    return None

# ======================================================
# VER SOPORTE FACTURA (VISOR)
# ======================================================

@proveedores_gastos_bp.route('/factura/soporte/<int:factura_id>')
@login_required
def ver_soporte_factura(factura_id):

    factura = Factura.query.get_or_404(factura_id)

    if not factura.soporte_foto:
        abort(404)

    ruta = os.path.join(
        current_app.root_path,
        'static/uploads/facturas_proveedores',
        factura.soporte_foto
    )

    if not os.path.exists(ruta):
        abort(404)

    return send_file(ruta)

# ======================================================
# DESCARGAR SOPORTE
# ======================================================

@proveedores_gastos_bp.route('/factura/descargar/<int:factura_id>')
@login_required
def descargar_soporte_factura(factura_id):

    factura = Factura.query.get_or_404(factura_id)

    if not factura.soporte_foto:
        abort(404)

    ruta = os.path.join(
        current_app.root_path,
        'static/uploads/facturas_proveedores',
        factura.soporte_foto
    )

    if not os.path.exists(ruta):
        abort(404)

    return send_file(
        ruta,
        as_attachment=True,
        download_name=factura.soporte_foto
    )

# ======================================================
# FACTURAS PROVEEDORES
# ======================================================

@proveedores_gastos_bp.route('/', methods=['GET', 'POST'])
@login_required
def enlista_proveedores():

    if current_user.rol.lower() not in ["administrador", "administradora"]:
        flash("Permiso denegado.", "danger")
        return redirect(url_for('ventas.dashboard'))

    # ---------- REGISTRAR FACTURA ----------
    if request.method == "POST":
        try:
            fecha_str = request.form.get("fecha")
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else date.today()

            file = request.files.get("soporte_foto")
            nombre_archivo = guardar_soporte(file, "facturas_proveedores")

            nueva = Factura(
                numero=request.form.get("numero"),
                proveedor=request.form.get("proveedor").upper(),
                total=float(request.form.get("total", 0)),
                fecha=fecha,
                soporte_foto=nombre_archivo
            )

            db.session.add(nueva)
            db.session.commit()
            flash("✅ Factura registrada correctamente", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error: {str(e)}", "danger")

        return redirect(url_for('proveedores_gastos.enlista_proveedores'))

    # ---------- LISTAR ----------
    facturas = Factura.query.order_by(Factura.fecha.desc()).all()

    for f in facturas:
        f.abonado = db.session.query(func.sum(Abono.monto)).filter(
            Abono.factura_id == f.id
        ).scalar() or 0

        f.saldo = f.total - f.abonado
        f.lista_abonos = Abono.query.filter_by(factura_id=f.id).all()
        f.fecha_txt = f.fecha.strftime('%Y-%m-%d')

    return render_template(
        "proveedores.html",
        facturas=facturas,
        hoy=date.today().strftime('%Y-%m-%d')
    )

# ======================================================
# EDITAR FACTURA
# ======================================================

@proveedores_gastos_bp.route('/factura/editar/<int:factura_id>', methods=['POST'])
@login_required
def editar_factura(factura_id):

    factura = Factura.query.get_or_404(factura_id)

    try:
        factura.numero = request.form.get("numero")
        factura.proveedor = request.form.get("proveedor").upper()
        factura.total = float(request.form.get("total", 0))

        fecha_str = request.form.get("fecha")
        if fecha_str:
            factura.fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()

        file = request.files.get("soporte_foto")

        if file and file.filename != "":
            if factura.soporte_foto:
                ruta_vieja = os.path.join(
                    current_app.root_path,
                    'static/uploads/facturas_proveedores',
                    factura.soporte_foto
                )
                if os.path.exists(ruta_vieja):
                    os.remove(ruta_vieja)

            factura.soporte_foto = guardar_soporte(file, "facturas_proveedores")

        db.session.commit()
        flash("✅ Factura actualizada", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error: {str(e)}", "danger")

    return redirect(url_for('proveedores_gastos.enlista_proveedores'))

# ======================================================
# ELIMINAR FACTURA
# ======================================================

@proveedores_gastos_bp.route('/eliminar_factura/<int:factura_id>')
@login_required
def eliminar_factura(factura_id):

    factura = Factura.query.get_or_404(factura_id)

    try:
        if factura.soporte_foto:
            ruta = os.path.join(
                current_app.root_path,
                'static/uploads/facturas_proveedores',
                factura.soporte_foto
            )
            if os.path.exists(ruta):
                os.remove(ruta)

        Abono.query.filter_by(factura_id=factura_id).delete()
        db.session.delete(factura)
        db.session.commit()
        flash("🗑️ Factura eliminada", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error: {str(e)}", "danger")

    return redirect(url_for('proveedores_gastos.enlista_proveedores'))

# ======================================================
# GASTOS
# ======================================================

@proveedores_gastos_bp.route('/gastos', methods=['GET', 'POST'])
@login_required
def gastos():

    if request.method == "POST":
        try:
            fecha_str = request.form.get("fecha")
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else date.today()

            file = request.files.get("soporte_foto")
            nombre_archivo = guardar_soporte(file, "gastos")

            nuevo = Gasto(
                categoria=request.form.get("categoria"),
                concepto=request.form.get("concepto"),
                total=float(request.form.get("total", 0)),
                fecha=fecha,
                soporte_foto=nombre_archivo
            )

            db.session.add(nuevo)
            db.session.commit()
            flash("✅ Gasto registrado", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error: {str(e)}", "danger")

        return redirect(url_for('proveedores_gastos.gastos'))

    gastos = Gasto.query.order_by(Gasto.fecha.desc()).all()

    for g in gastos:
        g.abonado = db.session.query(func.sum(Abono.monto)).filter(
            Abono.gasto_id == g.id
        ).scalar() or 0

        g.saldo = g.total - g.abonado
        g.lista_abonos = Abono.query.filter_by(gasto_id=g.id).all()

    return render_template(
        "modulo_gastos.html",
        gastos=gastos,
        hoy=date.today().strftime('%Y-%m-%d')
    )

# ======================================================
# ABONAR
# ======================================================

@proveedores_gastos_bp.route('/abonar', methods=['POST'])
@login_required
def abonar():

    try:
        nuevo = Abono(
            monto=float(request.form.get("monto", 0)),
            medio_pago=request.form.get("medio"),
            fecha=datetime.strptime(
                request.form.get("fecha_abono"),
                "%Y-%m-%d"
            ).date(),
            factura_id=request.form.get("factura_id") or None,
            gasto_id=request.form.get("gasto_id") or None
        )

        db.session.add(nuevo)
        db.session.commit()
        flash("✅ Abono registrado", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error: {str(e)}", "danger")

    return redirect(request.referrer)

# ======================================================
# ELIMINAR ABONO
# ======================================================

@proveedores_gastos_bp.route('/abono/eliminar/<int:abono_id>')
@login_required
def eliminar_abono_proveedor(abono_id):

    abono = Abono.query.get_or_404(abono_id)
    db.session.delete(abono)
    db.session.commit()
    flash("🗑️ Abono eliminado", "success")

    return redirect(request.referrer)

# ======================================================
# EXPORTAR EXCEL
# ======================================================

@proveedores_gastos_bp.route('/exportar_proveedores')
@login_required
def exportar_proveedores():

    facturas = Factura.query.all()
    data = []

    for f in facturas:
        abonado = db.session.query(func.sum(Abono.monto)).filter(
            Abono.factura_id == f.id
        ).scalar() or 0

        data.append({
            "Fecha": f.fecha,
            "Factura": f.numero,
            "Proveedor": f.proveedor,
            "Total": f.total,
            "Saldo": f.total - abonado
        })

    df = pd.DataFrame(data)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    output.seek(0)

    return send_file(
        output,
        download_name=f"proveedores_{date.today()}.xlsx",
        as_attachment=True
    )
