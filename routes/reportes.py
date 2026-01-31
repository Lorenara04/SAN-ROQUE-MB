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
import json
import pytz

reportes_bp = Blueprint("reportes", __name__)

# --------------------------------------------------
# FILTROS Y UTILIDADES
# --------------------------------------------------

@reportes_bp.app_template_filter('from_json')
def from_json_filter(value):
    """ Filtro para convertir texto JSON en diccionario dentro del HTML """
    try:
        if isinstance(value, dict): return value
        return json.loads(value) if value else {}
    except:
        return {}

def fmt(v):
    return f"$ {float(v or 0):,.0f}".replace(",", ".")

def generar_html_reporte(f_ini, f_fin, datos):
    """ Genera el diseño de informe premium para correos """
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0; padding:0; background-color:#edf2f7; font-family:'Helvetica Neue', Helvetica, Arial, sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#edf2f7; padding: 40px 0;">
    <tr>
        <td align="center">
            <table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff; border-radius:20px; overflow:hidden; box-shadow:0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04);">
                <tr>
                    <td style="background-color:#1a202c; padding:45px 40px; text-align:center;">
                        <h1 style="color:#ffffff; margin:0; font-size:30px; font-weight:700;">San Roque M.B</h1>
                        <p style="color:#a0aec0; margin:8px 0 0 0;">Informe Ejecutivo de Gestión</p>
                        <div style="display:inline-block; margin-top:20px; padding:6px 15px; background-color:#2d3748; border-radius:20px; color:#63b3ed; font-size:12px; font-weight:bold;">
                            {f_ini} — {f_fin}
                        </div>
                    </td>
                </tr>
                <tr>
                    <td style="padding:40px;">
                        <table width="100%">
                            <tr>
                                <td width="50%" style="padding-right:12px;">
                                    <div style="border:1px solid #e2e8f0; border-radius:16px; padding:25px; background-color:#f8fafc;">
                                        <p style="color:#718096; font-size:11px; margin:0; font-weight:700;">SALDO NETO</p>
                                        <h2 style="color:#2b6cb0; margin:8px 0 0 0;">{fmt(datos['saldo_neto'])}</h2>
                                    </div>
                                </td>
                                <td width="50%">
                                    <div style="border:1px solid #e2e8f0; border-radius:16px; padding:25px; background-color:#f8fafc;">
                                        <p style="color:#718096; font-size:11px; margin:0; font-weight:700;">EGRESOS</p>
                                        <h2 style="color:#e53e3e; margin:8px 0 0 0;">{fmt(datos['egresos'])}</h2>
                                    </div>
                                </td>
                            </tr>
                        </table>
                        <div style="margin-top:30px; background-color:#ffffff; border:1px solid #e2e8f0; border-radius:16px; padding:20px;">
                            <h3 style="color:#2d3748; font-size:17px; margin:0 0 15px 0;">Ingresos por Canal</h3>
                            <table width="100%">
                                <tr><td style="padding:8px 0; border-bottom:1px solid #edf2f7;">Efectivo</td><td align="right" style="font-weight:700;">{fmt(datos['efectivo'])}</td></tr>
                                <tr><td style="padding:8px 0; border-bottom:1px solid #edf2f7;">Nequi</td><td align="right" style="font-weight:700;">{fmt(datos['nequi'])}</td></tr>
                                <tr><td style="padding:8px 0; border-bottom:1px solid #edf2f7;">Daviplata</td><td align="right" style="font-weight:700;">{fmt(datos['daviplata'])}</td></tr>
                                <tr><td style="padding:8px 0;">Tarjeta / Otros</td><td align="right" style="font-weight:700;">{fmt(datos['tarjeta'])}</td></tr>
                            </table>
                        </div>
                    </td>
                </tr>
                <tr><td align="center" style="background-color:#f7fafc; padding:20px; color:#a0aec0; font-size:11px;">© 2026 San Roque M.B</td></tr>
            </table>
        </td>
    </tr>
