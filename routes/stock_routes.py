# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request, send_file
from auth import login_required, get_current_planta
from db import get_connection
from io import BytesIO
from pathlib import Path
from datetime import datetime
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


def _build_cierre_turno_data(planta):
    now = datetime.now(ZoneInfo("America/Santiago"))
    conn = None
    try:
        conn = get_connection(planta)
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT t.id, t.rut, t.trabajador, t.area,
                   CONCAT(a.descripcion, ' [', a.talla, ']') AS articulo,
                   t.hora_salida, t.hora_entrada, t.estado
            FROM transacciones t
            JOIN articulos a ON t.articulo_id = a.id
            WHERE DATE(t.hora_salida) = CURDATE()
            ORDER BY t.hora_salida DESC
            LIMIT 500
        """)
        registros = cur.fetchall()

        cur.execute("""
            SELECT t.rut, t.trabajador, t.area,
                   CONCAT(a.descripcion, ' [', a.talla, ']') AS articulo,
                   t.hora_salida
            FROM transacciones t
            JOIN articulos a ON t.articulo_id = a.id
            WHERE t.estado = 'EN TERRENO'
            ORDER BY t.hora_salida DESC
            LIMIT 200
        """)
        pendientes = cur.fetchall()

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

    for row in registros:
        row["hora_salida"] = _format_hora(row.get("hora_salida"))
        row["hora_entrada"] = _format_hora(row.get("hora_entrada"))

    for row in pendientes:
        row["hora_salida"] = _format_hora(row.get("hora_salida"))

    salidas = len(registros)
    devoluciones = sum(1 for row in registros if row.get("estado") == "DEVUELTO")
    total_movimientos = salidas + devoluciones
    trabajadores_pendientes = len({row.get("rut") for row in pendientes if row.get("rut")})

    kpi = {
        "total": total_movimientos,
        "salidas": salidas,
        "devoluciones": devoluciones,
        "pendientes": len(pendientes),
        "trabajadores_pendientes": trabajadores_pendientes,
        "stock_critico": len(stock_critico),
    }

    pendientes_lines = [
        f"- {p['trabajador']} ({p['rut']}) | {p['articulo']} | {p.get('area') or 'Sin area'} | salida {p['hora_salida']}"
        for p in pendientes[:25]
    ]
    if not pendientes_lines:
        pendientes_lines = ["Sin pendientes en terreno."]
    elif len(pendientes) > 25:
        pendientes_lines.append(f"... y {len(pendientes) - 25} pendientes mas.")

    stock_lines = [
        f"- {s['descripcion']} [{s.get('talla') or '-'}] stock {s['stock_disponible']} / alerta {s['limite_alerta']}"
        for s in stock_critico[:25]
    ]
    if not stock_lines:
        stock_lines = ["Sin stock critico."]
    elif len(stock_critico) > 25:
        stock_lines.append(f"... y {len(stock_critico) - 25} articulos mas.")

    resumen_copiable = "\n".join([
        "CIERRE DE TURNO",
        f"Planta: {planta}",
        f"Fecha: {now.strftime('%d/%m/%Y')}",
        f"Hora generacion: {now.strftime('%H:%M')}",
        "",
        f"Movimientos: {kpi['total']}",
        f"Salidas: {kpi['salidas']}",
        f"Devoluciones: {kpi['devoluciones']}",
        f"Pendientes en terreno: {kpi['pendientes']}",
        f"Trabajadores con pendientes: {kpi['trabajadores_pendientes']}",
        f"Stock critico: {kpi['stock_critico']}",
        "",
        "PENDIENTES",
        *pendientes_lines,
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
        "kpi": kpi,
        "pendientes": pendientes,
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
        try:
            from PIL import Image as PILImage
            with PILImage.open(logo_path) as img:
                orig_w, orig_h = img.size
            aspect = orig_w / orig_h
            max_w = 42 * mm
            max_h = 20 * mm
            if max_w / aspect <= max_h:
                w = max_w
                h = max_w / aspect
            else:
                h = max_h
                w = max_h * aspect
            header_left.insert(0, Image(str(logo_path), width=w, height=h))
        except Exception:
            header_left.insert(0, Image(str(logo_path), width=28 * mm, height=13 * mm))

    header_table = Table(
        [[header_left, Paragraph(f"{data.get('fecha_display') or '-'}<br/>Generado {data.get('hora_generacion') or '--:--'}", styles["RightMuted"])]],
        colWidths=[120 * mm, 51 * mm],
    )
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    story = [
        header_table,
        Paragraph("Cierre de Turno", styles["ReportTitle"]),
        Paragraph(
            f"Sucursal {data.get('planta_display') or data.get('planta') or '-'}",
            styles["Muted"],
        ),
        Spacer(1, 5 * mm),
    ]

    kpi = data.get("kpi") or {}
    kpi_rows = [
        [
            Paragraph("Movimientos", styles["KpiTitle"]),
            Paragraph("Salidas", styles["KpiTitle"]),
            Paragraph("Devoluciones", styles["KpiTitle"]),
        ],
        [
            Paragraph(str(kpi.get("total", 0)), styles["KpiValue"]),
            Paragraph(str(kpi.get("salidas", 0)), styles["KpiValue"]),
            Paragraph(str(kpi.get("devoluciones", 0)), styles["KpiValue"]),
        ],
        [
            Paragraph("Pendientes", styles["KpiTitle"]),
            Paragraph("Trabajadores con pendientes", styles["KpiTitle"]),
            Paragraph("Stock critico", styles["KpiTitle"]),
        ],
        [
            Paragraph(str(kpi.get("pendientes", 0)), styles["KpiValue"]),
            Paragraph(str(kpi.get("trabajadores_pendientes", 0)), styles["KpiValue"]),
            Paragraph(str(kpi.get("stock_critico", 0)), styles["KpiValue"]),
        ],
    ]
    kpi_table = Table(kpi_rows, colWidths=[57 * mm, 57 * mm, 57 * mm])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7f7f2")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9ded7")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9ded7")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([kpi_table, Spacer(1, 5 * mm)])

    def section_table(title, headers, rows, empty_text, widths):
        story.append(Paragraph(title, styles["SectionTitle"]))
        if not rows:
            story.append(Paragraph(empty_text, styles["Muted"]))
            story.append(Spacer(1, 2 * mm))
            return

        table_rows = [headers]
        table_rows.extend(rows)
        table = Table(table_rows, colWidths=widths, repeatRows=1)
        table.setStyle(TableStyle([
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
        ]))
        story.append(table)
        story.append(Spacer(1, 3 * mm))

    pendientes_rows = [
        [
            Paragraph(_safe_pdf_text(item.get("trabajador")), styles["TableCell"]),
            Paragraph(_safe_pdf_text(item.get("rut")), styles["TableCell"]),
            Paragraph(_safe_pdf_text(item.get("articulo")), styles["TableCell"]),
            Paragraph(_safe_pdf_text(item.get("area") or "Sin area"), styles["TableCell"]),
            Paragraph(_safe_pdf_text(item.get("hora_salida")), styles["TableCell"]),
        ]
        for item in (data.get("pendientes") or [])
    ]
    section_table(
        "Pendientes en terreno",
        ["Trabajador", "RUT", "Articulo", "Area", "Salida"],
        pendientes_rows,
        "Sin pendientes en terreno.",
        [40 * mm, 27 * mm, 54 * mm, 30 * mm, 20 * mm],
    )

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
            WHERE DATE(t.hora_salida) = CURDATE()
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
    try:
        return jsonify(_build_cierre_turno_data(planta))
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@stock_bp.route("/cierre_turno/pdf")
@login_required
def download_cierre_turno_pdf():
    planta = get_current_planta()
    try:
        data = _build_cierre_turno_data(planta)
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
