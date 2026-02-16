from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
import barcode
from barcode.writer import ImageWriter
import io
import pandas as pd

from database import db
from models import Producto, MovimientoStock, MesaItem


# =========================================================
# BLUEPRINT INVENTARIO
# =========================================================
inventario_bp = Blueprint(
    "inventario",
    __name__,
    url_prefix="/inventario"
)


# =========================================================
# FUNCIÓN AUXILIAR PARA VALIDAR ADMIN
# =========================================================
def es_admin():
    return (
        current_user.is_authenticated and
        current_user.rol and
        current_user.rol.lower() == "administrador"
    )


# =========================================================
# API BUSCADOR GLOBAL
# =========================================================
@inventario_bp.route("/api/productos/buscar")
@login_required
def api_buscar_productos():

    query = request.args.get("q", "").strip()

    if not query:
        return jsonify([])

    productos = Producto.query.filter(
        (Producto.nombre.ilike(f"%{query}%")) |
        (Producto.codigo.ilike(f"%{query}%")) |
        (Producto.marca.ilike(f"%{query}%"))
    ).limit(20).all()

    return jsonify([
        {
            "id": p.id,
            "codigo": p.codigo or "",
            "nombre": (p.nombre or "SIN NOMBRE").upper(),
            "stock": p.cantidad or 0,
            "precio": p.valor_venta or 0,
            "marca": (p.marca or "S.M").upper(),
            "valor_interno": p.valor_interno or 0
        }
        for p in productos
    ])


# =========================================================
# LISTADO PRINCIPAL INVENTARIO
# =========================================================
@inventario_bp.route("/")
@login_required
def inventario():

    page = request.args.get("page", 1, type=int)
    search_query = request.args.get("search", "").strip()

    query = Producto.query.order_by(Producto.id.desc())

    if search_query:
        query = query.filter(
            (Producto.nombre.ilike(f"%{search_query}%")) |
            (Producto.codigo.ilike(f"%{search_query}%")) |
            (Producto.marca.ilike(f"%{search_query}%"))
        )

    productos_paginados = query.paginate(
        page=page,
        per_page=15,
        error_out=False
    )

    historial = MovimientoStock.query.options(
        joinedload(MovimientoStock.producto)
    ).order_by(
        MovimientoStock.fecha.desc()
    ).limit(15).all()

    return render_template(
        "productos.html",
        productos_paginados=productos_paginados,
        historial=historial,
        search_query=search_query
    )


