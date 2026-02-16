from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from database import db
from models import Venta, CierreCaja, Abono
from utils.time_utils import (
    obtener_rango_turno_colombia,
    obtener_rango_turno_por_fecha_comercial
)
from sqlalchemy import func, and_
from datetime import timedelta, datetime
import json
import pytz

reportes_bp = Blueprint("reportes", __name__)

# --------------------------------------------------
# FILTROS Y UTILIDADES
# --------------------------------------------------

@reportes_bp.app_template_filter('from_json')
def from_json_filter(value):
    try:
        if isinstance(value, dict):
            return value
        return json.loads(value) if value else {}
    except Exception:
        return {}

def fmt(v):
    """Formato de moneda para los reportes HTML"""
    return f"$ {float(v or 0):,.0f}".replace(",", ".")

def generar_html_reporte(f_ini, f_fin, datos):
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="background:#edf2f7;font-family:Arial;padding:20px;">
    <div style="background:white;padding:20px;border-radius:10px;max-width:500px;margin:auto;">
        <h2 style="color:#2d3748;border-bottom:2px solid #edf2f7;padding-bottom:10px;">Reporte San Roque M.B</h2>
        <p style="color:#4a5568;"><b>Periodo:</b> {f_ini} hasta {f_fin}</p>
        <ul style="list-style:none;padding:0;">
            <li style="padding:8px 0;border-bottom:1px solid #f7fafc;"><b>Saldo neto:</b> {fmt(datos['saldo_neto'])}</li>
            <li style="padding:8px 0;border-bottom:1px solid #f7fafc;color:#e53e3e;"><b>Egresos:</b> {fmt(datos['egresos'])}</li>
            <li style="padding:8px 0;"><b>Efectivo:</b> {fmt(datos['efectivo'])}</li>
            <li style="padding:8px 0;"><b>Nequi:</b> {fmt(datos['nequi'])}</li>
            <li style="padding:8px 0;"><b>Daviplata:</b> {fmt(datos['daviplata'])}</li>
            <li style="padding:8px 0;"><b>Tarjeta/Bold:</b> {fmt(datos['tarjeta'])}</li>
        </ul>
    </div>
