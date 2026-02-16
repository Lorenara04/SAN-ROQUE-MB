from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import date, datetime
import pandas as pd
from io import BytesIO
import os
import json
from werkzeug.utils import secure_filename

from database import db
from models import Factura, Abono, Gasto

# ======================================================
# BLUEPRINT
# ======================================================
proveedores_gastos_bp = Blueprint(
    "proveedores_gastos",
    __name__,
    url_prefix="/proveedores"
)

# ======================================================
# CONFIGURACIÓN DE ARCHIVOS (SOPORTES)
# ======================================================
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf", "webp"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def guardar_soporte(file, carpeta):
    if file and file.filename != "" and allowed_file(file.filename):
        ext = file.filename.rsplit(".", 1)[1].lower()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = secure_filename(f"soporte_{timestamp}.{ext}")

        ruta = os.path.join(current_app.root_path, "static", "uploads", carpeta)
        os.makedirs(ruta, exist_ok=True)
        file.save(os.path.join(ruta, filename))
        return filename
    return None

# ======================================================
# ===================== FACTURAS =======================
# ======================================================

@proveedores_gastos_bp.route("/", methods=["GET", "POST"])
@login_required
def enlista_proveedores():
    if current_user.rol.lower() not in ["administrador", "administradora"]:
        flash("Permiso denegado. Se requiere rol de administrador.", "danger")
        return redirect(url_for("ventas.dashboard"))

    if request.method == "POST":
        try:
            fecha_str = request.form.get("fecha")
            fecha_dt = datetime.strptime(fecha_str, "%Y-%m-%d") if fecha_str else datetime.now()

            archivo = request.files.get("soporte_foto")
            soporte = guardar_soporte(archivo, "facturas_proveedores")

            nueva = Factura(
                numero=request.form.get("numero"),
                proveedor=(request.form.get("proveedor") or "").strip().upper(),
                total=float(request.form.get("total") or 0),
                fecha=fecha_dt,
                soporte_foto=soporte
            )

            db.session.add(nueva)
            db.session.commit()
            flash("✅ Factura registrada correctamente.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error: {str(e)}", "danger")
        return redirect(url_for("proveedores_gastos.enlista_proveedores"))

    facturas = Factura.query.order_by(Factura.fecha.desc()).all()
    for f in facturas:
        f.abonado = db.session.query(func.sum(Abono.monto)).filter(Abono.factura_id == f.id).scalar() or 0
        f.saldo = f.total - f.abonado
        f.lista_abonos = Abono.query.filter_by(factura_id=f.id).all()

    return render_template(
        "proveedores.html",
        facturas=facturas,
        hoy=date.today().strftime("%Y-%m-%d")
    )

@proveedores_gastos_bp.route("/factura/editar/<int:factura_id>", methods=["POST"])
@login_required
def editar_factura(factura_id):
    factura = Factura.query.get_or_404(factura_id)
    try:
        factura.numero = request.form.get("numero")
        factura.proveedor = (request.form.get("proveedor") or "").strip().upper()
        factura.total = float(request.form.get("total") or 0)
        
        fecha_str = request.form.get("fecha")
        if fecha_str:
            factura.fecha = datetime.strptime(fecha_str, "%Y-%m-%d")

        archivo = request.files.get("soporte_foto")
        if archivo and archivo.filename != "":
            factura.soporte_foto = guardar_soporte(archivo, "facturas_proveedores")

        db.session.commit()
        flash("✅ Factura actualizada correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error: {str(e)}", "danger")
    return redirect(url_for("proveedores_gastos.enlista_proveedores"))

@proveedores_gastos_bp.route("/eliminar_factura/<int:factura_id>", methods=["POST"])
@login_required
def eliminar_factura(factura_id):
    factura = Factura.query.get_or_404(factura_id)
    try:
        Abono.query.filter_by(factura_id=factura_id).delete()
        db.session.delete(factura)
        db.session.commit()
        flash("🗑️ Factura eliminada correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error: {str(e)}", "danger")
    return redirect(url_for("proveedores_gastos.enlista_proveedores"))

# ======================================================
# ====================== ABONOS ========================
# ======================================================

