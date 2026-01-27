from datetime import datetime, timedelta, time
import pytz

# 1. CONFIGURACIÓN DE ZONA HORARIA (Colombia)
TIMEZONE_CO = pytz.timezone('America/Bogota')

def obtener_hora_colombia():
    """Retorna la fecha y hora actual exacta en Colombia."""
    return datetime.now(TIMEZONE_CO)

def obtener_rango_turno_colombia():
    """
    Calcula el rango de tiempo del turno actual para la Licorera.
    Regla: El día comercial cambia a las 6:00 AM.
    Retorna: (fecha_comercial, inicio_utc, fin_utc)
    """
    ahora_co = obtener_hora_colombia()

    # Si son las 2:00 AM, el sistema entiende que es el día comercial anterior
    if ahora_co.hour < 6:
        fecha_comercial = ahora_co.date() - timedelta(days=1)
    else:
        fecha_comercial = ahora_co.date()

    # Definimos el inicio a las 06:00:00 del día comercial
    inicio_local = TIMEZONE_CO.localize(datetime.combine(fecha_comercial, time(6, 0, 0)))
    
    # El fin es 24 horas después (05:59:59 del día siguiente calendario)
    fin_local = inicio_local + timedelta(days=1) - timedelta(seconds=1)

    # Convertimos a UTC para que la base de datos no tenga confusiones
    return fecha_comercial, inicio_local.astimezone(pytz.UTC), fin_local.astimezone(pytz.UTC)

def obtener_rango_turno_por_fecha_comercial(fecha_comercial_date):
    """
    Calcula el rango UTC para una fecha específica elegida en el calendario.
    Útil para consultar reportes de días pasados.
    """
    inicio_local = TIMEZONE_CO.localize(datetime.combine(fecha_comercial_date, time(6, 0, 0)))
    fin_local = inicio_local + timedelta(days=1) - timedelta(seconds=1)

    return inicio_local.astimezone(pytz.UTC), fin_local.astimezone(pytz.UTC)

def fecha_colombia_string(valor_fecha):
    """
    Convierte una fecha de la base de datos (UTC) a un texto legible 
    con la hora de Colombia para mostrar en las tablas.
    """
    if not valor_fecha:
        return ""
    
    # Si la fecha no tiene zona horaria (naive), le asignamos UTC
    if valor_fecha.tzinfo is None:
        valor_fecha = pytz.utc.localize(valor_fecha)
    
    return valor_fecha.astimezone(TIMEZONE_CO).strftime('%d/%m/%Y %I:%M %p')
def cerrar_turno_anterior_si_pendiente(usuario_id=None):
    from models import CierreCaja
    from datetime import timedelta

    ahora_co = obtener_hora_colombia()

    # Si es antes de las 6am, el turno sigue activo
    if ahora_co.hour < 6:
        return True, "Turno activo"

    fecha_ayer = ahora_co.date() - timedelta(days=1)

    cierre_existente = CierreCaja.query.filter_by(
        fecha_cierre=fecha_ayer
    ).first()

    if cierre_existente:
        return True, "Turno anterior ya cerrado"

    # Aquí podrías crear el cierre automático si quieres
    return True, "Turno validado sin cierre automático"

print("✅ time_utils cargado correctamente")
