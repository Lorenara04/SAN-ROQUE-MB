from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import date, datetime
import pandas as pd
from io import BytesIO

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

            nueva_f = Factura(
                numero=request.form.get("numero"),
                proveedor=request.form.get("proveedor").upper(),
                total=float(request.form.get("total", 0)),
                fecha=fecha_final
            )
            db.session.add(nueva_f)
            db.session.commit()
            flash("✅ Factura de proveedor registrada con éxito.", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error al registrar factura: {e}", "danger")

        return redirect(url_for('proveedores_gastos.enlista_proveedores'))

    # Carga de datos
    facturas_db = Factura.query.order_by(Factura.fecha.desc()).all()
    
    for f in facturas_db:
        f.abonado = db.session.query(func.sum(Abono.monto)).filter(Abono.factura_id == f.id).scalar() or 0
        # Agregado para historial y saldo
        f.saldo = f.total - f.abonado
        f.lista_abonos = Abono.query.filter_by(factura_id=f.id).order_by(Abono.fecha.desc()).all()
        
        ultimo_abono = db.session.query(func.max(Abono.fecha)).filter(Abono.factura_id == f.id).scalar()
        f.fecha_ultimo_abono = ultimo_abono.strftime('%d/%m/%Y') if ultimo_abono else None
        f.fecha_factura = f.fecha.strftime('%Y-%m-%d') if f.fecha else ""

    return render_template("proveedores.html", facturas=facturas_db)

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
# ABONAR FACTURA / GASTO (BOTÓN BOLSA)
# ======================================================
@proveedores_gastos_bp.route('/abonar', methods=['POST'])
@login_required
def abonar():
    try:
        monto = float(request.form.get("monto", 0))
        medio = request.form.get("medio", "Efectivo")
        factura_id = request.form.get("factura_id")
        gasto_id = request.form.get("gasto_id")
        fecha_abono_str = request.form.get("fecha_abono") # Captura fecha del historial

        if monto <= 0:
            flash("⚠️ El monto debe ser mayor a cero.", "warning")
            return redirect(request.referrer)

        # Usar fecha enviada o la de hoy por defecto
        fecha_final = datetime.strptime(fecha_abono_str, "%Y-%m-%d").date() if fecha_abono_str else date.today()

        nuevo_abono = Abono(
            monto=monto,
            medio_pago=medio,
            fecha=fecha_final
        )
        
        if factura_id:
            nuevo_abono.factura_id = int(factura_id)
        elif gasto_id:
            nuevo_abono.gasto_id = int(gasto_id)

        db.session.add(nuevo_abono)
        db.session.commit()
        flash(f"✅ Abono de ${monto:,.0f} registrado.", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al procesar el abono: {e}", "danger")

    return redirect(request.referrer)

# ======================================================
# GESTIÓN DE ABONOS (EDICIÓN Y ELIMINACIÓN)
# ======================================================
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
        # Eliminar abonos relacionados
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
        categoria = request.form.get("categoria")
        concepto = request.form.get("concepto")
        total_form = request.form.get("total")
        fecha_str = request.form.get("fecha") # Captura la fecha del formulario

        if not categoria or not concepto:
            flash("❌ Debe seleccionar categoría y concepto.", "danger")
            return redirect(url_for('proveedores_gastos.gastos'))

        try:
            fecha_final = datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else date.today()
            nuevo_g = Gasto(
                categoria=categoria,
                concepto=concepto,
                total=float(total_form if total_form else 0),
                fecha=fecha_final
            )
            db.session.add(nuevo_g)
            db.session.commit()
            flash("✅ Gasto registrado.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Error: {e}", "danger")
        return redirect(url_for('proveedores_gastos.gastos'))

    gastos_list = Gasto.query.order_by(Gasto.fecha.desc()).all()
    for g in gastos_list:
        g.abonado = db.session.query(func.sum(Abono.monto)).filter(Abono.gasto_id == g.id).scalar() or 0
        # Agregado para historial y saldo
        g.saldo = g.total - g.abonado
        g.lista_abonos = Abono.query.filter_by(gasto_id=g.id).order_by(Abono.fecha.desc()).all()
        
    return render_template("modulo_gastos.html", gastos=gastos_list)

# ======================================================
# EDITAR GASTO (NUEVA RUTA PARA EVITAR DUPLICADOS)
# ======================================================
@proveedores_gastos_bp.route('/gasto/editar/<int:gasto_id>', methods=['POST'])
@login_required
def editar_gasto(gasto_id):
    gasto = Gasto.query.get_or_404(gasto_id)
    try:
        gasto.categoria = request.form.get("categoria")
        gasto.concepto = request.form.get("concepto")
        gasto.total = float(request.form.get("total", 0))
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
# ELIMINAR GASTO (CORRECCIÓN ERROR 404)
# ======================================================
@proveedores_gastos_bp.route('/eliminar_gasto/<int:gasto_id>', methods=['POST', 'GET'])
@login_required
def eliminar_gasto(gasto_id):
    gasto = Gasto.query.get_or_404(gasto_id)
    try:
        # Importante: Eliminar abonos del gasto antes
        Abono.query.filter_by(gasto_id=gasto_id).delete()
        db.session.delete(gasto)
        db.session.commit()
        flash("🗑️ Gasto eliminado.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error: {e}", "danger")
    return redirect(url_for('proveedores_gastos.gastos'))

# ======================================================
# EXPORTAR EXCEL
# ======================================================
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