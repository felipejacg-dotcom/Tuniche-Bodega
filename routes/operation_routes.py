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
    subarea = data.get("subarea", "").strip()
    art_id_raw = data.get("articulo_id")
    cantidad_raw = data.get("cantidad")

    # Validate
    if accion not in ("SALIDA", "DEVOLUCION"):
        return jsonify({"success": False, "message": "Accion invalida."}), 400

    if art_id_raw is None:
        return jsonify({"success": False, "message": "ID de articulo requerido."}), 400

    try:
        art_id = int(art_id_raw)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "ID de articulo invalido."}), 400

    cantidad = 1
    if cantidad_raw is not None:
        try:
            cantidad = int(cantidad_raw)
            if cantidad <= 0:
                raise ValueError()
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Cantidad invalida."}), 400

    planta = get_current_planta()
    operador = get_current_user()
    ahora = _ahora_chile()

    conn = None
    try:
        conn = get_connection(planta)
        cur = conn.cursor()

        # Get article info: lock row only if it is a SALIDA
        if accion == "SALIDA":
            cur.execute(
                "SELECT stock_disponible, descripcion, IFNULL(categoria, 'EPP'), IFNULL(tipo_control, 'RETORNABLE') "
                "FROM articulos WHERE id = %s FOR UPDATE",
                (art_id,),
            )
        else:
            cur.execute(
                "SELECT stock_disponible, descripcion, IFNULL(categoria, 'EPP'), IFNULL(tipo_control, 'RETORNABLE') "
                "FROM articulos WHERE id = %s",
                (art_id,),
            )
        item = cur.fetchone()

        if not item:
            return jsonify({"success": False, "message": f"Articulo ID {art_id} no existe."}), 404

        stock, descripcion, categoria, tipo_control = item
        categoria = str(categoria or "EPP").upper()
        tipo_control = str(tipo_control or "RETORNABLE").upper()

        if accion == "SALIDA":
            if categoria != 'CONSUMO_LIQUIDO':
                if not rut or not trabajador:
                    return jsonify({"success": False, "message": "RUT y Trabajador son obligatorios para EPP / Herramienta."}), 400
            else:
                rut = rut or 'CONSUMO'
                trabajador = trabajador or 'Consumo interno'

            if not area or not subarea:
                return jsonify({"success": False, "message": "El area y la subarea son obligatorias."}), 400

            if stock <= 0:
                return jsonify({
                    "success": False,
                    "message": f"Sin stock disponible de '{descripcion}'.",
                }), 409

            if stock < cantidad:
                return jsonify({
                    "success": False,
                    "message": f"Stock insuficiente de '{descripcion}'. Disponible: {stock}.",
                }), 409

            estado_salida = 'CONSUMIDO' if tipo_control == 'CONSUMIBLE' else 'EN TERRENO'

            cur.execute(
                "INSERT INTO transacciones "
                "(articulo_id, rut, trabajador, area, subarea, entregado_por, cantidad, estado, hora_salida) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (art_id, rut, trabajador, area, subarea, operador, cantidad, estado_salida, ahora),
            )
            cur.execute(
                "UPDATE articulos SET stock_disponible = stock_disponible - %s WHERE id = %s",
                (cantidad, art_id),
            )
            nuevo_stock = stock - cantidad
            msg = f"Entregado: {descripcion}"

        else:  # DEVOLUCION
            if not rut or not trabajador or not area or not subarea:
                return jsonify({"success": False, "message": "Faltan campos obligatorios para devolucion (incluyendo subarea)."}), 400

            if tipo_control == 'CONSUMIBLE':
                return jsonify({
                    "success": False,
                    "message": f"Los registros consumibles ('{descripcion}') no se devuelven ni reponen stock.",
                }), 400

            cur.execute(
                "SELECT id, IFNULL(cantidad, 1) FROM transacciones "
                "WHERE rut = %s AND articulo_id = %s AND estado = 'EN TERRENO' "
                "ORDER BY id DESC LIMIT 1 FOR UPDATE",
                (rut, art_id),
            )
            tid_row = cur.fetchone()

            if not tid_row:
                return jsonify({
                    "success": False,
                    "message": f"No hay salida pendiente de '{descripcion}' para este trabajador.",
                }), 404

            tid, cant_transaccion = tid_row
            cant_transaccion = int(cant_transaccion or 1)

            cur.execute(
                "UPDATE transacciones SET hora_entrada = %s, estado = 'DEVUELTO' WHERE id = %s",
                (ahora, tid),
            )
            cur.execute(
                "UPDATE articulos SET stock_disponible = stock_disponible + %s WHERE id = %s",
                (cant_transaccion, art_id),
            )
            nuevo_stock = stock + cant_transaccion
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
        import logging
        logging.getLogger("flask.app").error("Error en registrar: %s", e, exc_info=True)
        return jsonify({"success": False, "message": "Ocurrió un error en la base de datos al registrar la operación."}), 500
    finally:
        if conn:
            conn.close()


