from flask import Blueprint, render_template, request, redirect, url_for, flash, json
from flask_login import login_required, current_user
from database import db
from models import Venta, VentaDetalle, Producto, CierreCaja, Gasto, Usuario, AbonoCredito, Abono
from utils.time_utils import obtener_rango_turno_colombia, obtener_hora_colombia, obtener_rango_turno_por_fecha_comercial
from sqlalchemy import func, and_
from datetime import timedelta, datetime

reportes_bp = Blueprint('reportes', __name__)

@reportes_bp.before_request
@login_required
def verificar_admin():
    if current_user.rol.lower() not in ['administrador', 'administradora']:
        flash('❌ Acceso restringido a administradores de San Roque M.B.', 'danger')
        return redirect(url_for('ventas.dashboard'))

# --- VISTA PRINCIPAL DEL DASHBOARD ---
@reportes_bp.route('/reportes')
def reportes():
    fecha_comercial, inicio_utc, fin_utc = obtener_rango_turno_colombia()

    # A. Acumulado Mensual
    inicio_mes = fecha_comercial.replace(day=1)
    inicio_mes_utc, _ = obtener_rango_turno_por_fecha_comercial(inicio_mes)
    v_mes = db.session.query(func.sum(Venta.total)).filter(and_(Venta.fecha >= inicio_mes_utc, Venta.fecha <= fin_utc)).scalar() or 0
    a_mes = db.session.query(func.sum(AbonoCredito.monto)).filter(and_(AbonoCredito.fecha >= inicio_mes, AbonoCredito.fecha <= fecha_comercial)).scalar() or 0
    total_mensual_acumulado = float(v_mes) + float(a_mes)

    # B. Datos del Día Actual
    v_turno = db.session.query(func.sum(Venta.total)).filter(and_(Venta.fecha >= inicio_utc, Venta.fecha <= fin_utc)).scalar() or 0
    a_turno = db.session.query(func.sum(AbonoCredito.monto)).filter(AbonoCredito.fecha == fecha_comercial).scalar() or 0
    egresos_dia = db.session.query(func.sum(Abono.monto)).filter(Abono.fecha == fecha_comercial).scalar() or 0
    total_diario_ingresos = float(v_turno) + float(a_turno)
    saldo_caja_dia = total_diario_ingresos - float(egresos_dia)

    # C. Gráfico Semanal
    labels_grafico, datos_ventas, datos_gastos = [], [], []
    for i in range(6, -1, -1):
        d = fecha_comercial - timedelta(days=i)
        i_utc, f_utc = obtener_rango_turno_por_fecha_comercial(d)
        vd = db.session.query(func.sum(Venta.total)).filter(and_(Venta.fecha >= i_utc, Venta.fecha <= f_utc)).scalar() or 0
        ad = db.session.query(func.sum(AbonoCredito.monto)).filter(AbonoCredito.fecha == d).scalar() or 0
        gd = db.session.query(func.sum(Abono.monto)).filter(Abono.fecha == d).scalar() or 0
        labels_grafico.append(d.strftime("%d/%m"))
        datos_ventas.append(float(vd + ad))
        datos_gastos.append(float(gd))

    caja_cerrada_hoy = CierreCaja.query.filter_by(fecha_cierre=fecha_comercial).first() is not None

    return render_template('reportes.html',
                           hoy=fecha_comercial,
                           total_diario=total_diario_ingresos,
                           egresos_dia=egresos_dia,
                           saldo_caja_dia=saldo_caja_dia, 
                           total_mensual=total_mensual_acumulado,
                           caja_cerrada_hoy=caja_cerrada_hoy,
                           labels_grafico=labels_grafico,
                           datos_ventas=datos_ventas,
                           datos_gastos=datos_gastos)

# --- NUEVA FUNCIÓN: ENVÍO POR RANGO DE FECHAS ---
@reportes_bp.route('/enviar_reporte_email', methods=['POST'])
def enviar_reporte_email():
    email_destino = request.form.get('email')
    f_inicio = request.form.get('fecha_inicio')
    f_fin = request.form.get('fecha_fin')
    
    # Validación básica
    if f_inicio > f_fin:
        flash('❌ Error: La fecha inicial no puede ser posterior a la final.', 'danger')
        return redirect(url_for('reportes.reportes'))

    # AQUÍ se procesaría la lógica de generación de PDF filtrando por f_inicio y f_fin
    # Por ahora simulamos el envío:
    flash(f'📧 Informe solicitado ({f_inicio} a {f_fin}) enviado a {email_destino}', 'success')
    return redirect(url_for('reportes.reportes'))

@reportes_bp.route('/ejecutar_cierre_caja', methods=['POST'])
def ejecutar_cierre_caja():
    fecha_comercial, inicio_utc, fin_utc = obtener_rango_turno_colombia()
    ventas = db.session.query(func.sum(Venta.total)).filter(and_(Venta.fecha >= inicio_utc, Venta.fecha <= fin_utc)).scalar() or 0
    recaudo = db.session.query(func.sum(AbonoCredito.monto)).filter(AbonoCredito.fecha == fecha_comercial).scalar() or 0
    total_ingresos = float(ventas) + float(recaudo)
    abonos_hoy = Abono.query.filter_by(fecha=fecha_comercial).all()
    tot_egresos = sum(float(a.monto) for a in abonos_hoy)
    
    snapshot = {
        'VENTAS_PRODUCTOS': float(ventas),
        'RECAUDO_CARTERA': float(recaudo),
        'EGRESOS_TOTAL': tot_egresos,
        'SALDO_EFECTIVO_NETO': total_ingresos - tot_egresos,
        'HORA_CIERRE': obtener_hora_colombia().strftime('%I:%M %p')
    }

    cierre = CierreCaja.query.filter_by(fecha_cierre=fecha_comercial).first() or CierreCaja(fecha_cierre=fecha_comercial)
    cierre.total_venta = total_ingresos 
    cierre.detalles_json = json.dumps(snapshot)
    cierre.usuario_id = current_user.id
    db.session.add(cierre)
    db.session.commit()
    
    flash(f'✅ Cierre guardado correctamente.', 'success')
    return redirect(url_for('reportes.reportes'))

@reportes_bp.route('/cierre_caja/historial')
def historial_cierres():
    cierres = CierreCaja.query.order_by(CierreCaja.fecha_cierre.desc()).all()
    return render_template('historial_cierres.html', cierres=cierres)

@reportes_bp.route('/descargar_pdf_cierre')
def descargar_pdf_cierre():
    flash('Generando PDF del día...', 'info')
    return redirect(url_for('reportes.reportes'))