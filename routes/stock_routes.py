# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request, send_file
from auth import login_required, get_current_planta
from db import get_connection
from io import BytesIO
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

stock_bp = Blueprint("stock", __name__, url_prefix="/api")


def _format_hora(value):
    if value is None:
        return "---"
    if isinstance(value, datetime):
        return value.strftime("%H:%M")
    text = str(value)
    return text.split(" ")[1][:5] if " " in text else text[:5]


def _safe_pdf_text(value):
    return str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _display_planta(planta):
    return "Graneros" if planta == "TUNICHE" else planta


def _get_default_shift_range():
    now = datetime.now()
    day_start = now.replace(hour=8, minute=0, second=0, microsecond=0)
    night_start = now.replace(hour=20, minute=0, second=0, microsecond=0)

    if day_start <= now < night_start:
        shift_name = "Diurno"
        start_time = day_start
        end_time = now
    elif now >= night_start:
        shift_name = "Noche"
        start_time = night_start
        end_time = now
    else:
        shift_name = "Noche"
        start_time = night_start - timedelta(days=1)
        end_time = now
    return shift_name, start_time, end_time


def _parse_datetime(dt_str, default_val):
    if not dt_str:
        return default_val
    try:
        clean_str = dt_str.replace("T", " ")
        if len(clean_str) == 16:
            return datetime.strptime(clean_str, "%Y-%m-%d %H:%M")
        return datetime.strptime(clean_str[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return default_val


def _group_pendientes(items):
    grouped = {}
    for item in items:
        rut = item.get("rut") or ""
        trabajador = item.get("trabajador") or "Desconocido"
        area = item.get("area") or "Sin area"

        key = (rut, trabajador, area)
        if key not in grouped:
            grouped[key] = {
                "rut": rut,
                "trabajador": trabajador,
                "area": area,
                "articulos": []
            }

        val_hora = item.get("hora_salida")
        hora_str = _format_hora(val_hora)

        grouped[key]["articulos"].append({
            "articulo": item.get("articulo"),
            "hora_salida": hora_str
        })
    return list(grouped.values())


def _build_cierre_turno_data(planta, desde_str=None, hasta_str=None):
    now = datetime.now()
    def_name, def_start, def_end = _get_default_shift_range()

    start_time = _parse_datetime(desde_str, def_start)
    end_time = _parse_datetime(hasta_str, def_end)

    if 5 <= start_time.hour < 17:
        turno_name = "Diurno"
    else:
        turno_name = "Noche"

    conn = None
    try:
        conn = get_connection(planta)
        cur = conn.cursor(dictionary=True)

        # 1. Movimientos del turno: salidas o devoluciones dentro del rango de tiempo
        cur.execute("""
            SELECT t.id, t.rut, t.trabajador, t.area,
                   CONCAT(a.descripcion, ' [', a.talla, ']') AS articulo,
                   t.hora_salida, t.hora_entrada, t.estado
            FROM transacciones t
            JOIN articulos a ON t.articulo_id = a.id
            WHERE (t.hora_salida >= %s AND t.hora_salida <= %s)
               OR (t.estado = 'DEVUELTO' AND t.hora_entrada >= %s AND t.hora_entrada <= %s)
            ORDER BY COALESCE(t.hora_entrada, t.hora_salida) DESC
            LIMIT 500
        """, (start_time, end_time, start_time, end_time))
        registros = cur.fetchall()

        # 2. Pendientes del turno: entregadas en este rango que siguen EN TERRENO
        cur.execute("""
            SELECT t.rut, t.trabajador, t.area,
                   CONCAT(a.descripcion, ' [', a.talla, ']') AS articulo,
                   t.hora_salida
            FROM (
                SELECT rut, trabajador, area, articulo_id, hora_salida
                FROM transacciones
                WHERE estado = 'EN TERRENO'
                  AND hora_salida >= %s AND hora_salida <= %s
                ORDER BY hora_salida DESC
                LIMIT 300
            ) t
            JOIN articulos a ON t.articulo_id = a.id
            ORDER BY t.hora_salida DESC
        """, (start_time, end_time))
        raw_pendientes = cur.fetchall()

        # 3. Stock crítico
        cur.execute("""
            SELECT id, descripcion, talla, medida, stock_disponible, limite_alerta
            FROM articulos
            WHERE limite_alerta IS NOT NULL
              AND stock_disponible <= limite_alerta
            ORDER BY stock_disponible ASC, descripcion, talla
            LIMIT 100
        """)
        stock_critico = cur.fetchall()
        cur.close()
    finally:
        if conn:
            conn.close()

    # Formatear horas para el listado de registros
    for row in registros:
        row["hora_salida"] = _format_hora(row.get("hora_salida"))
        row["hora_entrada"] = _format_hora(row.get("hora_entrada"))

    # Calcular KPIs
    salidas_count = 0
    devoluciones_count = 0
    for r in registros:
        # Puesto que registros ya filtró por SQL, comparamos si son de este periodo
        # La comparación en SQL es suficiente, pero hacemos doble chequeo si los objetos son datetime
        h_salida = r.get("hora_salida")
        h_entrada = r.get("hora_entrada")
        # Nota: las horas ya se formatearon a string arriba. Por tanto, confiamos en la consulta SQL directamente.
        if r.get("estado") == "DEVUELTO":
            devoluciones_count += 1
        else:
            salidas_count += 1

    total_movimientos = len(registros)
    pendientes_count = len(raw_pendientes)
    trabajadores_pendientes = len({row.get("rut") for row in raw_pendientes if row.get("rut")})

    kpi = {
        "total": total_movimientos,
        "salidas": salidas_count,
        "devoluciones": devoluciones_count,
        "pendientes": pendientes_count,
        "trabajadores_pendientes": trabajadores_pendientes,
        "stock_critico": len(stock_critico),
    }

    # Agrupar pendientes
    gp_pendientes = _group_pendientes(raw_pendientes)

    # Resumen copiable en texto plano
    resumen_pendientes_lines = []
    for w in gp_pendientes[:15]:
        arts = ", ".join([f"{a['articulo']} ({a['hora_salida']})" for a in w["articulos"]])
        resumen_pendientes_lines.append(f"- {w['trabajador']} ({w['rut']}): {arts}")
    if not resumen_pendientes_lines:
        resumen_pendientes_lines = ["Sin pendientes en este turno."]
    elif len(gp_pendientes) > 15:
        resumen_pendientes_lines.append(f"... y {len(gp_pendientes) - 15} trabajadores mas.")

    stock_lines = [
        f"- {s['descripcion']} [{s.get('talla') or '-'}] stock {s['stock_disponible']} / alerta {s['limite_alerta']}"
        for s in stock_critico[:25]
    ]
    if not stock_lines:
        stock_lines = ["Sin stock critico."]
    elif len(stock_critico) > 25:
        stock_lines.append(f"... y {len(stock_critico) - 25} articulos mas.")

    rango_display = f"{start_time.strftime('%d/%m/%Y %H:%M')} a {end_time.strftime('%d/%m/%Y %H:%M')}"

    resumen_copiable = "\n".join([
        "CIERRE DE TURNO",
        f"Planta: {planta}",
        f"Turno: {turno_name}",
        f"Rango: {rango_display}",
        f"Hora generacion: {now.strftime('%H:%M')}",
        "",
        f"Movimientos turno: {kpi['total']}",
        f"Salidas turno: {kpi['salidas']}",
        f"Devoluciones turno: {kpi['devoluciones']}",
        f"Pendientes turno: {kpi['pendientes']}",
        f"Trabajadores c/ pendientes: {kpi['trabajadores_pendientes']}",
        f"Stock critico: {kpi['stock_critico']}",
        "",
        "PENDIENTES DEL TURNO",
        *resumen_pendientes_lines,
        "",
        "STOCK CRITICO",
        *stock_lines,
    ])

    return {
        "success": True,
        "fecha": now.strftime("%Y-%m-%d"),
        "fecha_display": now.strftime("%d/%m/%Y"),
        "hora_generacion": now.strftime("%H:%M"),
        "planta": planta,
        "planta_display": _display_planta(planta),
        "turno": turno_name,
        "desde": start_time.strftime("%Y-%m-%d %H:%M"),
        "desde_iso": start_time.strftime("%Y-%m-%dT%H:%M"),
        "hasta": end_time.strftime("%Y-%m-%d %H:%M"),
        "hasta_iso": end_time.strftime("%Y-%m-%dT%H:%M"),
        "kpi": kpi,
        "pendientes": gp_pendientes,
        "stock_critico": stock_critico,
        "resumen_copiable": resumen_copiable,
    }


def _build_cierre_turno_pdf(data):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title="Cierre de Turno Tuniche-Bodega",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#151515"),
        spaceAfter=3 * mm,
    ))
    styles.add(ParagraphStyle(
        name="BrandTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=13,
        textColor=colors.HexColor("#151515"),
    ))
    styles.add(ParagraphStyle(
        name="Muted",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#6b7280"),
    ))
    styles.add(ParagraphStyle(
        name="SectionTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#151515"),
        spaceBefore=4 * mm,
        spaceAfter=2 * mm,
    ))
    styles.add(ParagraphStyle(
        name="TableCell",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1f2937"),
    ))
    styles.add(ParagraphStyle(
        name="RightMuted",
        parent=styles["Muted"],
        alignment=TA_RIGHT,
    ))
    styles.add(ParagraphStyle(
        name="KpiTitle",
        parent=styles["Normal"],
        alignment=1,  # Center
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#6b7280"),
    ))
    styles.add(ParagraphStyle(
        name="KpiValue",
        parent=styles["Normal"],
        alignment=1,  # Center
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=21,
        textColor=colors.HexColor("#151515"),
    ))

    logo_path = Path(__file__).resolve().parents[1] / "static" / "logo-tuniche.png"
    header_left = [
        Paragraph("SGB LOGISTIC F.C.", styles["BrandTitle"]),
        Paragraph("Sistema de Bodega - Cierre operacional", styles["Muted"]),
    ]
    if logo_path.exists():
        aspect = 1.206896551724138
        max_w = 48 * mm
        max_h = 40 * mm
        if max_w / aspect <= max_h:
            w = max_w
            h = max_w / aspect
        else:
            h = max_h
            w = max_h * aspect
        header_left.insert(0, Image(str(logo_path), width=w, height=h))

    header_table = Table(
        [[header_left, Paragraph(f"Fecha: {data.get('fecha_display') or '-'}<br/>Generado {data.get('hora_generacion') or '--:--'}", styles["RightMuted"])]],
        colWidths=[120 * mm, 51 * mm],
    )
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    story = [
        header_table,
        Paragraph(f"Cierre de Turno — {data.get('turno', '')}", styles["ReportTitle"]),
        Paragraph(
            f"Sucursal {data.get('planta_display') or data.get('planta') or '-'} &middot; Rango: {data.get('desde') or ''} a {data.get('hasta') or ''}",
            styles["Muted"],
        ),
        Spacer(1, 5 * mm),
    ]

    kpi = data.get("kpi") or {}
    kpi_rows = [
        [
            Paragraph("Movimientos Turno", styles["KpiTitle"]),
            Paragraph("Salidas Turno", styles["KpiTitle"]),
            Paragraph("Devoluciones Turno", styles["KpiTitle"]),
        ],
        [
            Paragraph(str(kpi.get("total", 0)), styles["KpiValue"]),
            Paragraph(str(kpi.get("salidas", 0)), styles["KpiValue"]),
            Paragraph(str(kpi.get("devoluciones", 0)), styles["KpiValue"]),
        ],
        [
            Paragraph("Pendientes Turno", styles["KpiTitle"]),
            Paragraph("Trabajadores c/ Pend.", styles["KpiTitle"]),
            Paragraph("Stock Critico", styles["KpiTitle"]),
        ],
        [
            Paragraph(str(kpi.get("pendientes", 0)), styles["KpiValue"]),
            Paragraph(str(kpi.get("trabajadores_pendientes", 0)), styles["KpiValue"]),
            Paragraph(str(kpi.get("stock_critico", 0)), styles["KpiValue"]),
        ],
    ]
    kpi_table = Table(kpi_rows, colWidths=[60.6 * mm, 60.6 * mm, 60.6 * mm])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7f7f2")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9ded7")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9ded7")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([kpi_table, Spacer(1, 5 * mm)])

    def section_table(title, headers, rows, empty_text, widths, styles_to_apply=None):
        story.append(Paragraph(title, styles["SectionTitle"]))
        if not rows:
            story.append(Paragraph(empty_text, styles["Muted"]))
            story.append(Spacer(1, 2 * mm))
            return

        table_rows = [headers]
        table_rows.extend(rows)
        table = Table(table_rows, colWidths=widths, repeatRows=1)
        base_styles = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#151515")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("BACKGROUND", (0, 1), (-1, -1), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d9ded7")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]
        if styles_to_apply:
            base_styles.extend(styles_to_apply)
        table.setStyle(TableStyle(base_styles))
        story.append(table)
        story.append(Spacer(1, 3 * mm))

    # PENDIENTES DEL TURNO
    pendientes_list = data.get("pendientes") or []
    pendientes_rows = []
    p_styles = []
    row_idx = 1
    for w in pendientes_list:
        pendientes_rows.append([
            Paragraph(f"<b>{_safe_pdf_text(w['trabajador'])}</b> ({_safe_pdf_text(w['rut'])} &middot; {_safe_pdf_text(w['area'])})", styles["TableCell"]),
            "",
            ""
        ])
        p_styles.extend([
            ("SPAN", (0, row_idx), (2, row_idx)),
            ("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#f9fafb")),
            ("TOPPADDING", (0, row_idx), (-1, row_idx), 4),
            ("BOTTOMPADDING", (0, row_idx), (-1, row_idx), 4),
        ])
        row_idx += 1
        for art in w["articulos"]:
            pendientes_rows.append([
                "",
                Paragraph(_safe_pdf_text(art["articulo"]), styles["TableCell"]),
                Paragraph(_safe_pdf_text(art["hora_salida"]), styles["TableCell"])
            ])
            p_styles.append(("LEFTPADDING", (1, row_idx), (1, row_idx), 12))
            row_idx += 1

    section_table(
        "Pendientes del Turno (Entregados y No Devueltos)",
        ["Trabajador / Area", "Articulo Pendiente", "Salida (Hora)"],
        pendientes_rows,
        "Sin pendientes en este turno.",
        [75 * mm, 72 * mm, 35 * mm],
        p_styles,
    )

    # STOCK CRITICO
    stock_rows = [
        [
            Paragraph(_safe_pdf_text(item.get("id")), styles["TableCell"]),
            Paragraph(_safe_pdf_text(item.get("descripcion")), styles["TableCell"]),
            Paragraph(_safe_pdf_text(item.get("talla") or "-"), styles["TableCell"]),
            Paragraph(_safe_pdf_text(item.get("medida") or "-"), styles["TableCell"]),
            Paragraph(_safe_pdf_text(item.get("stock_disponible")), styles["TableCell"]),
            Paragraph(_safe_pdf_text(item.get("limite_alerta")), styles["TableCell"]),
        ]
        for item in (data.get("stock_critico") or [])
    ]
    section_table(
        "Stock critico",
        ["ID", "Articulo", "Talla", "Medida", "Stock", "Alerta"],
        stock_rows,
        "Sin stock critico.",
        [18 * mm, 72 * mm, 22 * mm, 23 * mm, 18 * mm, 18 * mm],
    )

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Documento generado automaticamente por Tuniche-Bodega.", styles["RightMuted"]))
    doc.build(story)
    buffer.seek(0)
    return buffer


