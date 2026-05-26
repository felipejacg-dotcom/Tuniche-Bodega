# -*- coding: utf-8 -*-
from flask import Blueprint, jsonify, request
from auth import login_required, get_current_planta
from db import get_connection

worker_bp = Blueprint("worker", __name__, url_prefix="/api")


@worker_bp.route("/buscar_trabajador", methods=["POST"])
@login_required
def buscar_trabajador():
    data = request.get_json() or {}
    rut = data.get("rut", "").strip()
    planta = get_current_planta()

    if not rut:
        return jsonify({"success": False, "message": "RUT requerido."}), 400

    conn = None
    try:
        conn = get_connection(planta)
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT trabajador, area FROM transacciones "
            "WHERE rut = %s ORDER BY id DESC LIMIT 1",
            (rut,),
        )
        row = cur.fetchone()
        cur.close()

        if row:
            return jsonify({
                "success": True,
                "nombre": row["trabajador"],
                "area": row["area"],
            })
        return jsonify({"success": False, "message": "Trabajador no encontrado en historial."})

    except Exception as e:
        return jsonify({"success": False, "message": f"Error BD: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()


@worker_bp.route("/pendientes")
@login_required
def get_pendientes():
    rut = request.args.get("rut", "").strip()
    if not rut:
        return jsonify({"success": False, "message": "RUT requerido."}), 400

    planta = get_current_planta()
    conn = None
    try:
        conn = get_connection(planta)
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT t.id AS transaccion_id, t.articulo_id, "
            "CONCAT(a.descripcion, ' [', a.talla, ']') AS descripcion, "
            "t.hora_salida "
            "FROM transacciones t "
            "JOIN articulos a ON t.articulo_id = a.id "
            "WHERE t.rut = %s AND t.estado = 'EN TERRENO' "
            "ORDER BY t.hora_salida DESC",
            (rut,),
        )
        rows = cur.fetchall()
        cur.close()

        # Format datetimes
        from datetime import datetime
        for r in rows:
            val = r["hora_salida"]
            if isinstance(val, datetime):
                r["hora_salida"] = val.strftime("%d/%m/%Y %H:%M")
            else:
                r["hora_salida"] = str(val)[:16]

        return jsonify({"success": True, "pendientes": rows})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error BD: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()