</table>
</body>
</html>
"""

# --------------------------------------------------
# RUTAS Y LOGICA
# --------------------------------------------------

@reportes_bp.before_request
@login_required
def verificar_admin():
    if current_user.rol.lower() not in ["administrador", "administradora"]:
        flash("Acceso restringido.", "danger")
        return redirect(url_for("ventas.dashboard"))

@reportes_bp.route("/reportes")
@login_required
def reportes():
    fecha_comercial, inicio_utc, fin_utc = obtener_rango_turno_colombia()

    # Obtener todas las ventas del turno
    ventas_turno = Venta.query.filter(and_(Venta.fecha >= inicio_utc, Venta.fecha <= fin_utc)).all()
    efectivo = nequi = daviplata = tarjeta = total_v = 0

    for v in ventas_turno:
        total_v += v.total
        if v.detalle_pago:
            try:
                p = json.loads(v.detalle_pago) if isinstance(v.detalle_pago, str) else v.detalle_pago
                efectivo += float(p.get('Efectivo', 0))
                nequi += float(p.get('Nequi', 0))
                daviplata += float(p.get('Daviplata', 0))
                # Sumamos Tarjeta, Bold y Transferencias aquí
                tarjeta += float(p.get('Tarjeta/Bold', 0) or p.get('Tarjeta', 0) or p.get('Transferencia', 0))
            except: pass

    recaudo = float(db.session.query(func.sum(AbonoCredito.monto)).filter(AbonoCredito.fecha == fecha_comercial).scalar() or 0)
    egresos = float(db.session.query(func.sum(Abono.monto)).filter(Abono.fecha == fecha_comercial).scalar() or 0)

    total_diario_completo = total_v + recaudo
    saldo = total_diario_completo - egresos

    # Gráfico 7 días
    labels_grafico, datos_ventas = [], []
    for i in range(6, -1, -1):
        dia = fecha_comercial - timedelta(days=i)
        labels_grafico.append(dia.strftime("%d/%m"))
        i_u, f_u = obtener_rango_turno_por_fecha_comercial(dia)
        total_dia = db.session.query(func.sum(Venta.total)).filter(and_(Venta.fecha >= i_u, Venta.fecha <= f_u)).scalar() or 0
        datos_ventas.append(float(total_dia))

    caja_cerrada = CierreCaja.query.filter_by(fecha_cierre=fecha_comercial).first() is not None

    return render_template(
        "reportes.html", hoy=fecha_comercial, total_diario=total_v, efectivo=efectivo,
        electronico=(nequi + daviplata + tarjeta), nequi=nequi, daviplata=daviplata, tarjeta=tarjeta,
        egresos_dia=egresos, saldo_caja_dia=saldo, 
        caja_cerrada_hoy=caja_cerrada, labels_grafico=labels_grafico, datos_ventas=datos_ventas
    )

@reportes_bp.route("/enviar_reporte_email", methods=["POST"])
@login_required
def enviar_reporte_email():
    from utils.correo_utils import enviar_correo
    email = request.form.get("email")
    f_ini = request.form.get("fecha_inicio")
    f_fin = request.form.get("fecha_fin")

    inicio = datetime.strptime(f_ini, "%Y-%m-%d")
    fin = datetime.strptime(f_fin, "%Y-%m-%d") + timedelta(days=1)

    ventas = Venta.query.filter(Venta.fecha >= inicio, Venta.fecha < fin).all()
    e_efectivo = e_nequi = e_daviplata = e_tarjeta = 0
    for v in ventas:
        if v.detalle_pago:
            try:
                p = json.loads(v.detalle_pago) if isinstance(v.detalle_pago, str) else v.detalle_pago
                e_efectivo += float(p.get('Efectivo', 0)); e_nequi += float(p.get('Nequi', 0))
                e_daviplata += float(p.get('Daviplata', 0)); e_tarjeta += float(p.get('Tarjeta/Bold', 0) or p.get('Tarjeta', 0))
            except: pass
    
    total_ingresos = sum(v.total for v in ventas)
    egresos = db.session.query(func.sum(Abono.monto)).filter(and_(Abono.fecha >= f_ini, Abono.fecha <= f_fin)).scalar() or 0

    datos_informe = {
        "saldo_neto": total_ingresos - egresos, "egresos": egresos, "efectivo": e_efectivo,
        "nequi": e_nequi, "daviplata": e_daviplata, "tarjeta": e_tarjeta,
        "num_ventas": len(ventas), "promedio": total_ingresos / len(ventas) if len(ventas) > 0 else 0
    }

    html = generar_html_reporte(f_ini, f_fin, datos_informe)
    enviar_correo(email, f"Reporte de Gestión San Roque - {f_ini}", html, [])
    flash("✅ Informe premium enviado correctamente", "success")
    return redirect(url_for("reportes.reportes"))

@reportes_bp.route("/ejecutar_cierre_caja", methods=["POST"])
@login_required
def ejecutar_cierre_caja():
    fecha_comercial, inicio_utc, fin_utc = obtener_rango_turno_colombia()
    
    if CierreCaja.query.filter_by(fecha_cierre=fecha_comercial).first():
        flash("⚠️ Ya existe un cierre registrado para hoy.", "warning")
        return redirect(url_for("reportes.reportes"))

    ventas_turno = Venta.query.filter(and_(Venta.fecha >= inicio_utc, Venta.fecha <= fin_utc)).all()
    t_efectivo = t_nequi = t_daviplata = t_tarjeta = t_venta = 0
    for v in ventas_turno:
        t_venta += v.total
        if v.detalle_pago:
            try:
                p = json.loads(v.detalle_pago) if isinstance(v.detalle_pago, str) else v.detalle_pago
                t_efectivo += float(p.get('Efectivo', 0)); t_nequi += float(p.get('Nequi', 0))
                t_daviplata += float(p.get('Daviplata', 0))
                t_tarjeta += float(p.get('Tarjeta/Bold', 0) or p.get('Tarjeta', 0) or p.get('Transferencia', 0))
            except: pass

    abonos_hoy = Abono.query.filter(Abono.fecha == fecha_comercial).all()
    egresos_hoy = sum(a.monto for a in abonos_hoy)
    
    detalle_dict = {
        "DESGLOSE_PAGOS": {"Efectivo": t_efectivo, "Nequi": t_nequi, "Daviplata": t_daviplata, "Tarjeta": t_tarjeta},
        "EGRESOS_TOTAL": egresos_hoy,
        "DETALLE_EGRESOS": [{"concepto": a.gasto_relacionado.concepto if a.gasto_relacionado else "Gasto", "monto": a.monto} for a in abonos_hoy],
        "HORA_CIERRE": datetime.now(pytz.timezone('America/Bogota')).strftime('%H:%M:%S')
    }

    nuevo_cierre = CierreCaja(
        fecha_cierre=fecha_comercial,
        usuario_id=current_user.id,
        total_venta=t_venta,
        total_efectivo=t_efectivo,
        total_electronico=(t_nequi + t_daviplata + t_tarjeta),
        detalles_json=json.dumps(detalle_dict)
    )
    
    try:
        db.session.add(nuevo_cierre)
        db.session.commit()
        flash("✅ Cierre guardado exitosamente.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al cerrar: {str(e)}", "danger")

    return redirect(url_for("reportes.reportes"))

@reportes_bp.route("/cierre_caja/historial")
@login_required
def historial_cierres():
    cierres = CierreCaja.query.order_by(CierreCaja.fecha_cierre.desc()).all()
    return render_template("historial_cierres.html", cierres=cierres)