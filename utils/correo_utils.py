# utils/correo_utils.py

import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

def enviar_correo(destinatario, asunto, html, adjuntos=None):
    """
    destinatario: string (correo destino)
    asunto: string
    html: contenido HTML del correo
    adjuntos: lista de dicts -> [{filename, content}]
    """

    try:
        smtp_server = os.getenv("MAIL_SERVER")
        smtp_port = int(os.getenv("MAIL_PORT"))
        email_user = os.getenv("MAIL_USERNAME")
        email_pass = os.getenv("MAIL_PASSWORD")

        if not smtp_server or not smtp_port:
            return False, "Servidor SMTP no configurado"

        msg = EmailMessage()
        msg["From"] = email_user
        msg["To"] = destinatario
        msg["Subject"] = asunto

        # Texto plano fallback
        msg.set_content("Este correo contiene un reporte adjunto.")

        # HTML principal
        msg.add_alternative(html, subtype="html")

        # Adjuntar archivos
        if adjuntos:
            for adj in adjuntos:
                msg.add_attachment(
                    adj["content"],
                    maintype="application",
                    subtype="pdf",
                    filename=adj["filename"]
                )

        # CONEXIÓN SSL DIRECTA
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(email_user, email_pass)
            server.send_message(msg)

        return True, None

    except Exception as e:
        return False, str(e)