# =========================================================
# CREAR PRODUCTO
# =========================================================
@inventario_bp.route("/crear_producto", methods=["POST"])
@login_required
def crear_producto():

    if not es_admin():
        flash("❌ Acceso denegado.", "danger")
        return redirect(url_for("inventario.inventario"))

    try:
        codigo = request.form.get("codigo", "").strip() or None

        if codigo and Producto.query.filter_by(codigo=codigo).first():
            flash(f"❌ El código '{codigo}' ya existe.", "danger")
            return redirect(url_for("inventario.inventario"))

        nuevo_p = Producto(
            codigo=codigo,
            nombre=request.form.get("nombre").strip().upper(),
            marca=(request.form.get("marca") or "S.M").strip().upper(),
            cantidad=int(request.form.get("cantidad") or 0),
            valor_venta=float(request.form.get("valor_venta") or 0),
            valor_interno=float(request.form.get("valor_interno") or 0)
        )

        db.session.add(nuevo_p)
        db.session.flush()

        # Auto código
        if not nuevo_p.codigo:
            nuevo_p.codigo = str(nuevo_p.id).zfill(8)

        mov = MovimientoStock(
            producto_id=nuevo_p.id,
            cantidad=nuevo_p.cantidad,
            tipo="CREACIÓN",
            usuario_id=current_user.id,
            motivo="Registro inicial"
        )

        db.session.add(mov)
        db.session.commit()

        flash("✅ Producto creado correctamente.", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al crear: {str(e)}", "danger")

    return redirect(url_for("inventario.inventario"))


# =========================================================
# EDITAR PRODUCTO ✅ SOLO POST
# =========================================================
@inventario_bp.route("/editar/<int:producto_id>", methods=["POST"])
@login_required
def editar_producto(producto_id):

    if not es_admin():
        flash("❌ No tienes permisos.", "danger")
        return redirect(url_for("inventario.inventario"))

    producto = Producto.query.get_or_404(producto_id)

    try:
        producto.nombre = request.form.get("nombre").strip().upper()
        producto.marca = (request.form.get("marca") or "S.M").strip().upper()
        producto.codigo = request.form.get("codigo").strip()
        producto.valor_interno = float(request.form.get("valor_interno") or 0)
        producto.valor_venta = float(request.form.get("valor_venta") or 0)
        producto.cantidad = int(request.form.get("cantidad") or 0)

        db.session.commit()
        flash("✅ Producto actualizado correctamente.", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al editar: {str(e)}", "danger")

    return redirect(url_for("inventario.inventario"))


# =========================================================
# ELIMINAR PRODUCTO
# =========================================================
@inventario_bp.route("/eliminar/<int:producto_id>", methods=["GET"])
@login_required
def eliminar_producto(producto_id):

    if not es_admin():
        flash("❌ Acceso denegado.", "danger")
        return redirect(url_for("inventario.inventario"))

    producto = Producto.query.get_or_404(producto_id)

    try:
        MovimientoStock.query.filter_by(producto_id=producto_id).delete()
        MesaItem.query.filter_by(producto_id=producto_id).delete()

        db.session.delete(producto)
        db.session.commit()

        flash("🗑️ Producto eliminado correctamente.", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error al eliminar: {str(e)}", "danger")

    return redirect(url_for("inventario.inventario"))


# =========================================================
# AJUSTAR STOCK ✅ SOLO POST
# =========================================================
@inventario_bp.route("/ajustar_stock/<int:producto_id>", methods=["POST"])
@login_required
def ajustar_stock(producto_id):

    producto = Producto.query.get_or_404(producto_id)

    try:
        cantidad = int(request.form.get("cantidad_sumar") or 0)
        producto.cantidad += cantidad

        mov = MovimientoStock(
            producto_id=producto.id,
            cantidad=cantidad,
            tipo="AJUSTE",
            usuario_id=current_user.id,
            motivo="Carga de bodega"
        )

        db.session.add(mov)
        db.session.commit()

        flash(f"✅ Stock actualizado: {producto.nombre}", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error en ajuste: {str(e)}", "danger")

    return redirect(url_for("inventario.inventario"))


# =========================================================
# EXPORTAR INVENTARIO EXCEL
# =========================================================
@inventario_bp.route("/exportar")
@login_required
def exportar_excel():

    if not es_admin():
        return redirect(url_for("inventario.inventario"))

    productos = Producto.query.all()

    data = [
        {
            "Código": p.codigo,
            "Nombre": p.nombre,
            "Marca": p.marca,
            "Stock": p.cantidad,
            "Costo": p.valor_interno,
            "Venta": p.valor_venta
        }
        for p in productos
    ]

    df = pd.DataFrame(data)

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Inventario")

    output.seek(0)

    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="Inventario_SanRoque.xlsx"
    )


# =========================================================
# GENERAR CÓDIGO DE BARRAS
# =========================================================
@inventario_bp.route("/generar_codigo/<codigo>")
@login_required
def generar_codigo(codigo):

    try:
        CODE128 = barcode.get_barcode_class("code128")
        buffer = io.BytesIO()

        instancia = CODE128(str(codigo), writer=ImageWriter())
        instancia.write(buffer)

        buffer.seek(0)

        return send_file(buffer, mimetype="image/png")

    except Exception as e:
        return f"Error: {str(e)}", 500
