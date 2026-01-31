from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from database import db
from models import Venta, CierreCaja, AbonoCredito, Abono
from utils.time_utils import (
    obtener_rango_turno_colombia,
    obtener_rango_turno_por_fecha_comercial
)
from sqlalchemy import func, and_
from datetime import timedelta, datetime
from fpdf import FPDF
import json

# UTILIDAD CORREO
from utils.correo_utils import enviar_correo

reportes_bp = Blueprint("reportes", __name__)

# --------------------------------------------------
# UTILIDADES
# --------------------------------------------------

def fmt(v):
    return f"$ {float(v or 0):,.0f}".replace(",", ".")

def generar_html_reporte(f_inicio, f_fin, datos):
    return f"""
    <!DOCTYPE html>
    <html>
    <body style="background:#f4f7fa;font-family:Arial">
        <h2>SAN ROQUE M.B</h2>
        <p>Reporte {f_inicio} a {f_fin}</p>
        <h3>Saldo Neto: {fmt(datos['saldo'])}</h3>
    </body>
    </html>
    """

# --------------------------------------------------
# SEGURIDAD
# --------------------------------------------------

@reportes_bp.before_request
@login_required
def verificar_admin():
    if current_user.rol.lower() not in ["administrador", "administradora"]:
        flash("Acceso restringido.", "danger")
        return redirect(url_for("ventas.dashboard"))

# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

@reportes_bp.route("/reportes")
@login_required
def reportes():
    fecha_comercial, inicio_utc, fin_utc = obtener_rango_turno_colombia()

    def sumar_por_tipo(tipo):
        return db.session.query(func.sum(Venta.total)).filter(
            and_(
                Venta.fecha >= inicio_utc,
                Venta.fecha <= fin_utc,
                Venta.tipo_pago == tipo
            )
        ).scalar() or 0

    def sumar_por_detalle(detalle):
        return db.session.query(func.sum(Venta.total)).filter(
            and_(
                Venta.fecha >= inicio_utc,
                Venta.fecha <= fin_utc,
                Venta.detalle_pago == detalle
            )
        ).scalar() or 0

    efectivo = float(sumar_por_tipo("Efectivo"))
    nequi = float(sumar_por_detalle("Nequi"))
    daviplata = float(sumar_por_detalle("Daviplata"))
    tarjeta = float(sumar_por_detalle("Tarjeta"))

    electronico = nequi + daviplata + tarjeta

    recaudo = float(db.session.query(func.sum(AbonoCredito.monto))
        .filter(AbonoCredito.fecha == fecha_comercial)
        .scalar() or 0)

    egresos = float(db.session.query(func.sum(Abono.monto))
        .filter(Abono.fecha == fecha_comercial)
        .scalar() or 0)

    total_diario = efectivo + electronico + recaudo
    saldo = total_diario - egresos

    inicio_mes_utc, _ = obtener_rango_turno_por_fecha_comercial(
        fecha_comercial.replace(day=1)
    )

    total_mensual = db.session.query(func.sum(Venta.total)).filter(
        and_(
            Venta.fecha >= inicio_mes_utc,
            Venta.fecha <= fin_utc
        )
    ).scalar() or 0

    labels_grafico, datos_ventas = [], []

    for i in range(6, -1, -1):
        dia = fecha_comercial - timedelta(days=i)
        labels_grafico.append(dia.strftime("%d/%m"))
        i_u, f_u = obtener_rango_turno_por_fecha_comercial(dia)
        total_dia = db.session.query(func.sum(Venta.total)).filter(
            and_(Venta.fecha >= i_u, Venta.fecha <= f_u)
        ).scalar() or 0
        datos_ventas.append(float(total_dia))

    caja_cerrada = CierreCaja.query.filter_by(
        fecha_cierre=fecha_comercial
    ).first() is not None

    return render_template(
        "reportes.html",
        hoy=fecha_comercial,
        total_diario=total_diario,
        efectivo=efectivo,
        electronico=electronico,
        nequi=nequi,
        daviplata=daviplata,
        tarjeta=tarjeta,
        egresos_dia=egresos,
        saldo_caja_dia=saldo,
        total_mensual=total_mensual,
        caja_cerrada_hoy=caja_cerrada,
        labels_grafico=labels_grafico,
        datos_ventas=datos_ventas
    )

# --------------------------------------------------
# ENVIO EMAIL
# --------------------------------------------------

