# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request, send_file
from auth import login_required, get_current_planta, get_current_user
from db import get_connection
from io import BytesIO
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import mysql.connector

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


def _parse_datetime(dt_str):
    if not dt_str:
        raise ValueError("Debes indicar fecha y hora de inicio y termino.")
    try:
        clean_str = dt_str.replace("T", " ")
        if len(clean_str) == 16:
            return datetime.strptime(clean_str, "%Y-%m-%d %H:%M")
        return datetime.strptime(clean_str[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        raise ValueError("Formato de fecha invalido. Usa fecha y hora completas.")


def _normalize_tipo_turno(tipo_turno):
    clean = (tipo_turno or "").strip().lower().replace("í", "i")
    if clean == "dia":
        return "dia", "Día"
    if clean == "noche":
        return "noche", "Noche"
    raise ValueError("Selecciona si el cierre corresponde a turno Día o Noche.")


def _validate_cierre_range(start_time, end_time):
    if start_time >= end_time:
        raise ValueError("La fecha/hora Desde debe ser anterior a Hasta.")
    if end_time - start_time > timedelta(hours=24):
        raise ValueError("El rango del cierre no puede superar 24 horas.")


def _fecha_operativa(start_time):
    return start_time.date()


def _format_dt(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    text = str(value)
    return text[:16].replace("T", " ")


def _format_fecha(value):
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10]


def _ensure_cierres_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cierres_turno (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            planta VARCHAR(32) NOT NULL,
            tipo_turno VARCHAR(16) NOT NULL,
            fecha_operativa DATE NOT NULL,
            desde DATETIME NOT NULL,
            hasta DATETIME NOT NULL,
            responsable VARCHAR(100) NOT NULL,
            hora_cierre DATETIME NOT NULL,
            total INT NOT NULL DEFAULT 0,
            salidas INT NOT NULL DEFAULT 0,
            devoluciones INT NOT NULL DEFAULT 0,
            pendientes INT NOT NULL DEFAULT 0,
            trabajadores_pendientes INT NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_cierre_turno_operativo (planta, tipo_turno, fecha_operativa)
        )
    """)


def _serialize_cierre_row(row):
    if not row:
        return None
    return {
        "id": row.get("id"),
        "planta": row.get("planta"),
        "tipo_turno": row.get("tipo_turno"),
        "fecha_operativa": _format_fecha(row.get("fecha_operativa")),
        "desde": _format_dt(row.get("desde")),
        "hasta": _format_dt(row.get("hasta")),
        "responsable": row.get("responsable") or "",
        "hora_cierre": _format_dt(row.get("hora_cierre")),
        "kpi": {
            "total": row.get("total") or 0,
            "salidas": row.get("salidas") or 0,
            "devoluciones": row.get("devoluciones") or 0,
            "pendientes": row.get("pendientes") or 0,
            "trabajadores_pendientes": row.get("trabajadores_pendientes") or 0,
        }
    }


def _get_cierre_row(cur, planta, tipo_turno, fecha_operativa):
    _ensure_cierres_table(cur)
    cur.execute("""
        SELECT id, planta, tipo_turno, fecha_operativa, desde, hasta,
               responsable, hora_cierre, total, salidas, devoluciones,
               pendientes, trabajadores_pendientes
        FROM cierres_turno
        WHERE planta = %s AND tipo_turno = %s AND fecha_operativa = %s
        LIMIT 1
    """, (planta, tipo_turno, fecha_operativa))
    return cur.fetchone()


def _group_pendientes(items):
    grouped = {}
    for item in items:
        rut = item.get("rut") or ""
        trabajador = item.get("trabajador") or "Desconocido"
        area = item.get("area") or "Sin área"

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


def _group_devoluciones(items):
    grouped = {}
    for item in items:
        rut = item.get("rut") or ""
        trabajador = item.get("trabajador") or "Desconocido"
        area = item.get("area") or "Sin área"

        key = (rut, trabajador, area)
        if key not in grouped:
            grouped[key] = {
                "rut": rut,
                "trabajador": trabajador,
                "area": area,
                "articulos": []
            }

        val_hora = item.get("hora_entrada") or item.get("hora_evento")
        hora_str = _format_hora(val_hora)

        grouped[key]["articulos"].append({
            "articulo": item.get("articulo"),
            "hora_entrada": hora_str
        })
    return list(grouped.values())


def _build_cierre_turno_data(planta, tipo_turno, desde_str, hasta_str, responsable=None):
    now = datetime.now(ZoneInfo("America/Santiago")).replace(tzinfo=None)
    turno_key, turno_name = _normalize_tipo_turno(tipo_turno)
    start_time = _parse_datetime(desde_str)
    end_time = _parse_datetime(hasta_str)
    _validate_cierre_range(start_time, end_time)
    fecha_operativa = _fecha_operativa(start_time)
    responsable = responsable or get_current_user()
    cierre_existente = None

    conn = None
    try:
        conn = get_connection(planta)
        cur = conn.cursor(dictionary=True)
        cierre_existente = _serialize_cierre_row(_get_cierre_row(cur, planta, turno_key, fecha_operativa))

        # 1. Eventos del turno. Una transaccion devuelta puede sumar como salida
        # y como devolucion si ambos eventos caen dentro del rango manual.
        cur.execute("""
            SELECT t.id, t.rut, t.trabajador, t.area,
                   CONCAT(a.descripcion, ' [', a.talla, ']') AS articulo,
                   t.hora_salida AS hora_evento,
                   'SALIDA' AS evento
            FROM transacciones t
            JOIN articulos a ON t.articulo_id = a.id
            WHERE t.hora_salida >= %s AND t.hora_salida <= %s
            ORDER BY t.hora_salida DESC
            LIMIT 500
        """, (start_time, end_time))
        salidas_eventos = cur.fetchall()

        cur.execute("""
            SELECT t.id, t.rut, t.trabajador, t.area,
                   CONCAT(a.descripcion, ' [', a.talla, ']') AS articulo,
                   t.hora_entrada AS hora_evento,
                   'DEVOLUCION' AS evento
            FROM transacciones t
            JOIN articulos a ON t.articulo_id = a.id
            WHERE t.estado = 'DEVUELTO'
              AND t.hora_entrada >= %s AND t.hora_entrada <= %s
            ORDER BY t.hora_entrada DESC
            LIMIT 500
        """, (start_time, end_time))
        devoluciones_eventos = cur.fetchall()
        eventos = salidas_eventos + devoluciones_eventos
        eventos.sort(key=lambda row: row.get("hora_evento") or datetime.min, reverse=True)
        for row in eventos:
            row["estado"] = "DEVUELTO" if row.get("evento") == "DEVOLUCION" else "EN TERRENO"
            row["hora_salida"] = row.get("hora_evento") if row.get("evento") == "SALIDA" else None
            row["hora_entrada"] = row.get("hora_evento") if row.get("evento") == "DEVOLUCION" else None
        registros = eventos

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

        cur.close()
    finally:
        if conn:
            conn.close()

    # Formatear horas para el listado de registros
    for row in registros:
        row["hora_salida"] = _format_hora(row.get("hora_salida"))
        row["hora_entrada"] = _format_hora(row.get("hora_entrada"))
        row["hora_evento"] = _format_hora(row.get("hora_evento"))

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
    }

    # Agrupar pendientes
    gp_pendientes = _group_pendientes(raw_pendientes)

    # Agrupar devoluciones
    gp_devoluciones = _group_devoluciones(devoluciones_eventos)

    # Resumen copiable en texto plano
    resumen_pendientes_lines = []
    for w in gp_pendientes[:15]:
        arts = ", ".join([f"{a['articulo']} ({a['hora_salida']})" for a in w["articulos"]])
        resumen_pendientes_lines.append(f"- {w['trabajador']} ({w['rut']}): {arts}")
    if not resumen_pendientes_lines:
        resumen_pendientes_lines = ["Sin pendientes en este turno."]
    elif len(gp_pendientes) > 15:
        resumen_pendientes_lines.append(f"... y {len(gp_pendientes) - 15} trabajadores más.")

    rango_display = f"{start_time.strftime('%d/%m/%Y %H:%M')} a {end_time.strftime('%d/%m/%Y %H:%M')}"

    resumen_copiable = "\n".join([
        "CIERRE DE TURNO",
        f"Planta: {planta}",
        f"Turno: {turno_name}",
        f"Rango: {rango_display}",
        f"Responsable: {responsable}",
        f"Hora generación: {now.strftime('%H:%M')}",
        "",
        f"Movimientos turno: {kpi['total']}",
        f"Salidas turno: {kpi['salidas']}",
        f"Devoluciones turno: {kpi['devoluciones']}",
        f"Pendientes turno: {kpi['pendientes']}",
        f"Trabajadores con pendientes: {kpi['trabajadores_pendientes']}",
        "",
        "PENDIENTES DEL TURNO",
        *resumen_pendientes_lines,
    ])

    return {
        "success": True,
        "fecha": now.strftime("%Y-%m-%d"),
        "fecha_display": now.strftime("%d/%m/%Y"),
        "fecha_operativa": fecha_operativa.strftime("%Y-%m-%d"),
        "hora_generacion": now.strftime("%H:%M"),
        "planta": planta,
        "planta_display": _display_planta(planta),
        "tipo_turno": turno_key,
        "turno": turno_name,
        "responsable": responsable,
        "cerrado": bool(cierre_existente),
        "cierre": cierre_existente,
        "desde": start_time.strftime("%Y-%m-%d %H:%M"),
        "desde_iso": start_time.strftime("%Y-%m-%dT%H:%M"),
        "hasta": end_time.strftime("%Y-%m-%d %H:%M"),
        "hasta_iso": end_time.strftime("%Y-%m-%dT%H:%M"),
        "kpi": kpi,
        "eventos": registros[:500],
        "pendientes": gp_pendientes,
        "devoluciones": gp_devoluciones,
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
            f"Sucursal {data.get('planta_display') or data.get('planta') or '-'}",
            styles["Muted"],
        ),
        Paragraph(
            f"Responsable: {_safe_pdf_text(data.get('responsable') or data.get('cierre', {}).get('responsable') or '-')}"
            f" &middot; Hora cierre: {_safe_pdf_text(data.get('cierre', {}).get('hora_cierre') or data.get('hora_generacion') or '-')}",
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
            Paragraph("Trabajadores con Pendientes", styles["KpiTitle"]),
            Paragraph("Responsable", styles["KpiTitle"]),
        ],
        [
            Paragraph(str(kpi.get("pendientes", 0)), styles["KpiValue"]),
            Paragraph(str(kpi.get("trabajadores_pendientes", 0)), styles["KpiValue"]),
            Paragraph(_safe_pdf_text(data.get("responsable") or "-"), styles["KpiValue"]),
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
        ["Trabajador / Área", "Artículo Pendiente", "Salida (Hora)"],
        pendientes_rows,
        "Sin pendientes en este turno.",
        [75 * mm, 72 * mm, 35 * mm],
        p_styles,
    )

    # DEVOLUCIONES DEL TURNO
    devoluciones_list = data.get("devoluciones") or []
    devoluciones_rows = []
    d_styles = []
    row_idx = 1
    for w in devoluciones_list:
        devoluciones_rows.append([
            Paragraph(f"<b>{_safe_pdf_text(w['trabajador'])}</b> ({_safe_pdf_text(w['rut'])} &middot; {_safe_pdf_text(w['area'])})", styles["TableCell"]),
            "",
            ""
        ])
        d_styles.extend([
            ("SPAN", (0, row_idx), (2, row_idx)),
            ("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#f0fdf4")),
            ("TOPPADDING", (0, row_idx), (-1, row_idx), 4),
            ("BOTTOMPADDING", (0, row_idx), (-1, row_idx), 4),
        ])
        row_idx += 1
        for art in w["articulos"]:
            devoluciones_rows.append([
                "",
                Paragraph(_safe_pdf_text(art["articulo"]), styles["TableCell"]),
                Paragraph(_safe_pdf_text(art["hora_entrada"]), styles["TableCell"])
            ])
            d_styles.append(("LEFTPADDING", (1, row_idx), (1, row_idx), 12))
            row_idx += 1

    section_table(
        "Devoluciones del Turno (Recibidas)",
        ["Trabajador / Área", "Artículo Devuelto", "Devolución (Hora)"],
        devoluciones_rows,
        "Sin devoluciones en este turno.",
        [75 * mm, 72 * mm, 35 * mm],
        d_styles,
    )

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Documento generado automáticamente por Tuniche-Bodega.", styles["RightMuted"]))
    doc.build(story)
    buffer.seek(0)
    return buffer


def _confirm_cierre_turno(planta, tipo_turno, desde_str, hasta_str):
    responsable = get_current_user()
    data = _build_cierre_turno_data(planta, tipo_turno, desde_str, hasta_str, responsable)

    now = datetime.now(ZoneInfo("America/Santiago")).replace(tzinfo=None)
    kpi = data.get("kpi") or {}
    conn = None
    try:
        conn = get_connection(planta)
        cur = conn.cursor(dictionary=True)
        _ensure_cierres_table(cur)
        cur.execute("""
            INSERT INTO cierres_turno (
                planta, tipo_turno, fecha_operativa, desde, hasta,
                responsable, hora_cierre, total, salidas, devoluciones,
                pendientes, trabajadores_pendientes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                desde = VALUES(desde),
                hasta = VALUES(hasta),
                responsable = VALUES(responsable),
                hora_cierre = VALUES(hora_cierre),
                total = VALUES(total),
                salidas = VALUES(salidas),
                devoluciones = VALUES(devoluciones),
                pendientes = VALUES(pendientes),
                trabajadores_pendientes = VALUES(trabajadores_pendientes)
        """, (
            planta,
            data["tipo_turno"],
            data["fecha_operativa"],
            data["desde"],
            data["hasta"],
            responsable,
            now,
            kpi.get("total", 0),
            kpi.get("salidas", 0),
            kpi.get("devoluciones", 0),
            kpi.get("pendientes", 0),
            kpi.get("trabajadores_pendientes", 0),
        ))
        conn.commit()
        cierre_row = _get_cierre_row(cur, planta, data["tipo_turno"], data["fecha_operativa"])
        cur.close()
        data["cerrado"] = True
        data["cierre"] = _serialize_cierre_row(cierre_row)
        data["responsable"] = responsable
        return data
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def _build_confirmed_cierre_data(planta, tipo_turno, desde_str, hasta_str):
    turno_key, _ = _normalize_tipo_turno(tipo_turno)
    start_time = _parse_datetime(desde_str)
    end_time = _parse_datetime(hasta_str)
    _validate_cierre_range(start_time, end_time)
    fecha_operativa = _fecha_operativa(start_time)

    conn = None
    try:
        conn = get_connection(planta)
        cur = conn.cursor(dictionary=True)
        cierre = _serialize_cierre_row(_get_cierre_row(cur, planta, turno_key, fecha_operativa))
        cur.close()
    finally:
        if conn:
            conn.close()

    if not cierre:
        raise LookupError("Primero debes confirmar el cierre de turno antes de descargar el PDF.")

    data = _build_cierre_turno_data(
        planta,
        cierre["tipo_turno"],
        cierre["desde"],
        cierre["hasta"],
        cierre.get("responsable") or get_current_user(),
    )
    data["cerrado"] = True
    data["cierre"] = cierre
    data["responsable"] = cierre.get("responsable") or data.get("responsable")
    return data


@stock_bp.route("/articulos")
@login_required
def get_articulos():
    planta = get_current_planta()
    conn = None
    try:
        conn = get_connection(planta)
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT id, codigo_material, descripcion, talla, medida,
                   stock_disponible, limite_alerta,
                   categoria, tipo_control
            FROM articulos
            ORDER BY descripcion, talla
        """)
        rows = cur.fetchall()
        cur.close()
        return jsonify({"success": True, "articulos": rows})
    except Exception as e:
        import logging
        logging.getLogger("flask.app").error("Error en get_articulos: %s", e, exc_info=True)
        return jsonify({"success": False, "message": "Ocurrió un error al obtener el catálogo de artículos."}), 500
    finally:
        if conn:
            conn.close()


@stock_bp.route("/registros")
@login_required
def get_registros():
    planta = get_current_planta()
    estado = request.args.get("estado", "").strip()
    texto = request.args.get("q", "").strip()
    desde = request.args.get("desde", "").strip()
    hasta = request.args.get("hasta", "").strip()

    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 50, type=int)
    if page < 1:
        page = 1
    if limit < 1 or limit > 200:
        limit = 50
    offset = (page - 1) * limit

    conn = None
    try:
        conn = get_connection(planta)
        cur = conn.cursor(dictionary=True)

        clauses = []
        params = []

        if estado:
            clauses.append("t.estado = %s")
            params.append(estado)

        if texto:
            clauses.append("(LOWER(t.trabajador) LIKE LOWER(%s) OR t.rut LIKE %s)")
            like = f"%{texto}%"
            params.extend([like, like])

        dt_desde = None
        if desde:
            try:
                dt_desde = _parse_datetime(desde) if ("T" in desde or " " in desde) else datetime.strptime(desde, "%Y-%m-%d")
            except ValueError:
                return jsonify({"success": False, "message": "Formato de fecha 'desde' inválido."}), 400

        dt_hasta = None
        if hasta:
            try:
                dt_hasta = _parse_datetime(hasta) if ("T" in hasta or " " in hasta) else datetime.strptime(hasta, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            except ValueError:
                return jsonify({"success": False, "message": "Formato de fecha 'hasta' inválido."}), 400

        # Si no hay filtros de fecha, limitamos por defecto a CURDATE()
        if not desde and not hasta:
            clauses.append("(t.hora_salida >= CURDATE() OR t.hora_entrada >= CURDATE())")
        else:
            if dt_desde and dt_hasta:
                clauses.append("((t.hora_salida >= %s AND t.hora_salida <= %s) OR (t.hora_entrada >= %s AND t.hora_entrada <= %s))")
                params.extend([dt_desde, dt_hasta, dt_desde, dt_hasta])
            elif dt_desde:
                clauses.append("(t.hora_salida >= %s OR t.hora_entrada >= %s)")
                params.extend([dt_desde, dt_desde])
            elif dt_hasta:
                clauses.append("(t.hora_salida <= %s OR t.hora_entrada <= %s)")
                params.extend([dt_hasta, dt_hasta])

        where_clause = " AND ".join(clauses)
        if where_clause:
            where_clause = " AND " + where_clause

        # 1. Total records count
        count_query = f"""
            SELECT COUNT(*) AS total
            FROM transacciones t
            JOIN articulos a ON t.articulo_id = a.id
            WHERE 1=1 {where_clause}
        """
        cur.execute(count_query, params)
        total_records = cur.fetchone()["total"]

        # 2. Page records
        query = f"""
            SELECT t.id, t.rut, t.trabajador, t.area,
                   CONCAT(a.descripcion, ' [', a.talla, ']') AS articulo,
                   t.hora_salida, t.hora_entrada, t.estado, IFNULL(t.cantidad, 1) AS cantidad
            FROM transacciones t
            JOIN articulos a ON t.articulo_id = a.id
            WHERE 1=1 {where_clause}
            ORDER BY COALESCE(t.hora_entrada, t.hora_salida) DESC
            LIMIT %s OFFSET %s
        """
        page_params = params + [limit, offset]
        cur.execute(query, page_params)
        rows = cur.fetchall()

        # 3. Global KPI counts for this filtered query
        kpi_query = f"""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN t.estado = 'EN TERRENO' THEN 1 ELSE 0 END) AS en_terreno,
                   SUM(CASE WHEN t.estado = 'DEVUELTO' THEN 1 ELSE 0 END) AS devueltos
            FROM transacciones t
            JOIN articulos a ON t.articulo_id = a.id
            WHERE 1=1 {where_clause}
        """
        cur.execute(kpi_query, params)
        kpi_res = cur.fetchone()

        # Normalize datetime fields
        for r in rows:
            for k in ("hora_salida", "hora_entrada"):
                val = r[k]
                if val is None:
                    r[k] = "---"
                elif isinstance(val, datetime):
                    if val.date() == datetime.today().date():
                        r[k] = val.strftime("%H:%M")
                    else:
                        r[k] = val.strftime("%d/%m %H:%M")
                else:
                    s = str(val)
                    r[k] = s.split(" ")[1][:5] if " " in s else s[:5]

        total_pages = (total_records + limit - 1) // limit
        if total_pages < 1:
            total_pages = 1

        cur.close()
        return jsonify({
            "success": True,
            "registros": rows,
            "kpi": {
                "total": kpi_res["total"] or 0,
                "en_terreno": kpi_res["en_terreno"] or 0,
                "devueltos": kpi_res["devueltos"] or 0,
            },
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "total_records": total_records
        })
    except Exception as e:
        import logging
        logging.getLogger("flask.app").error("Error en get_registros: %s", e, exc_info=True)
        return jsonify({"success": False, "message": "Ocurrió un error al obtener los registros."}), 500
    finally:
        if conn:
            conn.close()


@stock_bp.route("/cierre_turno")
@login_required
def get_cierre_turno():
    planta = get_current_planta()
    tipo_turno = request.args.get("tipo_turno")
    desde = request.args.get("desde")
    hasta = request.args.get("hasta")
    try:
        return jsonify(_build_cierre_turno_data(planta, tipo_turno, desde, hasta))
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        import logging
        logging.getLogger("flask.app").error("Error en get_cierre_turno: %s", e, exc_info=True)
        return jsonify({"success": False, "message": "Ocurrió un error al generar los datos del cierre."}), 500


@stock_bp.route("/cierre_turno", methods=["POST"])
@login_required
def post_cierre_turno():
    planta = get_current_planta()
    payload = request.get_json(silent=True) or {}
    tipo_turno = payload.get("tipo_turno")
    desde = payload.get("desde")
    hasta = payload.get("hasta")
    try:
        return jsonify(_confirm_cierre_turno(planta, tipo_turno, desde, hasta))
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"success": False, "message": str(e)}), 409
    except Exception as e:
        import logging
        logging.getLogger("flask.app").error("Error en post_cierre_turno: %s", e, exc_info=True)
        return jsonify({"success": False, "message": "Ocurrió un error al confirmar el cierre."}), 500


@stock_bp.route("/cierre_turno/pdf")
@login_required
def download_cierre_turno_pdf():
    planta = get_current_planta()
    tipo_turno = request.args.get("tipo_turno")
    desde = request.args.get("desde")
    hasta = request.args.get("hasta")
    try:
        data = _build_confirmed_cierre_data(planta, tipo_turno, desde, hasta)
        pdf_buffer = _build_cierre_turno_pdf(data)
        filename = f"cierre-turno-{data.get('tipo_turno', 'turno')}-{data['fecha']}-{data.get('planta_display', planta).lower().replace(' ', '-')}.pdf"
        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except LookupError as e:
        return jsonify({"success": False, "message": str(e)}), 409
    except Exception as e:
        import logging
        logging.getLogger("flask.app").error("Error en download_cierre_turno_pdf: %s", e, exc_info=True)
        return jsonify({"success": False, "message": "Ocurrió un error al generar el PDF del cierre."}), 500


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
        import logging
        logging.getLogger("flask.app").error("Error en get_ultimo_retiro: %s", e, exc_info=True)
        return jsonify({"success": False, "message": "Ocurrió un error al buscar el último retiro."}), 500
    finally:
        if conn:
            conn.close()
