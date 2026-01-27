import os
import json
import base64
import pytz
import barcode
from io import BytesIO
from datetime import datetime, date, timedelta, time
from barcode.writer import ImageWriter
from database import db
from .time_utils import (
    obtener_hora_colombia,
    cerrar_turno_anterior_si_pendiente
)

#from enviar_correo import enviar_correo_html # Tu archivo existente

# 1. CONFIGURACIÓN DE TIEMPO (COLOMBIA)
TIMEZONE_CO = pytz.timezone('America/Bogota')

def obtener_hora_colombia():
    return datetime.now(TIMEZONE_CO)

def obtener_rango_turno_colombia():
    ahora_co = obtener_hora_colombia()
    # Si es antes de las 6am, el día comercial es el anterior
    if ahora_co.hour < 6:
        fecha_comercial = ahora_co.date() - timedelta(days=1)
    else:
        fecha_comercial = ahora_co.date()

    inicio_local = TIMEZONE_CO.localize(datetime.combine(fecha_comercial, time(6, 0, 0)))
    fin_local = inicio_local + timedelta(days=1) - timedelta(seconds=1)
    return fecha_comercial, inicio_local.astimezone(pytz.UTC), fin_local.astimezone(pytz.UTC)

def obtener_rango_turno_por_fecha_comercial(fecha_comercial):
    inicio_local = TIMEZONE_CO.localize(datetime.combine(fecha_comercial, time(6, 0, 0)))
    fin_local = inicio_local + timedelta(days=1) - timedelta(seconds=1)
    return inicio_local.astimezone(pytz.UTC), fin_local.astimezone(pytz.UTC)

# 2. GENERACIÓN DE CÓDIGOS DE BARRAS
def generar_barcode_base64(codigo):
    if not codigo: return ""
    try:
        code128 = barcode.get_barcode_class('code128')
        instance = code128(str(codigo), writer=ImageWriter())
        buffer = BytesIO()
        instance.write(buffer)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except:
        return ""

# 3. LÓGICA DE CIERRE AUTOMÁTICO
def cerrar_turno_anterior_si_pendiente(usuario_id):
    from models import CierreCaja, Venta # Importación local para evitar círculos
    ahora_co = obtener_hora_colombia()
    if ahora_co.hour < 6: return True, "Turno activo"
    
    fecha_ayer = ahora_co.date() - timedelta(days=1)
    cierre_existente = CierreCaja.query.filter_by(fecha_cierre=fecha_ayer).first()
    
    if not cierre_existente:
        # Aquí podrías disparar la lógica de creación automática que ya tenías
        pass
    return True, "Validación completada"