@proveedores_gastos_bp.route("/abonar", methods=["POST"])
@login_required
def abonar():
    try:
        monto = float(request.form.get("monto") or 0)
        fecha_str = request.form.get("fecha_abono")
        fecha_dt = datetime.strptime(fecha_str, "%Y-%m-%d") if fecha_str else datetime.now()

        nuevo = Abono(
            monto=monto,
            medio_pago=request.form.get("medio"),
            fecha=fecha_dt,
            factura_id=request.form.get("factura_id") if request.form.get("factura_id") else None,
            gasto_id=request.form.get("gasto_id") if request.form.get("gasto_id") else None
        )

        db.session.add(nuevo)
        db.session.commit()
        flash("✅ Abono registrado correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al abonar: {str(e)}", "danger")
    return redirect(request.referrer)

@proveedores_gastos_bp.route("/abono/eliminar/<int:abono_id>", methods=["POST"])
@login_required
def eliminar_abono_proveedor(abono_id):
    abono = Abono.query.get_or_404(abono_id)
    try:
        db.session.delete(abono)
        db.session.commit()
        flash("🗑️ Abono eliminado correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error: {str(e)}", "danger")
    return redirect(request.referrer)

# ======================================================
# ====================== GASTOS ========================
# ======================================================

@proveedores_gastos_bp.route("/gastos", methods=["GET", "POST"])
@login_required
def gastos():
    if request.method == "POST":
        try:
            fecha_str = request.form.get("fecha")
            fecha_dt = datetime.strptime(fecha_str, "%Y-%m-%d") if fecha_str else datetime.now()

            archivo = request.files.get("soporte_foto")
            soporte = guardar_soporte(archivo, "gastos")

            # CORREGIDO: Usamos 'concepto' para que coincida con tu modelo
            nuevo = Gasto(
                categoria=request.form.get("categoria"),
                concepto=(request.form.get("concepto") or "").strip().upper(),
                total=float(request.form.get("total") or 0),
                fecha=fecha_dt,
                soporte_foto=soporte
            )
            db.session.add(nuevo)
            db.session.commit()
            flash("✅ Gasto registrado correctamente.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error: {str(e)}", "danger")
        return redirect(url_for("proveedores_gastos.gastos"))

    gastos_query = Gasto.query.order_by(Gasto.fecha.desc()).all()
    for g in gastos_query:
        g.abonado = db.session.query(func.sum(Abono.monto)).filter(Abono.gasto_id == g.id).scalar() or 0
        g.saldo = g.total - g.abonado
        g.lista_abonos = Abono.query.filter_by(gasto_id=g.id).all()

    return render_template(
        "modulo_gastos.html",
        gastos=gastos_query,
        hoy=date.today().strftime("%Y-%m-%d")
    )

@proveedores_gastos_bp.route("/gasto/editar/<int:gasto_id>", methods=["POST"])
@login_required
def editar_gasto(gasto_id):
    gasto = Gasto.query.get_or_404(gasto_id)
    try:
        gasto.categoria = request.form.get("categoria")
        gasto.concepto = (request.form.get("concepto") or "").strip().upper()
        gasto.total = float(request.form.get("total") or 0)
        
        fecha_str = request.form.get("fecha")
        if fecha_str:
            gasto.fecha = datetime.strptime(fecha_str, "%Y-%m-%d")

        archivo = request.files.get("soporte_foto")
        if archivo and archivo.filename != "":
            gasto.soporte_foto = guardar_soporte(archivo, "gastos")

        db.session.commit()
        flash("✅ Gasto actualizado correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error: {str(e)}", "danger")
    return redirect(url_for("proveedores_gastos.gastos"))

@proveedores_gastos_bp.route("/gasto/eliminar/<int:gasto_id>", methods=["POST"])
@login_required
def eliminar_gasto(gasto_id):
    try:
        Abono.query.filter_by(gasto_id=gasto_id).delete()
        gasto = Gasto.query.get_or_404(gasto_id)
        db.session.delete(gasto)
        db.session.commit()
        flash("🗑️ Gasto eliminado correctamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error: {str(e)}", "danger")
    return redirect(url_for("proveedores_gastos.gastos"))

# ======================================================
# EXPORTAR EXCEL
# ======================================================

@proveedores_gastos_bp.route("/exportar_proveedores")
@login_required
def exportar_proveedores():
    facturas = Factura.query.all()
    data = []
    for f in facturas:
        abonado = db.session.query(func.sum(Abono.monto)).filter(Abono.factura_id == f.id).scalar() or 0
        data.append({
            "Fecha": f.fecha.strftime("%Y-%m-%d") if f.fecha else "",
            "Factura": f.numero,
            "Proveedor": f.proveedor,
            "Total": f.total,
            "Abonado": abonado,
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
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )