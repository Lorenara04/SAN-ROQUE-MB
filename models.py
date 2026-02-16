from database import db
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# ======================================================
# 1. USUARIOS Y SEGURIDAD
# ======================================================
class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(20), default='vendedor')
    nombre = db.Column(db.String(100))
    apellido = db.Column(db.String(100))
    cedula = db.Column(db.String(20))

    # Relaciones
    cierres = db.relationship('CierreCaja', backref='usuario_rel', lazy=True)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)


# ======================================================
# 2. INVENTARIO Y STOCK
# ======================================================
class Producto(db.Model):
    __tablename__ = 'productos'

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True)
    nombre = db.Column(db.String(100), nullable=False)
    marca = db.Column(db.String(100))
    valor_venta = db.Column(db.Float, nullable=False)
    valor_interno = db.Column(db.Float)
    cantidad = db.Column(db.Integer, default=0)
    categoria = db.Column(db.String(50))

    # RELACIÓN CORREGIDA: Eliminamos la duplicidad para evitar el error 404
    movimientos = db.relationship(
        'MovimientoStock',
        back_populates='producto',
        cascade="all, delete-orphan",
        lazy=True
    )


class MovimientoStock(db.Model):
    __tablename__ = 'movimientos_stock'
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    cantidad = db.Column(db.Integer, nullable=False)
    tipo = db.Column(db.String(50), nullable=False) # 'CREACIÓN', 'AJUSTE', 'VENTA'
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    motivo = db.Column(db.String(200))

    # PUENTES DEFINITIVOS (BACK_POPULATES es más estable para lo que necesitas)
    producto = db.relationship('Producto', back_populates='movimientos')
    usuario = db.relationship('Usuario', backref=db.backref('movimientos_stock', lazy=True))

# ======================================================
# 3. GESTIÓN DE MESAS (POS)
# ======================================================
class Mesa(db.Model):
    __tablename__ = 'mesas'

    id = db.Column(db.Integer, primary_key=True)
    estado = db.Column(db.String(20), default='libre')
    total_cuenta = db.Column(db.Float, default=0.0)

    items = db.relationship(
        'MesaItem',
        backref='mesa_rel',
        lazy=True,
        cascade="all, delete-orphan"
    )


class MesaItem(db.Model):
    __tablename__ = 'mesa_items'

    id = db.Column(db.Integer, primary_key=True)
    mesa_id = db.Column(db.Integer, db.ForeignKey('mesas.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Integer, default=1)
    subtotal = db.Column(db.Float, default=0.0)

    producto = db.relationship('Producto')


# ======================================================
# 4. CLIENTES
# ======================================================
class Cliente(db.Model):
    __tablename__ = 'clientes'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(20), default='estandar')

    creditos_cliente = db.relationship(
        'Credito',
        backref='cliente_rel',
        lazy=True,
        cascade="all, delete-orphan"
    )


# ======================================================
# 5. CRÉDITOS
# ======================================================
class Credito(db.Model):
    __tablename__ = 'creditos'

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    fecha_inicio = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_vencimiento = db.Column(db.DateTime)
    total = db.Column(db.Float, default=0.0)
    estado = db.Column(db.String(20), default='pendiente')
    tipo = db.Column(db.String(50), default='PERSONAL')

    items = db.relationship('CreditoItem', backref='credito_rel', lazy=True, cascade="all, delete-orphan")
    abonos = db.relationship('AbonoCredito', backref='credito_rel', lazy=True, cascade="all, delete-orphan")


class CreditoItem(db.Model):
    __tablename__ = 'credito_items'
    id = db.Column(db.Integer, primary_key=True)
    credito_id = db.Column(db.Integer, db.ForeignKey('creditos.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    producto = db.relationship('Producto')


class AbonoCredito(db.Model):
    __tablename__ = 'abonos_credito'
    id = db.Column(db.Integer, primary_key=True)
    credito_id = db.Column(db.Integer, db.ForeignKey('creditos.id'), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    medio_pago = db.Column(db.String(50), default='EFECTIVO')


# ======================================================
# 6. CONTABILIDAD
# ======================================================
class CierreCaja(db.Model):
    __tablename__ = 'cierres_caja'
    id = db.Column(db.Integer, primary_key=True)
    fecha_apertura = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_cierre = db.Column(db.DateTime)
    monto_inicial = db.Column(db.Float, default=0.0)
    ingresos_efectivo = db.Column(db.Float, default=0.0)
    ingresos_otros = db.Column(db.Float, default=0.0)
    egresos = db.Column(db.Float, default=0.0)
    saldo_final = db.Column(db.Float, default=0.0)
    estado = db.Column(db.String(20), default='abierto')
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))


class AcumuladoMensual(db.Model):
    __tablename__ = 'acumulados_mensuales'
    id = db.Column(db.Integer, primary_key=True)
    mes = db.Column(db.Integer, nullable=False)
    anio = db.Column(db.Integer, nullable=False)
    total_ventas = db.Column(db.Float, default=0.0)
    total_gastos = db.Column(db.Float, default=0.0)
    utilidad = db.Column(db.Float, default=0.0)


# ======================================================
# 7. PROVEEDORES Y GASTOS
# ======================================================
class Factura(db.Model):
    __tablename__ = 'facturas'
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(50))
    proveedor = db.Column(db.String(100), nullable=False)
    total = db.Column(db.Float, default=0.0)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    soporte_foto = db.Column(db.String(255))
    abonos = db.relationship('Abono', backref='factura_rel', lazy=True, cascade="all, delete-orphan")


class Gasto(db.Model):
    __tablename__ = 'gastos'
    id = db.Column(db.Integer, primary_key=True)
    categoria = db.Column(db.String(100), nullable=False)
    concepto = db.Column(db.String(255), nullable=False)
    total = db.Column(db.Float, default=0.0)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    soporte_foto = db.Column(db.String(255))
    abonos = db.relationship('Abono', backref='gasto_rel', lazy=True, cascade="all, delete-orphan")


class Abono(db.Model):
    __tablename__ = 'abonos'
    id = db.Column(db.Integer, primary_key=True)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    medio_pago = db.Column(db.String(50))
    factura_id = db.Column(db.Integer, db.ForeignKey('facturas.id'))
    gasto_id = db.Column(db.Integer, db.ForeignKey('gastos.id'))


# ======================================================
# 8. VENTAS
# ======================================================
class Venta(db.Model):
    __tablename__ = 'ventas'
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    total = db.Column(db.Float, default=0.0)
    estado = db.Column(db.String(20), default='abierta')
    nombre_cliente = db.Column(db.String(100))
    metodo_pago = db.Column(db.String(50))
    pago_efectivo = db.Column(db.Float, default=0.0)
    cambio = db.Column(db.Float, default=0.0)
    detalle_pago = db.Column(db.String(255))

    mesa_id = db.Column(db.Integer, db.ForeignKey('mesas.id'))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'))

    detalles = db.relationship('VentaDetalle', backref='venta_rel', lazy=True, cascade="all, delete-orphan")


class VentaDetalle(db.Model):
    __tablename__ = 'venta_detalles'
    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(db.Integer, db.ForeignKey('ventas.id'))
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'))
    cantidad = db.Column(db.Integer)
    precio_unitario = db.Column(db.Float)
    subtotal = db.Column(db.Float)
    producto = db.relationship('Producto')