</body>
</html>
"""

# --------------------------------------------------
# SEGURIDAD (CORREGIDO)
# --------------------------------------------------

@reportes_bp.before_request
@login_required
def verificar_admin():
    # Evita verificar seguridad en rutas que no pertenecen a este blueprint explícitamente
    if request.endpoint and 'reportes.' not in request.endpoint:
        return
    if current_user.rol.lower() not in ["administrador", "administradora"]:
        flash("Acceso restringido. Se requieren permisos de administrador.", "danger")
        return redirect(url_for("ventas.dashboard"))

# --------------------------------------------------
# VISTA PRINCIPAL DE REPORTES
# --------------------------------------------------

@reportes_bp.route("/reportes")
@login_required
def reportes():
    fecha_comercial, inicio_utc, fin_utc = obtener_rango_turno_colombia()

    ventas = Venta.query.filter(
        and_(Venta.fecha >= inicio_utc, Venta.fecha <= fin_utc)
    ).all()

    efectivo = nequi = daviplata = tarjeta = total_ventas = 0

    for v in ventas:
        total_ventas += (v.total or 0)
        if v.detalle_pago:
            try:
                # Si detalle_pago ya es un dict, no intentamos cargar JSON
                p = v.detalle_pago if isinstance(v.detalle_pago, dict) else json.loads(v.detalle_pago)
                efectivo += float(p.get("Efectivo") or 0)
                nequi += float(p.get("Nequi") or 0)
                daviplata += float(p.get("Daviplata") or 0)
                tarjeta += float(
                    p.get("Tarjeta/Bold") or 
                    p.get("Tarjeta") or 
                    p.get("Transferencia") or 0
                )
            except Exception:
                # Si falla el JSON, sumamos el total al efectivo por defecto para no perder dinero en el reporte
                efectivo += (v.total or 0)

    egresos = float(
        db.session.query(func.sum(Abono.monto))
        .filter(Abono.fecha == fecha_comercial)
        .scalar() or 0
    )

    saldo = total_ventas - egresos

    # Gráfico últimos 7 días
    labels_grafico = []
    datos_ventas = []

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
        total_diario=total_ventas,
        efectivo=efectivo,
        electronico=(nequi + daviplata + tarjeta),
        nequi=nequi,
        daviplata=daviplata,
        tarjeta=tarjeta,
        egresos_dia=egresos,
        saldo_caja_dia=saldo,
        caja_cerrada_hoy=caja_cerrada,
        labels_grafico=labels_grafico,
        datos_ventas=datos_ventas
    )

# --------------------------------------------------
# ENVIAR REPORTE POR EMAIL
# --------------------------------------------------

@reportes_bp.route("/enviar_reporte_email", methods=["POST"])
@login_required
def enviar_reporte_email():
    from utils.correo_utils import enviar_correo

    email = request.form.get("email")
    f_ini_str = request.form.get("fecha_inicio")
    f_fin_str = request.form.get("fecha_fin")

    if not email or not f_ini_str or not f_fin_str:
        flash("Datos incompletos para enviar el reporte.", "warning")
        return redirect(url_for("reportes.reportes"))

    inicio = datetime.strptime(f_ini_str, "%Y-%m-%d")
    fin = datetime.strptime(f_fin_str, "%Y-%m-%d") + timedelta(days=1)

    ventas = Venta.query.filter(
        Venta.fecha >= inicio,
        Venta.fecha < fin
    ).all()

    efectivo = nequi = daviplata = tarjeta = 0
    for v in ventas:
        if v.detalle_pago:
            try:
                p = v.detalle_pago if isinstance(v.detalle_pago, dict) else json.loads(v.detalle_pago)
                efectivo += float(p.get("Efectivo") or 0)
                nequi += float(p.get("Nequi") or 0)
                daviplata += float(p.get("Daviplata") or 0)
                tarjeta += float(p.get("Tarjeta/Bold") or p.get("Tarjeta") or 0)
            except Exception:
                efectivo += (v.total or 0)

    total_ingresos = sum(v.total or 0 for v in ventas)

    egresos = float(
        db.session.query(func.sum(Abono.monto))
        .filter(Abono.fecha >= inicio.date(), Abono.fecha <= fin.date())
        .scalar() or 0
    )

    datos = {
        "saldo_neto": total_ingresos - egresos,
        "egresos": egresos,
        "efectivo": efectivo,
        "nequi": nequi,
        "daviplata": daviplata,
        "tarjeta": tarjeta
    }

    html = generar_html_reporte(f_ini_str, f_fin_str, datos)
    enviar_correo(email, f"Reporte San Roque MB ({f_ini_str})", html, [])
    flash("✅ Reporte enviado correctamente por correo.", "success")

    return redirect(url_for("reportes.reportes"))

# --------------------------------------------------
# CIERRE DE CAJA
# --------------------------------------------------

@reportes_bp.route("/ejecutar_cierre_caja", methods=["POST"])
@login_required
def ejecutar_cierre_caja():
    fecha_comercial, inicio_utc, fin_utc = obtener_rango_turno_colombia()

    if CierreCaja.query.filter_by(fecha_cierre=fecha_comercial).first():
        flash("⚠️ Ya se realizó el cierre de caja para esta fecha comercial.", "warning")
        return redirect(url_for("reportes.reportes"))

    ventas = Venta.query.filter(
        and_(Venta.fecha >= inicio_utc, Venta.fecha <= fin_utc)
    ).all()

    t_efectivo = t_nequi = t_daviplata = t_tarjeta = t_total = 0

    for v in ventas:
        t_total += (v.total or 0)
        if v.detalle_pago:
            try:
                p = v.detalle_pago if isinstance(v.detalle_pago, dict) else json.loads(v.detalle_pago)
                t_efectivo += float(p.get("Efectivo") or 0)
                t_nequi += float(p.get("Nequi") or 0)
                t_daviplata += float(p.get("Daviplata") or 0)
                t_tarjeta += float(p.get("Tarjeta/Bold") or p.get("Tarjeta") or 0)
            except Exception:
                t_efectivo += (v.total or 0)

    egresos_hoy = db.session.query(func.sum(Abono.monto)).filter(Abono.fecha == fecha_comercial).scalar() or 0

    detalles = {
        "pagos": {
            "Efectivo": t_efectivo,
            "Nequi": t_nequi,
            "Daviplata": t_daviplata,
            "Tarjeta": t_tarjeta
        },
        "egresos": float(egresos_hoy),
        "hora_cierre": datetime.now(pytz.timezone("America/Bogota")).strftime("%H:%M:%S")
    }

    try:
        cierre = CierreCaja(
            fecha_cierre=fecha_comercial,
            usuario_id=current_user.id,
            total_venta=t_total,
            total_efectivo=t_efectivo,
            total_electronico=(t_nequi + t_daviplata + t_tarjeta),
            detalles_json=json.dumps(detalles)
        )

        db.session.add(cierre)
        db.session.commit()
        flash("✅ Cierre de caja realizado y guardado.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al ejecutar el cierre: {str(e)}", "danger")

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