@operation_bp.route("/registrar_masivo", methods=["POST"])
@login_required
def registrar_masivo():
    data = request.get_json() or {}

    rut = data.get("rut", "").strip()
    trabajador = data.get("trabajador", "").strip()
    area = data.get("area", "").strip()
    subarea = data.get("subarea", "").strip()
    articulos_data = data.get("articulos")
    articulo_ids_raw = data.get("articulo_ids")

    items_to_process = []
    if isinstance(articulos_data, list) and len(articulos_data) > 0:
        for item in articulos_data:
            try:
                art_id = int(item.get("id"))
                qty = int(item.get("cantidad", 1))
                if qty <= 0:
                    raise ValueError()
                items_to_process.append({"id": art_id, "cantidad": qty})
            except (TypeError, ValueError):
                return jsonify({"success": False, "message": "Datos de articulos invalidos en la lista."}), 400
    elif isinstance(articulo_ids_raw, list) and len(articulo_ids_raw) > 0:
        for x in articulo_ids_raw:
            try:
                items_to_process.append({"id": int(x), "cantidad": 1})
            except (TypeError, ValueError):
                return jsonify({"success": False, "message": "IDs de articulo invalidos."}), 400
    else:
        return jsonify({"success": False, "message": "Campos obligatorios invalidos o vacios."}), 400

    # Sort items_to_process by id to prevent deadlocks when locking
    items_to_process.sort(key=lambda x: x["id"])

    planta = get_current_planta()
    operador = get_current_user()
    ahora = _ahora_chile()

    conn = None
    try:
        conn = get_connection(planta)
        cur = conn.cursor()

        processed_items = []
        requires_worker = False

        for item in items_to_process:
            art_id = item["id"]
            qty = item["cantidad"]

            cur.execute(
                "SELECT stock_disponible, descripcion, IFNULL(categoria, 'EPP'), IFNULL(tipo_control, 'RETORNABLE') "
                "FROM articulos WHERE id = %s FOR UPDATE",
                (art_id,),
            )
            res = cur.fetchone()
            if not res:
                conn.rollback()
                cur.close()
                return jsonify({"success": False, "message": f"Articulo ID {art_id} no existe."}), 404

            stock, descripcion, categoria, tipo_control = res
            categoria = str(categoria or "EPP").upper()
            tipo_control = str(tipo_control or "RETORNABLE").upper()

            if categoria != 'CONSUMO_LIQUIDO' and tipo_control != 'CONSUMIBLE':
                requires_worker = True

            if stock <= 0:
                conn.rollback()
                cur.close()
                return jsonify({"success": False, "message": f"Sin stock disponible de '{descripcion}'."}), 409

            if stock < qty:
                conn.rollback()
                cur.close()
                return jsonify({"success": False, "message": f"Stock insuficiente de '{descripcion}'. Disponible: {stock}."}), 409

            processed_items.append({
                "id": art_id,
                "cantidad": qty,
                "descripcion": descripcion,
                "categoria": categoria,
                "tipo_control": tipo_control,
                "nuevo_stock": stock - qty
            })

        if requires_worker:
            if not rut or not trabajador:
                conn.rollback()
                cur.close()
                return jsonify({"success": False, "message": "RUT y Trabajador son obligatorios para EPP / Herramienta."}), 400
        else:
            rut = rut or 'CONSUMO'
            trabajador = trabajador or 'Consumo interno'

        if not area or not subarea:
            conn.rollback()
            cur.close()
            return jsonify({"success": False, "message": "El area y la subarea son obligatorias."}), 400

        entregados = []
        for p in processed_items:
            estado_salida = 'CONSUMIDO' if p["tipo_control"] == 'CONSUMIBLE' else 'EN TERRENO'
            cur.execute(
                "INSERT INTO transacciones "
                "(articulo_id, rut, trabajador, area, subarea, entregado_por, cantidad, estado, hora_salida) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (p["id"], rut, trabajador, area, subarea, operador, p["cantidad"], estado_salida, ahora),
            )
            cur.execute(
                "UPDATE articulos SET stock_disponible = stock_disponible - %s WHERE id = %s",
                (p["cantidad"], p["id"]),
            )
            entregados.append({
                "id": p["id"],
                "descripcion": p["descripcion"],
                "nuevo_stock": p["nuevo_stock"],
            })

        conn.commit()
        cur.close()

        nombres = [item["descripcion"] for item in entregados]
        msg = f"Entregados ({len(nombres)}): " + ", ".join(nombres)

        return jsonify({
            "success": True,
            "message": msg,
            "entregados": entregados,
            "hora": ahora.split(" ")[1][:5],
        })

    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        import logging
        logging.getLogger("flask.app").error("Error en registrar_masivo: %s", e, exc_info=True)
        return jsonify({"success": False, "message": "Ocurrió un error en la base de datos al registrar la entrega masiva."}), 500
    finally:
        if conn:
            conn.close()
