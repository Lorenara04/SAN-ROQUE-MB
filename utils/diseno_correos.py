def generar_html_reporte(fecha_inicio, fecha_fin, total, ingresos=0, egresos=0):
    """
    Genera el HTML profesional para el reporte de San Roque M.B.
    Se agregaron campos de Ingresos y Egresos para que sea un balance real.
    """
    # Formateamos el total con puntos de miles para que se vea profesional
    total_formateado = f"{total:,.0f}".replace(",", ".")
    ingresos_formateado = f"{ingresos:,.0f}".replace(",", ".")
    egresos_formateado = f"{egresos:,.0f}".replace(",", ".")

    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background-color:#f0f4f8; font-family:'Segoe UI',Arial,sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f0f4f8; padding: 40px 0;">
    <tr>
        <td align="center">
            <table width="550" cellpadding="0" cellspacing="0" style="background-color:#ffffff; border-radius:24px; padding:0; overflow:hidden; box-shadow:0 10px 30px rgba(0,0,0,0.08); border-top:10px solid #1e3a8a;">
                
                <tr>
                    <td align="center" style="padding: 40px 30px 20px 30px;">
                        <div style="width:70px; height:70px; border-radius:20px; background-color:#e0f2fe; color:#1e3a8a; line-height:70px; font-size:32px; text-align:center; display:inline-block;">
                            📊
                        </div>
                        <h1 style="color:#1e3a8a; margin:20px 0 5px 0; font-size:26px; letter-spacing:-1px;">
                            San Roque M.B
                        </h1>
                        <p style="color:#64748b; font-size:15px; margin:0; font-weight:500;">
                            Inteligencia de Negocios
                        </p>
                    </td>
                </tr>

                <tr>
                    <td style="padding: 0 40px;">
                        <hr style="border:0; border-top:1px solid #f1f5f9;">
                        <p style="font-size:16px; color:#334155; text-align:center; line-height:1.5; margin:25px 0;">
                            Cordial saludo. Adjuntamos el informe consolidado correspondiente al periodo solicitado.
                        </p>
                        
                        <table width="100%" style="background-color:#f8fafc; border-radius:12px; padding:15px; margin-bottom:20px;">
                            <tr>
                                <td align="center" style="font-size:13px; color:#64748b;">
                                    Desde: <strong>{fecha_inicio}</strong> &nbsp;&nbsp; Hasta: <strong>{fecha_fin}</strong>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>

                <tr>
                    <td align="center" style="padding: 10px 40px 30px 40px;">
                        <table width="100%" cellpadding="0" cellspacing="0" style="background: linear-gradient(135deg, #1e3a8a 0%, #0284c7 100%); border-radius:18px; padding:25px; text-align:center; color:#ffffff;">
                            <tr>
                                <td style="font-size:14px; opacity:0.9; text-transform:uppercase; letter-spacing:1px; font-weight:bold;">
                                    Balance Neto del Periodo
                                </td>
                            </tr>
                            <tr>
                                <td style="font-size:36px; font-weight:800; padding-top:10px;">
                                    $ {total_formateado}
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>

                <tr>
                    <td align="center" style="padding: 0 40px 40px 40px;">
                        <p style="font-size:13px; color:#94a3b8; line-height:1.4;">
                            Este documento es confidencial y fue generado automáticamente por el sistema de gestión de <strong>Licorera San Roque M.B.</strong>
                        </p>
                        <div style="margin-top:20px; font-size:12px; color:#cbd5e1; font-weight:bold; letter-spacing:1px; text-transform:uppercase;">
                            &copy; 2026 Gestión Profesional
                        </div>
                    </td>
                </tr>
            </table>
        </td>
    </tr>
</table>

</body>
</html>
"""