# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request
from auth import login_required, get_current_planta
from db import get_connection
from datetime import datetime
from zoneinfo import ZoneInfo

stock_bp = Blueprint("stock", __name__, url_prefix="/api")


def _format_hora(value):
    if value is None:
        return "---"
    if isinstance(value, datetime):
        return value.strftime("%H:%M")
    text = str(value)
    return text.split(" ")[1][:5] if " " in text else text[:5]


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

        return jsonify({
            "success": True,
            "fecha": now.strftime("%Y-%m-%d"),
            "fecha_display": now.strftime("%d/%m/%Y"),
            "hora_generacion": now.strftime("%H:%M"),
            "planta": planta,
            "kpi": kpi,
            "pendientes": pendientes,
            "stock_critico": stock_critico,
            "resumen_copiable": resumen_copiable,
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn:
            conn.close()


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
