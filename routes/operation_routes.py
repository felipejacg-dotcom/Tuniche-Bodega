# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request
from auth import login_required, get_current_planta, get_current_user
from db import get_connection
from datetime import datetime
from zoneinfo import ZoneInfo

operation_bp = Blueprint("operation", __name__, url_prefix="/api")

ZONA_CHILE = ZoneInfo("America/Santiago")


def _ahora_chile() -> str:
    return datetime.now(ZONA_CHILE).strftime("%Y-%m-%d %H:%M:%S")


@operation_bp.route("/registrar", methods=["POST"])
@login_required
def registrar():
    data = request.get_json() or {}

    accion = data.get("accion", "").upper().strip()
    rut = data.get("rut", "").strip()
    trabajador = data.get("trabajador", "").strip()
    area = data.get("area", "").strip()
    art_id_raw = data.get("articulo_id")

    # Validate
    if accion not in ("SALIDA", "DEVOLUCION"):
        return jsonify({"success": False, "message": "Accion invalida."}), 400

    if not rut or not trabajador or not area or art_id_raw is None:
        return jsonify({"success": False, "message": "Faltan campos obligatorios."}), 400

    try:
        art_id = int(art_id_raw)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "ID de articulo invalido."}), 400

    planta = get_current_planta()
    operador = get_current_user()
    ahora = _ahora_chile()

    conn = None
    try:
        conn = get_connection(planta)
        cur = conn.cursor()

        # Get article info
        cur.execute(
            "SELECT stock_disponible, descripcion FROM articulos WHERE id = %s",
            (art_id,),
        )
        item = cur.fetchone()

        if not item:
            return jsonify({"success": False, "message": f"Articulo ID {art_id} no existe."}), 404

        stock, descripcion = item

        if accion == "SALIDA":
            if stock <= 0:
                return jsonify({
                    "success": False,
                    "message": f"Sin stock disponible de '{descripcion}'.",
                }), 409

            cur.execute(
                "INSERT INTO transacciones "
                "(articulo_id, rut, trabajador, area, entregado_por, estado, hora_salida) "
                "VALUES (%s, %s, %s, %s, %s, 'EN TERRENO', %s)",
                (art_id, rut, trabajador, area, operador, ahora),
            )
            cur.execute(
                "UPDATE articulos SET stock_disponible = stock_disponible - 1 WHERE id = %s",
                (art_id,),
            )
            nuevo_stock = stock - 1
            msg = f"Entregado: {descripcion}"

        else:  # DEVOLUCION
            cur.execute(
                "SELECT id FROM transacciones "
                "WHERE rut = %s AND articulo_id = %s AND estado = 'EN TERRENO' "
                "ORDER BY id DESC LIMIT 1",
                (rut, art_id),
            )
            tid = cur.fetchone()

            if not tid:
                return jsonify({
                    "success": False,
                    "message": f"No hay salida pendiente de '{descripcion}' para este trabajador.",
                }), 404

            cur.execute(
                "UPDATE transacciones SET hora_entrada = %s, estado = 'DEVUELTO' WHERE id = %s",
                (ahora, tid[0]),
            )
            cur.execute(
                "UPDATE articulos SET stock_disponible = stock_disponible + 1 WHERE id = %s",
                (art_id,),
            )
            nuevo_stock = stock + 1
            msg = f"Devuelto: {descripcion}"

        conn.commit()
        cur.close()

        return jsonify({
            "success": True,
            "message": msg,
            "descripcion": descripcion,
            "nuevo_stock": nuevo_stock,
            "hora": ahora.split(" ")[1][:5],
        })

    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return jsonify({"success": False, "message": f"Error BD: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()
