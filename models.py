from database import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date

# ============================================================
# 1. USUARIOS
# ============================================================

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuario'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    cedula = db.Column(db.String(20), unique=True, nullable=False)
    rol = db.Column(db.String(50), default='Vendedora')
    password = db.Column(db.String(255), nullable=False)

    def set_password(self, password_texto):
        self.password = generate_password_hash(password_texto)

    def check_password(self, password_texto):
        return check_password_hash(self.password, password_texto)


# ============================================================
# 2. CLIENTES Y PRODUCTOS
# ============================================================

class Cliente(db.Model):
    __tablename__ = 'cliente'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20))
    direccion = db.Column(db.String(200))
    email = db.Column(db.String(100))
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    categoria = db.Column(db.String(20), default='estandar')


class Producto(db.Model):
    __tablename__ = 'producto'

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(100), unique=True)
    codigo_barra = db.Column(db.String(100), unique=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.String(255))
    marca = db.Column(db.String(100))
    cantidad = db.Column(db.Integer, default=0)
    valor_venta = db.Column(db.Float)
    valor_interno = db.Column(db.Float)
    precio_unit = db.Column(db.Float)
    precio_costo = db.Column(db.Float)
    stock_minimo = db.Column(db.Integer, default=5)


class MovimientoStock(db.Model):
    __tablename__ = 'movimientos_stock'

    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    tipo = db.Column(db.String(50))
    usuario = db.Column(db.String(100))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

    producto = db.relationship('Producto', backref=db.backref('movimientos', lazy=True))


# ============================================================
# 3. VENTAS
# ============================================================

class Venta(db.Model):
    __tablename__ = 'venta'

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    total = db.Column(db.Float)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'))
    tipo_pago = db.Column(db.String(50))
    detalle_pago = db.Column(db.Text)

    detalles = db.relationship('VentaDetalle', backref='venta', lazy=True)
    vendedor = db.relationship('Usuario', backref='ventas_realizadas')
    comprador = db.relationship('Cliente', backref='compras_realizadas')


class VentaDetalle(db.Model):
    __tablename__ = 'venta_detalle'

    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(db.Integer, db.ForeignKey('venta.id'))
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'))
    cantidad = db.Column(db.Integer)
    precio_unitario = db.Column(db.Float)
    subtotal = db.Column(db.Float)

    producto = db.relationship('Producto')


# ============================================================
# 4. CIERRE CAJA
# ============================================================

class CierreCaja(db.Model):
    __tablename__ = 'cierre_caja'

    id = db.Column(db.Integer, primary_key=True)
    fecha_cierre = db.Column(db.Date)
    hora_cierre = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    total_venta = db.Column(db.Float)
    total_efectivo = db.Column(db.Float)
    total_electronico = db.Column(db.Float)
    detalles_json = db.Column(db.Text)

    usuario = db.relationship('Usuario', backref='cierres_realizados')


class AcumuladoMensual(db.Model):
    __tablename__ = 'acumulado_mensual'

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    total_venta = db.Column(db.Float, default=0)


# ============================================================
# 5. PROVEEDORES Y GASTOS
# ============================================================

class Factura(db.Model):
    __tablename__ = 'facturas'

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(100), nullable=False)
    proveedor = db.Column(db.String(150), nullable=False)
    total = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.Date, default=date.today)
    soporte_foto = db.Column(db.String(255))

    abonos = db.relationship(
        'Abono',
        backref='factura',
        lazy=True,
        cascade="all, delete-orphan"
    )


class Gasto(db.Model):
    __tablename__ = 'gastos'

    id = db.Column(db.Integer, primary_key=True)
    categoria = db.Column(db.String(100))
    concepto = db.Column(db.String(200))
    total = db.Column(db.Float)
    fecha = db.Column(db.Date, default=date.today)
    soporte_foto = db.Column(db.String(255))

    abonos = db.relationship(
        'Abono',
        backref='gasto',
        lazy=True,
        cascade="all, delete-orphan"
    )


class Abono(db.Model):
    __tablename__ = 'abonos'

    id = db.Column(db.Integer, primary_key=True)
    factura_id = db.Column(db.Integer, db.ForeignKey('facturas.id'))
    gasto_id = db.Column(db.Integer, db.ForeignKey('gastos.id'))
    monto = db.Column(db.Float, nullable=False)
    medio_pago = db.Column(db.String(50))
    fecha = db.Column(db.Date, default=date.today)


# ============================================================
# 6. CREDITOS
# ============================================================

class Credito(db.Model):
    __tablename__ = 'credito'

    id = db.Column(db.Integer, primary_key=True)
    cliente = db.Column(db.String(150), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    estado = db.Column(db.String(20), default='abierto')
    categoria_cliente = db.Column(db.String(50), default='estandar')
    fecha_inicio = db.Column(db.Date, default=date.today)
    fecha_vencimiento = db.Column(db.Date)
    fecha_cierre = db.Column(db.Date)
    total_consumido = db.Column(db.Float, default=0)
    abonado = db.Column(db.Float, default=0)
    fecha_ultimo_abono = db.Column(db.Date)

    items = db.relationship(
        'CreditoItem',
        backref='credito',
        cascade="all, delete-orphan"
    )

    abonos = db.relationship(
        'AbonoCredito',
        backref='credito',
        cascade="all, delete-orphan"
    )


class CreditoItem(db.Model):
    __tablename__ = 'credito_item'

    id = db.Column(db.Integer, primary_key=True)
    credito_id = db.Column(db.Integer, db.ForeignKey('credito.id'))
    producto = db.Column(db.String(150))
    cantidad = db.Column(db.Integer)
    precio_unit = db.Column(db.Float)
    total_linea = db.Column(db.Float)
    fecha = db.Column(db.Date, default=date.today)


class AbonoCredito(db.Model):
    __tablename__ = 'abono_credito'

    id = db.Column(db.Integer, primary_key=True)
    credito_id = db.Column(db.Integer, db.ForeignKey('credito.id'))
    monto = db.Column(db.Float)
    medio_pago = db.Column(db.String(50))
    fecha = db.Column(db.Date, default=date.today)