@stock_bp.route("/articulos")
@login_required
def get_articulos():
    planta = get_current_planta()
    conn = None
    try:
        conn = get_connection(planta)
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT id, descripcion, talla, medida,
                   stock_disponible, limite_alerta
            FROM articulos
            ORDER BY descripcion, talla
        """)
        rows = cur.fetchall()
        cur.close()
        return jsonify({"success": True, "articulos": rows})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn:
            conn.close()


@stock_bp.route("/registros")
@login_required
def get_registros():
    planta = get_current_planta()
    estado = request.args.get("estado", "").strip()
    texto = request.args.get("q", "").strip()

    conn = None
    try:
        conn = get_connection(planta)
        cur = conn.cursor(dictionary=True)

        query = """
            SELECT t.id, t.rut, t.trabajador, t.area,
                   CONCAT(a.descripcion, ' [', a.talla, ']') AS articulo,
                   t.hora_salida, t.hora_entrada, t.estado
            FROM transacciones t
            JOIN articulos a ON t.articulo_id = a.id
            WHERE t.hora_salida >= CURDATE()
        """
        params = []

        if estado:
            query += " AND t.estado = %s"
            params.append(estado)

        if texto:
            query += " AND (LOWER(t.trabajador) LIKE LOWER(%s) OR t.rut LIKE %s)"
            like = f"%{texto}%"
            params.extend([like, like])

        query += " ORDER BY t.hora_salida DESC LIMIT 200"
        cur.execute(query, params)
        rows = cur.fetchall()

        # Normalize datetime fields to HH:MM string
        for r in rows:
            for k in ("hora_salida", "hora_entrada"):
                val = r[k]
                if val is None:
                    r[k] = "---"
                elif isinstance(val, datetime):
                    r[k] = val.strftime("%H:%M")
                else:
                    s = str(val)
                    r[k] = s.split(" ")[1][:5] if " " in s else s[:5]

        total = len(rows)
        en_terreno = sum(1 for r in rows if r["estado"] == "EN TERRENO")
        devueltos = sum(1 for r in rows if r["estado"] == "DEVUELTO")

        cur.close()
        return jsonify({
            "success": True,
            "registros": rows,
            "kpi": {
                "total": total,
                "en_terreno": en_terreno,
                "devueltos": devueltos,
            },
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn:
            conn.close()


@stock_bp.route("/cierre_turno")
@login_required
def get_cierre_turno():
    planta = get_current_planta()
    desde = request.args.get("desde")
    hasta = request.args.get("hasta")
    try:
        return jsonify(_build_cierre_turno_data(planta, desde, hasta))
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@stock_bp.route("/cierre_turno/pdf")
@login_required
def download_cierre_turno_pdf():
    planta = get_current_planta()
    desde = request.args.get("desde")
    hasta = request.args.get("hasta")
    try:
        data = _build_cierre_turno_data(planta, desde, hasta)
        pdf_buffer = _build_cierre_turno_pdf(data)
        filename = f"cierre-turno-{data['fecha']}-{data.get('planta_display', planta).lower().replace(' ', '-')}.pdf"
        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@stock_bp.route("/ultimo_retiro")
@login_required
def get_ultimo_retiro():
    rut = request.args.get("rut", "").strip()
    art_id_raw = request.args.get("articulo_id", "").strip()

    if not rut or not art_id_raw:
        return jsonify({"success": False, "message": "RUT y ID de articulo requeridos."}), 400

    try:
        art_id = int(art_id_raw)
    except ValueError:
        return jsonify({"success": False, "message": "ID de articulo invalido."}), 400

    planta = get_current_planta()
    conn = None
    try:
        conn = get_connection(planta)
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT hora_salida FROM transacciones "
            "WHERE rut = %s AND articulo_id = %s "
            "ORDER BY id DESC LIMIT 1",
            (rut, art_id),
        )
        row = cur.fetchone()
        cur.close()

        if row:
            from datetime import datetime
            val = row["hora_salida"]

            # Parse datetime
            if isinstance(val, str):
                try:
                    dt = datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    dt = None
            else:
                dt = val

            if dt:
                from zoneinfo import ZoneInfo
                ZONA_CHILE = ZoneInfo("America/Santiago")
                now = datetime.now(ZONA_CHILE)

                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=ZONA_CHILE)

                diff = now - dt
                dias = diff.days

                alerta = dias <= 7
                return jsonify({
                    "success": True,
                    "alerta": alerta,
                    "dias": dias,
                    "fecha": dt.strftime("%d/%m/%Y %H:%M"),
                })

        return jsonify({"success": True, "alerta": False})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error BD: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()
