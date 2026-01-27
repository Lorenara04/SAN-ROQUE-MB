import barcode
from barcode.writer import ImageWriter
import os

def generar_ticket_barcode(codigo_texto, nombre_producto="producto"):
    """
    Genera un archivo PNG con el código de barras para impresión física.
    Los archivos se guardarán en una carpeta llamada 'etiquetas'.
    """
    try:
        # 1. Crear carpeta si no existe
        if not os.path.exists('etiquetas'):
            os.makedirs('etiquetas')

        # 2. Configurar el tipo de código (Code128 es el estándar industrial)
        EAN = barcode.get_barcode_class('code128')
        
        # 3. Generar el objeto del código
        # Agregamos el nombre del producto como texto debajo si es necesario
        codigo = EAN(codigo_texto, writer=ImageWriter())

        # 4. Guardar el archivo
        nombre_archivo = f"etiquetas/barcode_{nombre_producto.replace(' ', '_')}"
        path_final = codigo.save(nombre_archivo)
        
        print(f"✅ Etiqueta generada con éxito: {path_final}")
        return path_final

    except Exception as e:
        print(f"❌ Error al generar código de barras: {e}")
        return None

if __name__ == "__main__":
    # Ejemplo de uso manual:
    print("--- Generador de Etiquetas Licorera ---")
    cod = input("Ingrese el código (ej: 770123456): ")
    nom = input("Nombre del licor: ")
    generar_ticket_barcode(cod, nom)