@reportes_bp.route("/enviar_reporte_email", methods=["POST"])
@login_required
def enviar_reporte_email():
    email = request.form.get("email")
    f_ini = request.form.get("fecha_inicio")
    f_fin = request.form.get("fecha_fin")

    inicio = datetime.strptime(f_ini, "%Y-%m-%d")
    fin = datetime.strptime(f_fin, "%Y-%m-%d") + timedelta(days=1)

    ventas = Venta.query.filter(
        Venta.fecha >= inicio,
        Venta.fecha < fin
    ).all()

    if not ventas:
        flash("No hay ventas.", "warning")
        return redirect(url_for("reportes.reportes"))

    total_p = sum(v.total for v in ventas)

    egresos = db.session.query(func.sum(Abono.monto)).filter(
        and_(Abono.fecha >= f_ini, Abono.fecha <= f_fin)
    ).scalar() or 0

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "SAN ROQUE M.B", ln=True, align="C")
    pdf.cell(0, 10, f"TOTAL INGRESOS: {fmt(total_p)}", ln=True)
    pdf.cell(0, 10, f"EGRESOS: {fmt(egresos)}", ln=True)
    pdf.cell(0, 10, f"SALDO: {fmt(total_p-egresos)}", ln=True)

    pdf_bytes = pdf.output(dest="S").encode("latin-1")

    html = generar_html_reporte(
        f_ini,
        f_fin,
        {"saldo": total_p-egresos}
    )

    enviar_correo(
        email,
        f"Reporte San Roque {f_ini}",
        html,
        [{"filename":"reporte.pdf","content":pdf_bytes}]
    )

    flash("Reporte enviado", "success")
    return redirect(url_for("reportes.reportes"))

# --------------------------------------------------
# ✅ CIERRE DE CAJA CORREGIDO
# --------------------------------------------------

@reportes_bp.route("/ejecutar_cierre_caja", methods=["POST"])
@login_required
def ejecutar_cierre_caja():

    fecha_comercial, inicio_utc, fin_utc = obtener_rango_turno_colombia()

    def sumar(columna, valor):
        return db.session.query(func.sum(Venta.total)).filter(
            and_(
                Venta.fecha >= inicio_utc,
                Venta.fecha <= fin_utc,
                columna == valor
            )
        ).scalar() or 0

    efectivo = float(sumar(Venta.tipo_pago, "Efectivo"))
    nequi = float(sumar(Venta.detalle_pago, "Nequi"))
    daviplata = float(sumar(Venta.detalle_pago, "Daviplata"))
    tarjeta = float(sumar(Venta.detalle_pago, "Tarjeta"))

    electronico = nequi + daviplata + tarjeta

    recaudo = float(db.session.query(func.sum(AbonoCredito.monto))
        .filter(AbonoCredito.fecha == fecha_comercial)
        .scalar() or 0)

    egresos = float(db.session.query(func.sum(Abono.monto))
        .filter(Abono.fecha == fecha_comercial)
        .scalar() or 0)

    total_ingresos = efectivo + electronico + recaudo
    saldo = total_ingresos - egresos

    snapshot = {
        "EFECTIVO": efectivo,
        "NEQUI": nequi,
        "DAVIPLATA": daviplata,
        "TARJETA": tarjeta,
        "ELECTRONICO": electronico,
        "RECAUDO": recaudo,
        "EGRESOS": egresos,
        "TOTAL": total_ingresos,
        "SALDO": saldo
    }

    cierre = CierreCaja.query.filter_by(
        fecha_cierre=fecha_comercial
    ).first()

    if not cierre:
        cierre = CierreCaja(fecha_cierre=fecha_comercial)

    cierre.total_venta = total_ingresos
    cierre.total_efectivo = efectivo
    cierre.total_electronico = electronico
    cierre.detalles_json = json.dumps(snapshot)
    cierre.usuario_id = current_user.id

    db.session.add(cierre)
    db.session.commit()

    flash("✅ Cierre de caja guardado correctamente", "success")
    return redirect(url_for("reportes.reportes"))

# --------------------------------------------------
# HISTORIAL
# --------------------------------------------------

@reportes_bp.route("/cierre_caja/historial")
@login_required
def historial_cierres():
    cierres = CierreCaja.query.order_by(
        CierreCaja.fecha_cierre.desc()
    ).all()

    return render_template("historial_cierres.html", cierres=cierres)
